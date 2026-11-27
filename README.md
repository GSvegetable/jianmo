# JIANMO — Character Model Viewer

[![Version](https://img.shields.io/badge/version-0.6.1-c6a77b)](package.json) [![Deploy](https://github.com/GSvegetable/jianmo/actions/workflows/deploy.yml/badge.svg)](https://github.com/GSvegetable/jianmo/actions/workflows/deploy.yml)

**Online preview:** https://gsvegetable.github.io/jianmo/

A minimal real-time viewer for four standalone character models.

## Release

- **Current version:** `0.6.1`
- **Release stage:** GLB asset pipeline refactor
- **Characters:** Hitori Gotoh, Nijika Ijichi, Ryo Yamada, and Ikuyo Kita
- **Rendering:** Three.js + React Three Fiber + GLB/glTF
- **Controls:** Four character selectors; orbit and zoom in the viewport

## Version 0.6.1 — GLB-first viewer refactor

- Removed the procedural character-building system. Character bodies are no longer assembled from spheres, cones, tubes, and rounded boxes.
- Reduced the public preview to one 3D viewport and four character-switch buttons.
- Added a standalone GLB loading path with automatic model centering and scale normalization.
- Removed gallery navigation, categories, character descriptions, exhibition/exploration modes, settings, and decorative interface panels.
- Defined stable asset paths for the four standalone models under `public/models/characters/`.

## Model asset status

The viewer architecture is now ready for complete GLB assets, but the four final character meshes have **not** been created or imported yet. The current preview therefore shows an unobtrusive asset-in-production state rather than disguising the old procedural models as finished work.

The intended production workflow is:
1. Create each character as a complete, independently authored 3D mesh in Blender or another professional DCC tool.
2. Refine silhouette, facial forms, hair volumes, clothing construction, hands, accessories, and instruments as real mesh work.
3. Create clean topology, UVs, PBR materials, and a consistent neutral pose.
4. Export optimized GLB files into `public/models/characters/`.
5. Set each character's `modelUrl` in `src/data/catalog.js` to its corresponding asset path.

Expected asset paths:
- `/models/characters/hitori-gotoh.glb`
- `/models/characters/nijika-ijichi.glb`
- `/models/characters/ryo-yamada.glb`
- `/models/characters/ikuyo-kita.glb`

**Important:** This connected workspace currently does not expose a 3D mesh-generation capability. No generated mesh has been fabricated or represented as a finished model. The final character assets must be authored or generated through an available 3D production tool and then imported.

## Run locally

```bash
npm install
npm run dev
```

```bash
npm run build
npm run preview
```

## Deployment

Every push to `main` triggers GitHub Actions and deploys the production build to:

https://gsvegetable.github.io/jianmo/

Update the version in both this README and `package.json` on every project update.
