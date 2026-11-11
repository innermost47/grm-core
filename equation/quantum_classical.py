# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Anthony Charretier
"""Where the quantum and the classical descriptions of a mass meet, as one GRM network.

Every mass m has a quantum length, its reduced Compton wavelength (below it the mass cannot be localised without
creating particles), and a classical length, its Schwarzschild radius (the size at which its own gravity closes
on it):
    lambda_C = hbar / (m c)            quantum side
    r_s      = 2 G m / c^2             classical (gravitational) side
The mass appears in both. Eliminating it with global_equations gives what the network says about the two sides
together, for every mass at once. A third family (the thermal wavelength against the size of an object) says when
a warm object behaves classically.

    python quantum_classical.py
"""
import math

from pygrm import GlobalRelationalNetwork

HBAR = 1.054571817e-34     # J s (exact since 2019 with h)
C = 299792458.0            # m/s (exact)
G = 6.67430e-11            # m^3 kg^-1 s^-2 (CODATA 2018)
KB = 1.380649e-23          # J/K (exact)

CONSTANTS = {"hbar": HBAR, "c": C, "G": G, "kB": KB}


def network(extra_relations=()):
    nodes = {name: {"guess": value} for name, value in CONSTANTS.items()}
    nodes.update({
        "m": {"guess": 1.0},            # the mass (kg)
        "lambda_C": {"guess": 1e-15},   # reduced Compton wavelength (m)
        "r_s": {"guess": 1e-3},         # Schwarzschild radius (m)
        "l_P": {"guess": 1e-35},        # Planck length (m)
        "T": {"guess": 300.0},          # temperature (K)
        "lambda_th": {"guess": 1e-10},  # thermal de Broglie wavelength (m)
    })
    relations = [
        {"name": "compton", "terms": {"lambda_C": 1, "hbar": -1, "m": 1, "c": 1}, "rhs": 0.0},
        {"name": "schwarzschild", "terms": {"r_s": 1, "G": -1, "m": -1, "c": 2}, "rhs": math.log10(2.0)},
        {"name": "planck_length", "terms": {"l_P": 2, "hbar": -1, "G": -1, "c": 3}, "rhs": 0.0},
        # lambda_th = hbar sqrt(2 pi / (m kB T))
        {"name": "thermal", "terms": {"lambda_th": 1, "hbar": -1, "m": 0.5, "kB": 0.5, "T": 0.5},
         "rhs": 0.5 * math.log10(2 * math.pi)},
    ]
    relations += list(extra_relations)
    return GlobalRelationalNetwork(nodes, relations)


def measured(**more):
    m = {name: (value, 1e-12) for name, value in CONSTANTS.items()}
    m.update(more)
    return m


def main():
    net = network()

    print("1) Eliminating the mass: what the quantum and classical lengths of ANY mass share")
    for eq in net.global_equations(["lambda_C", "r_s", "hbar", "G", "c"]):
        print(f"   {eq['text']:45s}  (from {eq['relations']})")
    for eq in net.global_equations(["lambda_C", "r_s", "l_P"]):
        print(f"   {eq['text']:45s}  (from {eq['relations']})")
    print("   -> the product of the two lengths does not depend on the mass: they are mirror images around the")
    print("      Planck length. When one shrinks, the other grows by the same factor.\n")

    print("2) Where they meet: add 'lambda_C = r_s' and let the network find the mass")
    meet = network([{"name": "meeting", "terms": {"lambda_C": 1, "r_s": -1}, "rhs": 0.0}])
    r = meet.solve(measured())
    v = r["values"]
    m_planck = math.sqrt(HBAR * C / G)
    print(f"   m = {v['m']:.4e} kg  (Planck mass sqrt(hbar c / G) = {m_planck:.4e} kg, ratio {v['m'] / m_planck:.4f})")
    print(f"   lambda_C = r_s = {v['lambda_C']:.4e} m  (Planck length {v['l_P']:.4e} m)\n")

    print("3) Each mass on the scale: log10(lambda_C / r_s) > 0 quantum side, < 0 classical side")
    masses = [("electron", 9.1093837015e-31), ("proton", 1.67262192369e-27), ("Planck mass", m_planck),
              ("1 microgram", 1e-9), ("70 kg", 70.0), ("Earth", 5.972e24), ("Sun", 1.989e30)]
    for name, mass in masses:
        v = network().solve(measured(m=(mass, 1e-12), T=(300.0, 1e-12)))["values"]
        print(f"   {name:12s} m={mass:9.3e} kg  lambda_C={v['lambda_C']:9.3e} m  r_s={v['r_s']:9.3e} m  "
              f"log10(ratio)={math.log10(v['lambda_C'] / v['r_s']):+7.2f}")
    print("   (the ratio is (m_P / m)^2 / 2: 2 decades of ratio per decade of mass)\n")

    print("4) The other border, temperature: a warm object is classical when its thermal wavelength is smaller")
    print("   than its own size. Eliminating m between the thermal and Compton relations:")
    for eq in net.global_equations(["lambda_th", "lambda_C", "T", "kB", "hbar", "c"]):
        print(f"   {eq['text']}")
    v = network().solve(measured(m=(1.67262192369e-27, 1e-12), T=(300.0, 1e-12)))["values"]
    print(f"   a proton at 300 K: lambda_th = {v['lambda_th']:.3e} m")


if __name__ == "__main__":
    main()
