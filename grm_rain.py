# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Anthony Charretier
"""
GRM Rain - the sound of drops falling on water, every drop a set of GRM relations.

The sound of rain on water is mostly not the impact: it is a tiny air bubble trapped under the surface, ringing
like a bell for a millisecond (Pumphrey, Crum & Bjorno 1989; Prosperetti & Oguz, Annu. Rev. Fluid Mech. 25, 1993:
"the impact contributes an insignificant fraction of the total radiated energy"). Drops of 0.82 to 1.1 mm at their
terminal velocity trap one bubble every time (regular entrainment): that is the 14 kHz hiss of light rain. Larger,
faster drops trap a bubble about half of the time, of very different sizes: the lower "plinks".

The networks:
  falling drop     m g = 1/2 rho_air C_d(Re) (pi D^2 / 4) v^2       terminal velocity (drag of a sphere,
                   Re = rho_air v D / mu_air,  C_d = 24/Re (1 + 0.15 Re^0.687) + 0.42 / (1 + 42500 Re^-1.16))
  impact           Fr = v^2 / (g a),  We = rho_w v^2 a / sigma       (a = D / 2)
  regular window   k_lo Fr^0.179 < We < k_hi Fr^0.247                (the exponents of the review; the two constants
                   are fixed by the network so that the window, at terminal velocity, runs from 0.82 to 1.1 mm)
  bubble           f = (1 / 2 pi R) sqrt(3 gamma P0 / rho_w)         Minnaert (1933)
                   damping delta = kR (radiation) + 4 mu_w / (rho_w w R^2) (viscosity) + thermal (Devin 1959)
                   p(t) = A e^(-delta w t / 2) sin(w t)
  crater           the bubble is born when the crater collapses: t ~ sqrt(H / g), H ~ a Fr^(1/4) (hypothesis)

Hypotheses (no measured value found): the size of the regular bubble follows the drop (R = R14 D / 0.95 mm, with
R14 the Minnaert radius of a 14 kHz bubble); the initial wall displacement is 3 % of the radius (0.6 % for the irregular bubbles of large drops); large drops
(We above the window) trap a bubble with probability 0.5, of radius 0.33 to 1.6 mm (2 to 10 kHz); the impact itself is a dipole
pulse of duration D / v carrying 1e-4 of the drop's kinetic energy relative to the bubble.
"""
import math

import numpy as np

from grm import GlobalRelationalNetwork

SAMPLE_RATE = 44100
LN10 = math.log(10.0)

# Air and water at 20 C, 1 atm (handbook values)
RHO_AIR, MU_AIR = 1.204, 1.81e-5
RHO_W, MU_W, SIGMA_W = 998.0, 1.0e-3, 0.0728
P0, GAMMA_AIR, D_THERMAL_AIR = 101325.0, 1.4, 2.2e-5      # thermal diffusivity of air (m2/s)
C_WATER = 1482.0
G = 9.81
WINDOW = (0.82e-3, 1.1e-3)      # m: drop diameters that always trap a bubble at terminal velocity (review above)
LARGE_FROM = 2.0e-3             # m: from here on drops trap bubbles again, of many sizes; between 1.1 and 2 mm they
                                # trap none and are quiet (Nystuen, Listening to raindrops, NASA Earth Observatory)
IMPACT_AT = 4.0e-3              # m: a very large drop's impact is as loud as a large bubble (hypothesis, scale)
ALPHA_LO, ALPHA_HI = 0.179, 0.247
F_PEAK = 14000.0                # Hz, the peak of light rain on water
WALL = 0.03                     # initial bubble wall displacement / radius, regular bubbles (hypothesis)
WALL_LARGE = 0.006              # ... for the irregular bubbles of large drops (hypothesis, set so that light rain
                                # peaks at 13-25 kHz and heavy rain spreads down to 1 kHz, as measured by Nystuen)
BIG_PROBABILITY = 0.5


# ============================================================
# NETWORKS
# ============================================================

def drag_cd(Re):
    return 24.0 / Re * (1 + 0.15 * Re ** 0.687) + 0.42 / (1 + 42500.0 * Re ** -1.16)


def terminal_network(D):
    """Terminal velocity of a water drop of diameter D (m): weight = drag."""
    m = RHO_W * math.pi * D ** 3 / 6
    nodes = {"v": {"guess": min(9.0, 4000.0 * D)}, "Re": {"guess": 300.0}, "Cd": {"guess": 0.7}}
    rels = [
        {"name": "Reynolds", "terms": {"Re": 1, "v": -1}, "rhs": math.log10(RHO_AIR * D / MU_AIR), "sigma": 1e-9},
        {"name": "drag law", "type": "fn", "nodes": ["Cd", "Re"], "sigma": 1e-9,
         "f": lambda v: math.log10(v["Cd"]) - math.log10(drag_cd(v["Re"]))},
        {"name": "balance", "terms": {"Cd": 1, "v": 2}, "rhs": math.log10(m * G / (0.5 * RHO_AIR * math.pi * D ** 2 / 4)),
         "sigma": 1e-9},
    ]
    return GlobalRelationalNetwork(nodes, rels).solve(compute_uncertainty=False)["values"]["v"]


def impact_numbers(D, v):
    a = D / 2
    return v * v / (G * a), RHO_W * v * v * a / SIGMA_W          # Froude, Weber


def window_network():
    """The two constants of the regular-entrainment window, fixed by its two ends at terminal velocity."""
    lo_D, hi_D = WINDOW
    fr_lo, we_lo = impact_numbers(lo_D, terminal_network(lo_D))
    fr_hi, we_hi = impact_numbers(hi_D, terminal_network(hi_D))
    nodes = {"k_lo": {"guess": 40.0}, "k_hi": {"guess": 48.0}}
    # along the terminal-velocity curve the Weber number grows with D faster than the boundaries: the small
    # end of the window lies on the lower boundary, the large end on the upper one
    rels = [{"name": "lower end", "terms": {"k_lo": 1}, "rhs": math.log10(we_lo) - ALPHA_LO * math.log10(fr_lo), "sigma": 1e-9},
            {"name": "upper end", "terms": {"k_hi": 1}, "rhs": math.log10(we_hi) - ALPHA_HI * math.log10(fr_hi), "sigma": 1e-9}]
    v = GlobalRelationalNetwork(nodes, rels).solve(compute_uncertainty=False)["values"]
    return v["k_lo"], v["k_hi"]


def thermal_damping(R, w):
    """Devin (1959): thermal damping of a gas bubble, X = R sqrt(2 w / D_th)."""
    X = R * math.sqrt(2 * w / D_THERMAL_AIR)
    X = min(X, 300.0)
    num = X * (math.sinh(X) + math.sin(X)) - 2 * (math.cosh(X) - math.cos(X))
    den = X * X * (math.cosh(X) - math.cos(X)) + 3 * (GAMMA_AIR - 1) * X * (math.sinh(X) - math.sin(X))
    return 3 * (GAMMA_AIR - 1) * num / den


def bubble_network(R):
    """Minnaert frequency and total damping of an air bubble of radius R (m) in water."""
    f0 = math.sqrt(3 * GAMMA_AIR * P0 / RHO_W) / (2 * math.pi * R)
    nodes = {"f": {"guess": f0}, "R": {"guess": R}, "delta": {"guess": 0.05}}
    rels = [
        {"name": "Minnaert", "terms": {"f": 1, "R": 1}, "rhs": math.log10(math.sqrt(3 * GAMMA_AIR * P0 / RHO_W) / (2 * math.pi)),
         "sigma": 1e-9},
        {"name": "damping", "type": "fn", "nodes": ["delta", "f", "R"], "sigma": 1e-9,
         "f": lambda v: math.log10(v["delta"]) - math.log10(
             2 * math.pi * v["f"] * v["R"] / C_WATER + 4 * MU_W / (RHO_W * 2 * math.pi * v["f"] * v["R"] ** 2)
             + thermal_damping(v["R"], 2 * math.pi * v["f"]))},
    ]
    v = GlobalRelationalNetwork(nodes, rels).solve(measured_dict={"R": (R, 1e-6)}, compute_uncertainty=False)["values"]
    return v["f"], v["delta"]


# ============================================================
# A DROP AND ITS SOUND
# ============================================================

class RainPhysics:
    """Tables built once from the networks (drop sizes on a fine grid), then read for every drop."""

    def __init__(self):
        self.D = np.geomspace(0.2e-3, 6e-3, 60)
        self.v_t = np.array([terminal_network(d) for d in self.D])
        self.k_lo, self.k_hi = window_network()
        # the Weber number where large drops start trapping bubbles again, and the impact scale (E ~ M^3 T)
        self.we_large = impact_numbers(LARGE_FROM, self.terminal(LARGE_FROM))[1]
        v4 = self.terminal(IMPACT_AT)
        self.impact_ref = math.sqrt((v4 / 343.0) ** 3 * 0.5 * RHO_W * math.pi * IMPACT_AT ** 3 / 6 * v4 * v4)
        self.R14 = math.sqrt(3 * GAMMA_AIR * P0 / RHO_W) / (2 * math.pi * F_PEAK)
        self.R_grid = np.geomspace(0.05e-3, 4e-3, 50)
        fb = [bubble_network(r) for r in self.R_grid]
        self.f_grid = np.array([x[0] for x in fb])
        self.d_grid = np.array([x[1] for x in fb])

    def terminal(self, D):
        return float(np.exp(np.interp(math.log(D), np.log(self.D), np.log(self.v_t))))

    def regime(self, D, v):
        """'regular', 'large' or 'none' for a drop of diameter D hitting at speed v."""
        fr, we = impact_numbers(D, v)
        if self.k_lo * fr ** ALPHA_LO < we < self.k_hi * fr ** ALPHA_HI:
            return "regular"
        if we >= self.we_large:
            return "large"
        return "none"

    def bubble(self, R):
        lr = math.log(R)
        return (float(np.exp(np.interp(lr, np.log(self.R_grid), np.log(self.f_grid)))),
                float(np.exp(np.interp(lr, np.log(self.R_grid), np.log(self.d_grid)))))

    def drop_sound(self, D, v, rng, distance=1.0):
        """Pressure (arbitrary common unit, same for every drop) of one drop at `distance` m: the impact pulse
        and, if one is trapped, the bubble. Returns (samples, delay of the start in s)."""
        a = D / 2
        fr, _ = impact_numbers(D, v)
        kind = self.regime(D, v)
        parts = []
        # the impact: a short dipole pulse (half sine of duration D / v). Its radiated energy goes as M^3 T
        # (Mach number of the impact, kinetic energy: the review above); scaled so that a 4 mm drop's impact
        # is as loud as a 1 mm bubble ringing at 1 m (hypothesis for the scale, not for the law)
        T = max(D / v, 2.0 / SAMPLE_RATE)
        n = max(2, int(T * SAMPLE_RATE))
        kinetic = 0.5 * RHO_W * math.pi * D ** 3 / 6 * v * v
        loud = math.sqrt((v / 343.0) ** 3 * kinetic) / self.impact_ref
        ref_bubble = RHO_W * (2 * math.pi * self.bubble(1e-3)[0]) ** 2 * 1e-6 * WALL * 1e-3
        pulse = np.sin(np.linspace(0, 2 * math.pi, n)) * loud * ref_bubble / distance   # a dipole: no net push
        parts.append((0.0, pulse))
        R = None
        if kind == "regular":
            R = self.R14 * D / 0.95e-3 * (1 + 0.03 * rng.standard_normal())
        elif kind == "large" and rng.random() < BIG_PROBABILITY:
            R = math.exp(rng.uniform(math.log(0.33e-3), math.log(1.6e-3)))     # 2 to 10 kHz
        wall = WALL if kind == "regular" else WALL_LARGE
        if R is not None:
            f, delta = self.bubble(R)
            w = 2 * math.pi * f
            dur = min(10.0 / (delta * f), 0.5)
            t = np.arange(int(dur * SAMPLE_RATE)) / SAMPLE_RATE
            # pressure of a pulsating sphere at distance r: rho w^2 R^2 xi / r, xi = WALL R
            amp = RHO_W * w * w * R ** 2 * wall * R / distance
            ring = amp * np.exp(-delta * w * t / 2) * np.sin(w * t)
            ring *= np.minimum(1.0, t * f)       # the bubble pinches off within about one period
            crater = math.sqrt(a * fr ** 0.25 / G)
            parts.append((crater, ring))
        end = max(off + len(p) / SAMPLE_RATE for off, p in parts)
        out = np.zeros(int(end * SAMPLE_RATE) + 1)
        for off, p in parts:
            i = int(off * SAMPLE_RATE)
            out[i:i + len(p)] += p
        return out, kind


def marshall_palmer(rate_mm_h, d_mm):
    """Drops per m3 per mm of diameter (Marshall & Palmer 1948): N0 exp(-Lambda D)."""
    lam = 4.1 * max(rate_mm_h, 1e-3) ** -0.21
    return 8000.0 * np.exp(-lam * d_mm)


def drops_per_second(physics, rate_mm_h, area):
    """Drops hitting an area (m2) per second, by diameter bin: sum of N(D) v(D) dD."""
    d_mm = np.linspace(0.3, 6.0, 58)
    dd = d_mm[1] - d_mm[0]
    v = np.array([physics.terminal(d * 1e-3) for d in d_mm])
    flux = marshall_palmer(rate_mm_h, d_mm) * v * dd * area
    return d_mm, flux


# ============================================================
# STREAMING: drops arrive while the window runs, the room is added block by block
# ============================================================

class RainVoice:
    """A dry ring buffer where each drop's sound is added at its time, a wet ring the room fills block by block
    (overlap-add with the room's impulse response), and an output stream that reads the wet ring."""

    def __init__(self, seconds=8.0, latency=0.12):
        self.n = int(seconds * SAMPLE_RATE)
        self.dry = np.zeros(self.n)
        self.wet = np.zeros(self.n)
        self.read = 0                     # absolute sample counter of the stream
        self.done = 0                     # dry samples already passed through the room
        self.latency = int(latency * SAMPLE_RATE)
        self.ir = np.array([1.0])
        self.gain = 1.0
        self.stream = None
        self.clock0 = None
        try:
            import sounddevice as sd
            self.stream = sd.OutputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32",
                                          callback=self._callback, blocksize=1024)
            self.stream.start()
        except Exception:
            self.stream = None

    def _callback(self, outdata, frames, _time, _status):
        idx = (self.read + np.arange(frames)) % self.n
        out = self.wet[idx] * self.gain
        self.wet[idx] = 0.0
        self.read += frames
        outdata[:, 0] = np.tanh(out).astype(np.float32)

    def now(self):
        if self.stream is not None:
            return self.read
        import time
        if self.clock0 is None:
            self.clock0 = time.perf_counter()
        return int((time.perf_counter() - self.clock0) * SAMPLE_RATE)

    def add(self, sound, delay=0.0):
        start = self.now() + self.latency + int(delay * SAMPLE_RATE)
        idx = (start + np.arange(len(sound))) % self.n
        np.add.at(self.dry, idx, sound)

    def set_room(self, ir):
        self.ir = np.asarray(ir, dtype=float)

    def process(self):
        """Pass the dry samples that are complete (no drop can still add to them) through the room."""
        horizon = self.now() + self.latency
        if self.done < horizon - self.n // 2:
            self.done = horizon - self.latency
        if horizon <= self.done:
            return
        block_idx = np.arange(self.done, horizon) % self.n
        block = self.dry[block_idx].copy()
        self.dry[block_idx] = 0.0
        L = len(block) + len(self.ir) - 1
        nfft = 1 << (L - 1).bit_length()
        y = np.fft.irfft(np.fft.rfft(block, nfft) * np.fft.rfft(self.ir, nfft), nfft)[:L]
        L = min(L, self.n - SAMPLE_RATE)
        idx = (self.done + np.arange(L)) % self.n
        self.wet[idx] += y[:L]
        self.done = horizon

    def close(self):
        if self.stream is not None:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass


def environment_ir(name, material, distance):
    """Impulse response of the place where one listens: outdoors (direct sound only, with the air taking the
    highs over the distance) or one of the rooms of the room network (grm_guitar)."""
    if name == "Outdoors":
        # air absorption of the highs: about 0.1 dB/m at 4 kHz, 0.4 dB/m at 16 kHz (ISO 9613-1, 20 C, 50 %): a gentle
        # one-pole low-pass whose corner falls with distance (hypothesis for the shape)
        fc = 20000.0 / (1 + distance / 15.0)
        a = math.exp(-2 * math.pi * fc / SAMPLE_RATE)
        n = 256
        return (1 - a) * a ** np.arange(n) / max(distance, 0.3)
    from grm_guitar import ROOMS, room_impulse, room_network
    size = ROOMS[name]
    room = room_network(size, material)
    return room_impulse(room, size, distance)


def render_rain(seconds, rate_mm_h, area, ir=None, seed=0, cap_per_second=4000):
    """Offline: `seconds` of rain on `area` m2 of water, heard through the impulse response ir."""
    physics = RainPhysics()
    rng = np.random.default_rng(seed)
    d_mm, flux = drops_per_second(physics, rate_mm_h, area)
    counts = rng.poisson(flux * seconds)
    total = int(counts.sum())
    n_synth = min(total, int(cap_per_second * seconds))
    scale = math.sqrt(total / n_synth) if n_synth else 1.0
    sizes = rng.choice(np.repeat(d_mm, counts), size=n_synth, replace=False) if n_synth else []
    out = np.zeros(int((seconds + 0.6) * SAMPLE_RATE))
    for d in sizes:
        D = d * 1e-3
        snd, _ = physics.drop_sound(D, physics.terminal(D), rng)
        i = int(rng.uniform(0, seconds) * SAMPLE_RATE)
        j = min(len(out), i + len(snd))
        out[i:j] += snd[:j - i] * scale
    if ir is not None:
        L = len(out) + len(ir) - 1
        nfft = 1 << (L - 1).bit_length()
        out = np.fft.irfft(np.fft.rfft(out, nfft) * np.fft.rfft(ir, nfft), nfft)[:len(out)]
    return out[:int(seconds * SAMPLE_RATE)], total
