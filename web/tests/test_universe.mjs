// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Anthony Charretier
//
// The universe network against what is measured in ours. Run: node web/tests/test_universe.mjs
import { solveUniverse, DEFAULTS, UNITS, LYDIAN } from "../universe.js";

const { YEAR, KB, EV } = UNITS;
const t1 = performance.now();
const u = solveUniverse(DEFAULTS).values;
const ms = performance.now() - t1;
let failures = 0;
const check = (what, value, lo, hi, unit = "") => {
  const ok = value >= lo && value <= hi;
  if (!ok) failures++;
  console.log(`${ok ? "ok  " : "FAIL"} ${what}: ${value.toPrecision(5)} ${unit} (expected ${lo} .. ${hi})`);
};
check("Bohr radius", u.a0 * 1e12, 52.917, 52.918, "pm");
check("Rydberg energy", u.Ry / EV, 13.605, 13.606, "eV");
check("baryons per photon (Planck: 6.1e-10)", u.eta * 1e10, 6.0, 6.2, "e-10");
check("Omega_m (Planck: 0.315)", u.Om, 0.30, 0.32);
check("Omega_Lambda (Planck: 0.685)", u.OL, 0.68, 0.70);
check("age of the universe (Planck: 13.80 Gyr)", u.t0 / YEAR / 1e9, 13.75, 13.85, "Gyr");
check("nuclei: kT (textbook ~0.07 MeV)", (KB * u.Tnuc) / EV / 1e6, 0.06, 0.08, "MeV");
check("nuclei: time (textbook: a few minutes)", u.tnuc / 60, 2, 6, "min");
check("radius of the observable universe (~46 billion light-years)", u.Rhor / 9.4607e15 / 1e9, 45.5, 47, "Gly");
check("recombination z* (Planck: 1089.9)", u.zrec, 1088, 1092);
check("recombination: time (Planck: 372 kyr)", u.trec / YEAR / 1e3, 340, 400, "kyr");
check("first acoustic peak (Planck: 220)", u.l1, 215, 225);
check("sound horizon (Planck: 144 Mpc comoving)", u.rs / 3.0857e22, 140, 150, "Mpc");
check("life of a star like the Sun", u.tstar / YEAR / 1e9, 9.99, 10.01, "Gyr");
check("the Sun becomes a red giant, from now", (u.tredgiant - u.t0) / YEAR / 1e9, 5, 6, "Gyr");
check("speed of sound in air", u.cair, 335, 345, "m/s");
check("flute: the tonic (F4)", u.flute0, 349.2, 349.3, "Hz");
check("flute: the Lydian fourth", u.flute3 / u.flute0, LYDIAN[3] - 1e-9, LYDIAN[3] + 1e-9);
check("cosmic chord: first peak (F2)", u.pad1, 87.3, 87.32, "Hz");
check("stellar black hole evaporates (~1e70 yr)", Math.log10(u.tbh / YEAR), 69, 72, "log10 yr");
console.log(`solved in ${ms.toFixed(0)} ms`);

// a universe with gravity 10 times stronger: shorter-lived, lighter stars, the music unchanged in tune
const g = solveUniverse({ ...DEFAULTS, G: 10 }).values;
check("G x10: life of a star", g.tstar / YEAR / 1e9, 0.99, 1.01, "Gyr");
check("G x10: mass of a star (solar masses)", g.Mstar / UNITS.MSUN, 0.0315, 0.0318);
// alpha x 1.1: atoms bound harder, hotter stars, recombination earlier, a higher flute
const a = solveUniverse({ ...DEFAULTS, alpha: 1.1 }).values;
check("alpha x1.1: recombination z", a.zrec, 1300, 1340);
check("alpha x1.1: the flute plays higher (sound speed x1.1: T_sun ~ alpha^2)", a.flute0, 380, 388, "Hz");
check("alpha x1.1: still a Lydian fourth", a.flute3 / a.flute0, LYDIAN[3] - 1e-9, LYDIAN[3] + 1e-9);
// the long night (Adams & Laughlin 1997: galaxies evaporate in 10^19-10^20 years by their estimate)
check("white dwarfs black after (A&L: ~1e15 yr)", Math.log10(u.tblack / YEAR), 14.9, 15.1, "log10 yr");
check("crossing time of a galaxy (~1e8 yr)", Math.log10(u.tcross / YEAR), 7.5, 8.5, "log10 yr");
check("galaxies evaporate (A&L: 1e19-1e20 yr)", Math.log10(u.tevap / YEAR), 18, 20, "log10 yr");
check("protons decay, if they do (A&L reference: 1e37 yr)", Math.log10(u.tproton / YEAR), 36.9, 37.1, "log10 yr");
check("the order of the night: black dwarfs, evaporation, protons, black holes",
  Number(u.tblack < u.tevap && u.tevap < u.tproton && u.tproton < u.tbh && u.tbh < u.tsmbh), 1, 1);
// too much matter: a closed universe, reached by continuation, that stops and falls back (Big Crunch)
const c = solveUniverse({ ...DEFAULTS, omch2: 5, ombh2: 2 }).values;
check("closed: curvature is positive (Omega_k < 0)", c.Ok, -1e9, -0.01);
check("closed: the expansion stops later than today (a_max > 1)", c.amax, 1.0001, 10);
check("closed: the Crunch comes at twice the turnaround", c.tcrunch / c.tmax, 2 - 1e-9, 2 + 1e-9);
check("closed: still flat in sum (Om + Or + OL + Ok = 1)", c.Om + c.Or + c.OL + c.Ok, 1 - 1e-6, 1 + 1e-6);
check("closed: the Sun is born before today", c.tsunborn / c.t0, 0.5, 0.8);
check("closed: galaxies merge at 18π²^(1/3) (1 + z_first) T0", c.Tmerge / (c.T0 * 21 * Math.cbrt(18 * Math.PI ** 2)), 1 - 1e-6, 1 + 1e-6);
check("closed: the stars are cooked when the sky is as hot as their surface", c.Tcook / c.Tsun, 1 - 1e-6, 1 + 1e-6);
check("closed: galaxies merge before the stars are cooked", Number(c.dmerge > c.dcook), 1, 1);
// a burning universe (T x 37): light freed late, a Crunch within a few billion years
const h = solveUniverse({ ...DEFAULTS, Tcmb: 100 }).values;
check("hot: light freed late (z small)", h.zrec, 1, 200);
check("hot: Big Crunch soon", h.tcrunch / YEAR / 1e9, 0.5, 10, "Gyr");
process.exit(failures ? 1 : 0);
