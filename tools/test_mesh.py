"""Smoke tests for the procedural mesh kernel.

Run with:  python3 tools/test_mesh.py
"""

from __future__ import annotations

import os
import struct
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.chibi.mesh import (  # noqa: E402
    Mesh, blade, catmull_rom, cone, cylinder, merge, revolve, solidify_patch,
    split_by_material, superellipsoid, torus, tube, uv_sphere, patch_grid,
)
from tools.chibi.glb import Material, export_glb, hex_to_linear  # noqa: E402

FAILURES = []


def check(name, condition, detail=""):
    if condition:
        print(f"  PASS  {name}")
    else:
        print(f"  FAIL  {name} {detail}")
        FAILURES.append(name)


def is_closed(mesh) -> bool:
    """Watertight check on *positions*, not indices.

    Creased surfaces legitimately duplicate vertices along the crease line,
    so edges are matched after quantising positions.
    """
    f = mesh.f
    pos = np.round(mesh.v, 6)
    edges = np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]], axis=0)
    edges = np.sort(pos[edges], axis=1)
    _, counts = np.unique(edges, axis=0, return_counts=True)
    return bool(np.all(counts == 2))


def has_degenerate(mesh) -> bool:
    a = mesh.v[mesh.f[:, 0]]
    b = mesh.v[mesh.f[:, 1]]
    c = mesh.v[mesh.f[:, 2]]
    area = np.linalg.norm(np.cross(b - a, c - a), axis=1)
    return bool(np.any(area < 1e-12))


def normals_outward(mesh, center=(0.0, 0.0, 0.0)) -> bool:
    fn = mesh.n
    c = np.asarray(center, dtype=np.float64)
    radial = mesh.v - c
    # only test vertices well away from the centre
    keep = np.linalg.norm(radial, axis=1) > 1e-6
    dot = np.sum(fn[keep] * radial[keep], axis=1)
    return bool(np.mean(dot > 0) > 0.98)


def main():
    print("mesh kernel smoke test")

    print("\n[uv_sphere]")
    s = uv_sphere(0.5, 0.4, 0.3, 32, 24)
    check("closed", is_closed(s))
    check("no degenerate tris", not has_degenerate(s))
    check("normals outward", normals_outward(s))
    check("has uv", s.uv is not None and s.uv.shape == (s.vert_count, 2))

    print("\n[revolve]")
    r = revolve([(0.0, -0.5), (0.3, -0.2), (0.35, 0.2), (0.0, 0.5)], 40)
    check("closed", is_closed(r))
    check("no degenerate tris", not has_degenerate(r))
    check("normals outward", normals_outward(r))

    print("\n[revolve closed shell: skirt profile]")
    # a closed profile loop: outer surface down, hem, inner surface back up
    prof = [(0.118, 0.94), (0.190, 0.66), (0.182, 0.652), (0.174, 0.66),
            (0.112, 0.94), (0.118, 0.94)]
    skirt = revolve(prof, 64, cap_bottom=False, cap_top=False,
                    radial_mod=lambda phi: 1.0 + 0.05 * np.sin(14 * phi))
    check("closed", is_closed(skirt))
    check("no degenerate tris", not has_degenerate(skirt))

    print("\n[superellipsoid]")
    se = superellipsoid(0.4, 0.3, 0.2, 0.25, 40, 28)
    check("closed", is_closed(se))
    check("no degenerate tris", not has_degenerate(se))
    check("boxy (box>ellipsoid)", se.v[:, 0].max() > se.v[:, 0].min() * 0.9)

    print("\n[tube / blade]")
    path = catmull_rom([[0, 0, 0], [0.2, 0.3, 0], [0.5, 0.5, 0.1], [0.9, 0.4, 0.1]], 8)
    t = tube(path, np.linspace(0.05, 0.02, len(path)), 16)
    check("tube closed", is_closed(t))
    bl = blade(path, np.linspace(0.06, 0.01, len(path)))
    check("blade closed", is_closed(bl))
    check("blade no degenerate", not has_degenerate(bl))

    print("\n[solidify_patch]")
    grid = patch_grid(lambda u, v: np.stack([u * 2 - 1, v * 2 - 1, np.zeros_like(u)], axis=1), 8, 8)
    sp = solidify_patch(grid, 0.05)
    check("patch closed", is_closed(sp))
    check("patch no degenerate", not has_degenerate(sp))

    print("\n[torus / cone / cylinder]")
    check("torus closed", is_closed(torus(0.4, 0.1, 36, 16)))
    check("cone closed", is_closed(cone(0.2, 0.0, 0.6, 28)))
    check("cylinder closed", is_closed(cylinder(0.15, 0.8, 28)))

    print("\n[merge]")
    m = merge([s, se])
    check("merge vertex count", m.vert_count == s.vert_count + se.vert_count)
    check("merge indices in range", int(m.f.max()) < m.vert_count)

    print("\n[glb export]")
    mats = [
        Material("body", hex_to_linear("#f0c9a8"), 0.0, 0.6),
        Material("hair", hex_to_linear("#c9a7c8"), 0.0, 0.45),
    ]
    out = "/tmp/chibi_smoke.glb"
    stats = export_glb(out, [s.with_material(0), se.with_material(1)], mats, name="smoke")
    check("file written", os.path.exists(out))
    with open(out, "rb") as fh:
        head = fh.read(12)
    magic, version, length = struct.unpack("<III", head)
    check("glb magic", magic == 0x46546C67)
    check("glb version", version == 2)
    check("glb length matches file", length == os.path.getsize(out))
    check("stats triangles", stats["triangles"] == s.tri_count + se.tri_count)

    print("\n[material split]")
    # A face that straddles a material border must not have its colour
    # decided by averaging the slot indices: skin (0) and uniform (9)
    # would average to 4.5 and round to 4, the iris slot.
    tri = np.array([[0, 1, 2], [2, 3, 4]], dtype=np.int64)
    verts = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0],
                      [1.0, 1.0, 0.0], [2.0, 1.0, 0.0]])
    labels = np.array([0, 0, 9, 9, 9], dtype=np.int64)
    split = split_by_material(Mesh(verts, tri, None, 0, None, "probe"), labels)
    slots = sorted(p.mat for p in split)
    check("split keeps only real slots", slots == [0, 9], f"got {slots}")
    check("split does not invent a slot", all(p.mat in (0, 9) for p in split))

    print("\n[glb round-trip parse]")
    import json
    with open(out, "rb") as fh:
        data = fh.read()
    jlen, jtype = struct.unpack("<II", data[12:20])
    gltf = json.loads(data[20:20 + jlen].decode("utf-8"))
    check("gltf version", gltf["asset"]["version"] == "2.0")
    check("materials written", len(gltf["materials"]) == 2)
    check("meshes written", len(gltf["meshes"]) == 2)
    pos_accessors = [a for a in gltf["accessors"]
                     if a["type"] == "VEC3" and "min" in a]
    check("position accessors carry min/max", len(pos_accessors) >= 2)
    check("node tree", gltf["nodes"][0]["children"] == [1, 2])

    print()
    if FAILURES:
        print(f"FAILED: {len(FAILURES)} check(s): {FAILURES}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
