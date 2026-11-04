# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Anthony Charretier
"""
GRM Brain - a brain that learns while it discovers a maze.

The brain and the maze are two separate things. The brain knows nothing of the maze: not its size, not its
walls, not where the exit is. It only has:

    a sense of its own moves  it knows which way it tried to go, and whether it moved (path integration:
                              from that it builds its own idea of "where am I", like animals do)
    touch                     it feels a wall only by bumping into it
    the exit                  it feels it only when it is there (a reward)
    a scent (optional)        a faint smell of the exit, stronger when closer

Its memory is a matrix of triplets (A, tension, B): from place A, this move led to B (or into a wall), with the
tension it left. The tension is the sensation of the memory:

    a prediction that comes true      lowers the tension   (the relation becomes sure)
    a surprise (a wall where it went) raises it            (the relation becomes doubtful)
    a bump                            leaves a painful tension, remembered longer than a calm one
    time                              brings every tension slowly back to neutral (forgetting): a wall
                                      forgotten is tried again, and a maze that changes can be learned again

Its desire is a GRM network: one node per place it knows, d = how far the exit feels from there. Each sure
relation says "one step more" (d_A = d_B + 1), with a tolerance that grows with its tension. Once the exit has
been found, it is measured at d = 0; the unknown is a node too, measured at a distance set by curiosity, so that
an untried move feels like a short cut to an unknown place. The core solves the network after every step (a few
passes, each place keeping the relation to its most promising neighbour: a shortest path found by tensions).
The brain then moves where the exit feels closest, and away from what hurt.

Nothing is learned before: everything is learned while living. Change the maze while it runs and watch it relearn.

Usage:
    python grm_brain.py               # the window
    python grm_brain.py --headless 6  # 6 trips to the exit without a window, steps per trip
"""
import argparse
import math
import random

from grm import GlobalRelationalNetwork

MOVES = {"N": (0, -1), "E": (1, 0), "S": (0, 1), "W": (-1, 0)}
NEW_TENSION = 1.0        # a relation just discovered: not sure yet
LEARN = 0.35             # share of the tension a confirmed prediction takes away (hypothesis)
SURPRISE = 2.5           # tension added by a broken prediction (hypothesis)
PAIN = 4.0               # tension of a bump (hypothesis)
FORGET = 0.004           # per step: how fast tensions come back to neutral, slower for strong ones (hypothesis)
WALL_FORGOTTEN = 1.2     # below this tension a remembered wall is no longer avoided: it will be tried again
SIGMA_SURE = 0.1         # tolerance of "one step more" for a relation without tension
SIGMA_PER_TENSION = 0.6  # tolerance added per unit of tension
FAR = 50.0               # what a place leans to when nothing attracts it
LEAN = 6.0               # how weakly (a soft pull: attraction spreads, but fades with distance)


# ============================================================
# THE WORLD (the brain never looks inside)
# ============================================================

class Maze:
    def __init__(self, width=11, height=11, loops=8, seed=None):
        self.w, self.h = width, height
        self.rng = random.Random(seed)
        self.open = set()                       # frozenset({cell, cell}) of open passages
        self._carve()
        for _ in range(loops):                  # a few loops: more than one way
            self._open_random_wall()
        self.start, self.exit = (0, 0), (width - 1, height - 1)
        self.agent = self.start

    def _neighbours(self, c):
        x, y = c
        for dx, dy in MOVES.values():
            n = (x + dx, y + dy)
            if 0 <= n[0] < self.w and 0 <= n[1] < self.h:
                yield n

    def _carve(self):
        seen, stack = {(0, 0)}, [(0, 0)]
        while stack:
            c = stack[-1]
            nxt = [n for n in self._neighbours(c) if n not in seen]
            if not nxt:
                stack.pop()
                continue
            n = self.rng.choice(nxt)
            self.open.add(frozenset((c, n)))
            seen.add(n)
            stack.append(n)

    def _open_random_wall(self):
        for _ in range(200):
            c = (self.rng.randrange(self.w), self.rng.randrange(self.h))
            n = self.rng.choice(list(self._neighbours(c)))
            if frozenset((c, n)) not in self.open:
                self.open.add(frozenset((c, n)))
                return

    def passable(self, a, b):
        return frozenset((a, b)) in self.open

    def step(self, move):
        """The agent tries a move. Returns what the brain is allowed to feel: (moved, at_exit, scent)."""
        dx, dy = MOVES[move]
        target = (self.agent[0] + dx, self.agent[1] + dy)
        moved = (0 <= target[0] < self.w and 0 <= target[1] < self.h and self.passable(self.agent, target))
        if moved:
            self.agent = target
        d = math.dist(self.agent, self.exit)
        return moved, self.agent == self.exit, 1.0 / (1.0 + d)

    def reachable(self):
        seen, todo = {self.start}, [self.start]
        while todo:
            c = todo.pop()
            for n in self._neighbours(c):
                if n not in seen and self.passable(c, n):
                    seen.add(n)
                    todo.append(n)
        return self.exit in seen

    def shortest(self):
        dist, todo = {self.start: 0}, [self.start]
        while todo:
            c = todo.pop(0)
            for n in self._neighbours(c):
                if n not in dist and self.passable(c, n):
                    dist[n] = dist[c] + 1
                    todo.append(n)
        return dist.get(self.exit)

    def change(self, path=()):
        """Close a passage (on the given path if possible) and open a wall elsewhere, keeping an exit."""
        candidates = [frozenset((a, b)) for a, b in zip(path, path[1:]) if frozenset((a, b)) in self.open]
        for _ in range(100):
            closed = self.rng.choice(candidates) if candidates else self.rng.choice(list(self.open))
            self.open.discard(closed)
            self._open_random_wall()
            if self.reachable():
                return closed
            self.open.add(closed)
        return None


# ============================================================
# THE BRAIN
# ============================================================

class Brain:
    def __init__(self, curiosity=3.0, use_scent=False, seed=0):
        self.rng = random.Random(seed)
        self.here = (0, 0)               # where it believes it is, from its own moves
        self.home = (0, 0)
        self.memory = {}                 # (place, move) -> {"B": place or None (a wall), "tension": float}
        self.places = {(0, 0)}
        self.exit_place = None
        self.curiosity = curiosity
        self.use_scent = use_scent
        self.scent = {}                  # place -> scent felt there
        self.desire = {}                 # place -> d (how far the exit feels)
        self.doubt = {}                  # place -> sigma of d
        self.last_sensation = 0.0
        self.trail = [(0, 0)]

    # ---------------------------------------------------------------- memory
    def remember(self, move, moved, at_exit, scent):
        """What happened after trying `move`: update the triplet (here, move) -> B and its tension."""
        dx, dy = MOVES[move]
        expected = self.memory.get((self.here, move))
        outcome = (self.here[0] + dx, self.here[1] + dy) if moved else None
        if expected is None:
            tension = PAIN if outcome is None else NEW_TENSION
        elif expected["B"] == outcome and outcome is None:
            tension = max(expected["tension"], PAIN)              # the wall was there: it hurts again
        elif expected["B"] == outcome:
            tension = expected["tension"] * (1 - LEARN)          # the prediction came true
        else:
            tension = expected["tension"] + (PAIN if outcome is None else SURPRISE)   # surprise
        before = expected["tension"] if expected else 0.0
        self.memory[(self.here, move)] = {"B": outcome, "tension": tension}
        back = {"N": "S", "S": "N", "E": "W", "W": "E"}[move]
        if outcome is None and expected is not None and expected["B"] is not None:
            # a passage it knew is shut: what it believed of the way back is shut too (a wall has two sides)
            self.memory[(expected["B"], back)] = {"B": None, "tension": tension}
        self.last_sensation = tension - before
        if moved:
            # the way back is a relation too (seen from the other side), not yet tried
            if (outcome, back) not in self.memory or self.memory[(outcome, back)]["B"] is None:
                self.memory[(outcome, back)] = {"B": self.here, "tension": NEW_TENSION * 1.5}
            self.here = outcome
            self.places.add(outcome)
            self.trail.append(outcome)
        if self.use_scent:
            self.scent[self.here] = scent
        if at_exit:
            self.exit_place = self.here

    def forget(self):
        """Every tension drifts back towards neutral; strong tensions (pain) drift more slowly."""
        for key, m in list(self.memory.items()):
            t = m["tension"]
            m["tension"] = t + (NEW_TENSION - t) * FORGET / (1.0 + abs(t - NEW_TENSION))

    def respawn(self):
        """Back at the start (the brain is told: it is carried home, it knows where home is)."""
        self.here = self.home
        self.trail = [self.home]

    # ---------------------------------------------------------------- desire network
    def think(self):
        """GRM network of desire, one node per known place. The places are tied to each other like springs:
        a sure relation (low tension) is a stiff spring, a doubtful one a soft spring. The exit, once found, is
        pinned at 0; the unknown (every untried move) is pinned at a height set by curiosity; and every place
        leans weakly towards 'far'. The network finds the equilibrium: a landscape that only goes down towards
        what attracts, with no hollow to get stuck in (a harmonic field). The brain then follows the slope."""
        places = sorted(self.places)
        idx = {p: f"d{k}" for k, p in enumerate(places)}
        nodes = {idx[p]: {"guess": self.desire.get(p, FAR / 2), "scale": "lin"} for p in places}
        nodes["unknown"] = {"guess": 0.0, "scale": "lin"}
        rels, seen = [], set()
        for p in places:
            for move in MOVES:
                m = self.memory.get((p, move))
                if m is None:
                    a_, b_, sig = idx[p], "unknown", 1.0                       # an untried move: towards the unknown
                elif m["B"] is None and m["tension"] < WALL_FORGOTTEN:
                    a_, b_, sig = idx[p], "unknown", 4.0                       # a forgotten wall: a faint maybe
                elif m["B"] is not None and m["B"] in idx:
                    a_, b_ = idx[p], idx[m["B"]]
                    sig = SIGMA_SURE + SIGMA_PER_TENSION * m["tension"]
                else:
                    continue
                key = (a_, b_, move) if b_ == "unknown" else tuple(sorted((a_, b_)))
                if key in seen:
                    continue
                seen.add(key)
                rels.append({"name": f"{p}{move}", "type": "sum", "terms": {a_: 1.0, b_: -1.0}, "K": 0.0, "sigma": sig})
        measured = {idx[p]: (FAR, LEAN) for p in places}                      # every place leans towards far
        if self.exit_place is not None:
            measured[idx[self.exit_place]] = (0.0, 0.01)
            measured["unknown"] = (self.curiosity, 0.05)                      # known exit: the unknown is a detour
        else:
            measured["unknown"] = (0.0, 0.05)                                 # nothing known: go and see
        if self.use_scent:
            for p, sc in self.scent.items():                                  # a stronger scent: a nearer exit
                measured[idx[p]] = (min(FAR, 3.0 / max(sc, 1e-3)), 2.0)
        out = GlobalRelationalNetwork(nodes, rels, undetermined_sigma=10.0).solve(
            measured, max_iterations=10, continuation=False)
        self.desire = {p: out["values"][idx[p]] for p in places}
        self.desire["unknown"] = out["values"]["unknown"]
        self.doubt = {p: out["sigma_dex"][idx[p]] for p in places}

    def choose(self):
        """Move where the exit feels closest; what hurt is avoided; untried moves are the unknown."""
        scores = {}
        for move in MOVES:
            m = self.memory.get((self.here, move))
            if m is None:
                scores[move] = self.desire.get("unknown", 0.0)
            elif m["B"] is None:
                scores[move] = 1e3 if m["tension"] >= WALL_FORGOTTEN else self.desire.get("unknown", 0.0)
            else:
                scores[move] = self.desire.get(m["B"], FAR) + 0.02 * m["tension"]
        low = min(scores.values())
        options = [mv for mv, s_ in scores.items() if s_ <= low + 1e-6 + 1e-3 * abs(low)]
        return self.rng.choice(options)


# ============================================================
# LIFE: the brain in the world
# ============================================================

class Life:
    def __init__(self, seed=None, curiosity=3.0, use_scent=False, size=11):
        self.maze = Maze(size, size, seed=seed)
        self.brain = Brain(curiosity, use_scent, seed=0 if seed is None else seed)
        self.steps, self.bumps, self.trip_steps, self.trips = 0, 0, 0, []
        self.brain.think()

    def tick(self):
        """One step of life. Returns True when the exit is reached."""
        move = self.brain.choose()
        moved, at_exit, scent = self.maze.step(move)
        self.brain.remember(move, moved, at_exit, scent)
        self.brain.forget()
        self.steps += 1
        self.trip_steps += 1
        if not moved:
            self.bumps += 1
        self.brain.think()
        if at_exit:
            self.trips.append(self.trip_steps)
            self.trip_steps = 0
            self.maze.agent = self.maze.start
            self.brain.respawn()
            self.brain.think()
            return True
        return False

    def change_world(self):
        """Close a passage on the way the brain uses most, open one elsewhere."""
        path = [self.maze.start]
        p = self.brain.home
        for _ in range(200):                     # the brain's own best way, translated back to the world
            nxt = None
            for mv in MOVES:
                m = self.brain.memory.get((p, mv))
                if m and m["B"] is not None and self.brain.desire.get(m["B"], 1e9) < self.brain.desire.get(p, 1e9):
                    if nxt is None or self.brain.desire[m["B"]] < self.brain.desire[nxt]:
                        nxt = m["B"]
            if nxt is None:
                break
            p = nxt
            path.append(p)
        return self.maze.change(path)


# ============================================================
# WINDOW
# ============================================================

def run_window():
    import tkinter as tk
    from tkinter import ttk

    root = tk.Tk()
    root.title("GRM Brain")
    BG, PANEL, FG = "#0d1117", "#161b22", "#c9d1d9"
    root.configure(bg=BG)
    state = {"life": Life(seed=random.randrange(10 ** 6)), "running": True}
    CELL = 40
    left = tk.Canvas(root, width=11 * CELL + 20, height=11 * CELL + 20, bg=BG, highlightthickness=0)
    left.grid(row=0, column=0, padx=8, pady=8)
    right = tk.Canvas(root, width=11 * CELL + 20, height=11 * CELL + 20, bg=BG, highlightthickness=0)
    right.grid(row=0, column=1, padx=8, pady=8)
    curve = tk.Canvas(root, width=2 * (11 * CELL + 20) + 16, height=90, bg=PANEL, highlightthickness=0)
    curve.grid(row=1, column=0, columnspan=2, padx=8)
    bar = tk.Frame(root, bg=BG)
    bar.grid(row=2, column=0, columnspan=2, pady=6, sticky="w", padx=8)
    speed = tk.IntVar(value=4)
    scent = tk.BooleanVar(value=False)
    curiosity = tk.DoubleVar(value=3.0)
    info = tk.StringVar()
    pause_btn = ttk.Button(bar, text="Pause")

    def toggle():
        state["running"] = not state["running"]
        pause_btn.config(text="Pause" if state["running"] else "Play")

    def new_maze():
        state["life"] = Life(seed=random.randrange(10 ** 6), curiosity=curiosity.get(), use_scent=scent.get())

    def change():
        closed = state["life"].change_world()
        if closed:
            state["flash"] = (tuple(closed), 25)

    pause_btn.config(command=toggle)
    pause_btn.pack(side="left", padx=3)
    ttk.Button(bar, text="New maze", command=new_maze).pack(side="left", padx=3)
    ttk.Button(bar, text="Change the maze", command=change).pack(side="left", padx=3)
    tk.Label(bar, text="speed", bg=BG, fg=FG).pack(side="left", padx=(12, 2))
    ttk.Scale(bar, from_=1, to=30, variable=speed, length=110).pack(side="left")
    tk.Label(bar, text="curiosity", bg=BG, fg=FG).pack(side="left", padx=(12, 2))
    ttk.Scale(bar, from_=0.5, to=10, variable=curiosity, length=110,
              command=lambda _v: setattr(state["life"].brain, "curiosity", curiosity.get())).pack(side="left")
    tk.Checkbutton(bar, text="scent of the exit", variable=scent, bg=BG, fg=FG, selectcolor=BG, activebackground=BG,
                   command=lambda: setattr(state["life"].brain, "use_scent", scent.get())).pack(side="left", padx=10)
    tk.Label(root, textvariable=info, bg=BG, fg=FG, font=("Courier", 10), justify="left").grid(
        row=3, column=0, columnspan=2, sticky="w", padx=10, pady=(0, 8))

    def colour_tension(t):
        x = max(0.0, min(1.0, t / PAIN))
        r, g = int(80 + 175 * x), int(200 - 150 * x)
        return f"#{r:02x}{g:02x}60"

    def colour_desire(d, top):
        x = max(0.0, min(1.0, d / max(top, 1.0)))
        r, g, b = int(60 + 190 * x), int(160 + 60 * x), int(255 - 200 * x)
        return f"#{r:02x}{g:02x}{b:02x}"

    def draw():
        life = state["life"]
        m, b = life.maze, life.brain
        L, R = left, right
        L.delete("all")
        R.delete("all")
        o = 10
        # the world
        L.create_text(o, 2, text="THE WORLD (the brain never sees it)", anchor="nw", fill="#6e7681", font=("Helvetica", 9))
        for x in range(m.w):
            for y in range(m.h):
                cx, cy = o + x * CELL, o + 12 + y * CELL
                for (dx, dy), (x0, y0, x1, y1) in (((1, 0), (CELL, 0, CELL, CELL)), ((0, 1), (0, CELL, CELL, CELL))):
                    n = (x + dx, y + dy)
                    if n[0] < m.w and n[1] < m.h and not m.passable((x, y), n):
                        L.create_line(cx + x0, cy + y0, cx + x1, cy + y1, fill="#8b949e", width=2)
        L.create_rectangle(o, o + 12, o + m.w * CELL, o + 12 + m.h * CELL, outline="#8b949e", width=2)
        ex, ey = m.exit
        L.create_rectangle(o + ex * CELL + 6, o + 12 + ey * CELL + 6, o + ex * CELL + CELL - 6,
                           o + 12 + ey * CELL + CELL - 6, fill="#238636", outline="")
        if state.get("flash"):
            (c1, c2), n = state["flash"]
            L.create_line(o + c1[0] * CELL + CELL / 2, o + 12 + c1[1] * CELL + CELL / 2,
                          o + c2[0] * CELL + CELL / 2, o + 12 + c2[1] * CELL + CELL / 2, fill="#f85149", width=5)
            state["flash"] = ((c1, c2), n - 1) if n > 1 else None
        trail = b.trail[-60:]
        for p1, p2 in zip(trail, trail[1:]):
            L.create_line(o + p1[0] * CELL + CELL / 2, o + 12 + p1[1] * CELL + CELL / 2,
                          o + p2[0] * CELL + CELL / 2, o + 12 + p2[1] * CELL + CELL / 2, fill="#1f6feb", width=2)
        ax, ay = m.agent
        L.create_oval(o + ax * CELL + 10, o + 12 + ay * CELL + 10, o + ax * CELL + CELL - 10,
                      o + 12 + ay * CELL + CELL - 10, fill="#f0883e", outline="")
        # the brain: its places where it believes they are, its relations coloured by tension
        R.create_text(o, 2, text="THE BRAIN: places (blue = where it wants to go), relations (green sure, red painful)",
                      anchor="nw", fill="#6e7681", font=("Helvetica", 9))
        ranked = sorted(v for k, v in b.desire.items() if k != "unknown")
        rank = lambda v: (sum(1 for r in ranked if r < v) / max(len(ranked) - 1, 1))   # 0 = where it wants to go
        pos = lambda p: (o + p[0] * CELL + CELL / 2, o + 12 + p[1] * CELL + CELL / 2)
        for (p, mv), mem in b.memory.items():
            x1, y1 = pos(p)
            if mem["B"] is None:                      # a remembered wall: a red stub, fading as it is forgotten
                if mem["tension"] >= WALL_FORGOTTEN:
                    dx, dy = MOVES[mv]
                    R.create_line(x1 + dx * CELL * 0.3, y1 + dy * CELL * 0.3, x1 + dx * CELL * 0.48,
                                  y1 + dy * CELL * 0.48, fill=colour_tension(mem["tension"]), width=4)
                continue
            x2, y2 = pos(mem["B"])
            R.create_line(x1, y1, (x1 + x2) / 2, (y1 + y2) / 2, fill=colour_tension(mem["tension"]),
                          width=1 + 3 / (1 + mem["tension"]))
        for p in b.places:
            x, y = pos(p)
            d = b.desire.get(p)
            sigma = b.doubt.get(p, 0.0)
            r_halo = 5 + min(14, 6 * sigma)
            R.create_oval(x - r_halo, y - r_halo, x + r_halo, y + r_halo, outline="#30363d")
            fill = "#484f58" if (d is None or b.exit_place is None) else colour_desire(rank(d), 1.0)
            R.create_oval(x - 6, y - 6, x + 6, y + 6, fill=fill, outline="")
        if b.exit_place is not None:
            x, y = pos(b.exit_place)
            R.create_rectangle(x - 8, y - 8, x + 8, y + 8, outline="#3fb950", width=2)
        x, y = pos(b.here)
        R.create_oval(x - 9, y - 9, x + 9, y + 9, outline="#f0883e", width=3)
        # learning curve
        curve.delete("all")
        curve.create_text(8, 6, text="steps to reach the exit, trip after trip (shortest possible: dashed)",
                          anchor="nw", fill="#8b949e", font=("Helvetica", 9))
        trips = life.trips[-40:]
        if trips:
            hi = max(trips)
            wbar = min(28, (int(curve["width"]) - 20) / max(len(trips), 1))
            for k, s_ in enumerate(trips):
                h = 60 * s_ / hi
                curve.create_rectangle(10 + k * wbar, 84 - h, 10 + k * wbar + wbar - 3, 84, fill="#1f6feb", outline="")
            best = m.shortest()
            if best:
                yb = 84 - 60 * best / hi
                curve.create_line(8, yb, int(curve["width"]) - 8, yb, fill="#3fb950", dash=(4, 3))
        info.set(f"steps {life.steps:5d}   bumps {life.bumps:4d}   trips {len(life.trips):3d}   "
                 f"places known {len(b.places):3d}   relations {len(b.memory):3d}   "
                 f"last sensation {b.last_sensation:+5.2f}   exit {'known' if b.exit_place else 'not found yet'}")

    def loop():
        if state["running"]:
            for _ in range(int(speed.get())):
                state["life"].tick()
        draw()
        root.after(60, loop)

    loop()
    root.mainloop()


def run_headless(trips, seed=1, change_after=None):
    life = Life(seed=seed)
    while len(life.trips) < trips and life.steps < 20000:
        if life.tick() and change_after and len(life.trips) == change_after:
            life.change_world()
    return life


def main():
    ap = argparse.ArgumentParser(description="GRM Brain: a brain that learns while it discovers a maze.")
    ap.add_argument("--headless", type=int, metavar="TRIPS")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--change-after", type=int, default=None, help="change the maze after this trip")
    args = ap.parse_args()
    if args.headless:
        life = run_headless(args.headless, args.seed, args.change_after)
        print(f"shortest way: {life.maze.shortest()} steps; trips: {life.trips}; bumps {life.bumps}")
    else:
        run_window()


if __name__ == "__main__":
    main()
