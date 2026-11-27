"""Character body as a signed distance field.

The body is defined as one continuous field: limbs are blended into the
torso with a smooth minimum instead of being placed as separate meshes, so
the extracted surface is a single watertight shell that reads as a sculpted
form rather than as assembled primitives.

Hair and instruments stay as regular meshes -- they are separate objects
that overlap the body in any hand-authored model too.
"""

from __future__ import annotations

import math

import numpy as np

from .character import (
    ANKLE_Y, HEAD_CY, HEAD_RX, HEAD_RY, HEAD_RZ, HIP_X, HIP_Y, KNEE_Y, MAT,
    SHOULDER_X, head_surface, pose_for,
)
from .mesh import Mesh, smooth_material_labels, taubin_smooth
from .sdf import (
    Capsule, Ellipsoid, Field, FlutedCone, Shell,
)
from .surface_nets import surface_nets


def _lerp(a, b, t):
    return a + (b - a) * t


def build_field(spec) -> Field:
    """Assemble the whole body into a single distance field."""
    field = Field()
    pose = pose_for(spec)

    skin = MAT["skin"]
    uniform = MAT["uniform"]
    sock = MAT["sock"]
    shoe = MAT["shoe"]

    # ---------------------------------------------------------------- head
    field.add(Ellipsoid((0, HEAD_CY, 0), (HEAD_RX, HEAD_RY, HEAD_RZ), skin, "head"), 0.0)
    field.add(Ellipsoid((0, 1.248, 0.040), (0.120, 0.070, 0.112), skin, "jaw"), 0.018)
    field.add(Capsule((0, 1.160, 0.0), (0, 1.262, 0.0), 0.055, 0.060, skin, "neck"), 0.018)

    # --------------------------------------------------------------- torso
    field.add(Ellipsoid((0, 1.112, 0), (0.150, 0.150, 0.108), skin, "chest"), 0.020)
    field.add(Ellipsoid((0, 0.968, 0), (0.122, 0.135, 0.092), skin, "waist"), 0.020)
    field.add(Ellipsoid((0, 0.868, 0), (0.134, 0.120, 0.098), skin, "hips"), 0.020)

    # --------------------------------------------------------------- arms
    for side, key in ((-1, "left"), (1, "right")):
        shoulder, elbow, wrist = pose[key]
        s = np.asarray(shoulder)
        e = np.asarray(elbow)
        w = np.asarray(wrist)
        field.add(Capsule(s, e, 0.052, 0.044, skin, "upper_arm"), 0.018)
        field.add(Capsule(e, w, 0.044, 0.033, skin, "forearm"), 0.012)

        direction = w - e
        direction = direction / max(np.linalg.norm(direction), 1e-12)
        hand_c = w + direction * 0.028
        field.add(Ellipsoid(hand_c, (0.034, 0.040, 0.026), skin, "hand"), 0.008)
        thumb_c = hand_c + np.array([-side * 0.024, 0.004, 0.008])
        field.add(Capsule(thumb_c, thumb_c + direction * 0.020, 0.012, 0.009, skin, "thumb"), 0.008)

    # --------------------------------------------------------------- legs
    for side in (-1, 1):
        hip = np.array([side * HIP_X, HIP_Y, 0.0])
        knee = np.array([side * (HIP_X + 0.006), KNEE_Y, 0.006])
        ankle = np.array([side * (HIP_X + 0.010), ANKLE_Y, 0.0])
        field.add(Capsule(hip, knee, 0.064, 0.050, skin, "thigh"), 0.018)
        field.add(Capsule(knee, ankle, 0.048, 0.034, skin, "shin"), 0.012)

    # ------------------------------------------------------------- uniform
    # Every garment is a *shell* whose wall straddles the skin it covers.
    # A garment built as a solid sitting on top of the skin would leave two
    # surfaces a few cells apart; the extractor then puts one vertex in a
    # cell crossed by both sheets and the triangles flip. A shell that cuts
    # through the skin consumes the hidden surface and leaves exactly one.
    def garment_shell(outer, inner, name):
        return Shell(outer, inner, None, name)

    field.add(garment_shell(
        Ellipsoid((0, 1.112, 0), (0.175, 0.175, 0.133), None, "top_outer"),
        Ellipsoid((0, 1.112, 0), (0.134, 0.134, 0.092), None, "top_inner"),
        "top_chest"), 0.006, group=uniform)
    field.add(garment_shell(
        Ellipsoid((0, 0.968, 0), (0.147, 0.160, 0.117), None, "top_outer"),
        Ellipsoid((0, 0.968, 0), (0.106, 0.119, 0.076), None, "top_inner"),
        "top_waist"), 0.006, group=uniform)
    field.add(garment_shell(
        Ellipsoid((0, 0.892, 0), (0.159, 0.145, 0.123), None, "top_outer"),
        Ellipsoid((0, 0.892, 0), (0.118, 0.104, 0.082), None, "top_inner"),
        "top_hip"), 0.006, group=uniform)

    for side, key in ((-1, "left"), (1, "right")):
        shoulder, elbow, wrist = pose[key]
        s = np.asarray(shoulder)
        e = np.asarray(elbow)
        field.add(garment_shell(
            Capsule(s, s + (e - s) * 0.62, 0.066, 0.060, None, "sleeve_outer"),
            Capsule(s, s + (e - s) * 0.62, 0.036, 0.032, None, "sleeve_inner"),
            "sleeve"), 0.006, group=uniform)

    # pleated skirt: a hollow fluted cone
    outer = FlutedCone((0, 0.912, 0), (0, 0.664, 0), 0.126, 0.192,
                       flutes=16, depth=0.007, material=uniform, name="skirt")
    inner = FlutedCone((0, 0.912, 0), (0, 0.664, 0), 0.108, 0.174,
                       flutes=16, depth=0.007, material=None, name="skirt_inner")
    field.add(Shell(outer, inner, None, "skirt"), 0.010, group=uniform)

    # -------------------------------------------------------------- socks
    for side in (-1, 1):
        # the sock is a shell around the shin, not a sleeve pulled over it
        field.add(Shell(
            Capsule((side * 0.064, 0.300, 0.0), (side * 0.064, 0.140, 0.0),
                    0.056, 0.049, None, "sock_outer"),
            Capsule((side * 0.064, 0.300, 0.0), (side * 0.064, 0.140, 0.0),
                    0.030, 0.026, None, "sock_inner"),
            sock, "sock"), 0.005)

        # a loafers silhouette: rounded toe box, a low heel and a thin sole
        field.add(Ellipsoid((side * 0.064, 0.046, 0.028),
                            (0.049, 0.040, 0.082), shoe, "shoe"), 0.010)
        field.add(Ellipsoid((side * 0.064, 0.030, -0.036),
                            (0.043, 0.032, 0.028), shoe, "heel"), 0.010)
        field.add(Ellipsoid((side * 0.064, 0.013, 0.026),
                            (0.051, 0.013, 0.086), shoe, "sole"), 0.006)

    # The sailor collar and the ribbon are *not* part of the blended field:
    # they are cloth laid over the uniform, and building them as field
    # primitives turned them into volumes that swallowed the shoulders.
    # They are generated from the body surface instead (see garment.py).

    # ---------------------------------------------------------------- face
    # Fine facial features stay in the mesh layer: at the sampling step used
    # for the body they are thinner than one voxel and would break apart.

    return field


def sample_field(field: Field, bounds, spacing: float, slab: int = 48):
    """Sample the field onto a regular grid.

    The grid is evaluated in slabs along X: a full grid of a few million
    points does not fit in memory together with the temporaries each
    distance evaluation needs.
    """
    lo = np.asarray(bounds[0], dtype=np.float64)
    hi = np.asarray(bounds[1], dtype=np.float64)
    counts = np.maximum(np.ceil((hi - lo) / spacing).astype(int) + 1, 2)
    axes = [lo[k] + np.arange(counts[k]) * spacing for k in range(3)]
    values = np.empty((counts[0], counts[1], counts[2]), dtype=np.float64)

    yz = np.stack(np.meshgrid(axes[1], axes[2], indexing="ij"), axis=-1).reshape(-1, 2)
    for x0 in range(0, counts[0], slab):
        x1 = min(x0 + slab, counts[0])
        pts = np.empty((x1 - x0, yz.shape[0], 3), dtype=np.float64)
        pts[..., 0] = axes[0][x0:x1, None]
        pts[..., 1] = yz[None, :, 0]
        pts[..., 2] = yz[None, :, 1]
        values[x0:x1] = field.evaluate(
            pts.reshape(-1, 3)).reshape(x1 - x0, counts[1], counts[2])
        del pts
    return values, lo, spacing


def field_normal(field: Field, points: np.ndarray, eps: float = 0.0025) -> np.ndarray:
    """Exact surface normal via central differences on the distance field.

    Sampling the gradient from the voxel grid would quantise it to the cell
    grid and make the shading break into visible facets, so the continuous
    field is differentiated directly at every vertex. Bounding-sphere
    culling is disabled here: the culling shell is a discontinuity in the
    field and would leave a ring of broken normals around each primitive.
    """
    p = np.asarray(points, dtype=np.float64)
    grad = np.empty_like(p)
    for axis in range(3):
        step = np.zeros(3)
        step[axis] = eps
        grad[:, axis] = (field.evaluate(p + step, cull=False)
                         - field.evaluate(p - step, cull=False))
    ln = np.linalg.norm(grad, axis=1, keepdims=True)
    ln[ln == 0] = 1.0
    return grad / ln


def _project_to_isosurface(field: Field, values, origin, spacing, verts,
                           iterations: int = 3) -> np.ndarray:
    """Pull extracted vertices back onto the zero level set.

    Surface Nets places a vertex at the average of the edge crossings in a
    cell, which is only accurate to about one cell. Left uncorrected the
    error bands into visible concentric rings across a curved surface.
    One Newton step along the field gradient removes it.
    """
    nx, ny, nz = values.shape[0] - 1, values.shape[1] - 1, values.shape[2] - 1
    grad = np.gradient(values, spacing, edge_order=1)
    v = np.asarray(verts, dtype=np.float64).copy()

    for _ in range(iterations):
        f = field.evaluate(v, cull=False)
        idx = np.clip(np.rint((v - origin) / spacing).astype(np.int64), 0,
                      np.array([nx, ny, nz]))
        g = np.stack([grad[0][idx[:, 0], idx[:, 1], idx[:, 2]],
                      grad[1][idx[:, 0], idx[:, 1], idx[:, 2]],
                      grad[2][idx[:, 0], idx[:, 1], idx[:, 2]]], axis=1)
        g2 = (g * g).sum(axis=1, keepdims=True)
        g2[g2 == 0] = 1.0
        v = v - (f[:, None] / g2) * g
    return v


def _fix_winding(field: Field, mesh: Mesh) -> Mesh:
    """Make every triangle face outwards, judged by the field gradient.

    The dual mesh produced by Surface Nets can end up with inconsistent
    winding where the surface is thin or where two sheets cross a cell.
    A triangle facing inwards is culled by the renderer and shows up as a
    speck of missing surface, so the winding is corrected against the
    gradient of the distance field, which always points outwards.
    """
    tris = mesh.f
    if tris.shape[0] == 0:
        return mesh
    a, b, c = mesh.v[tris[:, 0]], mesh.v[tris[:, 1]], mesh.v[tris[:, 2]]
    fn = np.cross(b - a, c - a)
    centroids = mesh.v[tris].mean(axis=1)
    grad = field_normal(field, centroids)
    flip = np.sum(fn * grad, axis=1) < 0.0
    if flip.any():
        tris = tris.copy()
        tris[flip] = tris[flip][:, [0, 2, 1]]
    return Mesh(mesh.v, tris, mesh.n, mesh.mat, mesh.uv, mesh.name)


def extract_body(spec, spacing: float = 0.008, smooth: int = 4):
    """Build the SDF body and extract it into a mesh with materials.

    Returns (mesh, per_vertex_material_indices, cloth_parts).  The cloth
    parts are the garments that are laid over the uniform rather than
    blended into it; they are fitted to the body surface that was just
    extracted.
    """
    field = build_field(spec)
    bounds = ((-0.36, -0.03, -0.40), (0.36, 1.82, 0.40))
    values, origin, sp = sample_field(field, bounds, spacing)

    verts, quads = surface_nets(values, origin, sp)
    if verts.shape[0] == 0:
        raise RuntimeError("empty extraction")

    verts = _project_to_isosurface(field, values, origin, sp, verts)

    tris = np.empty((quads.shape[0] * 2, 3), dtype=np.int64)
    tris[0::2] = quads[:, [0, 1, 2]]
    tris[1::2] = quads[:, [0, 2, 3]]

    body = Mesh(verts, tris, None, 0, None, "body")
    if smooth:
        body = taubin_smooth(body, iterations=smooth)

    normals = field_normal(field, body.v)
    body = _fix_winding(field, body)
    # Classify the material slightly *inside* the surface. A garment sits
    # only about a centimetre off the skin, which is the same order as the
    # extraction error, so testing on the exact vertex position would flip
    # the colour of scattered vertices. Pushing in along the normal breaks
    # that tie reliably.
    mats = field.material_at(body.v - normals * 0.0045)
    mats = smooth_material_labels(body, mats, rounds=4)

    uvs = np.stack([
        (body.v[:, 0] - body.v[:, 0].min()) / max(np.ptp(body.v[:, 0]), 1e-9),
        (body.v[:, 1] - body.v[:, 1].min()) / max(np.ptp(body.v[:, 1]), 1e-9),
    ], axis=1)

    from .garment import build_uniform_details

    cloth = build_uniform_details(field, spec)

    return Mesh(body.v, body.f, normals, 0, uvs, "body"), mats, cloth
