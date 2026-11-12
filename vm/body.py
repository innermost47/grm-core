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
import os
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
WORKED = "#7fdbca"     # a relation that worked in the last round (stepping a round at a time)


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
            from i18n import tr
            lines = [name, "(" + tr("cannot read it: {error}", error=f"{type(ex).__name__}: {ex}") + ")"]
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
        # stepping a round at a time: the relations that worked in the last round
        worked = ({m.factors[f].name for f in getattr(m, "busy", ())} if m is not None and vm.in_tick() else set())
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
            if r["name"] in worked:
                c.create_rectangle(x - 10, y - 10, x + 10, y + 10, outline=WORKED, width=2)
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
        from i18n import tr
        legend = [(tr("input"), ROLE_COLOURS["input"]), (tr("output"), ROLE_COLOURS["output"]),
                  (tr("var"), ROLE_COLOURS["var"]), (tr("weight"), ROLE_COLOURS["learn"]), (tr("base"), "#6b7280")]
        x, row = 10, 0
        right = c.winfo_width() - 10

        def room(x, label):
            """The next place of the legend: on a new row above when this word would leave the canvas."""
            nonlocal row
            if x > 10 and x + 26 + 7 * len(label) > right:
                row += 1
                return 10
            return x
        for label, colour in legend:
            x = room(x, label)
            h = c.winfo_height() - 16 * row
            c.create_oval(x, h - 16, x + 8, h - 8, fill=colour, outline="")
            t = c.create_text(x + 12, h - 12, text=label, anchor="w", fill=DIM, font=("Consolas", 8))
            x = c.bbox(t)[2] + 12                    # the width of the word itself, in any language
        x = room(x, tr("set") + "     ")
        h = c.winfo_height() - 16 * row
        c.create_line(x, h - 12, x + 14, h - 12, fill="#7e5aa8", dash=(4, 3), arrow="last", arrowshape=(5, 6, 2))
        t = c.create_text(x + 18, h - 12, text=tr("set"), anchor="w", fill=DIM, font=("Consolas", 8))
        x = c.bbox(t)[2] + 12
        for label, colour in ((tr("holds"), HOLDS), (tr("strained"), STRAINED), (tr("does not hold"), BROKEN)):
            x = room(x, label)
            h = c.winfo_height() - 16 * row
            c.create_rectangle(x, h - 16, x + 8, h - 8, fill=colour, outline="")
            t = c.create_text(x + 12, h - 12, text=label, anchor="w", fill=DIM, font=("Consolas", 8))
            x = c.bbox(t)[2] + 12                    # the width of the word itself, in any language
        c.create_text(c.winfo_width() - 8, 10, text=tr("drag: move · wheel: zoom · double-click: back"), anchor="e",
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
    typed. Under it, a line of help (what is being typed); when the typing help is on, a menu of words floats above
    it, like a tooltip, so that nothing under or around the prompt moves: Up and Down choose, Tab, Enter or a click
    take, Esc closes."""

    def __init__(self, text, words, complete, log, hint=None, menu=None, suggest=None, helping=lambda: True,
                 popup=None):
        self.t = text
        self.words = words
        self.complete_at = complete
        self.log = log
        self.hint_label = hint
        self.menu = menu
        self.popup = popup          # the floating window that holds the menu
        self.shown = False
        self.suggest = suggest
        self.helping = helping
        self.items = []             # what the menu shows: [(word, a few words)]
        self.past, self.at = [], 0
        self.last_tab = None
        text.bind("<KeyRelease>", self.on_key)
        text.bind("<Tab>", self.on_tab)
        text.bind("<Up>", lambda e: self.move(-1) if self.menu_open() else self.back(-1))
        text.bind("<Down>", lambda e: self.move(1) if self.menu_open() else self.back(1))
        text.bind("<Escape>", lambda e: self.close_menu() if self.menu_open() else self.set(""))
        text.bind("<FocusOut>", lambda e: self.close_menu())
        if menu is not None:
            menu.bind("<Button-1>", self.on_click)      # taken at once: the focus never leaves the prompt

    def get(self):
        return self.t.get("1.0", "end-1c").replace("\n", " ")

    def cursor(self):
        return len(self.t.get("1.0", "insert"))

    def set(self, line):
        self.t.delete("1.0", "end")
        self.t.insert("1.0", line)
        self.colour()
        self.close_menu()
        self.show_hint()
        return "break"

    def colour(self):
        import editor
        line = self.get()
        for kind in editor.COLOURS:
            self.t.tag_remove(kind, "1.0", "end")
        nodes, relations, commands = self.words()
        for a, b, kind in editor.tokens(line, nodes, relations, commands):
            self.t.tag_add(kind, f"1.0+{a}c", f"1.0+{b}c")

    def on_key(self, e):
        if e.keysym in ("Up", "Down", "Return", "Escape", "Tab"):
            return
        self.colour()
        self.show_hint()
        self.show_menu()

    # ---- the line of help and the menu
    def show_hint(self):
        if self.hint_label is None:
            return
        import editor
        nodes, relations, commands = self.words()
        try:
            text = editor.hint(self.get(), self.cursor(), nodes, relations, commands)
        except Exception:  # noqa: BLE001 - a hint that cannot be made is no hint
            text = ""
        self.hint_label.configure(text=text)

    def show_menu(self):
        if self.menu is None or self.suggest is None:
            return
        if not self.helping():
            self.close_menu()
            return
        try:
            self.items = self.suggest(self.get(), self.cursor())
        except Exception:  # noqa: BLE001
            self.items = []
        if not self.items:
            self.close_menu()
            return
        self.menu.delete(0, "end")
        width = max(len(w) for w, _ in self.items)
        rows = [f" {w:<{width}}  {what} " for w, what in self.items]
        for r in rows:
            self.menu.insert("end", r)
        self.menu.configure(height=min(8, len(rows)), width=min(70, max(len(r) for r in rows)))
        self.menu.selection_clear(0, "end")
        self.place()

    def place(self):
        """The menu floats just above the prompt, its left edge under the word being typed."""
        if self.popup is None:
            return
        start, _ = self.complete_at(self.get(), self.cursor())
        box = self.t.bbox(f"1.0+{start}c")
        x = self.t.winfo_rootx() + (box[0] if box else 0)
        self.popup.update_idletasks()
        y = self.t.winfo_rooty() - self.popup.winfo_reqheight() - 2
        right = self.t.winfo_toplevel().winfo_rootx() + self.t.winfo_toplevel().winfo_width()
        x = max(self.t.winfo_rootx(), min(x, right - self.popup.winfo_reqwidth()))
        self.popup.geometry(f"+{x}+{max(0, y)}")
        if not self.shown:
            self.popup.deiconify()
            self.shown = True
        self.popup.lift()

    def menu_open(self):
        return self.menu is not None and self.shown and bool(self.items)

    def close_menu(self):
        if self.popup is not None and self.shown:
            self.popup.withdraw()
        self.shown = False
        self.items = []
        return "break"

    def on_click(self, e):
        i = self.menu.nearest(e.y)
        if 0 <= i < len(self.items):
            self.take(self.items[i][0])
        self.t.focus_set()
        return "break"

    def move(self, k):
        sel = self.menu.curselection()
        i = (sel[0] + k) if sel else (0 if k > 0 else len(self.items) - 1)
        i = max(0, min(len(self.items) - 1, i))
        self.menu.selection_clear(0, "end")
        self.menu.selection_set(i)
        self.menu.see(i)
        return "break"

    def chosen(self):
        """The word chosen in the menu (Up / Down), if any."""
        if not self.menu_open():
            return None
        sel = self.menu.curselection()
        return self.items[sel[0]][0] if sel else None

    def take(self, word):
        """The word at the cursor replaced by `word`."""
        line, cursor = self.get(), self.cursor()
        start, _ = self.complete_at(line, cursor)
        new = word + ("" if word.endswith("/") else " ")
        self.t.delete(f"1.0+{start}c", f"1.0+{cursor}c")
        self.t.insert(f"1.0+{start}c", new)
        self.colour()
        self.close_menu()
        self.show_hint()
        return "break"

    def on_tab(self, _e=None):
        import editor
        if self.menu_open():
            return self.take(self.chosen() or self.items[0][0])
        line = self.get()
        cursor = self.cursor()
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
        self.show_hint()
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


class Programs:
    """The programs window: a tab per program, coloured, lines numbered; everything with the keyboard.
        open / tab / close / edit / save / find / run from the prompt;
        in a tab: Ctrl+S saves, F5 runs, Ctrl+F searches, Ctrl+Tab goes to the next tab, Ctrl+W closes, Esc goes back
        to the prompt. An error while running turns its line red."""

    def __init__(self, root, shell, words, after_run, back_to_prompt):
        self.root = root
        self.shell = shell
        self.words = words
        self.after_run = after_run
        self.back_to_prompt = back_to_prompt
        self.top = None
        self.book = None
        self.pages = []             # [{"path", "frame", "text", "gutter", "search", "edit", "dirty"}]

    # ---- the window
    def ensure(self):
        import tkinter as tk
        from tkinter import ttk
        from i18n import tr
        if self.top is not None:
            if not self.top.winfo_viewable():
                self.top.deiconify()
            return
        self.top = tk.Toplevel(self.root)
        self.top.title(tr("GRM programs"))
        self.top.configure(bg=BG)
        self.root.update_idletasks()
        x = max(0, self.root.winfo_rootx() + self.root.winfo_width() - 840)
        self.top.geometry(f"820x760+{x}+{self.root.winfo_rooty() + 30}")
        self.top.protocol("WM_DELETE_WINDOW", self.top.withdraw)
        style = ttk.Style(self.top)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("GRM.TNotebook", background=BG, borderwidth=0)
        style.configure("GRM.TNotebook.Tab", background=PANEL, foreground=DIM, padding=(10, 4))
        style.map("GRM.TNotebook.Tab", background=[("selected", "#262a33")], foreground=[("selected", "#e6e8ec")])
        self.book = ttk.Notebook(self.top, style="GRM.TNotebook")
        self.book.pack(fill="both", expand=True)
        self.status = tk.Label(self.top, text="", anchor="w", bg=BG, fg=DIM, font=("Consolas", 9))
        self.status.pack(fill="x", padx=6, pady=(0, 4))
        self.say_status()

    def say_status(self, text=None):
        from i18n import tr
        if self.top is None:
            return
        self.status.configure(text=text or tr("tab N · edit · Ctrl+S save · F5 run · Ctrl+F find · Ctrl+Tab next · "
                                              "Esc back to the prompt"))

    def page(self, i=None):
        if not self.pages:
            return None
        if i is None:
            try:
                i = self.book.index(self.book.select())
            except Exception:  # noqa: BLE001
                return None
        return self.pages[i] if 0 <= i < len(self.pages) else None

    def current(self):
        return self.page()

    def tabs(self):
        return [(i + 1, os.path.basename(p["path"])) for i, p in enumerate(self.pages)]

    def title(self, p):
        return os.path.basename(p["path"]) + (" *" if p["dirty"] else "") + (" ✎" if p["edit"] else "")

    # ---- open, close, go to
    def open(self, path, edit=False):
        import tkinter as tk
        self.ensure()
        path = os.path.abspath(path)
        for i, p in enumerate(self.pages):
            if p["path"] == path:
                self.book.select(i)
                if edit:
                    self.edit()
                return i + 1
        frame = tk.Frame(self.book, bg=PANEL)
        body = tk.Frame(frame, bg=PANEL)
        body.pack(fill="both", expand=True)
        gutter = tk.Text(body, width=5, bg="#121419", fg="#4b525e", font=("Consolas", 10), borderwidth=0,
                         state="disabled", takefocus=0, padx=4)
        gutter.pack(side="left", fill="y")
        bar = tk.Scrollbar(body)
        bar.pack(side="right", fill="y")
        text = tk.Text(body, bg=PANEL, fg=INK, insertbackground="#e6e8ec", font=("Consolas", 10), borderwidth=0,
                       wrap="none", undo=True, padx=6)
        text.pack(side="left", fill="both", expand=True)

        def scrolled(a, b):
            bar.set(a, b)
            gutter.yview_moveto(a)
        text.configure(yscrollcommand=scrolled)
        bar.configure(command=lambda *a: (text.yview(*a), gutter.yview(*a)))
        search = tk.Entry(frame, bg="#1b1e24", fg="#e6e8ec", insertbackground="#e6e8ec", font=("Consolas", 10),
                          borderwidth=0)
        import editor
        for kind, colour in editor.COLOURS.items():
            text.tag_configure(kind, foreground=colour)
        text.tag_configure("header", foreground="#7fdbca")
        text.tag_configure("found", background="#5c4a00")
        text.tag_configure("here", background="#9a7b00")
        text.tag_configure("error", background="#4a1e24")
        with open(path, encoding="utf-8") as f:
            content = f.read()
        text.insert("1.0", content)
        text.edit_reset()
        p = {"path": path, "frame": frame, "text": text, "gutter": gutter, "search": search, "edit": False,
             "dirty": False}
        self.pages.append(p)
        self.book.add(frame, text=self.title(p))
        self.book.select(len(self.pages) - 1)
        self.colour_all(p)
        self.number(p)
        text.configure(state="disabled")
        text.bind("<Control-s>", lambda e: self.key_save())
        text.bind("<F5>", lambda e: self.key_run())
        text.bind("<Control-f>", lambda e: self.open_search())
        text.bind("<Control-w>", lambda e: (self.shell.do_close(""), "break")[1])
        text.bind("<Control-Tab>", lambda e: self.next_tab())
        text.bind("<Escape>", lambda e: self.escape())
        text.bind("<KeyRelease>", lambda e: self.typed(p, e))
        search.bind("<KeyRelease>", lambda e: self.search_typed(e))
        search.bind("<Return>", lambda e: self.next_found(1))
        search.bind("<Shift-Return>", lambda e: self.next_found(-1))
        search.bind("<Escape>", lambda e: self.close_search())
        self.top.bind("<Control-Tab>", lambda e: self.next_tab())
        if edit:
            self.edit()
        return len(self.pages)

    def select(self, what):
        if not self.pages:
            return False
        i = None
        if what.isdigit():
            i = int(what) - 1
        else:
            for k, p in enumerate(self.pages):
                name = os.path.basename(p["path"])
                if what in (name, os.path.splitext(name)[0]):
                    i = k
                    break
        if i is None or not 0 <= i < len(self.pages):
            return False
        self.ensure()
        self.book.select(i)
        return True

    def next_tab(self):
        if self.pages:
            i = (self.book.index(self.book.select()) + 1) % len(self.pages)
            self.book.select(i)
            self.pages[i]["text"].focus_set()
        return "break"

    def close(self, what=None):
        from i18n import tr
        if not self.pages:
            return None
        if what and not self.select(what):
            return tr("no tab {tab}", tab=what)
        p = self.page()
        name = os.path.basename(p["path"])
        unsaved = p["dirty"]
        i = self.pages.index(p)
        self.book.forget(i)
        self.pages.pop(i)
        return tr("closed {name}", name=name) + (" (" + tr("not saved") + ")" if unsaved else "")

    # ---- writing
    def edit(self):
        p = self.page()
        if p is None:
            return False
        p["edit"] = True
        p["text"].configure(state="normal")
        p["text"].focus_set()
        self.book.tab(self.pages.index(p), text=self.title(p))
        return True

    def escape(self):
        if self.page() and self.page()["search"].winfo_ismapped():
            return self.close_search()
        self.back_to_prompt()
        return "break"

    def typed(self, p, e):
        if not p["edit"] or e.keysym in ("Control_L", "Control_R", "Escape", "F5"):
            return
        if not p["dirty"] and p["text"].edit_modified():
            p["dirty"] = True
            self.book.tab(self.pages.index(p), text=self.title(p))
        line = int(p["text"].index("insert").split(".")[0])
        self.colour_line(p, line)
        if e.keysym in ("Return", "BackSpace", "Delete") or e.state & 0x4:
            self.colour_all(p)
            self.number(p)
        p["text"].tag_remove("error", "1.0", "end")

    def number(self, p):
        n = int(p["text"].index("end-1c").split(".")[0])
        g = p["gutter"]
        g.configure(state="normal")
        g.delete("1.0", "end")
        g.insert("1.0", "\n".join(f"{i:>4}" for i in range(1, n + 1)))
        g.configure(state="disabled")
        g.yview_moveto(p["text"].yview()[0])

    def colour_line(self, p, ln):
        import editor
        t = p["text"]
        for kind in list(editor.COLOURS) + ["header"]:
            t.tag_remove(kind, f"{ln}.0", f"{ln}.end")
        line = t.get(f"{ln}.0", f"{ln}.end")
        if line.lstrip().startswith("#!"):
            t.tag_add("header", f"{ln}.0", f"{ln}.end")
            return
        nodes, relations, commands = self.words()
        for a, b, kind in editor.tokens(line, nodes, relations, commands):
            t.tag_add(kind, f"{ln}.{a}", f"{ln}.{b}")

    def colour_all(self, p):
        n = int(p["text"].index("end-1c").split(".")[0])
        for ln in range(1, n + 1):
            self.colour_line(p, ln)

    def save(self, path=None):
        from i18n import tr
        p = self.page()
        if p is None:
            return None
        if path:
            if not path.endswith(".grm"):
                path += ".grm"
            if not os.path.isabs(path) and os.path.dirname(path) == "":
                path = os.path.join(os.path.dirname(p["path"]), path)
            p["path"] = os.path.abspath(path)
        with open(p["path"], "w", encoding="utf-8") as f:
            f.write(p["text"].get("1.0", "end-1c") + "\n")
        p["dirty"] = False
        p["text"].edit_modified(False)
        self.book.tab(self.pages.index(p), text=self.title(p))
        return tr("saved {path}", path=p["path"])

    def key_save(self):
        said = self.save()
        if said:
            self.shell.write("  " + said)
            self.say_status(said)
        return "break"

    # ---- running
    def run_current(self):
        """The tab's statements, line by line (as `use` would say them). An error stops it and turns its line red."""
        from i18n import tr
        from language import TalkError
        p = self.page()
        if p is None:
            return
        t = p["text"]
        t.tag_remove("error", "1.0", "end")
        lines = t.get("1.0", "end-1c").splitlines()
        base = os.path.dirname(p["path"])
        name = os.path.basename(p["path"])
        self.shell.write(f"grm> run {name}")
        said = 0
        for i, line in enumerate(lines, 1):
            try:
                out = self.shell.vm.say(line, base)
            except TalkError as e:
                self.shell.write("  ? " + tr("in {file}, line {n}: {line}", file=name, n=i, line=line.strip()))
                self.shell.write(f"    {e}")
                self.mark_line(p, i)
                break
            if out:
                said += 1
        else:
            self.shell.write("  " + tr("ran {name}: {n} statements", name=name, n=said))
        self.shell.say_events()
        self.after_run()

    def key_run(self):
        self.run_current()
        return "break"

    def mark_line(self, p, n):
        t = p["text"]
        t.tag_add("error", f"{n}.0", f"{n}.end+1c")
        t.see(f"{n}.0")
        self.book.select(self.pages.index(p))

    def mark_error(self, file, n):
        """An error in a file (said by `use`): its line red in its tab, if it is open."""
        for p in self.pages:
            if os.path.basename(p["path"]) == os.path.basename(file):
                self.mark_line(p, n)
                return True
        return False

    # ---- searching
    def open_search(self):
        p = self.page()
        if p is None:
            return "break"
        p["search"].pack(fill="x", padx=6, pady=4)
        p["search"].focus_set()
        p["search"].select_range(0, "end")
        return "break"

    def close_search(self):
        p = self.page()
        if p is not None:
            p["search"].pack_forget()
            p["text"].tag_remove("found", "1.0", "end")
            p["text"].tag_remove("here", "1.0", "end")
            p["text"].focus_set()
        return "break"

    def search_typed(self, e):
        if e.keysym in ("Return", "Escape"):
            return
        self.find(self.page()["search"].get(), from_bar=True)

    def find(self, term, from_bar=False):
        """Every place of `term` in the current tab highlighted; the first one shown. Returns how many."""
        p = self.page()
        if p is None:
            return None
        if not from_bar:
            p["search"].delete(0, "end")
            p["search"].insert(0, term)
            p["search"].pack(fill="x", padx=6, pady=4)
        t = p["text"]
        t.tag_remove("found", "1.0", "end")
        t.tag_remove("here", "1.0", "end")
        if not term:
            return 0
        n, at = 0, "1.0"
        while True:
            at = t.search(term, at, stopindex="end", nocase=True)
            if not at:
                break
            end = f"{at}+{len(term)}c"
            t.tag_add("found", at, end)
            n += 1
            at = end
        p["found_at"] = "1.0"
        if n:
            self.next_found(1)
        return n

    def next_found(self, k):
        p = self.page()
        if p is None:
            return "break"
        t = p["text"]
        ranges = t.tag_ranges("found")
        if not ranges:
            return "break"
        starts = [str(ranges[i]) for i in range(0, len(ranges), 2)]
        here = t.tag_ranges("here")
        i = 0
        if here:
            cur = str(here[0])
            i = (starts.index(cur) + k) % len(starts) if cur in starts else 0
        t.tag_remove("here", "1.0", "end")
        t.tag_add("here", starts[i], ranges[2 * i + 1])
        t.see(starts[i])
        if int(starts[i].split(".")[1]) < 60:          # near the start of its line: the line from its start
            t.xview_moveto(0)
        return "break"


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
    line.pack(fill="x", padx=8, pady=(0, 2))
    # under the prompt: a line of help (what is being typed), the menu of words (when the typing help is on), and the
    # box that turns it on or off
    # the line of help always takes two lines, so that the prompt above it never moves
    hint = tk.Label(left, text="", anchor="nw", bg=BG, fg="#8b919c", font=("Consolas", 9), height=2)
    hint.pack(fill="x", padx=10, pady=(0, 2))
    hint.configure(justify="left")
    hint.bind("<Configure>", lambda e: hint.configure(wraplength=max(200, e.width - 4)))
    # the menu of words: a tooltip floating above the prompt, outside the layout
    popup = tk.Toplevel(root)
    popup.withdraw()
    popup.overrideredirect(True)
    popup.configure(bg="#3e4451")
    menu = tk.Listbox(popup, height=6, bg="#1b1e24", fg="#c8ccd4", selectbackground="#3e4451",
                      selectforeground="#ffffff", font=("Consolas", 9), borderwidth=0, highlightthickness=0,
                      activestyle="none", takefocus=0)
    menu.pack(padx=1, pady=1)
    options = tk.Frame(left, bg=BG)
    options.pack(fill="x", padx=8, pady=(0, 6))
    helping = tk.BooleanVar(value=True)
    help_box = tk.Checkbutton(options, variable=helping, bg=BG, fg=DIM, selectcolor=PANEL, activebackground=BG,
                              activeforeground=INK, font=("Consolas", 9), borderwidth=0, highlightthickness=0)
    help_box.pack(side="left")
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
    # seeing it work: play / pause, a tick, a round; what it is doing now
    controls = tk.Frame(top, bg=BG)
    controls.pack(side="top", fill="x", pady=(0, 6))

    def button(cmd):
        return tk.Button(controls, command=cmd, bg=PANEL, fg=INK, activebackground="#3e4451", activeforeground=INK,
                         font=("DejaVu Sans Mono", 9), relief="flat", borderwidth=0, padx=8, pady=2, takefocus=0)
    play_button = button(lambda: act("pause" if shell.clock > 0 else "play"))
    tick_button = button(lambda: act("tick"))
    round_button = button(lambda: act("step"))
    for b in (play_button, tick_button, round_button):
        b.pack(side="left", padx=(0, 4))
    doing = tk.Label(top, text="", anchor="w", bg=BG, fg=DIM, font=("Consolas", 9))
    doing.pack(side="top", fill="x", pady=(0, 4))
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
    ago_note = tk.Label(row, text="", bg=BG, fg="#454b56", font=("Consolas", 8))
    ago_note.pack(side="left")
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
    from i18n import tr
    view = NetworkView(canvas, vm)

    def suggest(ln, cur):
        nodes, relations, commands = words()
        return editor.suggest(ln, cur, nodes=nodes, relations=relations, commands=commands,
                              networks=vm.net.networks, base=shell.base)
    helping.set(bool(shell.settings.get("help", True)))
    ed = Editor(line, words, lambda ln, cur: shell._complete(ln, cur), log, hint=hint, menu=menu, suggest=suggest,
                helping=helping.get, popup=popup)
    root.bind("<Configure>", lambda e: ed.close_menu() if e.widget is root else None)   # the window moves: it closes

    def help_toggled(on=None):
        if on is not None:
            helping.set(on)
        shell.settings["help"] = bool(helping.get())
        shell.save_settings()
        if not helping.get():
            ed.close_menu()
    help_box.configure(command=help_toggled)
    shell.on_help = help_toggled
    shell.programs = Programs(root, shell, words, after_run=lambda: draw(steps=20),
                              back_to_prompt=lambda: (root.focus_force(), line.focus_set()))

    def relabel():
        """The window's words, in the language of the machine."""
        help_box.configure(text=" " + tr("typing help (a menu of words while typing)"))
        root.title(tr("GRM machine"))
        tick_button.configure(text="⏭ " + tr("tick") + "  F10")
        round_button.configure(text="↘ " + tr("round") + "  F11")
        show_doing()
        ed.show_hint()

    def show_doing():
        """The play button and what the machine is doing: playing or paused, in a tick, its watches."""
        playing = shell.clock > 0
        play_button.configure(text=("⏸ " + tr("pause") if playing else "▶ " + tr("play")) + "  F8")
        parts = [tr("playing at {hz} Hz", hz=f"{shell.clock:g}") if playing else tr("paused")]
        m = vm.machine
        if vm.in_tick() and m is not None:
            parts.append(tr("in tick {tick}, round {round}", tick=m.ticks + 1, round=m.rounds - m._tick["r0"]))
        if vm.watches:
            parts.append(tr("{n} watch(es)", n=len(vm.watches)))
        doing.configure(text="  ·  ".join(parts))

    def act(typed):
        """A button or a key: said as if typed, so that it shows in the words."""
        log.write(f"grm> {typed}\n")
        shell.onecmd(typed)
        relabel()
        draw(steps=20)
        line.focus_set()
        return "break"

    root.bind("<F8>", lambda e: act("pause" if shell.clock > 0 else "play"))
    root.bind("<F10>", lambda e: act("tick"))
    root.bind("<F11>", lambda e: act("step"))
    relabel()
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
            res = {"text": tr("cannot compute it: {error}", error=f"{type(e).__name__}: {e}")}
        when = tr("now") if n == 0 else f"t - {n}"
        tick = ", " + tr("tick {tick}", tick=res["tick"]) if res.get("tick") is not None else ""
        extra = ""
        if "span" in res:
            extra = "\n" + tr("{span} decades of scale, residual {residual}", span=f"{res['span']:.3g}",
                               residual=f"{res['residual']:.2g}{res['unit']}") + (
                ", " + tr("implied by the network") if res.get("derived") else "")
        master_text.configure(text=tr("master equation ({when}{tick})", when=when, tick=tick) + f":  {res['text']}"
                              + extra)
        ago_note.configure(text=tr("(0: now; 240 ticks kept)"))

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
        panel.create_text(12, 14, text=tr("inside"), anchor="w", fill=DIM, font=("Consolas", 10))
        names = [tr("pleasure"), tr("flourishing"), tr("progress")]
        w = max(len(n) for n in names) + 2                 # the longest word of the language sets the column
        bar(36, f"{names[0]:<{w}}{md['dopamine']:+.2f}", md["dopamine"])
        bar(54, f"{names[1]:<{w}}{md['flourishing']:.2f}", md["flourishing"])
        bar(72, f"{names[2]:<{w}}{md['progress']:+.2f}", md["progress"])
        cap = mind.capacity(vm.net)
        limit = tr("by hand") if vm.net.capacity else tr("host: {limit}", limit=tr(vm.net.host.get("limit", "?")))
        panel.create_text(12, 90, text=tr("links {n} of {cap} ({limit})", n=mind.links(vm.net), cap=cap,
                                          limit=limit), anchor="w", fill=DIM, font=("Consolas", 9))
        panel.create_text(12, 106, text=tr("rent {p} bit a link a tick", p=f"{mind.price(vm.net):.2g}"), anchor="w",
                          fill=DIM, font=("Consolas", 9))
        panel.create_text(12, 134, text=tr("outputs"), anchor="w", fill=DIM, font=("Consolas", 10))
        y = 158
        names = vm.outputs() + (["surprise"] if vm.history.get("surprise") else [])
        shown = {"surprise": tr("surprise")}
        for name in names:
            try:
                h = list(vm.history.get(name) or [vm.get(name)])
            except Exception:  # noqa: BLE001 - an output that cannot be read is skipped, not a crash
                continue
            v = h[-1]
            size = max(abs(x) for x in h) or 1.0
            panel.create_text(12, y, text=f"{shown.get(name, name)} = {v:.6g}", anchor="w", fill="#e6e8ec",
                              font=("Consolas", 11))
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
                              text=tr("tick {tick}   {p} processors   round {round}", tick=m.ticks,
                                      p=m.processors(), round=m.rounds),
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
        word = ed.chosen()
        if word is not None:                 # a word chosen in the menu: taken, not run
            return ed.take(word)
        ed.close_menu()
        typed = ed.get()
        ed.remember(typed)
        ed.set("")
        log.write(f"grm> {typed}\n")
        if shell.onecmd(typed):
            root.destroy()
            return "break"
        relabel()
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
            if vm.stopped:                   # a watch was met: the clock pauses there
                shell.do_pause("")
                show_doing()
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
