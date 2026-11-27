"""Signed distance field primitives and smooth booleans.

This is the backbone of the character pipeline: instead of placing separate
meshes next to each other (which reads as "glued together"), every body
volume is expressed as a distance field and combined with a *smooth* boolean
so limbs grow out of the torso rather than intersecting it.

Distances are evaluated on flat (N, 3) arrays of points.
"""

from __future__ import annotations

import math

import numpy as np

FAR = 1.0e3


# --------------------------------------------------------------------------
# base
# --------------------------------------------------------------------------
class Part:
    """A distance field primitive with a material tag and a bounding sphere.

    ``material=None`` marks a boolean helper that must not influence the
    material lookup.
    """

    def __init__(self, material: int | None = 0, name: str = ""):
        self.material = material
        self.name = name
        self.center = np.zeros(3)
        self.radius = math.inf

    def _raw(self, p: np.ndarray) -> np.ndarray:
        raise NotImplementedError

    def distance(self, p: np.ndarray) -> np.ndarray:
        """Signed distance, culled to the bounding sphere."""
        d = self._raw(p)
        return d

    def distance_culled(self, p: np.ndarray, blend: float = 0.0,
                        cull: bool = True) -> np.ndarray:
        """Distance with points outside the influence radius pushed to FAR.

        The bounding-sphere shortcut is a performance trick only. It must be
        switched off wherever the *gradient* of the field matters: the field
        would jump at the culling shell and produce a ring of broken
        normals around every primitive.
        """
        if not cull or not np.isfinite(self.radius):
            return self._raw(p)
        reach = self.radius + blend + 0.02
        far = np.linalg.norm(p - self.center, axis=1) > reach
        if not far.any():
            return self._raw(p)
        out = np.full(p.shape[0], FAR)
        keep = ~far
        out[keep] = self._raw(p[keep])
        return out

    def bounds(self) -> tuple:
        return self.center, self.radius


def _smin(a: np.ndarray, b: np.ndarray, k: float) -> np.ndarray:
    """Polynomial smooth minimum (Quilez)."""
    if k <= 0.0:
        return np.minimum(a, b)
    h = np.maximum(k - np.abs(a - b), 0.0) / k
    return np.minimum(a, b) - h * h * k * 0.25


def _smax(a: np.ndarray, b: np.ndarray, k: float) -> np.ndarray:
    """Polynomial smooth maximum."""
    if k <= 0.0:
        return np.maximum(a, b)
    h = np.maximum(k - np.abs(a - b), 0.0) / k
    return np.maximum(a, b) + h * h * k * 0.25


# --------------------------------------------------------------------------
# primitives
# --------------------------------------------------------------------------
class Sphere(Part):
    def __init__(self, center, radius: float, material: int = 0, name: str = ""):
        super().__init__(material, name)
        self.c = np.asarray(center, dtype=np.float64)
        self.r = float(radius)
        self.center = self.c
        self.radius = self.r

    def _raw(self, p):
        return np.linalg.norm(p - self.c, axis=1) - self.r


class Ellipsoid(Part):
    """Approximate ellipsoid distance (standard scaled-sphere estimate)."""

    def __init__(self, center, radii, material: int = 0, name: str = ""):
        super().__init__(material, name)
        self.c = np.asarray(center, dtype=np.float64)
        self.r = np.asarray(radii, dtype=np.float64)
        self.center = self.c
        self.radius = float(np.linalg.norm(self.r))

    def _raw(self, p):
        q = (p - self.c) / self.r
        k0 = np.linalg.norm(q, axis=1)
        k1 = np.linalg.norm(q / self.r, axis=1)
        k1[k1 == 0.0] = 1.0
        return k0 * (k0 - 1.0) / k1


class Capsule(Part):
    """Round cone / capsule between two points with optional taper."""

    def __init__(self, a, b, r0: float, r1: float | None = None,
                 material: int = 0, name: str = ""):
        super().__init__(material, name)
        self.a = np.asarray(a, dtype=np.float64)
        self.b = np.asarray(b, dtype=np.float64)
        self.r0 = float(r0)
        self.r1 = float(r0 if r1 is None else r1)
        mid = (self.a + self.b) * 0.5
        half = (self.b - self.a) * 0.5
        self.center = mid
        self.radius = float(np.linalg.norm(half)) + max(self.r0, self.r1)

    def _raw(self, p):
        ba = self.b - self.a
        pa = p - self.a
        denom = float(np.dot(ba, ba))
        if denom < 1e-12:
            return np.linalg.norm(pa, axis=1) - self.r0
        h = np.clip((pa @ ba) / denom, 0.0, 1.0)
        d = pa - ba * h[:, None]
        radius = self.r0 + (self.r1 - self.r0) * h
        return np.linalg.norm(d, axis=1) - radius


class RoundBox(Part):
    def __init__(self, center, half_extents, rounding: float = 0.0,
                 material: int = 0, name: str = ""):
        super().__init__(material, name)
        self.c = np.asarray(center, dtype=np.float64)
        self.e = np.asarray(half_extents, dtype=np.float64)
        self.r = float(rounding)
        self.center = self.c
        self.radius = float(np.linalg.norm(self.e)) + self.r

    def _raw(self, p):
        q = np.abs(p - self.c) - self.e + self.r
        outside = np.linalg.norm(np.maximum(q, 0.0), axis=1)
        inside = np.minimum(np.max(q, axis=1), 0.0)
        return outside + inside - self.r


class Torus(Part):
    def __init__(self, center, major: float, minor: float,
                 material: int = 0, name: str = ""):
        super().__init__(material, name)
        self.c = np.asarray(center, dtype=np.float64)
        self.R = float(major)
        self.r = float(minor)
        self.center = self.c
        self.radius = self.R + self.r

    def _raw(self, p):
        q = p - self.c
        ring = np.linalg.norm(np.column_stack([q[:, 0], q[:, 2]]), axis=1) - self.R
        return np.linalg.norm(np.column_stack([ring, q[:, 1]]), axis=1) - self.r


class PolygonExtrude(Part):
    """Extrude a 2D polygon (XZ plane) along Y with optional bevel."""

    def __init__(self, outline, depth: float, center=(0.0, 0.0, 0.0),
                 material: int = 0, name: str = ""):
        super().__init__(material, name)
        pts = np.asarray(outline, dtype=np.float64)
        self.pts = pts
        self.depth = float(depth)
        self.c = np.asarray(center, dtype=np.float64)
        lo = pts.min(axis=0)
        hi = pts.max(axis=0)
        self.center = self.c + np.array([(lo[0] + hi[0]) * 0.5, 0.0, (lo[1] + hi[1]) * 0.5])
        self.radius = float(np.linalg.norm(np.maximum(hi - lo, 0.0))) + self.depth

    def _sd2d(self, p):
        pts = self.pts
        q = p[:, [0, 2]] - self.c[[0, 2]]
        n = pts.shape[0]
        best = np.full(q.shape[0], 1e9)
        sign = np.ones(q.shape[0])
        for i in range(n):
            a = pts[i]
            b = pts[(i + 1) % n]
            e = b - a
            w = q - a
            denom = float(np.dot(e, e))
            if denom < 1e-12:
                d = np.linalg.norm(w, axis=1)
                closest = np.repeat(a[None, :], q.shape[0], axis=0)
            else:
                t = np.clip((w @ e) / denom, 0.0, 1.0)
                closest = a[None, :] + t[:, None] * e[None, :]
                d = np.linalg.norm(q - closest, axis=1)
            best = np.minimum(best, d)
            # winding sign via the cross product with the edge
            cross = e[0] * w[:, 1] - e[1] * w[:, 0]
            sign = np.where(cross < 0, -1.0, sign)
        return sign * best

    def _raw(self, p):
        d2 = self._sd2d(p)
        dy = np.abs(p[:, 1] - self.c[1]) - self.depth
        return np.maximum(d2, dy)


class Shell(Part):
    """Hollow shell between two parts (outer minus inner)."""

    def __init__(self, outer: Part, inner: Part, material: int | None = 0, name: str = ""):
        super().__init__(material, name)
        self.outer = outer
        self.inner = inner
        self.center = outer.center
        self.radius = outer.radius

    def _raw(self, p):
        return np.maximum(self.outer._raw(p), -self.inner._raw(p))


class Compound(Part):
    """Combine parts with an intersection (max of their distances).

    Used to trim one sub-shape without touching the rest of the field --
    applying such a cut globally would delete whole regions of the body.
    """

    def __init__(self, parts, material: int | None = 0, name: str = ""):
        super().__init__(material, name)
        self.parts = list(parts)
        centers = np.array([p.center for p in self.parts])
        radii = np.array([p.radius for p in self.parts])
        self.center = centers.mean(axis=0)
        self.radius = float(radii.max()) + float(np.linalg.norm(centers - self.center, axis=1).max())

    def _raw(self, p):
        d = self.parts[0]._raw(p)
        for part in self.parts[1:]:
            d = np.maximum(d, part._raw(p))
        return d


class Transform(Part):
    """Rigid transform applied to a part."""

    def __init__(self, part: Part, matrix):
        super().__init__(part.material, part.name)
        self.part = part
        self.m = np.asarray(matrix, dtype=np.float64).reshape(4, 4)
        inv = np.linalg.inv(self.m)
        self.inv = inv
        self.center = part.center
        self.radius = part.radius

    def _raw(self, p):
        local = p @ self.inv[:3, :3].T + self.inv[:3, 3]
        return self.part._raw(local)


class HalfSpace(Part):
    """Keeps the side the normal points away from."""

    def __init__(self, normal, offset: float, material: int = 0, name: str = ""):
        super().__init__(material, name)
        n = np.asarray(normal, dtype=np.float64)
        self.n = n / max(np.linalg.norm(n), 1e-12)
        self.offset = float(offset)
        self.center = self.n * self.offset
        self.radius = 1.0e4

    def _raw(self, p):
        return (p - self.center) @ self.n


class PlaneCut(Part):
    """Half space used to trim other parts (negated for intersection)."""

    def __init__(self, normal, offset: float, material: int = 0, name: str = ""):
        super().__init__(material, name)
        n = np.asarray(normal, dtype=np.float64)
        self.n = n / max(np.linalg.norm(n), 1e-12)
        self.offset = float(offset)
        self.center = self.n * self.offset
        self.radius = 1.0e4

    def _raw(self, p):
        return -((p - self.center) @ self.n)


class FlutedCone(Part):
    """A cone whose radius ripples with the azimuth -- skirt pleats."""

    def __init__(self, apex_top, apex_bottom, r_top, r_bottom, flutes: int = 16,
                 depth: float = 0.010, material: int = 0, name: str = ""):
        super().__init__(material, name)
        self.a = np.asarray(apex_top, dtype=np.float64)
        self.b = np.asarray(apex_bottom, dtype=np.float64)
        self.r_top = float(r_top)
        self.r_bottom = float(r_bottom)
        self.flutes = float(flutes)
        self.depth = float(depth)
        mid = (self.a + self.b) * 0.5
        self.center = mid
        self.radius = float(np.linalg.norm(self.b - self.a)) * 0.5 + max(self.r_top, self.r_bottom)

    def _raw(self, p):
        base = Capsule(self.a, self.b, self.r_top, self.r_bottom)._raw(p)
        ang = np.arctan2(p[:, 2], p[:, 0])
        ripple = np.sin(ang * self.flutes)
        return base - self.depth * ripple


# --------------------------------------------------------------------------
# field assembly
# --------------------------------------------------------------------------
class Field:
    """A collection of parts grouped by material.

    Parts inside a group are combined with a *smooth* minimum, so a limb
    grows out of the torso instead of being planted next to it. Groups are
    then combined with a hard minimum: clothing has a real edge against
    skin, and keeping that edge crisp also keeps the per-vertex material
    lookup unambiguous (no speckling along the boundary).
    """

    def __init__(self):
        self.groups: dict = {}       # material -> [(part, blend_k)]

    def add(self, part: Part, blend: float = 0.0, group=None):
        key = part.material if group is None else group
        if key is None:
            raise ValueError("a part without material must name its group")
        self.groups.setdefault(key, []).append((part, float(blend)))
        return part

    def group(self, material: int):
        return self.groups.setdefault(material, [])

    def _group_field(self, entries, p, cull: bool = True):
        d = None
        for part, k in entries:
            di = part.distance_culled(p, k, cull)
            d = di if d is None else _smin(d, di, k)
        return d

    def evaluate(self, p: np.ndarray, cull: bool = True) -> np.ndarray:
        d = None
        for entries in self.groups.values():
            dg = self._group_field(entries, p, cull)
            d = dg if d is None else np.minimum(d, dg)
        if d is None:
            raise ValueError("empty field")
        return d

    def material_at(self, p: np.ndarray, cull: bool = False) -> np.ndarray:
        """Material of the group that owns the surface at each point.

        The lookup uses the *hard* minimum of each group rather than its
        smooth union. Smooth blending inside a group pulls the field down
        where limbs merge, which would let skin win against a garment that
        sits only a centimetre away; the hard distance keeps the two
        clearly separated.
        """
        best = np.full(p.shape[0], np.inf)
        out = np.zeros(p.shape[0], dtype=np.int64)
        for material, entries in self.groups.items():
            gd = None
            for part, _k in entries:
                di = part.distance_culled(p, 0.0, cull)
                gd = di if gd is None else np.minimum(gd, di)
            closer = gd < best
            best = np.where(closer, gd, best)
            out = np.where(closer, material, out)
        return out
