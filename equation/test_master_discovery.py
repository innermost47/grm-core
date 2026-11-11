# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Anthony Charretier
"""Solve every network of a GRM store and compare them.

When the store comes from import_cf4.py, it holds the network without CF4 and one CF4 network per systematic level
(cf4_sys_0pct, cf4_sys_1pct...): all of them are solved, in that order, and compared in a final table
(H0, H_end, Omega_Lambda, cost, pulls on Planck's omega_c and omega_b). The level at which the pull on omega_c
drops below 3 sigma is where the network stops siding with CF4 against Planck.

    python test_master_discovery.py                        the store of settings.GRM_NETWORK_STORE_FULL_CF4
    python test_master_discovery.py data/other.json       another store
    python test_master_discovery.py --full                 the complete report of each network
    python test_master_discovery.py --only cf4_sys_1pct    one network
"""
import argparse
import math

from pygrm import GlobalRelationalNetwork
from store import list_grm_networks, load_grm_network_safely

from settings import GRM_NETWORK_STORE_FULL_CF4 as DEFAULT_STORE

KMS_MPC_TO_SI = 1e3 / 3.0856775814913673e22
WATCHED = ("wc", "wb")
LIMIT = 3.0  # sigmas


def measured_pull(values, measured, network, name):
    if name not in measured or name not in values:
        return None
    value, sigma = measured[name]
    if network.lin[network.node_to_idx[name]]:
        return (values[name] - value) / sigma
    return (math.log10(values[name]) - math.log10(value)) / sigma


def networks_to_run(path, only):
    """The networks to solve: the CF4 variants and the network they were built from, or all of them."""
    import json
    with open(path, encoding="utf-8") as f:
        store = json.load(f)
    nets = store.get("networks", [])
    if only:
        return [(n["id"], n.get("name", "")) for n in nets if n.get("id") in only]
    cf4 = sorted((n for n in nets if str(n.get("id", "")).startswith("cf4_sys_")), key=lambda n: n.get("cf4_sys", 0))
    if not cf4:
        return list_grm_networks(path)[:1]          # an ordinary store: its active network
    base = cf4[0].get("cf4_base")
    head = [(n["id"], n.get("name", "")) for n in nets if n.get("id") == base]
    return head + [(n["id"], n.get("name", "")) for n in cf4]


def run(path, network_id, full):
    data = load_grm_network_safely(path, network_id=network_id)
    network = GlobalRelationalNetwork(nodes_spec=data["nodes_spec"], relations_spec=data["relations_spec"])
    table = network.build_grm_table(data)
    v = table["resolved_values"]
    measured = {k: tuple(m) if isinstance(m, list) else (m, 1e-4) for k, m in data["measured"].items()}
    master = table.get("master_equation", {})

    if full:
        print("\n" + table.get("text_report", ""))
    else:
        lines = table.get("text_report", "").split("\n")
        if "--- LARGEST PULLS (sigmas) ---" in lines:
            k = lines.index("--- LARGEST PULLS (sigmas) ---")
            print("\n".join(lines[k:k + 6]))
    h0, hend = v["H0"] / KMS_MPC_TO_SI, v["Hend"] / KMS_MPC_TO_SI
    print(f"master invariant: {master.get('equation', 'N/A')}")
    print(f"  residual {master.get('residual', 0.0):.3e}, span {master.get('span', 0.0):.2f} decades, "
          f"merit {master.get('merit', 0.0):.2f}")
    print(f"H0 = {h0:.2f} km/s/Mpc   Hend = {hend:.2f} km/s/Mpc")

    row = {"network": network_id, "H0": h0, "Hend": hend, "OL": (hend / h0) ** 2, "cost": table["system_cost"],
           "master": master.get("equation", "")}
    for n in WATCHED:
        row[n] = measured_pull(v, measured, network, n)
    cf4 = [(n, measured_pull(v, measured, network, n)) for n in measured if n.startswith("H0_cf4")]
    row["worst_cf4"] = max(cf4, key=lambda t: abs(t[1])) if cf4 else None
    return row


def main():
    ap = argparse.ArgumentParser(description="Solve and compare the networks of a GRM store.")
    ap.add_argument("store", nargs="?", default=DEFAULT_STORE)
    ap.add_argument("--full", action="store_true", help="complete report of each network")
    ap.add_argument("--only", nargs="+", help="network ids to run")
    args = ap.parse_args()

    rows = []
    for network_id, name in networks_to_run(args.store, args.only):
        print(f"\n{'=' * 100}\n=== {network_id}: {name}\n{'=' * 100}")
        rows.append(run(args.store, network_id, args.full))

    if len(rows) < 2:
        return

    def f(x):
        return "      -" if x is None else f"{x:+7.2f}"

    print(f"\n{'=' * 100}\n=== COMPARISON\n{'=' * 100}")
    print(f"{'network':24s} {'H0':>7s} {'Hend':>7s} {'OL':>6s} {'cost':>8s} "
          + " ".join(f"{'pull ' + n:>8s}" for n in WATCHED) + "   CF4 pulled hardest")
    for r in rows:
        worst = f"{r['worst_cf4'][0]} {r['worst_cf4'][1]:+.2f}" if r["worst_cf4"] else "-"
        print(f"{r['network']:24s} {r['H0']:7.2f} {r['Hend']:7.2f} {r['OL']:6.3f} {r['cost']:8.2f} "
              + " ".join(f(r[n]) + " " for n in WATCHED) + f"  {worst}")

    # which equation came out first, and in which networks (the first place is decided by the merit index; two
    # different winners do not mean the physics changed, only which relation ranked first)
    masters = {}
    for r in rows:
        masters.setdefault(r["master"], []).append(r["network"])
    print("\nmaster invariant (first by merit):")
    for eq, nets in masters.items():
        where = "every network" if len(nets) == len(rows) else ", ".join(nets)
        print(f"  {eq}\n      in: {where}")

    cf4_rows = [r for r in rows if r["network"].startswith("cf4_sys_")]
    released = next((r for r in cf4_rows if r["wc"] is not None and abs(r["wc"]) < LIMIT), None)
    if cf4_rows:
        if released:
            print(f"omega_c comes back under {LIMIT:g} sigma from {released['network']} "
                  f"(H0 = {released['H0']:.2f} km/s/Mpc): below that floor the network sides with CF4 against Planck.")
        else:
            print(f"omega_c stays above {LIMIT:g} sigma in every CF4 network.")


if __name__ == "__main__":
    main()
