"""Vectorise a piece of character artwork into flat colour shapes.

The charm pipeline does not sculpt volumes: it *traces* the artwork, so
the shapes on the charm are the shapes on the drawing.  A traced shape
keeps the silhouette the illustrator designed -- a pointed fringe tip
stays pointed, a pleat stays a pleat -- which is exactly what a volume
based approach cannot do.

The steps are:

1. find the ink (the dark strokes every part is drawn with),
2. take the regions the ink encloses,
3. trace the boundary of every region,
4. sample the artwork inside the region to recover its colour,
5. simplify and round the outline, then emit it as a filled, stroked
   path.

The result is a set of closed paths that reproduce the drawing: the
layers can be stacked in depth to make a charm, and re-coloured or
re-ordered without touching the geometry.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

TAU = math.pi * 2.0


def luminance(rgb: np.ndarray) -> np.ndarray:
    """The brightness of a colour, as the drawing uses it."""
    return rgb[..., 0] * 0.299 + rgb[..., 1] * 0.587 + rgb[..., 2] * 0.114


# --------------------------------------------------------------------------
# marching squares
# --------------------------------------------------------------------------
def _marching_squares(field: np.ndarray, level: float = 0.5):
    """Contours of a scalar field, as lists of (x, y) vertices.

    The field is sampled on a grid of points and the contour is the set of
    places where the field crosses ``level``.  Crossing points are found by
    interpolating along the edges of a cell, which makes the outline smooth
    instead of stepping from pixel to pixel.

    Every segment is oriented so that the side of the contour which is above
    the level is always on the same hand, which is what makes the segments
    join up into closed loops -- a hand written case table gets this wrong
    as soon as two of its cases disagree about the winding.
    """
    f = np.asarray(field, dtype=np.float64)
    h, w = f.shape
    # pad so every region is closed
    fp = np.zeros((h + 2, w + 2), dtype=np.float64)
    fp[1:-1, 1:-1] = f

    v_tl = fp[:-1, :-1]
    v_tr = fp[:-1, 1:]
    v_br = fp[1:, 1:]
    v_bl = fp[1:, :-1]

    f_tl = v_tl > level
    f_tr = v_tr > level
    f_br = v_br > level
    f_bl = v_bl > level

    cells = np.nonzero((f_tl != f_tr) | (f_tr != f_br) |
                       (f_br != f_bl) | (f_bl != f_tl))

    def cross(a: float, b: float, x0: float, y0: float, x1: float, y1: float):
        if abs(b - a) < 1e-12:
            t = 0.5
        else:
            t = (level - a) / (b - a)
        t = min(1.0, max(0.0, t))
        return (x0 + (x1 - x0) * t, y0 + (y1 - y0) * t)

    segs = []
    for j, i in zip(cells[0].tolist(), cells[1].tolist()):
        tl, tr, br, bl = (float(v_tl[j, i]), float(v_tr[j, i]),
                         float(v_br[j, i]), float(v_bl[j, i]))
        flags = (f_tl[j, i], f_tr[j, i], f_br[j, i], f_bl[j, i])
        top = cross(tl, tr, i, j, i + 1, j) if flags[0] != flags[1] else None
        right = cross(tr, br, i + 1, j, i + 1, j + 1) if flags[1] != flags[2] else None
        bottom = cross(bl, br, i, j + 1, i + 1, j + 1) if flags[3] != flags[2] else None
        left = cross(tl, bl, i, j, i, j + 1) if flags[0] != flags[3] else None

        crossings = [p for p in (top, right, bottom, left) if p is not None]

        if len(crossings) == 2:
            pairs = [(crossings[0], crossings[1])]
        elif len(crossings) == 4:
            # a diagonal touch: cut around each of the two corners that are
            # above the level, so the two lobes stay separate
            centre = (tl + tr + br + bl) * 0.25
            if (centre > level) == bool(flags[3] and flags[1]):
                pairs = [(bottom, left), (top, right)]
            else:
                pairs = [(top, left), (right, bottom)]
        else:
            continue

        for p, q in pairs:
            dx = q[0] - p[0]
            dy = q[1] - p[1]
            mx = (p[0] + q[0]) * 0.5
            my = (p[1] + q[1]) * 0.5
            seg = (p, q)
            for k, corner in enumerate(((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1))):
                ox = corner[0] - mx
                oy = corner[1] - my
                crossv = dx * oy - dy * ox
                if abs(crossv) < 1e-9:
                    continue
                # a corner above the level has to sit on the left of the
                # travel direction
                if flags[k] != (crossv < 0.0):
                    seg = (q, p)
                break
            segs.append(seg)

    return _link(segs)


def _link(segs):
    """Join marching-squares segments into closed loops."""
    if not segs:
        return []
    from collections import defaultdict

    def key(p):
        return (round(p[0], 3), round(p[1], 3))

    by_start = defaultdict(list)
    for idx, (a, _b) in enumerate(segs):
        by_start[key(a)].append(idx)

    used = [False] * len(segs)
    loops = []
    for idx in range(len(segs)):
        if used[idx]:
            continue
        used[idx] = True
        a0, b0 = segs[idx]
        loop = [a0, b0]
        current = b0
        for _ in range(len(segs)):
            nxt = None
            for cand in by_start.get(key(current), []):
                if not used[cand]:
                    nxt = cand
                    break
            if nxt is None:
                break
            used[nxt] = True
            a, b = segs[nxt]
            loop.append(b)
            current = b
            if key(current) == key(loop[0]):
                break
        if len(loop) >= 4:
            loops.append(np.asarray(loop[:-1], dtype=np.float64))
    return loops


# --------------------------------------------------------------------------
# polygon tools
# --------------------------------------------------------------------------
def polygon_area(poly: np.ndarray) -> float:
    x, y = poly[:, 0], poly[:, 1]
    return 0.5 * float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def simplify(poly: np.ndarray, eps: float = 1.2) -> np.ndarray:
    """Douglas-Peucker."""
    if poly.shape[0] < 3:
        return poly

    def rdp(points):
        if points.shape[0] < 3:
            return points
        a, b = points[0], points[-1]
        ab = b - a
        denom = float(np.dot(ab, ab))
        if denom < 1e-12:
            dist = np.linalg.norm(points - a, axis=1)
        else:
            t = np.clip(((points - a) @ ab) / denom, 0.0, 1.0)
            proj = a + t[:, None] * ab
            dist = np.linalg.norm(points - proj, axis=1)
        idx = int(np.argmax(dist))
        if dist[idx] <= eps:
            return np.array([a, b])
        left = rdp(points[:idx + 1])
        right = rdp(points[idx:])
        return np.vstack([left[:-1], right])

    return rdp(poly)


def smooth(poly: np.ndarray, iterations: int = 2) -> np.ndarray:
    """Chaikin corner cutting: turns a traced outline into a drawn one."""
    p = poly
    for _ in range(iterations):
        a = p
        b = np.roll(p, -1, axis=0)
        out = np.empty((p.shape[0] * 2, 2), dtype=np.float64)
        out[0::2] = 0.75 * a + 0.25 * b
        out[1::2] = 0.25 * a + 0.75 * b
        p = out
    return p
