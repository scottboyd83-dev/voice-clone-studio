"""Promo bed v2 (redesign) — uplifting but professional, and grid-locked:
at 120 BPM every scene cut (4.5/10/16/23/30/36s) lands exactly on a beat,
chord changes snap to the cuts with no overlap, and all parts stay diatonic
in C major so nothing clashes. Keep CUTS in sync with src/timeline.ts.
Run: uv run python promo/make_music_v2.py  (from the repo root)
"""

import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfilt

SR = 48000
DUR = 42.0
CUTS = [4.5, 10.0, 16.0, 23.0, 30.0, 36.0]  # scene boundaries (s)
BEAT = 0.5  # 120 BPM — all cuts are whole beats

t = np.arange(int(DUR * SR)) / SR
N = len(t)
rng = np.random.default_rng(5)


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


# ---- harmony: one chord per scene, all diatonic C major, no overlaps ----
# (root for bass, triad for pad, chord tones for the arp)
SCENES_CHORDS = [
    # root_hz, triad (pad), arp tones (an octave up, root-5th-oct-3rd order)
    (65.41, [130.81, 164.81, 196.0], [261.63, 392.0, 523.25, 329.63]),   # C
    (98.0,  [146.83, 196.0, 246.94], [392.0, 587.33, 783.99, 493.88]),   # G
    (110.0, [130.81, 164.81, 220.0], [440.0, 659.26, 880.0, 523.25]),    # Am
    (87.31, [130.81, 174.61, 220.0], [349.23, 523.25, 698.46, 440.0]),   # F
    (65.41, [164.81, 196.0, 261.63], [523.25, 783.99, 1046.5, 659.26]),  # C (lifted voicing)
    (87.31, [130.81, 174.61, 220.0], [349.23, 523.25, 698.46, 440.0]),   # F
    (65.41, [130.81, 164.81, 261.63], [261.63, 392.0, 523.25, 329.63]),  # C (home)
]
bounds = [0.0] + CUTS + [DUR]

# ---- bass + pad: sustained per scene, 0.4s attack/release, hard boundaries ----
bass = np.zeros(N)
pad = np.zeros(N)
for k, (root, triad, _) in enumerate(SCENES_CHORDS):
    s, e = bounds[k], bounds[k + 1]
    seg_len = int((e - s) * SR)
    seg_t = np.arange(seg_len) / SR
    att = np.clip(seg_t / 0.4, 0, 1) ** 2
    rel = np.clip(((e - s) - seg_t) / 0.4, 0, 1)
    env = att * rel
    b = np.sin(2 * np.pi * root * seg_t) + 0.3 * np.sin(2 * np.pi * root * 2 * seg_t)
    place(bass, b * env * 0.32, s)
    p = np.zeros(seg_len)
    for f in triad:
        ph = rng.uniform(0, 2 * np.pi)
        vib = 1 + 0.0015 * np.sin(2 * np.pi * 0.7 * seg_t + ph)  # gentle, no beating
        p += np.sin(2 * np.pi * f * seg_t * vib + ph)
        p += 0.25 * np.sin(2 * np.pi * 2 * f * seg_t + ph)
    place(pad, p * env / (len(triad) * 4.2), s)
pad = lowpass(pad, 1800)

# ---- kick: soft thump every beat, on the same grid as the cuts ----
kick = np.zeros(N)
k_len = int(0.32 * SR)
kx = np.arange(k_len) / SR
kf = 86 * np.exp(-kx / 0.04) + 50
k_sig = np.sin(2 * np.pi * np.cumsum(kf) / SR) * env_exp(k_len, 0.11)
for b in np.arange(0, 36.0, BEAT * 2):  # half-time feel: every 2nd beat
    place(kick, k_sig * 0.8, b)

# ---- arp: chord-tone plucks on 8ths, pattern restarts at every scene cut ----
arp = np.zeros(N)
pl_len = int(0.18 * SR)
px = np.arange(pl_len) / SR
for k, (_, _, tones) in enumerate(SCENES_CHORDS):
    s, e = bounds[k], bounds[k + 1]
    if e <= 4.5:  # arp enters with scene 2
        continue
    step = 0
    for b in np.arange(s, min(e, 38.5) - 0.01, BEAT / 2):
        f = tones[step % len(tones)]
        pluck = np.sin(2 * np.pi * f * px) * env_exp(pl_len, 0.06)
        place(arp, pluck * 0.13, b)
        step += 1
arp = lowpass(arp, 4500)

# ---- hats: offbeat ticks, mid-section only ----
hats = np.zeros(N)
tick_len = int(0.04 * SR)
for b in np.arange(10.0, 34.0, BEAT):
    tick = highpass(rng.standard_normal(tick_len), 9000) * env_exp(tick_len, 0.012)
    place(hats, tick * 0.11, b + BEAT / 2)

# ---- cut accents: warm boom exactly on each cut (a beat), no noisy risers ----
acc = np.zeros(N)
boom_len = int(0.9 * SR)
bx = np.arange(boom_len) / SR
bf = 120 * np.exp(-bx / 0.07) + 50
boom = np.sin(2 * np.pi * np.cumsum(bf) / SR) * env_exp(boom_len, 0.28)
for c in CUTS:
    place(acc, boom * 0.45, c)

# ---- mix, master envelope, stereo width ----
mix = kick + bass + pad * 0.9 + arp + hats + acc
master = np.clip(t / 1.0, 0, 1) * np.clip((41.6 - t) / 2.4, 0, 1)
mix *= np.clip(master, 0, 1)
mix = np.tanh(mix * 1.3) * 0.7

delay = int(0.01 * SR)
side = np.zeros(N)
side[delay:] = mix[:-delay]
left = mix + 0.16 * side
right = mix - 0.16 * side
peak = max(np.abs(left).max(), np.abs(right).max())
stereo = np.stack([left, right], axis=1) / peak * 0.85

sf.write("promo/public/music_v2.wav", stereo.astype(np.float32), SR)
print(f"wrote promo/public/music_v2.wav — {DUR}s, peak {np.abs(stereo).max():.2f}")
