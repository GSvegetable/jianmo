"""Cloth garments that are fitted to the body.

A sailor collar is a piece of cloth that *lies on* the shoulders; it is not
a blob bolted to the chest.  Modelling it as a separate primitive makes it
read as an applied object, and it leaves the ugly voxelised fringe that a
thin separate shell produces against the body.

So the surface is derived from the body instead.  The distance field is
probed along a ring of rays at every height to find where the body surface
actually is, and the cloth is offset a few millimetres outwards from that
curve.  The collar then follows the shoulder line and the chest exactly,
its outer edge is a clean curve, and the transition between collar and
uniform stays crisp because the two are separate objects with separate
materials.
"""

from __future__ import annotations

import math

import numpy as np

from .character import MAT
from .mesh import Mesh, blade, solidify_patch, superellipsoid

TAU = math.pi * 2.0


# --------------------------------------------------------------------------
# probing the body
# --------------------------------------------------------------------------
def probe_radius_map(field, phis: np.ndarray, ys: np.ndarray,
                     r_max: float = 0.36, samples: int = 240) -> np.ndarray:
    """Outermost body radius along a ray for every (height, azimuth) pair.

    ``phi`` is measured from the front (+Z) towards +X, matching the
    convention used by the hair and the legacy collar patch.  The returned
    array has shape ``(len(ys), len(phis))``.
    """
    r = np.linspace(0.0, r_max, samples)
    sin_p = np.sin(phis)
    cos_p = np.cos(phis)
    out = np.zeros((len(ys), len(phis)))

    for i, y in enumerate(ys):
        x = r[:, None] * sin_p[None, :]
        z = r[:, None] * cos_p[None, :]
        pts = np.stack([x, np.full_like(x, y), z], axis=-1).reshape(-1, 3)
        f = field.evaluate(pts, cull=False).reshape(samples, len(phis))

        inside = f < 0.0
        # the outermost negative -> positive crossing along the ray
        trans = inside[:-1] & ~inside[1:]
        has = trans.any(axis=0)
        idx = (samples - 2) - np.argmax(trans[::-1], axis=0)

        lo = np.where(has, r[np.maximum(idx, 0)], 0.0)
        hi = np.where(has, r[np.minimum(idx + 1, samples - 1)], 0.0)
        for _ in range(22):
            mid = 0.5 * (lo + hi)
            pts = np.stack([mid * sin_p, np.full_like(mid, y), mid * cos_p],
                           axis=-1)
            inside_mid = field.evaluate(pts, cull=False) < 0.0
            lo = np.where(inside_mid, mid, lo)
            hi = np.where(inside_mid, hi, mid)
        out[i] = 0.5 * (lo + hi)
    return out


def probe_front_z(field, x: float, y: float, z_max: float = 0.30,
                  samples: int = 240) -> float:
    """Z of the front-most body surface on the vertical line (x, y)."""
    z = np.linspace(-0.02, z_max, samples)
    pts = np.stack([np.full_like(z, x), np.full_like(z, y), z], axis=-1)
    f = field.evaluate(pts, cull=False)
    inside = f < 0.0
    trans = inside[:-1] & ~inside[1:]
    if not trans.any():
        return float(z[0])
    idx = (samples - 2) - int(np.argmax(trans[::-1]))
    lo, hi = float(z[idx]), float(z[idx + 1])
    for _ in range(24):
        mid = 0.5 * (lo + hi)
        if field.evaluate(np.array([[x, y, mid]]), cull=False)[0] < 0.0:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


class _RadiusMap:
    """Bilinear lookup into the probed radius table."""

    def __init__(self, radius: np.ndarray, phis: np.ndarray, ys: np.ndarray):
        self.r = radius
        self.phis = phis
        self.ys = ys
        self.dp = phis[1] - phis[0]
        self.dy = ys[1] - ys[0]

    def __call__(self, y, phi):
        y = np.asarray(y, dtype=np.float64)
        phi = np.mod(np.asarray(phi, dtype=np.float64), TAU)
        fy = np.clip((y - self.ys[0]) / self.dy, 0.0, self.ys.shape[0] - 1.0001)
        fp = np.mod(phi / self.dp, self.phis.shape[0])
        i0 = np.floor(fy).astype(int)
        j0 = np.floor(fp).astype(int)
        j1 = (j0 + 1) % self.phis.shape[0]
        ty = fy - i0
        tp = fp - j0
        r00 = self.r[i0, j0]
        r01 = self.r[i0, j1]
        r10 = self.r[i0 + 1, j0]
        r11 = self.r[i0 + 1, j1]
        return ((1 - ty) * ((1 - tp) * r00 + tp * r01)
                + ty * ((1 - tp) * r10 + tp * r11))


# --------------------------------------------------------------------------
# the sailor collar
# --------------------------------------------------------------------------
def _hem_y(phi: np.ndarray) -> np.ndarray:
    """Height of the collar hem: highest at the front, lowest at the back."""
    front = np.cos(phi)
    return (1.142 - 0.102 * np.maximum(0.0, -front)
            - 0.047 * np.abs(np.sin(phi)) ** 2.0)


def _flare(phi: np.ndarray, v: np.ndarray) -> np.ndarray:
    """How far the cloth stands away from the body, per point.

    The collar lies flat at the front, where it frames the chest, and lifts
    away towards the back, where it hangs as a cape over the shoulder
    blades.
    """
    front = np.cos(phi)
    w = np.maximum(0.0, -front) + 0.42 * np.abs(np.sin(phi))
    return 0.050 * np.power(np.clip(v, 0.0, 1.0), 1.8) * np.power(w, 0.85)


def _collar_grid(radius: _RadiusMap, v_rows: int, u_cols: int,
                 y_top: float, offset: float = 0.0,
                 v_range=(0.0, 1.0)):
    """Sample the collar surface.

    The front of the collar is cut away in a V: the two edges start wide
    apart at the neck and converge towards the knot at the chest, which is
    what makes a sailor collar read as a sailor collar.
    """
    v0, v1 = v_range
    grid = np.zeros((v_rows, u_cols, 3))
    for i in range(v_rows):
        v = v0 + (v1 - v0) * (i / max(v_rows - 1, 1))
        edge = 0.62 * np.power(max(1.0 - v, 0.0), 1.5) + 0.10
        u = np.linspace(0.0, 1.0, u_cols)
        phi = edge + (TAU - 2.0 * edge) * u
        y = y_top + (_hem_y(phi) - y_top) * v
        r = radius(y, phi) + offset + _flare(phi, v)
        grid[i, :, 0] = r * np.sin(phi)
        grid[i, :, 1] = y
        grid[i, :, 2] = r * np.cos(phi)
    return grid


def _orient(grid: np.ndarray) -> np.ndarray:
    """Flip the grid if its normal points inwards."""
    du = np.gradient(grid, axis=0)
    dv = np.gradient(grid, axis=1)
    nrm = np.cross(du, dv)
    radial = np.stack([grid[:, :, 0], np.zeros_like(grid[:, :, 0]),
                       grid[:, :, 2]], axis=-1)
    ln = np.linalg.norm(radial, axis=2, keepdims=True)
    ln[ln == 0] = 1.0
    radial = radial / ln
    if float(np.sum(nrm * radial)) < 0.0:
        return grid[:, ::-1, :]
    return grid


def build_sailor_collar(field, spec) -> list:
    """The white sailor collar with its navy hem stripe."""
    phis = np.linspace(0.0, TAU, 84, endpoint=False)
    ys = np.linspace(0.995, 1.226, 52)
    radius = _RadiusMap(probe_radius_map(field, phis, ys), phis, ys)

    grid = _orient(_collar_grid(radius, 20, 72, 1.212))
    collar = solidify_patch(grid, 0.012, MAT["collar"], "collar")

    # the double navy stripe that runs along the hem of every sailor collar
    stripe = _orient(_collar_grid(radius, 4, 72, 1.212, offset=0.0075,
                                   v_range=(0.865, 1.0)))
    hem = solidify_patch(stripe, 0.007, MAT["uniform"], "collar_stripe")
    return [collar, hem]


def build_knot(spec) -> list:
    """The ribbon at the bottom of the V: two loops, a knot and two tails."""
    front = 0.158
    parts = []

    knot = superellipsoid(0.026, 0.019, 0.015, 0.40, 28, 18,
                          MAT["tie"], "knot")
    parts.append(knot.translated((0.0, 1.134, front + 0.002)))

    for side in (-1, 1):
        loop = superellipsoid(0.042, 0.024, 0.010, 0.32, 30, 18,
                              MAT["tie"], "bow_loop")
        loop = loop.rotated("y", side * 18.0).rotated("x", -6.0)
        parts.append(loop.translated((side * 0.042, 1.139, front - 0.004)))

        path = np.array([
            [side * 0.012, 1.126, front + 0.002],
            [side * 0.030, 1.104, front - 0.005],
            [side * 0.043, 1.078, front - 0.018],
        ])
        widths = [0.030, 0.028, 0.020]
        parts.append(blade(path, widths, thickness=0.006, mat=MAT["tie"],
                           name="bow_tail"))
    return parts


def build_uniform_details(field, spec) -> list:
    """Every cloth part that is not part of the blended body field."""
    return build_sailor_collar(field, spec) + build_knot(spec)
