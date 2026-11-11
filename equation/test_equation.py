# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Anthony Charretier
"""Tests of the equation  S x Equant = Estock  against data, on a solved GRM network.

What the three terms are (all built from an expansion rate H):
    S      = pi / (H tP)^2       entropy of the horizon (its area over 4 lP^2), in units of kB
    Equant = hbar H / (2 pi)     energy of the Gibbons-Hawking temperature of the horizon (kB T)
    Estock = c^5 / (2 G H)       energy of the vacuum inside the horizon, rho (4 pi / 3) (c/H)^3
S x Equant = Estock then holds for ANY H: the equation cannot be tested through H alone. Each test below brings in
something measured by another route.

Test 1 - is there a final plateau H_end?
    The cycle (return at 1/(2 H_end), cycle of S tP) needs the expansion rate to settle on a constant H_end,
    i.e. a vacuum energy that never changes (w = -1). DESI DR2 measured w(a) = w0 + wa (1 - a) (CPL form).
    The future is integrated with each DESI fit: H(t) settles (w -> -1), keeps falling (w -> above -1), or blows
    up (w -> below -1, "phantom"). DESI fits the past; carrying it into the future is an assumption, so two
    versions are run: CPL as written (with wa < 0, w climbs and the dark energy fades), and w frozen at today's w0.

Test 2 (the main one) - the container IS the content
    Read with the whole content of the horizon (matter + dark energy), the equation says that what the horizon holds
    equals what the horizon is:  rho_total c^2 (4 pi / 3) (c/H)^3 = c^5 / (2 G H), which is Friedmann's equation for
    a universe without curvature, H^2 = 8 pi G rho_total / 3. Prediction: Omega_K = 0 exactly, at every instant.
    The law is added to the network as relations (nodes Otot, Econtainer, Econtent):
        Otot = Om + OL                         (sum)
        Econtainer = c^5 / (2 G H0)            energy of a black hole as large as the Hubble sphere
        Econtent = Otot x Econtainer           what the Hubble sphere holds
        Econtent = Econtainer                  the law: container = content
    and the network is solved with the DESI+CMB measurement of Omega_K, without and with the law. The pull on
    Omega_K and the change of cost say how well the data accept it.
    (The network's relation i_Estock builds Estock from the vacuum energy alone: the two readings agree only in the
    end state, when nothing but vacuum is left.)

Test 3 - Padmanabhan's holographic equipartition (arXiv 1206.4916)
    Padmanabhan: space grows as dV/dt = lP^2 c (N_sur - N_bulk), with N_sur = A / lP^2 = 4 S (degrees of freedom
    of the horizon) and N_bulk = 2 |E_Komar| / (kB T), E_Komar = |rho + 3p| V. Equilibrium N_sur = N_bulk in a
    vacuum (p = -rho, E_Komar = 2 rho V = 2 Estock) reads 4 S = 4 Estock / Equant, that is S x Equant = Estock:
    the equation is exactly the equilibrium of that law. Away from equilibrium:
        N_bulk / N_sur = |Omega_m(a) + (1 + 3 w(a)) Omega_DE(a)| / 2
    The test: does the universe go to equilibrium (ratio -> 1)? Today's ratio, and its future under each DESI fit.

Test 4 - the equation as a law at every instant: holographic dark energy (Li 2004, hep-th/0403127)
    Estock = c^5/(2 G H) is the energy of a black hole as large as the horizon (M = R c^2 / 2G, R = c/H). Li's model
    sets the dark energy inside the horizon to exactly that, rho_DE = 3 C^2 c^2 / (8 pi G L^2) with C = 1. With
    L = Hubble radius (the equation as written) the dark energy behaves like matter, w = 0, and nothing accelerates
    (Hsu); with L = future event horizon it works, and w evolves. Flat universe, matter + dark energy, N = ln a
    (review arXiv:1612.00345, eqs. 41 and 44):
        d Omega_DE / dN = Omega_DE (1 - Omega_DE) (1 + 2 sqrt(Omega_DE) / C)
        w = -1/3 - 2 sqrt(Omega_DE) / (3 C)
        H = H0 sqrt( (1 - Omega_DE0) a^-3 / (1 - Omega_DE) )
    C = 1 has no free parameter: w(a) is a prediction from Omega_DE today. C = 1 ends on a plateau (w -> -1),
    C < 1 turns phantom, C > 1 never settles. The predicted w(a) is compared with the four DESI fits, through the
    CPL pair (w0, wa) that best matches it over the range DESI measured (z = 0 to 1.5).

Sources of the numbers typed in this file (not in the network):
    DESI DR2 Results II, arXiv:2503.14738, Table V: w0waCDM fits; LCDM + Omega_K with DESI+CMB:
    1e3 Omega_K = 2.3 +- 1.1. The paper gives the preference for evolving dark energy over LCDM as 3.1 sigma
    (DESI+CMB) and 2.8 to 4.2 sigma with supernovae: those significances are quoted, not recomputed here (the
    w0-wa covariance is not in this file).

    python test_equation.py                                   network of settings (active one)
    python test_equation.py --hde-c 1 0.8 1.2                 values of C tried in test 4 (default 0.8 1 1.2)
    python test_equation.py data/grm_network_cf4.json --network cf4_sys_3pct
    python test_equation.py --save data/grm_network_cf4_container.json      also writes a copy of the store with
                                                                           the container law in every network
Writes test_equation.png (the futures of H and of the equipartition ratio) and test_equation_hde.png (test 4).
"""
import argparse
import math

import numpy as np

from pygrm import GlobalRelationalNetwork
from store import load_grm_network_safely

from settings import GRM_NETWORK_STORE_FULL_CF4 as DEFAULT_STORE

KMS_MPC_TO_SI = 1e3 / 3.0856775814913673e22
GYR = 3.15576e16  # seconds

# DESI DR2 Results II (arXiv:2503.14738), Table V, w0waCDM: (w0, sigma), (wa, sigma minus, sigma plus)
DESI_W0WA = {
    "DESI+CMB": ((-0.42, 0.21), (-1.75, 0.58, 0.58)),
    "DESI+CMB+Pantheon+": ((-0.838, 0.055), (-0.62, 0.19, 0.22)),
    "DESI+CMB+Union3": ((-0.667, 0.088), (-1.09, 0.27, 0.31)),
    "DESI+CMB+DESY5": ((-0.752, 0.057), (-0.86, 0.20, 0.23)),
}
DESI_OMEGA_K = (2.3e-3, 1.1e-3)  # DESI+CMB, LCDM + Omega_K
FUTURE_GYR = (10, 50, 100)


CONTAINER_SIGMA = 1e-7  # tolerance of the container law (an identity, like the network's other relations)


def container_law(nodes, values):
    """Nodes and relations of the law  container = content  (see test 2), with starting values taken from values."""
    c, G, h0 = values["c"], values["G"], values["H0"]
    otot = values["Om"] + values["OL"]
    econtainer = c ** 5 / (2 * G * h0)
    new_nodes = {
        "Otot": {"guess": otot, "solved": otot, "scale": "log", "fixed": False, "dim": [0, 0, 0, 0, 0]},
        "Econtainer": {"guess": econtainer, "solved": econtainer, "scale": "log", "fixed": False,
                       "dim": [1, 2, -2, 0, 0]},
        "Econtent": {"guess": otot * econtainer, "solved": otot * econtainer, "scale": "log", "fixed": False,
                     "dim": [1, 2, -2, 0, 0]},
    }
    relations = [
        {"name": "i_Otot", "type": "sum", "terms": {"Otot": 1, "Om": -1, "OL": -1}, "K": 0.0,
         "sigma": CONTAINER_SIGMA},
        {"name": "i_Econtainer", "terms": {"Econtainer": 1, "c": -5, "G": 1, "H0": 1}, "rhs": -math.log10(2),
         "sigma": CONTAINER_SIGMA},
        {"name": "i_Econtent", "terms": {"Econtent": 1, "Otot": -1, "Econtainer": -1}, "rhs": 0.0,
         "sigma": CONTAINER_SIGMA},
        {"name": "z_container_is_content", "terms": {"Econtent": 1, "Econtainer": -1}, "rhs": 0.0,
         "sigma": CONTAINER_SIGMA},
    ]
    missing = [n for n in ("c", "G", "H0", "Om", "OL") if n not in nodes]
    if missing:
        raise KeyError(f"the container law needs the nodes {missing}")
    return new_nodes, relations


def load(store, network_id):
    data = load_grm_network_safely(store, network_id=network_id)
    measured = {k: tuple(m) if isinstance(m, list) else (m, 1e-4) for k, m in data["measured"].items()}
    return data, measured


def solve(data, measured, law=False, extra_measured=None):
    """Solve a copy of the network; law=True adds the container law. Returns (values, cost, measured used)."""
    import copy
    nodes = copy.deepcopy(data["nodes_spec"])
    rels = copy.deepcopy(data["relations_spec"])
    m = dict(measured)
    m.update(extra_measured or {})
    if law:
        values = {n: spec.get("solved", spec.get("guess")) for n, spec in nodes.items()}
        new_nodes, new_rels = container_law(nodes, values)
        nodes.update(new_nodes)
        rels += new_rels
    net = GlobalRelationalNetwork(nodes, rels)
    sol = net.solve(measured_dict=m, compute_uncertainty=False)
    return sol["values"], sol["cost"], m


def save_with_law(store, out):
    """A copy of the store with the container law added to every network that has the nodes it needs."""
    import json
    import os
    if os.path.abspath(out) == os.path.abspath(store):
        raise SystemExit("--save: choose another file than the input store")
    with open(store, encoding="utf-8") as f:
        data = json.load(f)
    done = []
    for net in data.get("networks", []):
        nodes = net.get("nodes", {})
        if any(n not in nodes for n in ("c", "G", "H0", "Om", "OL")):
            continue
        values = {n: spec.get("solved", spec.get("value", spec.get("guess"))) for n, spec in nodes.items()}
        new_nodes, new_rels = container_law(nodes, values)
        nodes.update(new_nodes)
        rels = net.setdefault("customRelations", [])
        names = {r["name"] for r in new_rels}
        rels[:] = [r for r in rels if r.get("name") not in names] + new_rels
        done.append(net.get("id"))
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    print(f"\nWrote {out}: container law added to {len(done)} networks ({', '.join(map(str, done))}); {store} untouched")


def w_of(a, w0, wa, frozen):
    """Equation of state: CPL w0 + wa (1 - a); with frozen=True it stays at today's w0 in the future (a > 1)."""
    return w0 if (frozen and a > 1) else w0 + wa * (1 - a)


def de_density(a, w0, wa, frozen):
    """Dark energy density over today's for that equation of state."""
    if frozen and a > 1:
        return a ** (-3 * (1 + w0))
    return a ** (-3 * (1 + w0 + wa)) * math.exp(-3 * wa * (1 - a))


def future(h0, om, ode, ok, w0, wa, frozen, t_max_gyr=120.0, dn=2e-4, n_max=40.0):
    """Integrate the expansion forward from today (a = 1), in N = ln a.
    Returns time since today (Gyr), H (s^-1), equipartition ratio N_bulk/N_sur, and how the run ended."""
    t, n, rows = 0.0, 0.0, []
    end = "reached the end of the window"
    while n <= n_max:
        a = math.exp(n)
        de = ode * de_density(a, w0, wa, frozen)
        m, k = om * a ** -3, ok * a ** -2
        e2 = m + k + de
        if not e2 > 0:
            end = "the expansion stops (H^2 <= 0)"
            break
        h = h0 * math.sqrt(e2)
        w = w_of(a, w0, wa, frozen)
        ratio = abs(m + (1 + 3 * w) * de) / e2 / 2
        rows.append((t / GYR, h, ratio))
        if h > 1e6 * h0:
            end = "big rip: H runs away"
            break
        if t / GYR > t_max_gyr:
            break
        # trapezoid on dt = dN / H
        a2 = math.exp(n + dn)
        e2b = om * a2 ** -3 + ok * a2 ** -2 + ode * de_density(a2, w0, wa, frozen)
        if not e2b > 0:
            end = "the expansion stops (H^2 <= 0)"
            break
        t += dn * 0.5 * (1 / h + 1 / (h0 * math.sqrt(e2b)))
        n += dn
    arr = np.array(rows)
    return arr[:, 0], arr[:, 1], arr[:, 2], end


def hde(c_li, ode0, h0, a_min=0.25, t_max_gyr=120.0, dn=1e-3):
    """Holographic dark energy with the future event horizon. Returns the past (a, w) from a_min to 1 and the
    future (time from today in Gyr, H, w, equipartition ratio) up to t_max_gyr."""
    def deriv(o):
        o = min(max(o, 0.0), 1.0)
        return o * (1 - o) * (1 + 2 * math.sqrt(o) / c_li)

    def rk4(o, h):
        k1 = deriv(o)
        k2 = deriv(o + 0.5 * h * k1)
        k3 = deriv(o + 0.5 * h * k2)
        k4 = deriv(o + h * k3)
        return o + h * (k1 + 2 * k2 + 2 * k3 + k4) / 6

    def w_of_o(o):
        return -1 / 3 - 2 * math.sqrt(max(o, 0.0)) / (3 * c_li)

    om0 = 1 - ode0                        # flat, so that H(a=1) = H0 exactly

    def hubble(n, o):
        return h0 * math.sqrt(om0 * math.exp(-3 * n) / max(1 - o, 1e-300))

    past, o, n = [(1.0, w_of_o(ode0))], ode0, 0.0
    while math.exp(n) > a_min:
        o, n = rk4(o, -dn), n - dn
        past.append((math.exp(n), w_of_o(o)))
    past.reverse()

    fut, o, n, t = [], ode0, 0.0, 0.0
    while t / GYR <= t_max_gyr:
        h, w = hubble(n, o), w_of_o(o)
        fut.append((t / GYR, h, w, abs((1 - o) + (1 + 3 * w) * o) / 2))
        if 1 - o < 1e-12 or h > 1e6 * h0:
            break
        o2 = rk4(o, dn)
        t += dn * 0.5 * (1 / h + 1 / hubble(n + dn, o2))
        o, n = o2, n + dn
    return np.array(past), np.array(fut)


def cpl_fit(past, a_min=0.4):
    """CPL pair (w0, wa) closest (least squares) to w(a) over a_min <= a <= 1 (z = 0 to 1.5 for a_min = 0.4)."""
    keep = past[:, 0] >= a_min
    a, w = past[keep, 0], past[keep, 1]
    design = np.vstack([np.ones_like(a), 1 - a]).T
    (w0, wa), *_ = np.linalg.lstsq(design, w, rcond=None)
    return float(w0), float(wa), float(np.max(np.abs(design @ [w0, wa] - w)))


def at_time(ts, ys, t):
    return float(np.interp(t, ts, ys)) if t <= ts[-1] else None


def main():
    ap = argparse.ArgumentParser(description="Three tests of S x Equant = Estock against data.")
    ap.add_argument("store", nargs="?", default=DEFAULT_STORE)
    ap.add_argument("--network", default=None, help="network id (default: the active one)")
    ap.add_argument("--save", default=None, help="also write a copy of the store with the container law added")
    ap.add_argument("--hde-c", type=float, nargs="+", default=[0.8, 1.0, 1.2],
                    help="values of Li's constant C tried in test 4 (C = 1: no free parameter)")
    args = ap.parse_args()

    data, measured = load(args.store, args.network)
    v, cost_net, _ = solve(data, measured)
    c, G, hbar = v["c"], v["G"], v["hbar"]
    tp = math.sqrt(hbar * G / c ** 5)
    h0, hend, om, ol = v["H0"], v["Hend"], v["Om"], v["OL"]
    ok = v.get("OK", 1 - om - ol)
    print(f"\nnetwork: H0 = {h0 / KMS_MPC_TO_SI:.2f} km/s/Mpc, H_end = {hend / KMS_MPC_TO_SI:.2f} km/s/Mpc, "
          f"Om = {om:.4f}, OL = {ol:.4f}, OK = {ok:.2e}")

    def terms(h):
        return math.pi / (h * tp) ** 2, hbar * h / (2 * math.pi), c ** 5 / (2 * G * h)

    s, eq, es = terms(hend)
    print(f"S = {s:.4e}   Equant = {eq:.4e} J   Estock = {es:.4e} J   S x Equant / Estock = {s * eq / es:.12f}")
    print("(this ratio is 1 for any H: the tests below bring in something measured by another route)")

    # ------------------------------------------------------------------ test 1
    print("\n" + "=" * 100 + "\nTEST 1 - is there a final plateau H_end?  (dark energy w(a) = w0 + wa (1 - a))\n" + "=" * 100)
    if "w0" in measured:
        print(f"note: the network holds a measured w0 = {measured['w0'][0]:g} +- {measured['w0'][1]:g}, but no relation "
              "ties it to H_end (it does not take part in the solve)")
    print("DESI fits the past (a <= 1). Two ways to carry it into the future, both assumptions:")
    print("  CPL     w = w0 + wa (1 - a) as written: with wa < 0, w climbs without limit and the dark energy fades away")
    print("  frozen  w stays at today's value w0 from now on")
    models = {"LCDM (w = -1)": (-1.0, 0.0, False)}
    for k, w in DESI_W0WA.items():
        models[k + " CPL"] = (w[0][0], w[1][0], False)
        models[k + " frozen"] = (w[0][0], w[1][0], True)
    runs = {}
    print(f"\n{'model':30s} {'w0':>7s} {'wa':>6s}   "
          + "   ".join(f"H/H_end +{t:g} Gyr" for t in FUTURE_GYR) + "   fate")
    for name, (w0, wa, frozen) in models.items():
        ts, hs, ratios, end = future(h0, om, ol, ok, w0, wa, frozen)
        runs[name] = (ts, hs, ratios, end)
        cells = []
        for t in FUTURE_GYR:
            x = at_time(ts, hs, t)
            cells.append(f"{x / hend:>15.4g}" if x is not None else f"{'-':>15s}")
        last = hs[ts <= 100][-1] / hend
        if "rip" in end:
            fate = f"H runs away ({end})"
        elif abs(last - 1) < 0.01:
            fate = "settles on H_end"
        elif last < 1:
            fate = f"no plateau: H falls below H_end ({last:.3g} at +100 Gyr)"
        else:
            fate = f"no plateau: H above H_end ({last:.3g} at +100 Gyr)"
        print(f"{name:30s} {w0:7.3f} {wa:6.2f}   " + "   ".join(cells) + f"   {fate}")
    print("\nDESI DR2 prefers evolving dark energy over LCDM at 3.1 sigma (DESI+CMB) and 2.8 to 4.2 sigma with supernovae "
          "(quoted from the paper).")
    print("DESI measured the past only. IF today's trend (w0 above -1) went on, the vacuum energy would thin out and H")
    print("would keep falling; but nothing measured says it goes on. The plateau H_end needs w = -1 in the end.")
    print(f"LCDM with this network: return at 1/(2 H_end) = {1 / (2 * hend) / GYR:.2f} Gyr, "
          f"cycle S tP = {s * tp / GYR * 1e9:.3e} years")

    # ------------------------------------------------------------------ test 2
    print("\n" + "=" * 100 + "\nTEST 2 (the main one) - the container IS the content: Econtent = Econtainer, i.e. "
          "Omega_K = 0\n" + "=" * 100)
    es0 = terms(h0)[2]
    print(f"Econtainer = c^5/(2 G H0) = {es0:.4e} J  (a black hole as large as the Hubble sphere)")
    print(f"Econtent   = (Om + OL) x Econtainer = {(om + ol) * es0:.4e} J  ->  content / container = {om + ol:.6f} "
          f"in the network as it is (OK = {ok:.2e})")
    k, sk = DESI_OMEGA_K
    desi = {"OK": (k, sk)}
    own = measured.get("OK")
    print(f"\nmeasurements of Omega_K:  network's own {own[0]:g} +- {own[1]:g}" if own else "\nno Omega_K in the network",
          end="")
    print(f"   DESI+CMB {k:g} +- {sk:g}")
    print(f"\n{'network solved':42s} {'cost':>9s} {'OK':>10s} {'pull on OK':>11s} {'H0':>7s}")
    rows = [("as it is", False, None), ("+ container law", True, None),
            ("with DESI+CMB Omega_K", False, desi), ("with DESI+CMB Omega_K + container law", True, desi)]
    costs = {}
    for label, law, extra in rows:
        vals, cost, m = solve(data, measured, law=law, extra_measured=extra)
        target = m.get("OK")
        pull = (vals["OK"] - target[0]) / target[1] if target else float("nan")
        costs[label] = cost
        print(f"{label:42s} {cost:9.3f} {vals['OK']:10.2e} {pull:+11.2f} {vals['H0'] / KMS_MPC_TO_SI:7.2f}")
    d_own = costs["+ container law"] - costs["as it is"]
    d_desi = costs["with DESI+CMB Omega_K + container law"] - costs["with DESI+CMB Omega_K"]
    print(f"\ncost of imposing container = content: +{d_own:.2f} with the network's Omega_K, "
          f"+{d_desi:.2f} with DESI+CMB's")
    print(f"(a cost increase of 1 is a 1 sigma tension, 4 is 2 sigma, 9 is 3 sigma: here {math.sqrt(max(d_desi, 0)):.1f} "
          "sigma with DESI+CMB)")
    print("The law predicts Omega_K = 0 for ever: the coming measurements (Euclid, later DESI releases) decide whether the")
    print("small DESI+CMB offset grows (against the law) or fades (for it).")
    if args.save:
        save_with_law(args.store, args.save)

    # ------------------------------------------------------------------ test 3
    print("\n" + "=" * 100 + "\nTEST 3 - Padmanabhan's holographic equipartition: N_bulk / N_sur (1 = equilibrium = "
          "S x Equant = Estock)\n" + "=" * 100)
    n_sur = 4 * terms(h0)[0]
    e_komar = abs(om - 2 * ol) * es0
    print(f"today: N_sur = 4 S(H0) = {n_sur:.4e}   N_bulk = 2 E_Komar / kT = {2 * e_komar / terms(h0)[1]:.4e}   "
          f"ratio = {abs(om - 2 * ol) / 2:.4f}")
    print(f"\n{'model':30s} " + "   ".join(f"ratio +{t:g} Gyr" for t in FUTURE_GYR))
    for name in models:
        ts, hs, ratios, end = runs[name]
        cells = []
        for t in FUTURE_GYR:
            x = at_time(ts, ratios, t)
            cells.append(f"{x:>14.4f}" if x is not None else f"{'-':>14s}")
        print(f"{name:30s} " + "   ".join(cells))
    print("\nOnly a vacuum with w = -1 reaches equilibrium (ratio 1), and only there does S x Equant = Estock describe")
    print("the end state. With w frozen above -1 the ratio settles below 1 (|1 + 3 w0| / 2); with CPL it swings above")
    print("and below 1 as w climbs and the dark energy fades. In neither case does it settle on 1.")

    # ------------------------------------------------------------------ test 4
    print("\n" + "=" * 100 + "\nTEST 4 - the equation at every instant, on the future event horizon: holographic dark "
          "energy (Li 2004)\n" + "=" * 100)
    print(f"Estock = c^5/(2 G H) = energy of a black hole of radius c/H: check {c ** 4 / (2 * G) * (c / hend):.4e} J "
          f"= Estock {es:.4e} J")
    print(f"Omega_DE today = network OL = {ol:.4f};  CPL pair fitted to w(a) over z = 0 to 1.5 (a = 0.4 to 1)\n")
    print(f"{'model':32s} {'w today':>8s} {'w at z=1.5':>10s} {'CPL w0':>7s} {'CPL wa':>7s} {'fit err':>7s}   "
          f"{'H/H_end +100 Gyr':>16s} {'ratio +100 Gyr':>14s}   end")
    hde_runs = {}
    for c_li in args.hde_c:
        past, fut = hde(c_li, ol, h0)
        w0f, waf, err = cpl_fit(past)
        hde_runs[c_li] = (past, fut, w0f, waf)
        w15 = float(np.interp(0.4, past[:, 0], past[:, 1]))
        last_h = fut[-1, 1] / hend
        end = ("plateau (w -> -1)" if abs(c_li - 1) < 1e-9 else
               "phantom: H grows again" if c_li < 1 else "w stays above -1: no plateau")
        label = f"HDE C = {c_li:g}" + ("  (no free parameter)" if abs(c_li - 1) < 1e-9 else "")
        print(f"{label:32s} {fut[0, 2]:8.3f} {w15:10.3f} {w0f:7.3f} {waf:7.3f} {err:7.3f}   {last_h:16.4g} "
              f"{fut[-1, 3]:14.4f}   {end}")

    print("\ncompared with the DESI DR2 fits (each parameter on its own: the w0-wa correlation is not in this file, so")
    print("these distances are indicative only):")
    print(f"{'DESI fit':22s} {'w0':>14s} {'wa':>16s}   " + "   ".join(f"C={c_li:g}: w0, wa (sigma)" for c_li in args.hde_c))
    for name, ((w0d, s0), (wad, sm, sp)) in DESI_W0WA.items():
        cells = []
        for c_li in args.hde_c:
            _, _, w0f, waf = hde_runs[c_li]
            d0 = (w0f - w0d) / s0
            da = (waf - wad) / (sp if waf > wad else sm)
            cells.append(f"{d0:+8.1f}, {da:+5.1f}      ")
        print(f"{name:22s} {w0d:7.3f}+-{s0:<5.3f} {wad:7.2f}-{sm:.2f}+{sp:.2f}   " + "   ".join(cells))
    print("\nThe sign of wa tells the story: DESI finds wa < 0 (w was lower in the past, below -1); holographic dark")
    print("energy has w higher in the past (towards -1/3), i.e. wa > 0, for every C tried.")

    # ------------------------------------------------------------------ picture
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.5))
        for name, (ts, hs, ratios, end) in runs.items():
            keep = ts <= 100
            style = dict(lw=2.2, color="black") if name.startswith("LCDM") else dict(lw=1.2, ls="--" if "CPL" in name else "-")
            ax1.plot(ts[keep], hs[keep] / hend, label=name, **style)
            ax2.plot(ts[keep], ratios[keep], label=name, **style)
        ax1.axhline(1, color="grey", lw=0.8, ls=":")
        ax1.set_yscale("log")
        ax1.set_xlabel("time from today (Gyr)")
        ax1.set_ylabel("H / H_end (network)")
        ax1.set_title("Test 1: does H settle on H_end?")
        ax2.axhline(1, color="grey", lw=0.8, ls=":")
        ax2.set_xlabel("time from today (Gyr)")
        ax2.set_ylabel("N_bulk / N_sur")
        ax2.set_title("Test 3: holographic equipartition (1 = equation holds as equilibrium)")
        ax1.legend(fontsize=7)
        fig.tight_layout()
        fig.savefig("test_equation.png", dpi=140)
        print("\nWrote test_equation.png")

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.5))
        a = np.linspace(0.4, 1, 200)
        z = 1 / a - 1
        for name, ((w0d, _), (wad, _, _)) in DESI_W0WA.items():
            ax1.plot(z, w0d + wad * (1 - a), ls="--", lw=1.2, label=name)
        ax1.axhline(-1, color="black", lw=2, label="LCDM (w = -1)")
        hde_colors = ["#7c3aed", "#b45309", "#db2777", "#0d9488", "#4b5563"]
        for k, (c_li, (past, fut, _, _)) in enumerate(hde_runs.items()):
            keep = past[:, 0] >= 0.4
            col = hde_colors[k % len(hde_colors)]
            ax1.plot(1 / past[keep, 0] - 1, past[keep, 1], lw=2.2, color=col, label=f"HDE C = {c_li:g}")
            ax2.plot(fut[:, 0], fut[:, 1] / hend, lw=2, color=col, label=f"HDE C = {c_li:g}")
        lcdm = runs["LCDM (w = -1)"]
        ax2.plot(lcdm[0][lcdm[0] <= 120], lcdm[1][lcdm[0] <= 120] / hend, color="black", lw=2, label="LCDM")
        ax1.set_xlabel("redshift z (the range DESI measured)")
        ax1.set_ylabel("w")
        ax1.set_title("Test 4: w(z), holographic dark energy vs DESI fits")
        ax1.legend(fontsize=7)
        ax2.axhline(1, color="grey", lw=0.8, ls=":")
        ax2.set_yscale("log")
        ax2.set_xlabel("time from today (Gyr)")
        ax2.set_ylabel("H / H_end (network)")
        ax2.set_title("Test 4: future of H (plateau or not)")
        ax2.legend(fontsize=7)
        fig.tight_layout()
        fig.savefig("test_equation_hde.png", dpi=140)
        print("Wrote test_equation_hde.png")
    except ImportError:
        print("\nmatplotlib not installed: no picture")


if __name__ == "__main__":
    main()
