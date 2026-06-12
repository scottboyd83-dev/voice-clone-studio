import React from "react";
import { AbsoluteFill, Audio, Sequence, staticFile } from "remotion";
import { SCENES, dur } from "./timeline";
import { C } from "./theme";
import { Grain, Vignette } from "./ui";
import { Clone, Convert, Generate, Intro, Outro, Privacy, Train } from "./scenes";

const ORDER = [
  [SCENES.intro, Intro],
  [SCENES.clone, Clone],
  [SCENES.generate, Generate],
  [SCENES.train, Train],
  [SCENES.convert, Convert],
  [SCENES.privacy, Privacy],
  [SCENES.outro, Outro],
];

export const Promo = ({ music = "music.wav" }) => (
  <AbsoluteFill style={{ background: C.bg }}>
    <Audio src={staticFile(music)} />
    {ORDER.map(([scene, Comp], i) => (
      <Sequence key={i} from={scene.from} durationInFrames={dur(scene)}>
        <Comp total={dur(scene)} />
      </Sequence>
    ))}
    <Vignette />
    <Grain />
  </AbsoluteFill>
);
