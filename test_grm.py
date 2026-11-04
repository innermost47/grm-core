# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Anthony Charretier
"""
Test battery for the Global Relational Model engine (grm.py).

    python -m pytest -v test_grm.py
    GRM_SPEC=path/to/my_model.py python -m pytest -v -s test_grm.py     # also test a full model

Parts:
  1. Engine: exact answers on small systems, physical range, measurements, identifiability,
     state and inputs, robustness, uncertainties.
  2. Protocol: leave-one-out with random starting points, relation knock-out and chance test,
     on built-in examples (Kepler, Planck units) and on a user model if GRM_SPEC is set.
     A model file defines NODES, RELATIONS, MEASURED ({node: value}) and optionally
     TOLERANCE ({node: relative tolerance}, default 5 %).
  3. The water test, and what it actually shows.
"""
import importlib.util
import math
import os
import random
import time

import pytest

from grm import GlobalRelationalNetwork

REL_TOL = 1e-6          # an exactly solvable system must be solved to this precision


def net(nodes, relations):
    return GlobalRelationalNetwork(nodes, relations)


def rel_err(a, b):
    return abs(a - b) / max(abs(b), 1e-300)


# ============================================================================
# 1. ENGINE TESTS
# ============================================================================

class TestExactness:
    """Systems with a known analytic answer must be solved exactly."""

    def test_single_product_relation(self):
        # E = m c^2 with c fixed and m pinned to 2 by a relation
        nodes = {"E": {"guess": 1.0}, "m": {"guess": 1.0}, "c": {"guess": 3e8, "fixed": True}}
        rels = [{"terms": {"E": 1, "m": -1, "c": -2}, "rhs": 0.0},
                {"terms": {"m": 1}, "rhs": math.log10(2.0)}]
        v = net(nodes, rels).solve()["values"]
        assert rel_err(v["m"], 2.0) < REL_TOL
        assert rel_err(v["E"], 2.0 * 9e16) < REL_TOL

    def test_chain_of_twenty_relations(self):
        # x0 = 10, x_{k+1} = 3 * x_k  ->  x_k = 10 * 3^k
        n = 20
        nodes = {f"x{k}": {"guess": 1.0} for k in range(n)}
        rels = [{"terms": {"x0": 1}, "rhs": 1.0}]
        rels += [{"terms": {f"x{k+1}": 1, f"x{k}": -1}, "rhs": math.log10(3)} for k in range(n - 1)]
        v = net(nodes, rels).solve()["values"]
        for k in range(n):
            assert rel_err(v[f"x{k}"], 10 * 3 ** k) < REL_TOL, f"x{k}"

    def test_one_iteration_must_move_the_solution(self):
        # A purely linear (log-space) problem: one Gauss-Newton step is enough.
        nodes = {"a": {"guess": 5.0}}
        rels = [{"terms": {"a": 1}, "rhs": 2.0}]
        v = net(nodes, rels).solve(max_iterations=1)["values"]
        assert rel_err(v["a"], 100.0) < 1e-2, "the step of the last iteration is thrown away"

    def test_reported_cost_matches_returned_values(self):
        nodes = {"a": {"guess": 5.0}, "b": {"guess": 1.0}}
        rels = [{"terms": {"a": 1}, "rhs": 2.0, "sigma": 0.1},
                {"terms": {"a": 1, "b": -1}, "rhs": 0.5, "sigma": 0.1}]
        n = net(nodes, rels)
        out = n.solve()
        x = {k: math.log10(v) for k, v in out["values"].items()}
        cost = sum(((sum(c * x[k] for k, c in r["terms"].items()) - r["rhs"]) / r["sigma"]) ** 2 for r in rels)
        assert abs(cost - out["cost"]) < 1e-9 + 1e-6 * cost


class TestPhysicalRange:
    """Physics spans 10^-44 to 10^122: nothing may be clamped."""

    @pytest.mark.parametrize("value", [6.674e-11, 1.054571817e-34, 1.380649e-23, 5.39e-44, 1e-5 / 3])
    def test_small_fixed_constant_is_not_clamped(self, value):
        nodes = {"k": {"guess": value, "fixed": True}, "y": {"guess": 1.0}}
        rels = [{"terms": {"y": 1, "k": -1}, "rhs": 0.0}]
        v = net(nodes, rels).solve()["values"]
        assert rel_err(v["k"], value) < REL_TOL
        assert rel_err(v["y"], value) < REL_TOL

    def test_small_measurement_is_not_clamped(self):
        nodes = {"a": {"guess": 1.0}}
        rels = [{"terms": {"a": 1}, "rhs": 0.0, "sigma": 1e3}]  # very loose relation
        v = net(nodes, rels).solve(measured_dict={"a": 2.2e-30})["values"]
        assert v["a"] < 1e-20

    def test_huge_values(self):
        nodes = {"S": {"guess": 1.0}, "N": {"guess": 1.0}}
        rels = [{"terms": {"S": 1}, "rhs": 122.5}, {"terms": {"N": 1, "S": -1}, "rhs": -1.0}]
        v = net(nodes, rels).solve()["values"]
        assert rel_err(v["S"], 10 ** 122.5) < 1e-7
        assert rel_err(v["N"], 10 ** 121.5) < 1e-7

    @pytest.mark.parametrize("bad", [0.0, -1.0])
    def test_zero_or_negative_values_are_refused(self, bad):
        # log-space cannot hold 0 or a sign: the engine must say so, not substitute 1e-5
        with pytest.raises((ValueError, ArithmeticError)):
            net({"a": {"guess": bad}}, [{"terms": {"a": 1}, "rhs": 0.0}]).solve()


class TestMeasurements:
    """A measurement is information: it must constrain the result, not only seed it."""

    def test_measurement_is_kept_when_nothing_contradicts_it(self):
        nodes = {"a": {"guess": 1.0}, "b": {"guess": 1.0}}
        rels = [{"terms": {"a": 1, "b": -1}, "rhs": 0.0}]   # a = b, nothing else
        v = net(nodes, rels).solve(measured_dict={"a": 100.0})["values"]
        assert rel_err(v["a"], 100.0) < 1e-6, f"measured a=100 came back as {v['a']}"
        assert rel_err(v["b"], 100.0) < 1e-6

    def test_conflict_between_measurement_and_relation_is_a_weighted_compromise(self):
        # relation says a = 10 (sigma 0.01 dex); measurement says a = 1000 (sigma 0.01 dex)
        # -> the least-squares answer is the geometric middle, 100, and the cost must show the tension
        nodes = {"a": {"guess": 1.0}}
        rels = [{"terms": {"a": 1}, "rhs": 1.0, "sigma": 0.01}]
        out = net(nodes, rels).solve(measured_dict={"a": (1000.0, 0.01)})  # (value, sigma in dex)
        assert 50 < out["values"]["a"] < 200, f"measurement ignored: a = {out['values']['a']}"
        assert out["cost"] > 100

    def test_unknown_measurement_name_is_refused(self):
        with pytest.raises((KeyError, ValueError)):
            net({"a": {"guess": 1.0}}, [{"terms": {"a": 1}, "rhs": 0.0}]).solve(measured_dict={"aa": 3.0})


class TestIdentifiability:
    """An answer the relations do not determine must not be presented as a prediction."""

    def test_result_does_not_depend_on_initial_guess(self):
        rels = [{"terms": {"a": 1, "b": -1}, "rhs": 0.0}, {"terms": {"b": 1}, "rhs": 1.0}]
        v1 = net({"a": {"guess": 42.0}, "b": {"guess": 7.0}}, rels).solve()["values"]
        v2 = net({"a": {"guess": 1e4}, "b": {"guess": 3e-3}}, rels).solve()["values"]
        for k in v1:
            assert rel_err(v1[k], v2[k]) < 1e-6, k

    def test_undetermined_node_is_flagged(self):
        # a = b and nothing else: neither is determined. The engine returns sqrt(guess_a * guess_b)
        # silently. A predictive model must report that this value is not a prediction.
        out = net({"a": {"guess": 42.0}, "b": {"guess": 7.0}},
                  [{"terms": {"a": 1, "b": -1}, "rhs": 0.0}]).solve()
        assert "undetermined" in out, f"no identifiability information; a = {out['values']['a']:.4g} is just sqrt(42 * 7)"
        assert {"a", "b"} <= set(out["undetermined"])


class TestStateAndInputs:
    def test_two_solves_on_one_instance_are_independent(self):
        nodes = {"a": {"guess": 1.0}, "b": {"guess": 1.0}}
        rels = [{"terms": {"a": 1, "b": -1}, "rhs": 0.0}, {"terms": {"a": 1}, "rhs": 0.0, "sigma": 1e2}]
        n = net(nodes, rels)
        n.solve(measured_dict={"a": 50.0})
        again = n.solve()["values"]
        fresh = net(nodes, rels).solve()["values"]
        for k in fresh:
            assert rel_err(again[k], fresh[k]) < 1e-6, f"state leaked from the previous solve: {k}"

    def test_unknown_node_in_relation_is_refused(self):
        # a typo turns 'a / tpyo = 10' into 'a = 10' without any warning
        with pytest.raises((KeyError, ValueError)):
            net({"a": {"guess": 1.0}}, [{"terms": {"a": 1, "tpyo": -1}, "rhs": 1.0}]).solve()

    def test_network_without_relations(self):
        v = net({"a": {"guess": 3.0, "fixed": True}}, []).solve()["values"]
        assert rel_err(v["a"], 3.0) < REL_TOL

    def test_fixed_node_never_moves(self):
        nodes = {"c": {"guess": 3e8, "fixed": True}, "a": {"guess": 1.0}}
        rels = [{"terms": {"c": 1}, "rhs": 0.0}, {"terms": {"a": 1, "c": -1}, "rhs": 0.0}]
        v = net(nodes, rels).solve()["values"]
        assert rel_err(v["c"], 3e8) < REL_TOL

    def test_reported_iterations_are_real(self):
        out = net({"a": {"guess": 5.0}}, [{"terms": {"a": 1}, "rhs": 2.0}]).solve(max_iterations=50)
        assert out["iterations"] < 50, "iterations always equals max_iterations: no convergence test"


class TestRobustness:
    def test_contradictory_relations_do_not_crash_and_show_tension(self):
        nodes = {"a": {"guess": 1.0}}
        rels = [{"terms": {"a": 1}, "rhs": 0.0, "sigma": 0.01}, {"terms": {"a": 1}, "rhs": 1.0, "sigma": 0.01}]
        out = net(nodes, rels).solve()
        assert rel_err(out["values"]["a"], 10 ** 0.5) < 1e-6
        assert out["cost"] > 1000

    def test_dynamic_rhs_converges_to_its_fixed_point(self):
        # log a = 1 + 0.5 * log a  ->  log a = 2  ->  a = 100 (rhs depends on the current value)
        nodes = {"a": {"guess": 1.0}}
        rels = [{"terms": {"a": 1}, "rhs": lambda v: 1.0 + 0.5 * math.log10(v["a"])}]
        v = net(nodes, rels).solve(max_iterations=50)["values"]
        assert rel_err(v["a"], 100.0) < 1e-6

    def test_ill_conditioned_weights(self):
        # one relation 10^6 times tighter than another
        nodes = {"a": {"guess": 1.0}, "b": {"guess": 1.0}}
        rels = [{"terms": {"a": 1}, "rhs": 3.0, "sigma": 1e-6},
                {"terms": {"a": 1, "b": -1}, "rhs": 1.0, "sigma": 1.0}]
        v = net(nodes, rels).solve()["values"]
        assert rel_err(v["a"], 1e3) < 1e-6 and rel_err(v["b"], 1e2) < 1e-6

    def test_150_nodes_in_reasonable_time(self):
        n = 150
        rnd = random.Random(1)
        nodes = {f"x{k}": {"guess": 10 ** rnd.uniform(-3, 3)} for k in range(n)}
        rels = [{"terms": {"x0": 1}, "rhs": 0.0}]
        rels += [{"terms": {f"x{k}": 1, f"x{rnd.randrange(k)}": -1}, "rhs": rnd.uniform(-1, 1)} for k in range(1, n)]
        t = time.time()
        net(nodes, rels).solve()
        assert time.time() - t < 30


class TestRelationTypes:
    def test_sum_relation_with_signed_nodes(self):
        # hypercharges: 2 * Qu + Qd = 1 (proton), Qu + 2 * Qd = 0 (neutron) -> Qu = 2/3, Qd = -1/3
        nodes = {"Qu": {"scale": "lin", "guess": 0.0}, "Qd": {"scale": "lin", "guess": 0.0}}
        rels = [{"type": "sum", "terms": {"Qu": 2, "Qd": 1}, "K": 1.0, "sigma": 1e-9},
                {"type": "sum", "terms": {"Qu": 1, "Qd": 2}, "K": 0.0, "sigma": 1e-9}]
        v = net(nodes, rels).solve()["values"]
        assert abs(v["Qu"] - 2 / 3) < 1e-9 and abs(v["Qd"] + 1 / 3) < 1e-9

    def test_sum_relation_with_powers(self):
        # Omega_b + Omega_c + Omega_L = 1 with two of them measured
        nodes = {"Ob": {"guess": 0.1}, "Oc": {"guess": 0.1}, "OL": {"guess": 0.1}}
        rels = [{"type": "sum", "terms": {"Ob": 1, "Oc": 1, "OL": 1}, "K": 1.0, "sigma": 1e-7}]
        v = net(nodes, rels).solve(measured_dict={"Ob": 0.049, "Oc": 0.26})["values"]
        assert abs(v["OL"] - 0.691) < 1e-5

    def test_fn_relation_koide(self):
        # Koide: (me + mmu + mtau) / (sqrt me + sqrt mmu + sqrt mtau)^2 = 2/3 -> predicts mtau (MeV)
        nodes = {"me": {"guess": 1.0}, "mmu": {"guess": 1.0}, "mtau": {"guess": 1000.0}}
        koide = lambda v: (v["me"] + v["mmu"] + v["mtau"]) / (math.sqrt(v["me"]) + math.sqrt(v["mmu"]) + math.sqrt(v["mtau"])) ** 2 - 2 / 3
        rels = [{"type": "fn", "nodes": ["me", "mmu", "mtau"], "f": koide, "sigma": 1e-9}]
        out = net(nodes, rels).solve(measured_dict={"me": (0.51099895, 1e-9), "mmu": (105.6583755, 1e-9)})
        assert abs(out["values"]["mtau"] - 1776.97) < 0.1 and out["converged"]

    def test_signed_node_refused_in_log_relation(self):
        with pytest.raises(ValueError):
            net({"w": {"scale": "lin", "guess": -1.0}}, [{"terms": {"w": 1}, "rhs": 0.0}])

    def test_signed_node_accepts_negative_and_zero(self):
        nodes = {"w": {"scale": "lin", "guess": 0.0}}
        rels = [{"type": "sum", "terms": {"w": 1}, "K": -0.9, "sigma": 1e-6}]
        out = net(nodes, rels).solve()
        assert abs(out["values"]["w"] + 0.9) < 1e-9


class TestTuning:
    def test_tight_sum_is_solved_by_continuation(self):
        # shares pulled apart in log space, tied by a very tight sum: a direct descent crawls along the sum
        pulls = {"a": 0.45, "b": 0.27, "c": 0.09, "d": 0.09, "e": 0.09}
        nodes = {k: {"guess": 0.2} for k in pulls}
        rels = [{"name": "balance", "type": "sum", "terms": {k: 1.0 for k in pulls}, "K": 1.0, "sigma": 1e-6}]
        rels += [{"name": f"pull_{k}", "terms": {k: 1.0}, "rhs": math.log10(p), "sigma": 0.3} for k, p in pulls.items()]
        net = GlobalRelationalNetwork(nodes, rels)
        out = net.solve(max_iterations=30)
        assert out["converged"]
        assert abs(sum(out["values"].values()) - 1.0) < 1e-5
        # reference: the same network tightened by hand, stage by stage
        ref = GlobalRelationalNetwork(nodes, rels)
        values = None
        for sigma in (1e-2, 1e-4, 1e-6):
            ref.set_sigma("balance", sigma)
            values = ref.solve(max_iterations=50, start=values)["values"]
        for k in pulls:
            assert out["values"][k] == pytest.approx(values[k], rel=1e-6)
        assert out["values"]["a"] > out["values"]["b"] > out["values"]["c"]
        assert net.get_sigma("balance") == 1e-6         # the relation keeps its own sigma afterwards

    def test_set_sigma_moves_the_compromise(self):
        # two contradictory relations; tightening one pulls the answer towards it
        nodes = {"a": {"guess": 1.0}}
        rels = [{"name": "low", "terms": {"a": 1}, "rhs": 0.0, "sigma": 0.01},
                {"name": "high", "terms": {"a": 1}, "rhs": 1.0, "sigma": 0.01}]
        net_ = net(nodes, rels)
        assert abs(math.log10(net_.solve()["values"]["a"]) - 0.5) < 1e-6
        net_.set_sigma("high", 0.001)
        assert math.log10(net_.solve()["values"]["a"]) > 0.95
        assert net_.get_sigma("high") == 0.001

    def test_set_sigma_unknown_relation(self):
        with pytest.raises(KeyError):
            net({"a": {"guess": 1.0}}, [{"name": "r", "terms": {"a": 1}, "rhs": 0.0}]).set_sigma("nope", 1.0)

    def test_grm_plus_solves_a_small_3sat(self):
        import grm_sat
        clauses = grm_sat.random_3sat(30, 3.5, seed=11)
        assignment, sat = grm_sat.grm_plus_solve(30, clauses, seed=1)
        assert sat == grm_sat.count_satisfied(clauses, assignment) == len(clauses)


class TestTSP:
    def test_grm_tsp_methods_give_valid_tours(self):
        import numpy as np
        import grm_tsp
        rng = np.random.default_rng(3)
        coords = rng.random((30, 2)) * 1000
        dist = grm_tsp.distance_matrix(coords)
        tour, rounds = grm_tsp.grm_circle(coords, cooling=0.6, verbose=False)
        assert sorted(tour) == list(range(30)) and rounds > 0
        refined = grm_tsp.tension_refine(tour, dist, rounds=50, verbose=False)
        assert sorted(refined) == list(range(30))
        assert grm_tsp.tour_length(refined, dist) <= grm_tsp.tour_length(tour, dist)

    def test_tour_network_cost_is_the_tour_length(self):
        import numpy as np
        import grm_tsp
        coords = np.random.default_rng(4).random((20, 2)) * 100
        dist = grm_tsp.distance_matrix(coords)
        tour = list(range(20))
        assert abs(grm_tsp.TourNetwork(tour, dist).cost() - grm_tsp.tour_length(tour, dist)) < 1e-9


class TestText:
    def test_sentence_categories_without_training(self):
        """Held-out sentences: mostly right, never a confident error; no known word gives 'unknown'."""
        import grm_text
        rt = grm_text.RelationTable(grm_text.TABLE)
        answers = [(c, rt.classify(s)[0]) for c, sentences in grm_text.TEST.items() for s in sentences]
        right = sum(a == c for c, a in answers)
        confident_wrong = sum(a != c and not a.startswith(("unsure", "unknown")) for c, a in answers)
        assert right >= 0.75 * len(answers)
        assert confident_wrong == 0
        assert rt.classify("mon chat dort sur le canapé")[0] == "unknown"

    def test_shares_sum_to_one(self):
        import grm_text
        rt = grm_text.RelationTable(grm_text.TABLE)
        shares = rt.classify("le guitariste joue un solo")[1]
        assert abs(sum(shares.values()) - 1.0) < 1e-4


def import_guitar():
    """grm_guitar imports tkinter for its window; the physics needs only numpy."""
    import sys
    pytest.importorskip("numpy")
    try:
        import tkinter  # noqa: F401
    except ImportError:
        from unittest import mock
        for name in ("tkinter", "tkinter.filedialog", "tkinter.messagebox", "tkinter.ttk"):
            sys.modules.setdefault(name, mock.MagicMock())
    import grm_guitar
    return grm_guitar


class TestGuitar:
    LOW_E = (0.0061370673, 0.648)
    HIGH_E = (0.0003835658, 0.648)

    def test_palm_damps_highs_first_and_light_strings_most(self):
        g = import_guitar()
        palm = g.palm_network(*self.LOW_E, 0, T=73.0)["values"]
        rates = g.palm_sigma(range(6), palm)
        assert all(b > a for a, b in zip(rates[:4], rates[1:5]))       # the first partials die faster and faster
        high = g.palm_network(*self.HIGH_E, 0, T=72.0)["values"]
        assert high["sigma"][0] > 3 * palm["sigma"][0]                  # a light string is cut harder

    def test_palm_position_matters_more_than_pressure(self):
        # Ottaviani et al. (ICMC-SMC 2014): the distance of the hand from the bridge matters more than its force
        g = import_guitar()
        base = g.palm_network(*self.LOW_E, 0, 0.02, 1.0, 73.0)["values"]["sigma"][0]
        moved = g.palm_network(*self.LOW_E, 0, 0.03, 1.0, 73.0)["values"]["sigma"][0]       # +50 % distance
        pressed = g.palm_network(*self.LOW_E, 0, 0.02, 1.5, 73.0)["values"]["sigma"][0]     # +50 % force
        assert moved > pressed > base

    def test_palm_modes_are_exact_roots(self):
        g = import_guitar()
        v = g.palm_network(*self.LOW_E, 0, T=73.0)["values"]
        for n in (1, 3, 5, 12):
            w = 2 * math.pi * v["ratio"][n - 1] * n * v["f1"] + 1j * v["sigma"][n - 1]
            y = g._palm_shape(w, v["c"], v["mu"], v["T"], v["x"], v["w"], v["Leff"], v["rp"])
            assert abs(y) < 1e-5
        free = g.partial_frequencies(v["f1"], 0.0, 4)
        assert abs(g.palm_frequencies(free, v)[0] / free[0] - 1) < 0.01     # the note keeps its pitch

    def test_longitudinal_mode_matches_the_measured_one(self):
        # Pakarinen et al. 2007 report the first longitudinal mode of an open 6th string near 1400 Hz;
        # the network gives c_L / (2 L) from the steel core alone
        g = import_guitar()
        f = {k: g.squeak_network(*self.LOW_E, k, 0, 0, 0.1, 0.6)["values"]["fL"] for k in (0.36, 0.45)}
        assert f[0.36] == pytest.approx(1400, rel=0.03)
        assert f[0.45] / f[0.36] == pytest.approx(0.45 / 0.36, rel=1e-6)   # c_L grows with the core share

    def test_winding_pitch_is_speed_over_wire(self):
        g = import_guitar()
        v = g.squeak_network(*self.LOW_E, 0.45, 2, 3, 0.1, 0.6)["values"]
        assert v["fsq"] == pytest.approx(v["v"] / v["p"], rel=1e-6)

    def test_sympathetic_answer_never_exceeds_its_drive(self):
        import numpy as np
        g = import_guitar()
        modes, bv = g.body_modes()
        sv = g.play_string_model(*self.LOW_E, 70.0, 0, 0.45)["values"]
        f = np.fft.rfftfreq(1 << 18, 1.0 / g.SAMPLE_RATE)
        Y = g.bridge_admittance(f, modes, bv)
        loss = g.bridge_loss(modes, bv, sv["c"], sv["Leff"], sv["Zs"])
        gain = g.sympathetic_response(np.ones(len(f)), f, Y, sv["f1"], sv["B"], 70.0, sv["Leff"],
                                      lambda fn: 1.0 / 3.0 + loss(fn),
                                      lambda fn: (sv["c"] / sv["Leff"]) * sv["Zs"] * np.abs(g.bridge_admittance(fn, modes, bv)))
        assert np.max(np.abs(gain)) <= 1.0

    def test_player_is_human_but_keeps_time(self):
        import numpy as np
        g = import_guitar()
        step = 1 / 3
        grid = [(k * step, k % 8) for k in range(48)]
        strokes = g.player_network(grid, step, 0.22, np.random.default_rng(0))
        dev = np.array([s["t"] - t for s, (t, _) in zip(strokes, grid)])
        assert 0.004 < dev.std() < 0.02                                  # musicians: 10 to 20 ms
        assert all(b["t"] > a["t"] for a, b in zip(strokes, strokes[1:]))
        up = g.strum_contacts([5, 4, 3, 2, 1, 0], dict(strokes[0], d=g.PICK_DEPTH), up=True)
        assert 0 not in [i for i, _, _ in up]                            # an upstroke misses the low E


class TestBrain:
    def test_it_learns_the_way_while_living(self):
        import grm_brain as gbr
        life = gbr.run_headless(6, seed=3)
        assert len(life.trips) == 6
        assert life.trips[-1] <= 1.3 * life.maze.shortest()       # it ends up taking (almost) the shortest way
        assert life.trips[-1] < life.trips[0]

    def test_it_relearns_when_the_maze_changes(self):
        import grm_brain as gbr
        life = gbr.run_headless(10, seed=2, change_after=5)
        assert len(life.trips) == 10
        assert life.trips[-1] <= 1.3 * life.maze.shortest()       # the new maze is learned too

    def test_the_brain_never_reads_the_maze(self):
        import grm_brain as gbr
        brain = gbr.Brain()
        assert not any(isinstance(v, gbr.Maze) for v in vars(brain).values())


class TestScales:
    def test_small_predicts_the_large(self):
        import grm_scales as sc
        up = sc.run_up()
        for k in ("R_jup", "M_jup", "rho_rock", "R_potato"):
            assert abs(math.log10(up["values"][k] / sc.LARGE[k][0])) < math.log10(2.0)   # within a factor 2
        assert "h_earth" in up["undetermined"]          # the crust's strength is not given by the small

    def test_the_sky_gives_back_the_constants_of_matter(self):
        import grm_scales as sc
        far = sc.run_down(with_atom=False)              # no atom: planets, stars, rocks, mountains only
        for k in ("alpha", "me", "mp"):
            assert abs(math.log10(far["values"][k] / sc.SMALL[k][0])) < math.log10(2.0)

    def test_mountains_follow_one_over_g(self):
        import grm_scales as sc
        rows = {k: z for k, d, z in sc.leave_one_out()}
        assert all(abs(rows[k]) < 2 for k in ("h_earth", "h_mars", "h_venus"))


class TestVoice:
    def test_uniform_tube_resonates_at_odd_quarter_waves(self):
        # a tube closed at the glottis and open at the lips: F_n = (2n - 1) c / (4 L), raised a little by the
        # yielding walls and the narrower larynx
        import grm_voice as v
        p = {"xc": 9.0, "Ac": v.A_OPEN, "Alip": v.A_OPEN, "Llip": 1.0, "Avel": 0.0}
        L = (v.TRACT_LENGTH + 1.0) * v.CM
        found = [F for F, _ in v.resonances(p)][:3]
        for n, F in enumerate(found, start=1):
            assert F == pytest.approx((2 * n - 1) * v.C_AIR / (4 * L), rel=0.12)

    def test_vowel_shapes_give_their_formants(self):
        import grm_voice as v
        for sym in ("i", "a", "u"):
            shape = dict(v.VOWEL_SHAPES[sym], Avel=0.0)
            F = [f for f, _ in v.resonances(shape)][:2]
            assert F[0] == pytest.approx(shape["F"][0], rel=0.03)
            assert F[1] == pytest.approx(shape["F"][1], rel=0.03)
            assert v.VOWEL_MIN_AREA <= shape["Ac"] <= v.A_OPEN          # a human mouth

    def test_nasal_closure_makes_an_antiresonance(self):
        import grm_voice as v
        m = dict(v.VOWEL_SHAPES["a"], Alip=0.0, Avel=0.5)                # lips shut, velum open: [m]
        zeros = v.resonances(m, "zero")
        assert zeros and 700 < zeros[0][0] < 1600                          # the closed mouth, a side branch

    def test_airflow_shares_the_lung_pressure(self):
        import grm_voice as v
        open_ = v.airflow_network(800.0, v.AG_VOICED, 3.0, v.stress_for(110.0))
        shut = v.airflow_network(800.0, v.AG_VOICED, v.CLOSED, v.stress_for(110.0))
        assert open_["dPg"] + open_["dPc"] == pytest.approx(800.0, rel=1e-4)
        assert open_["Avib"] > 0.05 and open_["dPg"] > v.P_TH            # an open mouth: the folds vibrate
        assert shut["dPg"] < v.P_TH and shut["Avib"] < 1e-3              # a closure: the pressure moves forward
        assert open_["f0"] == pytest.approx(110.0 + v.KP * open_["dPg"], rel=1e-3)


class TestPong:
    def test_intercept_network_predicts_the_bounce(self):
        import grm_pong as gp
        # ball at (400, 100) going left and up: it bounces on the top wall before reaching x = 30
        x, y, vx, vy = 400.0, 100.0, -500.0, -300.0
        y_hit, sigma, t = gp.intercept_network(30.0, (x, y, vx, vy), 1e-3, 1e-3)
        assert t == pytest.approx((30.0 - x) / vx, rel=1e-6)
        assert y_hit == pytest.approx(gp.fold(y + vy * t), abs=1e-3)
        assert sigma < 0.1

    def test_paddles_play_and_score(self):
        import grm_pong as gp
        game = gp.PongGame(seed=5)
        hits = 0
        for _ in range(int(120 / gp.DT)):
            before = game.rally
            game.step()
            hits += game.rally > before
        assert hits > 20                                   # they return the ball
        assert sum(game.score.values()) + 11 * sum(game.matches.values()) >= 1   # and points are scored


class TestUncertainties:
    def test_uncertainty_propagates_through_a_power(self):
        # b = a^2, a measured with sigma 0.01 dex  ->  sigma(b) = 0.02 dex
        nodes = {"a": {"guess": 1.0}, "b": {"guess": 1.0}}
        rels = [{"terms": {"b": 1, "a": -2}, "rhs": 0.0, "sigma": 1e-6}]
        out = net(nodes, rels).solve(measured_dict={"a": (5.0, 0.01)})
        assert abs(out["sigma_dex"]["a"] - 0.01) < 1e-6
        assert abs(out["sigma_dex"]["b"] - 0.02) < 1e-6

    def test_two_measurements_combine(self):
        # two measurements of the same node, 0.01 dex each -> sigma 0.01 / sqrt(2), value at the log-middle
        nodes = {"a": {"guess": 1.0}, "b": {"guess": 1.0}}
        rels = [{"terms": {"a": 1, "b": -1}, "rhs": 0.0, "sigma": 1e-6}]
        out = net(nodes, rels).solve(measured_dict={"a": (10.0, 0.01), "b": (10 ** 1.02, 0.01)})
        assert abs(math.log10(out["values"]["a"]) - 1.01) < 1e-6
        assert abs(out["sigma_dex"]["a"] - 0.01 / math.sqrt(2)) < 1e-6
        assert abs(out["reduced_chi2"] - 2.0) < 1e-3   # (0.01 / 0.01)^2 * 2 / 1 dof

    def test_relation_pulls_are_reported(self):
        nodes = {"a": {"guess": 1.0}}
        rels = [{"name": "low", "terms": {"a": 1}, "rhs": 0.0, "sigma": 0.01},
                {"name": "high", "terms": {"a": 1}, "rhs": 0.04, "sigma": 0.01}]
        out = net(nodes, rels).solve()
        assert abs(out["relation_pulls"]["low"] - 2.0) < 1e-6
        assert abs(out["relation_pulls"]["high"] + 2.0) < 1e-6

    def test_leave_one_out_helper(self):
        nodes = {"a": {"guess": 1.0}, "b": {"guess": 1.0}}
        rels = [{"terms": {"b": 1, "a": -2}, "rhs": 0.0, "sigma": 1e-6}]
        rep = net(nodes, rels).leave_one_out({"a": (3.0, 0.001), "b": (9.0, 0.001)})
        assert rel_err(rep["a"]["predicted"], 3.0) < 1e-6 and rep["a"]["determined"]
        assert rel_err(rep["b"]["predicted"], 9.0) < 1e-6 and abs(rep["b"]["pull"]) < 1e-3

    def test_converged_flag(self):
        out = net({"a": {"guess": 5.0}}, [{"terms": {"a": 1}, "rhs": 2.0}]).solve()
        assert out["converged"] is True


# ============================================================================
# 2. PROTOCOL
# ============================================================================

def is_lin(nodes, k):
    return nodes[k].get("scale", "log") == "lin"


def split(m):
    """A measurement is a value, or (value, sigma) with sigma in dex (positive) or value units (signed)."""
    return (m[0], m[1]) if isinstance(m, (tuple, list)) else (m, None)


def distance(nodes, k, a, b):
    """Relative distance for positive nodes, absolute (scaled by max(1, |b|)) for signed nodes."""
    if is_lin(nodes, k):
        return abs(a - b) / max(1.0, abs(b))
    return rel_err(a, b)


def solve_with(nodes, rels, measured, seed_factor=None, rng=None):
    """Solve with the measurements as data; starting points optionally randomised
    (positive nodes by a factor up to 10^seed_factor, signed nodes by up to +-50 %)."""
    if not seed_factor:
        return net(nodes, rels).solve(measured_dict=measured)
    for _ in range(20):  # a random start can fall outside a relation's domain: draw again
        trial = {k: dict(v) for k, v in nodes.items()}
        for k, v in trial.items():
            if v.get("fixed"):
                continue
            if is_lin(trial, k):
                g = v.get("guess", 0.0)
                v["guess"] = g + rng.uniform(-0.5, 0.5) * max(1.0, abs(g))
            else:
                v["guess"] = v.get("guess", 1.0) * 10 ** rng.uniform(-seed_factor, seed_factor)
        try:
            return net(trial, rels).solve(measured_dict=measured)
        except ValueError:
            continue
    return net(nodes, rels).solve(measured_dict=measured)


def leave_one_out(nodes, rels, measured, tol, seeds=3, rng=None, seed_factor=1):
    """One row per measurement: (name, measured, predicted, seed spread, determined, recovered, pull).
    Recovered: |pull| < 2 when the measurement has a sigma, otherwise within the relative tolerance."""
    rng = rng or random.Random(0)
    rows = []
    for hidden, m in measured.items():
        truth, sigma_m = split(m)
        rest = {k: v for k, v in measured.items() if k != hidden}
        runs = [solve_with(nodes, rels, rest, seed_factor=seed_factor, rng=rng) for _ in range(seeds)]
        # a start that ends in a worse minimum is a solver failure, not a sign of indeterminacy:
        # judge on the runs that reach the best cost
        best = min(o["cost"] for o in runs)
        runs = sorted([o for o in runs if o["cost"] <= best * (1 + 1e-6) + 1e-9], key=lambda o: o["cost"])
        preds = [o["values"][hidden] for o in runs]
        try:
            spread = max(distance(nodes, hidden, p, preds[0]) for p in preds)
        except (ValueError, ZeroDivisionError, OverflowError):
            spread = math.inf
        determined = bool(spread < 1e-3 and all(hidden not in o["undetermined"] for o in runs))
        pull = None
        if not is_lin(nodes, hidden) and not (0 < preds[0] < math.inf):
            determined = False  # the value ran off to 0 or infinity: nothing holds it
            preds[0], close = float("nan"), False
        elif sigma_m is not None:
            d = preds[0] - truth if is_lin(nodes, hidden) else math.log10(preds[0]) - math.log10(truth)
            pull = d / math.sqrt(runs[0]["sigma_dex"][hidden] ** 2 + sigma_m ** 2)
            close = abs(pull) < 2
        else:
            close = distance(nodes, hidden, preds[0], truth) < tol.get(hidden, 0.05)
        sig = runs[0]["sigma_dex"][hidden] if determined else math.inf
        rows.append((hidden, truth, preds[0], spread, determined, bool(determined and close), pull, sig))
    return rows


def print_rows(rows):
    print("\n  hidden         measured      predicted     pull     status")
    for h, t, p, s, d, ok, pull, _ in rows:
        status = "ok" if ok else ("NOT DETERMINED (value = starting point)" if not d else "MISSED")
        ps = f"{pull:+.2f}" if pull is not None else "  -  "
        print(f"  {h:<14} {t:<13.5g} {p:<13.5g} {ps:<8} {status}")
    print(f"  recovered {sum(r[5] for r in rows)}/{len(rows)}; "
          f"determined by the rest of the network: {sum(r[4] for r in rows)}/{len(rows)}")


def definition_branches(nodes, rels, measured):
    """Relations that only fix quantities nobody else uses (peeled from the leaves inward):
    they define an output and cannot constrain anything else, so removing them changes nothing."""
    from collections import Counter
    fixed = {k for k, v in nodes.items() if v.get("fixed")}
    alive = {i: (set(r.get("terms", {})) | set(r.get("nodes", []))) - fixed for i, r in enumerate(rels)}
    peeled = set()
    while True:
        count = Counter(n for ns in alive.values() for n in ns)
        out = [i for i, ns in alive.items() if any(count[n] == 1 and n not in measured for n in ns)]
        if not out:
            return peeled
        for i in out:
            peeled.add(i)
            del alive[i]


def idle_relations(nodes, rels, measured, tol):
    """A relation matters if removing it changes what the network says about at least one hidden
    measurement: the prediction moves by more than 0.1 sigma, or its uncertainty grows by more
    than 5 %, or it stops being recovered. Starting points are not randomised here, so that only
    the relation changes between runs.
    Returns {"definitions": ..., "untestable": ..., "redundant": ...} (lists of indices):
      definitions  only fix their own output quantity (expected to change nothing)
      untestable   touch no measured quantity at all
      redundant    neither, yet change nothing: implied by the other relations"""
    base = {r[0]: r for r in leave_one_out(nodes, rels, measured, tol, seeds=1, seed_factor=None)}
    branches = definition_branches(nodes, rels, measured)
    result = {"definitions": [], "untestable": [], "redundant": []}
    for i, rel in enumerate(rels):
        if i in branches:
            result["definitions"].append(i)
            continue
        touched = set(rel.get("terms", {})) | set(rel.get("nodes", []))
        changed = False
        for r in leave_one_out(nodes, rels[:i] + rels[i + 1:], measured, tol, seeds=1, seed_factor=None):
            b0 = base[r[0]]
            if b0[5] and not r[5]:
                changed = True
            elif b0[4] and r[4]:
                shift = abs(math.log10(r[2]) - math.log10(b0[2])) if not is_lin(nodes, r[0]) else abs(r[2] - b0[2])
                if shift > 0.1 * max(b0[7], 1e-12) or r[7] > 1.05 * b0[7]:
                    changed = True
            elif b0[4] != r[4]:
                changed = True
            if changed:
                break
        if not changed:
            result["redundant" if touched & set(measured) else "untestable"].append(i)
    return result


def chance(nodes, rels, measured, tol, draws=20, rng=None):
    """Recoveries with the real values, and with every value scrambled (x10^+-1, or +-100 % if signed)."""
    rng = rng or random.Random(7)
    real = sum(r[5] for r in leave_one_out(nodes, rels, measured, tol, seeds=1, rng=rng, seed_factor=None))
    fake = []
    for _ in range(draws):
        scrambled = {}
        for k, m in measured.items():
            v, sg = split(m)
            v = v + rng.uniform(-1, 1) * max(1.0, abs(v)) if is_lin(nodes, k) else v * 10 ** rng.uniform(-1, 1)
            scrambled[k] = v if sg is None else (v, sg)
        fake.append(sum(r[5] for r in leave_one_out(nodes, rels, scrambled, tol, seeds=1, rng=rng, seed_factor=None)))
    return real, fake


# ---- built-in example 1: Kepler's third law, T^2 = a^3 (years, astronomical units)
PLANETS = {"mercury": (0.387098, 0.240846), "venus": (0.723332, 0.615198), "mars": (1.523679, 1.88085),
           "jupiter": (5.2044, 11.862), "saturn": (9.5826, 29.4571)}
KEPLER_NODES, KEPLER_RELATIONS, KEPLER_MEASURED = {}, [], {}
for _p, (_a, _T) in PLANETS.items():
    KEPLER_NODES[f"a_{_p}"] = {"guess": 1.0}
    KEPLER_NODES[f"T_{_p}"] = {"guess": 1.0}
    KEPLER_RELATIONS.append({"name": f"kepler_{_p}", "terms": {f"T_{_p}": 2, f"a_{_p}": -3}, "rhs": 0.0})
    KEPLER_MEASURED[f"a_{_p}"], KEPLER_MEASURED[f"T_{_p}"] = _a, _T
KEPLER_TOL = {k: 0.01 for k in KEPLER_MEASURED}

# ---- built-in example 2: Planck units from c, hbar, G (values from 1e-44 to 1e8)
PLANCK_NODES = {"c": {"guess": 2.99792458e8, "fixed": True}, "hbar": {"guess": 1.054571817e-34, "fixed": True},
                "G": {"guess": 6.67430e-11}, "lP": {"guess": 1.0}, "tP": {"guess": 1.0}, "mP": {"guess": 1.0}}
PLANCK_RELATIONS = [
    {"name": "length", "terms": {"lP": 2, "hbar": -1, "G": -1, "c": 3}, "rhs": 0.0},   # lP^2 = hbar G / c^3
    {"name": "time", "terms": {"tP": 1, "lP": -1, "c": 1}, "rhs": 0.0},                # tP = lP / c
    {"name": "mass", "terms": {"mP": 2, "hbar": -1, "c": -1, "G": 1}, "rhs": 0.0},     # mP^2 = hbar c / G
]
PLANCK_MEASURED = {"G": 6.67430e-11, "lP": 1.616255e-35, "tP": 5.391247e-44, "mP": 2.176434e-8}
PLANCK_TOL = {k: 1e-4 for k in PLANCK_MEASURED}


class TestProtocolOnExamples:
    def test_kepler_leave_one_out(self):
        rows = leave_one_out(KEPLER_NODES, KEPLER_RELATIONS, KEPLER_MEASURED, KEPLER_TOL)
        print_rows(rows)
        assert all(r[5] for r in rows)

    def test_kepler_every_relation_matters(self):
        res = idle_relations(KEPLER_NODES, KEPLER_RELATIONS, KEPLER_MEASURED, KEPLER_TOL)
        assert res == {"definitions": [], "untestable": [], "redundant": []}

    def test_kepler_beats_chance(self):
        real, fake = chance(KEPLER_NODES, KEPLER_RELATIONS, KEPLER_MEASURED, KEPLER_TOL)
        assert real == len(KEPLER_MEASURED) and max(fake) < real

    def test_planck_units_leave_one_out(self):
        rows = leave_one_out(PLANCK_NODES, PLANCK_RELATIONS, PLANCK_MEASURED, PLANCK_TOL)
        print_rows(rows)
        assert all(r[5] for r in rows)

    def test_planck_units_beat_chance(self):
        real, fake = chance(PLANCK_NODES, PLANCK_RELATIONS, PLANCK_MEASURED, PLANCK_TOL)
        assert real == len(PLANCK_MEASURED) and max(fake) < real

    def test_undetermined_value_is_not_counted_as_recovered(self):
        # 'z' is linked to nothing measured: hiding it must give NOT DETERMINED, never 'ok'
        nodes = {"x": {"guess": 1.0}, "y": {"guess": 1.0}, "z": {"guess": 5.0}}
        rels = [{"terms": {"y": 1, "x": -1}, "rhs": 0.3}, {"terms": {"z": 1, "x": -1, "y": -1}, "rhs": 0.0}]
        rows = leave_one_out(nodes, rels, {"x": 2.0, "z": 5.0}, {})
        z = [r for r in rows if r[0] == "z"][0]
        assert z[4] is True  # z = x * y is determined once x is measured
        rows = leave_one_out(nodes, rels[:1], {"x": 2.0, "z": 5.0}, {})
        z = [r for r in rows if r[0] == "z"][0]
        assert z[4] is False and z[5] is False


SPEC_PATH = os.environ.get("GRM_SPEC")


def load_spec():
    spec = importlib.util.spec_from_file_location("grm_spec", SPEC_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.skipif(not SPEC_PATH, reason="set GRM_SPEC=path/to/model.py to test a full model")
class TestProtocolOnUserModel:
    def test_model_builds(self):
        m = load_spec()
        net(m.NODES, m.RELATIONS)  # raises on unknown names, non-positive values, missing sigma
        unknown = set(m.MEASURED) - set(m.NODES)
        out = net(m.NODES, m.RELATIONS).solve(measured_dict=m.MEASURED)
        print(f"\n  converged: {out['converged']} in {out['iterations']} iterations, "
              f"reduced chi2 = {out['reduced_chi2']:.3f}, undetermined: {out['undetermined']}")
        assert out["converged"]
        assert not unknown, f"unknown measured nodes {unknown}"

    def test_leave_one_out(self):
        m = load_spec()
        rows = leave_one_out(m.NODES, m.RELATIONS, m.MEASURED, getattr(m, "TOLERANCE", {}))
        print_rows(rows)
        # a measurement that nothing else reaches cannot be tested; every other one must be recovered
        missed = [r[0] for r in rows if r[4] and not r[5]]
        assert not missed, f"missed: {missed}"

    def test_every_relation_matters(self):
        """Definitions, untestable theory and redundant identities are reported; a claim or an
        established relation (kind 'claim' / 'standard') that changes nothing fails the test."""
        m = load_spec()
        res = idle_relations(m.NODES, m.RELATIONS, m.MEASURED, getattr(m, "TOLERANCE", {}))
        name = lambda i: m.RELATIONS[i].get("name", f"relation_{i}")
        print(f"\n  definitions (only fix their own output): {len(res['definitions'])}")
        print(f"  untestable (touch no measurement): {[name(i) for i in res['untestable']]}")
        print(f"  redundant (implied by the others): {[name(i) for i in res['redundant']]}")
        idle_tests = [name(i) for i in res["redundant"] + res["untestable"]
                      if m.RELATIONS[i].get("kind") in ("claim", "standard") and i not in res["untestable"]]
        assert not idle_tests, f"claims or established relations that change nothing: {idle_tests}"

    def test_beats_chance(self):
        m = load_spec()
        real, fake = chance(m.NODES, m.RELATIONS, m.MEASURED, getattr(m, "TOLERANCE", {}))
        print(f"\n  recovered with real values: {real}; with scrambled values: "
              f"{sum(fake) / len(fake):.1f} on average (max {max(fake)}) out of {len(m.MEASURED)}")
        assert real > max(fake), "scrambled universes do as well as the real one"


# ============================================================================
# 3. THE WATER TEST
# ============================================================================

def water(angle_in_relation, d1=0.9584, d2=0.9584):
    nodes = {"d_oh1": {"guess": 0.95}, "d_oh2": {"guess": 0.95}, "d_h1h2": {"guess": 1.40}}
    rels = [
        {"name": "Target_Bond_H1", "terms": {"d_oh1": 1.0}, "rhs": math.log10(d1), "sigma": 0.001},
        {"name": "Target_Bond_H2", "terms": {"d_oh2": 1.0}, "rhs": math.log10(d2), "sigma": 0.001},
        {"name": "Angular_Closure_Law", "terms": {"d_h1h2": 1.0, "d_oh1": -0.5, "d_oh2": -0.5},
         "rhs": math.log10(2.0 * math.sin(math.radians(angle_in_relation / 2.0))), "sigma": 0.01},
    ]
    out = net(nodes, rels).solve(max_iterations=10, damping_lambda=1e-3)
    a, b, c = out["values"]["d_oh1"], out["values"]["d_oh2"], out["values"]["d_h1h2"]
    angle = math.degrees(math.acos(max(-1.0, min(1.0, (a * a + b * b - c * c) / (2 * a * b)))))
    return out, angle


class TestWater:
    def test_water_geometry_is_solved(self):
        out, angle = water(104.5)
        assert abs(out["values"]["d_oh1"] - 0.9584) < 1e-4
        assert abs(angle - 104.5) < 1e-6
        assert out["cost"] < 1e-12 and out["converged"]

    @pytest.mark.parametrize("angle_in", [60.0, 90.0, 109.47, 120.0])
    def test_water_angle_is_an_input_not_an_emergence(self, angle_in):
        # The angle is written into the closure relation: the solver gives back whatever is put in.
        _, angle = water(angle_in)
        assert abs(angle - angle_in) < 1e-6

    def test_water_closure_law_only_holds_for_equal_bonds(self):
        # with unequal bonds the same closure relation no longer gives 104.5 degrees
        _, angle = water(104.5, d1=0.9584, d2=1.20)
        assert abs(angle - 104.5) > 1.0


class TestWaterWaves:
    """GRM Water: the waves of a basin from the dispersion network."""

    def test_dispersion_matches_the_formula(self):
        import numpy as np
        import grm_water as w
        ks = np.geomspace(1.0, 2000.0, 12)
        net = w.water_network("Water", 9.81, 0.3, 1.6, 0.7, ks)
        rho, nu, sig = w.LIQUIDS["Water"]
        exact = np.sqrt((9.81 * ks + sig / rho * ks ** 3) * np.tanh(ks * 0.3))
        assert np.max(np.abs(net["w"] / exact - 1)) < 1e-6
        assert np.all(net["gamma"] >= 2 * nu * ks ** 2)          # never less than the bulk viscosity

    def test_known_numbers_of_water(self):
        # capillary length of water ~2.7 mm; slowest ripple ~23 cm/s near 1.7 cm (textbook values)
        import numpy as np
        import grm_water as w
        net = w.water_network("Water", 9.81, 1.0, 1.0, 1.0, np.geomspace(50, 1500, 40))
        assert abs(net["lc"] * 1000 - 2.7) < 0.1
        assert abs(net["cmin"] - 0.231) < 0.003
        c = net["w"] / net["k"]
        lam = 2 * np.pi / net["k"][np.argmin(c)]
        assert 0.014 < lam < 0.020
        assert c.min() >= net["cmin"] * 0.999

    def test_inverse_network_finds_the_wavelength(self):
        import grm_water as w
        deep = w.wavelength_network("Water", 9.81, 10.0, 2.0)        # deep water: lambda = g / (2 pi f^2)
        assert abs(deep["wavelength"] - 9.81 / (2 * 3.141592653589793 * 4)) < 0.002
        shallow = w.wavelength_network("Water", 9.81, 0.02, 0.2)     # shallow water: speed sqrt(g h)
        assert abs(shallow["speed"] / (9.81 * 0.02) ** 0.5 - 1) < 0.02

    def test_drop_keeps_the_level_and_fades(self):
        import numpy as np
        import grm_water as w
        b = w.Basin(*w.BASINS["Bathtub"])
        b.drop(0.8, 0.35, 0.03, 0.005)
        eta, _, _ = b.surface()
        volume = np.trapezoid(np.trapezoid(eta, b.y, axis=1), b.x)
        assert abs(volume) < 1e-6 * np.abs(eta).max() * b.Lx * b.Ly  # no water created or lost
        e0 = b.energy()
        for _ in range(50):
            b.step(0.02)
        assert 0.5 * e0 < b.energy() < e0                            # it dies, slowly
        honey = w.Basin(*w.BASINS["Bathtub"], liquid="Olive oil")
        honey.drop(0.8, 0.35, 0.03, 0.005)
        e1 = honey.energy()
        for _ in range(50):
            honey.step(0.02)
        assert honey.energy() / e1 < b.energy() / e0                 # a viscous liquid calms down faster

    def test_symmetric_drop_gives_symmetric_waves(self):
        import numpy as np
        import grm_water as w
        b = w.Basin(1.0, 1.0, 0.2)
        b.drop(0.5, 0.5, 0.04, 0.005)
        for _ in range(20):
            b.step(0.03)
        eta, _, _ = b.surface()
        assert np.allclose(eta, eta[::-1, :], atol=1e-9) and np.allclose(eta, eta.T, atol=1e-9)


class TestMatter:
    """GRM Matter: from the quantum constants to atoms and simple metals."""

    def test_constants_network_gives_codata(self):
        import grm_matter as m
        c = m.constants_network()["values"]
        assert abs(c["a0"] / 5.29177210903e-11 - 1) < 3e-10        # CODATA 2018 Bohr radius
        assert abs(c["Ha"] / 4.3597447222071e-18 - 1) < 3e-10      # CODATA 2018 Hartree energy

    def test_lda_neon_matches_nist_reference(self):
        # NIST atomic reference data (LDA, VWN): E_tot(Ne) = -128.233481 Ha; here Perdew-Zunger, within 0.05 %
        import grm_matter as m
        E = m.solve_atom(10)["E"]
        assert abs(E / -128.233481 - 1) < 5e-4

    def test_ionization_energies_of_alkali_metals(self):
        import grm_matter as m
        ha_ev = 27.211386
        for Z, sym in ((11, "Na"), (19, "K")):
            ie = m.ionization_energy(Z) * ha_ev
            assert abs(ie / m.MEASURED_IE[sym] - 1) < 0.03

    def test_heavy_alkali_metals_from_first_principles(self):
        import grm_matter as m
        c = m.constants_network()
        for sym in ("K", "Rb"):
            p = m.predict_metal(sym, c)
            assert abs(p["density"] / m.MEASURED_DENSITY[sym] - 1) < 0.15
            assert abs(p["bulk_GPa"] / m.MEASURED_BULK[sym] - 1) < 0.15


class TestRain:
    """GRM Rain: each drop's sound from the drag, impact and bubble networks."""

    def test_terminal_velocity_of_small_drops(self):
        # measured terminal velocities quoted by Prosperetti & Oguz (1993): 0.8 mm 3.28, 0.9 mm 3.66,
        # 1.0 mm 4.01, 1.2 mm 4.65 m/s
        import grm_rain as r
        for d, v in ((0.8e-3, 3.28), (0.9e-3, 3.66), (1.0e-3, 4.01), (1.2e-3, 4.65)):
            assert abs(r.terminal_network(d) / v - 1) < 0.06

    def test_which_drops_ring(self):
        import grm_rain as r
        p = r.RainPhysics()
        kinds = {d: p.regime(d, p.terminal(d)) for d in (0.6e-3, 0.95e-3, 1.5e-3, 3e-3)}
        assert kinds == {0.6e-3: "none", 0.95e-3: "regular", 1.5e-3: "none", 3e-3: "large"}

    def test_minnaert_bubble(self):
        import grm_rain as r
        f, delta = r.bubble_network(1e-3)
        assert abs(f / 3260 - 1) < 0.02                  # f R = 3.26 m/s for air in water at 1 atm
        f14, d14 = r.bubble_network(r.RainPhysics().R14)
        assert abs(f14 / 14000 - 1) < 1e-3 and 0.03 < d14 < 0.12

    def test_light_rain_is_heard_high_heavy_rain_low(self):
        import numpy as np
        import grm_rain as r

        def shares(rate):
            a, _ = r.render_rain(3.0, rate, 1.0, seed=1)
            spec = np.abs(np.fft.rfft(a)) ** 2
            f = np.fft.rfftfreq(len(a), 1 / r.SAMPLE_RATE)
            return spec[(f > 13e3) & (f < 25e3)].sum() / spec.sum(), spec[(f > 1e3) & (f < 1e4)].sum() / spec.sum()
        hi_light, lo_light = shares(2.0)
        hi_heavy, lo_heavy = shares(25.0)
        assert hi_light > lo_light                       # drizzle: the 13-25 kHz bubbles dominate
        assert lo_heavy > hi_heavy                       # heavy rain: the large drops' low bubbles take over


class TestExplorer:
    """grm_explorer.py: JSON -> network -> report, and its presets (grm_presets.py)."""

    def test_known_presets_reproduce_their_expected_values(self):
        from grm_explorer import preset_document, solve_document
        from grm_presets import PRESETS
        for p in PRESETS:
            if p["category"] != "known":
                continue
            report = solve_document(preset_document(p))
            assert report["valid"] is True, (p["id"], report["checks"])
            assert report["result"]["converged"], p["id"]

    def test_open_presets_show_the_tension_and_the_hypotheses_absorb_it(self):
        from grm_explorer import preset_document, solve_document
        from grm_presets import by_id
        for data_only in ("hubble_tension", "neutron_lifetime"):
            report = solve_document(preset_document(by_id(data_only)))
            assert report["consistent"] is False, data_only
            assert abs(report["pulls"][0][1]) > 4.0
        h = solve_document(preset_document(by_id("hubble_sound_horizon")))
        assert h["consistent"] and 0.90 < h["result"]["values"]["r_ratio"] < 0.95
        n = solve_document(preset_document(by_id("neutron_dark_decay")))
        assert n["consistent"] and 0.985 < n["result"]["values"]["Br_p"] < 0.992
        k = solve_document(preset_document(by_id("koide_tau")))
        assert abs(k["result"]["values"]["mtau"] - 1776.969) < 0.01

    def test_expressions_are_safe(self):
        from grm_explorer import compile_expression
        f, used = compile_expression("x - 5 * (1 - exp(-x))", {"x", "y"})
        assert used == ["x"] and abs(f({"x": 4.965114231744276})) < 1e-12
        for bad in ("__import__('os')", "x.real", "open('f')", "[x]", "y if x else 1", "'a'"):
            with pytest.raises((ValueError, SyntaxError)):
                compile_expression(bad, {"x", "y"})

    def test_checks_and_old_json(self):
        from grm_explorer import solve_document
        doc = {"nodes": {"x": {"guess": 1, "scale": "linear", "measured": [3.0, 1e-6]},
                         "y": {"guess": 1, "expected": 9.0, "tolerance": 1e-6}},
               "relations": [{"name": "square", "type": "fn", "expr": "y - x**2", "sigma": 1e-9}]}
        assert solve_document(doc)["valid"] is True
        doc["nodes"]["y"]["expected"] = 10.0
        report = solve_document(doc)
        assert report["valid"] is False and not report["checks"][0]["ok"]
        with pytest.raises(ValueError):
            solve_document({"nodes": {"x": {"guess": 1}}, "relations": [{"name": "r", "terms": {"z": 1}}]})
