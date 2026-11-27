// Assets live under `public/models/characters/`, which Vite serves at
// `<base>/models/characters/`. URLs are built from Vite's base path so they
// resolve both under https://gsvegetable.github.io/jianmo/ and at a domain root.
//
// Pipeline: characters are authored in VRoid Studio and exported as .vrm.
// Drop the exported file into public/models/characters/ with the filename
// below. The viewer loads VRM (MToon toon shading) natively; the procedural
// GLBs are kept as fallbacks so every character renders until its VRM lands.
const asset = (file) => `${import.meta.env.BASE_URL}models/characters/${file}`;

export const catalog = [
  {
    id: 'bocchi',
    name: '后藤一里',
    vrmUrl: asset('hitori-gotoh.vrm'),
    glbUrl: asset('hitori-gotoh.glb'),
  },
  {
    id: 'nijika',
    name: '伊地知虹夏',
    vrmUrl: asset('nijika-ijichi.vrm'),
    glbUrl: asset('nijika-ijichi.glb'),
  },
  {
    id: 'ryo',
    name: '山田凉',
    vrmUrl: asset('ryo-yamada.vrm'),
    glbUrl: asset('ryo-yamada.glb'),
  },
  {
    id: 'kita',
    name: '喜多郁代',
    vrmUrl: asset('ikuyo-kita.vrm'),
    glbUrl: asset('ikuyo-kita.glb'),
  },
];
