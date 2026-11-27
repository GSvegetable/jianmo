"""Isosurface extraction from a sampled distance field.

Surface Nets is used instead of Marching Cubes: its dual construction
produces a much cleaner, near-manifold mesh with no ambiguous cases, and it
gives quad faces that triangulate far more evenly.

Reference: "Surface Nets" by Mikola Lysenko, and the dual formulation of the
standard marching-cubes isosurface.
"""

from __future__ import annotations

import numpy as np

# corner bit layout: bit0 = +x, bit1 = +y, bit2 = +z
CORNERS = np.array([
    [0, 0, 0], [1, 0, 0], [0, 1, 0], [1, 1, 0],
    [0, 0, 1], [1, 0, 1], [0, 1, 1], [1, 1, 1],
], dtype=np.int64)

# the 12 cube edges as pairs of corner indices
EDGES = [
    (0, 1), (2, 3), (4, 5), (6, 7),   # along x
    (0, 2), (1, 3), (4, 6), (5, 7),   # along y
    (0, 4), (1, 5), (2, 6), (3, 7),   # along z
]


def surface_nets(field: np.ndarray, origin, spacing: float):
    """Extract the zero level set of ``field``.

    ``field`` has shape (nx+1, ny+1, nz+1) and holds signed distances
    (negative inside the surface). Returns (vertices, quads) where quads
    are index quadruples.
    """
    field = np.ascontiguousarray(field, dtype=np.float64)
    nx, ny, nz = field.shape[0] - 1, field.shape[1] - 1, field.shape[2] - 1
    origin = np.asarray(origin, dtype=np.float64)

    inside = field < 0.0

    # corner signs for every cell
    corner_sign = np.empty((nx, ny, nz, 8), dtype=bool)
    for ci, (dx, dy, dz) in enumerate(CORNERS):
        corner_sign[..., ci] = inside[dx:nx + dx, dy:ny + dy, dz:nz + dz]

    crosses = corner_sign.any(axis=3) & ~corner_sign.all(axis=3)
    ci, cj, ck = np.nonzero(crosses)
    count = ci.shape[0]
    if count == 0:
        return np.zeros((0, 3)), np.zeros((0, 4), dtype=np.int64)

    # corner distances for the surface cells only
    cd = np.empty((count, 8), dtype=np.float64)
    for ci_idx, (dx, dy, dz) in enumerate(CORNERS):
        cd[:, ci_idx] = field[ci + dx, cj + dy, ck + dz]

    # vertex position: mean of the zero crossings on the cell's edges
    local = np.zeros((count, 3), dtype=np.float64)
    hits = np.zeros(count, dtype=np.float64)
    for a, b in EDGES:
        da = cd[:, a]
        db = cd[:, b]
        edge_cross = (da < 0.0) != (db < 0.0)
        denom = da - db
        t = np.where(np.abs(denom) > 1e-12, da / np.where(np.abs(denom) > 1e-12, denom, 1.0), 0.5)
        t = np.clip(t, 0.0, 1.0)
        offset = CORNERS[a][None, :] + t[:, None] * (CORNERS[b] - CORNERS[a])[None, :]
        local += np.where(edge_cross[:, None], offset, 0.0)
        hits += edge_cross
    hits = np.maximum(hits, 1.0)[:, None]
    local /= hits

    verts = origin + (np.stack([ci, cj, ck], axis=1) + local) * spacing

    # vertex id per cell
    cell_id = np.full(nx * ny * nz, -1, dtype=np.int64)
    flat = (ci * ny + cj) * nz + ck
    cell_id[flat] = np.arange(count, dtype=np.int64)

    def vid(i, j, k):
        i = np.asarray(i)
        j = np.asarray(j)
        k = np.asarray(k)
        valid = (i >= 0) & (i < nx) & (j >= 0) & (j < ny) & (k >= 0) & (k < nz)
        out = np.full(i.shape, -1, dtype=np.int64)
        if valid.any():
            f = (i[valid] * ny + j[valid]) * nz + k[valid]
            out[valid] = cell_id[f]
        return out, valid

    quads = []

    # ---- edges along x: grid points (i,j,k) -> (i+1,j,k)
    i, j, k = np.nonzero(inside[:nx, :, :] != inside[1:nx + 1, :, :])
    if i.size:
        a = vid(i, j - 1, k - 1)[0]
        b = vid(i, j, k - 1)[0]
        c = vid(i, j, k)[0]
        d = vid(i, j - 1, k)[0]
        good = (a >= 0) & (b >= 0) & (c >= 0) & (d >= 0)
        flip = field[i, j, k] > 0
        quads.append((a, b, c, d, good, flip))

    # ---- edges along y: grid points (i,j,k) -> (i,j+1,k)
    i, j, k = np.nonzero(inside[:, :ny, :] != inside[:, 1:ny + 1, :])
    if i.size:
        a = vid(i - 1, j, k - 1)[0]
        b = vid(i, j, k - 1)[0]
        c = vid(i, j, k)[0]
        d = vid(i - 1, j, k)[0]
        good = (a >= 0) & (b >= 0) & (c >= 0) & (d >= 0)
        flip = field[i, j, k] < 0
        quads.append((a, d, c, b, good, flip))

    # ---- edges along z: grid points (i,j,k) -> (i,j,k+1)
    i, j, k = np.nonzero(inside[:, :, :nz] != inside[:, :, 1:nz + 1])
    if i.size:
        a = vid(i - 1, j - 1, k)[0]
        b = vid(i, j - 1, k)[0]
        c = vid(i, j, k)[0]
        d = vid(i - 1, j, k)[0]
        good = (a >= 0) & (b >= 0) & (c >= 0) & (d >= 0)
        flip = field[i, j, k] > 0
        quads.append((a, b, c, d, good, flip))

    if not quads:
        return verts, np.zeros((0, 4), dtype=np.int64)

    all_a, all_b, all_c, all_d = [], [], [], []
    for a, b, c, d, good, flip in quads:
        a, b, c, d = a[good], b[good], c[good], d[good]
        f = flip[good]
        b2, d2 = np.where(f[:, None], d[:, None], b[:, None]), np.where(f[:, None], b[:, None], d[:, None])
        all_a.append(a)
        all_b.append(b2[:, 0])
        all_c.append(c)
        all_d.append(d2[:, 0])
    quad_arr = np.stack([np.concatenate(all_a), np.concatenate(all_b),
                         np.concatenate(all_c), np.concatenate(all_d)], axis=1)
    return verts, quad_arr


def field_gradient(field: np.ndarray, origin, spacing: float, points: np.ndarray) -> np.ndarray:
    """Gradient of the field at arbitrary points (central differences)."""
    nx, ny, nz = field.shape[0] - 1, field.shape[1] - 1, field.shape[2] - 1
    g = np.gradient(field, spacing, edge_order=1)
    rel = (np.asarray(points) - np.asarray(origin)) / spacing
    idx = np.clip(np.rint(rel).astype(np.int64), 0, np.array([nx, ny, nz]))
    grad = np.stack([g[0][idx[:, 0], idx[:, 1], idx[:, 2]],
                     g[1][idx[:, 0], idx[:, 1], idx[:, 2]],
                     g[2][idx[:, 0], idx[:, 1], idx[:, 2]]], axis=1)
    ln = np.linalg.norm(grad, axis=1, keepdims=True)
    ln[ln == 0] = 1.0
    return grad / ln
