# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Anthony Charretier
"""
A bank of known quantities, for the explorer: when a network asks for a node nobody measured, is its value one that
is already known?

Each entry: symbol, name, value, relative 1-sigma uncertainty (0 = exact), SI unit, dimensionless or not, source.
Sources: CODATA 2018 (NIST, physics.nist.gov/cuu/Constants), IAU 2012 B2 and 2015 B3 nominal values, Planck 2018,
Particle Data Group, and mathematical constants.

The explorer compares a dimensionless node with the dimensionless entries and some simple forms of them
(powers, 1 + x, 1 - x). A match is a perspective, not a finding: with many entries and forms, some numbers match
by chance, and the explorer says how many would be expected.
"""
import math

BANK = [
    # ---------------------------------------------------------------- fundamental constants (CODATA 2018)
    ("c", "speed of light in vacuum", 299792458.0, 0.0, "m/s", False, "CODATA 2018 (exact)"),
    ("h", "Planck constant", 6.62607015e-34, 0.0, "J s", False, "CODATA 2018 (exact)"),
    ("hbar", "reduced Planck constant", 1.054571817e-34, 0.0, "J s", False, "CODATA 2018 (exact)"),
    ("e", "elementary charge", 1.602176634e-19, 0.0, "C", False, "CODATA 2018 (exact)"),
    ("k_B", "Boltzmann constant", 1.380649e-23, 0.0, "J/K", False, "CODATA 2018 (exact)"),
    ("N_A", "Avogadro constant", 6.02214076e23, 0.0, "1/mol", False, "CODATA 2018 (exact)"),
    ("G", "Newtonian constant of gravitation", 6.67430e-11, 2.2e-5, "m^3/(kg s^2)", False, "CODATA 2018"),
    ("m_e", "electron mass", 9.1093837015e-31, 3.0e-10, "kg", False, "CODATA 2018"),
    ("m_p", "proton mass", 1.67262192369e-27, 3.1e-10, "kg", False, "CODATA 2018"),
    ("m_n", "neutron mass", 1.67492749804e-27, 5.7e-10, "kg", False, "CODATA 2018"),
    ("m_mu", "muon mass", 1.883531627e-28, 2.2e-8, "kg", False, "CODATA 2018"),
    ("a_0", "Bohr radius", 5.29177210903e-11, 1.5e-10, "m", False, "CODATA 2018"),
    ("R_inf", "Rydberg constant", 10973731.568160, 1.9e-12, "1/m", False, "CODATA 2018"),
    ("sigma_SB", "Stefan-Boltzmann constant", 5.670374419e-8, 0.0, "W/(m^2 K^4)", False, "CODATA 2018 (exact)"),
    ("eps_0", "vacuum electric permittivity", 8.8541878128e-12, 1.5e-10, "F/m", False, "CODATA 2018"),
    ("b_Wien", "Wien wavelength displacement constant", 2.897771955e-3, 0.0, "m K", False, "CODATA 2018 (exact)"),
    ("l_P", "Planck length", 1.616255e-35, 1.1e-5, "m", False, "CODATA 2018"),
    ("m_P", "Planck mass", 2.176434e-8, 1.1e-5, "kg", False, "CODATA 2018"),
    ("r_p", "proton rms charge radius", 8.414e-16, 2.3e-3, "m", False, "CODATA 2018"),
    # ---------------------------------------------------------------- dimensionless (CODATA 2018, PDG)
    ("alpha", "fine-structure constant", 7.2973525693e-3, 1.5e-10, "", True, "CODATA 2018"),
    ("1/alpha", "inverse fine-structure constant", 137.035999084, 1.5e-10, "", True, "CODATA 2018"),
    ("m_p/m_e", "proton-electron mass ratio", 1836.15267343, 6.0e-11, "", True, "CODATA 2018"),
    ("m_n/m_p", "neutron-proton mass ratio", 1.67492749804e-27 / 1.67262192369e-27, 6.0e-10, "", True, "CODATA 2018"),
    ("m_mu/m_e", "muon-electron mass ratio", 206.7682830, 2.2e-8, "", True, "CODATA 2018"),
    ("m_tau/m_e", "tau-electron mass ratio", 1776.93 / 0.51099895, 5.1e-5, "", True, "PDG (m_tau = 1776.93 +- 0.09 MeV)"),
    ("g_e/2", "electron magnetic moment in Bohr magnetons", 1.00115965218128, 1.7e-13, "", True, "CODATA 2018"),
    ("alpha_G", "gravitational coupling of two protons", 6.67430e-11 * 1.67262192369e-27 ** 2 / (1.054571817e-34 * 299792458.0),
     2.2e-5, "", True, "from CODATA 2018"),
    # ---------------------------------------------------------------- astronomy (IAU) and cosmology
    ("au", "astronomical unit", 1.495978707e11, 0.0, "m", False, "IAU 2012 B2 (exact)"),
    ("GM_sun", "heliocentric gravitational constant", 1.3271244e20, 0.0, "m^3/s^2", False, "IAU 2015 B3 (nominal)"),
    ("R_sun", "nominal solar radius", 6.957e8, 0.0, "m", False, "IAU 2015 B3 (nominal)"),
    ("L_sun", "nominal solar luminosity", 3.828e26, 0.0, "W", False, "IAU 2015 B3 (nominal)"),
    ("T_sun", "nominal solar effective temperature", 5772.0, 0.0, "K", False, "IAU 2015 B3 (nominal)"),
    ("GM_earth", "geocentric gravitational constant", 3.986004e14, 0.0, "m^3/s^2", False, "IAU 2015 B3 (nominal)"),
    ("R_earth", "nominal Earth equatorial radius", 6.3781e6, 0.0, "m", False, "IAU 2015 B3 (nominal)"),
    ("H0_Planck", "Hubble constant (CMB, Planck 2018)", 67.4, 0.5 / 67.4, "km/s/Mpc", False, "Planck 2018"),
    ("T_CMB", "temperature of the microwave background", 2.7255, 0.0006 / 2.7255, "K", False, "Fixsen 2009"),
    ("Omega_L", "dark energy share (Planck 2018)", 0.6847, 0.0073 / 0.6847, "", True, "Planck 2018"),
    ("Omega_m", "matter share (Planck 2018)", 0.3153, 0.0073 / 0.3153, "", True, "Planck 2018"),
    ("tau_n", "neutron lifetime (PDG average)", 878.3, 0.4 / 878.3, "s", False, "PDG 2026"),
    # ---------------------------------------------------------------- mathematics (exact)
    ("pi", "pi", math.pi, 0.0, "", True, "mathematics"),
    ("e_math", "Euler's number", math.e, 0.0, "", True, "mathematics"),
    ("phi", "golden ratio", (1 + 5 ** 0.5) / 2, 0.0, "", True, "mathematics"),
    ("sqrt2", "square root of 2", 2 ** 0.5, 0.0, "", True, "mathematics"),
    ("sqrt3", "square root of 3", 3 ** 0.5, 0.0, "", True, "mathematics"),
    ("ln2", "natural logarithm of 2", math.log(2), 0.0, "", True, "mathematics"),
    ("zeta3", "Apery's constant zeta(3)", 1.2020569031595942, 0.0, "", True, "mathematics"),
    ("gamma_E", "Euler-Mascheroni constant", 0.5772156649015329, 0.0, "", True, "mathematics"),
]

FORMS = [  # (label, function of x, d log f / d log x; None: computed, and only for a small x)
    ("{}", lambda x: x, 1.0), ("1/{}", lambda x: 1 / x, 1.0), ("{}^2", lambda x: x * x, 2.0), ("1/{}^2", lambda x: 1 / (x * x), 2.0),
    ("sqrt({})", lambda x: x ** 0.5, 0.5), ("1/sqrt({})", lambda x: x ** -0.5, 0.5), ("{}^3", lambda x: x ** 3, 3.0),
    ("{}^(1/3)", lambda x: x ** (1 / 3), 1 / 3), ("1 + {}", lambda x: 1 + x, None), ("1 - {}", lambda x: 1 - x, None),
    ("1/(1 + {})", lambda x: 1 / (1 + x), None), ("2 {}", lambda x: 2 * x, 1.0), ("{}/2", lambda x: x / 2, 1.0),
]
SMALL_RATIONALS = sorted({(p, q) for q in range(1, 7) for p in range(1, 13) if math.gcd(p, q) == 1 and 0.1 < p / q < 12})


def candidates():
    """Every number the bank can offer to a dimensionless node: (label, value, relative uncertainty, source)."""
    out = []
    for sym, name, value, rel, unit, dimensionless, source in BANK:
        if not dimensionless:
            continue
        for label, f, power in FORMS:
            try:
                v = f(value)
            except (ZeroDivisionError, ValueError):
                continue
            if not (v > 0) or math.isinf(v):
                continue
            if power is None:                      # 1 + x, 1 - x: only small corrections make sense
                if value > 0.2:
                    continue
                h = 1e-6
                power = abs(math.log(f(value * (1 + h))) - math.log(v)) / h
            r = rel * power
            out.append((label.format(sym), v, r, f"{name} ({source})"))
    for p, q in SMALL_RATIONALS:
        out.append((f"{p}/{q}" if q > 1 else f"{p}", p / q, 0.0, "a small fraction"))
    return out


def matches(value, sigma_dex, z_max=2.0):
    """Known numbers within z_max sigma of a dimensionless value (sigma in dex), and how many would match by chance.
    Returns (list of (label, candidate value, z, source) best first, expected chance matches, number of candidates)."""
    if not value > 0:
        return [], 0.0, 0
    cands = candidates()
    lv = math.log10(value)
    found = []
    for label, v, rel, source in cands:
        s = math.hypot(sigma_dex, rel / math.log(10))
        z = abs(math.log10(v) - lv) / s if s > 0 else math.inf
        if z <= z_max:
            found.append((label, v, z, source))
    found.sort(key=lambda t: t[2])
    # chance: the density of candidates around the value (per dex), times the width of the window
    near = sum(1 for _, v, _, _ in cands if abs(math.log10(v) - lv) <= 0.5)
    expected = near * (2 * z_max * sigma_dex)
    return found, expected, len(cands)
