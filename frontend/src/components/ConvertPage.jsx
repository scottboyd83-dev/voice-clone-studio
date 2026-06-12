import React, { useEffect, useRef, useState } from "react";
import { api } from "../api.js";
import AudioPlayer from "./AudioPlayer.jsx";
import Recorder from "./Recorder.jsx";
import Slider from "./Slider.jsx";

const DEFAULTS = { diffusion_steps: 25, length_adjust: 1.0, pitch_shift: 0 };

export default function ConvertPage({ voices }) {
  const [voiceId, setVoiceId] = useState(voices[0]?.id || "");
  const [source, setSource] = useState(null); // { blob, filename, url }
  const [settings, setSettings] = useState(DEFAULTS);
  const [singing, setSinging] = useState(false);
  const [autoF0, setAutoF0] = useState(true);
  const [engine, setEngine] = useState({ installed: true, state: "idle" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const [history, setHistory] = useState([]);
  const fileRef = useRef(null);

  const set = (k) => (v) => setSettings((s) => ({ ...s, [k]: v }));
  const voiceName = (id) => voices.find((v) => v.id === id)?.name || "deleted voice";

  const refreshHistory = () => api.listConversions().then(setHistory).catch(() => {});
  const refreshEngine = () => api.convertStatus().then(setEngine).catch(() => {});

  useEffect(() => {
    refreshHistory();
    refreshEngine();
  }, []);

  // poll engine state while the worker loads models
  useEffect(() => {
    if (engine.state !== "loading") return;
    const t = setInterval(refreshEngine, 2000);
    return () => clearInterval(t);
  }, [engine.state]);

  const pickSource = (blob, filename) => {
    if (source?.url) URL.revokeObjectURL(source.url);
    setSource({ blob, filename, url: URL.createObjectURL(blob) });
    setResult(null);
  };

  const convert = async () => {
    if (!voiceId) { setError("Create a voice first."); return; }
    if (!source) { setError("Record or upload some speech to convert."); return; }
    setBusy(true);
    setError(null);
    setResult(null);
    refreshEngine();
    try {
      const conv = await api.convert({
        voiceId,
        blob: source.blob,
        filename: source.filename,
        diffusion_steps: settings.diffusion_steps,
        length_adjust: settings.length_adjust,
        f0_condition: singing,
        auto_f0_adjust: autoF0,
        pitch_shift: singing ? settings.pitch_shift : 0,
      });
      setResult(conv);
      refreshHistory();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
      refreshEngine();
    }
  };

  const remove = async (id) => {
    await api.deleteConversion(id).catch(() => {});
    if (result?.id === id) setResult(null);
    refreshHistory();
  };

  return (
    <>
      <h2 className="page-title">Voice Changer</h2>
      <p className="page-sub">
        Speak (or upload) anything in any voice — Seed-VC re-renders it in a library voice.
        No training, no transcript; delivery and pacing are kept, timbre is swapped.
      </p>

      {!engine.installed && (
        <div className="error-bar">
          Seed-VC isn't installed — run <code>scripts/setup_seedvc.sh</code> once, then restart the backend.
        </div>
      )}

      <div className="gen-layout">
        <div>
          <div className="panel">
            <span className="panel-label">Source speech</span>
            <Recorder
              onRecorded={(blob) => pickSource(blob, "recording.webm")}
              hint="Any length up to 5 minutes. Your wording, pacing and emotion carry through."
            />
            <div style={{ marginTop: 12, display: "flex", gap: 10, alignItems: "center" }}>
              <button className="btn small" onClick={() => fileRef.current?.click()}>
                Upload audio…
              </button>
              <input
                ref={fileRef} type="file" accept="audio/*" style={{ display: "none" }}
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) pickSource(f, f.name);
                  e.target.value = "";
                }}
              />
              {source && <span className="hint">{source.filename}</span>}
            </div>
            {source && (
              <div style={{ marginTop: 12 }}>
                <AudioPlayer src={source.url} />
              </div>
            )}

            <div style={{ marginTop: 16 }}>
              <button className="btn primary" onClick={convert} disabled={busy || !engine.installed}>
                {busy ? "Converting…" : "Convert ▸"}
              </button>
              {engine.state !== "ready" && !busy && (
                <span className="hint" style={{ marginLeft: 12 }}>
                  {engine.state === "loading"
                    ? "voice changer warming up…"
                    : "first conversion loads the voice changer (~1 min)"}
                </span>
              )}
            </div>

            {busy && (
              <div className="generating">
                <div className="bars"><span/><span/><span/><span/><span/></div>
                {engine.state === "ready" ? "converting voice" : "loading engine, then converting"}
              </div>
            )}
            {error && <div className="error-bar">{error}</div>}
          </div>

          {result && (
            <div className="panel">
              <span className="panel-label">Output — {voiceName(result.voice_id)}</span>
              <AudioPlayer src={api.convAudioUrl(result.id)} />
              <div className="hint" style={{ marginTop: 10 }}>
                {result.duration_secs?.toFixed(1)}s ·{" "}
                <a style={{ color: "var(--amber)" }} href={api.convAudioUrl(result.id)} download>
                  download wav
                </a>
              </div>
            </div>
          )}

          {history.length > 0 && (
            <div className="panel">
              <span className="panel-label">Recent conversions</span>
              {history.map((c) => (
                <div key={c.id} style={{ padding: "10px 0", borderBottom: "1px solid var(--line, #2a2a2a)" }}>
                  <div className="hint" style={{ marginBottom: 6 }}>
                    {c.source_name} → <span style={{ color: "var(--amber)" }}>{voiceName(c.voice_id)}</span>
                    {" · "}{c.duration_secs?.toFixed(1)}s
                    {c.settings?.f0_condition ? " · singing" : ""}
                    {" · "}
                    <a style={{ color: "var(--amber)" }} href={api.convAudioUrl(c.id, "source")} target="_blank" rel="noreferrer">
                      source
                    </a>
                    {" · "}
                    <a style={{ color: "var(--amber)", cursor: "pointer" }} onClick={() => remove(c.id)}>
                      delete
                    </a>
                  </div>
                  <AudioPlayer src={api.convAudioUrl(c.id)} />
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="panel">
          <span className="panel-label">Conversion settings</span>
          <label className="field" style={{ marginTop: 0 }}>Target voice</label>
          <select value={voiceId} onChange={(e) => setVoiceId(e.target.value)}>
            {voices.length === 0 && <option value="">— no voices yet —</option>}
            {voices.map((v) => (
              <option key={v.id} value={v.id}>{v.name}</option>
            ))}
          </select>
          <div className="hint" style={{ marginTop: 6 }}>
            Uses the voice's reference clip — works for instant and fine-tuned voices alike.
          </div>

          <Slider
            name="Quality" value={settings.diffusion_steps} min={10} max={50} step={5}
            onChange={set("diffusion_steps")} format={(v) => `${v} steps`}
            hint="Diffusion steps — higher is cleaner but slower. 25 is a good default."
          />
          <Slider
            name="Length" value={settings.length_adjust} min={0.5} max={2} step={0.05}
            onChange={set("length_adjust")} format={(v) => `${v.toFixed(2)}×`}
            hint="Stretch or compress the output relative to the source."
          />

          <label className="field">Singing mode</label>
          <label className="hint" style={{ display: "flex", gap: 8, alignItems: "center", cursor: "pointer" }}>
            <input type="checkbox" checked={singing} onChange={(e) => setSinging(e.target.checked)} />
            Pitch-aware conversion (44.1kHz) — use for singing, slower to render.
          </label>
          {singing && (
            <>
              <label className="hint" style={{ display: "flex", gap: 8, alignItems: "center", cursor: "pointer", marginTop: 8 }}>
                <input type="checkbox" checked={autoF0} onChange={(e) => setAutoF0(e.target.checked)} />
                Auto-match pitch to the target voice's range
              </label>
              <Slider
                name="Transpose" value={settings.pitch_shift} min={-12} max={12} step={1}
                onChange={set("pitch_shift")} format={(v) => `${v > 0 ? "+" : ""}${v} st`}
                hint="Manual pitch shift in semitones, applied on top."
              />
            </>
          )}

          <div style={{ marginTop: 18 }}>
            <button
              className="btn small"
              onClick={() => { setSettings(DEFAULTS); setSinging(false); setAutoF0(true); }}
            >
              Reset to defaults
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
