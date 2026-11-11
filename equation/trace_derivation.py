# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Anthony Charretier
"""Which relations of the GRM network add up to  S x Equant = Estock, and with which weights.

The log relations are linear in log10:  A x = b (one row per relation). A combination y of rows with
    y^T A = +1 on S, +1 on Equant, -1 on Estock, 0 on every other node except the fixed constants
is a derivation of the equation from the network's own relations. Many combinations can exist (closed loops of
relations that add up to nothing can be added freely), so the smallest one (minimum norm) is taken: it holds no
loop that does not serve the equation. The relations it uses, with their weights, are the network's steps.

The steps are then set against the derivation on paper:
    D0  tP^2 = hbar G / c^5                      (Planck time)
    D1  R = c / H                                (horizon)
    D2  Estock = c^4 R / (2 G)                   (black hole as large as the horizon)
    D3  Equant = hbar H / (2 pi)                 (Gibbons-Hawking temperature)
    D4  S = 4 pi R^2 / (4 lP^2)                  (Bekenstein-Hawking entropy)

    python trace_derivation.py
    python trace_derivation.py --store data/grm_network_cf4.json --network cf4_sys_3pct
    python trace_derivation.py --target S Equant Estock --powers 1 1 -1
"""
import argparse
import math

import numpy as np

from pygrm import GlobalRelationalNetwork
from store import load_grm_network_safely

import settings
DEFAULT_STORE = getattr(settings, "GRM_NETWORK_STORE_JSON_ENRICHED", None) or settings.GRM_NETWORK_STORE_JSON

# which paper step a relation of the network plays, when it is one of these (set by hand from their terms)
PAPER_STEP = {
    "i_lP": "D0  Planck length lP = sqrt(hbar G / c^3)   (= c tP)",
    "i_tP": "D0  Planck time tP = lP / c",
    "i_S": "D4 + D1  S = pi c^2 / (H_end^2 lP^2)",
    "i_Tfloor": "D3  T = hbar H_end / (2 pi kB)",
    "i_Equant": "D3  Equant = kB T",
    "i_Estock": "D2'  Estock = rho_vacuum c^2 x (4 pi / 3)(c / H_end)^3",
    "i_rhoL": "D2'  rho_vacuum = 3 H0^2 OL / (8 pi G)",
    "i_Hend": "D2'  H_end = H0 sqrt(OL)",
}


def main():
    ap = argparse.ArgumentParser(description="Trace the derivation of an equation through the GRM relations.")
    ap.add_argument("--store", default=DEFAULT_STORE)
    ap.add_argument("--network", default=None)
    ap.add_argument("--target", nargs="+", default=["S", "Equant", "Estock"])
    ap.add_argument("--powers", nargs="+", type=float, default=[1.0, 1.0, -1.0])
    args = ap.parse_args()
    if len(args.target) != len(args.powers):
        raise SystemExit("--target and --powers need the same length")

    data = load_grm_network_safely(args.store, network_id=args.network)
    net = GlobalRelationalNetwork(data["nodes_spec"], data["relations_spec"])
    names = net.nodes_names
    constants = [n for n in names if n in net.fixed_nodes]

    rows, rhs, rel_names, rel_terms = [], [], [], []
    for rel in net.relations:
        if rel["type"] != "log" or callable(rel["rhs"]):
            continue
        row = np.zeros(len(names))
        for i, c in rel["terms"]:
            row[i] += c
        rows.append(row)
        rhs.append(float(rel["rhs"]))
        rel_names.append(rel["name"])
        rel_terms.append({names[i]: c for i, c in rel["terms"]})
    A, b = np.array(rows), np.array(rhs)

    free_cols = [k for k, n in enumerate(names) if n not in constants]
    target = np.zeros(len(free_cols))
    for n, p in zip(args.target, args.powers):
        if n not in names:
            raise SystemExit(f"unknown node '{n}'")
        target[free_cols.index(names.index(n))] = p
    M = A[:, free_cols]
    y, *_ = np.linalg.lstsq(M.T, target, rcond=None)          # minimum-norm combination
    miss = np.max(np.abs(M.T @ y - target))
    if miss > 1e-8:
        print(f"\nThe network's log relations do not give this equation (closest combination misses by {miss:.2e}).")
        return

    const_coef = {names[k]: float((y @ A)[k]) for k in range(len(names)) if names[k] in constants}
    const_coef = {k: v for k, v in const_coef.items() if abs(v) > 1e-9}
    right = float(y @ b)
    print("\nEquation found in the network:")
    left = " + ".join(f"{p:g} log {n}" for n, p in zip(args.target, args.powers))
    consts = " ".join(f"{v:+g} log {k}" for k, v in const_coef.items())
    print(f"  {left} {consts} = {right:.6f}")
    print(f"  i.e. the constant part is 10^{right:.6f} = {10 ** right:.6g}" + ("  (1 / 4 pi)" if abs(10 ** right - 1 / (4 * math.pi)) < 1e-9 else ""))

    used = [(abs(w), w, rel_names[k], rel_terms[k], rhs[k]) for k, w in enumerate(y) if abs(w) > 1e-9]
    used.sort(key=lambda t: -t[0])
    print(f"\nThe network's steps ({len(used)} relations, weight = how many times each one is used):")
    for _, w, name, terms, r in used:
        t = " ".join(f"{c:+g}·log {n}" for n, c in terms.items())
        print(f"  {w:+7.3f} x {name:14s} [{t} = {r:.6f}]")
        if name in PAPER_STEP:
            print(f"              paper step: {PAPER_STEP[name]}")
    covered = {PAPER_STEP[n][:3].strip() for _, _, n, _, _ in used if n in PAPER_STEP}
    print("\nPaper steps found in the network's path: " + (", ".join(sorted(covered)) or "none"))
    if any(n in ("i_Estock", "i_rhoL") for _, _, n, _, _ in used):
        print("D2' instead of D2: the network builds Estock as the vacuum energy filling the horizon (rho_vacuum x"
              " volume),\nnot as a black hole of the horizon's size; with rho_vacuum = 3 H_end^2 / (8 pi G) the two"
              " give the same c^5 / (2 G H_end).")

    values = net.solve(measured_dict={k: tuple(v) if isinstance(v, list) else (v, 1e-4)
                                      for k, v in data["measured"].items()}, compute_uncertainty=False)["values"]
    lhs = sum(p * math.log10(values[n]) for n, p in zip(args.target, args.powers)) \
        + sum(v * math.log10(values[k]) for k, v in const_coef.items())
    print(f"\nCheck on the solved values: left side - right side = {lhs - right:.3e} decades")


if __name__ == "__main__":
    main()
