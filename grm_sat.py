# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Anthony Charretier
"""
Random 3-SAT solved by the GRM core (pygrm).

A 3-SAT formula is a set of clauses (a OR not-b OR c ...). Here each variable is a GRM node and each
clause is a relation that must equal zero:

    variable    a positive node o_i (odds); its truth value is v_i = o_i / (1 + o_i), always in (0, 1)
    literal     l = v (plain) or 1 - v (negated)
    clause      r = (1 - l_1) (1 - l_2) (1 - l_3) = 0        zero as soon as one literal is true

The network is solved by the GRM engine (least squares, Levenberg-Marquardt), then rounded:
true if v >= 0.5. Every assignment is checked clause by clause. A classical WalkSAT is included as a
baseline, so the GRM result can be compared with a standard method on the same formulas.

Usage:
    python grm_sat.py                         # alpha = 3.11, sizes 20 .. 500
    python grm_sat.py --alpha 4.2 --sizes 50 100 200 --trials 5
    python grm_sat.py --dimacs formula.cnf    # solve a DIMACS file
"""
import argparse
import math
import random
import time

from pygrm import GlobalRelationalNetwork

CLAUSE_SIGMA = 1e-2


# ------------------------------------------------------------------ formulas
def random_3sat(n, alpha, seed):
    """M = round(alpha * n) clauses, three distinct variables each, random signs (like the C++ test)."""
    rng = random.Random(seed)
    clauses = []
    for _ in range(int(round(alpha * n))):
        vs = rng.sample(range(n), 3)
        clauses.append([(v, rng.random() < 0.5) for v in vs])   # (variable, plain literal?)
    return clauses


def read_dimacs(path):
    clauses, n = [], 0
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line[0] in "c%":
                continue
            if line.startswith("p"):
                n = int(line.split()[2])
                continue
            lits = [int(t) for t in line.split() if t != "0"]
            if lits:
                clauses.append([(abs(l) - 1, l > 0) for l in lits])
    return n, clauses


def write_dimacs(path, n, clauses):
    with open(path, "w") as f:
        f.write(f"p cnf {n} {len(clauses)}\n")
        for c in clauses:
            f.write(" ".join(str(v + 1 if s else -(v + 1)) for v, s in c) + " 0\n")


def count_satisfied(clauses, assignment):
    return sum(any(assignment[v] == s for v, s in c) for c in clauses)


# ------------------------------------------------------------------ GRM network
def clause_relation(k, clause):
    names = [f"o{v}" for v, _ in clause]
    signs = [s for _, s in clause]

    def literals(val):
        out = []
        for name, plain in zip(names, signs):
            v = val[name] / (1.0 + val[name])
            out.append(v if plain else 1.0 - v)
        return out

    def f(val):
        l = literals(val)
        r = 1.0
        for x in l:
            r *= 1.0 - x
        return r

    def grad(val):
        l = literals(val)
        g = {}
        for j, (name, plain) in enumerate(zip(names, signs)):
            other = 1.0
            for q in range(len(l)):
                if q != j:
                    other *= 1.0 - l[q]
            dr_dl = -other
            o = val[name]
            t = 1.0 / (1.0 + o)                                  # = 1 - v, no overflow for huge odds
            dl_do = (1.0 if plain else -1.0) * t * t             # dv/do = 1 / (1 + o)^2
            g[name] = g.get(name, 0.0) + dr_dl * dl_do
        return g

    return {"name": f"clause_{k}", "type": "fn", "nodes": names, "f": f, "grad": grad, "sigma": CLAUSE_SIGMA}


def grm_solve(n, clauses, restarts=1, seed=0, max_iterations=50):
    rels = [clause_relation(k, c) for k, c in enumerate(clauses)]
    rng = random.Random(seed)
    best, best_sat = None, -1
    for _ in range(restarts):
        # start near v = 0.5 (+-0.1), as in the C++ version: odds between 0.67 and 1.5
        nodes = {f"o{i}": {"guess": 10 ** rng.uniform(-0.176, 0.176)} for i in range(n)}
        out = GlobalRelationalNetwork(nodes, rels).solve(max_iterations=max_iterations, compute_uncertainty=False)
        assignment = [out["values"][f"o{i}"] >= 1.0 for i in range(n)]
        sat = count_satisfied(clauses, assignment)
        if sat > best_sat:
            best, best_sat = assignment, sat
        if best_sat == len(clauses):
            break
    return best, best_sat


def binarity_relation(i, sigma):
    """v (1 - v) = 0: the variable is pushed towards true or false (continuous against discrete)."""
    name = f"o{i}"

    def f(val):
        v = val[name] / (1.0 + val[name])
        return v * (1.0 - v)

    def grad(val):
        o = val[name]
        t = 1.0 / (1.0 + o)            # 1 - v
        v = 1.0 - t
        return {name: (1.0 - 2.0 * v) * t * t}

    return {"name": f"binary_{i}", "type": "fn", "nodes": [name], "f": f, "grad": grad, "sigma": sigma}


def grm_plus_solve(n, clauses, rounds=40, seed=0, sigma_bin_start=10.0, sigma_bin_end=0.02,
                   tighten=0.75, reweight=1.6, iterations_per_round=25):
    """GRM with two tensions added between solves (each solve starts where the previous one ended):
      - continuation: the binarity relations start very loose, then are tightened round after round,
        so the network first explores freely, then has to choose true or false;
      - reweighting: every clause still false after a round weighs more in the next one."""
    rng = random.Random(seed)
    rels = [clause_relation(k, c) for k, c in enumerate(clauses)]
    rels += [binarity_relation(i, sigma_bin_start) for i in range(n)]
    nodes = {f"o{i}": {"guess": 10 ** rng.uniform(-0.176, 0.176)} for i in range(n)}
    net = GlobalRelationalNetwork(nodes, rels)
    start, sigma_bin = None, sigma_bin_start
    best, best_sat = None, -1
    for _ in range(rounds):
        out = net.solve(start=start, max_iterations=iterations_per_round, compute_uncertainty=False)
        start = out["values"]
        assignment = [start[f"o{i}"] >= 1.0 for i in range(n)]
        sat = count_satisfied(clauses, assignment)
        if sat > best_sat:
            best, best_sat = assignment, sat
        if sat == len(clauses):
            break
        for k, c in enumerate(clauses):
            if not any(assignment[v] == sg for v, sg in c):
                net.set_sigma(f"clause_{k}", net.get_sigma(f"clause_{k}") / reweight)
        sigma_bin = max(sigma_bin * tighten, sigma_bin_end)
        for i in range(n):
            net.set_sigma(f"binary_{i}", sigma_bin)
        # keep values strictly inside (0, 1) so that a variable can still change side
        start = {k: min(max(v, 1e-6), 1e6) for k, v in start.items()}
    return best, best_sat


# ------------------------------------------------------------------ classical baseline
def walksat(n, clauses, max_flips=200000, p_noise=0.5, seed=0, init=None):
    rng = random.Random(seed)
    a = list(init) if init is not None else [rng.random() < 0.5 for _ in range(n)]
    occ = [[] for _ in range(n)]
    for k, c in enumerate(clauses):
        for v, _ in c:
            occ[v].append(k)
    true_count = [sum(a[v] == s for v, s in c) for c in clauses]
    unsat = {k for k, t in enumerate(true_count) if t == 0}
    for _ in range(max_flips):
        if not unsat:
            break
        k = rng.choice(tuple(unsat))
        c = clauses[k]

        def breaks(v):
            return sum(1 for q in occ[v] if true_count[q] == 1 and any(w == v and a[w] == s for w, s in clauses[q]))
        if rng.random() < p_noise:
            v = rng.choice(c)[0]
        else:
            v = min((w for w, _ in c), key=breaks)
        a[v] = not a[v]
        for q in occ[v]:
            for w, s in clauses[q]:
                if w == v:
                    true_count[q] += 1 if a[v] == s else -1
            if true_count[q] == 0:
                unsat.add(q)
            else:
                unsat.discard(q)
    return a, len(clauses) - len(unsat)


def satisfiable(n, clauses):
    """Exact answer from MiniSat (pip install python-sat), or None if it is not installed."""
    try:
        from pysat.solvers import Minisat22
    except ImportError:
        return None
    with Minisat22(bootstrap_with=[[v + 1 if sg else -(v + 1) for v, sg in c] for c in clauses]) as solver:
        return solver.solve()


def compare(args):
    """On satisfiable formulas only (checked by MiniSat): GRM, GRM+, WalkSAT, and GRM+ then WalkSAT."""
    print(f"Satisfiable formulas only (MiniSat), alpha = {args.alpha}, WalkSAT budget {args.flips} flips")
    for n in args.sizes:
        formulas, t = [], 0
        while len(formulas) < args.trials:
            c = random_3sat(n, args.alpha, args.seed + 1000 * n + t)
            t += 1
            ok = satisfiable(n, c)
            if ok is None:
                raise SystemExit("compare needs MiniSat: pip install python-sat")
            if ok:
                formulas.append(c)
        rejected = t - len(formulas)
        score = {k: [0, 0.0] for k in ("GRM", "GRM+", "WalkSAT", "GRM+ then WalkSAT")}
        for j, c in enumerate(formulas):
            m = len(c)
            t0 = time.perf_counter(); _, sat = grm_solve(n, c, args.restarts, seed=j); dt = time.perf_counter() - t0
            score["GRM"][0] += sat == m; score["GRM"][1] += dt
            t0 = time.perf_counter(); a, sat = grm_plus_solve(n, c, seed=j); dt = time.perf_counter() - t0
            score["GRM+"][0] += sat == m; score["GRM+"][1] += dt
            t1 = time.perf_counter(); _, sat2 = walksat(n, c, max_flips=args.flips, seed=j, init=a)
            score["GRM+ then WalkSAT"][0] += sat2 == m; score["GRM+ then WalkSAT"][1] += dt + time.perf_counter() - t1
            t0 = time.perf_counter(); _, sat = walksat(n, c, max_flips=args.flips, seed=j); dt = time.perf_counter() - t0
            score["WalkSAT"][0] += sat == m; score["WalkSAT"][1] += dt
        k = len(formulas)
        cells = " | ".join(f"{name}: {v[0]}/{k} ({v[1] / k:.2f} s)" for name, v in score.items())
        print(f"N = {n:4d} M = {len(formulas[0]):4d} ({rejected} unsatisfiable skipped) | {cells}")


# ------------------------------------------------------------------ report
def main():
    ap = argparse.ArgumentParser(description="Random 3-SAT solved by the GRM core, with a WalkSAT baseline.")
    ap.add_argument("--alpha", type=float, default=3.11, help="clauses per variable (hard region near 4.2)")
    ap.add_argument("--sizes", type=int, nargs="+", default=[20, 50, 100, 200, 300, 500])
    ap.add_argument("--trials", type=int, default=1)
    ap.add_argument("--restarts", type=int, default=1)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--dimacs", help="solve this DIMACS file instead of random formulas")
    ap.add_argument("--export", action="store_true", help="write each random formula and its GRM assignment")
    ap.add_argument("--compare", action="store_true",
                    help="satisfiable formulas only: GRM, GRM+ (continuation + reweighting), WalkSAT, hybrid")
    ap.add_argument("--flips", type=int, default=20000, help="WalkSAT flip budget in --compare")
    args = ap.parse_args()
    if args.compare:
        compare(args)
        return

    print("=" * 78)
    print(f"  RANDOM 3-SAT — GRM core (pygrm) vs WalkSAT    alpha = {args.alpha}")
    print("=" * 78)
    jobs = []
    if args.dimacs:
        n, clauses = read_dimacs(args.dimacs)
        jobs.append((n, [clauses]))
    else:
        for n in args.sizes:
            jobs.append((n, [random_3sat(n, args.alpha, args.seed + 1000 * n + t) for t in range(args.trials)]))

    for n, formulas in jobs:
        g_perfect = w_perfect = g_sat = total = 0
        g_time = w_time = 0.0
        for t, clauses in enumerate(formulas):
            m = len(clauses)
            t0 = time.perf_counter()
            assignment, sat = grm_solve(n, clauses, args.restarts, seed=args.seed + t)
            g_time += time.perf_counter() - t0
            assert sat == count_satisfied(clauses, assignment)   # checked clause by clause
            g_sat += sat
            total += m
            g_perfect += sat == m
            t0 = time.perf_counter()
            _, wsat = walksat(n, clauses, seed=args.seed + t)
            w_time += time.perf_counter() - t0
            w_perfect += wsat == m
            if args.export:
                write_dimacs(f"instance_N{n}_t{t}.cnf", n, clauses)
                with open(f"assignment_N{n}_t{t}.sol", "w") as f:
                    f.write("c GRM assignment\n" + "".join(f"{i + 1} {int(b)}\n" for i, b in enumerate(assignment)))
        k = len(formulas)
        print(f"N = {n:5d}  M = {len(formulas[0]):5d} | GRM: all clauses {g_perfect}/{k}, "
              f"clauses {100 * g_sat / total:7.3f} %, {g_time / k:7.2f} s | WalkSAT: all clauses {w_perfect}/{k}, "
              f"{w_time / k:6.2f} s")


if __name__ == "__main__":
    main()
