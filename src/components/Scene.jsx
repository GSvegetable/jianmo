import { Suspense, useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { ContactShadows, Environment, Float, OrbitControls, useGLTF } from '@react-three/drei';
import * as THREE from 'three';

const cast = { castShadow: true, receiveShadow: true };
const characters = {
  bocchi: { hair:'#e99acb', hairDark:'#c978ad', eyes:'#58b9e8', outfit:'#f1c7dc', accent:'#272a32', style:'long', guitar:'#252632', bow:'#78b9e8' },
  nijika: { hair:'#f2d56e', hairDark:'#d5ae48', eyes:'#9b593b', outfit:'#f5eee0', accent:'#e7bd4b', style:'ponytail', guitar:'#b84c43', bow:'#f0c84f' },
  ryo: { hair:'#355b89', hairDark:'#263f68', eyes:'#b6a95d', outfit:'#e8e8e4', accent:'#263d62', style:'bob', guitar:'#d9d8c9', bow:'#355b89' },
  kita: { hair:'#d96c62', hairDark:'#b84d49', eyes:'#a7c84c', outfit:'#f2e8df', accent:'#b84d49', style:'longred', guitar:'#72a9bf', bow:'#d96c62' }
};
function Ball({ position, scale, color, roughness=0.68, ...props }) {
  return <mesh position={position} scale={scale} {...cast} {...props}><sphereGeometry args={[1,32,24]} /><meshStandardMaterial color={color} roughness={roughness} /></mesh>;
}
function Guitar({ color, position=[0.58,-0.45,0.32] }) {
  return <group position={position} rotation={[0.05,0,-0.28]}>
    <Ball position={[0,0,0]} scale={[0.25,0.34,0.09]} color={color} roughness={0.32}/>
    <Ball position={[0,0.2,0.015]} scale={[0.18,0.22,0.095]} color={color} roughness={0.32}/>
    <mesh position={[0,0.63,0]} rotation={[0,0,-0.12]} {...cast}><boxGeometry args={[0.09,0.8,0.07]}/><meshStandardMaterial color="#6b4a36" roughness={0.4}/></mesh>
    <mesh position={[0,1.06,0]} {...cast}><boxGeometry args={[0.18,0.16,0.08]}/><meshStandardMaterial color="#d8d0bd"/></mesh>
    <Ball position={[0,0,0.086]} scale={[0.055,0.055,0.018]} color="#e8d7ad"/>
    <mesh position={[0,0.5,0.055]}><boxGeometry args={[0.008,1.2,0.008]}/><meshStandardMaterial color="#eee5d1" metalness={0.5}/></mesh>
  </group>;
}
function Character({ characterId }) {
  const c = characters[characterId] || characters.bocchi;
  const root = useRef();
  useFrame((state, delta) => { if(root.current) root.current.rotation.y += delta*0.035; });
  const pony = c.style === 'ponytail';
  const bob = c.style === 'bob';
  const long = c.style === 'long' || c.style === 'longred';
  return <group ref={root} position={[0,-0.55,0]}>
    <Float speed={1.1} rotationIntensity={0.035} floatIntensity={0.055}>
      {/* oversized head and face */}
      <Ball position={[0,1.48,0]} scale={[0.88,0.91,0.72]} color={c.hair}/>
      <Ball position={[0,1.37,0.12]} scale={[0.76,0.72,0.65]} color="#ffe2d5"/>
      {/* hair back and side locks */}
      <Ball position={[-0.65,1.38,-0.05]} scale={[0.24,0.76,0.35]} color={c.hairDark}/>
      <Ball position={[0.65,1.38,-0.05]} scale={[0.24,0.76,0.35]} color={c.hairDark}/>
      {long && <><Ball position={[-0.72,0.72,-0.02]} scale={[0.19,0.65,0.24]} color={c.hair}/><Ball position={[0.72,0.72,-0.02]} scale={[0.19,0.65,0.24]} color={c.hair}/></>}
      {bob && <><Ball position={[-0.69,0.95,-0.02]} scale={[0.2,0.53,0.25]} color={c.hair}/><Ball position={[0.69,0.95,-0.02]} scale={[0.2,0.53,0.25]} color={c.hair}/></>}
      {pony && <><Ball position={[0.82,1.38,-0.1]} scale={[0.28,0.25,0.28]} color={c.hairDark}/><Ball position={[1.04,0.96,-0.08]} scale={[0.19,0.57,0.2]} color={c.hair}/><Ball position={[1.16,0.55,-0.05]} scale={[0.14,0.35,0.16]} color={c.hair}/></>}
      {/* fringe */}
      <Ball position={[-0.48,1.9,0.42]} scale={[0.34,0.28,0.27]} color={c.hair}/>
      <Ball position={[-0.12,2.0,0.48]} scale={[0.35,0.31,0.25]} color={c.hair}/>
      <Ball position={[0.28,1.94,0.45]} scale={[0.34,0.3,0.25]} color={c.hair}/>
      <Ball position={[0.57,1.82,0.35]} scale={[0.24,0.28,0.22]} color={c.hair}/>
      {/* eyes */}
      <Ball position={[-0.3,1.47,0.69]} scale={[0.105,0.16,0.045]} color="#fffdf5"/>
      <Ball position={[0.3,1.47,0.69]} scale={[0.105,0.16,0.045]} color="#fffdf5"/>
      <Ball position={[-0.29,1.47,0.73]} scale={[0.066,0.12,0.035]} color={c.eyes}/>
      <Ball position={[0.31,1.47,0.73]} scale={[0.066,0.12,0.035]} color={c.eyes}/>
      <Ball position={[-0.29,1.49,0.76]} scale={[0.028,0.065,0.02]} color="#25242a"/>
      <Ball position={[0.31,1.49,0.76]} scale={[0.028,0.065,0.02]} color="#25242a"/>
      <Ball position={[-0.32,1.53,0.78]} scale={[0.025,0.03,0.012]} color="#fff"/>
      <Ball position={[0.28,1.53,0.78]} scale={[0.025,0.03,0.012]} color="#fff"/>
      <Ball position={[-0.49,1.22,0.66]} scale={[0.13,0.055,0.02]} color="#efa5a0"/>
      <Ball position={[0.49,1.22,0.66]} scale={[0.13,0.055,0.02]} color="#efa5a0"/>
      <Ball position={[0,1.22,0.78]} scale={[0.045,0.025,0.025]} color="#a96862"/>
      {/* torso, skirt, limbs */}
      <Ball position={[0,0.48,0]} scale={[0.43,0.53,0.34]} color={c.outfit}/>
      <Ball position={[0,0.02,0]} scale={[0.47,0.2,0.36]} color={c.accent}/>
      <Ball position={[-0.28,-0.55,0.02]} scale={[0.17,0.4,0.18]} color="#f4d8c8"/>
      <Ball position={[0.28,-0.55,0.02]} scale={[0.17,0.4,0.18]} color="#f4d8c8"/>
      <Ball position={[-0.28,-0.91,0.13]} scale={[0.24,0.14,0.32]} color="#f2eee7"/>
      <Ball position={[0.28,-0.91,0.13]} scale={[0.24,0.14,0.32]} color="#f2eee7"/>
      <Ball position={[-0.48,0.56,0]} scale={[0.16,0.39,0.17]} color={c.outfit}/>
      <Ball position={[0.48,0.56,0]} scale={[0.16,0.39,0.17]} color={c.outfit}/>
      <Ball position={[0,0.69,0.34]} scale={[0.13,0.18,0.08]} color={c.accent}/>
      {characterId === 'nijika' && <><Ball position={[-0.03,2.16,0.1]} scale={[0.19,0.17,0.17]} color={c.hair}/><Ball position={[-0.03,2.28,0.12]} scale={[0.12,0.12,0.12]} color="#f4d46c"/></>}
      {characterId === 'bocchi' && <Ball position={[-0.73,1.82,0.1]} scale={[0.13,0.13,0.12]} color="#76bde5"/>}
      {characterId === 'kita' && <Ball position={[0.74,1.83,0.12]} scale={[0.12,0.12,0.12]} color="#f0d8c5"/>}
      {characterId === 'ryo' && <Ball position={[0.0,2.28,-0.05]} scale={[0.14,0.24,0.12]} color={c.hairDark}/>}
      <Guitar color={c.guitar}/>
    </Float>
  </group>;
}
function LoadedModel({ url }) { const { scene } = useGLTF(url); return <primitive object={scene} />; }
function Stage({ mode, modelUrl, characterId }) {
  return <>
    <color attach="background" args={['#111310']} />
    <fog attach="fog" args={['#111310', 7, 16]} />
    <ambientLight intensity={0.75} />
    <spotLight position={[4,7,5]} intensity={75} angle={0.42} penumbra={0.8} castShadow shadow-mapSize={[2048,2048]} />
    <pointLight position={[-4,1,-3]} intensity={18} color="#9bafaa" />
    <pointLight position={[2,-2,3]} intensity={8} color="#c69d70" />
    <Suspense fallback={null}>
      <Environment preset="studio" />
      {modelUrl ? <LoadedModel url={modelUrl}/> : <Character characterId={characterId}/>}
      <ContactShadows position={[0,-1.72,0]} opacity={0.42} scale={8} blur={2.8} far={4}/>
    </Suspense>
    <OrbitControls makeDefault enableDamping dampingFactor={0.06} minDistance={2.3} maxDistance={8} target={[0,0.35,0]} autoRotate={mode==='exhibition'} autoRotateSpeed={0.55} enablePan={mode==='explore'}/>
  </>;
}
export default function Scene({ mode, modelUrl, characterId }) {
  return <Canvas shadows dpr={[1,1.7]} camera={{position:[0,0.55,5.4],fov:38,near:0.1,far:50}} gl={{antialias:true,alpha:false,powerPreference:'high-performance'}}>
    <Stage mode={mode} modelUrl={modelUrl} characterId={characterId}/>
  </Canvas>;
}