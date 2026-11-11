# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Anthony Charretier
"""The body of the GRM machine: the converters between the network's outputs and a human's eyes and ears.

Nothing here decides anything: the network gives its outputs, the body shows and plays them.
  - The eyes: a window with the words typed to the machine and its answers on one side, and on the other side a
    part reserved to the outputs: each output with its value, its two opposed channels around zero (ON to the right,
    OFF to the left) and its last 240 ticks; and the network's
    surprise (how far its last inputs were from what it expected of them).
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
    """The Shell writes here; the window shows it."""

    def __init__(self, text):
        self.text = text

    def write(self, s):
        self.text.configure(state="normal")
        self.text.insert("end", s)
        self.text.see("end")
        self.text.configure(state="disabled")

    def flush(self):
        pass


def window(vm, Shell):
    import tkinter as tk
    root = tk.Tk()
    root.title("GRM machine")
    root.configure(bg="#0e1016")
    left = tk.Frame(root, bg="#0e1016")
    left.pack(side="left", fill="both", expand=True)
    text = tk.Text(left, width=78, height=34, bg="#14161a", fg="#c8ccd4", insertbackground="#c8ccd4",
                   font=("Consolas", 10), state="disabled", wrap="word", borderwidth=0)
    text.pack(fill="both", expand=True, padx=8, pady=(8, 4))
    entry = tk.Entry(left, bg="#1b1e24", fg="#e6e8ec", insertbackground="#e6e8ec", font=("Consolas", 11),
                     borderwidth=0)
    entry.pack(fill="x", padx=8, pady=(0, 8))
    entry.focus_set()
    panel = tk.Canvas(root, width=420, height=560, bg="#0e1016", highlightthickness=0)
    panel.pack(side="right", fill="y")
    log = _Log(text)
    shell = Shell(vm, out=log)
    log.write(shell.intro + "\n")

    def draw():
        panel.delete("all")
        panel.create_text(12, 14, text="outputs", anchor="w", fill="#7d838d", font=("Consolas", 10))
        y = 40
        names = vm.outputs() + (["surprise"] if vm.history.get("surprise") else [])
        for name in names:
            h = vm.history.get(name) or [vm.get(name)]
            if name == "surprise":
                h = list(h)
            v = h[-1]
            size = max(abs(x) for x in h) or 1.0
            panel.create_text(12, y, text=f"{name} = {v:.6g}", anchor="w", fill="#e6e8ec", font=("Consolas", 11))
            # two opposed channels around zero, as the senses have them: ON to the right, OFF to the left
            mid = 202
            panel.create_line(mid, y + 10, mid, y + 22, fill="#4b525e")
            if v >= 0:
                panel.create_rectangle(mid, y + 12, mid + 190 * v / size + 1, y + 20, fill="#ffb347", outline="")
            else:
                panel.create_rectangle(mid + 190 * v / size - 1, y + 12, mid, y + 20, fill="#5fa8d3", outline="")
            lo, hi = min(h + [0.0]), max(h + [0.0])
            span = (hi - lo) or 1.0
            if len(h) > 1:
                pts = []
                for k, val in enumerate(h):
                    pts += [12 + 380 * k / max(1, len(h) - 1), y + 64 - 36 * (val - lo) / span]
                panel.create_line(*pts, fill="#8a6db8", width=1.5)
            y += 84
            if y > 520:
                break
        m = vm.machine
        if m is not None:
            panel.create_text(12, 548, text=f"tick {m.ticks}   {m.processors()} processors   round {m.rounds}",
                              anchor="w", fill="#7d838d", font=("Consolas", 9))

    def enter(_e=None):
        line = entry.get()
        entry.delete(0, "end")
        log.write(f"grm> {line}\n")
        if shell.onecmd(line):
            root.destroy()
            return
        draw()

    entry.bind("<Return>", enter)
    last = [time.perf_counter()]

    def clock():
        if shell.clock > 0 and time.perf_counter() - last[0] >= 1.0 / shell.clock:
            last[0] = time.perf_counter()
            vm.tick()
            if shell.sound:
                play(sound_of(vm.history))
            draw()
        root.after(10, clock)

    def close():
        shell.do_quit("")
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", close)
    draw()
    clock()
    root.mainloop()
