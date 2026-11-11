# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Anthony Charretier
"""The same network solved by two kinds of machine, with what each one costs counted.

The network, for both: every node is solved in log10; every relation sum_i p_i x_i = b, every measurement x = m and
a very weak prior on every free node (the same ridge as pygrm) is a factor with a weight 1 / sigma^2. The answer
is the weighted least-squares one, the same as pygrm's.

The relational machine (RelationalMachine). No shared memory and no global step: every node and every relation is
its own small processor with its own memory, linked only to its neighbours. They exchange messages made of two
numbers (a precision and a mean). In each round, all at once:
  - a node tells each of its relations what all its OTHER relations say of it (precisions add up);
  - a relation tells each of its nodes what it would be if the relation held, given what its other nodes said,
    with a precision: 1 / (its own sigma^2 + the sum of what its other nodes are unsure of).
This is Gaussian belief propagation on the network's factor graph. On a network without loops it gives the exact
answer after as many rounds as the network is wide. With loops it usually settles on the exact values too (random
networks: within 1e-11 dex), but not always: where loops of exact relations say the same thing twice, it counts
some information twice and settles a little away (the grm-core store network: 0.035 sigma at most, on one group of
nodes). Its uncertainties are not reliable on loops: for those, ask pygrm. A relation never needs more than its own
nodes' messages: a relation of k nodes costs about 12 k operations, whatever the size of the network.

(A first version used consensus ADMM, the textbook way to split a least-squares problem among processors. With
weights from 1e-6 to 1e18 in the same network, it was still 1e5 sigma away after 100 000 rounds: it is left out.)

The classic machine (ClassicMachine). One core and a shared memory: the whole weighted system written in memory
as a dense matrix, then a Householder QR factorization and a back substitution, the way pygrm solves it. Every
arithmetic operation and every read or write of the matrix is counted (the arithmetic itself is done by NumPy, the
counts are those of the loop a single core would run).

Costs (cycles), one model for all: an operation takes `op` cycles; on the classic machine a memory access takes
`cache` cycles when it hits the cache and `ram` when it misses (a share `hit` hits); on the relational machine each
processor's memory is inside it, and a message to a neighbour takes `link` cycles. It is a model, not a measured
chip: every parameter can be changed.
"""
import math
import time

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None


class Problem:
    """The network as factors on the log10 values of its free nodes."""

    PRIOR_SIGMA = 1e3
    # The tightest relation, in dex: a relation said "exact" (1e-9) is held at 1e-6, as tight as a solve in double
    # precision can tell from exact next to measurements of a few percent.
    MIN_SIGMA = 1e-6

    def __init__(self, net):
        if any(r.get("kind", "product") != "product" for r in net.relations) or any(
                s.get("signed") for s in net.nodes.values()):
            raise ValueError("the benchmark machines take product networks (positive nodes, product relations)")
        self.names = [n for n, s in net.nodes.items() if not s["fixed"]]
        self.index = {n: k for k, n in enumerate(self.names)}
        self.fixed = {n: math.log10(s["guess"]) for n, s in net.nodes.items() if s["fixed"]}
        self.x0 = [math.log10(net.nodes[n]["guess"]) for n in self.names]
        self.factors = []      # (label, [(node index, power)], b, weight, kind)
        for r in net.relations:
            vars_, b = [], r["rhs"]
            for n, p in r["terms"].items():
                if n in self.index:
                    vars_.append((self.index[n], p))
                else:
                    b -= p * self.fixed[n]
            if vars_:
                self.factors.append((r["name"], vars_, b, 1.0 / max(r["sigma"], self.MIN_SIGMA) ** 2, "relation"))
        for n, (v, s) in net.measured.items():
            if n in self.index:
                self.factors.append((f"measured {n}", [(self.index[n], 1.0)], math.log10(v), 1.0 / s ** 2, "measure"))
        for k, n in enumerate(self.names):
            self.factors.append((f"prior {n}", [(k, 1.0)], self.x0[k], 1.0 / self.PRIOR_SIGMA ** 2, "prior"))
        self.node_factors = [[] for _ in self.names]
        for f, (_, vars_, _, _, _) in enumerate(self.factors):
            for slot, (i, _) in enumerate(vars_):
                self.node_factors[i].append((f, slot))
        self.edges = sum(len(v) for (_, v, _, _, _) in self.factors)

    def tension(self, x, f):
        """How far factor f is from holding, in its own sigmas (signed)."""
        _, vars_, b, w, _ = self.factors[f]
        return (sum(c * x[i] for i, c in vars_) - b) * math.sqrt(w)

    def cost(self, x):
        return sum(self.tension(x, f) ** 2 for f in range(len(self.factors)))


class Costs:
    def __init__(self, op=1.0, cache=4.0, ram=100.0, hit=0.9, link=10.0):
        self.op, self.cache, self.ram, self.hit, self.link = op, cache, ram, hit, link

    def access(self):
        return self.hit * self.cache + (1.0 - self.hit) * self.ram

    def __str__(self):
        return f"op {self.op:g}, cache {self.cache:g}, ram {self.ram:g}, hit {self.hit:g}, link {self.link:g} (cycles)"


def _others(values):
    """For each item, the sum of all the others (prefix and suffix sums: no subtraction, so a precision of 1e18
    next to one of 1 loses nothing)."""
    n = len(values)
    pre = [0.0] * (n + 1)
    for k in range(n):
        pre[k + 1] = pre[k] + values[k]
    out, suf = [0.0] * n, 0.0
    for k in range(n - 1, -1, -1):
        out[k] = pre[k] + suf
        suf += values[k]
    return out


class RelationalMachine:
    """Every node and relation a processor; rounds of messages between neighbours (Gaussian belief propagation)."""

    def __init__(self, problem):
        self.p = P = problem
        # relation -> node messages: precision and precision * mean, one per edge (kept by the relation that sends it)
        self.lam = [[0.0] * len(v) for (_, v, _, _, _) in P.factors]
        self.eta = [[0.0] * len(v) for (_, v, _, _, _) in P.factors]
        self.x = list(P.x0)
        self.precision = [0.0] * len(P.names)
        self.last_move = [0.0] * len(P.names)
        self.rounds = 0
        self.messages = 0
        self.ops = 0
        # the slowest processor of each kind sets the pace of a round
        self.max_factor_ops = max((self.factor_ops(len(v)) for (_, v, _, _, _) in P.factors), default=0)
        self.max_node_ops = max((self.node_ops(len(nf)) for nf in P.node_factors), default=0)
        self.wall = 0.0
        self.settled = False

    @staticmethod
    def factor_ops(k):
        return 12 * k + 4

    @staticmethod
    def node_ops(d):
        return 8 * d + 3

    def round(self):
        P = self.p
        F = P.factors
        to_lam = [[0.0] * len(v) for (_, v, _, _, _) in F]
        to_eta = [[0.0] * len(v) for (_, v, _, _, _) in F]
        moved = 0.0
        # 1) every node, at once: to each of its relations, what all its other relations say (two numbers)
        for i, nf in enumerate(P.node_factors):
            lams = [self.lam[f][s] for f, s in nf]
            etas = [self.eta[f][s] for f, s in nf]
            ol, oe = _others(lams), _others(etas)
            for k, (f, s) in enumerate(nf):
                to_lam[f][s] = ol[k]
                to_eta[f][s] = oe[k]
            total = sum(lams)
            if total > 0:
                new = sum(etas) / total
                self.last_move[i] = abs(new - self.x[i])
                moved = max(moved, self.last_move[i])
                self.x[i] = new
            self.precision[i] = total
            self.ops += self.node_ops(len(nf))
            self.messages += len(nf)
        # 2) every relation, at once: to each of its nodes, what it would be if the relation held
        for f, (_, v, b, w, _) in enumerate(F):
            var, mean = [], []
            for s, (i, c) in enumerate(v):
                d = to_lam[f][s]
                if d > 0:
                    var.append(c * c / d)
                    mean.append(c * to_eta[f][s] / d)
                else:
                    var.append(math.inf)
                    mean.append(0.0)
            ov, om = _others(var), _others(mean)
            for s, (i, c) in enumerate(v):
                total = 1.0 / w + ov[s]
                if math.isinf(total):
                    self.lam[f][s] = self.eta[f][s] = 0.0
                else:
                    lam = c * c / total
                    self.lam[f][s] = lam
                    self.eta[f][s] = lam * (b - om[s]) / c
            self.ops += self.factor_ops(len(v))
            self.messages += len(v)
        self.rounds += 1
        return moved

    def run(self, tol=1e-6, floor=1e-7, max_rounds=5000, every=None, callback=None, settle=3, patience=20):
        """Rounds until the network has settled, then stops. Settled: for `settle` rounds in a row, every node moves
        by less than `tol` of its own uncertainty (as the messages give it); or every node moves by less than
        `floor` dex and the moves have stopped shrinking for `patience` rounds (around a loop of exact relations
        the values jitter by about 1e-9 dex: the rounding of relations held at 1e-6). callback(machine, moved)
        every `every` rounds and at the end; returning False stops."""
        t0 = time.perf_counter()
        quiet = 0
        best, since = math.inf, 0
        moved = math.inf
        stop = max_rounds + self.rounds
        self.settled = False
        while self.rounds < stop:
            moved = self.round()
            if self.rounds > 1:
                rel = max((mv * math.sqrt(p) for mv, p in zip(self.last_move, self.precision)), default=0.0)
                quiet = quiet + 1 if rel < tol else 0
                if moved < best * 0.5:
                    best, since = moved, 0
                else:
                    since += 1
            if callback and every and self.rounds % every == 0:
                if callback(self, moved) is False:
                    break
            if quiet >= settle or (moved < floor and since >= patience):
                self.settled = True
                break
        self.wall += time.perf_counter() - t0
        if callback:
            callback(self, moved)
        return self.settled

    def round_cycles(self, costs):
        """A round: the slowest node, a message, the slowest relation, a message."""
        return (self.max_factor_ops + self.max_node_ops) * costs.op + 2.0 * costs.link

    def cycles(self, costs):
        return self.rounds * self.round_cycles(costs)

    def sequential_cycles(self, costs):
        """The same rounds run by one core with a shared memory: every operation one after the other, and every
        message written to memory and read back (two numbers each way)."""
        return self.ops * costs.op + self.messages * 4 * costs.access()

    def processors(self):
        return len(self.p.factors) + len(self.p.names)


class ClassicMachine:
    """One core, a shared memory, a dense matrix: Householder QR of the weighted system, then back substitution."""

    def __init__(self, problem):
        self.p = problem
        self.ops = 0
        self.accesses = 0
        self.wall = 0.0
        self.bytes = 0

    def matrix(self):
        P = self.p
        m, n = len(P.factors), len(P.names)
        A = np.zeros((m, n + 1))
        for f, (_, vars_, b, w, _) in enumerate(P.factors):
            sw = math.sqrt(w)
            for i, c in vars_:
                A[f, i] += c * sw
            A[f, n] = b * sw
        return A

    def solve(self):
        if np is None:
            raise RuntimeError("the classic machine needs NumPy")
        t0 = time.perf_counter()
        A = self.matrix()
        m, n = A.shape[0], A.shape[1] - 1
        # writing the matrix: every cell once (zeros included: a dense matrix)
        ops = 2 * self.p.edges
        acc = m * (n + 1)
        for k in range(n):
            rows = m - k
            col = A[k:, k].copy()
            norm = math.sqrt(float(col @ col))
            ops += 2 * rows + 1
            acc += rows
            if norm == 0.0:
                raise ArithmeticError("a direction nothing holds")
            alpha = -norm if col[0] >= 0 else norm
            col[0] -= alpha
            vv = float(col @ col)
            ops += 2 * rows + 1
            if vv == 0.0:
                continue
            # every column on the right (and the right-hand side): a dot product, then an update in place
            cols = n + 1 - k
            s = (col @ A[k:, k:]) * (2.0 / vv)
            A[k:, k:] -= np.outer(col, s)
            ops += cols * (4 * rows + 1)
            acc += cols * (3 * rows)           # read for the dot, read and write for the update
        # back substitution on the n x n triangle
        x = np.zeros(n)
        for i in range(n - 1, -1, -1):
            x[i] = (A[i, n] - A[i, i + 1:n] @ x[i + 1:]) / A[i, i]
            ops += 2 * (n - 1 - i) + 2
            acc += 2 * (n - 1 - i) + 3
        self.ops, self.accesses = ops, acc
        self.x = [float(v) for v in x]
        self.bytes = m * (n + 1) * 8
        self.wall = time.perf_counter() - t0
        return self.x

    def cycles(self, costs):
        return self.ops * costs.op + self.accesses * costs.access()
