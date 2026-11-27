import { Component, Suspense, useMemo } from 'react';
import { Canvas } from '@react-three/fiber';
import { ContactShadows, Environment, OrbitControls, useGLTF } from '@react-three/drei';
import * as THREE from 'three';

class ModelErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { failed: false };
  }

  static getDerivedStateFromError() {
    return { failed: true };
  }

  render() {
    if (this.state.failed) return <ModelStatus />;
    return this.props.children;
  }
}

function ModelStatus() {
  return (
    <group>
      <mesh position={[0, 0, 0]}>
        <sphereGeometry args={[0.002, 8, 8]} />
        <meshBasicMaterial transparent opacity={0} />
      </mesh>
    </group>
  );
}

function ModelAsset({ url }) {
  const { scene } = useGLTF(url);
  const model = useMemo(() => {
    const clone = scene.clone(true);
    const bounds = new THREE.Box3().setFromObject(clone);
    const size = bounds.getSize(new THREE.Vector3());
    const center = bounds.getCenter(new THREE.Vector3());
    const longestSide = Math.max(size.x, size.y, size.z) || 1;
    clone.position.sub(center);
    clone.scale.setScalar(3.2 / longestSide);
    return clone;
  }, [scene]);

  return <primitive object={model} />;
}

function Stage({ modelUrl }) {
  return (
    <>
      <color attach="background" args={['#111210']} />
      <ambientLight intensity={0.75} />
      <directionalLight position={[4, 7, 5]} intensity={2.2} />
      <directionalLight position={[-4, 2, -3]} intensity={1.1} color="#d6d9e8" />
      <Suspense fallback={null}>
        <Environment preset="studio" />
        {modelUrl ? (
          <ModelErrorBoundary key={modelUrl}>
            <ModelAsset url={modelUrl} />
          </ModelErrorBoundary>
        ) : null}
        {modelUrl ? <ContactShadows position={[0, -1.65, 0]} opacity={0.32} scale={7} blur={2.5} far={4} /> : null}
      </Suspense>
      <OrbitControls
        makeDefault
        enableDamping
        dampingFactor={0.065}
        minDistance={1.8}
        maxDistance={9}
        target={[0, 0, 0]}
        rotateSpeed={0.8}
      />
    </>
  );
}

export default function Scene({ modelUrl }) {
  return (
    <Canvas
      shadows
      dpr={[1, 1.75]}
      camera={{ position: [0, 0.25, 5.2], fov: 34, near: 0.1, far: 100 }}
      gl={{ antialias: true, alpha: false, powerPreference: 'high-performance' }}
    >
      <Stage modelUrl={modelUrl} />
    </Canvas>
  );
}
