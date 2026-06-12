import React from "react";
import {
  AbsoluteFill,
  interpolate,
  random,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { loadFont as loadMono } from "@remotion/google-fonts/IBMPlexMono";
import { loadFont as loadSerif } from "@remotion/google-fonts/InstrumentSerif";
import { C } from "./theme";

const mono = loadMono().fontFamily;
const serif = loadSerif().fontFamily;
export const FONTS = { mono, serif };

// Layout scale: designs assume 1920w landscape / 1080w portrait.
export const useScale = () => {
  const { width, height } = useVideoConfig();
  const portrait = height > width;
  return { s: portrait ? width / 1080 : width / 1920, portrait };
};

// Ease-in/out of a scene: fade+lift over the first/last `pad` frames.
export const sceneInOut = (frame, total, pad = 12) => {
  const inO = interpolate(frame, [0, pad], [0, 1], { extrapolateRight: "clamp" });
  const outO = interpolate(frame, [total - pad, total], [1, 0], { extrapolateLeft: "clamp" });
  const y = interpolate(frame, [0, pad], [24, 0], { extrapolateRight: "clamp" });
  return { opacity: Math.min(inO, outO), transform: `translateY(${y}px)` };
};

export const Backdrop = ({ glow = 0.6 }) => (
  <AbsoluteFill
    style={{
      background: `radial-gradient(60% 50% at 50% 30%, rgba(245,165,36,${0.07 * glow}), transparent 70%), ${C.bg}`,
    }}
  />
);

export const Vignette = () => (
  <AbsoluteFill
    style={{
      background: "radial-gradient(90% 80% at 50% 50%, transparent 55%, rgba(0,0,0,0.55) 100%)",
      pointerEvents: "none",
    }}
  />
);

const NOISE_SVG = encodeURIComponent(
  `<svg xmlns="http://www.w3.org/2000/svg" width="240" height="240"><filter id="n"><feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2"/></filter><rect width="240" height="240" filter="url(#n)" opacity="0.55"/></svg>`
);

export const Grain = () => {
  const frame = useCurrentFrame();
  const dx = Math.floor(random(`gx-${frame}`) * 240);
  const dy = Math.floor(random(`gy-${frame}`) * 240);
  return (
    <AbsoluteFill
      style={{
        backgroundImage: `url("data:image/svg+xml,${NOISE_SVG}")`,
        backgroundPosition: `${dx}px ${dy}px`,
        opacity: 0.05,
        mixBlendMode: "overlay",
        pointerEvents: "none",
      }}
    />
  );
};

export const Kicker = ({ children, size = 22, color = C.amber, style }) => (
  <div
    style={{
      fontFamily: FONTS.mono,
      fontSize: size,
      letterSpacing: "0.32em",
      textTransform: "uppercase",
      color,
      ...style,
    }}
  >
    {children}
  </div>
);

export const Chip = ({ children, color = C.amber, size = 20 }) => (
  <span
    style={{
      fontFamily: FONTS.mono,
      fontSize: size,
      letterSpacing: "0.18em",
      textTransform: "uppercase",
      color,
      border: `2px solid ${color}`,
      borderRadius: 6,
      padding: `${size * 0.35}px ${size * 0.9}px`,
      background: `${color}1f`,
    }}
  >
    {children}
  </span>
);

export const Led = ({ color = C.green, size = 14, on = true }) => (
  <span
    style={{
      display: "inline-block",
      width: size,
      height: size,
      borderRadius: "50%",
      background: on ? color : C.lineBright,
      boxShadow: on ? `0 0 ${size}px ${color}` : "none",
    }}
  />
);

export const Panel = ({ label, children, width, style }) => (
  <div
    style={{
      border: `2px solid ${C.line}`,
      background: C.panel,
      borderRadius: 12,
      padding: "40px 44px 36px",
      position: "relative",
      width,
      boxShadow: "0 30px 80px rgba(0,0,0,0.5)",
      ...style,
    }}
  >
    {label && (
      <div
        style={{
          position: "absolute",
          top: -14,
          left: 26,
          background: C.bg,
          padding: "0 14px",
          fontFamily: FONTS.mono,
          fontSize: 17,
          letterSpacing: "0.26em",
          textTransform: "uppercase",
          color: C.faint,
        }}
      >
        {label}
      </div>
    )}
    {children}
  </div>
);

// Animated waveform bars. `progress` 0-1 lights bars left→right; `live`
// makes lit bars dance. Heights are deterministic per `seed`.
export const WaveBars = ({
  n = 36,
  height = 90,
  color = C.amber,
  progress = 1,
  live = true,
  seed = "w",
  barWidth = 7,
  gap = 7,
}) => {
  const frame = useCurrentFrame();
  return (
    <div style={{ display: "flex", alignItems: "center", gap, height }}>
      {Array.from({ length: n }).map((_, i) => {
        const base = 0.25 + 0.75 * random(`${seed}-${i}`);
        const wobble = live ? 0.72 + 0.28 * Math.sin(frame / 2.6 + i * 1.7) : 1;
        const lit = i / n < progress;
        return (
          <div
            key={i}
            style={{
              width: barWidth,
              height: Math.max(6, height * base * wobble * (lit ? 1 : 0.45)),
              background: lit ? color : C.lineBright,
              opacity: lit ? 1 : 0.5,
              borderRadius: 4,
            }}
          />
        );
      })}
    </div>
  );
};

// Monospace text that types on from `start` (frames) at `cps` chars/sec.
export const TypeText = ({ text, start = 0, cps = 30, size = 30, color = C.text }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const chars = Math.max(0, Math.floor(((frame - start) / fps) * cps));
  const done = chars >= text.length;
  const cursorOn = Math.floor(frame / 14) % 2 === 0;
  return (
    <span style={{ fontFamily: FONTS.mono, fontSize: size, color, lineHeight: 1.55 }}>
      {text.slice(0, chars)}
      <span style={{ opacity: cursorOn ? 1 : 0, color: C.amber }}>▌</span>
      {!done && <span style={{ opacity: 0 }}>{text.slice(chars)}</span>}
    </span>
  );
};

// Serif display headline with per-word staggered rise.
export const Headline = ({ words, start = 0, size = 110, align = "center" }) => {
  const frame = useCurrentFrame();
  return (
    <div
      style={{
        fontFamily: FONTS.serif,
        fontSize: size,
        lineHeight: 1.08,
        textAlign: align,
        color: C.text,
        fontWeight: 400,
      }}
    >
      {words.map((w, i) => {
        const f = frame - start - i * 4;
        const o = interpolate(f, [0, 14], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });
        const y = interpolate(f, [0, 14], [40, 0], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });
        return (
          <span
            key={i}
            style={{
              display: "inline-block",
              whiteSpace: "pre",
              opacity: o,
              transform: `translateY(${y}px)`,
              color: w.accent ? C.amber : C.text,
              fontStyle: w.accent ? "italic" : "normal",
              textShadow: w.accent ? `0 0 60px ${C.amberGlow}` : "none",
            }}
          >
            {w.t}
            {i < words.length - 1 ? " " : ""}
          </span>
        );
      })}
    </div>
  );
};
