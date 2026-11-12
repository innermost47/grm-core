# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Anthony Charretier
"""What can go wrong in a calculation of the GRM machine, said instead of passing in silence.

    names(net, before, line)   a name written for the first time that looks like a known one (a typo makes a new
                               node, and the program then computes something else without a word)
    machine(m, settled)        values that are not numbers, a network that did not settle (and what keeps it moving),
                               relations far from holding (a contradiction, or data that disagree with them)
    internal(e)                an error of the machine itself (Python), with where it happened
"""
import difflib
import math
import os
import re
import traceback

from i18n import label, tr

NAME = r"[A-Za-z_~][A-Za-z0-9_]*"
FAR = 5.0          # sigmas: a relation this far from holding once settled is said
SHOWN = 6          # at most this many of each kind are listed


def close(word, words, cutoff=0.75):
    """The known words that look like `word` (a typo)."""
    return difflib.get_close_matches(word, list(words), n=3, cutoff=cutoff)


def names(net, before, line):
    """The nodes a statement created that look like nodes that existed before it: probably a typo."""
    out = []
    created = [n for n in net.nodes if n not in before]
    old = [n for n in before if "__" not in n]
    for n in created:
        if "__" in n or not re.search(rf"(?<![A-Za-z0-9_]){re.escape(n)}(?![A-Za-z0-9_])", line):
            continue
        like = close(n, old)
        if like:
            out.append(label("warning") + tr("'{n}' is a new node; did you mean {like}?", n=n,
                                                  like=tr(" or ").join(repr(x) for x in like)))
    return out


def machine(m, settled=True, reported=None):
    """What is wrong with the machine now. reported: a set kept between calls, so the same relation far from
    holding is said once (and again only after it has come back)."""
    out = []
    net = m.net
    bad = [m.var_names[i] for i, v in enumerate(m.x) if not math.isfinite(v)]
    if bad:
        touched = sorted({f.name for f in m.factors if f.kind in ("relation", "nonlinear")
                          and any(not math.isfinite(m.x[i]) for i in f.vars)})
        out.append(label("error") + tr("not a number: {names}", names=", ".join(bad[:SHOWN]))
                   + (" ..." if len(bad) > SHOWN else "")
                   + (" (" + tr("in {names}", names=", ".join(touched[:SHOWN])) + ")" if touched else ""))
    if settled and reported is not None:
        reported.discard(" unsettled")
    if not settled and not (reported is not None and " unsettled" in reported):
        if reported is not None:
            reported.add(" unsettled")           # said once, again only after it has settled
        moving = sorted(((m.last_move[i], m.var_names[i]) for i in m.dirty_nodes), reverse=True)[:SHOWN]
        swinging = [f.name for f in m.factors if f.kind == "relation" and f.swing >= 4]
        if moving and moving[0][0] > 1e-9:
            what = "; " + tr("still moving: {names}", names=", ".join(f"{n} ({d:.2g})" for d, n in moving))
        else:
            what = ("; " + tr("its values stand still but its messages keep growing more certain: exact relations "
                              "that say the same thing twice around a loop, or contradict each other")
                    + (" (" + tr("around {names}", names=", ".join(n for _, n in moving)) + ")" if moving else ""))
        out.append(label("warning") + tr("the network did not settle in the rounds it was given") + what
                   + ("; " + tr("swinging back and forth: {names}", names=", ".join(swinging[:SHOWN]))
                      if swinging else ""))
    if not bad:
        # relations that hear inputs or hold weights are far from holding when data surprise them: that is the
        # surprise, shown on its own; here only the program's own relations
        heard = {m.index[k] for n, sp in net.nodes.items() if sp.get("input") or sp.get("learn")
                 for k in (n, "~" + n) if k in m.index}
        far = {}
        for f in m.factors:
            if f.kind not in ("relation", "nonlinear") or f.w <= 0 or (f.watch and not f.active):
                continue
            if heard.intersection(f.vars):
                continue
            try:
                r = m.residual(f)
            except (OverflowError, ValueError, ZeroDivisionError):
                continue
            if math.isfinite(r) and abs(r) > FAR:
                far[f.name] = r
        if reported is not None:
            new = {k: v for k, v in far.items() if k not in reported}
            keep = {k for k in reported if k.startswith(" ")}
            reported.intersection_update(far)
            reported.update(far)
            reported.update(keep)
        else:
            new = far
        for name, r in sorted(new.items(), key=lambda kv: -abs(kv[1]))[:SHOWN]:
            rel = net.relation(name)
            text = rel["text"] if rel else ""
            out.append(label("warning") + tr("relation {name} does not hold: {s} sigma ({text}). Two relations "
                                                  "that contradict each other, or data that disagree with it.",
                                                  name=name, s=f"{abs(r):.3g}", text=text))
    return out


def internal(e):
    """An error of the machine itself, with the place it happened, instead of a crash."""
    tb = traceback.extract_tb(e.__traceback__)
    where = ""
    if tb:
        last = tb[-1]
        where = " (" + tr("{file}, line {n}, in {name}", file=os.path.basename(last.filename), n=last.lineno,
                          name=last.name) + ")"
    return tr("error inside the machine") + f": {type(e).__name__}: {e}{where}"
