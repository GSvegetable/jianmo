import Scene from './components/Scene.jsx';
import { catalog } from './data/catalog.js';

// The current production pass is intentionally limited to one hero asset.
// The other legacy meshes remain in the repository for comparison, but are
// not presented as finished work.
const hero = catalog.find((item) => item.id === 'kita') ?? catalog[0];

export default function App() {
  const isEmbed = new URLSearchParams(window.location.search).get('embed') === '1';

  return (
    <main className={`viewer viewer--hero${isEmbed ? ' viewer--embed' : ''}`}>

      {!isEmbed && <header className="viewer-header">
        <a className="brand" href="./" aria-label="JIANMO 首页">
          <span className="brand-mark">J.</span>
          <span className="brand-copy">
            <strong>JIANMO</strong>
            <small>CHARACTER SCULPT STUDY</small>
          </span>
        </a>
        <div className="header-note"><span className="status-dot" />HERO ASSET · 01</div>
      </header>}

      <section className="viewport" aria-label={`${hero.name} 3D 模型`}>
        <div className="viewport-caption">
          <span className="eyebrow">CHARACTER / 001</span>
          <h1>{hero.name}</h1>
          <p>FULL TURNAROUND <i /> DRAG TO ROTATE <i /> SCROLL TO ZOOM</p>
        </div>
        <Scene
          key={hero.id}
          kind="character"
          vrmUrl={hero.vrmUrl}
          glbUrl={hero.glbUrl}
          name={hero.name}
        />
        <div className="viewport-index" aria-hidden="true">
          <span>JIANMO / HERO STUDY</span>
          <span>360° VIEW</span>
        </div>
      </section>

      {!isEmbed && <footer className="hero-footer">
        <span>IKUYO KITA</span>
        <span>ONE CHARACTER. BUILT PROPERLY.</span>
        <span>GLB / VRM READY</span>
      </footer>}
    </main>
  );
}
