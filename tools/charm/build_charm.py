"""Build the Kita Ikuyo charm from the reference sheet.

The charm is not modelled by hand.  It is *taken* from the official
character sheet: the drawing is cut into the pieces it is made of, the
pieces are re-assembled at chibi proportions, and the result is given a
thickness so it reads as a charm rather than a picture.

Run it with:

    python3 tools/charm/build_charm.py --out build/charm

The layout of the charm -- how big the head is compared to the body, where
the two halves meet -- is described by the constants at the top of the
file, so the proportions can be tuned without touching the code that does
the work.
"""

from __future__ import annotations

import argparse
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from tools.charm.charm3d import build as build_charm_model
from tools.charm.compose import (Part, assemble, classify, load, render,
                                 render_svg)
from tools.charm.segment import Region

WORK = os.environ.get("CHARM_WORK", "/workspace/build/charm")
SHEET = os.environ.get(
    "CHARM_SHEET",
    "/workspace/attachments/3c341341e7b3cdfe/mmexport1795784867188.jpg")

# where the reference material is on the sheet
CUTS = {
    "head_front": (748, 1132, 954, 1400),     # the head, from the expressions
    "front": (140, 100, 430, 1050),           # the whole figure, from the front
    "back": (810, 105, 990, 800),             # the whole figure, from behind
}

CANVAS = (1536, 1920)

# The head is drawn large in the expression sheet, the body is drawn at
# normal height in the full body view.  They are scaled independently and
# then stacked, which is what turns a seven head figure into a chibi.
# The head ends up 40% of the height of the charm, which is what makes it
# read as a big head rather than a small one on a tall body.
HEAD_SCALE = 4.40
HEAD_ORIGIN = (381, -12)          # canvas position of the head's top left

BODY_SCALE = 1.315
BODY_ORIGIN = (577, 540)

CHARM_HEIGHT_MM = 58.0


def cut(name: str) -> str:
    """Cut a piece out of the reference sheet and save it."""
    image = Image.open(SHEET).convert("RGB")
    path = os.path.join(WORK, f"charm_{name}.png")
    image.crop(CUTS[name]).save(path)
    return path


def head_piece() -> Part:
    """The head, taken from the expression sheet.

    The expression sheet draws the head with the collar and the bow below
    it; those belong to the body, so they are dropped here and taken from
    the full body view instead.
    """
    part = load(cut("head_front"), "head")
    drop = []
    for i, region in enumerate(part.regions):
        group, _depth = classify(region)
        _x0, y0, _x1, _y1 = region.bbox
        if group in ("cream", "pink", "ink") and y0 > 180:
            drop.append(i)          # the collar and the bow
    part.drop = drop
    return part.placed(HEAD_SCALE, HEAD_ORIGIN[0], HEAD_ORIGIN[1])


def body_piece() -> Part:
    """The body, taken from the full body front view.

    The hair and the face of this view are dropped: the head comes from the
    expression sheet, which draws it much larger.
    """
    part = load(cut("front"), "body")
    drop = []
    for i, region in enumerate(part.regions):
        group, _depth = classify(region)
        x0, y0, x1, y1 = region.bbox
        if group in ("hair", "hairdk"):
            drop.append(i)          # the hair belongs to the head
        elif group == "cream" and y1 < 215 and (y1 - y0) < 120:
            drop.append(i)          # the face and the neck
    part.drop = drop
    return part.placed(BODY_SCALE, BODY_ORIGIN[0], BODY_ORIGIN[1])


def back_head_piece(head: Part) -> Part:
    """The back of the head.

    The expression sheet only draws the front of the head, but the back of
    it is the same shape with the face gone.  So the face is filled in with
    the colour of the hair and the strands are kept -- which means the back
    of the head has exactly the same outline as the front of it, and the
    two views line up when the charm is turned around.
    """
    part = Part("back_head", list(head.regions), head.scale, head.ox, head.oy)
    face = None
    hair_colour = (212, 77, 67)
    for i, region in enumerate(head.regions):
        group, _depth = classify(region)
        _x0, y0, _x1, _y1 = region.bbox
        if group == "cream" and 110 < y0 < 185 and (region.bbox[2] - region.bbox[0]) > 40:
            face = region
            part.drop.append(i)
        elif group in ("green", "ink", "pink") and y0 < 200:
            part.drop.append(i)          # the eyes, the brows, the mouth
        elif group == "hairdk" and y0 < 210:
            part.drop.append(i)          # the shadow in the fringe
        elif group == "hair":
            hair_colour = region.color
    if face is not None:
        filler = Region(color=hair_colour, mask=face.mask, outer=face.outer,
                        holes=[], area=face.area, bbox=face.bbox)
        part.regions.append(filler)
    return part


def _canvas_bbox(part: Part):
    """The bounding box of a part once it has been placed on the canvas."""
    xs, ys = [], []
    for i, region in enumerate(part.regions):
        if i in part.drop:
            continue
        poly = part.to_canvas(region.outer)
        xs += [float(poly[:, 0].min()), float(poly[:, 0].max())]
        ys += [float(poly[:, 1].min()), float(poly[:, 1].max())]
    return (min(xs), min(ys), max(xs), max(ys))


def back_body_piece(front: Part) -> Part:
    """The body seen from behind, taken from the back view.

    The back view is drawn smaller on the sheet, so it is measured and
    fitted to the body of the front view rather than guessed at.
    """
    part = load(cut("back"), "back_body")
    drop = []
    for i, region in enumerate(part.regions):
        group, _depth = classify(region)
        if group in ("hair", "hairdk"):
            drop.append(i)              # the hair belongs to the head
    part.drop = drop

    front_box = _canvas_bbox(front)
    back_regions = [r for i, r in enumerate(part.regions) if i not in part.drop]
    xs = [r.bbox[0] for r in back_regions] + [r.bbox[2] for r in back_regions]
    ys = [r.bbox[1] for r in back_regions] + [r.bbox[3] for r in back_regions]
    back_box = (min(xs), min(ys), max(xs), max(ys))
    fit = (front_box[3] - front_box[1]) / max(1.0, back_box[3] - back_box[1])
    ox = (front_box[0] + front_box[2]) * 0.5 - (back_box[0] + back_box[2]) * 0.5 * fit
    oy = front_box[1] - back_box[1] * fit
    return part.placed(fit, ox, oy)


def _flatten(art: Image.Image, colour=(240, 232, 218)) -> Image.Image:
    """Lay the drawing on the colour of the edge of the charm.

    The drawing is cut out of the charm, so the parts of the picture that
    are not the character -- the little gaps between the strands of hair --
    show the colour of the edge rather than a hole.
    """
    base = Image.new("RGBA", art.size, tuple(colour) + (255,))
    base.alpha_composite(art)
    return base.convert("RGBA")


def build_all(out_dir: str):
    os.makedirs(out_dir, exist_ok=True)

    head = head_piece()
    body = body_piece()

    front_regions = assemble([head, body])
    front_art = render(front_regions, CANVAS[0], CANVAS[1], supersample=2)
    front_art.save(os.path.join(out_dir, "front-art.png"))
    front_cut = front_art
    front_art.save(os.path.join(out_dir, "front.png"))
    with open(os.path.join(out_dir, "front.svg"), "w") as handle:
        handle.write(render_svg(front_regions, CANVAS[0], CANVAS[1]))

    back_regions = assemble([back_head_piece(head), back_body_piece(body)])
    back_art = render(back_regions, CANVAS[0], CANVAS[1], supersample=2)
    back_art.save(os.path.join(out_dir, "back-art.png"))
    back_cut = back_art
    back_art.save(os.path.join(out_dir, "back.png"))
    with open(os.path.join(out_dir, "back.svg"), "w") as handle:
        handle.write(render_svg(back_regions, CANVAS[0], CANVAS[1]))

    # the outline of the whole character, taken from the drawing itself
    alpha = np.asarray(front_cut)[..., 3] > 127
    ys, xs = np.nonzero(alpha)
    centre = (float(xs.mean()), float(ys.mean()))
    scale = CHARM_HEIGHT_MM / float(ys.max() - ys.min())

    stats = build_charm_model(
        front_regions, front_art.width, front_art.height,
        os.path.join(out_dir, "ikuyo-kita-charm.glb"),
        os.path.join(out_dir, "front.png"),
        os.path.join(out_dir, "back.png"),
        scale=scale, centre=centre)
    return {"front_regions": len(front_regions),
            "back_regions": len(back_regions),
            "glb": stats}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="/workspace/build/charm")
    args = parser.parse_args()
    info = build_all(args.out)
    print(f"front: {info['front_regions']} regions")
    print(f"back:  {info['back_regions']} regions")
    print("glb:  ", info["glb"])


if __name__ == "__main__":
    main()
