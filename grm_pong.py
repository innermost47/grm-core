# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Anthony Charretier
"""
GRM Pong: two paddles that play by themselves.

The ball is the relation, the paddles are its two ends, A and B. Each paddle has no rule of play, only two small
GRM networks that it solves with what it perceives:

  where will the ball meet me?  (intercept network)
      reach      x + vx * t = x_paddle                     the ball comes to my line
      walls      y_hit = fold(y + vy * t)                  the walls fold its path
      perceived  x, y, vx, vy are measurements, with a noise that grows with the distance
                 -> y_hit and its uncertainty: a paddle that is unsure says so

  where do I send it back?  (aim network)
      angle      the offset o of the hit on the paddle sets the return angle
      landing    y_land = fold(y_hit + vy_out * T)         where the ball will reach the other paddle
      escape     the other paddle can move v_max * T: the tension is high when y_land is within its reach
      safety     o is measured at 0 with a sigma of 0.3 paddle height: hitting near the edge is a risk
                 -> the offset that balances both tensions

The paddle then moves towards y_hit - o at its maximum speed. It perceives again every reaction time. The ball
speeds up at each hit, so sooner or later a paddle cannot reach it: a point is scored. A match is played to
11 points, then a new match starts.

Usage:
    python grm_pong.py                 # tkinter window
    python grm_pong.py --headless 3    # play 3 matches without a window and print the scores
"""
import argparse
import math
import random

from grm import GlobalRelationalNetwork

WIDTH, HEIGHT = 800, 500
BALL_RADIUS = 8
PADDLE_HEIGHT, PADDLE_WIDTH, PADDLE_MARGIN = 80, 10, 30
BALL_SPEED_START, BALL_SPEED_MAX, SPEED_UP = 450.0, 1350.0, 1.08
ESCAPE_SIGMA = 0.3                 # tolerance of the escape tension (see aim_network)
EDGE_SIGMAS = 3.0                  # the hit must stay on the paddle even 3 sigma away from the prediction
SAFETY_SIGMA = 0.4                 # hit offset measured at 0 with this sigma, in paddle heights
MAX_ANGLE = math.radians(55)       # return angle for a hit on the very edge of the paddle
POINTS_TO_WIN = 11
DT = 1.0 / 240                     # physics step (s)


def fold(u):
    """Position of the ball centre after bouncing between the two walls (a triangle wave)."""
    lo, span = BALL_RADIUS, HEIGHT - 2 * BALL_RADIUS
    v = (u - lo) % (2 * span)
    return lo + (v if v <= span else 2 * span - v)


# ------------------------------------------------------------------ the two networks of a paddle
def intercept_network(x_plane, seen, sigma_pos, sigma_vel):
    """Where and when the ball will cross the paddle line, from noisy perception. Returns (y_hit, sigma, t)."""
    x, y, vx, vy = seen
    t_guess = max((x_plane - x) / vx, 1e-3)
    nodes = {"t": {"guess": t_guess},
             "x": {"guess": x, "scale": "lin"}, "y": {"guess": y, "scale": "lin"},
             "vx": {"guess": vx, "scale": "lin"}, "vy": {"guess": vy, "scale": "lin"},
             "y_hit": {"guess": fold(y + vy * t_guess), "scale": "lin"}}
    rels = [
        {"name": "reach", "type": "fn", "nodes": ["x", "vx", "t"], "sigma": 0.01,
         "f": lambda v: v["x"] + v["vx"] * v["t"] - x_plane},
        {"name": "walls", "type": "fn", "nodes": ["y_hit", "y", "vy", "t"], "sigma": 0.01,
         "f": lambda v: v["y_hit"] - fold(v["y"] + v["vy"] * v["t"])},
    ]
    measured = {"x": (x, sigma_pos), "y": (y, sigma_pos), "vx": (vx, sigma_vel), "vy": (vy, sigma_vel)}
    out = GlobalRelationalNetwork(nodes, rels).solve(measured, max_iterations=20)
    return out["values"]["y_hit"], out["uncertainty"]["y_hit"], out["values"]["t"]


def return_velocity(offset, speed, direction):
    """Velocity of the ball after a hit at `offset` from the paddle centre (direction +1 to the right)."""
    angle = MAX_ANGLE * max(-1.0, min(1.0, offset / (PADDLE_HEIGHT / 2)))
    s = min(speed * SPEED_UP, BALL_SPEED_MAX)
    return direction * s * math.cos(angle), s * math.sin(angle)


def aim_network(y_hit, speed, direction, opponent_y, opponent_speed, my_y=None, my_reach=None, sigma_hit=0.0):
    """Offset of the hit on the paddle that sends the ball out of the opponent's reach, while staying within
    my own reach (how far I can move before the ball arrives). Returns (offset, y_land)."""
    distance = WIDTH - 2 * PADDLE_MARGIN

    def self_reach(v):
        if my_y is None:
            return 0.0
        excess = abs(y_hit - v["o"] - my_y) - my_reach
        return max(0.0, excess) / (PADDLE_HEIGHT / 8)

    def edge(v):
        # the ball may arrive EDGE_SIGMAS sigma away from y_hit: it must still meet the paddle
        room = PADDLE_HEIGHT / 2 + BALL_RADIUS - EDGE_SIGMAS * sigma_hit
        return max(0.0, abs(v["o"]) - max(room, 0.0)) / 2.0

    def landing(v):
        vx, vy = return_velocity(v["o"], speed, direction)
        return fold(y_hit + vy * distance / abs(vx))

    def escape(v):
        reach = opponent_speed * distance / abs(return_velocity(v["o"], speed, direction)[0])
        return reach / (abs(v["y_land"] - opponent_y) + 20.0)

    best = None
    for o_start in (-PADDLE_HEIGHT / 3, 0.0, PADDLE_HEIGHT / 3):
        nodes = {"o": {"guess": o_start, "scale": "lin"},
                 "y_land": {"guess": landing({"o": o_start}), "scale": "lin"}}
        rels = [
            {"name": "landing", "type": "fn", "nodes": ["o", "y_land"], "sigma": 0.01,
             "f": lambda v: v["y_land"] - landing(v)},
            {"name": "escape", "type": "fn", "nodes": ["o", "y_land"], "sigma": ESCAPE_SIGMA, "f": escape},
            {"name": "self_reach", "type": "fn", "nodes": ["o"], "sigma": 0.1, "f": self_reach},
            {"name": "edge", "type": "fn", "nodes": ["o"], "sigma": 0.1, "f": edge},
        ]
        try:
            out = GlobalRelationalNetwork(nodes, rels).solve({"o": (0.0, SAFETY_SIGMA * PADDLE_HEIGHT)},
                                                             max_iterations=15, tolerance=1e-8,
                                                             compute_uncertainty=False)
        except (ValueError, ArithmeticError):
            continue
        if best is None or out["cost"] < best["cost"]:
            best = out
    if best is None:
        return 0.0, y_hit
    o = max(-PADDLE_HEIGHT / 2 + 4, min(PADDLE_HEIGHT / 2 - 4, best["values"]["o"]))
    return o, best["values"]["y_land"]


# ------------------------------------------------------------------ players and game
class Paddle:
    def __init__(self, name, x, direction, noise=8.0, max_speed=290.0, reaction=0.14, seed=0, aims=True):
        self.name, self.x, self.direction = name, x, direction   # direction: where it sends the ball
        self.aims = aims             # False: only the intercept network, the ball is sent back from the centre
        self.noise, self.max_speed, self.reaction = noise, max_speed, reaction
        self.y = HEIGHT / 2
        self.target = HEIGHT / 2
        self.timer = 0.0
        self.rng = random.Random(seed)
        self.thought = None          # (y_hit, sigma, t, offset, y_land) for the display

    def perceive(self, ball):
        """Noisy view of the ball: the farther it is, the less precise."""
        far = 1.0 + abs(ball.x - self.x) / WIDTH
        sp, sv = self.noise * far, self.noise * 4.0 * far
        g = self.rng.gauss
        return (ball.x + g(0, sp), ball.y + g(0, sp), ball.vx + g(0, sv), ball.vy + g(0, sv)), sp, sv

    def think(self, ball, opponent):
        coming = (ball.vx < 0) == (self.direction > 0)          # the ball moves towards me
        if not coming:
            self.target, self.thought = HEIGHT / 2, None
            return
        seen, sp, sv = self.perceive(ball)
        if (self.x - seen[0]) * seen[2] <= 0:                  # noise says it moves away: wait
            return
        y_hit, sigma, t = intercept_network(self.x, seen, sp, sv)
        if not self.aims:
            self.target, self.thought = y_hit, (y_hit, sigma, t, 0.0, None)
            return
        my_reach = self.max_speed * max(t - self.reaction, 0.0)
        offset, y_land = aim_network(y_hit, math.hypot(ball.vx, ball.vy), self.direction,
                                     opponent.target, opponent.max_speed, self.y, my_reach, sigma)
        self.target = y_hit - offset
        self.thought = (y_hit, sigma, t, offset, y_land)

    def move(self, dt):
        step = self.target - self.y
        limit = self.max_speed * dt
        self.y += max(-limit, min(limit, step))
        self.y = max(PADDLE_HEIGHT / 2, min(HEIGHT - PADDLE_HEIGHT / 2, self.y))


class Ball:
    def __init__(self):
        self.x, self.y, self.vx, self.vy = WIDTH / 2, HEIGHT / 2, 0.0, 0.0


class PongGame:
    def __init__(self, seed=0):
        self.rng = random.Random(seed)
        self.a = Paddle("A", PADDLE_MARGIN, +1, seed=seed * 2 + 1)
        self.b = Paddle("B", WIDTH - PADDLE_MARGIN, -1, seed=seed * 2 + 2)
        self.ball = Ball()
        self.score = {"A": 0, "B": 0}
        self.matches = {"A": 0, "B": 0}
        self.rally = 0
        self.longest_rally = 0
        self.pause = 0.0
        self.message = ""
        self.serve(towards=self.rng.choice((-1, 1)))

    def serve(self, towards):
        b = self.ball
        b.x, b.y = WIDTH / 2, self.rng.uniform(HEIGHT * 0.3, HEIGHT * 0.7)
        angle = self.rng.uniform(-0.5, 0.5)
        b.vx, b.vy = towards * BALL_SPEED_START * math.cos(angle), BALL_SPEED_START * math.sin(angle)
        self.rally = 0
        self.pause = 0.8
        for p in (self.a, self.b):
            p.timer = 0.0

    def point(self, winner):
        self.score[winner] += 1
        self.longest_rally = max(self.longest_rally, self.rally)
        self.message = f"point {winner}"
        if self.score[winner] >= POINTS_TO_WIN:
            self.matches[winner] += 1
            self.message = f"{winner} wins {self.score['A']}-{self.score['B']}"
            self.score = {"A": 0, "B": 0}
            self.serve(towards=self.rng.choice((-1, 1)))
            self.pause = 3.0
            return winner
        self.serve(towards=1 if winner == "A" else -1)   # the next ball goes to the one who lost the point
        return None

    def step(self, dt=DT):
        """Advance the game by dt. Returns the name of a match winner when a match ends, else None."""
        if self.pause > 0:
            self.pause -= dt
            if self.pause <= 0:
                self.message = ""
            for p in (self.a, self.b):
                p.move(dt)
            return None
        for p, other in ((self.a, self.b), (self.b, self.a)):
            p.timer -= dt
            if p.timer <= 0:
                p.think(self.ball, other)
                p.timer = p.reaction
            p.move(dt)
        b = self.ball
        b.x += b.vx * dt
        b.y += b.vy * dt
        if b.y < BALL_RADIUS:
            b.y, b.vy = 2 * BALL_RADIUS - b.y, -b.vy
        elif b.y > HEIGHT - BALL_RADIUS:
            b.y, b.vy = 2 * (HEIGHT - BALL_RADIUS) - b.y, -b.vy
        for p in (self.a, self.b):
            face = p.x + p.direction * PADDLE_WIDTH / 2                    # the side that faces the court
            back = p.x - p.direction * PADDLE_WIDTH / 2                    # a ball already behind is lost
            crossing = (b.vx < 0 and p.direction > 0 and b.x - BALL_RADIUS <= face and b.x + BALL_RADIUS >= back) or \
                       (b.vx > 0 and p.direction < 0 and b.x + BALL_RADIUS >= face and b.x - BALL_RADIUS <= back)
            if crossing and abs(b.y - p.y) <= PADDLE_HEIGHT / 2 + BALL_RADIUS:
                b.x = face + p.direction * BALL_RADIUS
                b.vx, b.vy = return_velocity(b.y - p.y, math.hypot(b.vx, b.vy), p.direction)
                self.rally += 1
        if b.x < -BALL_RADIUS:
            return self.point("B")
        if b.x > WIDTH + BALL_RADIUS:
            return self.point("A")
        return None


# ------------------------------------------------------------------ window
def run_window():
    import tkinter as tk
    from tkinter import ttk

    game = PongGame(seed=random.randrange(10 ** 6))
    root = tk.Tk()
    root.title("GRM Pong")
    root.configure(bg="#14161a")
    canvas = tk.Canvas(root, width=WIDTH, height=HEIGHT, bg="#0d0f12", highlightthickness=0)
    canvas.grid(row=0, column=0, columnspan=2, padx=10, pady=10)
    state = {"running": True, "speed": tk.DoubleVar(value=1.0), "show": tk.BooleanVar(value=True)}

    panel = tk.Frame(root, bg="#14161a")
    panel.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 10))
    readouts = {}
    for col, p in enumerate((game.a, game.b)):
        box = tk.LabelFrame(panel, text=f"Paddle {p.name}", bg="#14161a", fg="#d8dee9", padx=6, pady=4)
        box.grid(row=0, column=col, padx=4, sticky="n")
        for row, (label, attr, lo, hi, fmt) in enumerate((("noise (px)", "noise", 0.0, 30.0, "{:.0f}"),
                                                          ("speed (px/s)", "max_speed", 150.0, 900.0, "{:.0f}"),
                                                          ("reaction (s)", "reaction", 0.02, 0.4, "{:.2f}"))):
            tk.Label(box, text=label, bg="#14161a", fg="#aab").grid(row=row, column=0, sticky="w")
            var = tk.DoubleVar(value=getattr(p, attr))
            shown = tk.Label(box, text=fmt.format(var.get()), width=5, bg="#14161a", fg="#d8dee9")
            shown.grid(row=row, column=2)

            def changed(_v, name=p.name, attr=attr, var=var, shown=shown, fmt=fmt):
                setattr(getattr(game, name.lower()), attr, var.get())     # the current game's paddle
                shown.config(text=fmt.format(var.get()))
            ttk.Scale(box, from_=lo, to=hi, variable=var, length=120, command=changed).grid(row=row, column=1)
        aims = tk.BooleanVar(value=True)
        tk.Checkbutton(box, text="aims (aim network)", variable=aims, bg="#14161a", fg="#aab", selectcolor="#14161a",
                       activebackground="#14161a",
                       command=lambda name=p.name, v=aims: setattr(getattr(game, name.lower()), "aims", v.get())
                       ).grid(row=3, column=0, columnspan=3, sticky="w")
        readouts[p.name] = tk.Label(box, text="", bg="#14161a", fg=("#7fb4ff", "#ffb37f")[col], width=34,
                                    anchor="w", justify="left", font=("Courier", 9))
        readouts[p.name].grid(row=4, column=0, columnspan=3, sticky="w")
    ctrl = tk.Frame(panel, bg="#14161a")
    ctrl.grid(row=0, column=2, padx=4, sticky="n")
    tk.Label(ctrl, text="game speed", bg="#14161a", fg="#aab").grid(row=0, column=0, columnspan=2)
    ttk.Scale(ctrl, from_=0.2, to=3.0, variable=state["speed"], length=120).grid(row=1, column=0, columnspan=2)
    pause_btn = ttk.Button(ctrl, text="Pause", width=7)
    pause_btn.grid(row=2, column=0, pady=4)

    def toggle():
        state["running"] = not state["running"]
        pause_btn.config(text="Pause" if state["running"] else "Play")

    def restart():
        nonlocal game
        old = game
        game = PongGame(seed=random.randrange(10 ** 6))
        for p_new, p_old in ((game.a, old.a), (game.b, old.b)):
            p_new.noise, p_new.max_speed, p_new.reaction, p_new.aims = \
                p_old.noise, p_old.max_speed, p_old.reaction, p_old.aims

    pause_btn.config(command=toggle)
    ttk.Button(ctrl, text="New", width=7, command=restart).grid(row=2, column=1, pady=4)
    tk.Checkbutton(ctrl, text="show thoughts", variable=state["show"], bg="#14161a", fg="#aab",
                   selectcolor="#14161a", activebackground="#14161a").grid(row=3, column=0, columnspan=2)

    colours = {"A": "#7fb4ff", "B": "#ffb37f"}

    def draw():
        c = canvas
        c.delete("all")
        for y in range(0, HEIGHT - 36, 24):
            c.create_line(WIDTH / 2, y, WIDTH / 2, y + 12, fill="#2a2f38", width=2)
        c.create_text(WIDTH / 2 - 60, 40, text=str(game.score["A"]), fill=colours["A"], font=("Helvetica", 36, "bold"))
        c.create_text(WIDTH / 2 + 60, 40, text=str(game.score["B"]), fill=colours["B"], font=("Helvetica", 36, "bold"))
        c.create_text(WIDTH / 2, HEIGHT - 16, fill="#667",
                      text=f"matches  A {game.matches['A']} - {game.matches['B']} B     rally {game.rally}     "
                           f"longest {max(game.longest_rally, game.rally)}     "
                           f"ball {math.hypot(game.ball.vx, game.ball.vy):.0f} px/s", font=("Helvetica", 11))
        b = game.ball
        for p in (game.a, game.b):
            if p.thought:
                y_hit, sigma, t, offset, y_land = p.thought
                text = f"hit {y_hit:5.0f} \u00b1{sigma:3.0f} px in {t:4.2f} s"
                if y_land is not None:
                    text += f"\naim {offset:+4.0f} px -> lands {y_land:4.0f}"
                readouts[p.name].config(text=text)
            else:
                readouts[p.name].config(text="waiting\n")
            if state["show"].get() and p.thought:
                y_hit, sigma, _t, offset, y_land = p.thought
                c.create_line(b.x, b.y, p.x, y_hit, fill="#3a404c", dash=(3, 4))          # the relation
                s = min(sigma, HEIGHT)
                c.create_rectangle(p.x - 3, y_hit - s, p.x + 3, y_hit + s, outline=colours[p.name])
                c.create_oval(p.x - 4, y_hit - 4, p.x + 4, y_hit + 4, fill=colours[p.name], outline="")
                if y_land is not None:
                    far_x = WIDTH - p.x
                    c.create_line(far_x - 10, y_land, far_x + 10, y_land, fill=colours[p.name], width=3)
            c.create_rectangle(p.x - PADDLE_WIDTH / 2, p.y - PADDLE_HEIGHT / 2, p.x + PADDLE_WIDTH / 2,
                               p.y + PADDLE_HEIGHT / 2, fill=colours[p.name], outline="")
        c.create_oval(b.x - BALL_RADIUS, b.y - BALL_RADIUS, b.x + BALL_RADIUS, b.y + BALL_RADIUS,
                      fill="#f2f2f2", outline="")
        if game.message:
            c.create_text(WIDTH / 2, HEIGHT / 2, text=game.message, fill="#d8dee9", font=("Helvetica", 22, "bold"))

    def tick():
        if state["running"]:
            steps = max(1, int(round(state["speed"].get() * (1 / 60) / DT)))
            for _ in range(steps):
                game.step()
        draw()
        root.after(16, tick)

    tick()
    root.mainloop()


def run_headless(matches, seed=0):
    game = PongGame(seed=seed)
    seconds = 0.0
    while sum(game.matches.values()) < matches:
        winner = game.step()
        seconds += DT
        if winner:
            print(f"match {sum(game.matches.values())}: {game.message}   "
                  f"(longest rally so far {game.longest_rally}, {seconds:.0f} s of play)")
    return game


def main():
    ap = argparse.ArgumentParser(description="GRM Pong: two paddles that play by themselves.")
    ap.add_argument("--headless", type=int, metavar="MATCHES", help="play without a window")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    if args.headless:
        run_headless(args.headless, args.seed)
    else:
        run_window()


if __name__ == "__main__":
    main()
