// Assets live under `public/models/characters/`, which Vite serves at
// `<base>/models/characters/`.  The URLs have to be built from the base
// path: the site is deployed to https://gsvegetable.github.io/jianmo/,
// so an absolute `/models/...` would resolve to the domain root and 404.
const asset = (file) => `${import.meta.env.BASE_URL}models/characters/${file}`;

export const catalog = [
  { id: 'bocchi', name: '后藤一里', modelUrl: asset('hitori-gotoh.glb') },
  { id: 'nijika', name: '伊地知虹夏', modelUrl: asset('nijika-ijichi.glb') },
  { id: 'ryo', name: '山田凉', modelUrl: asset('ryo-yamada.glb') },
  { id: 'kita', name: '喜多郁代', modelUrl: asset('ikuyo-kita.glb') },
];
