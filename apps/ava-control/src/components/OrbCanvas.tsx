import { memo, useEffect, useRef } from "react";
import * as THREE from "three";

type OrbState = "idle" | "thinking" | "deep" | "speaking" | "bored" | "excited" | "offline" | "listening";

interface OrbProps {
  emotion: string;
  emotionColor: string;
  state: OrbState;
  size?: number;
  /** Phase 49: override shape for pointer morph */
  shapeOverride?: string;
  /** Live speaking amplitude 0-1 (read from snap.tts.tts_amplitude). */
  amplitude?: number;
  /** Energy 0-1 from snap.mood.raw_mood.energy — drives breathing rate. */
  energy?: number;
}

const EMOTION_CONFIG: Record<string, {
  color: string; lightColor: string; darkColor: string;
  shape: string; coreScale: number; particleSpread: number;
  connectionDensity: number; gravityY: number; tiltX: number;
  pulseSpeed: number; pulseAmplitude: number;
}> = {
  calmness:     { color:"#1a6cf5",lightColor:"#6aa3ff",darkColor:"#0a3080",shape:"sphere",    coreScale:1.0, particleSpread:1.0, connectionDensity:0.3, gravityY:0,    tiltX:0,    pulseSpeed:1.5, pulseAmplitude:0.05 },
  joy:          { color:"#f5c518",lightColor:"#ffe680",darkColor:"#a07800",shape:"scattered",  coreScale:1.3, particleSpread:1.3, connectionDensity:0.8, gravityY:0.3,  tiltX:0,    pulseSpeed:3.0, pulseAmplitude:0.15 },
  happiness:    { color:"#f5c518",lightColor:"#ffe680",darkColor:"#a07800",shape:"scattered",  coreScale:1.2, particleSpread:1.2, connectionDensity:0.7, gravityY:0.2,  tiltX:0,    pulseSpeed:2.5, pulseAmplitude:0.12 },
  excitement:   { color:"#ff6b00",lightColor:"#ffa060",darkColor:"#8a3000",shape:"scattered",  coreScale:1.4, particleSpread:1.5, connectionDensity:0.9, gravityY:0,    tiltX:0,    pulseSpeed:6.0, pulseAmplitude:0.2  },
  curiosity:    { color:"#00d4d4",lightColor:"#80ffff",darkColor:"#007070",shape:"sphere",     coreScale:1.1, particleSpread:1.0, connectionDensity:0.5, gravityY:0,    tiltX:0.3,  pulseSpeed:2.0, pulseAmplitude:0.08 },
  interest:     { color:"#00d4d4",lightColor:"#80ffff",darkColor:"#007070",shape:"sphere",     coreScale:1.0, particleSpread:1.0, connectionDensity:0.4, gravityY:0,    tiltX:0.2,  pulseSpeed:2.0, pulseAmplitude:0.07 },
  boredom:      { color:"#4a5568",lightColor:"#8090a8",darkColor:"#202830",shape:"compressed", coreScale:0.7, particleSpread:0.8, connectionDensity:0.1, gravityY:-0.4, tiltX:0,    pulseSpeed:0.5, pulseAmplitude:0.03 },
  sadness:      { color:"#553c9a",lightColor:"#9070e0",darkColor:"#2a1a50",shape:"teardrop",   coreScale:0.75,particleSpread:0.85,connectionDensity:0.1, gravityY:-0.6, tiltX:0,    pulseSpeed:0.8, pulseAmplitude:0.04 },
  loneliness:   { color:"#2c5282",lightColor:"#6090c0",darkColor:"#102040",shape:"contracted", coreScale:0.6, particleSpread:0.7, connectionDensity:0.05,gravityY:-0.3, tiltX:0,    pulseSpeed:0.6, pulseAmplitude:0.03 },
  anger:        { color:"#c53030",lightColor:"#ff6060",darkColor:"#600000",shape:"compressed", coreScale:1.3, particleSpread:0.9, connectionDensity:0.2, gravityY:0,    tiltX:0,    pulseSpeed:8.0, pulseAmplitude:0.25 },
  frustration:  { color:"#e53e3e",lightColor:"#ff8080",darkColor:"#701010",shape:"compressed", coreScale:1.1, particleSpread:0.9, connectionDensity:0.15,gravityY:0,    tiltX:0,    pulseSpeed:5.0, pulseAmplitude:0.2  },
  fear:         { color:"#44337a",lightColor:"#8060c0",darkColor:"#201040",shape:"contracted", coreScale:0.5, particleSpread:0.6, connectionDensity:0.1, gravityY:0,    tiltX:0,    pulseSpeed:7.0, pulseAmplitude:0.08 },
  anxiety:      { color:"#44337a",lightColor:"#8060c0",darkColor:"#201040",shape:"contracted", coreScale:0.6, particleSpread:0.65,connectionDensity:0.1, gravityY:0,    tiltX:0,    pulseSpeed:6.0, pulseAmplitude:0.07 },
  surprise:     { color:"#d53f8c",lightColor:"#ff80cc",darkColor:"#700040",shape:"scattered",  coreScale:1.5, particleSpread:1.6, connectionDensity:0.3, gravityY:0,    tiltX:0,    pulseSpeed:10.0,pulseAmplitude:0.3  },
  trust:        { color:"#38a169",lightColor:"#70e0a0",darkColor:"#185030",shape:"sphere",     coreScale:1.0, particleSpread:1.0, connectionDensity:0.5, gravityY:0,    tiltX:0,    pulseSpeed:1.5, pulseAmplitude:0.05 },
  anticipation: { color:"#d69e2e",lightColor:"#ffd060",darkColor:"#705000",shape:"sphere",     coreScale:1.1, particleSpread:1.0, connectionDensity:0.4, gravityY:0.1,  tiltX:0.25, pulseSpeed:2.5, pulseAmplitude:0.1  },
  love:         { color:"#ed64a6",lightColor:"#ffaadd",darkColor:"#803060",shape:"double",     coreScale:1.2, particleSpread:1.1, connectionDensity:0.9, gravityY:0.1,  tiltX:0,    pulseSpeed:2.0, pulseAmplitude:0.1  },
  affection:    { color:"#ed64a6",lightColor:"#ffaadd",darkColor:"#803060",shape:"double",     coreScale:1.1, particleSpread:1.0, connectionDensity:0.7, gravityY:0.1,  tiltX:0,    pulseSpeed:1.8, pulseAmplitude:0.08 },
  adoration:    { color:"#ed64a6",lightColor:"#ffaadd",darkColor:"#803060",shape:"double",     coreScale:1.3, particleSpread:1.2, connectionDensity:0.8, gravityY:0.15, tiltX:0,    pulseSpeed:2.2, pulseAmplitude:0.12 },
  pride:        { color:"#6b46c1",lightColor:"#b080ff",darkColor:"#301870",shape:"elongated",  coreScale:1.2, particleSpread:1.1, connectionDensity:0.5, gravityY:0.5,  tiltX:0,    pulseSpeed:1.5, pulseAmplitude:0.06 },
  confidence:   { color:"#ecc94b",lightColor:"#ffe880",darkColor:"#806800",shape:"sphere",     coreScale:1.3, particleSpread:1.15,connectionDensity:0.6, gravityY:0.3,  tiltX:0,    pulseSpeed:1.8, pulseAmplitude:0.07 },
  triumph:      { color:"#ecc94b",lightColor:"#ffe880",darkColor:"#806800",shape:"elongated",  coreScale:1.4, particleSpread:1.2, connectionDensity:0.7, gravityY:0.6,  tiltX:0,    pulseSpeed:2.5, pulseAmplitude:0.1  },
  contempt:     { color:"#4a5568",lightColor:"#8090a8",darkColor:"#202830",shape:"compressed", coreScale:0.8, particleSpread:0.85,connectionDensity:0.05,gravityY:-0.1, tiltX:0,    pulseSpeed:1.0, pulseAmplitude:0.04 },
  shame:        { color:"#b7791f",lightColor:"#e0a040",darkColor:"#5a3500",shape:"contracted", coreScale:0.65,particleSpread:0.75,connectionDensity:0.1, gravityY:-0.4, tiltX:-0.2, pulseSpeed:0.8, pulseAmplitude:0.03 },
  guilt:        { color:"#2d3748",lightColor:"#607090",darkColor:"#101820",shape:"teardrop",   coreScale:0.6, particleSpread:0.7, connectionDensity:0.05,gravityY:-0.5, tiltX:0,    pulseSpeed:0.6, pulseAmplitude:0.03 },
  envy:         { color:"#68d391",lightColor:"#a0ffc0",darkColor:"#206030",shape:"scattered",  coreScale:0.9, particleSpread:1.1, connectionDensity:0.2, gravityY:0,    tiltX:0.15, pulseSpeed:2.0, pulseAmplitude:0.1  },
  disgust:      { color:"#2f855a",lightColor:"#60c080",darkColor:"#103020",shape:"compressed", coreScale:0.8, particleSpread:0.85,connectionDensity:0.1, gravityY:-0.2, tiltX:-0.1, pulseSpeed:1.5, pulseAmplitude:0.06 },
  awe:          { color:"#4299e1",lightColor:"#90d0ff",darkColor:"#183870",shape:"scattered",  coreScale:1.5, particleSpread:1.5, connectionDensity:0.4, gravityY:0.2,  tiltX:0,    pulseSpeed:1.0, pulseAmplitude:0.2  },
  relief:       { color:"#81e6d9",lightColor:"#c0fff8",darkColor:"#306860",shape:"sphere",     coreScale:1.0, particleSpread:1.0, connectionDensity:0.3, gravityY:0,    tiltX:0,    pulseSpeed:1.2, pulseAmplitude:0.06 },
  nostalgia:    { color:"#d4a574",lightColor:"#f0cc90",darkColor:"#705030",shape:"spiral",     coreScale:0.9, particleSpread:0.95,connectionDensity:0.3, gravityY:0,    tiltX:0,    pulseSpeed:0.8, pulseAmplitude:0.05 },
  hope:         { color:"#f6e05e",lightColor:"#fff080",darkColor:"#806800",shape:"elongated",  coreScale:1.1, particleSpread:1.05,connectionDensity:0.4, gravityY:0.4,  tiltX:0,    pulseSpeed:1.5, pulseAmplitude:0.08 },
  confusion:    { color:"#9f7aea",lightColor:"#d0a0ff",darkColor:"#402870",shape:"scattered",  coreScale:0.9, particleSpread:1.1, connectionDensity:0.2, gravityY:0,    tiltX:0,    pulseSpeed:4.0, pulseAmplitude:0.15 },
  contentment:  { color:"#68d391",lightColor:"#a0ffc0",darkColor:"#206030",shape:"sphere",     coreScale:1.0, particleSpread:1.0, connectionDensity:0.35,gravityY:0,    tiltX:0,    pulseSpeed:1.2, pulseAmplitude:0.05 },
  sympathy:     { color:"#38a169",lightColor:"#70e0a0",darkColor:"#185030",shape:"sphere",     coreScale:1.0, particleSpread:1.0, connectionDensity:0.5, gravityY:0,    tiltX:0.1,  pulseSpeed:1.5, pulseAmplitude:0.06 },
  // Phase 56 compound emotion states
  logical:      { color:"#4299e1",lightColor:"#90d0ff",darkColor:"#183870",shape:"cube",       coreScale:1.0, particleSpread:1.0, connectionDensity:0.7, gravityY:0,    tiltX:0,    pulseSpeed:0.8, pulseAmplitude:0.03 },
  analyzing:    { color:"#00d4d4",lightColor:"#80ffff",darkColor:"#007070",shape:"prism",      coreScale:1.1, particleSpread:1.0, connectionDensity:0.6, gravityY:0,    tiltX:0.5,  pulseSpeed:1.2, pulseAmplitude:0.05 },
  neutral:      { color:"#a0aec0",lightColor:"#d0d8e8",darkColor:"#404858",shape:"cylinder",   coreScale:1.0, particleSpread:1.0, connectionDensity:0.3, gravityY:0,    tiltX:0,    pulseSpeed:1.0, pulseAmplitude:0.04 },
  bored2:       { color:"#4a5568",lightColor:"#8090a8",darkColor:"#202830",shape:"infinity",   coreScale:0.8, particleSpread:0.9, connectionDensity:0.1, gravityY:0,    tiltX:0,    pulseSpeed:0.4, pulseAmplitude:0.02 },
  thinking_deep:{ color:"#553c9a",lightColor:"#9070e0",darkColor:"#2a1a50",shape:"double_helix",coreScale:1.0,particleSpread:1.1, connectionDensity:0.5, gravityY:0,    tiltX:0,    pulseSpeed:1.5, pulseAmplitude:0.06 },
  realization:  { color:"#f5c518",lightColor:"#ffe680",darkColor:"#a07800",shape:"burst",      coreScale:1.5, particleSpread:1.8, connectionDensity:0.3, gravityY:0,    tiltX:0,    pulseSpeed:5.0, pulseAmplitude:0.25 },
  scared:       { color:"#44337a",lightColor:"#8060c0",darkColor:"#201040",shape:"contracted_tremor",coreScale:0.5,particleSpread:0.6,connectionDensity:0.1,gravityY:0,tiltX:0,    pulseSpeed:9.0, pulseAmplitude:0.08 },
  proud:        { color:"#6b46c1",lightColor:"#b080ff",darkColor:"#301870",shape:"rising",     coreScale:1.3, particleSpread:1.2, connectionDensity:0.5, gravityY:0.7,  tiltX:0,    pulseSpeed:1.5, pulseAmplitude:0.07 },
};

function getCfg(emotion: string) {
  const key = emotion.toLowerCase().replace(/[^a-z]/g,"");
  return EMOTION_CONFIG[key] || EMOTION_CONFIG["calmness"];
}

function createGlowTex(color: string): THREE.Texture {
  const c = document.createElement("canvas");
  c.width=128; c.height=128;
  const ctx = c.getContext("2d")!;
  const col = new THREE.Color(color);
  const g = ctx.createRadialGradient(64,64,0,64,64,64);
  g.addColorStop(0,`rgba(${Math.round(col.r*255)},${Math.round(col.g*255)},${Math.round(col.b*255)},1)`);
  g.addColorStop(0.4,`rgba(${Math.round(col.r*255)},${Math.round(col.g*255)},${Math.round(col.b*255)},0.4)`);
  g.addColorStop(1,"rgba(0,0,0,0)");
  ctx.fillStyle=g; ctx.fillRect(0,0,128,128);
  return new THREE.CanvasTexture(c);
}

// State-overlay colors. We blend the emotion color toward these by an
// override-strength factor so the orb still reads as "Ava in mood X" but
// also clearly signals what she's doing right now.
const STATE_TINT = {
  thinking: new THREE.Color("#7a5dfc"),  // electric blue/purple
  listening: new THREE.Color("#3ee68f"), // calm green
  speaking: new THREE.Color("#ffb060"),  // warm amber
  offline: new THREE.Color("#404858"),
};

function OrbCanvasInner({ emotion, state, size = 320, shapeOverride, amplitude = 0, energy = 0.5 }: OrbProps) {
  const mountRef = useRef<HTMLDivElement>(null);
  const disposeRef = useRef<()=>void>(()=>{});

  // Live refs — update on every render so the animation loop reads the latest
  // value without remounting the whole Three.js scene.
  const stateRef = useRef<OrbState>(state);
  const amplitudeRef = useRef<number>(amplitude);
  const emotionRef = useRef<string>(emotion);
  const shapeOverrideRef = useRef<string | undefined>(shapeOverride);
  const energyRef = useRef<number>(energy);
  stateRef.current = state;
  amplitudeRef.current = amplitude;
  emotionRef.current = emotion;
  shapeOverrideRef.current = shapeOverride;
  energyRef.current = energy;

  useEffect(() => {
    if (!mountRef.current) return;
    disposeRef.current();
    const container = mountRef.current;
    const cfgInit = { ...getCfg(emotion), ...(shapeOverride ? { shape: shapeOverride } : {}) };

    const renderer = new THREE.WebGLRenderer({ antialias:true, alpha:true });
    renderer.setSize(size,size);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio,2));
    renderer.setClearColor(0x000000,0);
    container.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(70,1,0.01,100);
    camera.position.z = 2.8;

    // rootGroup holds all orb sub-groups so we can apply breathing scale +
    // gentle drift in one place without affecting per-frame morph maths.
    const rootGroup = new THREE.Group();
    scene.add(rootGroup);
    const innerGroup = new THREE.Group();
    const outerGroup = new THREE.Group();
    const streamGroup = new THREE.Group();
    rootGroup.add(innerGroup,outerGroup,streamGroup);

    // Core
    const coreGeo = new THREE.SphereGeometry(0.15,32,32);
    const coreMat = new THREE.MeshBasicMaterial({ color:new THREE.Color(cfgInit.lightColor), transparent:true, opacity:0.95, blending:THREE.AdditiveBlending, depthWrite:false });
    const core = new THREE.Mesh(coreGeo,coreMat);
    innerGroup.add(core);

    const igGeo = new THREE.SphereGeometry(0.3,16,16);
    const igMat = new THREE.MeshBasicMaterial({ color:new THREE.Color(cfgInit.color), transparent:true, opacity:0.3, blending:THREE.AdditiveBlending, depthWrite:false });
    const innerGlow = new THREE.Mesh(igGeo,igMat);
    innerGroup.add(innerGlow);

    // Streams
    const streamPhases: number[] = [];
    const streams: THREE.Line[] = [];
    for(let i=0;i<16;i++){
      const pts: THREE.Vector3[] = [];
      const cp = [
        new THREE.Vector3(0,0,0),
        new THREE.Vector3((Math.random()-.5)*1.2,(Math.random()-.5)*1.2,(Math.random()-.5)*1.2),
        new THREE.Vector3((Math.random()-.5)*1.4,(Math.random()-.5)*1.4,(Math.random()-.5)*1.4),
        new THREE.Vector3((Math.random()-.5)*1.0,(Math.random()-.5)*1.0,(Math.random()-.5)*1.0),
        new THREE.Vector3(0,0,0),
      ];
      const curve = new THREE.CatmullRomCurve3(cp);
      for(let j=0;j<=60;j++) pts.push(curve.getPoint(j/60));
      const geo = new THREE.BufferGeometry().setFromPoints(pts);
      const mat = new THREE.LineBasicMaterial({ color:new THREE.Color(i<8?cfgInit.lightColor:cfgInit.color), transparent:true, opacity:0.4+Math.random()*0.4, blending:THREE.AdditiveBlending, depthWrite:false });
      const line = new THREE.Line(geo,mat);
      line.rotation.set(Math.random()*Math.PI*2,Math.random()*Math.PI*2,Math.random()*Math.PI*2);
      streamGroup.add(line); streams.push(line); streamPhases.push(Math.random()*Math.PI*2);
    }

    // Particles
    const N = 1500;
    const pos = new Float32Array(N*3);
    const orig = new Float32Array(N*3);
    const vel = new Float32Array(N*3);
    const pcol = new Float32Array(N*3);
    const baseC = new THREE.Color(cfgInit.color);
    const lightC = new THREE.Color(cfgInit.lightColor);
    const darkC = new THREE.Color(cfgInit.darkColor);

    for(let i=0;i<N;i++){
      const tier = Math.random();
      const r = tier<0.25 ? 0.05+Math.random()*0.35 : tier<0.65 ? 0.35+Math.random()*0.35 : 0.7+Math.random()*0.3;
      const theta = Math.random()*Math.PI*2;
      const phi = Math.acos(2*Math.random()-1);
      const x=r*Math.sin(phi)*Math.cos(theta), y=r*Math.sin(phi)*Math.sin(theta), z=r*Math.cos(phi);
      pos[i*3]=x; pos[i*3+1]=y; pos[i*3+2]=z;
      orig[i*3]=x; orig[i*3+1]=y; orig[i*3+2]=z;
      vel[i*3]=(Math.random()-.5)*0.001; vel[i*3+1]=(Math.random()-.5)*0.001; vel[i*3+2]=(Math.random()-.5)*0.001;
      const c = tier<0.25?lightC:tier<0.65?baseC:darkC;
      pcol[i*3]=c.r; pcol[i*3+1]=c.g; pcol[i*3+2]=c.b;
    }

    const pGeo = new THREE.BufferGeometry();
    pGeo.setAttribute("position",new THREE.BufferAttribute(pos,3));
    pGeo.setAttribute("color",new THREE.BufferAttribute(pcol,3));
    const pMat = new THREE.PointsMaterial({ size:0.025, vertexColors:true, transparent:true, opacity:0.85, blending:THREE.AdditiveBlending, depthWrite:false, sizeAttenuation:true });
    innerGroup.add(new THREE.Points(pGeo,pMat));

    // Shell
    const shellGeo = new THREE.SphereGeometry(1.0,16,12);
    const shellMat = new THREE.MeshBasicMaterial({ color:new THREE.Color(cfgInit.darkColor), wireframe:true, transparent:true, opacity:0.08, blending:THREE.AdditiveBlending, depthWrite:false });
    outerGroup.add(new THREE.Mesh(shellGeo,shellMat));

    // Halo
    const haloTex = createGlowTex(cfgInit.color);
    const haloMat = new THREE.SpriteMaterial({ map:haloTex, transparent:true, opacity:0.2, blending:THREE.AdditiveBlending, depthWrite:false });
    const halo = new THREE.Sprite(haloMat);
    halo.scale.set(3.5,3.5,1);
    rootGroup.add(halo);

    const pLight = new THREE.PointLight(new THREE.Color(cfgInit.color),2.0,5);
    rootGroup.add(pLight);

    const clock = new THREE.Clock();
    let fid = 0;

    // Reusable color scratch — avoid allocating per frame.
    const _coreScratch = new THREE.Color();
    const _glowScratch = new THREE.Color();
    const _lightScratch = new THREE.Color();

    function morph(t: number, currentState: OrbState, currentAmp: number) {
      const c = getCfg(emotionRef.current);
      const sp = c.particleSpread, gy = c.gravityY, tx = c.tiltX;
      const shape = shapeOverrideRef.current || c.shape;
      const pa = pGeo.attributes.position as THREE.BufferAttribute;

      // Per-state amplitude/scale envelopes — read live each frame.
      const speakingScale = currentState === "speaking" ? (1 + currentAmp * 0.35) : 1;
      const listeningInBreath = currentState === "listening" ? (0.92 + Math.sin(t * 1.3) * 0.04) : 1;
      const thinkingScale = currentState === "thinking" || currentState === "deep" ? (0.96 + Math.sin(t * 6) * 0.04) : 1;

      for(let i=0;i<N;i++){
        const ox=orig[i*3], oy=orig[i*3+1], oz=orig[i*3+2];
        const dist=Math.sqrt(ox*ox+oy*oy+oz*oz);
        let mx=ox*sp, my=oy*sp, mz=oz*sp;
        if(shape==="teardrop"){ my-=Math.max(0,-oy)*0.4; my+=gy*dist*0.5; }
        else if(shape==="elongated"){ my*=1.4; my+=gy*0.3; }
        else if(shape==="compressed"){ my*=0.7; }
        else if(shape==="contracted"){ mx*=0.6; my*=0.6; mz*=0.6; }
        else if(shape==="scattered"){ const f=1+Math.sin(t*0.5+dist*3)*0.15; mx*=f; my*=f; mz*=f; }
        else if(shape==="double"){ if(oy>0){mx+=0.15;my+=0.1;}else{mx-=0.15;my-=0.05;} }
        else if(shape==="spiral"){ const a=t*0.3+dist*2; const nx=mx*Math.cos(a)-mz*Math.sin(a); mz=mx*Math.sin(a)+mz*Math.cos(a); mx=nx; }
        else if(shape==="pointer"){
          if(oy>0){ my*=2.2; mx*=Math.max(0.1, 1.0-oy*1.2); mz*=Math.max(0.1, 1.0-oy*1.2); }
          else{ mx*=0.5; my*=0.4; mz*=0.5; }
        }
        else if(shape==="cube"){
          mx = Math.sign(mx)*(Math.abs(mx)<0.5?Math.abs(mx):Math.abs(mx)*0.9+0.1*Math.sign(mx));
          my = Math.sign(my)*(Math.abs(my)<0.5?Math.abs(my):Math.abs(my)*0.9+0.1*Math.sign(my));
          mz = Math.sign(mz)*(Math.abs(mz)<0.5?Math.abs(mz):Math.abs(mz)*0.9+0.1*Math.sign(mz));
        }
        else if(shape==="prism"){
          const ang = Math.floor(Math.atan2(ox,oz)/(Math.PI*2/3))*Math.PI*2/3;
          const r2 = Math.sqrt(ox*ox+oz*oz); mx=r2*Math.sin(ang+t*0.5)*sp; mz=r2*Math.cos(ang+t*0.5)*sp;
        }
        else if(shape==="cylinder"){
          const r3 = Math.sqrt(ox*ox+oz*oz); mx=r3*Math.cos(Math.atan2(oz,ox))*sp; mz=r3*Math.sin(Math.atan2(oz,ox))*sp;
        }
        else if(shape==="infinity"){
          const u = Math.atan2(oy,ox); mx=sp*Math.cos(u)/(1+Math.sin(u)*Math.sin(u)); my=sp*Math.sin(u)*Math.cos(u)/(1+Math.sin(u)*Math.sin(u)); mz*=0.3;
        }
        else if(shape==="double_helix"){
          const strand = i%2===0?1:-1; const ang2=t*0.5+dist*4+strand*Math.PI; mx=0.5*Math.cos(ang2)*sp; mz=0.5*Math.sin(ang2)*sp;
        }
        else if(shape==="burst"){
          const phase = (Math.sin(t*1.5)*0.5+0.5); const scale = 1+phase*1.5; mx*=scale; my*=scale; mz*=scale;
        }
        else if(shape==="contracted_tremor"){
          mx*=0.4; my*=0.4; mz*=0.4;
          mx+=Math.sin(t*15+i*0.3)*0.05; my+=Math.cos(t*17+i*0.5)*0.05;
        }
        else if(shape==="rising"){
          my*=1.6; my+=gy*0.5; mx*=0.7; mz*=0.7;
        }
        my+=gy*0.2;
        mz+=tx*oy*0.3;
        mx+=vel[i*3]*30; my+=vel[i*3+1]*30; mz+=vel[i*3+2]*30;

        // ── Voice-state overlays ────────────────────────────────────────────
        if(currentState==="speaking"){
          // Amplitude-driven outward burst wave per-particle
          const wave = Math.sin(t * (4 + currentAmp * 8) + dist * 6) * currentAmp * 0.35;
          const wScale = 1 + wave;
          mx *= wScale * speakingScale;
          my *= wScale * speakingScale;
          mz *= wScale * speakingScale;
        } else if(currentState==="listening"){
          // Particles drift inward toward center, gentle breathing scale.
          const inward = 0.85 + Math.sin(t * 1.5 + dist * 4) * 0.06;
          mx *= inward * listeningInBreath;
          my *= inward * listeningInBreath;
          mz *= inward * listeningInBreath;
        } else if(currentState==="thinking" || currentState==="deep"){
          // Faster orbital motion + tight rapid pulse
          const fast = 1 + Math.sin(t * 8 + dist * 5) * 0.04;
          mx *= fast * thinkingScale;
          my *= fast * thinkingScale;
          mz *= fast * thinkingScale;
        }

        pa.setXYZ(i,mx,my,mz);
      }
      pa.needsUpdate=true;
    }

    function spd(s: OrbState) {
      return ({thinking:2.5,deep:5.0,speaking:1.8,bored:0.3,excited:7.0,offline:0.1,idle:1.0,listening:0.8} as Record<string, number>)[s] || 1.0;
    }

    function animate(){
      fid=requestAnimationFrame(animate);
      const t=clock.getElapsedTime();
      const liveState = stateRef.current;
      const liveAmp = amplitudeRef.current;
      const liveEmotion = emotionRef.current;
      const liveEnergy = Math.max(0, Math.min(1, energyRef.current));
      const c=getCfg(liveEmotion);
      const s=spd(liveState);
      const r=s*0.001;

      // ── Breathing (always-on) ─────────────────────────────────────────────
      // Period shrinks with energy (0 → 3.5s, 1 → 2.0s).
      const breathPeriod = 3.5 - liveEnergy * 1.5;
      const breath = 1 + Math.sin((t / breathPeriod) * Math.PI * 2) * 0.03;

      // ── Drift (always-on) ─────────────────────────────────────────────────
      // Two superimposed sines on each axis so the motion never repeats cleanly.
      // Amplitude is in scene units (camera at z=2.8); these translate to ~6-12
      // pixels at the canvas size, matching the user's spec of ~8/6 px.
      const driftScale = 0.012;  // tuned so the orb wanders within the frame
      const dx = (Math.sin(t * 0.30) * 8 + Math.sin(t * 0.70) * 4) * driftScale;
      const dy = (Math.cos(t * 0.40) * 6 + Math.cos(t * 0.11) * 3) * driftScale;
      rootGroup.position.set(dx, dy, 0);
      rootGroup.scale.setScalar(breath);

      // Rotation rates — thinking/listening/speaking each rotate differently.
      let rotMul = 1.0;
      if (liveState === "thinking" || liveState === "deep") rotMul = 2.5;
      else if (liveState === "speaking") rotMul = 1.0 + liveAmp * 1.5;
      else if (liveState === "listening") rotMul = 0.55;
      innerGroup.rotation.y += r * rotMul;
      innerGroup.rotation.x += r * 0.4 * rotMul;
      outerGroup.rotation.y -= r * 0.7 * rotMul;
      outerGroup.rotation.z += r * 0.3 * rotMul;
      streamGroup.rotation.y += r * 1.2 * rotMul;
      streamGroup.rotation.x -= r * 0.5 * rotMul;

      // Pulse — thinking pulses fast (2Hz), speaking pulses with amplitude.
      let pulseSpeed = c.pulseSpeed;
      let pulseAmp = c.pulseAmplitude;
      if (liveState === "thinking" || liveState === "deep") {
        pulseSpeed = 12.5;  // fast 2Hz
        pulseAmp = 0.18;
      } else if (liveState === "speaking") {
        pulseSpeed = 6 + liveAmp * 6;
        pulseAmp = 0.06 + liveAmp * 0.30;
      } else if (liveState === "listening") {
        pulseSpeed = 1.0;  // slow breathing
        pulseAmp = 0.08;
      }
      const pulse = 1 + Math.sin(t * pulseSpeed) * pulseAmp;
      const stateScaleMul = liveState === "speaking" ? (1 + liveAmp * 0.25)
        : liveState === "listening" ? (0.95 + Math.sin(t * 1.3) * 0.04)
        : 1;
      core.scale.setScalar(pulse * c.coreScale * stateScaleMul);
      innerGlow.scale.setScalar(pulse * c.coreScale * 0.9 * stateScaleMul);
      pLight.intensity = 1.5 + Math.sin(t * pulseSpeed) * 0.5;

      // ── Color overlays per state ──────────────────────────────────────────
      // Blend the emotion's light/base color toward the state tint.
      const baseLight = new THREE.Color(c.lightColor);
      const baseBase = new THREE.Color(c.color);
      _coreScratch.copy(baseLight);
      _glowScratch.copy(baseBase);
      _lightScratch.copy(baseBase);

      if (liveState === "thinking" || liveState === "deep") {
        _coreScratch.lerp(STATE_TINT.thinking, 0.55);
        _glowScratch.lerp(STATE_TINT.thinking, 0.45);
        _lightScratch.lerp(STATE_TINT.thinking, 0.45);
      } else if (liveState === "speaking") {
        // Color temperature shifts warmer with amplitude.
        const warmFactor = Math.min(0.6, 0.20 + liveAmp * 0.6);
        _coreScratch.lerp(STATE_TINT.speaking, warmFactor);
        _glowScratch.lerp(STATE_TINT.speaking, warmFactor * 0.7);
        _lightScratch.lerp(STATE_TINT.speaking, warmFactor * 0.6);
      } else if (liveState === "listening") {
        _coreScratch.lerp(STATE_TINT.listening, 0.30);
        _glowScratch.lerp(STATE_TINT.listening, 0.25);
        _lightScratch.lerp(STATE_TINT.listening, 0.25);
      } else if (liveState === "offline") {
        _coreScratch.lerp(STATE_TINT.offline, 0.6);
        _glowScratch.lerp(STATE_TINT.offline, 0.6);
        _lightScratch.lerp(STATE_TINT.offline, 0.6);
      }

      coreMat.color.copy(_coreScratch);
      igMat.color.copy(_glowScratch);
      pLight.color.copy(_lightScratch);

      morph(t, liveState, liveAmp);

      for(let i=0;i<N;i++){
        vel[i*3]+=(Math.random()-.5)*0.00002; vel[i*3+1]+=(Math.random()-.5)*0.00002; vel[i*3+2]+=(Math.random()-.5)*0.00002;
        vel[i*3]*=0.99; vel[i*3+1]*=0.99; vel[i*3+2]*=0.99;
      }
      streams.forEach((l,i)=>{
        const mat=l.material as THREE.LineBasicMaterial;
        mat.opacity=Math.sin(t*s*2+streamPhases[i])>0.7?0.9:0.2+Math.sin(t*s+streamPhases[i])*0.2;
        l.rotation.y+=r*0.5*Math.sin(streamPhases[i]);
      });
      const haloAmpBoost = liveState === "speaking" ? liveAmp * 0.5 : 0;
      halo.scale.set(3.5+Math.sin(t*0.7)*0.3 + haloAmpBoost, 3.5+Math.sin(t*0.7)*0.3 + haloAmpBoost, 1);
      haloMat.opacity = liveState === "offline"
        ? 0.06
        : 0.15 + Math.sin(t*0.5)*0.05 + (liveState === "speaking" ? liveAmp * 0.15 : 0);
      if(liveState==="offline"){ coreMat.opacity=Math.max(0.20,coreMat.opacity-0.001); pMat.opacity=Math.max(0.30,pMat.opacity-0.0005); }
      else { coreMat.opacity = 0.95; pMat.opacity = 0.85; }
      if(liveEmotion==="confusion") innerGroup.rotation.z+=Math.sin(t*3)*0.005;
      renderer.render(scene,camera);
    }
    animate();

    disposeRef.current=()=>{
      cancelAnimationFrame(fid);
      renderer.dispose();
      [coreGeo,igGeo,shellGeo,pGeo].forEach(g=>g.dispose());
      [coreMat,igMat,shellMat,pMat,haloMat].forEach(m=>m.dispose());
      streams.forEach(l=>{ l.geometry.dispose(); (l.material as THREE.Material).dispose(); });
      haloTex.dispose();
      if(container.contains(renderer.domElement)) container.removeChild(renderer.domElement);
    };

    return () => disposeRef.current();
    // Mount per emotion/size — state and amplitude are read via refs so they
    // update live without remounting the scene.
  }, [emotion, size]);

  return (
    <div ref={mountRef} style={{ width:size, height:size, display:"flex", alignItems:"center", justifyContent:"center", background:"transparent", overflow:"visible", flexShrink:0 }} />
  );
}

// React.memo: bail out only on micro-changes. Allow re-render on state OR
// amplitude change so the inner component re-runs and refreshes its refs;
// the useEffect deps (`[emotion, size]`) ensure the Three.js scene only
// rebuilds on emotion/size changes — state and amplitude updates feed the
// animation loop via refs without remounting.
const OrbCanvas = memo(OrbCanvasInner, (prev, next) => (
  prev.emotion === next.emotion &&
  prev.emotionColor === next.emotionColor &&
  prev.state === next.state &&
  (prev.size ?? 320) === (next.size ?? 320) &&
  prev.shapeOverride === next.shapeOverride &&
  Math.abs((prev.amplitude ?? 0) - (next.amplitude ?? 0)) < 0.03 &&
  Math.abs((prev.energy ?? 0.5) - (next.energy ?? 0.5)) < 0.05
));

export default OrbCanvas;
