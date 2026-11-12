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
        self.waiting = []           # what a piece of work running aside said, shown by the window's own thread

    def aside(self):
        import threading
        return threading.current_thread() is not threading.main_thread()

    def pump(self):
        """What was said aside, now shown."""
        while self.waiting:
            kind, what = self.waiting.pop(0)
            (self.write if kind == "write" else self.write_parts)(what)

    def write_parts(self, parts):
        """Pieces of text, each with its colour (ls: folders, programs, data)."""
        if self.aside():
            self.waiting.append(("parts", parts))
            return
        self.text.configure(state="normal")
        for t, kind in parts:
            self.text.insert("end", t, (kind,) if kind else ())
        self.text.see("end")
        self.text.configure(state="disabled")

    def write(self, s):
        import editor
        import re
        if self.aside():
            self.waiting.append(("write", s))
            return
        self.text.configure(state="normal")
        for line in s.splitlines(keepends=True):
            body = line.rstrip("\n")
            typed = re.match(r"grm( [^>]*)?> ", body)
            if typed:
                head = typed.group(0)
                self.text.insert("end", head, ("prompt",))
                start = self.text.index("end-1c")
                self.text.insert("end", body[len(head):])
                nodes, relations, commands = self.words()
                for a, b, kind in editor.tokens(body[len(head):], nodes, relations, commands):
                    self.text.tag_add(kind, f"{start}+{a}c", f"{start}+{b}c")
                self.text.insert("end", line[len(body):])
            elif graph_sep() in body:                     # a row of a card: the label dim, the value bright
                label, _, value = body.partition(graph_sep())
                self.text.insert("end", label, ("label",))
                self.text.insert("end", graph_sep(), ("rule",))
                self.text.insert("end", value + line[len(body):])
            elif body.lstrip().startswith("⚠ "):
                self.text.insert("end", line, ("warning",))
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


def graph_sep():
    import graph
    return graph.SEP


BG, PANEL, INK, DIM, LINE = "#0e1016", "#14161a", "#c8ccd4", "#7d838d", "#4b525e"
ROLE_COLOURS = {"input": "#5fa8d3", "output": "#ffb347", "var": "#c792ea", "learn": "#a3be8c",
                "fixed": "#7d838d", None: "#d0d4dc"}
HOLDS, STRAINED, BROKEN = "#56606e", "#e5c07b", "#e06c75"
SASH, SASH_EDGE, GRIP = "#1c2027", "#2e3440", "#8b93a3"     # the sashes between the parts, and their grip
FILE_COLOURS = {"folder": "#61afef", "program": "#c792ea", "data": "#a3be8c", "file": "#c8ccd4"}
SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


def progress_text(done, total, what):
    import grm_vm
    return grm_vm.progress_text(done, total, what)


PILL, PILL_LIT = "#262b33", "#7fdbca"   # the pills of the networks in the network (focus)
SOUND_ON = "#3f6f6a"                        # the sound button, when the sound plays
PLAY, PLAY_OVER, STEP, STEP_OVER = "#f0a840", "#ffc266", "#3a4352", "#4c5769"   # the buttons
FADE = {1: 0.0, 2: 0.55, 3: 0.86}   # how far each plane of the picture fades into the background (focus)


def fade(colour, k):
    """A colour k of the way to the background (0: itself, 1: the background)."""
    if k <= 0:
        return colour
    c = colour.lstrip("#")
    b = BG.lstrip("#")
    mix = [round(int(c[i:i + 2], 16) * (1 - k) + int(b[i:i + 2], 16) * k) for i in (0, 2, 4)]
    return "#" + "".join(f"{v:02x}" for v in mix)


WAVE_PERIOD, WAVE_LENGTH = 10.0, 520.0      # the swell: a wave every 10 s (as the sound breathes), 520 px long
WORKED = "#7fdbca"
WARM, COLD = "#1d150d", "#0b1220"           # the light with pleasure, with displeasure
GLOW, PULSE_COLOUR, RIPPLE_COLOUR = "#7fdbca", "#cfe8ff", "#8fb4d8"
DISCOVERY, SURPRISE = "#e5c07b", "#8fb4d8"   # the cards of the moments: a warm gold, a soft blue
PULSE, RIPPLE, CARD, RING = 1.4, 3.0, 11.0, 2.5   # seconds: a message along a link, a ripple, a card, a ring


def mix(a, b, k):
    """Colour a, k of the way to colour b."""
    a, b = a.lstrip("#"), b.lstrip("#")
    return "#" + "".join(f"{round(int(a[i:i + 2], 16) * (1 - k) + int(b[i:i + 2], 16) * k):02x}" for i in (0, 2, 4))     # a relation that worked in the last round (stepping a round at a time)


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
        self.busy = False           # the machine is at work aside: nothing is drawn
        self.front = None           # what is looked at (focus)
        # what the machine feels, shown (senses.py): how strongly, and what is moving now
        self.feeling = {"level": 0.35, "motion": True, "colour": True}
        self.pulses = []            # [relation, node, born]: a message going along a link
        self.ripples = []           # [x, y, born]: a surprise, spreading slowly
        self.cards = []             # [moment, born]: a discovery, a surprise, shared with the human
        self.warmth = 0.0           # the light, a little warmer with pleasure, colder with displeasure
        self.sea_now = None         # (time, height) of the swell the picture moves with (waves), or None
        self.moved_at = {}          # node -> when its value last moved (its ring fades from then)
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
        """What is looked at (the front, or the whole picture) in the pane, labels included, before the human's zoom
        and pan. The camera does not jump: it goes a part of the way at each drawing, and draws again until it is
        there."""
        w, h = max(self.c.winfo_width(), 50), max(self.c.winfo_height(), 50)
        if not self.places:
            self.fitted = (0.0, 0.0, 0.9 * min(w, h))
            return
        front = getattr(self, "front", None)
        seen = [p for k, p in self.places.items() if not front or k in front] or list(self.places.values())
        xs = [p[0] for p in seen]
        ys = [p[1] for p in seen]
        bw, bh = max(max(xs) - min(xs), 0.15), max(max(ys) - min(ys), 0.15)
        scale = min((w - 190) / bw, (h - 70) / bh)
        target = ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, max(scale, 1.0))
        now = getattr(self, "fitted", None)
        if now is None:
            self.fitted = target
            return
        k = 0.3
        eased = tuple(a + (b - a) * k for a, b in zip(now, target))
        close = all(abs(b - a) <= 1e-3 * max(1.0, abs(b)) for a, b in zip(eased, target))
        self.fitted = target if close else eased
        if not close and not getattr(self, "_easing", False):
            self._easing = True
            self.c.after(30, self._ease)

    def _ease(self):
        self._easing = False
        self.draw(steps=2)

    def frame(self):
        w, h = max(self.c.winfo_width(), 50), max(self.c.winfo_height(), 50)
        if not hasattr(self, "fitted"):
            self.fit()
        mx, my, scale = self.fitted
        s = scale * self.zoom
        return w / 2 - 40 + self.pan[0] - mx * s, h / 2 - 10 + self.pan[1] - my * s, s

    def to_screen(self, p):
        cx, cy, s = self.frame()
        x, y = cx + p[0] * s, cy + p[1] * s
        if self.sea_now is not None and not self.drag:
            phase_t, amplitude = self.sea_now
            # a swell going across the picture: each point turns on a small circle, as water does under a wave
            ph = 2 * math.pi * (phase_t / WAVE_PERIOD - x / WAVE_LENGTH)
            x, y = x + 0.35 * amplitude * math.cos(ph), y + amplitude * math.sin(ph)
        return x, y

    def sea_at(self, sound):
        """Where the swell is now, and how high: slow and low, higher with the sound and with a surprise."""
        f = self.feeling
        if not f.get("waves", True) or not f["level"]:
            self.sea_now = None
            return
        if sound is not None:
            t, level, swell = sound.sea()
        else:
            t, level, swell = time.perf_counter(), 0.0, 0.0
        self.sea_now = (t, (1.5 + 5.0 * f["level"]) * (0.7 + 0.6 * min(1.0, level * 2)) + 8.0 * swell)

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

    # ---- what the machine feels, shown (senses.py): every light and movement is a real quantity
    def strength(self, channel):
        f = self.feeling
        return f["level"] if f.get(channel, True) else 0.0

    def light(self):
        """The background: a little warmer with pleasure, a little colder with displeasure (colour channel)."""
        k = self.strength("colour") * self.warmth
        if abs(k) < 0.01:
            return BG
        return mix(BG, WARM if k > 0 else COLD, min(0.7, abs(k)))

    def glow(self, name, plane):
        """(radius, colour) of the halo of a relation: the information it brings, against the most any brings."""
        k = self.strength("colour")
        if not k or plane == 3:
            return None
        bits = self.vm.net.use.get("bits", {}) or {}
        top = max(list(bits.values()) + [1e-9])
        b = bits.get(name, 0.0) / top
        if b < 0.05:
            return None
        return 7 + 7 * b, fade(GLOW, 1.0 - 0.55 * k * b - 0.1 * (plane == 1))

    def feel(self, state, worked, moments):
        """After a tick, a round, a look: what the picture shows of it starts moving."""
        now = time.perf_counter()
        self.warmth += (state["pleasure"] - self.warmth) * 0.3
        k = self.strength("motion")
        if k and worked:
            net = self.vm.net
            for r in list(worked)[:int(4 + 16 * k)]:
                rel = net.relation(r)
                if rel is None:
                    continue
                for n in dict.fromkeys(net.nodes_of(rel)):
                    self.pulses.append([r, n, now])
            self.pulses = self.pulses[-int(20 + 60 * k):]
        for mo in moments:
            self.cards.append([mo, now])
            self.cards = self.cards[-2:]
            if mo["kind"] == "surprise" and k:
                w, h = self.c.winfo_width(), self.c.winfo_height()
                self.ripples.append([w / 2, h / 2, now])

    def moving(self):
        return bool(self.pulses or self.ripples or self.cards)

    def overlay(self):
        """What moves: messages along the links, ripples, the cards of the moments. Slow, soft, and nothing
        flashes."""
        c = self.c
        c.delete("sense")
        now = time.perf_counter()
        k = self.strength("motion")
        alive = []
        for p in self.pulses:
            r, n, born = p
            age = (now - born) / PULSE
            a, b = self.places.get(("r", r)), self.places.get(("n", n))
            if age >= 1 or a is None or b is None:
                continue
            alive.append(p)
            (x0, y0), (x1, y1) = self.to_screen(a), self.to_screen(b)
            e = 0.5 - 0.5 * math.cos(math.pi * age)                  # eased: it leaves and arrives softly
            x, y = x0 + (x1 - x0) * e, y0 + (y1 - y0) * e
            colour = fade(PULSE_COLOUR, 1.0 - k * math.sin(math.pi * age) * 0.9)
            c.create_oval(x - 2.5, y - 2.5, x + 2.5, y + 2.5, fill=colour, outline="", tags=("sense",))
        self.pulses = alive
        alive = []
        for rp in self.ripples:
            x, y, born = rp
            age = (now - born) / RIPPLE
            if age >= 1:
                continue
            alive.append(rp)
            radius = 20 + 260 * age
            c.create_oval(x - radius, y - radius, x + radius, y + radius, outline=fade(RIPPLE_COLOUR,
                          1.0 - 0.5 * k * (1 - age)), width=1, tags=("sense",))
        self.ripples = alive
        self.cards = [cd for cd in self.cards if now - cd[1] < CARD]
        for i, (mo, born) in enumerate(reversed(self.cards)):
            self.card(mo, now - born, i)

    def card(self, mo, age, i):
        """A moment shared with the human: it comes in slowly, stays, and goes slowly (a click closes it)."""
        from i18n import tr
        c = self.c
        k = min(1.0, age / 0.9, (CARD - age) / 1.5)                 # fade in, stay, fade out
        if k <= 0:
            return
        f = 1.0 - k
        w, h = 400, 150
        x0, y0 = 14, c.winfo_height() - 40 - (i + 1) * (h + 10)
        tag = ("sense", f"card{i}")
        accent = DISCOVERY if mo["kind"] == "discovery" else SURPRISE
        c.create_rectangle(x0, y0, x0 + w, y0 + h, fill=mix(BG, "#1f232b", k), outline=fade(accent, f + 0.3 * k),
                           width=1, tags=tag)
        title = ("✦ " + tr("found by itself")) if mo["kind"] == "discovery" else ("≈ " + tr("a surprise"))
        c.create_text(x0 + 14, y0 + 14, text=title, anchor="w", fill=fade(accent, f), font=("Consolas", 10, "bold"),
                      tags=tag)
        if mo["kind"] == "discovery":
            c.create_text(x0 + 14, y0 + 40, text=mo["text"][:48], anchor="w", fill=fade("#f2f4f8", f),
                          font=("Consolas", 12), tags=tag)
            c.create_text(x0 + 14, y0 + 66, text=mo["sentence"], anchor="nw", width=230, fill=fade(INK, f),
                          font=("Consolas", 9), tags=tag)
            c.create_text(x0 + 14, y0 + h - 14, text=f"r² {mo['r2']:.4f} · {mo['rows']} " + tr("rows"), anchor="w",
                          fill=fade(DIM, f), font=("Consolas", 8), tags=tag)
            xs, ys = mo.get("points") or ([], [])
            if len(xs) > 1:                                          # what it was found in
                px, py, pw, ph = x0 + 258, y0 + 62, 128, 72
                lx, hx, ly, hy = min(xs), max(xs), min(ys), max(ys)
                for a, b in list(zip(xs, ys))[::max(1, len(xs) // 80)]:
                    sx = px + pw * ((a - lx) / ((hx - lx) or 1))
                    sy = py + ph - ph * ((b - ly) / ((hy - ly) or 1))
                    c.create_oval(sx - 1.5, sy - 1.5, sx + 1.5, sy + 1.5, fill=fade(accent, f + 0.2 * k), outline="",
                                  tags=tag)
        else:
            c.create_text(x0 + 14, y0 + 44, text=mo["sentence"], anchor="nw", width=w - 28, fill=fade(INK, f),
                          font=("Consolas", 10), tags=tag)
            where = "  ".join(f"{n} {v:.2g}σ" for n, v in mo.get("where", []))
            c.create_text(x0 + 14, y0 + 90, text=where, anchor="w", fill=fade(DIM, f), font=("Consolas", 9),
                          tags=tag)
            c.create_text(x0 + 14, y0 + h - 14, text=tr("it is learning from it"), anchor="w", fill=fade(DIM, f),
                          font=("Consolas", 8), tags=tag)
        c.tag_bind(f"card{i}", "<Button-1>", lambda e, m=mo: self.close_card(m))

    def close_card(self, mo):
        self.cards = [cd for cd in self.cards if cd[0] is not mo]
        self.overlay()

    # ---- drawing
    def tip(self):
        kind, name = self.hover
        try:
            rows = (self.graph.node_card if kind == "n" else self.graph.relation_card)(self.vm, name)
        except Exception as ex:  # noqa: BLE001 - the card says why it could not be made
            from i18n import tr
            rows = [name, "(" + tr("cannot read it: {error}", error=f"{type(ex).__name__}: {ex}") + ")"]
        # a table: the headings, then a row a line, the labels (what does not change) dim on the left, the values
        # (what the machine holds now) bright on the right, a thin line between the two columns
        c, font, step = self.c, ("Consolas", 9), 16
        x, y = self.mouse
        x, y = x + 20, y + 18
        items, labels, values, lines = [], [], [], []
        for k, r in enumerate(rows):
            yy = y + k * step
            if isinstance(r, str):
                items.append(c.create_text(x, yy, text=r, anchor="nw", fill="#e6e8ec" if k == 0 else "#c8ccd4",
                                           font=font, tags=("tip",)))
            else:
                labels.append((c.create_text(x, yy, text=r[0], anchor="nw", fill=DIM, font=font, tags=("tip",)), yy))
                values.append(c.create_text(x, yy, text=r[1], anchor="nw", fill="#e6e8ec", font=font, tags=("tip",)))
        if labels:
            col = max(c.bbox(t)[2] for t, _ in labels) + 8
            for t in values:
                c.move(t, col + 8 - x, 0)
            top, bottom = labels[0][1] - 2, labels[-1][1] + step - 2
            lines.append(c.create_line(col, top, col, bottom, fill="#3e4451", tags=("tip",)))
            for _, yy in labels[1:]:
                lines.append(c.create_line(x, yy - 2, col + 8 + max(c.bbox(t)[2] for t in values) - col - 8, yy - 2,
                                           fill="#262b33", tags=("tip",)))
            items += [t for t, _ in labels] + values
        x0, y0, x1, y1 = c.bbox("tip")
        w, h = c.winfo_width(), c.winfo_height()
        dx = (w - 8 - x1) if x1 > w - 8 else 0
        dy = (h - 8 - y1) if y1 > h - 8 else 0
        dx, dy = max(dx, 6 - x0), max(dy, 6 - y0)
        if dx or dy:
            c.move("tip", dx, dy)
        x0, y0, x1, y1 = c.bbox("tip")
        r = c.create_rectangle(x0 - 8, y0 - 6, x1 + 8, y1 + 6, fill="#1f232b", outline="#3e4451", tags=("tip",))
        c.tag_lower(r, items[0] if items else None)
        for ln in lines:
            c.tag_raise(ln, r)

    def draw(self, steps=6):
        if self.busy:                       # the machine is at work aside: drawn again when it is done
            return
        vm, c = self.vm, self.c
        c.configure(bg=self.light())
        net = vm.net
        m = vm.machine
        # what is looked at (focus): the front; what touches it; the rest. Stepping a round at a time, the relations
        # that worked in the last round, and their nodes, come to the front too
        worked = ({m.factors[f].name for f in getattr(m, "busy", ())} if m is not None and vm.holding() else set())
        try:
            front = self.graph.focus_keys(net, vm.focus)
        except Exception:  # noqa: BLE001 - a focus that cannot be read is no focus
            front = None
        if front is not None and worked:
            near = self.graph.neighbours(net)
            front = set(front) | {("r", r) for r in worked} | {k for r in worked for k in near.get(("r", r), ())}
        plane = self.graph.planes(net, front)
        self.front = front
        self.graph.layout(net, self.places, steps=steps, pinned=self.pinned, front=front)
        if not self.drag:
            self.fit()
        c.delete("all")
        self.items = {}
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
            # a ring around what is moving now: its value has changed since the picture was last drawn
            now_x = dict(zip(m.var_names, m.x))
            before = getattr(self, "seen_x", {})
            t_now = time.perf_counter()
            for n, v in now_x.items():
                if n in before and abs(v - before[n]) > 1e-6 * max(1.0, abs(v)):
                    self.moved_at[n] = t_now
            self.seen_x = now_x
            moving = {n: (t_now - t) / RING for n, t in self.moved_at.items() if t_now - t < RING}   # n -> age
        few = len(net.nodes) <= 80 or front is not None

        def far(key):
            return FADE[plane.get(key, 3)]

        # each network in the network has its colour: a soft territory under its nodes, its links and relations
        # tinted with it (amber and red stay for what does not hold)
        found = self.graph.groups(net)
        tint = self.graph.colours(net)
        home = self.graph.home(net, found)
        focused = vm.focus[1] if vm.focus and vm.focus[0] == "group" else None

        def hue(key):
            return tint.get(home.get(key), "#b8c0cc")
        for n in net.nodes:
            key = ("n", n)
            p = self.places.get(key)
            if p is None or plane.get(key, 3) == 3 and front is not None:
                continue
            x, y = self.to_screen(p)
            strong = 0.30 if home.get(key) == focused else 0.16
            if plane.get(key, 3) == 2:
                strong *= 0.5
            radius = 24 if plane.get(key, 3) == 1 else 15
            c.create_oval(x - radius, y - radius, x + radius, y + radius, fill=mix(self.light(), hue(key), strong),
                          outline="")

        # the links first, under everything; the back first, the front last (on top)
        order = sorted(net.relations, key=lambda r: -plane.get(("r", r["name"]), 3))
        for r in order:
            rp = self.places.get(("r", r["name"]))
            if rp is None:
                continue
            x0, y0 = self.to_screen(rp)
            dash = (3, 3) if active.get(r["name"]) is False else None
            for n in dict.fromkeys(net.nodes_of(r)):
                np_ = self.places.get(("n", n))
                if np_ is None:
                    continue
                x1, y1 = self.to_screen(np_)
                k = max(far(("r", r["name"])), far(("n", n)))
                c.create_line(x0, y0, x1, y1, fill=fade(self.colour(strain.get(r["name"]), hue(("r", r["name"]))),
                                                        max(k, 0.25)), width=1.6 if k < 0.5
                              else 1.0, dash=dash)
        # the writes of each tick (set): an arrow from what is written to what it writes
        for st in net.sets:
            a, b = self.places.get(("n", st["source"])), self.places.get(("n", st["target"]))
            if a is None or b is None or a is b:
                continue
            (x0, y0), (x1, y1) = self.to_screen(a), self.to_screen(b)
            k = max(far(("n", st["source"])), far(("n", st["target"])))
            c.create_line(x0, y0, x1, y1, fill=fade("#7e5aa8", k), dash=(4, 3), arrow="last", arrowshape=(8, 9, 3))
        for r in order:
            key = ("r", r["name"])
            rp = self.places.get(key)
            if rp is None:
                continue
            x, y = self.to_screen(rp)
            p, k = plane.get(key, 3), far(key)
            colour = fade(self.colour(strain.get(r["name"]), hue(key)), k)
            if r["name"] in worked:
                c.create_rectangle(x - 10, y - 10, x + 10, y + 10, outline=WORKED, width=2)
            glow = self.glow(r["name"], p)
            if glow:                         # the information it brings: a soft halo, wider when it brings more
                radius, colour_g = glow
                c.create_oval(x - radius, y - radius, x + radius, y + radius, outline=colour_g, width=2)
            h = 5 if p < 3 else 3
            item = c.create_rectangle(x - h, y - h, x + h, y + h, fill=colour, outline="#0b0d12")
            self.items[item] = key
            if p == 1 and (few or net.origin["relations"].get(r["name"]) != "base"):
                c.create_text(x, y - 12, text=self.graph.shown(net, r["name"]), fill="#8b919c", font=("Consolas", 8))
            elif p == 2:
                c.create_text(x, y - 10, text=self.graph.shown(net, r["name"]), fill=fade("#8b919c", 0.5),
                              font=("Consolas", 7))
        nodes = sorted(net.nodes.items(), key=lambda kv: -plane.get(("n", kv[0]), 3))
        for n, spec in nodes:
            key = ("n", n)
            p = self.places.get(key)
            if p is None:
                continue
            x, y = self.to_screen(p)
            pl, k = plane.get(key, 3), far(key)
            base = net.origin["nodes"].get(n) == "base"
            role = _role(spec)
            size = 9 if role in ("input", "output") else 4 if base else 7
            if pl == 3:
                size = max(2, size * 0.55)
            elif pl == 2:
                size = max(3, size * 0.8)
            fill = ROLE_COLOURS.get(role) if role else hue(key)          # a plain node wears its network's colour
            if base:
                fill = self.graph.SPECIAL["base"]
            dash = (2, 2) if net.origin["nodes"].get(n) == "found" else None
            item = c.create_oval(x - size, y - size, x + size, y + size, fill=fade(fill, k), outline="#0b0d12",
                                 dash=dash)
            self.items[item] = key
            if n in moving and pl < 3:                   # it has just moved: a ring that fades slowly
                c.create_oval(x - size - 4, y - size - 4, x + size + 4, y + size + 4,
                              outline=fade("#ffffff", max(k, moving[n])), width=1)
            if pl == 1 and (few or not base):
                c.create_text(x + size + 4, y, text=self.graph.shown(net, n), anchor="w",
                              fill="#aab0bb" if not base else "#5f6672", font=("Consolas", 9))
            elif pl == 2:
                c.create_text(x + size + 3, y, text=self.graph.shown(net, n), anchor="w", fill=fade("#aab0bb", 0.55),
                              font=("Consolas", 7))
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
        self.overlay()
        if self.hover is not None:
            if self.hover in self.places:
                self.tip()
            else:
                self.hover = None

    @staticmethod
    def colour(strain, holds=HOLDS):
        """A relation's colour: its network's when it holds; amber, then red, when it does not."""
        if strain is None or strain < 1:
            return holds
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
        if word.endswith("/"):               # a folder: what is in it is offered at once, the first one chosen
            self.show_menu()
            if self.menu_open():
                self.move(1)
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
        if new.endswith("/"):                # a folder: what is in it is offered at once, the first one chosen
            self.show_menu()
            if self.menu_open():
                self.move(1)
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
        self.book.bind("<<NotebookTabChanged>>", lambda e: self.looked_at())
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
        from i18n import tr
        name = tr("untitled") if p.get("blank") else os.path.basename(p["path"])
        return name + (" *" if p["dirty"] else "") + (" ✎" if p["edit"] else "")

    # ---- open, close, go to
    def open(self, path, edit=False, blank=False):
        """A file in a tab (blank: a new tab with no file yet; `save NAME.ext` gives it its name)."""
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
        content = ""
        if not blank:
            with open(path, encoding="utf-8", errors="replace") as f:
                content = f.read()
        text.insert("1.0", content)
        text.edit_reset()
        p = {"path": path, "frame": frame, "text": text, "gutter": gutter, "search": search, "edit": False,
             "dirty": False, "blank": blank}
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

    def looked_at(self):
        """A program's tab chosen: its network comes to the front of the picture (if it has been run)."""
        p = self.page()
        if p is None:
            return
        import graph
        name = os.path.splitext(os.path.basename(p["path"]))[0]
        if name in graph.groups(self.shell.vm.net):
            self.shell.vm.focus = ("group", name)
            self.after_run()

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
        if not (p.get("blank") or p["path"].endswith(".grm")):      # only a program is coloured as GRML
            return
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
        if not path and p.get("blank"):
            return "? " + tr("a name first: save NAME.ext (in {folder})", folder=os.getcwd())
        if path:
            path = os.path.expanduser(path)
            if not os.path.splitext(path)[1]:            # no extension given: the tab's own, or .grm for a new one
                path += os.path.splitext(p["path"])[1] if not p.get("blank") and os.path.splitext(p["path"])[1] \
                    else ".grm"
            p["path"] = os.path.abspath(path)            # a relative name: in the folder it is in, as a shell does
            p["blank"] = False
        content = p["text"].get("1.0", "end-1c")
        with open(p["path"], "w", encoding="utf-8") as f:
            f.write(content if content.endswith("\n") or not content else content + "\n")
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
        if not (p.get("blank") or p["path"].endswith(".grm")):
            self.shell.write("  ? " + tr("{name} is not a program (.grm): nothing to run", name=os.path.basename(p["path"])))
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
                out = self.shell.vm.say(line, base, group=os.path.splitext(name)[0])
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


class Logbook:
    """The logbook in a window of its own: the days, and in each the moments that count, with the laws found drawn.
    Made to be read: large type, air, colours by kind of moment. A search line on top; Esc goes back to the prompt."""

    KIND_COLOURS = {"discovery": "#e5c07b", "surprise": "#8fb4d8", "night": "#9d8ec7", "file": "#81b29a",
                    "program": "#5fb3b3", "born": "#f2cc8f", "woke": "#f2cc8f", "found": "#e5c07b", "kept": "#e07a5f"}

    def __init__(self, root, vm, back_to_prompt):
        self.root, self.vm, self.back = root, vm, back_to_prompt
        self.top = None
        self.count = -1

    def show(self):
        import tkinter as tk
        from i18n import tr
        if self.top is None or not self.top.winfo_exists():
            self.top = tk.Toplevel(self.root)
            self.top.configure(bg=BG)
            self.root.update_idletasks()
            x = max(0, self.root.winfo_rootx() + self.root.winfo_width() - 760)
            self.top.geometry(f"720x{max(500, self.root.winfo_height() - 80)}+{x}+{self.root.winfo_rooty() + 40}")
            head = tk.Frame(self.top, bg=BG)
            head.pack(fill="x", padx=18, pady=(14, 6))
            self.title = tk.Label(head, text="", bg=BG, fg="#f2f4f8", font=("DejaVu Serif", 16))
            self.title.pack(side="left")
            self.search = tk.Entry(head, bg="#1b1e24", fg=INK, insertbackground=INK, relief="flat",
                                   font=("Consolas", 10), width=24)
            self.search.pack(side="right", ipady=3)
            self.search.bind("<KeyRelease>", lambda e: self.refresh(force=True))
            self.text = tk.Text(self.top, bg=BG, fg=INK, relief="flat", borderwidth=0, wrap="word",
                                font=("DejaVu Sans", 11), padx=22, pady=8, spacing1=2, spacing3=6, cursor="arrow")
            self.text.pack(fill="both", expand=True)
            self.text.tag_configure("day", font=("DejaVu Serif", 13), foreground="#f2f4f8", spacing1=18, spacing3=8)
            self.text.tag_configure("hour", foreground=DIM, font=("Consolas", 9))
            self.text.tag_configure("sentence", foreground="#e6e8ec")
            self.text.tag_configure("more", foreground="#a7adb8", lmargin1=58, lmargin2=58, font=("DejaVu Sans", 10))
            for k, c in self.KIND_COLOURS.items():
                self.text.tag_configure(k, foreground=c, font=("DejaVu Sans", 12))
            for w in (self.top, self.text, self.search):
                w.bind("<Escape>", lambda e: self.back())
            self.top.protocol("WM_DELETE_WINDOW", self.top.withdraw)
            self.title.configure(text="✎ " + tr("logbook"))
            self.search.insert(0, "")
            self.count = -1
        self.top.deiconify()
        self.top.lift()
        self.refresh(force=True)
        self.search.focus_set()

    def refresh(self, force=False):
        """Written again when something new happened (or the search changed)."""
        import tkinter as tk
        import journal
        from i18n import tr
        if self.top is None or not self.top.winfo_exists() or not self.top.winfo_viewable():
            return
        n = len(journal.entries(self.vm.net))
        if n == self.count and not force:
            return
        self.count = n
        t = self.text
        t.configure(state="normal")
        t.delete("1.0", "end")
        found = self.search.get().strip() or None
        days = journal.days(self.vm.net, found)
        if not days:
            t.insert("end", tr("nothing in the logbook holds {words}", words=found) if found else
                     tr("the logbook is empty"), ("more",))
        for day, es in reversed(days[-30:]):                  # the most recent day first
            t.insert("end", journal.pretty(day) + "\n", ("day",))
            for e in reversed(es):
                icon, sentence, more = journal.say(e)
                t.insert("end", f"{journal.hour(e)}   ", ("hour",))
                t.insert("end", icon + "  ", (e["kind"],))
                t.insert("end", sentence + "\n", ("sentence",))
                for m_ in more:
                    t.insert("end", m_ + "\n", ("more",))
                pts = e.get("points")
                if e["kind"] == "discovery" and pts and len(pts[0]) > 1:
                    t.insert("end", "      ")
                    t.window_create("end", window=self.chart(pts))
                    t.insert("end", "\n")
        t.configure(state="disabled")

    def chart(self, pts):
        """What a law was found in: a small drawing of its points."""
        import tkinter as tk
        xs, ys = pts
        w, h = 260, 74
        c = tk.Canvas(self.text, width=w, height=h, bg="#151820", highlightthickness=0)
        lx, hx, ly, hy = min(xs), max(xs), min(ys), max(ys)
        for a, b in zip(xs, ys):
            x = 8 + (w - 16) * ((a - lx) / ((hx - lx) or 1))
            y = h - 8 - (h - 16) * ((b - ly) / ((hy - ly) or 1))
            c.create_oval(x - 1.6, y - 1.6, x + 1.6, y + 1.6, fill="#e5c07b", outline="")
        return c


def window(vm, Shell, script=None):
    """The machine in a window. script: commands said at the start, as if typed (`--window -c "..."`)."""
    import tkinter as tk
    import editor
    import mind
    root = tk.Tk()
    root.title("GRM machine")
    root.configure(bg=BG)
    root.geometry("1440x800")
    try:                                     # the whole screen at once (the taskbar stays)
        root.state("zoomed")                 # Windows, macOS
    except tk.TclError:
        try:
            root.attributes("-zoomed", True)   # Linux
        except tk.TclError:
            pass

    def wide_enough():
        """No window manager to make it whole: the size of the screen, taken by hand."""
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        if root.winfo_width() < sw - 120:
            root.geometry(f"{sw}x{sh - 70}+0+0")
    root.after(20, wide_enough)
    busy = {"on": False}                     # a long piece of work is running aside
    # two columns: the words on the left; on the right, the network over what it feels and gives out. Between the
    # parts, a sash with a grip: drag it to give one part more room
    from tkinter import ttk
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    style.configure("Sash", sashthickness=9, gripcount=14, background=SASH, lightcolor=GRIP, darkcolor=SASH,
                    bordercolor=SASH_EDGE)
    style.configure("GRM.TPanedwindow", background=SASH_EDGE)
    panes = ttk.Panedwindow(root, orient="horizontal", style="GRM.TPanedwindow")
    panes.pack(fill="both", expand=True)

    # ---- the words (left)
    left = tk.Frame(panes, bg=BG)
    text = tk.Text(left, width=70, bg=PANEL, fg=INK, insertbackground=INK, font=("Consolas", 10),
                   state="disabled", wrap="word", borderwidth=0)
    text.pack(fill="both", expand=True, padx=8, pady=(8, 4))
    # the prompt: "grm>" says the human has the hand, then what is typed
    prompt_row = tk.Frame(left, bg="#1b1e24")
    prompt_row.pack(fill="x", padx=8, pady=(0, 2))
    prompt_label = tk.Label(prompt_row, text="grm>", bg="#1b1e24", fg=DIM, font=("Consolas", 11), padx=4)
    prompt_label.pack(side="left")
    line = tk.Text(prompt_row, height=1, bg="#1b1e24", fg="#e6e8ec", insertbackground="#e6e8ec", font=("Consolas", 11),
                   borderwidth=0, wrap="none", undo=True)
    line.pack(side="left", fill="x", expand=True)
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
    text.tag_configure("label", foreground=DIM)
    text.tag_configure("rule", foreground="#3e4451")
    text.tag_configure("error", foreground="#e06c75")
    text.tag_configure("self", foreground="#7fdbca")
    text.tag_configure("question", foreground="#e5c07b")
    text.tag_configure("warning", foreground="#e8a04c")
    for kind, colour in FILE_COLOURS.items():
        text.tag_configure(kind, foreground=colour)
    line.focus_set()
    panes.add(left, weight=5)

    # ---- the network (right, above)
    right = ttk.Panedwindow(panes, orient="vertical", style="GRM.TPanedwindow")
    panes.add(right, weight=6)
    middle = tk.Frame(right, bg=BG)
    top = tk.Frame(middle, bg=BG)
    top.pack(fill="x", padx=8, pady=(8, 0))
    # seeing it work: play / pause, a tick, a round; what it is doing now
    controls = tk.Frame(top, bg=BG)
    controls.pack(side="top", fill="x", pady=(0, 6))

    def button(cmd, bg, fg, over):
        b = tk.Button(controls, command=cmd, bg=bg, fg=fg, activebackground=over, activeforeground=fg,
                      font=("DejaVu Sans Mono", 11, "bold"), relief="flat", borderwidth=0, padx=14, pady=5,
                      takefocus=0, cursor="hand2", highlightthickness=1, highlightbackground="#4b5563")
        b.bind("<Enter>", lambda e: b.configure(bg=over))
        b.bind("<Leave>", lambda e: b.configure(bg=b.colour))
        b.colour = bg
        return b
    play_button = button(lambda: act("pause" if shell.clock > 0 else "play"), PLAY, "#14161a", PLAY_OVER)
    tick_button = button(lambda: act("tick"), STEP, "#f2f4f8", STEP_OVER)
    round_button = button(lambda: act("step"), STEP, "#f2f4f8", STEP_OVER)
    for b in (play_button, tick_button, round_button):
        b.pack(side="left", padx=(0, 4))
    # what the machine feels: its sound (on demand) and how strongly the picture shows it; a little apart from the
    # buttons that make it run
    tk.Frame(controls, bg=BG, width=18).pack(side="left")
    sound_button = button(lambda: act("ambient off" if shell.ambient is not None else "ambient on"), STEP, "#f2f4f8",
                          STEP_OVER)
    sound_button.pack(side="left", padx=(0, 0))

    def chooser(build):
        mb = tk.Menubutton(controls, bg=STEP, fg="#f2f4f8", activebackground=STEP_OVER, activeforeground="#f2f4f8",
                           font=("DejaVu Sans Mono", 11, "bold"), relief="flat", borderwidth=0, padx=8, pady=5,
                           cursor="hand2", highlightthickness=1, highlightbackground="#4b5563", direction="below")
        menu_ = tk.Menu(mb, tearoff=0, bg="#1b1e24", fg=INK, activebackground="#3e4451", activeforeground="#ffffff",
                        font=("Consolas", 10), borderwidth=0, selectcolor=PLAY)   # what is chosen: a lit mark
        menu_.vars = []                      # the menu's choices stay alive while it is shown (else no mark)
        mb.configure(menu=menu_)
        mb.bind("<Button-1>", lambda e: build(menu_), add="+")
        return mb
    import ambient as _ambient
    import senses as _senses

    def build_sound(menu_):
        menu_.delete(0, "end")
        a = shell.ambient_settings()
        chosen = tk.StringVar(value=a["kind"])
        menu_.vars = [chosen]
        for kind in _ambient.KINDS:
            menu_.add_radiobutton(label=tr(kind), value=kind, variable=chosen,
                                  command=lambda k=kind: act(f"ambient {k}"))
        menu_.add_separator()
        for v in (25, 50, 75, 100):
            menu_.add_command(label=tr("volume {v}%", v=v), command=lambda v=v: act(f"ambient {v}%"))
        menu_.add_separator()
        menu_.add_command(label=tr("mixer") + "…", command=open_mixer)

    mixer = {"top": None}

    def open_mixer():
        """The mixer: the volume, the ambient, the low drone, the bells, the room. Each slider is heard at once; when
        the hand lets go, the command it stands for is written in the words."""
        if mixer["top"] is not None and mixer["top"].winfo_exists():
            mixer["top"].deiconify()
            mixer["top"].lift()
            mixer["top"].focus_set()
            return
        top_ = tk.Toplevel(root)
        mixer["top"] = top_
        top_.transient(root)                 # a small tool window: it stays above the machine's window
        top_.title(tr("mixer"))
        top_.configure(bg=BG)
        top_.resizable(False, False)
        x = root.winfo_rootx() + sound_button.winfo_rootx() - root.winfo_rootx()
        top_.geometry(f"+{max(0, x - 40)}+{sound_button.winfo_rooty() + 44}")
        a = shell.ambient_settings()
        tk.Label(top_, text="♪ " + tr("mixer"), bg=BG, fg="#f2f4f8", font=("DejaVu Sans", 12)).grid(
            row=0, column=0, columnspan=5, pady=(12, 6))
        for col, key in enumerate(("volume",) + _ambient.LAYERS):
            var = tk.DoubleVar(value=round(a[key] * 100))

            def moved(_v, k=key, v=var):
                level = v.get() / 100.0
                if shell.ambient is not None:
                    if k == "volume":
                        shell.ambient.volume = level
                    else:
                        shell.ambient.set_mix(**{k: level})

            def released(_e, k=key, v=var, w=top_):
                act(f"ambient {'' if k == 'volume' else k + ' '}{round(v.get())}%", keep=True)
                w.lift()                     # the mixer stays where the hand is
                w.focus_set()
            sc = tk.Scale(top_, from_=100, to=0, orient="vertical", variable=var, command=moved, length=150,
                          showvalue=True, bg=BG, fg=INK, troughcolor="#262b33", highlightthickness=0, borderwidth=0,
                          sliderlength=18, width=14, font=("Consolas", 8), activebackground=PLAY)
            sc.grid(row=1, column=col, padx=12)
            sc.bind("<ButtonRelease-1>", released)
            tk.Label(top_, text=tr(key), bg=BG, fg=DIM, font=("Consolas", 9)).grid(row=2, column=col, pady=(2, 12))
        top_.bind("<Escape>", lambda e: (top_.withdraw(), line.focus_set()))
    sound_menu = chooser(build_sound)
    sound_menu.configure(text="▾")
    sound_menu.pack(side="left", padx=(1, 4))

    def build_senses(menu_):
        menu_.delete(0, "end")
        s = shell.senses_settings()
        chosen = tk.StringVar(value=s["level"])
        menu_.vars = [chosen]
        for level in _senses.LEVELS:
            menu_.add_radiobutton(label=tr(level), value=level, variable=chosen,
                                  command=lambda lv=level: act(f"senses {lv}"))
        menu_.add_separator()
        for ch in ("motion", "colour", "waves"):
            on = tk.BooleanVar(value=s[ch])
            menu_.vars.append(on)
            menu_.add_checkbutton(label=tr(ch), onvalue=True, offvalue=False, variable=on,
                                  command=lambda c=ch, was=s[ch]: act(f"senses {c} {'off' if was else 'on'}"))
    senses_menu = chooser(build_senses)
    senses_menu.pack(side="left", padx=(0, 4))
    tk.Frame(controls, bg=BG, width=12).pack(side="left")
    logbook_button = button(lambda: act("journal", keep=True), STEP, "#f2f4f8", STEP_OVER)
    logbook_button.pack(side="left", padx=(0, 4))
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
    # the sub-networks: a pill each, to look at one of them (focus)
    pills = tk.Frame(middle, bg=BG)
    pills.pack(side="top", fill="x", padx=8, pady=(4, 0))
    canvas = tk.Canvas(middle, bg=BG, highlightthickness=0)
    canvas.pack(fill="both", expand=True, padx=8, pady=8)
    right.add(middle, weight=4)

    # ---- inside and the outputs (right, below the network)
    panel = tk.Canvas(right, height=230, bg=BG, highlightthickness=0)
    right.add(panel, weight=1)

    def first_sizes(tries=0):
        """The parts as they were left last time (the words a little less than half the width, the network about
        two thirds of its column, the first time). Once the window has its size: the panel under the network is
        always there, at least 170 pixels high."""
        if (root.winfo_width() < 400 or right.winfo_height() < 300) and tries < 60:
            root.after(50, lambda: first_sizes(tries + 1))
            return
        layout = shell.settings.get("layout") or {}
        try:
            w, h = root.winfo_width(), right.winfo_height()
            panes.sashpos(0, int(w * min(0.8, max(0.2, float(layout.get("words", 0.44))))))
            right.sashpos(0, max(150, min(h - 170, int(h * float(layout.get("network", 0.68))))))
        except (tk.TclError, TypeError, ValueError):
            pass

    def save_layout(_e=None):
        """Where the human left the sashes, kept for the next time (as parts of the window, not pixels)."""
        try:
            w, h = root.winfo_width(), right.winfo_height()
            if w > 400 and h > 300:
                shell.settings["layout"] = {"words": round(panes.sashpos(0) / w, 3),
                                            "network": round(right.sashpos(0) / h, 3)}
                shell.save_settings()
        except tk.TclError:
            pass
    root.after(50, first_sizes)
    for p in (panes, right):
        p.bind("<ButtonRelease-1>", save_layout, add="+")

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
                              networks=vm.net.networks, base=shell.base, groups=shell.group_names())
    helping.set(bool(shell.settings.get("help", True)))
    ed = Editor(line, words, lambda ln, cur: shell._complete(ln, cur), log, hint=hint, menu=menu, suggest=suggest,
                helping=helping.get, popup=popup)
    ed.past = list(shell.history)            # Up and Down go back through what was typed, sessions before too
    ed.at = len(ed.past)
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

    def clear_words():
        text.configure(state="normal")
        text.delete("1.0", "end")
        text.configure(state="disabled")
    shell.on_clear = clear_words
    shell.logbook = Logbook(root, vm, back_to_prompt=lambda: (root.focus_force(), line.focus_set()))
    root.bind("<Control-l>", lambda e: act("clear"))
    shell.programs = Programs(root, shell, words, after_run=lambda: draw(steps=20),
                              back_to_prompt=lambda: (root.focus_force(), line.focus_set()))

    def relabel():
        """The window's words, in the language of the machine."""
        help_box.configure(text=" " + tr("typing help (a menu of words while typing)"))
        root.title(tr("GRM machine"))
        prompt_label.configure(text=shell.prompt.strip())
        tick_button.configure(text="⏭ " + tr("tick") + "  F10")
        logbook_button.configure(text="✎ " + tr("logbook"))
        round_button.configure(text="↘ " + tr("round") + "  F11")
        show_doing()
        ed.show_hint()

    def show_doing():
        """The play button and what the machine is doing: playing or paused, in a tick, its watches."""
        playing = shell.clock > 0
        play_button.configure(text=("⏸ " + tr("pause") if playing else "▶ " + tr("play")) + "  F8")
        sound_button.configure(text="♪ " + tr("sound"))
        sound_button.colour = SOUND_ON if shell.ambient is not None else STEP
        sound_button.configure(bg=sound_button.colour)
        s = shell.senses_settings()
        senses_menu.configure(text="◐ " + tr(s["level"]) + " ▾")
        view.feeling = {"level": _senses.LEVELS[s["level"]], "motion": s["motion"], "colour": s["colour"],
                        "waves": s["waves"]}
        parts = [tr("playing at {hz} Hz", hz=f"{shell.clock:g}") if playing else tr("paused")]
        m = vm.machine
        if vm.stepping:
            parts.append(tr("step by step"))
        if vm.in_tick() and m is not None:
            parts.append(tr("in tick {tick}, round {round}", tick=m.ticks + 1, round=m.rounds - m._tick["r0"]))
        if vm.watches:
            parts.append(tr("{n} watch(es)", n=len(vm.watches)))
        doing.configure(text="  ·  ".join(parts))

    def act(typed, keep=False):
        """A button or a key: said as if typed, so that it shows in the words. keep: the window it opened keeps the
        focus (the logbook), instead of the prompt."""
        log.write(f"{shell.prompt}{typed}\n")
        shell.onecmd(typed)
        relabel()
        draw(steps=20)
        if not keep:
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
        master_text.configure(text=tr("master equation ({when}{tick})", when=when, tick=tick) + ":  "
                              + view.graph.in_equation(vm.net, res["text"])
                              + extra)
        ago_note.configure(text=tr("(0: now; 240 ticks kept)"))

    ago.configure(command=lambda _v: show_master(force=True))

    def bar(y, label, v, size=1.0):
        panel.create_text(12, y, text=label, anchor="w", fill=DIM, font=("Consolas", 9))
        mid = 200
        panel.create_line(mid, y - 6, mid, y + 6, fill=LINE)
        w = 120 * max(-1.0, min(1.0, v / size))
        if w >= 0:
            panel.create_rectangle(mid, y - 4, mid + w + 1, y + 4, fill="#ffb347", outline="")
        else:
            panel.create_rectangle(mid + w - 1, y - 4, mid, y + 4, fill="#5fa8d3", outline="")

    def draw_panel():
        """Under the network: on the left what it feels and its room, on the right its outputs, side by side."""
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
        panel.create_text(12, 92, text=tr("links {n} of {cap} ({limit})", n=mind.links(vm.net), cap=cap,
                                          limit=limit), anchor="w", fill=DIM, font=("Consolas", 9))
        panel.create_text(12, 108, text=tr("rent {p} bit a link a tick", p=f"{mind.price(vm.net):.2g}"), anchor="w",
                          fill=DIM, font=("Consolas", 9))
        m = vm.machine
        if m is not None:
            panel.create_text(12, 132, text=tr("tick {tick}   {p} processors   round {round}", tick=m.ticks,
                                               p=m.processors(), round=m.rounds),
                              anchor="w", fill=DIM, font=("Consolas", 9))
        # the outputs: a card each, in columns, from left to right
        x0 = 360
        panel.create_line(x0 - 16, 8, x0 - 16, max(40, panel.winfo_height() - 8), fill="#262b33")
        panel.create_text(x0, 14, text=tr("outputs"), anchor="w", fill=DIM, font=("Consolas", 10))
        names = vm.outputs() + (["surprise"] if vm.history.get("surprise") else [])
        shown = {"surprise": tr("surprise")}
        card_h, top = 64, 32
        columns = max(1, (panel.winfo_width() - x0) // 280)
        card_w = max(280, (panel.winfo_width() - x0) // columns)
        per_column = max(1, (panel.winfo_height() - top) // card_h)
        for k, name in enumerate(names):
            x = x0 + (k // per_column) * card_w
            y = top + (k % per_column) * card_h + 8
            if x + 240 > panel.winfo_width():
                panel.create_text(x0 + (k // per_column - 1) * card_w + card_w - 30, panel.winfo_height() - 12,
                                  text=tr("and {n} more", n=len(names) - k), anchor="e", fill=DIM,
                                  font=("Consolas", 9))
                break
            try:
                h = list(vm.history.get(name) or [vm.get(name)])
            except Exception:  # noqa: BLE001 - an output that cannot be read is skipped, not a crash
                continue
            v = h[-1]
            size = max(abs(q) for q in h) or 1.0
            panel.create_text(x, y, text=f"{shown.get(name, name)} = {v:.6g}", anchor="w", fill="#e6e8ec",
                              font=("Consolas", 11))
            mid = x + 150
            panel.create_line(mid, y + 10, mid, y + 22, fill=LINE)
            if v >= 0:
                panel.create_rectangle(mid, y + 12, mid + 120 * v / size + 1, y + 20, fill="#ffb347", outline="")
            else:
                panel.create_rectangle(mid + 120 * v / size - 1, y + 12, mid, y + 20, fill="#5fa8d3", outline="")
            lo, hi = min(h + [0.0]), max(h + [0.0])
            span = (hi - lo) or 1.0
            if len(h) > 1:
                pts = []
                for i, val in enumerate(h):
                    pts += [x + (card_w - 30) * i / max(1, len(h) - 1), y + 50 - 24 * (val - lo) / span]
                panel.create_line(*pts, fill="#8a6db8", width=1.5)

    pill_state = {"key": None}

    def refresh_pills():
        """A pill per network in the network, the one looked at lit: a click brings it to the front."""
        import i18n
        names = shell.group_names()
        key = (tuple(names), vm.focus, i18n.lang())
        if key == pill_state["key"]:
            return
        pill_state["key"] = key
        for w in pills.winfo_children():
            w.destroy()
        if not names:
            return
        tk.Label(pills, text=tr("focus") + " ", bg=BG, fg=DIM, font=("Consolas", 9)).pack(side="left")
        import graph
        graph_colours = graph.colours(vm.net)
        for name in ["all"] + names:
            lit = (vm.focus is None) if name == "all" else (vm.focus == ("group", name))
            text = tr("everything") if name == "all" else name
            colour = graph_colours.get(name, PILL_LIT)
            p = tk.Label(pills, text=f" {text} ", bg=colour if lit else mix(BG, colour, 0.28),
                         fg="#14161a" if lit else mix(INK, colour, 0.35),
                         font=("Consolas", 9), padx=4, pady=1, cursor="hand2")
            p.pack(side="left", padx=(0, 4))
            p.bind("<Button-1>", lambda e, n=name: act(f"focus {n}"))

    def draw(steps=6):
        if busy["on"]:
            return
        try:
            refresh_pills()
            draw_panel()
            view.draw(steps=steps)
            show_master()
        except Exception as e:  # noqa: BLE001 - the picture fails, the machine goes on and says why
            import diagnose
            log.write("  ! " + diagnose.internal(e) + "\n")

    def enter(_e=None, aside=True):
        if busy["on"]:                       # a long piece of work is going: Enter waits for it
            return "break"
        word = ed.chosen()
        if word is not None:                 # a word chosen in the menu: taken, not run
            return ed.take(word)
        ed.close_menu()
        typed = ed.get()
        ed.remember(typed)
        shell.add_history(typed)
        ed.set("")
        log.write(f"{shell.prompt}{typed}\n")
        if aside and shell.is_long(typed):
            return run_aside(typed)
        finish(shell.onecmd(typed))
        return "break"

    def finish(stop):
        if stop:
            root.destroy()
            return
        shell.mark_errors()
        relabel()
        draw(steps=20)

    def run_aside(typed):
        """A long piece of work (a file, a night, many ticks) runs aside: the window stays alive, a wheel turns at the
        end of the prompt's row with how far it is, and what it says is shown as it comes."""
        import threading
        busy["on"] = view.busy = True
        state = {"text": "", "k": 0, "result": None, "done": False}
        vm.on_progress = lambda d, t, what: state.update(text=progress_text(d, t, what))

        def work():
            try:
                state["result"] = shell.onecmd(typed)
            finally:
                state["done"] = True
        threading.Thread(target=work, daemon=True).start()

        def turn():
            log.pump()
            if not state["done"]:               # the line under the prompt turns into the wheel, and how far
                state["k"] += 1
                hint.configure(fg="#7fdbca", font=("DejaVu Sans Mono", 9),
                               text=SPINNER[state["k"] % len(SPINNER)] + "  " + typed.strip()[:60]
                               + ("\n   " + state["text"] if state["text"] else ""))
                root.after(90, turn)
                return
            hint.configure(fg="#8b919c", font=("Consolas", 9))
            ed.show_hint()
            vm.on_progress = None
            busy["on"] = view.busy = False
            finish(state["result"])
        root.after(90, turn)
        return "break"

    line.bind("<Return>", enter)
    last = [time.perf_counter()]

    def clock():
        if busy["on"]:
            root.after(50, clock)
            return
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

    seen = {"ticks": -1, "rounds": -1, "at": 0.0}

    def sense_loop():
        """A few times a second: what the machine feels goes to the picture and to the sound; the moments are shared.
        Only what moves is drawn again."""
        if not busy["on"]:
            try:
                m = vm.machine
                worked = set()
                if m is not None:
                    if m.ticks != seen["ticks"]:
                        worked = set(getattr(vm, "last_worked", ()) or ())
                    elif vm.holding() and m.rounds != seen["rounds"]:
                        names = {r["name"] for r in vm.net.relations}
                        worked = {m.factors[f].name for f in getattr(m, "busy", ())} & names
                    seen["ticks"], seen["rounds"] = m.ticks, m.rounds
                now = time.perf_counter()
                if now - seen.get("book", 0.0) > 1.5:
                    seen["book"] = now
                    shell.logbook.refresh()          # an open logbook is written as things happen
                if worked or now - seen["at"] > 0.25:
                    seen["at"] = now
                    state = shell.feel.state(vm)
                    moments = shell.feel.moments(vm)
                    view.feel(state, worked, moments)
                    for mo in moments:
                        log.write("  ~ " + ("✦ " if mo["kind"] == "discovery" else "≈ ") + mo["sentence"] + "\n")
                    if shell.ambient is not None:
                        shell.ambient.set(state)
                        for mo in moments:
                            shell.ambient.event(mo["kind"], mo.get("ratio", 1.5))
                    if moments:
                        canvas.configure(bg=view.light())
                view.sea_at(shell.ambient)
                if view.sea_now is not None and not view.drag and now - seen.get("wave", 0.0) > 0.085:
                    seen["wave"] = now                   # the picture moves with the swell, gently
                    view.draw(steps=0)
                elif view.moving():
                    view.overlay()
            except Exception:  # noqa: BLE001 - what it feels is shown next time
                pass
        root.after(60, sense_loop)
    root.after(500, sense_loop)

    def save_ui():
        """The window as the human leaves it: its tabs, the one chosen, whether the logbook is open."""
        progs = shell.programs
        shown = progs is not None and progs.top is not None and progs.top.winfo_exists() and progs.top.winfo_viewable()
        pages = getattr(progs, "pages", []) if shown else []
        shell.settings["tabs"] = [p["path"] for p in pages]
        try:
            shell.settings["tab"] = progs.book.index(progs.book.select()) if pages else 0
        except Exception:  # noqa: BLE001
            shell.settings["tab"] = 0
        book = shell.logbook
        shell.settings["logbook"] = bool(book.top is not None and book.top.winfo_exists() and
                                         book.top.winfo_viewable())

    def close():
        save_layout()
        save_ui()
        shell.do_quit("")
        root.destroy()

    def as_left():
        """The window as it was left: its tabs, the logbook, the sound if it was on (it rises from silence)."""
        s = shell.settings
        for path in s.get("tabs") or []:
            if os.path.isfile(path):
                shell.programs.open(path)
        if s.get("tabs") and shell.programs.pages:
            shell.programs.select(str(min(len(shell.programs.pages), int(s.get("tab", 0)) + 1)))
        if s.get("logbook"):
            shell.logbook.show()
        if shell.ambient_settings().get("on"):
            act("ambient on")
        root.after(200, lambda: (root.focus_force(), line.focus_set()))

    root.protocol("WM_DELETE_WINDOW", close)

    def start():
        if shell.settings_path:
            as_left()
        for typed in (script or "").split(";"):
            if typed.strip():
                ed.set(typed.strip())
                enter(aside=False)
        draw(steps=60)

    root.after(50, start)
    clock()
    root.mainloop()
