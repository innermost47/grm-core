# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Anthony Charretier
"""What the machine feels, made perceptible: every light, movement and sound the body gives comes from a quantity the
machine really has, never from decoration.

    activity     how much it is working: rounds of messages a second (calm when it has settled)
    harmony      how well its relations hold (1: all of them; each one counts by the information it brings)
    pleasure     its dopamine: less surprised than it expected is pleasure, more is displeasure
    surprise     how far its last inputs were from what it expected, in sigmas
    voices       its relations that bring the most information, each with how far it is from holding

and the moments worth sharing with the human: a relation found by itself, a surprise.

The body (body.py: the picture; ambient.py: the sound) is meant to be calm: nothing flashes (far below the 3 flashes
a second of WCAG 2.3.1), every change is slow, everything can be turned down or off.
"""
import math
import time

import mind
from i18n import tr

LEVELS = {"off": 0.0, "calm": 0.35, "present": 0.65, "vivid": 1.0}   # how strongly the picture shows what it feels
VOICES = 6           # relations heard at most
SURPRISED = 3.0      # sigmas: a surprise worth a moment (and at least twice what it expected)
PENTATONIC = (1.0, 9 / 8, 5 / 4, 3 / 2, 5 / 3)   # the intervals a discovery may ring on: none of them clash


def clamp(x, lo=0.0, hi=1.0):
    return lo if x < lo else hi if x > hi else x


class Feel:
    """Follows the machine from one look to the next (how many rounds since the last look, what was already
    shared)."""

    def __init__(self):
        self.rounds = None
        self.at = time.perf_counter()
        self.activity = 0.0
        self.found = None           # how many relations found by itself had been seen
        self.last_surprise_moment = 0.0

    def state(self, vm):
        """{"activity", "harmony", "pleasure", "flourishing", "surprise", "voices": [{"name", "bits", "strain"}]}."""
        net, m = vm.net, vm.machine
        md = mind.mood(net)
        now = time.perf_counter()
        if m is not None:
            if self.rounds is not None and m.rounds >= self.rounds:
                rate = (m.rounds - self.rounds) / max(now - self.at, 1e-3)
                self.activity = max(1.0 - math.exp(-rate / 40.0), self.activity * math.exp(-(now - self.at) / 2.0))
            self.rounds = m.rounds
        self.at = now
        bits = net.use.get("bits", {}) or {}
        strain = {}
        if m is not None:
            for f in m.factors:
                if f.kind in ("relation", "nonlinear") and f.w > 0 and not (f.watch and not f.active):
                    try:
                        strain[f.name] = abs(m.residual(f))
                    except (OverflowError, ValueError, ZeroDivisionError):
                        strain[f.name] = 10.0
        names = [r["name"] for r in net.relations if r["name"] in strain]
        names.sort(key=lambda n: -bits.get(n, 0.0))
        voices = [{"name": n, "bits": bits.get(n, 0.0), "strain": min(strain[n], 10.0)} for n in names[:VOICES]]
        weight = sum(max(v["bits"], 0.1) for v in voices)
        harmony = (sum(max(v["bits"], 0.1) * math.exp(-v["strain"] ** 2 / 8.0) for v in voices) / weight
                   if voices else 1.0)
        h = vm.history.get("surprise") or []
        return {"key": key_of(vm), "activity": self.activity, "harmony": harmony, "pleasure": clamp(md["dopamine"], -1.0, 1.0),
                "flourishing": md.get("flourishing", 1.0), "surprise": h[-1] if h else 0.0, "voices": voices}

    def moments(self, vm):
        """What has just happened that is worth sharing: [{"kind": "discovery", ...} | {"kind": "surprise", ...}]."""
        net = vm.net
        out = []
        if self.found is None:
            self.found = len(net.found)          # what was found before the human was there is not a moment now
        for f in net.found[self.found:]:
            out.append(discovery(vm, f))
        self.found = len(net.found)
        h = vm.history.get("surprise") or []
        expected = mind.mood(net).get("expected") or 0.0
        if h and h[-1] >= max(SURPRISED, 2 * expected) and time.perf_counter() - self.last_surprise_moment > 8.0:
            self.last_surprise_moment = time.perf_counter()
            out.append(surprise(vm, h[-1]))
        return out


def key_of(vm):
    """The key the sound is in: each network in the network has its own (with its colour); everything: C."""
    import ambient
    import graph
    f = vm.focus
    if not f or f[0] != "group":
        return 1.0
    names = list(graph.colours(vm.net))
    k = names.index(f[1]) if f[1] in names else 0
    return ambient.KEYS[(k + 1) % len(ambient.KEYS)]


# ---------------------------------------------------------------------- the moments
def discovery(vm, f):
    """A relation found by itself, said as a human would like to hear it: its law, a sentence, the interval it rings
    on, and what it was found in (points to draw)."""
    target = f.get("target") or ""
    powers = f.get("powers") or {}
    mean = f.get("meaning") or {}
    kind = f.get("kind")
    if "period" in mean:
        sentence = tr("{x} swings: it comes back every {p} moments, and keeps {d} of itself each moment",
                      x=target, p=f"{mean['period']:.3g}", d=f"{mean['damping']:.3g}")
    elif "half_life" in mean:
        sentence = tr("{x} fades: it loses half of itself every {h} moments", x=target, h=f"{mean['half_life']:.3g}")
    elif "doubling" in mean:
        sentence = tr("{x} grows: it doubles every {d} moments", x=target, d=f"{mean['doubling']:.3g}")
    elif powers and kind == "power":
        x, p = max(powers.items(), key=lambda kv: abs(kv[1]))
        sentence = tr("when {x} doubles, {y} is multiplied by {k}", x=x, y=target, k=f"{2 ** p:.3g}")
    elif kind == "line":
        sentence = tr("{y} follows a straight line", y=target)
    elif kind == "sum":
        sentence = tr("{y} is a sum of products: two worlds of the machine, stacked", y=target)
    else:
        sentence = tr("a law that holds on every row it has seen")
    # the interval it rings on: the largest power folded into one octave, then the nearest note that does not clash
    p = max((abs(v) for v in powers.values()), default=1.5) or 1.5
    while p > 2:
        p /= 2
    while p < 1:
        p *= 2
    ratio = min(PENTATONIC + (2.0,), key=lambda r: abs(math.log(r / p)))
    return {"kind": "discovery", "relation": f["relation"], "text": f["text"], "sentence": sentence, "ratio": ratio,
            "r2": f.get("r2"), "rows": f.get("rows"), "points": points(vm.net, target, list(powers) or None)}


def points(net, target, inputs):
    """(xs, ys) to draw what a law was found in: target against its first input, or against time."""
    rows = [r for r in net.rows[-300:] if target in r]
    if not rows:
        return [], []
    x = next((i for i in (inputs or []) if all(i in r for r in rows)), None)
    xs = [r[x] for r in rows] if x else list(range(len(rows)))
    ys = [r[target] for r in rows]
    return xs, ys


def surprise(vm, sigma):
    """A surprise: how far, and where the network did not expect it."""
    m = vm.machine
    where = sorted(((abs(v), k) for k, v in (getattr(m, "last_surprise", {}) or {}).items()), reverse=True)[:2]
    return {"kind": "surprise", "sigma": sigma, "where": [(k, v) for v, k in where],
            "sentence": tr("it did not expect that: {s} sigma from what it thought", s=f"{sigma:.2g}")}
