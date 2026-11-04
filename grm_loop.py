# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Anthony Charretier
"""
A loop without a seed: three waves born from the void in opposition to the full, for ever.

The idea (Anthony Charretier): nothing starts from a first seed. Somewhere there is an absolute, and for it to exist it
must be a loop: the waves are born from the void in opposition to the full, permanently, with no beginning and no end.

Written as a network with no seed:
    three amplitudes r_n (r = sqrt m: the amplitude of a wave, its energy is r^2), split in two parts that oppose:
        the full   the part shared by all three (along (1, 1, 1))
        the void   what is left: three deviations that sum to zero (born from nothing, they cancel out)
    the loop: neither part wins, they exchange for ever. The full carries as much as the void: |void| = |full|.
Nothing else, and no number: no scale (only ratios), no seed, no tuning.

    1. what the loop alone fixes: |void| = |full| is the same as Koide's Q = 2/3 (the vector of the amplitudes at 45
       degrees from (1, 1, 1): Foot 1994, arXiv:hep-ph/9402242). The loop fixes one ratio, not all of them: the GRM
       network says so (a direction stays undetermined). Given two charged lepton masses, it predicts the third.
    2. what it leaves free: the phase delta of the three waves on their circle. Measured: it sits at 2/9 rad. How
       likely is a simple fraction that close by chance?
    3. a bet: the same loop for the neutrinos, whose masses nobody has measured (only their differences). The loop
       gives the masses. Cosmology (DESI 2024: sum < 0.072 eV at 95 %) will say if it holds.

Masses: Particle Data Group 2024 (charged leptons; neutrino mass-squared differences, normal and inverted order).

Run: python grm_loop.py
"""
import itertools
import math
import random

from grm import GlobalRelationalNetwork

ME, MMU, MTAU = (0.51099895000, 1.5e-10), (105.6583755, 2.3e-6), (1776.93, 0.09)     # MeV, PDG 2024
DM21 = (7.53e-5, 0.18e-5)                                   # eV^2, PDG 2024
DM32_NORMAL, DM32_INVERTED = (2.455e-3, 0.028e-3), (-2.529e-3, 0.029e-3)
DESI_SUM_LIMIT = 0.072                                      # eV, 95 %, DESI 2024 + CMB, LambdaCDM (arXiv:2404.03002)
OSC_MIN_NORMAL = 0.059                                      # eV, the smallest sum the oscillations allow (normal order)


def full_and_void(r):
    """The full: the shared part (the mean along (1,1,1)); the void: the deviations, which sum to zero."""
    mean = sum(r) / 3
    full2 = 3 * mean ** 2
    void2 = sum((x - mean) ** 2 for x in r)
    return full2, void2


def koide_q(m):
    r = [math.sqrt(x) for x in m]
    return sum(m) / sum(r) ** 2


def phase(m, signs=(1, 1, 1)):
    """The phase delta and the void/full ratio of three waves: sqrt m_n = mu (1 + k sqrt 2 cos(delta + 2 pi n / 3))."""
    r = [s * math.sqrt(x) for s, x in zip(signs, m)]
    mu = sum(r) / 3
    c = [(x / mu - 1) / math.sqrt(2) for x in r]
    re = sum(c[n] * math.cos(2 * math.pi * n / 3) for n in range(3)) * 2 / 3
    im = -sum(c[n] * math.sin(2 * math.pi * n / 3) for n in range(3)) * 2 / 3
    return math.atan2(im, re) % (2 * math.pi / 3), math.hypot(re, im)


# ------------------------------------------------------------------ the loop as a GRM network
def loop_network(names, signed=False):
    """Three waves m_n = r_n^2 and the loop |void| = |full|. No seed, no scale."""
    nodes = {}
    rels = []
    for n in names:
        nodes[f"r_{n}"] = {"guess": 1.0, "scale": "lin" if signed else "log"}
        nodes[n] = {"guess": 1.0}
        rels.append({"name": f"{n} = r^2", "type": "fn", "nodes": [n, f"r_{n}"],
                     "f": lambda v, n=n: math.log10(v[n]) - 2 * math.log10(abs(v[f"r_{n}"])), "sigma": 1e-9})

    def balance(v):
        full2, void2 = full_and_void([v[f"r_{n}"] for n in names])
        return (void2 - full2) / (void2 + full2)
    rels.append({"name": "the loop: |void| = |full|", "type": "fn", "nodes": [f"r_{n}" for n in names], "f": balance,
                 "sigma": 1e-9})
    return nodes, rels


def dex(value, sigma):
    return (value, max(sigma / value / math.log(10), 1e-12))


def predict_third(known, unknown):
    """The loop, two charged lepton masses measured: the third."""
    names = ["e", "mu", "tau"]
    data = {"e": ME, "mu": MMU, "tau": MTAU}
    nodes, rels = loop_network(names)
    for n in names:
        nodes[n]["guess"] = data[n][0] if n in known else data[known[-1]][0]
        nodes[f"r_{n}"]["guess"] = math.sqrt(nodes[n]["guess"])
    # the root of the loop that lies beyond (or between) the known ones: start on each side and keep both
    out = []
    for g in (data[known[0]][0] * 0.3, (data[known[0]][0] * data[known[1]][0]) ** 0.5, data[known[1]][0] * 30):
        nodes[unknown]["guess"], nodes[f"r_{unknown}"]["guess"] = g, math.sqrt(g)
        net = GlobalRelationalNetwork(nodes, rels)
        res = net.solve({n: dex(*data[n]) for n in known}, max_iterations=200)
        if res["converged"] and res["cost"] < 1e-6:
            out.append((res["values"][unknown], res["uncertainty"][unknown] * res["values"][unknown]))
    uniq = []
    for v, s in sorted(out):
        if not uniq or abs(v / uniq[-1][0] - 1) > 1e-6:
            uniq.append((v, s))
    return uniq


def neutrinos(dm32, signs):
    """The loop for the neutrinos: m2 - m1 and m3 - m2 measured (squared masses), the loop closes the system.
    signs: the sign of each amplitude (a wave may be in opposition: r < 0, as Brannen proposed for the lightest)."""
    names = ["n1", "n2", "n3"]
    nodes, rels = loop_network(names, signed=True)
    rels = [r for r in rels if not r["name"].endswith("= r^2")]
    for n in names:
        del nodes[n]
    rels.append({"name": "m2^2 - m1^2 (solar)", "type": "fn", "nodes": ["r_n1", "r_n2"],
                 "f": lambda v: (v["r_n2"] ** 4 - v["r_n1"] ** 4 - DM21[0]) / DM21[0], "sigma": DM21[1] / DM21[0]})
    rels.append({"name": "m3^2 - m2^2 (atmospheric)", "type": "fn", "nodes": ["r_n2", "r_n3"],
                 "f": lambda v: (v["r_n3"] ** 4 - v["r_n2"] ** 4 - dm32[0]) / abs(dm32[0]), "sigma": dm32[1] / abs(dm32[0])})
    best = []
    rng = random.Random(3)
    for _ in range(40):
        start = {f"r_{n}": s * math.sqrt(10 ** rng.uniform(-4, -0.5)) for n, s in zip(names, signs)}
        net = GlobalRelationalNetwork({k: {"guess": start[k], "scale": "lin"} for k in start}, rels)
        try:
            res = net.solve({}, max_iterations=300, start=start)
        except (ValueError, ZeroDivisionError, OverflowError):
            continue
        if not res["converged"] or res["cost"] > 1e-3:
            continue
        r = [res["values"][f"r_{n}"] for n in names]
        if any(math.copysign(1, x) != s for x, s in zip(r, signs)):
            continue
        m = [x * x for x in r]
        if not any(abs(sum(m) / sum(b[0]) - 1) < 1e-6 for b in best):
            best.append((m, r))
    return best


def simple_fraction_chance(value, window, top=2 * math.pi / 3, qmax=12):
    """How many fractions p/q (q <= qmax) lie in [0, top), and how many would be expected within +-window of any
    value by chance."""
    fr = {p / q for q in range(1, qmax + 1) for p in range(0, int(top * q) + 1) if p / q < top}
    near = sorted(f for f in fr if abs(f - value) <= window)
    expected = len(fr) * 2 * window / top
    return len(fr), near, expected


# ------------------------------------------------------------------ what the neutrino masses imply (PDG 2024 angles)
S12, S13 = (0.307, 0.013), (0.0219, 0.0007)                 # sin^2 theta_12, sin^2 theta_13, normal ordering


def neutrino_observables(m, s12=S12[0], s13=S13[0], steps=361):
    """From the three masses (eV): the mass seen in beta decay, m_beta = sqrt(sum |U_ei|^2 m_i^2), and the range of
    the effective mass of neutrinoless double beta decay, m_bb = |sum U_ei^2 m_i| over the two unknown Majorana phases."""
    w = [(1 - s12) * (1 - s13), s12 * (1 - s13), s13]
    m_beta = math.sqrt(sum(wi * mi * mi for wi, mi in zip(w, m)))
    t = [wi * mi for wi, mi in zip(w, m)]
    lo, hi = float("inf"), 0.0
    for a in range(steps):
        for b in range(steps):
            pa, pb = 2 * math.pi * a / (steps - 1), 2 * math.pi * b / (steps - 1)
            re = t[0] + t[1] * math.cos(pa) + t[2] * math.cos(pb)
            im = t[1] * math.sin(pa) + t[2] * math.sin(pb)
            v = math.hypot(re, im)
            lo, hi = min(lo, v), max(hi, v)
    return m_beta, lo, hi


def observables_envelope(m):
    """The same with the angles moved by their 1-sigma uncertainties: the widest range."""
    out = [neutrino_observables(m, s12, s13, steps=121)
           for s12 in (S12[0] - S12[1], S12[0], S12[0] + S12[1]) for s13 in (S13[0] - S13[1], S13[0], S13[0] + S13[1])]
    return (min(o[0] for o in out), max(o[0] for o in out)), min(o[1] for o in out), max(o[2] for o in out)


# ------------------------------------------------------------------ the run
def run(out=print):
    out("A loop without a seed: three waves, the full and the void in balance, for ever.\n")
    m = [ME[0], MMU[0], MTAU[0]]
    full2, void2 = full_and_void([math.sqrt(x) for x in m])
    q = koide_q(m)
    out("1. WHAT THE LOOP FIXES")
    out(f"   |void| / |full| for the charged leptons: {math.sqrt(void2 / full2):.6f} (the loop says 1); "
        f"Koide's Q = {q:.7f} (the loop says 2/3 = 0.6666667)")
    out("   the loop alone fixes this one ratio; the GRM network, given one mass, leaves the others undetermined:")
    nodes, rels = loop_network(["e", "mu", "tau"])
    res = GlobalRelationalNetwork(nodes, rels).solve({"e": dex(*ME)}, max_iterations=200)
    out(f"     undetermined: {', '.join(res['undetermined']) or 'nothing'}")
    out("   given two masses, it predicts the third (each in turn):")
    data = {"e": ME, "mu": MMU, "tau": MTAU}
    for unknown in ("tau", "mu", "e"):
        known = [n for n in ("e", "mu", "tau") if n != unknown]
        for v, s in predict_third(known, unknown):
            meas = data[unknown]
            if 0.2 < v / meas[0] < 5:
                out(f"     {unknown:>4} from {known[0]} and {known[1]}: {v:.6g} +- {s:.2g} MeV   "
                    f"(measured {meas[0]:.10g} +- {meas[1]:.2g}; {(v - meas[0]) / math.hypot(s, meas[1]):+.1f} sigma)")

    out("\n2. WHAT IT LEAVES FREE: the phase of the three waves on their circle")
    d, k = phase(sorted(m))
    rng = random.Random(0)
    draws = [phase(sorted([rng.gauss(ME[0], ME[1]), rng.gauss(MMU[0], MMU[1]), rng.gauss(MTAU[0], MTAU[1])]))[0]
             for _ in range(20000)]
    mean = sum(draws) / len(draws)
    sd = math.sqrt(sum((x - mean) ** 2 for x in draws) / len(draws))
    out(f"   delta = {d:.7f} +- {sd:.7f} rad; 2/9 = {2 / 9:.7f} ({(d - 2 / 9) / sd:+.1f} sigma)")
    n_fr, near, expected = simple_fraction_chance(d, 2 * sd)
    out(f"   chance: of the {n_fr} fractions p/q (q <= 12) between 0 and 2 pi / 3, {expected:.2g} would be expected "
        f"within 2 sigma of any value; found: {', '.join(f'{f:.7f}' for f in near) or 'none'}")
    out("   (about 1 in " + f"{1 / expected:.0f}" + "; but 2/9 was noticed after looking, by Brannen in 2006)")

    out("\n3. A BET: the neutrinos (only the differences of their squared masses are measured)")
    out(f"   cosmology: sum < {DESI_SUM_LIMIT} eV (DESI 2024, 95 %); oscillations alone: sum >= {OSC_MIN_NORMAL} eV (normal order)")
    bets = []
    for order, dm32 in (("normal", DM32_NORMAL), ("inverted", DM32_INVERTED)):
        found = []
        for signs in itertools.product((1, -1), repeat=3):
            for mm, r in neutrinos(dm32, signs):
                if not any(abs(sum(mm) / sum(f[0]) - 1) < 1e-6 for f in found):
                    found.append((mm, signs))
        if not found:
            out(f"   {order:<8} no wave set closes the loop")
        for mm, signs in found:
            # the uncertainty: the same loop with each measured difference moved by its sigma
            spread = []
            for dm21, d32 in ((DM21[0] + DM21[1], dm32[0]), (DM21[0], dm32[0] + math.copysign(dm32[1], dm32[0]))):
                saved = globals()["DM21"]
                globals()["DM21"] = (dm21, DM21[1])
                alt = neutrinos((d32, dm32[1]), signs)
                globals()["DM21"] = saved
                if alt:
                    spread.append(min((abs(sum(a[0]) - sum(mm)) for a in alt)))
            sigma = math.sqrt(sum(x * x for x in spread))
            total = sum(mm)
            verdict = "allowed" if total < DESI_SUM_LIMIT else "refused by DESI 2024"
            sg = "".join("+" if x > 0 else "-" for x in signs)
            out(f"   {order:<8} amplitudes {sg}: m = {mm[0] * 1000:.3f}, {mm[1] * 1000:.3f}, {mm[2] * 1000:.3f} meV; "
                f"sum = {total * 1000:.2f} +- {sigma * 1000:.2f} meV  -> {verdict}")
            bets.append((order, signs, total, mm, verdict, sigma))
    out("   (all amplitudes in phase, + + +: the loop does not close for the neutrinos; one wave must be in opposition)")

    out("\n4. WHAT FOLLOWS FROM THESE MASSES (normal order; mixing angles PDG 2024)")
    normal = [b for b in bets if b[0] == "normal"]
    if normal:
        mm = normal[0][3]
        m_beta, lo, hi = neutrino_observables(mm)
        (mb_lo, mb_hi), lo_env, hi_env = observables_envelope(mm)
        out(f"   tau mass (the loop, from e and mu): see 1 above")
        out(f"   mass seen in beta decay: m_beta = {m_beta * 1000:.2f} meV (angles +-1 sigma: {mb_lo * 1000:.2f} .. {mb_hi * 1000:.2f})")
        out(f"   neutrinoless double beta decay: m_bb between {lo * 1000:.2f} and {hi * 1000:.2f} meV "
            f"(angles +-1 sigma: {lo_env * 1000:.2f} .. {hi_env * 1000:.2f}), over the two unknown Majorana phases")
        out(f"   sum seen by cosmology: {normal[0][2] * 1000:.2f} meV")
    return {"q": q, "ratio": math.sqrt(void2 / full2), "delta": d, "sd_delta": sd, "bets": bets}


if __name__ == "__main__":
    run()
