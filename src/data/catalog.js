// Assets live under `public/models/characters/`, which Vite serves at
// `<base>/models/characters/`. URLs are built from Vite's base path so they
// resolve both under https://gsvegetable.github.io/jianmo/ and at a domain root.
//
// Pipeline: characters are authored in VRoid Studio and exported as .vrm.
// Drop the exported file into public/models/characters/ with the filename
// below. The viewer loads VRM (MToon toon shading) natively; the procedural
// GLBs are kept as fallbacks so every character renders until its VRM lands.
//
// The charm is the opposite: it is traced out of the official character
// sheet by the pipeline in tools/charm/, so it is a plain GLB with the
// drawing printed on both sides.
const asset = (file) => `${import.meta.env.BASE_URL}models/characters/${file}`;
const charm = (file) => `${import.meta.env.BASE_URL}models/charms/${file}`;

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

export const charms = [
  { id: 'kita', name: '喜多郁代', glbUrl: charm('ikuyo-kita-charm.glb') },
];
