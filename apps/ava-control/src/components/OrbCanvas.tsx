import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";

export interface OrbProps {
  emotion: string;
  emotionColor: string;
  state: "idle" | "thinking" | "deep" | "speaking" | "bored" | "excited" | "offline";
  size?: number;
}

type ParticleData = {
  base: THREE.Vector3;
  phase: number;
  speed: number;
  drift: THREE.Vector3;
  radial: number;
};

function hexToColor(hex: string): THREE.Color {
  try {
    return new THREE.Color(hex || "#1a6cf5");
  } catch {
    return new THREE.Color("#1a6cf5");
  }
}

export default function OrbCanvas({ emotionColor, state, size = 300 }: OrbProps) {
  const mountRef = useRef<HTMLDivElement | null>(null);
  const colorRef = useRef<THREE.Color>(hexToColor(emotionColor));
  const targetColorRef = useRef<THREE.Color>(hexToColor(emotionColor));
  const frameRef = useRef<number>(0);
  const pointLightRef = useRef<THREE.PointLight | null>(null);

  const particleCount = useMemo(() => {
    if (size <= 130) return 1100;
    if (size <= 220) return 1700;
    return 2200;
  }, [size]);

  useEffect(() => {
    targetColorRef.current = hexToColor(emotionColor);
  }, [emotionColor]);

  useEffect(() => {
    const host = mountRef.current;
    if (!host) return;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(48, 1, 0.1, 1000);
    camera.position.z = 5.2;

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setClearColor(0x000000, 0);
    host.appendChild(renderer.domElement);

    const ambient = new THREE.AmbientLight(0x223344, 0.28);
    scene.add(ambient);
    const point = new THREE.PointLight(0x6699ff, 1.35, 28, 2);
    point.position.set(0, 0, 0);
    pointLightRef.current = point;
    scene.add(point);

    const geom = new THREE.BufferGeometry();
    const positions = new Float32Array(particleCount * 3);
    const colors = new Float32Array(particleCount * 3);
    const sizes = new Float32Array(particleCount);
    const pdata: ParticleData[] = [];

    const baseColor = colorRef.current.clone();
    for (let i = 0; i < particleCount; i++) {
      const u = Math.random();
      const v = Math.random();
      const theta = 2 * Math.PI * u;
      const phi = Math.acos(2 * v - 1);
      const radius = 1.35 + (Math.random() - 0.5) * 0.24;
      const base = new THREE.Vector3(
        radius * Math.sin(phi) * Math.cos(theta),
        radius * Math.sin(phi) * Math.sin(theta),
        radius * Math.cos(phi)
      );
      pdata.push({
        base,
        phase: Math.random() * Math.PI * 2,
        speed: 0.4 + Math.random() * 1.2,
        drift: new THREE.Vector3((Math.random() - 0.5) * 0.03, (Math.random() - 0.5) * 0.03, (Math.random() - 0.5) * 0.03),
        radial: radius,
      });
      positions[i * 3 + 0] = base.x;
      positions[i * 3 + 1] = base.y;
      positions[i * 3 + 2] = base.z;
      const bright = THREE.MathUtils.clamp(1.4 - radius * 0.35, 0.55, 1.25);
      const c = baseColor.clone().multiplyScalar(bright);
      colors[i * 3 + 0] = c.r;
      colors[i * 3 + 1] = c.g;
      colors[i * 3 + 2] = c.b;
      sizes[i] = 1.5 + Math.random() * 1.35;
    }

    geom.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    geom.setAttribute("color", new THREE.BufferAttribute(colors, 3));
    geom.setAttribute("size", new THREE.BufferAttribute(sizes, 1));

    const mat = new THREE.ShaderMaterial({
      transparent: true,
      depthWrite: false,
      vertexColors: true,
      blending: THREE.AdditiveBlending,
      uniforms: {
        uScale: { value: 1.0 },
      },
      vertexShader: `
        attribute float size;
        varying vec3 vColor;
        uniform float uScale;
        void main() {
          vColor = color;
          vec4 mv = modelViewMatrix * vec4(position, 1.0);
          gl_PointSize = size * uScale * (300.0 / -mv.z);
          gl_Position = projectionMatrix * mv;
        }
      `,
      fragmentShader: `
        varying vec3 vColor;
        void main() {
          vec2 p = gl_PointCoord - vec2(0.5);
          float d = length(p);
          float alpha = smoothstep(0.5, 0.08, d);
          gl_FragColor = vec4(vColor, alpha);
        }
      `,
    });
    const points = new THREE.Points(geom, mat);
    scene.add(points);

    const tmp = new THREE.Vector3();
    const shootBase = Math.floor(Math.random() * particleCount);

    const resize = () => {
      const w = host.clientWidth || size;
      const h = host.clientHeight || size;
      renderer.setSize(w, h, false);
      camera.aspect = w / Math.max(h, 1);
      camera.updateProjectionMatrix();
      mat.uniforms.uScale.value = Math.max(0.65, Math.min(1.45, w / 240));
    };
    resize();
    const ro = new ResizeObserver(() => resize());
    ro.observe(host);

    const animate = () => {
      const t = performance.now() * 0.001;
      frameRef.current = requestAnimationFrame(animate);

      // smooth emotion color transition
      colorRef.current.lerp(targetColorRef.current, 0.04);
      point.color.copy(colorRef.current);

      let speedMul = 1.0;
      let turbulence = 0.02;
      let pulse = 1.0;
      switch (state) {
        case "bored":
          speedMul = 0.42;
          turbulence = 0.006;
          pulse = 0.93;
          break;
        case "thinking":
          speedMul = 1.4;
          turbulence = 0.03;
          pulse = 1.04;
          break;
        case "deep":
          speedMul = 2.0;
          turbulence = 0.05;
          pulse = 1.08;
          break;
        case "speaking":
          speedMul = 1.2;
          turbulence = 0.02;
          pulse = 1.02;
          break;
        case "excited":
          speedMul = 2.15;
          turbulence = 0.08;
          pulse = 1.12;
          break;
        case "offline":
          speedMul = 0.26;
          turbulence = 0.007;
          pulse = 0.88;
          break;
        default:
          break;
      }

      const activeColor = state === "offline" ? new THREE.Color("#6b7280") : colorRef.current;
      const posAttr = geom.getAttribute("position") as THREE.BufferAttribute;
      const colAttr = geom.getAttribute("color") as THREE.BufferAttribute;

      for (let i = 0; i < particleCount; i++) {
        const p = pdata[i];
        const idx = i * 3;
        const wave = Math.sin(t * (1.1 * speedMul) + p.phase);
        const spin = Math.cos(t * (0.9 * speedMul) + p.phase * 0.7);

        tmp.copy(p.base);
        tmp.multiplyScalar(pulse + wave * turbulence);
        tmp.x += p.drift.x * wave * 2.0;
        tmp.y += p.drift.y * spin * 2.0;
        tmp.z += p.drift.z * Math.sin(t * 0.8 + p.phase);

        if (state === "speaking") {
          const audioWave = Math.sin(t * 8 + p.radial * 22);
          tmp.multiplyScalar(1 + audioWave * 0.02);
        } else if (state === "deep") {
          const spike = Math.sin(t * 18 + p.phase * 2.2);
          tmp.multiplyScalar(1 + Math.max(0, spike) * 0.06);
        } else if (state === "excited") {
          const burst = Math.sin(t * 14 + p.phase);
          tmp.multiplyScalar(1 + Math.abs(burst) * 0.1);
        } else if (state === "offline") {
          tmp.multiplyScalar(1.0 + Math.min(0.55, t * 0.02));
        }

        // occasional "shoot out and return"
        if (i === (shootBase + Math.floor(t * 7.0)) % particleCount && state !== "offline") {
          tmp.multiplyScalar(1.5 + Math.sin(t * 8) * 0.22);
        }

        positions[idx + 0] = tmp.x;
        positions[idx + 1] = tmp.y;
        positions[idx + 2] = tmp.z;

        const bright = THREE.MathUtils.clamp(1.35 - p.radial * 0.35, 0.5, 1.25);
        const c = activeColor.clone().multiplyScalar(bright * (state === "deep" ? 1.18 : 1.0));
        colors[idx + 0] = c.r;
        colors[idx + 1] = c.g;
        colors[idx + 2] = c.b;
      }

      posAttr.needsUpdate = true;
      colAttr.needsUpdate = true;
      points.rotation.y += 0.0025 * speedMul;
      points.rotation.x += 0.0015 * speedMul;
      renderer.render(scene, camera);
    };
    animate();

    return () => {
      cancelAnimationFrame(frameRef.current);
      ro.disconnect();
      scene.remove(points);
      geom.dispose();
      mat.dispose();
      renderer.dispose();
      if (renderer.domElement.parentElement === host) {
        host.removeChild(renderer.domElement);
      }
    };
  }, [particleCount, size, state]);

  return (
    <div
      ref={mountRef}
      style={{
        width: `${size}px`,
        height: `${size}px`,
        maxWidth: "100%",
        maxHeight: "100%",
      }}
      aria-label="Ava particle orb"
      role="img"
    />
  );
}

