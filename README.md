# JIANMO — 3D Character & Creature Gallery

[![Version](https://img.shields.io/badge/version-0.3.0-c6a77b)](package.json) [![Deploy](https://github.com/GSvegetable/jianmo/actions/workflows/deploy.yml/badge.svg)](https://github.com/GSvegetable/jianmo/actions/workflows/deploy.yml)

**Online preview:** https://gsvegetable.github.io/jianmo/

A premium, interactive 3D gallery for characters, animals, and original-creature art. The current collection begins with chibi-inspired prototypes of the four members of Kessoku Band from *Bocchi the Rock!*.

## Release

- **Current version:** `0.3.0`
- **Release stage:** Early prototype
- **Current collection:** Hitori Gotoh, Nijika Ijichi, Ryo Yamada, and Ikuyo Kita
- **Rendering:** Three.js + React Three Fiber
- **Experience modes:** Automatic exhibition and free exploration

Version numbers follow Semantic Versioning where practical:
- **PATCH** (`0.2.1`): fixes and small refinements
- **MINOR** (`0.3.0`): backward-compatible features and meaningful content additions
- **MAJOR** (`1.0.0`): major milestone or breaking architectural changes

Update the version in both this README and `package.json` whenever a release-worthy project update is made.

## Version 0.3.0 — character modeling pass 01\n\n- Rebuilt the four character silhouettes and face details.\n- Added character-specific hair accessories and outfit color blocking.\n- Added a dedicated drum kit for Nijika and a longer-neck bass for Ryo; Bocchi and Kita retain individual guitar variants.\n- Kept the models procedural so they remain lightweight and editable in the browser.\n\n## Current features

- Four selectable character records with individual details and color identities
- Refined procedural chibi character models with differentiated hair silhouettes, layered outfits, facial details, and character-specific instruments (guitar, bass, or drum kit)
- Exhibition mode with slow automatic presentation
- Exploration mode with orbit, zoom, and pan controls
- Studio environment lighting, contact shadows, and viewport framing
- Catalog-driven GLB/glTF model registration
- Responsive desktop, tablet, and mobile layout
- GitHub Pages deployment on updates to `main`

> **Model status:** The four characters are currently procedural geometry prototypes, not final production-grade sculpts. This is the first dedicated character-modeling pass. The models are still stylized procedural meshes rather than final production-grade sculpts; facial likeness, fine costume construction, hand posing, instrument accuracy, and animation remain in progress. Replace or augment them with optimized, properly licensed GLB assets as the collection matures.

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

Every push to `main` triggers the GitHub Actions workflow in `.github/workflows/deploy.yml`. Once the repository's Pages source is configured to **GitHub Actions**, the production build is published automatically to:

https://gsvegetable.github.io/jianmo/

The first Pages deployment may require enabling **Settings → Pages → Build and deployment → Source → GitHub Actions** in the repository settings.
