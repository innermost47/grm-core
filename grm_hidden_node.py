# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Anthony Charretier
"""
A node nobody told the network about: can it make it emerge? (the Neptune question, on a kitchen scale)

Five objects A..E, each weighed alone, then ten weighings of several of them together (sigma 0.5 g each).
Unknown to the network: a coin (18 g) was stuck under the tray during some of the weighings.

    1. the network as it was told: the objects and the weighings. Does it see that something is missing?
    2. the same network with one node more, H, that nobody measured, and for each weighing a share s_j in (0, 1):
       "how much of H was in this weighing". Nothing says where H is or how heavy it is. A binarity relation
       s (1 - s) = 0, loose then tightened, asks each weighing to choose: H was there, or it was not.
    3. the judge: does H deserve to exist? The tension it removes must be worth the nodes it adds (Bayesian
       information criterion), its mass must be determined, and its shares must be clear-cut.

Control: the same weighings without any coin. The network must not invent one.

Run: python grm_hidden_node.py            (add --sweep: 30 draws of the noise, with and without the coin)
"""
import math
import random
import sys

from grm import GlobalRelationalNetwork

MASSES = {"A": 12.0, "B": 25.0, "C": 40.0, "D": 55.0, "E": 70.0}   # g, the truth
COMBOS = ["AB", "BC", "ACD", "BDE", "AE", "CDE", "ABC", "BD", "ACE", "ABDE"]
COIN = 18.0                                                        # g, the node nobody mentions
COIN_IN = {1, 4, 6, 9}                                             # the weighings it was in
SIGMA = 0.5                                                        # g


def weigh(seed, coin=True):
    rng = random.Random(seed)
    alone = {k: m + rng.gauss(0, SIGMA) for k, m in MASSES.items()}
    together = [sum(MASSES[c] for c in combo) + (COIN if coin and j in COIN_IN else 0.0) + rng.gauss(0, SIGMA)
                for j, combo in enumerate(COMBOS)]
    return alone, together


def measured(alone, together):
    m = {k: (v, SIGMA) for k, v in alone.items()}          # lin nodes: sigma in grams
    m.update({f"W{j}": (w, SIGMA) for j, w in enumerate(together)})
    return m


def told_network():
    """What the network was told: objects and weighings."""
    nodes = {k: {"guess": 30.0, "scale": "lin"} for k in MASSES}
    nodes.update({f"W{j}": {"guess": 50.0, "scale": "lin"} for j in range(len(COMBOS))})
    rels = [{"name": f"weighing {j} ({combo})", "type": "sum", "terms": {f"W{j}": 1.0, **{c: -1.0 for c in combo}},
             "K": 0.0, "sigma": 1e-6} for j, combo in enumerate(COMBOS)]
    return nodes, rels


def with_hidden(binarity):
    """The same, with H and its shares. s_j = o_j / (1 + o_j), o_j a positive node."""
    nodes, _ = told_network()
    nodes["H"] = {"guess": 5.0, "scale": "lin"}
    rels = []
    for j, combo in enumerate(COMBOS):
        nodes[f"o{j}"] = {"guess": 1.0}

        def weighing(v, j=j, combo=combo):
            s = v[f"o{j}"] / (1 + v[f"o{j}"])
            return v[f"W{j}"] - sum(v[c] for c in combo) - v["H"] * s

        def choose(v, j=j):
            s = v[f"o{j}"] / (1 + v[f"o{j}"])
            return s * (1 - s)
        rels.append({"name": f"weighing {j} ({combo})", "type": "fn",
                     "nodes": [f"W{j}", "H", f"o{j}", *combo], "f": weighing, "sigma": 1e-6})
        rels.append({"name": f"H in weighing {j}: yes or no", "type": "fn", "nodes": [f"o{j}"], "f": choose,
                     "sigma": binarity})
    return nodes, rels


def settled(meas, inside):
    """Once each weighing has chosen: the plain network, H in the weighings that chose it, nothing else."""
    nodes, rels = told_network()
    nodes["H"] = {"guess": 10.0, "scale": "lin"}
    for j in inside:
        rels[j]["terms"]["H"] = -1.0
    return GlobalRelationalNetwork(nodes, rels).solve(meas)


def share(v, j):
    return v[f"o{j}"] / (1 + v[f"o{j}"])


def emerge(meas, base):
    """Stage 2: the network with H, its binarity tightened round after round (each round starts where the
    last one ended). It starts from what the tensions of stage 1 say: a weighing heavier than explained
    (pull > +3 sigma) probably held H, the others probably not; H starts at the mean excess of those."""
    # what each weighing read, minus what the objects explain
    excess = {j: meas[f"W{j}"][0] - sum(base["values"][c] for c in combo) for j, combo in enumerate(COMBOS)}
    heavy = [j for j, e in excess.items() if e / SIGMA > 3]
    start = {k: v for k, v in base["values"].items()}
    start["H"] = sum(excess[j] for j in heavy) / len(heavy) if heavy else 1.0
    for j in range(len(COMBOS)):
        start[f"o{j}"] = 9.0 if j in heavy else 1 / 9.0          # share 0.9 or 0.1
    for binarity in (1.0, 0.3, 0.1, 0.03, 0.01):
        nodes, rels = with_hidden(binarity)
        out = GlobalRelationalNetwork(nodes, rels).solve(meas, max_iterations=200, start=start)
        # the next round starts where this one ended (a share that reached 0 or 1 stays just inside)
        start = {k: (min(max(val, 1e-9), 1e9) if k.startswith("o") else val) for k, val in out["values"].items()}
    return out


def judge(base, hidden, meas):
    """Does H deserve to exist? BIC = chi2 + k ln n, k = nodes it adds that the data fix (H and one share per
    weighing counted as one bit each: H + the number of weighings it is in)."""
    v = hidden["values"]
    shares = [share(v, j) for j in range(len(COMBOS))]
    inside = [j for j, s in enumerate(shares) if s > 0.5]
    chi2_hidden = sum(p * p for name, p in hidden["relation_pulls"].items() if name.startswith("weighing"))
    for k, (m, s) in meas.items():
        chi2_hidden += ((v[k] - m) / s) ** 2
    k_added = 1 + len(inside)
    bic_base = base["cost"]
    bic_hidden = chi2_hidden + k_added * math.log(len(meas))
    clear = all(min(s, 1 - s) < 0.1 for s in shares)
    sigma_h = hidden["uncertainty"]["H"]
    determined = sigma_h < 0.2 * max(abs(v["H"]), 1e-9)
    dof = base["dof"] - k_added + len(inside)     # H and its bits: the settled network loses one dof for H
    consistent = chi2_hidden < dof + 3 * math.sqrt(2 * max(dof, 1)) + 1
    verdict = bic_hidden < bic_base and clear and determined and v["H"] > 3 * sigma_h and consistent
    return verdict, {"shares": shares, "inside": inside, "chi2_base": base["cost"], "chi2_hidden": chi2_hidden,
                     "bic_base": bic_base, "bic_hidden": bic_hidden, "H": v["H"], "sigma_H": sigma_h,
                     "clear": clear, "determined": determined, "consistent": consistent}


def run(title, coin, seed=5, quiet=False):
    alone, together = weigh(seed, coin)
    meas = measured(alone, together)
    if quiet:                                   # for the sweep: (found it, exact weighings, H)
        nodes, rels = told_network()
        base = GlobalRelationalNetwork(nodes, rels).solve(meas)
        ok, info = judge(base, emerge(meas, base), meas)
        exact = ok and set(info["inside"]) == (COIN_IN if coin else set())
        return ok, exact, (settled(meas, info["inside"])["values"]["H"] if ok else None)
    print(title)
    nodes, rels = told_network()
    base = GlobalRelationalNetwork(nodes, rels).solve(meas)
    dof = base["dof"]
    print(f"  1. as told: chi2 = {base['cost']:.1f} for {dof} degrees of freedom"
          f" -> {'something is missing' if base['cost'] > dof + 3 * math.sqrt(2 * dof) else 'nothing missing'}")
    meas_pulls = {f"W{j}": (base["values"][f"W{j}"] - together[j]) / SIGMA for j in range(len(COMBOS))}
    print("     the weighing's own pull (measured minus explained, sigma): "
          + "  ".join(f"{j}:{-meas_pulls[f'W{j}']:+.1f}" for j in range(len(COMBOS))))
    hidden = emerge(meas, base)
    ok, info = judge(base, hidden, meas)
    true_in = sorted(COIN_IN) if coin else []
    print(f"  2. with a node H nobody measured (shares still soft): H = {info['H']:.2f} +- {info['sigma_H']:.2f} g")
    print("     share of H in each weighing: " + "  ".join(f"{j}:{s:.2f}" for j, s in enumerate(info["shares"])))
    print(f"     weighings it was in: found {info['inside']}, truth {true_in}")
    print(f"  3. judge: chi2 {info['chi2_base']:.1f} -> {info['chi2_hidden']:.1f}; BIC {info['bic_base']:.1f} -> "
          f"{info['bic_hidden']:.1f}; shares clear-cut: {info['clear']}; mass determined: {info['determined']};"
          f" nothing left unexplained: {info['consistent']}")
    print(f"     verdict: {'H EXISTS' if ok else 'no hidden node'}")
    if ok:
        final = settled(meas, info["inside"])
        print(f"  4. settled network (H only where it was chosen): H = {final['values']['H']:.2f} +- "
              f"{final['uncertainty']['H']:.2f} g (truth {COIN:.0f} g), chi2 = {final['cost']:.1f} for {final['dof']} dof")
    print()


def main():
    run("Run 1: a coin was stuck under the tray in some weighings", coin=True)
    run("Run 2 (control): no coin", coin=False)
    if "--sweep" in sys.argv:
        n = 30
        hits = [run("", True, seed=100 + k, quiet=True) for k in range(n)]
        false = [run("", False, seed=100 + k, quiet=True) for k in range(n)]
        hs = [h for _, _, h in hits if h is not None]
        print(f"Sweep over {n} draws of the noise:")
        print(f"  with the coin: found {sum(h[0] for h in hits)}/{n}, the right weighings {sum(h[1] for h in hits)}/{n},"
              f" H = {sum(hs) / len(hs):.2f} g on average (spread {math.sqrt(sum((h - sum(hs) / len(hs)) ** 2 for h in hs) / len(hs)):.2f})")
        print(f"  without the coin (control): a coin invented {sum(f[0] for f in false)}/{n} times")


if __name__ == "__main__":
    main()
