# JIANMO — 3D Character & Creature Gallery

[![Version](https://img.shields.io/badge/version-0.5.1-c6a77b)](package.json) [![Deploy](https://github.com/GSvegetable/jianmo/actions/workflows/deploy.yml/badge.svg)](https://github.com/GSvegetable/jianmo/actions/workflows/deploy.yml)

**Online preview:** https://gsvegetable.github.io/jianmo/

A premium, interactive 3D gallery for characters, animals, and original-creature art. The current collection begins with chibi-inspired prototypes of the four members of Kessoku Band from *Bocchi the Rock!*.

## Release

- **Current version:** `0.5.1`
- **Release stage:** Early prototype
- **Current collection:** Hitori Gotoh, Nijika Ijichi, Ryo Yamada, and Ikuyo Kita
- **Rendering:** Three.js + React Three Fiber
- **Experience modes:** Automatic exhibition and free exploration

Version numbers follow Semantic Versioning where practical:
- **PATCH** (`0.5.1`): fixes and small refinements
- **MINOR** (`0.5.1`): backward-compatible features and meaningful content additions
- **MAJOR** (`1.0.0`): major milestone or breaking architectural changes

Update the version in both this README and `package.json` whenever a release-worthy project update is made.

## Version 0.5.1 — Production build repair

- Added fine raised hair-strand lines to break up smooth hair caps and improve close-range silhouette.
- Refined eyebrow curves and subtle facial linework for clearer expressions.
- Added jacket seam accents, skirt pleat lines, and instrument straps.
- Updated character descriptions and archive status to identify sculpt pass 03.

## Current features

- Four selectable character records with individual details and color identities
- Iterative procedural chibi sculpt studies with layered hair locks and strand accents, facial construction, costume seam details, instrument straps, and character-specific instruments (guitar, bass, or drum kit)
- Exhibition mode with slow automatic presentation
- Exploration mode with orbit, zoom, and pan controls
- Studio environment lighting, contact shadows, and viewport framing
- Catalog-driven GLB/glTF model registration
- Responsive desktop, tablet, and mobile layout
- GitHub Pages deployment on updates to `main`

> **Model status:** The four characters are currently procedural geometry prototypes, not final production-grade sculpts. The models are still stylized procedural meshes rather than final production-grade sculpts; facial likeness, fully sculpted hair volumes, hand posing, instrument accuracy, material polish, and animation remain in progress. Replace or augment them with optimized, properly licensed GLB assets as the collection matures.

## Run locally

```bash
npm install
npm run dev
```

Create a production build and preview it locally:

```bash
npm run build
npm run preview
```

## Add or replace a model

1. Export the model from Blender as optimized GLB/glTF.
2. Place it under `public/models/`.
3. Set `modelUrl` in `src/data/catalog.js`, for example `/models/characters/hitori-gotoh.glb`.
4. Add animation names and character metadata to the catalog entry.

## Quality guidelines

- Prefer GLB with embedded PBR textures.
- Keep animation clips named clearly (Idle, Walk, Turn, etc.).
- Use 2K textures as a practical starting point; reserve 4K for close-up hero assets.
- Keep a high-quality source file separately; provide optimized web exports.
- Include a neutral/rest pose and consistent scale/origin.
- Use original or properly licensed model, texture, and reference assets.

## Deployment

Every push to `main` triggers the GitHub Actions workflow in `.github/workflows/deploy.yml`. The workflow uses GitHub Actions as its publishing source and deploys the generated `dist/` artifact to:

https://gsvegetable.github.io/jianmo/

If Pages has not yet been enabled for this repository, the first deployment may still require **Settings → Pages → Build and deployment → Source → GitHub Actions**.
