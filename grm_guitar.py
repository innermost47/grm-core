# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Anthony Charretier
"""
GRM Guitar - six vibrating strings computed by the Global Relational Model core (grm.py).

Python 3.10+
Dependencies: numpy (required), sounddevice (optional, for sound; WAV export works without it)

Each string is a small relational network solved by grm.GlobalRelationalNetwork:

    wave speed      c^2 * mu / T = 1
    fundamental     2 * L_eff * f1 / c = 1
    fret            L_eff = L * 2^(-fret / 12)
    steel core      d^2 = 4 * mu * k^2 / (pi * rho)      (k = core fraction of a wound string)
    stiffness       B = pi^3 * E * d^4 / (64 * T * L_eff^2)

Played this way, L, mu and T are measurements (with their uncertainty) and the network gives
f1, c and B with their uncertainty. Tuned this way, the target pitch becomes the measurement and
the same network gives the tension. The partials follow the stiff-string law
f_n = n * f1 * sqrt(1 + B * n^2).
"""
import math
import time
import tkinter as tk
import wave
from tkinter import filedialog, messagebox, ttk

import numpy as np

from grm import GlobalRelationalNetwork

try:
    import sounddevice as sd
except Exception:  # sound is optional
    sd = None


# ============================================================
# PHYSICAL DATA
# ============================================================

SAMPLE_RATE = 44100
RHO_STEEL = 7850.0          # kg/m^3
E_STEEL = 2.0e11            # Pa, Young's modulus of steel
LN10 = math.log(10.0)
CENTS_PER_DEX = 1200.0 / math.log10(2.0)

# default uncertainties of the inputs (absolute)
SIGMA_L = 0.0005            # m   (half a millimetre on the scale length)
SIGMA_MU_REL = 0.01         # 1 % on the linear mass density
SIGMA_T = 0.5               # N

STRINGS = [
    {"number": 6, "note": "E2", "name": "Low E", "target": 82.4069, "L": 0.648, "mu": 0.0061370673, "T": 70.0, "wound": True},
    {"number": 5, "note": "A2", "name": "A", "target": 110.0, "L": 0.648, "mu": 0.0034443134, "T": 70.0, "wound": True},
    {"number": 4, "note": "D3", "name": "D", "target": 146.832, "L": 0.648, "mu": 0.0019330657, "T": 70.0, "wound": True},
    {"number": 3, "note": "G3", "name": "G", "target": 196.0, "L": 0.648, "mu": 0.0010848655, "T": 70.0, "wound": False},
    {"number": 2, "note": "B3", "name": "B", "target": 246.942, "L": 0.648, "mu": 0.0006834364, "T": 70.0, "wound": False},
    {"number": 1, "note": "E4", "name": "High E", "target": 329.628, "L": 0.648, "mu": 0.0003835658, "T": 70.0, "wound": False},
]

# chord shapes, from string 6 to string 1; None = string not played
CHORDS = {
    "Open": [0, 0, 0, 0, 0, 0],
    "Em": [0, 2, 2, 0, 0, 0],
    "E": [0, 2, 2, 1, 0, 0],
    "Am": [None, 0, 2, 2, 1, 0],
    "A": [None, 0, 2, 2, 2, 0],
    "D": [None, None, 0, 2, 3, 2],
    "C": [None, 3, 2, 0, 1, 0],
    "G": [3, 2, 0, 0, 0, 3],
}


# ============================================================
# GRM NETWORK OF ONE STRING
# ============================================================

def string_network(fret, core_fraction):
    nodes = {
        "L": {"guess": 0.65}, "Leff": {"guess": 0.65}, "mu": {"guess": 1e-3}, "T": {"guess": 70.0},
        "c": {"guess": 200.0}, "f1": {"guess": 200.0}, "d": {"guess": 5e-4}, "B": {"guess": 1e-4},
    }
    relations = [
        {"name": "wave speed", "terms": {"c": 2, "mu": 1, "T": -1}, "rhs": 0.0, "sigma": 1e-9},
        {"name": "fundamental", "terms": {"Leff": 1, "f1": 1, "c": -1}, "rhs": -math.log10(2.0), "sigma": 1e-9},
        {"name": "fret", "terms": {"Leff": 1, "L": -1}, "rhs": -fret * math.log10(2.0) / 12.0, "sigma": 1e-9},
        {"name": "steel core", "terms": {"d": 2, "mu": -1},
         "rhs": math.log10(4.0 * core_fraction ** 2 / (math.pi * RHO_STEEL)), "sigma": 1e-9},
        {"name": "stiffness", "terms": {"B": 1, "d": -4, "T": 1, "Leff": 2},
         "rhs": math.log10(math.pi ** 3 * E_STEEL / 64.0), "sigma": 1e-9},
    ]
    return GlobalRelationalNetwork(nodes, relations)


def dex(rel):
    """Relative uncertainty -> sigma in dex."""
    return rel / LN10


def play_string_model(L, mu, T, fret=0, core_fraction=1.0):
    """L, mu, T are measured -> f1, c, B with uncertainties."""
    out = string_network(fret, core_fraction).solve(measured_dict={
        "L": (L, dex(SIGMA_L / L)), "mu": (mu, dex(SIGMA_MU_REL)), "T": (T, dex(SIGMA_T / T)),
    })
    return out


def tune_string_model(L, mu, target, core_fraction=1.0):
    """L, mu and the target pitch are measured -> the tension that gives that pitch (open string)."""
    out = string_network(0, core_fraction).solve(measured_dict={
        "L": (L, dex(SIGMA_L / L)), "mu": (mu, dex(SIGMA_MU_REL)), "f1": (target, 1e-9),
    })
    return out


# ============================================================
# GRM NETWORK OF THE ATTACK: the pick (or the finger) meets the string
# ============================================================
#   pluck point        x = p * L_eff,  x_r = L_eff - x
#   string stiffness   k_s = T * L_eff / (x * x_r)            (sideways, at the pluck point)
#   release height     y0 = F / k_s                           (louder when the force is larger)
#   pick stiffness     k_c = E_p * b * t^3 / (4 * l^3)        (the pick tip bends like a small beam)
#   finger stiffness   k_c = K_FLESH                          (the flesh of the fingertip)
#   mass in contact    m_c = mu * w                           (w: width of string touched)
#   release time       tau = pi * sqrt(m_c / k_c)             (how fast the string slips off)
#   brightness limit   f_c = 1 / (2 pi tau)                   (partials above f_c are softened)
#   click energy       E_c = F^2 / (2 k_c)                    (snap of the pick as it lets go)
PICK_E = 2.5e9          # Pa, plastic of a pick (hypothesis)
PICK_TIP_WIDTH = 0.005  # m, width of the tip that bends (hypothesis)
PICK_FREE = 0.004       # m, free length of the tip beyond the fingers (hypothesis)
PICK_CONTACT = 0.0015   # m, string length touched by the pick edge
K_FLESH = 2.0e3         # N/m, fingertip pulp, about 2 N per mm (hypothesis)
FINGER_CONTACT = 0.012  # m, string length touched by the fingertip
Y_REF = 0.003           # m, release height that gives gain 1


def pluck_network(mu, L, T, fret, p, force, technique, pick_mm):
    nodes = {n: {"guess": g} for n, g in {
        "mu": 1e-3, "L": 0.65, "Leff": 0.6, "T": 70.0, "p": 0.2, "x": 0.13, "xr": 0.5, "ks": 600.0,
        "F": 2.0, "y0": 0.003, "w": 0.002, "mc": 1e-5, "kc": 2e4, "tau": 1e-4, "fc": 2000.0, "Ec": 1e-4}.items()}
    rel = [
        {"name": "fret", "terms": {"Leff": 1, "L": -1}, "rhs": -fret * math.log10(2) / 12, "sigma": 1e-9},
        {"name": "pluck point", "terms": {"x": 1, "p": -1, "Leff": -1}, "rhs": 0.0, "sigma": 1e-9},
        {"name": "other side", "type": "sum", "terms": {"xr": 1, "Leff": -1, "x": 1}, "K": 0.0, "sigma": 1e-12},
        {"name": "string stiffness", "terms": {"ks": 1, "T": -1, "Leff": -1, "x": 1, "xr": 1}, "rhs": 0.0, "sigma": 1e-9},
        {"name": "release height", "terms": {"y0": 1, "F": -1, "ks": 1}, "rhs": 0.0, "sigma": 1e-9},
        {"name": "mass in contact", "terms": {"mc": 1, "mu": -1, "w": -1}, "rhs": 0.0, "sigma": 1e-9},
        {"name": "release time", "terms": {"tau": 1, "mc": -0.5, "kc": 0.5}, "rhs": math.log10(math.pi), "sigma": 1e-9},
        {"name": "brightness limit", "terms": {"fc": 1, "tau": 1}, "rhs": -math.log10(2 * math.pi), "sigma": 1e-9},
        {"name": "click energy", "terms": {"Ec": 1, "F": -2, "kc": 1}, "rhs": -math.log10(2), "sigma": 1e-9},
    ]
    measured = {"mu": (mu, 0.004), "L": (L, 3e-4), "T": (T, 0.003), "p": (p, 0.01), "F": (force, 0.02)}
    if technique == "pick":
        nodes.update({n: {"guess": g} for n, g in {"Ep": 2e9, "b": 0.005, "tp": 7e-4, "lp": 0.004}.items()})
        rel.append({"name": "pick tip", "terms": {"kc": 1, "Ep": -1, "b": -1, "tp": -3, "lp": 3},
                    "rhs": -math.log10(4), "sigma": 1e-9})
        measured.update({"Ep": (PICK_E, 0.04), "b": (PICK_TIP_WIDTH, 0.02), "tp": (pick_mm / 1000.0, 0.01),
                         "lp": (PICK_FREE, 0.04), "w": (PICK_CONTACT, 0.04)})
    else:
        measured.update({"kc": (K_FLESH, 0.1), "w": (FINGER_CONTACT, 0.04)})
    return GlobalRelationalNetwork(nodes, rel).solve(measured_dict=measured)


def partial_frequencies(f1, B, count):
    n = np.arange(1, count + 1, dtype=float)
    return n * f1 * np.sqrt(1.0 + B * n * n)


# ============================================================
# SOUND
# ============================================================

def pluck_amplitudes(count, pluck):
    """Fourier amplitudes of a string released from a triangle with its apex at `pluck` (0..1)."""
    n = np.arange(1, count + 1, dtype=float)
    p = float(np.clip(pluck, 0.02, 0.98))
    return 2.0 * np.sin(n * math.pi * p) / (n * n * math.pi * math.pi * p * (1.0 - p))


PALM_TAU = 0.16       # s, decay of the fundamental under the palm
PALM_CUTOFF = 350.0   # Hz, above this the palm damps the partials much faster


def synthesize_string(f1, B, duration, pluck, damping, brightness, sample_rate=SAMPLE_RATE, mute=False,
                      release_tau=0.0, click=0.0, seed=0):
    """Modal synthesis of one plucked stiff string. mute=True: palm mute (the side of the hand rests
    on the strings near the bridge: the note keeps its pitch but dies fast, its highs first)."""
    count_max = 80
    freqs = partial_frequencies(f1, B, count_max)
    keep = freqs < 0.45 * sample_rate
    freqs = freqs[keep]
    n = np.arange(1, len(freqs) + 1, dtype=float)
    # what the body feels is the force of the string on the bridge: n * (displacement amplitude),
    # in phase with a string released from rest (cosine); brightness only tilts it gently
    amps = n * pluck_amplitudes(len(freqs), pluck) * n ** (-(1.0 - brightness) * 0.6)
    if release_tau > 0:
        # the string slips off the pick or finger in a time tau: a ramp release softens f >~ 1 / tau
        amps = amps * np.sinc(freqs * release_tau)
    # higher partials die faster (air and internal losses grow with frequency)
    tau = damping / (1.0 + (freqs / 1800.0) ** 2)
    if mute:
        tau = np.minimum(tau, PALM_TAU / (1.0 + (freqs / PALM_CUTOFF) ** 2))
        amps = amps * np.exp(-n / 8.0)
    count = int(duration * sample_rate)
    t = np.arange(count) / sample_rate
    signal = np.zeros(count)
    peak = np.max(np.abs(amps)) if len(amps) else 1.0
    for f, a, ta in zip(freqs, amps, tau):  # partial by partial keeps memory low
        if abs(a) < 1e-4 * peak:
            continue                         # inaudible partial (e.g. a node at the pluck point)
        ta = max(ta, 0.02)
        m = min(count, int(9.2 * ta * sample_rate) + 1)   # stop once it has decayed by 80 dB
        tt = t[:m]
        signal[:m] += a * np.cos(2.0 * math.pi * f * tt) * np.exp(-tt / ta)
    # the onset is the release itself: its sharpness comes only from release_tau (pick or finger)
    signal -= signal[0] * np.exp(-np.arange(count) / max(release_tau * sample_rate, 1.0)) if count else 0.0
    if click > 0 and count > 0:                # snap of the pick edge: a very short bright burst
        m = min(count, int(0.004 * sample_rate))
        noise = np.random.default_rng(seed).standard_normal(m)
        burst = (noise - np.convolve(noise, np.ones(4) / 4, mode="same")) * np.exp(-np.arange(m) / (0.0008 * sample_rate))
        signal[:m] += click * burst
    return signal


def synthesize_mix(voices, duration, pluck, damping, brightness, strum_delay):
    """voices: list of (f1, B). Returns float32 normalised mix."""
    total = int((duration + strum_delay * max(len(voices) - 1, 0)) * SAMPLE_RATE)
    mix = np.zeros(total)
    for k, (f1, B) in enumerate(voices):
        s = synthesize_string(f1, B, duration, pluck, damping, brightness)
        start = int(k * strum_delay * SAMPLE_RATE)
        mix[start:start + len(s)] += s[: total - start]
    peak = np.max(np.abs(mix)) if len(mix) else 0.0
    if peak > 0:
        mix /= peak
    return mix.astype(np.float32)


# ============================================================
# GRM NETWORK OF A FINGER SLIDING ON A WOUND STRING
# ============================================================
# The finger rubs across the winding: every turn of wire it crosses is a small shock, so the squeak
# sings at f = v / p (v: finger speed, p: winding wire diameter, the pitch of the turns).
#   equivalent diameter  d_eq^2 = 4 mu / (pi rho)        core   d_core = k d_eq
#   outer diameter       D^2 = d_eq^2 / fill             wire   2 p = D - d_core
#   stopped lengths      L_i = L 2^(-fret_i / 12)        slide  dx = |L_1 - L_2|
#   speed v = dx / dt    squeak f = v / p                friction power P = mu_f N v
WIND_FILL = 0.8     # share of the outer section filled with metal (hypothesis)
MU_FRICTION = 0.3   # finger skin on steel (hypothesis)
LIFT_DX = 0.02      # m: the finger rolls off a string it leaves (no slide to another fret)


def squeak_network(mu, L, core_fraction, fret_from, fret_to, dt, force):
    nodes = {n: {"guess": g} for n, g in {
        "mu": 1e-3, "deq": 5e-4, "dcore": 3e-4, "D": 6e-4, "p": 2e-4, "L": 0.65, "L1": 0.6, "L2": 0.5,
        "dx": 0.03, "dt": 0.1, "v": 0.3, "fsq": 1500.0, "N": 0.5, "P": 0.05}.items()}
    rel = [
        {"name": "equivalent diameter", "terms": {"deq": 2, "mu": -1}, "rhs": math.log10(4 / (math.pi * RHO_STEEL)), "sigma": 1e-9},
        {"name": "core", "terms": {"dcore": 1, "deq": -1}, "rhs": math.log10(core_fraction), "sigma": 1e-9},
        {"name": "outer diameter", "terms": {"D": 2, "deq": -2}, "rhs": -math.log10(WIND_FILL), "sigma": 1e-9},
        {"name": "winding wire", "type": "sum", "terms": {"p": 2, "D": -1, "dcore": 1}, "K": 0.0, "sigma": 1e-12},
        {"name": "speed", "terms": {"v": 1, "dx": -1, "dt": 1}, "rhs": 0.0, "sigma": 1e-9},
        {"name": "squeak pitch", "terms": {"fsq": 1, "v": -1, "p": 1}, "rhs": 0.0, "sigma": 1e-9},
        {"name": "friction power", "terms": {"P": 1, "N": -1, "v": -1}, "rhs": math.log10(MU_FRICTION), "sigma": 1e-9},
    ]
    measured = {"mu": (mu, 0.004), "L": (L, 3e-4), "dt": (dt, 0.01), "N": (force, 0.05)}
    if fret_from > 0 and fret_to > 0:     # slide from one fret to another
        sign = 1.0 if fret_to > fret_from else -1.0   # L1 > L2 when moving up the neck
        rel += [
            {"name": "from", "terms": {"L1": 1, "L": -1}, "rhs": -fret_from * math.log10(2) / 12, "sigma": 1e-9},
            {"name": "to", "terms": {"L2": 1, "L": -1}, "rhs": -fret_to * math.log10(2) / 12, "sigma": 1e-9},
            {"name": "slide", "type": "sum", "terms": {"dx": 1, "L1": -sign, "L2": sign}, "K": 0.0, "sigma": 1e-12},
        ]
    else:                                  # the finger rolls off the string
        measured["dx"] = (LIFT_DX, 0.05)
        del nodes["L1"], nodes["L2"]
    return GlobalRelationalNetwork(nodes, rel).solve(measured_dict=measured)


def synthesize_squeak(fsq, power, duration, f1, B, sample_rate=SAMPLE_RATE, seed=0):
    """The finger crosses the winding turns one by one: each crossing is a tiny shock (rate f = v / p,
    rising and falling with the finger speed). Each shock rings the string itself, so the shocks are
    passed through the string's own high partials (f_n = n f1 sqrt(1 + B n^2), from its GRM network):
    that is what makes the squeak sound like metal."""
    count = max(int(duration * sample_rate), 2)
    s = np.linspace(0.0, 1.0, count)
    rng = np.random.default_rng(seed)
    rate = np.clip(fsq * (math.pi / 2) * np.sin(math.pi * s), 1.0, 0.45 * sample_rate)
    rate *= 1.0 + 0.04 * np.convolve(rng.standard_normal(count), np.ones(200) / 200, mode="same")
    turns = np.cumsum(rate) / sample_rate
    shocks = np.zeros(count)
    idx = np.nonzero(np.diff(np.floor(turns)) > 0)[0] + 1
    env = np.sin(math.pi * s) ** 1.2
    shocks[idx] = env[idx] * (0.7 + 0.6 * rng.random(len(idx)))
    # resonator: the string's partials between 700 Hz and 10 kHz, each ringing ~20 ms
    n = np.arange(1, 400, dtype=float)
    fn = n * f1 * np.sqrt(1.0 + B * n * n)
    fn = fn[(fn > 700) & (fn < min(10000, 0.45 * sample_rate))]
    t = np.arange(int(0.06 * sample_rate)) / sample_rate
    h = np.zeros_like(t)
    for k, f in enumerate(fn):
        h += np.sin(2 * math.pi * f * t) * np.exp(-t / 0.02) / math.sqrt(k + 1)
    h /= np.sqrt(np.sum(h * h)) + 1e-12
    m = count + len(h) - 1
    nfft = 1 << (m - 1).bit_length()
    ring = np.fft.irfft(np.fft.rfft(shocks, nfft) * np.fft.rfft(h, nfft), nfft)[:count]
    hiss = rng.standard_normal(count)
    hiss = (hiss - np.convolve(hiss, np.ones(3) / 3, mode="same")) * env * 0.08  # skin on metal
    level = 0.25 * math.sqrt(max(power, 0.0) / 0.05)
    return level * (ring + hiss)


def render_notes(notes, total, pluck, damping, brightness, squeaks=()):
    """notes: dicts with f1, B, start, length (s), muted (bool), gain. Each note rings for `length`
    then fades out in 15 ms (a string struck again stops its previous vibration)."""
    mix = np.zeros(int(total * SAMPLE_RATE) + 1)
    release = int(0.015 * SAMPLE_RATE)
    for nt in notes:
        if nt["muted"]:  # palm mute: same pitch, short and dark
            s = synthesize_string(nt["f1"], nt["B"], min(nt["length"], 0.8), pluck, damping, brightness, mute=True,
                                  release_tau=nt.get("tau", 0.0), click=nt.get("click", 0.0), seed=len(mix) % 997)
        else:
            s = synthesize_string(nt["f1"], nt["B"], nt["length"], pluck, damping, brightness,
                                  release_tau=nt.get("tau", 0.0), click=nt.get("click", 0.0),
                                  seed=int(nt["start"] * 1000) % 997)
        k = min(release, len(s))
        s[len(s) - k:] *= np.linspace(1.0, 0.0, k)
        start = int(nt["start"] * SAMPLE_RATE)
        end = min(start + len(s), len(mix))
        mix[start:end] += nt["gain"] * s[: end - start]
    for k, sq in enumerate(squeaks):
        s = synthesize_squeak(sq["fsq"], sq["P"], sq["dur"], sq["f1"], sq["B"], seed=k)
        start = max(int(sq["start"] * SAMPLE_RATE), 0)
        end = min(start + len(s), len(mix))
        mix[start:end] += s[: end - start]
    peak = np.max(np.abs(mix)) if len(mix) else 0.0
    if peak > 0:
        mix /= peak
    return mix.astype(np.float32)


# ============================================================
# GRM NETWORK OF THE BODY: the air in the box meets the wooden top
# ============================================================
# Air cavity (Helmholtz resonator)   f_H = c_air / (2 pi) * sqrt(A / (V * l_neck)),  l_neck = t + 1.7 r
# Top plate (clamped disc, 1st mode) f_T = 10.21 / (2 pi a^2) * h * sqrt(E / (12 rho (1 - nu^2)))
# Coupling: the two oscillators push each other apart into the two lowest body resonances
#   f_lo, f_hi^2 = ((f_H^2 + f_T^2) -/+ sqrt((f_H^2 - f_T^2)^2 + 4 k^2 f_H^2 f_T^2)) / 2
# Higher top modes follow the ratios of the clamped-disc eigenvalues.
# Radiation: a top of radius a moving the air radiates well only above f_rad = c_air / (2 pi a) (ka = 1);
# below, the radiated pressure falls in proportion to f / f_rad.
# Body dimensions and wood values are typical figures, not measurements of a given guitar.
GAMMA_AIR, R_GAS, M_AIR, T_AIR = 1.4, 8.314462618, 0.028965, 293.15
NU_WOOD = 0.3
PLATE_RATIOS = [21.26 / 10.21, 34.88 / 10.21, 39.77 / 10.21, 51.04 / 10.21, 60.82 / 10.21]
BODY_DEFAULT = {"V": 0.016, "r": 0.05, "t": 0.0028, "a": 0.17, "h": 0.0028, "E": 1.0e10, "rho": 430.0}


def coupled(fh, ft, k, sign):
    s_ = fh * fh + ft * ft
    d = math.sqrt((fh * fh - ft * ft) ** 2 + 4 * k * k * fh * fh * ft * ft)
    return math.sqrt(max((s_ + sign * d) / 2.0, 1e-12))


def body_network(size=1.0, top_mm=2.8, coupling=0.35):
    k = coupling
    nodes = {n: {"guess": g} for n, g in {
        "Tair": T_AIR, "cair": 340.0, "V": 0.02, "r": 0.05, "A": 0.008, "t": 0.003, "lneck": 0.09, "fH": 120.0,
        "a": 0.17, "h": 0.003, "E": 1e10, "rho": 450.0, "fT": 200.0, "f_lo": 100.0, "f_hi": 220.0,
        "frad": 300.0}.items()}
    nodes["Tair"]["fixed"] = True
    for j in range(len(PLATE_RATIOS)):
        nodes[f"f{j + 3}"] = {"guess": 400.0}
    rel = [
        {"name": "speed of sound", "terms": {"cair": 2, "Tair": -1}, "rhs": math.log10(GAMMA_AIR * R_GAS / M_AIR), "sigma": 1e-9},
        {"name": "sound hole area", "terms": {"A": 1, "r": -2}, "rhs": math.log10(math.pi), "sigma": 1e-9},
        {"name": "neck of air", "type": "sum", "terms": {"lneck": 1, "t": -1, "r": -1.7}, "K": 0.0, "sigma": 1e-9},
        {"name": "Helmholtz", "terms": {"fH": 1, "cair": -1, "A": -0.5, "V": 0.5, "lneck": 0.5},
         "rhs": -math.log10(2 * math.pi), "sigma": 1e-9},
        {"name": "top plate", "terms": {"fT": 1, "a": 2, "h": -1, "E": -0.5, "rho": 0.5},
         "rhs": math.log10(10.21 / (2 * math.pi) / math.sqrt(12 * (1 - NU_WOOD ** 2))), "sigma": 1e-9},
        {"name": "radiation", "terms": {"frad": 1, "cair": -1, "a": 1}, "rhs": -math.log10(2 * math.pi), "sigma": 1e-9},
        {"name": "air / top, low", "type": "fn", "nodes": ["f_lo", "fH", "fT"],
         "f": lambda v: math.log10(v["f_lo"]) - math.log10(coupled(v["fH"], v["fT"], k, -1)), "sigma": 1e-9},
        {"name": "air / top, high", "type": "fn", "nodes": ["f_hi", "fH", "fT"],
         "f": lambda v: math.log10(v["f_hi"]) - math.log10(coupled(v["fH"], v["fT"], k, +1)), "sigma": 1e-9},
    ]
    for j, ratio in enumerate(PLATE_RATIOS):
        rel.append({"name": f"top mode {j + 3}", "terms": {f"f{j + 3}": 1, "fT": -1}, "rhs": math.log10(ratio), "sigma": 1e-9})
    b = BODY_DEFAULT
    measured = {"V": (b["V"] * size ** 3, 0.01), "r": (b["r"] * size, 0.01), "t": (b["t"], 0.02),
                "a": (b["a"] * size, 0.01), "h": (top_mm / 1000.0, 0.02), "E": (b["E"], 0.05), "rho": (b["rho"], 0.02)}
    return GlobalRelationalNetwork(nodes, rel).solve(measured_dict=measured)


def body_modes(size=1.0, top_mm=2.8, coupling=0.35):
    """(frequency, gain, quality factor) of the body resonances, frequencies from the GRM network."""
    v = body_network(size, top_mm, coupling)["values"]
    freqs = [v["f_lo"], v["f_hi"]] + [v[f"f{j + 3}"] for j in range(len(PLATE_RATIOS))]
    gains = [0.9, 1.0, 0.55, 0.45, 0.35, 0.25, 0.18]
    qs = [16, 22, 25, 28, 30, 32, 35]
    return list(zip(freqs, gains, qs)), v


def body_impulse(modes, length=0.35):
    t = np.arange(int(length * SAMPLE_RATE)) / SAMPLE_RATE
    h = np.zeros_like(t)
    for f, g, q in modes:
        h += g * np.sin(2 * math.pi * f * t) * np.exp(-math.pi * f * t / q)
    return h / np.sqrt(np.sum(h * h))


def apply_body(audio, amount, modes, f_rad):
    """Strings heard through the body (FFT convolution with the body resonances), mixed with the bare
    strings, then radiated by the top: pressure ~ ka / sqrt(1 + (ka)^2), ka = f / f_rad."""
    if len(audio) == 0:
        return audio
    h = body_impulse(modes)
    n = len(audio) + len(h) - 1
    nfft = 1 << (n - 1).bit_length()
    spec = np.fft.rfft(audio, nfft)
    wet_spec = spec * np.fft.rfft(h, nfft)
    dry_rms = np.sqrt(np.sum(np.abs(spec) ** 2)) + 1e-12
    wet_rms = np.sqrt(np.sum(np.abs(wet_spec) ** 2)) + 1e-12
    mix = (1.0 - amount) * spec + amount * wet_spec * (dry_rms / wet_rms)
    f = np.fft.rfftfreq(nfft, 1.0 / SAMPLE_RATE)
    ka = f / f_rad
    mix *= ka / np.sqrt(1.0 + ka * ka)
    return np.fft.irfft(mix, nfft)[: len(audio)]


def write_wav(path, audio):
    data = (np.clip(audio, -1.0, 1.0) * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(data.tobytes())


# ============================================================
# INTERFACE
# ============================================================

BG = "#0d1117"
GRID = "#21262d"
TEXT = "#8b949e"
WAVE = "#58a6ff"
STRING_COLORS = ["#d29922", "#d29922", "#d29922", "#c9d1d9", "#c9d1d9", "#c9d1d9"]


class GRMGuitarApp:
    def __init__(self, root):
        self.root = root
        self.root.title("GRM Guitar — six strings computed by the Global Relational Model")
        self.root.geometry("1240x1000")
        self.root.minsize(1060, 820)

        self.models = [None] * 6
        self.entries, self.fret_vars = [], []
        self.freq_labels, self.cents_labels = [], []

        self.pluck = tk.DoubleVar(value=0.22)
        self.damping = tk.DoubleVar(value=1.2)
        self.brightness = tk.DoubleVar(value=0.6)
        self.duration = tk.DoubleVar(value=3.0)
        self.volume = tk.DoubleVar(value=0.7)
        self.core = tk.DoubleVar(value=0.45)
        self.stiff = tk.BooleanVar(value=True)
        self.chord = tk.StringVar(value="Open")
        self.status = tk.StringVar(value="Ready.")
        self.strum_ms = tk.DoubleVar(value=18.0)
        self.body_amount = tk.DoubleVar(value=0.6)
        self.body_size = tk.DoubleVar(value=1.0)
        self.palm = tk.BooleanVar(value=False)
        self.loop = tk.BooleanVar(value=True)
        self.loop_len = None
        self.top_mm = tk.DoubleVar(value=2.8)
        self.coupling = tk.DoubleVar(value=0.35)
        self.finger_force = tk.DoubleVar(value=0.6)
        self.squeak_on = tk.BooleanVar(value=True)
        self.technique = tk.StringVar(value="Pick")
        self.force = tk.DoubleVar(value=2.0)
        self.pick_mm = tk.DoubleVar(value=0.71)
        self.seq_mode = tk.StringVar(value="Strum")
        self.arp_pattern = tk.StringVar(value="Up and down")
        self.squeaks_shown = []
        self.last_frets = {}
        self.bpm = tk.IntVar(value=90)
        self.repeats = tk.IntVar(value=2)
        self.step_vars, self.dir_vars, self.dir_buttons = [], [], []
        self._model_cache = {}

        self.audio = None
        self.play_t0 = None
        self.voices_shown = []      # notes of the last play (dicts from note())
        self.anim_job = None

        self._build_ui()
        self.recalculate_all()
        self._animate()
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    # ---------------------------------------------------------------- layout
    def _build_ui(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        header = ttk.Frame(self.root, padding=(12, 10, 12, 0))
        header.pack(fill="x")
        ttk.Label(header, text="GRM GUITAR", font=("Segoe UI", 20, "bold")).pack(anchor="w")
        ttk.Label(header, text="Each string is a network of relations solved by the GRM core: wave speed, fundamental, "
                               "fret, steel stiffness. The uncertainties of the inputs propagate all the way to the notes.",
                  font=("Segoe UI", 9)).pack(anchor="w", pady=(2, 0))

        main = ttk.Frame(self.root, padding=10)
        main.pack(fill="both", expand=True)

        # strings table
        table = ttk.LabelFrame(main, text="Strings — inputs and network results", padding=8)
        table.pack(fill="x")
        heads = ["String", "Note", "Length L (m)", "Mass μ (kg/m)", "Tension T (N)", "Fret",
                 "GRM frequency", "Offset from the note", "", ""]
        for col, h in enumerate(heads):
            ttk.Label(table, text=h, font=("Segoe UI", 9, "bold")).grid(row=0, column=col, padx=4, pady=4, sticky="w")
        for i, spec in enumerate(STRINGS):
            r = i + 1
            ttk.Label(table, text=f"{spec['number']} · {spec['name']}").grid(row=r, column=0, padx=4, sticky="w")
            ttk.Label(table, text=spec["note"]).grid(row=r, column=1, padx=4)
            vars_row = [tk.StringVar(value=str(spec["L"])), tk.StringVar(value=f"{spec['mu']:.10f}"),
                        tk.StringVar(value=f"{spec['T']:.2f}")]
            self.entries.append(vars_row)
            for col, (var, width) in enumerate(zip(vars_row, [10, 14, 9]), start=2):
                e = ttk.Entry(table, textvariable=var, width=width)
                e.grid(row=r, column=col, padx=4, pady=2)
                e.bind("<Return>", lambda _e: self.recalculate_all())
            fret = tk.IntVar(value=0)
            self.fret_vars.append(fret)
            ttk.Spinbox(table, from_=0, to=19, textvariable=fret, width=4,
                        command=self.recalculate_all).grid(row=r, column=5, padx=4)
            fl = ttk.Label(table, text="—", width=18, font=("Segoe UI", 9, "bold"))
            fl.grid(row=r, column=6, padx=4, sticky="w")
            self.freq_labels.append(fl)
            cl = ttk.Label(table, text="—", width=18)
            cl.grid(row=r, column=7, padx=4, sticky="w")
            self.cents_labels.append(cl)
            ttk.Button(table, text="Play", width=7, command=lambda k=i: self.play([k])).grid(row=r, column=8, padx=2)
            ttk.Button(table, text="Tune", width=9, command=lambda k=i: self.tune([k])).grid(row=r, column=9, padx=2)

        bar = ttk.Frame(table)
        bar.grid(row=7, column=0, columnspan=10, sticky="ew", pady=(8, 0))
        ttk.Button(bar, text="Recompute the six networks", command=self.recalculate_all).pack(side="left", padx=2)
        ttk.Button(bar, text="Tune the six strings", command=lambda: self.tune(range(6))).pack(side="left", padx=2)
        ttk.Label(bar, text="   Chord:").pack(side="left")
        cb = ttk.Combobox(bar, textvariable=self.chord, values=list(CHORDS), state="readonly", width=10)
        cb.pack(side="left", padx=4)
        cb.bind("<<ComboboxSelected>>", lambda _e: self.apply_chord())

        # controls
        book = ttk.Notebook(main)
        book.pack(fill="x", pady=8)
        controls = ttk.Frame(book, padding=8)
        book.add(controls, text="Playing and synthesis")
        seq = ttk.Frame(book, padding=8)
        book.add(seq, text="Sequencer")
        self._build_sequencer(seq)
        sliders = [
            ("Pluck point", self.pluck, 0.05, 0.5, 0.01),
            ("Resonance (s)", self.damping, 0.2, 4.0, 0.1),
            ("Brightness", self.brightness, 0.0, 1.0, 0.05),
            ("Duration (s)", self.duration, 1.0, 8.0, 0.5),
            ("Volume", self.volume, 0.05, 1.0, 0.05),
            ("Wound core", self.core, 0.2, 1.0, 0.05),
            ("Strum speed (ms)", self.strum_ms, 4.0, 60.0, 1.0),
            ("Body", self.body_amount, 0.0, 1.0, 0.05),
            ("Body size", self.body_size, 0.7, 1.4, 0.05),
            ("Top (mm)", self.top_mm, 2.0, 4.0, 0.1),
            ("Air / top", self.coupling, 0.0, 0.8, 0.05),
            ("Sliding finger (N)", self.finger_force, 0.1, 2.0, 0.05),
            ("Pluck force (N)", self.force, 0.3, 5.0, 0.1),
            ("Pick (mm)", self.pick_mm, 0.4, 1.5, 0.01),
        ]
        row = ttk.Frame(controls)
        row.pack(fill="x")
        for k, (label, var, lo, hi, res) in enumerate(sliders):
            f = ttk.Frame(row)
            f.grid(row=k // 7, column=k % 7, padx=4, sticky="ew")
            row.columnconfigure(k % 7, weight=1)
            ttk.Label(f, text=label).pack(anchor="w")
            s = tk.Scale(f, variable=var, from_=lo, to=hi, resolution=res, orient="horizontal", length=120)
            s.pack(fill="x")
            if var is self.core:
                s.configure(command=lambda _v: self.recalculate_all())
        actions = ttk.Frame(controls)
        actions.pack(fill="x", pady=(8, 0))
        ttk.Button(actions, text="▶ Play chord", command=lambda: self.play(self.chord_strings())).pack(side="left", padx=3)
        ttk.Button(actions, text="▼ Strum down",
                   command=lambda: self.play(self.chord_strings(), strum=self.strum_ms.get() / 1000.0)).pack(side="left", padx=3)
        ttk.Button(actions, text="▲ Strum up",
                   command=lambda: self.play(self.chord_strings(), strum=self.strum_ms.get() / 1000.0, up=True)).pack(side="left", padx=3)
        ttk.Button(actions, text="♫ Arpeggio", command=lambda: self.play(self.chord_strings(), strum=0.12)).pack(side="left", padx=3)
        ttk.Button(actions, text="■ Stop", command=self.stop).pack(side="left", padx=3)
        ttk.Button(actions, text="Export the last sound (WAV)", command=self.export_wav).pack(side="left", padx=12)
        options = ttk.Frame(controls)
        options.pack(fill="x", pady=(6, 0))
        ttk.Label(options, text="Attack:").pack(side="left", padx=(3, 4))
        for label in ("Pick", "Fingers"):
            ttk.Radiobutton(options, text=label, value=label, variable=self.technique).pack(side="left", padx=4)
        ttk.Checkbutton(options, text="Steel stiffness", variable=self.stiff).pack(side="left", padx=(18, 12))
        ttk.Checkbutton(options, text="Palm mute", variable=self.palm).pack(side="left", padx=12)
        ttk.Checkbutton(options, text="Finger noise on wound strings", variable=self.squeak_on).pack(side="left", padx=12)

        # visuals
        bottom = ttk.Frame(main)
        bottom.pack(fill="both", expand=True)
        left = ttk.LabelFrame(bottom, text="The strings moving (slowed down ×100, exaggerated amplitude)", padding=6)
        left.pack(side="left", fill="both", expand=True, padx=(0, 5))
        self.neck = tk.Canvas(left, bg=BG, height=260, highlightthickness=0)
        self.neck.pack(fill="both", expand=True)
        right = ttk.Frame(bottom)
        right.pack(side="left", fill="both", expand=True, padx=(5, 0))
        osc = ttk.LabelFrame(right, text="Oscilloscope", padding=6)
        osc.pack(fill="both", expand=True)
        self.scope = tk.Canvas(osc, bg=BG, height=120, highlightthickness=0)
        self.scope.pack(fill="both", expand=True)
        diag = ttk.LabelFrame(right, text="Relational diagnostics", padding=6)
        diag.pack(fill="both", expand=True, pady=(6, 0))
        self.diag = tk.Text(diag, height=8, wrap="word", font=("Consolas", 9))
        self.diag.pack(fill="both", expand=True)

        ttk.Label(main, textvariable=self.status, font=("Segoe UI", 9)).pack(anchor="w", pady=(6, 0))

    # ---------------------------------------------------------------- GRM
    def read_inputs(self, i):
        try:
            L, mu, T = (float(v.get().replace(",", ".")) for v in self.entries[i])
        except ValueError:
            raise ValueError(f"Invalid values for string {STRINGS[i]['number']}.")
        if min(L, mu, T) <= 0:
            raise ValueError(f"The values of string {STRINGS[i]['number']} must be positive.")
        return L, mu, T

    def core_fraction(self, i):
        return float(self.core.get()) if STRINGS[i]["wound"] else 1.0

    def recalculate_all(self):
        lines = [f"{'string':<10}{'f1 (Hz)':>10}{'± cents':>9}{'c (m/s)':>10}{'B':>10}{'10th partial':>13}  converged"]
        try:
            for i, spec in enumerate(STRINGS):
                L, mu, T = self.read_inputs(i)
                fret = int(self.fret_vars[i].get())
                out = play_string_model(L, mu, T, fret, self.core_fraction(i))
                self.models[i] = out
                v, s = out["values"], out["sigma_dex"]
                f1, B = v["f1"], v["B"]
                sigma_cents = s["f1"] * CENTS_PER_DEX
                target = spec["target"] * 2 ** (fret / 12.0)
                cents = 1200.0 * math.log2(f1 / target)
                cents = 0.0 if abs(cents) < 0.05 else cents
                self.freq_labels[i].config(text=f"{f1:8.2f} Hz ± {sigma_cents:.0f} c")
                mark = "in tune" if abs(cents) < max(3.0, sigma_cents) else ("sharp" if cents > 0 else "flat")
                self.cents_labels[i].config(text=f"{cents:+6.1f} cents · {mark}")
                stretch = 1200.0 * math.log2(math.sqrt(1.0 + 100.0 * B))
                lines.append(f"{spec['note'] + ' c' + str(fret):<10}{f1:>10.2f}{sigma_cents:>9.1f}{v['c']:>10.1f}"
                             f"{B:>10.1e}{stretch:>10.1f} c  {out['converged']}")
            lines.append("")
            lines.append("± cents: uncertainty propagated by the network (L ±0.5 mm, μ ±1 %, T ±0.5 N).")
            lines.append("10th partial: shift due to stiffness, f_n = n·f1·√(1 + B n²).")
            modes, bv = body_modes(float(self.body_size.get()), float(self.top_mm.get()), float(self.coupling.get()))
            lines.append("")
            lines.append(f"Body (GRM network): air alone {bv['fH']:.0f} Hz, top alone {bv['fT']:.0f} Hz "
                         f"-> together {bv['f_lo']:.0f} and {bv['f_hi']:.0f} Hz; then "
                         + ", ".join(f"{f:.0f}" for f, _, _ in modes[2:]) + " Hz. "
                         f"The top radiates well above {bv['frad']:.0f} Hz (ka = 1), less below.")
            L5, mu5, _ = self.read_inputs(1)
            sq = squeak_network(mu5, L5, self.core_fraction(1), 2, 3, 0.1, float(self.finger_force.get()))["values"]
            L6, mu6, T6 = self.read_inputs(0)
            for tech, name in (("pick", f"{float(self.pick_mm.get()):.2f} mm pick"), ("finger", "finger")):
                a = pluck_network(mu6, L6, T6, 0, float(self.pluck.get()), float(self.force.get()), tech,
                                  float(self.pick_mm.get()))["values"]
                lines.append(f"Attack (GRM network), low E, {name}: contact stiffness {a['kc']:.2g} N/m, "
                             f"the string slips off in {a['tau'] * 1e3:.3f} ms -> highs softened above {a['fc']:.0f} Hz; "
                             f"string pulled {a['y0'] * 1e3:.1f} mm aside.")
            lines.append(f"Squeak (GRM network), A string from fret 2 to 3 in 0.1 s: {sq['p'] * 1e3:.2f} mm winding wire, "
                         f"finger at {sq['v']:.2f} m/s -> {sq['fsq']:.0f} Hz, {sq['P'] * 1e3:.0f} mW of friction.")
            self.diag.delete("1.0", tk.END)
            self.diag.insert("1.0", "\n".join(lines))
            self.status.set("Six GRM networks computed.")
        except Exception as exc:
            messagebox.showerror("GRM error", str(exc))

    def tune(self, indices):
        try:
            done = []
            for i in indices:
                L, mu, _ = self.read_inputs(i)
                out = tune_string_model(L, mu, STRINGS[i]["target"], self.core_fraction(i))
                T, sT = out["values"]["T"], out["uncertainty"]["T"] * out["values"]["T"]
                self.entries[i][2].set(f"{T:.2f}")
                done.append(f"{STRINGS[i]['note']}: T = {T:.2f} ± {sT:.2f} N")
            self.recalculate_all()
            self.status.set("Tuned by the network (the target pitch becomes the measurement, the tension the unknown) — " + " · ".join(done))
        except Exception as exc:
            messagebox.showerror("GRM error", str(exc))

    def apply_chord(self):
        shape = CHORDS[self.chord.get()]
        for i, f in enumerate(shape):
            self.fret_vars[i].set(0 if f is None else f)
        self.recalculate_all()

    def chord_strings(self):
        shape = CHORDS[self.chord.get()]
        return [i for i, f in enumerate(shape) if f is not None]

    # ---------------------------------------------------------------- sound
    def string_model(self, i, fret):
        """GRM result for string i at a given fret (cached until the inputs change)."""
        L, mu, T = self.read_inputs(i)
        key = (i, fret, L, mu, T, self.core_fraction(i))
        if key not in self._model_cache:
            self._model_cache[key] = play_string_model(L, mu, T, fret, self.core_fraction(i))
        return self._model_cache[key]["values"]

    def attack_model(self, i, fret, force):
        """GRM attack of string i: release height, release time, click (cached)."""
        L, mu, T = self.read_inputs(i)
        tech = "pick" if self.technique.get() == "Pick" else "finger"
        key = ("attack", i, fret, L, mu, T, round(float(self.pluck.get()), 3), round(force, 3), tech,
               round(float(self.pick_mm.get()), 3))
        if key not in self._model_cache:
            self._model_cache[key] = pluck_network(mu, L, T, fret, float(self.pluck.get()), force, tech,
                                                   float(self.pick_mm.get()))
        return self._model_cache[key]["values"], tech

    def note(self, i, fret, start, length, muted=False, force_factor=1.0):
        v = self.string_model(i, fret)
        B = v["B"] if self.stiff.get() else 0.0
        a, tech = self.attack_model(i, fret, float(self.force.get()) * force_factor)
        click = 0.08 * math.sqrt(a["Ec"] / 1e-4) if tech == "pick" else 0.0
        return {"i": i, "fret": fret, "f1": v["f1"], "B": B, "start": start, "length": length,
                "muted": muted, "gain": a["y0"] / Y_REF, "tau": a["tau"], "click": click}

    def squeak(self, i, fret_from, fret_to, start, dur):
        """GRM squeak of the finger leaving fret_from on wound string i (to fret_to, 0 = lifted)."""
        L, mu, _ = self.read_inputs(i)
        v = squeak_network(mu, L, self.core_fraction(i), fret_from, fret_to, dur, float(self.finger_force.get()))["values"]
        sv = self.string_model(i, fret_from)       # the string the finger rubs, as it is stopped
        return {"i": i, "start": start, "dur": dur, "fsq": v["fsq"], "P": v["P"], "from": fret_from, "to": fret_to,
                "f1": sv["f1"], "B": sv["B"]}

    def finger_moves(self, old, new, t_strike, lead, last_notes=None):
        """Squeaks for the wound strings whose finger leaves a fret before the next strike.
        old/new: {string index: fret}; the old note of a string stops when its finger moves."""
        out = []
        if not self.squeak_on.get():
            return out
        for i, f_old in old.items():
            if f_old <= 0 or not STRINGS[i]["wound"]:
                continue
            f_new = new.get(i, 0)
            if f_new == f_old:
                continue
            sq = self.squeak(i, f_old, f_new, t_strike - lead, lead * 0.85)
            out.append(sq)
            if last_notes and i in last_notes:
                prev = last_notes[i]
                prev["length"] = max(0.02, min(prev["length"], sq["start"] - prev["start"]))
        return out

    def play(self, indices, strum=0.0, up=False):
        indices = sorted(indices, reverse=up)  # index 0 is string 6: down = from the bass
        if not indices:
            return
        try:
            self.recalculate_all()
            dur = float(self.duration.get())
            frets = {i: int(self.fret_vars[i].get()) for i in indices}
            lead = 0.12
            squeaks = self.finger_moves(self.last_frets, frets, lead, lead)
            t0 = lead if squeaks else 0.0
            self.last_frets = frets
            factor = 0.75 if up else 1.0      # an upstroke is lighter
            notes = [self.note(i, frets[i], t0 + k * strum, dur, muted=self.palm.get(), force_factor=factor)
                     for k, i in enumerate(indices)]
            self.pending_squeaks = squeaks
            self.start_playback(notes, t0 + dur + strum * len(indices),
                                "Playing: " + " – ".join(STRINGS[i]["note"] for i in indices))
        except Exception as exc:
            messagebox.showerror("Audio error", str(exc))

    def start_playback(self, notes, total, label, loop_len=None, squeaks=None):
        """Render, pass through the body, then play once or (loop_len in s) in a seamless loop.
        For a loop the notes cover two passes; the second pass is kept: it already contains the
        tails of the first one, exactly as when the loop goes round."""
        if squeaks is None:
            squeaks, self.pending_squeaks = getattr(self, "pending_squeaks", []), []
        audio = render_notes(notes, total, self.pluck.get(), self.damping.get(), self.brightness.get(), squeaks)
        modes, bv = body_modes(float(self.body_size.get()), float(self.top_mm.get()), float(self.coupling.get()))
        audio = apply_body(audio.astype(float), float(self.body_amount.get()), modes, bv["frad"])
        if loop_len:
            n = int(round(loop_len * SAMPLE_RATE))
            audio = audio[n:2 * n]
            notes = [dict(nt, start=nt["start"] - loop_len) for nt in notes]
            squeaks = [dict(sq, start=sq["start"] - loop_len) for sq in squeaks]
        peak = np.max(np.abs(audio)) if len(audio) else 0.0
        if peak > 0:
            audio = audio / peak
        self.audio = (audio * float(self.volume.get())).astype(np.float32)
        self.voices_shown = notes
        self.squeaks_shown = squeaks
        self.loop_len = loop_len
        self.play_t0 = time.perf_counter()
        if sd is not None:
            sd.stop()
            sd.play(self.audio, SAMPLE_RATE, blocking=False, loop=bool(loop_len))
            self.status.set(label)
        else:
            self.status.set("No sound device (pip install sounddevice): animation only. The sound can still be exported as WAV.")

    # ---------------------------------------------------------------- sequencer
    STEPS = 16
    DIRS = ["↓", "↑", "x", "·"]   # strum down, strum up, palm-muted strum, let the strings ring
    PATTERNS = {
        "All down": "↓·↓·↓·↓·↓·↓·↓·↓·",
        "Folk ↓ ↓↑ ↑↓↑": "↓·↓↑·↑↓↑↓·↓↑·↑↓↑",
        "Eighths ↓↑": "↓↑↓↑↓↑↓↑↓↑↓↑↓↑↓↑",
        "Reggae (off-beat)": "·x·↓·x·↓·x·↓·x·↓",
        "Palm-muted rock": "xxx↓xxx↓xxx↓xx↓↑",
    }

    # arpeggio slots, one per step: B = bass (lowest string of the chord), B2 = next bass string,
    # 3 / 2 / 1 = treble strings (G, B, E); several digits = played together (a pinch)
    ARPEGGIOS = {
        "Up and down": ["B", "3", "2", "1", "2", "3", "2", "1"],
        "Travis (alternating bass)": ["B", "2", "B2", "1", "B", "2", "B2", "3"],
        "Bass + chord": ["B", "321", "B2", "321", "B", "321", "B2", "321"],
        "Ballad": ["B", "3", "2", "3", "1", "3", "2", "3"],
        "Pinch (bass + treble)": ["B1", "3", "2", "3", "B21", "3", "2", "3"],
    }

    @staticmethod
    def arpeggio_slot(content, slot):
        """Notes of a chord (list of (string index, fret)) chosen by an arpeggio slot."""
        by_string = dict(content)
        basses = [i for i in sorted(by_string) if i <= 2] or sorted(by_string)[:1]
        chosen = []
        token = slot
        if token.startswith("B2"):
            if len(basses) > 1:
                chosen.append(basses[1])
            token = token[2:]
        elif token.startswith("B"):
            chosen.append(basses[0])
            token = token[1:]
        for ch in token:                       # string 3 -> index 3, 2 -> 4, 1 -> 5
            i = 6 - int(ch)
            if i in by_string:
                chosen.append(i)
        return [(i, by_string[i]) for i in chosen]

    def _build_sequencer(self, frame):
        top = ttk.Frame(frame)
        top.pack(fill="x")
        ttk.Label(top, text="Tempo (BPM)").pack(side="left")
        ttk.Spinbox(top, from_=40, to=220, textvariable=self.bpm, width=5).pack(side="left", padx=(4, 14))
        ttk.Label(top, text="Repeats").pack(side="left")
        ttk.Spinbox(top, from_=1, to=8, textvariable=self.repeats, width=4).pack(side="left", padx=(4, 6))
        ttk.Checkbutton(top, text="Loop", variable=self.loop).pack(side="left", padx=(0, 14))
        ttk.Label(top, text="Mode").pack(side="left")
        ttk.Combobox(top, textvariable=self.seq_mode, values=["Strum", "Arpeggio"], state="readonly",
                     width=9).pack(side="left", padx=(4, 10))
        ttk.Label(top, text="Pattern").pack(side="left")
        ttk.Combobox(top, textvariable=self.arp_pattern, values=list(self.ARPEGGIOS), state="readonly",
                     width=19).pack(side="left", padx=(4, 10))
        ttk.Label(top, text="Rhythm").pack(side="left")
        pattern = tk.StringVar(value="Folk ↓ ↓↑ ↑↓↑")
        pcb = ttk.Combobox(top, textvariable=pattern, values=list(self.PATTERNS), state="readonly", width=20)
        pcb.pack(side="left", padx=4)
        pcb.bind("<<ComboboxSelected>>", lambda _e: self.apply_pattern(pattern.get()))
        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=(6, 0))
        ttk.Button(buttons, text="▶ Play the sequence", command=self.play_sequence).pack(side="left", padx=(0, 3))
        ttk.Button(buttons, text="■ Stop", command=self.stop).pack(side="left", padx=3)
        ttk.Button(buttons, text="Clear", command=self.clear_sequence).pack(side="left", padx=3)

        grid = ttk.Frame(frame)
        grid.pack(fill="x", pady=(8, 0))
        choices = ["—"] + list(CHORDS)
        demo = ["G"] * 4 + ["D"] * 4 + ["Em"] * 4 + ["C"] * 4
        for k in range(self.STEPS):
            cell = ttk.Frame(grid)
            cell.grid(row=k // 8, column=k % 8, padx=1, pady=3, sticky="w")
            ttk.Label(cell, text=f"{k + 1}", width=2, foreground="#6e7681").pack(side="left")
            var = tk.StringVar(value=demo[k])
            ttk.Combobox(cell, textvariable=var, values=choices, width=7).pack(side="left")
            d = tk.StringVar(value="↓")
            btn = ttk.Button(cell, textvariable=d, width=2, command=lambda k=k: self.cycle_dir(k))
            btn.pack(side="left", padx=(2, 0))
            self.step_vars.append(var)
            self.dir_vars.append(d)
        ttk.Label(frame, text="Arpeggio mode: each step plays one or two strings of the chord following the pattern "
                              "(B: bass, B2: second bass, 3-2-1: treble strings); the others keep ringing.",
                  font=("Segoe UI", 8)).pack(anchor="w", pady=(4, 0))
        ttk.Label(frame, text="Each step: a chord from the list, one or more notes written string:fret "
                              "(e.g. 6:3 5:2), or — for a rest. Button: ↓ strum down, "
                              "↑ strum up, x palm-muted strum, · let ring.",
                  font=("Segoe UI", 8)).pack(anchor="w", pady=(6, 0))
        self.apply_pattern("Folk ↓ ↓↑ ↑↓↑")

    def cycle_dir(self, k):
        d = self.dir_vars[k]
        d.set(self.DIRS[(self.DIRS.index(d.get()) + 1) % len(self.DIRS)])

    def apply_pattern(self, name):
        for k, ch in enumerate(self.PATTERNS[name][: self.STEPS]):
            self.dir_vars[k].set(ch)

    def clear_sequence(self):
        for v in self.step_vars:
            v.set("—")

    @staticmethod
    def parse_step(text):
        """Return a list of (string index, fret) or None for a rest."""
        text = text.strip()
        if not text or text in ("—", "-"):
            return None
        if text in CHORDS:
            return [(i, f) for i, f in enumerate(CHORDS[text]) if f is not None]
        notes = []
        for token in text.replace(",", " ").split():
            number, _, fret = token.partition(":")
            number, fret = int(number), int(fret or 0)
            if not 1 <= number <= 6 or not 0 <= fret <= 19:
                raise ValueError(f"invalid note: {token} (string 1 to 6, fret 0 to 19)")
            notes.append((6 - number, fret))
        return notes

    def play_sequence(self):
        try:
            self.recalculate_all()
            step_s = 60.0 / max(int(self.bpm.get()), 1) / 2.0       # steps are eighth notes
            strum = float(self.strum_ms.get()) / 1000.0
            steps = []
            for k in range(self.STEPS):
                steps.append((self.parse_step(self.step_vars[k].get()), self.dir_vars[k].get()))
            notes, last = [], {}          # last: string index -> its ringing note
            ring = float(self.duration.get())
            total = 0.0
            looping = bool(self.loop.get())
            passes = 3 if looping else max(int(self.repeats.get()), 1)   # loop: keep the middle pass
            squeaks, held = [], {}        # held: string index -> fret pressed by the last strike
            lead = min(0.14, 0.6 * step_s)
            for rep_ in range(passes):
                for k, (content, d) in enumerate(steps):
                    t0 = (rep_ * self.STEPS + k) * step_s
                    if content is None or d == "·":
                        continue          # rest, or the previous strum keeps ringing
                    single = len(content) == 1 or self.step_vars[k].get() not in CHORDS
                    new = dict(content)
                    if new != held:            # the hand changes shape: fingers leave their frets
                        squeaks += self.finger_moves(held, new, t0, lead, last)
                    held = new
                    arpeggio = self.seq_mode.get() == "Arpeggio" and not single
                    if arpeggio:               # one slot of the pattern; the other strings keep ringing
                        pattern = self.ARPEGGIOS[self.arp_pattern.get()]
                        order = self.arpeggio_slot(content, pattern[k % len(pattern)])
                    else:
                        order = sorted(content, key=lambda nf: nf[0], reverse=(d == "↑"))
                    for j, (i, fret) in enumerate(order):
                        start = t0 + (0.0 if (single or arpeggio) else j * strum)
                        if i in last:     # a string struck again stops ringing
                            prev = last[i]
                            prev["length"] = max(0.02, min(prev["length"], start - prev["start"]))
                        factor = 0.75 if d == "↑" else (0.85 if arpeggio else 1.0)
                        nt = self.note(i, fret, start, ring, muted=(d == "x"), force_factor=factor)
                        notes.append(nt)
                        last[i] = nt
                        total = max(total, start + ring)
            if not notes:
                messagebox.showinfo("Sequencer", "The sequence is empty.")
                return
            self.status.set("Rendering the sequence…")
            self.root.update_idletasks()
            if looping:
                self.start_playback(notes, max(total, 3 * self.STEPS * step_s), f"Looping sequence, {self.bpm.get()} BPM "
                                    "(■ Stop to end it)", loop_len=self.STEPS * step_s, squeaks=squeaks)
            else:
                self.start_playback(notes, total, f"Sequence: {self.STEPS} steps × {passes}, {self.bpm.get()} BPM",
                                    squeaks=squeaks)
        except Exception as exc:
            messagebox.showerror("Sequencer", str(exc))

    def stop(self):
        if sd is not None:
            try:
                sd.stop()
            except Exception:
                pass
        self.play_t0 = None
        self.status.set("Stopped.")

    def export_wav(self):
        if self.audio is None:
            messagebox.showinfo("Export", "Play a sound first.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".wav", filetypes=[("WAV", "*.wav")],
                                            initialfile="grm_guitar.wav")
        if path:
            audio = np.tile(self.audio, max(int(self.repeats.get()), 1)) if self.loop_len else self.audio
            write_wav(path, audio)
            self.status.set(f"Exported: {path}")

    # ---------------------------------------------------------------- drawing
    def _animate(self):
        elapsed = None if self.play_t0 is None else time.perf_counter() - self.play_t0
        if elapsed is not None and self.loop_len:
            elapsed %= self.loop_len
        elif elapsed is not None and self.audio is not None and elapsed > len(self.audio) / SAMPLE_RATE:
            self.play_t0, elapsed = None, None
        self.draw_neck(elapsed)
        self.draw_scope(elapsed)
        self.anim_job = self.root.after(33, self._animate)

    def draw_neck(self, elapsed):
        c = self.neck
        c.delete("all")
        w, h = max(c.winfo_width(), 300), max(c.winfo_height(), 160)
        x0, x1 = 40, w - 30                       # nut and bridge
        L = x1 - x0
        for k in range(1, 13):                    # frets
            xf = x0 + L * (1 - 2 ** (-k / 12.0))
            c.create_line(xf, 14, xf, h - 14, fill=GRID)
            if k in (3, 5, 7, 9, 12):
                c.create_text(xf - L * 0.015, h - 6, text=str(k), fill=TEXT, font=("Segoe UI", 7))
        c.create_line(x0, 10, x0, h - 10, fill=TEXT, width=3)
        c.create_line(x1, 10, x1, h - 10, fill=TEXT, width=2)
        active = {}
        if elapsed is not None:
            for nt in self.voices_shown:          # latest note of each string that has started
                if nt["start"] <= elapsed < nt["start"] + nt["length"]:
                    if nt["i"] not in active or nt["start"] > active[nt["i"]]["start"]:
                        active[nt["i"]] = nt
        held = {}                                 # during a sequence, the hand keeps the last chord
        if elapsed is not None:
            for nt in sorted(self.voices_shown, key=lambda n_: n_["start"]):
                if nt["start"] <= elapsed:
                    held[nt["i"]] = nt["fret"]
        gap = (h - 40) / 5.0
        slow = 100.0
        pts = 160
        for row in range(6):                      # string 1 at the top, as seen when playing
            i = 5 - row
            y = 20 + row * gap
            fret = active[i]["fret"] if i in active else held.get(i, int(self.fret_vars[i].get()))
            xs = x0 + L * (1 - 2 ** (-fret / 12.0))  # where the finger stops the string
            color = STRING_COLORS[i]
            width = 1 + (5 - row) * 0.35
            slide = None
            if elapsed is not None:
                for sq in self.squeaks_shown:
                    if sq["i"] == i and sq["start"] <= elapsed < sq["start"] + sq["dur"]:
                        slide = sq
            if slide is not None:                  # the finger travels (or rolls off): string at rest
                u_ = (elapsed - slide["start"]) / slide["dur"]
                u_ = 0.5 - 0.5 * math.cos(math.pi * u_)
                pa = 1 - 2 ** (-slide["from"] / 12.0)
                pb = 1 - 2 ** (-slide["to"] / 12.0) if slide["to"] > 0 else pa
                xf_ = x0 + L * (pa + (pb - pa) * u_)
                c.create_line(x0, y, x1, y, fill=color, width=width)
                r_ = 5 if slide["to"] > 0 else 5 * (1 - u_)
                c.create_oval(xf_ - r_, y - r_, xf_ + r_, y + r_, fill="#f0883e", outline="")
                c.create_text(12, y, text=STRINGS[i]["note"], fill="#f0883e", font=("Segoe UI", 8, "bold"))
                continue
            if fret > 0:
                c.create_line(x0, y, xs, y, fill=GRID, width=width)
                c.create_oval(xs - 5, y - 5, xs + 5, y + 5, fill="#3fb950", outline="")
            if i not in active:
                c.create_line(xs, y, x1, y, fill=color, width=width)
                c.create_text(12, y, text=STRINGS[i]["note"], fill=TEXT, font=("Segoe UI", 8))
                continue
            nt = active[i]
            f1, B, t = nt["f1"], nt["B"], elapsed - nt["start"]
            n = np.arange(1, 25, dtype=float)
            fn = partial_frequencies(f1, B, len(n))
            amps = pluck_amplitudes(len(n), self.pluck.get())
            tau = self.damping.get() / (1.0 + (fn / 1800.0) ** 2)
            if nt["muted"]:
                tau = np.minimum(tau, PALM_TAU / (1.0 + (fn / PALM_CUTOFF) ** 2))
            u = np.linspace(0.0, 1.0, pts)
            # standing waves seen in slow motion: real frequencies divided by `slow`
            phase = np.cos(2 * math.pi * fn * t / slow) * np.exp(-t / tau)
            disp = (amps * phase) @ np.sin(np.outer(n, u) * math.pi)
            amp = gap * 0.55
            coords = []
            for uu, dd in zip(u, disp):
                coords += [xs + (x1 - xs) * uu, y - dd * amp]
            c.create_line(*coords, fill=color, width=width, smooth=True)
            c.create_text(12, y, text=STRINGS[i]["note"], fill="#e6edf3", font=("Segoe UI", 8, "bold"))

    def draw_scope(self, elapsed):
        c = self.scope
        c.delete("all")
        w, h = max(c.winfo_width(), 200), max(c.winfo_height(), 80)
        mid = h / 2
        c.create_line(0, mid, w, mid, fill=GRID)
        c.create_text(8, 8, anchor="nw", text="OSCILLOSCOPE", fill=TEXT, font=("Segoe UI", 8, "bold"))
        if self.audio is None or elapsed is None:
            return
        start = int(elapsed * SAMPLE_RATE)
        chunk = self.audio[start:start + 1600]
        if len(chunk) < 2:
            return
        step = max(1, len(chunk) // w)
        coords = []
        for k in range(0, len(chunk), step):
            coords += [k / len(chunk) * w, mid - float(chunk[k]) * h * 0.45]
        c.create_line(*coords, fill=WAVE, width=1.4)

    def close(self):
        self.stop()
        if self.anim_job is not None:
            self.root.after_cancel(self.anim_job)
        self.root.destroy()


def main():
    root = tk.Tk()
    GRMGuitarApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
