# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Anthony Charretier
"""
GRM Guitar - six vibrating strings computed by the Global Relational Model core (grm.py).

Python 3.10+
Dependencies: numpy (required), sounddevice (optional, for sound; WAV export works without it)

A guitar is one object: every part is in relation with the others, and the whole of it vibrates.
Each meeting of two parts is a small relational network solved by grm.GlobalRelationalNetwork
(string and fret, pick and string, palm and string, finger and winding, string and bridge, bridge
and top, top and air, arm and tempo). One of them, the string:

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

LG10 = math.log10

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
        "Zs": {"guess": 0.5},
    }
    relations = [
        {"name": "wave speed", "terms": {"c": 2, "mu": 1, "T": -1}, "rhs": 0.0, "sigma": 1e-9},
        {"name": "fundamental", "terms": {"Leff": 1, "f1": 1, "c": -1}, "rhs": -math.log10(2.0), "sigma": 1e-9},
        {"name": "fret", "terms": {"Leff": 1, "L": -1}, "rhs": -fret * math.log10(2.0) / 12.0, "sigma": 1e-9},
        {"name": "steel core", "terms": {"d": 2, "mu": -1},
         "rhs": math.log10(4.0 * core_fraction ** 2 / (math.pi * RHO_STEEL)), "sigma": 1e-9},
        {"name": "stiffness", "terms": {"B": 1, "d": -4, "T": 1, "Leff": 2},
         "rhs": math.log10(math.pi ** 3 * E_STEEL / 64.0), "sigma": 1e-9},
        # how hard the string pushes on what holds it: wave impedance Zs = sqrt(T mu)
        {"name": "string impedance", "terms": {"Zs": 2, "T": -1, "mu": -1}, "rhs": 0.0, "sigma": 1e-9},
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


def pluck_amplitudes(count, pluck):
    """Fourier amplitudes of a string released from a triangle with its apex at `pluck` (0..1)."""
    n = np.arange(1, count + 1, dtype=float)
    p = float(np.clip(pluck, 0.02, 0.98))
    return 2.0 * np.sin(n * math.pi * p) / (n * n * math.pi * math.pi * p * (1.0 - p))


# ============================================================
# GRM NETWORK OF THE PALM: the side of the hand meets the strings near the bridge
# ============================================================
# The skin is a damper of strength r pressed at a distance x from the bridge. A mode n of the string
# (modal mass mu L_eff / 2) loses energy there in proportion to its own amplitude at x:
#   skin damping     r = R_SKIN * N                         (the harder the hand presses, the more it damps)
#   loss scale       s0 = r / (mu * L_eff)
#   position         q = x / L_eff
#   added decay rate of mode n:  sigma_n = s0 * sin^2(n pi q)
# Near the bridge, sin(n pi q) is small for the low modes and grows with n: the fundamental survives a
# little, the highs die within milliseconds, and a light string is muted more than a heavy one.
# The flesh is not only a damper: it has a mass and a spring, and each mode feels them where it moves:
#   mode n, modal mass m_n = mu L_eff / 2, share s_n = sin^2(n pi q) of its motion under the palm
#   decay      sigma_n = r s_n / (2 m_n)                                        (the damper)
#   frequency  w_n'^2 = (w_n^2 m_n + k_h s_n) / (m_n + m_h s_n)               (the spring and the mass)
# The higher a mode, the more it moves under the palm: the high modes are slowed, detuned, and damped faster
# than they vibrate (overdamped): they never ring. The low modes, whose motion near the bridge is tiny, keep
# their pitch: the chug keeps its note.
PALM_X = 0.015        # m, edge of the hand from the bridge (hypothesis)
PALM_FORCE = 1.0      # N, pressure of the hand on one string (hypothesis)
R_SKIN = 3.0          # N s/m per N of pressure, damping of the skin (hypothesis: no measured value found)
PALM_MASS = 0.003     # kg of flesh moving with one string (hypothesis)


def palm_network(mu, L, fret, x_hand=PALM_X, force=PALM_FORCE):
    nodes = {n: {"guess": g} for n, g in {
        "mu": 1e-3, "L": 0.65, "Leff": 0.6, "x": 0.015, "N": 1.0, "r": 3.0, "s0": 100.0, "q": 0.02,
        "mh": 0.003, "kh": 2000.0}.items()}
    rel = [
        {"name": "fret", "terms": {"Leff": 1, "L": -1}, "rhs": -fret * math.log10(2) / 12, "sigma": 1e-9},
        {"name": "skin damping", "terms": {"r": 1, "N": -1}, "rhs": math.log10(R_SKIN), "sigma": 1e-9},
        {"name": "loss scale", "terms": {"s0": 1, "r": -1, "mu": 1, "Leff": 1}, "rhs": 0.0, "sigma": 1e-9},
        {"name": "position", "terms": {"q": 1, "x": -1, "Leff": 1}, "rhs": 0.0, "sigma": 1e-9},
    ]
    # the harder the palm presses, the more flesh rests on the string: its mass grows with the pressure
    measured = {"mu": (mu, 0.004), "L": (L, 3e-4), "x": (x_hand, 0.05), "N": (force, 0.05),
                "mh": (PALM_MASS * force / PALM_FORCE, 0.1), "kh": (K_FLESH, 0.1)}     # the flesh: same pulp as a fingertip
    return GlobalRelationalNetwork(nodes, rel).solve(measured_dict=measured)


def palm_sigma(freqs_n, palm):
    """Added decay rate (1/s) of modes n = 1, 2, ... under the palm."""
    n = np.arange(1, len(freqs_n) + 1, dtype=float)
    return palm["s0"] * np.sin(n * math.pi * palm["q"]) ** 2


def palm_frequencies(freqs_n, palm):
    """Mode frequencies under the palm: raised by the flesh's spring, lowered by its mass, where each mode moves."""
    f = np.asarray(freqs_n, dtype=float)
    n = np.arange(1, len(f) + 1, dtype=float)
    share = np.sin(n * math.pi * palm["q"]) ** 2
    m_n = palm["mu"] * palm["Leff"] / 2
    w = 2 * math.pi * f
    return np.sqrt((w * w * m_n + palm["kh"] * share) / (m_n + palm["mh"] * share)) / (2 * math.pi)


# ============================================================
# SOUND OF ONE STRING
# ============================================================

def synthesize_string(f1, B, duration, pluck, damping, brightness, sample_rate=SAMPLE_RATE,
                      release_tau=0.0, seed=0, extra_sigma=None, palm=None, Zs=None):
    """Modal synthesis of the force of one plucked stiff string on the bridge.
    extra_sigma(freqs) -> added decay rates (energy given to the bridge, from the bridge network);
    palm: values of the palm network, or None (Zs: string impedance, for the palm transmission).
    The snap of the pick is not a force on the bridge: it is the pick's own vibration, and the energy it
    gives the string is already the pluck itself."""
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
    # losses: inside the string and in the air (grow with frequency), plus the bridge, plus the palm
    sigma = (1.0 + (freqs / 1800.0) ** 2) / damping
    if extra_sigma is not None:
        sigma = sigma + extra_sigma(freqs)
    if palm is not None:
        sigma = sigma + palm_sigma(freqs, palm)
        freqs = palm_frequencies(freqs, palm)
    count = int(duration * sample_rate)
    t = np.arange(count) / sample_rate
    signal = np.zeros(count)
    peak = np.max(np.abs(amps)) if len(amps) else 1.0
    for f, a, sg in zip(freqs, amps, sigma):  # partial by partial keeps memory low
        if abs(a) < 1e-4 * peak:
            continue                         # inaudible partial (e.g. a node at the pluck point)
        w = 2.0 * math.pi * f
        # a mode released from rest with its decay rate sigma: it rings if sigma < w; if the palm damps it
        # harder than that, it no longer rings at all and only creeps back to rest (overdamped)
        if sg < w:
            wd = math.sqrt(w * w - sg * sg)
            m = min(count, int(9.2 / sg * sample_rate) + 1)   # stop once it has decayed by 80 dB
            tt = t[:m]
            signal[:m] += a * np.exp(-sg * tt) * (np.cos(wd * tt) + (sg / wd) * np.sin(wd * tt))
        else:
            r = math.sqrt(sg * sg - w * w)
            l1, l2 = -sg + r, -sg - r                          # slow and fast return
            m = min(count, int(9.2 / max(-l1, 1e-6) * sample_rate) + 1)
            tt = t[:m]
            signal[:m] += a * (l2 * np.exp(l1 * tt) - l1 * np.exp(l2 * tt)) / (l2 - l1)
    # the onset is the release itself: its sharpness comes only from release_tau (pick or finger)
    if count:
        signal -= signal[0] * np.exp(-np.arange(count) / max(release_tau * sample_rate, 1.0))
    return signal


# ============================================================
# GRM NETWORK OF A FINGER ON A WOUND STRING (chord changes)
# ============================================================
# Measured on real strings (Pakarinen, Penttinen & Bank, JASA 122, EL197, 2007): a finger sliding on a
# wound string makes a noise with two parts. Moving harmonics: every turn of wire crossed is a shock,
# at f = k v / p, and the noise level grows in proportion to v. Static harmonics: the sliding excites
# the LONGITUDINAL modes of the string (f = n c_L / (2 L)), while the fingertip damps the transverse ones.
#   equivalent diameter  d_eq^2 = 4 mu / (pi rho)        core   d_core = k d_eq
#   outer diameter       D^2 = d_eq^2 / fill             wire   2 p = D - d_core
#   stopped lengths      L_i = L 2^(-fret_i / 12)        slide  dx = |L_1 - L_2|
#   speed v = dx / dt    winding pitch f = v / p         friction power P = mu_f N v
#   core section A = pi d_core^2 / 4                     longitudinal wave  c_L^2 mu = E A
#   longitudinal mode    2 L f_L = c_L                   (only the steel core is stretched; the winding adds mass)
WIND_FILL = 0.8     # share of the outer section filled with metal (hypothesis)
MU_FRICTION = 0.3   # finger skin on steel (hypothesis)
LIFT_DX = 0.02      # m: the finger rolls off a string it leaves (no slide to another fret)


def squeak_network(mu, L, core_fraction, fret_from, fret_to, dt, force):
    nodes = {n: {"guess": g} for n, g in {
        "mu": 1e-3, "deq": 5e-4, "dcore": 3e-4, "D": 6e-4, "p": 2e-4, "L": 0.65, "L1": 0.6, "L2": 0.5,
        "dx": 0.03, "dt": 0.1, "v": 0.3, "fsq": 1500.0, "N": 0.5, "P": 0.05,
        "A": 1e-7, "cL": 2000.0, "fL": 1500.0}.items()}
    rel = [
        {"name": "equivalent diameter", "terms": {"deq": 2, "mu": -1}, "rhs": math.log10(4 / (math.pi * RHO_STEEL)), "sigma": 1e-9},
        {"name": "core", "terms": {"dcore": 1, "deq": -1}, "rhs": math.log10(core_fraction), "sigma": 1e-9},
        {"name": "outer diameter", "terms": {"D": 2, "deq": -2}, "rhs": -math.log10(WIND_FILL), "sigma": 1e-9},
        {"name": "winding wire", "type": "sum", "terms": {"p": 2, "D": -1, "dcore": 1}, "K": 0.0, "sigma": 1e-12},
        {"name": "speed", "terms": {"v": 1, "dx": -1, "dt": 1}, "rhs": 0.0, "sigma": 1e-9},
        {"name": "squeak pitch", "terms": {"fsq": 1, "v": -1, "p": 1}, "rhs": 0.0, "sigma": 1e-9},
        {"name": "friction power", "terms": {"P": 1, "N": -1, "v": -1}, "rhs": math.log10(MU_FRICTION), "sigma": 1e-9},
        {"name": "core section", "terms": {"A": 1, "dcore": -2}, "rhs": math.log10(math.pi / 4), "sigma": 1e-9},
        {"name": "longitudinal wave", "terms": {"cL": 2, "mu": 1, "A": -1}, "rhs": math.log10(E_STEEL), "sigma": 1e-9},
        {"name": "from", "terms": {"L1": 1, "L": -1}, "rhs": -fret_from * math.log10(2) / 12, "sigma": 1e-9},
        # while the hand changes shape the finger only touches the string: the whole string rings along its length
        {"name": "longitudinal mode", "terms": {"fL": 1, "L": 1, "cL": -1}, "rhs": -math.log10(2), "sigma": 1e-9},
    ]
    measured = {"mu": (mu, 0.004), "L": (L, 3e-4), "dt": (dt, 0.01), "N": (force, 0.05)}
    if fret_from > 0 and fret_to > 0:     # slide from one fret to another
        sign = 1.0 if fret_to > fret_from else -1.0   # L1 > L2 when moving up the neck
        rel += [
            {"name": "to", "terms": {"L2": 1, "L": -1}, "rhs": -fret_to * math.log10(2) / 12, "sigma": 1e-9},
            {"name": "slide", "type": "sum", "terms": {"dx": 1, "L1": -sign, "L2": sign}, "K": 0.0, "sigma": 1e-12},
        ]
    else:                                  # the finger rolls off the string
        measured["dx"] = (LIFT_DX, 0.05)
        del nodes["L2"]
    return GlobalRelationalNetwork(nodes, rel).solve(measured_dict=measured)


# ============================================================
# GRM NETWORK OF A FINGER ON A FRET: lifting and landing (chord changes)
# ============================================================
# A finger holds the string down on its fret, by the height of the string above the fingerboard there.
# When it lifts, the string jumps back from that height: a soft pluck of the open string, with its apex at
# the finger, released as slowly as the skin leaves it (low notes, no click). When a finger lands, it
# pushes the string down onto the fret: a smaller, quicker knock on the newly stopped string.
#   finger position   x_f = L (1 - 2^(-fret / 12))            (from the nut)
#   string height     h = H_NUT + (H_12 - H_NUT) x_f / (L / 2) (the action rises along the neck)
H_NUT = 0.0005        # m, height of the string at the nut (typical acoustic set-up)
H_12 = 0.0022         # m, height at the 12th fret (typical acoustic set-up)
TAU_LIFT = 0.003      # s, time for the skin to leave the string (hypothesis)
TAU_LAND = 0.001      # s, time for the string to meet the fret (hypothesis)
LAND_SHARE = 0.4      # share of the height given to the stopped string by a landing finger (hypothesis)


def action_network(L, fret):
    nodes = {"L": {"guess": 0.65}, "xf": {"guess": 0.05}, "h": {"guess": 0.001}}
    rel = [
        {"name": "finger position", "type": "sum", "terms": {"xf": 1.0, "L": 2 ** (-fret / 12.0) - 1.0},
         "K": 0.0, "sigma": 1e-12},
        {"name": "string height", "type": "sum", "terms": {"h": 1.0, "xf": -(H_12 - H_NUT) / (L / 2)},
         "K": H_NUT, "sigma": 1e-12},
    ]
    return GlobalRelationalNetwork(nodes, rel).solve(measured_dict={"L": (L, 3e-4)}, max_iterations=30)


LONG_COUPLING = 0.3   # share of the longitudinal force that rocks the bridge into the top (hypothesis)
LONG_TAU = 0.04       # s, ring of a longitudinal mode under the finger (hypothesis)
V_REF = 0.3           # m/s, finger speed of the reference level


PAD_EDGE = 0.001      # m, softness of the edge of the finger pad on the winding (hypothesis)
FRET_CROWN = 0.002    # m, width of the crown of a fret wire (typical)
FRET_BUMP = 0.3       # share of the finger's pressing force that knocks the fret when it rides over it (hypothesis)


def synthesize_squeak(fsq, power, duration, f_long, x_ratio, v, sample_rate=SAMPLE_RATE, seed=0,
                      bumps=(), force=0.0):
    """Force on the bridge of a finger sliding on a wound string: a train of shocks (one per winding
    turn, rate f = v / p rising and falling with the finger speed), smoothed by the soft edge of the
    finger pad (it takes PAD_EDGE / v to cross a turn: a fast slide over a fine winding is softened
    the most), ringing the string's longitudinal modes n f_L, each weighted by |sin(n pi x)| at the finger
    position x. The level follows the friction force mu_f N and grows with the speed (P / V_REF).
    bumps: moments (0..1 of the slide) when the finger rides over a fret wire. Each one is a slow knock of
    FRET_BUMP * N lasting FRET_CROWN / v_local: a low, woody thud (tens to a few hundred Hz)."""
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
    reference = np.sqrt(np.mean(shocks ** 2)) + 1e-12
    # the pad edge spreads every shock over PAD_EDGE / v
    width = max(3, int(PAD_EDGE / max(v, 1e-3) * sample_rate))
    pad = np.hanning(width)
    soft = np.convolve(shocks, pad / pad.sum(), mode="same") * math.sqrt(width / 3.0)
    # the steady drag of the finger moves the bridge too slowly to be heard: keep what changes
    slow = int(0.01 * sample_rate)
    soft -= np.convolve(soft, np.ones(slow) / slow, mode="same")
    # the longitudinal modes of the string, struck by every shock
    t = np.arange(int(5 * LONG_TAU * sample_rate)) / sample_rate
    h = np.zeros_like(t)
    for k in range(1, 9):
        f = k * f_long
        if f > 0.45 * sample_rate:
            break
        h += abs(math.sin(k * math.pi * x_ratio)) * np.sin(2 * math.pi * f * t) * np.exp(-t / LONG_TAU) / k
    h /= np.max(np.abs(h)) + 1e-12
    m = count + len(h) - 1
    nfft = 1 << (m - 1).bit_length()
    ring = np.fft.irfft(np.fft.rfft(soft, nfft) * np.fft.rfft(h, nfft), nfft)[:m]
    ring[:count] += 0.5 * soft                         # the shocks themselves (moving harmonics k v / p)
    friction = max(power, 0.0) / V_REF                 # = mu_f N v / V_REF, in newtons
    out = LONG_COUPLING * friction * ring / reference / math.sqrt(len(h) / 3.0)
    for u in bumps:                                     # the finger rides over fret wires
        v_here = max(v * (math.pi / 2) * math.sin(math.pi * u), 0.02)
        width = max(4, int(FRET_CROWN / v_here * sample_rate))
        i0 = int(u * count) - width // 2
        knock = FRET_BUMP * force * np.sin(np.linspace(0.0, math.pi, width))
        a, b = max(i0, 0), min(i0 + width, len(out))
        if b > a:
            out[a:b] += knock[a - i0:b - i0]
    return out


# ============================================================
# GRM NETWORK OF THE PLAYER: the arm meets the tempo
# ============================================================
# The right arm swings like a pendulum, one half swing per step: what it does at one stroke depends on
# the strokes around it. One network per sequence, three nodes per stroke k:
#   t_k  time of the stroke         intent: t_k = grid_k (measured with the player's timing noise)
#                                   arm:    t_k - t_(k-1) = grid_k - grid_(k-1)   (the swing keeps its period)
#   A_k  swing amplitude (m)        intent: A_k = A0 * accent(k)   (beat 1 strongest, off-beats lighter)
#                                   arm:    A_k / A_(k-1) = accent(k) / accent(k-1)
#   p_k  hand position along the strings (pluck point), d_k pick depth into the strings,
#   x_k, N_k where the palm rests and how hard it presses: same pattern
# The intents are drawn with the player's imprecision; the network finds what the arm actually does,
# a compromise between each intent and the continuity of the swing. Then:
#   hand speed   v_k = pi A_k / step      (half a pendulum swing per step)
#   pluck force  F_k = F0 * A_k / A0      (an upstroke is lighter: UP_FORCE)
#   pick depth on string j along the arc of the wrist: o_j = d_k - (y_j - y_c)^2 / (2 R)
#   (a downstroke is centred on the middle strings, an upstroke on the treble: the bass is often missed)
TIMING_SIGMA = 0.015     # s, timing precision of a player (10 to 20 ms for musicians: Repp & Su 2013)
ARM_SIGMA = 0.015        # s, how closely the swing keeps its period (hypothesis)
AMPLITUDE_SIGMA = 0.07   # dex, stroke to stroke variation of the swing (hypothesis)
PLUCK_SIGMA = 0.06       # relative, wandering of the hand along the strings (hypothesis)
DEPTH_SIGMA = 0.0008     # m, wandering of the pick depth (hypothesis)
PALM_X_SIGMA = 0.003     # m, wandering of the palm along the strings (hypothesis)
PALM_N_SIGMA = 0.12      # dex, variation of the palm pressure (hypothesis)
SWING = 0.10             # m, swing amplitude A0 (hypothesis)
PICK_DEPTH = 0.003       # m, mean depth of the pick into the strings (hypothesis)
WRIST_RADIUS = 0.25      # m, radius of the arc of the pick (hypothesis)
STRING_SPACING = 0.0105  # m, between two strings at the sound hole
FULL_DEPTH = 0.0015      # m, depth from which the pick gives a string its full force (hypothesis)
UP_FORCE = 0.8           # an upstroke against gravity is lighter (hypothesis)
ACCENT_DEX = [0.06, -0.04, 0.0, -0.04, 0.03, -0.04, 0.0, -0.04]   # by eighth note in the bar (hypothesis)


def player_network(strokes, step, pluck, rng, swing=SWING):
    """strokes: list of (grid time, step index in the bar). Returns one dict per stroke:
    t, A, v (hand speed), force factor, p (pluck point), d (pick depth), palm_x and palm_N (where and how
    hard the palm rests, used by the palm-muted strokes)."""
    if not strokes:
        return []
    nodes, rel, measured = {}, [], {}
    for k, (grid, idx) in enumerate(strokes):
        acc = ACCENT_DEX[idx % len(ACCENT_DEX)]
        nodes[f"t{k}"] = {"guess": grid, "scale": "lin"}
        nodes[f"A{k}"] = {"guess": swing}
        nodes[f"p{k}"] = {"guess": pluck}
        nodes[f"d{k}"] = {"guess": PICK_DEPTH, "scale": "lin"}
        nodes[f"x{k}"] = {"guess": PALM_X}
        nodes[f"N{k}"] = {"guess": PALM_FORCE}
        measured[f"t{k}"] = (grid + rng.normal(0.0, TIMING_SIGMA), TIMING_SIGMA)
        measured[f"A{k}"] = (swing * 10 ** (acc + rng.normal(0.0, AMPLITUDE_SIGMA)), AMPLITUDE_SIGMA)
        measured[f"p{k}"] = (pluck * (1.0 + rng.normal(0.0, PLUCK_SIGMA)), PLUCK_SIGMA / LN10)
        measured[f"d{k}"] = (PICK_DEPTH + rng.normal(0.0, DEPTH_SIGMA), DEPTH_SIGMA)
        measured[f"x{k}"] = (max(PALM_X + rng.normal(0.0, PALM_X_SIGMA), 0.004), PALM_X_SIGMA / PALM_X / LN10)
        # the palm presses harder on the accents, like the pick
        measured[f"N{k}"] = (PALM_FORCE * 10 ** (acc + rng.normal(0.0, PALM_N_SIGMA)), PALM_N_SIGMA)
        if k:
            grid0, idx0 = strokes[k - 1]
            gap = max((grid - grid0) / step, 1.0)
            acc0 = ACCENT_DEX[idx0 % len(ACCENT_DEX)]
            rel += [
                {"name": f"arm period {k}", "type": "sum", "terms": {f"t{k}": 1.0, f"t{k - 1}": -1.0},
                 "K": grid - grid0, "sigma": ARM_SIGMA * math.sqrt(gap)},
                {"name": f"arm swing {k}", "terms": {f"A{k}": 1, f"A{k - 1}": -1}, "rhs": acc - acc0,
                 "sigma": AMPLITUDE_SIGMA * math.sqrt(gap)},
                {"name": f"hand along {k}", "terms": {f"p{k}": 1, f"p{k - 1}": -1}, "rhs": 0.0,
                 "sigma": PLUCK_SIGMA / LN10 * math.sqrt(gap)},
                {"name": f"pick depth {k}", "type": "sum", "terms": {f"d{k}": 1.0, f"d{k - 1}": -1.0},
                 "K": 0.0, "sigma": DEPTH_SIGMA * math.sqrt(gap)},
                {"name": f"palm place {k}", "terms": {f"x{k}": 1, f"x{k - 1}": -1}, "rhs": 0.0,
                 "sigma": PALM_X_SIGMA / PALM_X / LN10 * math.sqrt(gap)},
                {"name": f"palm pressure {k}", "terms": {f"N{k}": 1, f"N{k - 1}": -1}, "rhs": acc - acc0,
                 "sigma": PALM_N_SIGMA * math.sqrt(gap)},
            ]
    v = GlobalRelationalNetwork(nodes, rel).solve(measured_dict=measured, compute_uncertainty=False)["values"]
    out = []
    for k in range(len(strokes)):
        A = v[f"A{k}"]
        out.append({"t": v[f"t{k}"], "A": A, "v": math.pi * A / step, "force": A / swing,
                    "p": v[f"p{k}"], "d": v[f"d{k}"], "palm_x": v[f"x{k}"], "palm_N": v[f"N{k}"]})
    return out


def strum_contacts(order, stroke, up):
    """Which strings of `order` (string indices in the order the pick crosses them) the pick reaches,
    when (s after the stroke time) and with what share of the force."""
    centre = (4.5 if up else 2.5) * STRING_SPACING
    out, first = [], None
    for i in order:
        y = i * STRING_SPACING
        depth = stroke["d"] - (y - centre) ** 2 / (2 * WRIST_RADIUS)
        if first is None:
            first = y
        if depth <= 0:
            continue                                     # the arc passes above this string
        delay = abs(y - first) / stroke["v"]
        share = min(1.0, depth / FULL_DEPTH) * (UP_FORCE if up else 1.0)
        out.append((i, delay, share))
    return out


# ============================================================
# GRM NETWORK OF THE BODY: the air in the box meets the wooden top, the top meets the bridge
# ============================================================
# Air cavity (Helmholtz resonator)   f_H = c_air / (2 pi) * sqrt(A / (V * l_neck)),  l_neck = t + 1.7 r
# Top plate (clamped disc, 1st mode) f_T = 10.21 / (2 pi a^2) * h * sqrt(E / (12 rho (1 - nu^2)))
# Coupling: the two oscillators push each other apart into the two lowest body resonances
#   f_lo, f_hi^2 = ((f_H^2 + f_T^2) -/+ sqrt((f_H^2 - f_T^2)^2 + 4 k^2 f_H^2 f_T^2)) / 2
# Higher top modes follow the ratios of the clamped-disc eigenvalues.
# Radiation: a top of radius a moving the air radiates well only above f_rad = c_air / (2 pi a) (ka = 1);
# below, the radiated pressure falls in proportion to f / f_rad.
# Bridge: the top seen from the strings. Plate rigidity D = k_brace E h^3 / (12 (1 - nu^2)); far from its modes the
# top behaves like an infinite plate of point impedance Zp = 8 sqrt(D rho h); near a mode, like a mass
# M_m on a spring. Top mass M_top = rho h pi a^2, modal mass M = BETA M_top. The strings do not push on
# the plate directly but on the bridge glued to it, a mass m_b: Y_plate = 1 / (Zp + i w m_b), so above
# f = Zp / (2 pi m_b) the heavier bridge lets less and less of the high frequencies into the top.
# Body dimensions and wood values are typical figures, not measurements of a given guitar.
GAMMA_AIR, R_GAS, M_AIR, T_AIR = 1.4, 8.314462618, 0.028965, 293.15
NU_WOOD = 0.3
BETA_MODAL = 0.5    # share of the top mass that moves in its first modes (hypothesis)
BRACING = 4.0       # the braces under the top make it stiffer than bare spruce, seen from the bridge (hypothesis)
BRIDGE_VOLUME = 3.2e-5   # m^3, a rosewood bridge of about 150 x 30 x 7 mm (typical)
RHO_BRIDGE = 850.0       # kg/m^3, rosewood (typical)
BRIDGE_SHARE = 0.2       # share of the bridge mass the saddle carries (hypothesis, set by ear: corner near 2.3 kHz)
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
        "frad": 300.0, "D": 20.0, "Zp": 40.0, "Mtop": 0.1, "Mm": 0.05, "Vb": 3e-5, "rhob": 850.0,
        "mb": 0.008, "fb": 800.0}.items()}
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
        {"name": "plate rigidity", "terms": {"D": 1, "E": -1, "h": -3}, "rhs": math.log10(BRACING / (12 * (1 - NU_WOOD ** 2))), "sigma": 1e-9},
        {"name": "plate impedance", "terms": {"Zp": 1, "D": -0.5, "rho": -0.5, "h": -0.5}, "rhs": math.log10(8.0), "sigma": 1e-9},
        {"name": "top mass", "terms": {"Mtop": 1, "rho": -1, "h": -1, "a": -2}, "rhs": math.log10(math.pi), "sigma": 1e-9},
        {"name": "modal mass", "terms": {"Mm": 1, "Mtop": -1}, "rhs": math.log10(BETA_MODAL), "sigma": 1e-9},
        {"name": "bridge mass", "terms": {"mb": 1, "rhob": -1, "Vb": -1}, "rhs": math.log10(BRIDGE_SHARE), "sigma": 1e-9},
        {"name": "bridge corner", "terms": {"fb": 1, "mb": 1, "Zp": -1}, "rhs": -math.log10(2 * math.pi), "sigma": 1e-9},
    ]
    for j, ratio in enumerate(PLATE_RATIOS):
        rel.append({"name": f"top mode {j + 3}", "terms": {f"f{j + 3}": 1, "fT": -1}, "rhs": math.log10(ratio), "sigma": 1e-9})
    b = BODY_DEFAULT
    measured = {"V": (b["V"] * size ** 3, 0.01), "r": (b["r"] * size, 0.01), "t": (b["t"], 0.02),
                "a": (b["a"] * size, 0.01), "h": (top_mm / 1000.0, 0.02), "E": (b["E"], 0.05), "rho": (b["rho"], 0.02),
                "Vb": (BRIDGE_VOLUME, 0.02), "rhob": (RHO_BRIDGE, 0.02)}
    return GlobalRelationalNetwork(nodes, rel).solve(measured_dict=measured)


def body_modes(size=1.0, top_mm=2.8, coupling=0.35):
    """(frequency, gain, quality factor) of the body resonances, frequencies from the GRM network."""
    v = body_network(size, top_mm, coupling)["values"]
    freqs = [v["f_lo"], v["f_hi"]] + [v[f"f{j + 3}"] for j in range(len(PLATE_RATIOS))]
    gains = [0.9, 1.0, 0.55, 0.45, 0.35, 0.25, 0.18]
    qs = [16, 22, 25, 28, 30, 32, 35]
    return list(zip(freqs, gains, qs)), v


def bridge_admittance(freqs, modes, bv):
    """Velocity of the bridge per newton of string force (s/kg), complex, at the frequencies `freqs`:
    each body mode is a mass M = Mm / gain on its spring, the rest of the top an infinite plate seen
    through the mass of the bridge, 1 / (Zp + i w m_b)."""
    f = np.asarray(freqs, dtype=float)
    w = 2 * math.pi * f
    Y = np.zeros(len(f), dtype=complex)
    for fm, gain, q in modes:
        wm = 2 * math.pi * fm
        Y += 1j * w / ((bv["Mm"] / gain) * (wm * wm - w * w + 1j * w * wm / q))
    Y += f * f / (f * f + bv["fT"] ** 2) / (bv["Zp"] + 1j * w * bv["mb"])
    return Y


def bridge_loss(modes, bv, c, Leff, Zs):
    """Added decay rate of the partials of a string, from the energy it gives to the bridge:
    sigma = (c / L) Zs Re Y(f)  (the share 4 Zs Re Y lost at each reflection, two per round trip)."""
    return lambda freqs: (c / Leff) * Zs * np.maximum(bridge_admittance(freqs, modes, bv).real, 0.0)


def apply_body(audio, amount, modes, bv):
    """From the force of the strings on the bridge to the sound in the room. The force moves the top
    (velocity V = Y F, with the bridge admittance of the body network: its modes, the air resonance coupled
    to the top, and the plate between them), and a moving top of radius a radiates a pressure
    p ~ i ka / (1 + i ka) * V, ka = f / f_rad: in proportion to frequency below f_rad, flat above.
    `amount` mixes this radiated sound with the bare force of the strings."""
    if len(audio) == 0:
        return audio
    nfft = 1 << (len(audio) - 1).bit_length()
    spec = np.fft.rfft(audio, nfft)
    f = np.fft.rfftfreq(nfft, 1.0 / SAMPLE_RATE)
    ka = f / bv["frad"]
    wet_spec = spec * bridge_admittance(f, modes, bv) * (1j * ka / (1 + 1j * ka))
    dry_rms = np.sqrt(np.sum(np.abs(spec) ** 2)) + 1e-12
    wet_rms = np.sqrt(np.sum(np.abs(wet_spec) ** 2)) + 1e-12
    mix = (1.0 - amount) * spec + amount * wet_spec * (dry_rms / wet_rms)
    return np.fft.irfft(mix, nfft)[: len(audio)]


# ============================================================
# THE WHOLE GUITAR: every string pushes on the bridge, the bridge moves every string
# ============================================================
# The force of all the strings moves the bridge (velocity V = Y F). A moving bridge is a moving end for
# every string: mode n of string i answers with a force on the bridge
#   F_n(w) = (2 T / L) (-i w) Y(w) F_others(w) / (w_n^2 - w^2 + 2 i sigma_n w)
# so the strings that are not struck sing too: the open strings nobody plays, and a string the finger has
# just left. A struck string is left to its own sound (its energy is already its own).
# sigma_n contains the bridge loss of the string and its coupling rate kappa = (c / L) Zs |Y|: a mode can
# share energy with the bridge but never answer more than it is given.

def sympathetic_response(drive_spec, f_grid, Y, f1, B, T, Leff, sigma_fn, coupling_fn, count=40):
    w = 2 * math.pi * f_grid
    fn = partial_frequencies(f1, B, count)
    fn = fn[fn < 0.45 * SAMPLE_RATE]
    # a mode coupled to the bridge at the rate kappa = (c / L) Zs |Y| shares its energy with the bridge
    # rather than piling it up: its response is limited by sigma + kappa (one-way coupling stays below 1)
    sig = sigma_fn(fn) + coupling_fn(fn)
    df = f_grid[1] - f_grid[0]
    G = np.zeros(len(f_grid), dtype=complex)
    for f_, s_ in zip(fn, sig):
        half = max(15.0, 0.03 * f_, 40 * s_ / (2 * math.pi))
        lo, hi = int(max((f_ - half) / df, 1)), int(min((f_ + half) / df + 1, len(f_grid)))
        wn, ww = 2 * math.pi * f_, w[lo:hi]
        G[lo:hi] += (2 * T / Leff) * (-1j * ww) / (wn * wn - ww * ww + 2j * s_ * ww)
    return G * Y * drive_spec


def render_guitar(notes, total, damping, brightness, modes, bv, squeaks=(), body_amount=0.6,
                  sympathy=True, open_strings=None, palm_spans=()):
    """notes: dicts with i, f1, B, T, Leff, Zs, c, start, length, gain, tau, pluck, palm (palm network) or None.
    Every string is rendered as its force on the bridge (newtons); the strings and the finger noises
    then pass through the bridge into each other, and the whole guitar through its body.
    open_strings: the six strings at rest (same keys), free to answer before anyone plays them.
    palm_spans: (from, to, [palm values of the six strings]) while the palm rests on the strings."""
    count = int(total * SAMPLE_RATE) + 1
    per_string = np.zeros((6, count))
    release = int(0.015 * SAMPLE_RATE)
    for nt in notes:
        loss = bridge_loss(modes, bv, nt["c"], nt["Leff"], nt["Zs"])
        s = synthesize_string(nt["f1"], nt["B"], nt["length"], nt["pluck"], damping, brightness,
                              release_tau=nt.get("tau", 0.0), seed=int(nt["start"] * 1000) % 997,
                              extra_sigma=loss, palm=nt.get("palm"), Zs=nt["Zs"])
        k = min(release, len(s))
        s[len(s) - k:] *= np.linspace(1.0, 0.0, k)
        start = int(nt["start"] * SAMPLE_RATE)
        if start < 0:                          # began before the rendered window: keep what is inside
            s, start = s[-start:], 0
        end = min(start + len(s), count)
        if end > start:
            # newtons on the bridge: T pi / L * (release height) * (normalised modal amplitudes)
            scale = nt["T"] * math.pi / nt["Leff"] * Y_REF * nt["gain"]
            per_string[nt["i"], start:end] += scale * s[: end - start]
    for k, sq in enumerate(squeaks):
        s = synthesize_squeak(sq["fsq"], sq["P"], sq["dur"], sq["fL"], sq["x"], sq["v"], seed=k,
                              bumps=sq.get("bumps", ()), force=sq.get("N", 0.0))
        start = int(sq["start"] * SAMPLE_RATE)
        if start < 0:
            s, start = s[-start:], 0
        end = min(start + len(s), count)
        if end > start:
            per_string[sq["i"], start:end] += s[: end - start]
    mix = per_string.sum(axis=0)
    if sympathy and notes:
        nfft = 1 << (count + int(2.0 * SAMPLE_RATE) - 1).bit_length()
        f_grid = np.fft.rfftfreq(nfft, 1.0 / SAMPLE_RATE)
        Y = bridge_admittance(f_grid, modes, bv)
        specs = np.fft.rfft(per_string, nfft, axis=1)
        total_spec = specs.sum(axis=0)
        fade = int(0.005 * SAMPLE_RATE)
        for i in range(6):
            # when string i is free to answer: before its first note and after each lift or landing,
            # until its next stroke (open strings nobody plays are free all along)
            own = sorted((nt for nt in notes if nt["i"] == i), key=lambda nt: nt["start"])
            free = []
            first = own[0]["start"] if own else total
            if open_strings is not None:
                free.append((0.0, first, open_strings[i]))
            for j, nt in enumerate(own):
                if nt.get("kind", "strike") == "strike":
                    continue
                end_t = own[j + 1]["start"] if j + 1 < len(own) else total
                free.append((nt["start"], end_t, nt))
            # while the palm rests on the strings (palm-muted playing), a free string is under it too
            pieces = []
            for a_, b_, nt in free:
                a_, b_ = max(a_, 0.0), min(b_, total)
                if b_ <= a_:
                    continue
                cuts = sorted({a_, b_} | {t for pa, pb, _ in palm_spans for t in (pa, pb) if a_ < t < b_})
                for u, w_ in zip(cuts, cuts[1:]):
                    under = next((pl[i] for pa, pb, pl in palm_spans if pa <= u and w_ <= pb), None)
                    pieces.append((u, w_, nt, nt.get("palm") or under))
            states = {}
            for a_, b_, nt, palm in pieces:
                key = (round(nt["f1"], 3), None if palm is None else round(palm["s0"], 1))
                states.setdefault(key, (nt, palm, []))[2].append((a_, b_))
            if not states:
                continue
            drive = total_spec - specs[i]
            for nt, palm, spans in states.values():
                loss = bridge_loss(modes, bv, nt["c"], nt["Leff"], nt["Zs"])

                def sigma_fn(fn, loss=loss, palm=palm):
                    sg = (1.0 + (fn / 1800.0) ** 2) / damping + loss(fn)
                    return sg + (palm_sigma(fn, palm) if palm is not None else 0.0)

                def coupling_fn(fn, nt=nt):
                    return (nt["c"] / nt["Leff"]) * nt["Zs"] * np.abs(bridge_admittance(fn, modes, bv))
                spec_i = sympathetic_response(drive, f_grid, Y, nt["f1"], nt["B"], nt["T"], nt["Leff"],
                                              sigma_fn, coupling_fn)
                resp = np.fft.irfft(spec_i, nfft)[:count]
                mask = np.zeros(count)
                for a_, b_ in spans:
                    ia, ib = int(a_ * SAMPLE_RATE), min(int(b_ * SAMPLE_RATE), count)
                    if ib > ia:
                        mask[ia:ib] = 1.0
                        k = min(fade, ib - ia)
                        mask[ia:ia + k] *= np.linspace(0.0, 1.0, k)
                        mask[ib - k:ib] *= np.linspace(1.0, 0.0, k)
                mix += resp * mask
    out = apply_body(mix, body_amount, modes, bv)
    peak = np.max(np.abs(out)) if len(out) else 0.0
    return (out / peak if peak > 0 else out).astype(np.float32)


# ============================================================
# GRM NETWORK OF THE ROOM: the sound meets the walls
# ============================================================
# The guitar plays in a room of size L x W x H. Every wall takes a share alpha of the sound that hits it (by
# octave band, measured coefficients) and sends the rest back. The room is a network:
#   volume            V = L W H                     surface   S = 2 (L W + L H + W H)
#   absorption        A_b = sum (S_i alpha_i,b)     mean      alpha_b = A_b / S
#   reverberation     RT_b = 0.161 V / (-S ln(1 - alpha_b))   (Eyring: the time for the sound to fall 60 dB)
#   critical distance r_c = 0.057 sqrt(V / RT_1k)  (where the room is as loud as the guitar itself)
#   mixing            the reverberant energy at a distance r is (r / r_c)^2 times the direct one
#   Schroeder         f_s = 2000 sqrt(RT / V)       (below it, the room's own modes are heard one by one)
# The sound that reaches the ear: the direct sound, the first reflections (image sources: each wall a mirror,
# each bounce taking its share), then a diffuse tail that decays band by band at the rate RT_b sets.
ROOM_BANDS = [125.0, 250.0, 500.0, 1000.0, 2000.0, 4000.0]
MATERIALS = {   # absorption coefficients by octave band (sengpielaudio, table of absorption coefficients)
    "Painted brick": [0.01, 0.01, 0.02, 0.02, 0.02, 0.03],
    "Plaster": [0.013, 0.015, 0.02, 0.03, 0.04, 0.05],
    "Wood panels": [0.28, 0.22, 0.17, 0.09, 0.10, 0.11],
    "Glass": [0.35, 0.25, 0.18, 0.12, 0.07, 0.04],
    "Curtains": [0.14, 0.35, 0.55, 0.72, 0.70, 0.65],
    "Carpet": [0.02, 0.06, 0.14, 0.37, 0.60, 0.65],
}
ROOMS = {"Small room": (3.5, 3.0, 2.5), "Living room": (6.0, 4.5, 2.6), "Studio": (9.0, 7.0, 3.5),
         "Church": (30.0, 15.0, 14.0)}
C_ROOM = 343.0


def room_network(size, material, floor="Wood panels"):
    """The room as relations: its reverberation time in each band, its critical distance, its Schroeder
    frequency. Walls and ceiling of `material`, floor of `floor`."""
    L, W, H = size
    walls = MATERIALS[material]
    fl = MATERIALS[floor]
    nodes = {n: {"guess": g} for n, g in {"L": L, "W": W, "H": H, "V": 60.0, "S": 90.0, "rc": 1.0, "fs": 200.0}.items()}
    rels = [
        {"name": "volume", "terms": {"V": 1, "L": -1, "W": -1, "H": -1}, "rhs": 0.0, "sigma": 1e-9},
        {"name": "surface", "type": "fn", "nodes": ["S", "L", "W", "H"], "sigma": 1e-9,
         "f": lambda v: LG10(v["S"]) - LG10(2 * (v["L"] * v["W"] + v["L"] * v["H"] + v["W"] * v["H"]))},
    ]
    for b, f in enumerate(ROOM_BANDS):
        nodes[f"RT{b}"] = {"guess": 1.0}
        floor_share = (L * W) / (2 * (L * W + L * H + W * H))
        alpha = floor_share * fl[b] + (1 - floor_share) * walls[b]
        rels.append({"name": f"Eyring {int(f)} Hz", "type": "fn", "nodes": [f"RT{b}", "V", "S"], "sigma": 1e-9,
                     "f": lambda v, b=b, a=alpha: LG10(v[f"RT{b}"]) - LG10(0.161 * v["V"] / (-v["S"] * math.log(1 - a)))})
    rels.append({"name": "critical distance", "terms": {"rc": 1, "V": -0.5, "RT3": 0.5}, "rhs": LG10(0.057), "sigma": 1e-9})
    rels.append({"name": "Schroeder", "terms": {"fs": 1, "RT3": -0.5, "V": 0.5}, "rhs": LG10(2000.0), "sigma": 1e-9})
    out = GlobalRelationalNetwork(nodes, rels).solve({"L": (L, 0.005), "W": (W, 0.005), "H": (H, 0.005)})
    v = out["values"]
    v["alpha"] = [(L * W / (2 * (L * W + L * H + W * H))) * fl[b] + (1 - L * W / (2 * (L * W + L * H + W * H))) * walls[b]
                  for b in range(len(ROOM_BANDS))]
    return v


def room_impulse(room, size, distance, sample_rate=SAMPLE_RATE, seed=3):
    """Impulse response from the guitar to the ear: direct sound, image sources up to the second order, and
    a diffuse tail decaying band by band. Its energies follow the critical distance of the room network."""
    L, W, H = size
    src = np.array([0.35 * L, 0.5 * W, 1.0])
    lis = src + np.array([min(distance, 0.55 * L), 0.0, 0.2])
    rt = [room[f"RT{b}"] for b in range(len(ROOM_BANDS))]
    length = int(min(max(rt) * 1.2, 6.0) * sample_rate) + 1
    h = np.zeros(length)
    r_direct = float(np.linalg.norm(lis - src))
    reflect = math.sqrt(1 - room["alpha"][3])          # pressure kept at each bounce (1 kHz band)
    early_energy = 0.0
    for nx in range(-2, 3):
        for ny in range(-2, 3):
            for nz in range(-2, 3):
                order = abs(nx) + abs(ny) + abs(nz)
                if order > 2:
                    continue
                img = np.array([nx * L + (src[0] if nx % 2 == 0 else L - src[0]),
                                ny * W + (src[1] if ny % 2 == 0 else W - src[1]),
                                nz * H + (src[2] if nz % 2 == 0 else H - src[2])])
                r = float(np.linalg.norm(img - lis))
                k = int(r / C_ROOM * sample_rate)
                if k < length:
                    a = (reflect ** order) * r_direct / r      # relative to the direct sound
                    h[k] += a
                    if order:
                        early_energy += a * a
    # the diffuse tail: its energy relative to the direct sound is (r / r_c)^2 (room network)
    rev_energy = max((r_direct / room["rc"]) ** 2 - early_energy, 0.0)
    t0 = 2 * (4 * room["V"] / room["S"]) / C_ROOM        # after about two mean free paths
    t = np.arange(length) / sample_rate
    rng = np.random.default_rng(seed)
    nfft = 1 << (length - 1).bit_length()
    f = np.fft.rfftfreq(nfft, 1.0 / sample_rate)
    tail = np.zeros(length)
    edges = []
    for b, fc in enumerate(ROOM_BANDS):
        lo, hi = fc / math.sqrt(2), fc * math.sqrt(2)
        edges.append((20.0 if b == 0 else lo, sample_rate / 2 if b == len(ROOM_BANDS) - 1 else hi))
    total_bw = sum(hi - lo for lo, hi in edges)
    for b, fc in enumerate(ROOM_BANDS):
        band = np.fft.rfft(rng.standard_normal(nfft))
        lo, hi = edges[b]
        band[(f < lo) | (f >= hi)] = 0.0
        noise = np.fft.irfft(band, nfft)[:length]
        env = np.exp(-6.91 * np.maximum(t - t0, 0.0) / rt[b]) * (t >= t0 * 0.6)
        piece = noise * env
        # a diffuse field is white: each band carries energy in proportion to its width, and to how long it
        # lingers (steady-state reverberant energy grows with RT)
        share = (hi - lo) / total_bw * rt[b] / rt[3]
        piece *= math.sqrt(share / (np.sum(piece ** 2) + 1e-30))
        tail += piece
    h += math.sqrt(rev_energy) * tail
    return h


def apply_room(audio, room, size, distance):
    h = room_impulse(room, size, distance)
    n = len(audio) + len(h) - 1
    nfft = 1 << (n - 1).bit_length()
    out = np.fft.irfft(np.fft.rfft(audio, nfft) * np.fft.rfft(h, nfft), nfft)[:n]
    return out


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
        self.root.geometry("1240x1060")
        self.root.minsize(1060, 820)

        self.models = [None] * 6
        self.entries, self.fret_vars = [], []
        self.freq_labels, self.cents_labels = [], []

        self.pluck = tk.DoubleVar(value=0.22)
        self.damping = tk.DoubleVar(value=3.0)   # losses inside the string and the air; the bridge adds its own
        self.brightness = tk.DoubleVar(value=0.6)
        self.duration = tk.DoubleVar(value=3.0)
        self.volume = tk.DoubleVar(value=0.7)
        self.core = tk.DoubleVar(value=0.45)
        self.stiff = tk.BooleanVar(value=True)
        self.chord = tk.StringVar(value="Open")
        self.status = tk.StringVar(value="Ready.")
        self.swing_cm = tk.DoubleVar(value=SWING * 100)
        self.human = tk.BooleanVar(value=True)
        self.sympathy = tk.BooleanVar(value=True)
        self.body_amount = tk.DoubleVar(value=0.85)
        self.palm_intensity = tk.DoubleVar(value=0.6)
        self.room_on = tk.BooleanVar(value=True)
        self.room_size = tk.StringVar(value="Living room")
        self.room_material = tk.StringVar(value="Wood panels")
        self.room_distance = tk.DoubleVar(value=1.0)
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
        ttk.Label(header, text="One object whose parts are all in relation: strings, frets, bridge, top, air, and the hands "
                               "that play it. Every meeting of two parts is a network solved by the GRM core.",
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
            ("Arm swing (cm)", self.swing_cm, 4.0, 20.0, 0.5),
            ("Body", self.body_amount, 0.0, 1.0, 0.05),
            ("Body size", self.body_size, 0.7, 1.4, 0.05),
            ("Palm pressure", self.palm_intensity, 0.1, 2.0, 0.05),
            ("Listener (m)", self.room_distance, 0.3, 8.0, 0.1),
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
                   command=lambda: self.play(self.chord_strings(), strum=True)).pack(side="left", padx=3)
        ttk.Button(actions, text="▲ Strum up",
                   command=lambda: self.play(self.chord_strings(), strum=True, up=True)).pack(side="left", padx=3)
        ttk.Button(actions, text="♫ Arpeggio", command=lambda: self.play(self.chord_strings(), arpeggio=True)).pack(side="left", padx=3)
        ttk.Button(actions, text="■ Stop", command=self.stop).pack(side="left", padx=3)
        ttk.Button(actions, text="Export the last sound (WAV)", command=self.export_wav).pack(side="left", padx=12)
        options = ttk.Frame(controls)
        options.pack(fill="x", pady=(6, 0))
        ttk.Label(options, text="Attack:").pack(side="left", padx=(3, 4))
        for label in ("Pick", "Fingers"):
            ttk.Radiobutton(options, text=label, value=label, variable=self.technique).pack(side="left", padx=4)
        ttk.Checkbutton(options, text="Steel stiffness", variable=self.stiff).pack(side="left", padx=(18, 12))
        ttk.Checkbutton(options, text="Palm mute", variable=self.palm).pack(side="left", padx=12)
        ttk.Checkbutton(options, text="Finger noise", variable=self.squeak_on).pack(side="left", padx=12)
        ttk.Checkbutton(options, text="Human feel", variable=self.human).pack(side="left", padx=12)
        ttk.Checkbutton(options, text="Sympathetic strings", variable=self.sympathy).pack(side="left", padx=12)
        room = ttk.Frame(controls)
        room.pack(fill="x", pady=(6, 0))
        ttk.Checkbutton(room, text="Room", variable=self.room_on).pack(side="left", padx=(3, 8))
        ttk.Combobox(room, textvariable=self.room_size, values=list(ROOMS), state="readonly", width=12).pack(side="left", padx=4)
        ttk.Label(room, text="walls:").pack(side="left", padx=(8, 2))
        ttk.Combobox(room, textvariable=self.room_material, values=list(MATERIALS), state="readonly", width=14).pack(side="left", padx=4)
        self.room_label = ttk.Label(room, text="")
        self.room_label.pack(side="left", padx=10)

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
            lines.append(f"Finger noise (GRM network), A string from fret 2 to 3 in 0.1 s: {sq['p'] * 1e3:.2f} mm winding wire, "
                         f"finger at {sq['v']:.2f} m/s -> winding at {sq['fsq']:.0f} Hz, longitudinal modes from "
                         f"{sq['fL']:.0f} Hz (c_L = {sq['cL']:.0f} m/s), {sq['P'] * 1e3:.0f} mW of friction.")
            pm = palm_network(mu6, L6, 0)["values"]
            lines.append(f"Palm (GRM network), low E: skin {pm['r']:.1f} N s/m at {pm['x'] * 1e3:.0f} mm from the bridge -> "
                         f"fundamental lasts {1 / (pm['s0'] * math.sin(math.pi * pm['q']) ** 2):.2f} s more at most, "
                         f"10th partial {1e3 / (pm['s0'] * math.sin(10 * math.pi * pm['q']) ** 2):.1f} ms.")
            sv = self.string_model(0, 0)
            loss = bridge_loss(modes, bv, sv["c"], sv["Leff"], sv["Zs"])
            lines.append(f"Bridge (GRM network): top impedance {bv['Zp']:.0f} kg/s, modal mass {bv['Mm'] * 1e3:.0f} g; "
                         f"low E gives the bridge {loss(np.array([sv['f1']]))[0]:.2f} /s at its fundamental, "
                         f"{loss(np.array([bv['f_lo']]))[0]:.0f} /s at the body resonance {bv['f_lo']:.0f} Hz.")
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

    def attack_model(self, i, fret, force, pluck, tech):
        """GRM attack of string i: release height, release time, click (cached)."""
        L, mu, T = self.read_inputs(i)
        key = ("attack", i, fret, L, mu, T, round(pluck, 3), round(force, 3), tech, round(float(self.pick_mm.get()), 3))
        if key not in self._model_cache:
            self._model_cache[key] = pluck_network(mu, L, T, fret, pluck, force, tech, float(self.pick_mm.get()))
        return self._model_cache[key]["values"]

    def palm_model(self, i, fret, x=PALM_X, force=PALM_FORCE):
        L, mu, _ = self.read_inputs(i)
        force = force * float(self.palm_intensity.get())    # how hard the player chooses to mute
        x, force = round(x * 2000) / 2000, 10 ** (round(math.log10(force) * 50) / 50)   # 0.5 mm, 0.02 dex
        key = ("palm", i, fret, L, mu, x, force)
        if key not in self._model_cache:
            self._model_cache[key] = palm_network(mu, L, fret, x, force)
        return self._model_cache[key]["values"]

    def action_model(self, i, fret):
        L, _, _ = self.read_inputs(i)
        key = ("action", fret, L)
        if key not in self._model_cache:
            self._model_cache[key] = action_network(L, fret)
        return self._model_cache[key]["values"]

    def _note(self, i, fret, start, length, gain, tau, pluck, palm=None, kind="strike"):
        v = self.string_model(i, fret)
        _, _, T = self.read_inputs(i)
        return {"i": i, "fret": fret, "f1": v["f1"], "B": v["B"] if self.stiff.get() else 0.0, "T": T,
                "Leff": v["Leff"], "Zs": v["Zs"], "c": v["c"], "start": start, "length": length,
                "muted": palm is not None, "palm": palm, "gain": gain, "tau": tau,
                "pluck": pluck, "kind": kind}

    def note(self, i, fret, start, length, muted=False, force_factor=1.0, pluck=None, stroke=None):
        """A string struck by the pick or a finger (attack network), possibly under the palm (palm network)."""
        pluck = float(self.pluck.get()) if pluck is None else pluck
        tech = "pick" if self.technique.get() == "Pick" else "finger"
        a = self.attack_model(i, fret, float(self.force.get()) * force_factor, pluck, tech)
        palm = None
        if muted:
            palm = self.palm_model(i, fret, *((stroke["palm_x"], stroke["palm_N"]) if stroke else ()))
        return self._note(i, fret, start, length, a["y0"] / Y_REF, a["tau"], pluck, palm)

    def finger_note(self, i, fret_finger, fret_string, start, length, kind, palm_stroke=None):
        """A finger lifting from fret_finger (the string jumps back to open, kind 'lift') or landing on
        fret_string (kind 'land'): the action network gives the height of the string under the finger."""
        h = self.action_model(i, fret_finger)
        L, _, _ = self.read_inputs(i)
        apex = max(h["xf"] / L, 0.02)
        fret = 0 if kind == "lift" else fret_string
        palm = None
        if palm_stroke is not None:
            palm = self.palm_model(i, fret, palm_stroke["palm_x"], palm_stroke["palm_N"])
        if kind == "lift":
            return self._note(i, 0, start, length, h["h"] / Y_REF, TAU_LIFT, apex, palm, kind="lift")
        return self._note(i, fret_string, start, length, LAND_SHARE * h["h"] / Y_REF, TAU_LAND, 0.03, palm, kind="land")

    def squeak(self, i, fret_from, fret_to, start, dur):
        """GRM noise of the finger leaving fret_from on wound string i (to fret_to, 0 = lifted)."""
        L, mu, _ = self.read_inputs(i)
        v = squeak_network(mu, L, self.core_fraction(i), fret_from, fret_to, dur, float(self.finger_force.get()))["values"]
        mid = (fret_from + (fret_to if fret_to > 0 else fret_from)) / 2.0
        bumps = []
        if fret_from > 0 and fret_to > 0:
            # the finger rides over the fret wires between the two frets; its position follows the slide
            # x(u) = x_a + (x_b - x_a) (1 - cos(pi u)) / 2, from just behind one fret to just behind the other
            pos = lambda k: v["L"] * (1 - 2 ** (-k / 12.0))
            xa, xb = pos(fret_from) - 0.005, pos(fret_to) - 0.005
            for k in range(min(fret_from, fret_to), max(fret_from, fret_to)):
                c = (pos(k) - xa) / (xb - xa)
                if 0.0 < c < 1.0:
                    bumps.append(math.acos(1 - 2 * c) / math.pi)
        return {"i": i, "start": start, "dur": dur, "fsq": v["fsq"], "P": v["P"], "fL": v["fL"], "v": v["v"],
                "bumps": bumps, "N": v["N"],
                "x": 1 - 2 ** (-mid / 12.0), "from": fret_from, "to": fret_to}

    def player_rng(self):
        return np.random.default_rng() if self.human.get() else None

    def strokes(self, grid, step):
        """Run the player network on a list of (time, index in the bar)."""
        rng = self.player_rng()
        if rng is None:                       # no human feel: the intents are exactly the grid
            class Exact:
                @staticmethod
                def normal(_m, _s):
                    return 0.0
            rng = Exact()
        return player_network(grid, step, float(self.pluck.get()), rng, float(self.swing_cm.get()) / 100.0)

    def change_hand(self, held, new, t_change, lead, notes, last, rng, palm_stroke=None):
        """The fingers leave the frets of `held` and land on those of `new`, before a stroke at t_change + lead.
        Adds lift and landing notes (every string) and winding noises (wound strings); a lifted string stops
        the note it was ringing. palm_stroke: the palm stays on the strings (palm-muted playing), so what the
        fingers do on the strings is muted too. Returns the noises."""
        squeaks = []
        noises = bool(self.squeak_on.get())
        jitter = (lambda: rng.normal(0.0, 0.012)) if rng is not None else (lambda: 0.0)
        for i in sorted(set(held) | set(new)):
            f_old, f_new = held.get(i, 0), new.get(i, 0)
            if f_old == f_new:
                continue
            t_lift = t_change + max(0.0, 0.1 * lead + jitter())
            t_land = t_change + max(0.3 * lead, 0.65 * lead + jitter())
            if f_old > 0:
                if i in last:                          # the old note stops when the finger leaves
                    prev = last[i]
                    prev["length"] = max(0.02, min(prev["length"], t_lift - prev["start"]))
                    del last[i]
                if not noises:
                    continue
                nt = self.finger_note(i, f_old, 0, t_lift, 1.5, "lift", palm_stroke)
                notes.append(nt)
                last[i] = nt
                if STRINGS[i]["wound"]:
                    squeaks.append(self.squeak(i, f_old, f_new, t_lift, max(0.04, t_land - t_lift)))
            if f_new > 0 and noises:
                if i in last:
                    prev = last[i]
                    prev["length"] = max(0.02, min(prev["length"], t_land - prev["start"]))
                nt = self.finger_note(i, f_new, f_new, t_land, 1.5, "land", palm_stroke)
                notes.append(nt)
                last[i] = nt
        return squeaks

    def play(self, indices, strum=False, up=False, arpeggio=False):
        indices = sorted(indices, reverse=up)  # index 0 is string 6: down = from the bass
        if not indices:
            return
        try:
            self.recalculate_all()
            dur = float(self.duration.get())
            frets = {i: int(self.fret_vars[i].get()) for i in indices}
            lead = 0.14
            notes, last, squeaks = [], {}, []
            t0 = 0.0
            rng = self.player_rng()
            if self.last_frets and frets != self.last_frets:
                palm_stroke = {"palm_x": PALM_X, "palm_N": PALM_FORCE} if self.palm.get() else None
                squeaks = self.change_hand(self.last_frets, frets, 0.0, lead, notes, last, rng, palm_stroke)
                t0 = lead
            self.last_frets = frets
            if arpeggio:
                strokes = self.strokes([(t0 + 0.13 * k, k) for k in range(len(indices))], 0.13)
                for k, i in enumerate(indices):
                    nt = self.note(i, frets[i], max(0.0, strokes[k]["t"]), dur, self.palm.get(), strokes[k]["force"],
                                   strokes[k]["p"], strokes[k])
                    notes.append(nt)
            else:
                stroke = self.strokes([(t0, 0)], 0.25)[0]
                contacts = strum_contacts(indices, stroke, up) if strum else [(i, 0.0, 1.0) for i in indices]
                for i, delay, share in contacts:
                    if i in last:
                        prev = last[i]
                        prev["length"] = max(0.02, min(prev["length"], stroke["t"] + delay - prev["start"]))
                    notes.append(self.note(i, frets[i], max(0.0, stroke["t"] + delay), dur, self.palm.get(),
                                           stroke["force"] * share, stroke["p"], stroke))
            total = max(nt["start"] + nt["length"] for nt in notes) + 0.05
            spans = [(0.0, total, [self.palm_model(i, frets.get(i, 0)) for i in range(6)])] if self.palm.get() else []
            self.start_playback(notes, total, "Playing: " + " – ".join(STRINGS[i]["note"] for i in indices),
                                squeaks=squeaks, palm_spans=spans)
        except Exception as exc:
            messagebox.showerror("Audio error", str(exc))

    def render(self, notes, total, squeaks, palm_spans=()):
        modes, bv = body_modes(float(self.body_size.get()), float(self.top_mm.get()), float(self.coupling.get()))
        open_strings = [self._note(i, 0, 0.0, total, 0.0, 0.0, 0.5, kind="open") for i in range(6)]
        return render_guitar(notes, total, float(self.damping.get()), float(self.brightness.get()), modes, bv,
                             squeaks, float(self.body_amount.get()), bool(self.sympathy.get()), open_strings,
                             palm_spans)

    def start_playback(self, notes, total, label, loop_len=None, squeaks=(), loop_from=0.0, palm_spans=()):
        """Render the whole guitar, then play once or (loop_len in s) in a seamless loop taken from
        loop_from: what rings across the loop point is already in the rendered passes."""
        audio = self.render(notes, total, squeaks, palm_spans)
        if self.room_on.get():
            size = ROOMS[self.room_size.get()]
            room = room_network(size, self.room_material.get())
            audio = apply_room(audio.astype(float), room, size, float(self.room_distance.get()))
            self.room_label.config(text=f"reverberation {room['RT3']:.2f} s at 1 kHz ({room['RT0']:.2f} s at 125 Hz), "
                                        f"critical distance {room['rc']:.2f} m")
        else:
            self.room_label.config(text="")
        if loop_len:
            a = int(round(loop_from * SAMPLE_RATE))
            audio = audio[a:a + int(round(loop_len * SAMPLE_RATE))]
            notes = [dict(nt, start=nt["start"] - loop_from) for nt in notes]
            squeaks = [dict(sq, start=sq["start"] - loop_from) for sq in squeaks]
        peak = np.max(np.abs(audio)) if len(audio) else 0.0
        if peak > 0:
            audio = audio / peak
        self.audio = (audio * float(self.volume.get())).astype(np.float32)
        self.voices_shown = notes
        self.squeaks_shown = list(squeaks)
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

    def play_sequence(self, passes=None):
        try:
            self.recalculate_all()
            step_s = 60.0 / max(int(self.bpm.get()), 1) / 2.0       # steps are eighth notes
            steps = []
            for k in range(self.STEPS):
                steps.append((self.parse_step(self.step_vars[k].get()), self.dir_vars[k].get()))
            ring = float(self.duration.get())
            looping = bool(self.loop.get()) and passes is None
            if passes is None:
                passes = 4 if looping else max(int(self.repeats.get()), 1)   # loop: keep passes 2 and 3
            # 1) the player network: one stroke per step that strikes, over all the passes
            lead = min(0.25, 0.7 * step_s)        # time the left hand takes to change shape (hypothesis)
            offset = lead + 0.02                  # room for the first chord shape to be taken
            grid = [(offset + (rep_ * self.STEPS + k) * step_s, k) for rep_ in range(passes)
                    for k, (content, d) in enumerate(steps) if content is not None and d != "·"]
            if not grid:
                messagebox.showinfo("Sequencer", "The sequence is empty.")
                return
            strokes = iter(self.strokes(grid, step_s))
            rng = self.player_rng()
            # 2) the strokes meet the strings; the left hand changes shape before the strokes that need it
            notes, last, squeaks, held = [], {}, [], {}
            palm_spans = []
            total = 0.0
            arpeggio_mode = self.seq_mode.get() == "Arpeggio"
            for rep_ in range(passes):
                for k, (content, d) in enumerate(steps):
                    if content is None or d == "·":
                        continue          # rest, or the previous strum keeps ringing
                    stroke = next(strokes)
                    single = len(content) == 1 or self.step_vars[k].get() not in CHORDS
                    new = dict(content)
                    if new != held:            # the hand changes shape: fingers leave and land
                        squeaks += self.change_hand(held, new, stroke["t"] - lead, lead, notes, last, rng,
                                                    stroke if d == "x" else None)
                    held = new
                    arpeggio = arpeggio_mode and not single
                    up = d == "↑"
                    if d == "x":                   # the palm rests on all the strings until the next step
                        palm_spans.append((stroke["t"] - lead, stroke["t"] + step_s,
                                           [self.palm_model(i, new.get(i, 0), stroke["palm_x"], stroke["palm_N"])
                                            for i in range(6)]))
                    if arpeggio:               # one slot of the pattern; the other strings keep ringing
                        pattern = self.ARPEGGIOS[self.arp_pattern.get()]
                        chosen = self.arpeggio_slot(content, pattern[k % len(pattern)])
                        contacts = [(i, 0.0, 1.15 if i <= 2 else 0.85) for i, _ in chosen]   # thumb on the bass
                    elif single:
                        contacts = [(i, 0.0, 1.0) for i, _ in content]
                    else:
                        order = sorted((i for i, _ in content), reverse=up)
                        contacts = strum_contacts(order, stroke, up)
                    for i, delay, share in contacts:
                        start = max(0.0, stroke["t"] + delay)
                        if i in last:     # a string struck again stops ringing
                            prev = last[i]
                            prev["length"] = max(0.02, min(prev["length"], start - prev["start"]))
                        nt = self.note(i, new[i], start, ring, muted=(d == "x"),
                                       force_factor=stroke["force"] * share, pluck=stroke["p"], stroke=stroke)
                        notes.append(nt)
                        last[i] = nt
                        total = max(total, start + ring)
            self.status.set("Rendering the whole guitar…")
            self.root.update_idletasks()
            bar = self.STEPS * step_s
            if looping:
                self.start_playback(notes, max(total, passes * bar), f"Looping sequence, {self.bpm.get()} BPM, "
                                    "two passes that differ (■ Stop to end it)", loop_len=2 * bar, squeaks=squeaks,
                                    loop_from=offset + bar, palm_spans=palm_spans)
            else:
                self.start_playback(notes, total, f"Sequence: {self.STEPS} steps × {passes}, {self.bpm.get()} BPM",
                                    squeaks=squeaks, palm_spans=palm_spans)
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
            amps = pluck_amplitudes(len(n), nt.get("pluck", self.pluck.get())) * nt.get("gain", 1.0)
            sigma = (1.0 + (fn / 1800.0) ** 2) / self.damping.get()
            if nt.get("palm") is not None:
                sigma = sigma + palm_sigma(fn, nt["palm"])
            tau = 1.0 / sigma
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
