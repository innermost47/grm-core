# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Anthony Charretier
"""Solve reference networks with the Python GRM and write web/tests/golden.json, the numbers grm.js must
reproduce. Usage (from the repository root): python web/tests/make_golden.py"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from grm_explorer import build_network, preset_document  # noqa: E402
from grm_presets import PRESETS  # noqa: E402

cases = []
for p in PRESETS:
    doc = preset_document(p)
    net, measured = build_network(doc)
    out = net.solve(measured_dict=measured)
    cases.append({"id": p["id"], "doc": {"nodes": doc["nodes"], "relations": doc["relations"]},
                  "values": out["values"], "sigma_dex": out["sigma_dex"], "cost": out["cost"],
                  "converged": out["converged"], "undetermined": out["undetermined"]})

# an undetermined node and a fixed one
doc = {"nodes": {"a": {"guess": 2.0, "scale": "log", "measured": [3.0, 1e-3]}, "b": {"guess": 5.0, "scale": "log"},
                 "k": {"guess": 7.0, "scale": "log", "fixed": True}},
       "relations": [{"name": "a k", "type": "log", "terms": {"a": 1, "k": -1}, "rhs": 0.1, "sigma": 1e-3}]}
net, measured = build_network(doc)
out = net.solve(measured_dict=measured)
cases.append({"id": "undetermined", "doc": doc, "values": out["values"], "sigma_dex": out["sigma_dex"],
              "cost": out["cost"], "converged": out["converged"], "undetermined": out["undetermined"]})

path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "golden.json")
with open(path, "w") as f:
    json.dump(cases, f, indent=1)
print("written", path, len(cases), "cases")
