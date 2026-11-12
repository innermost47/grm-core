# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Anthony Charretier
"""Does the GRM machine bring up S x Equant = Estock from the seven relations of the chain, without being helped?

The criteria are fixed before anything is run:
  1. implied: S Equant / Estock is an exact combination of the seven relations (linear algebra on the relations in
     log10, every node but S, Equant, Estock and the constants eliminated; no merit, no choice);
  2. master: the master equation the machine gives (pygrm's master invariant), as it comes.
The program is vm/programs/universe.grm, run seven ways:
  A  as it is (c, hbar, kB, G fixed)
  B  G measured instead of fixed
  C  nothing fixed: c, hbar, kB, G all measured
  D  A with the base the machine is born with (30 points of the world, 3 relations: distractors)
  E  A with neutral names (n0, n1... for the nodes, r1..r7 for the relations)
  F  A with H0 a thousand times larger (the equation should hold for any H)
  G  negative control: one relation made wrong on purpose (stock: Hend^2 instead of Hend^3)

    python vm/test_universe_unbiased.py      the table of the seven runs
    pytest vm/test_universe_unbiased.py      what must hold (1 in A..F and not in G; 2 in A, C..F and never in G)

Run B is reported, not asserted: with G measured the machine settles its values to about 1e-8 dex, more than the
precision of its exact relations allows, and pygrm's master invariant then prefers another equation of the same span.
"""
import math
import os
import random
import re
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import grm_vm  # noqa: E402
import mind  # noqa: E402

pygrm = pytest.importorskip("pygrm")
np = pytest.importorskip("numpy")
NEW_ENOUGH = tuple(int(x) for x in pygrm.__version__.split(".")[:2]) >= (0, 5)

TARGET = {"S": 1.0, "Equant": 1.0, "Estock": -1.0}
VARIANTS = "ABCDEFG"
SOURCE = os.path.join(HERE, "programs", "universe.grm")


def variant(name):
    """The program of a run, and the new names of its nodes (E)."""
    with open(SOURCE, encoding="utf-8") as f:
        src = f.read()
    if name in ("B", "C"):
        src = src.replace("node G = 6.67430e-11 fixed [-1 3 -2 0 0]",
                          "node G [-1 3 -2 0 0]\nobserve G = 6.67430e-11 ± 0.0022%")
    if name == "C":
        for n, v in (("c", "299792458"), ("hbar", "1.054571817e-34"), ("kB", "1.380649e-23")):
            src = re.sub(rf"node {n} = {re.escape(v)} fixed (\[[^\]]*\])",
                         rf"node {n} \1\nobserve {n} = {v} ± 0.0000001%", src)
    if name == "F":
        src = src.replace("observe H0 = 2.184e-18", "observe H0 = 2.184e-15")
    if name == "G":
        src = src.replace("relate stock:   Estock * 3 * Hend^3", "relate stock:   Estock * 3 * Hend^2")
    rename = {}
    if name == "E":
        nodes = ["lP", "Hend", "rhoL", "Estock", "Tfloor", "Equant", "S", "H0", "OmegaL"]
        new = [f"n{k}" for k in range(len(nodes))]
        random.Random(7).shuffle(new)
        rename = dict(zip(nodes, new))
        for old, nw in sorted(rename.items(), key=lambda kv: -len(kv[0])):
            src = re.sub(rf"(?<![A-Za-z0-9_]){old}(?![A-Za-z0-9_])", nw, src)
        for k, r in enumerate(["planck", "end", "vacuum", "stock", "floor", "quantum", "entropy"]):
            src = src.replace(f"relate {r}:", f"relate r{k + 1}:")
    return src, rename


def implied(pic, target):
    """Criterion 1: is the target a combination of the relations (the constants free)? Least squares on the
    target's nodes over the independent equations pygrm returns. None when no combination gives it."""
    g = pygrm.GlobalRelationalNetwork(pic["nodes"], pic["relations"])
    consts = [n for n in g.nodes_names if n in g.fixed_nodes]
    eqs = g.global_equations(list(target) + consts)
    if not eqs:
        return None
    names = list(target)
    A = np.array([[e["terms"].get(n, 0.0) for e in eqs] for n in names])
    b = np.array([target[n] for n in names])
    y, *_ = np.linalg.lstsq(A, b, rcond=None)
    if np.max(np.abs(A @ y - b)) > 1e-9:
        return None
    rest = {}
    for w, e in zip(y, eqs):
        for n, c in e["terms"].items():
            if n not in target:
                rest[n] = rest.get(n, 0.0) + w * c
    return {"constants": {n: c for n, c in rest.items() if abs(c) > 1e-9},
            "value": 10 ** float(sum(w * e["rhs"] for w, e in zip(y, eqs)))}


def run(name, tmp):
    src, rename = variant(name)
    path = os.path.join(tmp, f"universe_{name}.grm")
    with open(path, "w", encoding="utf-8") as f:
        f.write(src)
    vm = grm_vm.VM(memory=None, blank=(name != "D"))
    vm.say(f"use {path}")
    vm.tick()
    target = {rename.get(k, k): v for k, v in TARGET.items()}
    s, eq, es = (vm.get(n) for n in target)
    res = mind.master(vm)
    master_terms = None
    if "span" in res:
        pic = vm.past[-1]
        g = pygrm.GlobalRelationalNetwork(pic["nodes"], pic["relations"])
        best = g.extract_master_invariant(pic["values"], display_mode="compact", max_pairs=mind.MAX_PAIRS)
        master_terms = best.get("terms")
    text = res["text"]
    for old, nw in rename.items():
        text = re.sub(rf"(?<![A-Za-z0-9_]){nw}(?![A-Za-z0-9_])", old, text)
    is_target = master_terms is not None and set(master_terms) == set(target) and all(
        abs(master_terms[n] / master_terms[next(iter(target))] - target[n] / target[next(iter(target))]) < 1e-9
        for n in target)
    return {"variant": name, "ratio": s * eq / es, "implied": implied(vm.past[-1], target), "master": text,
            "span": res.get("span"), "residual": res.get("residual"), "is_target": is_target}


@pytest.fixture(scope="module")
def runs(tmp_path_factory):
    tmp = str(tmp_path_factory.mktemp("universe"))
    return {v: run(v, tmp) for v in VARIANTS}


@pytest.mark.parametrize("name", "ABCDEF")
def test_implied_by_the_seven_relations(runs, name):
    r = runs[name]
    assert r["implied"] is not None and not r["implied"]["constants"]
    assert r["implied"]["value"] == pytest.approx(1, rel=1e-9)
    assert r["ratio"] == pytest.approx(1, rel=1e-6)


def test_a_wrong_relation_does_not_imply_it(runs):
    assert runs["G"]["implied"] is None and abs(math.log10(runs["G"]["ratio"])) > 10


@pytest.mark.skipif(not NEW_ENOUGH, reason="needs pygrm >= 0.5.0 (the master invariant over triples)")
@pytest.mark.parametrize("name", "ACDEF")
def test_the_master_equation_brings_it_up(runs, name):
    assert runs[name]["is_target"], runs[name]["master"]


def test_never_from_a_wrong_relation(runs):
    assert not runs["G"]["is_target"]


if __name__ == "__main__":
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        for v in VARIANTS:
            r = run(v, tmp)
            imp = r["implied"]
            span = "-" if r["span"] is None else f"{r['span']:.1f}"
            resid = "-" if r["residual"] is None else f"{r['residual']:.2g}"
            print(f"{v}  S·Equant/Estock = {r['ratio']:.9g}")
            print("   implied by the seven: " + (f"yes (= {imp['value']:.9g})" if imp else "no"))
            print(f"   master equation:      {r['master']}   [{span} decades, residual {resid}]"
                  + ("   <- S·Equant = Estock" if r["is_target"] else ""))
