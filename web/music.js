// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Anthony Charretier
//
// The music of the universe page. Every pitch and every colour of the sound comes from the network:
//   - the cosmic chord: the acoustic peaks of the early universe (their places ℓ_n and the weight the baryons give
//     to the odd ones), heard 50 octaves higher. It rings while the universe is a plasma, then stays as a memory;
//   - a distant flute in the Lydian mode on F: open pipes cut in our air; their pitch follows the speed of sound
//     in the air of the Earth (its temperature, the weight of its molecules), and the air between the flute and
//     the listener takes the highs away (ISO 9613-1, at the Earth's temperature). It plays while the Earth exists.
// What is a choice and not physics: the Lydian mode, the transposition, the melody (a slow random walk).

const FLUTE_DISTANCE = 250;          // m, the flute is far away
const DAMPING_SCALE = 4.65;          // diffusion damping of the peaks, ℓ_D ≈ 4.65 ℓ_A (hypothesis, Silk damping)

// atmospheric absorption, dB per metre (ISO 9613-1), T in kelvin, relative humidity in %
export function airAbsorption(f, T, rh = 50, pa = 101.325) {
  const pr = 101.325, T0 = 293.15, T01 = 273.16;
  const psat = 10 ** (-6.8346 * (T01 / T) ** 1.261 + 4.6151);
  const h = (rh * psat) / (pa / pr);
  const frO = (pa / pr) * (24 + (4.04e4 * h * (0.02 + h)) / (0.391 + h));
  const frN = (pa / pr) * (T / T0) ** -0.5 * (9 + 280 * h * Math.exp(-4.17 * ((T / T0) ** (-1 / 3) - 1)));
  return 8.686 * f * f * (1.84e-11 * (pa / pr) ** -1 * (T / T0) ** 0.5 + (T / T0) ** -2.5 *
    ((0.01275 * Math.exp(-2239.1 / T)) / (frO + (f * f) / frO) + (0.1068 * Math.exp(-3352 / T)) / (frN + (f * f) / frN)));
}

// a little seeded random, so that the same universe plays the same tune
function rng(seed) {
  let s = seed >>> 0;
  return () => {
    s = (s + 0x6d2b79f5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function reverbImpulse(ctx, seconds, brightDecay) {
  const n = Math.floor(seconds * ctx.sampleRate);
  const buf = ctx.createBuffer(2, n, ctx.sampleRate);
  for (let ch = 0; ch < 2; ch++) {
    const d = buf.getChannelData(ch);
    const r = rng(17 + ch);
    let low = 0;
    for (let i = 0; i < n; i++) {
      const t = i / ctx.sampleRate;
      // the highs die first: a one-pole low-pass that closes as the tail goes on
      const k = Math.min(0.95, 0.15 + t * brightDecay);
      low = low * k + (r() * 2 - 1) * (1 - k);
      d[i] = low * Math.exp((-6.91 * t) / seconds) * (i < 0.004 * ctx.sampleRate ? 0 : 1);
    }
  }
  return buf;
}

export class Music {
  constructor() {
    this.ctx = null;
    this.values = null;
    this.flute = { on: false, timer: null };
    this.random = rng(7);
    this.degree = 0;
  }

  // must be called from a user gesture (mobile browsers)
  async start() {
    if (this.ctx) {
      await this.ctx.resume();
      return;
    }
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    this.ctx = ctx;
    this.master = ctx.createGain();
    this.master.gain.value = 0;
    this.master.connect(ctx.destination);
    this.master.gain.setTargetAtTime(0.8, ctx.currentTime, 1.5);
    const reverb = ctx.createConvolver();
    reverb.buffer = reverbImpulse(ctx, 7.0, 0.35);
    this.reverb = reverb;
    this.wet = ctx.createGain();
    this.wet.gain.value = 0.9;
    reverb.connect(this.wet).connect(this.master);
    // the cosmic chord
    this.padBus = ctx.createGain();
    this.padBus.gain.value = 0;
    this.padTone = ctx.createBiquadFilter();
    this.padTone.type = "lowpass";
    this.padTone.frequency.value = 2400;
    this.padBus.connect(this.padTone);
    this.padTone.connect(this.master);
    this.padTone.connect(reverb);
    this.partials = [];
    for (let n = 1; n <= 6; n++) {
      const g = ctx.createGain();
      g.gain.value = 0;
      g.connect(this.padBus);
      const pair = [-1.6, 1.6].map((cents) => {
        const o = ctx.createOscillator();
        o.type = "sine";
        o.detune.value = cents;
        o.frequency.value = 87.3 * n;
        o.connect(g);
        o.start();
        return o;
      });
      // each peak breathes slowly on its own
      const lfo = ctx.createOscillator();
      lfo.frequency.value = 0.03 + 0.017 * n;
      const depth = ctx.createGain();
      depth.gain.value = 0;
      lfo.connect(depth).connect(g.gain);
      lfo.start();
      this.partials.push({ g, pair, depth });
    }
    // the flute's way to the listener: little direct sound, much room (far beyond the critical distance)
    this.fluteDry = ctx.createGain();
    this.fluteDry.gain.value = 0.25;
    this.fluteSend = ctx.createGain();
    this.fluteSend.gain.value = 1.0;
    this.fluteDry.connect(this.master);
    this.fluteSend.connect(reverb);
    this.noise = (() => {
      const b = ctx.createBuffer(1, ctx.sampleRate * 2, ctx.sampleRate);
      const d = b.getChannelData(0);
      const r = rng(3);
      for (let i = 0; i < d.length; i++) d[i] = r() * 2 - 1;
      return b;
    })();
    if (this.values) this.setUniverse(this.values);
  }

  // the network's values: pitches and colours follow them (smoothly, as an elastic would)
  setUniverse(v) {
    this.values = v;
    if (!this.ctx) return;
    const t = this.ctx.currentTime;
    const odd = (1 + 6 * v.Rrec) / 3, even = 1 / 3;
    this.partials.forEach((p, k) => {
      const n = k + 1;
      const f = v[`pad${n}`];
      p.pair.forEach((o) => o.frequency.setTargetAtTime(f, t, 0.8));
      const weight = (n % 2 ? odd : even) * Math.exp(-(((n - 0.267) / DAMPING_SCALE) ** 2)) / Math.sqrt(n);
      p.weight = weight;
      p.g.gain.setTargetAtTime(0.11 * weight, t, 1.0);
      p.depth.gain.setTargetAtTime(0.05 * weight, t, 1.0);
    });
  }

  // where the universe is: plasma (the chord sings), after (a memory), the Earth (the flute), the end (silence)
  // rise: the fall of a closed universe, in octaves (the chord is blueshifted like the light); final: the last moments
  setEra({ plasma, memory, earth, end, rise = 0, final = 0 }) {
    if (!this.ctx) return;
    const t = this.ctx.currentTime;
    const tension = Math.min(1, rise / 3);
    this.padBus.gain.setTargetAtTime(Math.max(plasma ? 0.9 : memory * 0.55, 0.5 + 0.7 * tension), t, 1.2);
    this.padTone.frequency.setTargetAtTime(plasma ? 3200 + 4000 * tension : 900 + 1300 * memory + 5000 * tension, t, 1.5);
    if (Math.abs(rise - (this.rise ?? 0)) > 0.005) {
      this.rise = rise;
      this.partials.forEach((p) => p.pair.forEach((o, k) => o.detune.setTargetAtTime((k ? 1.6 : -1.6) * (1 + 6 * tension) + 1200 * rise, t, 0.4)));
    }
    if (!this.muted && !this.silenced) this.master.gain.setTargetAtTime(end ? 0 : 0.8 + 0.3 * final, t, end ? (final > 0 ? 0.05 : 4) : 1.0);
    if (end && final > 0 && !this.silenced) {
      this.silenced = true;
      this.flash(true, 2.5);
    }
    if (!end) this.silenced = false;
    if (earth && !this.flute.on) this.startFlute();
    if (!earth && this.flute.on) this.stopFlute();
  }

  startFlute() {
    this.flute.on = true;
    const next = () => {
      if (!this.flute.on) return;
      const wait = this.playNote();
      this.flute.timer = setTimeout(next, wait * 1000);
    };
    this.flute.timer = setTimeout(next, 1500);
  }

  stopFlute() {
    this.flute.on = false;
    clearTimeout(this.flute.timer);
  }

  // one breath of the flute: a slow random walk on the Lydian degrees (the fourth, B over F, comes often)
  playNote() {
    const ctx = this.ctx, v = this.values;
    if (!ctx || !v) return 3;
    const r = this.random;
    const step = [-2, -1, -1, 1, 1, 2][Math.floor(r() * 6)];
    this.degree = Math.max(0, Math.min(10, this.degree + step));
    if (r() < 0.18) this.degree = 3;                               // the raised fourth
    const octave = this.degree >= 7 ? 2 : 1;
    const f = v[`flute${this.degree % 7}`] * octave;
    const dur = 2.5 + r() * 3.5, t0 = ctx.currentTime + 0.05;
    const Tair = v.Tearth;
    const out = ctx.createGain();
    out.gain.value = 0;
    out.connect(this.fluteDry);
    out.connect(this.fluteSend);
    // the voice of the flute: a few harmonics, each dimmed by the air on its way (ISO 9613-1)
    const harmonics = [1, 0.32, 0.12, 0.05];
    harmonics.forEach((a, k) => {
      const fk = f * (k + 1);
      if (fk > ctx.sampleRate * 0.45) return;
      const loss = 10 ** (-(airAbsorption(fk, Tair) * FLUTE_DISTANCE) / 20);
      const o = ctx.createOscillator();
      o.frequency.value = fk;
      const vib = ctx.createOscillator();
      vib.frequency.value = 4.6;
      const vg = ctx.createGain();
      vg.gain.setValueAtTime(0, t0);
      vg.gain.linearRampToValueAtTime(fk * 0.003, t0 + 1.2);
      vib.connect(vg).connect(o.frequency);
      const g = ctx.createGain();
      g.gain.value = a * loss;
      o.connect(g).connect(out);
      o.start(t0);
      vib.start(t0);
      o.stop(t0 + dur + 2.5);
      vib.stop(t0 + dur + 2.5);
    });
    // the breath: noise around the note
    const n = ctx.createBufferSource();
    n.buffer = this.noise;
    n.loop = true;
    const bp = ctx.createBiquadFilter();
    bp.type = "bandpass";
    bp.frequency.value = f * 2;
    bp.Q.value = 1.2;
    const ng = ctx.createGain();
    ng.gain.value = 0.05 * 10 ** (-(airAbsorption(f * 2, Tair) * FLUTE_DISTANCE) / 20);
    n.connect(bp).connect(ng).connect(out);
    n.start(t0);
    n.stop(t0 + dur + 2.5);
    out.gain.setValueAtTime(0, t0);
    out.gain.linearRampToValueAtTime(0.09, t0 + 0.7);
    out.gain.setTargetAtTime(0.07, t0 + 0.7, 1.0);
    out.gain.setTargetAtTime(0, t0 + dur, 0.6);
    return dur + 1 + r() * 3.5;
  }

  // a black hole's last flash (or the Crunch): a low strike that dies in the far room, pitched on the cosmic chord
  flash(big = false, strength = 1) {
    const ctx = this.ctx, v = this.values;
    if (!ctx || !v || this.muted) return;
    const t0 = ctx.currentTime + 0.02;
    const out = ctx.createGain();
    if (strength > 2) out.connect(ctx.destination);      // the Crunch: heard close, while everything else goes silent
    else {
      out.connect(this.fluteDry);
      out.connect(this.fluteSend);
    }
    const f = (big ? v.pad1 / 2 : v.pad3 ?? v.pad1 * 3) * (0.98 + 0.04 * this.random());
    const dur = big ? 7 : 3;
    const o = ctx.createOscillator();
    o.frequency.setValueAtTime(f * 2, t0);
    o.frequency.exponentialRampToValueAtTime(f, t0 + 0.4);
    const g = ctx.createGain();
    g.gain.setValueAtTime(0, t0);
    g.gain.linearRampToValueAtTime((big ? 0.35 : 0.12) * Math.min(strength, 1.6), t0 + 0.02);
    g.gain.setTargetAtTime(0, t0 + 0.05, dur / 4);
    o.connect(g).connect(out);
    o.start(t0);
    o.stop(t0 + dur);
    const n = ctx.createBufferSource();
    n.buffer = this.noise;
    const lp = ctx.createBiquadFilter();
    lp.type = "lowpass";
    lp.frequency.setValueAtTime(big ? 2500 : 4000, t0);
    lp.frequency.exponentialRampToValueAtTime(120, t0 + dur * 0.6);
    const ng = ctx.createGain();
    ng.gain.setValueAtTime((big ? 0.25 : 0.06) * Math.min(strength, 1.6), t0);
    ng.gain.setTargetAtTime(0, t0 + 0.03, dur / 5);
    n.connect(lp).connect(ng).connect(out);
    n.start(t0);
    n.stop(t0 + dur);
  }

  // the turnaround of a closed universe: one long strike, the chord starts to climb
  turn() { this.flash(true, 0.6); }

  mute(on) {
    this.muted = on;
    if (this.ctx) this.master.gain.setTargetAtTime(on ? 0 : 0.8, this.ctx.currentTime, 0.3);
  }
}
