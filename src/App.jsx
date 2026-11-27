import { useState } from 'react';
import Scene from './components/Scene.jsx';
import { catalog } from './data/catalog.js';

export default function App() {
  const [activeId, setActiveId] = useState(catalog[0].id);
  const active = catalog.find((item) => item.id === activeId) ?? catalog[0];

  return (
    <main className="viewer">
      <section className="viewport" aria-label={`${active.name} 3D 模型`}>
        <Scene key={active.id} modelUrl={active.modelUrl} />
      </section>
      <nav className="character-switcher" aria-label="切换角色">
        {catalog.map((item, index) => (
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
