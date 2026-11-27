"""Compose the chibi charm artwork out of the traced reference sheets.

The reference sheet is drawn at normal human proportions, and a charm needs
the opposite: a big head on a small body.  So the drawing is not scaled as
one piece.  It is taken apart into its coloured parts, and the parts are
re-assembled at chibi proportions:

    the head comes from the expression sheet, where it is drawn large,
    the body comes from the full body front view,
    the back of the head and the back of the body come from the back view.

Nothing is invented.  Every shape in the result is a shape the illustrator
drew; only the proportions and the arrangement are new.

Parts are ordered by how far forward they sit (the depth in :data:`PALETTE`)
so that the drawing stacks correctly: the hair covers the face, the skirt
covers the legs, the shoes cover the socks.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from PIL import Image, ImageDraw

from .segment import Region, segment

# The colour of every part of the outfit, sampled from the reference sheet,
# with the depth the part sits at.  A bigger depth is drawn further forward.
# The tolerance is generous on purpose: the sheets are printed with a screen
# and the shading drifts a long way from the flat colour in the palette, and
# the nearest colour still wins when two are close.
PALETTE = [
    ("ink",    ( 35,  31,  38),  55, 10),
    ("green",  (154, 174,  80),  65,  9),
    ("brown",  ( 92,  60,  54),  48,  8),
    ("hairdk", (147,  20,  29),  55,  7),
    ("hair",   (212,  77,  67),  95,  6),
    ("pink",   (228, 107, 106),  30,  5),
    ("white",  (244, 249, 252),  22,  4),
    ("navy",   ( 53,  67,  92),  45,  3),
    ("cream",  (242, 225, 202),  28,  2),
]

DEPTH_OF = {name: depth for name, _c, _t, depth in PALETTE}


@dataclass
class Part:
    """A traced piece of the drawing, ready to be placed on the canvas."""

    name: str
    regions: list
    scale: float = 1.0
    ox: float = 0.0
    oy: float = 0.0
    drop: list = field(default_factory=list)   # region indices to leave out

    def placed(self, scale: float, ox: float, oy: float) -> "Part":
        return Part(self.name, self.regions, scale, ox, oy, list(self.drop))

    def kept(self):
        return [r for i, r in enumerate(self.regions) if i not in self.drop]

    def to_canvas(self, pts: np.ndarray) -> np.ndarray:
        return pts * self.scale + np.array([self.ox, self.oy])


@dataclass
class Region2:
    """A region after it has been moved onto the canvas."""

    group: str
    depth: int
    color: tuple
    outer: np.ndarray
    holes: list = field(default_factory=list)
    source: str = ""


def classify(region: Region) -> tuple:
    """Find the part of the outfit a region belongs to."""
    col = np.asarray(region.color, dtype=np.float64)
    best = None
    best_d = 1e9
    for name, ref, tol, depth in PALETTE:
        d = float(np.linalg.norm(col - np.asarray(ref, dtype=np.float64)))
        if d < best_d:
            best_d = d
            best = (name, depth, tol)
    name, depth, tol = best
    if best_d > tol:
        return ("other", 1)
    return (name, depth)


def load(path: str, name: str, k: int = 16, merge_tol: float = 14.0,
         colour_tol: float = 24.0, min_area: int = 42, close: int = 1) -> Part:
    """Trace one sheet into coloured parts.

    Tracing a sheet takes a while, so the result is cached next to it.
    """
    import os
    import pickle

    cache = os.path.splitext(path)[0] + ".parts"
    stamp = (k, merge_tol, colour_tol, min_area, close)
    if os.path.exists(cache):
        with open(cache, "rb") as handle:
            saved_stamp, regions = pickle.load(handle)
        if saved_stamp == stamp:
            return Part(name, regions)

    image = Image.open(path).convert("RGB")
    rgb = np.asarray(image)
    regions = segment(rgb, k=k, colour_tol=colour_tol,
                      merge_tol=merge_tol, min_area=min_area, close=close)
    with open(cache, "wb") as handle:
        pickle.dump((stamp, regions), handle)
    return Part(name, regions)


def group_of(region: Region) -> str:
    return classify(region)[0]


def assemble(parts: list) -> list:
    """Move every part onto the canvas and sort them back to front."""
    out = []
    for part in parts:
        for region in part.kept():
            group, depth = classify(region)
            if group == "other":
                continue
            outer = part.to_canvas(region.outer)
            holes = [part.to_canvas(h) for h in region.holes]
            out.append(Region2(group=group, depth=depth, color=region.color,
                                outer=outer, holes=holes, source=part.name))
    out.sort(key=lambda r: (r.depth, -abs(_signed_area(r.outer))))
    return out


def _signed_area(poly: np.ndarray) -> float:
    x, y = poly[:, 0], poly[:, 1]
    return 0.5 * float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def render(regions: list, width: int, height: int, supersample: int = 3):
    """Draw the assembled regions into an image."""
    big = Image.new("RGBA", (width * supersample, height * supersample),
                    (0, 0, 0, 0))
    for region in regions:
        mask = Image.new("L", big.size, 0)
        draw = ImageDraw.Draw(mask)
        outer = [(float(p[0]), float(p[1])) for p in region.outer * supersample]
        if len(outer) >= 3:
            draw.polygon(outer, fill=255)
            for hole in region.holes:
                pts = [(float(p[0]), float(p[1])) for p in hole * supersample]
                if len(pts) >= 3:
                    draw.polygon(pts, fill=0)
        colour = Image.new("RGBA", big.size, tuple(int(c) for c in region.color) + (255,))
        big.paste(colour, (0, 0), mask)
    return big.resize((width, height), Image.LANCZOS)


def render_svg(regions: list, width: int, height: int, background: str = "#ffffff"):
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
             f'height="{height}" viewBox="0 0 {width} {height}">',
             f'<rect width="{width}" height="{height}" fill="{background}"/>']
    for region in regions:
        pts = " ".join(f"{p[0]:.2f},{p[1]:.2f}" for p in region.outer)
        colour = "#%02x%02x%02x" % tuple(int(c) for c in region.color)
        parts.append(f'<polygon points="{pts}" fill="{colour}" stroke="#241f26" '
                     f'stroke-width="1.4" stroke-linejoin="round"/>')
        for hole in region.holes:
            hpts = " ".join(f"{p[0]:.2f},{p[1]:.2f}" for p in hole)
            parts.append(f'<polygon points="{hpts}" fill="{background}" '
                         f'stroke="#241f26" stroke-width="1.4" '
                         f'stroke-linejoin="round"/>')
    parts.append("</svg>")
    return "\n".join(parts)


def silhouette(regions: list, width: int, height: int, supersample: int = 2):
    """The outline of the drawing: everything that is covered."""
    big = Image.new("L", (width * supersample, height * supersample), 0)
    draw = ImageDraw.Draw(big)
    for region in regions:
        outer = [(float(p[0]), float(p[1])) for p in region.outer * supersample]
        if len(outer) >= 3:
            draw.polygon(outer, fill=255)
    return big.resize((width, height), Image.LANCZOS)
