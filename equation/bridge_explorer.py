# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Anthony Charretier
"""The GRM bridge explorer: every law that holds for ANY object between a quantum and a classical quantity.

One network holds textbook relations of quantum, gravitational and thermal physics for an object of mass m, size R,
in surroundings at temperature T. For every pair of quantities, the object (m, R, T) is eliminated
(global_equations): when an equation is left, it holds for every object, a universal bridge. Most are textbook;
the explorer prints them all, with the relations they come from, so each can be checked by hand.

    python bridge_explorer.py
"""
import itertools
import math

from pygrm import GlobalRelationalNetwork

HBAR, C, G, KB = 1.054571817e-34, 299792458.0, 6.67430e-11, 1.380649e-23
CONSTANTS = ["hbar", "c", "G", "kB"]
OBJECT = ["m", "R", "T"]
L2 = math.log10

# name: (side, description)
QUANTITIES = {
    "lambda_C": ("quantum", "reduced Compton wavelength hbar/(m c)"),
    "t_C": ("quantum", "Compton time hbar/(m c^2)"),
    "lambda_th": ("quantum", "thermal de Broglie wavelength hbar sqrt(2 pi/(m kB T))"),
    "tau_DP": ("quantum", "Diosi-Penrose collapse time hbar R/(G m^2)"),
    "T_H": ("quantum", "Hawking temperature hbar c^3/(8 pi G m kB)"),
    "S_BH": ("quantum", "Bekenstein-Hawking entropy 4 pi G m^2 kB/(hbar c)"),
    "t_evap": ("quantum", "black-hole evaporation time 5120 pi G^2 m^3/(hbar c^4)"),
    "r_s": ("classical", "Schwarzschild radius 2 G m/c^2"),
    "t_light": ("classical", "light-crossing time R/c"),
    "t_ff": ("classical", "free-fall time sqrt(R^3/(G m))"),
    "E_grav": ("classical", "self-gravity energy G m^2/R"),
    "v_th": ("classical", "thermal speed sqrt(kB T/m)"),
}

RELATIONS = [
    ("compton", {"lambda_C": 1, "hbar": -1, "m": 1, "c": 1}, 0.0),
    ("compton_time", {"t_C": 1, "hbar": -1, "m": 1, "c": 2}, 0.0),
    ("thermal_wavelength", {"lambda_th": 1, "hbar": -1, "m": 0.5, "kB": 0.5, "T": 0.5}, 0.5 * L2(2 * math.pi)),
    ("diosi_penrose", {"tau_DP": 1, "hbar": -1, "R": -1, "G": 1, "m": 2}, 0.0),
    ("hawking", {"T_H": 1, "hbar": -1, "c": -3, "G": 1, "m": 1, "kB": 1}, -L2(8 * math.pi)),
    ("bekenstein_hawking", {"S_BH": 1, "G": -1, "m": -2, "kB": -1, "hbar": 1, "c": 1}, L2(4 * math.pi)),
    ("evaporation", {"t_evap": 1, "G": -2, "m": -3, "hbar": 1, "c": 4}, L2(5120 * math.pi)),
    ("schwarzschild", {"r_s": 1, "G": -1, "m": -1, "c": 2}, L2(2.0)),
    ("light_crossing", {"t_light": 1, "R": -1, "c": 1}, 0.0),
    ("free_fall", {"t_ff": 1, "R": -1.5, "G": 0.5, "m": 0.5}, 0.0),
    ("self_gravity", {"E_grav": 1, "G": -1, "m": -2, "R": 1}, 0.0),
    ("thermal_speed", {"v_th": 1, "kB": -0.5, "T": -0.5, "m": 0.5}, 0.0),
]


def build():
    guesses = {"hbar": HBAR, "c": C, "G": G, "kB": KB}
    nodes = {n: {"guess": guesses.get(n, 1.0)} for n in CONSTANTS + OBJECT + list(QUANTITIES)}
    rels = [{"name": name, "terms": terms, "rhs": rhs} for name, terms, rhs in RELATIONS]
    return GlobalRelationalNetwork(nodes, rels)


def main():
    net = build()
    found = []
    for a, b in itertools.combinations(QUANTITIES, 2):
        for eq in net.global_equations([a, b] + CONSTANTS):
            if a in eq["terms"] and b in eq["terms"]:
                found.append((a, b, eq))
    for a, b, eq in found:
        sides = f"{QUANTITIES[a][0]} / {QUANTITIES[b][0]}"
        print(f"[{sides:19s}] {eq['text']}")
        print(f"{'':22s}from {', '.join(eq['relations'])}")
    print(f"\n{len(found)} universal bridges between {len(QUANTITIES)} quantities "
          f"({len(QUANTITIES) * (len(QUANTITIES) - 1) // 2} pairs tried)\n")

    # three quantities, none of whose pairs is bridged: laws that need all three (the size or the temperature
    # cancels only between them), mixing the quantum and classical sides
    paired = {frozenset((a, b)) for a, b, _ in found}
    triples = []
    for trio in itertools.combinations(QUANTITIES, 3):
        if any(frozenset(p) in paired for p in itertools.combinations(trio, 2)):
            continue
        if len({QUANTITIES[q][0] for q in trio}) < 2:
            continue
        for eq in net.global_equations(list(trio) + CONSTANTS):
            if all(q in eq["terms"] for q in trio):
                triples.append((trio, eq))
    for trio, eq in triples:
        print(f"[{' + '.join(QUANTITIES[q][0][0] for q in trio)}] {eq['text']}")
        print(f"{'':9s}from {', '.join(eq['relations'])}")
    print(f"\n{len(triples)} three-way bridges")


if __name__ == "__main__":
    main()
