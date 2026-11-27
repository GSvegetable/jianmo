import { Suspense, useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { ContactShadows, Environment, Float, OrbitControls, useGLTF } from '@react-three/drei';
import * as THREE from 'three';

function PlaceholderSculpture({ mode }) {
  const group = useRef();
  const ring = useRef();
  useFrame((state, delta) => {
    if (!group.current) return;
    if (mode === 'exhibition') {
      group.current.rotation.y += delta * 0.16;
      group.current.position.y = Math.sin(state.clock.elapsedTime * 0.7) * 0.045;
    }
    if (ring.current) ring.current.rotation.z += delta * 0.08;
  });

  return (
    <group ref={group}>
      <Float speed={mode === 'exhibition' ? 1.1 : 0.35} rotationIntensity={0.08} floatIntensity={0.12}>
        <mesh castShadow position={[0, 0.28, 0]}>
          <icosahedronGeometry args={[1.05, 5]} />
          <meshPhysicalMaterial color="#b9a58a" roughness={0.28} metalness={0.12} clearcoat={0.72} clearcoatRoughness={0.2} />
        </mesh>
        <mesh scale={[0.62, 1.18, 0.62]} position={[0.18, -0.65, 0.05]} castShadow>
          <sphereGeometry args={[0.72, 64, 64]} />
          <meshPhysicalMaterial color="#6c716a" roughness={0.32} metalness={0.18} />
        </mesh>
        <mesh ref={ring} rotation={[1.18, 0.2, -0.35]} scale={[1.42, 1.42, 1.42]}>
          <torusGeometry args={[1.02, 0.012, 12, 180]} />
          <meshStandardMaterial color="#c7a77b" metalness={0.8} roughness={0.28} />
        </mesh>
        <mesh rotation={[0.4, 0.8, 0.1]} scale={[1.55, 1.55, 1.55]}>
          <torusGeometry args={[0.92, 0.006, 8, 180]} />
          <meshStandardMaterial color="#e5ded2" metalness={0.65} roughness={0.4} transparent opacity={0.55} />
        </mesh>
      </Float>
    </group>
  );
}

function LoadedModel({ url }) {
  const { scene } = useGLTF(url);
  return <primitive object={scene} />;
}

function Stage({ mode, modelUrl }) {
  return (
    <>
      <color attach="background" args={['#111310']} />
      <fog attach="fog" args={['#111310', 7, 16]} />
      <ambientLight intensity={0.55} />
      <spotLight position={[4, 7, 5]} intensity={95} angle={0.42} penumbra={0.8} castShadow shadow-mapSize={[2048, 2048]} />
      <pointLight position={[-4, 1, -3]} intensity={18} color="#9bafaa" />
      <pointLight position={[2, -2, 3]} intensity={8} color="#c69d70" />
      <Suspense fallback={null}>
        <Environment preset="studio" />
        {modelUrl ? <LoadedModel url={modelUrl} /> : <PlaceholderSculpture mode={mode} />}
        <ContactShadows position={[0, -1.72, 0]} opacity={0.42} scale={8} blur={2.8} far={4} />
      </Suspense>
      <OrbitControls
        makeDefault
        enableDamping
        dampingFactor={0.06}
        minDistance={2.3}
        maxDistance={8}
        target={[0, 0, 0]}
        autoRotate={mode === 'exhibition'}
        autoRotateSpeed={0.55}
        enablePan={mode === 'explore'}
      />
    </>
  );
}

export default function Scene({ mode, modelUrl }) {
  return (
    <Canvas
      shadows
      dpr={[1, 1.7]}
      camera={{ position: [0, 0.3, 5.2], fov: 38, near: 0.1, far: 50 }}
      gl={{ antialias: true, alpha: false, powerPreference: 'high-performance' }}
    >
      <Stage mode={mode} modelUrl={modelUrl} />
    </Canvas>
  );
}