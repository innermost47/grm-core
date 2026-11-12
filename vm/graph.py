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


def layout(net, places, steps=30, size=1.0, pinned=()):
    """Moves `places` ({("n" | "r", name): [x, y]}) a few steps toward a calm picture of the network; new things
    appear next to what they are linked to. Returns places (the same dict)."""
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
    """What a node holds, in words (lines)."""
    net, m = vm.net, vm.machine
    spec = net.nodes.get(name, {})
    roles = [r for r in ("input", "output", "var", "learn", "fixed") if spec.get(r)]
    kind = "signed" if spec.get("signed") else "positive"
    lines = [f"node {name}  ({', '.join(roles + [kind])})"]
    if m is not None and (name in m.index or name in m.fixed):
        try:
            v = m.value_si(name)
            sg = m.sigma(name)
            unit = " SI" if spec.get("dim") else ""
            if spec.get("signed"):
                lines.append(f"value  {_fmt(v)}{unit}" + (f"  ± {sg:.3g} (its unit inside)" if sg < 1e5 else ""))
            else:
                lines.append(f"value  {_fmt(v)}{unit}" + (f"  ± {sg:.3g} dex" if sg < 1e5 else ""))
            if name in m.index:
                i = m.index[name]
                lines.append(f"last move  {m.last_move[i]:.3g}" + ("  (moving)" if m.last_move[i] > 1e-9 else ""))
        except (KeyError, OverflowError, ValueError):
            pass
    if spec.get("dim"):
        lines.append("dimension  [M L T Q K] = [" + " ".join(f"{p:g}" for p in spec["dim"]) + "]")
    if name in net.measured:
        v, s = net.measured[name]
        lines.append(f"measured  {_fmt(v)} ± {s:.3g}" + ("" if spec.get("signed") else " dex"))
    aliases = [a for a, b in net.aliases.items() if b == name]
    inverses = [a for a, b in net.inverses.items() if b == name]
    if aliases:
        lines.append("also called  " + ", ".join(aliases))
    if inverses:
        lines.append("its inverse  " + ", ".join(inverses))
    rels = [r["name"] for r in net.relations if name in net.nodes_of(r)]
    lines.append(f"in {len(rels)} relation(s)" + (": " + ", ".join(rels[:8]) + (" ..." if len(rels) > 8 else "")
                                                  if rels else ""))
    origin = net.origin["nodes"].get(name, "written")
    lines.append(f"comes from  {_origin(origin)}")
    lines.append(f"use  {net.use['nodes'].get(name, mind.NEW_TRACE):.3g}")
    tag = net.mood.get("tags", {}).get(name)
    if tag is not None:
        lines.append(f"learned under  {'pleasure' if tag > 0 else 'displeasure'} ({tag:+.2f})")
    return lines


def relation_card(vm, name):
    """What a relation holds, in words (lines)."""
    net, m = vm.net, vm.machine
    rel = net.relation(name)
    if rel is None:
        return [f"no relation {name}"]
    kind = rel.get("kind", "product")
    lines = [f"relation {name}  ({_kind(kind)})", rel.get("text", "")]
    if kind in ("product", "sum"):
        lines.append(f"sigma  {rel['sigma']:.3g}" + (" dex" if kind == "product" else ""))
    if m is not None:
        f = next((f for f in m.factors if f.name == name), None)
        if f is not None:
            if f.kind in ("relation", "nonlinear") and f.w > 0:
                try:
                    r = m.residual(f)
                    lines.append(f"now  {abs(r):.3g} sigma from holding" + ("  (holds)" if abs(r) < 1 else ""))
                except (OverflowError, ValueError, ZeroDivisionError):
                    pass
            if f.watch:
                lines.append("conditions  " + ("hold: it acts" if f.active else "do not hold: it is silent"))
            if f.swing:
                lines.append(f"swings  {f.swing}" + (f", damped ({f.damp:g})" if f.damp else ""))
    weights = [n for n in net.nodes_of(rel) if net.nodes.get(n, {}).get("learn")]
    if weights and m is not None:
        lines.append("weights  " + ", ".join(f"{w} = {_fmt(m.value_si(w))}" for w in weights if w in m.index))
    tension = net.tension.get(name)
    if tension:
        lines.append(f"last surprise  {tension[-1]:.3g} sigma ({len(tension)} moments kept)")
    found = next((x for x in net.found if x["relation"] == name), None)
    origin = net.origin["relations"].get(name, "written")
    if found:
        lines.append(f"comes from  found by itself at tick {found['tick']}: r² {found['r2']:.6f} over "
                     f"{found['rows']} rows")
    else:
        lines.append(f"comes from  {_origin(origin)}")
    lines.append(f"use  {net.use['relations'].get(name, mind.NEW_TRACE):.3g}")
    bits = net.use.get("bits", {}).get(name)
    if bits is not None:
        n_links = len(set(net.nodes_of(rel)))
        rent = mind.price(net) * n_links
        lines.append(f"information  {bits:.3g} bits a tick; rent {rent:.3g} ({n_links} links)"
                     + ("  (pays its rent)" if bits >= rent else "  (does not pay its rent)"))
    return lines


def _origin(o):
    return {"base": "the base it was born with", "written": "written to it", "found": "found by itself"}.get(o, o)


def _kind(k):
    return {"product": "products and powers", "sum": "a sum", "log": "a logarithm", "keep": "a contact"}.get(k, k)
