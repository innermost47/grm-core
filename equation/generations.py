# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Anthony Charretier
"""The family tree of a GRM network: in which generation each node is born.

Generation 0 are the seeds: the fixed constants (c, G, hbar, kB, e...) and the nodes given with --seed (by default
H_end, the one degree of freedom of S x Equant = Estock). A relation in which every node but one is known gives
birth to that last one, one generation after the youngest of its parents. Each node keeps its earliest birth, and
the relation that gave it. Only log and sum relations are used (fn relations are not in the store).

    python generations.py                       seeds: fixed constants + Hend
    python generations.py --seed Hend H0        other seeds
    python generations.py --data                seeds: fixed constants + every measured node
    python generations.py --with-equation       S x Equant = Estock added as a relation of its own
    python generations.py --store data/grm_network_cf4.json --network cf4_sys_3pct
Writes generations.csv (node, generation, relation, parents) and prints the tree generation by generation.
"""
import argparse
import csv

from store import load_grm_network_safely

import settings
DEFAULT_STORE = getattr(settings, "GRM_NETWORK_STORE_JSON_ENRICHED", None) or settings.GRM_NETWORK_STORE_JSON

WATCH = ("EP", "tP", "lP", "Hend", "S", "Equant", "Estock", "stockEP")


def generations(nodes_spec, relations, seeds):
    """{node: (generation, relation name, parents)} by repeated relaxation (earliest birth wins)."""
    born = {n: (0, "seed", ()) for n in seeds}
    rels = []
    for r in relations:
        if r.get("type", "log") not in ("log", "sum"):
            continue
        terms = [n for n, c in r.get("terms", {}).items() if float(c) != 0.0]
        if len(terms) >= 2:
            rels.append((r.get("name", "?"), terms))
    changed = True
    while changed:
        changed = False
        for name, terms in rels:
            for child in terms:
                if child in seeds:
                    continue
                parents = [n for n in terms if n != child]
                if all(p in born for p in parents):
                    g = 1 + max(born[p][0] for p in parents)
                    if child not in born or g < born[child][0]:
                        born[child] = (g, name, tuple(parents))
                        changed = True
    return born


def main():
    ap = argparse.ArgumentParser(description="Family tree of a GRM network.")
    ap.add_argument("--store", default=DEFAULT_STORE)
    ap.add_argument("--network", default=None)
    ap.add_argument("--seed", nargs="+", default=["Hend"], help="nodes given besides the fixed constants")
    ap.add_argument("--data", action="store_true", help="every measured node is a seed too")
    ap.add_argument("--with-equation", action="store_true",
                    help="add S x Equant = Estock itself as a relation (the network only has it implicitly)")
    args = ap.parse_args()

    data = load_grm_network_safely(args.store, network_id=args.network)
    nodes = data["nodes_spec"]
    fixed = [n for n, s in nodes.items() if s.get("fixed")]
    seeds = set(fixed) | {n for n in args.seed if n in nodes}
    if args.data:
        seeds |= set(data["measured"])
    unknown = [n for n in args.seed if n not in nodes]
    if unknown:
        print(f"[WARN] seeds not in the network: {', '.join(unknown)}")
    relations = list(data["relations_spec"])
    if args.with_equation:
        relations.append({"name": "anthony_equation", "terms": {"S": 1, "Equant": 1, "Estock": -1}, "rhs": 0.0})
    born = generations(nodes, relations, seeds)

    by_gen = {}
    for n, (g, rel, parents) in born.items():
        by_gen.setdefault(g, []).append((n, rel, parents))
    print(f"\nseeds (generation 0): {', '.join(sorted(seeds))}\n")
    for g in sorted(by_gen):
        if g == 0:
            continue
        print(f"--- generation {g}: {len(by_gen[g])} nodes")
        for n, rel, parents in sorted(by_gen[g]):
            print(f"  {n:22s} <- {rel:28s} from {', '.join(parents)}")
    never = sorted(set(nodes) - set(born))
    print(f"\nnever born from these seeds: {len(never)} nodes" + (f" ({', '.join(never[:40])}"
                                                                + (", ..." if len(never) > 40 else "") + ")" if never else ""))
    print("\nwhere the equation's terms are born:")
    for n in WATCH:
        if n in born:
            g, rel, parents = born[n]
            print(f"  {n:10s} generation {g}" + (f"  ({rel} from {', '.join(parents)})" if g else "  (seed)"))
        elif n in nodes:
            print(f"  {n:10s} never born from these seeds")

    with open("generations.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["node", "generation", "relation", "parents"])
        for n, (g, rel, parents) in sorted(born.items(), key=lambda t: (t[1][0], t[0])):
            w.writerow([n, g, rel, " ".join(parents)])
        for n in never:
            w.writerow([n, "", "", ""])
    print("\nWrote generations.csv")


if __name__ == "__main__":
    main()
