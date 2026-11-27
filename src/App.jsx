import { useMemo, useRef, useState } from 'react';
import { Aperture, ArrowDownRight, ChevronDown, CircleHelp, Focus, Grid2X2, Info, Maximize2, MousePointer2, Rotate3D, Sparkles } from 'lucide-react';
import Scene from './components/Scene.jsx';
import { catalog, categories } from './data/catalog.js';

export default function App() {
  const [mode,setMode]=useState('exhibition');
  const [activeCategory,setActiveCategory]=useState('全部作品');
  const [activeId,setActiveId]=useState('bocchi');
  const [showInfo,setShowInfo]=useState(true);
  const stageRef=useRef(null);
  const toggleFullscreen=()=>{if(!document.fullscreenElement)stageRef.current?.requestFullscreen?.();else document.exitFullscreen?.();};
  const visibleItems=catalog.filter(item=>activeCategory==='全部作品'||item.category===activeCategory);
  const specimen=visibleItems.find(item=>item.id===activeId)||visibleItems[0]||catalog[0];
  const modeLabel=mode==='exhibition'?'艺术展览':'自由探索';
  const categoryCount=useMemo(()=>({'全部作品':catalog.length,'人物':catalog.length,'动物':0,'幻想生物':0}),[]);
  return <main className="app-shell">
    <header className="topbar"><a className="brand" href="#" aria-label="JIANMO home"><span className="brand-mark"><Aperture size={19} strokeWidth={1.5}/></span><span>JIANMO<span className="brand-dot">.</span></span></a><div className="top-center"><span className="live-dot"/> DIGITAL SPECIMEN ARCHIVE</div><button className="icon-button help-button" aria-label="帮助"><CircleHelp size={17}/></button></header>
    <section className="workspace">
      <aside className="sidebar"><div className="eyebrow">COLLECTION <span>01—04</span></div><h1>角色图鉴<span className="muted-dot">.</span></h1><p className="sidebar-intro">以数字雕塑的方式，收藏喜爱的角色。</p>
        <div className="category-list">{categories.map((category,index)=><button key={category} className={activeCategory===category?'category active':'category'} onClick={()=>setActiveCategory(category)}><span className="category-index">0{index+1}</span><span>{category}</span><span className="category-count">{categoryCount[category]??0}</span></button>)}</div>
        <div className="sidebar-bottom"><span className="small-label">ARCHIVE STATUS</span><div className="status-line"><span className="status-dot"/> FOUR CHARACTERS / PROTOTYPE</div><p>Q版角色原型已建立，后续可替换为精细模型。</p></div>
      </aside>
      <section className="stage-column">
        <div className="stage-heading"><div><div className="eyebrow">CHARACTER / {String(catalog.findIndex(x=>x.id===specimen.id)+1).padStart(2,'0')} — 04</div><h2>{specimen.name}<span style={{fontSize:'.58em',opacity:.55,marginLeft:10}}>{specimen.alias}</span></h2></div>
          <div className="stage-actions"><button className={mode==='exhibition'?'mode-button selected':'mode-button'} onClick={()=>setMode('exhibition')}><Sparkles size={14}/> 展览</button><button className={mode==='explore'?'mode-button selected':'mode-button'} onClick={()=>setMode('explore')}><Rotate3D size={14}/> 探索</button></div></div>
        <div className="character-picker">{catalog.map((item,index)=><button key={item.id} className={specimen.id===item.id?'character-chip selected':'character-chip'} onClick={()=>setActiveId(item.id)}><span className="chip-index">0{index+1}</span>{item.name}</button>)}</div>
        <div className="stage-frame" ref={stageRef}><div className="stage-grid"/><div className="stage-corner corner-tl"/><div className="stage-corner corner-tr"/><div className="stage-corner corner-bl"/><div className="stage-corner corner-br"/>
          <div className="scene-canvas"><Scene mode={mode} modelUrl={specimen.modelUrl} characterId={specimen.characterId}/></div>
          <div className="stage-top-meta"><span>3D CHARACTER VIEWPORT</span><span>REALTIME / WEBGL</span></div><div className="stage-bottom-meta"><span>0{catalog.findIndex(x=>x.id===specimen.id)+1} — 04</span><span>{mode==='exhibition'?'AUTO PRESENTATION':'INTERACTIVE VIEW'}</span></div>
          <button className="expand-button" onClick={toggleFullscreen} aria-label="切换全屏" title="全屏"><Maximize2 size={15}/></button>
          {mode==='explore'&&<div className="interaction-hint"><MousePointer2 size={13}/> 拖动旋转 · 滚轮缩放</div>}</div>
        <div className="under-stage"><div className="mode-caption"><span className="caption-icon"><Focus size={15}/></span><span>{modeLabel}</span><span className="caption-separator">/</span><span className="caption-muted">{mode==='exhibition'?'自动镜头与缓慢环绕':'自由旋转与缩放观察'}</span></div><div className="stage-shortcuts"><span><span className="keycap">DRAG</span> ROTATE</span><span><span className="keycap">SCROLL</span> ZOOM</span></div></div>
      </section>
      <aside className="detail-panel"><div className="detail-head"><span className="eyebrow">CHARACTER DETAILS</span><button className="icon-button" onClick={()=>setShowInfo(!showInfo)} aria-label="切换详情"><Info size={16}/></button></div>
        {showInfo&&<><div className="specimen-number">0{catalog.findIndex(x=>x.id===specimen.id)+1}</div><div className="latin-name">{specimen.latinName}</div><h3>{specimen.name}</h3><p className="detail-description">{specimen.description}</p><div className="detail-divider"/><div className="detail-row"><span>所属作品</span><span>孤独摇滚！</span></div><div className="detail-row"><span>角色定位</span><span>{specimen.latinName.split('/').pop()}</span></div><div className="detail-row"><span>模型状态</span><span className="pending">3D 原型</span></div><div className="detail-row"><span>展示模式</span><span>{modeLabel}</span></div></>}
        <div className="detail-bottom"><div className="detail-tip"><Grid2X2 size={14}/><span>当前为程序化 Q 版原型，后续将继续精修发型、服装、面部与乐器。</span></div><button className="detail-link" onClick={()=>setMode(mode==='exhibition'?'explore':'exhibition')}>切换体验模式 <ArrowDownRight size={15}/></button></div>
      </aside>
    </section>
    <footer className="footer"><span>JIANMO © 2026</span><span>BOCCHI THE ROCK! / CHIBI CHARACTER COLLECTION</span><span>BUILT FOR DIGITAL CURIOSITY <ChevronDown size={12}/></span></footer>
  </main>;
}