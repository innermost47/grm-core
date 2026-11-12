# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Anthony Charretier
"""GRML, the Global Relational Model Language: the language of the GRM machine, one statement per line.
Reference, tutorial and examples: docs/GRML.md.

    node H                       a node: a positive quantity, solved in log10
    node H = 2.2e-18             ... with a starting value
    node c = 299792458 fixed     ... that does not move
    node x = -3 signed           a signed quantity (a position, a velocity): it can be negative or zero

    relate grains: S * H^2 * tP^2 = pi              a product relation (products and powers), exact by default
    relate stock: Estock * G * H / c^5 = 0.5 ± 0.01  ... or with its uncertainty (dex)
    relate move: x1 = x0 + vx1 * dt                  a sum: see below
    observe H = 2.18e-18 ± 1%    a measurement (± in % or in dex: "± 0.004 dex"; default 0.01 dex)
    observe x0 = 2.5 ± 0.001     a signed node: ± in its own unit
    forget H                     removes the measurement of H

    keep land: y1 >= 2 when x1 in 3 .. 8 and y0 in 1.99 .. inf
                                 a contact: y1 stays above 2, only while the conditions hold

    network platform(id, left, right, top)      a network that can be called (a network in the network);
      keep land_{id}: y1 >= {top} when x1 in {left} .. {right}    {name} is replaced by the value given at the call
    end
    call platform(id=3, left=3, right=8, top=2)
    use FILE.grm                 says every statement of a file (its networks become callable)

    relate r: y = 2 * x when s in 0.5 .. 1.5        any relation can hold only while conditions hold (a choice)

    var x = 0                    a variable: a value the network holds until it is written again
    set x = x + 1 [when ...]     writes x at the next tick (Enter, the clock, a row of a file): a loop
    learn k = 1                  a weight: what the network learns of it stays (its next prior is what it believes now)
    input key [= 0]              a node the outside measures (keys, numbers, files)
    output y                     a node the outside reads (shown and heard by the human)
    input v [0 1 -1 0 0]         a node with its dimension [M L T Q K]: given and read in SI; inside, the machine
                                 counts in its own units, where c, hbar, G and kB are 1 (pygrm.units, "ticks")

Sums are multiplications. A signed quantity x is the exponent of a positive one, e^x: x1 = x0 + v * dt is
e^x1 = e^x0 * (e^v)^dt, a product with a power, the kind of relation the GRM solves in log. So a sum relation is
written with + and -, and the machine keeps it as a product of exponentials. Each term may hold numbers, fixed
nodes and ONE free node (with power 1): its coefficient is a number. When that free node is a positive quantity
(g in "v1 = v0 - g * dt"), a converter ties it to its signed twin (~g = g): the one relation between the world of
products (log g) and the world of sums (e^g). It is the only relation that is not straight in log; it is redrawn
around the current values at each round, by the relation itself.

The interpreter (grm_talk.py) adds the questions: ask, why, what-if, solve, relax, sleep, wake...
"""
import math
import os
import re

from i18n import label, tr

DEFAULT_RELATION_SIGMA = 1e-9     # dex: a product relation written without "±" is exact
DEFAULT_SUM_SIGMA = 1e-9          # in the relation's unit: a sum relation written without "±" is exact
DEFAULT_MEASURE_SIGMA = 0.01      # dex
DEFAULT_SIGNED_SIGMA = 1e-3       # in the node's unit
VAR_SIGMA = 1e-9                  # a variable holds its value (as tight as the machine can: 1e-6)
LEARN_PRIOR = 1e3                 # what a weight is before it has seen anything
CONSTANTS = {"pi": math.pi, "e": math.e, "tau": 2 * math.pi, "inf": math.inf}


class Network:
    """What has been said: nodes, relations, measurements, and the networks that can be called."""

    def __init__(self):
        self.nodes = {}        # name -> {"guess": value, "fixed": bool, "signed": bool}
        # product: {"kind": "product", "name", "terms": {node: power}, "rhs": log10 constant, "sigma": dex, "text"}
        # sum:     {"kind": "sum", "name", "terms": [(coef, {node: power})], "sigma", "text"}   sum of terms = 0
        # keep:    {"kind": "keep", "name", "node", "op": ">=" | "<=", "bound", "when": [(node, lo, hi)], "text"}
        self.relations = []
        self.measured = {}     # name -> (value, sigma): dex for a positive node, its own unit for a signed one
        self.networks = {}     # name -> (params, lines)
        self.recording = None  # (name, params, lines) while a network is being written
        self.calls = []        # (network, {param: value}) in the order they were made
        self.sets = []         # {"target", "source", "when"}: written at each tick
        self.ticks = 0         # how many ticks of the clock this network has lived
        self.links = []        # what groups of weights have learned together: {"names", "L", "h"}
        self.aliases = {}      # a name that became another node by a fusion -> that node
        self.inverses = {}     # a name that became the inverse of another node (a period, a frequency) -> that node
        self.fusions = []      # what was fused, and why
        self.seen = {}         # the last values given to each input (what the fusion routine looks at)
        self.rows = []         # the inputs of each moment seen (what the machine finds relations in)
        self.tension = {}      # how far each relation was from holding, moment after moment (in its sigmas)
        self.found = []        # the relations it found by itself
        # mind.py: what the machine feels and keeps
        self.use = {"nodes": {}, "relations": {}}      # how much each node and relation has worked lately (traces)
        self.origin = {"nodes": {}, "relations": {}}   # where each one comes from: base, written, found
        self.mood = {}         # its neuromodulators, its flourishing
        self.capacity = None   # how many links (synapses) it may hold (None: what the host's budget allows)
        self.host = {}         # what the host gives (measured each session, not remembered: another host, another
                               # budget)

    def relation(self, name):
        for r in self.relations:
            if r["name"] == name:
                return r
        return None

    def put(self, rel):
        old = self.relation(rel["name"])
        if old:
            self.relations[self.relations.index(old)] = rel
        else:
            self.relations.append(rel)

    def nodes_of(self, rel):
        if rel.get("kind", "product") == "product":
            return list(rel["terms"]) + [n for n, _, _ in rel.get("when", [])]
        if rel["kind"] == "log":
            return [rel["log"], rel["node"]]
        if rel["kind"] == "sum":
            return [n for _, t in rel["terms"] for n in t] + [n for n, _, _ in rel.get("when", [])]
        return [rel["node"]] + [n for n, _, _ in rel["when"]]

    def degree(self, node):
        return sum(1 for r in self.relations if node in self.nodes_of(r))

    def clear(self):
        self.__init__()


class TalkError(Exception):
    located = False          # already says the file and line it comes from


_NUMBER = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?"
_NAME = r"[A-Za-z_~][A-Za-z0-9_]*"


def _number(text):
    t = text.strip()
    if t in CONSTANTS:             # pi, e, tau, inf: lower case only (E, PI are names of nodes)
        return CONSTANTS[t]
    t = t.lower()
    if t in ("-inf", "+inf"):
        return -math.inf if t[0] == "-" else math.inf
    try:
        return float(t)
    except ValueError:
        pass
    # a little arithmetic on numbers, as a call writes it ("{top} - 0.25" becomes "2 - 0.25")
    if re.fullmatch(r"[0-9eE.+\-*/() ]+", t) and re.search(r"\d", t):
        try:
            return float(eval(t, {"__builtins__": {}}, {}))
        except Exception:  # noqa: BLE001
            pass
    raise TalkError(tr("not a number: '{text}'", text=text))


def _sigma(text, default):
    """'1%' -> dex, '0.004 dex' or '0.004' -> dex."""
    if text is None:
        return default
    t = text.strip().lower().replace(" ", "")
    if t.endswith("%"):
        return math.log10(1.0 + _number(t[:-1]) / 100.0)
    if t.endswith("dex"):
        t = t[:-3]
    return _number(t)


def parse_side(text, signed_ok=False):
    """'S * H^2 / tP^-1 * 2' -> ({node: power}, log10 of the numbers). With signed_ok, numbers may be any sign and
    the coefficient is returned as a number instead of its log."""
    text = text.strip()
    if not text:
        raise TalkError(tr("an empty side of a relation"))
    terms, log_const, coef = {}, 0.0, 1.0
    parts = re.split(r"\s*([*/])\s*", text)
    sign = 1.0
    for part in parts:
        if part in ("*", "/"):
            sign = 1.0 if part == "*" else -1.0
            continue
        if not part:
            continue
        base, _, exp = part.partition("^")
        power = sign * (_number(exp.strip("() ")) if exp else 1.0)
        base = base.strip("() ")
        if re.fullmatch(_NUMBER, base) or base in CONSTANTS:
            value = _number(base)
            if signed_ok:
                coef *= value ** power
            else:
                if value <= 0:
                    raise TalkError(tr("a product relation multiplies positive quantities: '{base}'", base=base))
                log_const += power * math.log10(value)
        elif re.fullmatch(_NAME, base):
            terms[base] = terms.get(base, 0.0) + power
        else:
            raise TalkError(tr("cannot read '{part}'", part=part))
        sign = 1.0
    return terms, (coef if signed_ok else log_const)


def _split_sum(text):
    """'x0 + v * dt - 3' -> [(+1, 'x0'), (+1, 'v * dt'), (-1, '3')]: + and - at the top level (not in 1e-5 or
    in a power ^-2)."""
    text = re.sub(r"([*/^(])\s+", r"\1", text.strip())     # "a * -2": the - belongs to the number
    pieces = re.split(r"(?<![0-9.][eE])(?<![*/^(])\s*([+-])\s*", text)
    out, sign = [], 1.0
    for p in pieces:
        if p == "+":
            continue
        if p == "-":
            sign = -sign
            continue
        if p.strip():
            out.append((sign, p.strip()))
        sign = 1.0
    return out


def _conditions(net, when):
    """'x1 in 3 .. 8 and y0 in 2 .. inf' -> [(node, lo, hi)]"""
    conds = []
    if when and when.strip():
        for c in re.split(r"\s+and\s+", when.strip()):
            cm = re.fullmatch(rf"({_NAME})\s+in\s+(\S+)\s*\.\.\s*(\S+)", c.strip())
            if not cm:
                raise TalkError(tr("cannot read the condition '{c}' (node in lo .. hi)", c=c))
            conds.append((cm.group(1), _number(cm.group(2)), _number(cm.group(3))))
            net.nodes.setdefault(cm.group(1), {"guess": 0.0, "fixed": False, "signed": True})
    return conds


def _dim(text):
    """'[0 1 -2 0 0]' -> [0, 1, -2, 0, 0] (mass, length, time, charge, temperature), and the text without it."""
    m = re.search(r"\[([^\]]*)\]\s*$", text)
    if not m:
        return None, text
    parts = m.group(1).replace(",", " ").split()
    if len(parts) != 5:
        raise TalkError(tr("a dimension is [M L T Q K]: five powers"))
    return [float(p) for p in parts], text[:m.start()].strip()


def _inverted(net, terms):
    """A name fused as the inverse of a node is that node to the power -1 (one node, its inverse included)."""
    if not getattr(net, "inverses", None):
        return terms
    out = {}
    for n, p in terms.items():
        if n in net.inverses:
            n, p = net.inverses[n], -p
        out[n] = out.get(n, 0.0) + p
    return {n: p for n, p in out.items() if abs(p) > 1e-15}


def _is_sum(net, left, right):
    l, r = _split_sum(left), _split_sum(right)
    if len(l) > 1 or len(r) > 1 or left.strip().startswith("-") or right.strip().startswith("-"):
        return True
    if right.strip() in ("0", "0.0") or left.strip() in ("0", "0.0"):
        return True
    for side in (left, right):
        for name in re.findall(_NAME, side):
            if net.nodes.get(name, {}).get("signed"):
                return True
    return False


def _relate(net, rest):
    name, colon, body = rest.partition(":")
    if not colon:
        body, name = rest, f"r{len(net.relations) + 1}"
    name = name.strip()
    body, _, when = body.partition(" when ")
    body, _, sig = body.partition("±")
    if "=" not in body:
        raise TalkError(tr("relate NAME: left = right [+/- sigma] [when node in lo .. hi and ...]"))
    conds = _conditions(net, when)
    lg = re.fullmatch(rf"\s*({_NAME})\s*=\s*ln\(\s*({_NAME})\s*\)\s*", body)
    if lg:                       # the converter of exponentials: L = ln(y), y positive (in log), L signed
        L, y = lg.group(1), lg.group(2)
        net.nodes.setdefault(L, {"guess": 0.0, "fixed": False, "signed": True})
        net.nodes.setdefault(y, {"guess": 1.0, "fixed": False, "signed": False})
        if net.nodes[y].get("signed"):
            raise TalkError(tr("ln({y}): {y} is signed; a logarithm takes a positive quantity", y=y))
        if not net.nodes[L].get("signed"):
            raise TalkError(tr("{L} = ln({y}): {L} must be signed (a logarithm can be negative)", L=L, y=y))
        net.put({"kind": "log", "name": name, "log": L, "node": y, "text": body.strip(), "when": []})
        return tr("relation {name}: {L} = ln({y}) (the converter between a quantity and its exponent)", name=name, L=L,
                  y=y)
    left, right = body.split("=", 1)
    if _is_sum(net, left, right):
        terms = []
        for side, s0 in ((left, 1.0), (right, -1.0)):
            for s, piece in _split_sum(side):
                t, c = parse_side(piece, signed_ok=True)
                if c != 0.0:
                    terms.append((s0 * s * c, _inverted(net, t)))
        if not any(t for _, t in terms):
            raise TalkError(tr("a relation needs at least one node"))
        for _, t in terms:
            for n in t:
                net.nodes.setdefault(n, {"guess": 0.0, "fixed": False, "signed": True})
        rel = {"kind": "sum", "name": name, "terms": terms, "sigma": _number(sig) if sig.strip() else DEFAULT_SUM_SIGMA,
               "text": body.strip() + (f" when {when.strip()}" if conds else ""), "when": conds}
        net.put(rel)
        return tr("relation {name} (a sum, kept as a product of exponentials): {text}", name=name, text=rel["text"])
    lt, lc = parse_side(left)
    rt, rc = parse_side(right)
    lt, rt = _inverted(net, lt), _inverted(net, rt)
    terms = dict(lt)
    for n, p in rt.items():
        terms[n] = terms.get(n, 0.0) - p
    terms = {n: p for n, p in terms.items() if abs(p) > 1e-15}
    if not terms:
        raise TalkError(tr("a relation needs at least one node"))
    for n in terms:
        net.nodes.setdefault(n, {"guess": 1.0, "fixed": False, "signed": False})
        if net.nodes[n].get("signed"):
            raise TalkError(tr("{n} is signed: a product relation needs positive quantities", n=n))
    rel = {"kind": "product", "name": name, "terms": terms, "rhs": rc - lc,
           "sigma": _sigma(sig or None, DEFAULT_RELATION_SIGMA),
           "text": body.strip() + (f" when {when.strip()}" if conds else ""), "when": conds}
    net.put(rel)
    return tr("relation {name}: {text}", name=name, text=rel["text"])


def _keep(net, rest):
    name, colon, body = rest.partition(":")
    if not colon:
        body, name = rest, f"k{len(net.relations) + 1}"
    name = name.strip()
    cond, _, when = body.partition(" when ")
    m = re.fullmatch(rf"\s*({_NAME})\s*(>=|<=)\s*(\S+)\s*", cond)
    if not m:
        raise TalkError(tr("keep NAME: node >= value [when node in lo .. hi and ...]"))
    conds = _conditions(net, when)
    node = m.group(1)
    for n in [node] + [c[0] for c in conds]:
        net.nodes.setdefault(n, {"guess": 0.0, "fixed": False, "signed": True})
    rel = {"kind": "keep", "name": name, "node": node, "op": m.group(2), "bound": _number(m.group(3)),
           "when": conds, "text": body.strip()}
    net.put(rel)
    return tr("contact {name}: {text}", name=name, text=rel["text"])


SHORT = {          # the short forms of the statements (first word of a line only)
    "nd": "node", "rel": "relate", "obs": "observe", "fgt": "forget", "kp": "keep", "net": "network", "cl": "call",
    "lrn": "learn", "inp": "input", "out": "output",
}


def normal(line):
    """A line as the language reads it: a short form at its head made whole, `+/-` written `±` (the sign is not on
    every keyboard)."""
    line = line.replace("+/-", "±")
    head = line.lstrip()
    word, sep, rest = head.partition(" ")
    if word.lower() in SHORT:
        return line[:len(line) - len(head)] + SHORT[word.lower()] + sep + rest
    return line


def statement(net, line, base=None):
    """Reads one statement into the network. Returns a short text of what was done, or None if the line is not a
    statement of the language (a question for the interpreter). base: the folder `use` reads from."""
    line = normal(line.split("#", 1)[0].rstrip())
    if net.recording is not None:
        if line.strip().lower() == "end":
            name, params, lines = net.recording
            net.networks[name] = (params, lines)
            net.recording = None
            return tr("network {name}({params}): {n} lines", name=name, params=", ".join(params), n=len(lines))
        if line.strip():
            net.recording[2].append(line.strip())
        return ""
    line = line.strip()
    if not line:
        return ""
    if net.aliases:         # a name fused into another node means that node
        line = re.sub(r"(?<![A-Za-z0-9_.~])" + _NAME, lambda m_: net.aliases.get(m_.group(0), m_.group(0)), line)
    word, _, rest = line.partition(" ")
    word = word.lower()
    rest = rest.strip()
    if word in ("var", "learn", "input", "output"):
        return _role(net, word, rest)
    if word == "set":
        return _set(net, rest, base)
    if word == "fuse":
        return fuse(net, *rest.split())
    if word == "node":
        dim, rest = _dim(rest)
        m = re.fullmatch(rf"({_NAME})\s*(?:=\s*(\S+))?((?:\s+(?:fixed|signed))*)", rest)
        if not m:
            raise TalkError(tr("node NAME [= value] [fixed] [signed]"))
        name, value, flags = m.group(1), m.group(2), m.group(3).split()
        old = net.nodes.get(name, {})
        signed = "signed" in flags or old.get("signed", False)
        guess = _number(value) if value else old.get("guess", 0.0 if signed else 1.0)
        if not signed and guess <= 0:
            raise TalkError(tr("a node is a positive quantity (solved in log10): say `signed` for a signed one"))
        net.nodes[name] = dict(old, guess=guess, fixed="fixed" in flags, signed=signed)
        if dim is not None:
            net.nodes[name]["dim"] = dim
        return tr("node {name} = {value}", name=name, value=f"{guess:g}") + (" (" + tr("fixed") + ")" if "fixed" in flags
                                                                             else "") + (" " + tr("signed") if signed
                                                                                         else "")
    if word == "relate":
        return _relate(net, rest)
    if word == "keep":
        return _keep(net, rest)
    if word == "observe":
        m = re.fullmatch(rf"({_NAME})\s*=\s*([^±]+?)\s*(?:±\s*(.+))?", rest)
        if not m:
            raise TalkError(tr("observe NAME = value [+/- 1% | +/- 0.004 dex]"))
        name, value = m.group(1), _number(m.group(2))
        node = net.nodes.get(name)
        if node and node.get("signed"):
            sg = m.group(3)
            if sg and sg.strip().endswith("%"):
                s = abs(value) * _number(sg.strip()[:-1]) / 100.0
            else:
                # as the senses do (Weber's law): a value said without its uncertainty is known to a thousandth of
                # itself (and never better than a thousandth of a unit)
                s = _number(sg) if sg else DEFAULT_SIGNED_SIGMA * max(abs(value), 1.0)
            if not s > 0:
                raise TalkError(tr("a measurement needs a positive sigma"))
            net.measured[name] = (value, s)
            return tr("observed {name} = {value} ± {s}", name=name, value=f"{value:g}", s=f"{s:.3g}")
        if value <= 0:
            raise TalkError(tr("{name} is a positive quantity: say `node {name} signed` first for a signed one", name=name))
        net.nodes.setdefault(name, {"guess": value, "fixed": False, "signed": False})
        net.measured[name] = (value, _sigma(m.group(3), DEFAULT_MEASURE_SIGMA))
        return tr("observed {name} = {value} ± {s} dex", name=name, value=f"{value:g}", s=f"{net.measured[name][1]:.3g}")
    if word == "forget":
        if rest in net.measured:
            del net.measured[rest]
            return tr("forgot the measurement of {name}", name=rest)
        raise TalkError(tr("{name} is not measured", name=rest))
    if word == "network":
        m = re.fullmatch(rf"({_NAME})\s*\(([^)]*)\)", rest)
        if not m:
            raise TalkError(tr("network NAME(param, param...) ... end"))
        params = [p.strip() for p in m.group(2).split(",") if p.strip()]
        net.recording = (m.group(1), params, [])
        return ""
    if word == "call":
        m = re.fullmatch(rf"({_NAME})\s*\(([^)]*)\)", rest)
        if not m or m.group(1) not in net.networks:
            raise TalkError(tr("call NETWORK(param=value, ...): no network '{name}'", name=rest.split("(")[0].strip()))
        params, lines = net.networks[m.group(1)]
        given = {}
        for kv in m.group(2).split(","):
            if kv.strip():
                k, _, v = kv.partition("=")
                given[k.strip()] = v.strip()
        missing = [p for p in params if p not in given]
        if missing:
            raise TalkError(tr("call {name}: missing {missing}", name=m.group(1), missing=", ".join(missing)))
        for ln in lines:
            text = ln
            for k, v in given.items():
                text = text.replace("{" + k + "}", v)
            statement(net, text, base)
        net.calls.append((m.group(1), given))
        return tr("called {name}({given})", name=m.group(1), given=", ".join(f"{k}={v}" for k, v in given.items()))
    if word == "use":
        path = rest
        if base and not os.path.isabs(path) and not os.path.exists(path):
            path = os.path.join(base, path)
        if not os.path.exists(path):
            raise TalkError(tr("no file {name}", name=rest))
        count = 0
        with open(path, encoding="utf-8") as f:
            for number, ln in enumerate(f, 1):
                try:
                    if statement(net, ln, os.path.dirname(os.path.abspath(path))):
                        count += 1
                except TalkError as e:
                    if e.located:      # already located (a file used by this one)
                        raise
                    err = TalkError(tr("in {file}, line {n}: {line}", file=os.path.basename(path), n=number,
                                       line=ln.strip()) + f"\n    {e}")
                    err.located = True
                    raise err from None
        return tr("used {file}: {n} statements", file=os.path.basename(path), n=count)
    return None


def _rename(d, old, new):
    return {(new if k == old else k): v for k, v in d.items()}


def fuse(net, keep=None, gone=None, *extra):
    """fuse A B: B was A under another name: one node, every relation of B now on A (no node written twice).
    What was measured of both is put together (their weighted mean).
    fuse A B inverse: B was the inverse of A (a period and a frequency): one node, B is A^-1 in every relation."""
    if extra == ("inverse",):
        return _fuse_inverse(net, keep, gone)
    if not keep or not gone or extra:
        raise TalkError(tr("fuse A B [inverse]: B becomes A (or its inverse)"))
    for n in (keep, gone):
        if n not in net.nodes:
            raise TalkError(tr("no node {name}", name=n))
    if keep == gone:
        return tr("{name} is already one node", name=keep)
    ka, kb = net.nodes[keep], net.nodes[gone]
    if ka.get("signed") and not kb.get("signed"):
        raise TalkError(tr("fuse {keep} {gone}: keep the positive one ({gone}) and fuse the signed one into it", keep=keep,
                              gone=gone))
    if not ka.get("signed") and kb.get("signed"):
        # a signed node becomes a positive one: it must have been positive, and it cannot be in a product as signed
        if gone in net.measured and net.measured[gone][0] <= 0:
            raise TalkError(tr("fuse {keep} {gone}: {gone} has been {v}, {keep} is positive", keep=keep, gone=gone,
                              v=f"{net.measured[gone][0]:g}"))
        if gone in net.measured:
            v, sg = net.measured[gone]
            net.measured[gone] = (v, max(sg / (v * math.log(10)), 1e-9))     # its uncertainty, in dex
    for r in net.relations:
        kind = r.get("kind", "product")
        if kind == "product":
            terms = {}
            for n, p in r["terms"].items():
                n = keep if n == gone else n
                terms[n] = terms.get(n, 0.0) + p
            r["terms"] = {n: p for n, p in terms.items() if abs(p) > 1e-15}
        elif kind == "sum":
            r["terms"] = [(c, _rename(t, gone, keep)) for c, t in r["terms"]]
        elif kind == "log":
            r["node"] = keep if r["node"] == gone else r["node"]
            r["log"] = keep if r["log"] == gone else r["log"]
        else:
            r["node"] = keep if r["node"] == gone else r["node"]
        if "when" in r:
            r["when"] = [((keep if n == gone else n), lo, hi) for n, lo, hi in r["when"]]
    for st in net.sets:
        st["target"] = keep if st["target"] == gone else st["target"]
        st["source"] = keep if st["source"] == gone else st["source"]
        st["when"] = [((keep if n == gone else n), lo, hi) for n, lo, hi in st["when"]]
    if gone in net.measured:
        vb, sb = net.measured.pop(gone)
        if keep in net.measured:
            va, sa = net.measured[keep]
            if not net.nodes[keep].get("signed"):
                va, vb = math.log10(va), math.log10(vb)
            w1, w2 = 1 / sa ** 2, 1 / sb ** 2
            v = (w1 * va + w2 * vb) / (w1 + w2)
            net.measured[keep] = (v if net.nodes[keep].get("signed") else 10 ** v, (w1 + w2) ** -0.5)
        else:
            net.measured[keep] = (vb, sb)
    for flag in ("var", "learn", "input", "output"):
        if net.nodes[gone].get(flag):
            net.nodes[keep][flag] = True
    del net.nodes[gone]
    for link in getattr(net, "links", []):
        link["names"] = [keep if n == gone else n for n in link["names"]]
    for a, b in list(net.aliases.items()):
        if b == gone:
            net.aliases[a] = keep
    net.aliases[gone] = keep
    if gone in net.seen:
        net.seen.setdefault(keep, []).extend(net.seen.pop(gone))
    return tr("fused: {gone} is {keep} (one node)", gone=gone, keep=keep)


def _fuse_inverse(net, keep, gone):
    for n in (keep, gone):
        if n not in net.nodes:
            raise TalkError(tr("no node {name}", name=n))
    for n in (keep, gone):
        if n in net.measured and net.measured[n][0] <= 0:
            raise TalkError(tr("fuse {keep} {gone} inverse: {n} has been {v}: an inverse is positive", keep=keep, gone=gone,
                              n=n, v=f"{net.measured[n][0]:g}"))
    for r in net.relations:
        if r.get("kind") in ("keep", "log") and gone in net.nodes_of(r):
            raise TalkError(tr("fuse {keep} {gone} inverse: {gone} is in {r}", keep=keep, gone=gone, r=r["name"]))
    for st in net.sets:
        if gone in (st["target"], st["source"]) or any(n == gone for n, _, _ in st["when"]):
            raise TalkError(tr("fuse {keep} {gone} inverse: {gone} is written at each tick", keep=keep, gone=gone))
    for name in (keep, gone):                     # an inverse is a positive quantity: solved in log
        spec = net.nodes[name]
        if spec.get("signed"):
            spec["signed"] = False
            if name in net.measured:
                v, sg = net.measured[name]
                net.measured[name] = (v, max(sg / (v * math.log(10)), 1e-9))
            if spec.get("guess", 0) <= 0:
                spec["guess"] = net.measured.get(name, (1.0,))[0]
    for r in net.relations:
        kind = r.get("kind", "product")
        if kind == "product":
            terms = {}
            for n, p in r["terms"].items():
                n, p = (keep, -p) if n == gone else (n, p)
                terms[n] = terms.get(n, 0.0) + p
            r["terms"] = {n: p for n, p in terms.items() if abs(p) > 1e-15}
        elif kind == "sum":
            new = []
            for c, t in r["terms"]:
                t2 = {}
                for n, p in t.items():
                    n, p = (keep, -p) if n == gone else (n, p)
                    t2[n] = t2.get(n, 0.0) + p
                new.append((c, {n: p for n, p in t2.items() if abs(p) > 1e-15}))
            r["terms"] = new
        if "when" in r and any(n == gone for n, _, _ in r["when"]):
            raise TalkError(tr("fuse {keep} {gone} inverse: {gone} is a condition of {r}", keep=keep, gone=gone, r=r["name"]))
    if gone in net.measured:
        vb, sb = net.measured.pop(gone)
        if keep in net.measured:
            va, sa = net.measured[keep]
            la, lb = math.log10(va), -math.log10(vb)
            w1, w2 = 1 / sa ** 2, 1 / sb ** 2
            net.measured[keep] = (10 ** ((w1 * la + w2 * lb) / (w1 + w2)), (w1 + w2) ** -0.5)
        else:
            net.measured[keep] = (1.0 / vb, sb)
    for flag in ("input", "output"):
        if net.nodes[gone].get(flag):
            net.nodes[keep][flag] = True
    del net.nodes[gone]
    net.inverses[gone] = keep
    for a, b in list(net.inverses.items()):
        if b == gone:
            net.inverses[a] = keep
    if gone in net.seen:
        net.seen.setdefault(keep, []).extend(1.0 / v for v in net.seen.pop(gone) if v)
    return tr("fused: {gone} is {keep}^-1 (one node, its inverse included)", gone=gone, keep=keep)


ROLES = {"var": "a variable", "learn": "a weight it learns", "input": "an input", "output": "an output"}


def _role(net, word, rest):
    """var / learn / input / output NAME [= value] [dim]: a signed node with a role."""
    dim, rest = _dim(rest)
    m = re.fullmatch(rf"({_NAME})\s*(?:=\s*(\S+))?(\s+positive)?", rest)
    if not m:
        raise TalkError(tr("{word} NAME [= value] [positive] [M L T Q K]", word=word))
    name, value, positive = m.group(1), m.group(2), bool(m.group(3))
    old = net.nodes.get(name, {})
    positive = positive or (name in net.nodes and not old.get("signed", True))
    guess = _number(value) if value else old.get("guess", 1.0 if positive else 0.0)
    if positive and guess <= 0:
        raise TalkError(tr("{name} is positive: its value must be above 0", name=name))
    spec = dict(old, guess=guess, fixed=False, signed=not positive)
    spec[word] = True
    if dim is not None:
        spec["dim"] = dim
    net.nodes[name] = spec
    if word in ("var", "input") and (value or name not in net.measured):
        net.measured[name] = (guess, VAR_SIGMA if not positive else 1e-6)
    if word == "learn":
        net.measured[name] = (guess, LEARN_PRIOR if not positive else 3.0)
    return label(ROLES[word]) + f"{name} = {guess:g}"


def _set(net, rest, base):
    """set x = EXPR [when ...]: at each tick x takes the value of EXPR (computed by the network)."""
    body, _, when = rest.partition(" when ")
    m = re.fullmatch(rf"({_NAME})\s*=\s*(.+)", body.strip())
    if not m:
        raise TalkError(tr("set NAME = expression [when node in lo .. hi and ...]"))
    target, expr = m.group(1), m.group(2).strip()
    if target not in net.nodes:
        _role(net, "var", target)
    conds = _conditions(net, when)
    if re.fullmatch(_NAME, expr) and expr in net.nodes:
        source = expr
    else:
        k = sum(1 for s_ in net.sets if s_["target"] == target) + 1
        source = f"{target}__next{k}"
        spec = net.nodes[target]
        net.nodes[source] = {"guess": spec["guess"], "fixed": False, "signed": spec.get("signed", False)}
        _relate(net, f"set_{target}_{k}: {source} = {expr}")
    net.sets.append({"target": target, "source": source, "when": conds, "text": " ".join(rest.split())})
    return tr("at each tick {target} <- {expr}", target=target, expr=expr) + (f" when {when.strip()}" if conds else "")


def from_store(store, net=None):
    """A network of a grm-core store (equation/store.py) in the words of this language. Only what the language
    says is kept: positive nodes and product relations ("log"); function and sum relations are left out."""
    net = net or Network()
    left_out = []
    for name, spec in store["nodes_spec"].items():
        if spec.get("scale", "log") != "log" or spec.get("guess", 1.0) <= 0:
            continue
        net.nodes[name] = {"guess": float(spec.get("guess", 1.0)), "fixed": bool(spec.get("fixed", False)),
                           "signed": False}
    for k, rel in enumerate(store["relations_spec"]):
        kind = rel.get("type", "log")
        terms = rel.get("terms", {})
        if kind != "log" or callable(rel.get("rhs")) or not terms or not all(n in net.nodes for n in terms):
            left_out.append(rel.get("name", f"#{k}"))
            continue
        net.relations.append({"kind": "product", "name": rel.get("name", f"r{k + 1}"),
                              "terms": {n: float(p) for n, p in terms.items()},
                              "rhs": float(rel.get("rhs", 0.0)), "sigma": float(rel.get("sigma", 1e-3)),
                              "text": " * ".join(f"{n}^{p:g}" for n, p in terms.items()) + f" = 10^{float(rel.get('rhs', 0.0)):.4g}"})
    for name, m in store["measured"].items():
        if name not in net.nodes:
            continue
        value, sigma = (m if isinstance(m, (list, tuple)) else (m, DEFAULT_MEASURE_SIGMA))
        if value and value > 0:
            net.measured[name] = (float(value), float(sigma))
    return net, left_out
