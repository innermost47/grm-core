# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Anthony Charretier
"""Harmonic test of the network: are its dimensionless numbers rational powers (harmonics) of one fundamental
number (default S)? Each number X is matched to S^(p/q), q <= MAXQ, within TOL decades; the same matching is
run against random fundamentals: the hypothesis gains support only if S explains clearly more numbers than they do.

    python harmonics.py [fundamental node, default S]
"""
import math
import random
import sys
from fractions import Fraction

from pygrm import GlobalRelationalNetwork as N
from settings import GRM_NETWORK_STORE_JSON
from store import load_grm_network_safely as load

FUNDAMENTAL = sys.argv[1] if len(sys.argv) > 1 else "S"
d = load(GRM_NETWORK_STORE_JSON)
r = N(d["nodes_spec"], d["relations_spec"]).solve({k: tuple(v) for k, v in d["measured"].items()}, compute_uncertainty=False)
v = r["values"]
dimless = [k for k, s in d["nodes_spec"].items() if s.get("scale", "log") == "log" and all(x == 0 for x in s["dim"])
           and v[k] > 0 and abs(math.log10(v[k])) >= 1.0]
TOL = 0.5          # dex
MAXQ, MAXP = 6, 24     # largest denominator and numerator of the harmonic powers

def harmonic(logx, logf):
    best = None
    for q in range(1, MAXQ + 1):
        p = round(q * logx / logf)
        if p == 0 or abs(p) > MAXP:
            continue
        err = logx - p / q * logf
        if best is None or abs(err) < abs(best[1]):
            best = (Fraction(p, q), err)
    return best

def score(logf, names):
    hits = []
    for k in names:
        h = harmonic(math.log10(v[k]), logf)
        if h and abs(h[1]) < TOL:
            hits.append((k, h))
    return hits

fund = math.log10(v[FUNDAMENTAL])
names = [k for k in dimless if k != FUNDAMENTAL]
hits = score(fund, names)
print(f"fundamental {FUNDAMENTAL} = 10^{fund:.3f}; {len(names)} dimensionless numbers (|log| >= 1)")
for k, (f, e) in sorted(hits, key=lambda h: -abs(math.log10(v[h[0]]))):
    print(f"  {k:12s} 10^{math.log10(v[k]):8.3f} = {FUNDAMENTAL}^({f})  off by {e:+.3f} dex")
rng = random.Random(1)
decoy = [len(score(rng.uniform(100, 140), names)) for _ in range(400)]
print(f"\n{len(hits)} harmonics of {FUNDAMENTAL}; a random fundamental 10^100..10^140 gives {sum(decoy)/len(decoy):.1f} on average, "
      f"and {sum(x >= len(hits) for x in decoy) / len(decoy):.0%} of random fundamentals do as well or better")
print()
for k in sorted(names, key=lambda k: -math.log10(v[k])):
    print(f"  {k:12s} log10 = {math.log10(v[k]):9.3f}   / log10 fundamental = {math.log10(v[k]) / fund:+.4f}")
