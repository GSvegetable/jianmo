import { useState } from 'react';
import Scene from './components/Scene.jsx';
import { catalog, charms } from './data/catalog.js';

const TABS = [
  { id: 'character', label: '角色', items: catalog },
  { id: 'charm', label: '挂件', items: charms },
];

export default function App() {
  const [tab, setTab] = useState('character');
  const [activeId, setActiveId] = useState(catalog[0].id);
  const current = TABS.find((item) => item.id === tab) ?? TABS[0];
  const active = current.items.find((item) => item.id === activeId) ?? current.items[0];

  function switchTab(nextId) {
    const next = TABS.find((item) => item.id === nextId) ?? TABS[0];
    setTab(next.id);
    setActiveId(next.items[0].id);
  }

  return (
    <main className="viewer">
      <header className="viewer-header">
        <a className="brand" href="./" aria-label="JIANMO 首页">
          <span className="brand-mark">J.</span>
          <span className="brand-copy">
            <strong>JIANMO</strong>
            <small>CHARACTER OBJECTS · 3D COLLECTION</small>
          </span>
        </a>
        <div className="tab-switcher" role="tablist" aria-label="作品类别">
          {TABS.map((item) => (
            <button key={item.id} type="button" role="tab"
              aria-selected={tab === item.id}
              className={tab === item.id ? 'tab-button active' : 'tab-button'}
              onClick={() => switchTab(item.id)}>
              {item.label}
              <span className="tab-count">{String(item.items.length).padStart(2, '0')}</span>
            </button>
          ))}
        </div>
        <div className="header-note"><span className="status-dot" />INTERACTIVE 3D</div>
      </header>

      <section className="viewport" aria-label={`${active.name} 3D 模型`}>
        <div className="viewport-caption">
          <span className="eyebrow">{current.id === 'charm' ? 'OBJECT STUDY' : 'CHARACTER STUDY'}</span>
          <h1>{active.name}</h1>
          <p>DRAG TO ROTATE <i /> SCROLL TO ZOOM</p>
        </div>
        <Scene key={`${current.id}-${active.id}`} kind={current.id}
          vrmUrl={active.vrmUrl} glbUrl={active.glbUrl} name={active.name} />
        <div className="viewport-index" aria-hidden="true">
          <span>J / 01</span><span>360° VIEW</span>
        </div>
      </section>

      <nav className="character-switcher" aria-label="切换作品">
        <div className="switcher-label">
          <span>COLLECTION</span>
          <span>{String(current.items.length).padStart(2, '0')} OBJECTS</span>
        </div>
        <div className="switcher-items">
          {current.items.map((item, index) => (
            <button key={item.id} type="button"
              className={active.id === item.id ? 'character-button active' : 'character-button'}
              aria-pressed={active.id === item.id} onClick={() => setActiveId(item.id)}>
              <span className="button-index">0{index + 1}</span>
              <span>{item.name}</span>
              <span className="button-arrow" aria-hidden="true">↗</span>
            </button>
          ))}
        </div>
      </nav>
    </main>
  );
}
