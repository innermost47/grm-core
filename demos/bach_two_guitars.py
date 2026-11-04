# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Anthony Charretier
"""
Bach, Prelude of the Cello Suite No. 1 (BWV 1007), arranged for two GRM guitars.

Left guitar: Bach's line, note for note from the score (MusicXML), transposed to D (as guitarists often play it),
played with the fingers. Right guitar: the harmony that each bar of the prelude spells out, found from its notes and
voiced on the six strings, played in changing ways along the piece: silent at first, then bass and chord with the
fingers, open strums with the pick, palm-muted eighths over the long dominant pedal, wide strums to the end.
Every note, stroke, finger noise, string answering in sympathy and the room around them come from the GRM
networks of grm_guitar.py. The two guitars have different bodies; each reaches both ears through its own path in
the room (decorrelated reverberation), mostly from its own side.

Run (needs tkinter for the guitar module; no window is shown):
    python demos/bach_two_guitars.py                                   # a studio, the listener close to the guitars
    python demos/bach_two_guitars.py --room Church --walls "Painted brick" --distance 4   # the first, very wet mix
    python demos/bach_two_guitars.py --remix ...                       # only the room again (guitars from the cache)
Rooms: Small room, Living room, Studio, Church. Walls: Painted brick, Plaster, Wood panels, Glass, Curtains, Carpet.
The further the listener beyond the room's critical distance (room network), the more reverberation.
"""

import argparse
import math
import os
import sys
import time
import wave
import xml.etree.ElementTree as ET

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import grm_guitar as g  # noqa: E402

SCORE = os.path.join(HERE, "bach_suite1_bwv1007.musicxml")
OUT = os.path.join(
    os.path.dirname(HERE), "docs", "audio", "bach_prelude_two_grm_guitars.wav"
)
TRANSPOSE = 7  # G major -> D major
TEMPO = 66.0  # quarter notes per minute
OPEN_MIDI = [40, 45, 50, 55, 59, 64]  # E2 A2 D3 G3 B3 E4, string index 0 = low E
STEP = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
SR = g.SAMPLE_RATE
DRY_CACHE = os.path.join(
    HERE, ".bach_two_guitars_dry.npz"
)  # the two guitars before the room


# ============================================================
# THE SCORE
# ============================================================


def read_prelude(path=SCORE, last_bar=42):
    """(bar, beat in the bar, length in beats, midi) of every note of the Prelude."""
    root = ET.parse(path).getroot()
    part = root.find("part")
    div = int(part.find(".//divisions").text)
    notes = []
    for m in part.findall("measure"):
        bar = int(m.get("number"))
        if bar > last_bar:
            break
        pos = 0
        for el in m:
            if el.tag == "note":
                d = int(el.findtext("duration") or 0)
                chord = el.find("chord") is not None
                p = el.find("pitch")
                if p is not None:
                    midi = (
                        12 * (int(p.findtext("octave")) + 1)
                        + STEP[p.findtext("step")]
                        + int(p.findtext("alter") or 0)
                    )
                    notes.append(
                        (
                            bar,
                            (pos if not chord else last_pos) / div,
                            d / div,
                            midi + TRANSPOSE,
                        )
                    )
                if not chord:
                    last_pos = pos
                    pos += d
            elif el.tag == "backup":
                pos -= int(el.findtext("duration"))
            elif el.tag == "forward":
                pos += int(el.findtext("duration"))
    return notes


# ============================================================
# ON THE FRETBOARD
# ============================================================


def fingering(midis, max_fret=14):
    """String and fret for each note of a line: dynamic programming that keeps the hand where it is (small
    position changes), prefers the middle of the neck, and lets two consecutive notes share a string rarely.
    """
    options = []
    for m in midis:
        opts = [
            (s, m - OPEN_MIDI[s]) for s in range(6) if 0 <= m - OPEN_MIDI[s] <= max_fret
        ]
        options.append(opts or [(0, max(0, m - OPEN_MIDI[0]))])
    cost = [{o: 0.02 * o[1] for o in options[0]}]
    back = [{}]
    for k in range(1, len(midis)):
        cur, bk = {}, {}
        for o in options[k]:
            best, arg = None, None
            for p, c in cost[-1].items():
                pos_o = o[1] if o[1] > 0 else None
                pos_p = p[1] if p[1] > 0 else None
                jump = (
                    abs(pos_o - pos_p)
                    if (pos_o is not None and pos_p is not None)
                    else 0
                )
                same = (
                    1.5 if o[0] == p[0] else 0.0
                )  # the previous note would be cut short
                c2 = c + 0.6 * max(0, jump - 3) + 0.08 * jump + same + 0.02 * o[1]
                if best is None or c2 < best:
                    best, arg = c2, p
            cur[o], bk[o] = best, arg
        cost.append(cur)
        back.append(bk)
    o = min(cost[-1], key=cost[-1].get)
    path = [o]
    for k in range(len(midis) - 1, 0, -1):
        o = back[k][o]
        path.append(o)
    return path[::-1]


def bar_chord(bar_notes):
    """The harmony a bar spells out: its bass (lowest note) and the pitch classes that last more than a passing
    note (over an eighth of the bar)."""
    weight = {}
    for _, _, d, m in bar_notes:
        weight[m % 12] = weight.get(m % 12, 0) + d
    total = sum(weight.values())
    bass = min(m for _, _, _, m in bar_notes) % 12
    main = [
        p for p in sorted(weight, key=weight.get, reverse=True) if weight[p] > total / 8
    ][:4]
    pcs = set(main) | {bass}
    if len(pcs) < 3:  # a bare pedal: complete the triad inside the key
        third = (bass + 4) % 12 if (bass + 4) % 12 in D_MAJOR else (bass + 3) % 12
        pcs |= {third, (bass + 7) % 12}
    return bass, pcs


D_MAJOR = {2, 4, 6, 7, 9, 11, 1}


def chromatic(pcs):
    """Two notes a semitone apart: a passing, chromatic bar, not a chord to strum."""
    return any((p + 1) % 12 in pcs for p in pcs)


def voicing(bass, pcs, max_span=3, max_fret=9):
    """Frets (None = muted) for the six strings: the bass on the lowest sounding string, the strings above it all
    sounding (to be strummed), as many of the chord's notes as possible, a compact hand low on the neck.
    Every combination is tried."""
    from itertools import product

    best = None
    for low in range(0, 3):
        options = []
        for s in range(low, 6):
            opts = [f for f in range(0, max_fret + 1) if (OPEN_MIDI[s] + f) % 12 in pcs]
            if s == low:
                opts = [f for f in opts if (OPEN_MIDI[s] + f) % 12 == bass]
            options.append(opts)
        if any(not o for o in options):
            continue
        for combo in product(*options):
            fretted = [f for f in combo if f > 0]
            span = (max(fretted) - min(fretted)) if fretted else 0
            if span > max_span:
                continue
            got = {(OPEN_MIDI[low + k] + f) % 12 for k, f in enumerate(combo)}
            score = (
                3 * len(got & pcs)
                + 0.8 * len(combo)
                - 0.6 * span
                - 0.3 * (max(fretted) if fretted else 0)
                + 0.3 * combo.count(0)
            )
            if best is None or score > best[0]:
                best = (score, [None] * low + list(combo))
    return best[1] if best else [None, None, 0, 2, 3, 2]


# ============================================================
# THE PERFORMANCE
# ============================================================


def make_app():
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    g.messagebox.showerror = lambda *a: print("ERROR", a)
    app = g.GRMGuitarApp(root)
    app.live_change = lambda: None
    app.loop.set(False)
    return root, app


def seconds(bar, beat, tempo_map):
    return tempo_map(bar, beat)


def build_tempo():
    """Bar -> seconds: steady, a breath at the end of phrases, a ritardando on the last two bars."""
    q = 60.0 / TEMPO
    starts = [0.0]
    for bar in range(1, 44):
        stretch = 1.0
        if bar in (4, 12, 21, 30):
            stretch = 1.04  # a small breath at the end of a phrase
        if bar >= 40:
            stretch = 1.0 + 0.12 * (bar - 39)  # ritardando
        starts.append(starts[-1] + 4 * q * stretch)

    def at(bar, beat):
        b0, b1 = starts[bar - 1], starts[bar]
        return b0 + (b1 - b0) * beat / 4.0

    return at, starts


def lead_part(app, notes, at):
    """Bach's line: fingered, each note ringing until its string is played again."""
    app.technique.set("Fingers")
    places = fingering([m for *_, m in notes])
    out = []
    by_bar = {}
    for k, n in enumerate(notes):
        by_bar.setdefault(n[0], []).append(k)
    last_on_string = {}
    for bar, ks in by_bar.items():
        grid = [(at(bar, notes[k][1]), j % 8) for j, k in enumerate(ks)]
        step = max(1e-3, (at(bar, 4) - at(bar, 0)) / 16)
        strokes = app.strokes(
            grid, step
        )  # the player network: timing, force, pluck point
        for j, k in enumerate(ks):
            _, beat, dur, midi = notes[k]
            s, f = places[k]
            st = strokes[j]
            start = max(0.0, st["t"])
            accent = 1.15 if beat == 0 else 1.0
            ring = 2.5 if dur >= 1 else 1.6
            nt = app.note(
                s, f, start, ring, False, 0.75 * accent * st["force"], st["p"], st
            )
            if s in last_on_string:
                prev = last_on_string[s]
                prev["length"] = max(0.03, min(prev["length"], start - prev["start"]))
            last_on_string[s] = nt
            out.append(nt)
    return out


SECTIONS = [  # (first bar, last bar, how the right guitar plays)
    (1, 4, "rest"),
    (5, 12, "pinch"),
    (13, 21, "strum"),
    (22, 30, "palm"),
    (31, 38, "strum_wide"),
    (39, 41, "big"),
    (42, 42, "final"),
]


def style_of(bar):
    return next(s for a, b, s in SECTIONS if a <= bar <= b)


def rhythm_part(app, notes, at):
    """The harmony of each bar, played in the style of its section."""
    out, squeaks, spans = [], [], []
    by_bar = {}
    for n in notes:
        by_bar.setdefault(n[0], []).append(n)
    held = {}
    last = {}
    rng = np.random.default_rng(7)
    for bar in sorted(by_bar):
        style = style_of(bar)
        if style == "rest":
            continue
        bass, pcs = bar_chord(by_bar[bar])
        frets = voicing(bass, pcs)
        if chromatic(pcs) and style not in ("final",):
            # a chromatic bar: only its bass, held (the lead's line carries the harmony)
            low = next(s for s in range(6) if frets[s] is not None)
            frets = [None] * 6
            frets[low] = voicing(bass, pcs)[low]
            style = "bass"
        strings = [s for s in range(6) if frets[s] is not None]
        new = {s: frets[s] for s in strings}
        t_bar = at(bar, 0)
        # the left hand changes shape just before the bar (finger noises on the wound strings)
        if held and new != held:
            lead = min(0.18, 0.3 * (at(bar, 1) - t_bar))
            squeaks += app.change_hand(
                held,
                new,
                t_bar - lead,
                lead,
                out,
                last,
                rng,
                (
                    {"palm_x": g.PALM_X, "palm_N": g.PALM_FORCE}
                    if style == "palm"
                    else None
                ),
            )
        held = new
        if style == "bass":
            app.technique.set("Fingers")
            st = app.strokes([(t_bar, 0)], 0.25)[0]
            s = strings[0]
            nt = app.note(
                s,
                frets[s],
                max(0.0, st["t"]),
                3.5,
                False,
                0.55 * st["force"],
                st["p"],
                st,
            )
            if s in last:
                last[s]["length"] = max(
                    0.02, min(last[s]["length"], nt["start"] - last[s]["start"])
                )
            out.append(nt)
            last[s] = nt
            continue
        if style == "pinch":  # bass on 1, the chord's top notes on 3 (fingers)
            app.technique.set("Fingers")
            grid = [(at(bar, 0), 0), (at(bar, 2), 4)]
            st = app.strokes(grid, 0.25)
            groups = [[strings[0]], strings[-3:]]
            for stroke, group in zip(st, groups):
                for s in group:
                    nt = app.note(
                        s,
                        frets[s],
                        max(0.0, stroke["t"]),
                        3.0,
                        False,
                        0.5 * stroke["force"],
                        stroke["p"],
                        stroke,
                    )
                    out.append(nt)
                    last[s] = nt
            continue
        app.technique.set("Pick")
        if style == "strum":
            pattern = [(0, False), (2, False), (2.5, True), (3.5, True)]
        elif style == "palm":
            pattern = [(b * 0.5, False) for b in range(8)]
        elif style == "strum_wide":
            pattern = [
                (0, False),
                (1, False),
                (1.5, True),
                (2.5, True),
                (3, False),
                (3.5, True),
            ]
        elif style == "big":
            pattern = [
                (0, False),
                (1, False),
                (2, False),
                (2.5, True),
                (3, False),
                (3.5, True),
            ]
        else:  # final: one wide stroke, let ring
            pattern = [(0, False)]
        grid = [(at(bar, beat), int(beat * 2) % 8) for beat, _ in pattern]
        st = app.strokes(grid, (at(bar, 4) - t_bar) / 8)
        level = {
            "strum": 0.45,
            "palm": 0.55,
            "strum_wide": 0.6,
            "big": 0.8,
            "final": 0.9,
        }[style]
        muted = style == "palm"
        order_all = (
            strings if not muted else strings[:3]
        )  # palm-muted eighths on the low strings
        for (beat, up), stroke in zip(pattern, st):
            order = sorted(order_all, reverse=up)
            ring = 6.0 if style == "final" else 1.6
            for s, delay, share in g.strum_contacts(order, stroke, up):
                t = max(0.0, stroke["t"] + delay)
                if s in last:
                    prev = last[s]
                    prev["length"] = max(0.02, min(prev["length"], t - prev["start"]))
                nt = app.note(
                    s,
                    frets[s],
                    t,
                    ring,
                    muted,
                    level * stroke["force"] * share,
                    stroke["p"],
                    stroke,
                )
                out.append(nt)
                last[s] = nt
        if muted:
            spans.append(
                (
                    t_bar,
                    at(bar, 4),
                    [app.palm_model(s, held.get(s, 0)) for s in range(6)],
                )
            )
    return out, squeaks, spans


def final_chord(app, at):
    """The lead closes on the score's last chord (G, D, B in D major: D, A, F#), rolled with the fingers."""
    app.technique.set("Fingers")
    t = at(42, 0)
    chord = [(2, 0), (3, 2), (4, 3), (5, 2)]  # D A D F# (open D shape)
    return [
        app.note(s, f, t + 0.045 * k, 6.0, False, 0.8, 0.2)
        for k, (s, f) in enumerate(chord)
    ]


# ============================================================
# MIX
# ============================================================


def convolve(x, h):
    L = len(x) + len(h) - 1
    n = 1 << (L - 1).bit_length()
    return np.fft.irfft(np.fft.rfft(x, n) * np.fft.rfft(h, n), n)[: len(x)]


def render_guitars():
    """The two guitars without the room (the long part): left = Bach's line, right = the harmony."""
    t0 = time.perf_counter()
    notes = read_prelude()
    at, starts = build_tempo()
    print(f"{len(notes)} notes of the Prelude, {starts[42]:.0f} s")
    root, app = make_app()
    for var in (app.human, app.sympathy, app.squeak_on, app.stiff):
        var.set(True)

    # left guitar: a bright small-bodied guitar
    lead = lead_part(app, [n for n in notes if n[0] < 42], at) + final_chord(app, at)
    total = starts[42] + 5.0
    app.body_size.set(0.92)
    app.top_mm.set(2.6)
    left = app.render(lead, total, [], ())
    print(f"left guitar: {len(lead)} notes rendered ({time.perf_counter() - t0:.0f} s)")

    # right guitar: a larger, darker body
    rhythm, squeaks, spans = rhythm_part(app, notes, at)
    app.body_size.set(1.15)
    app.top_mm.set(3.0)
    right = app.render(rhythm, total, squeaks, spans)
    print(
        f"right guitar: {len(rhythm)} notes, {len(squeaks)} finger noises ({time.perf_counter() - t0:.0f} s)"
    )
    root.destroy()
    return left.astype(float), right.astype(float)


def main():
    ap = argparse.ArgumentParser(
        description="Bach, Prelude BWV 1007, for two GRM guitars"
    )
    ap.add_argument("--room", default="Studio", choices=list(g.ROOMS))
    ap.add_argument("--walls", default="Wood panels", choices=list(g.MATERIALS))
    ap.add_argument(
        "--distance", type=float, default=0.8, help="listener to the guitars, m"
    )
    ap.add_argument(
        "--remix",
        action="store_true",
        help="reuse the guitars rendered last time, only the room again",
    )
    ap.add_argument("--out", default=OUT)
    args = ap.parse_args()
    t0 = time.perf_counter()
    if args.remix and os.path.exists(DRY_CACHE):
        d = np.load(DRY_CACHE)
        left, right = d["left"], d["right"]
    else:
        left, right = render_guitars()
        np.savez_compressed(DRY_CACHE, left=left, right=right)

    # the room: each guitar reaches each ear by its own path (different image sources and tails);
    # the far ear is 15 % further away
    size = g.ROOMS[args.room]
    room = g.room_network(size, args.walls)
    near, far = args.distance, args.distance * 1.15
    print(
        f"{args.room}, {args.walls}: RT60 {room['RT3']:.2f} s at 1 kHz, critical distance {room['rc']:.2f} m; "
        f"listener at {near:.2f} m: reverberant / direct energy about {(near / room['rc']) ** 2:.1f}"
    )
    irs = {
        k: g.room_impulse(room, size, dist, seed=sd)
        for k, (dist, sd) in {
            "LL": (near, 3),
            "LR": (far, 11),
            "RL": (far, 17),
            "RR": (near, 23),
        }.items()
    }
    n = max(len(left), len(right))
    left = np.pad(left, (0, n - len(left)))
    right = np.pad(right, (0, n - len(right)))
    # the same loudness for both guitars where they play (RMS over their active parts), the rhythm a little behind
    rms = lambda x: math.sqrt(np.mean(x[np.abs(x) > 1e-3] ** 2))
    left, right = left / rms(left), right / rms(right) * 0.8
    L = 0.9 * convolve(left, irs["LL"]) + 0.35 * convolve(right, irs["RL"])
    R = 0.35 * convolve(left, irs["LR"]) + 0.9 * convolve(right, irs["RR"])
    peak = max(np.abs(L).max(), np.abs(R).max())
    stereo = np.stack([L, R], axis=1) / peak * 0.9
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with wave.open(args.out, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((stereo * 32767).astype("<i2").tobytes())
    print(
        f"written {args.out} ({len(stereo) / SR:.0f} s, {time.perf_counter() - t0:.0f} s of computing)"
    )


if __name__ == "__main__":
    main()
