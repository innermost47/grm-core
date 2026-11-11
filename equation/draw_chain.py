# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Anthony Charretier
"""Draw the 7-relation chain behind S x Equant = Estock.

Left: the relation diagram (0 -> 1 -> 2A / 2B -> 3).
Right: each quantity placed in 3D by its exponents of hbar (x), G (y) and H (z), the factors c, kB and pure
numbers left out. In those coordinates a product is a vector sum, so S x Equant = Estock is a closed triangle:
S + Equant = Estock. The Planck step (lP^2 = hbar G / c^3) is the point (1/2, 1/2, 0).
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# exponents of (hbar, G, H) of each quantity, read from the relations
NODES = {
    "lP  (0)": (0.5, 0.5, 0.0),
    "H_end  (1)": (0.0, 0.0, 1.0),
    "rho_vacuum  (2A)": (0.0, -1.0, 2.0),
    "Estock  (2A)": (0.0, -1.0, -1.0),
    "T_floor  (2B)": (1.0, 0.0, 1.0),
    "Equant  (2B)": (1.0, 0.0, 1.0),
    "S  (3)": (-1.0, -1.0, -2.0),
}
EDGES = [("lP  (0)", "S  (3)"), ("H_end  (1)", "S  (3)"), ("H_end  (1)", "rho_vacuum  (2A)"),
         ("rho_vacuum  (2A)", "Estock  (2A)"), ("H_end  (1)", "Estock  (2A)"), ("H_end  (1)", "T_floor  (2B)"),
         ("T_floor  (2B)", "Equant  (2B)")]
COL = {"0": "#6b7280", "1": "#2563eb", "2A": "#dc2626", "2B": "#059669", "3": "#7c3aed"}


def stage(name):
    return name.split("(")[1].rstrip(")")


fig = plt.figure(figsize=(16, 7))

# ---------------------------------------------------------------- relation diagram
ax = fig.add_subplot(1, 2, 1)
pos = {"0": (0, 2), "1": (1.4, 2), "2A": (2.9, 3.1), "2B": (2.9, 0.9)}
labels = {"0": "0\nPlanck\nlP", "1": "1\nbubble\nH_end", "2A": "2A  gravity\nrho_vacuum -> Estock",
          "2B": "2B  quantum\nT_floor -> Equant"}
links = [("0", "1", "i_lP"), ("1", "2A", "i_Hend, i_rhoL\ni_Estock"), ("1", "2B", "i_Tfloor\ni_Equant")]
for a, b, lab in links:
    (x1, y1), (x2, y2) = pos[a], pos[b]
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="-", lw=2, color="#9ca3af", shrinkA=28, shrinkB=28))
    if lab:
        ax.text((x1 + x2) / 2, (y1 + y2) / 2 + 0.12, lab, ha="center", fontsize=8, color="#374151")
ax.annotate("", xy=pos["2B"], xytext=pos["2A"],
            arrowprops=dict(arrowstyle="<->", lw=2.5, color="#7c3aed", shrinkA=30, shrinkB=30))
ax.text(3.1, 2.0, "3 = the relation between 2A and 2B:\nS  (i_S, built from 0 and 1)\n\nS x Equant = Estock", color="#7c3aed",
        fontsize=10, va="center")
for k, (x, y) in pos.items():
    ax.scatter([x], [y], s=1800, color=COL[k], alpha=0.15, edgecolor=COL[k], lw=2)
    ax.text(x, y, labels[k], ha="center", va="center", fontsize=8.5, color="#111827")
ax.set_xlim(-0.6, 4.9)
ax.set_ylim(0.0, 4.0)
ax.axis("off")
ax.set_title("The chain the GRM took: 4 nodes, the 3 is a relation (7 relations of the network)")

# ---------------------------------------------------------------- 3D exponents
ax = fig.add_subplot(1, 2, 2, projection="3d")
for a, b in EDGES:
    p, q = np.array(NODES[a]), np.array(NODES[b])
    ax.plot(*zip(p, q), color="#d1d5db", lw=1.2)
o = np.zeros(3)
s, e, st = (np.array(NODES[k]) for k in ("S  (3)", "Equant  (2B)", "Estock  (2A)"))
ax.plot(*zip(o, s), color=COL["3"], lw=3)
ax.plot(*zip(s, s + e), color=COL["2B"], lw=3)
ax.plot(*zip(o, st), color=COL["2A"], lw=3, ls="--")
ax.text(*(s / 2), "  S", color=COL["3"])
ax.text(*(s + e / 2), "  + Equant", color=COL["2B"])
ax.text(*(st / 2), "  = Estock", color=COL["2A"])
ax.scatter([0], [0], [0], color="black", s=30)
ax.text(0, 0, 0, "  0", fontsize=9)
seen = {}
for name, p in NODES.items():
    key = tuple(p)
    seen.setdefault(key, []).append(name)
for key, names in seen.items():
    ax.scatter(*key, color=COL[stage(names[0])], s=60)
    ax.text(*key, "  " + " / ".join(n.split("  ")[0] for n in names), fontsize=8)
ax.set_xlabel("power of hbar")
ax.set_ylabel("power of G")
ax.set_zlabel("power of H")
ax.set_title("Each quantity by its powers of hbar, G, H\n(products become sums: the equation is a closed triangle)")
ax.view_init(elev=18, azim=-58)
fig.tight_layout()
fig.savefig("draw_chain.png", dpi=150)
print("Wrote draw_chain.png")
