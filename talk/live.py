# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Anthony Charretier
"""The network drawn while it works.

Circles are the nodes, squares the relations, a line joins a relation to each of its nodes. While the relational
machine runs:
  - a node lights up when it moves (the brighter, the more it moved in the last round; a white ring: measured);
  - a relation turns red when it does not hold yet (its tension, in its own sigmas), grey when it holds.
The title gives the round and how far the nodes still move. Answers to questions (ask, why) light the nodes and
relations they speak of.

With a screen, the window updates as the machine runs. Without one (matplotlib's Agg backend), each update is
written to a picture (talk_live.png by default).
"""
import math

try:
    import matplotlib
    import matplotlib.pyplot as plt
    import numpy as np
except ImportError:  # pragma: no cover
    plt = None


def available():
    return plt is not None


def layout(problem, seed=1, steps=300):
    """A force layout of the factor graph (priors left out): linked things pull, everything pushes."""
    P = problem
    shown = [f for f, fac in enumerate(P.factors) if fac[4] == "relation"]
    n, m = len(P.names), len(shown)
    rng = np.random.default_rng(seed)
    pos = rng.uniform(-1, 1, (n + m, 2))
    edges = []
    for k, f in enumerate(shown):
        for i, _ in P.factors[f][1]:
            edges.append((i, n + k))
    edges = np.array(edges, dtype=int).reshape(-1, 2)
    total = n + m
    area = 1.5 / math.sqrt(total)
    for step in range(steps):
        t = 0.1 * (1 - step / steps) + 0.005
        if total <= 1200:
            d = pos[:, None, :] - pos[None, :, :]
            dist = np.sqrt((d ** 2).sum(-1)) + 1e-9
            push = (d / dist[..., None] ** 2 * area ** 2).sum(1)
        else:  # many things: push against a sample only
            sample = rng.choice(total, 600, replace=False)
            d = pos[:, None, :] - pos[None, sample, :]
            dist = np.sqrt((d ** 2).sum(-1)) + 1e-9
            push = (d / dist[..., None] ** 2 * area ** 2).sum(1) * (total / 600)
        move = push - 0.05 * pos * np.sqrt((pos ** 2).sum(-1, keepdims=True))   # gravity: nothing drifts away
        if len(edges):
            d = pos[edges[:, 0]] - pos[edges[:, 1]]
            dist = np.sqrt((d ** 2).sum(-1)) + 1e-9
            pull = d * (dist / area)[:, None]
            np.add.at(move, edges[:, 0], -pull)
            np.add.at(move, edges[:, 1], pull)
        length = np.sqrt((move ** 2).sum(-1)) + 1e-9
        pos += move / length[:, None] * np.minimum(length, t)[:, None]
        pos -= pos.mean(0)
    return pos, shown, edges


class LiveGraph:
    def __init__(self, problem, out="talk_live.png", labels=None):
        self.p = problem
        self.out = out
        self.pos, self.shown, self.edges = layout(problem)
        self.interactive = matplotlib.get_backend().lower() not in ("agg", "pdf", "svg", "ps", "cairo", "template")
        if self.interactive:
            plt.ion()
        self.fig, self.ax = plt.subplots(figsize=(9, 7))
        self.fig.patch.set_facecolor("#14161a")
        self.ax.set_facecolor("#14161a")
        self.ax.set_axis_off()
        n = len(problem.names)
        self.n = n
        from matplotlib.collections import LineCollection
        segs = [(self.pos[a], self.pos[b]) for a, b in self.edges]
        self.lines = LineCollection(segs, colors="#4b525e", linewidths=0.8, zorder=1)
        self.ax.add_collection(self.lines)
        measured = {i for f, fac in enumerate(problem.factors) if fac[4] == "measure" for i, _ in fac[1]}
        from matplotlib.colors import LinearSegmentedColormap
        moving = LinearSegmentedColormap.from_list("moving", ["#5b6472", "#8a6db8", "#e0607e", "#ffb347", "#fff2a8"])
        self.node_art = self.ax.scatter(self.pos[:n, 0], self.pos[:n, 1], s=self._sizes(), c=np.full(n, -12.0),
                                        cmap=moving, vmin=-9, vmax=0, zorder=3,
                                        edgecolors=["#ffffff" if i in measured else "#14161a" for i in range(n)],
                                        linewidths=[1.2 if i in measured else 0.3 for i in range(n)])
        holds = LinearSegmentedColormap.from_list("holds", ["#6f7682", "#c0504d", "#ff3b30"])
        self.rel_art = self.ax.scatter(self.pos[n:, 0], self.pos[n:, 1], s=22, marker="s", c=np.zeros(len(self.shown)),
                                       cmap=holds, vmin=0, vmax=3, zorder=2, edgecolors="#14161a", linewidths=0.3)
        self.ax.text(1.0, -0.02, "circle: node (bright: moving; white ring: measured)   square: relation (red: does "
                     "not hold yet)", transform=self.ax.transAxes, color="#7d838d", fontsize=7, va="top", ha="right")
        self.texts = []
        show_labels = labels if labels is not None else n <= 40
        if show_labels:
            for i, name in enumerate(problem.names):
                self.texts.append(self.ax.text(self.pos[i, 0], self.pos[i, 1], " " + name, color="#c8ccd4",
                                               fontsize=8, zorder=4, va="center"))
            for k, f in enumerate(self.shown):
                self.ax.text(self.pos[n + k, 0], self.pos[n + k, 1], " " + problem.factors[f][0], color="#8a6060",
                             fontsize=7, zorder=4, va="center")
        self.title = self.ax.set_title("", color="#e6e8ec", fontsize=10, loc="left")
        self.note = self.ax.text(0.0, -0.06, "", transform=self.ax.transAxes, color="#9aa0aa", fontsize=8, va="top")
        self.ax.set_aspect("equal")
        self.ax.autoscale_view()

    def _sizes(self):
        deg = np.array([len(nf) for nf in self.p.node_factors], dtype=float)
        return 18 + 10 * np.sqrt(deg)

    def update(self, x, moves, round_, moved, note=""):
        P = self.p
        bright = np.log10(np.maximum(np.asarray(moves, dtype=float), 1e-12))
        self.node_art.set_array(bright)
        tens = [abs(P.tension(x, f)) for f in self.shown]
        self.rel_art.set_array(np.minimum(np.array(tens, dtype=float), 3.0))
        self.title.set_text(f"round {round_}   the nodes still move by {moved:.2e} dex")
        self.note.set_text(note)
        self.draw()

    def highlight(self, nodes=(), relations=(), note=""):
        """Lights the nodes and relations an answer speaks of; the rest fades."""
        n = self.n
        ns = {self.p.index[a] for a in nodes if a in self.p.index}
        rs = {k for k, f in enumerate(self.shown) if self.p.factors[f][0] in set(relations)}
        self.node_art.set_alpha([1.0 if (not ns or i in ns) else 0.25 for i in range(n)])
        self.rel_art.set_alpha([1.0 if (not rs or k in rs) else 0.2 for k in range(len(self.shown))])
        colours = []
        for a, b in self.edges:
            on = (a in ns) and (b - n in rs)
            colours.append("#d8b04a" if on else "#4b525e")
        self.lines.set_colors(colours)
        self.note.set_text(note)
        self.draw()

    def draw(self):
        if self.interactive:
            self.fig.canvas.draw_idle()
            plt.pause(0.001)
        else:
            self.fig.savefig(self.out, dpi=110, facecolor=self.fig.get_facecolor())

    def close(self):
        plt.close(self.fig)
