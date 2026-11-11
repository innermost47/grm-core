# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Anthony Charretier
"""What S x Equant = Estock looks like as a graph.

    S      = pi / (H tP)^2     Equant = hbar H / (2 pi)     Estock = c^5 / (2 G H)
In log10 the three are straight lines in log10(H) (slopes -2, +1, -1), so the equation is a straight line in the
space (log S, log Equant, log Estock): one degree of freedom, H. The line starts where S = 1 (one Planck cell):
there Equant = Estock = E_P / (2 sqrt(pi)), the quantum and the content are the same energy. Below S = 1 the
quantum would exceed the content. Today and the plateau H_end are marked on it.
Against time, H(t) = H_end coth(1.5 H_end t) (flat universe, matter + vacuum; radiation and anything before it left
out), so the same three quantities bend into the tanh of the plateau.

    python equation_graph.py                   values of H0 and H_end from the network of settings
    python equation_graph.py --h0 67.4 --hend 56.6     (km/s/Mpc) without the network
Writes equation_graph.png.
"""
import argparse
import math

import numpy as np

C, G, HBAR = 299792458.0, 6.67430e-11, 1.054571817e-34
TP = math.sqrt(HBAR * G / C ** 5)
EP = HBAR / TP
KMS_MPC_TO_SI = 1e3 / 3.0856775814913673e22
GYR = 3.15576e16


def terms(h):
    return math.pi / (h * TP) ** 2, HBAR * h / (2 * math.pi), C ** 5 / (2 * G * h)


def network_rates():
    from pygrm import GlobalRelationalNetwork
    from store import load_grm_network_safely
    try:
        from settings import GRM_NETWORK_STORE_JSON_ENRICHED as store
    except ImportError:
        from settings import GRM_NETWORK_STORE_JSON as store
    data = load_grm_network_safely(store)
    net = GlobalRelationalNetwork(data["nodes_spec"], data["relations_spec"])
    m = {k: tuple(v) if isinstance(v, list) else (v, 1e-4) for k, v in data["measured"].items()}
    v = net.solve(measured_dict=m, compute_uncertainty=False)["values"]
    return v["H0"], v["Hend"]


def main():
    ap = argparse.ArgumentParser(description="Graph of S x Equant = Estock.")
    ap.add_argument("--h0", type=float, help="H0 in km/s/Mpc (default: from the network)")
    ap.add_argument("--hend", type=float, help="H_end in km/s/Mpc (default: from the network)")
    args = ap.parse_args()
    if args.h0 and args.hend:
        h0, hend = args.h0 * KMS_MPC_TO_SI, args.hend * KMS_MPC_TO_SI
    else:
        h0, hend = network_rates()

    h_zero = math.sqrt(math.pi) / TP                      # S = 1
    s0, q0, e0 = terms(h_zero)
    print(f"point zero (S = 1): H = {h_zero:.4e} s^-1, Equant = Estock = {q0:.4e} J = E_P / (2 sqrt(pi)) = "
          f"{EP / (2 * math.sqrt(math.pi)):.4e} J")
    for label, h in (("today", h0), ("plateau", hend)):
        s, q, e = terms(h)
        print(f"{label:8s}: S = {s:.3e}, Equant = {q:.3e} J, Estock = {e:.3e} J, S x Equant / Estock = {s * q / e:.12f}")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    lh = np.linspace(math.log10(hend), math.log10(h_zero), 400)
    hs = 10 ** lh
    ls = np.log10(math.pi / (hs * TP) ** 2)
    lq = np.log10(HBAR * hs / (2 * math.pi))
    le = np.log10(C ** 5 / (2 * G * hs))

    fig = plt.figure(figsize=(16, 5.2))
    marks = [("point zero (S = 1)", h_zero, "#dc2626"), ("today", h0, "#2563eb"), ("plateau H_end", hend, "#111827")]

    ax = fig.add_subplot(1, 3, 1, projection="3d")
    ax.plot(ls, lq, le, color="#7c3aed", lw=2.5)
    for label, h, col in marks:
        s, q, e = terms(h)
        ax.scatter([math.log10(s)], [math.log10(q)], [math.log10(e)], color=col, s=40, label=label)
    ax.set_xlabel("log10 S")
    ax.set_ylabel("log10 Equant (J)")
    ax.set_zlabel("log10 Estock (J)")
    ax.set_title("The equation is a straight line\n(direction -2 : +1 : -1 per decade of H)")
    ax.legend(fontsize=7, loc="upper left")

    ax = fig.add_subplot(1, 3, 2)
    ax.plot(lh, ls, label="log10 S  (slope -2)", lw=2)
    ax.plot(lh, lq, label="log10 Equant  (slope +1)", lw=2)
    ax.plot(lh, le, label="log10 Estock  (slope -1)", lw=2)
    ax.plot(lh, ls + lq, ls=":", color="black", lw=2, label="log10 S + log10 Equant (on Estock)")
    for label, h, col in marks:
        ax.axvline(math.log10(h), color=col, lw=0.8, ls="--")
    ax.invert_xaxis()
    ax.set_xlabel("log10 H (s^-1)   <- from point zero to the plateau")
    ax.set_ylabel("decades")
    ax.set_title("Against H: three straight lines")
    ax.legend(fontsize=7)

    ax = fig.add_subplot(1, 3, 3)
    t = np.logspace(math.log10(TP), math.log10(200 * GYR), 600)
    h_t = hend / np.tanh(1.5 * hend * t)
    for name, vals in (("log10 S", np.log10(math.pi / (h_t * TP) ** 2)),
                       ("log10 Equant", np.log10(HBAR * h_t / (2 * math.pi))),
                       ("log10 Estock", np.log10(C ** 5 / (2 * G * h_t)))):
        ax.plot(np.log10(t / GYR), vals, lw=2, label=name)
    t0 = math.atanh(hend / h0) / (1.5 * hend)
    ax.axvline(math.log10(t0 / GYR), color="#2563eb", lw=0.8, ls="--", label=f"today ({t0 / GYR:.1f} Gyr)")
    ax.set_xlabel("log10 time since the start (Gyr)")
    ax.set_ylabel("decades")
    ax.set_title("Against time: the same line bends into the plateau\nH(t) = H_end coth(1.5 H_end t)")
    ax.legend(fontsize=7)

    fig.tight_layout()
    fig.savefig("equation_graph.png", dpi=140)
    print("Wrote equation_graph.png")


if __name__ == "__main__":
    main()
