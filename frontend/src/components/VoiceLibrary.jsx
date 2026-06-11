import React, { useState } from "react";
import { api } from "../api.js";
import AudioPlayer from "./AudioPlayer.jsx";
import Recorder, { REFERENCE_SCRIPT } from "./Recorder.jsx";

export default function VoiceLibrary({ voices, onChanged, onUse }) {
  const [showModal, setShowModal] = useState(false);

  const remove = async (v) => {
    if (!confirm(`Delete voice “${v.name}” and all its generations?`)) return;
    await api.deleteVoice(v.id);
    onChanged();
  };

  return (
    <>
      <h2 className="page-title">Voice Library</h2>
      <p className="page-sub">
        Each voice is built from a short reference clip — record one or upload existing audio.
      </p>

      <div style={{ marginBottom: 20 }}>
        <button className="btn primary" onClick={() => setShowModal(true)}>
          + New Voice
        </button>
      </div>

      {voices.length === 0 ? (
        <div className="empty">
          <div className="big">No voices yet.</div>
          Record a 10-second clip and hear yourself synthesized within the minute.
        </div>
      ) : (
        <div className="voice-grid">
          {voices.map((v) => (
            <div className="voice-card" key={v.id}>
              <h3>{v.name}</h3>
              <div className="meta">
                created {new Date(v.created_at * 1000).toLocaleDateString()}
              </div>
              {v.description && <div className="desc">{v.description}</div>}
              <AudioPlayer src={api.voiceRefUrl(v.id)} />
              <div className="row" style={{ marginTop: 12 }}>
                <button className="btn small primary" onClick={() => onUse(v.id)}>
                  Use voice →
                </button>
                <button className="btn small danger" onClick={() => remove(v)}>
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {showModal && (
        <NewVoiceModal
          onClose={() => setShowModal(false)}
          onCreated={() => { setShowModal(false); onChanged(); }}
        />
      )}
    </>
  );
}

function NewVoiceModal({ onClose, onCreated }) {
  const [mode, setMode] = useState("record"); // record | upload
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [blob, setBlob] = useState(null);
  const [filename, setFilename] = useState("recording.webm");
  const [uploadTranscript, setUploadTranscript] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const create = async () => {
    if (!name.trim()) { setError("Give the voice a name."); return; }
    if (!blob) { setError("Record or choose an audio file first."); return; }
    setBusy(true);
    setError(null);
    try {
      await api.createVoice({
        name,
        description,
        // recorded clips read the known script; uploads may supply their own transcript
        refText: mode === "record" ? REFERENCE_SCRIPT : uploadTranscript,
        blob,
        filename,
      });
      onCreated();
    } catch (e) {
      setError(e.message);
      setBusy(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal">
        <h2>New Voice</h2>

        <label className="field">Name</label>
        <input type="text" value={name} placeholder="e.g. Scott — natural"
               onChange={(e) => setName(e.target.value)} />

        <label className="field">Description (optional)</label>
        <input type="text" value={description} placeholder="e.g. relaxed read, AirPods mic"
               onChange={(e) => setDescription(e.target.value)} />

        <label className="field">Reference audio</label>
        <div className="seg">
          <button className={mode === "record" ? "on" : ""} onClick={() => { setMode("record"); setBlob(null); }}>
            Record
          </button>
          <button className={mode === "upload" ? "on" : ""} onClick={() => { setMode("upload"); setBlob(null); }}>
            Upload
          </button>
        </div>

        {mode === "record" ? (
          <>
            <div className="script-card">
              <div className="label">Read this aloud</div>
              <div className="text">{REFERENCE_SCRIPT}</div>
            </div>
            <Recorder onRecorded={(b) => { setBlob(b); setFilename("recording.webm"); }} />
            {blob && (
              <div style={{ marginTop: 12 }}>
                <AudioPlayer src={URL.createObjectURL(blob)} />
              </div>
            )}
          </>
        ) : (
          <>
            <div style={{ margin: "12px 0" }}>
              <input
                type="file"
                accept="audio/*,.m4a,.webm"
                onChange={(e) => {
                  const f = e.target.files[0];
                  if (f) { setBlob(f); setFilename(f.name); }
                }}
              />
            </div>
            <span className="hint">
              Best results: a clean 8–12s clip of just your voice. Longer files are trimmed to 12s.
            </span>
            <label className="field">Transcript of the clip (optional — auto-transcribed if blank)</label>
            <textarea
              rows={2}
              value={uploadTranscript}
              placeholder="Exactly what is said in the clip…"
              onChange={(e) => setUploadTranscript(e.target.value)}
            />
          </>
        )}

        {error && <div className="error-bar">{error}</div>}

        <div className="foot">
          <button className="btn" onClick={onClose} disabled={busy}>Cancel</button>
          <button className="btn primary" onClick={create} disabled={busy}>
            {busy ? "Creating…" : "Create voice"}
          </button>
        </div>
      </div>
    </div>
  );
}
