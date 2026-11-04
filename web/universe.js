// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Anthony Charretier
//
// The universe as one GRM network: from the constants of the small to the stars, the history of the cosmos,
// the air of the Earth and the music. Every number the page shows or plays is a node of this network.
//
// Each relation says what kind of elastic it is:
//   "law"         established physics (with its source)
//   "hypothesis"  a scaling law or an approximation, with a prefactor set on our universe (said where)
//   "music"       an artistic choice (the Lydian mode, the transposition of the cosmic sound into hearing)
//
// Units: SI. Times in seconds, temperatures in kelvin, energies in joules.

import { Network } from "./grm.js";

// ------------------------------------------------------------------ constants of our universe
export const OURS = {
  alpha: 7.2973525693e-3,          // CODATA 2018
  me: 9.1093837015e-31,            // kg
  mp: 1.67262192369e-27,           // kg
  G: 6.6743e-11,                   // m^3 kg^-1 s^-2
  H0: 67.36,                       // km/s/Mpc   Planck 2018 (TT,TE,EE+lowE+lensing)
  ombh2: 0.02237,                  // Omega_b h^2 Planck 2018
  omch2: 0.12,                     // Omega_c h^2 Planck 2018
  Tcmb: 2.7255,                    // K, Fixsen 2009
};
const HBAR = 1.054571817e-34, C = 299792458, KB = 1.380649e-23, EV = 1.602176634e-19, NA = 6.02214076e23;
const MPC = 3.0856775814913673e22, YEAR = 3.15576e7, MSUN = 1.98847e30, ZETA3 = 1.2020569031595942;
const NEFF = 3.046, NU_FACTOR = 1 + NEFF * (7 / 8) * (4 / 11) ** (4 / 3);
const B_DEUTERON = 2.224566e6 * EV;          // binding energy of the deuteron (strong force: not varied here)
const LG = Math.log10;

export const PARAMS = [
  // id, multiplier or value, range, log slider
  { id: "alpha", kind: "times", min: 0.4, max: 2.5, log: true },
  { id: "G", kind: "times", min: 1e-3, max: 1e3, log: true },
  { id: "me", kind: "times", min: 0.1, max: 10, log: true },
  { id: "mp", kind: "times", min: 0.3, max: 3, log: true },
  { id: "H0", kind: "value", min: 20, max: 200, log: true },
  { id: "ombh2", kind: "value", min: 0.001, max: 2, log: true },
  { id: "omch2", kind: "value", min: 0.001, max: 5, log: true },
  { id: "Tcmb", kind: "value", min: 0.3, max: 300, log: true },
];
export const DEFAULTS = { alpha: 1, G: 1, me: 1, mp: 1, H0: OURS.H0, ombh2: OURS.ombh2, omch2: OURS.omch2, Tcmb: OURS.Tcmb };

// the Lydian mode on F, just intonation (fixed: it is the music, not the physics)
export const LYDIAN = [1, 9 / 8, 5 / 4, 45 / 32, 3 / 2, 5 / 3, 15 / 8];
const F4 = 349.228, F2 = F4 / 4;
const FLUTE_RADIUS = 0.0095;                 // m, bore of a flute (typical)
const END_CORRECTION = 0.61;                 // per open end, in radii (Levine & Schwinger 1948)

// ------------------------------------------------------------------ the expansion: Friedmann
// time since the Big Bang at scale factor a: t = int_0^a da / (a H(a)), H² = H0² (Ω_r a⁻⁴ + Ω_m a⁻³ + Ω_k a⁻² + Ω_Λ)
export function friedmannTime(a, H0si, Or, Om, OL, Ok = 0) {
  const H = (u) => H0si * Math.sqrt(Or * Math.exp(-4 * u) + Om * Math.exp(-3 * u) + Ok * Math.exp(-2 * u) + OL);
  const u0 = -30, u1 = Math.log(a);
  const t0 = Math.exp(2 * u0) / (2 * H0si * Math.sqrt(Or));        // radiation era, exact below a = e^-30
  if (u1 <= u0) return Math.exp(2 * u1) / (2 * H0si * Math.sqrt(Or));
  const n = 600, h = (u1 - u0) / n;
  let s = 1 / H(u0) + 1 / H(u1);
  for (let k = 1; k < n; k++) s += (k % 2 ? 4 : 2) / H(u0 + k * h);
  return t0 + (s * h) / 3;
}

// comoving sound horizon at a and comoving distance from a to today
// a closed universe stops growing where H = 0 (no dark energy, curvature Ω_k < 0)
export function turnaround(Or, Om, Ok) {
  const E2 = (a) => Or / a ** 4 + Om / a ** 3 + Ok / a ** 2;
  let lo = 1, hi = 2;
  while (E2(hi) > 0 && hi < 1e12) hi *= 2;
  for (let k = 0; k < 200; k++) {
    const mid = Math.sqrt(lo * hi);
    if (E2(mid) > 0) lo = mid;
    else hi = mid;
  }
  return lo;
}
// the time of the turnaround: the integral up to 0.9 a_max, then a = a_max - w² (the 1/√ singularity removed)
export function turnaroundTime(amaxNode, H0si, Or, Om, Ok) {
  // the integral needs the exact root of H = 0 for these Omegas (the node a_max settles to it with its own relation)
  const amax = turnaround(Or, Om, Ok);
  const a1 = 0.9 * amax;
  const t1 = friedmannTime(a1, H0si, Or, Om, 0, Ok);
  const W = Math.sqrt(amax - a1), n = 400, h = W / n;
  const g = (w) => {
    const a = amax - w * w;
    const E2 = Or / a ** 4 + Om / a ** 3 + Ok / a ** 2;
    return w === 0 ? 0 : (2 * w) / (a * H0si * Math.sqrt(Math.max(E2, 1e-300)));
  };
  // at w = 0 the integrand tends to a finite limit: use its value just beside
  let s = g(W) + g(h * 1e-3);
  for (let k = 1; k < n; k++) s += (k % 2 ? 4 : 2) * g(k * h);
  return t1 + (s * h) / 3;
}

function soundHorizon(a, H0si, Or, Om, OL, Rcoef, Ok = 0) {
  const n = 600, u0 = -30, u1 = Math.log(a), h = (u1 - u0) / n;
  const g = (u) => {
    const x = Math.exp(u);
    const H = H0si * Math.sqrt(Or * x ** -4 + Om * x ** -3 + Ok * x ** -2 + OL);
    return C / Math.sqrt(3 * (1 + Rcoef * x)) / (x * H);          // c_s da / (a^2 H) with da = a du
  };
  let s = g(u0) + g(u1);
  for (let k = 1; k < n; k++) s += (k % 2 ? 4 : 2) * g(u0 + k * h);
  return (s * h) / 3;
}
function comovingDistance(a, H0si, Or, Om, OL, Ok = 0) {
  const n = 600, u0 = Math.log(a), h = -u0 / n;
  const g = (u) => {
    const x = Math.exp(u);
    return C / (x * H0si * Math.sqrt(Or * x ** -4 + Om * x ** -3 + Ok * x ** -2 + OL));
  };
  let s = g(u0) + g(0);
  for (let k = 1; k < n; k++) s += (k % 2 ? 4 : 2) * g(u0 + k * h);
  return (s * h) / 3;
}

// ------------------------------------------------------------------ the network
function buildNetwork(p, reference) {
  const nodes = {};
  const rels = [];
  const node = (name, guess, scale = "log") => { nodes[name] = { guess, scale }; };
  const law = (name, terms, rhs, about, kind = "law", sigma = 1e-10) => rels.push({ name, terms, rhs, sigma, about, kind });
  const fn = (name, list, f, about, kind = "law", sigma = 1e-9) => rels.push({ name, type: "fn", nodes: list, f, sigma, about, kind });
  const sum = (name, terms, K, about, kind = "law", sigma = 1e-12) => rels.push({ name, type: "sum", terms, K, sigma, about, kind });

  // the constants (measured: the user's universe)
  for (const [n, g] of [["alpha", 7e-3], ["me", 9e-31], ["mp", 1.7e-27], ["G", 7e-11], ["hbar", 1e-34], ["c", 3e8],
    ["kB", 1.4e-23], ["H0", 70], ["ombh2", 0.02], ["omch2", 0.1], ["T0", 2.7]]) node(n, g);
  // the atom
  node("a0", 5e-11); node("Ry", 2e-18); node("alphaG", 6e-39);
  law("Bohr radius", { a0: 1, hbar: -1, me: 1, c: 1, alpha: 1 }, 0, "a0 = ħ / (m_e c α)");
  law("Rydberg energy", { Ry: 1, alpha: -2, me: -1, c: -2 }, -LG(2), "Ry = α² m_e c² / 2: what binds an electron to a proton");
  law("gravitational coupling", { alphaG: 1, G: -1, mp: -2, hbar: 1, c: 1 }, 0, "α_G = G m_p² / (ħ c): how weak gravity is between two protons");
  // the cosmos: Friedmann
  node("H0si", 2e-18); node("h", 0.7); node("rhoc", 1e-26); node("Ob", 0.05); node("Oc", 0.25); node("Om", 0.3);
  node("rhog", 4e-14); node("Og", 5e-5); node("Or", 9e-5); node("OL", 0.7, "lin"); node("Ok", 0, "lin"); node("eta", 6e-10);
  law("Hubble constant in SI", { H0si: 1, H0: -1 }, LG(1000 / MPC), "H0 in 1/s");
  law("little h", { h: 1, H0: -1 }, -2, "h = H0 / 100");
  law("critical density", { rhoc: 1, H0si: -2, G: 1 }, LG(3 / (8 * Math.PI)), "ρ_c = 3 H0² / (8π G) (Friedmann)");
  law("baryons", { Ob: 1, ombh2: -1, h: 2 }, 0, "Ω_b = ω_b / h²");
  law("dark matter", { Oc: 1, omch2: -1, h: 2 }, 0, "Ω_c = ω_c / h²");
  sum("matter", { Om: 1, Ob: -1, Oc: -1 }, 0, "Ω_m = Ω_b + Ω_c");
  law("light energy density", { rhog: 1, kB: -4, T0: -4, hbar: 3, c: 3 }, LG(Math.PI ** 2 / 15), "ρ_γ = π²/15 (kT)⁴ / (ħc)³ (black body)");
  law("light share", { Og: 1, rhog: -1, rhoc: 1, c: 2 }, 0, "Ω_γ = ρ_γ / (ρ_c c²)");
  law("radiation share", { Or: 1, Og: -1 }, LG(NU_FACTOR), "Ω_r = Ω_γ (1 + 0.2271 N_eff): light and neutrinos");
  sum("flat universe", { Om: 1, Or: 1, OL: 1, Ok: 1 }, 1,
    "Ω_m + Ω_r + Ω_Λ + Ω_k = 1: flat (Ω_k = 0, what Planck measures) while matter leaves room for dark energy");
  // too much matter: no room left for dark energy; the universe is closed and falls back (a choice of this page)
  const h2 = (p.H0 / 100) ** 2;
  const OrGuess = 2.4728e-5 * (p.Tcmb / 2.7255) ** 4 * NU_FACTOR / h2;
  const OmGuess = (p.ombh2 + p.omch2) / h2;
  const closed = OmGuess + OrGuess >= 0.999;
  rels.push({ name: closed ? "closed universe" : "no curvature", type: "sum", terms: { [closed ? "OL" : "Ok"]: 1 }, K: 0,
    sigma: 1e-12, kind: "hypothesis",
    about: closed ? "too much matter for a flat universe: no dark energy (Ω_Λ = 0), curvature Ω_k < 0: it will stop and fall back"
      : "no curvature (Ω_k = 0)" });
  // guesses from the parameters themselves: the integrals must start inside their domain (H² > 0)
  nodes.OL.guess = closed ? 0 : Math.max(0.01, 1 - OmGuess - OrGuess);
  nodes.Om.guess = OmGuess;
  nodes.Ob.guess = p.ombh2 / h2;
  nodes.Oc.guess = p.omch2 / h2;
  nodes.Or.guess = OrGuess;
  nodes.Og.guess = OrGuess / NU_FACTOR;
  nodes.h.guess = p.H0 / 100;
  nodes.H0si.guess = (p.H0 * 1000) / MPC;
  nodes.T0.guess = p.Tcmb;
  nodes.Ok.guess = closed ? 1 - OmGuess - OrGuess : 0;
  law("baryons per photon", { eta: 1, Ob: -1, rhoc: -1, mp: 1, kB: 3, T0: 3, hbar: -3, c: -3 }, -LG(2 * ZETA3 / Math.PI ** 2),
    "η = n_b / n_γ, n_γ = 2ζ(3)/π² (kT/ħc)³");
  // the first three minutes: deuterium survives (Saha)
  node("Tnuc", 8e8); node("tnuc", 200);
  fn("deuterium bottleneck", ["Tnuc", "eta", "mp", "c", "kB"], (v) =>
    LG(6.5 * v.eta * ((v.kB * v.Tnuc) / (v.mp * v.c * v.c)) ** 1.5) + B_DEUTERON / (v.kB * v.Tnuc * Math.LN10),
    "nuclei form when deuterium stops being broken by light: 6.5 η (kT/m_p c²)^3/2 e^(B_D/kT) = 1 (Saha)", "law", 1e-9);
  // recombination: the universe becomes transparent
  node("Tsaha", 3800); node("Trec", 3000); node("zrec", 1100, "lin"); node("trec", 1e13);
  fn("hydrogen recombines", ["Tsaha", "me", "kB", "hbar", "Ry", "eta", "c"], (v) => {
    const kT = v.kB * v.Tsaha;
    const ng = ((2 * ZETA3) / Math.PI ** 2) * (kT / (v.hbar * v.c)) ** 3;
    return LG(((v.me * kT) / (2 * Math.PI * v.hbar ** 2)) ** 1.5 / (v.eta * ng) / 0.5) - v.Ry / (kT * Math.LN10);
  }, "half the hydrogen is neutral: x²/(1-x) = (m_e kT/2πħ²)^3/2 e^(-Ry/kT) / n_b at x = 1/2 (Saha)");
  law("delayed recombination", { Trec: 1, Tsaha: -1 }, LG(0.7904),
    "the real recombination lags behind Saha's (Peebles 1968, not modelled): factor set so our universe gives Planck's z* = 1089.9",
    "hypothesis");
  fn("redshift of recombination", ["zrec", "Trec", "T0"], (v) => v.zrec + 1 - v.Trec / v.T0, "1 + z = T / T0");
  // times of the events: Friedmann integrated
  const tOf = (Tnode, tnode, about) => fn(about[0], [tnode, Tnode, "T0", "H0si", "Or", "Om", "OL", "Ok"], (v) =>
    LG(v[tnode]) - LG(friedmannTime(v.T0 / v[Tnode], v.H0si, v.Or, v.Om, v.OL, v.Ok)), about[1]);
  tOf("Tnuc", "tnuc", ["when nuclei form", "t = ∫ da / (a H(a)), H² = H0² (Ω_r a⁻⁴ + Ω_m a⁻³ + Ω_Λ), a = T0 / T"]);
  tOf("Trec", "trec", ["when light is set free", "the same Friedmann integral, to recombination"]);
  node("t0", 4e17);
  fn("age of the universe", ["t0", "H0si", "Or", "Om", "OL", "Ok"], (v) => LG(v.t0) - LG(friedmannTime(1, v.H0si, v.Or, v.Om, v.OL, v.Ok)),
    "today: a = 1");
  node("Rhor", 4e26);
  fn("observable universe", ["Rhor", "H0si", "Or", "Om", "OL", "Ok"], (v) =>
    LG(v.Rhor) - LG(comovingDistance(1e-14, v.H0si, v.Or, v.Om, v.OL, v.Ok)),
    "R = ∫ c da / (a² H) from the Big Bang to today: how far the light we see now has come from (radius, today)");
  node("zfirst", 20); node("tfirst", 5e15);
  nodes.zfirst.guess = 20;
  fn("first stars", ["tfirst", "zfirst", "H0si", "Or", "Om", "OL", "Ok"], (v) =>
    LG(v.tfirst) - LG(friedmannTime(1 / (1 + v.zfirst), v.H0si, v.Or, v.Om, v.OL, v.Ok)),
    "the first stars light up near z = 20 (simulations of structure formation; not derived here)", "hypothesis");
  // the sound of the early universe: acoustic peaks of the cosmic microwave background
  node("Rcoef", 600); node("rs", 4.5e24); node("DA", 4.3e26); node("lA", 300); node("l1", 220); node("Rrec", 0.6);
  law("baryon loading", { Rcoef: 1, Ob: -1, Og: 1 }, LG(3 / 4), "R = 3ρ_b / 4ρ_γ = (3Ω_b / 4Ω_γ) a: baryons make the sound heavier");
  law("loading at recombination", { Rrec: 1, Rcoef: -1, T0: -1, Trec: 1 }, 0, "R* = R(a*)");
  fn("sound horizon", ["rs", "Trec", "T0", "H0si", "Or", "Om", "OL", "Ok", "Rcoef"], (v) =>
    LG(v.rs) - LG(soundHorizon(v.T0 / v.Trec, v.H0si, v.Or, v.Om, v.OL, v.Rcoef, v.Ok)),
    "r_s = ∫ c_s da / (a² H), c_s = c / √(3(1+R)): how far sound went before light was freed");
  fn("distance to the light", ["DA", "Trec", "T0", "H0si", "Or", "Om", "OL", "Ok"], (v) =>
    LG(v.DA) - LG(comovingDistance(v.T0 / v.Trec, v.H0si, v.Or, v.Om, v.OL, v.Ok)), "D = ∫ c da / (a² H), from recombination to us");
  if (closed) {
    const amax0 = turnaround(OrGuess, OmGuess, 1 - OmGuess - OrGuess);
    node("amax", amax0); node("tmax", 1e17); node("tcrunch", 2e17);
    fn("the universe stops growing", ["amax", "Or", "Om", "Ok"], (v) =>
      (v.Or / v.amax ** 4 + v.Om / v.amax ** 3 + v.Ok / v.amax ** 2) * v.amax ** 2 / Math.abs(v.Ok),
      "H = 0 at a_max: Ω_r a⁻⁴ + Ω_m a⁻³ + Ω_k a⁻² = 0 (Friedmann, closed)");
    fn("time of the turnaround", ["tmax", "amax", "H0si", "Or", "Om", "Ok"], (v) =>
      LG(v.tmax) - LG(turnaroundTime(v.amax, v.H0si, v.Or, v.Om, v.Ok)), "t_max = ∫ da / (a H) up to a_max");
    law("Big Crunch", { tcrunch: 1, tmax: -1 }, LG(2), "it falls back as it grew: the crunch comes at 2 t_max");
    // the fall (Rees 1969): each threshold is a temperature of the light; the time left before the end is the time
    // the universe took to cool down to it (it falls back as it grew)
    // guesses from the parameters (as above): the integrals start inside their domain
    const Hg = (p.H0 * 1000) / MPC, Okg = 1 - OmGuess - OrGuess;
    const TmergeG = p.Tcmb * (1 + 20) * Math.cbrt(18 * Math.PI ** 2);
    node("Tmerge", TmergeG); node("dmerge", friedmannTime(p.Tcmb / TmergeG, Hg, OrGuess, OmGuess, 0, Okg));
    node("Tcook", 5772); node("dcook", friedmannTime(Math.min(p.Tcmb / 5772, 0.5), Hg, OrGuess, OmGuess, 0, Okg));
    fn("galaxies merge", ["Tmerge", "T0", "zfirst"], (v) => LG(v.Tmerge) - LG(v.T0 * (1 + v.zfirst) * Math.cbrt(18 * Math.PI ** 2)),
      "galaxies touch when the whole universe is as dense as they are: 18π² times denser than when they formed (Rees 1969)");
    law("the sky outshines the stars", { Tcook: 1, Tsun: -1 }, 0,
      "when the light of the sky is as hot as the stars' surface, they can no longer cool: they are cooked from outside (Rees 1969)");
    const left = (Tnode, dnode, about) => fn(about[0], [dnode, Tnode, "T0", "H0si", "Or", "Om", "OL", "Ok"], (v) =>
      LG(v[dnode]) - LG(friedmannTime(v.T0 / v[Tnode], v.H0si, v.Or, v.Om, v.OL, v.Ok)), about[1]);
    left("Tmerge", "dmerge", ["time left when galaxies merge", "the Friedmann integral, run backwards"]);
    left("Tcook", "dcook", ["time left when the stars are cooked", "the Friedmann integral, run backwards"]);
  }
  law("acoustic scale", { lA: 1, DA: -1, rs: 1 }, LG(Math.PI), "ℓ_A = π D / r_s: the size of the sound on the sky");
  law("first peak", { l1: 1, lA: -1 }, LG(1 - 0.267), "ℓ_n = ℓ_A (n - φ), φ ≈ 0.27 (Doran & Lilley 2002)", "hypothesis");
  // stars (Carr & Rees 1979; prefactors set on the Sun)
  node("Mstar", 2e30); node("tstar", 3e17); node("Tsun", 5800); node("tsun", 3e17);
  law("mass of a star", { Mstar: 1, mp: -1, alphaG: 1.5 }, LG(MSUN / (OURS.mp * (OURS.G * OURS.mp ** 2 / (HBAR * C)) ** -1.5)),
    "M ~ m_p α_G^-3/2: gravity against the pressure of hot matter (prefactor: the Sun)", "hypothesis");
  law("life of a star", { tstar: 1, alpha: -2, alphaG: 1, mp: -1, me: 2, hbar: -1, c: 2 },
    LG(10e9 * YEAR / ((OURS.alpha ** 2 / (OURS.G * OURS.mp ** 2 / (HBAR * C))) * (OURS.mp / OURS.me) ** 2 * (HBAR / (OURS.mp * C * C)))),
    "t ~ α² α_G⁻¹ (m_p/m_e)² ħ/(m_p c²) (Carr & Rees 1979; prefactor: the Sun lives 10 billion years)", "hypothesis");
  law("surface of a star", { Tsun: 1, Ry: -1, kB: 1 }, LG(5772 / ((OURS.alpha ** 2 * OURS.me * C * C) / 2 / KB)),
    "a photosphere sits where atoms start to hold their electrons: T ∝ Ry / k (prefactor: the Sun, 5772 K)", "hypothesis");
  // the Sun and its future
  node("tsunborn", 3e17); node("tredgiant", 6e17); node("tstarsend", 3e21);
  law("birth of the Sun", { tsunborn: 1, t0: -1 }, LG(1 - 4.567 / 13.814),
    "the Sun is born at the same share of the universe's age as ours (4.567 billion years before our today)", "hypothesis");
  sum("the Sun becomes a red giant", { tredgiant: 1, tsunborn: -1, tstar: -1 }, 0, "after its life on the main sequence", "law", 1e9);
  law("end of the stars", { tstarsend: 1, tstar: -1 }, LG(1e14 / 10e9),
    "the last red dwarfs go out, the gas is used up: ~10¹⁴ years for us (Adams & Laughlin 1997), scaled with the life of stars",
    "hypothesis");
  // the long night (Adams & Laughlin 1997): what is left once the stars are out
  node("tblack", 3e22); node("Ngal", 1e11); node("tcross", 3e15); node("trelax", 1e24); node("tevap", 1e26); node("tproton", 3e44);
  law("white dwarfs go black", { tblack: 1, tstar: -1 }, LG(1e15 / 10e9),
    "the dead stars cool into black dwarfs: ~10¹⁵ years for us (Adams & Laughlin 1997), scaled with the life of stars",
    "hypothesis");
  law("stars in a galaxy", { Ngal: 1, Mstar: 1 }, LG(1e11 * MSUN),
    "a galaxy like ours holds 10¹¹ suns' worth of matter: as many stars as stars of this universe's mass fit in it", "hypothesis");
  fn("crossing time of a galaxy", ["tcross", "H0si", "Om", "zfirst"], (v) =>
    LG(v.tcross) + 0.5 * LG(((18 * Math.PI ** 2 * 3) / (8 * Math.PI)) * v.H0si ** 2 * v.Om * (1 + v.zfirst) ** 3),
    "t_cross = 1/√(Gρ), ρ = 18π² times the mean matter density when galaxies collapse (spherical collapse; G cancels)");
  fn("stars exchange their energy", ["trelax", "Ngal", "tcross"], (v) =>
    LG(v.trelax) - LG((v.Ngal / (8 * Math.log(v.Ngal))) * v.tcross),
    "t_relax = N / (8 ln N) t_cross: close passages slowly share out the stars' energy (Binney & Tremaine)");
  law("galaxies evaporate", { tevap: 1, trelax: -1 }, LG(136),
    "t_evap ≈ 136 t_relax: the stars that gain energy escape, the others sink into the central black hole (Binney & Tremaine)");
  law("protons decay", { tproton: 1, mp: 5 }, LG(1e37 * YEAR * OURS.mp ** 5),
    "if protons decay (never seen: > 2.4 × 10³⁴ years, Super-Kamiokande), ~10³⁷ years (Adams & Laughlin), τ ∝ m_p⁻⁵ (grand unification)",
    "hypothesis");
  // black holes evaporate (Hawking)
  node("tbh", 1e77); node("tsmbh", 1e104);
  law("a stellar black hole evaporates", { tbh: 1, G: -2, Mstar: -3, hbar: 1, c: 4 }, LG(5120 * Math.PI * 1000),
    "t = 5120 π G² M³ / (ħ c⁴), M = 10 stars (Hawking 1974)");
  law("the largest black holes evaporate", { tsmbh: 1, G: -2, Mstar: -3, hbar: 1, c: 4 }, LG(5120 * Math.PI * 1e30),
    "the same, M = 10¹⁰ stars (the largest known black holes)");
  // the air of the Earth and the speed of sound
  node("Tearth", 288); node("Mair", 0.029); node("cair", 340);
  law("the Earth warmed by the Sun", { Tearth: 1, Tsun: -1 }, LG(Math.sqrt(6.957e8 / (2 * 1.496e11)) * (1 - 0.306) ** 0.25 * 288 / 254.0),
    "T = T_sun √(R_sun / 2d) (1 - albedo)^1/4, and the greenhouse (+33 K today, kept as a ratio)", "hypothesis");
  law("weight of the air", { Mair: 1, mp: -1 }, LG(28.966 / 1.007276 * NA), "M = 28.97 atomic masses per molecule (N₂, O₂)");
  law("speed of sound in air", { cair: 2, Tearth: -1, Mair: 1, kB: -1 }, LG(1.4 * NA), "c² = γ R T / M (ideal gas, γ = 1.4)");
  // the music: the flute is built in our universe; when the air changes, it plays higher or lower, still in tune
  const cRef = reference?.cair ?? 340.3;
  LYDIAN.forEach((ratio, k) => {
    const f = F4 * ratio;
    const L = cRef / (2 * f) - 2 * END_CORRECTION * FLUTE_RADIUS;    // the length the flute maker cut
    node(`flute${k}`, f);
    law(`flute note ${k + 1}`, { [`flute${k}`]: 1, cair: -1 }, -LG(2 * (L + 2 * END_CORRECTION * FLUTE_RADIUS)),
      `f = c / (2 (L + 1.22 r)): an open pipe cut for the Lydian degree ${k + 1} in our air`);
  });
  // the cosmic chord: the acoustic peaks heard 50 octaves higher (the transposition is the music's choice)
  const l1Ref = reference?.l1 ?? 220;
  for (let n = 1; n <= 6; n++) {
    node(`pad${n}`, 100 * n);
    law(`cosmic chord ${n}`, { [`pad${n}`]: 1, lA: -1 }, LG(((n - 0.267) * F2) / l1Ref),
      `peak ${n} of the sky's sound, transposed so that our first peak is an F`, "music");
  }
  const measured = {
    alpha: [OURS.alpha * p.alpha, 1e-12], me: [OURS.me * p.me, 1e-12], mp: [OURS.mp * p.mp, 1e-12], G: [OURS.G * p.G, 1e-12],
    hbar: [HBAR, 1e-12], c: [C, 1e-12], kB: [KB, 1e-12], H0: [p.H0, 1e-12], ombh2: [p.ombh2, 1e-12], omch2: [p.omch2, 1e-12],
    T0: [p.Tcmb, 1e-12], zfirst: [20, 1e-12],
  };
  return { nodes, rels, measured };
}

// guesses from a solved universe: the next solve starts there (fast and safe when a slider moves a little)
let lastSolved = null;

function solveOnce(params, reference, start, maxIterations) {
  const { nodes, rels, measured } = buildNetwork(params, reference);
  const net = new Network(nodes, rels.map(({ about, kind, ...r }) => r));
  // start from a universe of the same kind (flat or closed), else from the guesses
  const usable = start && ("amax" in start) === ("amax" in nodes) ? start : null;
  const out = net.solve(measured, { maxIterations, start: usable, computeUncertainty: false });
  return { out, rels, ok: out.converged && out.cost <= 1e-3 };
}

// A universe far from ours is reached step by step: the network is deformed a little at a time (each step starts
// where the last one settled), the way an elastic is stretched, instead of jumping there at once.
export function solveUniverse(params = DEFAULTS, reference = REFERENCE) {
  let tryDirect = null;
  try {
    tryDirect = solveOnce(params, reference, lastSolved, 60);
  } catch { tryDirect = null; }
  let done = tryDirect && tryDirect.ok ? tryDirect : null;
  if (!done) {
    const steps = 12;
    let start = null, last = null;
    for (let k = 1; k <= steps; k++) {
      const f = k / steps, p = {};
      for (const key of Object.keys(DEFAULTS)) p[key] = DEFAULTS[key] * (params[key] / DEFAULTS[key]) ** f;
      try {
        last = solveOnce(p, reference, start, 200);
      } catch (e) {
        throw new Error(`the network could not follow this universe (${e.message})`);
      }
      if (!last.ok && last.out.cost < 1e-1) last.ok = true;      // settled to 1e-10 in every relation: good enough
      if (!last.ok) {
        const worst = Object.entries(last.out.relation_pulls).sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]))[0];
        throw new Error(`the network did not settle (cost ${last.out.cost.toPrecision(3)}; most strained: ${worst[0]})`);
      }
      start = last.out.values;
    }
    done = last;
  }
  lastSolved = done.out.values;
  return { values: done.out.values, relations: done.rels.map(({ name, about, kind }) => ({ name, about, kind })), cost: done.out.cost };
}

// our universe, solved once: the flute and the cosmic chord are tuned on it
export const REFERENCE = (() => {
  const first = buildNetwork(DEFAULTS, null);
  const net = new Network(first.nodes, first.rels.map(({ about, kind, ...r }) => r));
  const out = net.solve(first.measured, { maxIterations: 200, computeUncertainty: false });
  return { cair: out.values.cair, l1: out.values.l1 };
})();

export const UNITS = { YEAR, MSUN, KB, EV };

// a(t) for drawing: the Friedmann integral tabulated on the network's own H0 and Omegas, u = ln a
export function expansion(values) {
  const { H0si, Or, Om, OL, Ok } = values;
  const closed = "amax" in values;
  const uTop = closed ? Math.log(values.amax) - 1e-4 : 6;
  const us = [], ts = [];
  for (let u = -30; u <= uTop; u += 0.05) {
    us.push(u);
    ts.push(friedmannTime(Math.exp(u), H0si, Or, Om, OL, Ok));
  }
  if (closed) {
    us.push(Math.log(values.amax));
    ts.push(values.tmax);
  }
  const HL = H0si * Math.sqrt(Math.max(OL, 0));
  // how far light has gone since the Big Bang (comoving): chi = ∫ c dt / a = ∫ c du / (a H), from the radiation era
  const Hu = (u) => H0si * Math.sqrt(Math.max(Or * Math.exp(-4 * u) + Om * Math.exp(-3 * u) + Ok * Math.exp(-2 * u) + OL, 1e-300));
  const chis = [C * Math.exp(-us[0]) / Hu(us[0])];
  for (let i = 1; i < us.length; i++) {
    const g = (u) => (C * Math.exp(-u)) / Hu(u);
    const a = us[i - 1], b = us[i];
    // near the turnaround H -> 0: the integrand stays finite in t, so use the times there
    const step = closed && i === us.length - 1
      ? (C * (ts[i] - ts[i - 1])) / Math.exp(0.5 * (a + b))
      : ((b - a) / 6) * (g(a) + 4 * g(0.5 * (a + b)) + g(b));
    chis.push(chis[i - 1] + step);
  }
  const locate = (t) => {
    let lo = 0, hi = ts.length - 1;
    while (hi - lo > 1) {
      const mid = (lo + hi) >> 1;
      if (ts[mid] < t) lo = mid;
      else hi = mid;
    }
    return [lo, hi, (Math.log(t) - Math.log(ts[lo])) / (Math.log(ts[hi]) - Math.log(ts[lo]))];
  };
  const grow = (t) => {
    if (t <= ts[0]) return 0.5 * Math.log(2 * H0si * Math.sqrt(Or) * Math.max(t, 1e-300));
    if (t >= ts[ts.length - 1]) return closed ? us[us.length - 1] : us[us.length - 1] + HL * (t - ts[ts.length - 1]);
    const [lo, hi, f] = locate(t);
    return us[lo] + f * (us[hi] - us[lo]);
  };
  const chiOf = (t) => {
    const n = ts.length - 1;
    if (t <= ts[0]) return (2 * C * t) / Math.exp(grow(t));          // radiation era: a ~ t^1/2
    if (t >= ts[n]) return closed ? chis[n] : chis[n] + (C / HL) * (Math.exp(-us[n]) - Math.exp(-grow(t)));
    const [lo, hi, f] = locate(t);
    return chis[lo] + f * (chis[hi] - chis[lo]);
  };
  // u at time t (s); a closed universe falls back as it grew (symmetric about the turnaround)
  const uOf = (t) => {
    if (!closed || t <= values.tmax) return grow(t);
    return grow(Math.max(2 * values.tmax - t, 1e-30));
  };
  // during the fall, from the time left before the Crunch (precise even in its last second)
  uOf.left = (left) => grow(Math.max(left, 1e-30));
  // the size of the observable universe (proper radius, m): a times how far light has gone. Falling, light keeps going:
  // chi = 2 chi(t_max) - chi(time left)
  // (in log10 of metres: in the far future a = e^u overflows any number, the size keeps growing)
  uOf.logSize = (t) => grow(t) / Math.LN10 + Math.log10(chiOf(t));
  uOf.logSizeLeft = (left) => grow(Math.max(left, 1e-30)) / Math.LN10
    + Math.log10(2 * chis[chis.length - 1] - chiOf(Math.max(left, 1e-30)));
  uOf.size = (t) => 10 ** uOf.logSize(t);
  return uOf;
}
