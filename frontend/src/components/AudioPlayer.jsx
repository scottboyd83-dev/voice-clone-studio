import React, { useEffect, useRef, useState } from "react";

// Waveform player: decodes the file once, draws min/max peaks on canvas,
// click-to-seek, amber progress overlay.
export default function AudioPlayer({ src }) {
  const audioRef = useRef(null);
  const canvasRef = useRef(null);
  const peaksRef = useRef(null);
  const [playing, setPlaying] = useState(false);
  const [time, setTime] = useState(0);
  const [duration, setDuration] = useState(0);

  // decode + compute peaks
  useEffect(() => {
    let cancelled = false;
    peaksRef.current = null;
    (async () => {
      try {
        const buf = await fetch(src).then((r) => r.arrayBuffer());
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        const decoded = await ctx.decodeAudioData(buf);
        ctx.close();
        if (cancelled) return;
        const data = decoded.getChannelData(0);
        const buckets = 240;
        const per = Math.floor(data.length / buckets);
        const peaks = new Float32Array(buckets);
        for (let i = 0; i < buckets; i++) {
          let max = 0;
          for (let j = i * per; j < (i + 1) * per; j++) {
            const v = Math.abs(data[j]);
            if (v > max) max = v;
          }
          peaks[i] = max;
        }
        peaksRef.current = peaks;
        setDuration(decoded.duration);
        draw(0);
      } catch { /* draw nothing on decode failure; <audio> still works */ }
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [src]);

  const draw = (progress) => {
    const canvas = canvasRef.current;
    const peaks = peaksRef.current;
    if (!canvas || !peaks) return;
    const dpr = window.devicePixelRatio || 1;
    const w = canvas.clientWidth, h = canvas.clientHeight;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    const g = canvas.getContext("2d");
    g.scale(dpr, dpr);
    g.clearRect(0, 0, w, h);
    const barW = w / peaks.length;
    const playedX = progress * w;
    for (let i = 0; i < peaks.length; i++) {
      const x = i * barW;
      const bh = Math.max(2, peaks[i] * (h - 6));
      g.fillStyle = x < playedX ? "#f5a524" : "#3a3a42";
      g.fillRect(x, (h - bh) / 2, Math.max(1, barW - 1.5), bh);
    }
  };

  // playback progress loop
  useEffect(() => {
    if (!playing) return;
    let raf;
    const tick = () => {
      const a = audioRef.current;
      if (a) {
        setTime(a.currentTime);
        if (duration) draw(a.currentTime / duration);
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playing, duration]);

  const toggle = () => {
    const a = audioRef.current;
    if (!a) return;
    if (a.paused) { a.play(); } else { a.pause(); }
  };

  const seek = (e) => {
    const a = audioRef.current;
    if (!a || !duration) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const frac = (e.clientX - rect.left) / rect.width;
    a.currentTime = frac * duration;
    setTime(a.currentTime);
    draw(frac);
  };

  const fmt = (s) => {
    const m = Math.floor(s / 60);
    return `${m}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
  };

  return (
    <div className="player">
      <audio
        ref={audioRef}
        src={src}
        onPlay={() => setPlaying(true)}
        onPause={() => setPlaying(false)}
        onEnded={() => { setPlaying(false); setTime(0); draw(0); }}
      />
      <button className="pp" onClick={toggle} title={playing ? "Pause" : "Play"}>
        {playing ? "❚❚" : "▶"}
      </button>
      <canvas className="wave" ref={canvasRef} onClick={seek} />
      <span className="time">{fmt(time)} / {duration ? fmt(duration) : "–:––"}</span>
    </div>
  );
}
