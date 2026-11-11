# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Anthony Charretier
"""
From the 0 the 1, from the 1 the 2, from the 2 the 3, from the 3 the ten thousand beings (Tao Te Ching, 42).

A test of one idea: the masses of the particles are harmonics born in cascade from a few seeds.

    0          the void
    1          a first wave, the fundamental (between 0 and 1: the first force; it sets the scale m0)
    2A, 2B     two waves born from 1, each held to it by its own relation (two seeds a and b)
    3          the relation between 2A and 2B: it makes new waves, which make new waves...
    10 000     the cascade: everything that the relations can make, step after step

Three ways to read "relation" are tested, each fixed before looking at the masses:

    spiral         the relation multiplies: 2A = 1 x a, 2B = 1 x b, then a x b, a / b, a^2 b... Each step turns and
                   grows by a fixed ratio (a spiral in log space). The cascade of depth d reaches m0 a^i b^j with
                   |i| + |j| <= d.
    intermodulation the relation is that of real waves played together: two tones give their sum and difference
                   tones, which give theirs. Depth d: m0 (n0 + n1 a + n2 b), integers |n| <= d.
    trinity        the 3 is the relation itself: three waves on one circle, 120 degrees apart,
                   sqrt(m_n) = mu (1 + sqrt(2) cos(delta + 2 pi n / 3)). This is the Koide formula
                   (Q = sum m / (sum sqrt m)^2 = 2/3), here tested on every family of three.

The judge is chance. Every rule is also fitted to random spectra (same number of masses, same span, log-uniform):
a rule that fits random masses as well as the real ones explains nothing. p is the share of random spectra that fit
at least as well. The fit of the best seeds is then refined by the GRM network (log-linear relations), which gives
the seeds, their uncertainties and the strain left in every relation.

Masses: Particle Data Group 2024 summary tables (quarks: MS-bar masses, u d s at 2 GeV, c b at their own mass, t
direct; this choice of scheme is itself an assumption the masses depend on).

Run:  python grm_tao.py                (all three rules, 200 random spectra, a few minutes)
      python grm_tao.py --draw tao.png (also draw the cascade as waves, and the result)
"""
import argparse
import math
import random
import sys

import numpy as np

from pygrm import GlobalRelationalNetwork

# PDG 2024, GeV, with their 1-sigma uncertainties
MASSES = {
    "e": (0.51099895000e-3, 0.00000000015e-3), "mu": (0.1056583755, 0.0000000023), "tau": (1.77693, 0.00009),
    "u": (2.16e-3, 0.07e-3), "d": (4.70e-3, 0.07e-3), "s": (93.5e-3, 0.8e-3),
    "c": (1.2730, 0.0046), "b": (4.183, 0.007), "t": (172.57, 0.29),
    "W": (80.3692, 0.0133), "Z": (91.1880, 0.0020), "H": (125.20, 0.11),
}
# the families of three (generations); W, Z and H are not a generation: their span (less than 0.2 decade) would
# make any test of three close masses meaningless
FAMILIES = {"charged leptons": ("e", "mu", "tau"), "up quarks": ("u", "c", "t"), "down quarks": ("d", "s", "b")}
NAMES = list(MASSES)
LOGM = np.array([math.log10(MASSES[k][0]) for k in NAMES])


# ------------------------------------------------------------------ the cascades
def spiral_coefficients(depth):
    return [(i, j) for i in range(-depth, depth + 1) for j in range(-depth, depth + 1) if abs(i) + abs(j) <= depth]


def intermod_coefficients(depth):
    """Sum and difference tones of 1, a and b, up to depth: n0 + n1 a + n2 b with |n| <= depth, n1, n2 not both 0
    unless n0 > 0 (the fundamental itself)."""
    out = []
    for n0 in range(-depth, depth + 1):
        for n1 in range(-depth, depth + 1):
            for n2 in range(-depth, depth + 1):
                if abs(n0) + abs(n1) + abs(n2) <= depth and (n0, n1, n2) != (0, 0, 0):
                    out.append((n0, n1, n2))
    return out


def fit_spiral(logm, depth, grid=0.02, top=3.0, offsets=48):
    """Best seeds (log10 a <= log10 b) and offset log10 m0 for a spectrum: each mass goes to its nearest point of
    the cascade. Returns (rms in dex, la, lb, offset, assignment)."""
    co = np.array(spiral_coefficients(depth))
    I, J = co[:, 0], co[:, 1]
    lgrid = np.arange(grid, top + 1e-9, grid)
    lo, hi = logm.min(), logm.max()
    best = (np.inf, None, None, None)
    for la in lgrid:
        lbs = lgrid[lgrid >= la]
        span = depth * lbs.max()
        offs = np.linspace(lo - span, hi + span, offsets) if span < 2 * (hi - lo) else np.linspace(lo, hi, offsets)
        pts = la * I[None, :] + lbs[:, None] * J[None, :]                          # (nb, K)
        cand = offs[None, :, None] + pts[:, None, :]                               # (nb, no, K)
        d = np.abs(cand[..., None] - logm[None, None, None, :]).min(axis=2)      # (nb, no, M)
        rms = np.sqrt((d ** 2).mean(axis=2))
        k = np.unravel_index(np.argmin(rms), rms.shape)
        if rms[k] < best[0]:
            best = (rms[k], la, lbs[k[0]], offs[k[1]])
    rms, la, lb, off = best
    # finer offset: the mean of the residuals, twice
    for _ in range(2):
        pts = off + la * I + lb * J
        idx = np.abs(pts[:, None] - logm[None, :]).argmin(axis=0)
        off += (logm - pts[idx]).mean()
    pts = off + la * I + lb * J
    idx = np.abs(pts[:, None] - logm[None, :]).argmin(axis=0)
    rms = math.sqrt(((logm - pts[idx]) ** 2).mean())
    return rms, la, lb, off, [tuple(co[i]) for i in idx]


def fit_intermod(logm, depth, grid=0.1, top=6.0, offsets=24):
    co = np.array(intermod_coefficients(depth), dtype=float)
    lgrid = np.arange(grid, top + 1e-9, grid)
    lo, hi = logm.min(), logm.max()
    offs = np.linspace(lo - 1.0, lo + 1.0, offsets)
    best = (np.inf, None, None, None, None)
    for la in lgrid:
        lbs = lgrid[lgrid >= la]
        val = co[None, :, 0] + co[None, :, 1] * 10 ** la + co[None, :, 2] * (10 ** lbs)[:, None]   # (nb, K)
        with np.errstate(invalid="ignore", divide="ignore"):
            lv = np.where(val > 0, np.log10(np.where(val > 0, val, 1.0)), np.nan)
        cand = offs[None, :, None] + lv[:, None, :]
        d = np.nanmin(np.abs(cand[..., None] - logm[None, None, None, :]), axis=2)
        rms = np.sqrt((d ** 2).mean(axis=2))
        k = np.unravel_index(np.nanargmin(rms), rms.shape)
        if rms[k] < best[0]:
            best = (rms[k], la, lbs[k[0]], offs[k[1]], None)
    return best


def koide_q(masses):
    m = np.asarray(masses, dtype=float)
    return m.sum(axis=-1) / np.sqrt(m).sum(axis=-1) ** 2


def brannen_delta(masses):
    """sqrt(m_n) = mu (1 + sqrt 2 cos(delta + 2 pi n / 3)): mu from the mean, delta from the first harmonic."""
    r = np.sqrt(np.asarray(masses, dtype=float))
    mu = r.mean()
    c = np.array([(r[n] / mu - 1) / math.sqrt(2) for n in range(3)])
    z = sum(c[n] * np.exp(-2j * math.pi * n / 3) for n in range(3)) * 2 / 3
    return mu, float(np.angle(z)) % (2 * math.pi / 3)


# ------------------------------------------------------------------ chance
def random_spectra(n, size, lo, hi, seed):
    rng = np.random.default_rng(seed)
    return rng.uniform(lo, hi, size=(n, size))


def p_value(observed, null):
    null = np.asarray(null)
    return (np.sum(null <= observed) + 1) / (len(null) + 1)


# ------------------------------------------------------------------ the GRM refinement
def grm_spiral(assign, sigma_theory):
    """The cascade as a GRM network: each mass = m0 a^i b^j (a log-linear relation), each mass measured.
    sigma_theory (dex) is how exactly the cascade is asked to hold: the strain it cannot remove shows in chi2."""
    # (the seeds are called seed_a and seed_b: "b" is already the bottom quark)
    nodes = {"m0": {"guess": 1e-2}, "seed_a": {"guess": 10.0}, "seed_b": {"guess": 100.0}}
    rels = []
    for name, (i, j) in zip(NAMES, assign):
        nodes[name] = {"guess": MASSES[name][0]}
        rels.append({"name": f"{name} = m0 a^{i} b^{j}",
                     "terms": {name: 1.0, "m0": -1.0, "seed_a": -float(i), "seed_b": -float(j)},
                     "rhs": 0.0, "sigma": sigma_theory})
    # (a floor of 1e-4 dex: the masses are known far better than any cascade could hold, and weights of 1e10
    # would only make the least squares ill-conditioned)
    measured = {k: (MASSES[k][0], max(MASSES[k][1] / MASSES[k][0] / math.log(10), 1e-4)) for k in NAMES}
    net = GlobalRelationalNetwork(nodes, rels)
    return net.solve(measured, max_iterations=50)


# ------------------------------------------------------------------ the run
def run(n_null=300, depth=3, seed=1, out=print):
    lo, hi = LOGM.min(), LOGM.max()
    report = {}
    out("From the 0 the 1, from the 1 the 2, from the 2 the 3, from the 3 the ten thousand beings.")
    out(f"{len(NAMES)} masses (PDG 2024), from {MASSES['e'][0]:.3g} to {MASSES['t'][0]:.4g} GeV "
        f"({hi - lo:.2f} decades). Random spectra: {n_null}, log-uniform over the same span.\n")

    # 1. spiral
    rms, la, lb, off, assign = fit_spiral(LOGM, depth)
    null = [fit_spiral(np.sort(s), depth)[0] for s in random_spectra(n_null, len(NAMES), lo, hi, seed)]
    p = p_value(rms, null)
    out(f"SPIRAL (depth {depth}: m0 a^i b^j, |i| + |j| <= {depth}, {len(spiral_coefficients(depth))} harmonics)")
    out(f"  best seeds: a = 10^{la:.2f}, b = 10^{lb:.2f}, m0 = {10 ** off:.3g} GeV; rms {rms:.3f} dex "
        f"(x{10 ** rms:.2f} on average)")
    out(f"  random spectra: median rms {np.median(null):.3f} dex; p = {p:.3f} "
        f"({'better than chance' if p < 0.01 else 'not better than chance'})")
    for name, (i, j) in zip(NAMES, assign):
        pred = off + la * i + lb * j
        out(f"    {name:>4} = m0 a^{i:+d} b^{j:+d}   {10 ** pred:10.4g} GeV  (measured {MASSES[name][0]:.4g}, "
            f"off by {LOGM[NAMES.index(name)] - pred:+.3f} dex)")
    g = grm_spiral(assign, sigma_theory=max(rms, 1e-3))
    v, u = g["values"], g["uncertainty"]
    out(f"  GRM network with these assignments: a = {v['seed_a']:.4g} ({100 * u['seed_a']:.1f} %), "
        f"b = {v['seed_b']:.4g} ({100 * u['seed_b']:.1f} %), m0 = {v['m0']:.4g} GeV; reduced chi2 {g['reduced_chi2']:.2f} "
        f"(with each relation asked to hold to {max(rms, 1e-3):.3f} dex)")
    worst = sorted(g["relation_pulls"].items(), key=lambda kv: -abs(kv[1]))[:3]
    out("  most strained relations: " + ", ".join(f"{k} ({p_:+.1f} sigma)" for k, p_ in worst))
    report["spiral"] = {"rms": rms, "p": p, "la": la, "lb": lb, "m0": 10 ** off, "assign": assign, "null": null}

    # 2. intermodulation
    rms2, la2, lb2, off2, _ = fit_intermod(LOGM, depth)
    null2 = [fit_intermod(np.sort(s), depth)[0] for s in random_spectra(max(60, n_null // 5), len(NAMES), lo, hi, seed + 1)]
    p2 = p_value(rms2, null2)
    out(f"\nINTERMODULATION (depth {depth}: sum and difference tones of 1, a, b)")
    out(f"  best seeds: a = 10^{la2:.2f}, b = 10^{lb2:.2f}, m0 = {10 ** off2:.3g} GeV; rms {rms2:.3f} dex")
    out(f"  random spectra: median rms {np.median(null2):.3f} dex; p = {p2:.3f} "
        f"({'better than chance' if p2 < 0.01 else 'not better than chance'})")
    report["intermod"] = {"rms": rms2, "p": p2, "null": null2}

    # 3. trinity
    out("\nTRINITY (three waves on one circle, 120 degrees apart: Koide's Q = 2/3)")
    rng = np.random.default_rng(seed + 2)
    report["trinity"] = {}
    for fam, keys in FAMILIES.items():
        m = np.array([MASSES[k][0] for k in keys])
        q = float(koide_q(m))
        # the uncertainty of Q from the masses' (Monte Carlo)
        draws = np.array([[rng.normal(MASSES[k][0], MASSES[k][1]) for k in keys] for _ in range(4000)])
        sq = float(koide_q(draws).std())
        lm = np.log10(m)
        rand = 10 ** rng.uniform(lm.min(), lm.max(), size=(400000, 3))
        dq = abs(q - 2 / 3)
        pq = (np.sum(np.abs(koide_q(rand) - 2 / 3) <= dq) + 1) / (len(rand) + 1)
        mu, delta = brannen_delta(np.sort(m))
        out(f"  {fam:<16} Q = {q:.6f} +- {sq:.6f}   |Q - 2/3| = {dq:.2e}   p = {pq:.2g}   "
            f"(delta = {delta:.4f} rad{'; 2/9 = 0.2222' if fam == 'charged leptons' else ''})")
        report["trinity"][fam] = {"Q": q, "sQ": sq, "p": pq, "delta": delta}
    out("\nReading: a rule counts only if p is small AND it explains more masses than it has free numbers. "
        "The spiral and the intermodulation have 3 free numbers (m0, a, b) plus a choice of harmonic for every mass; "
        "chance measures what that choice is worth. The trinity has 2 per family (mu, delta) for 3 masses: one test each.")
    return report


# ------------------------------------------------------------------ the drawings
def draw(path, report):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    bg, ink, gold, blue, violet = "#05060f", "#f2efe8", "#ffd27a", "#8fd3ff", "#d6a8ff"
    plt.rcParams.update({"text.color": ink, "axes.labelcolor": ink, "xtick.color": "#a9a59c", "ytick.color": "#a9a59c",
                         "axes.edgecolor": "#33343c", "font.size": 10})
    fig = plt.figure(figsize=(12, 13), facecolor=bg)
    gs = fig.add_gridspec(7, 2, height_ratios=[0.7, 1, 1, 1, 1.25, 1.4, 1.7], hspace=0.95, wspace=0.18)
    t = np.linspace(0, 4, 2000)
    fa, fb = 3 / 2, 5 / 4          # for the eye: the seeds of the drawing (a fifth and a third above the fundamental)

    def wave_ax(row, title, col=slice(None)):
        ax = fig.add_subplot(gs[row, col], facecolor=bg)
        ax.set_title(title, loc="left", color=ink, fontsize=11)
        ax.set_yticks([]); ax.set_xticks([])
        for s in ax.spines.values():
            s.set_visible(False)
        return ax

    ax = wave_ax(0, "0 · le vide")
    ax.plot(t, 0 * t, color="#55565e", lw=1.5); ax.set_ylim(-1.2, 1.2)
    ax = wave_ax(1, "1 · la première onde, la fondamentale (entre 0 et 1 : la première force, elle fixe l'échelle)")
    ax.plot(t, np.sin(2 * np.pi * t), color=gold, lw=2); ax.set_ylim(-1.2, 1.2)
    ax = wave_ax(2, "2A · née de 1 par sa relation (×a)", col=0)
    ax.plot(t, np.sin(2 * np.pi * fa * t), color=blue, lw=2); ax.set_ylim(-1.2, 1.2)
    ax = wave_ax(2, "2B · née de 1 par sa relation (×b)", col=1)
    ax.plot(t, np.sin(2 * np.pi * fb * t), color=violet, lw=2); ax.set_ylim(-1.2, 1.2)
    ax = wave_ax(3, "3 · la relation entre 2A et 2B : jouées ensemble, elles battent (leur différence) et se somment")
    s = np.sin(2 * np.pi * fa * t) + np.sin(2 * np.pi * fb * t)
    env = 2 * np.abs(np.cos(np.pi * (fa - fb) * t))
    ax.plot(t, s, color=ink, lw=1.4); ax.plot(t, env, color=gold, lw=1, ls="--"); ax.plot(t, -env, color=gold, lw=1, ls="--")
    ax.set_ylim(-2.3, 2.3)

    # the cascade of combination tones (intermodulation), level by level
    ax = fig.add_subplot(gs[4, :], facecolor=bg)
    ax.set_title("… et les 10 000 êtres : chaque relation fait naître des sons nouveaux (sommes et différences), niveau après niveau",
                 loc="left", color=ink, fontsize=11)
    level = {1.0: 0, fa: 1, fb: 1}
    for depth in (2, 3, 4):
        new = {}
        for x in list(level):
            for y in list(level):
                for z in (x + y, abs(x - y)):
                    if z > 1e-9 and round(z, 6) not in {round(k, 6) for k in level} | {round(k, 6) for k in new}:
                        new[z] = depth
        level.update(new)
    colors = {0: gold, 1: blue, 2: ink, 3: "#a9a59c", 4: "#55565e"}
    for f, lv in level.items():
        ax.vlines(f, 0, 1 - 0.18 * lv, color=colors[lv], lw=2 if lv < 2 else 1)
    ax.set_xlim(0, 7); ax.set_ylim(0, 1.05); ax.set_yticks([])
    ax.set_xlabel("fréquence (en fondamentales)")
    ax.text(6.95, 0.92, f"niveau 1 : 1 · niveau 2 : 2 · niveaux 3-4 : {len(level) - 3} sons", ha="right", color="#a9a59c", fontsize=9)

    # the result: the spiral against the real masses
    sp = report["spiral"]
    ax = fig.add_subplot(gs[5, :], facecolor=bg)
    ax.set_title(f"Le test, la spirale : la meilleure cascade (a = 10^{sp['la']:.2f}, b = 10^{sp['lb']:.2f}) et les masses mesurées · "
                 f"hasard : p = {sp['p']:.2f}", loc="left", color=ink, fontsize=11)
    co = spiral_coefficients(3)
    off = math.log10(sp["m0"])
    for i, j in co:
        x = off + sp["la"] * i + sp["lb"] * j
        ax.vlines(x, 0, 0.55, color="#55565e", lw=1)
    for k, name in enumerate(NAMES):
        ax.vlines(LOGM[k], 0.6, 1.0, color=gold if name in ("e", "mu", "tau") else blue if name in "udscbt" else violet, lw=2)
        ax.text(LOGM[k], 1.04, name, ha="center", fontsize=9, color=ink)
    ax.set_ylim(0, 1.2); ax.set_yticks([]); ax.set_xlabel("log10 (masse / GeV)")
    ax.set_xlim(LOGM.min() - 1, LOGM.max() + 1)

    # chance: real against random
    ax = fig.add_subplot(gs[6, 0], facecolor=bg)
    ax.hist(sp["null"], bins=30, color="#55565e")
    ax.axvline(sp["rms"], color=gold, lw=2)
    ax.set_title("Spirale : les vraies masses (or) contre des spectres au hasard", loc="left", fontsize=10)
    ax.set_xlabel("écart moyen à la cascade (décades)")
    ax = fig.add_subplot(gs[6, 1], facecolor=bg)
    tri = report["trinity"]
    fams = list(tri)
    ax.bar(range(len(fams)), [abs(tri[f]["Q"] - 2 / 3) for f in fams], color=[gold, blue, blue])
    ax.set_yscale("log"); ax.set_xticks(range(len(fams)), ["leptons e μ τ", "quarks u c t", "quarks d s b"], fontsize=9)
    ax.set_title("Trinité (Koide) : |Q − 2/3| par famille de trois", loc="left", fontsize=10)
    for k, f in enumerate(fams):
        ax.text(k, abs(tri[f]["Q"] - 2 / 3) * 1.4, f"p = {tri[f]['p']:.1g}", ha="center", fontsize=9)
    fig.suptitle("Du 0 naît le 1, du 1 naît le 2, du 2 naît le 3, du 3 naissent les 10 000 êtres", color=gold, fontsize=15, y=0.995)
    fig.savefig(path, dpi=110, facecolor=bg, bbox_inches="tight")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--null", type=int, default=200, help="random spectra for the chance test")
    ap.add_argument("--depth", type=int, default=3, help="depth of the cascade")
    ap.add_argument("--draw", help="draw the cascade and the result into this PNG")
    args = ap.parse_args()
    rep = run(n_null=args.null, depth=args.depth)
    if args.draw:
        draw(args.draw, rep)
        print(f"\ndrawn: {args.draw}")
