# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Anthony Charretier
"""
Travelling salesman with the GRM only.

Method 1 - the circle (pure GRM, no move at all)
    Each city i gets a point (c_i, s_i) on the unit circle: its angle is its place in the tour.
    attraction   c_i - c_j = 0, s_i - s_j = 0   for cities close on the map (sigma = 1 / sqrt(w_ij),
                 w_ij = exp(-d_ij^2 / 2K^2)): close cities want close places
    circle       c_i^2 + s_i^2 = 1
    dispersion   sum cos(k theta_i) = 0, sum sin(k theta_i) = 0 (k = 1..H): the cities must fill the circle
    The GRM core solves the network, K is narrowed round after round (continuation), and the tour is read
    along the circle.

Method 2 - tension refinement (GRM-judged moves)
    Every edge of the tour is a relation whose residual is sqrt(d): the cost of the network, the sum of the
    squared residuals, is exactly the tour length. The tension of an edge is its length minus the distance
    from its city to its nearest neighbour. The most tense edges are treated first; a move (reversing or
    relocating a piece of tour) is kept only if the total tension of the network goes down. When nothing
    goes down any more, the most tense region is released (its cities taken out) and rebuilt city by city
    where the tension rises least; the rebuild is kept only if the network ends lower.

Usage:
    python grm_tsp.py lin318.tsp --optimum 42029 --plot
TSPLIB instances: http://comopt.ifi.uni-heidelberg.de/software/TSPLIB95/ (EUC_2D distances are rounded).
"""
import argparse
import math
import time

import numpy as np

from grm import GlobalRelationalNetwork


# ------------------------------------------------------------------ instances
def read_tsplib(path):
    """Read a TSPLIB file with EUC_2D (or CEIL_2D) coordinates. Returns (name, coords, rounding)."""
    name, kind, coords, reading = path, "EUC_2D", [], False
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line == "EOF":
                continue
            if line.startswith("NAME"):
                name = line.split(":", 1)[1].strip()
            elif line.startswith("EDGE_WEIGHT_TYPE"):
                kind = line.split(":", 1)[1].strip()
            elif line.startswith("NODE_COORD_SECTION"):
                reading = True
            elif reading:
                parts = line.split()
                if len(parts) >= 3:
                    coords.append((float(parts[1]), float(parts[2])))
    if kind not in ("EUC_2D", "CEIL_2D"):
        raise ValueError(f"unsupported EDGE_WEIGHT_TYPE {kind} (EUC_2D or CEIL_2D only)")
    return name, np.array(coords), kind


def distance_matrix(coords, kind="EUC_2D"):
    d = np.sqrt(((coords[:, None, :] - coords[None, :, :]) ** 2).sum(-1))
    return np.ceil(d) if kind == "CEIL_2D" else np.floor(d + 0.5)   # TSPLIB rounding


def tour_length(tour, dist):
    t = np.asarray(tour)
    return float(dist[t, np.roll(t, -1)].sum())


# ------------------------------------------------------------------ method 1: the circle (pure GRM)
def knn_pairs(cities, k):
    d2 = ((cities[:, None, :] - cities[None, :, :]) ** 2).sum(-1)
    np.fill_diagonal(d2, np.inf)
    near = np.argsort(d2, axis=1)[:, :k]
    pairs = {(min(i, j), max(i, j)) for i in range(len(cities)) for j in near[i]}
    return sorted(pairs), d2


def dispersion_relation(n, k, part):
    """sum over cities of cos(k theta) (part 'c') or sin(k theta) (part 's') = 0, theta = atan2(s, c)."""
    names = [f"c{i}" for i in range(n)] + [f"s{i}" for i in range(n)]

    def f(v):
        tot = 0.0
        for i in range(n):
            th = math.atan2(v[f"s{i}"], v[f"c{i}"])
            tot += math.cos(k * th) if part == "c" else math.sin(k * th)
        return tot

    def grad(v):
        g = {}
        for i in range(n):
            c, s_ = v[f"c{i}"], v[f"s{i}"]
            r2 = c * c + s_ * s_ or 1e-12
            th = math.atan2(s_, c)
            dth = -k * math.sin(k * th) if part == "c" else k * math.cos(k * th)   # d f_i / d theta
            g[f"c{i}"] = dth * (-s_ / r2)
            g[f"s{i}"] = dth * (c / r2)
        return g

    return {"name": f"spread_{part}{k}", "type": "fn", "nodes": names, "f": f, "grad": grad, "sigma": 0.3}


def grm_circle(coords, k_neighbours=8, harmonics=3, k_start=0.3, k_end=0.008, cooling=0.8, verbose=True):
    lo, span = coords.min(0), (coords.max(0) - coords.min(0)).max()
    cities = (coords - lo) / span
    n = len(cities)
    pairs, d2 = knn_pairs(cities, k_neighbours)
    centre = cities.mean(0)
    theta = np.arctan2(cities[:, 1] - centre[1], cities[:, 0] - centre[0])   # starting guess only
    values = {}
    for i in range(n):
        values[f"c{i}"], values[f"s{i}"] = math.cos(theta[i]), math.sin(theta[i])
    K, rounds = k_start, 0
    while K > k_end:
        nodes = {name: {"guess": v, "scale": "lin"} for name, v in values.items()}
        rels = [{"name": f"circle_{i}", "type": "sum", "terms": {f"c{i}": 1.0, f"s{i}": 1.0},
                 "pow": {f"c{i}": 2.0, f"s{i}": 2.0}, "K": 1.0, "sigma": 1e-3} for i in range(n)]
        for a, b in pairs:
            w = math.exp(-d2[a, b] / (2 * K * K))
            if w < 1e-8:
                continue
            sg = 1.0 / math.sqrt(w)
            rels.append({"name": f"near_c_{a}_{b}", "type": "sum", "terms": {f"c{a}": 1.0, f"c{b}": -1.0}, "K": 0.0, "sigma": sg})
            rels.append({"name": f"near_s_{a}_{b}", "type": "sum", "terms": {f"s{a}": 1.0, f"s{b}": -1.0}, "K": 0.0, "sigma": sg})
        for h in range(1, harmonics + 1):
            rels += [dispersion_relation(n, h, "c"), dispersion_relation(n, h, "s")]
        out = GlobalRelationalNetwork(nodes, rels).solve(max_iterations=12, compute_uncertainty=False)
        values = out["values"]
        rounds += 1
        K *= cooling
        if verbose:
            th = np.array([math.atan2(values[f"s{i}"], values[f"c{i}"]) for i in range(n)])
            print(f"  round {rounds:2d}  K = {K:.4f}  network cost = {out['cost']:.3g}")
    th = np.array([math.atan2(values[f"s{i}"], values[f"c{i}"]) for i in range(n)])
    return list(np.argsort(th)), rounds


def grm_circle_levels(coords, link=2.0, verbose=True):
    """Method 1 by levels: relations between groups first, then between cities.
    Groups: two cities are in the same group when they are linked by a chain of short gaps
    (each gap below `link` times the median nearest-neighbour distance). The GRM circle orders the
    group centres; inside a group, the cities follow their angle around the group centre, starting
    from the city that faces the previous group."""
    n = len(coords)
    d = np.sqrt(((coords[:, None, :] - coords[None, :, :]) ** 2).sum(-1))
    np.fill_diagonal(d, np.inf)
    limit = link * np.median(d.min(1))
    parent = list(range(n))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for i, j in zip(*np.nonzero(d < limit)):
        parent[root(i)] = root(j)
    groups = {}
    for i in range(n):
        groups.setdefault(root(i), []).append(i)
    groups = list(groups.values())
    centres = np.array([coords[g].mean(0) for g in groups])
    if len(groups) < 4:
        return grm_circle(coords, verbose=verbose)[0], len(groups)
    order, _ = grm_circle(centres, k_neighbours=min(8, len(groups) - 1), verbose=False)
    tour = []
    for q, gi in enumerate(order):
        g = np.array(groups[gi])
        c = centres[gi]
        ang = np.arctan2(coords[g, 1] - c[1], coords[g, 0] - c[0])
        seq = list(g[np.argsort(ang)])
        prev = centres[order[q - 1]]
        start = int(np.argmin(((coords[seq] - prev) ** 2).sum(1)))
        tour += seq[start:] + seq[:start]
    return tour, len(groups)


# ------------------------------------------------------------------ method 2: tension refinement
class TourNetwork:
    """The tour as a network of edge relations: residual sqrt(d) per edge, so cost = tour length."""

    def __init__(self, tour, dist, k=10):
        self.dist = dist
        self.n = len(tour)
        self.t = list(tour)
        self.pos = [0] * self.n
        for i, c in enumerate(self.t):
            self.pos[c] = i
        order = np.argsort(dist + np.diag(np.full(self.n, np.inf)), axis=1)
        self.near = [list(order[i, :k]) for i in range(self.n)]
        self.nn = [dist[i, order[i, 0]] for i in range(self.n)]

    def cost(self):
        t = self.t
        return float(sum(self.dist[t[i], t[(i + 1) % self.n]] for i in range(self.n)))

    def succ(self, c):
        return self.t[(self.pos[c] + 1) % self.n]

    def pred(self, c):
        return self.t[(self.pos[c] - 1) % self.n]

    def tension(self, c):
        """Tension of the edge leaving city c: its length beyond the nearest-neighbour distance."""
        return self.dist[c, self.succ(c)] - self.nn[c]

    def _reverse(self, i, j):          # reverse positions i..j (i <= j)
        t = self.t
        t[i:j + 1] = t[i:j + 1][::-1]
        for q in range(i, j + 1):
            self.pos[t[q]] = q

    def try_reverse(self, a):
        """Edges (a, a+) and (c, c+) become (a, c) and (a+, c+), c close to a: keep if tension drops."""
        d = self.dist
        b = self.succ(a)
        for c in self.near[a]:
            e = self.succ(c)
            if c in (a, b) or e == a:
                continue
            delta = d[a, c] + d[b, e] - d[a, b] - d[c, e]
            if delta < -1e-9:
                i, j = self.pos[b], self.pos[c]
                if i <= j:
                    self._reverse(i, j)
                else:                      # the piece wraps around: reverse the complement instead
                    self._reverse(self.pos[e], self.pos[a])
                return True
        return False

    def try_relocate(self, a):
        """Move city a between a close city c and its successor: keep if tension drops."""
        d = self.dist
        p, s = self.pred(a), self.succ(a)
        removed = d[p, a] + d[a, s] - d[p, s]
        for c in self.near[a]:
            e = self.succ(c)
            if c == a or e == a or c == p:
                continue
            for x, y in ((c, e), (self.pred(c), c)):
                if a in (x, y):
                    continue
                if d[x, a] + d[a, y] - d[x, y] - removed < -1e-9:
                    self.t.pop(self.pos[a])
                    k = self.t.index(x)
                    self.t.insert(k + 1, a)
                    for q, cc in enumerate(self.t):
                        self.pos[cc] = q
                    return True
        return False

    def try_relocate_piece(self, a, size):
        """Move the piece of `size` cities starting at a next to a close city (either direction)."""
        d, n = self.dist, self.n
        i = self.pos[a]
        piece = [self.t[(i + q) % n] for q in range(size)]
        p, s = self.t[(i - 1) % n], self.t[(i + size) % n]
        if s in piece or p in piece:
            return False
        first, last = piece[0], piece[-1]
        removed = d[p, first] + d[last, s] - d[p, s]
        inside = set(piece)
        for c in self.near[first] + self.near[last]:
            if c in inside:
                continue
            e = self.succ(c)
            if e in inside:
                continue
            fwd = d[c, first] + d[last, e] - d[c, e]
            bwd = d[c, last] + d[first, e] - d[c, e]
            best, rev = (fwd, False) if fwd <= bwd else (bwd, True)
            if best - removed < -1e-9:
                rest = [x for x in self.t if x not in inside]
                k = rest.index(c)
                self.t = rest[:k + 1] + (piece[::-1] if rev else piece) + rest[k + 1:]
                for q, cc in enumerate(self.t):
                    self.pos[cc] = q
                return True
        return False

    def settle(self):
        """Treat the most tense edges first until no move lowers the network."""
        while True:
            moved = False
            for a in sorted(range(self.n), key=self.tension, reverse=True):
                if self.tension(a) <= 0:
                    break
                if (self.try_reverse(a) or self.try_relocate(a)
                        or self.try_relocate_piece(a, 2) or self.try_relocate_piece(a, 3)):
                    moved = True
            if not moved:
                return

    def release_and_rebuild(self, size, rng):
        """Take out cities around a tense edge (drawn in proportion to tension, region of random size),
        then put them back one by one where the network tension rises least."""
        d = self.dist
        # the centre is drawn with a probability that grows with the tension of its edge
        weights = [max(self.tension(c), 0.0) + 1e-9 for c in range(self.n)]
        centre = rng.choices(range(self.n), weights=weights)[0]
        size = rng.randint(max(2, size // 2), size * 2)
        pool = self.near[centre]
        out = set([centre] + rng.sample(pool, min(size - 1, len(pool))))
        self.t = [c for c in self.t if c not in out]
        for c in sorted(out, key=lambda c: -self.nn[c]):
            r = np.array(self.t)
            nxt = np.roll(r, -1)
            rise = d[r, c] + d[c, nxt] - d[r, nxt]
            k = int(np.argmin(rise))
            self.t.insert(k + 1, c)
        for q, cc in enumerate(self.t):
            self.pos[cc] = q


def tension_refine(tour, dist, rounds=3000, size=5, seed=0, breath=1.0, verbose=True):
    """breath: how much the network may breathe, i.e. accept a rebuild that ends a little higher, as a
    share of the mean edge tension; it shrinks to zero over the rounds (0 = never accept a rise)."""
    rng = __import__("random").Random(seed)
    net = TourNetwork(tour, dist)
    net.settle()
    best_t, best = list(net.t), net.cost()
    cur_t, cur = list(net.t), best
    mean_tension = float(np.mean([max(net.tension(c), 0.0) for c in range(net.n)])) or 1.0
    for r in range(rounds):
        allowance = breath * mean_tension * (1.0 - r / rounds)
        net.release_and_rebuild(size, rng)
        net.settle()
        c = net.cost()
        if c < cur + allowance * rng.random():
            cur_t, cur = list(net.t), c       # the network breathes: keep it, even a little higher
            if c < best - 1e-9:
                best_t, best = list(net.t), c
        else:
            net.t = list(cur_t)
            for q, cc in enumerate(net.t):
                net.pos[cc] = q
        if verbose and (r + 1) % 500 == 0:
            print(f"  round {r + 1:5d}  network tension (tour length) = {best:.0f}")
    return best_t


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(description="TSP with the GRM only: the circle (method 1), tension refinement (method 2).")
    ap.add_argument("instance", help="TSPLIB file (EUC_2D)")
    ap.add_argument("--optimum", type=float, help="known optimal length, to print the gap")
    ap.add_argument("--rounds", type=int, default=3000, help="release-and-rebuild rounds of method 2")
    ap.add_argument("--breath", type=float, default=1.0, help="how much method 2 may breathe (0 = strict)")
    ap.add_argument("--plot", action="store_true", help="save a PNG of the tour (needs matplotlib)")
    args = ap.parse_args()

    name, coords, kind = read_tsplib(args.instance)
    dist = distance_matrix(coords, kind)
    gap = lambda L: f" (gap {100 * (L - args.optimum) / args.optimum:+.2f} %)" if args.optimum else ""
    print(f"{name}: {len(coords)} cities")
    t0 = time.perf_counter()
    tour1, groups = grm_circle_levels(coords)
    t1 = time.perf_counter() - t0
    L1 = tour_length(tour1, dist)
    print(f"method 1, GRM circle by levels  : {L1:10.0f}{gap(L1)}   {groups} groups, {t1:.1f} s")
    t0 = time.perf_counter()
    tour2 = tension_refine(tour1, dist, rounds=args.rounds, breath=args.breath)
    L2 = tour_length(tour2, dist)
    print(f"method 2, tension refinement    : {L2:10.0f}{gap(L2)}   {time.perf_counter() - t0:.1f} s")
    assert sorted(tour2) == list(range(len(coords)))      # every city exactly once
    if args.plot:
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(1, 2, figsize=(16, 8))
        for ax, t, title in ((axes[0], tour1, f"method 1 (circle by levels): {L1:.0f}{gap(L1)}"),
                             (axes[1], tour2, f"method 2 (tension): {L2:.0f}{gap(L2)}")):
            r = list(t) + [t[0]]
            ax.plot(coords[r, 0], coords[r, 1], color="teal", lw=0.9)
            ax.scatter(coords[:, 0], coords[:, 1], s=8, color="darkred", zorder=5)
            ax.set_title(f"{name} - {title}")
            ax.set_aspect("equal")
        out = f"grm_tsp_{name}.png"
        fig.savefig(out, dpi=150, bbox_inches="tight")
        print(f"saved {out}")


if __name__ == "__main__":
    main()
