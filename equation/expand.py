# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Anthony Charretier
"""Expand a GRM network where it is in tension, analyse what was added, find its unifying equation, export it.

1. Solve with the measurements; where relations stay in tension, auto_expand adds hidden nodes (a missing factor
   or term inside the tense relation), several passes until nothing is tense any more.
2. Solve again and analyse every hidden node: its value, whether it is really needed (sigmas from "nothing
   missing"), and what it could be (a simple number, or powers of existing nodes of the same dimension), with the
   number of matches chance alone would give.
3. Bridges: mine_bridges is run as a report only. Its hits are compared with its chance level and are NOT added
   as relations (a coincidence added as a relation would force the network).
4. The master invariant of the expanded network (with the unifying equations it implies).
5. Export to the store format: hidden nodes keep their prior, the measurements are kept, relations that cannot
   be written to JSON (functions) are left out with a warning.
"""
import json
import os

from pygrm import GlobalRelationalNetwork
import settings
from settings import GRM_NETWORK_STORE_JSON
from store import load_grm_network_safely

TENSION_SIGMAS = 3.0       # a relation is tense above this pull
EXPAND_PASSES = 5
ADDITIONS_PER_PASS = 5
OUTPUT = settings.GRM_NETWORK_STORE_JSON_ENRICHED


def jsonable(value):
    try:
        json.dumps(value)
        return True
    except (TypeError, ValueError):
        return False


def export_enriched_network(grm, measured, output_filepath, original_filepath):
    """Writes the expanded network into the store file format, as the active network."""
    if os.path.exists(original_filepath):
        with open(original_filepath, "r", encoding="utf-8") as f:
            base_data = json.load(f)
    else:
        base_data = {"activeId": "enriched_network", "networks": []}

    nodes_export = {}
    for name, spec in grm.nodes_specs.items():
        node = {
            "guess": spec.get("guess", 1.0),
            "solved": spec.get("solved", spec.get("guess", 1.0)),
            "scale": spec.get("scale", "log"),
            "fixed": spec.get("fixed", False),
            "dim": spec.get("dim", [0, 0, 0, 0, 0]),
        }
        for key in ("min", "max", "constant", "hidden_for", "hidden_prior", "sigma_dex"):
            if key in spec:
                node[key] = spec[key]
        nodes_export[name] = node

    relations, skipped = [], []
    for rel in grm.relations_spec:
        if all(jsonable(v) for v in rel.values()):
            relations.append(rel)
        else:
            skipped.append(rel.get("name", "?"))
    if skipped:
        print(f"[WARN] relations with functions cannot be written to JSON and were left out: {', '.join(skipped)}")

    payload = {
        "id": "enriched_grm_network",
        "name": "Enriched GRM Network (expanded where in tension)",
        "nodes": nodes_export,
        "relations": [],
        "customRelations": relations,
        "measured": {k: list(v) if isinstance(v, tuple) else v for k, v in measured.items()},
    }
    base_data["activeId"] = payload["id"]
    base_data["networks"] = [n for n in base_data.get("networks", []) if n.get("id") != payload["id"]] + [payload]
    os.makedirs(os.path.dirname(output_filepath) or ".", exist_ok=True)
    tmp = output_filepath + ".part"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(base_data, f, indent=4)
    os.replace(tmp, output_filepath)
    print(f"\nExpanded network written to {output_filepath}")


def print_hidden_report(report):
    if not report:
        print("No hidden node: no relation was in tension.")
        return
    for h in report:
        needed = h.get("needed_sigmas")
        needed_text = f"{needed:.1f} sigmas from 'nothing missing'" if needed is not None else "uncertainty unknown"
        print(f"\n  {h['node']}  (inside relation '{h['relation']}')")
        print(f"    value {h['value']:.6g}, {needed_text}")
        if needed is not None and needed < 2:
            print("    -> barely needed: the tension may come from a measurement rather than a missing quantity")
        if "candidates" in h:
            print(f"    {h['combinations_tried']} forms tried, chance alone gives {h['chance']:.1f} matches")
            for c in h["candidates"][:5]:
                print(f"      ~ {c['form']}  (off by {c['error_dex']:+.4f} dex)")
            if not h["candidates"]:
                print("      no simple form: something not yet in the network")


def run_full_pipeline_and_export(file_path):
    print(f"=== Loading the network from {file_path} ===")
    data = load_grm_network_safely(file_path)
    measured = dict(data.get("measured", {}))
    grm = GlobalRelationalNetwork(nodes_spec=data["nodes_spec"], relations_spec=data["relations_spec"])
    print(f"Nodes: {len(grm.nodes_names)} | relations: {len(grm.relations)}")

    first = grm.solve(measured_dict=measured)
    print(f"Initial tension (cost): {first['cost']:.3e}")

    print("\n--- 1. Expansion where the network is in tension ---")
    total = 0
    for p in range(EXPAND_PASSES):
        added = grm.auto_expand(threshold_tension=TENSION_SIGMAS, max_additions=ADDITIONS_PER_PASS,
                                measured_dict=measured, seed=p)
        total += added
        if added == 0:
            break
        print(f"  pass {p + 1}: +{added} hidden nodes")
    print(f"{total} hidden nodes added")

    sol = grm.solve(measured_dict=measured)
    print(f"Tension after expansion: {sol['cost']:.3e} (was {first['cost']:.3e})")
    for t in grm.get_relation_tensions()[:5]:
        if t["tension"] > TENSION_SIGMAS:
            print(f"  still tense: {t['name']} ({t['tension']:.1f} sigmas)")

    print("\n--- 2. What the network added ---")
    print_hidden_report(grm.explain_hidden_nodes(sol))

    print("\n--- 3. Bridges (report only, not added) ---")
    bridges = grm.mine_bridges(tolerance_dex=0.005, max_hits=450)
    info = grm.last_bridge_search
    print(f"{info['hits']} hits for {info['combinations_tested']} combinations; chance alone gives "
          f"{info['chance_hits']:.1f}")
    if info["hits"] <= 2 * info["chance_hits"]:
        print("  -> about what chance gives: these hits are not evidence of anything")
    for b in bridges[:10]:
        print(f"  {b['formula']}  (off by {b['residualDex']:.4f} dex)")

    print("\n--- 4. Master invariant of the expanded network ---")
    master = grm.extract_master_invariant(sol["values"])
    if "equation" in master:
        print(f"Equation : {master['equation']}")
        print(f"Residual : {master['residual']:.6e}")
        print(f"Span     : {master['span']:.4f} decades")
        print(f"Derived  : {master['derived']}" + (f" (from {master['relations']})" if master["derived"] else ""))
    else:
        print(master.get("equation_text", "no invariant"))

    export_enriched_network(grm, measured, OUTPUT, file_path)
    print("=== Done ===")


if __name__ == "__main__":
    run_full_pipeline_and_export(GRM_NETWORK_STORE_JSON)
