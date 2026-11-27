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

// A charm is not a figurine on a plinth: it hangs from a cord.  The cord
// is part of the scene, not the asset, so the piece reads as a keychain
// the moment it is on screen.
function CharmAsset({ glbUrl, onStatus }) {
  const [model, setModel] = useState(null);
  const [top, setTop] = useState(1.6);

  useEffect(() => {
    let cancelled = false;
    onStatus('loading');
    const loader = createLoader();

    loader.load(
      glbUrl,
      (gltf) => {
        if (cancelled) return;
        const root = gltf.scene;
        const box = new THREE.Box3().setFromObject(root);
        const size = box.getSize(new THREE.Vector3());
        const center = box.getCenter(new THREE.Vector3());
        const longestSide = Math.max(size.x, size.y, size.z) || 1;
        root.position.sub(center);
        const normalized = new THREE.Group();
        // a charm is much taller than it is wide, so it is framed a
        // little smaller than a standing character to keep the whole
        // piece -- ring, head, dress -- inside the viewport
        const scale = 2.5 / longestSide;
        normalized.scale.setScalar(scale);
        normalized.add(root);
        setTop((size.y * scale) / 2);
        setModel(normalized);
        onStatus('ready');
      },
      undefined,
      () => {
        if (!cancelled) onStatus('error');
      },
    );

    return () => {
      cancelled = true;
    };
  }, [glbUrl, onStatus]);

  return (
    <group>
      {model ? <primitive object={model} /> : null}
      <mesh position={[0, top + 1.5, 0]}>
        <cylinderGeometry args={[0.03, 0.03, 3.0, 12]} />
        <meshStandardMaterial color="#26262c" roughness={0.9} />
      </mesh>
    </group>
  );
}

function CharacterStage({ vrmUrl, glbUrl, onStatus }) {
  return (
    <>
      <ambientLight intensity={0.85} />
      <directionalLight position={[3, 6, 5]} intensity={1.7} />
      <directionalLight position={[-4, 2, -3]} intensity={0.6} color="#d6d9e8" />
      <ModelAsset vrmUrl={vrmUrl} glbUrl={glbUrl} onStatus={onStatus} />
      <ContactShadows position={[0, -1.65, 0]} opacity={0.32} scale={7} blur={2.5} far={4} />
    </>
  );
}

function CharmStage({ glbUrl, onStatus }) {
  return (
    <>
      {/* a charm hangs in the light, so the key light is pushed to the side
          and a rim light separates it from the background */}
      <ambientLight intensity={0.75} />
      <directionalLight position={[3, 5, 4]} intensity={1.9} />
      <directionalLight position={[-4, 2, -3]} intensity={0.8} color="#dfe6ff" />
      <CharmAsset glbUrl={glbUrl} onStatus={onStatus} />
    </>
  );
}

export default function Scene({ vrmUrl, glbUrl, name, kind = 'character' }) {
  const [status, setStatus] = useState('loading');
  const vrmFile = (vrmUrl ?? '').split('/').pop();

  return (
    <>
      <Canvas
        shadows
        dpr={[1, 1.75]}
        camera={{ position: [0, 0.25, 5.2], fov: 34, near: 0.1, far: 100 }}
        gl={{ antialias: true, alpha: false, powerPreference: 'high-performance' }}
      >
        <color attach="background" args={['#111210']} />
        {kind === 'charm' ? (
          <CharmStage glbUrl={glbUrl} onStatus={setStatus} />
        ) : (
          <CharacterStage vrmUrl={vrmUrl} glbUrl={glbUrl} onStatus={setStatus} />
        )}
        <OrbitControls
          makeDefault
          enableDamping
          dampingFactor={0.065}
          minDistance={1.8}
          maxDistance={9}
          target={[0, 0, 0]}
          rotateSpeed={0.8}
        />
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
