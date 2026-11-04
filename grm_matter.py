# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Anthony Charretier
"""
GRM Matter - from the constants of the quantum world to the density and stiffness of metals.

What goes in: the fundamental constants (electron mass, charge, Planck constant, vacuum permittivity, atomic
mass unit), and for each element only its number of protons Z and the mass of its atom. No material data.
What comes out: ionization energies, then the density and the bulk modulus of simple metals, each with an
uncertainty, compared with the measured values afterwards.

Three steps, each a network:
1. Constants network. Bohr radius a0 = 4 pi eps0 hbar^2 / (m_e e^2), Hartree energy Ha = m_e e^4 / (4 pi eps0)^2 hbar^2.
2. The atom. Electrons fill the orbitals in the order of the Madelung rule (n + l, then n), and the atom is solved
   self-consistently: Schrodinger's equation for each orbital in the field of the nucleus and of all electrons
   (Hartree potential, plus exchange and correlation of the electron gas in the local density approximation,
   Perdew-Zunger 1981 parametrisation of Ceperley-Alder). Energies of the atom and of its ions give the
   ionization energies (difference of total energies).
3. The metal. The valence electrons leave their atoms and fill the crystal as a uniform gas; each ion is seen
   by them as a charge Z_v with an empty core of radius r_c (Ashcroft 1966: inside r_c the valence electrons feel
   no attraction, the core electrons keep them out). The core radius comes from the atom itself: the GRM finds
   the r_c for which the valence electron of the ion has the energy the atom calculation gave (inverse network).
   Energy per valence electron (Rydberg, r_s = radius of the sphere holding one valence electron, in a0):
       kinetic       2.21 / r_s^2                      (Fermi gas)
       exchange     -0.916 / r_s
       correlation  -0.88 / (r_s + 7.8)                (Wigner)
       ion field    -1.8 Z_v^(2/3) / r_s               (Wigner-Seitz sphere)
       empty core   +3 r_c^2 / r_s^3
   The metal sits where this energy is lowest (dE/dr_s = 0): that gives r_s, hence the density; its curvature
   there gives the bulk modulus, B = E''(r_s) / (12 pi r_s) [Ry / a0^3].
Missing on purpose in this first version: the band-structure energy (how the crystal lattice bends the electron
gas), the crystal structure itself, d electrons. The comparison shows what that costs.
"""
import argparse
import math
import time

import numpy as np

from grm import GlobalRelationalNetwork

LN10 = math.log(10.0)

# CODATA 2018 (e and hbar exact since the 2019 SI): value, relative standard uncertainty
CONSTANTS = {
    "me": (9.1093837015e-31, 3.0e-10),     # kg
    "e": (1.602176634e-19, 0.0),            # C
    "hbar": (6.62607015e-34 / (2 * math.pi), 0.0),   # J s (h exact)
    "eps0": (8.8541878128e-12, 1.5e-10),    # F/m
    "mu": (1.66053906660e-27, 3.0e-10),     # kg, atomic mass unit
}

# The elements tried: Z, valence electrons, standard atomic weight
METALS = {
    "Li": (3, 1, 6.94), "Na": (11, 1, 22.990), "K": (19, 1, 39.098), "Rb": (37, 1, 85.468), "Cs": (55, 1, 132.91),
    "Be": (4, 2, 9.0122), "Mg": (12, 2, 24.305), "Ca": (20, 2, 40.078), "Sr": (38, 2, 87.62), "Ba": (56, 2, 137.33),
    "Al": (13, 3, 26.982),
}
# Measured values, used only to compare afterwards (Wikipedia data pages: densities "use" column; bulk moduli
# WebElements; first ionization energies CRC)
MEASURED_DENSITY = {"Li": 0.534, "Na": 0.968, "K": 0.89, "Rb": 1.532, "Cs": 1.93, "Be": 1.85, "Mg": 1.738,
                    "Ca": 1.55, "Sr": 2.64, "Ba": 3.51, "Al": 2.70}                       # g/cm3
MEASURED_BULK = {"Li": 11, "Na": 6.3, "K": 3.1, "Rb": 2.5, "Cs": 1.6, "Be": 130, "Mg": 45, "Ca": 17,
                 "Ba": 9.6, "Al": 76}                                                       # GPa
MEASURED_IE = {"H": 13.59844, "He": 24.58738, "Li": 5.39171, "Be": 9.32269, "B": 8.29803, "C": 11.26030,
               "N": 14.53414, "O": 13.61806, "F": 17.42282, "Ne": 21.5646, "Na": 5.13908, "Mg": 7.64624,
               "Al": 5.98577, "Si": 8.15169, "P": 10.48669, "S": 10.36001, "Cl": 12.96764, "Ar": 15.75962,
               "K": 4.34066, "Ca": 6.11316, "Rb": 4.17713, "Sr": 5.6949, "Cs": 3.89390, "Ba": 5.21170}   # eV
SYMBOLS = ["H", "He", "Li", "Be", "B", "C", "N", "O", "F", "Ne", "Na", "Mg", "Al", "Si", "P", "S", "Cl", "Ar",
           "K", "Ca"] + [""] * 16 + ["Rb", "Sr"] + [""] * 16 + ["Cs", "Ba"]
LDA_SPREAD = 0.04      # typical relative error of LDA ionization energies (checked on the table above: 3.4 % median)


# ============================================================
# 1. CONSTANTS NETWORK
# ============================================================

def constants_network():
    nodes = {k: {"guess": v} for k, (v, _) in CONSTANTS.items()}
    nodes.update({"a0": {"guess": 5e-11}, "Ha": {"guess": 4e-18}})
    rels = [
        {"name": "Bohr radius", "terms": {"a0": 1, "eps0": -1, "hbar": -2, "me": 1, "e": 2},
         "rhs": math.log10(4 * math.pi), "sigma": 1e-12},
        {"name": "Hartree energy", "terms": {"Ha": 1, "me": -1, "e": -4, "eps0": 2, "hbar": 2},
         "rhs": -2 * math.log10(4 * math.pi), "sigma": 1e-12},
    ]
    measured = {k: (v, max(s, 1e-13) / LN10) for k, (v, s) in CONSTANTS.items()}
    return GlobalRelationalNetwork(nodes, rels).solve(measured_dict=measured)


# ============================================================
# 2. THE ATOM (self-consistent, local density approximation), in Hartree atomic units
# ============================================================
ORDER = ["1s", "2s", "2p", "3s", "3p", "4s", "3d", "4p", "5s", "4d", "5p", "6s", "4f", "5d", "6p", "7s"]  # Madelung
CAPACITY = {"s": 2, "p": 6, "d": 10, "f": 14}
ELL = {"s": 0, "p": 1, "d": 2, "f": 3}


def configuration(Z, charge=0):
    """Orbitals (n, l, electrons) of the neutral atom filled by the Madelung rule, then `charge` electrons taken
    from the outermost ones."""
    occ, left = [], Z
    for o in ORDER:
        k = min(left, CAPACITY[o[1]])
        if k:
            occ.append([int(o[0]), ELL[o[1]], float(k)])
            left -= k
        if left <= 0:
            break
    for _ in range(charge):
        i = max(range(len(occ)), key=lambda j: (occ[j][2] > 0, occ[j][0], occ[j][1]))
        occ[i][2] -= 1
    return [o for o in occ if o[2] > 0]


def exchange_correlation(n):
    """Energy density per electron and potential of the uniform electron gas (Slater exchange; Perdew-Zunger)."""
    n = np.maximum(n, 1e-30)
    rs = (3 / (4 * math.pi * n)) ** (1 / 3)
    ex = -0.75 * (3 * n / math.pi) ** (1 / 3)
    vx = 4 / 3 * ex
    g, b1, b2 = -0.1423, 1.0529, 0.3334
    A, B, C, D = 0.0311, -0.048, 0.0020, -0.0116
    sq = np.sqrt(rs)
    high = rs >= 1
    ec = np.where(high, g / (1 + b1 * sq + b2 * rs), A * np.log(rs) + B + C * rs * np.log(rs) + D * rs)
    vc = np.where(high, ec * (1 + 7 / 6 * b1 * sq + 4 / 3 * b2 * rs) / (1 + b1 * sq + b2 * rs),
                  A * np.log(rs) + (B - A / 3) + 2 / 3 * C * rs * np.log(rs) + (2 * D - C) / 3 * rs)
    return ex + ec, vx + vc


class Grid:
    """Logarithmic radial grid x = ln r."""

    def __init__(self, Z, points=3000, r_max=60.0):
        self.x = np.linspace(math.log(1e-5 / Z), math.log(r_max), points)
        self.h = self.x[1] - self.x[0]
        self.r = np.exp(self.x)


try:   # the step-by-step integration is a loop: compiled when numba is there (about 50 times faster)
    from numba import njit
except ImportError:  # pragma: no cover
    def njit(*args, **_kw):
        return args[0] if args and callable(args[0]) else (lambda f: f)


@njit(cache=True)
def _numerov(h, f):
    h2 = h * h / 12.0
    n = f.shape[0]
    y = np.zeros(n)
    y[0] = 1e-10
    y[1] = 1e-10 * math.exp(h * math.sqrt(max(f[0], 1e-12)))
    for i in range(1, n - 1):
        y[i + 1] = (2 * y[i] * (1 + 5 * h2 * f[i]) - y[i - 1] * (1 - h2 * f[i - 1])) / (1 - h2 * f[i + 1])
        if abs(y[i + 1]) > 1e150:
            for j in range(i + 2):
                y[j] /= 1e150
    return y


def bound_state(grid, V, n, l, depth):
    """Energy and radial function u(r) of the state (n, l): the energy whose solution has n - l - 1 nodes
    (bisection). With u = sqrt(r) y(x): y'' = [2 r^2 (V - E) + (l + 1/2)^2] y (Numerov)."""
    r = grid.r
    wanted = n - l - 1
    lo, hi = max(float(np.min(V + l * (l + 1) / (2 * r * r))) - 1.0, -depth), 0.0
    for _ in range(80):
        E = 0.5 * (lo + hi)
        f = 2 * r * r * (V - E) + (l + 0.5) ** 2
        turn = np.where(f < 0)[0]
        stop = min(len(f) - 1, (turn[-1] + int(1.5 / grid.h)) if len(turn) else len(f) - 1)
        y = _numerov(grid.h, np.ascontiguousarray(f[:stop + 1]))
        if int(np.sum(y[:-1] * y[1:] < 0)) > wanted:
            hi = E
        else:
            lo = E
        if hi - lo < 1e-10:
            break
    E = 0.5 * (lo + hi)
    f = 2 * r * r * (V - E) + (l + 0.5) ** 2
    turn = np.where(f < 0)[0]
    stop = min(len(f) - 1, (turn[-1] + int(1.5 / grid.h)) if len(turn) else len(f) - 1)
    y = _numerov(grid.h, np.ascontiguousarray(f[:stop + 1]))
    k = len(y) - 1
    while k > 2 and abs(y[k]) > abs(y[k - 1]):           # drop the diverging tail
        k -= 1
    y = np.concatenate([y[:k + 1], np.zeros(len(r) - k - 1)])
    u = np.sqrt(r) * y
    return E, u / math.sqrt(np.sum(u * u * r) * grid.h)


def solve_atom(Z, charge=0, iterations=150, mix=0.3, tolerance=1e-7):
    """Self-consistent LDA atom or ion. Returns total energy (Ha) and orbital energies."""
    occ = configuration(Z, charge)
    g = Grid(Z)
    V = -Z / g.r * np.exp(-g.r * Z ** (1 / 3) / 1.5) - 1 / (g.r + 1)      # a screened start
    E_old, E_tot = 0.0, 0.0
    for it in range(iterations):
        n = np.zeros_like(g.r)
        eig = []
        for (nn, l, k) in occ:
            e, u = bound_state(g, V, nn, l, float(Z * Z))
            eig.append(e)
            n += k * u * u / (4 * math.pi * g.r ** 2)
        # charge inside r and the potential of the charge outside (trapezoids, second order)
        a_in = 4 * math.pi * n * g.r ** 3
        a_out = 4 * math.pi * n * g.r ** 2
        inside = np.concatenate([[0.0], np.cumsum(0.5 * (a_in[1:] + a_in[:-1]))]) * g.h
        outside = np.concatenate([np.cumsum(0.5 * (a_out[1:] + a_out[:-1])[::-1])[::-1], [0.0]]) * g.h
        VH = inside / g.r + outside
        exc, vxc = exchange_correlation(n)
        V_new = -Z / g.r + VH + vxc
        E_tot = (sum(k * e for (_, _, k), e in zip(occ, eig))
                 + np.sum(n * (-0.5 * VH + exc - vxc) * 4 * math.pi * g.r ** 3) * g.h)
        if abs(E_tot - E_old) < tolerance and it > 5:
            break
        E_old = E_tot
        V = mix * V_new + (1 - mix) * V
    return {"E": float(E_tot), "orbitals": [(o[0], o[1], o[2], e) for o, e in zip(occ, eig)], "iterations": it}


_ATOMS = {}


def atom_energy(Z, charge=0):
    if (Z, charge) not in _ATOMS:
        _ATOMS[(Z, charge)] = solve_atom(Z, charge)["E"]
    return _ATOMS[(Z, charge)]


def ionization_energy(Z, k=1):
    """k-th ionization energy (Ha): E(ion k+) - E(ion (k-1)+)."""
    return atom_energy(Z, k) - atom_energy(Z, k - 1)


# ============================================================
# 3. THE METAL
# ============================================================

def empty_core_level(Zv, rc):
    """Lowest s level (Ha) of one electron around a charge Zv whose field is cut inside rc."""
    g = Grid(max(Zv, 1.0), points=4000, r_max=80.0)
    # the edge of the core is smoothed over 0.02 a0, so that the level moves smoothly with rc
    V = -Zv / g.r * 0.5 * (1 + np.tanh((g.r - rc) / 0.02))
    return bound_state(g, V, 1, 0, float((Zv + 1) ** 2))[0]


def core_network(Zv, I_last):
    """Inverse network: the core radius r_c for which the valence electron of the ion is bound by I_last (Ha).
    I_last carries the LDA uncertainty; the network passes it on to r_c."""
    nodes = {"rc": {"guess": 1.5}, "I": {"guess": I_last}}
    rels = [{"name": "valence level", "type": "fn", "nodes": ["rc", "I"], "sigma": 1e-6,
             "f": lambda v: math.log10(-empty_core_level(Zv, v["rc"])) - math.log10(v["I"])}]
    return GlobalRelationalNetwork(nodes, rels).solve(measured_dict={"I": (I_last, LDA_SPREAD / LN10)},
                                                      max_iterations=40)


def electron_energy(rs, Zv, rc):
    """Energy per valence electron (Ry) of the electron gas among empty-core ions, and its two derivatives."""
    E = 2.21 / rs ** 2 - 0.916 / rs - 0.88 / (rs + 7.8) - 1.8 * Zv ** (2 / 3) / rs + 3 * rc ** 2 / rs ** 3
    d1 = -4.42 / rs ** 3 + 0.916 / rs ** 2 + 0.88 / (rs + 7.8) ** 2 + 1.8 * Zv ** (2 / 3) / rs ** 2 - 9 * rc ** 2 / rs ** 4
    d2 = 13.26 / rs ** 4 - 1.832 / rs ** 3 - 1.76 / (rs + 7.8) ** 3 - 3.6 * Zv ** (2 / 3) / rs ** 3 + 36 * rc ** 2 / rs ** 5
    return E, d1, d2


# ---- second order: the crystal lattice bends the electron gas (band-structure energy)
def _reciprocal(structure, n=7):
    """|G| of the reciprocal lattice (units of 2 pi / a, cubic cell), without G = 0."""
    i = np.arange(-n, n + 1)
    h, k, l = np.meshgrid(i, i, i, indexing="ij")
    H = np.stack([h.ravel(), k.ravel(), l.ravel()], 1)
    keep = (H.sum(1) % 2 == 0) if structure == "bcc" else ((H % 2 == 0).all(1) | (H % 2 == 1).all(1))
    H = H[keep]
    return np.linalg.norm(H[(H != 0).any(1)], axis=1)


RECIPROCAL = {"bcc": _reciprocal("bcc"), "fcc": _reciprocal("fcc")}
ATOMS_PER_CELL = {"bcc": 2, "fcc": 4}


def band_energy(rs, Zv, rc, structure):
    """Second-order energy per valence electron (Ha) of the empty-core ions on a lattice, screened by the
    electron gas: sum over the reciprocal lattice of -(Omega q^2 / 8 pi) |w(q)|^2 (1 - 1/eps(q)), with the
    bare form factor w(q) = -4 pi Zv cos(q rc) / (Omega q^2), Lindhard screening and the Hubbard local-field
    correction G(q) = q^2 / 2 (q^2 + kF^2) (Harrison, Pseudopotentials in the theory of metals, 1966)."""
    omega = Zv * 4 / 3 * math.pi * rs ** 3
    kF = (9 * math.pi / 4) ** (1 / 3) / rs
    a = (ATOMS_PER_CELL[structure] * omega) ** (1 / 3)
    q = RECIPROCAL[structure] * 2 * math.pi / a
    x = q / (2 * kF)
    with np.errstate(divide="ignore", invalid="ignore"):
        lind = np.where(np.abs(x - 1) < 1e-9, 0.5, 0.5 + (1 - x * x) / (4 * x) * np.log(np.abs((1 + x) / (1 - x))))
    chi0 = kF / math.pi ** 2 * lind
    local = q * q / (2 * (q * q + kF * kF))
    eps = 1 + (1 - local) * 4 * math.pi / (q * q) * chi0
    w = -4 * math.pi * Zv / (omega * q * q) * np.cos(q * rc)
    return float(np.sum(-(omega * q * q / (8 * math.pi)) * w * w * (1 - 1 / eps)) / Zv)


def total_energy(rs, Zv, rc, structure=None):
    """Energy per valence electron in Ry: the electron gas among empty cores, plus (if a structure is given)
    the band-structure energy of that lattice."""
    E = electron_energy(rs, Zv, rc)[0]
    if structure is not None:
        E += 2 * band_energy(rs, Zv, rc, structure)
    return E


def _derivatives(rs, Zv, rc, structure):
    if structure is None:
        _, d1, d2 = electron_energy(rs, Zv, rc)
        return d1, d2
    h = 1e-3 * rs
    e0, ep, em = (total_energy(rs + d, Zv, rc, structure) for d in (0.0, h, -h))
    return (ep - em) / (2 * h), (ep - 2 * e0 + em) / (h * h)


def metal_network(symbol, constants, rc, rc_sigma_dex, structure=None):
    """The metal: r_s where the energy is lowest, the density and the bulk modulus that follow.
    structure None: first order (gas + ions); "bcc" or "fcc": with the band-structure energy of that lattice."""
    Z, Zv, A = METALS[symbol]
    c = constants["values"]
    nodes = {"rs": {"guess": 4.0}, "rc": {"guess": rc}, "rho": {"guess": 1000.0}, "B": {"guess": 1e10},
             "a0": {"guess": c["a0"]}, "Ha": {"guess": c["Ha"]}, "mu": {"guess": c["mu"]}, "M": {"guess": A},
             "curv": {"guess": 0.05}}
    rels = [
        # equilibrium: no pressure, dE/drs = 0 (scaled to the size of its terms)
        {"name": "equilibrium", "type": "fn", "nodes": ["rs", "rc"], "sigma": 1e-9,
         "f": lambda v: _derivatives(v["rs"], Zv, v["rc"], structure)[0] * v["rs"] ** 2},
        {"name": "curvature", "type": "fn", "nodes": ["curv", "rs", "rc"], "sigma": 1e-9,
         "f": lambda v: math.log10(v["curv"]) - math.log10(max(_derivatives(v["rs"], Zv, v["rc"], structure)[1], 1e-12))},
        # B = E'' / (12 pi rs) in Ry / a0^3, with Ry = Ha / 2
        {"name": "bulk modulus", "terms": {"B": 1, "curv": -1, "rs": 1, "Ha": -1, "a0": 3},
         "rhs": math.log10(1 / (24 * math.pi)), "sigma": 1e-9},
        # density: an atom of mass M mu shares its Zv electrons' spheres
        {"name": "density", "terms": {"rho": 1, "rs": 3, "a0": 3, "M": -1, "mu": -1},
         "rhs": math.log10(1 / (Zv * 4 * math.pi / 3)), "sigma": 1e-9},
    ]
    measured = {"rc": (rc, rc_sigma_dex), "a0": (c["a0"], constants["sigma_dex"]["a0"] + 1e-14),
                "Ha": (c["Ha"], constants["sigma_dex"]["Ha"] + 1e-14),
                "mu": (c["mu"], constants["sigma_dex"]["mu"] + 1e-14), "M": (A, 1e-5)}
    return GlobalRelationalNetwork(nodes, rels).solve(measured_dict=measured, max_iterations=60)


def predict_metal(symbol, constants, lattice=False):
    """lattice False: first order. True: each lattice (bcc, fcc) is tried, the one of lowest energy is kept."""
    Z, Zv, _ = METALS[symbol]
    I_last = ionization_energy(Z, Zv)          # the last valence electron to leave
    core = core_network(Zv, I_last)
    rc, rc_s = core["values"]["rc"], core["sigma_dex"]["rc"]
    best = None
    for structure in (("bcc", "fcc") if lattice else (None,)):
        out = metal_network(symbol, constants, rc, rc_s, structure)
        E = total_energy(out["values"]["rs"], Zv, rc, structure)
        if best is None or E < best[0]:
            best = (E, structure, out)
    _, structure, out = best
    v, s = out["values"], out["sigma_dex"]
    return {"symbol": symbol, "I_last_eV": I_last * constants["values"]["Ha"] / CONSTANTS["e"][0],
            "rc": rc, "rs": v["rs"], "structure": structure or "-",
            "density": v["rho"] / 1000.0, "density_rel": LN10 * s["rho"],
            "bulk_GPa": v["B"] / 1e9, "bulk_rel": LN10 * s["B"], "converged": out["converged"]}


# ============================================================
# REPORT
# ============================================================

def report(atoms=True, metals=True):
    constants = constants_network()
    c = constants["values"]
    print(f"Constants network: a0 = {c['a0']:.9e} m, Ha = {c['Ha'] / CONSTANTS['e'][0]:.6f} eV")
    ha_ev = c["Ha"] / CONSTANTS["e"][0]
    if atoms:
        print("\nIonization energies from Z alone (LDA atoms):")
        errs = []
        for Z, sym in enumerate(SYMBOLS, start=1):
            if not sym or sym not in MEASURED_IE:
                continue
            ie = ionization_energy(Z) * ha_ev
            err = ie / MEASURED_IE[sym] - 1
            errs.append(err)
            print(f"  {sym:3} {ie:6.2f} eV  measured {MEASURED_IE[sym]:6.2f}  {100 * err:+5.1f} %")
        print(f"  median error {100 * np.median(np.abs(errs)):.1f} %")
    if metals:
        for lattice in (False, True):
            title = ("first order: electron gas among empty-core ions" if not lattice else
                     "second order: + band-structure energy of the lattice (bcc or fcc, the lower is kept)")
            print(f"\nSimple metals, {title}:")
            print(f"  {'':3} {'r_c':>5} {'r_s':>5} {'lattice':>7} {'density g/cm3':>15} {'meas.':>6} {'err':>5} "
                  f"{'bulk GPa':>14} {'meas.':>6} {'err':>5}")
            d_err, b_err = [], []
            for sym in METALS:
                p = predict_metal(sym, constants, lattice)
                dm, bm = MEASURED_DENSITY[sym], MEASURED_BULK.get(sym)
                d_err.append(abs(p["density"] / dm - 1))
                if bm:
                    b_err.append(abs(p["bulk_GPa"] / bm - 1))
                berr = f"{100 * (p['bulk_GPa'] / bm - 1):+4.0f}%" if bm else "    -"
                print(f"  {sym:3} {p['rc']:5.2f} {p['rs']:5.2f} {p['structure']:>7} {p['density']:6.3f} ± {100 * p['density_rel']:3.0f}% "
                      f"{dm:6.3f} {100 * (p['density'] / dm - 1):+4.0f}% {p['bulk_GPa']:6.1f} ± {100 * p['bulk_rel']:3.0f}% "
                      f"{bm if bm else '-':>6} {berr}")
            print(f"  median error: density {100 * np.median(d_err):.0f} %, bulk modulus {100 * np.median(b_err):.0f} %")


def main():
    ap = argparse.ArgumentParser(description="GRM Matter: from quantum constants to metals")
    ap.add_argument("--atoms-only", action="store_true")
    ap.add_argument("--metals-only", action="store_true")
    args = ap.parse_args()
    t = time.perf_counter()
    report(atoms=not args.metals_only, metals=not args.atoms_only)
    print(f"\n({time.perf_counter() - t:.0f} s)")


if __name__ == "__main__":
    main()
