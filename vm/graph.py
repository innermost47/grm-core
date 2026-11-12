# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Anthony Charretier
"""The network seen: where its nodes and relations go on the screen, and what each one holds (what the mouse shows
when it passes over it). Nothing here depends on the window: body.py draws what this computes.

The picture is a factor graph, as the machine is: a round for each node, a small square for each relation, a line
for each link between them (a synapse). The places come from forces (Fruchterman & Reingold): linked things pull
each other, everything pushes everything away, and a little gravity keeps the whole in view. A few steps are taken
at each redraw, so a network that grows rearranges itself smoothly.
"""
import math
import random

try:
    import numpy as _np
except ImportError:  # pragma: no cover
    _np = None

import mind
from i18n import tr


def picture(net):
    """(nodes, relations, links): the names of the nodes, the names of the relations, and the links
    (relation, node)."""
    nodes = list(net.nodes)
    relations = [r["name"] for r in net.relations]
    links = []
    for r in net.relations:
        for n in dict.fromkeys(net.nodes_of(r)):
            if n in net.nodes:
                links.append((r["name"], n))
    return nodes, relations, links


def writes(net):
    """The writes of each tick: (source, target) pairs (`set target = ...`)."""
    return [(st["source"], st["target"]) for st in net.sets if st["source"] in net.nodes and st["target"] in net.nodes]


def layout(net, places, steps=30, size=1.0, pinned=(), front=None):
    """Moves `places` ({("n" | "r", name): [x, y]}) a few steps toward a calm picture of the network; new things
    appear next to what they are linked to. front: the keys looked at (focus): they draw together, the rest makes
    room around them. Returns places (the same dict)."""
    nodes, relations, links = picture(net)
    keys = [("n", n) for n in nodes] + [("r", r) for r in relations]
    alive = set(keys)
    for k in list(places):
        if k not in alive:
            del places[k]
    neighbours = {}
    for r, n in links:
        neighbours.setdefault(("r", r), []).append(("n", n))
        neighbours.setdefault(("n", n), []).append(("r", r))
    pairs = [(("r", r), ("n", n)) for r, n in links] + [(("n", a), ("n", b)) for a, b in writes(net) if a != b]
    for a, b in pairs[len(links):]:
        neighbours.setdefault(a, []).append(b)
        neighbours.setdefault(b, []).append(a)
    rng = random.Random(len(keys))
    for k in keys:
        if k not in places:
            near = [places[o] for o in neighbours.get(k, []) if o in places]
            if near:
                cx = sum(p[0] for p in near) / len(near)
                cy = sum(p[1] for p in near) / len(near)
                places[k] = [cx + rng.uniform(-0.05, 0.05) * size, cy + rng.uniform(-0.05, 0.05) * size]
            else:
                a = rng.uniform(0, 2 * math.pi)
                r0 = rng.uniform(0.2, 0.45) * size
                places[k] = [r0 * math.cos(a), r0 * math.sin(a)]
    n = len(keys)
    if n < 2 or _np is None or steps <= 0:
        return places
    idx = {k: i for i, k in enumerate(keys)}
    P = _np.array([places[k] for k in keys], dtype=float)
    E = _np.array([(idx[a], idx[b]) for a, b in pairs], dtype=int).reshape(-1, 2)
    fixed = _np.array([k in pinned for k in keys])
    member = _np.array([front is not None and k in front for k in keys])
    together = front is not None and 1 < member.sum() < n
    k_opt = size * math.sqrt(1.0 / n) * 1.6
    temp = 0.05 * size
    for _ in range(steps):
        D = P[:, None, :] - P[None, :, :]
        dist2 = (D ** 2).sum(-1) + 1e-9
        F = (D * (k_opt ** 2 / dist2)[:, :, None]).sum(1)          # everything pushes everything away
        if len(E):
            d = P[E[:, 0]] - P[E[:, 1]]
            dl = _np.sqrt((d ** 2).sum(-1)) + 1e-9
            pull = d * (dl / k_opt)[:, None]                       # linked things pull each other
            _np.add.at(F, E[:, 0], -pull)
            _np.add.at(F, E[:, 1], pull)
        F -= P * 0.25 / size                                        # gravity: the whole stays in view
        if together:                                                # focus: the front draws together, the rest
            c = P[member].mean(0)                                   # leaves room around it
            F[member] -= (P[member] - c) * 1.2 / size
            d = P[~member] - c
            dist = _np.sqrt((d ** 2).sum(-1)) + 1e-9
            room = 0.35 * size
            push = _np.clip(room - dist, 0, None) / dist
            F[~member] += d * push[:, None] * 2.0 / size
        length = _np.sqrt((F ** 2).sum(-1)) + 1e-12
        step = F / length[:, None] * _np.minimum(length, temp)[:, None]
        step[fixed] = 0.0
        P += step
        temp *= 0.95
    for i, k in enumerate(keys):
        places[k] = [float(P[i, 0]), float(P[i, 1])]
    return places


def _fmt(v):
    if isinstance(v, float) and not math.isfinite(v):
        return str(v)
    if v == 0 or (1e-3 <= abs(v) < 1e6):
        return f"{v:.6g}"
    return f"{v:.4e}"


def node_card(vm, name):
    """What a node holds: a table. [str (a heading) | (label, value) (a row)]; table() writes it as text."""
    net, m = vm.net, vm.machine
    spec = net.nodes.get(name, {})
    roles = [tr(r) for r in ("input", "output", "var", "learn", "fixed") if spec.get(r)]
    kind = tr("signed") if spec.get("signed") else tr("positive")
    rows = [tr("node {name}", name=shown(net, name)) + f"  ({', '.join(roles + [kind])})"]
    if m is not None and (name in m.index or name in m.fixed):
        try:
            v = m.value_si(name)
            sg = m.sigma(name)
            unit = " SI" if spec.get("dim") else ""
            if spec.get("signed"):
                rows.append((tr("value"), f"{_fmt(v)}{unit}"
                             + (f"  ± {sg:.3g} (" + tr("its unit inside") + ")" if sg < 1e5 else "")))
            else:
                rows.append((tr("value"), f"{_fmt(v)}{unit}" + (f"  ± {sg:.3g} dex" if sg < 1e5 else "")))
            if name in m.index:
                i = m.index[name]
                rows.append((tr("last move"), f"{m.last_move[i]:.3g}"
                             + ("  (" + tr("moving") + ")" if m.last_move[i] > 1e-9 else "")))
        except (KeyError, OverflowError, ValueError):
            pass
    if spec.get("dim"):
        rows.append((tr("dimension"), "[M L T Q K] = [" + " ".join(f"{p:g}" for p in spec["dim"]) + "]"))
    if name in net.measured:
        v, s = net.measured[name]
        rows.append((tr("measured"), f"{_fmt(v)} ± {s:.3g}" + ("" if spec.get("signed") else " dex")))
    aliases = [a for a, b in net.aliases.items() if b == name]
    inverses = [a for a, b in net.inverses.items() if b == name]
    if aliases:
        rows.append((tr("also called"), ", ".join(aliases)))
    if inverses:
        rows.append((tr("its inverse"), ", ".join(inverses)))
    rels = [r["name"] for r in net.relations if name in net.nodes_of(r)]
    rows.append((tr("relations"), (", ".join(shown(net, r) for r in rels[:8]) + (" ..." if len(rels) > 8 else ""))
                 if rels else tr("none")))
    origin = net.origin["nodes"].get(name, "written")
    rows.append((tr("comes from"), _origin(origin)))
    rows.append((tr("use"), f"{net.use['nodes'].get(name, mind.NEW_TRACE):.3g}"))
    tag = net.mood.get("tags", {}).get(name)
    if tag is not None:
        rows.append((tr("learned under"), f"{tr('pleasure') if tag > 0 else tr('displeasure')} ({tag:+.2f})"))
    return rows


def relation_card(vm, name):
    """What a relation holds: a table, as node_card."""
    net, m = vm.net, vm.machine
    rel = net.relation(name)
    if rel is None:
        return [tr("no relation {name}", name=name)]
    kind = rel.get("kind", "product")
    rows = [tr("relation {name}", name=shown(net, name)) + f"  ({_kind(kind)})", text_of(net, rel)]
    if kind in ("product", "sum"):
        rows.append(("sigma", f"{rel['sigma']:.3g}" + (" dex" if kind == "product" else "")))
    if m is not None:
        f = next((f for f in m.factors if f.name == name), None)
        if f is not None:
            if f.kind in ("relation", "nonlinear") and f.w > 0:
                try:
                    r = m.residual(f)
                    rows.append((tr("now"), tr("{s} sigma from holding", s=f"{abs(r):.3g}")
                                 + ("  (" + tr("holds") + ")" if abs(r) < 1 else "")))
                except (OverflowError, ValueError, ZeroDivisionError):
                    pass
            if f.watch:
                rows.append((tr("conditions"), tr("hold: it acts") if f.active else tr("do not hold: it is silent")))
            if f.swing:
                rows.append((tr("swings"), f"{f.swing}" + (", " + tr("damped") + f" ({f.damp:g})" if f.damp else "")))
    weights = [n for n in net.nodes_of(rel) if net.nodes.get(n, {}).get("learn")]
    if weights and m is not None:
        rows.append((tr("weights"), ", ".join(f"{w} = {_fmt(m.value_si(w))}" for w in weights if w in m.index)))
    tension = net.tension.get(name)
    if tension:
        rows.append((tr("last surprise"), tr("{s} sigma ({n} moments kept)", s=f"{tension[-1]:.3g}", n=len(tension))))
    found = next((x for x in net.found if x["relation"] == name), None)
    origin = net.origin["relations"].get(name, "written")
    if found:
        rows.append((tr("comes from"), tr("found by itself at tick {tick}: r² {r2} over {rows} rows",
                                          tick=found["tick"], r2=f"{found['r2']:.6f}", rows=found["rows"])))
    else:
        rows.append((tr("comes from"), _origin(origin)))
    rows.append((tr("use"), f"{net.use['relations'].get(name, mind.NEW_TRACE):.3g}"))
    bits = net.use.get("bits", {}).get(name)
    if bits is not None:
        n_links = len(set(net.nodes_of(rel)))
        rent = mind.price(net) * n_links
        rows.append((tr("information"), tr("{bits} bits a tick; rent {rent} ({n} links)", bits=f"{bits:.3g}",
                                           rent=f"{rent:.3g}", n=n_links)
                     + ("  (" + (tr("pays its rent") if bits >= rent else tr("does not pay its rent")) + ")")))
    return rows


SEP = " │ "       # between the label and the value of a row of a card


def table(rows):
    """A card as lines of text: its headings as they are, its rows in two columns (the label, then the value)."""
    width = max((len(r[0]) for r in rows if isinstance(r, tuple)), default=0)
    return [r if isinstance(r, str) else f"{r[0]:<{width}}{SEP}{r[1]}" for r in rows]


# ---------------------------------------------------------------------- the machine's own helpers, named for a human
def shown(net, name):
    """A name as a human reads it. The helpers a `set` makes are named by what they are: the node that holds the
    next value of n (n__next1) is "next n", the relation that computes it (set_n_1) is "set n"."""
    for k, st in enumerate(net.sets):
        target, source = st["target"], st["source"]
        if name == source and "__next" in source:
            return tr("next {name}", name=target)
        if "__next" in source and name == "set_" + target + "_" + source.rsplit("__next", 1)[1]:
            return f"set {target}"
    return name


def text_of(net, rel):
    """The text of a relation as a human wrote it: a `set` is said as it was written."""
    for st in net.sets:
        source = st["source"]
        if "__next" in source and rel["name"] == "set_" + st["target"] + "_" + source.rsplit("__next", 1)[1]:
            return "set " + (st.get("text") or f"{st['target']} = ...")
    return rel.get("text", "")


def _origin(o):
    return tr({"base": "the base it was born with", "written": "written to it", "found": "found by itself"}.get(o, o))


def _kind(k):
    return tr({"product": "products and powers", "sum": "a sum", "log": "a logarithm", "keep": "a contact"}.get(k, k))


# ---------------------------------------------------------------------- focus: a network in the network
def groups(net):
    """{name: (nodes, relations)} of the networks in the network, as they are now: those recorded (programs, calls,
    files, the base, what was typed) and what the machine found by itself. Names gone (forgotten, fused) are left out
    or followed to the node they became."""
    alive_rel = {r["name"] for r in net.relations}
    out = {}
    recorded = dict(getattr(net, "groups", {}) or {})
    found_rel = [r for r, o in net.origin["relations"].items() if o == "found"]
    found_nodes = [n for n, o in net.origin["nodes"].items() if o == "found"]
    if found_rel or found_nodes:
        g = recorded.get("found", {"nodes": [], "relations": []})
        recorded["found"] = {"nodes": list(g["nodes"]) + found_nodes, "relations": list(g["relations"]) + found_rel}
    for name, g in recorded.items():
        rels = {r for r in g.get("relations", []) if r in alive_rel}
        nodes = {net.aliases.get(n, net.inverses.get(n, n)) for n in g.get("nodes", [])}
        for r in rels:
            nodes |= set(net.nodes_of(net.relation(r)))
        nodes = {n for n in nodes if n in net.nodes}
        if nodes or rels:
            out[name] = (nodes, rels)
    return out


def neighbours(net):
    """{key: set of keys} of the picture: a relation and its nodes, a write of a tick and its two nodes."""
    _, _, links = picture(net)
    near = {}
    for r, n in links:
        near.setdefault(("r", r), set()).add(("n", n))
        near.setdefault(("n", n), set()).add(("r", r))
    for a, b in writes(net):
        near.setdefault(("n", a), set()).add(("n", b))
        near.setdefault(("n", b), set()).add(("n", a))
    return near


def focus_keys(net, spec):
    """What a focus brings to the front: the set of keys ("n" | "r", name), or None for everything.
        ("group", NAME)              the nodes and relations of a program, a call, a file, the base...
        ("node", NAME, DEPTH)        a node, its relations and their nodes, DEPTH relations away (1)
        ("relation", NAME)           a relation and its nodes
        ("between", A, B, ...)       the shortest ways that tie these nodes or relations to each other"""
    if not spec:
        return None
    kind, args = spec[0], spec[1:]
    if kind == "group":
        g = groups(net).get(args[0])
        if g is None:
            return set()
        return {("n", n) for n in g[0]} | {("r", r) for r in g[1]}
    near = neighbours(net)
    if kind == "node":
        name = net.aliases.get(args[0], args[0])
        depth = int(args[1]) if len(args) > 1 else 1
        keys, edge = {("n", name)}, {("n", name)}
        for _ in range(2 * depth):                      # a relation away is two steps: to it, then to its nodes
            edge = {k for e in edge for k in near.get(e, ())} - keys
            keys |= edge
        return keys
    if kind == "relation":
        return {("r", args[0])} | near.get(("r", args[0]), set())
    if kind == "between":
        ends = [("n", net.aliases.get(a, a)) if a in net.nodes or a in net.aliases else ("r", a) for a in args]
        keys = set(ends)
        for i, a in enumerate(ends):
            for b in ends[i + 1:]:
                keys |= _way(near, a, b)
        return keys
    return None


def _way(near, a, b):
    """The keys on the shortest ways from a to b (all of them, if there are several of the same length)."""
    from collections import deque
    dist = {a: 0}
    q = deque([a])
    while q:
        k = q.popleft()
        for o in near.get(k, ()):
            if o not in dist:
                dist[o] = dist[k] + 1
                q.append(o)
    if b not in dist:
        return set()
    # walk back from b through every key one step nearer to a
    keys, edge = {b}, {b}
    while edge:
        edge = {o for k in edge for o in near.get(k, ()) if dist.get(o, -1) == dist[k] - 1}
        keys |= edge
    return keys


def planes(net, front):
    """{key: 1 | 2 | 3}: the front (1), what touches it (2), the rest (3). Without a front, everything is 1."""
    nodes, relations, _ = picture(net)
    keys = [("n", n) for n in nodes] + [("r", r) for r in relations]
    if front is None:
        return {k: 1 for k in keys}
    near = neighbours(net)
    second = {o for k in front for o in near.get(k, ())} - front
    return {k: 1 if k in front else 2 if k in second else 3 for k in keys}


# ---------------------------------------------------------------------- the colours of the networks in the network
# soft hues that sit well together on the dark background; amber and red are kept for what does not hold
PALETTE = ("#5fb3b3", "#e07a5f", "#9d8ec7", "#81b29a", "#6fa8dc", "#e5989b", "#f2cc8f", "#b5c99a", "#c49bbb",
           "#7fc8d6", "#d4a373", "#a3b4e0")
SPECIAL = {"base": "#7d8aa3", "found": "#e5c07b", "typed": "#c3b1e1"}


def colours(net):
    """{group: colour}: each network in the network keeps its colour (the order it was born in), the base slate,
    what it found gold, what was typed lilac."""
    out, k = {}, 0
    for name in list(getattr(net, "groups", {}) or {}) + ["found"]:
        if name in out:
            continue
        if name in SPECIAL:
            out[name] = SPECIAL[name]
        else:
            out[name] = PALETTE[k % len(PALETTE)]
            k += 1
    return out


def home(net, found=None):
    """{key: group}: the network each node and relation belongs to (the smallest one that holds it)."""
    found = found if found is not None else groups(net)
    out = {}
    for name, (nodes, rels) in sorted(found.items(), key=lambda kv: -(len(kv[1][0]) + len(kv[1][1]))):
        for n in nodes:
            out[("n", n)] = name
        for r in rels:
            out[("r", r)] = name
    return out


def in_equation(net, text):
    """An equation as a human writes it: the node that holds the next value of n (n__next1) is n′."""
    import re
    for st in net.sets:
        source = st["source"]
        if "__next" in source:
            text = re.sub(rf"(?<![A-Za-z0-9_]){re.escape(source)}(?![A-Za-z0-9_])", st["target"] + "′", text)
    return text
