# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Anthony Charretier
"""Seeing the machine work: a round at a time, breakpoints (watch), and why a node has its value.

A tick is a few rounds: in each, the nodes that heard something new tell their relations, and the relations that
heard something new answer their nodes, until nothing new is said (then the writes of `set`). Stepping a round at
a time shows that conversation: who moved, who worked.

    watch NODE in LO .. HIGH [and ...]   stops when the condition becomes true
    watch NODE                           stops when its value changes
    watch RELATION                       stops when it stops holding (more than 1 sigma from it)

A node's value is what all its relations say of it, each weighted by how sure it is (belief propagation: the
precisions add up). `why NODE` shows those messages, their share, and what each relation heard from its other
nodes.
"""
import math
import re

from i18n import colon, tr
from language import TalkError, _number

NAME = r"[A-Za-z_][A-Za-z0-9_]*"
SHOWN = 8          # at most this many messages are shown by `why`
FAINT = 1e-3       # a message that brings less than this share of what is known of a node is not shown
CHANGE = 1e-12     # a relative change smaller than this is not a change


# ---------------------------------------------------------------------- breakpoints
class Watch:
    def __init__(self, text, kind, target, conds=()):
        self.text, self.kind, self.target, self.conds = text, kind, target, list(conds)
        self.last = None


def parse(vm, text):
    """A watch from what was typed after `watch`."""
    net = vm.net
    text = " ".join(text.split())
    if " in " in text:
        conds = []
        for c in re.split(r"\s+and\s+", text):
            cm = re.fullmatch(rf"({NAME})\s+in\s+(\S+)\s*\.\.\s*(\S+)", c.strip())
            if not cm:
                raise TalkError(tr("cannot read the condition '{c}' (node in lo .. hi)", c=c))
            name = net.aliases.get(cm.group(1), cm.group(1))
            if name not in net.nodes:
                raise TalkError(tr("no node {name}", name=name))
            conds.append((name, _number(cm.group(2)), _number(cm.group(3))))
        return Watch(text, "when", None, conds)
    name = net.aliases.get(text, text)
    if name in net.nodes:
        return Watch(text, "change", name)
    if net.relation(name) is not None:
        return Watch(text, "holds", name)
    raise TalkError(tr("no node or relation {name}", name=text))


def state(vm, w):
    """What a watch looks at, now (without running the machine)."""
    m = vm.machine
    if m is None:
        return None
    try:
        if w.kind == "when":
            return all(lo <= m.value_si(n) <= hi for n, lo, hi in w.conds)
        if w.kind == "change":
            return m.value_si(w.target)
        f = next((f for f in m.factors if f.name == w.target), None)
        if f is None or f.kind not in ("relation", "nonlinear") or f.w <= 0 or (f.watch and not f.active):
            return True                         # a relation that does not act cannot fail to hold
        return abs(m.residual(f)) < 1.0
    except (KeyError, OverflowError, ValueError, ZeroDivisionError):
        return None


def arm(vm, w):
    """A new watch starts from what it sees now: a condition already true does not stop at once."""
    vm.m()
    w.last = state(vm, w)
    return w


def check(vm):
    """The watches that have just been met: [what is said]. Each remembers what it saw."""
    said = []
    for w in vm.watches:
        now = state(vm, w)
        if now is None:
            continue
        before, w.last = w.last, now
        if before is None:
            continue
        if w.kind == "when" and now and not before:
            said.append(tr("watch: {text} (tick {tick})", text=w.text, tick=vm.machine.ticks))
        elif w.kind == "change" and _changed(before, now):
            said.append(tr("watch: {name} changed, {a} -> {b} (tick {tick})", name=w.target, a=_fmt(before),
                           b=_fmt(now), tick=vm.machine.ticks))
        elif w.kind == "holds" and before and not now:
            said.append(tr("watch: {name} no longer holds (tick {tick})", name=w.target, tick=vm.machine.ticks))
    return said


def _changed(a, b):
    return abs(b - a) > CHANGE * max(abs(a), abs(b), 1e-300)


# ---------------------------------------------------------------------- a round at a time
def public(name):
    """A name as the human wrote it (the signed twin of a positive node is that node)."""
    return name[1:] if name.startswith("~") else name


def round_report(m, before, woken, moved_from, fresh=()):
    """What one round did: the nodes that moved (name, from, to), the relations that worked."""
    moved = []
    for i in sorted(before):
        name = m.var_names[i]
        if "__" in name or i not in moved_from:
            continue
        if m.last_move[i] > 1e-12:
            try:
                to = m.value_si(name)
                frm = _si(m, i, moved_from[i])
            except (OverflowError, ValueError):
                continue
            moved.append((public(name), frm, to))
    worked = set()
    for f in woken:
        fac = m.factors[f]
        if fac.kind in ("relation", "nonlinear", "keep"):
            worked.add(fac.name)
        elif fac.kind == "anchor" and f in fresh and "__" not in m.var_names[fac.vars[0]]:   # a new measurement
            worked.add(tr("the measurement of {name}", name=public(m.var_names[fac.vars[0]])))
        elif fac.kind == "joint":
            worked.add(tr("the weights' memory"))
    return moved, sorted(worked)


def step_lines(report):
    """The words of a step: one line a round, and the end of the tick."""
    lines = []
    for r in report:
        if r.get("round") is not None:
            moved = ", ".join(f"{n} {_fmt(a)} -> {_fmt(b)}" for n, a, b in r["moved"][:6])
            if len(r["moved"]) > 6:
                moved += " ..."
            lines.append(tr("tick {tick}, round {round}", tick=r["tick"] + 1, round=r["round"]) + colon()
                         + (tr("{names} worked", names=", ".join(r["worked"][:6])) if r["worked"] else
                            tr("no relation worked"))
                         + (tr("; ") + tr("moved: {moved}", moved=moved) if moved else ""))
        if r.get("done") is not None:
            writes = ", ".join(f"{k} <- {_fmt(v)}" for k, v in r["done"].items())
            lines.append(tr("tick {tick} done in {rounds} rounds", tick=r["tick"], rounds=r["rounds"])
                         + (tr("; ") + tr("written: {writes}", writes=writes) if writes else ""))
    return lines


# ---------------------------------------------------------------------- why
def why(vm, name):
    """Why a node has its value: the messages of its relations, each with its share and what it heard."""
    net = vm.net
    name = net.aliases.get(name, name)
    if name in net.inverses:
        return [tr("{name} is {other}^-1: why {other}", name=name, other=net.inverses[name])]
    if name not in net.nodes:
        raise TalkError(tr("no node {name}", name=name))
    m = vm.m()
    if name in m.fixed:
        return [tr("{name} = {value}: fixed, it does not move", name=name, value=_fmt(m.value_si(name)))]
    value = vm.get(name)
    i = m.index[name]
    unit = "" if m.is_signed(i) else " dex"
    lines = [tr("why {name} = {value}", name=name, value=_fmt(value)) + f"  (± {m.sigma(name):.3g}{unit})"]
    said = []
    for f_i, s in m.node_factors[i]:
        f = m.factors[f_i]
        lam = f.out_lam[s]
        if lam <= 0:
            continue
        said.append((lam, f, s))
    total = sum(lam for lam, _, _ in said) or 1.0
    said.sort(key=lambda t: -t[0])
    faint = [t for t in said if t[0] / total < FAINT]
    said = [t for t in said if t[0] / total >= FAINT]
    for lam, f, s in said[:SHOWN]:
        share = 100.0 * lam / total
        try:
            says = _fmt(_si(m, i, f.out_eta[s] / lam))
        except (OverflowError, ValueError):
            says = "?"
        what, heard = _what(vm, m, f, i)
        lines.append(f"  {share:5.1f}%  {what}")
        lines.append("          " + tr("says {value}", value=says) + f"  (± {1 / math.sqrt(lam):.3g}{unit})"
                     + (tr("; ") + tr("from {heard}", heard=heard) if heard else ""))
    if len(said) > SHOWN or faint:
        lines.append("          " + tr("and {n} that say almost nothing of it", n=max(0, len(said) - SHOWN) + len(faint)))
    if not said:
        lines.append("  " + tr("nothing says anything of it yet"))
    return lines


def _what(vm, m, f, i):
    """What a factor is, in words, and what it heard from its other nodes."""
    net = vm.net
    name = m.var_names[i]
    if f.kind == "anchor":
        writers = [st for st in net.sets if st["target"] == name]
        if writers and m.ticks > 0:
            return tr("written at the last tick: {text}", text="; ".join(
                "set " + (st.get("text") or f"{st['target']} = {st['source']}") for st in writers)), ""
        if name in net.measured:
            v, s = net.measured[name]
            return tr("measured: {value}", value=f"{_fmt(v)} ± {s:.3g}"), ""
        return tr("its starting value (nothing measured: a weak hold)"), ""
    if f.kind == "joint":
        return tr("what the weights learned together ({names})", names=", ".join(m.var_names[j] for j in f.vars)), ""
    if f.kind == "convert":
        twin = f.vars[0]
        others = sorted({m.factors[g].name for g, _ in m.node_factors[twin] if m.factors[g] is not f})
        return tr("through its signed twin, from {names}", names=", ".join(others) or "?"), ""
    rel = net.relation(f.name)
    text = rel["text"] if rel else f.text
    kind = tr("contact") if f.kind == "keep" else tr("relation")
    heard = []
    for j in dict.fromkeys(f.vars):
        if j == i or "__" in m.var_names[j]:
            continue
        other = public(m.var_names[j])
        if public(name) == other:
            continue
        try:
            heard.append(f"{other} = {_fmt(m.value_si(m.var_names[j]))}")
        except (OverflowError, ValueError):
            pass
    return f"{kind} {f.name}: {text}", ", ".join(heard[:6]) + (" ..." if len(heard) > 6 else "")


def _si(m, i, u):
    """An internal value of node i (log10 or signed, in the machine's units) as the outside reads it."""
    name = m.var_names[i]
    k = m.shift.get(name, 0.0)
    if m.is_signed(i):
        return u * 10 ** k
    return 10 ** (u + k) if u + k < 308 else math.inf


def _fmt(v):
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, float) and not math.isfinite(v):
        return str(v)
    if v == 0 or (1e-3 <= abs(v) < 1e6):
        return f"{v:.6g}"
    return f"{v:.4e}"
