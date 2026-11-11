# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Anthony Charretier
"""The GRM virtual machine: a network that is the program, the memory and the calculator at once, and the few
drivers that are its body (keyboard and files in, screen and sound out for a human).

    python vm/grm_vm.py                  the machine in the terminal
    python vm/grm_vm.py --window         the machine in a window: the outputs shown and heard
    python vm/grm_vm.py --blank          start from a blank network (the memory is not read)
    python vm/grm_vm.py -c "use programs/double.grm; tick 20; outputs"

The machine starts blank, or from its memory (vm/memory.json) if it has one, and puts itself to sleep there when it
stops: the next session goes on from where this one ended. Everything it does comes from the network (vm/language.py
for the words, vm/runtime.py for the relational machine). This file is only the body: it measures the inputs, gives
the clock's ticks, reads the outputs and turns them into something a human sees and hears.

Units: inside, the machine counts in its own units, where c, hbar, G and kB are 1 (pygrm.units, "ticks"). A node
with a dimension ([M L T Q K]) is given and read in SI; a node without one is a pure number.
"""
import cmd
import csv
import json
import math
import os
import shlex
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from language import Network, TalkError, from_store, statement   # noqa: E402
from runtime import Machine   # noqa: E402
import body   # noqa: E402

try:
    from pygrm import units as _units
except ImportError:  # pragma: no cover
    _units = None
try:
    from pygrm import discover as _discover
except ImportError:  # pragma: no cover - pygrm older than 0.3.0: the machine does not find relations by itself
    _discover = None

MEMORY = os.path.join(HERE, "memory.json")
BASE = os.path.join(HERE, "base.grm")
UNITS = "ticks"
ROWS = 500         # how many moments the machine keeps to find relations and missing nodes in
MAX_NEW = 5        # relations it may add in one go
SEEN = 240         # how many past values of each input the machine keeps (for its fusions)
SAME = 0.01        # two series are one when they agree row by row (correlation 0.999) and in level and spread to 1 %
MATCH_SIGMA = 2.0  # a still input is a known node when it is within 2 sigmas of it...
PRECISE = 0.0043   # ...and that node is known to 1 % (0.0043 dex) at least: a coincidence with a vague node
                   # (a human mass, 70 kg ± 20 %) says nothing
NIGHT = 0.8        # what a night of sleep leaves of the weights' precision (the synapses of the cortex shrink by
                   # about 20 % in sleep: Tononi & Cirelli's synaptic homeostasis); their values are kept


def fmt(v):
    if v == 0 or (1e-3 <= abs(v) < 1e6):
        return f"{v:.6g}"
    return f"{v:.6e}"


class VM:
    """The machine: a network, its relational machine, its memory file."""

    def __init__(self, memory=MEMORY, blank=False):
        self.memory = memory
        self.net = Network()
        self.machine = None
        self.note = "blank"
        self.history = {}           # output -> recent values (for the body); "surprise" too
        if not blank and memory and os.path.exists(memory):
            try:
                self.machine = Machine.wake(memory)
                self.net = self.machine.net
                self.note = f"woke from {os.path.basename(memory)} (tick {self.machine.ticks})"
                return
            except Exception as e:  # noqa: BLE001 - an unreadable memory: start from the base, say why
                self.note = f"{os.path.basename(memory)} not usable ({e}): "
        else:
            self.note = ""
        if not blank and os.path.exists(BASE):
            statement(self.net, "use base.grm", HERE)
            self.note += f"born with its base ({len(self.net.nodes)} points of the world)"
        else:
            self.note += "blank"

    # ------------------------------------------------------------------ the network
    def say(self, line, base=None):
        """A statement of the language. The machine is rebuilt when the network changes; what the network holds
        (variables, weights, measurements) is kept, so it settles again from where it was."""
        said = statement(self.net, line, base or HERE)
        if said is not None and self.net.recording is None and said:
            self.machine = None
        return said

    def m(self):
        if self.machine is None:
            self.machine = Machine(self.net)
            self.machine.run(5000)
        return self.machine

    def dim(self, name):
        return self.net.nodes.get(name, {}).get("dim")

    def put(self, name, value, sigma=None):
        """An input: a value given from outside (in SI if the node has a dimension)."""
        name = self.net.aliases.get(name, name)
        if name in self.net.inverses:            # a name fused as an inverse: its node is given 1 / value
            name, value = self.net.inverses[name], 1.0 / value
            if sigma is not None:
                sigma = sigma / abs(value)
        if name not in self.net.nodes:
            self.say(f"input {name}")
        spec = self.net.nodes[name]
        if not spec.get("signed") and value <= 0:
            raise TalkError(f"{name} is a positive quantity")
        self.m().observe(name, value, sigma)
        h = self.net.seen.setdefault(name, [])
        h.append(value)
        del h[:-SEEN]

    def get(self, name):
        m = self.m()
        m.run(5000)              # what it says once it has heard everything new
        return m.value_si(name)

    def outputs(self):
        return [n for n, s in self.net.nodes.items() if s.get("output")]

    def tick(self, n=1, learn=False, max_rounds=2000):
        m = self.m()
        writes = {}
        for _ in range(n):
            m.last_surprise = {}
            writes = m.tick(max_rounds, learn=learn)
            for o in self.outputs():
                self.remember(o, self.get(o))
            z = list(m.last_surprise.values())
            if z:   # how far the inputs were from what the network expected of them (rms, in sigmas)
                self.remember("surprise", math.sqrt(sum(v * v for v in z) / len(z)))
            # what it has seen, kept for what it finds by itself: the inputs of each new moment, and how far each
            # relation was from holding then
            row = {k: self.net.measured[k][0] for k, sp in self.net.nodes.items()
                   if sp.get("input") and k in self.net.measured}
            if row and (learn or row != getattr(self, "_last_row", None)):
                self._last_row = row
                self.net.rows.append(row)
                del self.net.rows[:-ROWS]
                for rel, r in m.last_surprise.items():
                    h = self.net.tension.setdefault(rel, [])
                    h.append(r)
                    del h[:-ROWS]
        return writes

    def remember(self, name, v):
        h = self.history.setdefault(name, [])
        h.append(v)
        del h[:-240]

    # ------------------------------------------------------------------ data
    def load(self, path):
        """A file of data, row by row: each row is given to the inputs (a column = a node) and the network learns
        from it (its weights keep what they now believe). CSV with a header; JSON: a list of records, {name: [values]},
        {name: value}, or a grm-core store (a network: it joins this one)."""
        rows = []
        if path.lower().endswith(".csv"):
            with open(path, newline="", encoding="utf-8") as f:
                for rec in csv.DictReader(f):
                    rows.append(rec)
        else:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and "networks" in data:
                sys.path.insert(0, os.path.join(os.path.dirname(HERE), "equation"))
                from store import load_grm_network_safely   # noqa: E402
                _, left_out = from_store(load_grm_network_safely(path), self.net)
                self.machine = None
                return f"network loaded: {len(self.net.nodes)} nodes, {len(self.net.relations)} relations" + (
                    f" ({len(left_out)} left out)" if left_out else "")
            if isinstance(data, list):
                rows = data
            elif isinstance(data, dict) and all(isinstance(v, list) for v in data.values()):
                n = min(len(v) for v in data.values())
                rows = [{k: v[i] for k, v in data.items()} for i in range(n)]
            elif isinstance(data, dict):
                rows = [data]
            else:
                raise TalkError("JSON data: a list of records, {name: [values]} or {name: value}")
        weights = [n for n, s in self.net.nodes.items() if s.get("learn")]
        before = {w: self.get(w) for w in weights}
        used = 0
        for rec in rows:
            given = False
            for k, v in rec.items():
                try:
                    x = float(v)
                except (TypeError, ValueError):
                    continue
                k = k.strip()
                if not k:
                    continue
                self.put(k, x)
                given = True
            if given:
                self.tick(learn=True)
                used += 1
        out = f"{used} rows learned"
        for w in weights:
            out += f"\n    {w}: {fmt(before[w])} -> {fmt(self.get(w))}  (± {self.m().sigma(w):.3g})"
        for line in self.grow():
            out += f"\n    {line}"
        return out

    # ------------------------------------------------------------------ what the machine does by itself
    def grow(self):
        """Everything the machine does by itself with what it has seen, after a file and at night: it fuses what is
        one thing under two names, writes the relations that hold among its inputs and that it did not know, and makes
        a node appear where a relation keeps missing something. Returns what it did, in words."""
        done = self.self_fuse()
        done += self.self_discover()
        done += self.self_hidden()
        return done

    def linked(self):
        """The groups of nodes the network already ties together (connected by its relations)."""
        parent = {}

        def root(a):
            parent.setdefault(a, a)
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a
        for r in self.net.relations:
            ns = self.net.nodes_of(r)
            for a in ns[1:]:
                parent[root(a)] = root(ns[0])
        groups = {}
        for a in list(parent):
            groups.setdefault(root(a), set()).add(a)
        return [g for g in groups.values() if len(g) > 1]

    def make_positive(self, name):
        spec = self.net.nodes[name]
        if not spec.get("signed"):
            return
        spec["signed"] = False
        if name in self.net.measured:
            v, sg = self.net.measured[name]
            self.net.measured[name] = (v, max(sg / (v * math.log(10)), 1e-9))
        if spec.get("guess", 0) <= 0:
            spec["guess"] = self.net.measured.get(name, (1.0,))[0]

    def self_discover(self):
        """New relations: the ones that hold among the inputs it has seen (pygrm.discover), when the network does not
        tie those inputs yet (a relation that would say again what the network says is not written: an echo).
        Power laws, straight lines, exponentials and logarithms, sums built on products, and what carries an input
        from one moment to the next (growth, decay, oscillations)."""
        if _discover is None or len(self.net.rows) < 8:
            return []
        names = [n for n in self.net.nodes if self.net.nodes[n].get("input")]
        rows = [{k: r[k] for k in names if k in r} for r in self.net.rows]
        rows = [r for r in rows if len(r) == len(rows[-1]) and set(r) == set(rows[-1])]
        try:
            found = _discover.find_relations(rows[-200:], exclude=self.linked())
            moving = getattr(_discover, "find_dynamics", None)
            dyn = moving(rows[-200:]) if moving else []
        except (ValueError, ZeroDivisionError):
            return []
        done = []
        for rel in found + [d for d in dyn if f"{d['target']}_before" not in self.net.nodes]:
            if len(done) >= MAX_NEW:
                break
            if rel["kind"] != "dynamics":
                nodes = [rel["target"], *(x for _, m in rel["terms"] for x in m)] if rel["kind"] == "sum" \
                    else [rel["target"], *rel["terms"]]
                if any(set(nodes) <= g for g in self.linked()):
                    continue                   # tied by what was just written
            k = sum(1 for r in self.net.relations if r["name"].startswith("found_")) + 1
            name = f"found_{k}"
            write = getattr(self, "_write_" + rel["kind"])
            write(rel, name, k)
            self.net.found.append({"relation": name, "kind": rel["kind"], "text": rel["text"], "r2": rel["r2"],
                                   "rows": rel["rows"], "tick": self.net.ticks})
            self.machine = None
            extra = ""
            mean = rel.get("meaning", {})
            if "period" in mean:
                extra = f"; an oscillation: period {mean['period']:.4g} moments, {mean['damping']:.4g} left each moment"
            elif "half_life" in mean:
                extra = f"; a decay: half-life {mean['half_life']:.4g} moments"
            elif "doubling" in mean:
                extra = f"; a growth: doubles in {mean['doubling']:.4g} moments"
            done.append(f"found by itself: {rel['text']} (relation {name}, r² {rel['r2']:.6f} over {rel['rows']} "
                        f"rows{extra})")
        return done

    def _weight(self, name, value, sigma, positive=False):
        statement(self.net, f"learn {name} = {value!r}" + (" positive" if positive else ""))
        self.net.measured[name] = (value, max(sigma, 1e-9 if not positive else 1e-6))
        return name

    def _ln(self, x):
        """The log of a positive input, as a node (the converter between a quantity and its exponent)."""
        self.make_positive(x)
        L = f"ln_{x}"
        if L not in self.net.nodes:
            statement(self.net, f"relate log_{x}: {L} = ln({x})")
        return L

    def _write_power(self, rel, name, k):
        for n in [rel["target"], *rel["terms"]]:
            self.make_positive(n)
        K = self._weight(f"K_{k}", rel["constant"], rel["constant_sigma"], positive=True)
        right = " * ".join([K] + [f"{x}^{p!r}" for x, p in rel["terms"].items()])
        statement(self.net, f"relate {name}: {rel['target']} = {right} ± {max(rel['sigma'], 1e-4)!r} dex")

    def _write_linear(self, rel, name, k):
        (x, a), b = next(iter(rel["terms"].items())), rel["constant"]
        sa = self._weight(f"a_{k}", a, rel.get("slope_sigma", 1.0))
        sb = self._weight(f"b_{k}", b, rel["constant_sigma"])
        statement(self.net, f"relate {name}: {rel['target']} = {sa} * {x} + {sb} ± {max(rel['sigma'], 1e-9)!r}")

    def _write_exponential(self, rel, name, k):
        # y = A e^(kx)  <=>  ln y = k x + ln A: a straight line between x and the exponent of y
        (x, kk), A = next(iter(rel["terms"].items())), rel["constant"]
        L = self._ln(rel["target"])
        sk = self._weight(f"k_{k}", kk, abs(kk) * 1e-3 + 1e-9)
        sa = self._weight(f"lnA_{k}", math.log(A), rel["constant_sigma"] * math.log(10))
        statement(self.net, f"relate {name}: {L} = {sk} * {x} + {sa} ± {max(rel['sigma'] * math.log(10), 1e-9)!r}")

    def _write_log(self, rel, name, k):
        (x, a), b = next(iter(rel["terms"].items())), rel["constant"]
        L = self._ln(x)
        sa = self._weight(f"a_{k}", a, abs(a) * 1e-3 + 1e-9)
        sb = self._weight(f"b_{k}", b, rel["constant_sigma"])
        statement(self.net, f"relate {name}: {rel['target']} = {sa} * {L} + {sb} ± {max(rel['sigma'], 1e-9)!r}")

    def _write_sum(self, rel, name, k):
        # a sum built on products: each product its own node (found once, used by every relation that needs it),
        # then the sum of those nodes
        parts = []
        for j, (a, mono) in enumerate(rel["terms"]):
            if len(mono) == 1 and next(iter(mono.values())) == 1.0:
                node = next(iter(mono))
            else:
                node = "_".join(x if p == 1 else f"{x}{p:g}" for x, p in sorted(mono.items()))
                if node not in self.net.nodes:
                    for x in mono:
                        self.make_positive(x)
                    right = " * ".join(x if p == 1 else f"{x}^{p!r}" for x, p in mono.items())
                    statement(self.net, f"relate product_{node}: {node} = {right}")
            w = self._weight(f"a{j + 1}_{k}", a, abs(a) * 1e-3 + 1e-9)
            parts.append(f"{w} * {node}")
        b = self._weight(f"b_{k}", rel["constant"], rel["constant_sigma"])
        statement(self.net, f"relate {name}: {rel['target']} = " + " + ".join(parts)
                  + f" + {b} ± {max(rel['sigma'], 1e-9)!r}")

    def _write_dynamics(self, rel, name, k):
        # what carries x from one moment to the next: its past is a variable written at each tick
        x = rel["target"]
        last = [r[x] for r in self.net.rows if x in r][-2:]
        before, before2 = f"{x}_before", f"{x}_before2"
        statement(self.net, f"var {before} = {last[-1]!r}")
        terms = [f"{self._weight(f'a1_{k}', rel['lags'][0], 1e-3 * abs(rel['lags'][0]) + 1e-9)} * {before}"]
        if len(rel["lags"]) > 1:
            statement(self.net, f"var {before2} = {last[0]!r}")
            terms.append(f"{self._weight(f'a2_{k}', rel['lags'][1], 1e-3 * abs(rel['lags'][1]) + 1e-9)} * {before2}")
            statement(self.net, f"set {before2} = {before}")
        statement(self.net, f"set {before} = {x}")
        c = self._weight(f"c_{k}", rel["constant"], rel["sigma"] + 1e-9)
        statement(self.net, f"relate {name}: {x} = " + " + ".join(terms) + f" + {c} ± {max(rel['sigma'], 1e-9)!r}")

    def self_hidden(self):
        """A node nobody mentioned: where a relation keeps missing the data on the same side, far beyond chance
        (pygrm.discover.hidden_node), a node appears in it, with the value that was missing. It is a weight: it goes
        on learning. Nothing is invented when nothing is missing."""
        if _discover is None:
            return []
        done = []
        for rel in list(self.net.relations):
            res = self.net.tension.get(rel["name"])
            if not res or rel.get("kind", "product") not in ("product", "sum"):
                continue
            names = self.net.nodes_of(rel)
            # misses that follow each other first: a hidden variable with its own law (it also takes an offset)
            moving = getattr(_discover, "hidden_dynamics", None)
            if moving and rel.get("kind") == "sum" and not any(n.startswith("drift_") for n in names):
                drift = moving(res[-200:])
                if drift["needed"]:
                    done.append(self._drift(rel, drift, res))
                    continue
            if any(n.startswith(("hidden_", "drift_")) for n in names):
                continue                      # it already has its missing node: that node goes on learning
            verdict = _discover.hidden_node(res[-200:])
            if not verdict["needed"]:
                continue
            k = sum(1 for n in self.net.nodes if n.startswith("hidden_")) + 1
            h = f"hidden_{k}"
            sigma = max(rel["sigma"], 1e-6)
            if rel.get("kind") == "sum":
                value = -verdict["value"] * sigma
                statement(self.net, f"learn {h} = {value!r}")
                self.net.measured[h] = (value, max(verdict["sigma"] * sigma, 1e-9))
                rel["terms"].append((1.0, {h: 1.0}))
            else:
                value = 10 ** (-verdict["value"] * sigma)
                statement(self.net, f"learn {h} = {value!r} positive")
                self.net.measured[h] = (value, max(verdict["sigma"] * sigma, 1e-6))
                rel["terms"][h] = 1.0
            rel["text"] += f"  [+ {h}]"
            self.net.tension[rel["name"]] = []
            self.machine = None
            done.append(f"a node nobody mentioned: {h} = {value:.6g} in {rel['name']} (it kept missing the data on "
                        f"the same side: {verdict['t']:.1f} sigma over {verdict['rows']} rows)")
        return done

    def _drift(self, rel, drift, res):
        """A node nobody mentioned that changes from moment to moment: a hidden variable with its own law
        (h = rho h_before), which the relation's data move each moment and the law carries to the next."""
        k = sum(1 for n in self.net.nodes if n.startswith("drift_") and not n.endswith("_before")) + 1
        h, before = f"drift_{k}", f"drift_{k}_before"
        sigma = max(rel["sigma"], 1e-6)
        last = -res[-1] * sigma
        statement(self.net, f"node {h} = {last!r} signed")
        statement(self.net, f"var {before} = {last!r}")
        rho = self._weight(f"rho_{k}", drift["rho"], 0.05)
        statement(self.net, f"relate {h}_law: {h} = {rho} * {before} ± {max(drift['sigma'] * sigma, 1e-9)!r}")
        statement(self.net, f"set {before} = {h}")
        rel["terms"].append((1.0, {h: 1.0}))
        rel["text"] += f"  [+ {h}]"
        self.net.tension[rel["name"]] = []
        self.machine = None
        return (f"a node nobody mentioned, that changes: {h} in {rel['name']} (its misses followed each other: "
                f"each one {drift['rho']:.2f} of the one before, over {drift['rows']} rows)")

    def self_fuse(self):
        """The machine's own routine against writing a node twice: it looks at what its inputs have been and fuses
        what is one thing under two names. Two inputs that agree row by row, in level and spread: one node. An input
        that holds still at the value of a node known precisely (within 2 sigmas, the node known to 1 %): that
        node. Run after a file is loaded and at night. Returns what it did, in words."""
        done = []
        while True:
            found = self._one_fusion()
            if not found:
                return done
            keep, gone, why = found[:3]
            inverse = len(found) > 3
            try:
                statement(self.net, f"fuse {keep} {gone}" + (" inverse" if inverse else ""))
            except TalkError as e:
                self.net.fusions.append({"keep": keep, "gone": gone, "why": why, "refused": str(e)})
                done.append(f"{gone} looks like {keep} ({why}) but stays apart: {e}")
                self._refused = getattr(self, "_refused", set()) | {(keep, gone) + (("inverse",) if inverse else ())}
                continue
            self.net.fusions.append({"keep": keep, "gone": gone, "why": why, "tick": self.net.ticks,
                                     "inverse": inverse})
            self.machine = None
            done.append(f"fused by itself: {gone} is {keep}" + ("^-1" if inverse else "") + f" ({why})")

    def _one_fusion(self):
        refused = getattr(self, "_refused", set())
        seen = {n: h for n, h in self.net.seen.items() if n in self.net.nodes and len(h) >= 3}
        names = list(seen)
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                va, vb = seen[a], seen[b]
                n = min(len(va), len(vb))
                if n < 5:
                    continue
                va, vb = va[-n:], vb[-n:]
                ma, mb = sum(va) / n, sum(vb) / n
                da, db = [v - ma for v in va], [v - mb for v in vb]
                sa, sb = math.sqrt(sum(v * v for v in da)), math.sqrt(sum(v * v for v in db))
                if sa > 0 and sb > 0 and sum(x * y for x, y in zip(da, db)) / (sa * sb) > 1 - SAME / 10 \
                        and abs(ma - mb) <= SAME * max(abs(ma), abs(mb)) and abs(sa - sb) <= SAME * sa:
                    keep, gone = self._order(a, b)
                    if (keep, gone) not in refused:
                        return keep, gone, "the same values, row by row"
                # one is the other's inverse (a period and a frequency): one node, its inverse included
                if min(va) > 0 and min(vb) > 0 and max(va) > min(va):
                    if all(abs(math.log10(x * y)) < math.log10(1 + SAME) for x, y in zip(va, vb)):
                        keep, gone = (a, b) if names.index(a) < names.index(b) else (b, a)
                        if (keep, gone, "inverse") not in refused:
                            return keep, gone, "its inverse, row by row", "inverse"
        m = self.m()
        m.run(5000)
        for b, vb in seen.items():
            mean = sum(vb) / len(vb)
            if mean <= 0 or (max(vb) - min(vb)) > 1e-3 * abs(mean):
                continue
            best = []
            for a, spec in self.net.nodes.items():
                if a == b or a in seen or spec.get("signed") or a.startswith("~") or "__" in a:
                    continue
                try:
                    va, sa = m.value_si(a), m.sigma(a)
                except (KeyError, OverflowError):
                    continue
                if not va > 0 or not sa < PRECISE:
                    continue
                sb = self.net.measured.get(b, (mean, 1e-3))[1]
                sb_dex = sb / (mean * math.log(10)) if self.net.nodes[b].get("signed") else sb
                t = abs(math.log10(mean / va)) / math.sqrt(sa ** 2 + sb_dex ** 2 + 1e-12)
                if t < MATCH_SIGMA:
                    best.append((t, a))
            if len(best) == 1 and (best[0][1], b) not in refused:
                return best[0][1], b, f"{mean:.6g} held still, {best[0][1]} is {m.value_si(best[0][1]):.6g}, " \
                                      f"{best[0][0]:.2g} sigma apart"
        return None

    def _order(self, a, b):
        """Which name stays: the positive one, otherwise the older one."""
        sa, sb = self.net.nodes[a], self.net.nodes[b]
        if sa.get("signed") and not sb.get("signed"):
            return b, a
        return a, b

    # ------------------------------------------------------------------ memory
    def sleep(self, path=None, night=False):
        """night: the end of a session. The weights' memory loosens a little before it is written (room to learn
        again the next day)."""
        done = []
        if night:
            done = self.grow()               # at night, the machine puts together what it has seen
            self.m().downscale(NIGHT)
        self.m().sleep(path or self.memory)
        return done

    def wake(self, path=None):
        self.machine = Machine.wake(path or self.memory)
        self.net = self.machine.net

    def blank(self):
        self.net = Network()
        self.machine = None
        self.history = {}


class Shell(cmd.Cmd):
    prompt = "grm> "
    WORDS = ("node", "relate", "observe", "forget", "keep", "network", "call", "use", "end", "var", "set",
             "learn", "input", "output", "fuse")

    def __init__(self, vm, out=None):
        super().__init__(stdout=out)
        self.vm = vm
        self.write = (lambda t: print(t)) if out is None else (lambda t: out.write(t + "\n"))
        self.base = HERE
        self.sound = False
        self.clock = 0.0
        self.intro = (f"GRM machine: {vm.note}. Talk to it in its words (var, set, relate, learn, input, output...); "
                      f"Enter alone = one tick. `help` for the rest.")

    def emptyline(self):
        self.do_tick("")

    def default(self, line):
        word = line.split()[0].lower() if line.split() else ""
        if self.vm.net.recording is not None or word in self.WORDS:
            try:
                said = self.vm.say(line, self.base)
            except TalkError as e:
                self.write(f"  ? {e}")
                return
            if said:
                self.write(f"  {said}")
            return
        self.write(f"  ? '{word}' is not a word of the machine (help)")

    def onecmd(self, line):
        if self.vm.net.recording is not None:
            self.default(line)
            return False
        if ";" in line:
            for part in line.split(";"):
                if part.strip() and self.onecmd(part.strip()):
                    return True
            return False
        return super().onecmd(line)

    # --------------------------------------------------------------- running
    def do_tick(self, arg):
        """tick [n]: n ticks of the clock (Enter alone: one)"""
        try:
            n = int(arg) if arg.strip() else 1
        except ValueError:
            self.write("  tick [n]")
            return
        m = self.vm.m()
        r0 = m.rounds
        writes = self.vm.tick(n)
        if n == 1:
            ws = ", ".join(f"{k} = {fmt(v)}" for k, v in writes.items() if "__" not in k)
            self.write(f"  tick {m.ticks}: {m.rounds - r0} rounds" + (f"; {ws}" if ws else ""))
        else:
            self.write(f"  {n} ticks (now {m.ticks}): {m.rounds - r0} rounds")
        if self.vm.outputs():
            self.do_outputs("")
        if self.sound:
            body.play(body.sound_of(self.vm.history))

    def do_put(self, arg):
        """put NAME = VALUE [± sigma]: an input (in SI if the node has a dimension)"""
        name, _, rest = arg.partition("=")
        value, _, sig = rest.partition("±")
        try:
            self.vm.put(name.strip(), float(value), float(sig) if sig.strip() else None)
        except (ValueError, TalkError) as e:
            self.write(f"  ? {e}  (put NAME = value)")
            return
        self.write(f"  {name.strip()} <- {value.strip()}")

    def do_run(self, arg):
        """run FILE.grm: says every statement of a file (= use)"""
        self.default("use " + arg.strip())

    def do_load(self, arg):
        """load FILE.csv | FILE.json: data, row by row: the network learns from it"""
        path = arg.strip()
        if not os.path.exists(path) and os.path.exists(os.path.join(HERE, path)):
            path = os.path.join(HERE, path)
        try:
            self.write("  " + self.vm.load(path))
        except (OSError, ValueError, TalkError) as e:
            self.write(f"  ? {e}")

    # --------------------------------------------------------------- looking
    def do_ask(self, arg):
        """ask NODE: its value (± what the messages say of its uncertainty)"""
        name = arg.strip()
        if name not in self.vm.net.nodes:
            self.write(f"  ? no node {name}")
            return
        m = self.vm.m()
        m.run(5000)
        sg = m.sigma(name)
        unit = "" if self.vm.dim(name) else ""
        self.write(f"  {name} = {fmt(self.vm.get(name))}{unit}" + (f"  (± {sg:.3g} inside)" if sg < 1e5 else ""))

    def do_outputs(self, arg):
        """outputs: what the network gives out (and how surprised it was by its last inputs)"""
        for o in self.vm.outputs():
            self.write(f"    {o:>12} = {fmt(self.vm.get(o))}")
        h = self.vm.history.get("surprise")
        if h:
            self.write(f"    {'surprise':>12} = {h[-1]:.3g} sigma (how far the last inputs were from what it expected)")

    def do_show(self, arg):
        """show: what the network is"""
        n = self.vm.net
        roles = {r: [k for k, s in n.nodes.items() if s.get(r)] for r in ("var", "learn", "input", "output")}
        self.write(f"  {len(n.nodes)} nodes, {len(n.relations)} relations, {len(n.sets)} writes at each tick, "
                   f"{len(n.networks)} networks" + (f" ({', '.join(n.networks)})" if n.networks else ""))
        for r, ks in roles.items():
            if ks:
                self.write(f"    {r}: {', '.join(ks[:20])}" + (" ..." if len(ks) > 20 else ""))
        if len(n.relations) <= 30:
            for r in n.relations:
                self.write(f"    {r['name']}: {r['text']}")
            for st in n.sets:
                self.write(f"    set {st['target']} <- {st['source']}")
        if self.vm.machine:
            m = self.vm.machine
            self.write(f"  {m.processors()} processors, tick {m.ticks}, round {m.rounds}")

    # --------------------------------------------------------------- memory
    def do_sleep(self, arg):
        """sleep [FILE.json]: the network and every message to its memory"""
        self.vm.sleep(arg.strip() or None)
        self.write(f"  asleep in {arg.strip() or self.vm.memory}")

    def do_wake(self, arg):
        """wake [FILE.json]: back as it was put to sleep"""
        try:
            self.vm.wake(arg.strip() or None)
        except (OSError, TalkError, ValueError) as e:
            self.write(f"  ? {e}")
            return
        self.write(f"  awake at tick {self.vm.machine.ticks}")

    def do_blank(self, arg):
        """blank: forget everything (the memory file stays until the next sleep)"""
        self.vm.blank()
        self.write("  blank")

    # --------------------------------------------------------------- the body
    def do_sound(self, arg):
        """sound on | off: hear the outputs at each tick"""
        self.sound = arg.strip().lower() != "off"
        self.write(f"  sound {'on' if self.sound else 'off'}")

    def do_clock(self, arg):
        """clock HZ: ticks by themselves, HZ a second (window only; 0: only on Enter)"""
        try:
            self.clock = max(0.0, float(arg))
        except ValueError:
            self.write("  clock HZ")
            return
        self.write(f"  clock {self.clock:g} Hz")

    def do_help(self, arg):
        if arg:
            return super().do_help(arg)
        self.write("""  the network   var x = 0            a variable (held until written again)
                set x = x + 1 [when s in 0.5 .. 1.5]   written at each tick: loops and choices
                relate r: y = k * x + c [± 0.5] [when ...]   a relation (products, sums), only while...
                learn k = 0          a weight: it keeps what it learns (with the weights it shares relations with)
                fuse A B             B was A under another name: one node (the machine also does it by itself)
                input x [= v]        output y           node NAME [M L T Q K]
                network NAME(a, b) ... end      call NAME(a=.., b=..)      use FILE.grm
  running       Enter: one tick      tick [n]           put NAME = value      load FILE.csv | FILE.json
  looking       ask NODE             outputs            show
  memory        sleep [FILE]         wake [FILE]        blank      (quit puts it to sleep)
  the body      sound on | off       clock HZ (window)
                quit""")

    def do_quit(self, arg):
        """quit: the machine goes to sleep in its memory"""
        if self.vm.net.nodes and self.vm.memory:
            for line in self.vm.sleep(night=True):
                self.write(f"  {line}")
            self.write(f"  asleep in {self.vm.memory}")
        return True

    do_exit = do_quit
    do_EOF = do_quit


def main(argv):
    vm = VM(blank="--blank" in argv)
    argv = [a for a in argv if a != "--blank"]
    if "--window" in argv:
        body.window(vm, Shell)
        return
    shell = Shell(vm)
    if argv and argv[0] == "-c":
        shell.write(shell.intro)
        shell.onecmd(" ".join(argv[1:]))
        return
    try:
        shell.cmdloop()
    except KeyboardInterrupt:
        shell.do_quit("")


if __name__ == "__main__":
    main(sys.argv[1:])
