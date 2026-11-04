# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Anthony Charretier
"""
GRM Water - a basin of liquid whose waves come from a network of relations.

The surface of the liquid is the sum of the standing waves (modes) of the basin: walls that reflect make
cosine modes, cos(m pi x / Lx) cos(n pi y / Ly). How fast each mode swings and how fast it dies is not
written by hand: it is the answer of a GRM network that puts in relation gravity, surface tension, depth
and viscosity (linear water waves):

    gravity part         G = g k
    capillary part       C = (sigma / rho) k^3
    restoring            S = G + C
    depth                th = tanh(k h)
    dispersion           w^2 = S * th                       (Lamb, Hydrodynamics; any textbook on water waves)
    bulk viscosity       g_bulk = 2 nu k^2                  (Lamb)
    walls and bottom     g_edge = sqrt(nu w / 2) (k / sinh(2 k h) + 1/Lx + 1/Ly)
                         (laminar boundary layers; bottom and side terms as in Robertson & Rousseaux,
                          "Viscous dissipation of surface waves...", arXiv:1706.05255; the 1/Lx + 1/Ly
                          of a closed box is a hypothesis: the paper treats a channel of width b, 1/b)
    decay                gamma = g_bulk + g_edge

The network is solved once for a set of wavenumbers covering the basin (with the uncertainties of the
measured liquid properties); the modes in between read it by interpolation. Another small network runs
backwards: given the frequency of the paddle, which wavelength must it make?

Click: a drop falls. Drag: a finger moves through the water (watch the wake). Rain, paddle, liquids,
planets, depth: everything changes the network, and the waves with it.

Limits: linear waves (small amplitude, no breaking, no splashes), a flat bottom, perfectly reflecting walls.
"""
import argparse
import math
import time

import numpy as np

from grm import GlobalRelationalNetwork

try:
    import tkinter as tk
    from tkinter import ttk
except Exception:  # headless use
    tk = None
    ttk = None

LN10 = math.log(10.0)

# Liquids at 20 C: density (kg/m3), kinematic viscosity (m2/s), surface tension (N/m) - usual handbook values
LIQUIDS = {
    "Water": (998.0, 1.00e-6, 0.0728),
    "Sea water": (1025.0, 1.05e-6, 0.0735),
    "Olive oil": (911.0, 9.0e-5, 0.032),
    "Mercury": (13534.0, 1.15e-7, 0.485),
}
PLANETS = {"Earth": 9.81, "Mars": 3.71, "Moon": 1.62}
# basins: length, width (m), default depth (m)
BASINS = {
    "Puddle": (0.30, 0.20, 0.01),
    "Bathtub": (1.60, 0.70, 0.30),
    "Pool": (12.0, 6.0, 1.5),
    "Harbour": (300.0, 150.0, 8.0),
}
SAMPLES = 32           # wavenumbers solved by the network
MODES_LONG = 96        # modes along the long side
GRID_LONG = 128        # points where the surface is computed, along the long side


# ============================================================
# GRM NETWORKS
# ============================================================

def _measured(liquid, g, h):
    rho, nu, sig = LIQUIDS[liquid]
    # handbook values: density to 0.1 %, viscosity 2 %, surface tension 1 % (clean surface); depth to 1 %
    return {"rho": (rho, 0.0005), "nu": (nu, 0.009), "sig": (sig, 0.0045), "g": (g, 1e-5), "h": (h, 0.0045)}


def water_network(liquid, g, h, Lx, Ly, k_values):
    """The physics of the waves at the wavenumbers k_values: one GRM network for all of them."""
    nodes = {"rho": {"guess": 1000.0}, "nu": {"guess": 1e-6}, "sig": {"guess": 0.07}, "g": {"guess": 9.8},
             "h": {"guess": 0.3}, "c0": {"guess": 1.0}, "lc": {"guess": 0.003}, "cmin": {"guess": 0.23}}
    rels = [
        {"name": "shallow-water speed", "terms": {"c0": 2, "g": -1, "h": -1}, "rhs": 0.0, "sigma": 1e-9},
        {"name": "capillary length", "terms": {"lc": 2, "sig": -1, "rho": 1, "g": 1}, "rhs": 0.0, "sigma": 1e-9},
        {"name": "slowest ripple", "terms": {"cmin": 4, "g": -1, "sig": -1, "rho": 1}, "rhs": math.log10(4.0),
         "sigma": 1e-9},
    ]
    for i, k in enumerate(k_values):
        lk = math.log10(k)
        for name, guess in (("G", 9.8 * k), ("C", 7e-5 * k ** 3), ("S", 9.8 * k + 7e-5 * k ** 3),
                            ("th", math.tanh(k * h)), ("w", math.sqrt((9.8 * k + 7e-5 * k ** 3) * math.tanh(k * h))),
                            ("gb", 2e-6 * k * k), ("ge", 1e-3), ("gam", 1e-3)):
            nodes[f"{name}{i}"] = {"guess": guess}
        rels += [
            {"name": f"gravity {i}", "terms": {f"G{i}": 1, "g": -1}, "rhs": lk, "sigma": 1e-9},
            {"name": f"capillarity {i}", "terms": {f"C{i}": 1, "sig": -1, "rho": 1}, "rhs": 3 * lk, "sigma": 1e-9},
            {"name": f"restoring {i}", "type": "fn", "nodes": [f"S{i}", f"G{i}", f"C{i}"], "sigma": 1e-9,
             "f": lambda v, i=i: math.log10(v[f"S{i}"]) - math.log10(v[f"G{i}"] + v[f"C{i}"])},
            {"name": f"depth {i}", "type": "fn", "nodes": [f"th{i}", "h"], "sigma": 1e-9,
             "f": lambda v, i=i, k=k: math.log10(v[f"th{i}"]) - math.log10(math.tanh(k * v["h"]))},
            {"name": f"dispersion {i}", "terms": {f"w{i}": 2, f"S{i}": -1, f"th{i}": -1}, "rhs": 0.0, "sigma": 1e-9},
            {"name": f"bulk viscosity {i}", "terms": {f"gb{i}": 1, "nu": -1}, "rhs": math.log10(2 * k * k),
             "sigma": 1e-9},
            {"name": f"boundary layers {i}", "type": "fn", "nodes": [f"ge{i}", "nu", f"w{i}", "h"], "sigma": 1e-9,
             "f": lambda v, k=k, i=i: math.log10(v[f"ge{i}"]) - math.log10(
                 math.sqrt(v["nu"] * v[f"w{i}"] / 2) * (k / math.sinh(min(2 * k * v["h"], 700.0)) + 1 / Lx + 1 / Ly))},
            {"name": f"decay {i}", "type": "fn", "nodes": [f"gam{i}", f"gb{i}", f"ge{i}"], "sigma": 1e-9,
             "f": lambda v, i=i: math.log10(v[f"gam{i}"]) - math.log10(v[f"gb{i}"] + v[f"ge{i}"])},
        ]
    out = GlobalRelationalNetwork(nodes, rels).solve(measured_dict=_measured(liquid, g, h), max_iterations=60)
    v, u = out["values"], out["uncertainty"]
    n = len(k_values)
    return {"k": np.asarray(k_values, dtype=float),
            "w": np.array([v[f"w{i}"] for i in range(n)]),
            "w_rel": np.array([u[f"w{i}"] for i in range(n)]),
            "gamma": np.array([v[f"gam{i}"] for i in range(n)]),
            "c0": v["c0"], "lc": v["lc"], "cmin": v["cmin"], "converged": out["converged"],
            "values": v}


def wavelength_network(liquid, g, h, frequency):
    """Backwards: the paddle fixes the frequency, the network finds the wavenumber that goes with it."""
    w = 2 * math.pi * frequency
    k_deep = w * w / g
    nodes = {"rho": {"guess": 1000.0}, "sig": {"guess": 0.07}, "g": {"guess": 9.8}, "h": {"guess": 0.3},
             "k": {"guess": k_deep / math.tanh(math.sqrt(k_deep * h) + 1e-9) if h > 0 else k_deep},
             "G": {"guess": g * k_deep}, "C": {"guess": 1e-4 * k_deep ** 3}, "S": {"guess": g * k_deep},
             "th": {"guess": 0.5}, "w": {"guess": w}}
    rels = [
        {"name": "gravity", "terms": {"G": 1, "g": -1, "k": -1}, "rhs": 0.0, "sigma": 1e-9},
        {"name": "capillarity", "terms": {"C": 1, "sig": -1, "rho": 1, "k": -3}, "rhs": 0.0, "sigma": 1e-9},
        {"name": "restoring", "type": "fn", "nodes": ["S", "G", "C"], "sigma": 1e-9,
         "f": lambda v: math.log10(v["S"]) - math.log10(v["G"] + v["C"])},
        {"name": "depth", "type": "fn", "nodes": ["th", "k", "h"], "sigma": 1e-9,
         "f": lambda v: math.log10(v["th"]) - math.log10(math.tanh(min(v["k"] * v["h"], 50.0)))},
        {"name": "dispersion", "terms": {"w": 2, "S": -1, "th": -1}, "rhs": 0.0, "sigma": 1e-9},
    ]
    measured = _measured(liquid, g, h)
    del measured["nu"]
    measured["w"] = (w, 1e-6)
    out = GlobalRelationalNetwork(nodes, rels).solve(measured_dict=measured, max_iterations=80)
    k = out["values"]["k"]
    return {"k": k, "wavelength": 2 * math.pi / k, "speed": w / k, "converged": out["converged"]}


# ============================================================
# THE BASIN: modes, interactions, surface
# ============================================================

class Basin:
    """Standing waves of a rectangular basin with reflecting walls. Each mode (m, n) is a complex amplitude
    Z: the surface is Re(Z) cos(kx x) cos(ky y), and Z turns at w and shrinks at gamma (from the network)."""

    def __init__(self, Lx, Ly, h, liquid="Water", g=9.81):
        self.Lx, self.Ly = Lx, Ly
        self.Mx = MODES_LONG if Lx >= Ly else max(12, round(MODES_LONG * Lx / Ly))
        self.My = max(12, round(self.Mx * Ly / Lx))
        self.Gx = GRID_LONG if Lx >= Ly else max(16, round(GRID_LONG * Lx / Ly))
        self.Gy = max(16, round(self.Gx * Ly / Lx))
        self.kx = np.arange(self.Mx) * math.pi / Lx
        self.ky = np.arange(self.My) * math.pi / Ly
        self.K = np.sqrt(self.kx[:, None] ** 2 + self.ky[None, :] ** 2)
        self.x = np.linspace(0, Lx, self.Gx)
        self.y = np.linspace(0, Ly, self.Gy)
        self.Cx = np.cos(np.outer(self.x, self.kx))                 # Gx x Mx
        self.Cy = np.cos(np.outer(self.y, self.ky))                 # Gy x My
        self.Sx = -np.sin(np.outer(self.x, self.kx)) * self.kx      # derivative along x
        self.Sy = -np.sin(np.outer(self.y, self.ky)) * self.ky
        self.Z = np.zeros((self.Mx, self.My), dtype=complex)
        self.time = 0.0
        self.set_physics(h, liquid, g)

    def set_physics(self, h, liquid, g):
        self.h, self.liquid, self.g = h, liquid, g
        k_min = math.pi / max(self.Lx, self.Ly)
        k_max = float(self.K.max()) * 1.01
        ks = np.geomspace(k_min * 0.99, k_max, SAMPLES)
        self.net = water_network(liquid, g, h, self.Lx, self.Ly, ks)
        K = np.where(self.K > 0, self.K, k_min)
        lk = np.log(K)
        self.w = np.exp(np.interp(lk, np.log(ks), np.log(self.net["w"])))
        self.gamma = np.exp(np.interp(lk, np.log(ks), np.log(self.net["gamma"])))
        # a mode damped faster than it swings no longer swings (very viscous liquids, tiny ripples): keep it
        # just below that limit (it then dies within one turn)
        self.w = np.maximum(self.w, 1.01 * self.gamma)
        self.alive = self.K > 0                                     # mode (0, 0) is the mean level: fixed

    def _shape(self, x0, y0, s):
        """Modal coefficients of a bump exp(-r^2 / 2 s^2) of unit height at (x0, y0) (walls as mirrors)."""
        nx = np.where(np.arange(self.Mx) == 0, 1.0, 2.0) / self.Lx
        ny = np.where(np.arange(self.My) == 0, 1.0, 2.0) / self.Ly
        gx = nx * math.sqrt(2 * math.pi) * s * np.exp(-0.5 * (self.kx * s) ** 2) * np.cos(self.kx * x0)
        gy = ny * math.sqrt(2 * math.pi) * s * np.exp(-0.5 * (self.ky * s) ** 2) * np.cos(self.ky * y0)
        return np.outer(gx, gy) * self.alive

    def drop(self, x0, y0, size, depth):
        """A drop hits the surface: a hollow of the given depth and size, released at rest."""
        self.Z += -depth * self._shape(x0, y0, size)

    def push(self, x0, y0, size, speed, dt):
        """Something moving in the water pushes it down at `speed` (m/s) during dt: a kick to each mode."""
        dv = -speed * dt * self._shape(x0, y0, size)
        self.Z += -1j * dv / self.w

    def paddle(self, amplitude, frequency, dt):
        """A paddle along the wall x = 0 moves up and down: it feeds the modes that are uniform across."""
        s = 0.02 * self.Lx
        nx = np.where(np.arange(self.Mx) == 0, 1.0, 2.0) / self.Lx
        gx = nx * math.sqrt(2 * math.pi) * s * np.exp(-0.5 * (self.kx * s) ** 2)
        wp = 2 * math.pi * frequency
        dv = amplitude * wp * math.cos(wp * self.time) * dt * gx
        self.Z[:, 0] += -1j * dv / self.w[:, 0] * self.alive[:, 0]

    def step(self, dt):
        self.Z *= np.exp((-self.gamma + 1j * self.w) * dt)
        self.time += dt

    def calm(self):
        self.Z[:] = 0

    def surface(self):
        """Height and slopes of the surface on the grid (Gx x Gy)."""
        A = self.Z.real
        eta = self.Cx @ A @ self.Cy.T
        ex = self.Sx @ A @ self.Cy.T
        ey = self.Cx @ A @ self.Sy.T
        return eta, ex, ey

    def energy(self):
        """Potential + kinetic energy per unit area (J/m2) of the modes, up to a constant factor."""
        rho = LIQUIDS[self.liquid][0]
        return float(0.25 * rho * self.g * np.sum(np.abs(self.Z) ** 2 * self.alive))


# ============================================================
# RENDERING: a camera above the basin, the sky reflected by the waves
# ============================================================

class Camera:
    """Fixed perspective camera. For each pixel: where its ray meets the still surface, and the direction
    towards the eye. The waves then tilt the surface there, and the sky they reflect makes the picture."""

    def __init__(self, Lx, Ly, width, height):
        self.W, self.H = width, height
        S = max(Lx, 1.6 * Ly)
        target = np.array([Lx / 2, Ly * 0.52, 0.0])
        cam = np.array([Lx / 2, -0.42 * S, 0.80 * S])
        fwd = target - cam
        fwd /= np.linalg.norm(fwd)
        right = np.cross(fwd, [0, 0, 1.0])
        right /= np.linalg.norm(right)
        up = np.cross(right, fwd)
        # focal length so that the whole basin fits, with a margin
        corners = np.array([[0, 0, 0], [Lx, 0, 0], [0, Ly, 0], [Lx, Ly, 0]], dtype=float)
        rel = corners - cam
        u = rel @ right / (rel @ fwd)
        v = rel @ up / (rel @ fwd)
        f = min(0.9 * width / (u.max() - u.min()), 0.86 * height / (v.max() - v.min()))
        cx = width / 2 - f * (u.max() + u.min()) / 2
        cy = height / 2 + f * (v.max() + v.min()) / 2
        px, py = np.meshgrid(np.arange(width) + 0.5, np.arange(height) + 0.5)
        d = fwd[None, None, :] * f + right[None, None, :] * (px - cx)[..., None] - up[None, None, :] * (py - cy)[..., None]
        d /= np.linalg.norm(d, axis=2, keepdims=True)
        with np.errstate(divide="ignore", invalid="ignore"):
            t = np.where(d[..., 2] < -1e-6, -cam[2] / d[..., 2], np.inf)
        P = cam[None, None, :] + d * np.where(np.isfinite(t), t, 0.0)[..., None]
        self.ground = np.isfinite(t)
        self.inside = self.ground & (P[..., 0] >= 0) & (P[..., 0] <= Lx) & (P[..., 1] >= 0) & (P[..., 1] <= Ly)
        self.px, self.py = P[..., 0], P[..., 1]
        self.view = -d                                   # towards the eye
        self.sky_dir = d
        self.dist = np.where(np.isfinite(t), t, 0.0)
        self.Lx, self.Ly = Lx, Ly

    def plane_point(self, sx, sy):
        """Point of the surface under the screen pixel (sx, sy), or None."""
        sx, sy = int(sx), int(sy)
        if 0 <= sx < self.W and 0 <= sy < self.H and self.inside[sy, sx]:
            return float(self.px[sy, sx]), float(self.py[sy, sx])
        return None


SUN = np.array([-0.35, -0.45, 0.82])     # behind the viewer: its glints show only on steep wave faces
SUN = SUN / np.linalg.norm(SUN)


def _sky(dz):
    """Sky colour seen in a direction of height dz (0 = horizon, 1 = zenith)."""
    t = np.clip(dz, 0.0, 1.0) ** 0.6
    horizon = np.array([0.80, 0.87, 0.95])
    zenith = np.array([0.18, 0.40, 0.75])
    return horizon * (1 - t)[..., None] + zenith * t[..., None]


def background(camera, basin):
    """What does not move: the sky above the horizon and the stone floor around the basin (uint8)."""
    img = np.zeros((camera.H, camera.W, 3))
    img[~camera.ground] = _sky(camera.sky_dir[~camera.ground][:, 2])
    stone = camera.ground & ~camera.inside
    gx, gy = camera.px[stone], camera.py[stone]
    dx = np.maximum.reduce([-gx, gx - basin.Lx, np.zeros_like(gx)])
    dy = np.maximum.reduce([-gy, gy - basin.Ly, np.zeros_like(gy)])
    rim = np.clip(np.hypot(dx, dy) / (0.03 * max(basin.Lx, basin.Ly)), 0, 1)     # a darker coping at the edge
    tile = 0.04 * ((np.floor(gx / (0.08 * basin.Lx)) + np.floor(gy / (0.08 * basin.Lx))) % 2)
    base = (0.60 + tile) * rim + 0.42 * (1 - rim)
    img[stone] = np.stack([base, base * 0.96, base * 0.9], axis=1)
    return (np.clip(img, 0, 1) ** (1 / 1.15) * 255).astype(np.uint8)


class WaterPixels:
    """The pixels that see the water, with everything about them that does not change from frame to frame."""

    def __init__(self, camera, basin):
        m = camera.inside
        self.flat = np.flatnonzero(m.ravel())
        fx = camera.px[m] / basin.Lx * (basin.Gx - 1)
        fy = camera.py[m] / basin.Ly * (basin.Gy - 1)
        i0 = np.clip(np.floor(fx).astype(int), 0, basin.Gx - 2)
        j0 = np.clip(np.floor(fy).astype(int), 0, basin.Gy - 2)
        ax, ay = (fx - i0).astype(np.float32), (fy - j0).astype(np.float32)
        G = basin.Gy
        self.idx = [i0 * G + j0, (i0 + 1) * G + j0, i0 * G + j0 + 1, (i0 + 1) * G + j0 + 1]
        self.wts = [(1 - ax) * (1 - ay), ax * (1 - ay), (1 - ax) * ay, ax * ay]
        self.V = camera.view[m].astype(np.float32)
        self.background = background(camera, basin)

    def read(self, a):
        a = a.ravel().astype(np.float32)
        return sum(a[i] * w for i, w in zip(self.idx, self.wts))


def render(pixels, basin, ex, ey, relief):
    """RGB picture (H x W x 3, uint8) of the basin: each water pixel reflects the sky the waves turn to it."""
    sx, sy = pixels.read(ex) * relief, pixels.read(ey) * relief
    inv = 1.0 / np.sqrt(sx * sx + sy * sy + 1.0)
    nx, ny, nz = -sx * inv, -sy * inv, inv
    V = pixels.V
    cos_v = np.clip(nx * V[:, 0] + ny * V[:, 1] + nz * V[:, 2], 0.0, 1.0)
    fresnel = 0.02 + 0.98 * (1 - cos_v) ** 5                          # Schlick, water n = 1.33
    rz = 2 * cos_v * nz - V[:, 2]                                       # the reflected ray
    rx = 2 * cos_v * nx - V[:, 0]
    ry = 2 * cos_v * ny - V[:, 1]
    # a sky with clouds: what the ray meets on a cloud layer above (a texture, not physics: it lets the eye
    # read the slopes of the surface, as on a real lake)
    lift = 1.0 / (np.abs(rz) + 0.25)
    u, v = rx * lift * 9.0, ry * lift * 9.0
    cloud = (np.sin(3.1 * u + 1.3) + np.sin(2.3 * v + 0.4) + np.sin(1.7 * (u + v) + 2.1)
             + 0.6 * np.sin(5.3 * u - 3.7 * v)) / 3.6
    cloud = np.clip(cloud + 0.15, 0.0, 1.0) ** 1.6
    rs = 2 * cos_v * (nx * SUN[0] + ny * SUN[1] + nz * SUN[2]) - V @ SUN.astype(np.float32)
    t = np.clip(rz, 0.0, 1.0) ** 0.6
    spec = np.clip(rs, 0, 1) ** 300 * 4.0
    # light goes down to a pale bottom and back up: pure water absorbs red much more than blue
    # (about 0.35, 0.06 and 0.015 per metre at 650, 550 and 450 nm, Pope & Fry 1997)
    absorb = np.array([0.35, 0.06, 0.015]) * (LIQUIDS[basin.liquid][0] < 5000)
    bottom = np.array([0.80, 0.82, 0.80]) * np.exp(-2 * basin.h * absorb) * np.array([0.82, 0.92, 1.0])
    shade = np.clip(0.85 + 0.6 * (nx * SUN[0] + ny * SUN[1] + nz * SUN[2] - SUN[2]), 0.4, 1.3)
    mirror = LIQUIDS[basin.liquid][0] > 5000                          # mercury: a mirror, not a window
    if mirror:
        fresnel = 0.75 + 0.25 * fresnel
    out = pixels.background.reshape(-1, 3).copy()
    horizon, zenith = (0.80, 0.87, 0.95), (0.18, 0.40, 0.75)
    for c in range(3):
        sky = (horizon[c] * (1 - t) + zenith[c] * t) * (1 - 0.7 * cloud) + 0.97 * 0.7 * cloud
        body = np.full_like(shade, 0.25) if mirror else bottom[c] * shade
        col = fresnel * sky + (1 - fresnel) * body + spec
        out[pixels.flat, c] = (np.clip(col, 0, 1) ** (1 / 1.15) * 255).astype(np.uint8)
    return out.reshape(pixels.background.shape)


# ============================================================
# WINDOW
# ============================================================
BG = "#0d1117"
TEXT = "#8b949e"
WAVE = "#58a6ff"


class WaterApp:
    VIEW_W, VIEW_H = 820, 470

    def __init__(self, root):
        self.root = root
        root.title("GRM Water — waves from a network of relations")
        root.geometry("1290x900")
        self.basin_name = tk.StringVar(value="Bathtub")
        self.liquid = tk.StringVar(value="Water")
        self.planet = tk.StringVar(value="Earth")
        self.depth_cm = tk.DoubleVar(value=30.0)
        self.drop_cm = tk.DoubleVar(value=2.5)
        self.strength_mm = tk.DoubleVar(value=6.0)
        self.relief = tk.DoubleVar(value=6.0)
        self.speed = tk.DoubleVar(value=1.0)
        self.rain = tk.DoubleVar(value=0.0)
        self.paddle_on = tk.BooleanVar(value=False)
        self.paddle_hz = tk.DoubleVar(value=2.0)
        self.status = tk.StringVar(value="")
        self.finger = None
        self.last = time.perf_counter()
        self.rng = np.random.default_rng()
        self.physics_job = None
        self._build()
        self.new_basin()
        self.root.after(30, self.tick)

    def _build(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        header = ttk.Frame(self.root, padding=(12, 8, 12, 0))
        header.pack(fill="x")
        ttk.Label(header, text="GRM WATER", font=("Segoe UI", 18, "bold")).pack(side="left")
        ttk.Label(header, text="   Click: a drop falls. Drag: a finger goes through the water. "
                               "Every wave swings and dies as a GRM network says.", font=("Segoe UI", 9)).pack(side="left", pady=(6, 0))
        main = ttk.Frame(self.root, padding=10)
        main.pack(fill="both", expand=True)
        left = ttk.Frame(main)
        left.pack(side="left", fill="both")
        self.view = tk.Canvas(left, width=self.VIEW_W, height=self.VIEW_H, bg=BG, highlightthickness=0, cursor="crosshair")
        self.view.pack()
        self.photo = tk.PhotoImage(width=self.VIEW_W, height=self.VIEW_H)
        self.view.create_image(0, 0, image=self.photo, anchor="nw")
        self.view.bind("<ButtonPress-1>", self.press)
        self.view.bind("<B1-Motion>", self.drag)
        self.view.bind("<ButtonRelease-1>", self.release)
        prof = ttk.LabelFrame(left, text="Profile along the middle of the basin (true height, exaggerated ×20)", padding=4)
        prof.pack(fill="x", pady=(6, 0))
        self.profile = tk.Canvas(prof, width=self.VIEW_W - 12, height=100, bg=BG, highlightthickness=0)
        self.profile.pack(fill="x")

        right = ttk.Frame(main)
        right.pack(side="left", fill="both", expand=True, padx=(10, 0))
        box = ttk.LabelFrame(right, text="Basin and liquid", padding=6)
        box.pack(fill="x")
        for row, (label, var, values) in enumerate((("Basin", self.basin_name, list(BASINS)),
                                                    ("Liquid", self.liquid, list(LIQUIDS)),
                                                    ("Gravity", self.planet, list(PLANETS)))):
            ttk.Label(box, text=label).grid(row=row, column=0, sticky="w", pady=2)
            cb = ttk.Combobox(box, textvariable=var, values=values, state="readonly", width=14)
            cb.grid(row=row, column=1, sticky="w", padx=6)
            cb.bind("<<ComboboxSelected>>", lambda _e, v=var: self.new_basin() if v is self.basin_name else self.physics_later())
        self.depth_scale = tk.Scale(box, label="Depth (cm)", variable=self.depth_cm, from_=0.5, to=60, resolution=0.5,
                                    orient="horizontal", length=330, command=lambda _v: self.physics_later())
        self.depth_scale.grid(row=3, column=0, columnspan=2, sticky="ew")

        hand = ttk.LabelFrame(right, text="Hands and weather", padding=6)
        hand.pack(fill="x", pady=(8, 0))
        for label, var, lo, hi, res in (("Drop / finger size (cm)", self.drop_cm, 0.3, 50, 0.1),
                                        ("Strength (mm)", self.strength_mm, 0.5, 60, 0.5),
                                        ("Rain (drops per second)", self.rain, 0, 40, 1),
                                        ("Paddle frequency (Hz)", self.paddle_hz, 0.1, 12, 0.1)):
            tk.Scale(hand, label=label, variable=var, from_=lo, to=hi, resolution=res, orient="horizontal",
                     length=330, command=(lambda _v: self.update_paddle()) if var is self.paddle_hz else None).pack(fill="x")
        row = ttk.Frame(hand)
        row.pack(fill="x", pady=(4, 0))
        ttk.Checkbutton(row, text="Paddle on the left wall", variable=self.paddle_on,
                        command=self.update_paddle).pack(side="left")
        ttk.Button(row, text="Calm the water", command=lambda: self.basin.calm()).pack(side="right")
        self.paddle_label = ttk.Label(hand, text="", font=("Segoe UI", 8), wraplength=400)
        self.paddle_label.pack(anchor="w")

        look = ttk.LabelFrame(right, text="Looking", padding=6)
        look.pack(fill="x", pady=(8, 0))
        for label, var, lo, hi, res in (("Time (×)", self.speed, 0.05, 3.0, 0.05),
                                        ("Relief of the light (×)", self.relief, 1, 20, 0.5)):
            tk.Scale(look, label=label, variable=var, from_=lo, to=hi, resolution=res, orient="horizontal",
                     length=330).pack(fill="x")

        diag = ttk.LabelFrame(left, text="What the network says", padding=4)
        diag.pack(fill="x", pady=(6, 0))
        self.curve = tk.Canvas(diag, width=330, height=130, bg=BG, highlightthickness=0)
        self.curve.pack(side="left")
        self.diag = tk.Text(diag, height=9, width=60, wrap="word", font=("Consolas", 8))
        self.diag.pack(side="left", fill="both", expand=True, padx=(6, 0))
        ttk.Label(self.root, textvariable=self.status, font=("Segoe UI", 9), padding=(12, 0, 12, 6)).pack(anchor="w")

    # ---------------------------------------------------------------- physics
    def new_basin(self):
        Lx, Ly, h = BASINS[self.basin_name.get()]
        top = max(4 * h, 0.05) * 100
        res = 0.1 if top < 20 else (0.5 if top < 300 else 10)
        self.depth_scale.configure(from_=max(res, round(h * 10 / res) * res), to=round(top / res) * res, resolution=res)
        self.depth_cm.set(h * 100)
        size = {"Puddle": 0.6, "Bathtub": 2.5, "Pool": 20.0, "Harbour": 400.0}[self.basin_name.get()]
        strength = {"Puddle": 1.0, "Bathtub": 6.0, "Pool": 40.0, "Harbour": 600.0}[self.basin_name.get()]
        self.drop_cm.set(min(size, 50))
        self.strength_mm.set(min(strength, 60))
        self.size_scale = size / min(size, 50)         # big basins: the slider is multiplied
        t0 = time.perf_counter()
        self.basin = Basin(Lx, Ly, h, self.liquid.get(), PLANETS[self.planet.get()])
        self.camera = Camera(Lx, Ly, self.VIEW_W, self.VIEW_H)
        self.pixels = WaterPixels(self.camera, self.basin)
        self.status.set(f"New basin {Lx:g} × {Ly:g} m: {self.basin.Mx * self.basin.My} modes, "
                        f"network of {SAMPLES} wavenumbers solved in {time.perf_counter() - t0:.2f} s.")
        self.show_network()
        self.update_paddle()

    def physics_later(self):
        if self.physics_job is not None:
            self.root.after_cancel(self.physics_job)
        self.physics_job = self.root.after(200, self.apply_physics)

    def apply_physics(self):
        self.physics_job = None
        t0 = time.perf_counter()
        self.basin.set_physics(float(self.depth_cm.get()) / 100, self.liquid.get(), PLANETS[self.planet.get()])
        self.status.set(f"{self.liquid.get()}, {self.planet.get()}, depth {self.depth_cm.get():g} cm: "
                        f"network solved in {time.perf_counter() - t0:.2f} s; the waves already there go on with it.")
        self.show_network()
        self.update_paddle()

    def update_paddle(self):
        if not self.paddle_on.get():
            self.paddle_label.config(text="")
            return
        b = self.basin
        r = wavelength_network(b.liquid, b.g, b.h, float(self.paddle_hz.get()))
        self.paddle_label.config(text=f"Inverse network: at {self.paddle_hz.get():.1f} Hz the paddle makes waves "
                                      f"{r['wavelength'] * 100:.1f} cm long, running at {r['speed'] * 100:.1f} cm/s.")

    def show_network(self):
        b, net = self.basin, self.basin.net
        k, w = net["k"], net["w"]
        c = w / k
        lam = 2 * np.pi / k
        lines = [f"{b.liquid} on {self.planet.get()}, depth {b.h * 100:g} cm (converged: {net['converged']})",
                 f"long waves run at most at sqrt(g h) = {net['c0']:.3f} m/s",
                 f"capillary length sqrt(sigma / (rho g)) = {net['lc'] * 1000:.2f} mm: shorter ripples are held by surface tension",
                 f"no ripple runs slower than (4 g sigma / rho)^(1/4) = {net['cmin'] * 100:.1f} cm/s",
                 f"longest mode: {lam[0]:.3g} m, period {2 * np.pi / w[0]:.3g} s, lives {1 / net['gamma'][0]:.3g} s",
                 f"shortest mode: {lam[-1] * 100:.3g} cm, period {2 * np.pi / w[-1] * 1000:.3g} ms, lives {1 / net['gamma'][-1]:.3g} s",
                 f"uncertainty on the frequencies (from the handbook values): ±{100 * net['w_rel'].max():.2f} %"]
        self.diag.delete("1.0", "end")
        self.diag.insert("1.0", "\n".join(lines))
        # phase speed against wavelength, log-log
        cv = self.curve
        cv.delete("all")
        cw, ch = 330, 130
        lx, ly = np.log10(lam), np.log10(c)
        x0, x1 = lx.min(), lx.max()
        y0, y1 = min(ly.min(), math.log10(net["cmin"])) - 0.05, ly.max() + 0.05
        X = lambda v: 34 + (v - x0) / (x1 - x0 + 1e-9) * (cw - 44)
        Y = lambda v: ch - 16 - (v - y0) / (y1 - y0 + 1e-9) * (ch - 26)
        pts = []
        for a, bb in zip(lx, ly):
            pts += [X(a), Y(bb)]
        cv.create_line(*pts, fill=WAVE, width=2, smooth=True)
        cv.create_line(34, Y(math.log10(net["c0"])), cw - 10, Y(math.log10(net["c0"])), fill="#3fb950", dash=(3, 3))
        cv.create_text(cw - 12, Y(math.log10(net["c0"])) + 9, anchor="e", text="sqrt(g h)", fill="#3fb950", font=("Segoe UI", 7))
        cv.create_text(6, 4, anchor="nw", text="wave speed vs wavelength\n(log-log), from the network",
                       fill=TEXT, font=("Segoe UI", 8))
        cv.create_text(34, ch - 4, anchor="sw", text=f"{lam.min() * 100:.2g} cm", fill=TEXT, font=("Segoe UI", 7))
        cv.create_text(cw - 10, ch - 4, anchor="se", text=f"{lam.max():.3g} m", fill=TEXT, font=("Segoe UI", 7))

    # ---------------------------------------------------------------- hands
    def _point(self, event):
        return self.camera.plane_point(event.x, event.y)

    def press(self, event):
        p = self._point(event)
        if p is not None:
            size = float(self.drop_cm.get()) / 100 * self.size_scale
            self.basin.drop(p[0], p[1], size, float(self.strength_mm.get()) / 1000)
        self.finger = (p, time.perf_counter())

    def drag(self, event):
        p = self._point(event)
        now = time.perf_counter()
        if p is not None and self.finger is not None and self.finger[0] is not None:
            (x0, y0), t0 = self.finger
            dt = max(now - t0, 1e-3)
            dist = math.hypot(p[0] - x0, p[1] - y0)
            size = float(self.drop_cm.get()) / 100 * self.size_scale
            # the finger pushes the water aside along its path; the faster it goes, the more it pushes
            steps = max(1, int(dist / (0.5 * size)))
            push = float(self.strength_mm.get()) / 1000 / max(size, 1e-3) * 4.0
            for s in range(1, steps + 1):
                u = s / steps
                self.basin.push(x0 + (p[0] - x0) * u, y0 + (p[1] - y0) * u, size,
                                push * min(dist / dt, 2.0) / 2.0, dt / steps * float(self.speed.get()) * 4)
        self.finger = (p, now)

    def release(self, _event):
        self.finger = None

    # ---------------------------------------------------------------- time
    def tick(self):
        now = time.perf_counter()
        real = min(now - self.last, 0.06)
        self.last = now
        dt = real * float(self.speed.get())
        b = self.basin
        rate = float(self.rain.get())
        if rate > 0:
            for _ in range(self.rng.poisson(rate * real)):
                size = float(self.drop_cm.get()) / 100 * self.size_scale * 0.4
                b.drop(self.rng.uniform(0, b.Lx), self.rng.uniform(0, b.Ly), size,
                       float(self.strength_mm.get()) / 1000 * 0.4)
        if self.paddle_on.get():
            b.paddle(float(self.strength_mm.get()) / 1000 * 0.5, float(self.paddle_hz.get()), dt)
        b.step(dt)
        eta, ex, ey = b.surface()
        img = render(self.pixels, b, ex, ey, float(self.relief.get()))
        header = f"P6 {self.VIEW_W} {self.VIEW_H} 255\n".encode()
        self.photo.configure(data=header + img.tobytes(), format="PPM")
        self.draw_profile(eta)
        self.root.after(max(1, 30 - int((time.perf_counter() - now) * 1000)), self.tick)

    def draw_profile(self, eta):
        c = self.profile
        c.delete("all")
        w, h = max(c.winfo_width(), 400), 100
        mid = h * 0.45
        row = eta[:, eta.shape[1] // 2]
        scale = 20.0 * (w - 20) / self.basin.Lx            # same scale as the length, ×20
        depth_px = min(h - mid - 6, self.basin.h * scale / 20 * 3)
        c.create_rectangle(10, mid, w - 10, mid + depth_px, fill="#0b2a3a", outline="")
        c.create_line(10, mid + depth_px, w - 10, mid + depth_px, fill="#c2a878", width=2)
        pts = []
        for i, v in enumerate(row):
            pts += [10 + i / (len(row) - 1) * (w - 20), mid - float(np.clip(v * scale, -mid + 4, h - mid))]
        c.create_line(*pts, fill=WAVE, width=2)
        c.create_text(12, 6, anchor="nw", fill=TEXT, font=("Segoe UI", 8),
                      text=f"highest point {row.max() * 1000:+.1f} mm, lowest {row.min() * 1000:+.1f} mm "
                           f"(bottom drawn ×3 closer)")


# ============================================================
# WITHOUT A WINDOW
# ============================================================

def run_headless(seconds=2.0):
    b = Basin(*BASINS["Bathtub"])
    b.drop(0.5, 0.35, 0.025, 0.006)
    e0 = b.energy()
    for _ in range(int(seconds / 0.02)):
        b.step(0.02)
    eta, _, _ = b.surface()
    net = b.net
    print(f"Bathtub, water, 30 cm: sqrt(gh) = {net['c0']:.3f} m/s, slowest ripple {net['cmin'] * 100:.1f} cm/s, "
          f"capillary length {net['lc'] * 1000:.2f} mm")
    print(f"after {seconds:g} s: energy kept {b.energy() / e0:.3f}, surface between {eta.min() * 1000:.2f} "
          f"and {eta.max() * 1000:.2f} mm")
    r = wavelength_network("Water", 9.81, 0.30, 2.0)
    print(f"paddle at 2 Hz -> waves of {r['wavelength'] * 100:.1f} cm at {r['speed'] * 100:.1f} cm/s")


def main():
    parser = argparse.ArgumentParser(description="GRM Water")
    parser.add_argument("--headless", action="store_true", help="run a drop without a window and print the numbers")
    args = parser.parse_args()
    if args.headless or tk is None:
        run_headless()
        return
    root = tk.Tk()
    WaterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
