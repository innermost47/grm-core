# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Anthony Charretier
"""
GRM Voice - a voice made of relations.

Lungs, vocal folds, airflow, vocal tract, velum, nose and lips are networks solved by the GRM core.
Nothing is sampled, nothing is learned:

    lungs and airflow   the subglottal pressure is shared between the glottis and the narrowest place of the
                        mouth, both orifices letting through the same flow   U = A sqrt(2 dP / rho)
    vocal folds         a string under tension:  f0 = 1 / (2 L_f) sqrt(stress / rho_tissue), raised a little by
                        the pressure across them; they vibrate only above the phonation threshold pressure
    vocal tract         a tube of 0.5 cm sections whose area is set by the tongue, the jaw and the lips. Its
                        resonances (the formants) are the complex frequencies at which a closed glottis lets no
                        flow through: the GRM solves  U_glottis(F + iB/2) = 0  for F and B. Walls that yield, and
                        the radiation at the lips and nostrils, give the bandwidths.
    velum and nose      a side branch: when the velum opens, the nose resonates and the mouth, closed or not,
                        makes anti-resonances (the GRM solves those too)
    turbulence          air forced through a narrow place hisses: noise pressure ~ rho U^3 / A^2.5 (Stevens),
                        filtered by the cavity in front of the constriction (s, ch, f, the burst of p t k)
    articulation        each articulator moves through time as a network: a target for every sound, and the
                        continuity of its motion. Coarticulation is what the network finds between them.
    vowels              the mouth shape of each vowel is not written by hand: the GRM finds the shape whose
                        resonances match measured formants (inverse network)

Usage:
    python grm_voice.py                        # "Bonjour Anthony. Je suis le réseau."  -> grm_voice.wav
    python grm_voice.py "b on j ou r"          # phonemes separated by spaces, "|" for a pause
    python grm_voice.py --vowels               # each vowel alone, with the formants the networks find
"""
import argparse
import math
import random
import wave

import numpy as np

from pygrm import GlobalRelationalNetwork

SAMPLE_RATE = 22050
RHO_AIR = 1.14          # kg/m^3, warm humid air in the vocal tract
C_AIR = 350.0           # m/s, speed of sound at body temperature
MU_AIR = 1.86e-5        # Pa s, viscosity of air
CM = 0.01               # metres per centimetre
CM2 = 1e-4              # square metres per square centimetre

# ============================================================
# THE TUBE: area function of the vocal tract
# ============================================================
# Glottis at x = 0. A larynx tube, then the pharynx and the mouth shaped by one tongue constriction, then
# the lips as a tube of their own (longer when rounded). Values are typical adult male figures.
TRACT_LENGTH = 16.0     # cm, glottis to the lips' inner edge (typical adult male, 17 cm with the lips)
DX = 0.5                # cm, length of one section
LARYNX_LENGTH = 2.0     # cm (typical)
LARYNX_AREA = 1.5       # cm^2 (typical)
A_OPEN = 4.0            # cm^2, area of the tube away from the constriction (hypothesis)
TONGUE_WIDTH = 2.6      # cm, half-width of the tongue hump (hypothesis)
VELUM_X = 8.5           # cm from the glottis, where the nasal tract branches off (typical)
NASAL_LENGTH = 11.0     # cm, velum to nostrils (typical)
NASAL_AREA = 2.0        # cm^2, nasal passages (typical)
NOSTRIL_AREA = 0.8      # cm^2, both nostrils (typical)
WALL_MASS = 15.0        # kg/m^2, yielding walls of the tract (typical figure, Fant 1960: 1.5 g/cm^2)
WALL_RESISTANCE = 1.6e4  # kg/(m^2 s) (typical figure, Fant 1960: 1600 g/(s cm^2))
GLOTTAL_RESISTANCE = 1.5e7  # Pa s/m^3, 2 dPg / U_mean over a cycle, 700 Pa and 0.1 l/s (replaced by the airflow network)


def area_function(p):
    """Areas (cm^2) and lengths (cm) of the sections, glottis to lips, from the articulators
    p = {xc, Ac, Alip, Llip, J, P, W}: constriction place (cm from the glottis), constriction area, lip area, lip
    length, jaw (how much wider than A_OPEN the mouth cavity in front of the constriction is), pharynx (the same
    behind it), and the half-length W of the tongue constriction."""
    areas, lengths = [], []
    n = int(round(TRACT_LENGTH / DX))
    for k in range(n):
        x = (k + 0.5) * DX
        if x < LARYNX_LENGTH:
            a = LARYNX_AREA
        else:
            g = math.exp(-((x - p["xc"]) / p.get("W", TONGUE_WIDTH)) ** 2)
            # the jaw opens the mouth cavity in front of the tongue; the tongue root widens the pharynx behind it
            wide = A_OPEN * (p.get("J", 1.0) if x > p["xc"] else p.get("P", 1.0))
            a = p["Ac"] + (wide - p["Ac"]) * (1.0 - g)
        areas.append(a)
        lengths.append(DX)
    nl = max(1, int(math.ceil(p["Llip"] / DX)))
    for _ in range(nl):
        areas.append(p["Alip"])
        lengths.append(p["Llip"] / nl)
    return areas, lengths


def radiation(A, s):
    """Radiation impedance (Pa s/m^3) of an opening of area A (m^2), piston in a baffle, at complex omega s."""
    a = math.sqrt(A / math.pi)
    ka = s / C_AIR * a
    return RHO_AIR * C_AIR / A * (ka * ka / 2 + 1j * 8 / (3 * math.pi) * ka)


def propagate(state, areas_cm2, lengths_cm, w):
    """(P, U) at the far end of a run of sections -> (P, U) at its near end, at complex angular frequency w.
    Each section: a lossless tube, the viscous drag of its walls (series resistance
    R = S / A^2 sqrt(w rho mu / 2) per metre, Flanagan), and the flow its yielding walls take."""
    P, U = state
    wr = np.maximum(np.abs(np.real(w)), 1.0)
    for A, l in zip(reversed(areas_cm2), reversed(lengths_cm)):
        A_m, l_m = max(A, 1e-4) * CM2, l * CM
        k = w / C_AIR
        z0 = RHO_AIR * C_AIR / A_m
        c, s_ = np.cos(k * l_m), np.sin(k * l_m)
        P, U = c * P + 1j * z0 * s_ * U, 1j * s_ / z0 * P + c * U
        perimeter = 2 * math.sqrt(math.pi * A_m)
        P = P + perimeter / A_m ** 2 * np.sqrt(wr * RHO_AIR * MU_AIR / 2) * l_m * U
        wall = perimeter * l_m / (WALL_RESISTANCE + 1j * w * WALL_MASS)
        U = U + wall * P
    return P, U


def tract_state(p, w):
    """Propagate from the openings back to the glottis. Returns (U_glottis, U_out, P_branch_oral):
    flows normalised so that the flow out of the lips is 1 (or the oral pressure at a closure is 1)."""
    areas, lengths = area_function(p)
    iv = int(round(VELUM_X / DX))
    back_a, back_l = areas[:iv], lengths[:iv]
    front_a, front_l = areas[iv:], lengths[iv:]
    closed = p["Alip"] < 0.01 or p["Ac"] < 0.01         # the mouth is shut: closed end at the occlusion
    if closed:
        # the occlusion: everything in front of it is silent; the oral branch ends there, closed
        cut = len(front_a)
        if p["Alip"] >= 0.01:
            xs = [(iv + k + 0.5) * DX for k in range(len(front_a))]
            cut = next((k for k, x in enumerate(xs) if x >= p["xc"]), len(front_a))
        front_a, front_l = front_a[:cut], front_l[:cut]
        Po, Uo = propagate((1.0 + 0j, 0j), front_a, front_l, w)
        U_lips = 0j
    else:
        Alip_m = p["Alip"] * CM2
        Po, Uo = propagate((radiation(Alip_m, w), 1.0 + 0j), front_a, front_l, w)
        U_lips = 1.0 + 0j
    alpha = 0j
    if p["Avel"] > 0.005:
        # the nose: port (area Avel, 1 cm), then the nasal passages, out through the nostrils
        nasal_a = [p["Avel"], p["Avel"]] + [NASAL_AREA] * int(NASAL_LENGTH / DX - 2)
        nasal_l = [DX] * len(nasal_a)
        Pn, Un = propagate((radiation(NOSTRIL_AREA * CM2, w), 1.0 + 0j), nasal_a, nasal_l, w)
        alpha = Po / np.where(np.abs(Pn) > 1e-30, Pn, 1e-30)   # same pressure at the branch point
        Uo, Uo_n = Uo + alpha * Un, alpha
    else:
        Uo_n = 0j
    Pg, Ug = propagate((Po, Uo), back_a, back_l, w)
    # the glottis is not a wall: an orifice of differential resistance Rg = 2 dPg / U lets some of the
    # sound back into the trachea. The tract rings freely when  U_g + P_g / Rg = 0.
    Rg = p.get("Rg", GLOTTAL_RESISTANCE)
    return Ug + Pg / Rg, U_lips + Uo_n, Po


# ============================================================
# GRM NETWORK OF THE RESONANCES
# ============================================================
# A resonance of the tract is a free vibration with the glottis closed: a complex frequency F + iB/2 at which
# the glottal flow is zero for a finite flow at the openings. Two nodes (F, B), two relations (real and imaginary
# parts of U_glottis = 0). The anti-resonances of a nasal sound are where the output flow vanishes.
F_MAX = 5000.0


def _scan(p, fn_index, f_lo=90.0, f_hi=F_MAX, step=10.0, b0=60.0):
    fs = np.arange(f_lo, f_hi, step)
    out = tract_state(p, 2 * math.pi * (fs + 1j * b0 / 2))       # all frequencies at once
    mags = np.abs(out[fn_index]) * np.ones(len(fs))
    lm = [i for i in range(1, len(fs) - 1) if mags[i] < mags[i - 1] and mags[i] <= mags[i + 1]]
    return [float(fs[i]) for i in lm], float(np.max(mags)) + 1e-30


def resonance_network(p, f_guess, which, scale):
    """Solve which(complex frequency) = 0 for F and B with the GRM core, from a guess."""
    def value(v):
        w = 2 * math.pi * complex(v["F"], v["B"] / 2)
        out = tract_state(p, w)
        z = complex(out[0] if which == "pole" else out[1])
        return z / scale
    nodes = {"F": {"guess": f_guess}, "B": {"guess": 60.0}}
    rels = [{"name": "real part", "type": "fn", "nodes": ["F", "B"], "f": lambda v: value(v).real, "sigma": 1e-6},
            {"name": "imaginary part", "type": "fn", "nodes": ["F", "B"], "f": lambda v: value(v).imag, "sigma": 1e-6}]
    try:
        out = GlobalRelationalNetwork(nodes, rels).solve(max_iterations=30, compute_uncertainty=False)
    except (ValueError, ArithmeticError, OverflowError):
        return None
    F, B = out["values"]["F"], out["values"]["B"]
    if not (60 < F < F_MAX + 500 and 1 < B < 5000) or out["cost"] > 1e-3:
        return None
    return F, B


def resonances(p, which="pole", previous=()):
    """Formants (F, B) of the tract with articulators p, or its anti-resonances (which = 'zero').
    previous: the resonances of the frame before, also used as starting points (a resonance made very wide
    by an open glottis no longer shows in the scan, but the network still finds it from where it was)."""
    guesses, scale = _scan(p, 0 if which == "pole" else 1)
    guesses = guesses + [F for F, _ in previous if all(abs(F - g) > 60 for g in guesses)]
    found = []
    for g in guesses:
        r = resonance_network(p, g, which, scale)
        if r is not None and all(abs(r[0] - f) > 30 for f, _ in found):
            found.append(r)
    return sorted(found)


# ============================================================
# INVERSE NETWORK: the mouth shape of a vowel, from its measured formants
# ============================================================
# Formants of a male voice for cardinal vowels (Wikipedia, "Formant", table of average vowel formants).
VOWEL_FORMANTS = {"i": (240, 2400), "y": (235, 2100), "e": (390, 2300), "ø": (370, 1900), "ɛ": (610, 1900),
                  "œ": (585, 1710), "a": (850, 1610), "ɑ": (750, 940), "ɔ": (500, 700), "o": (360, 640),
                  "u": (250, 595)}
# rounded vowels round the lips: a weak hint, the network decides how much
ROUNDED = set("yøœɔou")


LIP_MAX = 6.0           # cm^2, widest lip opening (hypothesis)
VOWEL_MIN_AREA = 0.25   # cm^2: narrower, the air would hiss (a fricative, not a vowel) (hypothesis)
LIP_MIN_AREA = 0.15     # cm^2, the most rounded lips of a vowel (hypothesis)
JAW_MIN, JAW_MAX = 0.6, 2.6   # the mouth cavity of a vowel, relative to A_OPEN (hypothesis)
PHA_MIN, PHA_MAX = 0.6, 2.2   # the pharynx, relative to A_OPEN (hypothesis)
W_MIN, W_MAX = 1.5, 4.0       # cm, half-length of the tongue constriction (hypothesis)


def shape_from_shares(v):
    """A vowel keeps its tongue constriction between VOWEL_MIN_AREA and A_OPEN, its lips between LIP_MIN_AREA
    and LIP_MAX: the network works on shares that cannot leave these bounds."""
    return {"xc": v["xc"], "Ac": VOWEL_MIN_AREA + (A_OPEN - VOWEL_MIN_AREA) * v["s"] / (1 + v["s"]),
            "Alip": LIP_MIN_AREA + (LIP_MAX - LIP_MIN_AREA) * v["u"] / (1 + v["u"]), "Llip": v["Llip"],
            "J": JAW_MIN + (JAW_MAX - JAW_MIN) * v["j"] / (1 + v["j"]),
            "P": PHA_MIN + (PHA_MAX - PHA_MIN) * v["q"] / (1 + v["q"]),
            "W": W_MIN + (W_MAX - W_MIN) * v["w"] / (1 + v["w"])}


def fit_vowel(symbol, verbose=False):
    """Articulators (xc, Ac, Alip, Llip) whose first two resonances match the measured formants.
    Nodes: the four articulators and the two formants. Relations: each formant equals the resonance the
    tract network computes for these articulators. Measurements: the formants (2 %), and loose priors on the
    articulators (they must stay a human mouth)."""
    F1, F2 = VOWEL_FORMANTS[symbol]
    rounded = symbol in ROUNDED
    cache = {}

    def model(v):
        p = dict(shape_from_shares(v), Avel=0.0)
        key = tuple(round(p[k], 7) for k in ("xc", "Ac", "Alip", "Llip", "J", "P", "W"))
        if key not in cache:
            r = resonances(p)
            cache[key] = (r[0][0], r[1][0]) if len(r) >= 2 else (float("nan"), float("nan"))
        return cache[key]
    # the constriction cannot be wider than the open tube, nor the lips wider than a mouth: the network works
    # on shares, Ac = A_OPEN s / (1 + s) and Alip = LIP_MAX u / (1 + u), which stay inside those bounds
    nodes = {"xc": {"guess": 8.0}, "s": {"guess": 0.5}, "u": {"guess": 0.3 if rounded else 1.0},
             "Llip": {"guess": 1.5 if rounded else 1.0}, "j": {"guess": 0.25}, "q": {"guess": 0.4}, "w": {"guess": 0.6},
             "F1": {"guess": F1}, "F2": {"guess": F2}}
    names = ["xc", "s", "u", "Llip", "j", "q", "w"]
    rels = [{"name": "first resonance", "type": "fn", "nodes": names + ["F1"], "sigma": 0.002,
             "f": lambda v: math.log10(v["F1"]) - math.log10(model(v)[0])},
            {"name": "second resonance", "type": "fn", "nodes": names + ["F2"], "sigma": 0.002,
             "f": lambda v: math.log10(v["F2"]) - math.log10(model(v)[1])}]
    measured = {"F1": (F1, 0.009), "F2": (F2, 0.009),          # 2 % on each formant
                "xc": (8.0, 0.3), "s": (0.5, 1.0), "u": (0.3 if rounded else 1.0, 0.7),
                "Llip": (1.5 if rounded else 1.0, 0.15), "j": (0.25, 0.7), "q": (0.4, 0.7), "w": (0.6, 0.7)}
    best = None
    starts = [(5.0, 0.3), (8.5, 0.3), (12.5, 3.0)] if not rounded else [(5.0, 0.3), (9.0, 0.3), (12.0, 3.0)]
    for xc0, q0 in starts:                                     # tongue back, middle, front (pharynx wide)
        nodes["xc"]["guess"], nodes["q"]["guess"] = xc0, q0
        try:
            out = GlobalRelationalNetwork(nodes, rels).solve(measured, max_iterations=30, tolerance=1e-7,
                                                             compute_uncertainty=False, continuation=False)
        except (ValueError, ArithmeticError):
            continue
        if math.isfinite(out["cost"]) and (best is None or out["cost"] < best["cost"]):
            best = out
    v = best["values"]
    art = shape_from_shares(v)
    got = model(v)
    if verbose:
        print(f"  {symbol}: tongue at {art['xc']:4.1f} cm, constriction {art['Ac']:4.2f} cm2, lips {art['Alip']:4.2f} cm2 "
              f"x {art['Llip']:3.1f} cm, jaw {art['J']:4.2f}, pharynx {art['P']:4.2f}, tongue {art['W']:3.1f} cm -> F1 {got[0]:4.0f} (measured {F1}), F2 {got[1]:5.0f} (measured {F2})")
    return art, got


# ============================================================
# GRM NETWORK OF THE LUNGS, THE GLOTTIS AND THE AIRFLOW (one per frame)
# ============================================================
# The lungs push with the subglottal pressure Ps. The air crosses two orifices in series, the glottis and the
# narrowest place downstream (tongue, lips, velum port), each with the Bernoulli law U = A sqrt(2 dP / rho):
#   pressure     dPg + dPc = Ps
#   glottis      U = (Ag + OQ / 2 Avib) sqrt(2 dPg / rho)       Ag: how far the folds are apart (abduction)
#   downstream   U = A_out sqrt(2 dPc / rho)                    A_out = constriction + velum port + wall leak
#   vibration    Avib = AVIB_MAX k_add sqrt((dPg - P_TH) / (P_REF - P_TH))   the folds vibrate only above the
#                phonation threshold pressure, and only if they are close enough together (k_add)
#   folds        f0s = 1 / (2 L_f) sqrt(stress / rho_tissue)    a string under tension (Titze)
#   pressure     f0 = f0s + KP dPg                              f0 rises with the pressure across the folds
# When the mouth closes for p, t, k the pressure moves from the glottis to the closure: the voicing dies and
# the air waits behind the lips. When it opens, the flow through the small opening is fast: the burst.
P_TH = 300.0            # Pa, phonation threshold pressure (typical: about 3 cm of water)
P_REF = 800.0           # Pa, speaking pressure at which the folds reach AVIB_MAX
AVIB_MAX = 0.12         # cm^2, largest glottal opening during a vibration cycle at P_REF (typical)
AG_VIBRATE = 0.12       # cm^2: folds further apart than this no longer vibrate (hypothesis)
OPEN_QUOTIENT = 0.6     # share of a cycle the glottis is open (typical)
FOLD_LENGTH = 0.016     # m, vibrating length of male vocal folds (typical)
RHO_TISSUE = 1040.0     # kg/m^3
KP = 0.03               # Hz/Pa, about 3 Hz per cm of water (typical figure)
REYNOLDS_CRIT = 1800.0  # below it a jet stays quiet (Stevens)
K_TURB = 0.02           # share of the jet's dynamic pressure that becomes noise (hypothesis, set by ear)
WALL_RADIATION = 0.05   # what the walls of a shut tract radiate, relative to an open mouth (hypothesis)
PS_REST = 5.0           # Pa, lungs at rest between phrases (quiet breathing)
PS_REST_TARGET = (PS_REST, 0.3)
STROUHAL = 0.2          # a jet sheds its eddies at f ~ 0.2 v / d: where its noise is strongest (typical)


def airflow_network(Ps, Ag, A_out, stress, guess=None):
    """One frame of the lungs, glottis, folds and downstream constriction. Areas in cm^2, pressures in Pa."""
    Ag_m, Aout_m = max(Ag, 1e-4) * CM2, max(A_out, 1e-5) * CM2
    k_add = max(0.0, 1.0 - Ag / AG_VIBRATE)

    def avib(v):
        x = max(v["dPg"] - P_TH, 0.0) / (P_REF - P_TH)
        return AVIB_MAX * k_add * math.sqrt(x) + 1e-6
    g = guess or {}
    nodes = {"U": {"guess": g.get("U", 2e-4)}, "dPg": {"guess": g.get("dPg", 0.6 * Ps)},
             "dPc": {"guess": g.get("dPc", 0.4 * Ps)}, "Avib": {"guess": g.get("Avib", 0.05)},
             "Ps": {"guess": Ps}, "stress": {"guess": stress}, "f0s": {"guess": 110.0}, "f0": {"guess": 110.0}}
    rels = [
        {"name": "pressure shared", "type": "sum", "terms": {"dPg": 1.0, "dPc": 1.0, "Ps": -1.0}, "K": 0.0, "sigma": 1e-3},
        {"name": "glottis", "type": "fn", "nodes": ["U", "dPg", "Avib"], "sigma": 1e-6,
         "f": lambda v: math.log10(v["U"]) - math.log10((Ag_m + OPEN_QUOTIENT / 2 * v["Avib"] * CM2)
                                                        * math.sqrt(2 * v["dPg"] / RHO_AIR))},
        {"name": "downstream", "terms": {"U": 1, "dPc": -0.5}, "rhs": math.log10(Aout_m * math.sqrt(2 / RHO_AIR)),
         "sigma": 1e-6},
        {"name": "vibration", "type": "fn", "nodes": ["Avib", "dPg"], "sigma": 1e-4,
         "f": lambda v: math.log10(v["Avib"]) - math.log10(avib(v))},
        {"name": "folds", "terms": {"f0s": 1, "stress": -0.5}, "rhs": math.log10(1 / (2 * FOLD_LENGTH) / math.sqrt(RHO_TISSUE)),
         "sigma": 1e-6},
        {"name": "pressure on the folds", "type": "sum", "terms": {"f0": 1.0, "f0s": -1.0, "dPg": -KP}, "K": 0.0,
         "sigma": 1e-3},
    ]
    out = GlobalRelationalNetwork(nodes, rels).solve({"Ps": (Ps, 1e-6), "stress": (stress, 1e-6)},
                                                     max_iterations=40, compute_uncertainty=False)
    return out["values"]


def stress_for(f0):
    """Fold stress (Pa) that gives f0 at rest: the inverse of the string law (prosody is planned in f0)."""
    return (2 * FOLD_LENGTH * f0) ** 2 * RHO_TISSUE


def jet_noise(U, A_cm2):
    """Turbulent noise of a jet of flow U through an opening A: its pressure (Pa), the resistance of the
    opening (p / R is the noise flow), and the frequency where it is strongest (Strouhal: 0.2 v / d)."""
    A = max(A_cm2, 1e-5) * CM2
    v = U / A
    d = math.sqrt(4 * A / math.pi)
    re = v * d * RHO_AIR / MU_AIR
    p = K_TURB * 0.5 * RHO_AIR * v * v * max(0.0, 1.0 - (REYNOLDS_CRIT / max(re, 1.0)) ** 2)
    return p, RHO_AIR * v / A + 1.0, max(STROUHAL * v / d, 200.0)


def noise_shape(f, f_peak):
    """Spectrum of jet noise around its eddy frequency: rising below, falling above (peak 1)."""
    x = f / f_peak
    return 2 * x / (1 + x * x)


# ============================================================
# THE SOUNDS OF FRENCH AS TARGETS FOR THE ARTICULATORS
# ============================================================
# Each sound gives targets to some articulators only, (value, sigma in dex). An articulator a sound does not
# use is left free: the network moves it from its neighbours (that is coarticulation). Areas in cm^2.
CLOSED = 0.0005         # cm^2, a closure (lips or tongue), not exactly zero
V_OPEN = 0.5            # cm^2, velum port of a nasal sound (typical)
AG_VOICED = 0.02        # cm^2, folds together: voicing
AG_VOICELESS = 0.30     # cm^2, folds apart: no voicing, the air hisses through (typical)
AG_BREATH = 0.6         # cm^2, breathing in a pause
LEAK_VOICED = 0.02      # cm^2: the cheeks and pharynx give way during b d g, the voicing goes on (hypothesis)
SHUT = 0.001            # cm^2, a velum or a leak that is shut

SHAPE_KEYS = ("xc", "Ac", "Alip", "Llip", "J", "P", "W")
PARAMS = list(SHAPE_KEYS) + ["Avel", "Ag", "leak"]
SMOOTH = {"xc": 0.02, "Ac": 0.06, "Alip": 0.06, "Llip": 0.03, "J": 0.03, "P": 0.02, "W": 0.02,
          "Avel": 0.05, "Ag": 0.06, "leak": 0.06}
#            dex per frame^2 (5 ms): how fast each articulator can change course (tongue slower than lips; hypothesis)


def vowel(shape, nasal=False):
    t = {k: (shape[k], 0.02) for k in SHAPE_KEYS}
    t["Avel"] = (V_OPEN if nasal else SHUT, 0.1)
    t["Ag"] = (AG_VOICED, 0.05)
    t["leak"] = (SHUT, 0.1)
    return t


def consonant(place=None, lips=None, nasal=False, voiced=True, extra=None):
    t = {}
    if place:
        t["xc"], t["Ac"] = (place[0], 0.01), (place[1], 0.05)
    if lips:
        t["Alip"], t["Llip"] = (lips[0], 0.05), (lips[1], 0.05)
    t["Avel"] = (V_OPEN if nasal else SHUT, 0.1)
    t["Ag"] = (AG_VOICED if voiced else AG_VOICELESS, 0.05)
    t["leak"] = (LEAK_VOICED if voiced and not nasal else SHUT, 0.1)
    t.update(extra or {})
    return t


def phoneme_table(shapes):
    """SAMPA symbols of French -> (targets, duration in ms, kind)."""
    v = {s: shapes[s] for s in shapes}
    schwa = {k: (v["ø"][k] + v["ɛ"][k]) / 2 for k in SHAPE_KEYS}
    T = {
        "i": (vowel(v["i"]), 85, "V"), "y": (vowel(v["y"]), 85, "V"), "e": (vowel(v["e"]), 85, "V"),
        "2": (vowel(v["ø"]), 85, "V"), "E": (vowel(v["ɛ"]), 85, "V"), "9": (vowel(v["œ"]), 85, "V"),
        "a": (vowel(v["a"]), 90, "V"), "A": (vowel(v["ɑ"]), 90, "V"), "O": (vowel(v["ɔ"]), 85, "V"),
        "o": (vowel(v["o"]), 85, "V"), "u": (vowel(v["u"]), 85, "V"), "@": (vowel(schwa), 60, "V"),
        "a~": (vowel(v["ɑ"], True), 110, "V"), "o~": (vowel(v["ɔ"], True), 110, "V"),
        "e~": (vowel(v["ɛ"], True), 110, "V"), "9~": (vowel(v["œ"], True), 110, "V"),
        # lips: closure; tongue free
        "p": (consonant(lips=(CLOSED, 0.8), voiced=False), 80, "stop"),
        "b": (consonant(lips=(CLOSED, 0.8)), 70, "stop"),
        "m": (consonant(lips=(CLOSED, 0.8), nasal=True), 70, "nasal"),
        "f": (consonant(lips=(0.12, 0.5), voiced=False), 95, "fric"),
        "v": (consonant(lips=(0.12, 0.5)), 70, "fric"),
        # tongue tip on the teeth ridge
        "t": (consonant(place=(14.8, CLOSED), voiced=False), 80, "stop"),
        "d": (consonant(place=(14.8, CLOSED)), 70, "stop"),
        "n": (consonant(place=(14.8, CLOSED), nasal=True), 70, "nasal"),
        "s": (consonant(place=(15.0, 0.06), voiced=False, extra={"J": (0.8, 0.05)}), 100, "fric"),
        "z": (consonant(place=(15.0, 0.06), extra={"J": (0.8, 0.05)}), 80, "fric"),
        "l": (consonant(place=(14.8, 0.3)), 60, "liquid"),
        # tongue blade behind the ridge, lips rounded forward
        "S": (consonant(place=(13.8, 0.12), lips=(0.8, 1.8), voiced=False), 100, "fric"),
        "Z": (consonant(place=(13.8, 0.12), lips=(0.8, 1.8)), 80, "fric"),
        # tongue back on the velum
        "k": (consonant(place=(10.5, CLOSED), voiced=False), 80, "stop"),
        "g": (consonant(place=(10.5, CLOSED)), 70, "stop"),
        # tongue root towards the uvula: a voiced hiss, often almost a vowel
        "R": (consonant(place=(6.5, 0.18), extra={"leak": (SHUT, 0.1)}), 65, "liquid"),
        # glides: the narrowest vowels
        "j": (consonant(place=(v["i"]["xc"], 0.18), extra={"Alip": (v["i"]["Alip"], 0.05), "leak": (SHUT, 0.1)}), 50, "glide"),
        "w": (consonant(place=(v["u"]["xc"], 0.3), lips=(0.12, 1.6), extra={"leak": (SHUT, 0.1)}), 55, "glide"),
        "H": (consonant(place=(v["y"]["xc"], 0.2), lips=(0.18, 1.5), extra={"leak": (SHUT, 0.1)}), 50, "glide"),
    }
    return T


NEUTRAL = {"xc": 9.0, "Ac": 2.0, "Alip": 2.0, "Llip": 1.0, "J": 1.0, "P": 1.0, "W": TONGUE_WIDTH, "Avel": SHUT,
           "Ag": AG_BREATH, "leak": SHUT}
FRAME = 0.005           # s


def plan(phonemes, table, f0_base=118.0):
    """Targets in time. Returns (frames, targets per parameter, f0 intents, Ps intents, labels)."""
    t, segs = 0.25, []
    groups = [[]]
    for ph in phonemes:
        if ph in ("|", "||"):
            groups[-1].append(ph)
            groups.append([])
        else:
            groups[-1].append(ph)
    for gi, grp in enumerate(groups):
        sounds = [ph for ph in grp if ph not in ("|", "||")]
        last_v = max([k for k, ph in enumerate(sounds) if table[ph][2] == "V"] or [len(sounds) - 1])
        for k, ph in enumerate(sounds):
            targets, dur, kind = table[ph]
            if k == last_v:
                dur *= 1.7                                   # French: the last syllable of a group is longer
            segs.append((ph, t, t + dur / 1000.0, kind, gi, k == last_v))
            t += dur / 1000.0
        if grp and grp[-1] in ("|", "||"):
            segs.append(("_", t, t + (0.12 if grp[-1] == "|" else 0.30), "pause", gi, False))
            t += 0.12 if grp[-1] == "|" else 0.30
    total = t + 0.3
    n = int(total / FRAME) + 1
    targets = {p: [[] for _ in range(n)] for p in PARAMS}
    f0_int, ps_int = [None] * n, [None] * n
    final_group = len(groups) - 1
    for ph, a, b, kind, gi, last in segs:
        ka, kb = int(a / FRAME), int(b / FRAME)
        if ph == "_":
            for k in range(ka, kb):
                targets["Ag"][k].append((AG_BREATH, 0.05))
                ps_int[k] = (PS_REST, 0.05)
            continue
        tg = table[ph][0]
        core = (0.25, 0.75) if kind == "V" else (0.2, 0.8)
        for k in range(ka + int((kb - ka) * core[0]), max(ka + int((kb - ka) * core[1]), ka + 1)):
            for p, val in tg.items():
                targets[p][k].append(val)
        # prosody: speaking pressure, and pitch falling slowly through the group; a rise on the last
        # syllable of a group that goes on, a fall at the end of a sentence
        for k in range(ka, kb):
            ps_int[k] = (P_REF, 0.03)
        if kind == "V":
            mid = (ka + kb) // 2
            g_start = min(s[1] for s in segs if s[4] == gi)
            g_end = max(s[2] for s in segs if s[4] == gi)
            frac = ((a + b) / 2 - g_start) / max(g_end - g_start, 1e-3)
            f = f0_base * (1.05 - 0.15 * frac)
            if last:
                ends = groups[gi][-1] if groups[gi] else ""
                f = f0_base * (0.80 if ends == "||" or gi == final_group else 1.22)
            f0_int[mid] = (f, 0.01)
    labels = [(ph, a, b) for ph, a, b, *_ in segs]
    return n, targets, f0_int, ps_int, labels


def trajectory_network(n, targets, smooth, neutral):
    """One articulator through time: a node per frame, the targets of the sounds as measurements, and the
    continuity of the motion (second difference ~ 0, in log) as relations. Coarticulation is the answer."""
    nodes = {f"x{k}": {"guess": neutral} for k in range(n)}
    rels = [{"name": f"motion {k}", "terms": {f"x{k - 1}": 1, f"x{k}": -2, f"x{k + 1}": 1}, "rhs": 0.0, "sigma": smooth}
            for k in range(1, n - 1)]
    measured = {}
    for k in range(n):
        tg = targets[k]
        if tg:
            # several sounds may aim at the same frame: they pull together, weighted by their sigmas
            w = sum(1 / s_ ** 2 for _, s_ in tg)
            mean = sum(math.log10(val) / s_ ** 2 for val, s_ in tg) / w
            measured[f"x{k}"] = (10 ** mean, 1 / math.sqrt(w))
        else:
            measured[f"x{k}"] = (neutral, 3.0)               # free: only a very weak pull to rest
    out = GlobalRelationalNetwork(nodes, rels).solve(measured, compute_uncertainty=False)
    return [out["values"][f"x{k}"] for k in range(n)]


# ============================================================
# FROM THE NETWORKS TO SOUND
# ============================================================

def transfer(f, poles, zeros):
    """H(f) of the tract from its resonances and anti-resonances (unit gain at 0 Hz)."""
    s = 2j * math.pi * f
    H = np.ones(len(f), dtype=complex)
    for F, B in poles:
        p = complex(-math.pi * B, 2 * math.pi * F)
        H *= (p * p.conjugate()) / ((s - p) * (s - p.conjugate()))
    for F, B in zeros:
        z = complex(-math.pi * B, 2 * math.pi * F)
        H *= ((s - z) * (s - z.conjugate())) / (z * z.conjugate())
    return H


def front_resonances(p):
    """Resonances of the cavity in front of the narrowest place (where the hiss is made), closed behind."""
    areas, lengths = area_function(p)
    if p["Alip"] <= p["Ac"]:
        return []                                          # the narrowest place is the lips: nothing in front
    xs = np.cumsum(lengths) - np.array(lengths) / 2
    ic = int(np.argmin(areas[:len(areas) - max(1, int(math.ceil(p["Llip"] / DX)))]))
    fa, fl = areas[ic + 1:], lengths[ic + 1:]
    if not fa:
        return []

    def state(w):
        P, U = propagate((radiation(p["Alip"] * CM2, w), 1.0 + 0j), fa, fl, w)
        return U, U, P
    fs = np.arange(300.0, 9000.0, 20.0)
    mags = np.abs(state(2 * math.pi * (fs + 30j))[0])
    found = []
    for i in range(1, len(fs) - 1):
        if mags[i] < mags[i - 1] and mags[i] <= mags[i + 1]:
            def value(v):
                return complex(state(2 * math.pi * complex(v["F"], v["B"] / 2))[0]) / (np.max(mags) + 1e-30)
            nodes = {"F": {"guess": float(fs[i])}, "B": {"guess": 200.0}}
            rels = [{"name": "re", "type": "fn", "nodes": ["F", "B"], "f": lambda v: value(v).real, "sigma": 1e-6},
                    {"name": "im", "type": "fn", "nodes": ["F", "B"], "f": lambda v: value(v).imag, "sigma": 1e-6}]
            try:
                o = GlobalRelationalNetwork(nodes, rels).solve(max_iterations=30, compute_uncertainty=False)
                F, B = o["values"]["F"], o["values"]["B"]
                if 200 < F < 10000 and 10 < B < 4000:
                    found.append((F, B))
            except (ValueError, ArithmeticError, OverflowError):
                pass
    return found[:3]


def speak(phonemes, shapes, verbose=False, seed=1):
    table = phoneme_table(shapes)
    n, targets, f0_int, ps_int, labels = plan(phonemes, table)
    # 1) the articulators through time
    traj = {p: trajectory_network(n, targets[p], SMOOTH[p], NEUTRAL[p]) for p in PARAMS}
    # the folds' stress through time: the intended pitch at the vowels (stress ~ f0^2: twice the sigma in dex)
    # (the pressure on the folds adds KP * dPg: the intended pitch is reached at the speaking pressure)
    stress_targets = [[(stress_for(f[0] - KP * P_REF), 2 * f[1])] if f else [] for f in f0_int]
    stress = trajectory_network(n, stress_targets, 0.004, stress_for(110.0))
    ps = trajectory_network(n, [[v] if v else [PS_REST_TARGET] for v in ps_int], 0.03, PS_REST)
    # 2) every frame: airflow, folds, resonances
    frames, guess = [], None
    for k in range(n):
        p = {q: traj[q][k] for q in PARAMS}
        areas, _ = area_function(p)
        oral_min = min(areas)
        A_out = oral_min + (p["Avel"] if p["Avel"] > 0.005 else 0.0) + p["leak"]
        air = airflow_network(ps[k], p["Ag"], A_out, stress[k], guess)
        guess = air
        p["Rg"] = max(2 * air["dPg"] / max(air["U"], 1e-7), 1e5)
        poles = resonances(p, previous=frames[-1]["poles"] if frames else ())
        zeros = resonances(p, "zero", previous=frames[-1]["zeros"] if frames else ()) if p["Avel"] > 0.02 else []
        front = front_resonances(p) if oral_min < 0.4 else []
        frames.append({"p": p, "air": air, "poles": poles, "zeros": zeros, "front": front, "oral_min": oral_min})
        if verbose and k % 20 == 0:
            print(f"  {k * FRAME:5.2f} s  f0 {air['f0']:5.1f} Hz  dPg {air['dPg']:4.0f} Pa  U {air['U'] * 1e6:5.0f} cm3/s  "
                  f"formants {[round(F) for F, _ in poles[:3]]}")
    return render(frames, seed), labels, frames


def render(frames, seed=1):
    """Sources in time (glottal pulses, aspiration, frication), shaped frame by frame by the transfer of the
    tract (poles and zeros from the GRM), radiated from the lips (pressure ~ d/dt of the flow)."""
    rng = np.random.default_rng(seed)
    hop = int(FRAME * SAMPLE_RATE)
    count = hop * len(frames) + 4096
    # glottal flow: a pulse per cycle (opening 2/3, closing 1/3 of the open phase), with the folds' own
    # small irregularities (jitter 0.5 %, shimmer 3 %: hypotheses)
    ug = np.zeros(count)
    phase, amp_cycle = 0.0, 1.0
    f0s = np.interp(np.arange(count), np.arange(len(frames)) * hop, [fr["air"]["f0"] for fr in frames])
    uac = np.interp(np.arange(count), np.arange(len(frames)) * hop,
                    [fr["air"]["Avib"] * CM2 * math.sqrt(2 * fr["air"]["dPg"] / RHO_AIR) for fr in frames])
    jitter = 1.0
    for i in range(count):
        phase += f0s[i] * jitter / SAMPLE_RATE
        if phase >= 1.0:
            phase -= 1.0
            jitter = 1.0 + rng.normal(0, 0.005)
            amp_cycle = 1.0 + rng.normal(0, 0.03)
        if phase < OPEN_QUOTIENT:
            x = phase / OPEN_QUOTIENT
            shape = 0.5 * (1 - math.cos(math.pi * x / 0.667)) if x < 0.667 else math.cos(math.pi * (x - 0.667) / (2 * 0.333))
            ug[i] = uac[i] * amp_cycle * shape
    # noises: aspiration at the glottis and frication at the constriction, as flows (p / R)
    asp_level, fric_level = np.zeros(len(frames)), np.zeros(len(frames))
    asp_peak, fric_peak = np.zeros(len(frames)), np.zeros(len(frames))
    for k, fr in enumerate(frames):
        a, p = fr["air"], fr["p"]
        pn, R, fp = jet_noise(a["U"], p["Ag"] + OPEN_QUOTIENT / 2 * a["Avib"])
        asp_level[k], asp_peak[k] = pn / R, fp
        pn, R, fp = jet_noise(a["U"], fr["oral_min"])
        fric_level[k], fric_peak[k] = pn / R, fp
    t_idx = np.arange(count)
    asp = rng.standard_normal(count) * np.interp(t_idx, np.arange(len(frames)) * hop, asp_level)
    asp *= 0.4 + ug / (np.max(ug) + 1e-12)                  # the glottal hiss is louder when the glottis is open
    fric = rng.standard_normal(count) * np.interp(t_idx, np.arange(len(frames)) * hop, fric_level)
    # frame by frame: window, filter by the tract, overlap-add
    win_len = 2 * hop
    window = np.hanning(win_len + 1)[:-1]
    nfft = 8192
    f = np.fft.rfftfreq(nfft, 1.0 / SAMPLE_RATE)
    radiation_f = 2j * math.pi * f                          # pressure ~ d/dt of the flow out of the lips
    out = np.zeros(count + nfft)
    for k, fr in enumerate(frames):
        a = k * hop
        w_ = window[: len(ug[a:a + win_len])]
        src = np.fft.rfft(ug[a:a + win_len] * w_, nfft) + np.fft.rfft(asp[a:a + win_len] * w_, nfft) * noise_shape(f, asp_peak[k])
        src_f = np.fft.rfft(fric[a:a + win_len] * w_, nfft) * noise_shape(f, fric_peak[k])
        H = transfer(f, fr["poles"], fr["zeros"])
        # as the mouth shuts (p t k b d g) less and less leaves the lips (the nose too is shut): only the walls
        # of the throat, pushed by the voicing, still radiate a weak low murmur (the voice bar)
        A_rad = fr["oral_min"] + (fr["p"]["Avel"] if fr["p"]["Avel"] > 0.005 else 0.0)
        m = A_rad / (A_rad + 0.02)
        H = H * (m + (1 - m) * WALL_RADIATION / (1 + 1j * f / 300.0))
        Hf = transfer(f, fr["front"], []) if fr["front"] else np.ones(len(f))
        spec = src * H + src_f * Hf
        y = np.fft.irfft(spec * radiation_f, nfft)
        out[a:a + nfft] += y
    out = out[:count]
    peak = np.max(np.abs(out))
    return out / peak * 0.9 if peak > 0 else out


def write_wav(path, audio):
    data = (np.clip(audio, -1, 1) * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(data.tobytes())


# Found by the inverse networks (python grm_voice.py --fit shapes.json), from VOWEL_FORMANTS.
# F: the first two resonances of that shape, as the tract network computes them.
VOWEL_SHAPES = {
    "i": {"xc": 11.8572, "Ac": 0.2665, "Alip": 1.6775, "Llip": 0.9252, "J": 0.6255, "P": 2.1643, "W": 3.814, "F": [271, 2221]},
    "y": {"xc": 12.8528, "Ac": 0.2661, "Alip": 0.5493, "Llip": 1.4769, "J": 0.6804, "P": 2.1109, "W": 3.6788, "F": [250, 1964]},
    "e": {"xc": 11.0891, "Ac": 0.3881, "Alip": 4.8065, "Llip": 0.7492, "J": 0.8133, "P": 1.1194, "W": 3.3936, "F": [390, 2174]},
    "ø": {"xc": 12.3635, "Ac": 0.5883, "Alip": 2.0452, "Llip": 1.4287, "J": 0.8884, "P": 1.3476, "W": 2.7819, "F": [370, 1895]},
    "ɛ": {"xc": 11.3674, "Ac": 1.5868, "Alip": 5.2261, "Llip": 0.5153, "J": 1.4101, "P": 0.7006, "W": 2.9983, "F": [589, 1798]},
    "œ": {"xc": 11.7091, "Ac": 1.8473, "Alip": 4.5011, "Llip": 1.0406, "J": 1.1798, "P": 0.7224, "W": 2.4345, "F": [578, 1690]},
    "a": {"xc": 3.6755, "Ac": 1.2384, "Alip": 5.7275, "Llip": 0.3188, "J": 1.5756, "P": 0.7817, "W": 3.7954, "F": [729, 1493]},
    "ɑ": {"xc": 5.0825, "Ac": 0.2682, "Alip": 4.8088, "Llip": 0.8639, "J": 2.093, "P": 0.6999, "W": 3.7215, "F": [729, 970]},
    "ɔ": {"xc": 7.2753, "Ac": 0.2809, "Alip": 1.1696, "Llip": 1.5579, "J": 2.1546, "P": 0.8307, "W": 3.3514, "F": [488, 755]},
    "o": {"xc": 8.1322, "Ac": 0.2789, "Alip": 0.4888, "Llip": 1.6823, "J": 2.1588, "P": 1.2591, "W": 3.2493, "F": [357, 656]},
    "u": {"xc": 8.6975, "Ac": 0.2858, "Alip": 0.2294, "Llip": 2.2342, "J": 2.0833, "P": 1.8235, "W": 2.7406, "F": [251, 602]},
}

SENTENCE = "b o~ Z u R | a~ t O n i || Z @ s H i l @ R e z o ||"


def main():
    ap = argparse.ArgumentParser(description="GRM Voice: a voice made of relations.")
    ap.add_argument("phonemes", nargs="?", default=SENTENCE,
                    help='French SAMPA phonemes separated by spaces, "|" short pause, "||" end of sentence')
    ap.add_argument("-o", "--output", default="grm_voice.wav")
    ap.add_argument("--vowels", action="store_true", help="each vowel alone, with its formants")
    ap.add_argument("--fit", metavar="JSON", help="find the vowel shapes again (inverse networks) and save them")
    args = ap.parse_args()
    if args.fit:
        import json
        shapes = {}
        for sym in VOWEL_FORMANTS:
            art, got = fit_vowel(sym, verbose=True)
            shapes[sym] = {k: round(v, 4) for k, v in art.items()}
            shapes[sym]["F"] = [round(g) for g in got]
        with open(args.fit, "w") as fh:
            json.dump(shapes, fh, ensure_ascii=False, indent=1)
        return
    if args.vowels:
        seq = []
        for sym, sampa in (("i", "i"), ("e", "e"), ("ɛ", "E"), ("a", "a"), ("ɑ", "A"), ("ɔ", "O"), ("o", "o"),
                           ("u", "u"), ("y", "y"), ("ø", "2"), ("œ", "9")):
            sh = VOWEL_SHAPES[sym]
            print(f"  {sym}: formants {sh['F'][0]} / {sh['F'][1]} Hz (measured {VOWEL_FORMANTS[sym][0]} / {VOWEL_FORMANTS[sym][1]})")
            seq += [sampa, "|"]
        phonemes = seq + ["||"]
    else:
        phonemes = args.phonemes.split()
    audio, labels, _ = speak(phonemes, VOWEL_SHAPES, verbose=False)
    write_wav(args.output, audio)
    print(f"{args.output}: {len(audio) / SAMPLE_RATE:.2f} s, " + " ".join(ph for ph, _, _ in labels))


if __name__ == "__main__":
    main()
