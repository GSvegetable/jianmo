import { useEffect, useRef, useState } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { ContactShadows, OrbitControls } from '@react-three/drei';
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { VRMLoaderPlugin, VRMUtils } from '@pixiv/three-vrm';

// One loader handles both .vrm and .glb: VRM is glTF with an extension,
// and VRMLoaderPlugin only activates when that extension is present.
function createLoader() {
  const loader = new GLTFLoader();
  loader.register((parser) => new VRMLoaderPlugin(parser));
  return loader;
}

function ModelAsset({ vrmUrl, glbUrl, onStatus }) {
  const [model, setModel] = useState(null);
  const vrmRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    let loadedRoot = null;
    onStatus('loading');
    const loader = createLoader();

    const tryLoad = (url, isFallback) => {
      loader.load(
        url,
        (gltf) => {
          if (cancelled) return;
          const vrm = gltf.userData.vrm ?? null;
          const root = vrm ? vrm.scene : gltf.scene;
          if (vrm && vrm.meta?.metaVersion === '0') {
            VRMUtils.rotateVRM0(vrm); // VRM0 faces -Z; turn it toward the camera
          }
          const box = new THREE.Box3().setFromObject(root);
          const size = box.getSize(new THREE.Vector3());
          const center = box.getCenter(new THREE.Vector3());
          const longestSide = Math.max(size.x, size.y, size.z) || 1;
          root.position.sub(center);
          const normalized = new THREE.Group();
          normalized.scale.setScalar(3.2 / longestSide);
          normalized.add(root);
          loadedRoot = root;
          vrmRef.current = vrm;
          setModel(normalized);
          onStatus('ready');
        },
        undefined,
        () => {
          if (cancelled) return;
          if (!isFallback && glbUrl) {
            tryLoad(glbUrl, true);
          } else {
            onStatus('error');
          }
        },
      );
    };

    tryLoad(vrmUrl, false);
    return () => {
      cancelled = true;
      vrmRef.current = null;
      if (loadedRoot) VRMUtils.deepDispose(loadedRoot);
    };
  }, [vrmUrl, glbUrl, onStatus]);

  useFrame((_, delta) => {
    vrmRef.current?.update(delta); // spring bones: hair & skirt physics
  });

  return model ? <primitive object={model} /> : null;
}

function Stage({ vrmUrl, glbUrl, onStatus }) {
  return (
    <>
      <color attach="background" args={['#111210']} />
      {/* MToon materials carry their own toon ramp; plain lights are enough.
          No HDR environment fetch, so the viewer works fully offline. */}
      <ambientLight intensity={0.85} />
      <directionalLight position={[3, 6, 5]} intensity={1.7} />
      <directionalLight position={[-4, 2, -3]} intensity={0.6} color="#d6d9e8" />
      <ModelAsset vrmUrl={vrmUrl} glbUrl={glbUrl} onStatus={onStatus} />
      <ContactShadows position={[0, -1.65, 0]} opacity={0.32} scale={7} blur={2.5} far={4} />
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

export default function Scene({ vrmUrl, glbUrl, name }) {
  const [status, setStatus] = useState('loading');
  const vrmFile = vrmUrl.split('/').pop();

  return (
    <>
      <Canvas
        shadows
        dpr={[1, 1.75]}
        camera={{ position: [0, 0.25, 5.2], fov: 34, near: 0.1, far: 100 }}
        gl={{ antialias: true, alpha: false, powerPreference: 'high-performance' }}
      >
        <Stage vrmUrl={vrmUrl} glbUrl={glbUrl} onStatus={setStatus} />
      </Canvas>
      {status === 'loading' && (
        <div className="model-status" role="status">
          正在加载 {name} …
        </div>
      )}
      {status === 'error' && (
        <div className="model-status error" role="alert">
          <strong>{name} 的模型文件缺失</strong>
          <span>
            请用 VRoid Studio 导出该角色，命名为 <code>{vrmFile}</code>，
            放入 <code>public/models/characters/</code> 后重新构建。
          </span>
        </div>
      )}
    </>
  );
}
