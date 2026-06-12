import React from "react";
import { Composition } from "remotion";
import { FPS, TOTAL_FRAMES } from "./timeline";
import { Promo } from "./Promo";

export const Root = () => (
  <>
    <Composition id="promo-16x9" component={Promo} durationInFrames={TOTAL_FRAMES} fps={FPS} width={1920} height={1080} />
    <Composition id="promo-9x16" component={Promo} durationInFrames={TOTAL_FRAMES} fps={FPS} width={1080} height={1920} />
    {/* v2: same cut, faster & brighter score */}
    <Composition id="promo-16x9-v2" component={Promo} durationInFrames={TOTAL_FRAMES} fps={FPS} width={1920} height={1080} defaultProps={{ music: "music_v2.wav" }} />
    <Composition id="promo-9x16-v2" component={Promo} durationInFrames={TOTAL_FRAMES} fps={FPS} width={1080} height={1920} defaultProps={{ music: "music_v2.wav" }} />
    {/* v3: same cut, warm EP score, no drums */}
    <Composition id="promo-16x9-v3" component={Promo} durationInFrames={TOTAL_FRAMES} fps={FPS} width={1920} height={1080} defaultProps={{ music: "music_v3.wav" }} />
    <Composition id="promo-9x16-v3" component={Promo} durationInFrames={TOTAL_FRAMES} fps={FPS} width={1080} height={1920} defaultProps={{ music: "music_v3.wav" }} />
  </>
);
