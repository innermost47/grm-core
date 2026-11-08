import { Network } from "./grm.js";

const RHO_STEEL = 7850.0;
const E_STEEL = 2.0e11;
const K_FLESH = 2.0e3;
const FINGER_CONTACT = 0.012;
const Y_REF = 0.003;
const GAMMA_AIR = 1.4;
const R_GAS = 8.314462618;
const M_AIR = 0.028965;
const T_AIR = 293.15;
const NU_WOOD = 0.3;
const BETA_MODAL = 0.5;
const BRACING = 4.0;
const BRIDGE_VOLUME = 3.2e-5;
const RHO_BRIDGE = 850.0;
const BRIDGE_SHARE = 0.2;
const PLATE_RATIOS = [
  21.26 / 10.21,
  34.88 / 10.21,
  39.77 / 10.21,
  51.04 / 10.21,
  60.82 / 10.21,
];

function solveStringNetwork(f1Target, coreFraction = 1.0) {
  const nodes = {
    L: { guess: 0.65 },
    Leff: { guess: 0.65 },
    mu: { guess: 1e-3 },
    T: { guess: 70.0 },
    c: { guess: 200.0 },
    f1: { guess: f1Target },
    d: { guess: 5e-4 },
    B: { guess: 1e-4 },
    Zs: { guess: 0.5 },
  };

  const relations = [
    {
      name: "wave speed",
      terms: { c: 2, mu: 1, T: -1 },
      rhs: 0.0,
      sigma: 1e-9,
    },
    {
      name: "fundamental",
      terms: { Leff: 1, f1: 1, c: -1 },
      rhs: -Math.log10(2.0),
      sigma: 1e-9,
    },
    {
      name: "steel core",
      terms: { d: 2, mu: -1 },
      rhs: Math.log10(
        (4.0 * coreFraction * coreFraction) / (Math.PI * RHO_STEEL),
      ),
      sigma: 1e-9,
    },
    {
      name: "stiffness",
      terms: { B: 1, d: -4, T: 1, Leff: 2 },
      rhs: Math.log10((Math.PI ** 3 * E_STEEL) / 64.0),
      sigma: 1e-9,
    },
    {
      name: "string impedance",
      terms: { Zs: 2, T: -1, mu: -1 },
      rhs: 0.0,
      sigma: 1e-9,
    },
  ];

  const net = new Network(nodes, relations);
  const measured = {
    f1: [f1Target, 1e-7],
    L: [0.648, 1e-4],
    mu: [0.0018, 0.02],
  };

  return net.solve(measured);
}

function solvePluckNetwork(mu, L, T, p = 0.22, force = 1.8) {
  const nodes = {
    mu: { guess: mu },
    L: { guess: L },
    Leff: { guess: L },
    T: { guess: T },
    p: { guess: p },
    x: { guess: p * L },
    xr: { guess: L * (1 - p) },
    ks: { guess: 600.0 },
    F: { guess: force },
    y0: { guess: 0.003 },
    w: { guess: 0.002 },
    mc: { guess: 1e-5 },
    kc: { guess: K_FLESH },
    tau: { guess: 1e-4 },
    fc: { guess: 2000.0 },
    Ec: { guess: 1e-4 },
  };

  const relations = [
    {
      name: "pluck point",
      terms: { x: 1, p: -1, Leff: -1 },
      rhs: 0.0,
      sigma: 1e-9,
    },
    {
      name: "other side",
      type: "sum",
      terms: { xr: 1, Leff: -1, x: 1 },
      K: 0.0,
      sigma: 1e-12,
    },
    {
      name: "string stiffness",
      terms: { ks: 1, T: -1, Leff: -1, x: 1, xr: 1 },
      rhs: 0.0,
      sigma: 1e-9,
    },
    {
      name: "release height",
      terms: { y0: 1, F: -1, ks: 1 },
      rhs: 0.0,
      sigma: 1e-9,
    },
    {
      name: "mass in contact",
      terms: { mc: 1, mu: -1, w: -1 },
      rhs: 0.0,
      sigma: 1e-9,
    },
    {
      name: "release time",
      terms: { tau: 1, mc: -0.5, kc: 0.5 },
      rhs: Math.log10(Math.PI),
      sigma: 1e-9,
    },
    {
      name: "brightness limit",
      terms: { fc: 1, tau: 1 },
      rhs: -Math.log10(2 * Math.PI),
      sigma: 1e-9,
    },
    {
      name: "click energy",
      terms: { Ec: 1, F: -2, kc: 1 },
      rhs: -Math.log10(2),
      sigma: 1e-9,
    },
  ];

  const net = new Network(nodes, relations);
  const measured = {
    mu: [mu, 0.004],
    L: [L, 3e-4],
    T: [T, 0.003],
    p: [p, 0.01],
    F: [force, 0.02],
    kc: [K_FLESH, 0.1],
    w: [FINGER_CONTACT, 0.04],
  };

  return net.solve(measured);
}

function solveBodyNetwork(size = 1.0, top_mm = 2.8, coupling = 0.35) {
  const k = coupling;
  const nodes = {
    Tair: { guess: T_AIR, fixed: true },
    cair: { guess: 340.0 },
    V: { guess: 0.02 },
    r: { guess: 0.05 },
    A: { guess: 0.008 },
    t: { guess: 0.003 },
    lneck: { guess: 0.09 },
    fH: { guess: 120.0 },
    a: { guess: 0.17 },
    h: { guess: 0.003 },
    E: { guess: 1e10 },
    rho: { guess: 450.0 },
    fT: { guess: 200.0 },
    f_lo: { guess: 100.0 },
    f_hi: { guess: 220.0 },
    frad: { guess: 300.0 },
    D: { guess: 20.0 },
    Zp: { guess: 40.0 },
    Mtop: { guess: 0.1 },
    Mm: { guess: 0.05 },
    Vb: { guess: 3e-5 },
    rhob: { guess: 850.0 },
    mb: { guess: 0.008 },
    fb: { guess: 800.0 },
  };

  for (let j = 0; j < PLATE_RATIOS.length; j++) {
    nodes[`f${j + 3}`] = { guess: 400.0 };
  }

  const relations = [
    {
      name: "speed of sound",
      terms: { cair: 2, Tair: -1 },
      rhs: Math.log10((GAMMA_AIR * R_GAS) / M_AIR),
      sigma: 1e-9,
    },
    {
      name: "sound hole area",
      terms: { A: 1, r: -2 },
      rhs: Math.log10(Math.PI),
      sigma: 1e-9,
    },
    {
      name: "neck of air",
      type: "sum",
      terms: { lneck: 1, t: -1, r: -1.7 },
      K: 0.0,
      sigma: 1e-9,
    },
    {
      name: "Helmholtz",
      terms: { fH: 1, cair: -1, A: -0.5, V: 0.5, lneck: 0.5 },
      rhs: -Math.log10(2 * Math.PI),
      sigma: 1e-9,
    },
    {
      name: "top plate",
      terms: { fT: 1, a: 2, h: -1, E: -0.5, rho: 0.5 },
      rhs: Math.log10(
        10.21 / (2 * Math.PI) / Math.sqrt(12 * (1 - NU_WOOD ** 2)),
      ),
      sigma: 1e-9,
    },
    {
      name: "radiation",
      terms: { frad: 1, cair: -1, a: 1 },
      rhs: -Math.log10(2 * Math.PI),
      sigma: 1e-9,
    },
    {
      name: "air / top, low",
      type: "fn",
      nodes: ["f_lo", "fH", "fT"],
      f: (v) =>
        Math.log10(v.f_lo) -
        Math.log10(
          Math.sqrt(
            Math.max(
              (v.fH ** 2 +
                v.fT ** 2 -
                Math.sqrt(
                  (v.fH ** 2 - v.fT ** 2) ** 2 +
                    4 * k * k * v.fH ** 2 * v.fT ** 2,
                )) /
                2,
              1e-12,
            ),
          ),
        ),
      sigma: 1e-9,
    },
    {
      name: "air / top, high",
      type: "fn",
      nodes: ["f_hi", "fH", "fT"],
      f: (v) =>
        Math.log10(v.f_hi) -
        Math.log10(
          Math.sqrt(
            Math.max(
              (v.fH ** 2 +
                v.fT ** 2 +
                Math.sqrt(
                  (v.fH ** 2 - v.fT ** 2) ** 2 +
                    4 * k * k * v.fH ** 2 * v.fT ** 2,
                )) /
                2,
              1e-12,
            ),
          ),
        ),
      sigma: 1e-9,
    },
    {
      name: "plate rigidity",
      terms: { D: 1, E: -1, h: -3 },
      rhs: Math.log10(BRACING / (12 * (1 - NU_WOOD ** 2))),
      sigma: 1e-9,
    },
    {
      name: "plate impedance",
      terms: { Zp: 1, D: -0.5, rho: -0.5, h: -0.5 },
      rhs: Math.log10(8.0),
      sigma: 1e-9,
    },
    {
      name: "top mass",
      terms: { Mtop: 1, rho: -1, h: -1, a: -2 },
      rhs: Math.log10(Math.PI),
      sigma: 1e-9,
    },
    {
      name: "modal mass",
      terms: { Mm: 1, Mtop: -1 },
      rhs: Math.log10(BETA_MODAL),
      sigma: 1e-9,
    },
    {
      name: "bridge mass",
      terms: { mb: 1, rhob: -1, Vb: -1 },
      rhs: Math.log10(BRIDGE_SHARE),
      sigma: 1e-9,
    },
    {
      name: "bridge corner",
      terms: { fb: 1, mb: 1, Zp: -1 },
      rhs: -Math.log10(2 * Math.PI),
      sigma: 1e-9,
    },
  ];

  for (let j = 0; j < PLATE_RATIOS.length; j++) {
    relations.push({
      name: `top mode ${j + 3}`,
      terms: { [`f${j + 3}`]: 1, fT: -1 },
      rhs: Math.log10(PLATE_RATIOS[j]),
      sigma: 1e-9,
    });
  }

  const net = new Network(nodes, relations);
  const measured = {
    V: [0.016 * size ** 3, 0.01],
    r: [0.05 * size, 0.01],
    t: [0.0028, 0.02],
    a: [0.17 * size, 0.01],
    h: [top_mm / 1000.0, 0.02],
    E: [1e10, 0.05],
    rho: [430.0, 0.02],
    Vb: [BRIDGE_VOLUME, 0.02],
    rhob: [RHO_BRIDGE, 0.02],
  };

  return net.solve(measured);
}

let cachedBody = null;
function getBodyModel() {
  if (!cachedBody) {
    cachedBody = solveBodyNetwork(1.15, 2.7, 0.35).values;
  }
  return cachedBody;
}

export class GRMSynth {
  constructor() {
    this.ctx = null;
    this.sampleRate = 44100;
    this.convolver = null;
    this.dryGain = null;
    this.wetGain = null;
    this.masterGain = null;
    this.isInitialized = false;
  }

  ensureContext() {
    if (!this.ctx) {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      this.ctx = new AudioCtx();
      this.sampleRate = this.ctx.sampleRate || 44100;
      this.buildAudioGraph();
    }
    if (this.ctx.state === "suspended") {
      this.ctx.resume();
    }
  }

  createEtherealSpaceIR(duration = 4.8, decay = 1.9) {
    const totalSamples = Math.floor(duration * this.sampleRate);
    const buffer = this.ctx.createBuffer(2, totalSamples, this.sampleRate);
    const left = buffer.getChannelData(0);
    const right = buffer.getChannelData(1);

    for (let i = 0; i < totalSamples; i++) {
      const t = i / this.sampleRate;
      const env = Math.exp(-decay * t);
      const damping = Math.exp(-1.4 * t);

      left[i] = (Math.random() * 2 - 1) * damping * env;
      right[i] = (Math.random() * 2 - 1) * damping * env;
    }
    return buffer;
  }

  buildAudioGraph() {
    if (this.isInitialized) return;

    this.masterGain = this.ctx.createGain();
    this.masterGain.gain.setValueAtTime(0.85, this.ctx.currentTime);

    this.dryGain = this.ctx.createGain();
    this.dryGain.gain.setValueAtTime(0.45, this.ctx.currentTime);

    this.wetGain = this.ctx.createGain();
    this.wetGain.gain.setValueAtTime(0.75, this.ctx.currentTime);

    this.convolver = this.ctx.createConvolver();
    this.convolver.buffer = this.createEtherealSpaceIR(4.8, 1.9);

    this.dryGain.connect(this.masterGain);
    this.convolver.connect(this.wetGain);
    this.wetGain.connect(this.masterGain);
    this.masterGain.connect(this.ctx.destination);

    this.isInitialized = true;
  }

  synthesizeGRMString(f1Target, pullValue, duration = 4.5) {
    const strRes = solveStringNetwork(f1Target).values;
    const f1 = strRes.f1;
    const B_base = strRes.B;
    const c = strRes.c;
    const Zs = strRes.Zs;
    const Leff = strRes.Leff;
    const mu = strRes.mu;
    const T = strRes.T;

    const atkRes = solvePluckNetwork(mu, Leff, T, 0.22, 1.6).values;
    const y0 = atkRes.y0;
    const tauRelease = atkRes.tau;

    const bv = getBodyModel();

    const pTension = Math.abs(pullValue || 0);
    const B = B_base * (1.0 + 3.0 * Math.min(pTension * pTension, 4.0));
    const baseDamping = Math.max(1.5, 3.8 / (1.0 + 0.3 * pTension));

    const totalSamples = Math.floor(duration * this.sampleRate);
    const buffer = this.ctx.createBuffer(2, totalSamples, this.sampleRate);
    const left = buffer.getChannelData(0);
    const right = buffer.getChannelData(1);

    const maxPartials = 28;
    const partials = [];
    const p = 0.22;

    for (let n = 1; n <= maxPartials; n++) {
      const fn = n * f1 * Math.sqrt(1.0 + B * n * n);
      if (fn >= 0.45 * this.sampleRate) break;

      const aPluck =
        (2.0 * Math.sin(n * Math.PI * p)) /
        (n * n * Math.PI * Math.PI * p * (1.0 - p));
      const amp = n * aPluck * Math.pow(n, -0.65);
      const sinc =
        tauRelease > 0
          ? Math.sin(Math.PI * fn * tauRelease) /
            (Math.PI * fn * tauRelease || 1)
          : 1.0;

      const w = 2 * Math.PI * fn;
      let Y_real = 0;
      const modes = [
        [bv.f_lo, 0.9, 16],
        [bv.f_hi, 1.0, 22],
      ];
      for (let m = 0; m < modes.length; m++) {
        const [fm, gain, q] = modes[m];
        const wm = 2 * Math.PI * fm;
        const denom = (wm * wm - w * w) ** 2 + ((w * wm) / q) ** 2;
        Y_real +=
          (w * ((w * wm) / q)) / ((bv.Mm / gain) * Math.max(denom, 1e-12));
      }
      const bridgeLoss = (c / Leff) * Zs * Math.max(Y_real, 0.0);
      const sigma =
        (1.0 + Math.pow(fn / 1600.0, 1.3)) / baseDamping + bridgeLoss * 0.15;

      const detuneL = 1.0 - 0.0006 * (n % 4);
      const detuneR = 1.0 + 0.0006 * (n % 4);

      partials.push({ fn, amp: amp * sinc, sigma, detuneL, detuneR });
    }

    const scaleForce = ((T * Math.PI) / Leff) * (y0 / Y_REF);
    const bloomSamples = Math.floor(0.035 * this.sampleRate);

    for (let i = 0; i < totalSamples; i++) {
      const t = i / this.sampleRate;
      let sL = 0;
      let sR = 0;

      for (let k = 0; k < partials.length; k++) {
        const prt = partials[k];
        const env = prt.amp * Math.exp(-prt.sigma * t);
        sL += env * Math.cos(2 * Math.PI * (prt.fn * prt.detuneL) * t);
        sR += env * Math.sin(2 * Math.PI * (prt.fn * prt.detuneR) * t);
      }

      let bloom = 1.0;
      if (i < bloomSamples) {
        bloom = 0.5 * (1.0 - Math.cos((Math.PI * i) / bloomSamples));
      }

      left[i] = sL * scaleForce * bloom;
      right[i] = sR * scaleForce * bloom;
    }

    const tailFade = Math.floor(0.3 * this.sampleRate);
    for (let i = 0; i < tailFade; i++) {
      const idx = totalSamples - 1 - i;
      const fade = Math.sin((i / tailFade) * (Math.PI / 2));
      left[idx] *= fade;
      right[idx] *= fade;
    }

    let peak = 0;
    for (let i = 0; i < totalSamples; i++) {
      const vL = Math.abs(left[i]);
      const vR = Math.abs(right[i]);
      if (vL > peak) peak = vL;
      if (vR > peak) peak = vR;
    }
    if (peak > 0) {
      const inv = 0.85 / peak;
      for (let i = 0; i < totalSamples; i++) {
        left[i] *= inv;
        right[i] *= inv;
      }
    }

    return buffer;
  }

  pluck(f1Target, pullValue, delay = 0, volume = 0.75) {
    this.ensureContext();
    const buf = this.synthesizeGRMString(f1Target, pullValue, 4.5);

    const src = this.ctx.createBufferSource();
    src.buffer = buf;

    const gain = this.ctx.createGain();
    gain.gain.setValueAtTime(volume, this.ctx.currentTime + delay);

    src.connect(gain);
    gain.connect(this.dryGain);
    gain.connect(this.convolver);

    src.start(this.ctx.currentTime + delay);
  }
}
