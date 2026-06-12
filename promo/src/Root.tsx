import React from "react";
import { Composition } from "remotion";
import { FPS, TOTAL_FRAMES } from "./timeline";
import { Promo } from "./Promo";

export const Root = () => (
  <>
    <Composition id="promo-16x9" component={Promo} durationInFrames={TOTAL_FRAMES} fps={FPS} width={1920} height={1080} />
    <Composition id="promo-9x16" component={Promo} durationInFrames={TOTAL_FRAMES} fps={FPS} width={1080} height={1920} />
  </>
);
