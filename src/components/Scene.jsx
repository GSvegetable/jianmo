import { Suspense, useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { ContactShadows, Environment, Float, OrbitControls, RoundedBox, useGLTF } from '@react-three/drei';
import * as THREE from 'three';

const palette = {
  bocchi: { hair:'#e9a4cf', hairShade:'#c87eae', eyes:'#56b6e5', skin:'#ffe0d1', jacket:'#e9a6ce', shirt:'#f8eee9', tie:'#64b8dc', skirt:'#343b52', socks:'#f1e9e6', shoes:'#eee9e4', instrument:'#df82b4', hairClip:'#73c4e8' },
  nijika: { hair:'#f0d36c', hairShade:'#d6ad48', eyes:'#a56a42', skin:'#ffe1d0', jacket:'#f5eee3', shirt:'#fffaf0', tie:'#d7aa49', skirt:'#d9d4c8', socks:'#f4eee6', shoes:'#f2eee7', instrument:'#b96a50', hairClip:'#f2d05d' },
  ryo: { hair:'#41648e', hairShade:'#2b466b', eyes:'#b7aa68', skin:'#f5d9ca', jacket:'#e9e8e1', shirt:'#f9f7f0', tie:'#42658e', skirt:'#333b4b', socks:'#e8e6df', shoes:'#e8e6df', instrument:'#d8d6c9', hairClip:'#456b9a' },
  kita: { hair:'#d96f67', hairShade:'#b94e4d', eyes:'#a9c95d', skin:'#ffe0d1', jacket:'#f3e9df', shirt:'#fffaf2', tie:'#d66d63', skirt:'#d5c6bc', socks:'#f4eee8', shoes:'#f1ece6', instrument:'#bd5551', hairClip:'#f1d9cf' }
};
const mat = (color, roughness=.62, metalness=0) => <meshStandardMaterial color={color} roughness={roughness} metalness={metalness}/>;

function Orb({ position, scale, color, roughness=.62, rotation, ...props }) {
  return <mesh position={position} scale={scale} rotation={rotation} castShadow receiveShadow {...props}>
    <sphereGeometry args={[1,32,24]}/>{mat(color,roughness)}
  </mesh>;
}
function SoftBox({ position, size, color, radius=.08, rotation, roughness=.65 }) {
  return <RoundedBox position={position} args={size} radius={radius} smoothness={3} rotation={rotation} castShadow receiveShadow>
    {mat(color,roughness)}
  </RoundedBox>;
}
function TubeLimb({ start, end, radius, color }) {
  const a = new THREE.Vector3(...start), b = new THREE.Vector3(...end);
  const direction = new THREE.Vector3().subVectors(b,a);
  const midpoint = new THREE.Vector3().addVectors(a,b).multiplyScalar(.5);
  return <mesh position={midpoint.toArray()} quaternion={new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0,1,0),direction.clone().normalize())} castShadow receiveShadow>
    <capsuleGeometry args={[radius,Math.max(.01,direction.length()-radius*2),6,12]}/>{mat(color)}
  </mesh>;
}
function Eye({ x, z, iris, style }) {
  return <group position={[x,1.55,z]}>
    <Orb position={[0,0,0]} scale={[.105,style==="ryo" ? 0.115 : style==="kita" ? 0.17 : 0.15,.045]} color="#fffaf2" roughness=.32}/>
    <Orb position={[0,-.005,.035]} scale={[.066,style==="ryo" ? 0.082 : style==="kita" ? 0.12 : 0.108,.026]} color={iris} roughness=.28}/>
    <Orb position={[0,-.005,.057]} scale={[.031,.073,.014]} color="#25232a" roughness=.2}/>
    <Orb position={[-.018,.045,.07]} scale={[.022,.027,.012]} color="#fff" roughness=.15}/>
    <Orb position={[.018,-.045,.069]} scale={[.009,.012,.008]} color="#fff" roughness=.15}/>
  </group>;
}
function HairLock({ start, end, width, color }) {
  const a = new THREE.Vector3(...start), b = new THREE.Vector3(...end);
  const direction = new THREE.Vector3().subVectors(b,a);
  const midpoint = new THREE.Vector3().addVectors(a,b).multiplyScalar(.5);
  return <mesh position={midpoint.toArray()} quaternion={new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0,1,0),direction.clone().normalize())} castShadow receiveShadow>
    <coneGeometry args={[width,direction.length(),16,2]}/>{mat(color,.48)}
  </mesh>;
}
function HairStrand({ points, radius=.018, color }) {
  const curve = new THREE.CatmullRomCurve3(points.map(point => new THREE.Vector3(...point)));
  return <mesh castShadow receiveShadow><tubeGeometry args={[curve,24,radius,8,false]}/>{mat(color,.36)}</mesh>;
}
function Hair({ id, c }) {
  const long = id==='bocchi' || id==='kita';
  const bob = id==='ryo';
  return <group>
    <Orb position={[0,1.78,-.03]} scale={[.88,.87,.76]} color={c.hair}/>
    <Orb position={[0,1.35,-.22]} scale={[.78,.7,.55]} color={c.hairShade}/>
    {/* pointed fringe locks add a sculpted silhouette */}
    <HairStrand points={[[-.63,2.08,.55],[-.56,1.91,.72],[-.5,1.69,.77]]} radius={.018} color={c.hair}/>
    <HairStrand points={[[-.22,2.22,.66],[-.16,2.02,.76],[-.1,1.84,.81]]} radius={.014} color={c.hairShade}/>
    <HairStrand points={[[.22,2.22,.65],[.28,2.02,.75],[.34,1.83,.79]]} radius={.014} color={c.hair}/>
    <HairStrand points={[[.61,2.04,.53],[.59,1.88,.69],[.55,1.68,.75]]} radius={.018} color={c.hairShade}/>
    <HairStrand points={[[-.72,1.55,.26],[-.77,1.25,.28],[-.75,.98,.22]]} radius={.014} color={c.hair}/>
    <HairStrand points={[[.72,1.55,.26],[.77,1.25,.28],[.75,.98,.22]]} radius={.014} color={c.hair}/>

    <HairLock start={[-.58,2.2,.55]} end={[-.39,1.78,.77]} width={.2} color={c.hairShade}/>
    <HairLock start={[-.28,2.28,.61]} end={[-.12,1.83,.82]} width={.2} color={c.hair}/>
    <HairLock start={[.08,2.28,.61]} end={[.23,1.82,.82]} width={.19} color={c.hairShade}/>
    <HairLock start={[.43,2.17,.55]} end={[.48,1.82,.76]} width={.18} color={c.hair}/>
    <HairLock start={[-.73,1.78,.34]} end={[-.78,1.18,.29]} width={.16} color={c.hairShade}/>
    <HairLock start={[.72,1.76,.34]} end={[.78,1.16,.29]} width={.16} color={c.hairShade}/>
    {/* distinct fringe silhouette */}
    <Orb position={[-.48,2.02,.34]} scale={[.34,.28,.34]} color={c.hair}/>
    <Orb position={[-.16,2.12,.4]} scale={[.36,.31,.32]} color={c.hair}/>
    <Orb position={[.2,2.09,.39]} scale={[.34,.3,.32]} color={c.hair}/>
    <Orb position={[.51,1.96,.31]} scale={[.28,.27,.3]} color={c.hair}/>
    <Orb position={[-.68,1.42,.02]} scale={[.22,.62,.28]} color={c.hair}/>
    <Orb position={[.68,1.42,.02]} scale={[.22,.62,.28]} color={c.hair}/>
    {long && <>
      <Orb position={[-.72,.85,-.04]} scale={[.2,.65,.22]} color={c.hair}/>
      <Orb position={[.72,.85,-.04]} scale={[.2,.65,.22]} color={c.hair}/>
      <Orb position={[-.75,.36,-.04]} scale={[.16,.32,.18]} color={c.hairShade}/>
      <Orb position={[.75,.36,-.04]} scale={[.16,.32,.18]} color={c.hairShade}/>
    </>}
    {bob && <>
      <Orb position={[-.62,.99,-.05]} scale={[.22,.43,.24]} color={c.hair}/>
      <Orb position={[.62,.99,-.05]} scale={[.22,.43,.24]} color={c.hair}/>
      <Orb position={[0,2.27,-.1]} scale={[.15,.25,.17]} color={c.hairShade}/>
    </>}
    {id==='nijika' && <>
      <HairLock start={[.72,1.75,-.24]} end={[1.18,.7,-.4]} width={.24} color={c.hair}/>
      <HairLock start={[.82,1.55,-.34]} end={[1.28,.92,-.42]} width={.16} color={c.hairShade}/>
      <Orb position={[.76,1.72,-.28]} scale={[.31,.25,.3]} color={c.hairShade}/>
      <Orb position={[.98,1.38,-.27]} scale={[.2,.5,.2]} color={c.hair}/>
      <Orb position={[1.08,1.02,-.25]} scale={[.15,.34,.16]} color={c.hair}/>
      <Orb position={[.95,.73,-.22]} scale={[.13,.23,.14]} color={c.hairShade}/>
      <Orb position={[-.05,2.3,.12]} scale={[.2,.16,.18]} color={c.hair}/>
      <Orb position={[-.05,2.38,.13]} scale={[.15,.1,.12]} color={c.hairClip}/>
      <Orb position={[.12,2.34,.15]} scale={[.12,.1,.1]} color={c.hairClip}/>
    </>}
    {id==='bocchi' && <>
      <HairLock start={[-.76,1.22,-.02]} end={[-.92,.12,.1]} width={.13} color={c.hairShade}/>
      <HairLock start={[.76,1.22,-.02]} end={[.91,.12,.1]} width={.13} color={c.hairShade}/>
      <Orb position={[-.79,1.95,.12]} scale={[.13,.13,.12]} color={c.hairClip}/>
      <Orb position={[-.67,1.83,.18]} scale={[.1,.11,.1]} color={c.hairClip}/>
      <Orb position={[.76,1.95,.08]} scale={[.12,.12,.12]} color={c.hairClip}/>
    </>}
    {id==='kita' && <>
      <HairLock start={[-.72,1.25,-.03]} end={[-.82,.16,-.02]} width={.15} color={c.hair}/>
      <HairLock start={[.72,1.25,-.03]} end={[.84,.16,-.02]} width={.15} color={c.hairShade}/>
      <Orb position={[.75,1.96,.12]} scale={[.13,.13,.12]} color={c.hairClip}/>
      <Orb position={[.85,1.85,.1]} scale={[.1,.11,.1]} color={c.hairClip}/>
    </>}
  </group>;
}
function Face({ c, id }) {
  return <group>
    <Orb position={[0,1.48,.18]} scale={[.76,.72,.65]} color={c.skin}/>
    <Orb position={[-.48,1.22,.72]} scale={[.14,.06,.025]} color="#f2a6a0"/>
    <Orb position={[.48,1.22,.72]} scale={[.14,.06,.025]} color="#f2a6a0"/>
    <Eye x={-.29} z={.77} iris={c.eyes} style={id}/><Eye x={.29} z={.77} iris={c.eyes} style={id}/>
    <Orb position={[0,1.22,.83]} scale={[.045,.025,.02]} color="#a96862"/>
    <Orb position={[0,1.12,.81]} scale={[.085,.025,.018]} color={id==='ryo'?'#9c6866':'#c77978'}/>
    {id==='bocchi' && <Orb position={[0,1.095,.825]} scale={[.045,.018,.012]} color="#8f5962"/>}
    {id==='nijika' && <Orb position={[0,1.105,.825]} scale={[.095,.022,.014]} color="#c77978"/>}
    {id==='kita' && <Orb position={[0,1.105,.825]} scale={[.11,.026,.014]} color="#c77978"/>}
    <HairStrand points={[[-.43,1.75,.77],[-.3,1.79,.8],[-.17,1.75,.78]]} radius={.018} color={c.hairShade}/>
    <HairStrand points={[[.17,1.75,.78],[.3,1.79,.8],[.43,1.75,.77]]} radius={.018} color={c.hairShade}/>
    <HairStrand points={[[-.4,1.62,.8],[-.3,1.64,.815],[-.2,1.62,.8]]} radius={.009} color="#fff0e7"/>
    <HairStrand points={[[.2,1.62,.8],[.3,1.64,.815],[.4,1.62,.8]]} radius={.009} color="#fff0e7"/>
    <Orb position={[-.56,1.47,.65]} scale={[.055,.09,.035]} color={c.skin}/>
    <Orb position={[.56,1.47,.65]} scale={[.055,.09,.035]} color={c.skin}/>
    <TubeLimb start={[-.42,1.72,.72]} end={[-.18,1.78,.76]} radius=.018 color={c.hairShade}/>
    <TubeLimb start={[.18,1.78,.76]} end={[.42,1.72,.72]} radius=.018 color={c.hairShade}/>
  </group>;
}
function Guitar({ color, bass=false, position=[.45,.03,.64], rotation=[0,0,-.34] }) {
  const neckLength = bass ? 1.28 : 1.08;
  return <group position={position} rotation={rotation}>
    {/* sculpted double-cut body */}
    <Orb position={[-.05,.02,0]} scale={[.29,.39,.105]} color={color} roughness=.34/>
    <Orb position={[-.2,.12,.008]} scale={[.17,.2,.108]} color={color} roughness=.34}/>
    <Orb position={[.11,.12,.008]} scale={[.17,.2,.108]} color={color} roughness=.34}/>
    <SoftBox position={[-.04,.37,.02]} size={[.095,neckLength,.075]} color="#75543e" radius=.025/>
    <SoftBox position={[-.04,.37,.064]} size={[.072,neckLength-.06,.012]} color="#2d2b2a" radius=.012/>
    <SoftBox position={[-.04,.37+neckLength/2,.02]} size={[.19,.17,.08]} color="#d8d2c3" radius=.035/>
    <SoftBox position={[-.05,-.02,.112]} size={[.25,.13,.022]} color="#ded6c5" radius=.018/>
    <Orb position={[-.05,.07,.12]} scale={[.11,.1,.018]} color="#24272a" roughness=.35/>
    {Array.from({length:bass?4:6},(_,i)=><mesh key={i} position={[-.11+i*(.12/(bass?3:5)),.38,.09]}><boxGeometry args={[.006,neckLength+.28,.006]}/>{mat('#e8e1d2',.3,.65)}</mesh>)}
    {Array.from({length:7},(_,i)=><SoftBox key={i} position={[-.04,.02+i*.115,.073]} size={[.09,.012,.012]} color="#b6aa93" radius=.003/>)}
    {Array.from({length:bass?4:3},(_,i)=><Orb key={i} position={[-.16+i*.11,-.08,.12]} scale={[.018,.025,.014]} color="#c9c5b9" roughness=.25}/>)}
    <SoftBox position={[-.04,.37+neckLength/2,.065]} size={[.2,.045,.025]} color="#c8c2b5" radius=.01/>
    {[-1,1].map((side)=><group key={side}>{[0,1,2].map(i=><Orb key={i} position={[-.04+side*(.13),.37+neckLength/2-.05+i*.07,.015]} scale={[.055,.025,.025]} color="#bcb8ae" roughness=.3/>)}</group>)}
  </group>;
}
function DrumKit() {
  const drum = '#e8d8b8';
  return <group position={[0,-.7,1.05]}>
    <mesh position={[0,.13,0]} rotation={[Math.PI/2,0,0]} castShadow receiveShadow><cylinderGeometry args={[.48,.48,.24,48]}/>{mat(drum,.3)}</mesh>
    <mesh position={[0,.13,.13]}><circleGeometry args={[.4,48]}/>{mat('#eee7d9',.35)}</mesh>
    <mesh position={[-.48,.5,-.1]} rotation={[Math.PI/2,0,0]} castShadow><cylinderGeometry args={[.24,.24,.2,32]}/>{mat('#d9c7a8',.35)}</mesh>
    <mesh position={[.45,.48,-.12]} rotation={[Math.PI/2,0,0]} castShadow><cylinderGeometry args={[.22,.22,.2,32]}/>{mat('#d9c7a8',.35)}</mesh>
    <mesh position={[-.78,.18,-.06]} rotation={[Math.PI/2,0,0]} castShadow><cylinderGeometry args={[.27,.27,.12,32]}/>{mat('#b8a58c',.35)}</mesh>
    {[-.82,.78].map((x,i)=><group key={i} position={[x,.85,-.08]}>
      <TubeLimb start={[0,-.75,0]} end={[0,.06,0]} radius=.018 color="#a6a39a"/>
      <mesh position={[0,.12,0]} castShadow><cylinderGeometry args={[.27,.22,.035,32]}/>{mat('#c7b994',.27,.55)}</mesh>
    </group>)}
    <TubeLimb start={[-.5,.65,.42]} end={[-.12,.95,.42]} radius=.018 color="#e6d3b3"/>
    <TubeLimb start={[.5,.65,.42]} end={[.12,.95,.42]} radius=.018 color="#e6d3b3"/>
  </group>;
}
function Character({ characterId }) {
  const id = palette[characterId] ? characterId : 'bocchi';
  const c = palette[id];
  const root = useRef();
  useFrame((state,delta)=>{ if(root.current) root.current.rotation.y += delta*.025; });
  const isDrummer = id==='nijika';
  return <group ref={root} position={[0,-.48,0]}>
    <Float speed={1.05} rotationIntensity={.025} floatIntensity={.045}>
      <Hair id={id} c={c}/>
      <Face c={c} id={id}/>
      {/* collar, jacket and torso */}
      <Orb position={[0,.47,-.02]} scale={[.43,.56,.34]} color={c.jacket}/>
      <SoftBox position={[0,.63,.29]} size={[.3,.36,.08]} color={c.shirt} radius=.035/>
      <SoftBox position={[0,.48,.35]} size={[.07,.35,.035]} color={c.tie} radius=.012/>
      <SoftBox position={[-.16,.63,.35]} size={[.13,.25,.035]} color={c.jacket} radius=.018 rotation={[0,0,-.24]}/>
      <SoftBox position={[.16,.63,.35]} size={[.13,.25,.035]} color={c.jacket} radius=.018 rotation={[0,0,.24]}/>
      <Orb position={[0,.54,.39]} scale={[.025,.025,.012]} color="#c7b58f" roughness=.3/>
      <Orb position={[0,.39,.39]} scale={[.025,.025,.012]} color="#c7b58f" roughness=.3/>
      <HairStrand points={[[-.36,.78,.29],[-.31,.55,.36],[-.25,.29,.32]]} radius={.012} color={c.hairShade}/>
      <HairStrand points={[[.36,.78,.29],[.31,.55,.36],[.25,.29,.32]]} radius={.012} color={c.hairShade}/>
      <HairStrand points={[[-.12,.78,.365],[0,.73,.38],[.12,.78,.365]]} radius={.012} color={c.tie}/>

      <Orb position={[-.2,.77,.3]} scale={[.12,.12,.06]} color={c.shirt}/>
      <Orb position={[.2,.77,.3]} scale={[.12,.12,.06]} color={c.shirt}/>
      <Orb position={[0,.03,-.01]} scale={[.48,.2,.34]} color={c.skirt}/>
      {Array.from({length:8},(_,i)=><SoftBox key={i} position={[Math.sin(i*Math.PI/4)*.34,-.04,Math.cos(i*Math.PI/4)*.22]} size={[.14,.23,.045]} color={i%2?c.skirt:c.jacket} radius=.018 rotation={[0,-i*Math.PI/4,0]}/>)}
      {/* sleeves, arms and tiny hands */}
      {Array.from({length:8},(_,i)=><HairStrand key={`pleat-${i}`} points={[[Math.sin(i*Math.PI/4)*.2,.08,Math.cos(i*Math.PI/4)*.17],[Math.sin(i*Math.PI/4)*.31,-.02,Math.cos(i*Math.PI/4)*.23],[Math.sin(i*Math.PI/4)*.4,-.14,Math.cos(i*Math.PI/4)*.27]]} radius={.009} color={c.hairShade}/>)}

      <TubeLimb start={[-.35,.68,.02]} end={[-.55,.22,.4]} radius=.115 color={c.jacket}/>
      <TubeLimb start={[.35,.68,.02]} end={[.55,.22,.4]} radius=.115 color={c.jacket}/>
      <Orb position={[-.55,.2,.42]} scale={[.12,.11,.1]} color={c.skin}/>
      <Orb position={[.55,.2,.42]} scale={[.12,.11,.1]} color={c.skin}/>
      {[-1,1].map(side=><group key={side} position={[side*.55,.18,.49]}>
        {[-1,0,1].map(finger=><HairLock key={finger} start={[finger*.045,0,0]} end={[finger*.052,-.075,.005]} width={.022} color={c.skin}/>)}
      </group>)}
      {/* legs, socks and shoes */}
      <TubeLimb start={[-.23,-.1,0]} end={[-.25,-.75,.04]} radius=.105 color={c.skin}/>
      <TubeLimb start={[.23,-.1,0]} end={[.25,-.75,.04]} radius=.105 color={c.skin}/>
      <TubeLimb start={[-.25,-.65,.03]} end={[-.25,-.88,.03]} radius=.11 color={c.socks}/>
      <TubeLimb start={[.25,-.65,.03]} end={[.25,-.88,.03]} radius=.11 color={c.socks}/>
      <Orb position={[-.25,-.93,.13]} scale={[.2,.11,.29]} color={c.shoes}/>
      <Orb position={[.25,-.93,.13]} scale={[.2,.11,.29]} color={c.shoes}/>
      <SoftBox position={[-.25,-.9,.31]} size={[.19,.035,.025]} color={c.jacket} radius=.012/>
      <SoftBox position={[.25,-.9,.31]} size={[.19,.035,.025]} color={c.jacket} radius=.012/>
      {isDrummer ? <DrumKit/> : <Guitar color={c.instrument} bass={id==='ryo'} position={id==='ryo'?[.48,.02,.58]:[.47,.02,.6]}/>}
      {!isDrummer && <HairStrand points={[[-.34,.83,.35],[-.12,.55,.42],[.12,.29,.47],[.43,.12,.57]]} radius={.035} color={id==='bocchi'?'#a85e88':id==='ryo'?'#596c7c':'#a65a50'}/>}

      {id==='bocchi' && <Orb position={[-.67,1.98,.36]} scale={[.08,.08,.025]} color="#78c8ed"/>}
      {id==='kita' && <Orb position={[.76,1.98,.28]} scale={[.07,.07,.025]} color="#fff1d8"/>}
    </Float>
  </group>;
}
function LoadedModel({ url }) { const { scene } = useGLTF(url); return <primitive object={scene} />; }
function Stage({ mode, modelUrl, characterId }) {
  return <>
    <color attach="background" args={['#111310']}/>
    <fog attach="fog" args={['#111310',7,16]}/>
    <ambientLight intensity={.72}/>
    <spotLight position={[4,7,5]} intensity={72} angle={.42} penumbra={.8} castShadow shadow-mapSize={[2048,2048]}/>
    <pointLight position={[-4,1,-3]} intensity={16} color="#9bafaa"/>
    <pointLight position={[2,-2,3]} intensity={8} color="#c69d70"/>
    <Suspense fallback={null}>
      <Environment preset="studio"/>
      {modelUrl ? <LoadedModel url={modelUrl}/> : <Character characterId={characterId}/>}
      <ContactShadows position={[0,-1.65,0]} opacity={.4} scale={8} blur={2.8} far={4}/>
    </Suspense>
    <OrbitControls makeDefault enableDamping dampingFactor={.06} minDistance={2.5} maxDistance={8} target={[0,.35,0]} autoRotate={mode==='exhibition'} autoRotateSpeed={.48} enablePan={mode==='explore'}/>
  </>;
}
export default function Scene({ mode, modelUrl, characterId }) {
  return <Canvas shadows dpr={[1,1.7]} camera={{position:[0,.55,5.4],fov:38,near:.1,far:50}} gl={{antialias:true,alpha:false,powerPreference:'high-performance'}}>
    <Stage mode={mode} modelUrl={modelUrl} characterId={characterId}/>
  </Canvas>;
}
