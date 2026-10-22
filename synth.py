"""Tiny pure-Python synthesizer used to generate demo audio for FL HUB.

It is intentionally simple: wavetable oscillators, synthetic drums and a few
arrangement helpers. No third-party packages required.
"""
from __future__ import annotations

import math
import random
import wave
from array import array
from pathlib import Path

SR = 22050
TABLE_SIZE = 4096
TAU = math.tau

NOTE_OFFSETS = {
    "C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5,
    "F#": 6, "Gb": 6, "G": 7, "G#": 8, "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11,
}


def note_number(name: str) -> int:
    if name[-1].isdigit():
        octave = int(name[-1])
        pitch = name[:-1]
    else:
        octave = int(name[-2:])
        pitch = name[:-2]
    return 12 * (octave + 1) + NOTE_OFFSETS[pitch]


def freq(name: str) -> float:
    return 440.0 * (2.0 ** ((note_number(name) - 69) / 12.0))


def _make_table(kind: str) -> list[float]:
    table = [0.0] * (TABLE_SIZE + 1)
    for i in range(TABLE_SIZE + 1):
        x = TAU * i / TABLE_SIZE
        if kind == "sine":
            value = math.sin(x)
        elif kind == "saw":
            value = sum(math.sin(x * k) / k for k in range(1, 15)) * 0.55
        elif kind == "saw_soft":
            value = sum(math.sin(x * k) / (k * k) for k in range(1, 9)) * 1.15
        elif kind == "square":
            value = sum(math.sin(x * k) / k for k in range(1, 16, 2)) * 0.8
        elif kind == "triangle":
            value = sum(((-1) ** ((k - 1) // 2)) * math.sin(x * k) / (k * k)
                        for k in range(1, 16, 2)) * 1.1
        elif kind == "rhodes":
            value = math.sin(x) + 0.34 * math.sin(2 * x) + 0.13 * math.sin(3 * x) + 0.05 * math.sin(5 * x)
        elif kind == "organ":
            value = math.sin(x) + 0.45 * math.sin(2 * x) + 0.2 * math.sin(4 * x) + 0.1 * math.sin(6 * x)
        else:
            value = math.sin(x)
        table[i] = value
    peak = max(abs(v) for v in table) or 1.0
    return [v / peak for v in table]


TABLES = {name: _make_table(name) for name in
          ("sine", "saw", "saw_soft", "square", "triangle", "rhodes", "organ")}


def silence(seconds: float) -> list[float]:
    return [0.0] * int(seconds * SR)


def place(buf: list[float], sound: list[float], at_sec: float, gain: float = 1.0) -> None:
    start = int(at_sec * SR)
    if start < 0 or start >= len(buf):
        return
    limit = min(len(sound), len(buf) - start)
    for i in range(limit):
        buf[start + i] += sound[i] * gain


def osc(table: str, f: float, dur: float, amp: float = 0.5, attack: float = 0.005,
        decay: float = 0.0, sustain: float = 1.0, release: float = 0.08,
        detune: float = 0.0, vibrato: float = 0.0) -> list[float]:
    """Render one note with a simple envelope and optional detuned voice."""
    n = max(1, int(dur * SR))
    out = [0.0] * n
    wave_table = TABLES[table]
    attack_n = max(1, int(attack * SR))
    release_n = max(1, min(int(release * SR), n // 2 or 1))
    decay_n = int(decay * SR) if decay else 0
    step = f / SR
    step2 = step * (1.0 + detune) if detune else 0.0
    phase = 0.0
    phase2 = 0.5
    vib_depth = vibrato / SR
    for i in range(n):
        env = 1.0
        if i < attack_n:
            env = i / attack_n
        if decay_n:
            if i < attack_n + decay_n:
                env *= sustain + (1.0 - sustain) * (1.0 - (i - attack_n) / decay_n)
            else:
                env *= sustain
        if i >= n - release_n:
            env *= (n - i) / release_n
        if vib_depth:
            step_now = step * (1.0 + vib_depth * math.sin(TAU * 5.0 * i / SR))
        else:
            step_now = step
        phase += step_now
        if phase >= 1.0:
            phase -= 1.0
        idx = phase * TABLE_SIZE
        i0 = int(idx)
        frac = idx - i0
        sample = wave_table[i0] * (1.0 - frac) + wave_table[i0 + 1] * frac
        if detune:
            phase2 += step2
            if phase2 >= 1.0:
                phase2 -= 1.0
            idx2 = phase2 * TABLE_SIZE
            i2 = int(idx2)
            frac2 = idx2 - i2
            sample = 0.58 * sample + 0.42 * (
                wave_table[i2] * (1.0 - frac2) + wave_table[i2 + 1] * frac2
            )
        out[i] = sample * env * amp
    return out


def synth_808(f: float, dur: float, amp: float = 0.7) -> list[float]:
    n = int(dur * SR)
    out = [0.0] * n
    phase = 0.0
    for i in range(n):
        t = i / SR
        pitch = f * (1.0 + 1.5 * math.exp(-t * 32.0))
        phase += TAU * pitch / SR
        env = math.exp(-t * 2.2) * (1.0 - math.exp(-t * 320.0))
        out[i] = math.tanh(1.9 * math.sin(phase) * env) * amp
    return out


def kick(amp: float = 0.85) -> list[float]:
    n = int(0.42 * SR)
    out = [0.0] * n
    phase = 0.0
    for i in range(n):
        t = i / SR
        pitch = 44.0 + 110.0 * math.exp(-t * 28.0)
        phase += TAU * pitch / SR
        env = math.exp(-t * 8.5)
        out[i] = math.sin(phase) * env * amp
        if t < 0.012:
            out[i] += (random.random() * 2 - 1) * 0.2 * (1 - t / 0.012)
    return out


def snare(amp: float = 0.55, seed: int = 3) -> list[float]:
    rnd = random.Random(seed)
    n = int(0.24 * SR)
    out = [0.0] * n
    prev = 0.0
    for i in range(n):
        t = i / SR
        noise = rnd.uniform(-1, 1)
        bright = noise - prev * 0.75
        prev = noise
        tone = math.sin(TAU * 186.0 * t) * 0.42
        out[i] = (bright * 0.55 + tone) * math.exp(-t * 17.0) * amp
    return out


def hat(open_hat: bool = False, amp: float = 0.24, seed: int = 7) -> list[float]:
    rnd = random.Random(seed)
    dur = 0.34 if open_hat else 0.075
    n = int(dur * SR)
    out = [0.0] * n
    prev = 0.0
    decay = 10.0 if open_hat else 55.0
    for i in range(n):
        t = i / SR
        noise = rnd.uniform(-1, 1)
        bright = noise - prev * 0.9
        prev = noise
        out[i] = bright * math.exp(-t * decay) * amp
    return out


def clap(amp: float = 0.4, seed: int = 11) -> list[float]:
    rnd = random.Random(seed)
    n = int(0.3 * SR)
    out = [0.0] * n
    prev = 0.0
    for i in range(n):
        t = i / SR
        noise = rnd.uniform(-1, 1)
        bright = noise - prev * 0.82
        prev = noise
        env = math.exp(-t * 12.0)
        for offset in (0.0, 0.011, 0.022, 0.033):
            if offset <= t < offset + 0.012:
                env += 0.9 * math.exp(-(t - offset) * 90.0)
        out[i] = bright * env * amp * 0.5
    return out


def crash(amp: float = 0.32, seed: int = 21) -> list[float]:
    rnd = random.Random(seed)
    n = int(1.4 * SR)
    out = [0.0] * n
    prev = 0.0
    for i in range(n):
        t = i / SR
        noise = rnd.uniform(-1, 1)
        bright = noise - prev * 0.6
        prev = noise
        out[i] = bright * math.exp(-t * 3.4) * amp
    return out


def cowbell(f: float = 540.0, amp: float = 0.28) -> list[float]:
    n = int(0.28 * SR)
    out = [0.0] * n
    for i in range(n):
        t = i / SR
        env = math.exp(-t * 15.0)
        value = math.sin(TAU * f * t) + 0.7 * math.sin(TAU * f * 1.48 * t)
        out[i] = math.tanh(value * 1.3) * env * amp
    return out


def rim(amp: float = 0.25) -> list[float]:
    n = int(0.08 * SR)
    out = [0.0] * n
    for i in range(n):
        t = i / SR
        out[i] = (math.sin(TAU * 1720 * t) * 0.6 + math.sin(TAU * 830 * t) * 0.4) * math.exp(-t * 55) * amp
    return out


def vinyl(duration: float, amp: float = 0.014, seed: int = 5) -> list[float]:
    rnd = random.Random(seed)
    n = int(duration * SR)
    out = [0.0] * n
    prev = 0.0
    for i in range(n):
        noise = rnd.uniform(-1, 1)
        bright = noise - prev * 0.86
        prev = noise
        out[i] = bright * amp
    for _ in range(int(duration * 6)):
        pos = rnd.randrange(max(1, n - 200))
        length = rnd.randint(40, 150)
        for j in range(length):
            if pos + j < n:
                out[pos + j] += rnd.uniform(-1, 1) * amp * 5 * math.exp(-j / (length / 3))
    return out


def add_swing(step: int, swing: float) -> float:
    return swing if step % 2 else 0.0


def normalize(buf: list[float], peak: float = 0.88) -> None:
    loudest = max((abs(v) for v in buf), default=0.0)
    if loudest <= 0:
        return
    scale = peak / loudest
    for i in range(len(buf)):
        buf[i] *= scale


def fade_edges(buf: list[float], seconds: float = 0.06) -> None:
    n = min(len(buf), int(seconds * SR))
    for i in range(n):
        buf[i] *= i / n
        buf[-1 - i] *= i / n


def write_wav(path: Path, buf: list[float]) -> None:
    fade_edges(buf)
    normalize(buf)
    data = array("h", (int(max(-1.0, min(1.0, v)) * 32767) for v in buf))
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(SR)
        handle.writeframes(data.tobytes())


def _bar_len(bpm: float) -> float:
    return 60.0 / bpm * 4.0


def _step_len(bpm: float) -> float:
    return 60.0 / bpm / 4.0


# ---------------------------------------------------------------------------
# Demo tracks
# ---------------------------------------------------------------------------

def render_neon_rain() -> tuple[list[float], float]:
    bpm = 140.0
    bars = 12
    bar = _bar_len(bpm)
    step = _step_len(bpm)
    buf = silence(bar * bars + 1.0)
    chords = [["A2", "C3", "E3"], ["F2", "A2", "C3"], ["C3", "E3", "G3"], ["G2", "B2", "D3"]]
    arp_notes = ["A4", "C5", "E5", "G5", "E5", "C5", "B4", "G4"]
    rnd = random.Random(41)

    place(buf, vinyl(bar * bars + 1.0, 0.01, 8), 0)

    for b in range(bars):
        chord = chords[b % 4]
        root = chord[0]
        # atmospheric pad
        for name in chord:
            place(buf, osc("saw_soft", freq(name), bar * 1.02, 0.075, attack=0.35,
                           release=0.5, detune=0.006), b * bar)
        if b < 2:
            continue
        # 808 line
        for s, length, amp in [(0, 0.55, 0.85), (6, 0.3, 0.5), (10, 0.45, 0.7), (14, 0.25, 0.35)]:
            place(buf, synth_808(freq(root) / 2, length * bar, amp), b * bar + s * step)
        # drums
        place(buf, kick(0.9), b * bar)
        place(buf, kick(0.7), b * bar + 10 * step)
        place(buf, snare(0.6, seed=b + 3), b * bar + 8 * step)
        place(buf, clap(0.32, seed=b + 9), b * bar + 8 * step)
        for s in range(0, 16, 2):
            amp = 0.23 if s % 4 == 0 else 0.14
            place(buf, hat(False, amp, seed=b * 16 + s), b * bar + s * step)
        if b % 4 == 3:
            for s in range(12, 16):
                place(buf, hat(False, 0.12, seed=b * 31 + s), b * bar + s * step)
            place(buf, hat(True, 0.18, seed=b), b * bar + 14 * step)
        # eerie arp with delay
        if b >= 4:
            for s in (2, 5, 9, 12):
                name = arp_notes[(b * 4 + s) % len(arp_notes)]
                sound = osc("triangle", freq(name), 0.45, 0.1, attack=0.004, decay=0.4, sustain=0.0)
                place(buf, sound, b * bar + s * step)
                place(buf, sound, b * bar + s * step + 0.32, 0.22)
        if b in (4, 8):
            place(buf, crash(0.2, seed=b), b * bar)
        if b == 2:
            place(buf, crash(0.18, seed=99), b * bar)
        # subtle rim ghost
        if rnd.random() < 0.4:
            place(buf, rim(0.14), b * bar + 15 * step)

    return buf, bpm


def render_midnight() -> tuple[list[float], float]:
    bpm = 82.0
    bars = 8
    bar = _bar_len(bpm)
    step = _step_len(bpm)
    swing = 0.035
    buf = silence(bar * bars + 1.2)
    chords = [
        ["D3", "F3", "A3", "C4", "E4"],
        ["Bb2", "D3", "F3", "A3"],
        ["G2", "Bb2", "D3", "F3"],
        ["A2", "C#3", "E3", "G3"],
    ]
    melody = ["D5", "F5", "E5", "C5", "A4", "C5", "D5", "F5"]
    rnd = random.Random(82)

    place(buf, vinyl(bar * bars + 1.2, 0.02, 12), 0)

    for b in range(bars):
        chord = chords[b % 4]
        for name in chord:
            place(buf, osc("rhodes", freq(name), bar * 0.98, 0.07, attack=0.02,
                           decay=1.4, sustain=0.25, release=0.6, detune=0.003), b * bar)
        place(buf, osc("triangle", freq(chord[0]) / 2, bar * 1.05, 0.05,
                       attack=0.4, release=0.7), b * bar)
        # bass
        for s, length, amp in [(0, 0.9, 0.34), (10, 0.5, 0.24)]:
            place(buf, osc("sine", freq(chord[0]) / 2, length * bar, amp,
                           attack=0.02, decay=0.8, sustain=0.3, release=0.2), b * bar + s * step)
        # drums
        place(buf, kick(0.62), b * bar)
        place(buf, kick(0.45), b * bar + 10 * step)
        place(buf, snare(0.38, seed=b + 2), b * bar + 4 * step)
        place(buf, snare(0.42, seed=b + 5), b * bar + 12 * step)
        for s in range(0, 16, 2):
            offset = add_swing(s // 2, swing)
            amp = 0.12 if s % 4 == 0 else 0.07
            place(buf, hat(False, amp, seed=b * 16 + s), b * bar + s * step + offset)
        if b % 2 == 1:
            place(buf, hat(True, 0.09, seed=b + 7), b * bar + 14 * step + swing)
        # lazy keys melody
        for s in (3, 7, 11):
            if rnd.random() < 0.8:
                name = melody[(b * 3 + s) % len(melody)]
                place(buf, osc("rhodes", freq(name), 0.7, 0.055, attack=0.01,
                               decay=0.7, sustain=0.05, release=0.2),
                      b * bar + s * step + swing)
        if b in (0, 4):
            place(buf, crash(0.1, seed=b + 31), b * bar)

    return buf, bpm


def render_deep_signal() -> tuple[list[float], float]:
    bpm = 124.0
    bars = 12
    bar = _bar_len(bpm)
    step = _step_len(bpm)
    buf = silence(bar * bars + 1.0)
    chords = [
        ["F#3", "A3", "C#4"],
        ["D3", "F#3", "A3"],
        ["A3", "C#4", "E4"],
        ["E3", "G#3", "B3"],
    ]

    for b in range(bars):
        chord = chords[b % 4]
        root = chord[0]
        # four on the floor
        for beat in range(4):
            place(buf, kick(0.72), b * bar + beat * 4 * step)
        # clap on 2 and 4
        place(buf, clap(0.26, seed=b + 4), b * bar + 4 * step)
        place(buf, clap(0.26, seed=b + 8), b * bar + 12 * step)
        # hats
        for s in range(0, 16, 2):
            place(buf, hat(False, 0.12 if s % 4 else 0.2, seed=b * 16 + s),
                  b * bar + s * step)
        for s in (2, 6, 10, 14):
            place(buf, hat(True, 0.12, seed=b * 16 + s), b * bar + s * step)
        # offbeat bass
        if b >= 1:
            for s in (2, 6, 10, 14):
                place(buf, osc("saw_soft", freq(root) / 2, 0.16, 0.26, attack=0.005,
                               decay=0.18, sustain=0.0, release=0.04),
                      b * bar + s * step)
        # chord stabs
        if b >= 2:
            for s in (3, 11):
                for name in chord:
                    place(buf, osc("saw_soft", freq(name), 0.2, 0.06, attack=0.004,
                                   decay=0.16, sustain=0.0, release=0.05),
                          b * bar + s * step)
        # pad
        if b >= 2:
            for name in chord:
                place(buf, osc("saw_soft", freq(name), bar * 1.02, 0.045, attack=0.5,
                               release=0.6, detune=0.005), b * bar)
        if b in (4, 8):
            place(buf, crash(0.22, seed=b + 17), b * bar)
        if b == 6:
            for s in range(8, 16):
                place(buf, snare(0.18, seed=b + s), b * bar + s * step)

    return buf, bpm


def render_fracture() -> tuple[list[float], float]:
    bpm = 174.0
    bars = 16
    bar = _bar_len(bpm)
    step = _step_len(bpm)
    buf = silence(bar * bars + 1.0)
    roots = ["G1", "G1", "Bb1", "Bb1", "F1", "F1", "Eb1", "Eb1"]
    chords = [
        ["G3", "Bb3", "D4"],
        ["G3", "Bb3", "D4"],
        ["Bb3", "D4", "F4"],
        ["Bb3", "D4", "F4"],
        ["F3", "A3", "C4"],
        ["F3", "A3", "C4"],
        ["Eb3", "G3", "Bb3"],
        ["Eb3", "G3", "Bb3"],
    ]

    place(buf, vinyl(bar * bars + 1.0, 0.008, 33), 0)

    for b in range(bars):
        root = roots[b % 8]
        chord = chords[b % 8]
        # reese bass
        place(buf, osc("saw", freq(root), bar * 1.0, 0.16, attack=0.02,
                       release=0.15, detune=0.012), b * bar)
        place(buf, osc("sine", freq(root), bar * 1.0, 0.12, attack=0.01,
                       release=0.2), b * bar)
        # atmospheric chords every other bar
        if b % 2 == 0:
            for name in chord:
                place(buf, osc("saw_soft", freq(name), bar * 2.0, 0.035, attack=0.9,
                               release=1.0, detune=0.007), b * bar)
        # breakbeat
        place(buf, kick(0.78), b * bar)
        place(buf, kick(0.55), b * bar + 10 * step)
        place(buf, snare(0.5, seed=b + 3), b * bar + 4 * step)
        place(buf, snare(0.52, seed=b + 7), b * bar + 12 * step)
        place(buf, snare(0.18, seed=b + 11), b * bar + 7 * step)
        place(buf, snare(0.16, seed=b + 13), b * bar + 15 * step)
        for s in range(0, 16):
            amp = 0.1 if s % 2 == 0 else 0.05
            place(buf, hat(False, amp, seed=b * 16 + s), b * bar + s * step)
        place(buf, hat(True, 0.14, seed=b + 19), b * bar + 14 * step)
        if b % 8 == 0:
            place(buf, crash(0.22, seed=b + 23), b * bar)
        if b % 8 == 7:
            for s in range(8, 16):
                place(buf, snare(0.12 + s * 0.008, seed=b * 10 + s), b * bar + s * step)

    return buf, bpm


def render_concrete_morning() -> tuple[list[float], float]:
    bpm = 132.0
    bars = 12
    bar = _bar_len(bpm)
    step = _step_len(bpm)
    buf = silence(bar * bars + 1.0)
    chords = [
        ["C#3", "E3", "G#3"],
        ["A2", "C#3", "E3"],
        ["E3", "G#3", "B3"],
        ["B2", "D#3", "F#3"],
    ]
    bells = ["C#5", "E5", "G#5", "B5", "G#5", "E5", "F#5", "G#5"]
    rnd = random.Random(132)

    place(buf, vinyl(bar * bars + 1.0, 0.018, 66), 0)

    for b in range(bars):
        chord = chords[b % 4]
        root = chord[0]
        for name in chord:
            place(buf, osc("saw_soft", freq(name), bar * 1.02, 0.06, attack=0.25,
                           release=0.5, detune=0.004), b * bar)
        # 808 with slides
        for s, length, amp in [(0, 0.6, 0.8), (7, 0.3, 0.45), (10, 0.5, 0.65)]:
            place(buf, synth_808(freq(root) / 2, length * bar, amp), b * bar + s * step)
        # drums
        place(buf, kick(0.8), b * bar)
        place(buf, kick(0.6), b * bar + 3 * step)
        place(buf, kick(0.7), b * bar + 8 * step)
        place(buf, snare(0.5, seed=b + 2), b * bar + 4 * step)
        place(buf, snare(0.5, seed=b + 6), b * bar + 12 * step)
        for s in range(0, 16, 2):
            place(buf, hat(False, 0.16 if s % 4 == 0 else 0.09, seed=b * 16 + s),
                  b * bar + s * step)
        if b % 2 == 1:
            for s in (13, 14, 15):
                place(buf, hat(False, 0.09, seed=b * 19 + s), b * bar + s * step)
            place(buf, hat(True, 0.12, seed=b + 5), b * bar + 14 * step)
        # cowbell melody
        if b >= 2:
            for s in (0, 2, 5, 8, 10, 13):
                if rnd.random() < 0.85:
                    name = bells[(b * 3 + s) % len(bells)]
                    sound = cowbell(freq(name), 0.16)
                    place(buf, sound, b * bar + s * step)
                    place(buf, sound, b * bar + s * step + 0.22, 0.2)
        if b in (0, 4, 8):
            place(buf, crash(0.16, seed=b + 44), b * bar)
        if rnd.random() < 0.5:
            place(buf, rim(0.12), b * bar + 11 * step)

    return buf, bpm


TRACKS = {
    "neon_rain": render_neon_rain,
    "midnight": render_midnight,
    "deep_signal": render_deep_signal,
    "fracture": render_fracture,
    "concrete_morning": render_concrete_morning,
}


def render_track(key: str) -> tuple[list[float], float]:
    return TRACKS[key]()


def render_loop(kind: str, bpm: float, bars: int, root: str = "A2") -> tuple[list[float], float]:
    """Small loop used inside demo packs and stems."""
    bar = _bar_len(bpm)
    step = _step_len(bpm)
    buf = silence(bar * bars + 0.4)
    if kind == "drums":
        for b in range(bars):
            place(buf, kick(0.8), b * bar)
            place(buf, kick(0.55), b * bar + 10 * step)
            place(buf, snare(0.45, seed=b), b * bar + 4 * step)
            place(buf, snare(0.48, seed=b + 3), b * bar + 12 * step)
            for s in range(0, 16, 2):
                place(buf, hat(False, 0.15 if s % 4 == 0 else 0.08, seed=b * 16 + s),
                      b * bar + s * step)
            place(buf, hat(True, 0.1, seed=b + 8), b * bar + 14 * step)
    elif kind == "bass":
        for b in range(bars):
            place(buf, synth_808(freq(root) / 2, bar * 0.55, 0.8), b * bar)
            place(buf, synth_808(freq(root) / 2, bar * 0.3, 0.45), b * bar + 10 * step)
    elif kind == "keys":
        chord = [root, _transpose(root, 3), _transpose(root, 7), _transpose(root, 10)]
        for b in range(bars):
            for name in chord:
                place(buf, osc("rhodes", freq(name), bar * 0.95, 0.08, attack=0.02,
                               decay=1.0, sustain=0.2, release=0.5), b * bar)
    elif kind == "melody":
        scale = [root, _transpose(root, 3), _transpose(root, 7), _transpose(root, 10),
                 _transpose(root, 12), _transpose(root, 15)]
        for b in range(bars):
            for i, s in enumerate((0, 3, 6, 10, 12, 14)):
                name = scale[(b * 2 + i) % len(scale)]
                place(buf, osc("triangle", freq(name), 0.4, 0.12, attack=0.005,
                               decay=0.35, sustain=0.0), b * bar + s * step)
    return buf, bpm


def _transpose(name: str, semitones: int) -> str:
    number = note_number(name) + semitones
    names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    return f"{names[number % 12]}{number // 12 - 1}"


def drum_one_shots() -> dict[str, list[float]]:
    return {
        "kick": kick(0.95),
        "snare": snare(0.7, seed=101),
        "clap": clap(0.65, seed=102),
        "closed_hat": hat(False, 0.35, seed=103),
        "open_hat": hat(True, 0.32, seed=104),
        "808": synth_808(freq("A1"), 1.4, 0.9),
        "rim": rim(0.5),
        "cowbell": cowbell(freq("C5"), 0.45),
        "crash": crash(0.5, seed=105),
    }
