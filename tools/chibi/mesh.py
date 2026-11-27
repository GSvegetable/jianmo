"""Procedural mesh kernel for the JIANMO chibi character pipeline.

Pure numpy: no third-party 3D dependency is needed to rebuild the four
character GLB assets from source. Every primitive is deterministic, so
running the build twice yields byte-identical output.

Conventions
-----------
* Right-handed, Y-up. The character faces +Z.
* Faces are triangle soup stored as an (M, 3) int array.
* Winding is counter-clockwise seen from outside, so normals point outward.
* Every primitive carries analytic per-vertex normals. Hard creases are
  produced by emitting separate primitives with their own vertices, which
  keeps topology clean without a post-process splitting pass.
* Each primitive carries a material slot index.
"""

from __future__ import annotations

import math

import numpy as np

TAU = math.pi * 2.0


# --------------------------------------------------------------------------
# container
# --------------------------------------------------------------------------
class Mesh:
    """A triangle mesh with per-vertex normals, UVs and a material slot."""

    __slots__ = ("v", "f", "n", "mat", "uv", "name")

    def __init__(self, verts, faces, normals=None, mat=0, uv=None, name=""):
        self.v = np.ascontiguousarray(verts, dtype=np.float64).reshape(-1, 3)
        self.f = np.ascontiguousarray(faces, dtype=np.int64).reshape(-1, 3)
        self.n = None if normals is None else np.ascontiguousarray(normals, dtype=np.float64).reshape(-1, 3)
        self.mat = int(mat)
        self.uv = None if uv is None else np.ascontiguousarray(uv, dtype=np.float64).reshape(-1, 2)
        self.name = name

    # -- introspection -------------------------------------------------
    @property
    def tri_count(self) -> int:
        return int(self.f.shape[0])

    @property
    def vert_count(self) -> int:
        return int(self.v.shape[0])

    def bounds(self):
        """Return (min_corner, max_corner) of the mesh bounds."""
        return self.v.min(axis=0), self.v.max(axis=0)

    # -- rigid / affine transforms (functional, each returns a new Mesh)
    def translated(self, delta) -> "Mesh":
        return self.transformed(_translation(delta))

    def rotated(self, axis, degrees) -> "Mesh":
        return self.transformed(_rotation(axis, degrees))

    def scaled(self, scale) -> "Mesh":
        return self.transformed(_scaling(scale))

    def transformed(self, matrix: np.ndarray) -> "Mesh":
        m = np.asarray(matrix, dtype=np.float64).reshape(4, 4)
        nv = self.v @ m[:3, :3].T + m[:3, 3]
        nn = None if self.n is None else self.n @ m[:3, :3].T
        return Mesh(nv, self.f, nn, self.mat, self.uv, self.name)

    def with_material(self, mat: int) -> "Mesh":
        return Mesh(self.v, self.f, self.n, mat, self.uv, self.name)

    def copy(self) -> "Mesh":
        return Mesh(self.v.copy(), self.f.copy(),
                    None if self.n is None else self.n.copy(),
                    self.mat, None if self.uv is None else self.uv.copy(), self.name)

    def assign_uv(self, uv) -> "Mesh":
        return Mesh(self.v, self.f, self.n, self.mat, uv, self.name)

    def warp(self, fn) -> "Mesh":
        """Apply a per-vertex deformation; normals are rebuilt afterwards."""
        nv = fn(self.v)
        return smooth_normals(Mesh(nv, self.f, None, self.mat, self.uv, self.name))

    def mirror_x(self) -> "Mesh":
        """Mirror the mesh across the YZ plane, flipping winding."""
        m = np.eye(4)
        m[0, 0] = -1.0
        nv = self.v @ m[:3, :3].T
        nf = self.f[:, ::-1].copy()
        nn = None if self.n is None else -self.n @ m[:3, :3].T
        return Mesh(nv, nf, nn, self.mat, self.uv, self.name)

    def flip_normals(self) -> "Mesh":
        """Mirror the mesh through the XZ plane and reverse winding."""
        m = np.eye(4)
        m[0, 0] = -1.0
        nv = self.v @ m[:3, :3].T + m[:3, 3]
        nf = self.f[:, ::-1].copy()
        nn = None if self.n is None else -self.n @ m[:3, :3].T
        return Mesh(nv, nf, nn, self.mat, self.uv, self.name)


# --------------------------------------------------------------------------
# affine helpers
# --------------------------------------------------------------------------
def _translation(d) -> np.ndarray:
    m = np.eye(4)
    m[:3, 3] = np.asarray(d, dtype=np.float64)
    return m


def _scaling(s) -> np.ndarray:
    m = np.eye(4)
    sx, sy, sz = (s, s, s) if np.isscalar(s) else s
    m[0, 0], m[1, 1], m[2, 2] = float(sx), float(sy), float(sz)
    return m


def _rotation(axis, degrees) -> np.ndarray:
    """Right-handed rotation matrix about a principal axis."""
    ang = math.radians(float(degrees))
    c, s = math.cos(ang), math.sin(ang)
    m = np.eye(4)
    if axis == "x":
        m[1, 1], m[1, 2] = c, -s
        m[2, 1], m[2, 2] = s, c
    elif axis == "y":
        m[0, 0], m[0, 2] = c, s
        m[2, 0], m[2, 2] = -s, c
    elif axis == "z":
        m[0, 0], m[0, 1] = c, -s
        m[1, 0], m[1, 1] = s, c
    else:
        raise ValueError(f"unknown axis {axis!r}")
    return m


def trs(translate=(0, 0, 0), rotate=(0, 0, 0), scale=(1, 1, 1)) -> np.ndarray:
    """Compose translate * Rz * Ry * Rx * scale into a single 4x4 matrix."""
    rx, ry, rz = rotate
    return (_translation(translate)
            @ _rotation("z", rz)
            @ _rotation("y", ry)
            @ _rotation("x", rx)
            @ _scaling(scale))


# --------------------------------------------------------------------------
# merging
# --------------------------------------------------------------------------
def merge(meshes) -> Mesh:
    """Concatenate meshes into one, preserving per-part material slots."""
    meshes = [m for m in meshes if m is not None and m.vert_count > 0]
    if not meshes:
        return Mesh(np.zeros((0, 3)), np.zeros((0, 3), dtype=np.int64))
    verts, faces, norms, uvs = [], [], [], []
    offset = 0
    has_uv = all(m.uv is not None for m in meshes)
    has_n = all(m.n is not None for m in meshes)
    for m in meshes:
        verts.append(m.v)
        faces.append(m.f + offset)
        if has_n:
            norms.append(m.n)
        if has_uv:
            uvs.append(m.uv)
        offset += m.vert_count
    return Mesh(
        np.concatenate(verts, axis=0),
        np.concatenate(faces, axis=0),
        np.concatenate(norms, axis=0) if has_n else None,
        meshes[0].mat,
        np.concatenate(uvs, axis=0) if has_uv else None,
        "merged",
    )


def merge_by_material(meshes) -> list:
    """Group parts by material slot so the exporter can build primitives."""
    buckets: dict = {}
    for m in meshes:
        if m is None or m.vert_count == 0:
            continue
        buckets.setdefault(m.mat, []).append(m)
    out = []
    for mat in sorted(buckets):
        out.append(merge(buckets[mat]))
    return out


def split_by_material(mesh: Mesh, vertex_materials) -> list:
    """Split a mesh with per-vertex materials into one mesh per material."""
    mats = np.asarray(vertex_materials)
    tri = mats[mesh.f]
    # Majority vote over the three vertices of a face -- never the *mean*
    # of their slot indices.  Averaging skin (0) with uniform (9) yields
    # 4.5, which rounds to 4: the iris slot.  Every triangle straddling a
    # material border would then be painted with an unrelated colour.
    a, b, c = tri[:, 0], tri[:, 1], tri[:, 2]
    face_mats = a.copy()
    face_mats = np.where((b == a) | (b == c), b, face_mats)
    face_mats = np.where((c == a) | (c == b), c, face_mats)
    out = []
    for mat in np.unique(face_mats):
        sel = np.nonzero(face_mats == mat)[0]
        faces = mesh.f[sel]
        used = np.unique(faces)
        remap = np.full(mesh.vert_count, -1, dtype=np.int64)
        remap[used] = np.arange(used.size, dtype=np.int64)
        out.append(Mesh(
            mesh.v[used],
            remap[faces],
            None if mesh.n is None else mesh.n[used],
            int(mat),
            None if mesh.uv is None else mesh.uv[used],
            f"{mesh.name}_{int(mat)}",
        ))
    return out


def _adjacency(mesh: Mesh):
    """Return (src, dst) arrays describing the undirected 1-ring."""
    f = mesh.f
    e = np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]], axis=0)
    e = np.unique(np.sort(e, axis=1), axis=0)
    src = np.concatenate([e[:, 0], e[:, 1]])
    dst = np.concatenate([e[:, 1], e[:, 0]])
    return src, dst


def taubin_smooth(mesh: Mesh, iterations: int = 4, lam: float = 0.52,
                   mu: float = -0.54) -> Mesh:
    """Laplacian (Taubin) smoothing.

    Voxelised isosurfaces carry a visible staircase; a Taubin pass removes
    it without the shrinkage a plain Laplacian filter would cause.
    """
    if mesh.vert_count == 0:
        return mesh
    src, dst = _adjacency(mesh)
    v = mesh.v.copy()
    n = mesh.vert_count

    def step(verts, factor):
        sums = np.zeros_like(verts)
        counts = np.zeros(n)
        np.add.at(sums, src, verts[dst])
        np.add.at(counts, src, 1.0)
        counts = np.maximum(counts, 1.0)[:, None]
        return verts + factor * (sums / counts - verts)

    for _ in range(iterations):
        v = step(v, lam)
        v = step(v, mu)

    return Mesh(v, mesh.f, None, mesh.mat, mesh.uv, mesh.name)


def smooth_material_labels(mesh: Mesh, labels, rounds: int = 2) -> np.ndarray:
    """Majority vote over the 1-ring to remove speckled material borders."""
    labels = np.asarray(labels, dtype=np.int64)
    if mesh.vert_count == 0:
        return labels
    src, dst = _adjacency(mesh)
    n_materials = int(labels.max()) + 1 if labels.size else 1
    out = labels.copy()
    for _ in range(rounds):
        counts = np.zeros((mesh.vert_count, n_materials), dtype=np.int32)
        np.add.at(counts, (src, out[dst]), 1)
        counts[np.arange(mesh.vert_count), out] += 2  # keep the vertex's own label
        out = counts.argmax(axis=1).astype(np.int64)
    return out


# --------------------------------------------------------------------------
# normals
# --------------------------------------------------------------------------
def face_normals(verts: np.ndarray, faces: np.ndarray) -> np.ndarray:
    a = verts[faces[:, 0]]
    b = verts[faces[:, 1]]
    c = verts[faces[:, 2]]
    n = np.cross(b - a, c - a)
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    ln[ln == 0] = 1.0
    return n / ln


def orient_outward(faces: np.ndarray, verts: np.ndarray, inside) -> np.ndarray:
    """Flip triangles whose normal points away from ``inside``."""
    inside = np.asarray(inside, dtype=np.float64)
    c = verts[faces].mean(axis=1) - inside
    n = face_normals(verts, faces)
    flip = (n * c).sum(axis=1) < 0
    out = faces.copy()
    out[flip] = out[flip][:, [0, 2, 1]]
    return out


def smooth_normals(mesh: Mesh) -> Mesh:
    """Fallback: area-weighted averaged normals (no hard-edge splitting)."""
    verts, faces = mesh.v, mesh.f
    if faces.shape[0] == 0:
        return mesh
    a, b, c = verts[faces[:, 0]], verts[faces[:, 1]], verts[faces[:, 2]]
    fn = face_normals(verts, faces)
    area = np.linalg.norm(np.cross(b - a, c - a), axis=1) * 0.5
    contrib = fn * area[:, None]
    acc = np.zeros_like(verts)
    for k in range(3):
        np.add.at(acc, faces[:, k], contrib)
    ln = np.linalg.norm(acc, axis=1, keepdims=True)
    ln[ln == 0] = 1.0
    return Mesh(verts, faces, acc / ln, mesh.mat, mesh.uv, mesh.name)


def _grid_faces(nu: int, nv: int, wrap_u: bool = False, wrap_v: bool = False) -> np.ndarray:
    """Quad grid -> triangles. Index = i * nv + j (i along u, j along v)."""
    faces = []
    i_max = nu if wrap_u else nu - 1
    j_max = nv if wrap_v else nv - 1
    for i in range(i_max):
        i2 = (i + 1) % nu
        for j in range(j_max):
            j2 = (j + 1) % nv
            a = i * nv + j
            b = i2 * nv + j
            c = i2 * nv + j2
            d = i * nv + j2
            faces.append((a, b, c))
            faces.append((a, c, d))
    return np.asarray(faces, dtype=np.int64).reshape(-1, 3)


def _param_grid(fn, nu: int, nv: int, wrap_u: bool = True, wrap_v: bool = False,
                eps: float = 1e-4, flip: bool = False):
    """Sample a parametric surface and derive normals by finite differences.

    ``fn(u, v)`` must return an (N, 3) array of positions for an (N,) array
    of u and v parameters.
    """
    u = np.linspace(0.0, 1.0, nu, endpoint=not wrap_u)
    v = np.linspace(0.0, 1.0, nv, endpoint=not wrap_v)
    uu, vv = np.meshgrid(u, v, indexing="ij")
    uu = uu.reshape(-1)
    vv = vv.reshape(-1)
    p = fn(uu, vv)

    du = (fn(uu + eps, vv) - fn(uu - eps, vv))
    dv = (fn(uu, vv + eps) - fn(uu, vv - eps))
    n = np.cross(du, dv)
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    ln[ln == 0] = 1.0
    n = n / ln
    if flip:
        n = -n
    uv = np.stack([uu, vv], axis=1)
    return p.reshape(nu, nv, 3), n.reshape(nu, nv, 3), uv.reshape(nu, nv, 2)


# --------------------------------------------------------------------------
# primitives
# --------------------------------------------------------------------------
def uv_sphere(rx=1.0, ry=1.0, rz=1.0, seg_u=48, seg_v=32, mat=0, name="sphere") -> Mesh:
    """Ellipsoid with proper pole fans (no degenerate triangles)."""
    verts, norms, uvs = [], [], []
    faces = []

    north = np.array([0.0, 0.0, rz])
    verts.append(north)
    norms.append(np.array([0.0, 0.0, 1.0]))
    uvs.append(np.array([0.5, 1.0]))

    ring_start = []
    for i in range(1, seg_v):
        theta = math.pi * i / seg_v
        st, ct = math.sin(theta), math.cos(theta)
        ring_start.append(len(verts))
        for j in range(seg_u):
            phi = TAU * j / seg_u
            x, y = st * math.cos(phi), st * math.sin(phi)
            p = np.array([rx * x, ry * y, rz * ct])
            verts.append(p)
            n = np.array([x / max(rx, 1e-9), y / max(ry, 1e-9), ct / max(rz, 1e-9)])
            norms.append(n / max(np.linalg.norm(n), 1e-12))
            uvs.append(np.array([j / seg_u, 1.0 - i / seg_v]))

    south = len(verts)
    verts.append(np.array([0.0, 0.0, -rz]))
    norms.append(np.array([0.0, 0.0, -1.0]))
    uvs.append(np.array([0.5, 0.0]))

    for j in range(seg_u):
        j2 = (j + 1) % seg_u
        faces.append((0, ring_start[0] + j, ring_start[0] + j2))
    for i in range(len(ring_start) - 1):
        a, b = ring_start[i], ring_start[i + 1]
        for j in range(seg_u):
            j2 = (j + 1) % seg_u
            faces.append((a + j, b + j, b + j2))
            faces.append((a + j, b + j2, a + j2))
    last = ring_start[-1]
    for j in range(seg_u):
        j2 = (j + 1) % seg_u
        faces.append((last + j, south, last + j2))

    return Mesh(np.asarray(verts), np.asarray(faces, dtype=np.int64),
                np.asarray(norms), mat, np.asarray(uvs), name)


def revolve(profile, seg_u=48, mat=0, name="revolve", radial_mod=None,
            cap_bottom=True, cap_top=True, flip=False) -> Mesh:
    """Surface of revolution around the Y axis.

    ``profile`` is a sequence of ``(radius, z)`` pairs ordered bottom to top.
    A profile point with radius 0 becomes a pole; a profile that returns to
    radius 0 closes the surface on its own.

    ``radial_mod(phi)`` may scale the radius per angle to add pleats or
    flutes. End caps duplicate their rim vertices so the rim reads as a
    crisp crease while the mesh stays watertight.
    """
    prof = np.asarray(profile, dtype=np.float64)
    m = prof.shape[0]
    thetas = np.linspace(0.0, TAU, seg_u, endpoint=False)
    ct, st = np.cos(thetas), np.sin(thetas)

    verts, uvs, faces = [], [], []
    rings = []

    for i in range(m):
        r, z = float(prof[i, 0]), float(prof[i, 1])
        if r < 1e-7:
            idx = len(verts)
            verts.append([0.0, z, 0.0])
            uvs.append([0.5, i / max(m - 1, 1)])
            rings.append([idx])
            continue
        base = len(verts)
        for j in range(seg_u):
            phi = float(thetas[j])
            mod = float(radial_mod(phi)) if radial_mod is not None else 1.0
            rr = r * mod
            verts.append([rr * ct[j], z, rr * st[j]])
            uvs.append([j / seg_u, i / max(m - 1, 1)])
        rings.append(list(range(base, base + seg_u)))

    for i in range(m - 1):
        a, b = rings[i], rings[i + 1]
        a_pole = len(a) == 1
        b_pole = len(b) == 1
        if a_pole and b_pole:
            continue
        if a_pole:  # pole below a ring
            for j in range(seg_u):
                j2 = (j + 1) % seg_u
                faces.append((b[j], b[j2], a[0]))
        elif b_pole:  # ring below a pole
            for j in range(seg_u):
                j2 = (j + 1) % seg_u
                faces.append((a[j2], a[j], b[0]))
        else:
            for j in range(seg_u):
                j2 = (j + 1) % seg_u
                faces.append((a[j], b[j], b[j2]))
                faces.append((a[j], b[j2], a[j2]))

    # end caps duplicate the rim so the crease stays sharp
    if cap_bottom and len(rings[0]) > 1:
        faces.extend(_cap_faces(verts, uvs, rings[0], +1))
    if cap_top and len(rings[-1]) > 1:
        faces.extend(_cap_faces(verts, uvs, rings[-1], -1))

    mesh = Mesh(np.asarray(verts), np.asarray(faces, dtype=np.int64), None, mat,
                np.asarray(uvs), name)
    mesh = smooth_normals(mesh)
    if flip:
        mesh = Mesh(mesh.v, mesh.f[:, ::-1].copy(), -mesh.n, mesh.mat, mesh.uv, mesh.name)
    return mesh


def _cap_faces(verts, uvs, rim, winding, center=None, normals=None, normal=None):
    """Add a flat cap over ``rim``; returns new face triples.

    The rim vertices are duplicated so the cap can carry its own flat
    normals while the surface underneath keeps its smooth shading.

    ``winding`` +1 emits (center, rim[j], rim[j2]) and -1 the mirror, which
    is how the cap faces the correct way for each call site.
    """
    base = len(verts)
    rim_pos = [list(verts[i]) for i in rim]
    rim_uv = [list(uvs[i]) for i in rim]
    for pos, uv in zip(rim_pos, rim_uv):
        verts.append(pos)
        uvs.append(uv)
        if normals is not None and normal is not None:
            normals.append(list(normal))
    if center is None:
        center = [0.0, rim_pos[0][1], 0.0]
    else:
        center = [float(c) for c in center]
    center_idx = len(verts)
    verts.append(center)
    uvs.append([0.5, 0.5])
    if normals is not None and normal is not None:
        normals.append(list(normal))
    faces = []
    n = len(rim)
    for j in range(n):
        j2 = (j + 1) % n
        if winding > 0:
            faces.append((center_idx, base + j, base + j2))
        else:
            faces.append((center_idx, base + j2, base + j))
    return faces


def superellipsoid(rx=1.0, ry=1.0, rz=1.0, power=0.35, seg_u=48, seg_v=32,
                   mat=0, name="superellipsoid") -> Mesh:
    """Rounded-box-ish volume with poles on the Y axis.

    ``power`` 1.0 is a plain ellipsoid; smaller values square the form off
    (0.25 reads as a rounded box).
    """
    def sp(x, p):
        return np.sign(x) * np.abs(x) ** p

    verts, uvs = [], []
    faces = []

    def point(eta, om):
        ce, se = math.cos(eta), math.sin(eta)
        return np.array([
            rx * sp(ce, power) * sp(math.cos(om), power),
            ry * sp(se, power),
            rz * sp(ce, power) * sp(math.sin(om), power),
        ])

    bottom = len(verts)
    verts.append(np.array([0.0, -ry, 0.0]))
    uvs.append(np.array([0.5, 0.0]))

    ring_start = []
    for i in range(1, seg_v):
        eta = -math.pi * 0.5 + math.pi * i / seg_v
        ring_start.append(len(verts))
        for j in range(seg_u):
            om = TAU * j / seg_u
            verts.append(point(eta, om))
            uvs.append(np.array([j / seg_u, i / seg_v]))

    top = len(verts)
    verts.append(np.array([0.0, ry, 0.0]))
    uvs.append(np.array([0.5, 1.0]))

    for j in range(seg_u):
        j2 = (j + 1) % seg_u
        faces.append((bottom, ring_start[0] + j2, ring_start[0] + j))
    for i in range(len(ring_start) - 1):
        a, b = ring_start[i], ring_start[i + 1]
        for j in range(seg_u):
            j2 = (j + 1) % seg_u
            faces.append((a + j, a + j2, b + j2))
            faces.append((a + j, b + j2, b + j))
    last = ring_start[-1]
    for j in range(seg_u):
        j2 = (j + 1) % seg_u
        faces.append((top, last + j, last + j2))

    v = np.asarray(verts)
    f = orient_outward(np.asarray(faces, dtype=np.int64), v, (0.0, 0.0, 0.0))
    mesh = Mesh(v, f, None, mat, np.asarray(uvs), name)
    return smooth_normals(mesh)


def torus(R=1.0, r=0.2, seg_u=48, seg_v=16, mat=0, name="torus",
          arc=1.0, start=0.0) -> Mesh:
    """Torus (optionally a partial arc, used for trim and rings)."""
    full = arc >= 1.0 - 1e-9
    nu = seg_u if full else max(3, int(seg_u * arc) + 1)

    def surf(u, v):
        a = (start + u * arc) * TAU
        b = v * TAU
        rr = R + r * np.cos(b)
        out = np.empty((u.size, 3), dtype=np.float64)
        out[:, 0] = rr * np.cos(a)
        out[:, 1] = r * np.sin(b)
        out[:, 2] = rr * np.sin(a)
        return out

    p, n, uv = _param_grid(surf, nu, seg_v, wrap_u=full, wrap_v=True)
    faces = _grid_faces(nu, seg_v, wrap_u=full, wrap_v=True)
    if not full:
        faces = _grid_faces(nu, seg_v, wrap_u=False, wrap_v=True)
    # the parameterisation winds inward, so flip the surface normals
    return Mesh(p.reshape(-1, 3), faces, -n.reshape(-1, 3), mat, uv.reshape(-1, 2), name)


def tube(points, radii, seg_u=20, mat=0, name="tube", cap_start=True, cap_end=True,
         flat=1.0) -> Mesh:
    """Swept tube along a polyline using parallel-transport frames.

    ``flat`` squashes the cross-section along the binormal, which turns the
    tube into a flat blade -- the shape used for hair strands and straps.
    """
    pts = np.asarray(points, dtype=np.float64)
    rad = np.asarray(radii, dtype=np.float64)
    n = pts.shape[0]
    if np.isscalar(rad):
        rad = np.full(n, float(rad))
    if rad.size == 1:
        rad = np.full(n, float(rad[0]))

    tangents = np.empty((n, 3), dtype=np.float64)
    tangents[0] = pts[1] - pts[0]
    tangents[-1] = pts[-1] - pts[-2]
    for i in range(1, n - 1):
        tangents[i] = pts[i + 1] - pts[i - 1]
    tl = np.linalg.norm(tangents, axis=1, keepdims=True)
    tl[tl == 0] = 1.0
    tangents /= tl

    # parallel transport: rotate the reference normal step by step
    ref = np.array([0.0, 1.0, 0.0])
    if abs(float(np.dot(ref, tangents[0]))) > 0.95:
        ref = np.array([0.0, 0.0, 1.0])
    normals = np.empty((n, 3), dtype=np.float64)
    normals[0] = ref - tangents[0] * float(np.dot(ref, tangents[0]))
    normals[0] /= max(np.linalg.norm(normals[0]), 1e-12)
    for i in range(1, n):
        prev_t, cur_t = tangents[i - 1], tangents[i]
        axis = np.cross(prev_t, cur_t)
        s = float(np.linalg.norm(axis))
        if s > 1e-9:
            axis /= s
            ang = math.atan2(s, float(np.dot(prev_t, cur_t)))
            rot = _axis_angle(axis, ang)
            normals[i] = normals[i - 1] @ rot.T
        else:
            normals[i] = normals[i - 1]
        normals[i] -= cur_t * float(np.dot(normals[i], cur_t))
        ln = float(np.linalg.norm(normals[i]))
        normals[i] = normals[i] / ln if ln > 1e-12 else normals[i]

    verts, norms, uvs = [], [], []
    for i in range(n):
        binormal = np.cross(tangents[i], normals[i])
        for j in range(seg_u):
            phi = TAU * j / seg_u
            c, s = math.cos(phi), math.sin(phi)
            d = normals[i] * c + binormal * s * flat
            verts.append(pts[i] + d * rad[i])
            # ellipse gradient: (cos/r, sin/(r*flat)) -> scaled to (cos*flat, sin)
            nn = normals[i] * (c * flat) + binormal * s
            ln = float(np.linalg.norm(nn))
            norms.append(nn / ln if ln > 1e-12 else d)
            uvs.append(np.array([j / seg_u, i / max(n - 1, 1)]))

    faces = _grid_faces(n, seg_u, wrap_u=False, wrap_v=True).tolist()

    # end caps reuse the exact rim positions so the tube stays watertight
    if cap_start and rad[0] > 1e-9:
        faces.extend(_cap_faces(verts, uvs, list(range(0, seg_u)), -1, center=pts[0],
                                normals=norms, normal=-tangents[0]))
    if cap_end and rad[-1] > 1e-9:
        ring = list(range((n - 1) * seg_u, n * seg_u))
        faces.extend(_cap_faces(verts, uvs, ring, +1, center=pts[-1],
                                normals=norms, normal=tangents[-1]))

    return Mesh(np.asarray(verts), np.asarray(faces, dtype=np.int64),
                np.asarray(norms), mat, np.asarray(uvs), name)


def _axis_angle(axis, angle) -> np.ndarray:
    x, y, z = axis
    c, s = math.cos(angle), math.sin(angle)
    t = 1.0 - c
    return np.array([
        [t * x * x + c, t * x * y - s * z, t * x * z + s * y],
        [t * x * y + s * z, t * y * y + c, t * y * z - s * x],
        [t * x * z - s * y, t * y * z + s * x, t * z * z + c],
    ], dtype=np.float64)


def solidify_patch(grid, thickness, mat=0, name="patch", wrap_u: bool = False) -> Mesh:
    """Turn an open surface patch into a closed solid with a rim.

    ``grid`` is an (nu, nv, 3) array of surface points. The patch is offset
    along its own normals by half the thickness on each side and closed with
    a side wall, producing real cloth-like volume.

    ``wrap_u`` marks a patch whose first and last columns meet in space
    (a patch that runs all the way around the head).  The rim then has to
    skip that seam, otherwise a wall is built along a line where the
    surface already closes on itself -- which shows up as a ridge cutting
    across the model.
    """
    g = np.asarray(grid, dtype=np.float64)
    nu, nv, _ = g.shape
    du = np.gradient(g, axis=0)
    dv = np.gradient(g, axis=1)
    nrm = np.cross(du, dv)
    ln = np.linalg.norm(nrm, axis=2, keepdims=True)
    ln[ln == 0] = 1.0
    nrm = nrm / ln

    half = thickness * 0.5
    top = (g + nrm * half).reshape(-1, 3)
    bot = (g - nrm * half).reshape(-1, 3)
    verts = np.concatenate([top, bot], axis=0)
    norms = np.concatenate([nrm.reshape(-1, 3), -nrm.reshape(-1, 3)], axis=0)
    uvs = np.tile(np.stack(np.meshgrid(np.linspace(0, 1, nu),
                                       np.linspace(0, 1, nv), indexing="ij"), axis=-1).reshape(-1, 2), 2)

    off = nu * nv
    faces = []
    quads = _quad_list(nu, nv)
    for (a, b, c, d) in quads:
        faces.append((a, b, c))
        faces.append((a, c, d))
        faces.append((off + a, off + d, off + c))
        faces.append((off + a, off + c, off + b))
    # rim walls
    if wrap_u:
        border = ([i * nv for i in range(nu)]
                  + [i * nv + nv - 1 for i in range(nu - 1, -1, -1)])
    else:
        border = (list(range(nv))
                  + [i * nv + nv - 1 for i in range(1, nu)]
                  + [(nu - 1) * nv + j for j in range(nv - 2, -1, -1)]
                  + [i * nv for i in range(nu - 2, 0, -1)])
    for k in range(len(border)):
        a = border[k]
        b = border[(k + 1) % len(border)]
        faces.append((a, b, off + b))
        faces.append((a, off + b, off + a))

    return Mesh(verts, np.asarray(faces, dtype=np.int64), norms, mat, uvs, name)


def _quad_list(nu: int, nv: int):
    out = []
    for i in range(nu - 1):
        for j in range(nv - 1):
            a = i * nv + j
            b = (i + 1) * nv + j
            c = (i + 1) * nv + j + 1
            d = i * nv + j + 1
            out.append((a, b, c, d))
    return out


def patch_grid(fn, nu: int, nv: int, wrap_u: bool = False, wrap_v: bool = False):
    """Sample a surface patch into an (nu, nv, 3) array for solidify_patch."""
    u = np.linspace(0.0, 1.0, nu, endpoint=not wrap_u)
    v = np.linspace(0.0, 1.0, nv, endpoint=not wrap_v)
    uu, vv = np.meshgrid(u, v, indexing="ij")
    return fn(uu.reshape(-1), vv.reshape(-1)).reshape(nu, nv, 3)


def box(w=1.0, h=1.0, d=1.0, mat=0, name="box", power=0.08) -> Mesh:
    """Rounded box built from a superellipsoid."""
    return superellipsoid(w * 0.5, h * 0.5, d * 0.5, power, 40, 28, mat, name)


def cone(r_bottom=0.2, r_top=0.0, height=1.0, seg_u=32, mat=0, name="cone",
         cap_bottom=True, cap_top=True) -> Mesh:
    """Tapered cylinder / cone along Y, centred on the origin."""
    profile = [(r_bottom, -height * 0.5), (r_top, height * 0.5)]
    return revolve(profile, seg_u, mat, name,
                   cap_bottom=cap_bottom, cap_top=cap_top)


def cylinder(r=0.1, height=1.0, seg_u=32, mat=0, name="cylinder") -> Mesh:
    return revolve([(r, -height * 0.5), (r, height * 0.5)], seg_u, mat, name)


def sphere_at(radius, center, seg_u=40, seg_v=28, mat=0, name="ball", scale=(1, 1, 1)) -> Mesh:
    sx, sy, sz = scale
    m = uv_sphere(radius * sx, radius * sy, radius * sz, seg_u, seg_v, mat, name)
    return m.translated(center)


# --------------------------------------------------------------------------
# curve helpers
# --------------------------------------------------------------------------
def slab_from_outline(outline, thickness=0.04, dome=0.0, mat=0, name="slab"):
    """A flat slab with an arbitrary closed outline, optionally domed.

    Extruding a drawn outline is how a real modeller blocks in a guitar
    body: the silhouette is the hard part, and a superellipsoid can only
    ever be a rounded rectangle.  The front face is domed towards the
    centre so the slab catches a highlight like a real instrument.
    """
    pts = np.asarray(outline, dtype=np.float64)
    n = pts.shape[0]
    x = pts[:, 0]
    y = pts[:, 1]
    span = max(float(np.abs(pts).max()), 1e-9)
    bulge = dome * (1.0 - (x * x + y * y) / (span * span))

    front = np.stack([x, y, np.full(n, thickness * 0.5) + bulge], axis=1)
    back = np.stack([x, y, np.full(n, -thickness * 0.5)], axis=1)
    front_c = np.array([0.0, 0.0, thickness * 0.5 + dome])
    back_c = np.array([0.0, 0.0, -thickness * 0.5])

    verts = np.concatenate([front, back, front_c[None, :], back_c[None, :]], axis=0)
    fc = 2 * n
    bc = fc + 1

    faces = []
    for i in range(n):
        j = (i + 1) % n
        faces.append((fc, i, j))          # front fan
        faces.append((bc, n + j, n + i))  # back fan
        faces.append((i, n + i, n + j))    # rim
        faces.append((i, n + j, j))
    mesh = Mesh(verts, faces, None, mat, None, name)
    return smooth_normals(mesh)


def catmull_rom(control, samples_per_seg=8) -> np.ndarray:
    """Smooth a control polyline into a dense polyline."""
    p = np.asarray(control, dtype=np.float64)
    if p.shape[0] == 2:
        p = np.vstack([p[0], p[0], p[1], p[1]])
    elif p.shape[0] == 3:
        p = np.vstack([p[0], p[0], p[1], p[2], p[2]])
    ext = np.vstack([p[0] + (p[0] - p[1]), p, p[-1] + (p[-1] - p[-2])])
    out = []
    for i in range(ext.shape[0] - 3):
        p0, p1, p2, p3 = ext[i], ext[i + 1], ext[i + 2], ext[i + 3]
        for s in range(samples_per_seg):
            t = s / samples_per_seg
            t2, t3 = t * t, t * t * t
            pt = 0.5 * ((2 * p1)
                        + (-p0 + p2) * t
                        + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2
                        + (-p0 + 3 * p1 - 3 * p2 + p3) * t3)
            out.append(pt)
    out.append(p[-1])
    return np.asarray(out)


def resample(points, count) -> np.ndarray:
    """Resample a polyline to ``count`` evenly spaced points."""
    p = np.asarray(points, dtype=np.float64)
    seg = np.linalg.norm(np.diff(p, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    if s[-1] <= 1e-12:
        return np.repeat(p[:1], count, axis=0)
    t = np.linspace(0.0, s[-1], count)
    return np.column_stack([np.interp(t, s, p[:, k]) for k in range(p.shape[1])])


def taper(count, start=1.0, end=0.0, power=1.0) -> np.ndarray:
    """A linear ramp of radii for tapered strands."""
    t = np.linspace(0.0, 1.0, count)
    return (start + (end - start) * (t ** power)).astype(np.float64)


def blade(path, widths, thickness=None, seg_u=14, mat=0, name="blade") -> Mesh:
    """A flat tapered strand (hair lock, strap) swept along ``path``."""
    p = np.asarray(path, dtype=np.float64)
    w = np.asarray(widths, dtype=np.float64)
    if thickness is None:
        thickness = float(np.max(w)) * 0.55
    thick = np.full(p.shape[0], float(thickness))
    return _blade(p, w, thick, seg_u, mat, name)


def _blade(points, widths, thickness, seg_u, mat, name) -> Mesh:
    """Flat blade sweep: a rectangle swept along a polyline."""
    pts = np.asarray(points, dtype=np.float64)
    wid = np.asarray(widths, dtype=np.float64)
    n = pts.shape[0]

    tangents = np.empty((n, 3), dtype=np.float64)
    tangents[0] = pts[1] - pts[0]
    tangents[-1] = pts[-1] - pts[-2]
    for i in range(1, n - 1):
        tangents[i] = pts[i + 1] - pts[i - 1]
    tl = np.linalg.norm(tangents, axis=1, keepdims=True)
    tl[tl == 0] = 1.0
    tangents /= tl

    # side vector: perpendicular to the tangent, kept in the XZ-ish plane
    side = np.cross(tangents, np.array([0.0, 1.0, 0.0]))
    bad = np.linalg.norm(side, axis=1) < 1e-6
    side[bad] = np.array([1.0, 0.0, 0.0])
    side /= np.linalg.norm(side, axis=1, keepdims=True)
    up = np.cross(side, tangents)
    up /= np.linalg.norm(up, axis=1, keepdims=True)

    verts, norms, uvs = [], [], []
    for i in range(n):
        hw = wid[i] * 0.5
        ht = thickness[i] * 0.5
        for sy, sz in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            verts.append(pts[i] + side[i] * (hw * sy) + up[i] * (ht * sz))
            norms.append(side[i] * (sy / max(hw, 1e-9)) + up[i] * (sz / max(ht, 1e-9)))
            uvs.append(np.array([(sy + 1) * 0.5, i / max(n - 1, 1)]))

    faces = []
    for i in range(n - 1):
        for k in range(4):
            k2 = (k + 1) % 4
            a = i * 4 + k
            b = i * 4 + k2
            c = (i + 1) * 4 + k2
            d = (i + 1) * 4 + k
            faces.append((a, b, c))
            faces.append((a, c, d))
    # end caps
    faces.append((0, 1, 2))
    faces.append((0, 2, 3))
    base = (n - 1) * 4
    faces.append((base, base + 2, base + 1))
    faces.append((base, base + 3, base + 2))

    norms = np.asarray(norms)
    norms /= np.maximum(np.linalg.norm(norms, axis=1, keepdims=True), 1e-12)
    return Mesh(np.asarray(verts), np.asarray(faces, dtype=np.int64), norms, mat,
                np.asarray(uvs), name)
