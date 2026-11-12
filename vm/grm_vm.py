# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Anthony Charretier
"""The GRM virtual machine: a network that is the program, the memory and the calculator at once, and the few
drivers that are its body (keyboard and files in, screen and sound out for a human).

    python vm/grm_vm.py                  the machine in the terminal
    python vm/grm_vm.py --window         the machine in a window: the outputs shown and heard
    python vm/grm_vm.py --blank          start from a blank network (the memory is not read)
    python vm/grm_vm.py -c "use programs/double.grm; tick 20; outputs"
    python vm/grm_vm.py --window -c "use programs/fall.grm"     the window, with commands said at the start

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
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from language import Network, TalkError, from_store, normal, statement   # noqa: E402
from runtime import Machine   # noqa: E402
import body   # noqa: E402
import guide   # noqa: E402
import i18n   # noqa: E402
import programs   # noqa: E402
from i18n import label, tr   # noqa: E402
import debug   # noqa: E402
import diagnose   # noqa: E402
import editor   # noqa: E402
import files   # noqa: E402
import journal   # noqa: E402
import senses   # noqa: E402
import graph   # noqa: E402
import mind   # noqa: E402

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


def group_of(line):
    """The group a line typed at the prompt belongs to: the program it uses, the call it makes, or what was typed."""
    word, _, rest = normal(line).split("#", 1)[0].strip().partition(" ")
    if word == "use" and rest.strip():
        return os.path.splitext(os.path.basename(rest.strip().strip('"')))[0]
    if word == "call":
        m = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*\((.*)\)", rest)
        if m:
            first = m.group(2).split(",")[0].split("=")[-1].strip()
            return f"{m.group(1)}({first})" if first else m.group(1)
    return "typed"


def number(v):
    """A cell as a number: 3.14, 3,14 (a decimal comma), 1 234,5 or 1,234.5 (thousands), 12% ; None if it is not one."""
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    if not isinstance(v, str):
        return None
    t = v.strip().replace("\u00a0", "").replace("\u202f", "").replace(" ", "")
    if not t:
        return None
    percent = t.endswith("%")
    t = t.rstrip("%")
    if "," in t and "." in t:                      # 1,234.5 or 1.234,5: the last one is the decimal point
        t = t.replace(",", "") if t.rfind(".") > t.rfind(",") else t.replace(".", "").replace(",", ".")
    elif "," in t:
        t = t.replace(",", ".") if t.count(",") == 1 else t.replace(",", "")
    try:
        x = float(t)
    except ValueError:
        return None
    return x / 100.0 if percent else x


def name_of(column):
    """A column's header as a node's name: letters without accents, digits and _ (CO2 (ppm) -> CO2_ppm, Année ->
    Annee, 2020 -> _2020)."""
    import unicodedata
    t = unicodedata.normalize("NFKD", column.strip())
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    t = re.sub(r"[^A-Za-z0-9_]+", "_", t).strip("_")
    if not t:
        return ""
    return "_" + t if t[0].isdigit() else t


def read_table(path):
    """The rows of a CSV as written by any program: UTF-8 (with or without BOM) or Windows' own encoding, separated
    by , ; or tabs, decimal points or commas. Returns (rows, {header: the name it became}) ."""
    with open(path, "rb") as f:
        raw = f.read()
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return [], {}
    sample = "\n".join(lines[:20])
    try:
        sep = csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        sep = max(",;\t", key=lambda d: lines[0].count(d))
    reader = csv.reader(lines, delimiter=sep)
    header = next(reader)
    names, renamed = [], {}
    for h in header:
        n = name_of(h)
        base, k = n, 2
        while n and n in names:                    # two columns that would get one name
            n, k = f"{base}_{k}", k + 1
        names.append(n)
        if n and n != h.strip():
            renamed[h.strip()] = n
    rows = [{n: cell for n, cell in zip(names, rec) if n} for rec in reader]
    return rows, renamed


class VM:
    """The machine: a network, its relational machine, its memory file."""

    def __init__(self, memory=MEMORY, blank=False):
        self.memory = memory
        self.net = Network()
        self.machine = None
        self.note = "blank"
        self.history = {}           # output -> recent values (for the body); "surprise" too
        self.past = []              # the values of the last ticks (the master equation at t - n)
        self.events = []            # what the machine has to say by itself (errors, warnings, what it did)
        self._read = set()          # the nodes read since the last tick (their use)
        self._reported = set()      # relations already said to be far from holding
        self.clock_hz = 0.0         # the clock the body runs it at (0: only on Enter)
        self._loading = False
        self.watches = []           # breakpoints (debug.Watch): the clock stops when one is met
        self.stopped = []           # what the last tick or step stopped on
        self.stepping = False       # step by step: nothing runs but a round at a time (until tick or play)
        self.on_progress = None     # the body shows how far a long piece of work is: (done, total, what)
        self.focus = None           # what the human looks at: ("group" | "node" | "relation" | "between", names...)
        self.group = None           # the group what is said now belongs to (a file being loaded, a tab being run)
        if not blank and memory and os.path.exists(memory):
            try:
                self.machine = Machine.wake(memory)
                self.net = self.machine.net
                self.note = tr("woke from {file} (tick {tick})", file=os.path.basename(memory), tick=self.machine.ticks)
                journal.write(self.net, "woke", nodes=len(self.net.nodes), relations=len(self.net.relations))
                return
            except Exception as e:  # noqa: BLE001 - an unreadable memory: start from the base, say why
                self.note = tr("{file} not usable ({error}): ", file=os.path.basename(memory), error=e)
        else:
            self.note = ""
        if not blank and os.path.exists(BASE):
            statement(self.net, "use base.grm", HERE)
            mind.mark(self.net, set(), set(), "base")
            self.join("base", set(), set())
            self.note += tr("born with its base ({n} points of the world)", n=len(self.net.nodes))
            self.born_with_base = True
            journal.write(self.net, "born", nodes=len(self.net.nodes))
        else:
            self.note += tr("a blank machine")
            journal.write(self.net, "born", nodes=0)

    # ------------------------------------------------------------------ the network
    def say(self, line, base=None, group=None):
        """A statement of the language. The machine is rebuilt when the network changes; what the network holds
        (variables, weights, measurements) is kept, so it settles again from where it was. What it adds joins a group:
        the program it comes from (use), the call (call), or what was typed."""
        nodes, relations = set(self.net.nodes), {r["name"] for r in self.net.relations}
        said = statement(self.net, line, base or HERE)
        mind.mark(self.net, nodes, relations, "written")
        name = group or self.group or group_of(line)
        if self.join(name, nodes, relations) and name not in ("typed",):
            self.focus = ("group", name)             # a program or a call just said: looked at
            if group is None and self.group is None:  # a program used or a network called: a line in the logbook
                nodes_g, rels_g = graph.groups(self.net).get(name, ((), ()))
                journal.write(self.net, "program", name=name, nodes=len(nodes_g), relations=len(rels_g))
        self.events += diagnose.names(self.net, nodes, line)
        if said is not None and self.net.recording is None and said:
            if not self._measure_in_place(line, nodes, relations):
                self.machine = None
        return said

    def _measure_in_place(self, line, nodes, relations):
        """observe / forget of a node the machine already has: heard by its node, as an input is (put), instead of
        building the machine again. Then it goes through the network round by round like anything new."""
        m = self.machine
        if m is None or set(self.net.nodes) != nodes or {r["name"] for r in self.net.relations} != relations:
            return False
        word, _, rest = normal(line).split("#", 1)[0].strip().partition(" ")
        name = re.split(r"[\s=]", rest.strip(), maxsplit=1)[0] if rest.strip() else ""
        name = self.net.aliases.get(name, name)
        if word not in ("observe", "forget") or name not in m.index or name.startswith("~"):
            return False
        m.set_anchor(name)
        m.dirty_factors.add(m._anchor_index[name])
        return True

    def m(self):
        """The relational machine, built again when the network has changed, and settled at once, but step by step:
        then what a new relation changes is left to the rounds (step), where it can be seen."""
        if self.machine is None:
            self.machine = Machine(self.net)
            if not self.holding():
                self.machine.run(5000)
        return self.machine

    def join(self, name, nodes, relations):
        """What was added since (nodes, relations) joins group `name`: its new relations, their nodes, its new nodes.
        Returns whether anything joined."""
        net = self.net
        new_rel = [r for r in net.relations if r["name"] not in relations]
        new_nodes = {n for n in net.nodes if n not in nodes}
        for r in new_rel:
            new_nodes |= {n for n in net.nodes_of(r) if n in net.nodes}
        if not new_rel and not new_nodes:
            return False
        g = net.groups.setdefault(name, {"nodes": [], "relations": []})
        g["nodes"] += [n for n in sorted(new_nodes) if n not in g["nodes"]]
        g["relations"] += [r["name"] for r in new_rel if r["name"] not in g["relations"]]
        return True

    def progress(self, done, total, what):
        if self.on_progress is not None:
            self.on_progress(done, total, what)

    def holding(self):
        """Whether the machine runs only a round at a time: step by step, or inside a tick stepped into."""
        return self.stepping or self.in_tick()

    def settle(self):
        """Everything new heard, as a look at the machine expects it (but not step by step)."""
        m = self.m()
        if not self.holding():
            m.run(5000)
        return m

    def peek(self, name):
        """A node's value as it is now, without running the machine (the body draws with it)."""
        return self.m().value_si(name)

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
            raise TalkError(tr("{name} is a positive quantity", name=name))
        self.m().observe(name, value, sigma)
        h = self.net.seen.setdefault(name, [])
        h.append(value)
        del h[:-SEEN]

    def get(self, name):
        m = self.settle()        # what it says once it has heard everything new (step by step: what it says now)
        self._read.add(name)
        return m.value_si(name)

    def outputs(self):
        return [n for n, s in self.net.nodes.items() if s.get("output")]

    def in_tick(self):
        """Whether a tick has been started a round at a time (step) and not finished."""
        return self.machine is not None and getattr(self.machine, "_tick", None) is not None

    def _begin(self, m, learn=False):
        m.last_surprise = {}
        m.begin_tick(learn)
        m._tick["r0"] = m.rounds
        m._tick["learn"] = learn

    def tick(self, n=1, learn=False, max_rounds=2000):
        """n ticks (a tick stepped into is finished first). Stops early when a watch is met (self.stopped)."""
        writes = {}
        self.stopped = []
        self.stepping = False
        for _ in range(n):
            m = self.m()
            if not self.in_tick():
                self._begin(m, learn)
            m.run(max(1, max_rounds - (m.rounds - m._tick["r0"])))
            writes = self._finish(m)
            if self.watches and self.machine is not None:
                self.machine.run(5000)       # what the writes change, settled, before the watches look
            if self._stop():
                break
        return writes

    def step(self, n=1):
        """n rounds, one at a time: [{"tick", "round", "moved", "worked"} | {"tick", "done", "rounds"}]. A tick
        begins when needed and ends (with its writes) when nothing new is said. Stops early when a watch is met."""
        report = []
        self.stopped = []
        self.stepping = True
        for _ in range(n):
            m = self.m()
            if not self.in_tick():
                self._begin(m)
            if not m.quiet:
                before = set(m.dirty_nodes)
                was = {i: m.x[i] for i in before}
                fresh = set(m.dirty_factors)
                m.round()
                moved, worked = debug.round_report(m, before, m.busy, was, fresh)
                report.append({"tick": m.ticks, "round": m.rounds - m._tick["r0"], "moved": moved,
                               "worked": worked})
            if m.quiet:
                rounds = m.rounds - m._tick["r0"]
                writes = self._finish(m, settle=False)
                report.append({"tick": m.ticks, "done": writes, "rounds": rounds})
            if self._stop():
                break
        return report

    def _stop(self):
        said = debug.check(self)
        if said:
            self.stopped = said
            self.events += said
        return bool(said)

    def _finish(self, m, settle=True):
        """The end of a tick: its writes, then what the machine keeps, says and feels of it. settle=False (stepping a
        round at a time): the outputs are read as they are, and what the writes change is left to the rounds of the
        next tick, where it can be seen."""
        r0, learn = m._tick["r0"], m._tick.get("learn", False)
        writes = m.end_tick()
        settled = m.settled
        mind.measure(self.net, m.rounds - r0, self.clock_hz)
        for o in self.outputs():
            self.remember(o, self.get(o) if settle else m.value_si(o))
        z = list(m.last_surprise.values())
        surprise = None
        if z:   # how far the inputs were from what the network expected of them (rms, in sigmas)
            surprise = math.sqrt(sum(v * v for v in z) / len(z))
            self.remember("surprise", surprise)
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
        # what is wrong is said (and felt: an error is displeasure)
        problems = diagnose.machine(m, settled, self._reported)
        if any(p.startswith(label("error")) for p in problems):
            mind.reward(self.net, -0.5)
        self.events += problems
        # what it feels and keeps, and what it does by itself to flourish
        expected = mind.mood(self.net).get("expected") or 0.0
        if surprise is not None and not self._loading and surprise >= max(senses.SURPRISED, 2 * expected) \
                and self.net.ticks - getattr(self, "_surprised_at", -99) >= 10:
            self._surprised_at = self.net.ticks         # a surprise worth a line (not one a tick)
            where = sorted(((abs(v), k) for k, v in (m.last_surprise or {}).items()), reverse=True)[:2]
            journal.write(self.net, "surprise", sigma=surprise, where=[(k, v) for v, k in where])
        self.events += mind.after_tick(self, surprise, explore=not self._loading)
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
        renamed = {}
        if path.lower().endswith((".csv", ".tsv", ".txt")):
            rows, renamed = read_table(path)
        else:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and "networks" in data:
                sys.path.insert(0, os.path.join(os.path.dirname(HERE), "equation"))
                from store import load_grm_network_safely   # noqa: E402
                _, left_out = from_store(load_grm_network_safely(path), self.net)
                self.machine = None
                return tr("network loaded: {nodes} nodes, {relations} relations", nodes=len(self.net.nodes),
                          relations=len(self.net.relations)) + (
                    " (" + tr("{n} left out", n=len(left_out)) + ")" if left_out else "")
            if isinstance(data, list):
                rows = data
            elif isinstance(data, dict) and all(isinstance(v, list) for v in data.values()):
                n = min(len(v) for v in data.values())
                rows = [{k: v[i] for k, v in data.items()} for i in range(n)]
            elif isinstance(data, dict):
                rows = [data]
            else:
                raise TalkError(tr("JSON data: a list of records, {{name: [values]}} or {{name: value}}"))
        weights = [n for n, s in self.net.nodes.items() if s.get("learn")]
        before = {w: self.get(w) for w in weights}
        used = 0
        self._loading = True
        group = os.path.splitext(os.path.basename(path))[0]
        nodes0, relations0 = set(self.net.nodes), {r["name"] for r in self.net.relations}
        self.group = group
        what = tr("rows")
        try:
            for k_row, rec in enumerate(rows, 1):
                self.progress(k_row, len(rows), what)
                given = False
                for k, v in rec.items():
                    x = number(v)
                    if x is None:
                        continue
                    k = k.strip()
                    if not k:
                        continue
                    self.put(k, x)
                    given = True
                if given:
                    self.tick(learn=True)
                    used += 1
        finally:
            self._loading = False
            self.group = None
        out = tr("{n} rows learned", n=used)
        if renamed:
            out += "\n    " + tr("columns named as the machine can write them: {names}", names=", ".join(
                f"'{a}' -> {b}" for a, b in renamed.items()))
        for w in weights:
            out += f"\n    {w}: {fmt(before[w])} -> {fmt(self.get(w))}  (± {self.m().sigma(w):.3g})"
        self.progress(None, None, tr("looking for what it has not been told"))
        journal.write(self.net, "file", name=os.path.basename(path), rows=used,
                      columns=sorted({k for r in rows[:1] for k in r}))
        for line in self.grow():
            out += f"\n    {line}"
        self.join(group, nodes0, relations0)                 # the file's inputs, and what was found in them
        self.focus = ("group", group)
        return out

    # ------------------------------------------------------------------ what the machine does by itself
    def grow(self):
        """Everything the machine does by itself with what it has seen, after a file and at night: it fuses what is
        one thing under two names, writes the relations that hold among its inputs and that it did not know, and makes
        a node appear where a relation keeps missing something. Returns what it did, in words."""
        nodes, relations = set(self.net.nodes), {r["name"] for r in self.net.relations}
        fused = self.self_fuse()
        found0 = len(self.net.found)
        done = fused + self.self_discover()
        hidden = self.self_hidden()
        done += hidden
        for f in self.net.found[found0:]:                # what it found, in its logbook, as a human likes to read it
            mo = senses.discovery(self, f)
            xs, ys = mo["points"]
            step = max(1, len(xs) // 80)
            journal.write(self.net, "discovery", text=mo["text"], sentence=mo["sentence"], r2=mo["r2"],
                          rows=mo["rows"], points=[list(xs[::step]), list(ys[::step])])
        for line in fused + hidden:
            journal.write(self.net, "found", text=line)
        mind.mark(self.net, nodes, relations, "found")
        self.join("found", nodes, relations)
        if done:
            mind.reward(self.net, 0.6)      # finding something by itself: a burst of pleasure
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
            terms = rel.get("terms")
            self.net.found.append({"relation": name, "kind": rel["kind"], "text": rel["text"], "r2": rel["r2"],
                                   "rows": rel["rows"], "tick": self.net.ticks, "target": rel.get("target"),
                                   "powers": {k: float(v) for k, v in terms.items()} if isinstance(terms, dict) and
                                   all(isinstance(v, (int, float)) for v in terms.values()) else {},
                                   "meaning": {k: float(v) for k, v in (rel.get("meaning") or {}).items()
                                               if isinstance(v, (int, float))}})
            self.machine = None
            extra = ""
            mean = rel.get("meaning", {})
            if "period" in mean:
                extra = "; " + tr("an oscillation: period {p} moments, {d} left each moment", p=f"{mean['period']:.4g}",
                                  d=f"{mean['damping']:.4g}")
            elif "half_life" in mean:
                extra = "; " + tr("a decay: half-life {h} moments", h=f"{mean['half_life']:.4g}")
            elif "doubling" in mean:
                extra = "; " + tr("a growth: doubles in {d} moments", d=f"{mean['doubling']:.4g}")
            done.append(tr("found by itself: {text} (relation {name}, r² {r2} over {rows} rows{extra})",
                           text=rel["text"], name=name, r2=f"{rel['r2']:.6f}", rows=rel["rows"], extra=extra))
        return done

    def _dimv(self, name):
        """The dimension of a node, [M L T Q K] (zeros for a pure number)."""
        d = self.net.nodes.get(name, {}).get("dim")
        return [float(x) for x in d] if d else [0.0] * 5

    @staticmethod
    def _dim_text(d):
        if d is None or all(abs(x) < 1e-12 for x in d):
            return ""
        return " [" + " ".join(f"{x:g}" for x in d) + "]"

    @staticmethod
    def _combine(*parts):
        """sum of k * dim over (k, dim)."""
        out = [0.0] * 5
        for k, d in parts:
            out = [a + k * b for a, b in zip(out, d)]
        return out

    def _weight(self, name, value, sigma, positive=False, dim=None):
        """A weight the machine writes for itself. Its dimension balances the relation it is in: inside, the machine
        counts in its own units (c = hbar = G = kB = 1), so a relation is only right in SI if its two sides have the
        same dimension."""
        statement(self.net, f"learn {name} = {value!r}" + (" positive" if positive else "") + self._dim_text(dim))
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
        dim = self._combine((1, self._dimv(rel["target"])), *((-p, self._dimv(x)) for x, p in rel["terms"].items()))
        K = self._weight(f"K_{k}", rel["constant"], rel["constant_sigma"], positive=True, dim=dim)
        right = " * ".join([K] + [f"{x}^{p!r}" for x, p in rel["terms"].items()])
        statement(self.net, f"relate {name}: {rel['target']} = {right} ± {max(rel['sigma'], 1e-4)!r} dex")

    def _write_linear(self, rel, name, k):
        (x, a), b = next(iter(rel["terms"].items())), rel["constant"]
        dy = self._dimv(rel["target"])
        sa = self._weight(f"a_{k}", a, rel.get("slope_sigma", 1.0), dim=self._combine((1, dy), (-1, self._dimv(x))))
        sb = self._weight(f"b_{k}", b, rel["constant_sigma"], dim=dy)
        statement(self.net, f"relate {name}: {rel['target']} = {sa} * {x} + {sb} ± {max(rel['sigma'], 1e-9)!r}")

    def _write_exponential(self, rel, name, k):
        # y = A e^(kx)  <=>  ln y = k x + ln A: a straight line between x and the exponent of y
        (x, kk), A = next(iter(rel["terms"].items())), rel["constant"]
        L = self._ln(rel["target"])
        sk = self._weight(f"k_{k}", kk, abs(kk) * 1e-3 + 1e-9, dim=self._combine((-1, self._dimv(x))))
        sa = self._weight(f"lnA_{k}", math.log(A), rel["constant_sigma"] * math.log(10))
        statement(self.net, f"relate {name}: {L} = {sk} * {x} + {sa} ± {max(rel['sigma'] * math.log(10), 1e-9)!r}")

    def _write_log(self, rel, name, k):
        (x, a), b = next(iter(rel["terms"].items())), rel["constant"]
        L = self._ln(x)
        dy = self._dimv(rel["target"])
        sa = self._weight(f"a_{k}", a, abs(a) * 1e-3 + 1e-9, dim=dy)
        sb = self._weight(f"b_{k}", b, rel["constant_sigma"], dim=dy)
        statement(self.net, f"relate {name}: {rel['target']} = {sa} * {L} + {sb} ± {max(rel['sigma'], 1e-9)!r}")

    def _write_sum(self, rel, name, k):
        # a sum built on products: each product its own node (found once, used by every relation that needs it),
        # then the sum of those nodes
        parts = []
        dy = self._dimv(rel["target"])
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
                    dim = self._combine(*((p, self._dimv(x)) for x, p in mono.items()))
                    if self._dim_text(dim):
                        self.net.nodes[node]["dim"] = dim     # the product carries the dimension of its factors
            w = self._weight(f"a{j + 1}_{k}", a, abs(a) * 1e-3 + 1e-9,
                             dim=self._combine((1, dy), (-1, self._dimv(node))))
            parts.append(f"{w} * {node}")
        b = self._weight(f"b_{k}", rel["constant"], rel["constant_sigma"], dim=dy)
        statement(self.net, f"relate {name}: {rel['target']} = " + " + ".join(parts)
                  + f" + {b} ± {max(rel['sigma'], 1e-9)!r}")

    def _write_dynamics(self, rel, name, k):
        # what carries x from one moment to the next: its past is a variable written at each tick
        x = rel["target"]
        last = [r[x] for r in self.net.rows if x in r][-2:]
        before, before2 = f"{x}_before", f"{x}_before2"
        dx = self._dim_text(self._dimv(x))
        statement(self.net, f"var {before} = {last[-1]!r}" + dx)
        terms = [f"{self._weight(f'a1_{k}', rel['lags'][0], 1e-3 * abs(rel['lags'][0]) + 1e-9)} * {before}"]
        if len(rel["lags"]) > 1:
            statement(self.net, f"var {before2} = {last[0]!r}" + dx)
            terms.append(f"{self._weight(f'a2_{k}', rel['lags'][1], 1e-3 * abs(rel['lags'][1]) + 1e-9)} * {before2}")
            statement(self.net, f"set {before2} = {before}")
        statement(self.net, f"set {before} = {x}")
        c = self._weight(f"c_{k}", rel["constant"], rel["sigma"] + 1e-9, dim=self._dimv(x))
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
                statement(self.net, f"learn {h} = {value!r}" + self._dim_text(self._sum_dim(rel)))
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
            done.append(tr("a node nobody mentioned: {h} = {value} in {rel} (it kept missing the data on the same side: "
                           "{t} sigma over {rows} rows)", h=h, value=f"{value:.6g}", rel=rel["name"],
                           t=f"{verdict['t']:.1f}", rows=verdict["rows"]))
        return done

    def _drift(self, rel, drift, res):
        """A node nobody mentioned that changes from moment to moment: a hidden variable with its own law
        (h = rho h_before), which the relation's data move each moment and the law carries to the next."""
        k = sum(1 for n in self.net.nodes if n.startswith("drift_") and not n.endswith("_before")) + 1
        h, before = f"drift_{k}", f"drift_{k}_before"
        sigma = max(rel["sigma"], 1e-6)
        last = -res[-1] * sigma
        dim = self._dim_text(self._sum_dim(rel))
        statement(self.net, f"node {h} = {last!r} signed" + dim)
        statement(self.net, f"var {before} = {last!r}" + dim)
        rho = self._weight(f"rho_{k}", drift["rho"], 0.05)
        statement(self.net, f"relate {h}_law: {h} = {rho} * {before} ± {max(drift['sigma'] * sigma, 1e-9)!r}")
        statement(self.net, f"set {before} = {h}")
        rel["terms"].append((1.0, {h: 1.0}))
        rel["text"] += f"  [+ {h}]"
        self.net.tension[rel["name"]] = []
        self.machine = None
        return tr("a node nobody mentioned, that changes: {h} in {rel} (its misses followed each other: each one {rho} "
                  "of the one before, over {rows} rows)", h=h, rel=rel["name"], rho=f"{drift['rho']:.2f}",
                  rows=drift["rows"])

    def _sum_dim(self, rel):
        """The dimension of a sum relation's terms (that of its first node with one)."""
        for _, t in rel["terms"]:
            for n in t:
                if self.net.nodes.get(n, {}).get("dim"):
                    return self._dimv(n)
        return None

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
                done.append(tr("{gone} looks like {keep} ({why}) but stays apart: {error}", gone=gone, keep=keep,
                               why=tr(why) if isinstance(why, str) else why, error=e))
                self._refused = getattr(self, "_refused", set()) | {(keep, gone) + (("inverse",) if inverse else ())}
                continue
            self.net.fusions.append({"keep": keep, "gone": gone, "why": why, "tick": self.net.ticks,
                                     "inverse": inverse})
            self.machine = None
            done.append(tr("fused by itself: {gone} is {keep}", gone=gone, keep=keep) + ("^-1" if inverse else "")
                        + f" ({tr(why)})")

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
                return best[0][1], b, tr("{mean} held still, {a} is {va}, {t} sigma apart", mean=f"{mean:.6g}",
                                         a=best[0][1], va=f"{m.value_si(best[0][1]):.6g}", t=f"{best[0][0]:.2g}")
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
        if self.in_tick():                   # a tick stepped into is finished before it sleeps
            self.tick()
        if night:
            day = journal.today(self.net)
            done = self.grow()               # at night, the machine puts together what it has seen
            pruned = mind.prune(self, night=True)   # and forgets what it no longer uses
            done += pruned
            # the weights loosen, less those that learned under pleasure, more those that learned under displeasure
            self.m().downscale(NIGHT, mind.night_factors(self.net, NIGHT))
            tags = mind.mood(self.net)["tags"]
            for w in tags:
                tags[w] *= 0.5
            day = day + journal.today(self.net)[len(day):]
            journal.write(self.net, "night", discoveries=sum(1 for e in day if e["kind"] == "discovery"),
                          files=sum(1 for e in day if e["kind"] == "file"),
                          surprises=sum(1 for e in day if e["kind"] == "surprise"),
                          flourishing=mind.mood(self.net).get("flourishing", 1.0), done=list(pruned))
        self.m().sleep(path or self.memory)
        return done

    def wake(self, path=None):
        self.machine = Machine.wake(path or self.memory)
        self.net = self.machine.net
        self.past = []
        self._reported = set()

    def blank(self):
        self.net = Network()
        self.machine = None
        self.history = {}
        self.past = []
        self._reported = set()

    def pop_events(self):
        out, self.events = self.events, []
        return out


WATCH_KINDS = {"when": "stops when it becomes true", "change": "stops when it changes",
               "holds": "stops when it no longer holds"}


YES = ("y", "yes", "o", "oui")
HISTORY = 1000     # lines typed kept from session to session
SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


def progress_text(done, total, what):
    """How far a long piece of work is: a bar and a count, or only what it is doing."""
    if done is None or not total:
        return what or ""
    width = 20
    full = int(width * done / total)
    return "[" + "█" * full + "·" * (width - full) + f"] {done}/{total} {what}"


class Shell(cmd.Cmd):
    @property
    def prompt(self):
        """grm, the folder it is in, and >: the human has the hand."""
        return f"grm {files.short()}> "
    WORDS = ("node", "relate", "observe", "forget", "keep", "network", "call", "use", "end", "var", "set",
             "learn", "input", "output", "fuse")
    WINDOW_ONLY = ("open", "tab", "close", "edit", "save", "find")

    def __init__(self, vm, out=None, settings=None):
        super().__init__(stdout=out)
        self.vm = vm
        self.write = (lambda t: print(t)) if out is None else (lambda t: out.write(t + "\n"))
        self.base = HERE
        self.sound = False
        self.clock = 0.0
        self.last_clock = 0.0       # the last clock that ran (play starts it again)
        self.programs = None        # the programs window (body.py), when there is one
        self.on_help = None         # what the window does when the typing help is turned on or off
        self.on_clear = None        # what the window does to clear its words
        self.logbook = None         # the window of the logbook, when there is one
        self.tour_at = 0
        self.asking = None          # a question waiting for its answer: ("rm", paths)
        self.history = []
        self.feel = senses.Feel()   # what the machine feels, followed for the body
        self.feel.found = len(vm.net.found)        # what it found before this session is not a moment now
        self.ambient = None         # the ambient sound, when it plays (ambient.py)
        self._listening = None      # in the terminal: the thread that tells the sound what the machine feels
        self.marks = []             # lines of programs to turn red in their tabs
        # in a terminal, long work is run aside while a wheel turns (the window does it its own way)
        self.wheel = out is None and getattr(sys.stdout, "isatty", lambda: False)()
        self._aside = False
        # the settings (language, typing help) are remembered next to the memory; a machine without memory (tests)
        # neither reads nor writes them, and speaks English
        self.settings_path = settings if settings is not None else (
            os.path.join(os.path.dirname(os.path.abspath(vm.memory)), "settings.json") if vm.memory else None)
        self.settings = i18n.load_settings(self.settings_path)
        self.history_path = os.path.join(os.path.dirname(self.settings_path), "history.txt") if self.settings_path \
            else None
        self.history = self.load_history()
        # the folder it was in when it was left: the prompt starts there again (no path to type again)
        where = self.settings.get("cwd") if self.settings_path else None
        if where and os.path.isdir(where):
            try:
                os.chdir(where)
            except OSError:
                pass
        if self.settings_path and self.settings.get("focus"):
            self.vm.focus = tuple(self.settings["focus"])
        self.last_clock = float(self.settings.get("clock") or 0.0)
        if self.settings_path:
            i18n.set_lang(self.settings.get("lang") or i18n.system_lang())
        enc = getattr(sys.stdout, "encoding", None) if out is None else "utf-8"
        self.intro = (editor.banner(enc) + "\n  " + tr("{note}.", note=self.note()) + "\n  "
                      + tr("Talk to it in its words (relate, observe, var, set, learn, input, output...); Enter alone: "
                           "one tick; Tab completes; help: the words; tour: a guided tour; lang fr / lang en."))

    def note(self):
        return self.vm.note

    def keep_state(self):
        """What the human leaves as it is, kept for the next time: the folder, what is looked at, the sound."""
        if not self.settings_path:
            return
        self.settings["cwd"] = os.getcwd()
        self.settings["focus"] = list(self.vm.focus) if self.vm.focus else None
        self.ambient_settings()["on"] = self.ambient is not None
        self.settings["clock"] = self.last_clock
        self.save_settings()

    def save_settings(self):
        i18n.save_settings(self.settings_path, self.settings)

    def emptyline(self):
        self.do_tick("")

    def commands(self):
        return [n[3:] for n in self.get_names() if n.startswith("do_") and n not in ("do_EOF",)]

    def precmd(self, line):
        """A line typed in the terminal: remembered (from session to session), its short form made whole."""
        self.add_history(line)
        return self._expand(line)

    # --------------------------------------------------------------- what was typed, from session to session
    def load_history(self):
        if not self.history_path:
            return []
        try:
            with open(self.history_path, encoding="utf-8") as f:
                return [ln.rstrip("\n") for ln in f if ln.strip()][-HISTORY:]
        except OSError:
            return []

    def add_history(self, line):
        line = line.strip()
        if not line or (self.history and self.history[-1] == line) or self.asking is not None:
            return
        self.history.append(line)
        del self.history[:-HISTORY]
        if self.history_path:
            try:
                with open(self.history_path, "a", encoding="utf-8") as f:
                    f.write(line + "\n")
                if len(self.history) == HISTORY and os.path.getsize(self.history_path) > 4 * HISTORY * 80:
                    with open(self.history_path, "w", encoding="utf-8") as f:   # kept short
                        f.write("\n".join(self.history) + "\n")
            except OSError:
                pass

    # --------------------------------------------------------------- long work: shown as it goes
    def is_long(self, line):
        """A command that may take a while (a file, a night, many ticks): the body shows it going."""
        head, _, rest = self._expand(line.strip()).partition(" ")
        head = editor.whole(head.lower())
        if ";" in line:
            return any(self.is_long(p) for p in line.split(";"))
        if head in ("use", "load", "wake", "sleep", "prune"):
            return True
        if head == "run":
            return bool(rest.strip())
        if head in ("tick", "step"):
            try:
                return int(rest.strip() or 1) > 20
            except ValueError:
                return False
        return False

    def busy(self, line):
        """In the terminal: the line run aside while a wheel turns, with how far it is; then what it said."""
        import threading
        said, done = [], threading.Event()
        state = {"text": ""}
        write, self.write = self.write, said.append
        self.vm.on_progress = lambda d, t, what: state.update(text=progress_text(d, t, what))
        result = {}

        def work():
            try:
                result["stop"] = self.onecmd(line)
            finally:
                done.set()
        threading.Thread(target=work, daemon=True).start()
        k, t0 = 0, time.perf_counter()
        try:
            while not done.wait(0.1):
                if time.perf_counter() - t0 > 0.3:
                    sys.stdout.write("\r  " + SPINNER[k % len(SPINNER)] + " " + line.strip()[:50] + "  "
                                     + state["text"] + "\033[K")
                    sys.stdout.flush()
                    k += 1
        finally:
            if k:
                sys.stdout.write("\r\033[K")
            self.write = write
            self.vm.on_progress = None
        for s in said:
            self.write(s)
        return result.get("stop", False)

    def _expand(self, line):
        """A short form of a command at the head of the line is the whole command."""
        head, sep, rest = line.strip().partition(" ")
        if head.lower() in editor.SHORT_COMMANDS:
            return editor.SHORT_COMMANDS[head.lower()] + sep + rest
        return line

    def default(self, line):
        word = line.split()[0].lower() if line.split() else ""
        if self.vm.net.recording is not None or editor.whole(word) in self.WORDS:
            try:
                said = self.vm.say(line, self.base)
            except TalkError as e:
                self.write(f"  ? {e}")
                self.locate(str(e))
                mind.reward(self.vm.net, -0.2)
                return
            if said:
                self.write(f"  {said}")
            return
        like = diagnose.close(word, list(self.WORDS) + self.commands() + list(editor.SHORT))
        if like:
            self.write("  ? " + tr("'{word}' is not a word of the machine; did you mean {like}?", word=word,
                                   like=tr(" or ").join(like)))
        else:
            self.write("  ? " + tr("'{word}' is not a word of the machine (help)", word=word))

    def locate(self, message):
        """An error in a file: its line turns red in its tab (the programs window), once the window can draw it."""
        m = re.search(r"(?:in|dans) (\S+\.grm), (?:line|ligne) (\d+)", message)
        if m and self.programs is not None:
            self.marks.append((m.group(1), int(m.group(2))))
            import threading
            if threading.current_thread() is threading.main_thread():
                self.mark_errors()

    def mark_errors(self):
        while self.marks and self.programs is not None:
            self.programs.mark_error(*self.marks.pop(0))

    def onecmd(self, line):
        if self.wheel and not self._aside and self.asking is None and self.is_long(line):
            self._aside = True
            try:
                return self.busy(line)
            finally:
                self._aside = False
        try:
            if self.asking is not None:              # the answer to a question (rm: delete? y/n)
                return self.answer(line)
            if line.strip().startswith("!") and len(line.strip()) > 1:
                return self.again(line)
            if self.vm.net.recording is not None:
                self.default(line)
                return False
            if ";" in line:
                for part in line.split(";"):
                    if part.strip() and self.onecmd(self._expand(part.strip())):
                        return True
                return False
            return super().onecmd(self._expand(line))
        except Exception as e:  # noqa: BLE001 - an error of the machine is said, never a crash
            self.write("  ! " + diagnose.internal(e))
            mind.reward(self.vm.net, -0.5)
            return False
        finally:
            self.say_events()

    def say_events(self):
        for ev in self.vm.pop_events():
            # an error in red (!), a warning in amber (⚠): a warning is not an error
            mark = "!" if ev.startswith(("error", tr("error"))) else "⚠" if ev.startswith(("warning", tr("warning"))) \
                else "~"
            self.write(f"  {mark} {ev}")

    # --------------------------------------------------------------- Tab (terminal, with readline)
    def _complete(self, line, endidx):
        net = self.vm.net
        start, found = editor.complete(line, endidx, nodes=net.nodes, relations=[r["name"] for r in net.relations],
                                       commands=self.commands(), networks=net.networks, base=self.base,
                                       groups=self.group_names())
        return start, found

    def completenames(self, text, *ignored):
        return self.completedefault(text, text, 0, len(text))

    def completedefault(self, text, line, begidx, endidx):
        start, found = self._complete(line, endidx)
        cut = begidx - start
        return [f[cut:] for f in found if len(f) >= cut]

    def usage(self, word):
        self.write("  " + label("usage") + editor.DOCS[word][0])

    # --------------------------------------------------------------- running
    def do_tick(self, arg):
        """tick [n]: n ticks of the clock (Enter alone: one)"""
        try:
            n = int(arg) if arg.strip() else 1
        except ValueError:
            self.usage("tick")
            return
        m = self.vm.m()
        r0, t0 = m.rounds, m.ticks
        writes = self.vm.tick(n)
        m = self.vm.m()
        done = m.ticks - t0
        if n == 1:
            ws = ", ".join(f"{k} = {fmt(v)}" for k, v in writes.items() if "__" not in k)
            self.write("  " + tr("tick {tick}: {rounds} rounds", tick=m.ticks, rounds=m.rounds - r0)
                       + (f"; {ws}" if ws else ""))
        elif done < n:
            self.write("  " + tr("stopped after {done} of {n} ticks (now {tick})", done=done, n=n, tick=m.ticks))
        else:
            self.write("  " + tr("{n} ticks (now {tick}): {rounds} rounds", n=n, tick=m.ticks, rounds=m.rounds - r0))
        if self.vm.outputs():
            self.do_outputs("")
        if self.sound:
            body.play(body.sound_of(self.vm.history))

    def do_put(self, arg):
        """put NAME = VALUE [+/- sigma]: an input (in SI if the node has a dimension)"""
        name, _, rest = arg.replace("+/-", "±").partition("=")
        value, _, sig = rest.partition("±")
        try:
            self.vm.put(name.strip(), float(value), float(sig) if sig.strip() else None)
        except (ValueError, TalkError) as e:
            self.write(f"  ? {e}")
            self.usage("put")
            return
        self.write(f"  {name.strip()} <- {value.strip()}")

    def do_run(self, arg):
        """run [FILE.grm]: says every statement of a file (= use); no file: the open tab"""
        if not arg.strip():
            if self.programs is not None and self.programs.current() is not None:
                self.programs.run_current()
            else:
                self.usage("run")
            return
        path = programs.find(arg, self.base) or arg.strip()
        self.default("use " + path)

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
    def no_node(self, name, also=()):
        like = diagnose.close(name, list(self.vm.net.nodes) + list(also))
        self.write("  ? " + (tr("no node {name}; did you mean {like}?", name=name, like=tr(" or ").join(like)) if like
                             else tr("no node {name}", name=name)))

    def do_ask(self, arg):
        """ask NODE: its value (± what the messages say of its uncertainty)"""
        name = arg.strip()
        if name not in self.vm.net.nodes:
            self.no_node(name)
            return
        m = self.vm.m()
        m.run(5000)
        sg = m.sigma(name)
        self.write(f"  {name} = {fmt(self.vm.get(name))}" + ("  (± " + tr("{s} inside", s=f"{sg:.3g}") + ")"
                                                            if sg < 1e5 else ""))

    def do_outputs(self, arg):
        """outputs: what the network gives out (and how surprised it was by its last inputs)"""
        for o in self.vm.outputs():
            self.write(f"    {o:>12} = {fmt(self.vm.get(o))}")
        h = self.vm.history.get("surprise")
        if h:
            self.write(f"    {tr('surprise'):>12} = " + tr("{s} sigma (how far the last inputs were from what it "
                                                            "expected)", s=f"{h[-1]:.3g}"))

    def do_show(self, arg):
        """show: what the network is"""
        n = self.vm.net
        roles = {r: [k for k, s in n.nodes.items() if s.get(r)] for r in ("var", "learn", "input", "output")}
        self.write("  " + tr("{nodes} nodes, {relations} relations, {sets} writes at each tick, {networks} networks",
                             nodes=len(n.nodes), relations=len(n.relations), sets=len(n.sets),
                             networks=len(n.networks)) + (f" ({', '.join(n.networks)})" if n.networks else ""))
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
            self.write("  " + tr("{p} processors, tick {tick}, round {round}", p=m.processors(), tick=m.ticks,
                                 round=m.rounds))

    # --------------------------------------------------------------- memory
    def do_sleep(self, arg):
        """sleep [FILE.json]: the network and every message to its memory"""
        self.vm.sleep(arg.strip() or None)
        self.write("  " + tr("asleep in {path}", path=arg.strip() or self.vm.memory))

    def do_wake(self, arg):
        """wake [FILE.json]: back as it was put to sleep"""
        try:
            self.vm.wake(arg.strip() or None)
        except (OSError, TalkError, ValueError) as e:
            self.write(f"  ? {e}")
            return
        self.write("  " + tr("awake at tick {tick}", tick=self.vm.machine.ticks))

    def do_blank(self, arg):
        """blank: forget everything (the memory file stays until the next sleep)"""
        self.vm.blank()
        self.write("  " + tr("blank"))

    # --------------------------------------------------------------- the body
    def do_sound(self, arg):
        """sound on | off: hear the outputs at each tick"""
        self.sound = arg.strip().lower() != "off"
        self.write("  " + (tr("sound on") if self.sound else tr("sound off")))

    def do_clock(self, arg):
        """clock HZ: ticks by themselves, HZ a second (window only; 0: only on Enter)"""
        try:
            self._set_clock(max(0.0, float(arg)))
        except ValueError:
            self.usage("clock")
            return
        self.write("  " + tr("clock {hz} Hz", hz=f"{self.clock:g}"))

    def _set_clock(self, hz):
        self.clock = hz
        self.vm.clock_hz = hz
        if hz > 0:
            self.last_clock = hz

    # --------------------------------------------------------------- seeing it work (debugging)
    def do_play(self, arg):
        """play [HZ]: the clock runs (window), HZ ticks a second (10 by default, or the last one); pause stops it"""
        try:
            hz = float(arg) if arg.strip() else (self.last_clock or 10.0)
        except ValueError:
            self.usage("play")
            return
        self._set_clock(max(hz, 0.0))
        self.write("  " + (tr("playing at {hz} Hz", hz=f"{self.clock:g}") if self.clock > 0 else tr("paused")))

    def do_pause(self, arg):
        """pause: the clock stops (Enter, tick and step still go on by hand)"""
        self._set_clock(0.0)
        self.write("  " + tr("paused"))

    def do_step(self, arg):
        """step [n]: n rounds of the network, one at a time: who worked, who moved, and the end of each tick"""
        try:
            n = int(arg) if arg.strip() else 1
        except ValueError:
            self.usage("step")
            return
        for line in debug.step_lines(self.vm.step(max(1, n))):
            self.write("  " + line)

    def do_watch(self, arg):
        """watch [NODE in LO .. HIGH | NODE | RELATION]: stop the clock (and tick n) when it is met; alone: the list"""
        text = arg.strip()
        if not text:
            if not self.vm.watches:
                self.write("  " + tr("no watch (watch NODE in LO .. HIGH, watch NODE, watch RELATION)"))
            for k, w in enumerate(self.vm.watches, 1):
                self.write(f"  {k}: {w.text}  ({tr(WATCH_KINDS[w.kind])})")
            return
        try:
            w = debug.arm(self.vm, debug.parse(self.vm, text))
        except TalkError as e:
            self.write(f"  ? {e}")
            return
        self.vm.watches.append(w)
        self.write("  " + tr("watch {k}: {text} ({what})", k=len(self.vm.watches), text=w.text,
                             what=tr(WATCH_KINDS[w.kind])))

    def do_unwatch(self, arg):
        """unwatch [N | all]: take a watch away (all: every one)"""
        a = arg.strip().lower()
        if a in ("", "all"):
            n = len(self.vm.watches)
            self.vm.watches = []
            self.write("  " + tr("{n} watch(es) taken away", n=n))
            return
        try:
            w = self.vm.watches.pop(int(a) - 1)
        except (ValueError, IndexError):
            self.write("  ? " + tr("no watch {k} (watch: the list)", k=a))
            return
        self.write("  " + tr("watch taken away: {text}", text=w.text))

    def do_why(self, arg):
        """why NODE: why it has its value: what each of its relations says of it, and how much it counts"""
        name = arg.strip()
        if not name:
            self.usage("why")
            return
        try:
            lines = debug.why(self.vm, name)
        except TalkError as e:
            like = diagnose.close(name, list(self.vm.net.nodes))
            self.write("  ? " + (tr("no node {name}; did you mean {like}?", name=name, like=tr(" or ").join(like))
                                 if like else str(e)))
            return
        for line in lines:
            self.write("  " + line)

    # --------------------------------------------------------------- inside
    def do_master(self, arg):
        """master [n]: the master equation of the network now, or n ticks ago (pygrm's master invariant)"""
        try:
            n = int(arg) if arg.strip() else 0
        except ValueError:
            self.usage("master")
            return
        res = mind.master(self.vm, n)
        when = f"t - {n}" if n else tr("now")
        tick = " (" + tr("tick {tick}", tick=res["tick"]) + ")" if res.get("tick") is not None else ""
        self.write("  " + tr("master equation, {when}{tick}: {text}", when=when, tick=tick,
                             text=graph.in_equation(self.vm.net, res["text"])))
        if "span" in res:
            self.write("    " + tr("ties {span} decades of scale, residual {residual}", span=f"{res['span']:.3g}",
                                   residual=f"{res['residual']:.3g}{res['unit']}")
                       + ("; " + label("implied by the network")
                          + ", ".join(f"{k} × {v:g}" for k, v in res["relations"].items())
                          if res.get("derived") and res.get("relations") else "; " + tr("written as one of its "
                                                                                       "relations")))

    def do_mood(self, arg):
        """mood: its pleasure, what it expects, how it flourishes"""
        md = mind.mood(self.vm.net)
        mind.flourishing(self.vm.net)
        d = md["dopamine"]
        feel = tr("pleasure") if d > 0.05 else tr("displeasure") if d < -0.05 else tr("calm")
        exp = md["expected"]
        rows = [(tr("dopamine"), f"{d:+.3f}  ({feel})"),
                (tr("expects"), tr("{s} sigma of surprise", s=f"{exp:.3g}") if exp is not None else
                 tr("nothing yet (no input has surprised it)")),
                (tr("flourishing"), f"{md['flourishing']:.3f}  = sqrt({tr('accuracy')} {md['accuracy']:.3f} × "
                                    f"{tr('room')} {md['room']:.3f})"),
                (tr("progress"), f"{md['progress']:+.3f}  (" + tr("how much its surprise is falling") + ")")]
        net = self.vm.net
        rows.append((tr("links"), tr("{n} of {cap}", n=mind.links(net), cap=mind.capacity(net))
                     + ("  (" + tr("set by hand") + ")" if net.capacity else f"  ({self._host_text()})")))
        rows.append((tr("rent"), tr("{p} bits per link per tick", p=f"{mind.price(net):.3g}")))
        w = max(len(k) for k, _ in rows) + 2                # the longest word of the language sets the column
        for k, v in rows:
            self.write(f"    {k:<{w}}{v}")

    def do_capacity(self, arg):
        """capacity [N | auto]: how many links (synapses) the network may hold (auto: what the host's budget allows);
        beyond, it forgets what pays the least"""
        net = self.vm.net
        if arg.strip().lower() == "auto":
            net.capacity = None
        elif arg.strip():
            try:
                net.capacity = max(1, int(float(arg)))
            except ValueError:
                self.usage("capacity")
                return
        if arg.strip():
            for line in mind.prune(self.vm):
                self.write(f"  ~ {line}")
        cap = mind.capacity(net)
        self.write("  " + tr("{n} links of {cap}", n=mind.links(net), cap=cap)
                   + ("  (" + tr("set by hand") + ")" if net.capacity else f"  ({self._host_text()})"))
        self.write("  " + tr("rent: {p} bits per link per tick", p=f"{mind.price(net):.3g}"))

    def _host_text(self):
        h = self.vm.net.host
        caps = h.get("caps") or {}
        if not caps:
            return tr("nothing measured on this host: {n} by default", n=mind.CAPACITY)
        parts = [f"{tr(k)} {int(v):,}".replace(",", " ") for k, v in sorted(caps.items())]
        return tr("the host's budget: {parts}; limited by {limit}", parts=", ".join(parts),
                  limit=tr(h.get("limit") or ""))

    def do_prune(self, arg):
        """prune: forget now what a night would forget (what it found and no longer uses, and beyond capacity)"""
        done = mind.prune(self.vm, night=True)
        for line in done or [tr("nothing to forget")]:
            self.write(f"  {line}")

    def do_check(self, arg):
        """check: everything that is wrong now (values that are not numbers, no settling, relations far from holding)"""
        m = self.vm.m()
        m.run(5000)
        problems = diagnose.machine(m, m.quiet)
        for p in problems or [tr("no problem found")]:
            self.write(f"  {p}")

    def do_inspect(self, arg):
        """inspect NAME: what a node or a relation holds (what the window shows under the mouse)"""
        name = arg.strip()
        net = self.vm.net
        if name in net.nodes:
            self.vm.settle()
            lines = graph.table(graph.node_card(self.vm, name))
        elif net.relation(name):
            self.vm.settle()
            lines = graph.table(graph.relation_card(self.vm, name))
        else:
            like = diagnose.close(name, list(net.nodes) + [r["name"] for r in net.relations])
            self.write("  ? " + (tr("no node or relation {name}; did you mean {like}?", name=name,
                                    like=tr(" or ").join(like)) if like else
                                 tr("no node or relation {name}", name=name)))
            return
        for ln in lines:
            self.write(f"    {ln}")

    # --------------------------------------------------------------- programs
    def do_programs(self, arg):
        """programs: the programs and what they do (the machine's, and those of the folder it is in)"""
        found = programs.listing(os.path.join(self.base, "programs"))
        here = os.path.abspath(os.getcwd())
        if here != os.path.abspath(os.path.join(self.base, "programs")):
            mine = programs.listing(here)
            if mine:
                found = mine + [p for p in found if p["name"] not in {q["name"] for q in mine}]
        if not found:
            self.write("  " + tr("no program in {folder}", folder=os.path.join(self.base, "programs")))
            return
        width = max(len(p["name"]) for p in found)
        for p in found:
            self.write(f"    {p['name']:<{width}}  {p.get('does', '')}")
            io = []
            if p["inputs"]:
                io.append(label("in") + ", ".join(p["inputs"]))
            if p["outputs"]:
                io.append(label("out") + ", ".join(p["outputs"]))
            if p["networks"]:
                io.append(label("networks") + ", ".join(p["networks"]))
            if io:
                self.write(f"    {'':<{width}}  " + "; ".join(io))
        self.write("  " + tr("open NAME: in a tab; read NAME: here; run NAME: run it"))

    def _program(self, arg, word):
        if not arg.strip():
            self.usage(word)
            return None
        path = programs.find(arg, self.base)
        if path is None:
            like = diagnose.close(arg.strip(), editor.program_names(self.base))
            self.write("  ? " + (tr("no program {name}; did you mean {like}?", name=arg.strip(),
                                    like=tr(" or ").join(like)) if like else
                                 tr("no program {name} (programs: the list)", name=arg.strip())))
        return path

    def do_read(self, arg):
        """read PROGRAM: the program, here, its lines numbered"""
        path = self._program(arg, "read")
        if path is None:
            return
        with open(path, encoding="utf-8") as f:
            lines = f.read().splitlines()
        self.write(f"  {path}")
        for i, ln in enumerate(lines, 1):
            self.write(f"  {i:>4}  {ln}")

    def _window(self, word):
        if self.programs is None:
            self.write("  ? " + tr("{word}: in the window only (python vm/grm_vm.py --window); read NAME shows a "
                                   "program here", word=word))
            return False
        return True

    def do_open(self, arg):
        """open PROGRAM: in a tab of the programs window"""
        if not self._window("open"):
            return
        path = self._program(arg, "open")
        if path:
            n = self.programs.open(path)
            self.write("  " + tr("open in tab {n}: {path}", n=n, path=path))

    def do_tab(self, arg):
        """tab N | NAME: go to a tab of the programs window"""
        if not self._window("tab"):
            return
        if not arg.strip():
            self.write("  " + (", ".join(f"{i}: {name}" for i, name in self.programs.tabs()) or tr("no tab open")))
            return
        if not self.programs.select(arg.strip()):
            self.write("  ? " + tr("no tab {tab} (tab: the list)", tab=arg.strip()))

    def do_close(self, arg):
        """close [N | NAME]: close a tab (the current one)"""
        if not self._window("close"):
            return
        said = self.programs.close(arg.strip() or None)
        self.write("  " + (said or tr("no tab to close")))

    def do_new(self, arg):
        """new [NAME | NAME.ext]: a new program (NAME: from a short template), a new file of any kind (NAME.ext: empty),
        or a new tab with no name yet (save NAME.ext names it); open to be written"""
        name = os.path.expanduser(arg.strip().strip('"'))
        if not name:
            if not self._window("new"):
                return
            self.programs.open(os.path.join(os.getcwd(), "untitled"), edit=True, blank=True)
            self.write("  " + tr("a new tab: save NAME.ext gives it its name (in {folder})", folder=os.getcwd()))
            return
        if os.path.splitext(name)[1] and not name.endswith(".grm"):    # a file of any kind, empty, in the folder
            path = os.path.abspath(name)
            if os.path.exists(path):
                self.write("  ? " + tr("{path} already exists: open {name}", path=path, name=name))
                return
            try:
                open(path, "x", encoding="utf-8").close()
            except OSError as e:
                self.write(f"  ? {e}")
                return
            self.write("  " + tr("new file: {path}", path=path))
            if self.programs is not None:
                self.programs.open(path, edit=True)
            return
        name = name[:-4] if name.endswith(".grm") else name
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_\-]*", name or ""):
            self.usage("new")
            return
        folder = "programs" if os.path.isdir("programs") else "."      # in the folder it is in
        path = os.path.abspath(os.path.join(folder, name + ".grm"))
        if os.path.exists(path):
            self.write("  ? " + tr("{path} already exists: open {name}", path=path, name=name))
            return
        with open(path, "w", encoding="utf-8") as f:
            f.write(programs.template(name))
        self.write("  " + tr("new program: {path}", path=path))
        if self.programs is not None:
            self.programs.open(path, edit=True)

    def do_edit(self, arg):
        """edit [PROGRAM]: write in a tab (the current one); Ctrl+S saves, F5 runs, Esc comes back here"""
        if not self._window("edit"):
            return
        if arg.strip():
            path = self._program(arg, "edit")
            if path is None:
                return
            self.programs.open(path, edit=True)
        elif not self.programs.edit():
            self.write("  ? " + tr("no tab open: edit NAME"))

    def do_save(self, arg):
        """save [NAME.ext]: save the current tab (as NAME.ext, in the folder it is in; no extension: its own)"""
        if not self._window("save"):
            return
        said = self.programs.save(arg.strip() or None)
        self.write("  " + (said or tr("no tab open")))

    def do_find(self, arg):
        """find WORDS: search the current tab (Ctrl+F there)"""
        if not self._window("find"):
            return
        n = self.programs.find(arg.strip())
        self.write("  " + tr("{n} found", n=n) if n is not None else "  ? " + tr("no tab open"))

    # --------------------------------------------------------------- its logbook
    def do_journal(self, arg):
        """journal [N | today | WORDS]: its logbook: what it lived, day after day (the window opens it)"""
        a = arg.strip()
        found = None
        if self.logbook is not None and not a:   # the window shows it: nothing to write here
            self.logbook.show()
            return
        if a.isdigit():
            pick = journal.entries(self.vm.net)[-int(a):]
        elif a.lower() in ("today", "aujourd'hui"):
            pick = journal.today(self.vm.net)
        elif a:
            found = a
            pick = [e for _, es in journal.days(self.vm.net, a) for e in es]
        else:
            pick = journal.entries(self.vm.net)[-12:]
        if not pick:
            self.write("  " + (tr("nothing in the logbook holds {words}", words=found) if found else
                               tr("the logbook is empty")))
            return
        day = None
        for e in pick:
            if journal.day_of(e) != day:
                day = journal.day_of(e)
                self.write(f"  ── {journal.pretty(day)} ──")
            icon, sentence, more = journal.say(e)
            self.write(f"  {journal.hour(e)}  {icon} {sentence}")
            for m_ in more:
                self.write(f"            {m_}")

    # --------------------------------------------------------------- the senses: what it feels, seen and heard
    def senses_settings(self):
        s = self.settings.setdefault("senses", {})
        s.setdefault("level", "calm")
        s.setdefault("motion", True)
        s.setdefault("colour", True)
        s.setdefault("waves", True)
        return s

    def do_senses(self, arg):
        """senses [off | calm | present | vivid] [motion | colour | waves on|off]: how strongly the picture shows what
        the machine feels"""
        s = self.senses_settings()
        words = arg.lower().split()
        if not words:
            self.write("  " + tr("senses: {level}; motion {m}, colour {c}, waves {w}", level=tr(s["level"]),
                                 m=tr("on") if s["motion"] else tr("off"), c=tr("on") if s["colour"] else tr("off"),
                                 w=tr("on") if s["waves"] else tr("off")))
            return
        while words:
            w = words.pop(0)
            if w in senses.LEVELS:
                s["level"] = w
            elif w in ("motion", "colour", "color", "waves") and words and words[0] in ("on", "off"):
                s["colour" if w == "color" else w] = words.pop(0) == "on"
            else:
                self.usage("senses")
                return
        self.save_settings()
        self.do_senses("")

    def ambient_settings(self):
        a = self.settings.setdefault("ambient", {})
        a.setdefault("kind", "pad")
        a.setdefault("volume", 0.5)
        import ambient
        for k, v in ambient.MIX.items():
            a.setdefault(k, v)
        return a

    def do_ambient(self, arg):
        """ambient [engine | pad | wind | on | off] [VOLUME%] [main | drone | bells | reverb N%] |
        ambient save FILE.wav [SECONDS]: a calm sound that follows what the machine feels"""
        import ambient
        a = self.ambient_settings()
        words = arg.split()
        if words and words[0].lower() == "save":
            if len(words) < 2:
                self.usage("ambient")
                return
            seconds = float(words[2]) if len(words) > 2 and words[2].replace(".", "", 1).isdigit() else 30.0
            sound = ambient.Ambient(a["kind"], a["volume"])
            sound.set_mix(**{k: a[k] for k in ambient.LAYERS})
            state = self.feel.state(self.vm)
            sound.save(words[1], seconds, [(0, state, None), (seconds * 0.4, None, ("discovery", 1.5))])
            self.write("  " + tr("{kind}, {s} seconds, in {path}", kind=tr(a["kind"]), s=f"{seconds:g}",
                                 path=os.path.abspath(words[1])))
            return
        if not words:
            on = self.ambient is not None
            self.write("  " + tr("ambient: {state} ({kind}, volume {v}%)", state=tr("on") if on else tr("off"),
                                 kind=tr(a["kind"]), v=round(a["volume"] * 100)) + "; " + self.mix_text())
            return
        turn_on, other = None, False
        words = [w.lower().rstrip("%") for w in words]
        while words:
            w = words.pop(0)
            if w in ambient.LAYERS:                   # the mixer: ambient drone 30%
                if not words or not words[0].replace(".", "", 1).isdigit():
                    self.usage("ambient")
                    return
                a[w] = max(0.0, min(1.0, float(words.pop(0)) / 100.0))
                if self.ambient is not None:
                    self.ambient.set_mix(**{w: a[w]})
                self.save_settings()
                self.write("  " + self.mix_text())
                continue
            other = True
            if w in ambient.KINDS:
                a["kind"], turn_on = w, True
            elif w == "on":
                turn_on = True
            elif w == "off":
                turn_on = False
            elif w.replace(".", "", 1).isdigit():
                a["volume"] = max(0.0, min(1.0, float(w) / 100.0))
                if self.ambient is not None:
                    self.ambient.volume = a["volume"]
            else:
                self.usage("ambient")
                return
        if not other:                                 # only the mixer was set: said already
            return
        self.save_settings()
        if turn_on is False:
            if self.ambient is not None:
                self.ambient.stop()
                self.ambient = None
            self.write("  " + tr("ambient off"))
            return
        if turn_on:
            if self.ambient is not None and self.ambient.kind != a["kind"]:
                self.ambient.stop()
                self.ambient = None
            if self.ambient is None:
                sound = ambient.Ambient(a["kind"], a["volume"])
                sound.set_mix(**{k: a[k] for k in ambient.LAYERS})
                sound.set(self.feel.state(self.vm))
                why = sound.start()
                if why is not None:
                    self.write("  ? " + tr("no sound here ({why}): pip install sounddevice; ambient save FILE.wav "
                                           "writes it to a file", why=why))
                    return
                self.ambient = sound
                if self.programs is None:
                    self.listen()
        self.write("  " + tr("ambient: {kind}, volume {v}%", kind=tr(a["kind"]), v=round(a["volume"] * 100)))

    def mix_text(self):
        import ambient
        a = self.ambient_settings()
        return label("mixer") + ", ".join(f"{tr(k)} {round(a[k] * 100)}%" for k in ambient.LAYERS)

    def listen(self):
        """In the terminal, nobody draws: a thread tells the sound what the machine feels, a few times a second."""
        import threading
        if self._listening is not None:
            return

        def follow():
            while self.ambient is not None:
                try:
                    self.ambient.set(self.feel.state(self.vm))
                    for mo in self.feel.moments(self.vm):
                        self.ambient.event(mo["kind"], mo.get("ratio", 1.5))
                except Exception:  # noqa: BLE001 - the machine changed while it was looked at: next time
                    pass
                time.sleep(0.25)
            self._listening = None
        self._listening = threading.Thread(target=follow, daemon=True)
        self._listening.start()

    # --------------------------------------------------------------- focus: a network in the network
    def group_names(self):
        return sorted(graph.groups(self.vm.net))

    def do_focus(self, arg):
        """focus [NAME | node N [depth] | relation R | between A B... | all]: what comes to the front of the picture"""
        net = self.vm.net
        words = arg.split()
        found = graph.groups(net)
        if not words:
            if not found:
                self.write("  " + tr("no network in the network yet (use a program, call a network)"))
            width = max([len(g) for g in found] + [4])
            for g, (nodes, rels) in sorted(found.items()):
                mark = "▸" if self.vm.focus == ("group", g) else " "
                self.write(f"  {mark} {g:<{width}}  " + tr("{n} node(s), {r} relation(s)", n=len(nodes), r=len(rels)))
            self.write("  " + tr("now: {what}", what=self.focus_text()) + "   (focus NAME, focus node N, focus "
                       "relation R, focus between A B, focus all)")
            return
        kind = words[0].lower()
        if kind == "all":
            self.vm.focus = None
        elif kind == "between" or (kind not in ("group", "node", "relation") and len(words) > 1
                                   and not words[1].isdigit()):
            names = words[1:] if kind == "between" else words
            bad = [n for n in names if n not in net.nodes and n not in net.aliases and net.relation(n) is None]
            if len(names) < 2 or bad:
                self.write("  ? " + (tr("no node or relation {name}", name=bad[0]) if bad else
                                     tr("between what and what? (focus between A B)")))
                return
            self.vm.focus = ("between",) + tuple(names)
            if not graph.focus_keys(net, self.vm.focus) - {("n", n) for n in names} - {("r", n) for n in names}:
                self.write("  ~ " + tr("nothing ties them"))
        else:
            name = words[1] if kind in ("group", "node", "relation") and len(words) > 1 else words[0]
            depth = words[-1] if words[-1].isdigit() and len(words) > 1 else "1"
            if kind == "group" or (kind not in ("node", "relation") and name in found):
                if name not in found:
                    return self._no_focus(name, list(found))
                self.vm.focus = ("group", name)
            elif kind == "node" or (kind != "relation" and (name in net.nodes or name in net.aliases)):
                if name not in net.nodes and name not in net.aliases:
                    return self._no_focus(name, list(net.nodes))
                self.vm.focus = ("node", name, int(depth))
            elif net.relation(name) is not None:
                self.vm.focus = ("relation", name)
            else:
                return self._no_focus(name, list(found) + list(net.nodes) + [r["name"] for r in net.relations])
        self.write("  " + tr("focus: {what}", what=self.focus_text()))

    def _no_focus(self, name, words):
        like = diagnose.close(name, words)
        self.write("  ? " + (tr("nothing called {name}; did you mean {like}?", name=name, like=tr(" or ").join(like))
                             if like else tr("nothing called {name} (focus: the list)", name=name)))

    def focus_text(self):
        f = self.vm.focus
        if not f:
            return tr("everything")
        keys = graph.focus_keys(self.vm.net, f) or set()
        n = sum(1 for k in keys if k[0] == "n")
        r = len(keys) - n
        args = [str(a) for a in f[1:]]
        if f[0] == "group":
            what = args[0]
        elif f[0] == "node":
            what = tr("node {name}, {depth} relation(s) around", name=args[0], depth=args[1] if len(args) > 1 else 1)
        elif f[0] == "relation":
            what = tr("relation {name}", name=args[0])
        else:
            what = tr("between {names}", names=", ".join(args))
        return what + "  · " + tr("{n} node(s), {r} relation(s)", n=n, r=r)

    # --------------------------------------------------------------- files (as a Unix shell has them)
    def files(self, fn, arg):
        try:
            return fn(arg)
        except (files.FileError, OSError) as e:
            self.write(f"  ? {e}")
        return None

    def do_clear(self, arg):
        """clear: the words cleared from the screen (Ctrl+L in the window); nothing of the machine is forgotten"""
        if self.on_clear is not None:
            self.on_clear()
        elif getattr(sys.stdout, "isatty", lambda: False)():
            os.system("cls" if os.name == "nt" else "clear")

    def do_history(self, arg):
        """history [N]: the last N lines typed (20), sessions before included, numbered; !N types line N again"""
        try:
            n = int(arg) if arg.strip() else 20
        except ValueError:
            self.usage("history")
            return
        start = max(0, len(self.history) - n)
        for k, line in enumerate(self.history[start:], start + 1):
            self.write(f"  {k:>4}  {line}")

    def again(self, line):
        """!N: line N of the history, typed again (!! the last one)."""
        ref = line.strip()[1:]
        try:
            k = len(self.history) - 1 if ref == "!" else int(ref) - 1
            if not 0 <= k < len(self.history):
                raise IndexError
        except (ValueError, IndexError):
            self.write("  ? " + tr("no line {ref} in the history (history: the list)", ref=ref))
            return False
        typed = self.history[k]
        self.write(f"  {typed}")
        return self.onecmd(typed)

    def do_touch(self, arg):
        """touch FILE...: an empty file (or an old one dated now), as a Unix shell does"""
        flags, names = files.split(arg)
        if not names:
            self.usage("touch")
            return
        for n in names:
            try:
                with open(os.path.expanduser(n), "a", encoding="utf-8"):
                    os.utime(os.path.expanduser(n), None)
            except OSError as e:
                self.write(f"  ? {e}")
                return
        self.write("  " + tr("made {names}", names=", ".join(names)))

    def do_pwd(self, arg):
        """pwd: the folder it is in"""
        self.write("  " + os.getcwd())

    def do_cd(self, arg):
        """cd [FOLDER | .. | ~ | -]: into a folder (alone: home; -: the one before)"""
        said = self.files(files.cd, arg)
        if said is not None:
            self.write("  " + said)
            self.keep_state()

    def do_ls(self, arg):
        """ls [-l] [-a] [PATH...]: what is there (folders/, programs, data)"""
        rows = self.files(files.ls, arg)
        if rows is None:
            return
        parts = getattr(self.stdout, "write_parts", None)
        for row in rows:
            if parts is not None:
                parts([("  ", None)] + row + [("\n", None)])
            else:
                self.write("  " + "".join(t for t, _ in row).rstrip())

    def _lines(self, fn, arg):
        lines = self.files(fn, arg)
        for ln in lines or ():
            self.write("  " + ln)

    def do_head(self, arg):
        """head [-n N] FILE: its first lines (10)"""
        self._lines(files.head, arg)

    def do_tail(self, arg):
        """tail [-n N] FILE: its last lines (10)"""
        self._lines(lambda a: files.head(a, last=True), arg)

    def do_cat(self, arg):
        """cat FILE: all of it"""
        self._lines(files.cat, arg)

    def do_mkdir(self, arg):
        """mkdir [-p] FOLDER: a new folder"""
        self._lines(files.mkdir, arg)

    def do_cp(self, arg):
        """cp [-r] FROM... TO: a copy"""
        self._lines(files.cp, arg)

    def do_mv(self, arg):
        """mv FROM... TO: moved, or renamed"""
        self._lines(files.mv, arg)

    def do_rm(self, arg):
        """rm [-r] PATH...: deleted, once the human has said yes"""
        found = self.files(files.to_remove, arg)
        if not found:
            return
        found, _ = found
        names = ", ".join(found[:6]) + (tr(" and {n} more", n=len(found) - 6) if len(found) > 6 else "")
        self.asking = ("rm", found)
        self.write("  ! " + tr("delete {names}? (y/n)", names=names))

    def answer(self, line):
        what, found = self.asking
        self.asking = None
        if line.strip().lower() in YES:
            self._lines(lambda _a: files.remove(found), "")
        else:
            self.write("  " + tr("nothing deleted"))
        return False

    # --------------------------------------------------------------- help
    def do_lang(self, arg):
        """lang fr | en: the language of the machine"""
        code = arg.strip().lower()
        if code not in i18n.LANGS:
            self.write("  " + tr("language: {lang}", lang=i18n.lang()) + "   (lang fr | lang en)")
            return
        i18n.set_lang(code)
        for pic in self.vm.past:                 # the master equations said again, in the new language
            pic.pop("master", None)
        self.settings["lang"] = code
        self.save_settings()
        self.write("  " + tr("language: {lang}", lang=code))

    def do_help(self, arg):
        """help [WORD | on | off]"""
        w = arg.strip().lower()
        if w in ("on", "off"):
            self.settings["help"] = w == "on"
            self.save_settings()
            if self.on_help:
                self.on_help(self.settings["help"])
            self.write("  " + (tr("typing help on") if w == "on" else tr("typing help off")))
            return
        if w:
            whole = editor.whole(w)
            if whole not in editor.DOCS:
                like = diagnose.close(w, list(editor.DOCS) + list(editor.SHORT))
                self.write("  ? " + (tr("'{word}' is not a word of the machine; did you mean {like}?", word=w,
                                        like=tr(" or ").join(like)) if like else
                                     tr("'{word}' is not a word of the machine (help)", word=w)))
                return
            for line in guide.word(whole):
                self.write(line)
            return
        for line in guide.overview():
            self.write(line)

    def do_tour(self, arg):
        """tour [N | end]: a guided tour, a step at a time"""
        a = arg.strip().lower()
        if a in ("end", "stop", "fin"):
            self.tour_at = 0
            self.write("  " + tr("the tour is over (tour 1: again)"))
            return
        if a.isdigit():
            self.tour_at = max(1, min(len(guide.TOUR), int(a)))
        else:
            self.tour_at = self.tour_at + 1 if self.tour_at < len(guide.TOUR) else 1
        for line in guide.tour_step(self.tour_at):
            self.write(line)

    def do_quit(self, arg):
        """quit: the machine goes to sleep in its memory"""
        self.keep_state()
        if self.ambient is not None:
            self.ambient.stop()
            self.ambient = None
        if self.vm.net.nodes and self.vm.memory:
            for line in self.vm.sleep(night=True):
                self.write(f"  {line}")
            self.write("  " + tr("asleep in {path}", path=self.vm.memory))
        return True

    do_exit = do_quit
    do_EOF = do_quit


def main(argv):
    try:
        sys.stdout.reconfigure(errors="replace")
    except (AttributeError, ValueError):  # pragma: no cover
        pass
    # the language first, so that the machine's first words are in it
    i18n.set_lang(i18n.load_settings(os.path.join(HERE, "settings.json")).get("lang") or i18n.system_lang())
    vm = VM(blank="--blank" in argv)
    argv = [a for a in argv if a != "--blank"]
    if "--window" in argv:
        argv = [a for a in argv if a != "--window"]
        body.window(vm, Shell, " ".join(argv[1:]) if argv and argv[0] == "-c" else None)
        return
    shell = Shell(vm)
    if argv and argv[0] == "-c":
        shell.write(shell.intro)
        shell.onecmd(" ".join(argv[1:]))
        return
    try:
        import readline                          # Up and Down go back through what was typed, sessions before too
        for line in shell.history:
            readline.add_history(line)
    except ImportError:  # pragma: no cover - no readline (Windows without pyreadline): Up and Down do nothing more
        pass
    try:
        shell.cmdloop()
    except KeyboardInterrupt:
        shell.do_quit("")


if __name__ == "__main__":
    main(sys.argv[1:])
