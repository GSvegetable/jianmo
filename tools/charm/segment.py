"""Segment flat line art into coloured regions.

The reference sheet is flat colour line art, so the reliable way to find the
shapes is to cluster the *colours* and then take the connected components of
each colour -- not to threshold brightness.

A brightness threshold cannot tell the dark navy skirt apart from a dark ink
stroke, so a flood fill leaks out of the drawing and the regions collapse.
A colour cluster can: every flat fill in the drawing has its own colour, and
the ink strokes have their own.

The pipeline is:

1. cluster the pixels into a small palette (k-means in RGB),
2. merge palette entries that are really the same fill,
3. for every colour, take the connected components of that colour,
4. drop the components that touch the image border (that is the paper),
5. trace the boundary of every surviving component.

The result is a list of :class:`Region` objects, each of which knows its
colour, its raster mask and its vector outline.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .trace import (_marching_squares, luminance, polygon_area, simplify,
                      smooth)


# --------------------------------------------------------------------------
# palette
# --------------------------------------------------------------------------
def kmeans_palette(rgb: np.ndarray, k: int = 12, iters: int = 14,
                   seed: int = 7):
    """Cluster the pixels of an image into ``k`` colours.

    Returns ``(centroids, counts)`` where ``centroids`` is (k, 3) in the
    0-255 range.
    """
    data = rgb.reshape(-1, 3).astype(np.float32)
    rng = np.random.default_rng(seed)

    # k-means++ seeding: spread the starting points out over the image
    idx = rng.integers(0, data.shape[0])
    centres = [data[idx]]
    for _ in range(1, k):
        d = np.min(
            ((data[:, None, :] - np.asarray(centres)[None, :, :]) ** 2).sum(axis=2),
            axis=1)
        total = float(d.sum())
        if total <= 1e-6:
            centres.append(data[rng.integers(0, data.shape[0])])
            continue
        pick = rng.choice(data.shape[0], p=d / total)
        centres.append(data[pick])
    centres = np.asarray(centres, dtype=np.float32)

    for _ in range(iters):
        diff = data[:, None, :] - centres[None, :, :]
        dist = (diff * diff).sum(axis=2)
        assign = np.argmin(dist, axis=1)
        moved = False
        for c in range(k):
            sel = assign == c
            n = int(sel.sum())
            if n == 0:
                continue
            new = data[sel].mean(axis=0)
            if not np.allclose(new, centres[c], atol=0.4):
                moved = True
            centres[c] = new
        if not moved:
            break

    counts = np.bincount(
        np.argmin(((data[:, None, :] - centres[None, :, :]) ** 2).sum(axis=2), axis=1),
        minlength=k)
    return centres, counts


def merge_palette(centres: np.ndarray, tol: float = 18.0):
    """Collapse palette entries that are within ``tol`` of each other."""
    groups: list[list[int]] = []
    for i in range(centres.shape[0]):
        for g in groups:
            ref = centres[g].mean(axis=0)
            if float(np.linalg.norm(centres[i] - ref)) < tol:
                g.append(i)
                break
        else:
            groups.append([i])
    merged = []
    for g in groups:
        col = centres[g].mean(axis=0)
        merged.append((np.clip(col, 0, 255), g))
    return merged


# --------------------------------------------------------------------------
# connected components
# --------------------------------------------------------------------------
def _row_runs(row: np.ndarray):
    """Runs of True in a boolean row, as (start, end) index pairs."""
    padded = np.concatenate(([False], row, [False]))
    edges = np.flatnonzero(padded[1:] != padded[:-1])
    return list(zip(edges[0::2].tolist(), edges[1::2].tolist()))


def label_components(mask: np.ndarray):
    """4-connected component labelling.  Returns (labels, count)."""
    h, w = mask.shape
    parent: list[int] = [0]

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    run_label = np.zeros((h, w), dtype=np.int32)
    next_run = 1
    prev_runs: list[tuple[int, int, int]] = []
    for y in range(h):
        runs = _row_runs(mask[y])
        cur: list[tuple[int, int, int]] = []
        for (a, b) in runs:
            lab = 0
            for (pa, pb, pl) in prev_runs:
                if pa < b and a < pb:            # overlapping columns
                    if lab:
                        union(lab, pl)
                    else:
                        lab = pl
            if not lab:
                parent.append(next_run)
                lab = next_run
                next_run += 1
            run_label[y, a:b] = lab
            cur.append((a, b, lab))
        prev_runs = cur

    # resolve run labels to component ids
    roots = {}
    for y in range(h):
        row = run_label[y]
        for r in np.unique(row):
            if r:
                root = find(int(r))
                if root not in roots:
                    roots[root] = len(roots) + 1
                row[row == r] = roots[root]
    labels = run_label
    return labels, len(roots)


# --------------------------------------------------------------------------
# regions
# --------------------------------------------------------------------------
@dataclass
class Region:
    """One flat area of the drawing."""

    color: tuple
    mask: np.ndarray
    outer: np.ndarray
    holes: list = field(default_factory=list)
    area: float = 0.0
    bbox: tuple = (0, 0, 0, 0)

    @property
    def name(self) -> str:
        r, g, b = self.color
        return f"#{r:02x}{g:02x}{b:02x}"

    def centroid(self):
        return self.outer.mean(axis=0)


def _loop_polarity(loop: np.ndarray, mask: np.ndarray) -> bool:
    """True when the loop encloses an area where the mask is set."""
    h, w = mask.shape
    n = loop.shape[0]
    area = polygon_area(loop)
    sign = 1.0 if area >= 0 else -1.0
    # sample just inside the loop at a few vertices
    hits = 0
    total = 0
    for i in range(0, n, max(1, n // 24)):
        p = loop[i]
        prev = loop[(i - 1) % n]
        nxt = loop[(i + 1) % n]
        tangent = nxt - prev
        length = float(np.linalg.norm(tangent))
        if length < 1e-9:
            continue
        tangent = tangent / length
        normal = np.array([-tangent[1], tangent[0]]) * sign
        for step in (0.45, 1.2):
            q = p + normal * step
            xi = int(round(q[0]))
            yi = int(round(q[1]))
            if 0 <= xi < w and 0 <= yi < h:
                total += 1
                if mask[yi, xi]:
                    hits += 1
                break
    if total == 0:
        return False
    return hits * 2 >= total


def _dilate(mask: np.ndarray, times: int = 1) -> np.ndarray:
    out = mask.copy()
    for _ in range(times):
        grown = out.copy()
        grown[1:, :] |= out[:-1, :]
        grown[:-1, :] |= out[1:, :]
        grown[:, 1:] |= out[:, :-1]
        grown[:, :-1] |= out[:, 1:]
        out = grown
    return out


def _erode(mask: np.ndarray, times: int = 1) -> np.ndarray:
    out = mask.copy()
    for _ in range(times):
        shrunk = out.copy()
        shrunk[1:, :] &= out[:-1, :]
        shrunk[:-1, :] &= out[1:, :]
        shrunk[:, 1:] &= out[:, :-1]
        shrunk[:, :-1] &= out[:, 1:]
        out = shrunk
    return out


def _blur(field: np.ndarray, sigma: float = 1.2, radius: int = 3) -> np.ndarray:
    """A small gaussian blur, used to find smooth outlines."""
    k = np.exp(-0.5 * (np.arange(-radius, radius + 1) / sigma) ** 2)
    k /= k.sum()
    height, width = field.shape
    padded = np.pad(field, radius, mode="edge")
    rows = np.zeros_like(field)
    for i, weight in enumerate(k):
        rows += weight * padded[i:i + height, radius:radius + width]
    cols = np.pad(rows, ((0, 0), (radius, radius)), mode="edge")
    out = np.zeros_like(field)
    for i, weight in enumerate(k):
        out += weight * cols[:, i:i + width]
    return out


def _contours(component: np.ndarray):
    """Outer outline plus hole outlines of one connected component.

    The outline is the level set of a blurred copy of the component, so it
    follows the edge of the shape smoothly instead of stepping from pixel
    to pixel.
    """
    h, w = component.shape
    field = _blur(component.astype(np.float64))
    loops = _marching_squares(field, 0.5)
    if not loops:
        return None, []
    areas = [abs(polygon_area(loop)) for loop in loops]
    outer = loops[int(np.argmax(areas))]
    holes = [loop for loop, area in zip(loops, areas)
             if area < areas[int(np.argmax(areas))] * 0.999]
    return outer, holes


def _assign_pixels(rgb: np.ndarray, centres: np.ndarray) -> np.ndarray:
    """Give every pixel to the nearest palette colour.

    A threshold around a cluster centroid only captures the pixels that
    happen to sit at that exact shade, which shreds a shaded area into
    speckle.  Nearest neighbour assignment gives a shaded area to the two
    or three colours it is really made of, and each of those comes out as
    one clean shape.
    """
    h, w, _ = rgb.shape
    flat = rgb.reshape(-1, 3).astype(np.float32)
    out = np.empty(flat.shape[0], dtype=np.int32)
    chunk = 20000
    for start in range(0, flat.shape[0], chunk):
        block = flat[start:start + chunk]
        diff = block[:, None, :] - centres[None, :, :]
        out[start:start + chunk] = np.argmin((diff * diff).sum(axis=2), axis=1)
    return out.reshape(h, w)


def segment(rgb: np.ndarray, k: int = 12, colour_tol: float = 26.0,
            merge_tol: float = 16.0, min_area: int = 30,
            simplify_eps: float = 0.9, smooth_iters: int = 2,
            min_hole: float = 8.0, blur: float = 0.7, median: int = 3,
            close: int = 0):
    """Split an image into flat colour regions.

    The screen the reference sheets are printed with puts a fine dot
    pattern over every flat area, which shatters a plain colour match into
    thousands of specks.  A median filter removes that pattern without
    touching the drawing itself, and a light blur afterwards takes the
    jagged edge off the shapes.

    The colours are still sampled from the original picture, so the screen
    shows through in the colour of every region.

    ``rgb`` is an (H, W, 3) uint8 array.
    """
    from PIL import Image, ImageFilter

    work = rgb
    if median:
        work = np.asarray(
            Image.fromarray(work).filter(ImageFilter.MedianFilter(median)),
            dtype=np.uint8)
    smooth_rgb = np.asarray(
        Image.fromarray(work).filter(ImageFilter.GaussianBlur(blur)),
        dtype=np.uint8)

    centres, _ = kmeans_palette(smooth_rgb, k=k)
    merged = merge_palette(centres, tol=merge_tol)
    palette = np.asarray([c for c, _g in merged], dtype=np.float32)
    labels = _assign_pixels(smooth_rgb, palette)

    # The line work is the darkest material in the drawing, but the shading
    # that sits right next to it lands in the same cluster.  Only the very
    # darkest part of that cluster is line; the rest is shading and goes
    # back to the material it actually shades, otherwise a soft shadow
    # under the fringe turns into a black slab.
    lum = luminance(rgb)
    pal_lum = luminance(palette)
    darkest = int(np.argmin(pal_lum))
    if pal_lum[darkest] < 110:
        ink = labels == darkest
        if ink.sum() > 60:
            edge = float(np.percentile(lum[ink], 45.0))
            soft = ink & (lum > edge)
            if soft.any():
                others = [i for i in range(palette.shape[0]) if i != darkest]
                block = smooth_rgb[soft].astype(np.float32)
                diff = block[:, None, :] - palette[others][None, :, :]
                labels[soft] = np.asarray(others)[np.argmin((diff * diff).sum(axis=2), axis=1)]

    if close:
        # close the thin gaps that separate the strands of hair from the
        # rest of it, so a lock that is only joined by a line of ink stays
        # one shape instead of drifting off as a loose piece
        for idx in range(palette.shape[0]):
            part = labels == idx
            if not part.any():
                continue
            joined = _erode(_dilate(part, close), close)
            labels[joined & part] = idx

    h, w, _ = rgb.shape
    regions: list[Region] = []
    for idx, (colour, _members) in enumerate(merged):
        mask = labels == idx
        if not mask.any():
            continue
        comp_labels, count = label_components(mask)
        for c in range(1, count + 1):
            comp = comp_labels == c
            area = float(comp.sum())
            if area < min_area:
                continue
            ys, xs = np.nonzero(comp)
            if ys[0] == 0 or xs[0] == 0 or ys[-1] == h - 1 or xs[-1] == w - 1:
                continue                       # touches the border: paper
            outer, holes = _contours(comp)
            if outer is None:
                continue
            outer = smooth(simplify(outer, simplify_eps), smooth_iters)
            holes = [smooth(simplify(hp, simplify_eps), smooth_iters)
                     for hp in holes if abs(polygon_area(hp)) >= min_hole]
            # the colour comes from the original picture, not from the
            # blurred copy the shapes were found in
            picked = rgb[ys, xs]
            colour = tuple(int(v) for v in np.median(picked, axis=0))
            regions.append(Region(
                color=colour,
                mask=comp,
                outer=outer,
                holes=holes,
                area=area,
                bbox=(int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))))

    regions.sort(key=lambda r: -r.area)
    return regions


def regions_to_svg(regions, width: int, height: int, stroke="#2b2333",
                   stroke_width: float = 1.4, background: str | None = None,
                   offset=(0.0, 0.0)) -> str:
    """Render traced regions as an SVG document."""
    ox, oy = offset
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
             f'height="{height}" viewBox="0 0 {width} {height}">']
    if background:
        parts.append(f'<rect width="{width}" height="{height}" fill="{background}"/>')
    for r in regions:
        pts = " ".join(f"{p[0] + ox:.2f},{p[1] + oy:.2f}" for p in r.outer)
        parts.append(f'<polygon points="{pts}" fill="{r.name}" stroke="{stroke}" '
                     f'stroke-width="{stroke_width}" stroke-linejoin="round"/>')
        for hp in r.holes:
            hpts = " ".join(f"{p[0] + ox:.2f},{p[1] + oy:.2f}" for p in hp)
            parts.append(f'<polygon points="{hpts}" fill="{background or "#ffffff"}" '
                         f'stroke="{stroke}" stroke-width="{stroke_width}" '
                         f'stroke-linejoin="round"/>')
    parts.append("</svg>")
    return "\n".join(parts)


def region_report(regions, limit: int = 40) -> str:
    lines = [f"{'#':>3} {'colour':>8} {'area':>7}  bbox"]
    for i, r in enumerate(regions[:limit]):
        lines.append(f"{i:>3} {r.name:>8} {int(r.area):>7}  {r.bbox}")
    return "\n".join(lines)
