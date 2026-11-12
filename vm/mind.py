# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Anthony Charretier
"""What the GRM machine feels and keeps, as close as it can be to what is known of a brain.

The host's budget: how many links it may hold (capacity)
    A brain does not count its synapses: it has an energy budget (about 20 W), most of it spent on synaptic
    transmission (Attwell & Laughlin 2001), and the number of synapses it can keep follows from that budget. Here the
    energy is what the host machine gives: time (a tick must take at most TIME_SHARE of the clock's period, or of a
    tenth of a second when no clock runs: real time) and memory (at most MEMORY_SHARE of the memory available now).
    The machine measures what a link costs on this host (a calibration of its rounds once a session, the rounds a
    tick takes as it goes; about BYTES_PER_LINK of memory), and its capacity is the budget divided by that cost. A
    faster host gives it more room, a faster clock less. `capacity N` sets it by hand; CAPACITY when nothing can be
    measured.

Entropy: the rent of a relation, in bits
    Every relation brings information: how much it narrows what its nodes can be. For Gaussian beliefs it is exact:
    without the relation's message a node's precision would be lam - l instead of lam, its entropy higher by
    1/2 log2(lam / (lam - l)) bits. A relation that says what others already say (an echo) brings almost nothing; one
    that alone fixes a node brings a lot. Holding a link costs: the rent of a relation is PRICE bits per link and per
    tick, a price that grows as room runs out (occupancy / (1 - occupancy)): nothing is charged in an empty network,
    much in a full one (Rissanen's minimum description length, with a price set by scarcity). What the machine found
    by itself and no longer pays its rent is forgotten at night; when room runs out, what pays the least goes first.

Use (synaptic pruning)
    Every node and every relation also carries a trace of its use: it rises each time it works (a relation that
    answers, a node it moves or that is read) and fades by itself, halving every HALF_LIFE ticks when nothing uses it
    (an unused synapse weakens). At night, what the machine found by itself and no longer uses is forgotten. Never
    forgotten: the base it was born with, its inputs and outputs. (In the brain: synapses that are not used are
    pruned, mostly during sleep.)

Pleasure and displeasure (dopamine)
    The dopamine neurons do not signal a reward itself but the difference between what was expected and what came
    (a reward prediction error, Schultz, Dayan & Montague 1997). Here: the machine expects a certain surprise from
    its inputs (a running mean); being less surprised than it expected (a prediction that holds) is pleasure, more
    surprised is displeasure; finding something by itself (a relation, a fusion, a missing node) is a burst of
    pleasure, an error (a calculation that does not settle, a value that is not a number) a burst of displeasure.
    Dopamine is the third factor of learning (Fremaux & Gerstner 2016): it tags what has just worked. A relation
    that works under pleasure gains more trace (it is kept), under displeasure less (it is forgotten sooner); a
    weight that learned under pleasure keeps more of its precision through the night (sleep consolidates what was
    rewarded), under displeasure less.

Flourishing
    Two things together. (a) Learning progress: how much the surprise is falling (Oudeyer & Kaplan's curiosity: a
    system drawn to what it is learning, neither to what it knows, nor to what it cannot understand). (b) Economy:
    explaining much with little (accuracy times the room left, the spirit of Friston's free energy). The machine
    tends to it by itself: when it stays surprised and has stopped learning, it looks for what it is missing
    (curiosity: it tries to find relations and missing nodes, without waiting for the night); when it has no room
    left, it forgets.

The master equation
    pygrm's master invariant (GlobalRelationalNetwork.extract_master_invariant): of the relations the network holds,
    and of those it implies between its farthest scales, the one that ties the widest span of scales with the
    smallest residual. A picture of the values is kept at every tick, so it can be read at t and at t - n.
"""
import math
import os
import time

from i18n import tr

try:
    from pygrm import GlobalRelationalNetwork as _GRM
except ImportError:  # pragma: no cover - without pygrm there is no master equation
    _GRM = None

CAPACITY = 10000       # links (one node in one relation: a synapse) when the host cannot be measured
REFERENCE_HZ = 10.0    # without a clock, a tick should still be real time: a tenth of a second
TIME_SHARE = 0.5       # of the clock's period a tick may take
MEMORY_SHARE = 0.25    # of the memory available now the network may take
BYTES_PER_LINK = 4000  # what a link takes in memory (measured: about 3.5 kB, its messages and history included)
MIN_CAPACITY = 500     # never less room than this
PRICE = 0.1            # bits a link costs each tick when half the room is taken
MAX_BITS = 32.0        # what a relation can tell of one node, at most (a node it alone fixes)
INFO_RATE = 0.05       # how fast the information of a relation follows what it brings now
HALF_LIFE = 1000       # ticks for an unused trace to halve
FADE = 0.01            # a trace below this at night: what the machine found by itself is forgotten
NEW_TRACE = 1.0        # the trace of what has just appeared
REWARD_GAIN = 0.5      # how much pleasure (or displeasure) adds to (or takes from) the trace of what works
EXPECT_RATE = 0.1      # how fast the expected surprise follows the surprise
NIGHT_TAG = 0.2        # a weight tagged by pleasure (+1) keeps NIGHT + 0.2 of its precision at night, by
                       # displeasure (-1) NIGHT - 0.2
WINDOW = 20            # ticks over which surprise and progress are measured
CURIOUS_SURPRISE = 2.0 # a mean surprise above this (sigmas) with no progress: the machine goes looking
CURIOUS_EVERY = 50     # ticks between two of its searches
MAX_PAST = 240         # ticks of values kept for the master equation at t - n
MAX_PAIRS = 20         # pairs of far scales tried for the unifying equations


# ---------------------------------------------------------------------- bookkeeping
def links(net):
    """The links the network holds: each node of each relation (a synapse)."""
    return sum(len(set(net.nodes_of(r))) for r in net.relations)


def capacity(net):
    """The links the network may hold: set by hand (`capacity N`), or what the host's budget allows."""
    return net.capacity or host_capacity(net)


# ---------------------------------------------------------------------- the host
_HOST = {"link_round": None, "memory": None, "memory_at": 0.0}


def available_memory():
    """The memory available now on the host, in bytes (None when it cannot be read)."""
    try:
        import psutil
        return int(psutil.virtual_memory().available)
    except Exception:  # noqa: BLE001 - psutil is optional
        pass
    try:
        with open("/proc/meminfo", encoding="ascii") as f:
            for line in f:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) * 1024
    except OSError:
        pass
    if os.name == "nt":
        try:
            import ctypes

            class Status(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            st = Status()
            st.dwLength = ctypes.sizeof(Status)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):
                return int(st.ullAvailPhys)
        except Exception:  # noqa: BLE001
            pass
    try:
        return int(os.sysconf("SC_AVPHYS_PAGES") * os.sysconf("SC_PAGE_SIZE"))
    except (AttributeError, ValueError, OSError):
        return None


def link_round():
    """What one link costs in one round on this host, in seconds: measured once a session on a chain of relations
    (every processor working at every round, the worst case)."""
    if _HOST["link_round"] is None:
        from language import Network, statement
        from runtime import Machine
        net = Network()
        n = 150
        for k in range(n):
            statement(net, f"relate c{k}: x{k} = 2 * x{k + 1}")
        statement(net, "observe x0 = 3")
        m = Machine(net)
        rounds = 20
        t0 = time.perf_counter()
        for _ in range(rounds):
            m.dirty_nodes = set(range(len(m.var_names)))
            m.dirty_factors = set(range(len(m.factors)))
            m.round()
        _HOST["link_round"] = max((time.perf_counter() - t0) / (rounds * 2 * n), 1e-9)
    return _HOST["link_round"]


def measure(net, rounds, clock_hz=0.0):
    """After a tick: the rounds it took (a running mean), and the clock it runs at."""
    h = net.host
    r = h.get("rounds")
    h["rounds"] = float(rounds) if r is None else r + 0.1 * (rounds - r)
    h["clock"] = clock_hz or 0.0


def host_capacity(net):
    """The budget of the host divided by what a link costs: time (a tick within TIME_SHARE of the clock's period)
    and memory (MEMORY_SHARE of what is available). Also kept in net.host for `mood` and `capacity`."""
    h = net.host
    caps = {}
    try:
        hz = h.get("clock") or REFERENCE_HZ
        rounds = max(1.0, h.get("rounds") or 1.0)
        caps["time"] = TIME_SHARE / hz / (link_round() * rounds)
    except Exception:  # noqa: BLE001 - a host that cannot be timed: memory only
        pass
    now = time.monotonic()
    if _HOST["memory"] is None or now - _HOST["memory_at"] > 5.0:
        _HOST["memory"], _HOST["memory_at"] = available_memory(), now
    if _HOST["memory"]:
        caps["memory"] = MEMORY_SHARE * _HOST["memory"] / BYTES_PER_LINK
    h["caps"] = caps
    if not caps:
        h["limit"] = "none measured"
        return CAPACITY
    limit = min(caps, key=caps.get)
    h["limit"] = limit
    return max(MIN_CAPACITY, int(caps[limit]))


# ---------------------------------------------------------------------- entropy
def information(m, net):
    """{relation: bits}: how much each relation narrows what its nodes can be, now (the entropy its nodes would
    gain without its messages)."""
    names = {r["name"] for r in net.relations}
    out = {}
    for f in m.factors:
        if f.name not in names:
            continue
        bits = 0.0
        for s, i in enumerate(f.vars):
            l_ = f.out_lam[s]
            if not l_ > 0:
                continue
            lam = m.lam[i]
            rest = lam - l_
            if not lam > 0:
                continue
            if rest <= lam * 2.0 ** (-2 * MAX_BITS):
                bits += MAX_BITS
            else:
                bits += min(MAX_BITS, 0.5 * math.log2(lam / rest))
        out[f.name] = out.get(f.name, 0.0) + bits
    return out


def price(net):
    """Bits a link costs each tick: nothing in an empty network, PRICE at half the room, more and more as it fills."""
    rho = min(links(net) / capacity(net), 0.99)
    return PRICE * rho / (1.0 - rho)


def worth(net, name, p=None):
    """What a relation brings each tick, minus its rent: below zero, it does not pay for its links."""
    rel = net.relation(name)
    if rel is None:
        return 0.0
    p = price(net) if p is None else p
    return net.use.setdefault("bits", {}).get(name, 0.0) - p * len(set(net.nodes_of(rel)))


def mark(net, nodes_before, relations_before, origin):
    """What appeared since (nodes_before, relations_before) comes from `origin` (base, written, found)."""
    for n in net.nodes:
        if n not in nodes_before:
            net.origin["nodes"].setdefault(n, origin)
            net.use["nodes"].setdefault(n, NEW_TRACE)
    for r in net.relations:
        if r["name"] not in relations_before:
            net.origin["relations"].setdefault(r["name"], origin)
            net.use["relations"].setdefault(r["name"], NEW_TRACE)


def mood(net):
    md = net.mood
    md.setdefault("dopamine", 0.0)
    md.setdefault("expected", None)
    md.setdefault("surprises", [])
    md.setdefault("tags", {})
    md.setdefault("flourishing", 1.0)
    md.setdefault("accuracy", 1.0)
    md.setdefault("room", 1.0)
    md.setdefault("progress", 0.0)
    md.setdefault("last_search", 0)
    return md


def flourishing(net):
    """How the network flourishes now: (b) accuracy (1 when its inputs no longer surprise it) times room (1 when it
    holds no link yet, 0 at capacity), and (a) the progress of its learning (how much its surprise is falling)."""
    md = mood(net)
    S = md["surprises"]
    recent = S[-WINDOW:]
    mean_s = sum(recent) / len(recent) if recent else 0.0
    md["accuracy"] = 1.0 / (1.0 + mean_s * mean_s)
    md["room"] = max(0.0, 1.0 - links(net) / capacity(net))
    md["flourishing"] = math.sqrt(md["accuracy"] * md["room"])
    if len(S) >= 2 * WINDOW:
        before = sum(S[-2 * WINDOW:-WINDOW]) / WINDOW
        md["progress"] = math.tanh((before - mean_s) / (before + 0.1))
    else:
        md["progress"] = 0.0
    return md["flourishing"]


def reward(net, amount):
    """A burst of pleasure (amount > 0) or displeasure (amount < 0)."""
    md = mood(net)
    md["dopamine"] = max(-1.0, min(1.0, md["dopamine"] + amount))


# ---------------------------------------------------------------------- one tick
def after_tick(vm, surprise=None, explore=True):
    """What the machine feels and keeps after a tick: traces, dopamine, tags, flourishing, the picture of its
    values, and what it does by itself to flourish. surprise: rms of how far the inputs were from what it expected
    (None when no new input came). explore: it may go looking for what it misses (not while a file is being
    learned: the file ends with that search anyway). Returns what it did, in words."""
    net, m = vm.net, vm.machine
    md = mood(net)
    done = []
    # what each relation brings (entropy), followed as it goes
    if m is not None:
        bits = net.use.setdefault("bits", {})
        for name, b in information(m, net).items():
            old = bits.get(name)
            bits[name] = b if old is None else old + INFO_RATE * (b - old)
    # what worked this tick
    worked = set()
    if m is not None:
        relation_names = {r["name"] for r in net.relations}
        worked = {m.factors[i].name for i in m.worked if i < len(m.factors)} & relation_names
        m.worked.clear()
    vm.last_worked = worked                   # what the body shows working (senses.py)
    nodes_worked = set(getattr(vm, "_read", set()))
    vm._read = set()
    for r in net.relations:
        if r["name"] in worked:
            nodes_worked.update(net.nodes_of(r))
    # dopamine: the reward prediction error on surprise, and what comes back to rest when nothing new comes
    D = md["dopamine"]
    if surprise is not None and math.isfinite(surprise):
        E = md["expected"]
        delta = 0.0 if E is None else (E - surprise) / (E + surprise + 0.1)
        md["expected"] = surprise if E is None else E + EXPECT_RATE * (surprise - E)
        D = max(-1.0, min(1.0, 0.3 * D + delta))
        md["surprises"].append(surprise)
        del md["surprises"][:-3 * WINDOW]
    else:
        D *= 0.7
    md["dopamine"] = D
    # the traces: what works gains (more under pleasure), everything fades (entropy)
    decay = 0.5 ** (1.0 / HALF_LIFE)
    gain = max(0.0, 1.0 + REWARD_GAIN * D)
    for r in net.relations:
        name = r["name"]
        u = net.use["relations"].get(name, NEW_TRACE) * decay
        net.use["relations"][name] = u + (gain if name in worked else 0.0)
    for n in net.nodes:
        u = net.use["nodes"].get(n, NEW_TRACE) * decay
        net.use["nodes"][n] = u + (gain if n in nodes_worked else 0.0)
    # the weights that just learned are tagged by the dopamine of the moment
    for r in net.relations:
        if r["name"] in worked:
            for n in net.nodes_of(r):
                if net.nodes.get(n, {}).get("learn"):
                    t = md["tags"].get(n, 0.0)
                    md["tags"][n] = t + 0.2 * (D - t)
    # flourishing: accuracy times room, and the progress of learning
    flourishing(net)
    S = md["surprises"]
    recent = S[-WINDOW:]
    mean_s = sum(recent) / len(recent) if recent else 0.0
    vm.remember("pleasure", D)
    vm.remember("flourishing", md["flourishing"])
    # what it does by itself to flourish: no room left, it forgets; surprised and not learning, it goes looking
    if md["room"] <= 0.0:
        done += prune(vm)
    tick = getattr(net, "ticks", 0)
    if (explore and len(recent) >= WINDOW and mean_s > CURIOUS_SURPRISE and md["progress"] <= 0.05
            and tick - md["last_search"] >= CURIOUS_EVERY and len(net.rows) >= 8):
        md["last_search"] = tick
        found = vm.grow()
        if found:
            done += [tr("curiosity (surprised by {s} sigma, no longer learning)", s=f"{mean_s:.2g}") + f": {line}"
                     for line in found]
    snapshot(vm)
    return done


# ---------------------------------------------------------------------- forgetting
def _protected_node(net, n):
    spec = net.nodes.get(n, {})
    return (net.origin["nodes"].get(n) == "base" or spec.get("input") or spec.get("output")
            or net.origin["nodes"].get(n, "written") == "written")


def _defined_node(rel):
    """The node a helper relation the machine wrote for itself defines (ln_x, a product), if any."""
    if rel["name"].startswith("log_") and rel.get("kind") == "log":
        return rel["log"]
    if rel["name"].startswith("product_"):
        return rel["name"][len("product_"):]
    return None


def _remove_relation(net, name):
    rel = net.relation(name)
    if rel is None:
        return
    net.relations.remove(rel)
    net.use["relations"].pop(name, None)
    net.use.get("bits", {}).pop(name, None)
    net.origin["relations"].pop(name, None)
    net.tension.pop(name, None)


def _remove_node(net, n):
    net.nodes.pop(n, None)
    net.measured.pop(n, None)
    net.seen.pop(n, None)
    net.use["nodes"].pop(n, None)
    net.origin["nodes"].pop(n, None)
    net.mood.get("tags", {}).pop(n, None)
    net.links = [lk for lk in net.links if n not in lk["names"]]
    net.sets = [st for st in net.sets if st["target"] != n and st["source"] != n]
    for a in [a for a, b in net.aliases.items() if a == n or b == n]:
        net.aliases.pop(a)


def _tidy(net):
    """After a relation is forgotten: the helpers nothing uses any more, then the nodes the machine made for itself
    that no relation holds any more (with what writes them at each tick)."""
    gone = []
    changed = True
    while changed:
        changed = False
        for rel in list(net.relations):
            d = _defined_node(rel)
            if d and not any(d in net.nodes_of(o) for o in net.relations if o is not rel):
                _remove_relation(net, rel["name"])
                gone.append(tr("relation {name}", name=rel["name"]))
                changed = True
        held = {n for r in net.relations for n in net.nodes_of(r)}
        held |= {st["source"] for st in net.sets if st["target"] in held}
        for n in list(net.nodes):
            if n not in held and net.origin["nodes"].get(n) == "found" and not _protected_node(net, n):
                _remove_node(net, n)
                gone.append(tr("node {name}", name=n))
                changed = True
    return gone


def prune(vm, night=False):
    """Forgetting: at night, what the machine found by itself and no longer uses or no longer pays its rent in
    bits; whenever the links pass the capacity, what pays the least (what it found first, then what was written),
    until there is room. Never the base. Returns what it forgot, in words."""
    net = vm.net
    out = []
    forgotten = []
    if night:
        p = price(net)
        for rel in list(net.relations):
            name = rel["name"]
            if net.origin["relations"].get(name) != "found" or _defined_node(rel) is not None:
                continue
            unused = net.use["relations"].get(name, NEW_TRACE) < FADE
            if unused or worth(net, name, p) < 0:
                _remove_relation(net, name)
                forgotten.append(name + " (" + (tr("unused") if unused else tr("it no longer paid its rent")) + ")")
    cap = capacity(net)
    while links(net) > cap:
        rank = {"found": 0, "written": 1}
        candidates = [r for r in net.relations
                      if net.origin["relations"].get(r["name"], "written") in rank
                      and _defined_node(r) is None
                      and not (r["name"].startswith("set_") and any(st["source"] in net.nodes_of(r)
                                                                     for st in net.sets))]
        if not candidates:
            out.append(tr("no room: {n} links for {cap}, and nothing left that may be forgotten", n=links(net), cap=cap))
            break
        p = price(net)
        least = min(candidates, key=lambda r: (rank[net.origin["relations"].get(r["name"], "written")],
                                               worth(net, r["name"], p),
                                               net.use["relations"].get(r["name"], NEW_TRACE)))
        _remove_relation(net, least["name"])
        forgotten.append(least["name"] + " (" + tr("no room left") + ")")
    if forgotten:
        extra = _tidy(net)
        vm.machine = None
        out.append(tr("forgot {n} relation(s): {names}", n=len(forgotten), names=", ".join(forgotten))
                   + (" (" + tr("and {names}", names=", ".join(extra)) + ")" if extra else ""))
    return out


def night_factors(net, night):
    """{weight: what it keeps of its precision tonight}: more for what learned under pleasure."""
    tags = mood(net)["tags"]
    return {w: max(0.5, min(1.0, night + NIGHT_TAG * t)) for w, t in tags.items()}


# ---------------------------------------------------------------------- the master equation
def pygrm_network(net):
    """The relations of the network in pygrm's words (log relations: products and powers; sums of single nodes),
    and the specs of their nodes. Values are in SI, as the machine gives and reads them."""
    nodes, rels = {}, []
    for r in net.relations:
        kind = r.get("kind", "product")
        if kind == "product":
            rels.append({"name": r["name"], "terms": dict(r["terms"]), "rhs": float(r["rhs"]),
                         "sigma": max(float(r["sigma"]), 1e-9)})
            used = list(r["terms"])
        elif kind == "sum":
            terms, powers, K, ok = {}, {}, 0.0, True
            for c, t in r["terms"]:
                if not t:
                    K -= c
                elif len(t) == 1:
                    (n, p), = t.items()
                    if n in terms and powers[n] != p:
                        ok = False
                        break
                    terms[n] = terms.get(n, 0.0) + c
                    powers[n] = p
                else:
                    ok = False
                    break
            if not ok or len(terms) < 2:
                continue
            rels.append({"name": r["name"], "type": "sum", "terms": terms, "pow": powers, "K": K,
                         "sigma": max(float(r["sigma"]), 1e-9)})
            used = list(terms)
        else:
            continue
        for n in used:
            spec = net.nodes.get(n, {})
            signed = spec.get("signed", False)
            nodes[n] = {"guess": 0.0 if signed else 1.0, "fixed": bool(spec.get("fixed")),
                        "scale": "lin" if signed else "log"}
    return nodes, rels


def snapshot(vm):
    """The values of this tick, kept for the master equation at t - n (with the relations they held under)."""
    nodes, rels = pygrm_network(vm.net)
    past = vm.past
    if past and past[-1]["relations"] == rels:
        rels = past[-1]["relations"]                 # the same relations: shared, not copied
    m = vm.settle() if nodes else vm.machine
    values = {}
    if m is not None:
        for n in nodes:
            try:
                values[n] = m.value_si(n)
            except (KeyError, OverflowError):
                continue
    pic = {"tick": getattr(vm.net, "ticks", 0), "nodes": nodes, "relations": rels, "values": values}
    if past and past[-1]["tick"] == pic["tick"]:      # the same moment, looked at again
        last = past[-1]
        if last["relations"] is rels and last["values"] == values and last["nodes"] == nodes:
            return
        past[-1] = pic
    else:
        past.append(pic)
    del past[:-MAX_PAST]


def _fmt(v):
    if v == 0 or (1e-3 <= abs(v) < 1e6):
        return f"{v:.6g}"
    return f"{v:.6e}"


def equation_text(best):
    terms, powers = best["terms"], best.get("pow") or {}
    if best.get("type") == "sum":
        parts = []
        for k, (n, c) in enumerate(terms.items()):
            p = powers.get(n, 1.0)
            body = n if p == 1 else f"{n}^{p:g}"
            coef = "" if abs(c) == 1 else f"{abs(c):g}·"
            sign = ("-" if c < 0 else "") if k == 0 else (" - " if c < 0 else " + ")
            parts.append(sign + coef + body)
        return "".join(parts) + f" = {_fmt(best['rhs'])}"
    rhs = best["rhs"]
    terms = {n: float(c) for n, c in terms.items()}
    if sum(c < 0 for c in terms.values()) > sum(c > 0 for c in terms.values()):
        terms = {n: -c for n, c in terms.items()}           # the same equation, the other way up
        rhs = -rhs
    parts = []
    for n, c in sorted(terms.items(), key=lambda kv: kv[1] < 0):     # the positive powers first
        parts.append(n if c == 1 else f"{n}^{c:g}")
    right = _fmt(10.0 ** rhs) if abs(rhs) < 300 else f"10^{rhs:.6f}"
    return " · ".join(parts) + f" = {right}"


def master(vm, ago=0):
    """The master equation of the network at t - ago: {"tick", "text", "residual", "span", "derived",
    "relations"}, or {"tick", "text"} when there is none (or "error" when it cannot be computed)."""
    if ago == 0 or not vm.past:
        snapshot(vm)                                  # now: the network as it is at this moment
    if ago < 0 or ago >= len(vm.past):
        return {"tick": None, "text": tr("only the last {n} ticks are kept (t - 0 .. t - {last})", n=len(vm.past),
                                         last=len(vm.past) - 1)}
    pic = vm.past[-1 - ago]
    if pic.get("master") is not None:
        return pic["master"]
    if _GRM is None:
        return {"tick": pic["tick"], "text": tr("no master equation without pygrm")}
    vals = pic["values"]
    # a sum whose terms are not all of some size (a counter at 0, a value that is 0 but for rounding) spans no
    # scale: its "span" would only be the rounding's
    rels = []
    for r in pic["relations"]:
        if r.get("type") == "sum":
            sizes = [abs(vals.get(n, 0.0)) for n in r["terms"]]
            if not sizes or min(sizes) <= 1e-12 * max(max(sizes), 1e-300):
                continue
        rels.append(r)
    if not rels:
        out = {"tick": pic["tick"], "text": tr("no relation yet") if not pic["relations"] else
               tr("no closed relation found")}
    else:
        try:
            g = _GRM(pic["nodes"], rels)
            best = g.extract_master_invariant(vals, display_mode="compact", max_pairs=MAX_PAIRS)
        except Exception as e:  # noqa: BLE001 - say why instead of failing
            return {"tick": pic["tick"], "text": tr("cannot compute it: {error}", error=f"{type(e).__name__}: {e}"),
                    "error": True}
        if "terms" not in best:
            out = {"tick": pic["tick"], "text": tr("no closed relation found")}
        else:
            given = next((r for r in rels if r.get("type") == "sum" and r["terms"] == best["terms"]
                          and r["K"] == best["rhs"]), None)
            if given is not None and not best.get("derived"):
                best = dict(best, type="sum", pow=given["pow"])
            out = {"tick": pic["tick"], "text": equation_text(best), "residual": best["residual"],
                   "unit": "" if best.get("type") == "sum" else " dex",
                   "span": best["span"], "derived": best.get("derived", False),
                   "relations": best.get("relations")}
    pic["master"] = out
    return out
