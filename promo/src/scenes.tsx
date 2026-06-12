import React from "react";
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { C } from "./theme";
import {
  Backdrop,
  Chip,
  FONTS,
  Headline,
  Kicker,
  Led,
  Panel,
  TypeText,
  WaveBars,
  sceneInOut,
  useScale,
} from "./ui";

// Centers a fixed-design-size column (1560w landscape / 940w portrait),
// scales it to the actual composition, and applies the scene fade in/out.
const SceneFrame = ({ total, glow = 0.6, children }) => {
  const frame = useCurrentFrame();
  const { s, portrait } = useScale();
  return (
    <AbsoluteFill>
      <Backdrop glow={glow} />
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
        <div
          style={{
            width: portrait ? 940 : 1560,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: portrait ? 44 : 36,
            transform: `scale(${s}) ${sceneInOut(frame, total).transform}`,
            opacity: sceneInOut(frame, total).opacity,
          }}
        >
          {children}
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

const fadeAt = (frame, start, len = 10) =>
  interpolate(frame, [start, start + len], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

// ---------- 01 · intro ----------
export const Intro = ({ total }) => {
  const frame = useCurrentFrame();
  const { portrait } = useScale();
  return (
    <SceneFrame total={total} glow={interpolate(frame, [0, 60], [0, 1], { extrapolateRight: "clamp" })}>
      <div style={{ display: "flex", alignItems: "center", gap: 18, opacity: fadeAt(frame, 6, 14) }}>
        <Led color={C.amber} size={16} on={frame > 10 && Math.floor(frame / 4) % 5 !== 0 ? true : frame > 34} />
        <Kicker>On-device voice AI</Kicker>
      </div>
      <Headline
        start={28}
        size={portrait ? 124 : 170}
        words={[{ t: "Voice" }, { t: "Clone", accent: true }, { t: "Studio" }]}
      />
      <div
        style={{
          fontFamily: FONTS.mono,
          fontSize: 26,
          color: C.dim,
          letterSpacing: "0.12em",
          opacity: fadeAt(frame, 70, 14),
        }}
      >
        for Apple Silicon
      </div>
    </SceneFrame>
  );
};

// ---------- 02 · instant clone ----------
export const Clone = ({ total }) => {
  const frame = useCurrentFrame();
  const { portrait } = useScale();
  const secs = Math.min(10, Math.max(0, (frame - 30) / 9)); // 0→10 "seconds" quickly
  const done = secs >= 10;
  return (
    <SceneFrame total={total}>
      <div style={{ opacity: fadeAt(frame, 0, 10) }}>
        <Chip>01 · Instant cloning — F5-TTS</Chip>
      </div>
      <Headline
        start={8}
        size={portrait ? 96 : 120}
        words={[{ t: "Your" }, { t: "voice." }, { t: "Ten" }, { t: "seconds,", accent: true }, { t: "cloned." }]}
      />
      <div style={{ opacity: fadeAt(frame, 26, 12), width: "100%" }}>
        <Panel label="Reference · recording" width="100%">
          <div style={{ display: "flex", alignItems: "center", gap: 30 }}>
            <Led color={done ? C.green : C.red} size={18} on={done || Math.floor(frame / 12) % 2 === 0} />
            <WaveBars n={portrait ? 26 : 44} seed="clone" color={done ? C.green : C.red} live={!done} height={100} />
            <div style={{ fontFamily: FONTS.mono, fontSize: 40, color: done ? C.green : C.text, minWidth: 170, textAlign: "right" }}>
              {done ? "ready" : `0:0${Math.floor(secs)}.${Math.floor((secs % 1) * 10)}`}
            </div>
          </div>
        </Panel>
      </div>
    </SceneFrame>
  );
};

// ---------- 03 · generate ----------
export const Generate = ({ total }) => {
  const frame = useCurrentFrame();
  const { portrait } = useScale();
  const speakStart = 96;
  const speaking = frame >= speakStart;
  return (
    <SceneFrame total={total}>
      <div style={{ opacity: fadeAt(frame, 0, 10) }}>
        <Chip>02 · Text to speech</Chip>
      </div>
      <Headline
        start={8}
        size={portrait ? 100 : 130}
        words={[{ t: "Type." }, { t: "It" }, { t: "speaks.", accent: true }]}
      />
      <div style={{ opacity: fadeAt(frame, 24, 12), width: "100%" }}>
        <Panel label="Generate" width="100%">
          <div style={{ minHeight: 110 }}>
            <TypeText
              text="Anything you can write, said in your voice — long reads included."
              start={30}
              cps={34}
              size={portrait ? 30 : 34}
            />
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 30, marginTop: 26, opacity: fadeAt(frame, speakStart, 8) }}>
            <div
              style={{
                fontFamily: FONTS.mono,
                fontSize: 26,
                fontWeight: 600,
                color: C.bg,
                background: C.amber,
                borderRadius: 8,
                padding: "12px 30px",
                transform: `scale(${1 + 0.08 * Math.max(0, 1 - (frame - speakStart) / 8)})`,
              }}
            >
              ▶ Playing
            </div>
            <WaveBars
              n={portrait ? 22 : 38}
              seed="gen"
              progress={Math.min(1, (frame - speakStart) / 60)}
              live={speaking}
              height={84}
            />
          </div>
        </Panel>
      </div>
    </SceneFrame>
  );
};

// ---------- 04 · train ----------
const Bar = ({ label, frac, value }) => (
  <div style={{ display: "flex", alignItems: "center", gap: 24, width: "100%" }}>
    <div style={{ fontFamily: FONTS.mono, fontSize: 24, color: C.dim, width: 130, letterSpacing: "0.1em" }}>{label}</div>
    <div style={{ flex: 1, height: 12, background: C.lineBright, borderRadius: 6, overflow: "hidden" }}>
      <div style={{ width: `${frac * 100}%`, height: "100%", background: C.amber, borderRadius: 6 }} />
    </div>
    <div style={{ fontFamily: FONTS.mono, fontSize: 24, color: C.text, width: 120, textAlign: "right" }}>{value}</div>
  </div>
);

export const Train = ({ total }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { portrait } = useScale();
  const f1 = interpolate(frame, [34, 120], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const f2 = interpolate(frame, [48, 150], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const starPop = spring({ frame: frame - 158, fps, config: { damping: 11, mass: 0.6 } });
  return (
    <SceneFrame total={total}>
      <div style={{ opacity: fadeAt(frame, 0, 10) }}>
        <Chip>03 · Fine-tuning — GPT-SoVITS</Chip>
      </div>
      <Headline
        start={8}
        size={portrait ? 92 : 116}
        words={[{ t: "Overnight," }, { t: "it" }, { t: "learns" }, { t: "you.", accent: true }]}
      />
      <div style={{ opacity: fadeAt(frame, 24, 12), width: "100%" }}>
        <Panel label="Training · your dataset" width="100%">
          <div style={{ fontFamily: FONTS.mono, fontSize: 24, color: C.dim, marginBottom: 26 }}>
            90 scripted prompts · quality-gated · transcript-verified
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 22 }}>
            <Bar label="SoVITS" frac={f1} value={`${Math.ceil(f1 * 8)}/8 ep`} />
            <Bar label="GPT" frac={f2} value={`${Math.ceil(f2 * 15)}/15 ep`} />
          </div>
          <div
            style={{
              marginTop: 30,
              fontFamily: FONTS.mono,
              fontSize: 30,
              color: C.amber,
              opacity: Math.min(1, starPop),
              transform: `scale(${0.6 + 0.4 * starPop})`,
              transformOrigin: "left center",
            }}
          >
            ★ Fine-tuned voice added to your library
          </div>
        </Panel>
      </div>
    </SceneFrame>
  );
};

// ---------- 05 · convert ----------
export const Convert = ({ total }) => {
  const frame = useCurrentFrame();
  const { portrait } = useScale();
  const morph = interpolate(frame, [60, 130], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const tag = (txt, color, on) => (
    <div style={{ fontFamily: FONTS.mono, fontSize: 24, letterSpacing: "0.2em", textTransform: "uppercase", color, opacity: on ? 1 : 0.35, textAlign: "center" }}>
      {txt}
    </div>
  );
  return (
    <SceneFrame total={total}>
      <div style={{ opacity: fadeAt(frame, 0, 10) }}>
        <Chip color={C.green}>04 · Speech to speech — Seed-VC</Chip>
      </div>
      <Headline
        start={8}
        size={portrait ? 84 : 104}
        words={[{ t: "Perform" }, { t: "the" }, { t: "line." }, { t: "Swap" }, { t: "the" }, { t: "voice.", accent: true }]}
      />
      <div
        style={{
          opacity: fadeAt(frame, 26, 12),
          display: "flex",
          flexDirection: portrait ? "column" : "row",
          alignItems: "center",
          gap: portrait ? 30 : 50,
          width: "100%",
          justifyContent: "center",
        }}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: 14, alignItems: "center" }}>
          <WaveBars n={portrait ? 22 : 26} seed="perform" color={C.red} height={92} live={morph < 1} />
          {tag("Any voice in", C.red, morph < 1)}
        </div>
        <div
          style={{
            fontFamily: FONTS.mono,
            fontSize: 64,
            color: C.amber,
            transform: portrait ? "rotate(90deg)" : "none",
            opacity: 0.5 + 0.5 * Math.abs(Math.sin(frame / 9)),
          }}
        >
          ⇢
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 14, alignItems: "center" }}>
          <WaveBars n={portrait ? 22 : 26} seed="perform" color={C.amber} height={92} live progress={morph} />
          {tag("Your clone out", C.amber, morph > 0.15)}
        </div>
      </div>
      <div style={{ fontFamily: FONTS.mono, fontSize: 26, color: C.dim, opacity: fadeAt(frame, 140, 12), textAlign: "center" }}>
        Same words, same pacing, same emotion — new timbre. <span style={{ color: C.green }}>Singing mode ♪</span>
      </div>
    </SceneFrame>
  );
};

// ---------- 06 · privacy ----------
export const Privacy = ({ total }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { portrait } = useScale();
  const lines = ["NO CLOUD.", "NO ACCOUNTS.", "NO UPLOADS."];
  return (
    <SceneFrame total={total} glow={0.3}>
      <div style={{ display: "flex", flexDirection: "column", gap: portrait ? 30 : 22, alignItems: "center" }}>
        {lines.map((l, i) => {
          const pop = spring({ frame: frame - 10 - i * 22, fps, config: { damping: 12, mass: 0.5 } });
          return (
            <div
              key={l}
              style={{
                fontFamily: FONTS.mono,
                fontWeight: 600,
                fontSize: portrait ? 88 : 110,
                letterSpacing: "0.06em",
                color: C.text,
                opacity: Math.min(1, pop),
                transform: `scale(${0.7 + 0.3 * pop})`,
              }}
            >
              {l}
            </div>
          );
        })}
      </div>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 20,
          opacity: fadeAt(frame, 96, 14),
          fontFamily: FONTS.serif,
          fontSize: portrait ? 54 : 62,
          color: C.amber,
          fontStyle: "italic",
        }}
      >
        <Led color={C.green} size={18} />
        Everything stays on your Mac.
      </div>
    </SceneFrame>
  );
};

// ---------- 07 · outro ----------
export const Outro = ({ total }) => {
  const frame = useCurrentFrame();
  const { portrait } = useScale();
  return (
    <SceneFrame total={total}>
      <Headline
        start={4}
        size={portrait ? 110 : 140}
        words={[{ t: "Voice" }, { t: "Clone", accent: true }, { t: "Studio" }]}
      />
      <div
        style={{
          fontFamily: FONTS.mono,
          fontSize: portrait ? 28 : 32,
          letterSpacing: "0.18em",
          textTransform: "uppercase",
          color: C.dim,
          opacity: fadeAt(frame, 34, 14),
        }}
      >
        Your voice · Your Mac · Nothing else
      </div>
      <div
        style={{
          marginTop: 14,
          fontFamily: FONTS.mono,
          fontSize: 30,
          color: C.text,
          background: C.panel,
          border: `2px solid ${C.line}`,
          borderRadius: 10,
          padding: "16px 34px",
          opacity: fadeAt(frame, 58, 12),
        }}
      >
        <span style={{ color: C.green }}>$</span> <TypeText text="./run.sh" start={66} cps={16} size={30} />
      </div>
      <div
        style={{
          marginTop: 26,
          fontFamily: FONTS.mono,
          fontSize: 21,
          letterSpacing: "0.14em",
          color: C.faint,
          opacity: fadeAt(frame, 100, 16),
        }}
      >
        Designed &amp; created by <span style={{ color: C.dim }}>Scott Rodham-Boyd</span>
      </div>
    </SceneFrame>
  );
};
