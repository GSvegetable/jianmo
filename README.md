# JIANMO — Character Model Viewer

[![Version](https://img.shields.io/badge/version-0.6.2-c6a77b)](package.json) [![Deploy](https://github.com/GSvegetable/jianmo/actions/workflows/deploy.yml/badge.svg)](https://github.com/GSvegetable/jianmo/actions/workflows/deploy.yml)

**Online preview:** https://gsvegetable.github.io/jianmo/

A minimal real-time viewer for four standalone character models.

## Release

- **Current version:** `0.6.2`
- **Release stage:** GLB asset pipeline refactor
- **Characters:** Hitori Gotoh, Nijika Ijichi, Ryo Yamada, and Ikuyo Kita
- **Rendering:** Three.js + React Three Fiber + GLB/glTF
- **Controls:** Four character selectors; orbit and zoom in the viewport

## Version 0.6.2 — Direct GLB asset loading

- Removed the procedural character-building system. Character bodies are no longer assembled from spheres, cones, tubes, and rounded boxes.
- Reduced the public preview to one 3D viewport and four character-switch buttons.
- Added a standalone GLB loading path with automatic model centering and scale normalization.
- Removed gallery navigation, categories, character descriptions, exhibition/exploration modes, settings, and decorative interface panels.
- Defined stable asset paths for the four standalone models under `public/models/characters/`.

## Model asset status

The viewer architecture is now ready for complete GLB assets, but the four final character meshes have **not** been created or imported yet. The four selector entries now point directly to their final GLB paths. Until those files are added, the viewport remains intentionally clean and empty; it does not display placeholder geometry or status copy.

The intended production workflow is:
1. Create each character as a complete, independently authored 3D mesh in Blender or another professional DCC tool.
2. Refine silhouette, facial forms, hair volumes, clothing construction, hands, accessories, and instruments as real mesh work.
3. Create clean topology, UVs, PBR materials, and a consistent neutral pose.
4. Export optimized GLB files into `public/models/characters/`.
5. Place each exported file at the matching path already configured in `src/data/catalog.js`; no additional UI or loader wiring is required.

Expected asset paths:
- `/models/characters/hitori-gotoh.glb`
- `/models/characters/nijika-ijichi.glb`
- `/models/characters/ryo-yamada.glb`
- `/models/characters/ikuyo-kita.glb`

**Important:** The viewer code is ready, but the four final character meshes have not yet been generated or imported. No placeholder has been represented as a finished model.

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
