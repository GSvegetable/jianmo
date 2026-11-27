# JIANMO — Character Model Viewer

Online preview: <https://gsvegetable.github.io/jianmo/>

A real-time viewer for four *Bocchi the Rock!* characters, built with
Three.js + React Three Fiber. **Characters are authored in VRoid Studio and
loaded as VRM with native MToon toon shading.**

## Release

- Current version: 0.8.0
- Rendering: VRM (MToon toon materials, spring-bone hair physics) via `@pixiv/three-vrm`
- Fallback: the procedural GLBs are loaded for any character whose VRM is not present yet
- Missing models now show an explicit on-screen hint instead of a blank viewport

## Asset pipeline (VRM-first)

1. Author the character in [VRoid Studio](https://vroid.com/en/studio) (free, Windows/macOS).
2. Export as **VRM** (VRM 1.0 recommended; VRM 0.x is also supported and auto-rotated).
3. Place the file under `public/models/characters/` using these exact names:

   | Character | Filename |
   | --- | --- |
   | 后藤一里 | `hitori-gotoh.vrm` |
   | 伊地知虹夏 | `nijika-ijichi.vrm` |
   | 山田凉 | `ryo-yamada.vrm` |
   | 喜多郁代 | `ikuyo-kita.vrm` |

4. `npm run build` and deploy. No code changes are needed to add a character.

URLs are built from Vite's base path (`import.meta.env.BASE_URL`), so they
resolve both under `https://gsvegetable.github.io/jianmo/` and at a domain root.

The viewer normalizes every model (auto-centering + scale), updates spring
bones each frame, and needs no network access at runtime (no HDR/CDN fetches).

### Legacy procedural pipeline

`tools/` contains the old SDF-based procedural generator (Python + NumPy).
It is kept for reference only; its output is the four fallback GLB assets. See git history for the original documentation.

## Run locally

```bash
npm install
npm run dev

npm run build
npm run preview
```

## Deployment

Every push to `main` triggers GitHub Actions and deploys the production build
to GitHub Pages. Update the version in both this README and `package.json`
on every project update.

## Licensing and source material

These characters are from *Bocchi the Rock!* (ぼっち・ザ・ロック！); the anime
and its characters are the property of their respective rights holders.
Models authored in VRoid Studio are original fan works — follow the VRoid
terms of use and the rights holders' fan-creation guidelines, and keep the
project non-commercial.
