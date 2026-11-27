"""Minimal, dependency-free glTF 2.0 / GLB writer.

The repository has no 3D toolchain in its npm dependencies, so the character
assets are emitted by this writer instead of an external DCC export. It
writes a single-node scene with one mesh primitive per material, which is
exactly what ``useGLTF`` in the viewer expects.
"""

from __future__ import annotations

import json
import struct
from dataclasses import dataclass, field

import numpy as np

from .mesh import Mesh, merge_by_material

GLB_MAGIC = 0x46546C67
CHUNK_JSON = 0x4E4F534A
CHUNK_BIN = 0x004E4942

_COMP_FLOAT = 5126
_COMP_UINT32 = 5125
_TARGET_ARRAY_BUFFER = 34962
_TARGET_ELEMENT_ARRAY_BUFFER = 34963


@dataclass
class Material:
    """A metallic-roughness PBR material."""

    name: str
    base_color: tuple = (0.8, 0.8, 0.8, 1.0)
    metallic: float = 0.0
    roughness: float = 0.65
    emissive: tuple | None = None
    double_sided: bool = False
    base_color_texture: int | None = None
    alpha_mode: str | None = None
    extras: dict = field(default_factory=dict)

    def to_gltf(self) -> dict:
        mat: dict = {
            "name": self.name,
            "pbrMetallicRoughness": {
                "baseColorFactor": [float(c) for c in self.base_color],
                "metallicFactor": float(self.metallic),
                "roughnessFactor": float(self.roughness),
            },
        }
        if self.emissive is not None:
            mat["emissiveFactor"] = [float(c) for c in self.emissive]
        if self.base_color_texture is not None:
            mat["pbrMetallicRoughness"]["baseColorTexture"] = {
                "index": int(self.base_color_texture)}
        if self.alpha_mode:
            mat["alphaMode"] = self.alpha_mode
        if self.double_sided:
            mat["doubleSided"] = True
        if self.extras:
            mat["extras"] = self.extras
        return mat


def srgb_to_linear(c: float) -> float:
    """Convert an sRGB colour channel to the linear space glTF expects."""
    if c <= 0.04045:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def hex_to_linear(hex_color: str, alpha: float = 1.0) -> tuple:
    """'#rrggbb' (sRGB) -> linear RGBA tuple used by glTF baseColorFactor."""
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    return (srgb_to_linear(r), srgb_to_linear(g), srgb_to_linear(b), float(alpha))


class _BufferBuilder:
    """Accumulates buffer views with 4-byte alignment."""

    def __init__(self):
        self.data = bytearray()
        self.views: list = []

    def add(self, array: np.ndarray, target: int) -> int:
        arr = np.ascontiguousarray(array)
        # 4-byte alignment for float and uint32 accessors
        pad = (-len(self.data)) % 4
        if pad:
            self.data.extend(b"\x00" * pad)
        offset = len(self.data)
        self.data.extend(arr.tobytes())
        self.views.append({
            "buffer": 0,
            "byteOffset": offset,
            "byteLength": int(arr.nbytes),
            "target": target,
        })
        return len(self.views) - 1


def _accessor(view_index: int, component_type: int, count: int, type_name: str,
              minmax: tuple | None = None) -> dict:
    acc: dict = {
        "bufferView": view_index,
        "componentType": component_type,
        "count": int(count),
        "type": type_name,
    }
    if minmax is not None:
        acc["min"], acc["max"] = [float(x) for x in minmax[0]], [float(x) for x in minmax[1]]
    return acc


def export_glb(path, parts, materials, name="model", generator=None,
               scene_extras: dict | None = None, textures=None) -> dict:
    """Write a GLB file and return a stats dictionary.

    ``parts`` is a list of :class:`~chibi.mesh.Mesh` objects; they are merged
    per material so the file holds one primitive per material.
    ``materials`` is the ordered list of :class:`Material` slots.
    ``textures`` is an optional list of ``(name, png_path)`` pairs; the
    images are embedded in the file and a material refers to one of them
    through ``Material.base_color_texture``.
    """
    builder = _BufferBuilder()
    accessors: list = []
    gltf_meshes: list = []
    node_children: list = []
    used_materials: list[int] = []
    total_tris = 0
    total_verts = 0

    grouped = merge_by_material(parts)
    for gi, gm in enumerate(grouped):
        mat_index = gm.mat
        used_materials.append(mat_index)

        positions = gm.v.astype(np.float32)
        pos_view = builder.add(positions, _TARGET_ARRAY_BUFFER)
        accessors.append(_accessor(pos_view, _COMP_FLOAT, positions.shape[0], "VEC3",
                                   (positions.min(axis=0), positions.max(axis=0))))

        attributes = {"POSITION": len(accessors) - 1}

        if gm.n is not None:
            normals = gm.n.astype(np.float32)
            n_view = builder.add(normals, _TARGET_ARRAY_BUFFER)
            accessors.append(_accessor(n_view, _COMP_FLOAT, normals.shape[0], "VEC3"))
            attributes["NORMAL"] = len(accessors) - 1

        if gm.uv is not None:
            uvs = gm.uv.astype(np.float32)
            uv_view = builder.add(uvs, _TARGET_ARRAY_BUFFER)
            accessors.append(_accessor(uv_view, _COMP_FLOAT, uvs.shape[0], "VEC2"))
            attributes["TEXCOORD_0"] = len(accessors) - 1

        indices = gm.f.astype(np.uint32).reshape(-1)
        idx_view = builder.add(indices, _TARGET_ELEMENT_ARRAY_BUFFER)
        accessors.append(_accessor(idx_view, _COMP_UINT32, indices.shape[0], "SCALAR"))

        gltf_meshes.append({
            "name": f"{name}_{gi:02d}",
            "primitives": [{
                "attributes": attributes,
                "indices": len(accessors) - 1,
                "material": mat_index,
                "mode": 4,
            }],
        })
        node_children.append(len(node_children) + 1)  # root is node 0
        total_tris += gm.tri_count
        total_verts += gm.vert_count

    nodes = [{"name": name, "children": node_children}]
    for gi, gm in enumerate(grouped):
        nodes.append({"name": f"{name}_{gi:02d}", "mesh": gi})

    images = []
    samplers = []
    texture_list = []
    for (tname, tex_path) in (textures or []):
        with open(tex_path, "rb") as handle:
            blob = np.frombuffer(handle.read(), dtype=np.uint8)
        view = builder.add(blob, _TARGET_ARRAY_BUFFER)
        images.append({"name": tname, "mimeType": "image/png",
                       "bufferView": view})
        samplers.append({"magFilter": 9729, "minFilter": 9987,
                         "wrapS": 33071, "wrapT": 33071})
        texture_list.append({"sampler": len(samplers) - 1,
                             "source": len(images) - 1})

    gltf = {
        "asset": {
            "version": "2.0",
            "generator": generator or "jianmo procedural chibi pipeline",
        },
        "scene": 0,
        "scenes": [{"name": name, "nodes": [0]}],
        "nodes": nodes,
        "meshes": gltf_meshes,
        "materials": [m.to_gltf() for m in materials],
        "accessors": accessors,
        "bufferViews": builder.views,
        "buffers": [{"byteLength": len(builder.data)}],
    }
    if texture_list:
        gltf["images"] = images
        gltf["samplers"] = samplers
        gltf["textures"] = texture_list
    if scene_extras:
        gltf["extras"] = scene_extras

    json_bytes = json.dumps(gltf, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    json_bytes += b" " * ((-len(json_bytes)) % 4)
    bin_bytes = bytes(builder.data)
    bin_bytes += b"\x00" * ((-len(bin_bytes)) % 4)

    total = 12 + 8 + len(json_bytes) + 8 + len(bin_bytes)
    with open(path, "wb") as fh:
        fh.write(struct.pack("<III", GLB_MAGIC, 2, total))
        fh.write(struct.pack("<II", len(json_bytes), CHUNK_JSON))
        fh.write(json_bytes)
        fh.write(struct.pack("<II", len(bin_bytes), CHUNK_BIN))
        fh.write(bin_bytes)

    return {
        "path": str(path),
        "bytes": total,
        "triangles": total_tris,
        "vertices": total_verts,
        "materials": len(used_materials),
        "meshes": len(gltf_meshes),
        "accessors": len(accessors),
    }
