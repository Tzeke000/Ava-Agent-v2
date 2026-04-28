import { useEffect, useRef } from "react";
import * as THREE from "three";

export interface OrbProps {
  emotion: string;
  emotionColor: string;
  state: "idle" | "thinking" | "deep" | "speaking" | "bored" | "excited" | "offline";
  size?: number;
}

type ParticleBand = "inner" | "mid" | "outer";
type ParticleData = { base: THREE.Vector3; phase: number; drift: THREE.Vector3; band: ParticleBand };
type StreamData = {
  line: THREE.Line;
  points: THREE.Vector3[];
  baseOpacity: number;
  speed: number;
  phase: number;
  radialBias: number;
};

function hexToColor(hex: string): THREE.Color {
  try {
    return new THREE.Color(hex || "#1a6cf5");
  } catch {
    return new THREE.Color("#1a6cf5");
  }
}

function randomPointInSphere(radius = 1): THREE.Vector3 {
  const u = Math.random();
  const v = Math.random();
  const w = Math.random();
  const theta = 2 * Math.PI * u;
  const phi = Math.acos(2 * v - 1);
  const r = radius * Math.cbrt(w);
  return new THREE.Vector3(r * Math.sin(phi) * Math.cos(theta), r * Math.sin(phi) * Math.sin(theta), r * Math.cos(phi));
}

function makeGlowTexture(): THREE.Texture {
  const c = document.createElement("canvas");
  c.width = 128;
  c.height = 128;
  const ctx = c.getContext("2d");
  if (!ctx) return new THREE.Texture();
  const g = ctx.createRadialGradient(64, 64, 6, 64, 64, 64);
  g.addColorStop(0, "rgba(255,255,255,1)");
  g.addColorStop(0.25, "rgba(255,255,255,0.75)");
  g.addColorStop(0.55, "rgba(170,200,255,0.3)");
  g.addColorStop(1, "rgba(0,0,0,0)");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, 128, 128);
  const tex = new THREE.CanvasTexture(c);
  tex.needsUpdate = true;
  return tex;
}

export default function OrbCanvas({ emotionColor, state, size = 300 }: OrbProps) {
  const mountRef = useRef<HTMLDivElement | null>(null);
  const stateRef = useRef(state);
  const colorRef = useRef<THREE.Color>(hexToColor(emotionColor));
  const targetColorRef = useRef<THREE.Color>(hexToColor(emotionColor));
  const rafRef = useRef<number>(0);

  useEffect(() => {
    stateRef.current = state;
  }, [state]);

  useEffect(() => {
    targetColorRef.current = hexToColor(emotionColor);
  }, [emotionColor]);

  useEffect(() => {
    const host = mountRef.current;
    if (!host) return;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(70, 1, 0.1, 100);
    camera.position.z = 2.8;
    camera.lookAt(0, 0, 0);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setClearColor(0x000000, 0);
    renderer.domElement.style.background = "transparent";
    renderer.domElement.style.width = "100%";
    renderer.domElement.style.height = "100%";
    renderer.domElement.style.display = "block";
    host.appendChild(renderer.domElement);

    const ambient = new THREE.AmbientLight(0x222233, 0.22);
    scene.add(ambient);
    const point = new THREE.PointLight(0xffffff, 2.0, 5);
    scene.add(point);

    const orbRoot = new THREE.Group();
    const innerGroup = new THREE.Group();
    const streamGroup = new THREE.Group();
    orbRoot.add(innerGroup);
    orbRoot.add(streamGroup);
    scene.add(orbRoot);

    const coreMaterial = new THREE.MeshBasicMaterial({
      color: colorRef.current.clone().lerp(new THREE.Color("#ffffff"), 0.4),
      transparent: true,
      opacity: 0.95,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    const coreMesh = new THREE.Mesh(new THREE.SphereGeometry(0.15, 32, 32), coreMaterial);
    innerGroup.add(coreMesh);

    const streamCount = 16;
    const streams: StreamData[] = [];
    for (let i = 0; i < streamCount; i++) {
      const controlPoints = Array.from({ length: 6 }, () => randomPointInSphere(0.95));
      const curve = new THREE.CatmullRomCurve3(controlPoints, false, "catmullrom", 0.45);
      const points = curve.getPoints(60);
      const geom = new THREE.BufferGeometry().setFromPoints(points);
      const mat = new THREE.LineBasicMaterial({
        color: colorRef.current,
        transparent: true,
        opacity: 0.62 + Math.random() * 0.2,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
      });
      const line = new THREE.Line(geom, mat);
      streamGroup.add(line);
      streams.push({
        line,
        points,
        baseOpacity: mat.opacity,
        speed: 0.3 + Math.random() * 0.8,
        phase: Math.random() * Math.PI * 2,
        radialBias: 0.7 + Math.random() * 0.35,
      });
    }

    const particleCount = 1500;
    const pGeom = new THREE.BufferGeometry();
    const pPos = new Float32Array(particleCount * 3);
    const pCol = new Float32Array(particleCount * 3);
    const pSize = new Float32Array(particleCount);
    const pdata: ParticleData[] = [];
    for (let i = 0; i < particleCount; i++) {
      const roll = Math.random();
      const band: ParticleBand = roll < 0.5 ? "inner" : roll < 0.82 ? "mid" : "outer";
      let radius = 0;
      if (band === "inner") radius = 0.1 + Math.random() * 0.3;
      else if (band === "mid") radius = 0.4 + Math.random() * 0.3;
      else radius = 0.7 + Math.random() * 0.3;
      const base = randomPointInSphere(1).normalize().multiplyScalar(radius);
      pdata.push({
        base,
        phase: Math.random() * Math.PI * 2,
        drift: new THREE.Vector3((Math.random() - 0.5) * 0.025, (Math.random() - 0.5) * 0.025, (Math.random() - 0.5) * 0.025),
        band,
      });
      pPos[i * 3] = base.x;
      pPos[i * 3 + 1] = base.y;
      pPos[i * 3 + 2] = base.z;
      if (band === "inner") pSize[i] = 3;
      else if (band === "mid") pSize[i] = 2;
      else pSize[i] = 1;
    }
    pGeom.setAttribute("position", new THREE.BufferAttribute(pPos, 3));
    pGeom.setAttribute("color", new THREE.BufferAttribute(pCol, 3));
    pGeom.setAttribute("size", new THREE.BufferAttribute(pSize, 1));
    const pMat = new THREE.ShaderMaterial({
      transparent: true,
      depthWrite: false,
      vertexColors: true,
      blending: THREE.AdditiveBlending,
      uniforms: { uScale: { value: 1 } },
      vertexShader: `
        attribute float size;
        varying vec3 vColor;
        uniform float uScale;
        void main() {
          vColor = color;
          vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
          gl_PointSize = size * uScale * (300.0 / -mvPosition.z);
          gl_Position = projectionMatrix * mvPosition;
        }
      `,
      fragmentShader: `
        varying vec3 vColor;
        void main() {
          float d = length(gl_PointCoord - vec2(0.5));
          float a = smoothstep(0.5, 0.08, d);
          gl_FragColor = vec4(vColor, a);
        }
      `,
    });
    const points = new THREE.Points(pGeom, pMat);
    innerGroup.add(points);

    const shellMaterial = new THREE.MeshBasicMaterial({
      color: colorRef.current,
      transparent: true,
      opacity: 0.1,
      wireframe: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    const shell = new THREE.Mesh(new THREE.SphereGeometry(1, 22, 22), shellMaterial);
    orbRoot.add(shell);

    const haloTexture = makeGlowTexture();
    const haloMaterial = new THREE.SpriteMaterial({
      map: haloTexture,
      color: colorRef.current,
      transparent: true,
      opacity: 0.2,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    const halo = new THREE.Sprite(haloMaterial);
    halo.scale.set(3.5, 3.5, 1);
    scene.add(halo);

    const tmp = new THREE.Vector3();
    const flashTimer = { value: 0 };

    const resize = () => {
      const w = host.clientWidth || size;
      const h = host.clientHeight || size;
      renderer.setSize(w, h, false);
      camera.aspect = w / Math.max(1, h);
      camera.updateProjectionMatrix();
      pMat.uniforms.uScale.value = Math.max(0.62, Math.min(1.35, w / 240));
    };
    resize();
    const ro = new ResizeObserver(() => resize());
    ro.observe(host);

    const animate = () => {
      const t = performance.now() * 0.001;
      rafRef.current = requestAnimationFrame(animate);
      colorRef.current.lerp(targetColorRef.current, 0.05);

      const s = stateRef.current;
      const isOffline = s === "offline";
      const activeColor = isOffline ? new THREE.Color("#6b7280") : colorRef.current.clone();
      point.color.copy(activeColor);

      let rot = 0.001;
      let pulseHz = 1 / 3;
      let streamDrift = 0.3;
      let flashChance = 0.006;
      let burst = 0;
      if (s === "thinking") { rot = 0.003; pulseHz = 1; streamDrift = 0.6; flashChance = 0.02; }
      else if (s === "deep") { rot = 0.006; pulseHz = 1.6; streamDrift = 1.0; flashChance = 0.05; }
      else if (s === "speaking") { rot = 0.0026; pulseHz = 1.9; streamDrift = 0.7; flashChance = 0.03; }
      else if (s === "bored") { rot = 0.0003; pulseHz = 0.18; streamDrift = 0.12; flashChance = 0.0015; }
      else if (s === "excited") { rot = 0.008; pulseHz = 2.3; streamDrift = 1.4; flashChance = 0.07; burst = 0.12; }
      else if (isOffline) { rot = 0.00004; pulseHz = 0.08; streamDrift = 0.06; flashChance = 0; }

      const coreScale = THREE.MathUtils.lerp(0.9, 1.1, 0.5 + 0.5 * Math.sin(t * Math.PI * 2 * pulseHz));
      coreMesh.scale.setScalar(coreScale + (burst ? Math.abs(Math.sin(t * 6)) * burst : 0));
      coreMaterial.color.copy(activeColor).lerp(new THREE.Color("#ffffff"), isOffline ? 0.05 : 0.52);
      coreMaterial.opacity = isOffline ? 0.18 : 0.94;
      haloMaterial.color.copy(activeColor);
      haloMaterial.opacity = isOffline ? 0.07 : 0.15 + 0.1 * (0.5 + 0.5 * Math.sin(t * 1.3));
      shellMaterial.color.copy(activeColor);
      shellMaterial.opacity = isOffline ? 0.03 : 0.08 + 0.04 * (0.5 + 0.5 * Math.sin(t * 0.8));

      innerGroup.rotation.y += rot;
      innerGroup.rotation.x += rot * 0.45;
      streamGroup.rotation.y += rot * 1.25;
      streamGroup.rotation.x += rot * 0.62;
      shell.rotation.y -= rot * 0.8;
      shell.rotation.x -= rot * 0.35;

      if (Math.random() < flashChance) flashTimer.value = 1;
      flashTimer.value = Math.max(0, flashTimer.value - 0.04);

      for (let i = 0; i < streams.length; i++) {
        const stream = streams[i];
        const mat = stream.line.material as THREE.LineBasicMaterial;
        mat.color.copy(activeColor);
        const wave = Math.sin(t * streamDrift * stream.speed + stream.phase);
        const strongFlash = s === "deep" ? 0.45 : 0.22;
        const flash = flashTimer.value * (s === "deep" ? (i % 3 === 0 ? 1 : 0.6) : (i % 5 === 0 ? 1 : 0.4));
        mat.opacity = (isOffline ? 0.03 : stream.baseOpacity) + flash * strongFlash;
        const geom = stream.line.geometry as THREE.BufferGeometry;
        const attr = geom.getAttribute("position") as THREE.BufferAttribute;
        for (let p = 0; p < stream.points.length; p++) {
          const base = stream.points[p];
          const ripple = s === "speaking" ? Math.sin(t * 7 - p * 0.22) * 0.02 : 0;
          const excite = s === "excited" ? Math.max(0, Math.sin(t * 10 + stream.phase)) * 0.08 : 0;
          const amp = (0.03 + excite) * stream.radialBias + ripple;
          attr.setXYZ(p, base.x + Math.sin(t * streamDrift + p * 0.2 + stream.phase) * amp, base.y + wave * amp, base.z + Math.cos(t * streamDrift + p * 0.23) * amp);
        }
        attr.needsUpdate = true;
      }

      const posAttr = pGeom.getAttribute("position") as THREE.BufferAttribute;
      const colAttr = pGeom.getAttribute("color") as THREE.BufferAttribute;
      for (let i = 0; i < particleCount; i++) {
        const p = pdata[i];
        const idx = i * 3;
        tmp.copy(p.base);
        const driftWave = Math.sin(t * (0.6 + p.phase) + p.phase) * 0.02;
        tmp.addScaledVector(p.drift, driftWave * (s === "bored" ? 0.3 : s === "deep" ? 1.2 : 0.8));
        if (s === "speaking") {
          const radial = tmp.length();
          tmp.multiplyScalar(1 + Math.sin(t * 9 - radial * 9) * 0.02);
        } else if (s === "excited") {
          tmp.multiplyScalar(1 + Math.abs(Math.sin(t * 10 + p.phase)) * 0.07);
        } else if (isOffline && p.band === "outer") {
          tmp.multiplyScalar(1 + 0.0007 * i / particleCount);
        }
        posAttr.setXYZ(i, tmp.x, tmp.y, tmp.z);
        const c = activeColor.clone();
        if (p.band === "inner") c.lerp(new THREE.Color("#ffffff"), 0.42).multiplyScalar(isOffline ? 0.3 : 1.28);
        else if (p.band === "mid") c.multiplyScalar(isOffline ? 0.25 : 0.94);
        else c.multiplyScalar(isOffline ? 0.18 : 0.5);
        colAttr.setXYZ(i, c.r, c.g, c.b);
      }
      posAttr.needsUpdate = true;
      colAttr.needsUpdate = true;

      renderer.render(scene, camera);
    };
    animate();

    return () => {
      cancelAnimationFrame(rafRef.current);
      ro.disconnect();
      streams.forEach((s) => {
        s.line.geometry.dispose();
        (s.line.material as THREE.Material).dispose();
      });
      pGeom.dispose();
      pMat.dispose();
      shell.geometry.dispose();
      shellMaterial.dispose();
      coreMesh.geometry.dispose();
      coreMaterial.dispose();
      haloTexture.dispose();
      haloMaterial.dispose();
      renderer.dispose();
      if (renderer.domElement.parentElement === host) host.removeChild(renderer.domElement);
    };
  }, [size]);

  return (
    <div
      ref={mountRef}
      style={{
        width: `${size}px`,
        height: `${size}px`,
        maxWidth: "100%",
        maxHeight: "100%",
        position: "relative",
        overflow: "visible",
        background: "transparent",
      }}
      aria-label="Ava energy orb"
      role="img"
    />
  );
}

