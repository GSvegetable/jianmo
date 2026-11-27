"""Triangulate the outlines that have been traced out of the artwork.

A charm is made of flat pieces with holes in them -- the gap between the
legs, the gap between an arm and the body, the hole a lock of hair leaves
around a face.  Turning such an outline into triangles takes two steps:

1. every hole is connected to the outline that contains it by a bridge, so
   the whole thing becomes one closed loop,
2. the loop is cut into triangles by ear clipping.

Both steps are the classical ones; they are here because a charm needs them
and because the outline of the drawing is full of little holes.
"""

from __future__ import annotations

import numpy as np


def signed_area(poly: np.ndarray) -> float:
    x, y = poly[:, 0], poly[:, 1]
    return 0.5 * float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def _point_in_triangle(p, a, b, c) -> bool:
    def cross(u, v):
        return (u[0] - v[0]) * (p[1] - v[1]) - (u[1] - v[1]) * (p[0] - v[0])

    d1 = cross(a, b)
    d2 = cross(b, c)
    d3 = cross(c, a)
    has_neg = (d1 < 0) or (d2 < 0) or (d3 < 0)
    has_pos = (d1 > 0) or (d2 > 0) or (d3 > 0)
    return not (has_neg and has_pos)


def _point_strictly_inside(p, a, b, c, eps: float = 1e-9) -> bool:
    """Like :func:`_point_in_triangle`, but the edge of the triangle is not
    inside it.

    A bridged hole repeats two vertices, and the ear that is cut between
    them is flat.  A vertex that lies exactly on the edge of a candidate
    ear must not stop that ear from being cut.
    """
    def cross(u, v):
        return (u[0] - v[0]) * (p[1] - v[1]) - (u[1] - v[1]) * (p[0] - v[0])

    d1 = cross(a, b)
    d2 = cross(b, c)
    d3 = cross(c, a)
    if abs(d1) < eps or abs(d2) < eps or abs(d3) < eps:
        return False
    return (d1 > 0) == (d2 > 0) == (d3 > 0)


def _segments_cross(p1, p2, p3, p4) -> bool:
    """True when two segments cross each other properly.

    Touching at a shared end point does not count: the bridge is always
    joined to the outline at one of its own vertices.
    """
    def orient(a, b, c):
        v = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        if abs(v) < 1e-12:
            return 0
        return 1 if v > 0 else -1

    o1 = orient(p3, p4, p1)
    o2 = orient(p3, p4, p2)
    o3 = orient(p1, p2, p3)
    o4 = orient(p1, p2, p4)
    if 0 in (o1, o2, o3, o4):
        return False
    return (o1 != o2) and (o3 != o4)


def _bridge_candidate(poly, hole, m_index, edge_index) -> bool:
    """True when the bridge from the hole to this edge is a legal one."""
    m = hole[m_index]
    a = poly[edge_index]
    b = poly[(edge_index + 1) % len(poly)]
    # the triangle that the bridge sweeps has to stay empty
    for j in range(len(poly)):
        if j in (edge_index, (edge_index + 1) % len(poly)):
            continue
        if _point_in_triangle(poly[j], m, a, b):
            return False
    for k in range(len(hole)):
        if k == m_index:
            continue
        if _point_in_triangle(hole[k], m, a, b):
            return False
    # and it must not cross anything
    for j in range(len(poly)):
        j2 = (j + 1) % len(poly)
        if j == edge_index or j2 == edge_index:
            continue
        if _segments_cross(m, a, poly[j], poly[j2]):
            return False
    for k in range(len(hole)):
        k2 = (k + 1) % len(hole)
        if k == m_index:
            continue
        if _segments_cross(m, a, hole[k], hole[k2]):
            return False
    return True


def _bridge_one(poly: list, hole: np.ndarray) -> list:
    """Connect one hole to the outline that surrounds it."""
    m_index = int(np.argmax(hole[:, 0]))
    m = hole[m_index]
    best = None
    for j in range(len(poly)):
        a = poly[j]
        b = poly[(j + 1) % len(poly)]
        if (a[1] > m[1]) == (b[1] > m[1]):
            continue
        t = (m[1] - a[1]) / (b[1] - a[1])
        x = a[0] + (b[0] - a[0]) * t
        if x <= m[0]:
            continue
        if best is None or x < best[0]:
            best = (x, j)
    if best is None:
        return poly
    edge = best[1]
    for candidate in (edge, (edge + 1) % len(poly)):
        if _bridge_candidate(poly, hole, m_index, candidate):
            edge = candidate
            break
    # the hole is walked the other way round from the outline, starting at
    # the vertex the bridge is joined to
    rotated = list(hole)
    rotated = rotated[m_index:] + rotated[:m_index]
    # the bridge vertex is repeated, which is what makes the bridge a
    # bridge: the loop walks out to the hole and back again
    return poly[:edge + 1] + rotated + [rotated[0]] + poly[edge:]


def bridge_holes(outer: np.ndarray, holes: list) -> np.ndarray:
    """Turn an outline with holes into one closed loop."""
    poly = [tuple(p) for p in outer]
    if signed_area(np.asarray(poly)) < 0:
        poly = poly[::-1]
    for hole in sorted(holes, key=lambda h: -abs(signed_area(h))):
        hole = np.asarray(hole)
        if signed_area(hole) > 0:
            hole = hole[::-1]
        poly = _bridge_one(poly, hole)
    return np.asarray(poly, dtype=np.float64)


def earclip(poly: np.ndarray):
    """Cut a closed loop into triangles.

    The outline of a drawing runs to hundreds of points, so the ears are
    found with a linked list: once an ear is cut the search carries on from
    there instead of starting over.
    """
    n = poly.shape[0]
    if n < 3:
        return []
    index = list(range(n))
    if signed_area(poly) < 0:
        index = index[::-1]
    if len(index) < 3:
        return []

    previous = {v: index[k - 1] for k, v in enumerate(index)}
    following = {v: index[(k + 1) % len(index)] for k, v in enumerate(index)}
    alive = set(index)
    triangles = []

    current = index[0]
    guard = 0
    while len(alive) > 3 and guard < 20 * n:
        guard += 1
        before = previous[current]
        after = following[current]
        a, b, c = poly[before], poly[current], poly[after]
        cross = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        if cross > 1e-9:
            blocked = False
            for j in alive:
                if j in (before, current, after):
                    continue
                if _point_strictly_inside(poly[j], a, b, c):
                    blocked = True
                    break
            if not blocked:
                triangles.append((before, current, after))
                alive.discard(current)
                following[before] = after
                previous[after] = before
                current = before
                continue
        current = after

    if len(alive) == 3:
        rest = sorted(alive)
        triangles.append((rest[0], rest[1], rest[2]))
    return triangles
