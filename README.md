# JIANMO — 3D Creature Gallery

A premium, interactive 3D gallery foundation for character, animal, and original-creature art.

## Current foundation

- React + Vite application shell
- Three.js rendering through React Three Fiber
- Exhibition mode with slow automatic presentation
- Exploration mode with orbit, zoom, and pan controls
- Studio environment lighting, contact shadows, and viewport framing
- Catalog-driven model registration
- GLB/glTF loader path ready for incoming assets
- Responsive desktop, tablet, and mobile layout

## Run locally

```bash
npm install
npm run dev
```

## Add a model

1. Export the model from Blender as optimized GLB/glTF.
2. Place it under `public/models/`.
3. Set `modelUrl` in `src/data/catalog.js`, for example `/models/creatures/creature-001.glb`.
4. Add animation names and specimen metadata to the catalog entry.

The current viewport sculpture is only a temporary engine placeholder. It is not the first creature model and will be replaced when the actual asset is supplied.

## Quality guidelines for incoming assets

- Prefer GLB with embedded PBR textures.
- Keep animation clips named clearly (Idle, Walk, Turn, etc.).
- Use 2K textures as a practical starting point; reserve 4K for close-up hero assets.
- Keep a high-quality source file separately; provide optimized web exports.
- Include a neutral/rest pose and consistent scale/origin.
