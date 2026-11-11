# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Anthony Charretier
import json
import os
import random

# node spec keys passed through to the network as they are
EXTRA_NODE_KEYS = ("min", "max", "constant", "hidden_for", "hidden_prior")


def list_grm_networks(file_path):
    """[(id, name)] of the networks of a GRM store file, the active one first."""
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    nets = [(n.get("id"), n.get("name", "")) for n in data.get("networks", [])]
    active = data.get("activeId")
    return sorted(nets, key=lambda t: t[0] != active)


def load_grm_network_safely(file_path, chaos_factor=0.0, chaos_probability=0.2, functions=None, network_id=None):
    """Loads a network of a GRM store file: the active one, or the one whose id is network_id.

    A node is fixed only when its spec says "fixed": true. Function relations ("type": "fn") need their Python
    function: pass them as functions={relation name: callable(values) -> residual}; a function relation without
    one is left out, with a warning. A log relation that uses a signed (lin) node or a non-positive value cannot
    be solved in log space: it is left out with a warning (turning it into a sum relation would change its
    meaning: in a log relation the coefficients are powers, in a sum relation they are multipliers).
    chaos_factor > 0 perturbs the starting values of some free nodes (a test of how robust the solve is).
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"The file '{file_path}' could not be found.")

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"LOAD FILE: {file_path}" + (f"  [network {network_id}]" if network_id else "") + "\n")
    active_id = network_id or data.get("activeId", "default")
    networks = data.get("networks", [])

    target_network = None
    for net in networks:
        if net.get("id") == active_id:
            target_network = net
            break
    if not target_network and network_id:
        raise ValueError(f"no network with id '{network_id}' in {file_path}")
    if not target_network and networks:
        target_network = networks[0]

    if not target_network:
        raise ValueError("[Error] No valid network found in the JSON payload.")

    nodes_dict = target_network.get("nodes", {})
    disabled_nodes = set(target_network.get("disabledNodes", []))
    measured_data = {k: v for k, v in target_network.get("measured", {}).items() if k not in disabled_nodes}
    functions = functions or {}

    active_nodes_spec = {}
    for name, spec in nodes_dict.items():
        if name in disabled_nodes:
            continue
        val = spec.get("solved", spec.get("value", spec.get("guess", 1.0)))
        is_fixed = bool(spec.get("fixed", False))
        scale = spec.get("scale", "lin" if val <= 0 else "log")
        if chaos_factor > 0.0 and not is_fixed and val != 0 and random.random() < chaos_probability:
            val = val * (1.0 + random.uniform(-chaos_factor, chaos_factor))
            if scale == "log" and val <= 0:
                val = abs(val) or 1.0
        node = {
            "guess": float(val),
            "solved": float(val),
            "scale": scale,
            "fixed": is_fixed,
            "dim": spec.get("dim", [0, 0, 0, 0, 0]),
        }
        for key in EXTRA_NODE_KEYS:
            if key in spec:
                node[key] = spec[key]
        active_nodes_spec[name] = node

    all_raw_rels = []
    for src in (target_network.get("relations", []), target_network.get("customRelations", [])):
        if isinstance(src, list):
            all_raw_rels.extend(src)
        elif isinstance(src, dict):
            for k, v in src.items():
                if isinstance(v, dict):
                    rc = dict(v)
                    rc.setdefault("name", k)
                    all_raw_rels.append(rc)

    cleaned_relations = []
    seen_names = set()
    left_out = {"function missing": [], "disabled or unknown node": [], "log relation on a signed node": []}

    for rel in all_raw_rels:
        if not isinstance(rel, dict):
            continue
        rel = dict(rel)
        r_name = rel.get("name")
        r_type = rel.get("type", "log")

        if r_type == "fn":
            if not callable(rel.get("f")):
                if r_name in functions:
                    rel["f"] = functions[r_name]
                else:
                    left_out["function missing"].append(r_name)
                    continue
            if not all(n in active_nodes_spec for n in rel.get("nodes", [])):
                left_out["disabled or unknown node"].append(r_name)
                continue

        terms = rel.get("terms", {})
        if terms and not all(n in active_nodes_spec for n in terms):
            left_out["disabled or unknown node"].append(r_name)
            continue

        if r_type == "log" and any(
            active_nodes_spec[n]["scale"] == "lin" or active_nodes_spec[n]["guess"] <= 0 for n in terms
        ):
            left_out["log relation on a signed node"].append(r_name)
            continue

        if r_name:
            if r_name in seen_names:
                continue
            seen_names.add(r_name)
        cleaned_relations.append(rel)

    for reason, names in left_out.items():
        if names:
            print(f"[WARN] {len(names)} relations left out ({reason}): {', '.join(str(n) for n in names)}")

    return {
        "nodes_spec": active_nodes_spec,
        "relations_spec": cleaned_relations,
        "measured": measured_data,
    }
