# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Anthony Charretier
"""Tests of the GRM virtual machine.   python -m pytest vm/test_vm.py"""
import json
import math
import os
import random
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from language import Network, TalkError, statement   # noqa: E402
from runtime import Machine   # noqa: E402
import body   # noqa: E402
import grm_vm   # noqa: E402


def say(net, text, base=HERE):
    for line in text.splitlines():
        statement(net, line, base)
    return net


def run_until(m, name, value, limit=10000):
    for _ in range(limit):
        if abs(m.value(name) - value) < 1e-6:
            return True
        m.tick()
        m.run()
    return False


# ---------------------------------------------------------------------- Turing completeness
def minsky(program, counters):
    """A Minsky machine (registers and two instructions) written in the machine's language: any one can be.
    program: {line: ("inc", r, next) | ("dec", r, next_if_not_zero, next_if_zero) | ("halt",)}."""
    lines = ["var s = 0"] + [f"var {r} = {v}" for r, v in counters.items()]
    for k, ins in program.items():
        at = f"s in {k - 0.5} .. {k + 0.5}"
        if ins[0] == "inc":
            _, r, nxt = ins
            lines += [f"set {r} = {r} + 1 when {at}", f"set s = {nxt} when {at}"]
        elif ins[0] == "dec":
            _, r, nz, z = ins
            lines += [f"set {r} = {r} - 1 when {at} and {r} in 0.5 .. inf",
                      f"set s = {nz} when {at} and {r} in 0.5 .. inf",
                      f"set s = {z} when {at} and {r} in -0.5 .. 0.5"]
    return "\n".join(lines)


HALT = 99


def run_minsky(program, counters, limit=5000):
    m = Machine(say(Network(), minsky(program, counters)))
    for t in range(limit):
        m.tick()
        m.run()
        if abs(m.value("s") - HALT) < 0.5:
            return m, t + 1
    raise AssertionError("the machine did not halt")


def test_double_program():
    m = Machine(say(Network(), "use programs/double.grm"))
    assert run_until(m, "s", 9)
    assert m.value("b") == pytest.approx(10, abs=1e-6)


def test_minsky_addition_and_multiplication():
    add = {0: ("dec", "b", 1, HALT), 1: ("inc", "a", 0)}                       # a <- a + b
    m, _ = run_minsky(add, {"a": 7, "b": 5})
    assert m.value("a") == pytest.approx(12, abs=1e-6) and m.value("b") == pytest.approx(0, abs=1e-6)
    mul = {0: ("dec", "a", 1, HALT),                                             # c <- a * b
           1: ("dec", "b", 2, 4), 2: ("inc", "c", 3), 3: ("inc", "t", 1),
           4: ("dec", "t", 5, 0), 5: ("inc", "b", 4)}
    m, ticks = run_minsky(mul, {"a": 6, "b": 7, "c": 0, "t": 0})
    assert m.value("c") == pytest.approx(42, abs=1e-6)
    assert m.value("b") == pytest.approx(7, abs=1e-6)                           # b given back


def test_loop_and_choice():
    m = Machine(say(Network(), "use programs/count.grm"))
    for _ in range(30):
        m.tick()
    m.run()
    assert m.value("n") == pytest.approx(10, abs=1e-6)                          # the loop stopped at 10


def test_gated_relation():
    m = Machine(say(Network(), """var s = 0
input x = 3
relate a: y = 2 * x when s in -0.5 .. 0.5
relate b: y = 3 * x when s in 0.5 .. 1.5"""))
    m.run()
    assert m.value("y") == pytest.approx(6, abs=1e-6)
    m.observe("s", 1.0, 1e-9)
    m.run()
    assert m.value("y") == pytest.approx(9, abs=1e-6)


def test_nonlinear_terms():
    m = Machine(say(Network(), """input x = 3
input y = -2
relate p: z = x * y + x^2"""))
    m.run()
    assert m.value("z") == pytest.approx(3.0, abs=1e-6)


# ---------------------------------------------------------------------- learning
def test_learns_from_a_file_and_remembers(tmp_path):
    rng = random.Random(3)
    rows = []
    for _ in range(150):
        x = rng.uniform(-5, 5)
        rows.append({"x": x, "y": -1.5 * x + 4 + rng.gauss(0, 0.3)})
    data = tmp_path / "rows.json"
    data.write_text(json.dumps(rows))
    mem = str(tmp_path / "memory.json")
    vm = grm_vm.VM(memory=mem, blank=True)
    for line in ["learn k = 0", "learn c = 0", "input x", "input y", "output y", "relate model: y = k * x + c ± 0.3"]:
        vm.say(line)
    vm.load(str(data))
    assert vm.get("k") == pytest.approx(-1.5, abs=0.05) and vm.get("c") == pytest.approx(4, abs=0.1)
    vm.sleep()
    again = grm_vm.VM(memory=mem)                                                # the next session
    assert again.get("k") == pytest.approx(vm.get("k"), abs=1e-9)
    again.say("forget y")
    again.put("x", 2.0)
    assert again.get("y") == pytest.approx(-1.5 * 2 + 4, abs=0.15)              # what it learned, used


def test_csv(tmp_path):
    p = tmp_path / "d.csv"
    rng = random.Random(1)
    p.write_text("x,y\n" + "".join(f"{x},{2 * x + 1}\n" for x in [rng.uniform(-3, 3) for _ in range(50)]))
    vm = grm_vm.VM(memory=None, blank=True)
    for line in ["learn k = 0", "learn c = 0", "input x", "input y", "relate model: y = k * x + c ± 0.01"]:
        vm.say(line)
    out = vm.load(str(p))
    assert "50 rows learned" in out
    assert vm.get("k") == pytest.approx(2, abs=0.01) and vm.get("c") == pytest.approx(1, abs=0.02)


# ---------------------------------------------------------------------- memory, units, body
def test_sleep_and_wake_go_on_exactly(tmp_path):
    def machine():
        m = Machine(say(Network(), "use programs/double.grm"))
        return m

    a = machine()
    for _ in range(7):
        a.tick()
    path = str(tmp_path / "m.json")
    a.sleep(path)
    b = Machine.wake(path)
    assert b.ticks == 7
    for m in (a, b):
        for _ in range(20):
            m.tick()
        m.run()
    assert a.value("b") == b.value("b") == pytest.approx(10, abs=1e-6)


def test_units_inside_are_the_machines_own():
    pytest.importorskip("pygrm")
    vm = grm_vm.VM(memory=None, blank=True)
    vm.say("input g positive [0 1 -2 0 0]")
    vm.say("input T positive [0 0 1 0 0]")
    vm.say("output h positive [0 1 0 0 0]")
    vm.say("relate fall: 2 * h = g * T^2")
    vm.put("g", 9.81)                                       # given in SI
    vm.put("T", 2.0)
    assert vm.get("h") == pytest.approx(19.62, rel=1e-6)    # read back in SI
    assert vm.m().value("g") < 1e-40                        # inside: the machine's units (c = hbar = G = kB = 1)



def test_signed_nodes_with_dimensions():
    """A velocity, a time, positions: signed, with their dimensions, given and read in SI; inside, in the machine's
    own units (a meter is about 6e34 of them), with uncertainties that follow the unit."""
    pytest.importorskip("pygrm")
    vm = grm_vm.VM(memory=None, blank=True)
    for line in ["input v [0 1 -1 0 0]", "input t [0 0 1 0 0]", "input x0 [0 1 0 0 0]", "output x [0 1 0 0 0]",
                 "relate move: x = x0 + v * t"]:
        vm.say(line)
    vm.put("v", -3.0)
    vm.put("t", 2.0)
    vm.put("x0", 10.0)
    assert vm.get("x") == pytest.approx(4.0, abs=1e-5)
    assert abs(vm.m().value("x")) > 1e30                    # 4 m inside: about 2.5e35 Planck lengths


def test_body_sound():
    hist = {"a": [0.0, 1.0, 2.0], "b": [5.0, 5.0, 5.0]}
    s = body.sound_of(hist)
    assert s and max(abs(v) for v in s) <= 1.0
    assert body.sound_of({"b": [5.0, 5.0]}) == []           # a network that holds still is silent


def test_shell(capsys, tmp_path):
    vm = grm_vm.VM(memory=str(tmp_path / "mem.json"), blank=True)
    sh = grm_vm.Shell(vm)
    sh.onecmd("use programs/count.grm")
    sh.onecmd("")                                            # Enter: one tick
    sh.onecmd("tick 20; outputs; ask n")
    out = capsys.readouterr().out
    assert "n = 10" in out
    assert sh.onecmd("quit") is True and os.path.exists(tmp_path / "mem.json")


# ---------------------------------------------------------------------- inspired by the brain
def test_weights_learn_together(tmp_path):
    """Weights that share a relation keep what they learn together (their link): 4 exact rows are enough."""
    p = tmp_path / "d.csv"
    p.write_text("x,y\n1,3\n2,5\n-1,-1\n0.5,2\n")
    vm = grm_vm.VM(memory=None, blank=True)
    for line in ["learn k = 0", "learn c = 0", "input x", "input y", "relate model: y = k * x + c ± 0.01"]:
        vm.say(line)
    vm.load(str(p))
    assert vm.get("k") == pytest.approx(2, abs=0.01) and vm.get("c") == pytest.approx(1, abs=0.01)


def test_same_as_least_squares():
    np = pytest.importorskip("numpy")
    import csv
    vm = grm_vm.VM(memory=None, blank=True)
    for line in ["learn k = 0", "learn c = 0", "input x", "input y", "relate model: y = k * x + c ± 0.5"]:
        vm.say(line)
    vm.load(os.path.join(HERE, "programs", "measures.csv"))
    rows = [(float(r["x"]), float(r["y"])) for r in csv.DictReader(open(os.path.join(HERE, "programs", "measures.csv")))]
    A = np.array([[x, 1.0] for x, _ in rows])
    k, c = np.linalg.lstsq(A, np.array([y for _, y in rows]), rcond=None)[0]
    assert vm.get("k") == pytest.approx(k, abs=1e-3) and vm.get("c") == pytest.approx(c, abs=1e-3)


def test_surprise():
    vm = grm_vm.VM(memory=None, blank=True)
    for line in ["learn k = 0", "learn c = 0", "input x", "input y", "relate model: y = k * x + c ± 0.1"]:
        vm.say(line)
    rng = random.Random(5)
    for _ in range(60):
        x = rng.uniform(-3, 3)
        vm.put("x", x)
        vm.put("y", 2 * x + 1 + rng.gauss(0, 0.1))
        vm.tick(learn=True)
    usual = vm.history["surprise"][-1]
    vm.put("x", 1.0)
    vm.put("y", 40.0)                          # nothing like what it has learned
    vm.tick(learn=True)
    assert vm.history["surprise"][-1] > 20 * max(usual, 0.5)


def test_fuse_writes_no_node_twice():
    net = say(Network(), """input temperature
input T
relate a: heat = 2 * temperature
relate b: glow = 3 * T""")
    statement(net, "fuse temperature T")
    assert "T" not in net.nodes
    assert net.relation("b")["terms"][1][1] == {"temperature": 1.0}
    m = Machine(net)
    m.observe("temperature", 10.0, 1e-6)
    m.run()
    assert m.value("heat") == pytest.approx(20, abs=1e-6) and m.value("glow") == pytest.approx(30, abs=1e-6)


def test_born_with_a_base_and_finds_its_points(tmp_path):
    pytest.importorskip("pygrm")
    vm = grm_vm.VM(memory=str(tmp_path / "m.json"))
    assert "born with its base" in vm.note
    assert vm.m().value("planck_length") == pytest.approx(1.0, rel=1e-6)         # its own unit of length
    assert vm.get("earth_gravity") == pytest.approx(9.82, rel=1e-3)              # G M / R^2, read in SI
    assert "blank" in grm_vm.VM(memory=None, blank=True).note


def test_fuses_by_itself_and_remembers(tmp_path):
    """No node written twice: the machine fuses by itself what is one thing under two names, and remembers it."""
    pytest.importorskip("pygrm")
    mem = str(tmp_path / "m.json")
    vm = grm_vm.VM(memory=mem)
    p = tmp_path / "fall.csv"
    p.write_text("g,h,height\n" + "".join(f"9.8,{h},{h}\n" for h in range(1, 7)))
    out = vm.load(str(p))
    assert "g is earth_gravity" in out and "height is h" in out
    assert "g" not in vm.net.nodes and "height" not in vm.net.nodes
    vm.put("g", 9.81)                                   # the old name still reaches the node
    assert vm.net.measured["earth_gravity"][0] == 9.81
    q = tmp_path / "price.csv"
    q.write_text("price\n70\n70\n70\n")
    assert "fused" not in vm.load(str(q))               # 70 is also a human mass, but one known to 20 %: no fusion
    vm.sleep(night=True)
    again = grm_vm.VM(memory=mem)
    assert again.net.aliases["g"] == "earth_gravity"
    again.say("node double [0 1 -2 0 0]")
    again.say("relate twice: double = 2 * g")           # a statement with the old name: the fused node
    assert again.get("double") == pytest.approx(2 * 9.81, rel=1e-6)


def test_a_night_loosens_what_was_learned(tmp_path):
    mem = str(tmp_path / "m.json")
    vm = grm_vm.VM(memory=mem, blank=True)
    for line in ["learn k = 0", "input x", "input y", "relate model: y = k * x ± 0.1"]:
        vm.say(line)
    for x in (1.0, 2.0, 3.0, 4.0):
        vm.put("x", x)
        vm.put("y", 2 * x)
        vm.tick(learn=True)
    vm.put("x", 0.0)                                  # an input that says nothing of k: the last row is kept
    vm.tick()
    vm.say("forget y")
    s_day = vm.m().sigma("k")
    vm.sleep(night=True)
    after = grm_vm.VM(memory=mem)
    assert after.get("k") == pytest.approx(2, abs=1e-3)                          # what it learned stays
    assert after.m().sigma("k") == pytest.approx(s_day / math.sqrt(grm_vm.NIGHT), rel=0.05)   # a little looser


# ---------------------------------------------------------------------- the examples of docs/GRML.md
def example(name, blank=True):
    vm = grm_vm.VM(memory=None, blank=blank)
    vm.say(f"use programs/{name}.grm")
    return vm


def test_example_hello():
    assert example("hello").get("speed") == pytest.approx(100 / 9.58, rel=1e-6)


def test_example_fall():
    pytest.importorskip("pygrm")
    assert example("fall").get("height") == pytest.approx(19.62, rel=1e-6)


def test_example_fibonacci():
    vm = example("fibonacci")
    vm.tick(10)
    assert vm.get("b") == pytest.approx(89, abs=1e-6)


def test_example_thermostat():
    vm = example("thermostat")
    rooms = []
    for _ in range(60):
        vm.tick()
        rooms.append(vm.get("room"))
    late = rooms[20:]
    assert 16 < min(late) < 19 and 21 < max(late) < 24          # it swings around the band, one tick late
    assert any(abs(vm.history["heater"][k] - vm.history["heater"][k - 1]) > 0.5 for k in range(30, 60))


def test_example_circles():
    vm = example("circles")
    assert vm.get("area_small") == pytest.approx(math.pi, rel=1e-6)
    assert vm.get("area_big") == pytest.approx(9 * math.pi, rel=1e-6)


def test_example_mean():
    vm = example("mean")
    vm.load(os.path.join(HERE, "programs", "numbers.csv"))
    vals = [float(v) for v in open(os.path.join(HERE, "programs", "numbers.csv")).read().split()[1:]]
    assert vm.get("mu") == pytest.approx(sum(vals) / len(vals), abs=1e-6)
    assert vm.m().sigma("mu") == pytest.approx(1 / math.sqrt(len(vals)), rel=0.02)   # 1 / sqrt(n): sure as it should be


def test_example_fit_and_double():
    vm = example("fit")
    vm.load(os.path.join(HERE, "programs", "measures.csv"))
    assert vm.get("k") == pytest.approx(3, abs=0.05)
    vm = example("double")
    vm.tick(20)
    assert vm.get("b") == pytest.approx(10, abs=1e-6) and vm.get("s") == pytest.approx(9, abs=1e-6)


# ---------------------------------------------------------------------- what the machine does by itself
def csv_of(tmp_path, name, header, rows):
    p = tmp_path / name
    p.write_text(header + "\n" + "".join(",".join(repr(v) for v in r) + "\n" for r in rows))
    return str(p)


def test_finds_relations_by_itself(tmp_path):
    pytest.importorskip("pygrm.discover")
    rng = random.Random(1)
    vm = grm_vm.VM(memory=str(tmp_path / "m.json"), blank=True)
    ts = [rng.uniform(0.3, 3) for _ in range(30)]
    out = vm.load(csv_of(tmp_path, "fall.csv", "t,h", [(t, 4.905 * t * t * (1 + rng.gauss(0, 0.001))) for t in ts]))
    assert "found by itself: h = 4.9" in out and "t^2" in out
    vm.say("forget h")
    vm.put("t", 3.0)
    assert vm.get("h") == pytest.approx(4.905 * 9, rel=1e-3)          # it uses what it found
    again = vm.load(csv_of(tmp_path, "fall2.csv", "t,h", [(t, 4.905 * t * t) for t in ts]))
    assert "found by itself" not in again                              # already tied: no echo
    vm.sleep(night=True)
    assert any(r["name"].startswith("found_") for r in grm_vm.VM(memory=str(tmp_path / "m.json")).net.relations)


def test_finds_nothing_in_noise(tmp_path):
    pytest.importorskip("pygrm.discover")
    rng = random.Random(2)
    vm = grm_vm.VM(memory=None, blank=True)
    out = vm.load(csv_of(tmp_path, "n.csv", "a,b,c", [(rng.uniform(1, 9), rng.uniform(1, 9), rng.uniform(-9, 9))
                                                        for _ in range(40)]))
    assert "found" not in out and "nobody" not in out and not vm.net.relations


def test_a_node_nobody_mentioned(tmp_path):
    pytest.importorskip("pygrm.discover")
    rng = random.Random(3)
    vm = grm_vm.VM(memory=None, blank=True)
    for line in ["input x", "input y", "relate model: y = 2 * x ± 0.1"]:
        vm.say(line)
    xs = [rng.uniform(-3, 3) for _ in range(40)]
    out = vm.load(csv_of(tmp_path, "d.csv", "x,y", [(x, 2 * x + 5 + rng.gauss(0, 0.1)) for x in xs]))
    assert "a node nobody mentioned: hidden_1" in out
    vm.say("forget y")
    vm.put("x", 1.0)
    assert vm.get("y") == pytest.approx(7, abs=0.1)
    clean = grm_vm.VM(memory=None, blank=True)
    for line in ["input x", "input y", "relate model: y = 2 * x ± 0.1"]:
        clean.say(line)
    out = clean.load(csv_of(tmp_path, "c.csv", "x,y", [(x, 2 * x + rng.gauss(0, 0.1)) for x in xs]))
    assert "nobody" not in out                                          # nothing missing, nothing invented


def test_example_falling():
    pytest.importorskip("pygrm.discover")
    vm = grm_vm.VM(memory=None, blank=True)
    out = vm.load(os.path.join(HERE, "programs", "falling.csv"))
    assert "found by itself: h = 4.9" in out
    vm.say("forget h")
    vm.put("t", 3.0)
    assert vm.get("h") == pytest.approx(44.15, rel=2e-3)


# ---------------------------------------------------------------------- beyond power laws and lines
def test_finds_an_exponential_and_a_sum(tmp_path):
    pytest.importorskip("pygrm.discover")
    rng = random.Random(4)
    vm = grm_vm.VM(memory=None, blank=True)
    xs = [rng.uniform(-2, 2) for _ in range(30)]
    out = vm.load(csv_of(tmp_path, "g.csv", "x,growth", [(x, 2 * math.exp(0.5 * x)) for x in xs]))
    assert "growth = 2 * e^(0.5 * x)" in out
    vm.say("forget growth")
    vm.put("x", 1.0)
    assert vm.get("growth") == pytest.approx(2 * math.exp(0.5), rel=1e-6)
    vm = grm_vm.VM(memory=None, blank=True)
    rows = []
    for _ in range(40):
        m, v, h = rng.uniform(1, 5), rng.uniform(0.5, 4), rng.uniform(0.1, 3)
        rows.append((m, v, h, 0.5 * m * v * v + 9.81 * m * h))
    out = vm.load(csv_of(tmp_path, "E.csv", "m,v,h,E", rows))       # E: a name, not Euler's number
    assert "9.81 * h * m + 0.5 * m * v^2" in out
    vm.say("forget E")
    vm.put("m", 2.0)
    vm.put("v", 3.0)
    vm.put("h", 1.0)
    assert vm.get("E") == pytest.approx(0.5 * 2 * 9 + 9.81 * 2, rel=1e-6)
    assert "m_v2" in vm.net.nodes and "h_m" in vm.net.nodes        # each product its own node


def test_finds_an_oscillation_and_carries_it_on(tmp_path):
    pytest.importorskip("pygrm.discover")
    rng = random.Random(4)
    xs, theta, rr = [1.0, 0.95], 2 * math.pi / 25, 0.995
    for _ in range(120):
        xs.append(2 * rr * math.cos(theta) * xs[-1] - rr * rr * xs[-2] + rng.gauss(0, 1e-5))
    vm = grm_vm.VM(memory=None, blank=True)
    out = vm.load(csv_of(tmp_path, "w.csv", "wave", [(x,) for x in xs]))
    assert "an oscillation: period 25 moments" in out
    vm.say("forget wave")                 # no more data: the machine carries the wave on by itself
    a, b = xs[-1], xs[-2]
    true = []
    for _ in range(11):
        a, b = 2 * rr * math.cos(theta) * a - rr * rr * b, a
        true.append(a)
    got = []
    for _ in range(10):
        vm.tick()
        got.append(vm.get("wave"))        # after a tick, the machine is already at the next moment
    assert max(abs(g - t) for g, t in zip(got, true[1:])) < 1e-3


def test_a_node_that_changes(tmp_path):
    pytest.importorskip("pygrm.discover")
    rng = random.Random(4)
    vm = grm_vm.VM(memory=None, blank=True)
    for line in ["input x", "input y", "relate model: y = 2 * x ± 0.1"]:
        vm.say(line)
    drift, rows = 0.0, []
    for _ in range(180):
        drift = 0.95 * drift + rng.gauss(0, 0.5)
        x = rng.uniform(-3, 3)
        rows.append((x, 2 * x + drift + rng.gauss(0, 0.1)))
    out = vm.load(csv_of(tmp_path, "d1.csv", "x,y", rows[:120]))
    assert "a node nobody mentioned, that changes: drift_1" in out
    h0 = len(vm.history["surprise"])
    vm.load(csv_of(tmp_path, "d2.csv", "x,y", rows[120:]))
    with_drift = sorted(vm.history["surprise"][h0:])[30]
    plain = grm_vm.VM(memory=None, blank=True)
    for line in ["input x", "input y", "relate model: y = 2 * x ± 0.1"]:
        plain.say(line)
    plain.load(csv_of(tmp_path, "d3.csv", "x,y", rows[120:]))
    without = sorted(plain.history["surprise"])[30]
    assert with_drift < 2.0 < 10.0 < without                         # it follows what it could not see


def test_fuses_an_inverse(tmp_path):
    pytest.importorskip("pygrm.discover")
    rng = random.Random(2)
    vm = grm_vm.VM(memory=None, blank=True)
    ts = [rng.uniform(0.1, 2) for _ in range(20)]
    out = vm.load(csv_of(tmp_path, "o.csv", "period,frequency,energy", [(t, 1 / t, 3 * t ** -2) for t in ts]))
    assert "frequency is period^-1" in out and "frequency" not in vm.net.nodes
    vm.say("forget energy")
    vm.put("frequency", 4.0)              # given as a frequency, held as its period
    assert vm.get("period") == pytest.approx(0.25, rel=1e-6)
    assert vm.get("energy") == pytest.approx(3 * 16, rel=1e-4)


def test_example_wave():
    pytest.importorskip("pygrm.discover")
    vm = grm_vm.VM(memory=None, blank=True)
    out = vm.load(os.path.join(HERE, "programs", "wave.csv"))
    assert "an oscillation: period 25 moments" in out
