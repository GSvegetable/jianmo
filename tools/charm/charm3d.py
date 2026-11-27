"""Turn the composed artwork into the three dimensional charm.

The charm is built the way a real acrylic charm is made: a shaped plate
with the drawing printed on it, and the parts of the drawing that matter
raised a little above the plate so the charm catches the light.

* the **plate** carries the whole outline of the character; its front is
  printed with the front of the drawing and its back with the back,
* the **raised parts** are the colours of the outfit -- the hair stands
  proud of the face, the skirt of the legs, the bow of the cardigan --
  every one of them printed with the same drawing, so the print and the
  shape always agree,
* the **ring** at the top is what the chain goes through.
"""

from __future__ import annotations

import numpy as np

from tools.chibi.glb import Material, export_glb
from tools.chibi.mesh import Mesh, face_normals, torus

from .segment import label_components

from .mesh2d import bridge_holes, earclip
from .trace import _marching_squares, simplify, smooth

# How far each part of the outfit stands proud of the plate, in canvas
# pixels.  The order follows the way the drawing is painted: the further
# forward a part is drawn, the further forward it stands.
RELIEF = {
    "navy": 10,
    "white": 15,
    "pink": 22,
    "hair": 30,
    "hairdk": 36,
    "brown": 40,
    "green": 45,
    "ink": 50,
}

PLATE_THICKNESS = 130          # canvas pixels
RING_RADIUS = 60               # canvas pixels
RING_TUBE = 19

MAT_FRONT, MAT_BACK, MAT_RIM = 0, 1, 2


def _area(poly: np.ndarray) -> float:
    x, y = poly[:, 0], poly[:, 1]
    return 0.5 * float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def contour_of(mask: np.ndarray):
    """The outlines of a mask: one outer boundary and its holes per piece.

    A drawing is not always one solid shape -- the hair of the charm hangs
    beside the body rather than over it -- so the mask is taken apart into
    its pieces and every piece is outlined on its own.
    """
    labels, count = label_components(mask)
    pieces = []
    for c in range(1, count + 1):
        piece = labels == c
        if int(piece.sum()) < 200:
            continue
        loops = _marching_squares(piece.astype(np.float64), 0.5)
        if not loops:
            continue
        areas = [abs(_area(loop)) for loop in loops]
        biggest = int(np.argmax(areas))
        outer = loops[biggest]
        # only the gaps that matter are kept as holes: the little gaps
        # between the strands of hair are filled in, which keeps the
        # outline easy to cut into triangles
        holes = [loop for loop, area in zip(loops, areas)
                 if area < areas[biggest] * 0.999 and area > 300]
        pieces.append((outer, holes))
    return pieces


def _slab(poly: np.ndarray, holes: list, z0: float, z1: float,
          width: int, height: int):
    """A flat piece of the drawing, given thickness.

    Returns the vertices, the texture coordinates and the three groups of
    faces: the printed front, the printed back and the edge.
    """
    # the outlines carry more points than the charm needs; a light
    # simplification keeps the triangles down without changing the shape
    poly = _tidy(poly, 1.4)
    holes = [_tidy(h, 1.4) for h in holes]
    loop = bridge_holes(poly, holes)
    triangles = earclip(loop)
    if not triangles:
        return None
    n = loop.shape[0]
    verts = np.zeros((n * 2, 3), dtype=np.float64)
    verts[:n, 0] = loop[:, 0]
    verts[:n, 1] = loop[:, 1]
    verts[:n, 2] = z1
    verts[n:, 0] = loop[:, 0]
    verts[n:, 1] = loop[:, 1]
    verts[n:, 2] = z0

    # glTF puts the origin of a texture in the upper left corner, so the
    # picture is sampled the way it is drawn
    u = loop[:, 0] / float(width)
    v = loop[:, 1] / float(height)
    uv = np.zeros((n * 2, 2), dtype=np.float64)
    uv[:n, 0] = u
    uv[:n, 1] = v
    uv[n:, 0] = 1.0 - u            # the back is seen the other way round
    uv[n:, 1] = v

    front = []
    back = []
    rim = []
    # the drawing is measured with y running down the page, which makes the
    # winding of a triangle the other way round from the model; the front
    # of the piece therefore takes the triangles in reverse
    for (a, b, c) in triangles:
        front.append((c, b, a))
        back.append((n + a, n + b, n + c))
    for i in range(n):
        j = (i + 1) % n
        rim.append((i, n + i, n + j))
        rim.append((i, n + j, j))

    return (verts, uv,
            np.asarray(front, dtype=np.int64),
            np.asarray(back, dtype=np.int64),
            np.asarray(rim, dtype=np.int64))


def _tidy(poly: np.ndarray, eps: float) -> np.ndarray:
    """Simplify an outline until it is small enough to cut into triangles.

    Cutting a polygon into triangles costs the square of the number of
    points, and the outline of a drawing has thousands of them, so the
    outline is thinned out until the triangles stay a sensible size.
    """
    for _ in range(5):
        poly = simplify(poly, eps)
        if poly.shape[0] <= 900:
            break
        eps *= 1.9
    return smooth(poly, 1)


def _mesh(verts, uv, faces, mat, name, outward_from=None):
    if faces is None or len(faces) == 0:
        return None
    faces = np.asarray(faces, dtype=np.int64)
    if outward_from is not None:
        # the edge of a piece has to point away from the middle of it
        normals = face_normals(verts, faces)
        middle = verts[faces].mean(axis=1)
        away = middle - outward_from
        flip = (normals * away).sum(axis=1) < 0
        if flip.any():
            faces = faces.copy()
            faces[flip] = faces[flip][:, ::-1]
            normals = face_normals(verts, faces)
    else:
        normals = face_normals(verts, faces)
    return Mesh(verts, faces, normals, mat, uv, name)


def build(regions, width: int, height: int, out_path: str,
          front_png: str, back_png: str, scale: float = 0.035,
          centre=(0.0, 0.0)):
    """Assemble the charm and write it out as a glTF binary.

    Every colour of the drawing becomes a piece of the charm.  The pieces
    fit together the way the colours fit together in the drawing, so the
    outline of the charm is the outline of the drawing, and each piece
    carries the part of the drawing it stands for.
    """
    parts = []

    def place(verts):
        out = verts.copy()
        out[:, 0] = (out[:, 0] - centre[0]) * scale
        # the drawing measures downwards, the model measures upwards
        out[:, 1] = (centre[1] - out[:, 1]) * scale
        return out

    # every colour of the drawing becomes a piece of the charm; the pieces
    # stand forward by how far forward the colour is drawn
    for region in regions:
        group = region.group
        lift = RELIEF.get(group, 0)
        # the line work is only a thin layer on top of the drawing, so it
        # does not reach the back of the charm
        back_z = 0.6 * scale if group == "ink" else -PLATE_THICKNESS * scale
        slab = _slab(region.outer, region.holes, back_z,
                     (lift + 0.6) * scale, width, height)
        if slab is None:
            continue
        verts, uv, front, back, rim = slab
        verts = place(verts)
        tag = f"{group}_{region.source}"
        middle = verts.mean(axis=0)
        parts.append(_mesh(verts, uv, front, MAT_FRONT, tag + "_front"))
        parts.append(_mesh(verts, uv, back, MAT_BACK, tag + "_back"))
        parts.append(_mesh(verts, uv, rim, MAT_RIM, tag + "_edge", middle))

    # the ring the chain goes through
    ys = [r.outer[:, 1].min() for r in regions]
    top = min(ys)
    heads = [r for r in regions if r.outer[:, 1].min() < top + 40]
    ring_x = float(np.mean([r.outer[:, 0].mean() for r in heads]))
    ring = torus(R=RING_RADIUS * scale, r=RING_TUBE * scale, seg_u=40, seg_v=14,
                 mat=MAT_RIM, name="ring")
    ring = ring.rotated("x", 90.0)
    ring = ring.translated(((ring_x - centre[0]) * scale,
                            (centre[1] - (top - RING_RADIUS)) * scale,
                            0.0))
    parts.append(ring)

    materials = [
        Material("front", base_color=(1, 1, 1, 1), roughness=0.42,
                 base_color_texture=0, alpha_mode="BLEND"),
        Material("back", base_color=(1, 1, 1, 1), roughness=0.42,
                 base_color_texture=1, alpha_mode="BLEND"),
        Material("edge", base_color=(0.94, 0.91, 0.86, 1.0), roughness=0.55),
    ]
    parts = [p for p in parts if p is not None]
    stats = export_glb(out_path, parts, materials, name="ikuyo-kita-charm",
                       generator="jianmo charm pipeline",
                       textures=[("front", front_png), ("back", back_png)])
    return stats
