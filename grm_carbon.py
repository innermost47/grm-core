# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Anthony Charretier
"""
The carbon of the Earth as a network of zeros: where the global CO2 budget does not close, and which data are blurred.

Carbon is neither created nor destroyed. Every year, what humanity emits (fossil fuels and industry, land-use
change) must equal where it goes (the atmosphere, the ocean, the land, the carbonation of cement). The Global Carbon
Project publishes each term with its uncertainty, and the gap itself, the "budget imbalance". This script does not
look for causes. It asks where the gap sits and which estimates are least consistent with the others:

    1. THE ZERO THAT IS NOT ZERO: the imbalance year by year and by decade, in tonnes and in combined sigma; is it
       larger than the stated uncertainties allow (Birge ratio over all the years)?
    2. EVERY ESTIMATE AGAINST ALL THE OTHERS: a GRM network per year with the conservation law as an exact relation and
       every independent estimate as a measurement (atmospheric growth from NOAA stations and from inverse models;
       ocean sink from biogeochemistry models and from fCO2 data products; land sink from vegetation models;
       emissions). Each estimate is hidden in turn and predicted by the rest: its tension, year after year.
    3. WHICH OCEAN: the budget closed with the ocean models, then with the data products.
    4. WHERE THE YEARLY SWINGS SIT: which term the year-to-year imbalance follows (after removing slow trends).
    5. 2024: the record atmospheric growth, and the largest negative imbalance of the series.

Data: Global Carbon Budget 2025 (Friedlingstein et al. 2025, doi:10.18160/gcp-2025), via the CSV package of
openclimatedata/global-carbon-budget; in data/gcb2025_global_budget.csv. Values in GtC per year
(1 GtC = 3.664 Gt of CO2). Uncertainties as stated by the Global Carbon Budget (1 sigma): fossil 5 %, land-use change
0.7, atmospheric growth 0.2 (from 1980), ocean 0.4, land 0.5 GtC/yr; for the individual estimates, the spread of the
models or products. Two choices of this script, said here: cement carbonation is given 10 % (no value is stated), and
the atmospheric growth before 1980 is given 0.3.

Run: python grm_carbon.py
"""
import csv
import math
import os

from pygrm import GlobalRelationalNetwork

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "gcb2025_global_budget.csv")
TERMS = ("fossil", "land_use_change", "atmospheric_growth", "ocean_sink", "land_sink", "cement_carbonation")
SIGNS = {"fossil": 1, "land_use_change": 1, "atmospheric_growth": -1, "ocean_sink": -1, "land_sink": -1,
         "cement_carbonation": -1}


def load(path=DATA):
    rows = {}
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            rows[int(r["year"])] = {k: (float(v) if v not in ("", None) else None) for k, v in r.items() if k != "year"}
    return rows


def stated_sigma(term, row, year):
    return {"fossil": 0.05 * row["fossil"], "land_use_change": 0.7,
            "atmospheric_growth": 0.2 if year >= 1980 else 0.3, "ocean_sink": 0.4, "land_sink": 0.5,
            "cement_carbonation": 0.1 * row["cement_carbonation"]}[term]


def combined_sigma(row, year):
    return math.sqrt(sum(stated_sigma(t, row, year) ** 2 for t in TERMS))


# ------------------------------------------------------------------ the estimates of one year
def estimates(row, year):
    """Every independent estimate of every term: (name, term, value, sigma). The ocean models are scaled by 1.1 and
    the fCO2 products raised by 0.18 GtC/yr, the land models scaled by 0.81, as the Global Carbon Budget does before
    combining them (its documented adjustments)."""
    est = [("fossil emissions", "fossil", row["fossil"], stated_sigma("fossil", row, year)),
           ("land-use change emissions", "land_use_change", row["land_use_change"], 0.7),
           ("atmospheric growth, NOAA stations", "atmospheric_growth", row["atmospheric_growth"],
            stated_sigma("atmospheric_growth", row, year)),
           ("cement carbonation", "cement_carbonation", row["cement_carbonation"],
            stated_sigma("cement_carbonation", row, year))]
    if row.get("atm_growth_inversions_mean") is not None and row.get("atm_growth_inversions_sd") is not None:
        est.append(("atmospheric growth, inverse models", "atmospheric_growth", row["atm_growth_inversions_mean"],
                    max(row["atm_growth_inversions_sd"], 0.1)))
    if row.get("ocean_models_mean") is not None and row.get("ocean_models_sd") is not None:
        est.append(("ocean sink, biogeochemistry models", "ocean_sink", 1.1 * row["ocean_models_mean"],
                    max(1.1 * row["ocean_models_sd"], 0.1)))
    if row.get("ocean_products_mean") is not None and row.get("ocean_products_sd") is not None:
        est.append(("ocean sink, fCO2 data products", "ocean_sink", row["ocean_products_mean"] + 0.18,
                    max(row["ocean_products_sd"], 0.1)))
    if row.get("land_models_mean") is not None and row.get("land_models_sd") is not None:
        est.append(("land sink, vegetation models", "land_sink", 0.81 * row["land_models_mean"],
                    max(0.81 * row["land_models_sd"], 0.1)))
    else:
        est.append(("land sink (GCB)", "land_sink", row["land_sink"], 0.5))
    return est


def year_network(est, leave_out=None):
    """The conservation law as an exact relation; each estimate a measured node tied to its term by its sigma."""
    nodes = {t: {"guess": 1.0, "scale": "lin"} for t in TERMS}
    rels = [{"name": "carbon is conserved", "type": "sum", "terms": {t: float(SIGNS[t]) for t in TERMS}, "K": 0.0,
             "sigma": 1e-6}]
    measured = {}
    for k, (name, term, value, sigma) in enumerate(est):
        nodes[f"m{k}"] = {"guess": value, "scale": "lin"}
        measured[f"m{k}"] = (value, 1e-6)
        if k != leave_out:
            rels.append({"name": name, "type": "sum", "terms": {term: 1.0, f"m{k}": -1.0}, "K": 0.0, "sigma": sigma})
    net = GlobalRelationalNetwork(nodes, rels)
    return net.solve(measured, max_iterations=10)


def tensions(row, year):
    """Each estimate hidden in turn, predicted by all the others: (name, value, predicted, tension in sigma)."""
    est = estimates(row, year)
    out = []
    for k, (name, term, value, sigma) in enumerate(est):
        res = year_network(est, leave_out=k)
        pred, s_pred = res["values"][term], res["uncertainty"][term]
        out.append((name, value, pred, (value - pred) / math.sqrt(sigma ** 2 + s_pred ** 2)))
    full = year_network(est)
    return out, full


# ------------------------------------------------------------------ helpers
def detrend(xs, ys, degree=3):
    """Remove the slow trend (a polynomial, by least squares) to keep the year-to-year swings."""
    n = degree + 1
    x0 = sum(xs) / len(xs)
    X = [[(x - x0) / 20 ** j if False else ((x - x0) / 20) ** j for j in range(n)] for x in xs]
    A = [[sum(X[i][a] * X[i][b] for i in range(len(xs))) for b in range(n)] for a in range(n)]
    v = [sum(X[i][a] * ys[i] for i in range(len(xs))) for a in range(n)]
    for i in range(n):                                   # Gauss elimination (small system)
        p = A[i][i]
        for j in range(i + 1, n):
            f = A[j][i] / p
            A[j] = [aj - f * ai for aj, ai in zip(A[j], A[i])]
            v[j] -= f * v[i]
    c = [0.0] * n
    for i in reversed(range(n)):
        c[i] = (v[i] - sum(A[i][j] * c[j] for j in range(i + 1, n))) / A[i][i]
    return [y - sum(c[j] * X[i][j] for j in range(n)) for i, y in enumerate(ys)]


def corr(a, b):
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    sab = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    return sab / math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b))


# ------------------------------------------------------------------ the run
def run(out=print):
    data = load()
    years = sorted(data)
    out("THE CARBON OF THE EARTH AS A NETWORK OF ZEROS (Global Carbon Budget 2025, GtC per year)\n")

    out("1. THE ZERO THAT IS NOT ZERO: emissions - (atmosphere + ocean + land + cement)")
    decades = {}
    for y in years:
        decades.setdefault(10 * (y // 10), []).append(data[y]["budget_imbalance"])
    out("   decade mean imbalance: " + ", ".join(f"{d}s {sum(v) / len(v):+.2f}" for d, v in sorted(decades.items())))
    t = {y: data[y]["budget_imbalance"] / combined_sigma(data[y], y) for y in years}
    birge = math.sqrt(sum(v * v for v in t.values()) / len(t))
    out(f"   in combined sigma: {sum(1 for v in t.values() if abs(v) > 1)} of {len(t)} years beyond 1 sigma "
        f"(expected about {round(0.317 * len(t))}), beyond 2 sigma: {', '.join(str(y) for y in years if abs(t[y]) > 2) or 'none'}")
    out(f"   Birge ratio over all the years: {birge:.2f} (1: the stated uncertainties fit the scatter; below 1: they are "
        f"generous)")
    mean_all = sum(data[y]["budget_imbalance"] for y in years) / len(years)
    sem = math.sqrt(sum((data[y]["budget_imbalance"] - mean_all) ** 2 for y in years) / (len(years) - 1) / len(years))
    out(f"   but the mean is not zero: {mean_all:+.2f} +- {sem:.2f} GtC/yr over {years[0]}-{years[-1]}: on average, "
        f"about {mean_all * 3.664:.1f} Gt of CO2 a year go somewhere the budget does not see (the scatter hides a bias)")

    out("\n2. EVERY ESTIMATE AGAINST ALL THE OTHERS (GRM network per year, each estimate hidden in turn)")
    span = [y for y in years if data[y].get("ocean_products_mean") is not None and data[y].get("land_models_mean") is not None]
    stats = {}
    per_year = {}
    for y in span:
        tens, _ = tensions(data[y], y)
        per_year[y] = tens
        for name, value, pred, tn in tens:
            stats.setdefault(name, []).append(tn)
    out(f"   {span[0]}-{span[-1]}: mean tension (sign: the estimate is above (+) or below (-) what the rest implies), "
        f"years beyond 2 sigma")
    for name, ts in sorted(stats.items(), key=lambda kv: -abs(sum(kv[1]) / len(kv[1]))):
        mean = sum(ts) / len(ts)
        out(f"     {name:<38} {mean:+5.2f} sigma   {sum(1 for v in ts if abs(v) > 2):2d} of {len(ts)} years beyond 2 sigma")

    out("\n3. WHICH OCEAN: the budget closed with each ocean estimate (same years)")
    for label, key, f, add in (("ocean models (x1.1)", "ocean_models_mean", 1.1, 0.0),
                               ("fCO2 data products (+0.18)", "ocean_products_mean", 1.0, 0.18),
                               ("GCB combined", "ocean_sink", 1.0, 0.0)):
        imb = [data[y]["fossil"] + data[y]["land_use_change"] - data[y]["atmospheric_growth"] - (f * data[y][key] + add)
               - data[y]["land_sink"] - data[y]["cement_carbonation"] for y in span]
        out(f"     {label:<28} mean imbalance {sum(imb) / len(imb):+.2f}, rms {math.sqrt(sum(v * v for v in imb) / len(imb)):.2f} GtC/yr")

    out("\n4. WHERE THE YEARLY SWINGS SIT (1980-2024, slow trends removed)")
    ys = [y for y in years if y >= 1980]
    imb = detrend(ys, [data[y]["budget_imbalance"] for y in ys])
    swings = {}
    for term in TERMS[:5]:
        swings[term] = corr(imb, detrend(ys, [data[y][term] for y in ys]))
    out("   correlation of the imbalance's swings with each term's swings: " +
        ", ".join(f"{k.replace('_', ' ')} {v:+.2f}" for k, v in swings.items()))
    out("   (the imbalance swings almost exactly against the atmospheric growth: the year-to-year jumps measured in the "
        "air are not followed by the estimated sinks)")

    out("\n5. 2024")
    y = 2024
    out(f"   atmospheric growth {data[y]['atmospheric_growth']:.2f} GtC (NOAA), inverse models "
        f"{data[y]['atm_growth_inversions_mean']:.2f} +- {data[y]['atm_growth_inversions_sd']:.2f}, satellite (GRESO) "
        f"{data[y]['atm_growth_greso']:.2f}; imbalance {data[y]['budget_imbalance']:+.2f} ({t[y]:+.1f} combined sigma)")
    if y in per_year:
        for name, value, pred, tn in per_year[y]:
            out(f"     {name:<38} {value:6.2f}  predicted by the rest {pred:6.2f}   {tn:+.1f} sigma")
    return {"birge": birge, "mean": mean_all, "sem": sem, "stats": stats, "swings": swings, "per_year": per_year}


if __name__ == "__main__":
    run()
