import React, { useState } from "react";
import { api } from "../api.js";
import AudioPlayer from "./AudioPlayer.jsx";
import Slider from "./Slider.jsx";

const DEFAULTS = { speed: 1.0, nfe_step: 32, cfg_strength: 2.0 };

export default function GeneratePage({ voices, initialVoiceId, modelLoaded }) {
  const [voiceId, setVoiceId] = useState(initialVoiceId || voices[0]?.id || "");
  const [text, setText] = useState("");
  const [settings, setSettings] = useState(DEFAULTS);
  const [seedLock, setSeedLock] = useState(null); // null = random each time
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  const set = (k) => (v) => setSettings((s) => ({ ...s, [k]: v }));

  const generate = async () => {
    if (!voiceId) { setError("Create a voice first."); return; }
    if (!text.trim()) { setError("Type something to say."); return; }
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const gen = await api.generate({
        voice_id: voiceId,
        text: text.trim(),
        speed: settings.speed,
        nfe_step: settings.nfe_step,
        cfg_strength: settings.cfg_strength,
        seed: seedLock,
      });
      setResult(gen);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <h2 className="page-title">Generate Speech</h2>
      <p className="page-sub">Type, tune, synthesize. First generation after startup is slower while the engine warms up.</p>

      <div className="gen-layout">
        <div>
          <div className="panel">
            <span className="panel-label">Input</span>
            <label className="field" style={{ marginTop: 0 }}>Voice</label>
            <select value={voiceId} onChange={(e) => setVoiceId(e.target.value)}>
              {voices.length === 0 && <option value="">— no voices yet —</option>}
              {voices.map((v) => (
                <option key={v.id} value={v.id}>{v.name}</option>
              ))}
            </select>

            <label className="field">Text</label>
            <textarea
              rows={7}
              value={text}
              placeholder="Hello! This is my cloned voice speaking. Long passages are fine — they're chunked and stitched automatically."
              onChange={(e) => setText(e.target.value)}
            />
            <div className="hint" style={{ marginTop: 6 }}>{text.length} characters</div>

            <div style={{ marginTop: 16 }}>
              <button className="btn primary" onClick={generate} disabled={busy}>
                {busy ? "Synthesizing…" : "Generate ▸"}
              </button>
              {!modelLoaded && !busy && (
                <span className="hint" style={{ marginLeft: 12 }}>
                  engine still loading — request will queue
                </span>
              )}
            </div>

            {busy && (
              <div className="generating">
                <div className="bars"><span/><span/><span/><span/><span/></div>
                rendering voice
              </div>
            )}
            {error && <div className="error-bar">{error}</div>}
          </div>

          {result && (
            <div className="panel">
              <span className="panel-label">Output</span>
              <AudioPlayer src={api.genAudioUrl(result.id)} />
              <div className="hint" style={{ marginTop: 10 }}>
                {result.duration_secs?.toFixed(1)}s · seed {result.seed}
                {" · "}
                <a style={{ color: "var(--amber)" }} href={api.genAudioUrl(result.id, "wav")} download>wav</a>
                {" / "}
                <a style={{ color: "var(--amber)" }} href={api.genAudioUrl(result.id, "mp3")} download>mp3</a>
                {" · "}
                <a
                  style={{ color: "var(--amber)", cursor: "pointer" }}
                  onClick={() => setSeedLock(result.seed)}
                >
                  lock this seed
                </a>
              </div>
            </div>
          )}
        </div>

        <div className="panel">
          <span className="panel-label">Voice settings</span>
          <Slider
            name="Speed" value={settings.speed} min={0.5} max={2} step={0.05}
            onChange={set("speed")} format={(v) => `${v.toFixed(2)}×`}
            hint="Pacing of delivery"
          />
          <Slider
            name="Quality" value={settings.nfe_step} min={8} max={64} step={4}
            onChange={set("nfe_step")} format={(v) => `${v} steps`}
            hint="Higher = cleaner, slower to render"
          />
          <Slider
            name="Voice adherence" value={settings.cfg_strength} min={1} max={4} step={0.1}
            onChange={set("cfg_strength")} format={(v) => v.toFixed(1)}
            hint="How tightly output sticks to your reference timbre"
          />

          <label className="field">Seed</label>
          {seedLock === null ? (
            <div className="hint">Random each run — lock a seed from an output you like to make takes reproducible.</div>
          ) : (
            <div className="hint">
              Locked: <span style={{ color: "var(--amber)" }}>{seedLock}</span>{" "}
              <a style={{ color: "var(--amber)", cursor: "pointer" }} onClick={() => setSeedLock(null)}>
                unlock
              </a>
            </div>
          )}

          <div style={{ marginTop: 18 }}>
            <button className="btn small" onClick={() => { setSettings(DEFAULTS); setSeedLock(null); }}>
              Reset to defaults
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
