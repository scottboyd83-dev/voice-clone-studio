// Scene timing — keep the second values in sync with CUTS in make_music.py,
// where the music's risers and booms land.
export const FPS = 30;
export const SECONDS = 42;
export const TOTAL_FRAMES = FPS * SECONDS;

const s = (sec) => Math.round(sec * FPS);

export const SCENES = {
  intro:    { from: s(0),    to: s(4.5) },
  clone:    { from: s(4.5),  to: s(10) },
  generate: { from: s(10),   to: s(16) },
  train:    { from: s(16),   to: s(23) },
  convert:  { from: s(23),   to: s(30) },
  privacy:  { from: s(30),   to: s(36) },
  outro:    { from: s(36),   to: s(42) },
};

export const dur = (scene) => scene.to - scene.from;
