# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Anthony Charretier
"""Pluck the relations of the GRM network like strings, and find the ones that vibrate together.

A relation is a string: its right-hand side (rhs for a log relation, K for a sum) is its tension. Plucking it
shifts that tension a little; the whole network is solved again and every node answers. The answer of every
node to every string is one column of the network's response matrix.
    - reach      how many nodes a string sets moving, and how strongly
    - together   strings whose answers have the same shape (cosine close to 1), whatever their ratio: they vibrate
                 as one. The ratio between them is reported as it is; no ratio is preferred (this is not music)
    - modes      the natural vibrations of the whole network (singular value decomposition of the responses):
                 each mode is a set of strings that vibrate together and the nodes they move
    - families   each string goes with its strongest mode; strings strong in several families are the bridges
                 between them
    - timbre     two fingerprints of each string:
                 * its mix of modes: how its vibration shares itself over the families of the network
                 * its distortion: the string's tension is driven by a sine, gently then hard; a string whose
                   answer stays a faithful copy is pure (log relations, power laws), a string that bends the
                   sine adds harmonics of its own (sums, functions: where the network makes curves). The share
                   of harmonics 2, 3, 4 at the hard drive is its colour. --no-distortion skips this (slower) part.
A chord can also be struck: several strings plucked at once (--chord name1,name2,...); the report then says how
its vibration spreads over the families of the network.
The network read is GRM_NETWORK_STORE_JSON_ENRICHED from settings.py when it exists (the expanded network
written by the pipeline), otherwise GRM_NETWORK_STORE_JSON; --store gives another file.

    python grm_strings.py                      pluck every string one by one
    python grm_strings.py --chord i_S,i_Equant,i_Estock
    python grm_strings.py --store data/other_network.json
Writes grm_strings_responses.csv and grm_strings.png, and prints the report.
"""
import argparse
import csv
import math

import numpy as np

from grm_anatomy import anatomy, write_report

from pygrm import GlobalRelationalNetwork
import settings
from store import load_grm_network_safely

PLUCK = 1e-3          # shift of the tension: dex for a log relation; for a sum, this share of the size of its terms
STILL = 1e-9          # a node moving less than this (per unit of pluck) does not answer
TOGETHER = 0.999      # |cosine| above which two strings vibrate as one
SAME_MIX = 0.98       # cosine of two mode mixes above which two strings share a timbre
DRIVE = (0.02, 0.3)   # gentle and hard sine drives of the tension (dex, or share of the terms' size for a sum)
DRIVE_STEPS = 16      # samples per period of the sine
PURE = 1e-3           # harmonics below this share of the fundamental: the string is pure
FAMILY_MIN = 0.01     # a mode carrying at least this share of the answers makes a family
BRIDGE = 0.5          # a string is a bridge when its weight in a second family is at least this share of its first


def node_log(net, values, scale):
    """Every node on a common footing: log10 for a positive node, value / its own size / ln 10 for a signed one
    (a relative change, in the same units as a change of log10), so a charge and a mass are heard alike."""
    return np.array([values[n] / scale[n] / math.log(10) if net.lin[net.node_to_idx[n]] or values[n] <= 0
                     else math.log10(values[n]) for n in net.nodes_names])


def sizes(net, values):
    """Typical size of each signed node (its value, at least 1) and of each sum relation's terms."""
    # a signed node near zero (a charge of 0, say) is measured in absolute units, never divided by its own noise
    node = {n: max(abs(values[n]), 1.0) for n in net.nodes_names}
    rel = {}
    for r in net.relations:
        if r["type"] == "sum":
            t = sum(abs(c * net._to_value(i, net.x[i]) ** p) for i, c, p in r["terms"])
            rel[r["name"]] = max(t, abs(r["K"])) or 1.0
    return node, rel


def tension_key(rel):
    return "rhs" if rel["type"] == "log" else "K"


def pluck(net, measured, base, rels, scales, amount=PLUCK, full=False):
    """Shift the tension of the given internal relations, solve, return the answer of every node per unit."""
    node_scale, rel_scale = scales
    saved = []
    for rel in rels:
        key = tension_key(rel)
        saved.append((rel, key, rel[key]))
        step = amount if rel["type"] == "log" else amount * rel_scale[rel["name"]]
        rel[key] = rel[key] + step
    try:
        res = net.solve(measured_dict=measured, compute_uncertainty=False, start=base["values"])
        out = res["values"]
    finally:
        for rel, key, v in saved:
            rel[key] = v
    if full:
        return res
    return (node_log(net, out, node_scale) - node_log(net, base["values"], node_scale)) / amount


def drive(net, measured, base, rel, scales, amplitude, direction):
    """Drive one string's tension with a sine; the network's answer along the string's own direction, per sample."""
    node_scale, rel_scale = scales
    key = tension_key(rel)
    rest = rel[key]
    size = amplitude if rel["type"] == "log" else amplitude * rel_scale[rel["name"]]
    signal, converged = [], True
    start = base["values"]
    b0 = node_log(net, base["values"], node_scale)
    try:
        for n in range(DRIVE_STEPS):
            rel[key] = rest + size * math.sin(2 * math.pi * n / DRIVE_STEPS)
            res = net.solve(measured_dict=measured, compute_uncertainty=False, start=start)
            converged = converged and res["converged"]
            out = res["values"]
            start = out
            signal.append(float((node_log(net, out, node_scale) - b0) @ direction))
    finally:
        rel[key] = rest
    spec = np.abs(np.fft.rfft(signal))
    h1 = spec[1] if spec[1] > 0 else 1.0
    return spec[2:5] / h1, converged   # harmonics 2, 3, 4 relative to the fundamental; did every solve converge


def ratio_of(a, b):
    """Ratio between two answers of the same shape (a = r b), as it is."""
    i = np.argmax(np.abs(b))
    return a[i] / b[i] if abs(b[i]) > STILL else float("nan")


def main():
    ap = argparse.ArgumentParser(description="Pluck the relations of the GRM network and listen for harmony.")
    ap.add_argument("--chord", default=None, help="comma-separated relation names to strike together")
    ap.add_argument("--no-distortion", action="store_true", help="skip the distortion part of the timbre")
    ap.add_argument("--store", default=None, help="network file (default: the enriched store, else the store)")
    args = ap.parse_args()

    store = args.store or getattr(settings, "GRM_NETWORK_STORE_JSON_ENRICHED", None) or settings.GRM_NETWORK_STORE_JSON
    print(f"Network: {store}")
    data = load_grm_network_safely(store)
    measured = {k: tuple(v) if isinstance(v, list) else v for k, v in data.get("measured", {}).items()}
    net = GlobalRelationalNetwork(data["nodes_spec"], data["relations_spec"])
    base = net.solve(measured_dict=measured, compute_uncertainty=False)
    scales = sizes(net, base["values"])
    strings = [r for r in net.relations if r["type"] in ("log", "sum") and not callable(r.get("rhs"))]
    names = [r["name"] for r in strings]

    print(f"\nPlucking {len(strings)} strings one by one...")
    R = np.column_stack([pluck(net, measured, base, [r], scales) for r in strings])   # nodes x strings
    reach = np.sum(np.abs(R) > STILL, axis=0)
    loud = np.linalg.norm(R, axis=0)

    print("\nStrings that reach furthest (nodes set moving, loudness):")
    for j in np.argsort(-reach)[:15]:
        print(f"  {names[j]:32s} {reach[j]:4d} nodes   {loud[j]:.3g}")
    silent = [names[j] for j in range(len(names)) if reach[j] == 0]
    if silent:
        print(f"\n{len(silent)} strings move nothing (held by the measurements): {', '.join(silent[:20])}"
              + (" ..." if len(silent) > 20 else ""))

    # unison and harmony between strings
    U = R / np.where(loud > 0, loud, 1)
    cos = U.T @ U
    groups, seen = [], set()
    for j in np.argsort(-reach):
        if j in seen or loud[j] == 0:
            continue
        mates = [k for k in range(len(names)) if k not in seen and loud[k] > 0 and abs(cos[j, k]) >= TOGETHER]
        seen.update(mates)
        if len(mates) > 1:
            groups.append(mates)
    print("\nStrings that vibrate together (same answer shape), with their ratio to the first, as it is:")
    for g in sorted(groups, key=len, reverse=True)[:15]:
        lead = g[0]
        print(f"  {len(g):3d}: " + ", ".join(f"{names[k]} ({ratio_of(R[:, k], R[:, lead]):+.4g})" for k in g))

    # natural modes of the network
    # every string plucked with the same energy (unit answers), so the modes say which strings vibrate alike,
    # not only which are loudest
    Uu, s, Vt = np.linalg.svd(U[:, loud > 0], full_matrices=False)
    live_names = [names[j] for j in range(len(names)) if loud[j] > 0]
    energy = s ** 2 / np.sum(s ** 2)
    print("\nLoudest strings (how hard the network shakes when they are plucked):")
    for j in np.argsort(-loud)[:8]:
        print(f"  {names[j]:32s} {loud[j]:.3g}")
    print("\nModes of the whole network, every string plucked with the same energy (share of the answers):")
    for m in range(min(6, len(s))):
        strs = np.argsort(-np.abs(Vt[m]))[:6]
        nds = np.argsort(-np.abs(Uu[:, m]))[:6]
        print(f"  mode {m + 1}: {100 * energy[m]:5.1f} %   strings: {', '.join(live_names[k] for k in strs)}")
        print(f"            nodes:   {', '.join(net.nodes_names[i] for i in nds)}")
    print(f"  {int(np.sum(energy > 0.01))} modes carry more than 1 % each; "
          f"{int(np.searchsorted(np.cumsum(energy), 0.99)) + 1} modes carry 99 % of everything")

    # families: each string with its strongest mode; bridges: strings strong in two families
    live = [j for j in range(len(names)) if loud[j] > 0]
    fam_modes = [m for m in range(len(s)) if energy[m] >= FAMILY_MIN]
    W = np.abs(Vt[fam_modes]) * s[fam_modes, None]                    # weight of each string in each family
    home = np.argmax(W, axis=0)
    print(f"\nFamilies ({len(fam_modes)} modes above {100 * FAMILY_MIN:.0f} %):")
    for f_i, m in enumerate(fam_modes):
        members = [live_names[k] for k in range(len(live)) if home[k] == f_i]
        if members:
            nds = np.argsort(-np.abs(Uu[:, m]))[:5]
            print(f"  family {f_i + 1:2d} ({len(members)} strings; nodes {', '.join(net.nodes_names[i] for i in nds)}): "
                  f"{', '.join(members[:10])}{' ...' if len(members) > 10 else ''}")
    bridges = []
    for k in range(len(live)):
        w = np.sort(W[:, k])[::-1]
        if len(w) > 1 and w[1] >= BRIDGE * w[0]:
            second = np.argsort(-W[:, k])[1]
            bridges.append((live_names[k], home[k] + 1, second + 1, w[1] / w[0]))
    print("\nBridges (strings that belong to two families):")
    for name, a_f, b_f, r in sorted(bridges, key=lambda b: -b[3])[:20]:
        print(f"  {name:32s} families {a_f} and {b_f} ({r:.2f})")

    # timbre 1: the mix of modes of each string
    mix = W ** 2 / np.maximum((W ** 2).sum(axis=0), 1e-300)          # share of each family in each string
    mixn = mix / np.maximum(np.linalg.norm(mix, axis=0), 1e-300)
    left, timbres = list(range(len(live))), []
    while left:
        a = left.pop(0)
        same = [a] + [b for b in left if float(mixn[:, a] @ mixn[:, b]) >= SAME_MIX]
        left = [b for b in left if b not in same]
        timbres.append(same)
    print("\nTimbre 1, mix of modes (strings with the same mix; the families they mix):")
    for g in sorted(timbres, key=len, reverse=True)[:12]:
        if len(g) < 2:
            break
        avg = mix[:, g].mean(axis=1)
        top = np.argsort(-avg)[:3]
        recipe = " + ".join(f"family {t + 1} {100 * avg[t]:.0f} %" for t in top if avg[t] > 0.02)
        print(f"  {len(g):3d} strings [{recipe}]: {', '.join(live_names[k] for k in g[:10])}{' ...' if len(g) > 10 else ''}")

    # timbre 2: distortion under a sine drive of the tension
    if not args.no_distortion:
        print(f"\nTimbre 2, distortion: driving {len(live)} strings with a sine, gently ({DRIVE[0]}) then hard ({DRIVE[1]})...")
        colours, unsettled = {}, []
        for k, j in enumerate(live):
            direction = U[:, j]
            gentle, ok_g = drive(net, measured, base, strings[j], scales, DRIVE[0], direction)
            hard, ok_h = drive(net, measured, base, strings[j], scales, DRIVE[1], direction)
            if ok_g and ok_h:
                colours[names[j]] = (strings[j]["type"], gentle, hard)
            else:
                unsettled.append(names[j])
        pure = [n for n, (_, g, h) in colours.items() if h.max() < PURE]
        coloured = sorted(((n, t, h) for n, (t, g, h) in colours.items() if h.max() >= PURE), key=lambda c: -c[2].sum())
        kinds = {}
        for n, (t, _, h) in colours.items():
            kinds.setdefault(t, [0, 0])[int(h.max() >= PURE)] += 1
        print(f"  pure: {len(pure)} strings   coloured: {len(coloured)} strings   "
              + "   ".join(f"{t}: {v[0]} pure, {v[1]} coloured" for t, v in kinds.items()))
        if unsettled:
            print(f"  left out, the network does not settle when they are driven (no timbre to read): {', '.join(unsettled)}")
        print("  most coloured (harmonics 2, 3, 4 / fundamental, at the hard drive):")
        for n, t, h in coloured[:20]:
            print(f"    {n:32s} [{t}]  {h[0]:.4f}  {h[1]:.4f}  {h[2]:.4f}")
        # strings sharing the same colour (same proportions of harmonics, clearly above purity)
        left, same_colour = [c for c in coloured if c[2].max() >= 10 * PURE], []
        while left:
            a = left.pop(0)
            va = a[2] / np.linalg.norm(a[2])
            mates = [a] + [b for b in left if float(va @ (b[2] / np.linalg.norm(b[2]))) >= 0.995
                           and 0.8 < np.linalg.norm(b[2]) / np.linalg.norm(a[2]) < 1.25]
            left = [b for b in left if b not in mates]
            if len(mates) > 1:
                same_colour.append(mates)
        print("  strings with the same colour (same harmonics in the same proportions):")
        for g in same_colour[:12]:
            print(f"    {', '.join(m[0] for m in g)}")
        if not same_colour:
            print("    none")

    if args.chord:
        wanted = [x.strip() for x in args.chord.split(",")]
        chosen = [r for r in strings if r["name"] in wanted]
        missing = set(wanted) - {r["name"] for r in chosen}
        if missing:
            raise SystemExit(f"unknown relations: {', '.join(sorted(missing))}")
        answer = pluck(net, measured, base, chosen, scales)
        moved = int(np.sum(np.abs(answer) > STILL))
        print(f"\nChord {', '.join(wanted)}: {moved} nodes answer")
        for i in np.argsort(-np.abs(answer))[:20]:
            if abs(answer[i]) > STILL:
                print(f"  {net.nodes_names[i]:20s} {answer[i]:+.5f}")
        unit = answer / (np.linalg.norm(answer) or 1)
        share = np.array([(Uu[:, m] @ unit) ** 2 for m in fam_modes])
        print("How the chord spreads over the families (share of its vibration):")
        for f_i in np.argsort(-share):
            if share[f_i] > 0.005:
                print(f"  family {f_i + 1:2d}: {100 * share[f_i]:5.1f} %")
        print(f"  outside the families: {100 * max(0.0, 1 - share.sum()):5.1f} %")

    # the nodes, the silent floors, the decades, the propagation, the rupture; then the report
    home_all = np.full(len(names), len(fam_modes))
    for k, j in enumerate(live):
        home_all[j] = home[k]
    print("\nAnatomy: nodes, silent floors, decades, propagation, rupture...")
    sections = anatomy(net, measured, base, strings, names, R, scales, pluck, fam_modes, home_all)
    for title, text, latex, _ in sections:
        print(f"\n== {title} ==\n{text}")
        if latex:
            print(f"   LaTeX: {latex}")
    report = write_report(sections, [])
    print(f"\nWrote {report}, grm_strings_breaks.csv and grm_strings_nodes.csv")

    with open("grm_strings_responses.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["node"] + names)
        for i, n in enumerate(net.nodes_names):
            w.writerow([n] + [f"{R[i, j]:.6g}" for j in range(len(names))])

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        live = [j for j in range(len(names)) if loud[j] > 0]
        order = [k for g in sorted(groups, key=len, reverse=True) for k in g]
        order += [j for j in live if j not in order]
        C = np.abs(cos[np.ix_(order, order)])
        fig, ax = plt.subplots(1, 2, figsize=(14, 6.5), gridspec_kw={"width_ratios": [1.3, 1]})
        ax[0].imshow(C, cmap="magma", vmin=0, vmax=1)
        ax[0].set_title("Harmony between strings (|cosine| of their answers)")
        ax[0].set_xticks([]); ax[0].set_yticks([])
        ax[1].bar(np.arange(1, min(30, len(s)) + 1), 100 * energy[:30], color="#d97706")
        ax[1].set_title("Modes of the network")
        ax[1].set_xlabel("mode"); ax[1].set_ylabel("% of all answers")
        fig.tight_layout()
        fig.savefig("grm_strings.png", dpi=130)
        print("\nWrote grm_strings_responses.csv and grm_strings.png")
    except ImportError:
        print("\nWrote grm_strings_responses.csv")


if __name__ == "__main__":
    main()
