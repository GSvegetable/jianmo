import { useState } from 'react';
import Scene from './components/Scene.jsx';
import { catalog, charms } from './data/catalog.js';

const TABS = [
  { id: 'character', label: '角色', items: catalog },
  { id: 'charm', label: '挂件', items: charms },
];

export default function App() {
  const [tab, setTab] = useState(TABS[0].id);
  const [activeId, setActiveId] = useState(TABS[0].items[0].id);

  const current = TABS.find((item) => item.id === tab) ?? TABS[0];
  const items = current.items;
  const active = items.find((item) => item.id === activeId) ?? items[0];

  const switchTab = (id) => {
    const next = TABS.find((item) => item.id === id) ?? TABS[0];
    setTab(next.id);
    setActiveId(next.items[0].id);
  };

  return (
    <main className="viewer">
      <header className="viewer-header">
        <h1 className="viewer-title">JIANMO</h1>
        <div className="tab-switcher" role="tablist" aria-label="切换视图">
          {TABS.map((item) => (
            <button
              key={item.id}
              type="button"
              role="tab"
              aria-selected={current.id === item.id}
              className={current.id === item.id ? 'tab-button active' : 'tab-button'}
              onClick={() => switchTab(item.id)}
            >
              {item.label}
            </button>
          ))}
        </div>
      </header>

      <section className="viewport" aria-label={`${active.name} 3D 模型`}>
        <Scene
          key={`${current.id}-${active.id}`}
          kind={current.id}
          vrmUrl={active.vrmUrl}
          glbUrl={active.glbUrl}
          name={active.name}
        />
      </section>

      <nav className="character-switcher" aria-label="切换角色">
        {items.map((item, index) => (
          <button
            key={item.id}
            type="button"
            className={active.id === item.id ? 'character-button active' : 'character-button'}
            aria-pressed={active.id === item.id}
            onClick={() => setActiveId(item.id)}
          >
            <span className="button-index">0{index + 1}</span>
            <span>{item.name}</span>
          </button>
        ))}
      </nav>
    </main>
  );
}
