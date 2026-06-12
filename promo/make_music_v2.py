"""Promo bed v2 — slightly faster (108 BPM) and brighter/more uplifting than v1:
major-key progression resolving home, opened-up pad filter, and a soft melodic
arp, while keeping the minimal professional feel. Accents land on the scene
cuts defined in src/timeline.ts — keep in sync.
Run: uv run python promo/make_music_v2.py  (from the repo root)
"""

import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfilt

SR = 48000
DUR = 42.0
CUTS = [4.5, 10.0, 16.0, 23.0, 30.0, 36.0]  # scene boundaries (s)
BEAT = 60 / 108  # 108 BPM

t = np.arange(int(DUR * SR)) / SR
N = len(t)
rng = np.random.default_rng(11)


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


# ---- pulse: soft four-on-the-floor thump, a touch lighter than v1 ----
pulse = np.zeros(N)
thump_len = int(0.4 * SR)
x = np.arange(thump_len) / SR
freq_sweep = 84 * np.exp(-x / 0.045) + 52
thump = np.sin(2 * np.pi * np.cumsum(freq_sweep) / SR) * env_exp(thump_len, 0.13)
for b in np.arange(0, DUR, BEAT):
    if b < 36.0:
        place(pulse, thump * 0.8, b)

# ---- pad: brighter major progression, resolving home on the outro ----
# C-major family, voiced low-mid; rises through convert, resolves on outro.
CHORDS = [
    [65.41, 98.0, 164.81],            # intro     C2 G2 E3
    [55.0, 82.41, 130.81],            # clone     A1 E2 C3  (Am, depth)
    [87.31, 130.81, 220.0],           # generate  F2 C3 A3
    [98.0, 146.83, 246.94],           # train     G2 D3 B3
    [110.0, 164.81, 261.63],          # convert   A2 E3 C4  (lifting)
    [87.31, 130.81, 174.61, 220.0],   # privacy   F2 C3 F3 A3
    [65.41, 98.0, 164.81, 261.63],    # outro     C2 G2 E3 C4 (home)
]
bounds = [0.0] + CUTS + [DUR]
pad = np.zeros(N)
for k, chord in enumerate(CHORDS):
    s, e = bounds[k], bounds[k + 1]
    seg_len = int((e - s + 1.5) * SR)
    seg_t = np.arange(seg_len) / SR
    seg = np.zeros(seg_len)
    for f in chord:
        for det in (-0.8, 0.0, 0.8):
            ph = rng.uniform(0, 2 * np.pi)
            seg += np.sin(2 * np.pi * (f + det) * seg_t + ph)
            seg += 0.45 * np.sin(2 * np.pi * 2 * (f + det) * seg_t + ph)
    att = np.clip(seg_t / 1.4, 0, 1) ** 2
    rel = np.clip((seg_len / SR - seg_t) / 1.2, 0, 1)
    place(pad, seg * att * rel / (len(chord) * 6), s)
pad = lowpass(pad, 2000)  # opened up vs v1's 900Hz — brighter, more hopeful

# ---- arp: soft plucked chord tones on 8ths, the v2 "lift" ----
arp = np.zeros(N)
pluck_len = int(0.22 * SR)
px = np.arange(pluck_len) / SR
for k, chord in enumerate(CHORDS):
    s, e = bounds[k], bounds[k + 1]
    tones = [f * 4 for f in chord[:3]]  # two octaves up, sparkly but mellow
    step = 0
    for b in np.arange(s, min(e, 38.0), BEAT / 2):
        if b < 8.0:  # arp enters with scene 2
            continue
        f = tones[step % len(tones)]
        pluck = np.sin(2 * np.pi * f * px) * env_exp(pluck_len, 0.07)
        place(arp, pluck * 0.16, b)
        place(arp, pluck * 0.07, b + 0.14)  # tiny echo
        step += 1
arp = lowpass(arp, 5000)

# ---- hats: ticks on the offbeats, a little more present than v1 ----
hats = np.zeros(N)
tick_len = int(0.05 * SR)
for b in np.arange(10.0, 34.0, BEAT):
    tick = highpass(rng.standard_normal(tick_len), 8000) * env_exp(tick_len, 0.014)
    place(hats, tick * 0.15, b + BEAT / 2)

# ---- scene accents: airy riser into each cut + warm boom on it ----
acc = np.zeros(N)
for c in CUTS:
    rise_len = int(1.0 * SR)
    noise = highpass(rng.standard_normal(rise_len), 2000)
    riser = noise * (np.arange(rise_len) / rise_len) ** 3 * 0.10
    place(acc, riser, c - 1.0)
    boom_len = int(1.0 * SR)
    bx = np.arange(boom_len) / SR
    bf = 130 * np.exp(-bx / 0.08) + 48
    boom = np.sin(2 * np.pi * np.cumsum(bf) / SR) * env_exp(boom_len, 0.3) * 0.45
    place(acc, boom, c)

# ---- mix, master envelope, stereo width ----
mix = pulse * 0.5 + pad * 0.85 + arp + hats + acc
master = np.clip(t / 1.0, 0, 1) * np.clip((41.6 - t) / 2.2, 0, 1)
mix *= np.clip(master, 0, 1)
mix = np.tanh(mix * 1.4) * 0.7

delay = int(0.011 * SR)
side = np.zeros(N)
side[delay:] = mix[:-delay]
left = mix + 0.2 * side
right = mix - 0.2 * side
peak = max(np.abs(left).max(), np.abs(right).max())
stereo = np.stack([left, right], axis=1) / peak * 0.85

sf.write("promo/public/music_v2.wav", stereo.astype(np.float32), SR)
print(f"wrote promo/public/music_v2.wav — {DUR}s, peak {np.abs(stereo).max():.2f}")
