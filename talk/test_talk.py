# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Anthony Charretier
"""Tests of grm talk: the words, the two machines, the benchmark.   python -m pytest talk/test_talk.py"""
import math
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "vm"))

from language import Network, TalkError, parse_side, statement   # noqa: E402
from machine import ClassicMachine, Costs, Problem, RelationalMachine   # noqa: E402
import grm_talk   # noqa: E402


def equation():
    net = Network()
    with open(os.path.join(HERE, "examples", "equation.grm"), encoding="utf-8") as f:
        for line in f:
            statement(net, line)
    return net


def test_words():
    terms, const = parse_side("S * H^2 / tP^-1 * 2")
    assert terms == {"S": 1.0, "H": 2.0, "tP": 1.0}
    assert const == pytest.approx(math.log10(2))
    net = Network()
    statement(net, "relate r: A * B^2 = 100 * C")
    r = net.relation("r")
    assert r["terms"] == {"A": 1.0, "B": 2.0, "C": -1.0} and r["rhs"] == pytest.approx(2.0)
    statement(net, "observe A = 3 ± 1%")
    assert net.measured["A"][1] == pytest.approx(math.log10(1.01))
    statement(net, "observe B = 2 ± 0.004 dex")
    assert net.measured["B"] == (2.0, 0.004)
    with pytest.raises(TalkError):
        statement(net, "relate s: A * -2 = B")
    assert statement(net, "ask A") is None      # a question, not a statement


def test_equation_two_machines_agree():
    P = Problem(equation())
    xc = ClassicMachine(P).solve()
    m = RelationalMachine(P)
    assert m.run()
    assert max(abs(a - b) for a, b in zip(m.x, xc)) < 1e-7
    S = 10 ** m.x[P.index["S"]]
    Equant = 10 ** m.x[P.index["Equant"]]
    Estock = 10 ** m.x[P.index["Estock"]]
    assert S * Equant / Estock == pytest.approx(1.0, rel=1e-5)


def test_tree_is_exact_in_few_rounds():
    """A chain without loops: belief propagation is exact after about as many rounds as the chain is long."""
    net = Network()
    statement(net, "observe x0 = 10 ± 1%")
    for k in range(1, 8):
        statement(net, f"relate r{k}: x{k} = 2 * x{k - 1}^2")
    P = Problem(net)
    xc = ClassicMachine(P).solve()
    m = RelationalMachine(P)
    for _ in range(10):
        m.round()
    assert max(abs(a - b) for a, b in zip(m.x, xc)) < 1e-9


def test_random_networks_same_answer():
    for n in (30, 200):
        P = Problem(grm_talk.synthetic(n, seed=n))
        xc = ClassicMachine(P).solve()
        m = RelationalMachine(P)
        assert m.run()
        assert max(abs(a - b) for a, b in zip(m.x, xc)) < 1e-8


def test_cost_model():
    P = Problem(grm_talk.synthetic(100))
    cm = ClassicMachine(P)
    cm.solve()
    m = RelationalMachine(P)
    m.run()
    c = Costs(link=10)
    assert m.cycles(c) == m.rounds * ((m.max_factor_ops + m.max_node_ops) + 20)
    assert cm.cycles(c) > m.sequential_cycles(c) > m.cycles(c)
    # dearer links make the relational machine slower, a dearer RAM only the classic one
    assert m.cycles(Costs(link=1000)) > m.cycles(c)
    assert cm.cycles(Costs(ram=1000)) > cm.cycles(c) and m.cycles(Costs(ram=1000)) == m.cycles(c)


def test_interpreter(tmp_path, capsys):
    t = grm_talk.Talk()
    t.graph_out = str(tmp_path / "live.png")
    t.onecmd("load equation; relax; ask S; why Estock; what-if H = 2.3e-18 ± 0.5%")
    out = capsys.readouterr().out
    assert "quiet after" in out and "S = 2.27" in out and "if H were" in out
    assert "H" in t.net.measured and t.net.measured["H"][0] == pytest.approx(2.18e-18)   # what-if leaves it
    t.onecmd(f"save {tmp_path / 'net.grm'}")
    u = grm_talk.Talk()
    u.onecmd(f"load {tmp_path / 'net.grm'}")
    assert len(u.net.relations) == 4 and set(u.net.measured) == {"G", "H"}


# ---------------------------------------------------------------------- the runtime: sums, converters, contacts, memory
from runtime import Machine   # noqa: E402


def say(net, text, base=HERE):
    for line in text.splitlines():
        statement(net, line, base)
    return net


def test_universe_gives_the_equation():
    m = Machine(say(Network(), "use universe.grm"))
    m.run()
    assert m.quiet
    assert m.value("S") * m.value("Equant") / m.value("Estock") == pytest.approx(1.0, rel=1e-6)   # relations held to 1e-6
    assert m.value("g_earth") == pytest.approx(9.82, rel=1e-3)
    assert m.value("g_moon") == pytest.approx(1.623, rel=1e-3)
    assert m.run() == 0                       # nothing new: nothing works


def test_sum_parsing():
    net = say(Network(), "node x0 signed\nrelate move: x1 = x0 + v * dt - 3 * 2e-1")
    r = net.relation("move")
    assert r["kind"] == "sum"
    got = {tuple(sorted(t)): c for c, t in r["terms"]}
    assert got == {("x1",): 1.0, ("x0",): -1.0, ("dt", "v"): -1.0, (): pytest.approx(0.6)}
    with pytest.raises(TalkError):
        statement(net, "relate s: A * -2 = B")


def test_converter_and_contact_ball():
    """A ball dropped on the Moon from 2 m: its gravity from G, M and R through a converter, the floor a contact."""
    net = say(Network(), """use universe.grm
node dt = 0.01 fixed
node y0 = 2 signed
node vy0 = 0 signed
observe y0 = 2 ± 1e-6
observe vy0 = 0 ± 1e-6
node n = 0 signed
observe n = 0 ± 1000
relate fall: vy1 = vy0 - g_moon * dt + n * dt
relate move: y1 = y0 + vy1 * dt
keep floor: y1 >= 0""")
    m = Machine(net)
    t = 0.0
    landed = None
    for _ in range(400):
        m.run(100)
        y1, v1 = m.value("y1"), m.value("vy1")
        t += 0.01
        if landed is None and y1 <= 1e-9:
            landed = t
        m.observe("y0", y1, 1e-6)
        m.observe("vy0", v1, 1e-6)
    g = m.value("g_moon")
    assert landed == pytest.approx(math.sqrt(2 * 2 / g), abs=0.02)       # 1.57 s
    assert m.value("y1") == pytest.approx(0.0, abs=1e-6)
    assert m.value("n") == pytest.approx(g, rel=1e-3)                     # the floor holds the weight


def test_networks_call_and_use():
    net = say(Network(), """network pair(id, k)
  relate double_{id}: y_{id} = {k} * x_{id}
end
call pair(id=a, k=2)
call pair(id=b, k=3)
observe x_a = 5
observe x_b = 7""")
    m = Machine(net)
    m.run()
    assert m.value("y_a") == pytest.approx(10, rel=1e-6) and m.value("y_b") == pytest.approx(21, rel=1e-6)
