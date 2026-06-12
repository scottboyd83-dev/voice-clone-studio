"""Assemble demo.mp4: trim/speed scenes to voiceover-driven slots, mux VO track."""
import json
import subprocess
from pathlib import Path

DEMO = Path(__file__).parent
RAW, VO = DEMO / "raw", DEMO / "vo"
meta = json.loads((VO / "meta.json").read_text())
vo_dur = meta["durations"]

TITLE_HOLD = 3.5   # silent title card at the head of scene 0
PAD = 2.0          # breathing room after each VO segment
OUTRO = 4.0        # longer hold + fade on the final scene

slots = [TITLE_HOLD + vo_dur[0] + PAD - 0.5]
slots += [vo_dur[i] + PAD for i in range(1, 6)]
slots += [vo_dur[6] + OUTRO]
total = sum(slots)
print("slots:", [round(s, 1) for s in slots], "total:", round(total, 1))


def probe(p):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "default=noprint_wrappers=1:nokey=1", str(p)],
                         capture_output=True, text=True)
    return float(out.stdout.strip())


inputs, vf, af = [], [], []
for i in range(7):
    scene = RAW / f"scene{i}.webm"
    dur = probe(scene)
    inputs += ["-i", str(scene)]
    if i == 2 and dur > slots[i]:  # typing + live generation: timelapse it into the slot
        factor = slots[i] / dur
        vf.append(f"[{i}:v]setpts=PTS*{factor:.5f},fps=30,scale=1280:800,"
                  f"trim=duration={slots[i]:.3f},setpts=PTS-STARTPTS[v{i}]")
    else:
        pad = max(0.0, slots[i] - dur)
        vf.append(f"[{i}:v]fps=30,scale=1280:800,trim=duration={slots[i]:.3f},"
                  f"tpad=stop_mode=clone:stop_duration={pad:.3f},"
                  f"trim=duration={slots[i]:.3f},setpts=PTS-STARTPTS[v{i}]")

for i in range(7):
    inputs += ["-i", str(VO / f"vo{i}.wav")]
    delay = int(TITLE_HOLD * 1000) if i == 0 else 400  # title hold, then a beat per scene
    af.append(f"[{7 + i}:a]aresample=48000,adelay={delay}|{delay},apad,"
              f"atrim=duration={slots[i]:.3f},asetpts=PTS-STARTPTS[a{i}]")

fc = (";".join(vf) + ";" + ";".join(af) + ";"
      + "".join(f"[v{i}]" for i in range(7)) + "concat=n=7:v=1:a=0[vc];"
      + f"[vc]fade=t=out:st={total - 1.2:.2f}:d=1.2[vout];"
      + "".join(f"[a{i}]" for i in range(7)) + "concat=n=7:v=0:a=1[ac];"
      + f"[ac]loudnorm=I=-16:TP=-1.5,afade=t=out:st={total - 1.2:.2f}:d=1.2[aout]")

cmd = ["ffmpeg", "-y", *inputs, "-filter_complex", fc,
       "-map", "[vout]", "-map", "[aout]",
       "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
       "-c:a", "aac", "-b:a", "192k", str(DEMO / "demo.mp4")]
subprocess.run(cmd, check=True, capture_output=True)
print("demo.mp4:", round(probe(DEMO / "demo.mp4"), 1), "secs")
