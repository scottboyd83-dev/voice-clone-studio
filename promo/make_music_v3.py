"""Promo bed v3 — warm, Apple-promo-style: soft electric-piano chords rolled
on each scene change, a sparse rising melody, warm sub bass and pad, light
room reverb, and no drums. Same 120 BPM grid as v2 so every event still
lands on a beat and chord changes sit exactly on the scene cuts.
Run: uv run python promo/make_music_v3.py  (from the repo root)
"""

import numpy as np
import soundfile as sf
from scipy.signal import butter, fftconvolve, sosfilt

SR = 48000
DUR = 42.0
CUTS = [4.5, 10.0, 16.0, 23.0, 30.0, 36.0]  # scene boundaries (s)

t = np.arange(int(DUR * SR)) / SR
N = len(t)
rng = np.random.default_rng(3)


def place(buf, sig, at):
    i = int(at * SR)
    j = min(i + len(sig), N)
    if i < N:
        buf[i:j] += sig[: j - i]


def lowpass(x, hz, order=4):
    sos = butter(order, hz / (SR / 2), "low", output="sos")
    return sosfilt(sos, x)


# Soft EP/felt-piano tone: gentle attack, long decay, warm harmonics, tremolo.
def ep_note(freq, dur=2.6, vel=1.0):
    n = int(dur * SR)
    x = np.arange(n) / SR
    env = np.minimum(x / 0.02, 1) * np.exp(-x / 0.9)
    trem = 1 + 0.06 * np.sin(2 * np.pi * 3.8 * x)
    sig = (
        np.sin(2 * np.pi * freq * x)
        + 0.38 * np.sin(2 * np.pi * 2 * freq * x)
        + 0.10 * np.sin(2 * np.pi * 3 * freq * x)
    )
    return sig * env * trem * vel


# ---- harmony: one chord per scene, diatonic C major (same plan as v2) ----
# (bass root, chord voicing for the EP, melody notes octave(s) up)
SCENES_CHORDS = [
    (65.41, [130.81, 196.0, 261.63, 329.63], [523.25, 659.26]),          # C
    (98.0,  [123.47, 196.0, 246.94, 293.66], [587.33, 783.99]),          # G
    (110.0, [110.0, 164.81, 220.0, 261.63], [659.26, 880.0]),            # Am
    (87.31, [87.31, 174.61, 220.0, 261.63], [698.46, 880.0]),            # F
    (65.41, [130.81, 196.0, 329.63, 392.0], [783.99, 1046.5]),           # C lifted
    (87.31, [87.31, 174.61, 261.63, 349.23], [698.46, 523.25]),          # F
    (65.41, [65.41, 130.81, 196.0, 261.63], [523.25, 1046.5]),           # C home
]
bounds = [0.0] + CUTS + [DUR]

# ---- EP chords: rolled on each scene start, re-struck softly every 2 bars ----
ep = np.zeros(N)
for k, (_, voicing, _) in enumerate(SCENES_CHORDS):
    s, e = bounds[k], bounds[k + 1]
    for strike, vel in [(s, 1.0), (s + 4.0, 0.55)]:
        if strike >= e - 0.5 or strike >= 38.0:
            continue
        for ni, f in enumerate(voicing):
            place(ep, ep_note(f, dur=3.2, vel=vel * 0.22), strike + ni * 0.045)

# ---- melody: two sparse notes per scene, rising across the film ----
mel = np.zeros(N)
for k, (_, _, notes) in enumerate(SCENES_CHORDS):
    s, e = bounds[k], bounds[k + 1]
    span = e - s
    for ni, f in enumerate(notes):
        at = s + span * (0.35 + 0.35 * ni)
        at = round(at * 2) / 2  # snap to the 120 BPM beat grid
        if at < e - 0.4 and at < 39.5:
            place(mel, ep_note(f, dur=2.4, vel=0.16), at)

# ---- bass: warm sustained roots, hard boundaries on the cuts ----
bass = np.zeros(N)
for k, (root, _, _) in enumerate(SCENES_CHORDS):
    s, e = bounds[k], bounds[k + 1]
    n = int((e - s) * SR)
    x = np.arange(n) / SR
    env = np.minimum(x / 0.5, 1) * np.clip(((e - s) - x) / 0.5, 0, 1)
    sig = np.sin(2 * np.pi * (root / 2) * x) + 0.35 * np.sin(2 * np.pi * root * x)
    place(bass, sig * env * 0.26, s)

# ---- pad: airy and far back ----
pad = np.zeros(N)
for k, (_, voicing, _) in enumerate(SCENES_CHORDS):
    s, e = bounds[k], bounds[k + 1]
    n = int((e - s) * SR)
    x = np.arange(n) / SR
    env = np.minimum(x / 1.2, 1) * np.clip(((e - s) - x) / 0.8, 0, 1)
    sig = np.zeros(n)
    for f in voicing[1:]:
        ph = rng.uniform(0, 2 * np.pi)
        sig += np.sin(2 * np.pi * f * x + ph)
    place(pad, sig * env * 0.05, s)
pad = lowpass(pad, 1200)

# ---- cut accents: a single soft low octave note, no booms, no noise ----
acc = np.zeros(N)
for k, c in enumerate(CUTS):
    root = SCENES_CHORDS[k + 1][0]
    place(acc, ep_note(root, dur=2.8, vel=0.3), c)

# ---- mix, light room reverb, master envelope ----
dry = ep + mel + bass + pad + acc
ir_len = int(0.8 * SR)
ir = lowpass(rng.standard_normal(ir_len), 2800) * np.exp(-np.arange(ir_len) / SR / 0.35)
ir /= np.abs(ir).sum() * 0.02
wet = fftconvolve(dry, ir)[:N] * 0.22
mix = dry + wet

master = np.clip(t / 1.2, 0, 1) * np.clip((41.4 - t) / 2.8, 0, 1)
mix *= np.clip(master, 0, 1)
mix = np.tanh(mix * 1.2) * 0.7

delay = int(0.009 * SR)
side = np.zeros(N)
side[delay:] = mix[:-delay]
left = mix + 0.15 * side
right = mix - 0.15 * side
peak = max(np.abs(left).max(), np.abs(right).max())
stereo = np.stack([left, right], axis=1) / peak * 0.8

sf.write("promo/public/music_v3.wav", stereo.astype(np.float32), SR)
print(f"wrote promo/public/music_v3.wav — {DUR}s, peak {np.abs(stereo).max():.2f}")
