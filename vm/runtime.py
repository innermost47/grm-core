# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Anthony Charretier
"""The relational machine that runs programs: every node and every relation a small processor that only talks to
its neighbours, and that only works when one of its neighbours has something new to say.

What it runs (language.py): product relations (straight in log), sum relations (straight on signed values: sums of
exponents, e^x1 = e^x0 * (e^v)^dt), the converters between the two worlds (~g = g, redrawn around the current value
by the converter itself), contacts (`keep y >= 2 when x in 3 .. 8`: a contact decides by itself, from what its
node's other relations say of it and from the nodes it watches, whether it pushes), and measurements.

A message is two numbers, a precision and a mean (Gaussian belief propagation). A round: the nodes that received
something new tell each of their relations what the others say; the relations that received something new answer
each of their nodes. A processor that hears nothing new does nothing: a network whose measurements do not change
falls silent, and a change wakes only what it reaches.

Memory: `sleep` writes the network and the state of every processor (every value and every message) to a JSON
file; `wake` puts them back and the network goes on from where it stopped, without solving anything again. The
network is the program, its memory and its calculator at once.
"""
import json
import math

try:
    import numpy as _np
except ImportError:  # pragma: no cover
    _np = None
try:
    from pygrm import units as _units
except ImportError:  # pragma: no cover - without pygrm the machine counts in SI
    _units = None

UNITS = "ticks"           # inside, the machine counts in its own units: c = hbar = G = kB = 1 (pygrm.units)

from i18n import tr
from language import Network, TalkError

LN10 = math.log(10.0)
MIN_SIGMA = 1e-6          # the tightest relation a double-precision machine tells from exact (dex or the unit)
PRIOR_LOG = 1e3           # weak anchor of an unmeasured positive node (dex)
PRIOR_SIGNED = 1e6        # weak anchor of an unmeasured signed node (its unit)
CONVERTER_SIGMA = 1e-9    # relative tightness of a converter
DAMPING = 0.5             # a relation that sees its answers swing back and forth keeps this share of its last one:
SWINGS = 4                # around loops of exact relations that say the same thing twice, undamped messages can
                          # swing further each time round and blow up; after SWINGS reversals a relation calms down
QUIET = 1e-10             # a mean that moves less than this (dex, or the node's unit) is not news (the relations
                          # themselves are held to 1e-6)
QUIET_PRECISION = 1e-6    # a precision that changes less than this (relative) is not news: around a loop of exact
                          # relations that say the same thing twice, precisions grow for ever while means stand still


def _others(values):
    n = len(values)
    pre = [0.0] * (n + 1)
    for k in range(n):
        pre[k + 1] = pre[k] + values[k]
    out, suf = [0.0] * n, 0.0
    for k in range(n - 1, -1, -1):
        out[k] = pre[k] + suf
        suf += values[k]
    return out


class Factor:
    """A relation, a measurement, a converter or a contact: a linear relation sum_s c_s u_s = b on the internal
    values u of its nodes (log10 for a positive node, the value itself for a signed one), with weight w = 1/sigma^2.
    Converters and contacts redraw (c, b, w) themselves."""

    __slots__ = ("name", "kind", "vars", "coef", "b", "w", "out_lam", "out_eta", "in_lam", "in_eta", "watch",
                 "bound", "op", "active", "text", "damp", "swing", "trend", "terms", "L", "h")

    def __init__(self, name, kind, vars_, coef, b, w, text=""):
        self.name, self.kind, self.vars, self.coef, self.b, self.w = name, kind, list(vars_), list(coef), b, w
        k = len(self.vars)
        self.out_lam, self.out_eta = [0.0] * k, [0.0] * k
        self.in_lam, self.in_eta = [0.0] * k, [0.0] * k
        self.watch = []          # (node index, lo, hi): contact conditions
        self.bound, self.op, self.active = 0.0, ">=", False
        self.text = text
        self.damp, self.swing, self.trend = 0.0, 0, [0.0] * k
        self.terms = None        # a nonlinear sum: [(coef, [(slot, power)])]
        self.L, self.h = None, None  # the memory of weights learned together: information matrix and vector


class Machine:
    def __init__(self, net):
        self.net = net
        self.compile()

    # ------------------------------------------------------------------ building the processors
    def compile(self):
        net = self.net
        self.names = [n for n, s in net.nodes.items() if not s["fixed"]]
        self.signed = {}
        self.fixed = {}
        # a node with a dimension is given in SI and counted inside in the machine's units. For a positive node (in
        # log) the unit is a shift; for a signed one, a scale (its value divided by 10^shift). Uncertainties follow:
        # relative for a positive node, in its own unit for a signed one, never tighter than a millionth of an SI unit
        self.shift = {}
        for n, s in net.nodes.items():
            if s.get("dim") and _units is not None:
                self.shift[n] = _units.unit_log10(s["dim"], UNITS)
        for n, s in net.nodes.items():
            if s["fixed"]:
                if not s.get("signed") and s["guess"] <= 0:
                    raise TalkError(tr("fixed node {n} must be positive (or signed)", n=n))
                self.fixed[n] = s["guess"] / 10 ** self.shift.get(n, 0.0)
        self.index = {}
        self.var_names, self.var_signed, self.start = [], [], []
        for n in self.names:
            self.add_var(n, bool(net.nodes[n].get("signed")))
        self.factors = []
        self.anchor = {}
        twins = {}

        def twin(q):
            """The signed twin of a positive node: ~q = q, tied by a converter."""
            if q in twins:
                return twins[q]
            t = "~" + q
            self.add_var(t, True)
            f = Factor(f"convert {q}", "convert", [self.index[t], self.index[q]], [1.0, 0.0], 0.0, 1.0,
                       f"{t} = {q}")
            self.factors.append(f)
            twins[q] = self.index[t]
            return twins[q]

        def watch(f, conds):
            for wn, lo, hi in conds or ():
                if wn in self.index:
                    f.watch.append((self.index[wn], lo, hi))
                elif not (lo <= self.fixed[wn] <= hi):
                    f.watch.append((-1, 1.0, 0.0))     # a fixed condition that never holds
            return f

        for r in net.relations:
            kind = r.get("kind", "product")
            if kind == "product":
                vars_, coef, b = [], [], r["rhs"]
                for n, p in r["terms"].items():
                    if n in self.index:
                        vars_.append(self.index[n])
                        coef.append(p)
                    else:
                        b -= p * math.log10(self.fixed[n])
                if vars_:
                    self.factors.append(watch(Factor(r["name"], "relation", vars_, coef, b,
                                                     1.0 / max(r["sigma"], MIN_SIGMA) ** 2, r["text"]), r.get("when")))
            elif kind == "sum" and self.nonlinear_sum(r):
                # a term with two free nodes (k * x) or a power: the relation redraws itself around the current values
                vars_, terms, b = [], [], 0.0
                for c, t in r["terms"]:
                    k, parts = c, []
                    for n, p in t.items():
                        if n in self.index:
                            i = self.index[n]
                            if i not in vars_:
                                vars_.append(i)
                            parts.append((vars_.index(i), p))
                        else:
                            k *= self.fixed[n] ** p
                    if parts:
                        terms.append((k, parts))
                    else:
                        b -= k
                f = Factor(r["name"], "nonlinear", vars_, [0.0] * len(vars_), b,
                           1.0 / (max(r["sigma"], MIN_SIGMA) / self.unit_of(r)) ** 2, r["text"])
                f.terms = terms
                self.factors.append(watch(f, r.get("when")))
            elif kind == "sum":
                vars_, coef, b = [], [], 0.0
                for c, t in r["terms"]:
                    free = [n for n in t if n in self.index]
                    k = c
                    for n, p in t.items():
                        if n not in self.index:
                            k *= self.fixed[n] ** p
                    if not free:
                        b -= k
                        continue
                    if len(free) > 1 or abs(t[free[0]] - 1.0) > 1e-12:
                        raise TalkError(tr("relation {name}: a term of a sum holds one free node, to the power 1 (give "
                                           "a product its own node: relate p: p = a * b)", name=r["name"]))
                    n = free[0]
                    i = self.index[n] if self.is_signed(self.index[n]) else twin(n)
                    if i in vars_:
                        coef[vars_.index(i)] += k
                    else:
                        vars_.append(i)
                        coef.append(k)
                if vars_:
                    self.factors.append(watch(Factor(r["name"], "relation", vars_, coef, b,
                                                     1.0 / (max(r["sigma"], MIN_SIGMA) / self.unit_of(r)) ** 2,
                                                     r["text"]), r.get("when")))
            elif kind == "log":
                # L = ln(y): in the machine, y is held by its log10 (u), so L = ln10 (u + shift): a straight relation
                L, y = r["log"], r["node"]
                vars_, coef, b = [], [], 0.0
                if L in self.index:
                    vars_.append(self.index[L])
                    coef.append(1.0)
                else:
                    b -= self.fixed[L]
                if y in self.index:
                    vars_.append(self.index[y])
                    coef.append(-LN10)
                    b += LN10 * self.shift.get(y, 0.0)
                else:
                    b += math.log(self.fixed[y] * 10 ** self.shift.get(y, 0.0))
                if vars_:
                    self.factors.append(Factor(r["name"], "relation", vars_, coef, b, 1.0 / MIN_SIGMA ** 2,
                                               r["text"]))
            elif kind == "keep":
                n = r["node"]
                if n not in self.index:
                    continue
                f = Factor(r["name"], "keep", [self.index[n]], [1.0], 0.0, 0.0, r["text"])
                i = self.index[n]
                k = self.shift.get(n, 0.0)
                f.bound = r["bound"] / 10 ** k if self.is_signed(i) else math.log10(r["bound"]) - k
                f.op = r["op"]
                self.factors.append(watch(f, r["when"]))
        # the weights (`learn`) learn together: weights that share a relation keep one memory of what they know,
        # their links included (an information matrix), instead of each one alone
        self.joints = []
        for names in self.weight_groups():
            f = Factor("weights " + " ".join(names), "joint", [self.index[n] for n in names], [0.0] * len(names),
                       0.0, 0.0, "what " + ", ".join(names) + " have learned")
            f.L, f.h = self.link_memory(names)
            self.joints.append(f)
            self.factors.append(f)
        # one anchor per free node: its measurement, or a weak prior at its start
        for n in self.names:
            i = self.index[n]
            f = Factor(f"anchor {n}", "anchor", [i], [1.0], 0.0, 0.0)
            self.anchor[n] = f
            self.factors.append(f)
            self.set_anchor(n)
        self.node_factors = [[] for _ in self.var_names]
        self.watchers = [[] for _ in self.var_names]
        for fi, f in enumerate(self.factors):
            for s, i in enumerate(f.vars):
                self.node_factors[i].append((fi, s))
            for i, _, _ in f.watch:
                if i >= 0:
                    self.watchers[i].append(fi)
        self._anchor_index = {name: self.factors.index(f) for name, f in self.anchor.items()}
        n = len(self.var_names)
        self.lam = [0.0] * n
        self.eta = [0.0] * n
        self.x = [self.start[i] for i in range(n)]
        self.dirty_nodes = set(range(n))
        self.dirty_factors = set(range(len(self.factors)))
        self.rounds = 0
        self.messages = 0
        self.last_move = [0.0] * n
        self.worked = set()      # the processors that have worked since it was last emptied (mind.py reads it)

    def weight_groups(self):
        """Weights that share a relation, together (connected groups)."""
        weights = [n for n in self.names if self.net.nodes[n].get("learn")]
        parent = {w: w for w in weights}

        def root(a):
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a
        for r in self.net.relations:
            ws = [n for n in self.net.nodes_of(r) if n in parent]
            for a in ws[1:]:
                parent[root(a)] = root(ws[0])
        groups = {}
        for w in weights:
            groups.setdefault(root(w), []).append(w)
        return list(groups.values())

    def link_memory(self, names):
        """The memory of a group of weights: from the network's links (what was learned before, possibly by
        smaller groups that have met since), the rest from each weight's own prior."""
        n = len(names)
        L = [[0.0] * n for _ in range(n)]
        h = [0.0] * n
        covered = set()
        for link in getattr(self.net, "links", []):
            idx = [names.index(a) for a in link["names"] if a in names]
            if len(idx) != len(link["names"]):
                continue
            for a, ia in enumerate(idx):
                h[ia] += link["h"][a]
                for b, ib in enumerate(idx):
                    L[ia][ib] += link["L"][a][b]
            covered.update(link["names"])
        for k, name in enumerate(names):
            if name not in covered:
                v, sg = self.net.measured.get(name, (self.net.nodes[name]["guess"], 1e3))
                sh = self.shift.get(name, 0.0)
                if self.is_signed(self.index[name]):
                    u, sg = v / 10 ** sh, sg / 10 ** sh
                else:
                    u = math.log10(v) - sh
                L[k][k] += 1.0 / sg ** 2
                h[k] += u / sg ** 2
        return L, h

    def unit_of(self, r):
        """The machine's unit of a sum relation (that of its first node with a dimension): its sigma is given in SI."""
        for _, t in r["terms"]:
            for n in t:
                if n in self.shift:
                    return 10 ** self.shift[n]
        return 1.0

    def nonlinear_sum(self, r):
        for _, t in r["terms"]:
            free = [n for n in t if n in self.index]
            if len(free) > 1 or (free and abs(t[free[0]] - 1.0) > 1e-12):
                return True
        return False

    def add_var(self, name, signed):
        if name in self.index:
            return
        self.index[name] = len(self.var_names)
        self.var_names.append(name)
        self.var_signed.append(signed)
        spec = self.net.nodes.get(name)
        if name.startswith("~"):
            q = self.net.nodes[name[1:]]
            self.start.append(q["guess"])
        elif signed:
            self.start.append(float(spec["guess"]) / 10 ** self.shift.get(name, 0.0))
        else:
            self.start.append(math.log10(spec["guess"]) - self.shift.get(name, 0.0))

    def is_signed(self, i):
        return self.var_signed[i]

    def set_anchor(self, name):
        f = self.anchor[name]
        i = self.index[name]
        if self.net.nodes.get(name, {}).get("learn"):
            f.b, f.w = 0.0, 0.0          # a weight's memory is its group's (joint), not an anchor
            return
        if name in self.net.measured:
            v, s = self.net.measured[name]
            if self.is_signed(i):
                k = 10 ** self.shift.get(name, 0.0)
                f.b, f.w = v / k, 1.0 / (max(s, MIN_SIGMA) / k) ** 2
            else:
                f.b, f.w = math.log10(v) - self.shift.get(name, 0.0), 1.0 / max(s, MIN_SIGMA) ** 2
        else:
            f.b = self.start[i]
            f.w = 1.0 / (PRIOR_SIGNED / 10 ** self.shift.get(name, 0.0) if self.is_signed(i) else PRIOR_LOG) ** 2

    # ------------------------------------------------------------------ talking to it while it runs
    def observe(self, name, value, sigma=None):
        """A new measurement (an input: a key, a sensor, the past of the next moment). Wakes only its node."""
        i = self.index.get(name)
        if i is None:
            raise TalkError(tr("{name} is not a free node", name=name))
        if sigma is None:
            # as the senses do (Weber): what is not said of a signed value is known to a thousandth of it
            sigma = self.net.measured.get(name, (None, 1e-3 * max(abs(value), 1.0) if self.is_signed(i) else 0.01))[1]
        self.net.measured[name] = (value, sigma)
        self.set_anchor(name)
        self.dirty_factors.add(self._anchor_index[name])

    def forget(self, name):
        self.net.measured.pop(name, None)
        self.set_anchor(name)
        self.dirty_factors.add(self._anchor_index[name])

    def value(self, name):
        if name in self.fixed:
            return self.fixed[name]
        i = self.index[name]
        if self.is_signed(i):
            return self.x[i]
        return 10 ** self.x[i] if self.x[i] < 308 else math.inf

    def value_si(self, name):
        """The value as the outside reads it: in SI for a node with a dimension."""
        return self.value(name) * 10 ** self.shift.get(name, 0.0)

    def sigma(self, name):
        """The uncertainty the messages give (not reliable around loops): dex, or the node's unit if signed."""
        if name in self.fixed:
            return 0.0
        lam = self.lam[self.index[name]]
        return 1.0 / math.sqrt(lam) if lam > 0 else math.inf

    # ------------------------------------------------------------------ one round
    def round(self):
        F = self.factors
        moved = 0.0
        woken = set(self.dirty_factors)
        # 1) the nodes that heard something new: to each relation, what all the others say
        for i in self.dirty_nodes:
            nf = self.node_factors[i]
            lams = [F[f].out_lam[s] for f, s in nf]
            etas = [F[f].out_eta[s] for f, s in nf]
            ol, oe = _others(lams), _others(etas)
            for k, (f, s) in enumerate(nf):
                fac = F[f]
                if _news(fac.in_lam[s], fac.in_eta[s], ol[k], oe[k]):
                    fac.in_lam[s], fac.in_eta[s] = ol[k], oe[k]
                    woken.add(f)
                    self.messages += 1
            lam, eta = sum(lams), sum(etas)
            self.lam[i], self.eta[i] = lam, eta
            if lam > 0:
                new = eta / lam
                self.last_move[i] = abs(new - self.x[i])
                if self.last_move[i] > QUIET + 1e-15 * abs(new):
                    for f in self.watchers[i]:
                        woken.add(f)
                moved = max(moved, self.last_move[i])
                self.x[i] = new
        # 2) the relations that heard something new: to each node, what it would be if the relation held
        nodes = set()
        for f in woken:
            fac = F[f]
            old_l, old_e = list(fac.out_lam), list(fac.out_eta)
            self.answer(fac)
            for s, i in enumerate(fac.vars):
                if _news(old_l[s], old_e[s], fac.out_lam[s], fac.out_eta[s]):
                    nodes.add(i)
                    self.messages += 1
        # a relation that had nothing to do this round has settled: its next work starts calm and undamped
        for f in self.resting(woken):
            fac = F[f]
            fac.swing, fac.damp = 0, 0.0
            fac.trend = [0.0] * len(fac.vars)
        self.busy = woken
        self.worked.update(woken)
        self.dirty_factors = set()
        self.dirty_nodes = nodes
        self.rounds += 1
        return moved

    def resting(self, woken):
        """The relations that were busy last round and not this one."""
        return [f for f in getattr(self, "busy", ()) if f not in woken]

    def holds(self, fac):
        """The conditions a relation watches (`when`): it holds only while they all hold."""
        for i, lo, hi in fac.watch:
            if i < 0:
                return False
            v = self.value_si(self.var_names[i])
            if not lo <= v <= hi:
                return False
        return True

    def answer(self, fac):
        if fac.kind in ("relation", "nonlinear") and fac.watch:
            fac.active = self.holds(fac)
            if not fac.active:
                fac.out_lam = [0.0] * len(fac.vars)
                fac.out_eta = [0.0] * len(fac.vars)
                return
        if fac.kind == "nonlinear":
            self.redraw(fac)
            return
        if fac.kind == "joint":
            self.joint(fac)
            return
        if fac.kind == "convert":
            self.convert(fac)
        elif fac.kind == "keep":
            self.contact(fac)
        elif fac.kind == "relation":
            ol, oe = list(fac.out_lam), list(fac.out_eta)
            self.linear(fac)
            for s, (l0, e0, l1, e1) in enumerate(zip(ol, oe, fac.out_lam, fac.out_eta)):
                if l0 > 0 and l1 > 0:
                    step = e1 / l1 - e0 / l0
                    if abs(step) > QUIET + 1e-15 * abs(e1 / l1):
                        if step * fac.trend[s] < 0:
                            fac.swing += 1
                        fac.trend[s] = step
            if fac.swing >= SWINGS:
                fac.damp = DAMPING
            if fac.damp > 0:
                d = fac.damp
                fac.out_lam = [d * a + (1 - d) * b for a, b in zip(ol, fac.out_lam)]
                fac.out_eta = [d * a + (1 - d) * b for a, b in zip(oe, fac.out_eta)]
        else:
            self.linear(fac)

    def linear(self, fac):
        var, mean = [], []
        for s, c in enumerate(fac.coef):
            d = fac.in_lam[s]
            if d > 0 and c != 0.0:
                var.append(c * c / d)
                mean.append(c * fac.in_eta[s] / d)
            else:
                var.append(math.inf if c != 0.0 else 0.0)
                mean.append(0.0)
        ov, om = _others(var), _others(mean)
        for s, c in enumerate(fac.coef):
            total = (1.0 / fac.w if fac.w > 0 else math.inf) + ov[s]
            if c == 0.0 or math.isinf(total):
                fac.out_lam[s] = fac.out_eta[s] = 0.0
            else:
                lam = c * c / total
                fac.out_lam[s] = lam
                fac.out_eta[s] = lam * (fac.b - om[s]) / c

    def convert(self, fac):
        """~q = q, that is x = 10^y: drawn as a straight relation around the current y (its own redrawing,
        three times, so the line it sends is drawn where it lands)."""
        for _ in range(3):
            lam = fac.in_lam[1] + fac.out_lam[1]
            y0 = (fac.in_eta[1] + fac.out_eta[1]) / lam if lam > 0 else self.x[fac.vars[1]]
            y0 = max(min(y0, 300.0), -300.0)
            v = 10.0 ** y0
            fac.coef = [1.0, -v * LN10]
            fac.b = v * (1.0 - y0 * LN10)
            fac.w = 1.0 / (CONVERTER_SIGMA * max(1.0, v)) ** 2
            self.linear(fac)

    def redraw(self, fac):
        """A sum whose terms multiply free nodes (k * x) or raise them to a power: drawn as a straight relation
        around where its nodes are (in + own messages), three times, by the relation itself."""
        for _ in range(3):
            u0 = []
            for s, i in enumerate(fac.vars):
                lam = fac.in_lam[s] + fac.out_lam[s]
                u0.append((fac.in_eta[s] + fac.out_eta[s]) / lam if lam > 0 else self.x[i])
            vals = [u if self.is_signed(i) else 10.0 ** max(min(u, 300.0), -300.0) for u, i in zip(u0, fac.vars)]
            r0 = -fac.b
            grad = [0.0] * len(fac.vars)
            for k, parts in fac.terms:
                term = k
                for s, p in parts:
                    term *= vals[s] ** p
                r0 += term
                for s, p in parts:
                    i = fac.vars[s]
                    if self.is_signed(i):
                        others = k * p * (vals[s] ** (p - 1) if vals[s] != 0 or p >= 1 else 0.0)
                        for s2, p2 in parts:
                            if s2 != s:
                                others *= vals[s2] ** p2
                        grad[s] += others
                    else:
                        grad[s] += term * p * LN10
            fac.coef = grad
            b = sum(g * u for g, u in zip(grad, u0)) - r0
            w0 = fac.w
            saved_b = fac.b
            fac.b = b
            self.linear(fac)
            fac.b = saved_b
            fac.w = w0

    def joint(self, fac):
        """What a group of weights remembers, told to each weight given what the others hear: the Gaussian
        (L, h) with the others' messages added, the others marginalized out."""
        n = len(fac.vars)
        if n == 1:
            fac.out_lam[0], fac.out_eta[0] = fac.L[0][0], fac.h[0]
            return
        L = _np.array(fac.L, dtype=float)
        h = _np.array(fac.h, dtype=float)
        d = _np.array(fac.in_lam, dtype=float)
        e = _np.array(fac.in_eta, dtype=float)
        for s in range(n):
            o = [k for k in range(n) if k != s]
            J = L[_np.ix_(o, o)] + _np.diag(d[o])
            hv = h[o] + e[o]
            Jso = L[s, o]
            try:
                sol = _np.linalg.solve(J, _np.column_stack([Jso, hv]))
            except _np.linalg.LinAlgError:
                fac.out_lam[s] = fac.out_eta[s] = 0.0
                continue
            fac.out_lam[s] = float(L[s, s] - Jso @ sol[:, 0])
            fac.out_eta[s] = float(h[s] - Jso @ sol[:, 1])

    def evidence(self):
        """What the current inputs teach the weights, relation by relation: each relation that holds weights,
        drawn straight where it is, its other nodes marginalized (they are what the inputs made them). Returns
        {joint factor: (dL, dh)}."""
        out = {}
        for jf in self.joints:
            slots = {i: k for k, i in enumerate(jf.vars)}
            n = len(jf.vars)
            dL = [[0.0] * n for _ in range(n)]
            dh = [0.0] * n
            for f in self.factors:
                if f.kind not in ("relation", "nonlinear") or not any(i in slots for i in f.vars):
                    continue
                if f.watch and not f.active:
                    continue
                if f.kind == "nonlinear":
                    self.redraw(f)
                g, others_var, rest = {}, 1.0 / f.w if f.w > 0 else math.inf, 0.0
                for s_, (i, c) in enumerate(zip(f.vars, f.coef)):
                    if i in slots:
                        g[slots[i]] = g.get(slots[i], 0.0) + c
                    elif c != 0.0:
                        d = f.in_lam[s_]
                        if d <= 0:
                            others_var = math.inf
                            break
                        others_var += c * c / d
                        rest += c * f.in_eta[s_] / d
                if math.isinf(others_var) or not g:
                    continue
                b = self._linear_b(f) - rest
                w = 1.0 / others_var
                for a, ga in g.items():
                    dh[a] += w * ga * b
                    for c_, gc in g.items():
                        dL[a][c_] += w * ga * gc
            out[jf] = (dL, dh)
        return out

    def _linear_b(self, f):
        if f.kind != "nonlinear":
            return f.b
        # the straight line the nonlinear relation drew last: sum g u = b_line
        u0 = []
        for s_, i in enumerate(f.vars):
            lam = f.in_lam[s_] + f.out_lam[s_]
            u0.append((f.in_eta[s_] + f.out_eta[s_]) / lam if lam > 0 else self.x[i])
        vals = [u if self.is_signed(i) else 10.0 ** max(min(u, 300.0), -300.0) for u, i in zip(u0, f.vars)]
        r0 = -f.b
        for k, parts in f.terms:
            t = k
            for s_, p in parts:
                t *= vals[s_] ** p
            r0 += t
        return sum(g * u for g, u in zip(f.coef, u0)) - r0

    def fold(self):
        """The weights keep what the inputs taught them: their memory (L, h) becomes what they knew plus what the
        current inputs say. Called before new inputs are heard, so each set of inputs is counted once."""
        for jf, (dL, dh) in self.evidence().items():
            n = len(jf.vars)
            for a in range(n):
                jf.h[a] += dh[a]
                for b in range(n):
                    jf.L[a][b] += dL[a][b]
            self.dirty_factors.add(self.factors.index(jf))
        self.save_links()

    def save_links(self):
        self.net.links = [{"names": [self.var_names[i] for i in jf.vars], "L": jf.L, "h": jf.h}
                          for jf in self.joints]

    def downscale(self, factor, per_weight=None):
        """Sleep: every memory of weights loosens a little (its precision times factor, its values kept): room to
        learn again (inspired by the synaptic homeostasis of sleep). per_weight: {weight: factor} for the weights
        that keep more or less of what they learned (tagged by pleasure or displeasure, mind.py); a group of
        weights takes the mean of its members."""
        for jf in self.joints:
            k = factor
            if per_weight:
                ks = [per_weight.get(self.var_names[i], factor) for i in jf.vars]
                k = sum(ks) / len(ks)
            jf.L = [[v * k for v in row] for row in jf.L]
            jf.h = [v * k for v in jf.h]
            self.dirty_factors.add(self.factors.index(jf))
        self.save_links()

    def residual(self, f):
        """How far relation f is from holding at the current values, in its own sigmas."""
        if f.kind == "nonlinear":
            vals = [self.x[i] if self.is_signed(i) else 10.0 ** max(min(self.x[i], 300.0), -300.0) for i in f.vars]
            r = -f.b
            for k, parts in f.terms:
                t = k
                for s_, p in parts:
                    t *= vals[s_] ** p
                r += t
        else:
            r = sum(c * self.x[i] for i, c in zip(f.vars, f.coef)) - f.b
        return r * math.sqrt(f.w)

    def surprise(self):
        """Prediction errors: how far each relation that hears the inputs is from holding once the new inputs are
        in, in its sigmas (the weights have barely moved yet: it is how far the inputs were from what the network
        expected). An ignorant network is not surprised: its weights simply follow."""
        inputs = {self.index[n] for n, sp in self.net.nodes.items() if sp.get("input") and n in self.index}
        # a hidden variable that moves with the inputs (a drift) takes their surprise: its law says how far it had
        # to move from what it was expected to be
        hidden = {self.index[n] for n in self.index if n.startswith("drift_") and not n.endswith("_before")}
        out = {}
        for f in self.factors:
            if f.kind in ("relation", "nonlinear") and f.w > 0 and (inputs.intersection(f.vars) or (
                    hidden.intersection(f.vars) and f.name.endswith("_law"))):
                if f.watch and not f.active:
                    continue
                out[f.name] = self.residual(f)
        return out

    def contact(self, fac):
        """keep u >= bound: pushes (holds u at the bound) only when the conditions it watches hold and what the
        other relations say of u is beyond the bound."""
        ok = all(i >= 0 and lo <= self.value_si(self.var_names[i]) <= hi for i, lo, hi in fac.watch)
        d = fac.in_lam[0]
        others = fac.in_eta[0] / d if d > 0 else self.x[fac.vars[0]]
        beyond = others < fac.bound if fac.op == ">=" else others > fac.bound
        fac.active = bool(ok and beyond)
        if fac.active:
            lam = 1.0 / MIN_SIGMA ** 2
            fac.out_lam[0], fac.out_eta[0] = lam, lam * fac.bound
        else:
            fac.out_lam[0] = fac.out_eta[0] = 0.0

    # ------------------------------------------------------------------ running
    def run(self, max_rounds=1000, callback=None, every=1):
        """Rounds until nothing has anything new to say (or max_rounds). Returns the rounds it took."""
        start = self.rounds
        while self.rounds - start < max_rounds and (self.dirty_nodes or self.dirty_factors):
            moved = self.round()
            if callback and (self.rounds - start) % every == 0:
                if callback(self, moved) is False:
                    break
        return self.rounds - start

    def tick(self, max_rounds=1000, learn=False):
        """One tick of the machine's clock: the network settles (at most max_rounds), then every `set` whose
        conditions hold writes its variable (all at once, from the values before the tick). Returns
        {variable: new value}.

        Learning: when the inputs have changed since the last tick (a key, a number, a row of a file; or learn=True),
        every weight first keeps what it believed with the inputs before (its prior becomes that belief), then
        hears the new ones. So each set of inputs is counted once, and what the weights have learned stays."""
        self.begin_tick(learn)
        self.run(max_rounds)
        return self.end_tick()

    def begin_tick(self, learn=False):
        """The start of a tick: when the inputs have changed, the weights keep what the inputs before taught them.
        Then rounds (run, or one at a time: round), then end_tick."""
        seen = {n: self.net.measured.get(n) for n, sp in self.net.nodes.items() if sp.get("input")}
        new = learn or seen != getattr(self, "_seen", None)
        if new and getattr(self, "_heard", False):
            self.fold()              # the inputs before are kept by the weights, then the new ones are heard
        self._tick = {"new": new, "seen": seen}

    def end_tick(self):
        """The end of a tick: its surprise, then every `set` whose conditions hold writes its variable."""
        t = getattr(self, "_tick", None) or {"new": False, "seen": getattr(self, "_seen", None)}
        self._tick = None
        new, seen = t["new"], t["seen"]
        self.settled = self.quiet    # whether it settled in the rounds it was given (before the writes below)
        if new:
            self.last_surprise = self.surprise()
        writes = {}
        for st in self.net.sets:
            if all(lo <= self.value_si(n) <= hi for n, lo, hi in st["when"]):
                writes[st["target"]] = self.value_si(st["source"])
        for name, v in writes.items():
            if name not in self.net.measured or v != self.net.measured[name][0]:
                self.observe(name, v, self.net.measured.get(name, (0, 1e-9))[1])
        self._heard = True
        self._seen = seen
        self.net.ticks = getattr(self.net, "ticks", 0) + 1
        return writes

    def beliefs(self):
        """What every weight (`learn`) believes now: (value, sigma)."""
        out = {}
        for name, spec in self.net.nodes.items():
            if spec.get("learn") and name in self.index:
                lam = self.lam[self.index[name]]
                if lam > 0:
                    out[name] = (self.x[self.index[name]], 1.0 / math.sqrt(lam))
        return out

    @property
    def ticks(self):
        return getattr(self.net, "ticks", 0)

    @property
    def quiet(self):
        return not (self.dirty_nodes or self.dirty_factors)

    def processors(self):
        return len(self.factors) + len(self.var_names)

    # ------------------------------------------------------------------ memory
    def sleep(self, path, extra=None):
        """The network and the state of every processor, as they are now."""
        net = self.net
        state = {
            "format": "grm-talk-sleep-1",
            "nodes": net.nodes, "relations": net.relations, "measured": net.measured,
            "networks": net.networks, "calls": net.calls, "sets": net.sets, "ticks": getattr(net, "ticks", 0),
            "rounds": self.rounds, "x": self.x, "lam": self.lam, "eta": self.eta,
            "factors": [{"name": f.name, "out_lam": f.out_lam, "out_eta": f.out_eta, "in_lam": f.in_lam,
                         "in_eta": f.in_eta, "coef": f.coef, "b": f.b, "w": f.w, "active": f.active,
                         "damp": f.damp, "swing": f.swing, "trend": f.trend, "L": f.L, "h": f.h}
                        for f in self.factors],
            "dirty_nodes": sorted(self.dirty_nodes), "dirty_factors": sorted(self.dirty_factors),
            "extra": extra or {},
            "links": getattr(net, "links", []), "heard": getattr(self, "_heard", False),
            "aliases": getattr(net, "aliases", {}), "fusions": getattr(net, "fusions", []),
            "inverses": getattr(net, "inverses", {}),
            "seen_values": getattr(net, "seen", {}), "rows_seen": getattr(net, "rows", []),
            "tension": getattr(net, "tension", {}), "found": getattr(net, "found", []),
            "seen": getattr(self, "_seen", None),
            "use": getattr(net, "use", {}), "origin": getattr(net, "origin", {}), "mood": getattr(net, "mood", {}),
            "groups": getattr(net, "groups", {}), "journal": getattr(net, "journal", []),
            "capacity": getattr(net, "capacity", None),
        }
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(state, fh)

    @staticmethod
    def wake(path):
        """A machine as it was put to sleep: same network, same messages, nothing solved again."""
        with open(path, encoding="utf-8") as fh:
            st = json.load(fh)
        if st.get("format") != "grm-talk-sleep-1":
            raise TalkError(tr("{path} is not a sleeping grm network", path=path))
        net = Network()
        net.nodes = st["nodes"]
        net.relations = []
        for r in st["relations"]:
            if r.get("kind") == "sum":
                r["terms"] = [(c, t) for c, t in r["terms"]]
            if r.get("kind") == "keep":
                r["when"] = [tuple(w) for w in r["when"]]
            net.relations.append(r)
        net.measured = {k: tuple(v) for k, v in st["measured"].items()}
        net.links = st.get("links", [])
        net.aliases = st.get("aliases", {})
        net.inverses = st.get("inverses", {})
        net.fusions = st.get("fusions", [])
        net.seen = st.get("seen_values", {})
        net.rows = st.get("rows_seen", [])
        net.tension = st.get("tension", {})
        net.found = st.get("found", [])
        net.use = st.get("use") or {"nodes": {}, "relations": {}}
        net.origin = st.get("origin") or {"nodes": {}, "relations": {}}
        net.mood = st.get("mood") or {}
        net.groups = st.get("groups") or {}
        net.journal = st.get("journal") or []
        net.capacity = st.get("capacity")
        net.networks = {k: (v[0], v[1]) for k, v in st["networks"].items()}
        net.calls = [tuple(c) for c in st["calls"]]
        net.sets = [dict(x, when=[tuple(w) for w in x["when"]]) for x in st.get("sets", [])]
        for r in net.relations:
            if "when" in r:
                r["when"] = [tuple(w) for w in r["when"]]
        m = Machine(net)
        if len(m.factors) != len(st["factors"]):
            raise TalkError(tr("the sleeping state does not match its network"))
        for f, s in zip(m.factors, st["factors"]):
            f.out_lam, f.out_eta, f.in_lam, f.in_eta = s["out_lam"], s["out_eta"], s["in_lam"], s["in_eta"]
            f.coef, f.b, f.w, f.active = s["coef"], s["b"], s["w"], s["active"]
            f.damp, f.swing, f.trend = s.get("damp", 0.0), s.get("swing", 0), s.get("trend", [0.0] * len(f.vars))
            if s.get("L") is not None:
                f.L, f.h = s["L"], s["h"]
        m.x, m.lam, m.eta = st["x"], st["lam"], st["eta"]
        m.rounds = st["rounds"]
        m.dirty_nodes, m.dirty_factors = set(st["dirty_nodes"]), set(st["dirty_factors"])
        m.extra = st.get("extra", {})
        net.ticks = st.get("ticks", 0)
        m._heard = st.get("heard", False)
        seen = st.get("seen")
        m._seen = {k: (tuple(v) if v is not None else None) for k, v in seen.items()} if seen is not None else None
        return m

    # ------------------------------------------------------------------ the picture (live.py)
    def view(self):
        return _View(self)


def _news(old_l, old_e, new_l, new_e):
    if old_l == new_l and old_e == new_e:
        return False
    if old_l <= 0 and new_l <= 0:
        return False
    if old_l <= 0 or new_l <= 0:
        return True
    if abs(new_l - old_l) > QUIET_PRECISION * max(old_l, new_l):
        return True
    m0, m1 = old_e / old_l, new_e / new_l
    return abs(m1 - m0) > QUIET + 1e-15 * abs(m1)


class _View:
    """The machine as live.py draws it: nodes, relations (the anchors of measured nodes as measurements)."""

    def __init__(self, m):
        self.m = m
        self.names = m.var_names
        self.index = m.index
        self.factors = []
        for f in m.factors:
            if f.kind == "anchor":
                n = f.name.split(" ", 1)[1]
                kind = "measure" if n in m.net.measured else "prior"
            else:
                kind = "relation"
            self.factors.append((f.name, list(zip(f.vars, f.coef)), f.b, f.w, kind))
        self.node_factors = m.node_factors

    def tension(self, x, fi):
        f = self.m.factors[fi]
        if f.kind == "keep":
            return 3.0 if f.active and abs(x[f.vars[0]] - f.bound) > 1e-6 else 0.0
        if f.w <= 0:
            return 0.0
        return (sum(c * x[i] for i, c in zip(f.vars, f.coef)) - f.b) * math.sqrt(f.w)
