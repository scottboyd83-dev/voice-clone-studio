import React, { useEffect, useRef, useState } from "react";

// Reading script shown while recording the reference clip (~10s read aloud).
// Phonetically varied, with a question for natural pitch movement.
export const REFERENCE_SCRIPT =
  "The quick brown fox jumps over the lazy dog, but honestly, who measures a " +
  "fox's enthusiasm? On Thursday morning I drank fresh orange juice, watched the " +
  "weather change, and wondered: could this voice really be cloned?";

// Mic recorder with a live oscilloscope while recording.
// Calls onRecorded(blob) with audio/webm when the user stops.
export default function Recorder({ onRecorded }) {
  const [recording, setRecording] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState(null);
  const mediaRef = useRef(null);   // { recorder, stream, audioCtx, raf }
  const canvasRef = useRef(null);

  const stopAll = () => {
    const m = mediaRef.current;
    if (!m) return;
    cancelAnimationFrame(m.raf);
    if (m.recorder.state !== "inactive") m.recorder.stop();
    m.stream.getTracks().forEach((t) => t.stop());
    m.audioCtx.close();
    mediaRef.current = null;
  };

  useEffect(() => () => stopAll(), []); // cleanup on unmount

  const start = async () => {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false },
      });
      const recorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
      const chunks = [];
      recorder.ondataavailable = (e) => e.data.size && chunks.push(e.data);
      recorder.onstop = () => onRecorded(new Blob(chunks, { type: "audio/webm" }));
      recorder.start();

      // live scope
      const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 2048;
      audioCtx.createMediaStreamSource(stream).connect(analyser);
      const data = new Uint8Array(analyser.fftSize);
      const startedAt = Date.now();

      const drawLoop = () => {
        setElapsed((Date.now() - startedAt) / 1000);
        const canvas = canvasRef.current;
        if (canvas) {
          const dpr = window.devicePixelRatio || 1;
          const w = canvas.clientWidth, h = canvas.clientHeight;
          canvas.width = w * dpr; canvas.height = h * dpr;
          const g = canvas.getContext("2d");
          g.scale(dpr, dpr);
          analyser.getByteTimeDomainData(data);
          g.clearRect(0, 0, w, h);
          g.beginPath();
          g.strokeStyle = "#e5484d";
          g.lineWidth = 1.5;
          for (let i = 0; i < data.length; i++) {
            const x = (i / data.length) * w;
            const y = (data[i] / 255) * h;
            i === 0 ? g.moveTo(x, y) : g.lineTo(x, y);
          }
          g.stroke();
        }
        if (mediaRef.current) mediaRef.current.raf = requestAnimationFrame(drawLoop);
      };

      mediaRef.current = { recorder, stream, audioCtx, raf: 0 };
      mediaRef.current.raf = requestAnimationFrame(drawLoop);
      setElapsed(0);
      setRecording(true);
    } catch (e) {
      setError(`Microphone unavailable: ${e.message}`);
    }
  };

  const stop = () => {
    stopAll();
    setRecording(false);
  };

  return (
    <div>
      <div className="meter-wrap">
        <canvas className="scope" ref={canvasRef} />
        <span className="rec-time">{recording ? `${elapsed.toFixed(1)}s` : "0.0s"}</span>
      </div>
      <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
        {!recording ? (
          <button className="btn rec" onClick={start}>● Record</button>
        ) : (
          <button className="btn rec recording" onClick={stop}>■ Stop</button>
        )}
        <span className="hint">
          Aim for 8–12 seconds. Quiet room, normal speaking voice, ~20cm from the mic.
        </span>
      </div>
      {error && <div className="error-bar">{error}</div>}
    </div>
  );
}
