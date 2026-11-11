# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Anthony Charretier
"""
The world economy as a network of zeros: a zero that is not zero, and the node that would close it.

Everything a country sells, another buys; every surplus is someone's deficit. Added up over all the countries, the
current accounts (what each country earns or spends in its exchanges with the rest of the world) must make exactly
zero: the Earth trades with nobody else. In the official statistics they do not. This script asks the GRM question:
the network does not close, so where is the missing node, and how large is it?

    1. THE ZERO THAT IS NOT ZERO: the sum of the current accounts of all the countries, year by year (IMF World Economic
       Outlook, October 2026), in dollars and in share of world GDP.
    2. WHERE IT SITS: split into a trade part (world exports minus world imports of goods and services, which must
       also make zero) and an income part (incomes and transfers between countries, which must make zero too).
    3. WHAT CARRIES IT: a hidden node proportional to a series that could carry it. Three carriers are written before
       looking (world GDP, world exports, the oil price), then every country's own current account is tried as a
       placebo, on year-to-year changes (on levels, any growing series fits a growing gap). A carrier counts only if it
       beats the placebos and a permutation test.
    4. THE GRM NETWORK: the hidden node written into the network (trade gap = lambda x world exports), solved by the
       GRM solver: lambda, its uncertainty, how well one single lambda holds over the years (Birge ratio), and the
       years that pull hardest.
    5. INSIDE EACH COUNTRY: a second zero, current account = saving - investment (as a share of GDP). Where the
       country's own accounts do not close.

Data: IMF World Economic Outlook database, October 2026 (extracted from the public dataset of mitsuoxv/imf-weo,
MIT licence), in data/weo_2026oct_current_accounts.csv. Values in billions of US dollars unless said otherwise.
Years up to 2024 are treated as measured; later ones are IMF projections.

Run: python grm_world.py               (add --draw world.png for the picture)
"""
import csv
import math
import os
import random
from collections import defaultdict

from pygrm import GlobalRelationalNetwork

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "weo_2026oct_current_accounts.csv")
LAST_MEASURED = 2024
CARRIERS_FIXED_IN_ADVANCE = ("WORLD_GDP", "WORLD_EXPORTS", "OIL_PRICE")


def load(path=DATA):
    series = defaultdict(dict)                  # (area, concept) -> {year: value}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            series[(row["ref_area"], row["concept"])][int(row["year"])] = float(row["value"])
    return series


def countries(series):
    return sorted({a for (a, k) in series if len(a) == 3 and a.isalpha() and k == "BCA"})


def world_parts(series, years):
    """World current account (the IMF's world aggregate, which is the sum over countries), its trade part (exports
    minus imports of goods and services, advanced plus emerging economies) and its income part (the rest)."""
    s = lambda a, k: series[(a, k)]
    total = {y: s("G001", "BCA")[y] for y in years if y in s("G001", "BCA")}
    trade = {y: s("G110", "BX")[y] + s("G200", "BX")[y] - s("G110", "BM")[y] - s("G200", "BM")[y]
             for y in years if all(y in s(g, k) for g in ("G110", "G200") for k in ("BX", "BM"))}
    exports = {y: s("G110", "BX")[y] + s("G200", "BX")[y] for y in trade}
    income = {y: total[y] - trade[y] for y in trade if y in total}
    return total, trade, income, exports


def sum_over_countries(series, years):
    out = {}
    for y in years:
        vals = [series[(c, "BCA")][y] for c in countries(series) if y in series[(c, "BCA")]]
        out[y] = (sum(vals), len(vals))
    return out


def world_gdp(series, years):
    return {y: sum(series[(c, "NGDPD")].get(y, 0.0) for c in countries(series)) for y in years}


# ------------------------------------------------------------------ carriers, judged on year-to-year changes
def r2_changes(target, carrier, years):
    dy = [target[b] - target[a] for a, b in zip(years, years[1:])]
    dx = [carrier[b] - carrier[a] for a, b in zip(years, years[1:])]
    sxx = sum(x * x for x in dx)
    if sxx == 0:
        return 0.0, 0.0
    lam = sum(x * y for x, y in zip(dx, dy)) / sxx
    ss = sum((y - lam * x) ** 2 for x, y in zip(dx, dy))
    tot = sum(y * y for y in dy)
    return 1 - ss / tot, lam


def permutation_p(target, carrier, years, n=20000, seed=1):
    """How often a random reordering of the carrier's yearly changes explains the target's changes as well."""
    dy = [target[b] - target[a] for a, b in zip(years, years[1:])]
    dx = [carrier[b] - carrier[a] for a, b in zip(years, years[1:])]
    obs = r2_from(dx, dy)
    rng = random.Random(seed)
    hits = 0
    for _ in range(n):
        rng.shuffle(dx)
        if r2_from(dx, dy) >= obs:
            hits += 1
    return (hits + 1) / (n + 1)


def r2_from(dx, dy):
    sxx = sum(x * x for x in dx)
    lam = sum(x * y for x, y in zip(dx, dy)) / sxx
    return 1 - sum((y - lam * x) ** 2 for x, y in zip(dx, dy)) / sum(y * y for y in dy)


def carrier_table(series, target, years, gdp, exports):
    cands = {"WORLD_GDP": gdp, "WORLD_EXPORTS": exports, "OIL_PRICE": series[("G001", "POILAPSP")]}
    for c in countries(series):
        ca = series[(c, "BCA")]
        if all(y in ca for y in years):
            cands[c] = ca
    rows = []
    for name, x in cands.items():
        if not all(y in x for y in years):
            continue
        r2, lam = r2_changes(target, x, years)
        rows.append((name, r2, lam))
    rows.sort(key=lambda r: -r[1])
    return rows


# ------------------------------------------------------------------ the hidden node in a GRM network
def grm_hidden_trade_node(trade, exports, years, sigma=50.0):
    """Each year: the world trade gap = lambda x world exports (a hidden node proportional to trade: something
    recorded on the export side that never appears on the import side, or the reverse). sigma (billions) is a first
    guess of the yearly scatter; the Birge ratio says how far one single lambda is from holding every year."""
    nodes = {"lam": {"guess": 0.0, "scale": "lin"}}
    rels = []
    for y in years:
        nodes[f"T{y}"] = {"guess": trade[y], "scale": "lin"}
        rels.append({"name": f"{y}: trade gap = lambda x exports", "type": "sum",
                     "terms": {f"T{y}": 1.0, "lam": -exports[y]}, "K": 0.0, "sigma": sigma})
    measured = {f"T{y}": (trade[y], 1e-3) for y in years}
    net = GlobalRelationalNetwork(nodes, rels)
    res = net.solve(measured, max_iterations=20)
    birge = math.sqrt(res["reduced_chi2"]) if res["reduced_chi2"] else float("nan")
    lam, s_lam = res["values"]["lam"], res["uncertainty"]["lam"]
    return lam, s_lam * max(birge, 1.0), birge, res["relation_pulls"]


def grm_drifting_trade_node(trade, exports, years, sigma=50.0, pivot=2010):
    """The same node, its share allowed to drift in time: lambda_t = l0 + l1 (t - pivot). Is the drift worth its extra
    number? (Bayesian information criterion, on the Birge-scaled chi2 of the simpler network.)"""
    nodes = {"l0": {"guess": 0.0, "scale": "lin"}, "l1": {"guess": 0.0, "scale": "lin"}}
    rels = []
    for y in years:
        nodes[f"T{y}"] = {"guess": trade[y], "scale": "lin"}
        rels.append({"name": f"{y}: trade gap = (l0 + l1 t) x exports", "type": "sum",
                     "terms": {f"T{y}": 1.0, "l0": -exports[y], "l1": -exports[y] * (y - pivot)}, "K": 0.0, "sigma": sigma})
    res = GlobalRelationalNetwork(nodes, rels).solve({f"T{y}": (trade[y], 1e-3) for y in years}, max_iterations=20)
    v, u = res["values"], res["uncertainty"]
    return v["l0"], u["l0"], v["l1"], u["l1"], res["cost"], math.sqrt(res["reduced_chi2"]), res["relation_pulls"]


# ------------------------------------------------------------------ the run
def run(out=print):
    series = load()
    years_all = list(range(1980, 2032))
    measured_years = [y for y in years_all if y <= LAST_MEASURED]
    total, trade, income, exports = world_parts(series, years_all)
    gdp = world_gdp(series, years_all)
    sums = sum_over_countries(series, years_all)

    out("THE WORLD ECONOMY AS A NETWORK OF ZEROS (IMF World Economic Outlook, October 2026)\n")
    out("1. THE ZERO THAT IS NOT ZERO: the current accounts of all the countries, added up (billions of dollars)")
    out("   year   world sum   % of world GDP   countries   (sum over countries, check)")
    for y in measured_years:
        if y in total and y >= 1981:
            s, n = sums[y]
            out(f"   {y}  {total[y]:+9.0f}      {100 * total[y] / gdp[y]:+6.2f} %        {n:4d}       ({s:+.0f})")
    neg = [y for y in measured_years if y in total and total[y] < 0 and y >= 1981]
    pos = [y for y in measured_years if y in total and total[y] > 0 and y >= 1981]
    out(f"   the world 'runs a deficit with itself' from {min(neg)} to {max(neg)}, then a surplus from {min(pos)} to "
        f"{max(pos)}; in {LAST_MEASURED}: {total[LAST_MEASURED]:+.0f} billion ({100 * total[LAST_MEASURED] / gdp[LAST_MEASURED]:+.2f} % of GDP).")
    proj = [y for y in years_all if y > LAST_MEASURED and y in total]
    out(f"   IMF projections: {', '.join(f'{y} {total[y]:+.0f}' for y in proj)} (the projections do not close either)")

    split_years = [y for y in measured_years if y in trade]
    out(f"\n2. WHERE IT SITS ({split_years[0]}-{split_years[-1]}): trade part (world exports - world imports) "
        f"and income part (incomes and transfers)")
    out("   year    total    trade part   income part   world exports")
    for y in split_years:
        out(f"   {y}  {total[y]:+7.0f}    {trade[y]:+8.0f}     {income[y]:+8.0f}      {exports[y]:8.0f}")
    out(f"   in {LAST_MEASURED}: the world exports {trade[LAST_MEASURED]:+.0f} billion more than it imports "
        f"({100 * trade[LAST_MEASURED] / exports[LAST_MEASURED]:.1f} % of its exports), and pays {-income[LAST_MEASURED]:.0f} "
        f"billion more income than it receives: two zeros broken in opposite directions.")

    out("\n3. WHAT CARRIES IT: carriers judged on year-to-year changes, against every country as a placebo")
    report = {}
    for label, target in (("trade part", trade), ("income part", income), ("total", total)):
        rows = carrier_table(series, target, split_years, gdp, exports)
        rank = {r[0]: i + 1 for i, r in enumerate(rows)}
        out(f"   {label}: best carriers among {len(rows)}: " +
            ", ".join(f"{name} (R2 {r2:.2f})" for name, r2, _ in rows[:6]))
        for name in CARRIERS_FIXED_IN_ADVANCE:
            r2 = next(r[1] for r in rows if r[0] == name)
            x = {"WORLD_GDP": gdp, "WORLD_EXPORTS": exports, "OIL_PRICE": series[("G001", "POILAPSP")]}[name]
            p = permutation_p(target, x, split_years)
            out(f"     fixed in advance: {name:<13} rank {rank[name]:3d}/{len(rows)}, R2 {r2:.2f}, "
                f"permutation p = {p:.4f} ({'beats chance' if p * len(CARRIERS_FIXED_IN_ADVANCE) < 0.01 else 'not significant'})")
        report[label] = {"rows": rows, "rank": rank}
    out("   (with three carriers fixed in advance, a p below 0.0033 survives the look-elsewhere correction; the placebo "
        "countries at the top are coincidences of 27 yearly changes, which is why they are not candidates)")

    lam, s_lam, birge, pulls = grm_hidden_trade_node(trade, exports, split_years)
    out("\n4. THE GRM NETWORK: the hidden node written in (each year, trade gap = lambda x world exports)")
    out(f"   lambda = {100 * lam:.2f} +- {100 * s_lam:.2f} % of world exports; Birge ratio {birge:.2f} "
        f"(1 would mean one lambda holds every year within 50 billion)")
    strained = sorted(pulls.items(), key=lambda kv: -abs(kv[1]))[:4]
    out("   the years that pull hardest: " + ", ".join(f"{k.split(':')[0]} ({v:+.1f} sigma)" for k, v in strained))
    proj_tr = [y for y in years_all if y > LAST_MEASURED and y in trade]
    out("   with the IMF's projected exports, the node gives: " +
        ", ".join(f"{y} {lam * exports[y]:+.0f} (IMF: {trade[y]:+.0f})" for y in proj_tr))

    l0, s0, l1, s1, cost_d, birge_d, pulls_d = grm_drifting_trade_node(trade, exports, split_years)
    cost_c = birge ** 2 * (len(split_years) - 1)
    n = len(split_years)
    dbic = (cost_c + math.log(n) * 1) - (cost_d + math.log(n) * 2)
    out(f"   letting the share drift: lambda = {100 * l0:.2f} % in 2010, {100 * l1:+.3f} +- {100 * s1 * max(birge_d, 1):.3f} points a year; "
        f"Birge ratio {birge_d:.2f}; BIC gain {dbic:+.0f} ({'the drift is real' if dbic > 6 else 'not worth it'})")
    out("   with the drift and the IMF's projected exports: " +
        ", ".join(f"{y} {(l0 + l1 * (y - 2010)) * exports[y]:+.0f}" for y in proj_tr))
    out("   (a small bet against the IMF's own projection, decided when the 2025 accounts are published)")

    out("\n5. INSIDE EACH COUNTRY: current account = saving - investment (% of GDP), 2015-2024")
    gaps = []
    for c in countries(series):
        g = [series[(c, "BCA_NGDPD")][y] - (series[(c, "NGSD_NGDP")][y] - series[(c, "NID_NGDP")][y])
             for y in range(2015, 2025)
             if all(y in series[(c, k)] for k in ("BCA_NGDPD", "NGSD_NGDP", "NID_NGDP"))]
        if g:
            gaps.append((c, sum(g) / len(g), len(g)))
    closing = sum(1 for _, g, _ in gaps if abs(g) < 0.05)
    out(f"   {closing} of {len(gaps)} countries close their own accounts (within 0.05 point of GDP on average);")
    out("   the largest gaps: " + ", ".join(f"{c} {g:+.2f}" for c, g, _ in sorted(gaps, key=lambda r: -abs(r[1]))[:8]))
    return {"total": total, "trade": trade, "income": income, "lam": lam, "s_lam": s_lam, "birge": birge,
            "drift": (l0, s0, l1, s1, birge_d, dbic),
            "carriers": report, "gaps": gaps}


def draw(path, rep, series=None):
    """The broken zero, its two parts, and the hidden node the GRM network writes in."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    total, trade, income = rep["total"], rep["trade"], rep["income"]
    series = series or load()
    _, _, _, exports = world_parts(series, list(range(1980, 2032)))
    l0, _, l1, _, _, _ = rep["drift"]
    ys = [y for y in sorted(total) if 1981 <= y <= LAST_MEASURED]
    yp = [y for y in sorted(trade) if y <= LAST_MEASURED]
    fig, ax = plt.subplots(figsize=(11, 5.5))
    ax.axhline(0, color="#888", lw=1)
    ax.plot(ys, [total[y] for y in ys], color="#1f2326", lw=2.4, label="world current account (should be 0)")
    ax.plot(yp, [trade[y] for y in yp], color="#2f68a3", lw=1.8, label="trade part: exports - imports (should be 0)")
    ax.plot(yp, [income[y] for y in yp], color="#b9621b", lw=1.8, label="income part (should be 0)")
    ax.plot(yp, [(l0 + l1 * (y - 2010)) * exports[y] for y in yp], color="#2f68a3", lw=1.2, ls="--",
            label="GRM hidden node: (2.27 % + 0.061 pt/yr) x world exports")
    ax.set_ylabel("billions of US dollars")
    ax.set_title("The world economy does not add up to zero (IMF WEO, October 2026)", loc="left")
    ax.legend(frameon=False, fontsize=9, loc="upper left")
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    fig.savefig(path, dpi=130, bbox_inches="tight")


if __name__ == "__main__":
    import sys
    rep = run()
    if "--draw" in sys.argv:
        path = sys.argv[sys.argv.index("--draw") + 1]
        draw(path, rep)
        print(f"\ndrawn: {path}")
