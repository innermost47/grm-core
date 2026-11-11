# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Anthony Charretier
"""The wave of S x Equant = Estock over a cycle: Equant and Estock as one wave and its mirror.

Computed:  H(t) = H_end coth(1.5 H_end t) (flat universe, matter + vacuum), Equant = hbar H / 2 pi,
           Estock = c^5 / (2 G H), S = Estock / Equant. In log, Equant and Estock are mirror images around
           E_P / sqrt(4 pi): their sum never moves, S is the gap between them.
           The start is the point zero, S = 1 (Equant = Estock); the cycle lasts S_end tP Planck times.
Chosen:    the return replays the expansion backwards (Anthony's cycle), so each cycle is drawn symmetric;
           the horizontal axis is log10 of the number of Planck times since the start (first half) and
           before the end (second half). Radiation and anything before matter are left out.
"""
import math

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

C, G, HBAR = 299792458.0, 6.67430e-11, 1.054571817e-34
TP = math.sqrt(HBAR * G / C ** 5)
EP = HBAR / TP
H_END = 58.39 * 1e3 / 3.0856775814913673e22       # network value (km/s/Mpc -> s^-1)
T_TODAY = 4.26e17                                  # s, network t0

axis = math.log10(EP / math.sqrt(4 * math.pi))
s_end = math.pi / (H_END * TP) ** 2
half = math.log10(s_end) / 2                       # log10 of the cycle length in tP, halved
t_start = 2 * TP / (3 * math.sqrt(math.pi))        # H = sqrt(pi)/tP there: S = 1

x = np.linspace(math.log10(t_start / TP), half, 1500)
t = TP * 10 ** x
h = H_END / np.tanh(1.5 * H_END * t)
l_eq = np.log10(HBAR * h / (2 * math.pi))
l_st = np.log10(C ** 5 / (2 * G * h))
x0 = x[0]


def one_cycle(offset):
    """x positions and values of a full cycle (expansion, then the mirrored return)."""
    xs = np.concatenate([x - x0, 2 * (half - x0) - (x[::-1] - x0)]) + offset
    return xs, np.concatenate([l_eq, l_eq[::-1]]), np.concatenate([l_st, l_st[::-1]])


period = 2 * (half - x0)
fig, (top, bottom) = plt.subplots(2, 1, figsize=(15, 10), gridspec_kw={"height_ratios": [1, 1.2]})

for k in range(3):
    xs, eq, st = one_cycle(k * period)
    top.fill_between(xs, eq, st, color="#7c3aed", alpha=0.10, lw=0)
    top.plot(xs, st, color="#dc2626", lw=2, label="Estock (gravity, content)" if k == 0 else None)
    top.plot(xs, eq, color="#059669", lw=2, label="Equant (quantum, grain)" if k == 0 else None)
top.axhline(axis, color="black", lw=1.2, ls="--", label=f"axis E_P / sqrt(4 pi) = 10^{axis:.2f} J (the sum never moves)")
for k in range(4):
    top.axvline(k * period, color="#9ca3af", lw=0.8, ls=":")
top.set_xticks([k * period for k in range(4)])
top.set_xticklabels(["point zero"] * 4)
top.set_ylabel("log10 energy (J)")
top.set_title("One wave and its mirror, cycle after cycle (each cycle: point zero -> plateau -> point zero)")
top.legend(loc="upper right", fontsize=8)

xs, eq, st = one_cycle(0)
bottom.fill_between(xs, eq, st, color="#7c3aed", alpha=0.12, lw=0, label="gap = log10 S (S = Estock / Equant)")
bottom.plot(xs, st, color="#dc2626", lw=2.5, label="Estock")
bottom.plot(xs, eq, color="#059669", lw=2.5, label="Equant")
bottom.axhline(axis, color="black", lw=1.2, ls="--")
x_today = math.log10(T_TODAY / TP) - x0
for xv, lab, y, ha in ((0, "point zero\nS = 1", 75, "left"), (x_today, "today  ", 75, "right"),
                      (half - x0, "middle of the cycle\n(plateau)", 82, "center"),
                      (period - x_today, "  mirror of today\n  (return)", 75, "left"),
                      (period, "point zero\n(next cycle)", 75, "right")):
    bottom.axvline(xv, color="#6b7280", lw=0.8, ls=":")
    bottom.text(xv, y, lab, ha=ha, va="bottom", fontsize=8)
bottom.set_ylim(-62, 95)
first = [0, 20, 40, 60]
ticks = first + [period - v for v in reversed(first)]
bottom.set_xticks(ticks)
bottom.set_xticklabels([f"{v}" for v in first] + [f"-{v}" for v in reversed(first)])
bottom.set_xlabel("decades of Planck time since the start  |  (negative) decades of Planck time before the end   "
                  "[chosen axis: log time from the nearest end]")
bottom.set_ylabel("log10 energy (J)")
bottom.set_title("One cycle in detail")
bottom.legend(loc="lower center", fontsize=8, ncol=3)
fig.tight_layout()
fig.savefig("equation_wave.png", dpi=140)
print(f"axis 10^{axis:.3f} J, S_end = {s_end:.3e}, half cycle = {half:.2f} decades, today at {x_today + x0:.2f} decades")
print("Wrote equation_wave.png")
