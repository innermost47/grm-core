# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Anthony Charretier
"""The GRM seismograph: shake one node of the network and record how every other node answers.

The source node is moved step by step over a range of decades; at each step the whole network is solved again,
with every other measurement kept. Each node's answer is its trace: log10(value) against log10(source).
    - still      the node does not move
    - straight   a power law: a straight line in log (the slope is the exponent). Log relations can only make these.
    - curved     anything else: curves are born in sum and fn relations (sums, saturations)
The curved traces are then compared with one another (same shape after normalising) and with the wave of
S x Equant = Estock (a tanh); the same comparison with random saturation curves gives the chance level.

    python seismograph.py Hend            shake H_end by +-1 decade
    python seismograph.py OL --span 0.5   shake Omega_Lambda by +-0.5 decade
Writes seismograph_<node>.csv (all traces), seismograph_<node>.png (the seismogram), and prints the report.
"""
import argparse
import csv
import math

import numpy as np

from pygrm import GlobalRelationalNetwork
from settings import GRM_NETWORK_STORE_JSON
from store import load_grm_network_safely

STILL = 1e-6          # decades: below this a node did not move
STRAIGHT_R2 = 0.9999  # a trace this close to a line is a power law
SAME_SHAPE = 0.999    # correlation above which two normalised traces have the same shape


def to_log(net, name, value):
    return value if net.lin[net.node_to_idx[name]] else math.log10(value)


def shake(net, measured, source, span, steps):
    base = net.solve(measured_dict=measured, compute_uncertainty=False)["values"]
    centre = base[source]
    is_lin = net.lin[net.node_to_idx[source]]
    xs = np.linspace(-span, span, steps)
    traces = {n: [] for n in net.nodes_names}
    start = dict(base)
    for x in xs:
        value = centre + x if is_lin else centre * 10 ** x
        m = dict(measured)
        m[source] = (value, 1e-9)
        out = net.solve(measured_dict=m, compute_uncertainty=False, start=start)["values"]
        start = out
        for n in net.nodes_names:
            v = out[n]
            traces[n].append(v if net.lin[net.node_to_idx[n]] or v <= 0 else math.log10(v))
    return xs, {n: np.array(t) for n, t in traces.items()}


def classify(xs, trace):
    y = trace - trace[len(trace) // 2]
    if np.max(np.abs(y)) < STILL:
        return "still", 0.0, 1.0
    slope, icept = np.polyfit(xs, trace, 1)
    fit = slope * xs + icept
    ss = np.sum((trace - trace.mean()) ** 2)
    r2 = 1 - np.sum((trace - fit) ** 2) / ss if ss > 0 else 1.0
    return ("straight" if r2 >= STRAIGHT_R2 else "curved"), float(slope), float(r2)


def normalise(t):
    t = t - t.min()
    return t / t.max() if t.max() > 0 else t


def tanh_match(xs, t):
    """Best correlation of a normalised trace with a tanh of any centre and steepness (either direction)."""
    tn = normalise(t)
    best = 0.0
    for x0 in np.linspace(xs[0], xs[-1], 41):
        for k in np.geomspace(0.3, 30, 30):
            w = np.tanh(k * (xs - x0))
            c = abs(np.corrcoef(tn, w)[0, 1]) if np.std(w) > 0 else 0.0
            best = max(best, c)
    return best


def main():
    ap = argparse.ArgumentParser(description="Shake one node of the GRM network and record every answer.")
    ap.add_argument("source", help="node to shake")
    ap.add_argument("--span", type=float, default=1.0, help="decades (or units for a signed node) each way; default 1")
    ap.add_argument("--steps", type=int, default=41)
    args = ap.parse_args()

    data = load_grm_network_safely(GRM_NETWORK_STORE_JSON)
    measured = {k: tuple(v) if isinstance(v, list) else v for k, v in data.get("measured", {}).items()}
    net = GlobalRelationalNetwork(data["nodes_spec"], data["relations_spec"])
    if args.source not in net.node_to_idx:
        raise SystemExit(f"unknown node '{args.source}'")
    measured.pop(args.source, None)

    xs, traces = shake(net, measured, args.source, args.span, args.steps)
    kinds = {n: classify(xs, t) for n, t in traces.items() if n != args.source}

    still = [n for n, k in kinds.items() if k[0] == "still"]
    straight = sorted(((n, k[1]) for n, k in kinds.items() if k[0] == "straight"), key=lambda a: -abs(a[1]))
    curved = [n for n, k in kinds.items() if k[0] == "curved"]
    print(f"\nShaking {args.source} over +-{args.span} ({args.steps} steps): {len(kinds)} nodes listened to")
    print(f"  still: {len(still)}   straight (power laws): {len(straight)}   curved: {len(curved)}")
    print("\nStraight answers (exponent = slope in log):")
    for n, s in straight[:25]:
        print(f"  {n:20s} {s:+.4f}")

    if curved:
        shapes = {n: normalise(traces[n]) for n in curved}
        print("\nCurved answers (where shapes are born):")
        for n in curved:
            print(f"  {n:20s} tanh match {tanh_match(xs, traces[n]):.4f}")
        # families of the same shape
        left, families = list(curved), []
        while left:
            a = left.pop(0)
            fam = [a] + [b for b in left if abs(np.corrcoef(shapes[a], shapes[b])[0, 1]) >= SAME_SHAPE]
            left = [b for b in left if b not in fam]
            families.append(fam)
        print("\nFamilies of curved answers with the same shape:")
        for fam in sorted(families, key=len, reverse=True):
            print(f"  {len(fam):3d}: {', '.join(fam)}")
        # chance: how often random saturation curves look like a tanh as well as the curved answers do
        rng = np.random.default_rng(0)
        rand = []
        for _ in range(200):
            p = rng.uniform(0.5, 4)
            x0 = rng.uniform(xs[0], xs[-1])
            k = 10 ** rng.uniform(-0.5, 1.5)
            rand.append(tanh_match(xs, np.sign(xs - x0) * np.abs(np.tanh(k * (xs - x0))) ** p))
        print(f"\nChance level: random saturation curves reach a tanh match of {np.median(rand):.4f} (median), "
              f"{np.percentile(rand, 90):.4f} (90th percentile)")

    with open(f"seismograph_{args.source}.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["shift_" + args.source] + list(traces))
        for i, x in enumerate(xs):
            w.writerow([f"{x:.6g}"] + [f"{traces[n][i]:.10g}" for n in traces])

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        moving = [n for n in kinds if kinds[n][0] != "still"]
        moving.sort(key=lambda n: (kinds[n][0] != "curved", -np.ptp(traces[n])))
        moving = moving[:40]
        fig, ax = plt.subplots(figsize=(10, max(4, 0.32 * len(moving) + 1)))
        for i, n in enumerate(moving):
            t = traces[n] - traces[n][len(xs) // 2]
            scale = 0.45 / max(np.max(np.abs(t)), 1e-12)
            color = "#d97706" if kinds[n][0] == "curved" else "#2563eb"
            ax.plot(xs, i + t * scale, color=color, lw=1.2)
            ax.text(xs[-1] + 0.02 * (xs[-1] - xs[0]), i, f"{n}  ({np.ptp(traces[n]):.3g})", va="center", fontsize=7)
        ax.set_yticks([])
        ax.set_xlabel(f"shift of {args.source} ({'decades' if not net.lin[net.node_to_idx[args.source]] else 'units'})")
        ax.set_title(f"Seismogram: shaking {args.source} (orange: curved, blue: power law; each trace scaled)")
        ax.set_xlim(xs[0], xs[-1] + 0.35 * (xs[-1] - xs[0]))
        fig.tight_layout()
        fig.savefig(f"seismograph_{args.source}.png", dpi=140)
        print(f"\nWrote seismograph_{args.source}.csv and seismograph_{args.source}.png")
    except ImportError:
        print(f"\nWrote seismograph_{args.source}.csv (matplotlib not installed: no picture)")


if __name__ == "__main__":
    main()
