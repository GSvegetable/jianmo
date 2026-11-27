#!/usr/bin/env python3
"""Build the character GLB assets with the SDF body pipeline.

The body (skin, uniform, face) is one continuous implicit surface blended
with smooth booleans and extracted with Surface Nets. Hair and instruments
are added as regular meshes on top.

Usage:
    python3 tools/build_characters.py
    python3 tools/build_characters.py --only ryo --spacing 0.007
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.chibi.character import build_materials, build_props  # noqa: E402
from tools.chibi.glb import export_glb  # noqa: E402
from tools.chibi.mesh import split_by_material  # noqa: E402
from tools.chibi.roster import ROSTER  # noqa: E402
from tools.chibi.sdf_body import extract_body  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "public", "models", "characters")
STATS_PATH = os.path.join(ROOT, "public", "models", "characters", "manifest.json")


def build_one(spec, out_dir: str, spacing: float, write: bool = True) -> dict:
    started = time.perf_counter()

    body, vertex_materials, cloth = extract_body(spec, spacing)
    parts = split_by_material(body, vertex_materials)
    parts.extend(cloth)
    parts.extend(build_props(spec))
    materials = build_materials(spec)

    low, high = None, None
    for part in parts:
        lo, hi = part.bounds()
        low = lo if low is None else np.minimum(low, lo)
        high = hi if high is None else np.maximum(high, hi)

    path = os.path.join(out_dir, spec.filename)
    stats = {}
    if write:
        os.makedirs(out_dir, exist_ok=True)
        stats = export_glb(
            path,
            parts,
            materials,
            name=f"{spec.id}_{spec.name}",
            generator="jianmo procedural chibi pipeline (SDF + Surface Nets)",
            scene_extras={
                "character": {
                    "id": spec.id,
                    "name": spec.name,
                    "source": "Bocchi the Rock! (fan-made procedural model)",
                },
                "build": {
                    "unit": "metre",
                    "method": "signed distance field + smooth booleans + surface nets",
                    "voxel_size": spacing,
                    "height": round(float(high[1] - low[1]), 4),
                    "triangles": sum(p.tri_count for p in parts),
                    "vertices": sum(p.vert_count for p in parts),
                    "materials": len(materials),
                },
            },
        )

    elapsed = time.perf_counter() - started
    return {
        "id": spec.id,
        "name": spec.name,
        "file": spec.filename,
        "bytes": stats.get("bytes", 0),
        "triangles": sum(p.tri_count for p in parts),
        "vertices": sum(p.vert_count for p in parts),
        "materials": len(materials),
        "bounds": {
            "min": [round(float(x), 4) for x in low],
            "max": [round(float(x), 4) for x in high],
        },
        "height": round(float(high[1] - low[1]), 4),
        "seconds": round(elapsed, 2),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", nargs="*", help="character ids to build")
    parser.add_argument("--out", default=OUT_DIR, help="output directory")
    parser.add_argument("--spacing", type=float, default=0.008,
                        help="SDF sampling step; smaller is finer and slower")
    parser.add_argument("--stats", action="store_true", help="only report, do not write")
    args = parser.parse_args()

    roster = [s for s in ROSTER if not args.only or s.id in args.only]
    if not roster:
        print("no characters matched", file=sys.stderr)
        return 1

    results = []
    for spec in roster:
        print(f"building {spec.name} ({spec.id}) ...", flush=True)
        info = build_one(spec, args.out, args.spacing, write=not args.stats)
        results.append(info)
        size = f"{info['bytes'] / 1024:.0f} KB" if info["bytes"] else "not written"
        print(f"  {info['triangles']:>7,} tris  {info['vertices']:>7,} verts  "
              f"{size:>10}  h={info['height']:.3f}  {info['seconds']}s")

    manifest = {
        "generator": "jianmo procedural chibi pipeline",
        "method": "signed distance field + smooth booleans + surface nets",
        "characters": results,
    }
    if not args.stats:
        os.makedirs(os.path.dirname(STATS_PATH), exist_ok=True)
        with open(STATS_PATH, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        print(f"\nwrote {STATS_PATH}")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
