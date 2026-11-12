# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Anthony Charretier
"""The machine heard: a slow, soft, calm ambient sound that follows what it feels (senses.py), in real time.

    engine   a low hum, like an engine at rest: its pulse follows how much the machine works, a roughness comes
             when its relations do not hold
    pad      a voice for each relation that brings information, tuned on the harmonics of one note: a relation
             that holds is in tune, one that does not beats against the others (the beat is its disagreement)
    wind     a breath of filtered noise: it rises when the machine works, a surprise is a slow wave

What it feels moves the sound: pleasure opens the higher harmonics, displeasure closes them; a relation found by
itself rings a soft bell on an interval taken from its law; a surprise swells and settles. Everything goes through a
long reverb.

Calm by design (it is meant for everyone, autistic people included): nothing starts suddenly (every change takes
seconds), nothing is sharp (no harmonics above a few kHz), the level is capped, and it is off unless asked for.

The sound is made here, block after block (numpy); sounddevice plays it when it is there. Without it, save()
writes the same sound to a WAV file.
"""
import math
import threading
import wave

import numpy as np

try:
    from scipy.signal import lfilter
except ImportError:  # pragma: no cover
    lfilter = None

RATE = 44100
BLOCK = 256
KINDS = ("engine", "pad", "wind")
BASE = {"engine": 65.41, "pad": 130.81, "wind": 0.0}   # C2 and C3: low, but still heard on a laptop
HARMONICS = (1.0, 1.5, 2.0, 2.5, 3.0, 4.0)       # the pad's voices: the harmonics of one note (none of them clash)
SLOW = 3.0           # seconds: how long the sound takes to follow what the machine feels
CAP = 0.5            # the loudest it can be (before the volume)
LAYERS = ("main", "drone", "bells", "reverb")      # what the mixer sets: the ambient itself, a low drone under it,
MIX = {"main": 1.0, "drone": 0.4, "bells": 1.0, "reverb": 0.6}   # the bells of the moments, the room
KEYS = (1.0, 3 / 4, 5 / 6, 9 / 8, 2 / 3, 8 / 9)   # the keys a network may sound in, as ratios of C: C, the G and
                                                 # the A below, D, the F below, the B flat below; low, and in tune
GLIDE = 5.0          # seconds: how long the sound takes to go from one key to the next (it glides, never jumps)
SWELL = 0.1          # Hz: the breath of the sound, and of the waves the picture shows with it (a sea swell, 10 s)


class Reverb:
    """A long, soft room (Schroeder / Freeverb): four damped combs in parallel, two allpasses after them, for each
    side. Its delays are longer than a block, so a block is computed at once from what is past."""

    COMBS = (1557, 1617, 1491, 1422)
    ALLPASSES = (556, 441)

    def __init__(self, room=0.86, damp=0.35, spread=23):
        self.room, self.damp = room, damp
        self.sides = []
        for s in (0, spread):
            combs = [{"d": d + s, "hist": np.zeros(d + s), "zi": np.zeros(1)} for d in self.COMBS]
            alls = [{"d": d + s, "x": np.zeros(d + s), "y": np.zeros(d + s)} for d in self.ALLPASSES]
            self.sides.append((combs, alls))

    def __call__(self, x):
        out = []
        for combs, alls in self.sides:
            acc = np.zeros_like(x)
            n = len(x)
            for c in combs:
                past = c["hist"][:n]                         # what this comb gave d samples ago
                if lfilter is not None:
                    damped, c["zi"] = lfilter([1 - self.damp], [1, -self.damp], past, zi=c["zi"])
                else:  # pragma: no cover
                    damped = past
                y = x + self.room * damped
                c["hist"] = np.concatenate([c["hist"][n:], y])
                acc += y
            y = acc / len(combs)
            for a in alls:
                g = 0.5
                xd, yd = a["x"][:n], a["y"][:n]
                out_a = -g * y + xd + g * yd
                a["x"] = np.concatenate([a["x"][n:], y])
                a["y"] = np.concatenate([a["y"][n:], out_a])
                y = out_a
            out.append(y)
        return np.stack(out, axis=1)


class Ambient:
    """The ambient sound. set(state) from what the machine feels; event() for a moment; render(n) the next n
    samples (stereo); start() / stop() to play it."""

    def __init__(self, kind="pad", volume=0.5, rate=RATE):
        self.rate = rate
        self.kind = kind if kind in KINDS else "pad"
        self.volume = volume
        self.target = {"activity": 0.0, "harmony": 1.0, "pleasure": 0.0, "swell": 0.0, "level": 1.0}
        self.now = dict(self.target, level=0.0)          # it starts in silence and rises (no sudden start)
        self.voices_target = [0.0] * len(HARMONICS)
        self.voices = [0.0] * len(HARMONICS)
        self.detune_target = [0.0] * len(HARMONICS)
        self.detune = [0.0] * len(HARMONICS)
        self.phase = np.zeros(32)
        self.t = 0.0
        self.bells = []                                   # [frequency, age in seconds, loudness]
        self.reverb = Reverb()
        self.lp_zi = np.zeros(1)
        self.noise_zi = np.zeros(1)
        self.band_zi = np.zeros(2)
        self.rng = np.random.default_rng(1)
        self.lock = threading.Lock()
        self.stream = None
        self.mix = dict(MIX)
        self.mix_now = dict(MIX)
        self.key, self.key_now = 1.0, 1.0      # the key it sounds in (a ratio of C): the network looked at

    def set_mix(self, **levels):
        """The mixer: main, drone, bells, reverb, each from 0 to 1 (followed slowly, never at once)."""
        with self.lock:
            for k, v in levels.items():
                if k in self.mix:
                    self.mix[k] = max(0.0, min(1.0, float(v)))

    # ---- what it follows
    def set(self, state):
        """What the machine feels now (senses.Feel.state)."""
        with self.lock:
            self.target["activity"] = float(state.get("activity", 0.0))
            self.target["harmony"] = float(state.get("harmony", 1.0))
            self.target["pleasure"] = float(state.get("pleasure", 0.0))
            self.key = float(state.get("key", self.key))
            voices = state.get("voices") or []
            top = max([v["bits"] for v in voices] + [1e-9])
            for i in range(len(HARMONICS)):
                if i < len(voices):
                    v = voices[i]
                    self.voices_target[i] = 0.25 + 0.75 * min(1.0, max(v["bits"], 0.0) / top)
                    self.detune_target[i] = 0.9 * min(v["strain"], 5.0)        # Hz of beating: its disagreement
                else:
                    self.voices_target[i] = 0.0
                    self.detune_target[i] = 0.0

    def event(self, kind, ratio=1.5):
        """A moment: a discovery rings a soft bell on `ratio` of the note; a surprise swells and settles."""
        with self.lock:
            if kind == "discovery":
                f = (BASE.get(self.kind) or 110.0) * self.key_now
                while f < 330:
                    f *= 2
                self.bells.append([f * ratio, 0.0, 0.5])
            elif kind == "surprise":
                self.target["swell"] = 1.0

    def sea(self):
        """(the time of the sound, how loud it is now, its swell): the picture's waves follow them."""
        return self.t, self.now["level"] * self.volume, self.now["swell"]

    def fade_out(self):
        with self.lock:
            self.target["level"] = 0.0

    # ---- the sound
    def _follow(self, n):
        k = 1.0 - math.exp(-n / (self.rate * SLOW))
        for key in self.now:
            self.now[key] += (self.target[key] - self.now[key]) * k
        self.target["swell"] *= math.exp(-n / (self.rate * 4.0))    # a surprise settles in a few seconds
        self.key_now *= (self.key / self.key_now) ** (1.0 - math.exp(-n / (self.rate * GLIDE)))   # it glides
        quick = 1.0 - math.exp(-n / (self.rate * 0.4))            # the mixer follows the hand in a breath
        for key in self.mix_now:
            self.mix_now[key] += (self.mix[key] - self.mix_now[key]) * quick
        for i in range(len(self.voices)):
            self.voices[i] += (self.voices_target[i] - self.voices[i]) * k
            self.detune[i] += (self.detune_target[i] - self.detune[i]) * k

    def _sines(self, freqs, amps, n, slot):
        """Sum of sines, their phases kept from one block to the next."""
        t = np.arange(1, n + 1) / self.rate
        out = np.zeros(n)
        for j, (f, a) in enumerate(zip(freqs, amps)):
            if a <= 1e-5 or f <= 0:
                continue
            i = slot + j
            ph = self.phase[i] + 2 * math.pi * f * t
            out += a * np.sin(ph)
            self.phase[i] = ph[-1] % (2 * math.pi)
        return out

    def _lowpass(self, x, cutoff, state):
        a = math.exp(-2 * math.pi * cutoff / self.rate)
        if lfilter is None:  # pragma: no cover
            return x, state
        return lfilter([1 - a], [1, -a], x, zi=state)

    def render(self, n=BLOCK):
        """The next n samples, stereo, in [-1, 1]."""
        with self.lock:
            self._follow(n)
            s = dict(self.now)
            voices, detune = list(self.voices), list(self.detune)
            bells = [list(b) for b in self.bells]
            mix = dict(self.mix_now)
            key = self.key_now
        t = self.t + np.arange(n) / self.rate
        breath = 1.0 + 0.22 * np.sin(2 * math.pi * SWELL * t)         # it breathes as the sea does: a swell in 10 s
        bright = 650.0 + 1100.0 * (0.5 + 0.5 * s["pleasure"])           # pleasure opens the harmonics
        x = np.zeros(n)
        if self.kind == "pad":
            f0 = BASE["pad"] * key
            freqs, amps = [], []
            for h, a, d in zip(HARMONICS, voices, detune):
                f = f0 * h
                freqs += [f, f + d + 0.07, 2 * f]                       # a voice, its twin (the beat), its octave
                amps += [0.16 * a, 0.16 * a, 0.035 * a]
            x = self._sines(freqs, amps, n, 0) * breath
            if max(voices + [0.0]) < 0.05:                              # no relation yet: one note, held quietly
                x = self._sines([f0, f0 * 1.5], [0.08, 0.05], n, 20) * breath
        elif self.kind == "engine":
            f0 = BASE["engine"] * key
            rough = (1.0 - s["harmony"]) * 2.5
            pulse = 0.35 + 2.2 * s["activity"]                          # its pulse follows how much it works
            am = 1.0 - (0.18 + 0.25 * s["activity"]) * (0.5 + 0.5 * np.sin(2 * math.pi * pulse * t))
            freqs = [f0 * k for k in range(1, 7)] + [f0 * 2 + rough]
            amps = [0.26 / k ** 0.9 for k in range(1, 7)] + [0.08 * min(1.0, rough)]
            x = self._sines(freqs, amps, n, 0) * am * breath
        else:   # wind
            white = self.rng.standard_normal(n)
            pink, self.noise_zi = self._lowpass(white, 900.0, self.noise_zi)
            centre = (300.0 + 500.0 * (0.5 + 0.5 * math.sin(2 * math.pi * 0.025 * self.t)) + 400.0 * s["activity"]) * key
            if lfilter is not None:
                r = 0.985
                w = 2 * math.pi * centre / self.rate
                b, a = [1 - r, 0, -(1 - r)], [1, -2 * r * math.cos(w), r * r]
                band, self.band_zi = lfilter(b, a, pink, zi=self.band_zi)
            else:  # pragma: no cover
                band = pink
            x = band * (0.9 + 1.6 * s["activity"] + 1.4 * s["swell"]) * breath
        x = x * mix["main"]
        # the drone: a low C with its octave and its fifth, as a tanpura holds it, breathing with the swell
        if mix["drone"] > 1e-3:
            d0 = 65.41 * key
            drone = self._sines([d0, d0 + 0.11, 2 * d0, 3 * d0, 4 * d0 - 0.07],
                                [0.20, 0.12, 0.12, 0.07, 0.04], n, 24)
            x = x + 0.9 * mix["drone"] * drone * (1.0 + 0.15 * np.sin(2 * math.pi * SWELL * t + 1.3))
        # the bells of what it found: a slow attack, a long fall
        for b in bells:
            f, age, loud = b
            ages = age + np.arange(n) / self.rate
            env = loud * np.minimum(1.0, ages / 0.6) * np.exp(-ages / 5.0)
            x += env * (np.sin(2 * math.pi * f * ages) + 0.3 * np.sin(2 * math.pi * 2 * f * ages)) * 0.25 * mix["bells"]
        with self.lock:
            for b in self.bells:
                b[1] += n / self.rate
            self.bells = [b for b in self.bells if b[1] < 20.0]
        x *= 1.0 + 0.5 * s["swell"]
        x, self.lp_zi = self._lowpass(x, bright, self.lp_zi)          # nothing sharp
        wet = self.reverb(x)
        y = 0.55 * np.stack([x, x], axis=1) + 1.25 * mix["reverb"] * wet
        y = np.tanh(y * 1.2) * CAP * self.volume * s["level"]         # never louder than the cap
        self.t += n / self.rate
        return y.astype(np.float32)

    # ---- playing it
    def start(self):
        """Plays it (sounddevice). Returns None, or why it cannot."""
        try:
            import sounddevice as sd
        except (ImportError, OSError) as e:
            return str(e) or type(e).__name__

        def callback(outdata, frames, _time, _status):
            outdata[:] = self.render(frames)
        try:
            self.stream = sd.OutputStream(samplerate=self.rate, channels=2, blocksize=BLOCK, dtype="float32",
                                          callback=callback)
            self.stream.start()
        except Exception as e:  # noqa: BLE001 - no device, a busy device: said, not a crash
            self.stream = None
            return str(e)
        return None

    def stop(self):
        if self.stream is not None:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:  # noqa: BLE001
                pass
            self.stream = None

    def save(self, path, seconds=30.0, states=None):
        """The same sound in a WAV file. states: [(at seconds, state, event or None)] to play a little story."""
        n = int(seconds * self.rate)
        chunks, done = [], 0
        story = sorted(states or [], key=lambda s: s[0])
        while done < n:
            while story and story[0][0] * self.rate <= done:
                _, st, ev = story.pop(0)
                if st:
                    self.set(st)
                if ev:
                    self.event(*ev)
            k = min(BLOCK, n - done)
            chunks.append(self.render(k))
            done += k
        y = np.concatenate(chunks)
        pcm = (np.clip(y, -1, 1) * 32767).astype("<i2")
        with wave.open(path, "wb") as w:
            w.setnchannels(2)
            w.setsampwidth(2)
            w.setframerate(self.rate)
            w.writeframes(pcm.tobytes())
        return y
