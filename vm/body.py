# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Anthony Charretier
"""The body of the GRM machine: the converters between the network's outputs and a human's eyes and ears.

Nothing here decides anything: the network gives its outputs, the body shows and plays them.
  - The eyes: a window in three parts. On the left, the words typed to the machine (coloured as they are typed, Tab
    completes, Up and Down go back through what was typed) and its answers. In the middle, the network itself: a
    round for each node, a square for each relation, a line for each link; the mouse over one of them shows what it
    holds; a relation far from holding turns red; above, the master equation, now or at t - n. On the right, the
    outputs: each one with its value, its two opposed channels around zero (ON to the right, OFF to the left) and
    its last 240 ticks; the network's surprise (how far its last inputs were from what it expected of them), its
    pleasure and how it flourishes.
  - The ears: each output is a pair of opposed voices, as the senses and the muscles have them (ON and OFF cells,
    agonist and antagonist): above zero one voice from 440 Hz, below zero another from 220 Hz, higher as the value is
    larger (on a log scale of its size: Weber's law); its loudness is how much it has just moved. A network that
    holds still is silent.
"""
import io
import math
import struct
import time
import wave

RATE = 22050
BLOCK = 0.15          # s of sound a tick


def sound_of(history, rate=RATE, length=BLOCK):
    """One block of sound from the outputs' last values. As the senses and the muscles do, each output is a pair of
    opposed channels: ON when it is above zero (a voice from 440 Hz), OFF when it is below (a voice from 220 Hz),
    one octave higher at the largest it has been (pitch on a log scale of its size, as Weber's law has it).
    Loudness: how much it has just moved. A network that holds still is silent."""
    n = int(rate * length)
    out = [0.0] * n
    voices = 0
    for name, h in history.items():
        if len(h) < 2:
            continue
        size = max(abs(v) for v in h)
        if size <= 0:
            continue
        moved = min(1.0, abs(h[-1] - h[-2]) / size)
        if moved < 1e-6:
            continue
        base = 440.0 if h[-1] >= 0 else 220.0                      # the ON channel, or the OFF one
        f = base * 2.0 ** (math.log1p(9.0 * abs(h[-1]) / size) / math.log(10.0))
        a = 0.25 * moved ** 0.5
        voices += 1
        for k in range(n):
            t = k / rate
            env = min(1.0, t / 0.01) * math.exp(-t / (0.4 * length))
            out[k] += a * env * math.sin(2 * math.pi * f * t)
    if not voices:
        return []
    peak = max(1.0, max(abs(s) for s in out))
    return [s / peak for s in out]


def play(samples, rate=RATE):
    if not samples:
        return
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"".join(struct.pack("<h", int(max(-1.0, min(1.0, s)) * 30000)) for s in samples))
    try:
        import winsound
        winsound.PlaySound(buf.getvalue(), winsound.SND_MEMORY | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
        return
    except (ImportError, RuntimeError):
        pass
    try:
        import numpy as np
        import sounddevice as sd
        sd.play(np.array(samples, dtype="float32"), rate)
    except Exception:  # noqa: BLE001 - no sound on this machine: the body is deaf, the machine goes on
        pass


class _Log:
    """The Shell writes here; the window shows it, coloured: what was typed as the editor colours it, errors in red,
    what the machine did by itself in teal, questions it could not answer in amber."""

    def __init__(self, text, words):
        self.text = text
        self.words = words          # () -> (nodes, relations, commands)

    def write(self, s):
        import editor
        self.text.configure(state="normal")
        for line in s.splitlines(keepends=True):
            body = line.rstrip("\n")
            if body.startswith("grm> "):
                self.text.insert("end", "grm> ", ("prompt",))
                start = self.text.index("end-1c")
                self.text.insert("end", body[5:])
                nodes, relations, commands = self.words()
                for a, b, kind in editor.tokens(body[5:], nodes, relations, commands):
                    self.text.tag_add(kind, f"{start}+{a}c", f"{start}+{b}c")
                self.text.insert("end", line[len(body):])
            elif body.lstrip().startswith("! "):
                self.text.insert("end", line, ("error",))
            elif body.lstrip().startswith("~ "):
                self.text.insert("end", line, ("self",))
            elif body.lstrip().startswith("? "):
                self.text.insert("end", line, ("question",))
            else:
                self.text.insert("end", line)
        self.text.see("end")
        self.text.configure(state="disabled")

    def flush(self):
        pass


BG, PANEL, INK, DIM, LINE = "#0e1016", "#14161a", "#c8ccd4", "#7d838d", "#4b525e"
ROLE_COLOURS = {"input": "#5fa8d3", "output": "#ffb347", "var": "#c792ea", "learn": "#a3be8c",
                "fixed": "#7d838d", None: "#d0d4dc"}
HOLDS, STRAINED, BROKEN = "#56606e", "#e5c07b", "#e06c75"


def _role(spec):
    for r in ("output", "input", "learn", "var", "fixed"):
        if spec.get(r):
            return r
    return None


class NetworkView:
    """The network drawn on a canvas, what is under the mouse shown, dragging moves a node (it stays there) or the
    whole picture, the wheel zooms."""

    def __init__(self, canvas, vm):
        import graph
        self.graph = graph
        self.c = canvas
        self.vm = vm
        self.places = {}
        self.pinned = set()
        self.zoom, self.pan = 1.0, [0.0, 0.0]
        self.hover = None           # the key under the mouse, and where the mouse was
        self.mouse = (0, 0)
        self.drag = None
        self.items = {}             # canvas item -> key
        c = canvas
        c.bind("<Motion>", self.on_motion)
        c.bind("<Leave>", lambda e: self.set_hover(None))
        c.bind("<ButtonPress-1>", self.on_press)
        c.bind("<B1-Motion>", self.on_drag)
        c.bind("<ButtonRelease-1>", lambda e: setattr(self, "drag", None))
        c.bind("<MouseWheel>", lambda e: self.on_zoom(e, 1.1 if e.delta > 0 else 1 / 1.1))
        c.bind("<Button-4>", lambda e: self.on_zoom(e, 1.1))
        c.bind("<Button-5>", lambda e: self.on_zoom(e, 1 / 1.1))
        c.bind("<Double-Button-1>", lambda e: self.reset())
        c.bind("<Configure>", lambda e: self.draw(steps=0))

    # ---- geometry
    def fit(self):
        """The whole picture in the pane (labels included), before the human's zoom and pan."""
        w, h = max(self.c.winfo_width(), 50), max(self.c.winfo_height(), 50)
        if not self.places:
            self.fitted = (0.0, 0.0, 0.9 * min(w, h))
            return
        xs = [p[0] for p in self.places.values()]
        ys = [p[1] for p in self.places.values()]
        bw, bh = max(max(xs) - min(xs), 1e-3), max(max(ys) - min(ys), 1e-3)
        scale = min((w - 190) / bw, (h - 70) / bh)
        self.fitted = ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, max(scale, 1.0))

    def frame(self):
        w, h = max(self.c.winfo_width(), 50), max(self.c.winfo_height(), 50)
        if not hasattr(self, "fitted"):
            self.fit()
        mx, my, scale = self.fitted
        s = scale * self.zoom
        return w / 2 - 40 + self.pan[0] - mx * s, h / 2 - 10 + self.pan[1] - my * s, s

    def to_screen(self, p):
        cx, cy, s = self.frame()
        return cx + p[0] * s, cy + p[1] * s

    def to_place(self, x, y):
        cx, cy, s = self.frame()
        return [(x - cx) / s, (y - cy) / s]

    def reset(self):
        self.zoom, self.pan = 1.0, [0.0, 0.0]
        self.pinned.clear()
        self.draw(steps=40)

    # ---- the mouse
    def key_at(self, x, y):
        for item in reversed(self.c.find_overlapping(x - 3, y - 3, x + 3, y + 3)):
            if item in self.items:
                return self.items[item]
        return None

    def on_motion(self, e):
        self.mouse = (e.x, e.y)
        self.set_hover(self.key_at(e.x, e.y))

    def set_hover(self, key):
        self.c.delete("tip")
        self.hover = key
        if key is not None:
            self.tip()

    def on_press(self, e):
        key = self.key_at(e.x, e.y)
        self.drag = ("key", key, e.x, e.y) if key else ("pan", None, e.x, e.y)

    def on_drag(self, e):
        if not self.drag:
            return
        what, key, x0, y0 = self.drag
        if what == "key" and key in self.places:
            self.places[key] = self.to_place(e.x, e.y)
            self.pinned.add(key)
        else:
            self.pan[0] += e.x - x0
            self.pan[1] += e.y - y0
        self.drag = (what, key, e.x, e.y)
        self.mouse = (e.x, e.y)
        self.draw(steps=0)

    def on_zoom(self, e, k):
        p = self.to_place(e.x, e.y)       # the point under the mouse stays under the mouse
        self.zoom *= k
        x, y = self.to_screen(p)
        self.pan[0] += e.x - x
        self.pan[1] += e.y - y
        self.draw(steps=0)

    # ---- drawing
    def tip(self):
        kind, name = self.hover
        try:
            lines = (self.graph.node_card if kind == "n" else self.graph.relation_card)(self.vm, name)
        except Exception as ex:  # noqa: BLE001 - the card says why it could not be made
            lines = [name, f"(cannot read it: {type(ex).__name__}: {ex})"]
        x, y = self.mouse
        t = self.c.create_text(x + 14, y + 14, text="\n".join(lines), anchor="nw", fill="#e6e8ec",
                               font=("Consolas", 9), tags=("tip",))
        x0, y0, x1, y1 = self.c.bbox(t)
        w, h = self.c.winfo_width(), self.c.winfo_height()
        dx = min(0, w - 6 - x1) if x1 > w - 6 else 0
        dy = min(0, h - 6 - y1) if y1 > h - 6 else 0
        if dx or dy:
            self.c.move(t, dx if x0 + dx > 4 else -x0 + 4, dy if y0 + dy > 4 else -y0 + 4)
            x0, y0, x1, y1 = self.c.bbox(t)
        r = self.c.create_rectangle(x0 - 6, y0 - 4, x1 + 6, y1 + 4, fill="#1f232b", outline="#3e4451", tags=("tip",))
        self.c.tag_lower(r, t)

    def draw(self, steps=6):
        vm, c = self.vm, self.c
        net = vm.net
        self.graph.layout(net, self.places, steps=steps, pinned=self.pinned)
        if not self.drag:
            self.fit()
        c.delete("all")
        self.items = {}
        m = vm.machine
        strain, active, moving = {}, {}, set()
        if m is not None:
            for f in m.factors:
                if f.kind in ("relation", "nonlinear", "keep"):
                    if f.watch:
                        active[f.name] = f.active
                    if f.kind != "keep" and f.w > 0:
                        try:
                            strain[f.name] = abs(m.residual(f))
                        except (OverflowError, ValueError, ZeroDivisionError):
                            strain[f.name] = float("inf")
            moving = {m.var_names[i] for i, d in enumerate(m.last_move) if d > 1e-9}
        few = len(net.nodes) <= 80
        # the links first, under everything
        for r in net.relations:
            rp = self.places.get(("r", r["name"]))
            if rp is None:
                continue
            x0, y0 = self.to_screen(rp)
            colour = self.colour(strain.get(r["name"]))
            dash = (3, 3) if active.get(r["name"]) is False else None
            for n in dict.fromkeys(net.nodes_of(r)):
                np_ = self.places.get(("n", n))
                if np_ is None:
                    continue
                x1, y1 = self.to_screen(np_)
                c.create_line(x0, y0, x1, y1, fill=colour, width=1.4, dash=dash)
        # the writes of each tick (set): an arrow from what is written to what it writes
        for st in net.sets:
            a, b = self.places.get(("n", st["source"])), self.places.get(("n", st["target"]))
            if a is None or b is None or a is b:
                continue
            (x0, y0), (x1, y1) = self.to_screen(a), self.to_screen(b)
            c.create_line(x0, y0, x1, y1, fill="#7e5aa8", dash=(4, 3), arrow="last", arrowshape=(8, 9, 3))
        for r in net.relations:
            rp = self.places.get(("r", r["name"]))
            if rp is None:
                continue
            x, y = self.to_screen(rp)
            colour = self.colour(strain.get(r["name"]))
            item = c.create_rectangle(x - 5, y - 5, x + 5, y + 5, fill=colour, outline="#0b0d12")
            self.items[item] = ("r", r["name"])
            if few or net.origin["relations"].get(r["name"]) != "base":
                c.create_text(x, y - 12, text=r["name"], fill="#8b919c", font=("Consolas", 8))
        for n, spec in net.nodes.items():
            p = self.places.get(("n", n))
            if p is None:
                continue
            x, y = self.to_screen(p)
            base = net.origin["nodes"].get(n) == "base"
            role = _role(spec)
            size = 9 if role in ("input", "output") else 4 if base else 7
            fill = ROLE_COLOURS.get(role, ROLE_COLOURS[None])
            if base:
                fill = "#6b7280"
            dash = (2, 2) if net.origin["nodes"].get(n) == "found" else None
            item = c.create_oval(x - size, y - size, x + size, y + size, fill=fill, outline="#0b0d12", dash=dash)
            self.items[item] = ("n", n)
            if n in moving:
                c.create_oval(x - size - 4, y - size - 4, x + size + 4, y + size + 4, outline="#ffffff", width=1)
            if few or not base:
                c.create_text(x + size + 4, y, text=n, anchor="w", fill="#aab0bb" if not base else "#5f6672",
                              font=("Consolas", 9))
        # the legend
        h = c.winfo_height()
        legend = [("input", ROLE_COLOURS["input"]), ("output", ROLE_COLOURS["output"]),
                  ("var", ROLE_COLOURS["var"]), ("weight", ROLE_COLOURS["learn"]), ("base", "#6b7280")]
        x = 10
        for label, colour in legend:
            c.create_oval(x, h - 16, x + 8, h - 8, fill=colour, outline="")
            c.create_text(x + 12, h - 12, text=label, anchor="w", fill=DIM, font=("Consolas", 8))
            x += 16 + 7 * len(label)
        c.create_line(x, h - 12, x + 14, h - 12, fill="#7e5aa8", dash=(4, 3), arrow="last", arrowshape=(5, 6, 2))
        c.create_text(x + 18, h - 12, text="set", anchor="w", fill=DIM, font=("Consolas", 8))
        x += 46
        for label, colour in (("holds", HOLDS), ("strained", STRAINED), ("does not hold", BROKEN)):
            c.create_rectangle(x, h - 16, x + 8, h - 8, fill=colour, outline="")
            c.create_text(x + 12, h - 12, text=label, anchor="w", fill=DIM, font=("Consolas", 8))
            x += 16 + 7 * len(label)
        c.create_text(c.winfo_width() - 8, 10, text="drag: move · wheel: zoom · double-click: back", anchor="e",
                      fill="#454b56", font=("Consolas", 8))
        if self.hover is not None:
            if self.hover in self.places:
                self.tip()
            else:
                self.hover = None

    @staticmethod
    def colour(strain):
        if strain is None:
            return HOLDS
        if strain < 1:
            return HOLDS
        if strain < 3:
            return STRAINED
        return BROKEN


class Editor:
    """The line the human types: coloured as it is typed, Tab completes, Up and Down go back through what was
    typed."""

    def __init__(self, text, words, complete, log):
        self.t = text
        self.words = words
        self.complete_at = complete
        self.log = log
        self.past, self.at = [], 0
        self.last_tab = None
        text.bind("<KeyRelease>", lambda e: self.colour())
        text.bind("<Tab>", self.on_tab)
        text.bind("<Up>", lambda e: self.back(-1))
        text.bind("<Down>", lambda e: self.back(1))
        text.bind("<Escape>", lambda e: self.set(""))

    def get(self):
        return self.t.get("1.0", "end-1c").replace("\n", " ")

    def set(self, line):
        self.t.delete("1.0", "end")
        self.t.insert("1.0", line)
        self.colour()
        return "break"

    def colour(self):
        import editor
        line = self.get()
        for kind in editor.COLOURS:
            self.t.tag_remove(kind, "1.0", "end")
        nodes, relations, commands = self.words()
        for a, b, kind in editor.tokens(line, nodes, relations, commands):
            self.t.tag_add(kind, f"1.0+{a}c", f"1.0+{b}c")

    def on_tab(self, _e=None):
        import editor
        line = self.get()
        cursor = len(self.t.get("1.0", "insert"))
        start, found = self.complete_at(line, cursor)
        if not found:
            return "break"
        word = line[start:cursor]
        if len(found) == 1:
            new = found[0] + ("" if found[0].endswith("/") else " ")
        else:
            new = editor.common(found)
            if new == word:
                if self.last_tab == (line, cursor):
                    self.log.write("   " + "  ".join(found[:60]) + (" ..." if len(found) > 60 else "") + "\n")
                self.last_tab = (line, cursor)
                return "break"
        self.t.delete(f"1.0+{start}c", f"1.0+{cursor}c")
        self.t.insert(f"1.0+{start}c", new)
        self.colour()
        return "break"

    def back(self, k):
        if not self.past:
            return "break"
        self.at = max(0, min(len(self.past), self.at + k))
        return self.set(self.past[self.at] if self.at < len(self.past) else "")

    def remember(self, line):
        if line.strip() and (not self.past or self.past[-1] != line):
            self.past.append(line)
        self.at = len(self.past)


def window(vm, Shell, script=None):
    """The machine in a window. script: commands said at the start, as if typed (`--window -c "..."`)."""
    import tkinter as tk
    import editor
    import mind
    root = tk.Tk()
    root.title("GRM machine")
    root.configure(bg=BG)
    root.geometry("1440x800")
    panes = tk.PanedWindow(root, orient="horizontal", bg=BG, sashwidth=4, borderwidth=0)
    panes.pack(fill="both", expand=True)

    # ---- the words (left)
    left = tk.Frame(panes, bg=BG)
    text = tk.Text(left, width=70, bg=PANEL, fg=INK, insertbackground=INK, font=("Consolas", 10),
                   state="disabled", wrap="word", borderwidth=0)
    text.pack(fill="both", expand=True, padx=8, pady=(8, 4))
    line = tk.Text(left, height=1, bg="#1b1e24", fg="#e6e8ec", insertbackground="#e6e8ec", font=("Consolas", 11),
                   borderwidth=0, wrap="none", undo=True)
    line.pack(fill="x", padx=8, pady=(0, 8))
    for widget in (text, line):
        for kind, colour in editor.COLOURS.items():
            widget.tag_configure(kind, foreground=colour)
    text.tag_configure("prompt", foreground=DIM)
    text.tag_configure("error", foreground="#e06c75")
    text.tag_configure("self", foreground="#7fdbca")
    text.tag_configure("question", foreground="#e5c07b")
    line.focus_set()
    panes.add(left, minsize=360, width=540)

    # ---- the network (middle)
    middle = tk.Frame(panes, bg=BG)
    top = tk.Frame(middle, bg=BG)
    top.pack(fill="x", padx=8, pady=(8, 0))
    master_text = tk.Label(top, text="", anchor="w", justify="left", bg=BG, fg="#e6e8ec", font=("Consolas", 10),
                           wraplength=520)
    master_text.pack(side="top", fill="x")
    master_text.bind("<Configure>", lambda e: master_text.configure(wraplength=max(200, e.width - 10)))
    row = tk.Frame(top, bg=BG)
    row.pack(side="top", fill="x")
    tk.Label(row, text="t - n", bg=BG, fg=DIM, font=("Consolas", 8)).pack(side="left")
    ago = tk.Scale(row, from_=0, to=mind.MAX_PAST - 1, orient="horizontal", length=260, bg=BG, fg=DIM,
                   troughcolor=PANEL, highlightthickness=0, borderwidth=0, showvalue=True, font=("Consolas", 8),
                   sliderlength=14, width=8)
    ago.pack(side="left", padx=6)
    tk.Label(row, text="(0: now; the last 240 ticks are kept)", bg=BG, fg="#454b56",
             font=("Consolas", 8)).pack(side="left")
    canvas = tk.Canvas(middle, bg=BG, highlightthickness=0)
    canvas.pack(fill="both", expand=True, padx=8, pady=8)
    panes.add(middle, minsize=360, width=560)

    # ---- the outputs (right)
    panel = tk.Canvas(panes, width=340, bg=BG, highlightthickness=0)
    panes.add(panel, minsize=240, width=340)

    def words():
        net = vm.net
        return net.nodes, [r["name"] for r in net.relations], shell.commands()

    log = _Log(text, words)
    shell = Shell(vm, out=log)
    view = NetworkView(canvas, vm)
    ed = Editor(line, words, lambda ln, cur: shell._complete(ln, cur), log)
    log.write(shell.intro + "\n")
    state = {"master_at": 0.0, "master_key": None}

    def show_master(force=False):
        n = int(ago.get())
        key = (n, getattr(vm.net, "ticks", 0), len(vm.net.relations))
        if not force and key == state["master_key"] and time.perf_counter() - state["master_at"] < 1.0:
            return
        state["master_key"], state["master_at"] = key, time.perf_counter()
        try:
            res = mind.master(vm, n)
        except Exception as e:  # noqa: BLE001
            res = {"text": f"cannot compute it: {type(e).__name__}: {e}"}
        when = "now" if n == 0 else f"t - {n}"
        tick = f", tick {res['tick']}" if res.get("tick") is not None else ""
        extra = ""
        if "span" in res:
            extra = f"\n{res['span']:.3g} decades of scale, residual {res['residual']:.2g}{res['unit']}" + (
                ", implied by the network" if res.get("derived") else "")
        master_text.configure(text=f"master equation ({when}{tick}):  {res['text']}{extra}")

    ago.configure(command=lambda _v: show_master(force=True))

    def bar(y, label, v, size=1.0):
        panel.create_text(12, y, text=label, anchor="w", fill=DIM, font=("Consolas", 9))
        mid = 190
        panel.create_line(mid, y - 6, mid, y + 6, fill=LINE)
        w = 130 * max(-1.0, min(1.0, v / size))
        if w >= 0:
            panel.create_rectangle(mid, y - 4, mid + w + 1, y + 4, fill="#ffb347", outline="")
        else:
            panel.create_rectangle(mid + w - 1, y - 4, mid, y + 4, fill="#5fa8d3", outline="")

    def draw_panel():
        panel.delete("all")
        md = mind.mood(vm.net)
        mind.flourishing(vm.net)
        panel.create_text(12, 14, text="inside", anchor="w", fill=DIM, font=("Consolas", 10))
        bar(36, f"pleasure     {md['dopamine']:+.2f}", md["dopamine"])
        bar(54, f"flourishing  {md['flourishing']:.2f}", md["flourishing"])
        bar(72, f"progress     {md['progress']:+.2f}", md["progress"])
        cap = mind.capacity(vm.net)
        limit = "by hand" if vm.net.capacity else f"host: {vm.net.host.get('limit', '?')}"
        panel.create_text(12, 90, text=f"links {mind.links(vm.net)} of {cap} ({limit})", anchor="w", fill=DIM,
                          font=("Consolas", 9))
        panel.create_text(12, 106, text=f"rent {mind.price(vm.net):.2g} bit a link a tick", anchor="w", fill=DIM,
                          font=("Consolas", 9))
        panel.create_text(12, 134, text="outputs", anchor="w", fill=DIM, font=("Consolas", 10))
        y = 158
        names = vm.outputs() + (["surprise"] if vm.history.get("surprise") else [])
        for name in names:
            try:
                h = list(vm.history.get(name) or [vm.get(name)])
            except Exception:  # noqa: BLE001 - an output that cannot be read is skipped, not a crash
                continue
            v = h[-1]
            size = max(abs(x) for x in h) or 1.0
            panel.create_text(12, y, text=f"{name} = {v:.6g}", anchor="w", fill="#e6e8ec", font=("Consolas", 11))
            mid = 160
            panel.create_line(mid, y + 10, mid, y + 22, fill=LINE)
            if v >= 0:
                panel.create_rectangle(mid, y + 12, mid + 150 * v / size + 1, y + 20, fill="#ffb347", outline="")
            else:
                panel.create_rectangle(mid + 150 * v / size - 1, y + 12, mid, y + 20, fill="#5fa8d3", outline="")
            lo, hi = min(h + [0.0]), max(h + [0.0])
            span = (hi - lo) or 1.0
            if len(h) > 1:
                pts = []
                for k, val in enumerate(h):
                    pts += [12 + 300 * k / max(1, len(h) - 1), y + 64 - 36 * (val - lo) / span]
                panel.create_line(*pts, fill="#8a6db8", width=1.5)
            y += 84
            if y > panel.winfo_height() - 40:
                break
        m = vm.machine
        if m is not None:
            panel.create_text(12, panel.winfo_height() - 12,
                              text=f"tick {m.ticks}   {m.processors()} processors   round {m.rounds}",
                              anchor="w", fill=DIM, font=("Consolas", 9))

    def draw(steps=6):
        try:
            draw_panel()
            view.draw(steps=steps)
            show_master()
        except Exception as e:  # noqa: BLE001 - the picture fails, the machine goes on and says why
            import diagnose
            log.write("  ! " + diagnose.internal(e) + "\n")

    def enter(_e=None):
        typed = ed.get()
        ed.remember(typed)
        ed.set("")
        log.write(f"grm> {typed}\n")
        if shell.onecmd(typed):
            root.destroy()
            return "break"
        draw(steps=20)
        return "break"

    line.bind("<Return>", enter)
    last = [time.perf_counter()]

    def clock():
        if shell.clock > 0 and time.perf_counter() - last[0] >= 1.0 / shell.clock:
            last[0] = time.perf_counter()
            try:
                vm.tick()
            except Exception as e:  # noqa: BLE001
                import diagnose
                log.write("  ! " + diagnose.internal(e) + "\n")
                shell.clock = 0.0
            shell.say_events()
            if shell.sound:
                play(sound_of(vm.history))
            draw(steps=3)
        root.after(10, clock)

    def close():
        shell.do_quit("")
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", close)

    def start():
        for typed in (script or "").split(";"):
            if typed.strip():
                ed.set(typed.strip())
                enter()
        draw(steps=60)

    root.after(50, start)
    clock()
    root.mainloop()
