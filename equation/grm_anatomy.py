# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Anthony Charretier
"""Anatomy of the GRM network: the nodes as well as the strings, and where the network breaks.

Called by grm_strings.py once every string has been plucked (the response matrix R, nodes x strings).

    - nodes: what they measure. On a guitar a node is where the string pulls on the material; here each node
      has a resistance (how hard the whole network holds it: 1 / its uncertainty after the solve), a load (how much
      it moves when the strings are plucked) and a stress (how strongly the relations around it pull on it)
    - silent floors: nodes that never answer, and why (fixed, held by a measurement, cut off by fixed nodes)
    - decades: at which scales the network still answers, and where it stops
    - propagation: how an answer weakens with the number of relations it crosses (the attenuation per hop)
    - rupture: each string is pulled until the network can no longer hold its data (the total tension rises by
      a critical amount, 5 sigma by default); its breaking point, the node that gives way first, and the wave the
      break sends through the network
Every finding gets a fitted law of this network, written in LaTeX, and a picture; everything is gathered in
grm_strings_report.html (formulas rendered by MathJax when online, the pictures are embedded).
"""
import base64
import io
import math
from collections import deque

import numpy as np

CRITICAL = 25.0       # rise of the total tension (chi^2) at which a string breaks: 5 sigma
STILL = 1e-9


# ------------------------------------------------------------------ helpers
def measurement_pulls(net, values, measured):
    out = {}
    for name, m in measured.items():
        if name not in net.node_to_idx:
            continue
        v, s = (m if isinstance(m, (tuple, list)) else (m, 1e-4))
        i = net.node_to_idx[name]
        x = values[name] if net.lin[i] else math.log10(max(values[name], 1e-300))
        t = v if net.lin[i] else math.log10(v)
        out[name] = (x - t) / s
    return out


def hops_from(net, start_nodes):
    """Number of relations crossed from a set of nodes to every node (breadth first over the relations)."""
    neighbours = {n: set() for n in net.nodes_names}
    for rel in net.relations:
        names = relation_nodes(net, rel)
        for a in names:
            neighbours[a].update(names)
    dist = {n: math.inf for n in net.nodes_names}
    q = deque()
    for n in start_nodes:
        dist[n] = 0
        q.append(n)
    while q:
        a = q.popleft()
        for b in neighbours[a]:
            if dist[b] == math.inf:
                dist[b] = dist[a] + 1
                q.append(b)
    return dist, neighbours


def relation_nodes(net, rel):
    if rel["type"] == "sum":
        return [net.nodes_names[i] for i, _, _ in rel["terms"]]
    if rel["type"] == "log":
        return [net.nodes_names[i] for i, _ in rel["terms"]]
    return [net.nodes_names[i] for i in rel["nodes"]]


def fit_line(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    ok = np.isfinite(x) & np.isfinite(y)
    if ok.sum() < 3:
        return float("nan"), float("nan"), float("nan")
    b, a = np.polyfit(x[ok], y[ok], 1)
    r = np.corrcoef(x[ok], y[ok])[0, 1]
    return float(a), float(b), float(r)


def png(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120)
    return base64.b64encode(buf.getvalue()).decode()


# ------------------------------------------------------------------ the analysis
def anatomy(net, measured, base, strings, names, R, scales, pluck, families, home_of):
    """Everything about nodes and rupture. Returns a list of sections (title, text, latex, picture)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    sections = []
    values = base["values"]
    nodes = net.nodes_names
    n_nodes = len(nodes)

    # ---- nodes: resistance, load, stress
    full = net.solve(measured_dict=measured, compute_uncertainty=True, start=values)
    sig = full["sigma_dex"]
    resistance = np.array([1.0 / sig[n] if sig[n] > 0 else math.inf for n in nodes])
    load = np.linalg.norm(R, axis=1)
    degree = np.array([sum(n in relation_nodes(net, r) for r in net.relations) for n in nodes])
    pulls = full["relation_pulls"]
    stress = np.array([sum(pulls.get(r["name"], 0.0) ** 2 for r in net.relations if n in relation_nodes(net, r))
                       for n in nodes])
    fixed = np.array([n in net.fixed_nodes for n in nodes])
    free = set(full.get("undetermined", []))                       # nothing holds them: no resistance to speak of
    finite = np.isfinite(resistance) & (resistance > 0) & np.array([n not in free for n in nodes])
    a, b, r = fit_line(np.log10(np.maximum(degree[finite], 1)), np.log10(resistance[finite]))
    text = (f"{int(fixed.sum())} nodes are fixed (infinite resistance). Among the others, the most rigid are "
            + ", ".join(f"{nodes[i]} ({resistance[i]:.3g})" for i in np.argsort(-np.where(finite, resistance, 0))[:6])
            + "; the most yielding are "
            + ", ".join(f"{nodes[i]} ({resistance[i]:.3g})" for i in np.argsort(np.where(finite, resistance, np.inf))[:6])
            + f". {len(free)} nodes are held by nothing (undetermined) and are left out"
            + f". The resistance grows with the number of relations holding a node with exponent {b:.2f} "
              f"(correlation {r:.2f}). The most loaded nodes (moved by the plucks): "
            + ", ".join(nodes[i] for i in np.argsort(-load)[:6])
            + "; the most stressed by the relations around them: "
            + ", ".join(f"{nodes[i]} ({stress[i]:.2g})" for i in np.argsort(-stress)[:5]) + ".")
    latex = (r"\rho_i = \frac{1}{\sigma_i},\qquad \frac{1}{\sigma_i^{2}} = \Big[\big(J^{\top}WJ\big)^{-1}\Big]_{ii}^{-1}"
             rf",\qquad \rho_i \approx 10^{{{a:.2f}}}\,k_i^{{{b:.2f}}}")
    fig, ax = plt.subplots(1, 2, figsize=(11, 4))
    ax[0].scatter(np.maximum(degree[finite], 1), resistance[finite], s=12, color="#2563eb")
    ax[0].set_xscale("log"); ax[0].set_yscale("log")
    ax[0].set_xlabel("relations holding the node (k)"); ax[0].set_ylabel("resistance 1/sigma")
    ax[0].set_title("Resistance of the nodes")
    ax[1].scatter(np.log10(resistance[finite]), np.log10(np.maximum(load[finite], 1e-12)), s=12, color="#d97706")
    ax[1].set_xlabel("log10 resistance"); ax[1].set_ylabel("log10 load (how much it moves)")
    ax[1].set_title("Rigid nodes move less")
    fig.tight_layout()
    sections.append(("The nodes: resistance, load, stress", text, latex, png(fig)))
    plt.close(fig)

    # ---- silent floors
    silent = [i for i in range(n_nodes) if np.max(np.abs(R[i])) < STILL]
    reasons = {}
    measured_tight = {k for k, m in measured.items()
                      if isinstance(m, (tuple, list)) and k in net.node_to_idx and m[1] <= 1e-6}
    free_neighbours = hops_from(net, [])[1]
    for i in silent:
        n = nodes[i]
        if n in net.fixed_nodes:
            why = "fixed"
        elif n in measured_tight:
            why = "held by a tight measurement"
        elif degree[i] == 0:
            why = "in no relation"
        elif all(m in net.fixed_nodes or m == n or m in measured_tight for m in free_neighbours[n]):
            why = "only tied to fixed or held nodes"
        elif n in measured:
            why = "measured; its relations do not reach the plucked strings"
        else:
            why = "cut off from every string"
        reasons.setdefault(why, []).append(n)
    text = (f"{len(silent)} of {n_nodes} nodes never answer, whatever string is plucked. "
            + " ".join(f"{why.capitalize()}: {len(v)} ({', '.join(v[:12])}{' ...' if len(v) > 12 else ''})."
                       for why, v in sorted(reasons.items(), key=lambda kv: -len(kv[1]))))
    latex = (r"\text{silent}_i \iff \max_j \left|\frac{\partial \log x_i}{\partial \tau_j}\right| = 0"
             rf",\qquad \frac{{N_\text{{silent}}}}{{N}} = {len(silent)}/{n_nodes} = {len(silent) / n_nodes:.2f}")
    sections.append(("Silent floors", text, latex, None))

    # ---- decades: where the network still answers
    decade = np.array([math.log10(abs(values[n])) if values[n] != 0 else np.nan for n in nodes])
    answering = np.max(np.abs(R), axis=1) >= STILL
    bins = np.arange(np.floor(np.nanmin(decade) / 10) * 10, np.ceil(np.nanmax(decade) / 10) * 10 + 10, 10)
    rows = []
    for lo, hi in zip(bins[:-1], bins[1:]):
        inside = (decade >= lo) & (decade < hi)
        if inside.sum():
            rows.append((lo, hi, int(inside.sum()), int((inside & answering).sum()),
                         float(np.median(load[inside & answering])) if (inside & answering).any() else 0.0))
    first = float(np.nanmin(np.where(answering, decade, np.nan)))
    last = float(np.nanmax(np.where(answering, decade, np.nan)))
    sparse = [f"{int(lo)}..{int(hi)}" for lo, hi, n_, k_, _ in rows if n_ <= 2]
    xs = [(lo + hi) / 2 for lo, hi, *_ in rows]
    share = [k_ / n_ for _, _, n_, k_, _ in rows]
    a, b, r = fit_line(xs, share)
    text = (f"Nodes span decades {int(np.nanmin(decade))} to {int(np.nanmax(decade))} (values in the network's own units). "
            f"The network still answers from decade {int(first)} to decade {int(last)}. "
            f"Few data (two nodes or fewer) in the decades {', '.join(sparse) if sparse else 'none'}. "
            f"Across decades the share of answering nodes changes by {100 * b:.2f} points per decade (correlation {r:.2f}).")
    latex = rf"f_\text{{answer}}(D) \approx {a:.3f} {b:+.4f}\,D"
    fig, ax = plt.subplots(figsize=(11, 3.6))
    ax.bar(xs, [n_ for _, _, n_, _, _ in rows], width=8, color="#cbd5e1", label="nodes")
    ax.bar(xs, [k_ for _, _, _, k_, _ in rows], width=8, color="#2563eb", label="answering")
    ax.set_xlabel("decade of the value (log10)"); ax.set_ylabel("nodes"); ax.legend()
    ax.set_title("Where the network still answers")
    fig.tight_layout()
    sections.append(("Decades", text, latex, png(fig)))
    plt.close(fig)

    # ---- propagation: attenuation per relation crossed
    dist_amp = {}
    for j, rel in enumerate(strings):
        col = np.abs(R[:, j])
        if col.max() < STILL:
            continue
        dist, _ = hops_from(net, relation_nodes(net, rel))
        for i, n in enumerate(nodes):
            d = dist[n]
            if math.isfinite(d) and col[i] > STILL:
                dist_amp.setdefault(int(d), []).append(col[i] / col.max())
    ds = sorted(dist_amp)
    med = [float(np.median(dist_amp[d])) for d in ds]
    beyond = [k for k, d in enumerate(ds) if d >= 1]
    a, b, r = fit_line([ds[k] for k in beyond], np.log10([med[k] for k in beyond]))
    first_drop = med[beyond[0]] / med[0] if beyond and ds[0] == 0 else float("nan")
    reach = max(ds) if ds else 0
    text = ("An answer weakens as it crosses relations: median relative amplitude "
            + ", ".join(f"{m:.2g} at {d} hops" for d, m in zip(ds, med))
            + f". Crossing the first relation divides the answer by {1 / first_drop:.2g}: the measurements around a "
              f"string absorb most of it. Beyond, the attenuation is a factor 10 every "
              f"{(-1 / b) if b < 0 else math.inf:.2f} relations (fitted from 1 hop on, correlation {r:.2f}); "
              f"the farthest answer is {reach} relations away.")
    latex = (rf"\bar A(d) \approx A_0\,\epsilon_1\,10^{{{b:.3f}\,(d-1)}},\qquad \epsilon_1 \approx {first_drop:.2g},"
             r"\qquad d \ge 1")
    fig, ax = plt.subplots(figsize=(7, 3.8))
    for d in ds:
        ax.scatter(np.full(len(dist_amp[d]), d), dist_amp[d], s=4, alpha=0.25, color="#64748b")
    ax.plot(ds, med, "o-", color="#d97706", label="median")
    dd = np.array(ds, float)
    fit_d = dd[dd >= 1]
    ax.plot(fit_d, 10 ** (a + b * fit_d), "--", color="#111827", label="fit (from 1 hop)")
    ax.set_yscale("log"); ax.set_xlabel("relations crossed (hops)"); ax.set_ylabel("relative amplitude")
    ax.set_title("Propagation through the network"); ax.legend()
    fig.tight_layout()
    sections.append(("Propagation", text, latex, png(fig)))
    plt.close(fig)

    # ---- rupture: breaking point of each string, the node that gives way, the wave of the break
    c0 = base["cost"]
    eps = 1e-3
    breaks = []
    for j, rel in enumerate(strings):
        if np.abs(R[:, j]).max() < STILL:
            continue
        up = pluck(net, measured, base, [rel], scales, amount=eps, full=True)
        down = pluck(net, measured, base, [rel], scales, amount=-eps, full=True)
        k2 = (up["cost"] + down["cost"] - 2 * c0) / eps ** 2
        if not (k2 > 0):
            continue
        a_star = math.sqrt(2 * CRITICAL / k2)
        mp0 = measurement_pulls(net, values, measured)
        mp1 = measurement_pulls(net, up["values"], measured)
        rp0, rp1 = full["relation_pulls"], up["relation_pulls"]
        moves = {f"measure {k}": (mp1[k] - mp0[k]) / eps for k in mp0}
        moves.update({f"relation {k}": (rp1[k] - rp0.get(k, 0.0)) / eps for k in rp1 if k != rel["name"]})
        weakest = max(moves, key=lambda k: abs(moves[k])) if moves else "-"
        wave = np.abs(R[:, j]) * a_star
        reach = int(np.sum(wave > 0.01))          # nodes moved by more than 1 % (0.0043 dex) when it breaks
        breaks.append((rel["name"], rel["type"], a_star, weakest, reach, float(np.linalg.norm(R[:, j]))))
    breaks.sort(key=lambda b_: b_[2])
    loudness = np.array([b_[5] for b_ in breaks])
    astar = np.array([b_[2] for b_ in breaks])
    a, b, r = fit_line(np.log10(loudness), np.log10(astar))
    give = {}
    for b_ in breaks:
        give[b_[3]] = give.get(b_[3], 0) + 1
    text = (f"Each string was pulled until the total tension of the network rose by {CRITICAL:.0f} "
            f"(the data can no longer be held at 5 sigma). The most fragile strings break at "
            + ", ".join(f"{n} ({x:.2g})" for n, _, x, _, _, _ in breaks[:6])
            + "; the toughest hold up to "
            + ", ".join(f"{n} ({x:.2g})" for n, _, x, _, _, _ in breaks[-4:])
            + f" (tension shift: dex for a log relation, share of its terms for a sum). The breaking point falls "
              f"with how loud the string is, with exponent {b:.2f} (correlation {r:.2f}). What gives way first: "
            + ", ".join(f"{k} ({v} strings)" for k, v in sorted(give.items(), key=lambda kv: -kv[1])[:6])
            + ". The wave of a break moves on average "
            + f"{np.mean([b_[4] for b_ in breaks]):.0f} nodes by more than 1 %, at most {max(b_[4] for b_ in breaks)}"
            + f" ({max(breaks, key=lambda b_: b_[4])[0]}).")
    latex = (rf"a^{{*}}_j = \sqrt{{\frac{{2\,\Delta\chi^{{2}}_c}}{{k_j}}}},\quad k_j = \frac{{\partial^{{2}}\chi^{{2}}}}{{\partial\tau_j^{{2}}}},"
             rf"\quad \Delta\chi^{{2}}_c = {CRITICAL:.0f},\qquad a^{{*}}_j \approx 10^{{{a:.2f}}}\,L_j^{{{b:.2f}}}")
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.2))
    top = breaks[:25]
    ax[0].barh([t[0] for t in top][::-1], [t[2] for t in top][::-1], color="#dc2626")
    ax[0].set_xscale("log"); ax[0].set_xlabel("breaking point (tension shift)")
    ax[0].set_title("The 25 most fragile strings"); ax[0].tick_params(axis="y", labelsize=7)
    ax[1].scatter(loudness, astar, s=14, color="#7c3aed")
    xx = np.geomspace(loudness.min(), loudness.max(), 50)
    ax[1].plot(xx, 10 ** (a + b * np.log10(xx)), "--", color="#111827")
    ax[1].set_xscale("log"); ax[1].set_yscale("log")
    ax[1].set_xlabel("loudness of the string L"); ax[1].set_ylabel("breaking point a*")
    ax[1].set_title("Loud strings break first")
    fig.tight_layout()
    sections.append(("Rupture", text, latex, png(fig)))
    plt.close(fig)

    # ---- the whole network: nodes x strings, grouped by family
    order_s = np.argsort(home_of) if len(home_of) else np.arange(len(names))
    order_n = np.argsort(-load)
    fig, ax = plt.subplots(figsize=(12, 7))
    M = np.log10(np.abs(R[np.ix_(order_n, order_s)]) + 1e-12)
    im = ax.imshow(M, aspect="auto", cmap="inferno", vmin=-8, vmax=1)
    ax.set_xlabel("strings (grouped by family)"); ax.set_ylabel("nodes (most loaded first)")
    ax.set_title("Every node against every string: log10 |answer| (black: silent)")
    fig.colorbar(im, ax=ax, fraction=0.025)
    fig.tight_layout()
    sections.append(("The whole network", f"{n_nodes} nodes against {len(names)} strings; the black rows at the bottom "
                     "are the silent floors.", None, png(fig)))
    plt.close(fig)

    with open("grm_strings_breaks.csv", "w") as f:
        f.write("string,type,breaking_point,gives_way_first,nodes_moved_over_1pct\n")
        for n, t, x, w, reach_, _ in breaks:
            f.write(f"{n},{t},{x:.6g},{w},{reach_}\n")
    with open("grm_strings_nodes.csv", "w") as f:
        f.write("node,value,resistance,load,stress,relations,silent\n")
        silent_set = {nodes[i] for i in silent}
        for i, n in enumerate(nodes):
            f.write(f"{n},{values[n]:.10g},{resistance[i]:.6g},{load[i]:.6g},{stress[i]:.6g},{degree[i]},{n in silent_set}\n")
    return sections


def write_report(sections, extra_sections, path="grm_strings_report.html"):
    parts = ["""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>GRM strings report</title>
<script>window.MathJax = {tex: {inlineMath: [['\\\\(', '\\\\)']]}};</script>
<script src="https://cdn.jsdelivr.net/npm/mathjax@3.2.2/es5/tex-chtml.js"></script>
<style>body{font-family:Inter,Arial,sans-serif;max-width:1100px;margin:0 auto;padding:24px 16px;color:#111827;background:#fff}
h1{font-size:26px}h2{font-size:19px;margin-top:34px;border-top:1px solid #e5e7eb;padding-top:16px}
p{line-height:1.55}.eq{background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;padding:10px 14px;overflow-x:auto}
img{max-width:100%;border:1px solid #e5e7eb;border-radius:6px}</style></head><body>
<h1>The GRM network, plucked, measured and broken</h1>
<p>Laws fitted on this network: they describe the network as it is written, not nature itself.</p>"""]
    for title, text, latex, picture in list(extra_sections) + list(sections):
        parts.append(f"<h2>{title}</h2><p>{text}</p>")
        if latex:
            parts.append(f'<div class="eq">\\[{latex}\\]</div>')
        if picture:
            parts.append(f'<img alt="{title}" src="data:image/png;base64,{picture}">')
    parts.append("</body></html>")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(parts))
    return path
