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


# ---------------------------------------------------------------------- what it says when something is wrong
import editor   # noqa: E402
import graph   # noqa: E402
import mind   # noqa: E402


def shell_of(vm):
    out = []

    class W:
        def write(self, s):
            out.append(s)

        def flush(self):
            pass
    return grm_vm.Shell(vm, out=W()), out


def test_an_error_in_a_file_says_where(tmp_path):
    p = tmp_path / "bad.grm"
    p.write_text("node a = 2\nrelate r: a = b\nobserve a = -3\n", encoding="utf-8")
    with pytest.raises(TalkError) as e:
        say(Network(), f"use {p}")
    assert "bad.grm, line 3" in str(e.value) and "observe a = -3" in str(e.value)


def test_a_typo_is_said():
    vm = grm_vm.VM(memory=None, blank=True)
    sh, out = shell_of(vm)
    sh.onecmd("use programs/fall.grm")
    sh.onecmd("relate oops: heigt = g * t")
    assert any("'heigt' is a new node; did you mean 'height'" in s for s in out)
    sh.onecmd("tikc")
    assert any("did you mean tick" in s for s in out)
    sh.onecmd("ask heigth")
    assert any("no node heigth; did you mean" in s and "'height'" not in s and "height" in s for s in out)


def test_an_error_inside_the_machine_is_said_not_a_crash():
    vm = grm_vm.VM(memory=None, blank=True)
    sh, out = shell_of(vm)

    def broken(arg):
        return 1 / 0
    sh.do_broken = broken
    assert sh.onecmd("broken") is False
    assert any("error inside the machine: ZeroDivisionError" in s and "line" in s for s in out)
    assert vm.net.mood["dopamine"] < 0                       # and it is felt: displeasure


def test_contradiction_is_said():
    vm = grm_vm.VM(memory=None, blank=True)
    for line in ["relate a: x = 2 * y", "relate b: x = 3 * y", "observe y = 1"]:
        vm.say(line)
    vm.tick(max_rounds=300)
    said = " ".join(vm.pop_events())
    assert "did not settle" in said and "relation a does not hold" in said and "relation b does not hold" in said
    vm.tick(max_rounds=300)
    assert not any("does not hold" in s for s in vm.pop_events())        # said once, not at every tick


def test_found_weights_carry_the_dimension_that_balances_them(tmp_path):
    pytest.importorskip("pygrm.discover")
    vm = example("fall")
    vm.load(os.path.join(HERE, "programs", "falling.csv"))
    assert vm.net.nodes["K_1"]["dim"] == [0, 0, -2, 0, 0]
    assert 1 < vm.get("t") < 4                      # it was pushed to 1e-29 s by a relation without dimension
    assert vm.get("K_1") == pytest.approx(4.906, rel=1e-3)


# ---------------------------------------------------------------------- writing to it
def test_colours_of_a_line():
    kinds = {kind for _, _, kind in editor.tokens("relate r: y = 2 * x ± 1% when s in 0 .. 1  # why",
                                                   nodes=["x", "y", "s"], commands=["tick"])}
    assert {"statement", "node", "number", "sigma", "keyword", "range", "comment", "new"} <= kinds
    assert editor.tokens("tick 3", commands=["tick"])[0][2] == "command"
    assert editor.tokens("node a; ask a", nodes=["a"], commands=["ask"])[-2][2] == "command"   # after ;


def test_tab_completes():
    assert editor.complete("ins", 3, commands=["inspect", "input", "tick"]) == (0, ["inspect"])
    assert editor.complete("in", 2, commands=["inspect", "tick"])[1] == ["input", "inspect"]
    assert editor.complete("relate r: hei", 13, nodes=["height", "g"]) == (10, ["height"])
    assert "programs/fall.grm" in editor.complete("use programs/fa", 15, base=HERE)[1]
    assert "programs/falling.csv" in editor.complete("load programs/fa", 16, base=HERE)[1]
    vm = grm_vm.VM(memory=None, blank=True)
    sh, _ = shell_of(vm)
    vm.say("node height")
    assert sh.completedefault("hei", "ask hei", 4, 7) == ["height"]


def test_banner():
    assert "the Global Relational Model machine" in editor.banner("utf-8")
    assert editor.banner("ascii") == editor.BANNER_ASCII


# ---------------------------------------------------------------------- the network seen
def test_picture_and_cards():
    vm = example("fall")
    vm.get("height")
    places = graph.layout(vm.net, {}, steps=40)
    assert set(places) == {("n", n) for n in vm.net.nodes} | {("r", "fall")}
    assert all(math.isfinite(v) for p in places.values() for v in p)
    card = "\n".join(graph.node_card(vm, "height"))
    assert "value  19.62" in card and "[0 1 0 0 0]" in card and "fall" in card
    card = "\n".join(graph.relation_card(vm, "fall"))
    assert "2 * height = g * t^2" in card and "(holds)" in card


# ---------------------------------------------------------------------- what it feels and keeps
def test_master_equation_now_and_before():
    pytest.importorskip("pygrm")
    vm = example("fall")
    now = mind.master(vm)
    assert now["text"] == "g · t^2 · height^-1 = 2" and now["residual"] < 1e-9
    vm.say("relate run: distance = height * 3")
    vm.say("observe distance = 58.86")
    vm.tick(3)
    assert "distance" in mind.master(vm)["text"] or "height" in mind.master(vm)["text"]
    before = mind.master(vm, 2)
    assert before["tick"] == vm.net.ticks - 2
    assert "only the last" in mind.master(vm, 10_000)["text"]


def test_traces_fade_and_what_works_is_kept():
    vm = example("double")
    vm.tick(5)
    use = vm.net.use["relations"]
    worked = [r for r in use if use[r] > mind.NEW_TRACE]
    assert worked                                         # the relations that computed gained
    old = dict(use)
    vm.net.relations.append({"kind": "product", "name": "idle", "terms": {"q": 1.0}, "rhs": 0.0, "sigma": 1e-9,
                             "text": "q = 1", "when": []})
    vm.net.nodes["q"] = {"guess": 1.0, "fixed": False, "signed": False}
    vm.machine = None
    vm.tick(1)                                            # rebuilt: everything works once
    first = vm.net.use["relations"]["idle"]
    vm.tick(3)
    assert vm.net.use["relations"]["idle"] < first                       # then nothing uses it: it fades
    assert all(vm.net.use["relations"][r] > 0 for r in old)


def test_no_room_it_forgets_the_least_used_never_the_base():
    pytest.importorskip("pygrm.discover")
    vm = grm_vm.VM(memory=None)                                  # born with its base
    base_links = mind.links(vm.net)
    vm.load(os.path.join(HERE, "programs", "falling.csv"))
    assert vm.net.relation("found_1") and "K_1" in vm.net.nodes
    sh, out = shell_of(vm)
    sh.onecmd(f"capacity {base_links}")
    assert vm.net.relation("found_1") is None and "K_1" not in vm.net.nodes
    assert all(vm.net.relation(r) for r, o in vm.net.origin["relations"].items() if o == "base")
    assert any("forgot 1 relation(s)" in s for s in out)
    sh.onecmd("capacity 1")
    assert mind.links(vm.net) == base_links and any("no room" in s for s in out)


def test_at_night_what_it_found_and_no_longer_uses_is_forgotten(tmp_path):
    pytest.importorskip("pygrm.discover")
    vm = grm_vm.VM(memory=str(tmp_path / "m.json"), blank=True)
    vm.load(os.path.join(HERE, "programs", "falling.csv"))
    vm.net.use["relations"]["found_1"] = mind.FADE / 2
    done = vm.sleep(night=True)
    assert any("forgot" in d and "found_1" in d for d in done) and "K_1" not in vm.net.nodes


def test_pleasure_and_displeasure():
    vm = grm_vm.VM(memory=None, blank=True)
    for line in ["input x", "input y", "relate model: y = 2 * x ± 0.1"]:
        vm.say(line)
    for x in range(1, 6):                      # it gets used to a surprise of about 3 sigma
        vm.put("x", float(x))
        vm.put("y", 2 * x + 0.3)
        vm.tick()
    vm.put("x", 6.0)
    vm.put("y", 12.0)                          # less surprised than it expected: pleasure
    vm.tick()
    assert vm.net.mood["dopamine"] > 0.3
    for _ in range(10):
        vm.tick()                              # nothing new: back to calm
    assert abs(vm.net.mood["dopamine"]) < 0.05
    vm.put("x", 7.0)
    vm.put("y", 20.0)                          # far more surprised than it expected: displeasure
    vm.tick()
    assert vm.net.mood["dopamine"] < -0.3


def test_finding_something_is_a_pleasure_and_what_learned_under_it_keeps_more_at_night():
    pytest.importorskip("pygrm.discover")
    vm = grm_vm.VM(memory=None, blank=True)
    vm.load(os.path.join(HERE, "programs", "falling.csv"))
    assert vm.net.mood["dopamine"] >= 0.5                     # a burst: it found h = K t^2
    vm.net.mood["tags"] = {"K_1": 1.0, "other": -1.0}
    k = mind.night_factors(vm.net, grm_vm.NIGHT)
    assert k["K_1"] == pytest.approx(1.0) and k["other"] == pytest.approx(0.6)
    s0 = vm.m().sigma("K_1")
    vm.m().downscale(grm_vm.NIGHT, {"K_1": 1.0})
    vm.m().run(5000)
    assert vm.m().sigma("K_1") == pytest.approx(s0, rel=1e-6)    # rewarded: nothing loosened


def test_flourishing_and_curiosity():
    pytest.importorskip("pygrm.discover")
    rng = random.Random(5)
    vm = grm_vm.VM(memory=None, blank=True)
    for line in ["input x", "input y", "relate model: y = 2 * x ± 0.1"]:
        vm.say(line)
    found = []
    for _ in range(80):                                      # something is missing: y = 2 x + 5
        x = rng.uniform(-3, 3)
        vm.put("x", x)
        vm.put("y", 2 * x + 5 + rng.gauss(0, 0.1))
        vm.tick()
        found += [e for e in vm.pop_events() if e.startswith("curiosity")]
    assert found and "hidden_1" in found[0]                  # it went looking by itself, without a night
    md = vm.net.mood
    assert 0 <= md["flourishing"] <= 1 and md["room"] > 0.99
    vm.net.mood["surprises"] = [10.0] * 20 + [1.0] * 20
    mind.flourishing(vm.net)
    assert vm.net.mood["progress"] > 0.5 and vm.net.mood["accuracy"] == pytest.approx(0.5)


def test_what_it_feels_is_remembered(tmp_path):
    pytest.importorskip("pygrm.discover")
    mem = str(tmp_path / "m.json")
    vm = grm_vm.VM(memory=mem, blank=True)
    vm.load(os.path.join(HERE, "programs", "falling.csv"))
    vm.net.capacity = 500
    vm.sleep()
    again = grm_vm.VM(memory=mem)
    assert again.net.capacity == 500
    assert again.net.origin["relations"]["found_1"] == "found"
    assert again.net.use["relations"]["found_1"] == vm.net.use["relations"]["found_1"]
    assert again.net.mood["dopamine"] == vm.net.mood["dopamine"]


def test_inside_commands():
    vm = example("fall")
    sh, out = shell_of(vm)
    for c in ("mood", "master", "master 0", "check", "inspect height", "inspect fall", "prune", "capacity"):
        sh.onecmd(c)
    text = "\n".join(out)
    for piece in ("dopamine", "master equation, now", "no problem found", "node height", "relation fall",
                  "nothing to forget", "links of", "the host's budget", "rent"):
        assert piece in text, piece


def test_the_host_sets_the_room():
    vm = example("fall")
    vm.tick(3)
    cap = mind.capacity(vm.net)
    assert cap >= mind.MIN_CAPACITY and set(vm.net.host["caps"]) <= {"time", "memory"}
    vm.clock_hz = 1000.0                                        # a faster clock: less time a tick, less room
    vm.tick()
    assert vm.net.host["caps"]["time"] < cap * 0.2 or vm.net.host["limit"] == "memory"
    vm.net.capacity = 123                                       # by hand
    assert mind.capacity(vm.net) == 123
    sh, out = shell_of(vm)
    sh.onecmd("capacity auto")
    assert vm.net.capacity is None and any("the host's budget" in s for s in out)


def test_information_in_bits_and_the_rent():
    vm = example("fall")
    vm.tick(2)
    alone = vm.net.use["bits"]["fall"]
    assert alone > 10                                    # it alone fixes height: many bits
    vm.say("relate echo: 2 * height = g * t^2")
    vm.tick(120)                                         # (what a relation brings is followed as it goes)
    bits = vm.net.use["bits"]
    assert bits["echo"] < 2 and bits["fall"] < 2         # each says what the other says: an echo brings little
    assert mind.price(vm.net) < 1e-3                     # an empty network charges almost nothing
    vm.net.capacity = mind.links(vm.net)                 # full: the rent rises
    assert mind.price(vm.net) > 1
    assert mind.worth(vm.net, "echo") < 0


def test_at_night_what_does_not_pay_its_rent_is_forgotten(tmp_path):
    pytest.importorskip("pygrm.discover")
    vm = grm_vm.VM(memory=str(tmp_path / "m.json"), blank=True)
    vm.load(os.path.join(HERE, "programs", "falling.csv"))
    vm.net.use["bits"]["found_1"] = 1e-6                 # it brings nothing any more
    vm.net.capacity = mind.links(vm.net) * 2             # half full: a rent of 0.1 bit per link and tick
    done = vm.sleep(night=True)
    assert any("found_1 (it no longer paid its rent)" in d for d in done)


def test_example_universe_and_its_master_equation():
    pytest.importorskip("pygrm")
    vm = example("universe")
    S, Eq, Es = vm.get("S"), vm.get("Equant"), vm.get("Estock")
    assert S * Eq / Es == pytest.approx(1, rel=1e-6)          # S Equant = Estock, never written
    import pygrm
    if tuple(int(x) for x in pygrm.__version__.split(".")[:3]) < (0, 5, 1):
        pytest.skip("the master equation over triples of nodes needs pygrm >= 0.5.1")
    res = mind.master(vm)
    assert res["text"] == "Equant · S · Estock^-1 = 1" and res["derived"]
    assert res["span"] == pytest.approx(175, abs=1)


# ---------------------------------------------------------------------- short forms, help, programs, two languages
import ast   # noqa: E402
import glob   # noqa: E402
import string   # noqa: E402

import guide   # noqa: E402
import i18n   # noqa: E402
import programs   # noqa: E402


@pytest.fixture(autouse=True)
def english():
    """Every test starts in English, whatever the one before it chose."""
    i18n.set_lang("en")
    yield
    i18n.set_lang("en")


def test_short_forms_and_plus_minus():
    a = say(Network(), "nd x = 2\nrel model: y = 3 * x ± 0.1\nobs y = 6 ± 1%")
    b = say(Network(), "node x = 2\nrelate model: y = 3 * x +/- 0.1\nobserve y = 6 +/- 1%")
    assert a.relations == b.relations and a.measured == b.measured and set(a.nodes) == set(b.nodes)
    assert set(editor.SHORT.values()) <= set(editor.DOCS)                    # every short form stands for a word
    assert len(set(editor.SHORT)) == len(set(editor.SHORT.values()))         # one short form per word
    assert not set(editor.SHORT) & set(editor.DOCS)                          # and none is a word itself
    vm = grm_vm.VM(memory=None, blank=True)
    sh, out = shell_of(vm)
    sh.onecmd("inp x = 2 ; out y ; rel r: y = 3 * x +/- 0.1 ; t 2 ; ins r")
    assert vm.get("y") == pytest.approx(6, rel=1e-3) and vm.net.nodes["y"].get("output")
    assert not any(s.startswith(("  ?", "  !")) for s in out)
    assert any("relation r" in s for s in out)


def test_every_program_says_what_it_does():
    found = programs.listing()
    assert {p["name"] for p in found} >= {"fall", "circles", "universe", "hello"}
    for p in found:
        assert p.get("does") and p.get("try"), p["name"]
    circles = next(p for p in found if p["name"] == "circles")
    assert circles["networks"] and not any(o.endswith("_") for o in circles["outputs"])   # not a network's own
    assert programs.find("fall") == os.path.join(HERE, "programs", "fall.grm")
    assert programs.find("no_such_program") is None


def test_programs_read_and_new(tmp_path):
    vm = grm_vm.VM(memory=None, blank=True)
    sh, out = shell_of(vm)
    sh.onecmd("progs")
    assert any(s.strip().startswith("fall") for s in out)
    out.clear()
    sh.onecmd("rd fal")                                                       # a typo: what it looks like
    assert "fall" in out[-1] and out[-1].startswith("  ?")
    out.clear()
    sh.onecmd("read fall")
    assert any("#! name: fall" in s for s in out)
    sh.onecmd("open fall")                                                    # no window: said, not a crash
    assert "--window" in out[-1]
    (tmp_path / "programs").mkdir()
    sh.base = str(tmp_path)
    sh.onecmd("new mine")
    path = tmp_path / "programs" / "mine.grm"
    assert path.exists() and programs.header(str(path))["name"] == "mine"
    sh.onecmd("use programs/mine.grm")                                        # the template runs as it is
    assert vm.get("y") == pytest.approx(6, rel=1e-2)


def test_help_on_every_word():
    vm = grm_vm.VM(memory=None, blank=True)
    sh, out = shell_of(vm)
    grouped = [w for _, words in guide.GROUPS for w in words]
    assert sorted(grouped) == sorted(editor.DOCS)                             # every word in one group, once
    for w in editor.DOCS:
        out.clear()
        sh.onecmd(f"help {w}")
        assert out and out[0].strip().startswith(w) and not out[0].startswith("  ?"), w
    out.clear()
    sh.onecmd("h rel")                                                        # a short form, of help and of relate
    assert out[0].strip().startswith("relate")
    out.clear()
    sh.onecmd("help relat")
    assert "relate" in out[0] and out[0].startswith("  ?")
    out.clear()
    sh.onecmd("help")
    assert len(out) > len(editor.DOCS)


def test_every_command_of_the_tour_runs():
    vm = grm_vm.VM(memory=None)                                               # born with its base
    sh, out = shell_of(vm)
    for n, (_, _, typed) in enumerate(guide.TOUR, 1):
        sh.onecmd(f"tour {n}")
        out.clear()
        sh.onecmd(typed)
        wrong = [s for s in out if s.startswith(("  ?", "  !")) and "--window" not in s]
        assert not wrong, (typed, wrong)
    assert vm.get("height") == pytest.approx(30, rel=1e-3)
    sh.onecmd("tour end")
    assert sh.tour_at == 0


def said_texts():
    """Every text the machine may say: the literal templates of tr(), and those kept in tables."""
    found = set()
    for path in glob.glob(os.path.join(HERE, "*.py")):
        if os.path.basename(path).startswith(("test_", "fr.")):
            continue
        with open(path, encoding="utf-8") as f:
            tree = ast.parse(f.read())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) in ("tr", "label") and node.args:
                a = node.args[0]
                if isinstance(a, ast.Constant) and isinstance(a.value, str):
                    found.add(a.value)
    import language
    found |= {what for _, what, _ in editor.DOCS.values()} | set(guide.MORE.values())
    found |= {t for title, text, _ in guide.TOUR for t in (title, text)} | {g for g, _ in guide.GROUPS}
    found |= set(language.ROLES.values())
    return found


def test_the_french_catalogue_is_whole():
    from fr import FR

    def fields(s):
        return sorted(f for _, f, _, _ in string.Formatter().parse(s) if f)
    texts = said_texts()
    assert not [t for t in texts if t not in FR]                              # nothing said in English by mistake
    assert not [t for t in texts if fields(t) != fields(FR[t])]               # the same {fields}


def test_language_switch(tmp_path):
    vm = grm_vm.VM(memory=None, blank=True)
    sh, out = shell_of(vm)
    assert sh.settings_path is None
    sh.onecmd("lang fr")
    assert out[-1].strip() == "langue : fr"
    out.clear()
    sh.onecmd("relate fall: 2 * height = g * t^2 ; obs g = 9.81 +/- 0.1% ; obs t = 2 ; ask height")
    assert any("relation fall" in s for s in out) and any("mesuré g" in s for s in out)
    out.clear()
    sh.onecmd("help relate")
    assert "une relation" in out[0]
    out.clear()
    sh.onecmd("xyz")
    assert "n'est pas un mot de la machine" in out[-1]
    sh.onecmd("lang en")
    assert not list(tmp_path.iterdir()) and not os.path.exists(os.path.join(HERE, "settings.json"))
    # with a memory, the choice is kept beside it
    vm = grm_vm.VM(memory=str(tmp_path / "m.json"), blank=True)
    sh, out = shell_of(vm)
    sh.onecmd("lang fr ; help off")
    with open(tmp_path / "settings.json", encoding="utf-8") as f:
        assert json.load(f) == {"lang": "fr", "help": False}
    i18n.set_lang("en")
    sh, out = shell_of(grm_vm.VM(memory=str(tmp_path / "m.json"), blank=True))
    assert i18n.lang() == "fr" and sh.settings["help"] is False


def test_a_located_error_in_french():
    i18n.set_lang("fr")
    with pytest.raises(TalkError) as e:
        say(Network(), "use programs/no_such.grm")
    assert "pas de fichier" in str(e.value)


def test_hint_and_menu_under_the_prompt():
    assert "tour" in editor.hint("", 0)
    assert editor.hint("rel", 3).startswith("rel = relate")
    assert editor.hint("relate a: ", 10).startswith("relate (rel)")
    assert "word(s)" in editor.hint("ob", 2)
    menu = dict(editor.suggest("ob", 2, commands=["outputs"]))
    assert "observe" in menu and menu.get("obs") == "= observe"
    assert editor.suggest("relate r: h", 11, nodes=["height", "h2"]) == []        # one letter: no names yet
    assert [w for w, _ in editor.suggest("relate r: he", 12, nodes=["height", "head"])] == ["head", "height"]
    many = [f"n{i}" for i in range(20)]
    assert editor.suggest("ask n", 5, nodes=many) == [] and editor.suggest("ask n1", 6, nodes=many) != []
    assert [w for w, _ in editor.suggest("help rel", 8)] == ["relate"]
    i18n.set_lang("fr")
    assert "une relation" in editor.hint("rel", 3)


def test_a_colon_as_each_language_writes_it():
    assert i18n.label("error") == "error: "
    i18n.set_lang("fr")
    assert i18n.label("error") == "erreur : "
    assert guide.word("relate")[0].endswith("(abrégé : rel) — une relation : produits, puissances, sommes")
