"""Synthesize the promo's minimal dark-electronic bed (42s, 48kHz stereo).
Accents land on the scene cuts defined in src/timeline.js — keep in sync.
Run: uv run python promo/make_music.py  (from the repo root; needs numpy/scipy/soundfile)
"""

import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfilt

SR = 48000
DUR = 42.0
CUTS = [4.5, 10.0, 16.0, 23.0, 30.0, 36.0]  # scene boundaries (s)
BEAT = 60 / 96  # 96 BPM

t = np.arange(int(DUR * SR)) / SR
N = len(t)
rng = np.random.default_rng(7)


def env_exp(length, decay):
    x = np.arange(length) / SR
    return np.exp(-x / decay)


def place(buf, sig, at):
    i = int(at * SR)
    j = min(i + len(sig), N)
    if i < N:
        buf[i:j] += sig[: j - i]


def lowpass(x, hz, order=4):
    sos = butter(order, hz / (SR / 2), "low", output="sos")
    return sosfilt(sos, x)


def highpass(x, hz, order=4):
    sos = butter(order, hz / (SR / 2), "high", output="sos")
    return sosfilt(sos, x)


# ---- sub pulse: soft 50Hz thump on each beat, sidechain-style gap feel ----
pulse = np.zeros(N)
thump_len = int(0.5 * SR)
x = np.arange(thump_len) / SR
freq_sweep = 78 * np.exp(-x / 0.05) + 48
thump = np.sin(2 * np.pi * np.cumsum(freq_sweep) / SR) * env_exp(thump_len, 0.16)
beats = np.arange(0, DUR, BEAT)
for b in beats:
    if b < 36.0:  # pulse drops out for the outro
        place(pulse, thump * 0.9, b)

# ---- pad: slow detuned saw-ish chords, one per scene, dark and low ----
# A minor-flavored progression; voiced low (Hz)
CHORDS = [
    [55.0, 82.41, 110.0],            # intro      A1 E2 A2
    [55.0, 65.41, 98.0],             # clone      A1 C2 G2
    [43.65, 65.41, 87.31],           # generate   F1 C2 F2
    [49.0, 73.42, 98.0],             # train      G1 D2 G2
    [55.0, 82.41, 130.81],           # convert    A1 E2 C3
    [43.65, 65.41, 110.0],           # privacy    F1 C2 A2
    [55.0, 82.41, 110.0],            # outro      A1 E2 A2
]
bounds = [0.0] + CUTS + [DUR]
pad = np.zeros(N)
for k, chord in enumerate(CHORDS):
    s, e = bounds[k], bounds[k + 1]
    seg_len = int((e - s + 1.5) * SR)  # overlap into next scene for legato
    seg_t = np.arange(seg_len) / SR
    seg = np.zeros(seg_len)
    for f in chord:
        for det in (-0.7, 0.0, 0.7):  # gentle detune
            ph = rng.uniform(0, 2 * np.pi)
            seg += np.sin(2 * np.pi * (f + det) * seg_t + ph)
            seg += 0.35 * np.sin(2 * np.pi * 2 * (f + det) * seg_t + ph)  # octave shimmer
    att = np.clip(seg_t / 1.8, 0, 1) ** 2
    rel = np.clip((seg_len / SR - seg_t) / 1.5, 0, 1)
    place(pad, seg * att * rel / (len(chord) * 6), s)
pad = lowpass(pad, 900)

# ---- hats: tiny filtered-noise ticks on 8ths, only mid-section ----
hats = np.zeros(N)
tick_len = int(0.05 * SR)
for b in np.arange(10.0, 30.0, BEAT / 2):
    tick = highpass(rng.standard_normal(tick_len), 8000) * env_exp(tick_len, 0.012)
    place(hats, tick * 0.12, b + BEAT / 2 * 0.0)

# ---- scene accents: airy riser into each cut + soft boom on it ----
acc = np.zeros(N)
for c in CUTS:
    rise_len = int(1.0 * SR)
    noise = highpass(rng.standard_normal(rise_len), 2000)
    riser = noise * (np.arange(rise_len) / rise_len) ** 3 * 0.10
    place(acc, riser, c - 1.0)
    boom_len = int(1.2 * SR)
    bx = np.arange(boom_len) / SR
    bf = 110 * np.exp(-bx / 0.09) + 40
    boom = np.sin(2 * np.pi * np.cumsum(bf) / SR) * env_exp(boom_len, 0.35) * 0.5
    place(acc, boom, c)

# ---- mix, master envelope, stereo width ----
mix = pulse * 0.55 + pad * 0.8 + hats + acc
master = np.clip(t / 1.2, 0, 1) * np.clip((41.6 - t) / 2.2, 0, 1)
mix *= np.clip(master, 0, 1)
mix = np.tanh(mix * 1.4) * 0.7  # gentle saturation + headroom

# cheap width: slightly delayed/filtered side signal
delay = int(0.012 * SR)
side = np.zeros(N)
side[delay:] = mix[:-delay]
left = mix + 0.18 * side
right = mix - 0.18 * side
peak = max(np.abs(left).max(), np.abs(right).max())
stereo = np.stack([left, right], axis=1) / peak * 0.85

sf.write("promo/public/music.wav", stereo.astype(np.float32), SR)
print(f"wrote promo/public/music.wav — {DUR}s, peak {np.abs(stereo).max():.2f}")
