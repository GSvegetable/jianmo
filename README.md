# JIANMO — Character Sculpt Study

Online preview: https://gsvegetable.github.io/jianmo/

JIANMO is a browser-based 3D character viewer built with React Three Fiber and Three.js. The current production scope is deliberately reduced to one hero character: 喜多郁代.

## Release

- Current version: 0.11.0
- Runtime formats: glTF 2.0 / GLB and VRM
- VRM support: MToon materials and spring-bone updates through `@pixiv/three-vrm`
- Current hero fallback: `public/models/characters/ikuyo-kita.glb`

## Honest asset status

The current Kita GLB is still a legacy procedural SDF model. It has a dense triangulated surface, but its silhouette, facial construction, hair design and clothing are not yet at the quality expected of a finished character sculpt. Increasing polygon count alone will not solve those shortcomings.

The other three character models, their catalog entries, and the acrylic-style charm are retained in the repository unchanged. They are simply not shown on the current single-character preview page; nothing has been deleted.

## Hero asset acceptance criteria

The next Kita model is not considered complete until it has:

- A recognizable, well-proportioned silhouette from every angle, including a complete back view
- Deliberately sculpted facial planes and integrated anime-style eyes, not floating primitive-like features
- Individually designed hair masses, bangs, side locks and twin tails with clean transitions
- Properly layered clothing, collar, skirt, shoes and character-specific details
- Clean topology, useful material separation, UVs and PBR/toon materials
- A reproducible, editable authoring source (preferably Blender `.blend`) delivered alongside GLB; FBX/OBJ may be included as interchange formats
- A verified web preview at mobile/tablet performance

Triangle count is a diagnostic, not a quality target. Silhouette, anatomy, surface design, topology and presentation are the acceptance criteria.

## Legacy procedural source

The existing generator is retained for reference and comparison:

```bash
python3 tools/build_characters.py --only kita
```

Its implementation is in `tools/chibi/`. This SDF/parametric pipeline is not considered the final authoring method for the hero sculpt.

A GLB is a runtime delivery format, not a substitute for an editable source project. Any replacement must preserve its authoring source and export settings.

## Viewer

- One focused hero-character presentation
- Orbit rotation and zoom
- Studio lighting and grounded framing
- Responsive tablet/mobile layout
- VRM MToon and spring-bone support
- Vite base-path-aware URLs for GitHub Pages

## Run locally

```bash
npm ci
npm run dev
npm run build
npm run preview
```

## Deployment

Every push to `main` triggers GitHub Actions and deploys the production build to GitHub Pages. Keep the version in `README.md`, `package.json`, and the root package entry in `package-lock.json` aligned.

## Licensing

The character is from *Bocchi the Rock!* (ぼっち・ざ・ろっく！); the anime and character belong to their respective rights holders. This is a fan-made, non-commercial project. Follow the applicable rights-holder fan-work guidelines and the terms of any tools or source assets used.
