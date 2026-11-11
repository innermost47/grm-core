# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Anthony Charretier
"""grm talk: talk to a GRM network from a terminal, watch it answer, put it to sleep and wake it, time it.

    python talk/grm_talk.py                       the prompt
    python talk/grm_talk.py examples/equation.grm  runs a script, then the prompt
    python talk/grm_talk.py -c "load equation; relax; bench"   commands, then quits

The words of the network (language.py): node, relate, observe, forget, keep, network, call, use. The questions
and orders: see `help`.
"""
import cmd
import math
import os
import random
import shlex
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "vm"))      # the language and the relational machine live in vm/

from language import Network, TalkError, from_store, statement   # noqa: E402
from machine import ClassicMachine, Costs, Problem, RelationalMachine   # noqa: E402,F401
from runtime import Machine   # noqa: E402
import live   # noqa: E402

try:
    from pygrm import GlobalRelationalNetwork
except ImportError:  # pragma: no cover
    GlobalRelationalNetwork = None

STORE = os.path.join(ROOT, "equation", "data", "grm_network_store.json")
EXAMPLE = os.path.join(HERE, "examples", "equation.grm")


def fmt(v):
    return f"{v:.6g}" if 1e-3 <= abs(v) < 1e6 else f"{v:.6e}"


def global_solve(net, min_sigma=None):
    """pygrm's solve of the network (relations at their sigma, or at least min_sigma). Returns (log10 values,
    sigma_dex, result) or None without pygrm."""
    if GlobalRelationalNetwork is None:
        return None
    nodes = {n: {"guess": s["guess"], "fixed": s["fixed"]} for n, s in net.nodes.items()}
    rels = [{"name": r["name"], "terms": dict(r["terms"]), "rhs": r["rhs"],
             "sigma": max(r["sigma"], min_sigma) if min_sigma else r["sigma"]} for r in net.relations]
    res = GlobalRelationalNetwork(nodes, rels).solve(dict(net.measured))
    logs = {n: math.log10(v) for n, v in res["values"].items()}
    return logs, res["sigma_dex"], res


def synthetic(n, seed=7):
    """A random sparse network of n nodes, true to a hidden world: relations of 2 or 3 nodes with small integer
    powers, a third of the nodes measured at 1 to 5 %, the relations exact."""
    rng = random.Random(seed)
    truth = {f"n{k}": rng.uniform(-30, 30) for k in range(n)}
    net = Network()
    for k in range(n):
        net.nodes[f"n{k}"] = {"guess": 1.0, "fixed": False}
    names = list(truth)
    for k in range(1, n):        # a tree, so every node is reached...
        a, b = names[k], names[rng.randrange(k)]
        terms = {a: rng.choice([1, 2, -1]), b: rng.choice([1, -1, 2, -2, 3])}
        net.relations.append({"name": f"t{k}", "terms": terms, "rhs": sum(p * truth[m] for m, p in terms.items()),
                              "sigma": 1e-9, "text": ""})
    for k in range(n // 5):      # ...and loops
        trio = rng.sample(names, 3)
        terms = {m: rng.choice([1, -1, 2]) for m in trio}
        net.relations.append({"name": f"l{k}", "terms": terms, "rhs": sum(p * truth[m] for m, p in terms.items()),
                              "sigma": 1e-9, "text": ""})
    for m in rng.sample(names, max(1, n // 3)):
        s = rng.uniform(0.004, 0.02)
        net.measured[m] = (10 ** (truth[m] + rng.gauss(0, s)), s)
    return net


class Talk(cmd.Cmd):
    intro = ("grm talk. Say what the network is (node, relate, observe, keep, network, call, use), ask it (ask, why, "
             "what-if), let it work (relax, solve), put it to sleep and wake it (sleep, wake). `help` for the words, "
             "`load equation` or `use universe.grm` to start.")
    prompt = "grm> "
    WORDS = ("node", "relate", "observe", "forget", "keep", "network", "call", "use", "end")

    def __init__(self):
        super().__init__()
        self.net = Network()
        self.machine = None     # the relational machine of the last relax / wake (runtime.Machine)
        self.values = {}        # the last answer: real values
        self.sigma = {}         # their sigma (dex for a positive node), from the global solve
        self.source = ""
        self.base = HERE
        self.graph_on = False
        self.graph = None
        self.graph_out = os.path.join(os.getcwd(), "talk_live.png")
        self.costs = Costs()
        self.ghz = 3.0

    # ---------------------------------------------------------------- the words of the network
    def say(self, part):
        try:
            said = statement(self.net, part, self.base)
        except TalkError as e:
            print(f"  ? {e}")
            return
        if said:
            print(f"  {said}")
        if said is not None and self.net.recording is None:
            self.changed()

    def default(self, line):
        for part in line.split(";") if self.net.recording is None else [line]:
            part = part.strip()
            if not part:
                continue
            word = part.split()[0].lower()
            if self.net.recording is not None or word in self.WORDS:
                self.say(part)
            elif hasattr(self, "do_" + word.replace("-", "_")):
                self.onecmd(part)
            else:
                print(f"  ? '{word}' is not a word of grm talk (help)")

    def onecmd(self, line):
        if self.net.recording is not None:
            self.default(line)
            return False
        if ";" in line:
            for part in line.split(";"):
                if part.strip():
                    self.onecmd(part.strip())
            return False
        line = line.replace("what-if", "what_if", 1)
        word = line.split()[0].lower() if line.split() else ""
        if word in self.WORDS:
            self.default(line)
            return False
        return super().onecmd(line)

    def emptyline(self):
        return False

    def changed(self):
        self.values, self.sigma, self.source = {}, {}, ""
        self.machine = None
        if self.graph:
            self.graph.close()
            self.graph = None

    def signed(self, name):
        return name.startswith("~") or self.net.nodes.get(name, {}).get("signed", False)

    def products_only(self):
        return all(r.get("kind", "product") == "product" for r in self.net.relations) and not any(
            s.get("signed") for s in self.net.nodes.values())

    # ---------------------------------------------------------------- loading
    def do_load(self, arg):
        """load equation | load store [network id] | load FILE.grm | load FILE.json [network id]"""
        words = shlex.split(arg)
        if not words:
            print("  load equation | load store [id] | load FILE.grm | load FILE.json [id]")
            return
        what = words[0]
        if what == "equation":
            self.net.clear()
            self.changed()
            self.do_run(EXAMPLE)
            return
        path = STORE if what == "store" else what
        if path.endswith(".grm"):
            self.net.clear()
            self.changed()
            self.do_run(path)
            return
        sys.path.insert(0, os.path.join(ROOT, "equation"))
        from store import load_grm_network_safely   # noqa: E402
        try:
            store = load_grm_network_safely(path, network_id=words[1] if len(words) > 1 else None)
        except (OSError, ValueError) as e:
            print(f"  ? {e}")
            return
        self.net.clear()
        self.changed()
        _, left_out = from_store(store, self.net)
        print(f"  {len(self.net.nodes)} nodes, {len(self.net.relations)} relations, {len(self.net.measured)} "
              f"measurements" + (f" ({len(left_out)} function or sum relations left out: the words of grm talk "
                                 f"are products and powers)" if left_out else ""))

    def do_run(self, arg):
        """run FILE: says every line of a script"""
        path = arg.strip()
        for cand in (path, os.path.join(self.base, path), os.path.join(HERE, path)):
            if os.path.exists(cand):
                path = cand
                break
        try:
            with open(path, encoding="utf-8") as f:
                lines = f.readlines()
        except OSError as e:
            print(f"  ? {e}")
            return
        shown = os.path.relpath(path, ROOT) if os.path.abspath(path).startswith(ROOT) else path
        print(f"  running {shown}")
        old, self.base = self.base, os.path.dirname(os.path.abspath(path))
        try:
            for line in lines:
                line = line.split("#", 1)[0].strip()
                if line:
                    self.onecmd(line)
        finally:
            self.base = old

    def do_save(self, arg):
        """save FILE.grm: the network in the words of grm talk (networks already called are written out)"""
        path = arg.strip() or "network.grm"
        with open(path, "w", encoding="utf-8") as f:
            for n, s in self.net.nodes.items():
                f.write(f"node {n} = {s['guess']:.12g}" + (" fixed" if s["fixed"] else "")
                        + (" signed" if s.get("signed") else "") + "\n")
            for r in self.net.relations:
                kind = r.get("kind", "product")
                if kind == "product":
                    left = " * ".join(f"{n}^{p:g}" for n, p in r["terms"].items())
                    f.write(f"relate {r['name']}: {left} = {10 ** r['rhs']:.15g} ± {r['sigma']:g}\n")
                elif kind == "sum":
                    parts = []
                    for c, t in r["terms"]:
                        body = " * ".join([repr(abs(c))] + [f"{n}^{p:g}" for n, p in t.items()])
                        parts.append(("- " if c < 0 else "+ ") + body)
                    f.write(f"relate {r['name']}: {' '.join(parts).lstrip('+ ')} = 0 ± {r['sigma']:g}\n")
                else:
                    when = " and ".join(f"{n} in {lo!r} .. {hi!r}".replace("inf", "inf") for n, lo, hi in r["when"])
                    f.write(f"keep {r['name']}: {r['node']} {r['op']} {r['bound']!r}" + (f" when {when}" if when else "")
                            + "\n")
            for n, (v, s) in self.net.measured.items():
                unit = "" if self.signed(n) else " dex"
                f.write(f"observe {n} = {v!r} ± {s!r}{unit}\n")
        print(f"  saved {path}")

    # ---------------------------------------------------------------- looking
    def do_show(self, arg):
        """show: what the network is | show NODE: one node"""
        name = arg.strip()
        if name:
            if name not in self.net.nodes:
                print(f"  ? no node {name}")
                return
            s = self.net.nodes[name]
            print(f"  {name}: start {fmt(s['guess'])}" + (" (fixed)" if s["fixed"] else "")
                  + (" signed" if s.get("signed") else ""))
            if name in self.net.measured:
                v, sg = self.net.measured[name]
                print(f"    measured {fmt(v)} ± {sg:.3g}" + ("" if self.signed(name) else " dex"))
            for r in self.net.relations:
                if name in self.net.nodes_of(r):
                    print(f"    in {r['name']}: {r['text']}")
            return
        n = self.net
        print(f"  {len(n.nodes)} nodes, {len(n.relations)} relations, {len(n.measured)} measurements, "
              f"{len(n.networks)} networks ({', '.join(n.networks)})" if n.networks else
              f"  {len(n.nodes)} nodes, {len(n.relations)} relations, {len(n.measured)} measurements")
        if len(n.nodes) <= 40:
            for r in n.relations:
                print(f"    {r['name']}: {r['text']}")
            for k, (v, s) in n.measured.items():
                print(f"    measured {k} = {fmt(v)} ± {s:.3g}" + ("" if self.signed(k) else " dex"))

    def answer_table(self, limit=30):
        names = sorted(k for k in self.values if not k.startswith("~"))
        if len(names) > limit:
            print(f"  ({len(names)} values: `ask NODE` for one)")
            return
        for k in names:
            sg = self.sigma.get(k)
            print(f"    {k:>14} = {fmt(self.values[k]):>14}" + (f"  ± {sg:.2g} dex" if sg is not None else ""))

    # ---------------------------------------------------------------- the two ways of working
    def do_solve(self, arg):
        """solve: the whole network at once (pygrm: one global factorization; product networks)"""
        if not self.net.nodes:
            print("  nothing to solve yet")
            return
        if not self.products_only():
            print("  solve takes product networks here; this one has sums, signed nodes or contacts: `relax` runs it")
            return
        t0 = time.perf_counter()
        out = global_solve(self.net)
        if out is None:
            P = Problem(self.net)
            x = ClassicMachine(P).solve()
            self.values = {n: 10 ** v for n, v in zip(P.names, x)}
            self.values.update({n: 10 ** v for n, v in P.fixed.items()})
            self.sigma = {}
            print("  (pygrm is not installed: solved by the classic machine, without uncertainties)")
        else:
            logs, self.sigma, res = out
            self.values = {n: 10 ** v for n, v in logs.items()}
            print(f"  solved in {1000 * (time.perf_counter() - t0):.1f} ms: cost {res['cost']:.4g}, "
                  f"{'converged' if res['converged'] else 'NOT converged'}")
        self.source = "the global solve"
        self.answer_table()

    def take(self, m):
        self.values = {n: m.value(n) for n in m.var_names}
        self.values.update(m.fixed)
        self.sigma = {}
        self.source = "the relational machine"

    def do_relax(self, arg):
        """relax [max rounds]: the relational machine, every node and relation at once, messages between
        neighbours only, each processor working only when it hears something new; watch it with `graph on`"""
        if not self.net.nodes:
            print("  nothing to relax yet")
            return
        try:
            max_rounds = int(arg) if arg.strip() else 5000
        except ValueError:
            print("  relax [max rounds]")
            return
        try:
            m = self.machine or Machine(self.net)
        except TalkError as e:
            print(f"  ? {e}")
            return
        self.machine = m
        if self.graph_on and live.available():
            if self.graph is None:
                self.graph = live.LiveGraph(m.view(), out=self.graph_out)
        every = 1 if len(m.var_names) <= 200 else 5

        def show(machine, moved):
            sys.stdout.write(f"\r  round {machine.rounds:5d}   the nodes still move by {moved:9.2e}   ")
            sys.stdout.flush()
            if self.graph:
                self.graph.update(machine.x, machine.last_move, machine.rounds, moved)

        before, msgs = m.rounds, m.messages
        m.run(max_rounds, callback=show, every=every)
        if self.graph:
            self.graph.update(m.x, m.last_move, m.rounds, 0.0)
        print()
        print(f"  {'quiet' if m.quiet else 'NOT quiet yet'} after {m.rounds - before} rounds, "
              f"{m.messages - msgs} messages, {m.processors()} processors")
        self.take(m)
        if self.graph and not self.graph.interactive:
            print(f"  graph: {self.graph_out}")
        self.answer_table()

    # ---------------------------------------------------------------- memory
    def do_sleep(self, arg):
        """sleep FILE.json: the network and the state of every processor, to a file"""
        path = arg.strip() or "network_sleep.json"
        if self.machine is None:
            try:
                self.machine = Machine(self.net)
            except TalkError as e:
                print(f"  ? {e}")
                return
        self.machine.sleep(path)
        print(f"  asleep in {path} (round {self.machine.rounds}, {self.machine.processors()} processors)")

    def do_wake(self, arg):
        """wake FILE.json: the network as it was put to sleep, going on from where it stopped"""
        path = arg.strip() or "network_sleep.json"
        try:
            m = Machine.wake(path)
        except (OSError, TalkError, ValueError) as e:
            print(f"  ? {e}")
            return
        self.changed()
        self.net = m.net
        self.machine = m
        self.take(m)
        print(f"  awake at round {m.rounds}: {m.processors()} processors, "
              f"{'quiet' if m.quiet else 'with news still to pass on'}")

    # ---------------------------------------------------------------- questions
    def need_answer(self):
        if not self.values:
            if self.products_only():
                print("  (no answer yet: solving)")
                self.do_solve("")
            else:
                print("  (no answer yet: relaxing)")
                self.do_relax("")
        return bool(self.values)

    def do_ask(self, arg):
        """ask NODE: its value"""
        name = arg.strip()
        if name not in self.net.nodes:
            print(f"  ? no node {name}")
            return
        if not self.need_answer():
            return
        v = self.values[name]
        sg = self.sigma.get(name)
        line = f"  {name} = {fmt(v)}"
        if sg is not None:
            line += f"  ± {sg:.3g} dex (± {100 * (10 ** sg - 1):.3g} %)"
        if name in self.net.measured:
            mv, ms = self.net.measured[name]
            line += f"   measured {fmt(mv)} ± {ms:.3g}" + ("" if self.signed(name) else " dex")
        print(line + f"   [{self.source}]")
        if self.graph:
            self.graph.highlight([name], [], f"ask {name}: {fmt(v)}")

    def says(self, rel, name):
        """What `name` would be if `rel` held exactly, the other nodes at their answer; and how far rel is from
        holding, in its sigmas."""
        kind = rel.get("kind", "product")
        if kind == "product":
            logs = {n: math.log10(self.values[n]) for n in rel["terms"]}
            rest = sum(p * logs[n] for n, p in rel["terms"].items() if n != name)
            alone = 10 ** ((rel["rhs"] - rest) / rel["terms"][name])
            t = (sum(p * logs[n] for n, p in rel["terms"].items()) - rel["rhs"]) / max(rel["sigma"], Problem.MIN_SIGMA)
            return alone, t
        if kind == "sum":
            total, own = 0.0, 0.0
            for c, t in rel["terms"]:
                k = c
                for n, p in t.items():
                    if n != name:
                        k *= self.values[n] ** p
                if name in t:
                    own += k
                else:
                    total += k
            alone = -total / own if own else math.nan
            res = total + own * self.values[name]
            return alone, res / max(rel["sigma"], Problem.MIN_SIGMA)
        return rel["bound"], 0.0

    def do_why(self, arg):
        """why NODE: what says what of it (each relation's own word, and how far each one is from holding)"""
        name = arg.strip()
        if name not in self.net.nodes:
            print(f"  ? no node {name}")
            return
        if not self.need_answer():
            return
        print(f"  {name} = {fmt(self.values[name])}   [{self.source}]")
        if self.net.nodes[name]["fixed"]:
            print("    fixed: it does not move")
        if name in self.net.measured:
            v, s = self.net.measured[name]
            if self.signed(name):
                pull = (self.values[name] - v) / s
            else:
                pull = (math.log10(self.values[name]) - math.log10(v)) / s
            print(f"    measured {fmt(v)} ± {s:.3g}: the answer is {pull:+.2f} sigma from it")
        rels = [r for r in self.net.relations if name in self.net.nodes_of(r)]
        for r in rels:
            if r.get("kind") == "keep":
                active = ""
                if self.machine:
                    for f in self.machine.factors:
                        if f.name == r["name"]:
                            active = " (pushing)" if f.active else " (not pushing)"
                print(f"    contact {r['name']} ({r['text']}){active}")
                continue
            try:
                alone, t = self.says(r, name)
            except (KeyError, ValueError, ZeroDivisionError):
                continue
            print(f"    {r['name']} ({r['text']}): says {fmt(alone)}, holds to {t:+.2g} sigma")
        if not rels and name not in self.net.measured:
            print("    nothing speaks of it: its value is only its start")
        if self.graph:
            near = {n for r in rels for n in self.net.nodes_of(r)}
            self.graph.highlight(near or [name], [r["name"] for r in rels], f"why {name}")

    def do_what_if(self, arg):
        """what-if NODE = VALUE [± sigma]: the answer if NODE were measured so (the network is left as it was)"""
        try:
            name, _, rest = arg.partition("=")
            name = name.strip()
            if name not in self.net.nodes:
                raise TalkError(f"no node {name}")
            if not self.need_answer():
                return
            before = dict(self.values)
            saved = dict(self.net.measured)
            statement(self.net, f"observe {name} = {rest.strip()}")
        except TalkError as e:
            print(f"  ? {e}  (what-if NODE = value [± 1%])")
            return
        try:
            if self.products_only():
                out = global_solve(self.net)
                if out is None:
                    P = Problem(self.net)
                    x = ClassicMachine(P).solve()
                    after = {n: 10 ** v for n, v in zip(P.names, x)}
                    after.update({n: 10 ** v for n, v in P.fixed.items()})
                else:
                    after = {n: 10 ** v for n, v in out[0].items()}
            else:
                m = Machine(self.net)
                m.run(5000)
                after = {n: m.value(n) for n in m.var_names}
                after.update(m.fixed)
        finally:
            self.net.measured = saved

        def change(k):
            a, b = before[k], after[k]
            if self.signed(k):
                return abs(b - a)
            return abs(math.log10(b) - math.log10(a))

        moved = sorted(((change(k), k) for k in after if k in before and not k.startswith("~")), reverse=True)
        print(f"  if {name} were {rest.strip()}:")
        for d, k in moved[:10]:
            if d < 1e-9:
                break
            ratio = "" if self.signed(k) else f"   (x {after[k] / before[k]:.4g})"
            print(f"    {k:>14}: {fmt(before[k]):>14} -> {fmt(after[k]):>14}{ratio}")
        if not moved or moved[0][0] < 1e-9:
            print("    nothing moves")
        print("  (the network is as it was: `observe` to keep it)")

    # ---------------------------------------------------------------- the graph
    def do_graph(self, arg):
        """graph on | off | FILE.png: draws the network while the relational machine works"""
        a = arg.strip().lower()
        if not live.available():
            print("  ? the graph needs matplotlib and numpy")
            return
        if a.endswith(".png"):
            self.graph_out = os.path.abspath(arg.strip())
            a = "on"
        self.graph_on = a != "off"
        if self.graph:
            self.graph.close()
            self.graph = None
        print(f"  graph {'on' if self.graph_on else 'off'}" + (
            "" if not self.graph_on or matplotlib_interactive() else f" (no screen: pictures in {self.graph_out})"))

    # ---------------------------------------------------------------- the benchmark
    def set_costs(self, words):
        for w in words:
            key, _, val = w.partition("=")
            if key in ("op", "cache", "ram", "hit", "link"):
                setattr(self.costs, key, float(val))
            elif key == "ghz":
                self.ghz = float(val)

    def do_bench(self, arg):
        """bench [op= cache= ram= hit= link= ghz=]: the network on the classic machine and on the relational one
        bench sizes [n n n...]: the same on random networks of growing size"""
        words = shlex.split(arg)
        self.set_costs([w for w in words if "=" in w])
        rest = [w for w in words if "=" not in w]
        if rest and rest[0] == "sizes":
            sizes = [int(w) for w in rest[1:]] or [30, 100, 300, 1000, 3000]
            self.bench_sizes(sizes)
            return
        if not self.net.nodes:
            print("  nothing to bench yet (load equation, load store...)")
            return
        if not self.products_only():
            print("  bench takes product networks (the classic machine of the benchmark solves those)")
            return
        print(f"  cost model: {self.costs}, {self.ghz:g} GHz")
        row = bench_one(self.net, self.costs)
        print_bench(row, self.ghz)

    def bench_sizes(self, sizes):
        print(f"  random networks (relations of 2 or 3 nodes, a fifth of them closing loops, a third of the nodes "
              f"measured); cost model: {self.costs}")
        print(f"  {'nodes':>6} {'relations':>9} | {'dense QR':>10} {'same msgs':>10} | {'processors':>10} {'rounds':>6} "
              f"{'cycles':>9} | {'vs QR':>8} {'vs msgs':>8} | {'agree (sigma)':>13}")
        for n in sizes:
            net = synthetic(n)
            r = bench_one(net, self.costs, run_classic=n <= 1500, quiet=True)
            agree = f"{r['agree_sigma']:.2g}" if r["agree_sigma"] is not None else "-"
            star = "" if r["classic_run"] else "*"
            print(f"  {n:6d} {len(net.relations):9d} | {r['classic_cycles']:9.3e}{star or ' '} {r['seq_cycles']:10.3e} | "
                  f"{r['processors']:10d} {r['rounds']:6d} {r['rel_cycles']:9.3e} | "
                  f"{r['classic_cycles'] / r['rel_cycles']:8.3g} {r['seq_cycles'] / r['rel_cycles']:8.3g} | {agree:>13}")
        print("  cycles: modelled. dense QR: the classic machine as pygrm solves (counted from the size, not run, where *).")
        print("  same msgs: the relational machine's own work done by one core with a RAM. agree: relational vs pygrm,")
        print("  in pygrm's sigmas (- : pygrm not run, too big here).")

    def do_help(self, arg):
        if arg:
            return super().do_help(arg)
        print(__doc__.split("\n\n")[0])
        print("""
  the network      node NAME [= value] [fixed] [signed]
                   relate NAME: A * B^2 / C = 3.2 * pi [± sigma dex]        products
                   relate NAME: x1 = x0 + v * dt [± sigma]                  sums (kept as products of e^x)
                   keep NAME: y >= 2 when x in 3 .. 8 and ...               contacts
                   observe NAME = value [± 1% | ± 0.004 dex | ± 0.1]        forget NAME
  programs         network NAME(a, b) ... end      call NAME(a=.., b=..)      use FILE.grm
  loading          load equation | load store [id] | load FILE.grm | load FILE.json [id]
                   run FILE.grm      save FILE.grm      show [NODE]
  working          relax [rounds]    the relational machine: every node and relation at once
                   solve             the whole network at once (pygrm; product networks)
  memory           sleep FILE.json   wake FILE.json
  questions        ask NODE          why NODE          what-if NODE = value [± sigma]
  watching         graph on | off | FILE.png
  timing           bench [op=1 cache=4 ram=100 hit=0.9 link=10 ghz=3]      bench sizes [n n n]
                   quit""")

    def do_quit(self, arg):
        """quit"""
        return True

    do_exit = do_quit
    do_EOF = do_quit


def matplotlib_interactive():
    if not live.available():
        return False
    return live.matplotlib.get_backend().lower() not in ("agg", "pdf", "svg", "ps", "cairo", "template")


def bench_one(net, costs, run_classic=True, quiet=False):
    P = Problem(net)
    row = {"nodes": len(P.names), "factors": len(P.factors), "edges": P.edges}
    cm = ClassicMachine(P)
    if run_classic:
        xc = cm.solve()
        row["classic_run"] = True
    else:
        xc = None
        m, n = len(P.factors), len(P.names)
        cm.ops = 2 * P.edges + sum((n + 1 - k) * (4 * (m - k) + 1) + 4 * (m - k) + 2 for k in range(n)) + n * n
        cm.accesses = m * (n + 1) + sum((n + 1 - k) * 3 * (m - k) + (m - k) for k in range(n)) + n * n
        cm.bytes = m * (n + 1) * 8
        row["classic_run"] = False
    rm = RelationalMachine(P)
    rm.run()
    row.update(classic_ops=cm.ops, classic_acc=cm.accesses, classic_cycles=cm.cycles(costs), classic_wall=cm.wall,
               classic_bytes=cm.bytes, rounds=rm.rounds, settled=rm.settled, messages=rm.messages, rel_ops=rm.ops,
               rel_cycles=rm.cycles(costs), round_cycles=rm.round_cycles(costs), seq_cycles=rm.sequential_cycles(costs),
               rel_wall=rm.wall, processors=rm.processors(), max_factor_ops=rm.max_factor_ops,
               max_node_ops=rm.max_node_ops)
    # how far the two answers are, in the global solve's own sigmas (pygrm, the same relations)
    row["agree_sigma"] = row["agree_dex"] = row["classic_sigma"] = None
    ref = global_solve(net, min_sigma=Problem.MIN_SIGMA) if len(P.names) <= 1500 else None
    if ref:
        logs, sig, res = ref
        und = set(res.get("undetermined", []))
        keep = [k for k, n in enumerate(P.names) if n not in und and sig.get(n, 0) > 0]
        if keep:
            row["agree_sigma"] = max(abs(rm.x[k] - logs[P.names[k]]) / sig[P.names[k]] for k in keep)
            row["agree_dex"] = max(abs(rm.x[k] - logs[P.names[k]]) for k in keep)
            if xc is not None:
                row["classic_sigma"] = max(abs(xc[k] - logs[P.names[k]]) / sig[P.names[k]] for k in keep)
        row["undetermined"] = len(und)
    return row


def print_bench(r, ghz):
    def t(c):
        s = c / (ghz * 1e9)
        return f"{s * 1e6:.3g} us" if s < 1e-3 else f"{s * 1e3:.3g} ms"
    print(f"  the network: {r['nodes']} free nodes, {r['factors']} relations, measurements and priors, "
          f"{r['edges']} links")
    print(f"  {'':34} {'operations':>12} {'memory/msgs':>12} {'cycles':>11} {'modelled':>10} {'python here':>12}")
    print(f"  {'classic CPU+RAM, dense QR':34} {r['classic_ops']:12.3e} {r['classic_acc']:12.3e} "
          f"{r['classic_cycles']:11.3e} {t(r['classic_cycles']):>10} {1000 * r['classic_wall']:9.2f} ms")
    print(f"  {'classic CPU+RAM, same messages':34} {r['rel_ops']:12.3e} {4 * r['messages']:12.3e} "
          f"{r['seq_cycles']:11.3e} {t(r['seq_cycles']):>10} {'(same run)':>12}")
    print(f"  {'relational machine':34} {r['rel_ops']:12.3e} {r['messages']:12.3e} "
          f"{r['rel_cycles']:11.3e} {t(r['rel_cycles']):>10} {1000 * r['rel_wall']:9.2f} ms")
    print(f"  relational: {r['processors']} processors, {r['rounds']} rounds "
          f"({'settled' if r['settled'] else 'NOT settled'}), a round = slowest relation {r['max_factor_ops']} ops "
          f"+ slowest node {r['max_node_ops']} ops + 2 links = {r['round_cycles']:.0f} cycles")
    print(f"  modelled: the relational machine is {r['classic_cycles'] / r['rel_cycles']:.3g} x the classic dense "
          f"solve, {r['seq_cycles'] / r['rel_cycles']:.3g} x the same messages on one core")
    if r["agree_sigma"] is not None:
        print(f"  same answer? relational vs pygrm: at most {r['agree_sigma']:.2g} sigma ({r['agree_dex']:.2g} dex)"
              + (f"; classic vs pygrm: {r['classic_sigma']:.2g} sigma" if r["classic_sigma"] is not None else "")
              + (f"; {r['undetermined']} undetermined nodes left out" if r.get("undetermined") else ""))
    print("  (modelled cycles are a model of two machines, not a measure of a chip; `python here` is this PC "
          "running Python, where the relational machine is simulated one processor after the other)")


def main(argv):
    talk = Talk()
    if argv and argv[0] == "-c":
        talk.onecmd(" ".join(argv[1:]))
        return
    for path in argv:
        talk.do_run(path)
    try:
        talk.cmdloop()
    except KeyboardInterrupt:
        print()


if __name__ == "__main__":
    main(sys.argv[1:])
