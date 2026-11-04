// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Anthony Charretier
//
// The picture of the universe (Three.js). It draws what the network says at a moment t:
//   temperature of the plasma and of the light (T = T0 / a, a from the Friedmann integral),
//   the moment light is freed, the first stars, the colour of stars (their surface temperature),
//   the Sun's life, the end of the stars, the black holes and their evaporation.
// The motion between those moments (particles gathering into galaxies, the camera) is drawing, not physics.

import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

const N_PARTICLES = 9000;
const N_GALAXIES = 32;
const N_BLACK_HOLES = 14;

// colour of a black body (display approximation: Tanner Helland's fit), T in kelvin
export function blackbody(T) {
  const t = Math.min(Math.max(T, 800), 40000) / 100;
  let r, g, b;
  if (t <= 66) {
    r = 255;
    g = 99.4708025861 * Math.log(t) - 161.1195681661;
    b = t <= 19 ? 0 : 138.5177312231 * Math.log(t - 10) - 305.0447927307;
  } else {
    r = 329.698727446 * (t - 60) ** -0.1332047592;
    g = 288.1221695283 * (t - 60) ** -0.0755148492;
    b = 255;
  }
  const c = (x) => Math.min(255, Math.max(0, x)) / 255;
  return new THREE.Color(c(r), c(g), c(b));
}

const smooth = (a, b, x) => {
  const t = Math.min(1, Math.max(0, (x - a) / (b - a)));
  return t * t * (3 - 2 * t);
};

const VERTEX = /* glsl */ `
  attribute vec3 seed;
  attribute vec3 home;
  attribute vec4 extra;          // x: star or gas, y: temperature factor, z: galaxy (0 = ours), w: phase
  attribute vec3 centre;         // centre of its galaxy
  attribute vec3 axis;           // the galaxy's axis of rotation
  uniform float uScale, uCrush, uCluster, uTime, uSize, uStarFrac, uAcoustic, uRecede, uPixel;
  uniform float uStarTemp, uGasHeat, uSpin, uShock;
  uniform float uLogT, uLogFirst, uLogEnd, uLogLife;
  uniform float uLogBlack, uEvap, uDecay, uMerge, uCook, uWhite;
  varying vec3 vColor;
  varying float vAlpha;
  vec3 blackbody(float T) {
    float t = clamp(T, 800.0, 40000.0) / 100.0;
    vec3 c;
    if (t <= 66.0) {
      c.r = 255.0;
      c.g = 99.4708 * log(t) - 161.1196;
      c.b = t <= 19.0 ? 0.0 : 138.5177 * log(t - 10.0) - 305.0448;
    } else {
      c.r = 329.6987 * pow(t - 60.0, -0.1332);
      c.g = 288.1222 * pow(t - 60.0, -0.0755);
      c.b = 255.0;
    }
    return clamp(c / 255.0, 0.0, 1.0);
  }
  void main() {
    // before galaxies: a uniform gas that expands, breathing with the sound of the plasma
    vec3 gas = seed * uScale * (1.0 + uAcoustic * sin(uTime * 2.2 + length(seed) * 9.0));
    // galaxies: bound, they keep their size while the space between them grows (uRecede)
    float ours = step(extra.z, 0.5);
    // a galaxy turns: flat rotation curve (speed the same at every radius, so the inside turns faster)
    vec3 rel = home - centre;
    float r = length(rel);
    float ang = uSpin * uTime / (0.5 + r);
    vec3 turned = rel * cos(ang) + cross(axis, rel) * sin(ang) + axis * dot(axis, rel) * (1.0 - cos(ang));
    vec3 pos = mix(gas, centre + turned, uCluster);
    // the elastics shaken when a constant moves (drawing: the network settling)
    pos += uShock * vec3(sin(extra.w * 91.0 + uTime * 9.0), sin(extra.w * 53.0 + uTime * 11.0), sin(extra.w * 27.0 + uTime * 7.0));
    pos += normalize(pos + 1e-5) * uRecede * (1.0 - ours) * length(home) * uCluster;
    // the galaxies evaporate: nine stars in ten gain energy and leave for ever, the others sink to the centre
    float luck = fract(extra.w * 7.31 + extra.y * 3.7);
    vec3 away = normalize(rel + 1e-4 * axis) * (5.0 + 45.0 * luck * luck);
    pos += (luck < 0.9 ? away : -turned * 0.97) * uEvap * uCluster;
    // the fall: the galaxies merge into one swarm, then everything falls into one point (Big Crunch)
    pos = mix(pos, turned * 1.4 + centre * 0.12, uMerge);
    pos *= 1.0 - 0.985 * uCrush;
    pos += uCrush * uCrush * 0.25 * vec3(sin(uTime * 37.0 + extra.w * 91.0), sin(uTime * 41.0 + extra.w * 53.0), sin(uTime * 43.0 + extra.w * 27.0));
    vec4 mv = modelViewMatrix * vec4(pos, 1.0);
    gl_Position = projectionMatrix * mv;
    // each star is born after the first ones and lives as long as its mass allows: hotter = heavier = shorter
    // (T ~ M^0.5, life ~ M^-2.5 ~ T^-5), from the network's life of a star like the Sun
    float lb = uLogFirst + extra.w * max(min(uLogEnd, uLogFirst + 2.0) - uLogFirst, 0.1);
    float ll = uLogLife - 5.0 * log(extra.y) / log(10.0);
    float lend = max(lb, ll) + log(1.0 + pow(10.0, -abs(lb - ll))) / log(10.0);
    bool alive = uLogT > lb && uLogT < lend;
    // cooked by the sky (the fall): the stars go out, the hottest last
    bool cooked = luck < uCook;
    bool star = extra.x < uStarFrac && alive && !cooked;
    // a dead star: a white dwarf that cools to a black dwarf (by the network's time), until protons decay
    bool remnant = extra.x < 0.55 && uLogT > lb && (uLogT >= lend || uLogT > uLogEnd) && !cooked && uLogT > uLogFirst;
    float cool = smoothstep(lend, uLogBlack, uLogT);
    float twinkle = 0.85 + 0.15 * sin(uTime * 3.0 + extra.w * 40.0);
    vec3 starColor = blackbody(uStarTemp * extra.y);
    vec3 gasColor = blackbody(uGasHeat);
    float far = 1.0 - smoothstep(0.0, 1.0, uRecede * 0.12) * (1.0 - ours);
    // cold gas stays faintly visible (drawn, not physics: it no longer glows); it is used up by the stars
    float glow = clamp((uGasHeat - 700.0) / 2500.0, 0.0, 1.0);
    float gasLeft = 1.0 - 0.75 * smoothstep(uLogEnd - 1.0, uLogEnd, uLogT) * (1.0 - glow);
    if (star) {
      vColor = starColor;
      vAlpha = 0.95 * twinkle;
    } else if (remnant && glow < 0.5) {
      // (a black dwarf no longer shines: it is drawn as a faint ghost so that its motion stays visible)
      vColor = mix(blackbody(mix(16000.0, 2500.0, cool)), vec3(0.3, 0.27, 0.42), cool);
      vAlpha = 0.75 - 0.45 * cool;
    } else {
      vColor = mix(vec3(0.35, 0.22, 0.2), gasColor, glow);
      // (in the fall the glowing swarm is thinned for the eye, so that its shape and its trembling stay visible)
      vAlpha = max(glow * 0.5, 0.08) * gasLeft * (1.0 - 0.6 * smoothstep(0.0, 0.4, uCrush));
    }
    vAlpha *= far * (1.0 - uDecay);
    // the last flash: everything white
    vColor = mix(vColor, vec3(1.0), uWhite);
    float size = star ? uSize * (0.8 + 0.9 * extra.y) : remnant ? uSize * 0.7 : uSize * 1.1;
    size *= 1.0 + 0.6 * uCrush;
    gl_PointSize = size * uPixel * (60.0 / -mv.z);
  }
`;
const FRAGMENT = /* glsl */ `
  varying vec3 vColor;
  varying float vAlpha;
  void main() {
    vec2 d = gl_PointCoord - 0.5;
    float r = length(d);
    float a = smoothstep(0.5, 0.0, r);
    gl_FragColor = vec4(vColor * a, a * vAlpha);
  }
`;

export class Universe3D {
  constructor(canvas) {
    const renderer = new THREE.WebGLRenderer({ canvas, antialias: false, alpha: false, powerPreference: "high-performance" });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    this.renderer = renderer;
    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(60, 1, 0.1, 5000);
    this.camera.position.set(0, 30, 34);
    this.controls = new OrbitControls(this.camera, canvas);
    this.controls.enableDamping = true;
    this.controls.enablePan = false;
    this.controls.minDistance = 4;
    this.controls.maxDistance = 400;
    this.controls.autoRotate = true;
    this.controls.autoRotateSpeed = 0.25;
    // the camera follows the story, unless the spectator takes it (then it waits 6 s before following again)
    this.targetDistance = 40;
    this.userUntil = 0;
    this.controls.addEventListener("start", () => { this.userUntil = Infinity; });
    this.controls.addEventListener("end", () => { this.userUntil = performance.now() + 6000; });
    this.clock = new THREE.Clock();
    this.buildParticles();
    this.buildBackground();
    this.buildSunAndHoles();
    this.resize();
    window.addEventListener("resize", () => this.resize());
  }

  buildParticles() {
    const seed = new Float32Array(N_PARTICLES * 3), home = new Float32Array(N_PARTICLES * 3), extra = new Float32Array(N_PARTICLES * 4);
    let s = 12345;
    const rand = () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
    const centres = [[0, 0, 0]];
    while (centres.length < N_GALAXIES) {
      const v = [rand() * 2 - 1, rand() * 2 - 1, rand() * 2 - 1];
      const r = Math.hypot(...v);
      if (r > 1 || r < 0.25) continue;
      centres.push(v.map((x) => x * 34));
    }
    const tilts = centres.map((_, k) => (k === 0 ? new THREE.Euler(0, 0, 0) : new THREE.Euler(rand() * Math.PI, rand() * Math.PI, 0)));
    for (let i = 0; i < N_PARTICLES; i++) {
      // a uniform ball
      let v;
      do v = [rand() * 2 - 1, rand() * 2 - 1, rand() * 2 - 1]; while (Math.hypot(...v) > 1);
      seed.set(v, i * 3);
      // its galaxy (ours, at the centre, is the largest) and its place on a spiral arm
      const gi = i < N_PARTICLES * 0.22 ? 0 : 1 + Math.floor(rand() * (N_GALAXIES - 1));
      const size = gi === 0 ? 3.2 : 1.1 + rand() * 0.8;
      const rr = size * Math.sqrt(rand());
      const arm = Math.floor(rand() * 2);
      const th = Math.log(1 + rr * 3) * 2.4 + arm * Math.PI + (rand() - 0.5) * 0.7;
      const p = new THREE.Vector3(rr * Math.cos(th), (rand() - 0.5) * 0.18 * size * (1 - rr / size + 0.2), rr * Math.sin(th));
      p.applyEuler(tilts[gi]);
      home.set([centres[gi][0] + p.x, centres[gi][1] + p.y, centres[gi][2] + p.z], i * 3);
      // star or gas, its temperature (spread around the network's star), its galaxy, a phase
      const tf = 2 ** ((rand() - 0.62) * 2.4);
      extra.set([rand(), tf, gi, rand()], i * 4);
    }
    const centre = new Float32Array(N_PARTICLES * 3), axis = new Float32Array(N_PARTICLES * 3);
    for (let i = 0; i < N_PARTICLES; i++) {
      const gi = extra[i * 4 + 2];
      centre.set(centres[gi], i * 3);
      const a = new THREE.Vector3(0, 1, 0).applyEuler(tilts[gi]);
      axis.set([a.x, a.y, a.z], i * 3);
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(new Float32Array(N_PARTICLES * 3), 3));
    geo.setAttribute("centre", new THREE.BufferAttribute(centre, 3));
    geo.setAttribute("axis", new THREE.BufferAttribute(axis, 3));
    geo.setAttribute("seed", new THREE.BufferAttribute(seed, 3));
    geo.setAttribute("home", new THREE.BufferAttribute(home, 3));
    geo.setAttribute("extra", new THREE.BufferAttribute(extra, 4));
    geo.boundingSphere = new THREE.Sphere(new THREE.Vector3(), 1e6);
    this.uniforms = {
      uScale: { value: 1 }, uCrush: { value: 0 }, uCluster: { value: 0 }, uTime: { value: 0 }, uSize: { value: 1.2 }, uStarFrac: { value: 0 },
      uAcoustic: { value: 0 }, uRecede: { value: 0 }, uPixel: { value: this.renderer.getPixelRatio() },
      uStarTemp: { value: 5772 }, uGasHeat: { value: 30000 }, uSpin: { value: 0.18 }, uShock: { value: 0 },
      uLogT: { value: 0 }, uLogFirst: { value: 15.7 }, uLogEnd: { value: 21.5 }, uLogLife: { value: 17.5 },
      uLogBlack: { value: 22.5 }, uEvap: { value: 0 }, uDecay: { value: 0 }, uMerge: { value: 0 }, uCook: { value: 0 }, uWhite: { value: 0 },
    };
    this.shock = 0;
    const mat = new THREE.ShaderMaterial({ vertexShader: VERTEX, fragmentShader: FRAGMENT, uniforms: this.uniforms,
      transparent: true, depthWrite: false, blending: THREE.AdditiveBlending });
    this.points = new THREE.Points(geo, mat);
    this.scene.add(this.points);
    this.centres = centres;
  }

  buildBackground() {
    // the light freed at recombination: a shell all around, cooling with the expansion
    const geo = new THREE.SphereGeometry(900, 48, 24);
    this.cmbUniforms = { uColor: { value: new THREE.Color(1, 0.5, 0.2) }, uAlpha: { value: 0 } };
    const mat = new THREE.ShaderMaterial({
      side: THREE.BackSide, transparent: true, depthWrite: false, uniforms: this.cmbUniforms,
      vertexShader: `varying vec3 vP; void main(){ vP = normalize(position); gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0);} `,
      fragmentShader: `
        uniform vec3 uColor; uniform float uAlpha; varying vec3 vP;
        float h(vec3 p){ return fract(sin(dot(p, vec3(12.9898,78.233,37.719))) * 43758.5453); }
        float n(vec3 p){ vec3 i = floor(p), f = fract(p); f = f*f*(3.0-2.0*f);
          return mix(mix(mix(h(i),h(i+vec3(1,0,0)),f.x),mix(h(i+vec3(0,1,0)),h(i+vec3(1,1,0)),f.x),f.y),
                     mix(mix(h(i+vec3(0,0,1)),h(i+vec3(1,0,1)),f.x),mix(h(i+vec3(0,1,1)),h(i+vec3(1,1,1)),f.x),f.y),f.z); }
        void main(){ float v = 0.55*n(vP*6.0) + 0.3*n(vP*13.0) + 0.15*n(vP*29.0);
          gl_FragColor = vec4(uColor * (0.5 + v), uAlpha * (0.6 + 0.4*v)); }`,
    });
    this.cmb = new THREE.Mesh(geo, mat);
    this.scene.add(this.cmb);
    this.scene.background = new THREE.Color(0, 0, 0);
  }

  buildSunAndHoles() {
    const sprite = (size) => {
      const c = document.createElement("canvas");
      c.width = c.height = 64;
      const g = c.getContext("2d");
      const grad = g.createRadialGradient(32, 32, 0, 32, 32, 32);
      grad.addColorStop(0, "rgba(255,255,255,1)");
      grad.addColorStop(0.25, "rgba(255,255,255,0.7)");
      grad.addColorStop(1, "rgba(255,255,255,0)");
      g.fillStyle = grad;
      g.fillRect(0, 0, 64, 64);
      const m = new THREE.SpriteMaterial({ map: new THREE.CanvasTexture(c), blending: THREE.AdditiveBlending, depthWrite: false, transparent: true });
      const s = new THREE.Sprite(m);
      s.scale.set(size, size, 1);
      return s;
    };
    this.sun = sprite(0.7);
    this.sun.position.set(2.1, 0.05, 0.4);
    this.scene.add(this.sun);
    // black holes: a dark heart in a violet ring, then the last flash of their evaporation
    this.holes = [];
    let s = 99;
    const rand = () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
    // a black hole: a dark heart in a thin glowing ring (the light bent around it)
    const c = document.createElement("canvas");
    c.width = c.height = 128;
    const g = c.getContext("2d");
    const grad = g.createRadialGradient(64, 64, 0, 64, 64, 64);
    grad.addColorStop(0, "rgba(255,255,255,0)");
    grad.addColorStop(0.3, "rgba(255,255,255,0)");
    grad.addColorStop(0.38, "rgba(255,255,255,1)");
    grad.addColorStop(0.5, "rgba(255,255,255,0.35)");
    grad.addColorStop(1, "rgba(255,255,255,0)");
    g.fillStyle = grad;
    g.fillRect(0, 0, 128, 128);
    const ringMap = new THREE.CanvasTexture(c);
    this.glowMap = this.sun.material.map;
    this.ringMap = ringMap;
    for (let k = 0; k < N_BLACK_HOLES; k++) {
      const ring = sprite(1.6);
      ring.material.map = ringMap;
      ring.material.color = new THREE.Color(0.55, 0.3, 1.0);
      const big = k < 3;
      ring.position.set((rand() - 0.5) * 6, (rand() - 0.5) * 2, (rand() - 0.5) * 6);
      if (big) ring.position.set((rand() - 0.5) * 1.5, 0, (rand() - 0.5) * 1.5);
      // when it evaporates, in decades from the network's time: stellar holes weigh 5 to 100 suns (t ~ M³: 4 decades);
      // the central ones 10⁶ to 10¹⁰ suns, the largest last (it is the network's t for 10¹⁰ stars)
      const offset = big ? [0, -5, -10][k] : (rand() - 0.5) * 4;
      ring.userData = { big, offset, home: ring.position.clone(), gone: false };
      this.scene.add(ring);
      this.holes.push(ring);
    }
  }

  resize() {
    const w = window.innerWidth, h = window.innerHeight;
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
  }

  // back to the Big Bang (a new film)
  reset() {
    this.endAt = null;
    this.lastLt = null;
    for (const h of this.holes) h.userData.gone = false;
  }

  // the state of the universe at the moment m ({ t, left, falling, final }) from the network's values v and u = ln a
  update(m, v, u) {
    const t = m.t, falling = m.falling;
    const T = v.T0 * Math.exp(-u);                          // temperature of the light
    const lt = Math.log10(t);
    const un = this.uniforms;
    const flashes = [];
    // size of what we see (compressed for the eye), and the plasma's breath before recombination
    un.uScale.value = 34 * Math.exp(0.11 * Math.min(u, 0));
    // a closed universe falling back heats up again: above the recombination temperature it is plasma once more
    const Trec = v.T0 * (1 + v.zrec);
    const plasma = t < v.trec || (falling && T > Trec);
    const lT = Math.log10(T);
    // the fall, threshold by threshold (each one a node of the network): galaxies merge, stars are cooked,
    // atoms then nuclei are broken, everything falls into one point
    un.uMerge.value = falling ? smooth(Math.log10(v.Tmerge) - 0.5, Math.log10(v.Tmerge) + 0.3, lT) : 0;
    un.uCook.value = falling ? smooth(Math.log10(v.Tcook) - 0.2, Math.log10(v.Tcook) + 0.4, lT) : 0;
    un.uCrush.value = falling ? Math.max(0.55 * smooth(Math.log10(Trec) - 0.3, Math.log10(v.Tnuc) + 0.5, lT), m.final) : 0;
    // the long night (open universe): black dwarfs, galaxies evaporate, protons decay (if they do)
    un.uLogBlack.value = Math.log10(v.tblack);
    un.uEvap.value = falling ? 0 : smooth(Math.log10(v.tevap) - 1, Math.log10(v.tevap) + 0.6, lt);
    un.uDecay.value = falling ? 0 : smooth(Math.log10(v.tproton) - 0.6, Math.log10(v.tproton) + 0.6, lt);
    // the last flash of the Crunch, then the dark (3 s of real time once the end is reached)
    let white = falling ? smooth(0.55, 1, m.final) : 0;
    let afterglow = null;
    if (falling && m.final >= 1) {
      this.endAt ??= performance.now();
      afterglow = Math.max(0, 1 - (performance.now() - this.endAt) / 3000);
      white = afterglow;
      un.uDecay.value = 1;
    } else this.endAt = null;
    un.uWhite.value = white;
    un.uAcoustic.value = plasma ? 0.012 : 0;
    // gas glows with the light's temperature until it is too cold to see
    un.uGasHeat.value = Math.min(T, 40000);
    // stars: from the first ones to the end of the stars
    const lf = Math.log10(v.tfirst), le = Math.log10(v.tstarsend);
    un.uStarFrac.value = 0.55 * smooth(lf - 0.3, lf + 0.6, lt) * (1 - smooth(le - 1.2, le, lt));
    un.uLogT.value = lt;
    un.uLogFirst.value = lf;
    un.uLogEnd.value = le;
    un.uLogLife.value = Math.log10(v.tstar);
    // galaxies turn at a rate set by their density, i.e. by the density of matter when they formed:
    // G rho ~ H0^2 Omega_m ~ omega_m (G cancels); relative to ours (the speed itself is chosen for the eye)
    un.uSpin.value = 0.18 * Math.sqrt((v.ombh2 + v.omch2) / (0.02237 + 0.12));
    un.uStarTemp.value = v.Tsun * (1 - 0.45 * smooth(le - 2, le, lt));          // the last stars are red dwarfs
    // galaxies gather after the first stars; in the far future the others recede beyond our horizon
    un.uCluster.value = smooth(lf, Math.log10(v.tfirst * 12), lt);
    un.uRecede.value = Math.max(0, u) * 1.4;
    // the freed light: a glowing shell that reddens and fades as it cools
    const born = smooth(Math.log10(v.trec) - 0.15, Math.log10(v.trec) + 0.05, lt);
    this.cmbUniforms.uColor.value = blackbody(T);
    this.cmbUniforms.uAlpha.value = (falling ? 1 - smooth(Trec * 0.4, Trec, T) : born) * smooth(500, 3000, T) * 0.75;
    // before: the whole sky is the plasma
    const glow = falling ? smooth(Trec * 0.4, Trec * 3, T) : plasma ? smooth(Math.log10(v.trec) + 0.1, Math.log10(v.trec) - 0.6, lt) : 0;
    const sky = glow > 0 || plasma ? blackbody(T).multiplyScalar(0.38 * glow + 0.08 * Number(plasma)) : new THREE.Color(0, 0, 0);
    // falling, the sky brightens past the stars' surface: it ends blinding
    // (kept below full brightness so that what falls stays visible against it)
    if (falling) sky.lerp(blackbody(T), 0.3 * un.uCook.value * smooth(Math.log10(Trec), Math.log10(Trec) + 2, lT)).multiplyScalar(0.5);
    this.cmbUniforms.uAlpha.value *= 1 - m.final;
    this.scene.background = afterglow !== null ? new THREE.Color(afterglow, afterglow, afterglow) : sky.lerp(new THREE.Color(1, 1, 1), white);
    // the Sun: born, on the main sequence, a red giant, then a white dwarf that fades
    const sunOn = t >= v.tsunborn;
    const giant = smooth(v.tredgiant * 0.98, v.tredgiant, t) * (1 - smooth(v.tredgiant * 1.02, v.tredgiant * 1.06, t));
    const dwarf = t > v.tredgiant * 1.05;
    this.sun.visible = sunOn && un.uStarFrac.value > 0.01 && un.uCook.value < 0.3 && un.uMerge.value < 0.5;
    this.sun.material.color = dwarf ? blackbody(9000 * Math.max(0.2, 1 - (lt - Math.log10(v.tredgiant)) / 4)) : blackbody(giant > 0.1 ? 3500 : v.Tsun);
    const sz = (giant > 0.1 ? 0.7 + 2.3 * giant : dwarf ? 0.3 : 0.7);
    this.sun.scale.set(sz, sz, 1);
    this.sun.material.opacity = dwarf ? Math.max(0, 1 - (lt - Math.log10(v.tredgiant)) / 4) : 1;
    // black holes: shown once the stars thin out; they evaporate (Hawking) one by one, each in a last flash.
    // Falling, they are drawn together and merge into one.
    const forward = this.lastLt !== null && lt > this.lastLt && lt - this.lastLt < 3;
    for (const h of this.holes) {
      const d = h.userData;
      const end = Math.log10(d.big ? v.tsmbh : v.tbh) + d.offset;
      const show = falling ? un.uMerge.value > 0.2 && m.final < 0.9 : lt > le - 0.5;
      if (!falling && lt >= end && !d.gone) {
        d.gone = true;
        if (forward) flashes.push(d.big);
      }
      if (lt < end) d.gone = false;
      const flash = !falling && lt >= end ? 1 - (lt - end) / (d.big ? 0.5 : 0.25) : 0;
      h.visible = show && (lt < end || flash > 0 || falling);
      h.position.copy(d.home).multiplyScalar(falling ? 1 - 0.98 * Math.max(un.uMerge.value * 0.6, un.uCrush.value) : 1);
      h.material.color = flash > 0 ? new THREE.Color(1, 0.95, 0.85) : new THREE.Color(0.6, 0.4, 1.0);
      h.material.map = flash > 0 ? this.glowMap : this.ringMap;
      const grow = falling ? 1 + 2.5 * un.uCrush.value : 1;
      const sz2 = (d.big ? 0.9 : 0.4) * grow * (flash > 0 ? 1 + (d.big ? 12 : 5) * flash : 1);
      h.scale.set(sz2, sz2, 1);
      h.material.opacity = flash > 0 ? flash : 0.8 * (falling ? smooth(0.2, 0.5, un.uMerge.value) : smooth(le - 0.5, le, lt));
    }
    this.lastLt = lt;
    // where the camera wants to be: around everything at first, then close to our galaxy; out wide while the
    // galaxies evaporate, back to the black holes after; falling, closer and closer to the point
    const near = smooth(lf, lf + 1.0, lt);
    let target = (1 - near) * Math.max(6, un.uScale.value * 1.5) + near * (lt > le ? 11 : 15);
    if (!falling) target += 30 * un.uEvap.value * (1 - smooth(Math.log10(v.tevap) + 1, Math.log10(v.tevap) + 3, lt));
    else target = 15 - 9 * Math.max(un.uMerge.value * 0.3, un.uCrush.value);
    this.targetDistance = target;
    return { T, u, plasma, flashes, logT: Math.log10(v.T0) - u / Math.LN10 };
  }

  // a constant moved: the network shakes, as much as the values moved (in dex)
  kick(amount) { this.shock = Math.min(1.2, this.shock + amount); }

  render() {
    this.uniforms.uTime.value = this.clock.getElapsedTime();
    this.shock *= 0.95;
    this.uniforms.uShock.value = this.shock;
    // the Sun turns with our galaxy (its axis is the y axis)
    const ang = (this.uniforms.uSpin.value * this.uniforms.uTime.value) / (0.5 + Math.hypot(2.1, 0.4));
    this.sun.position.set(2.1 * Math.cos(ang) + 0.4 * Math.sin(ang), 0.05, -2.1 * Math.sin(ang) + 0.4 * Math.cos(ang));
    if (performance.now() > this.userUntil) {
      const d = this.camera.position.length();
      const k = 1 + (this.targetDistance / d - 1) * 0.03;
      this.camera.position.multiplyScalar(k);
    }
    this.controls.update();
    this.renderer.render(this.scene, this.camera);
  }

  // where the Sun is on the screen (for its label), or null
  sunOnScreen() {
    if (!this.sun.visible) return null;
    const p = this.sun.position.clone().project(this.camera);
    if (p.z > 1) return null;
    return { x: (p.x * 0.5 + 0.5) * window.innerWidth, y: (-p.y * 0.5 + 0.5) * window.innerHeight };
  }
}
