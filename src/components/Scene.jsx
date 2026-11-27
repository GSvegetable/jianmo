import { useEffect, useRef, useState } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { ContactShadows, OrbitControls } from '@react-three/drei';
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { VRMLoaderPlugin, VRMUtils } from '@pixiv/three-vrm';

function createLoader() {
  const loader = new GLTFLoader();
  loader.register((parser) => new VRMLoaderPlugin(parser));
  return loader;
}

function normalizeModel(root, targetHeight) {
  root.updateMatrixWorld(true);
  const bounds = new THREE.Box3().setFromObject(root);
  const center = bounds.getCenter(new THREE.Vector3());
  const height = Math.max(bounds.getSize(new THREE.Vector3()).y, 0.001);
  const normalized = new THREE.Group();

  // Put the feet on the stage before scaling; the old implementation
  // centered the whole bounding box, which made the ground contact drift.
  root.position.x -= center.x;
  root.position.y -= bounds.min.y;
  root.position.z -= center.z;
  normalized.add(root);
  normalized.scale.setScalar(targetHeight / height);
  normalized.position.y = -targetHeight / 2;
  return normalized;
}

function ModelAsset({ vrmUrl, glbUrl, onStatus }) {
  const [model, setModel] = useState(null);
  const vrmRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    let loadedRoot = null;
    const loader = createLoader();
    onStatus('loading');

    const load = (url, fallback = false) => {
      loader.load(
        url,
        (gltf) => {
          if (cancelled) {
            VRMUtils.deepDispose(gltf.scene);
            return;
          }
          const vrm = gltf.userData.vrm ?? null;
          const root = vrm ? vrm.scene : gltf.scene;
          if (vrm && vrm.meta?.metaVersion === '0') VRMUtils.rotateVRM0(vrm);
          const normalized = normalizeModel(root, 2.65);
          loadedRoot = root;
          vrmRef.current = vrm;
          setModel(normalized);
          onStatus('ready');
        },
        undefined,
        () => {
          if (cancelled) return;
          if (!fallback && glbUrl) load(glbUrl, true);
          else onStatus('error');
        },
      );
    };

    if (vrmUrl) load(vrmUrl);
    else if (glbUrl) load(glbUrl, true);
    else onStatus('error');

    return () => {
      cancelled = true;
      vrmRef.current = null;
      if (loadedRoot) VRMUtils.deepDispose(loadedRoot);
    };
  }, [vrmUrl, glbUrl, onStatus]);

  useFrame((_, delta) => vrmRef.current?.update(delta));
  return model ? <primitive object={model} /> : null;
}

function CharmAsset({ glbUrl, onStatus }) {
  const [model, setModel] = useState(null);

  useEffect(() => {
    let cancelled = false;
    onStatus('loading');
    const loader = createLoader();
    loader.load(
      glbUrl,
      (gltf) => {
        if (cancelled) {
          VRMUtils.deepDispose(gltf.scene);
          return;
        }
        setModel(normalizeModel(gltf.scene, 2.2));
        onStatus('ready');
      },
      undefined,
      () => { if (!cancelled) onStatus('error'); },
    );
    return () => { cancelled = true; };
  }, [glbUrl, onStatus]);

  return model ? <primitive object={model} /> : null;
}

function StudioLights() {
  return (
    <>
      <ambientLight intensity={0.62} />
      <hemisphereLight args={['#f2e9dc', '#34342e', 1.0]} />
      <directionalLight position={[3.5, 5, 4]} intensity={2.0} castShadow
        shadow-mapSize-width={1024} shadow-mapSize-height={1024} />
      <directionalLight position={[-4, 2.5, -3]} intensity={1.15} color="#c9d5ed" />
      <spotLight position={[0, 5, -1]} intensity={22} angle={0.52}
        penumbra={0.8} distance={10} color="#f0d9bd" />
    </>
  );
}

export default function Scene({ vrmUrl, glbUrl, name, kind = 'character' }) {
  const [status, setStatus] = useState('loading');
  const modelFile = (vrmUrl || glbUrl || '').split('/').pop();

  return (
    <>
      <Canvas
        shadows
        dpr={[1, 1.5]}
        camera={{
          position: [0, 0.1, 5.15],
          fov: 32,
          near: 0.1,
          far: 100,
        }}
        gl={{
          antialias: true,
          alpha: false,
          powerPreference: 'high-performance',
          toneMapping: THREE.ACESFilmicToneMapping,
          toneMappingExposure: 1.12,
        }}
      >
        <color attach="background" args={['#151611']} />
        <StudioLights />
        {kind === 'charm' ? (
          <CharmAsset glbUrl={glbUrl} onStatus={setStatus} />
        ) : (
          <>
            <ModelAsset vrmUrl={vrmUrl} glbUrl={glbUrl} onStatus={setStatus} />
            <ContactShadows position={[0, -1.325, 0]} opacity={0.38}
              scale={4.8} blur={2.4} far={3} resolution={512} />
          </>
        )}
        <OrbitControls
          makeDefault
          enableDamping
          dampingFactor={0.07}
          minDistance={2.8}
          maxDistance={8.5}
          minPolarAngle={0.18}
          maxPolarAngle={Math.PI * 0.88}
          target={[0, 0, 0]}
          rotateSpeed={0.72}
        />
      </Canvas>
      {status === 'loading' && (
        <div className="model-status" role="status">
          <span className="loading-orbit" />
          <span>正在准备 {name} 的模型</span>
        </div>
      )}
      {status === 'error' && (
        <div className="model-status error" role="alert">
          <strong>{name} 的模型暂时无法加载</strong>
          <span>
            请检查 <code>{modelFile}</code> 是否存在于 <code>public/models/</code>，
            并确认文件可正常读取。
          </span>
        </div>
      )}
    </>
  );
}
