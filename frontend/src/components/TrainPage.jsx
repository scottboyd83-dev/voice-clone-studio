import React, { useEffect, useRef, useState } from "react";
import { api } from "../api.js";
import Slider from "./Slider.jsx";

const STAGE_LABELS = {
  preprocess_text: "1/6 · Text features",
  preprocess_ssl: "2/6 · Speech features",
  preprocess_semantic: "3/6 · Semantic tokens",
  train_sovits: "4/6 · Training SoVITS (timbre)",
  train_gpt: "5/6 · Training GPT (prosody)",
  register: "6/6 · Registering voice",
};

export default function TrainPage({ onVoicesChanged }) {
  const [datasets, setDatasets] = useState([]);
  const [datasetId, setDatasetId] = useState("");
  const [voiceName, setVoiceName] = useState("");
  const [sovitsEpochs, setSovitsEpochs] = useState(8);
  const [gptEpochs, setGptEpochs] = useState(15);
  const [job, setJob] = useState(null);
  const [error, setError] = useState(null);
  const timer = useRef(null);

  const poll = () => api.trainStatus().then((s) => {
    setJob(s);
    if (s.state !== "running" && timer.current) {
      clearInterval(timer.current);
      timer.current = null;
      if (s.state === "done") onVoicesChanged();
    }
  }).catch(() => {});

  useEffect(() => {
    api.listDatasets().then((d) => {
      setDatasets(d);
      if (d.length) setDatasetId(d[0].id);
    }).catch(() => {});
    poll();
    // resume polling if a run is already in flight (e.g. page reload mid-train)
    timer.current = setInterval(poll, 4000);
    return () => timer.current && clearInterval(timer.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const start = async () => {
    setError(null);
    if (!voiceName.trim()) { setError("Name the fine-tuned voice."); return; }
    try {
      await api.trainStart({
        dataset_id: datasetId,
        voice_name: voiceName.trim(),
        sovits_epochs: sovitsEpochs,
        gpt_epochs: gptEpochs,
      });
      if (!timer.current) timer.current = setInterval(poll, 4000);
      poll();
    } catch (e) {
      setError(e.message);
    }
  };

  const running = job?.state === "running";
  const ds = datasets.find((d) => d.id === datasetId);

  return (
    <>
      <h2 className="page-title">Fine-tune</h2>
      <p className="page-sub">
        Train a dedicated GPT-SoVITS model on your dataset — the big jump in similarity over
        instant cloning. Training runs on CPU: expect a few hours for a 10-minute dataset.
        Start it in the evening, wake up to your voice.
      </p>

      {datasets.length === 0 ? (
        <div className="empty">
          <div className="big">No datasets yet.</div>
          Record prompts in the Studio tab and hit “Build dataset” first.
        </div>
      ) : (
        <div className="gen-layout">
          <div className="panel">
            <span className="panel-label">Training run</span>

            <label className="field" style={{ marginTop: 0 }}>Dataset</label>
            <select value={datasetId} onChange={(e) => setDatasetId(e.target.value)} disabled={running}>
              {datasets.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.id} — {d.segments} segments, {(d.total_secs / 60).toFixed(1)} min
                </option>
              ))}
            </select>
            {ds && ds.total_secs < 300 && (
              <div className="hint" style={{ marginTop: 6, color: "var(--amber)" }}>
                △ Under 5 minutes of audio — it will train, but 10+ minutes gives noticeably
                better results.
              </div>
            )}

            <label className="field">Voice name</label>
            <input type="text" value={voiceName} placeholder="e.g. Scott — fine-tuned v1"
                   disabled={running} onChange={(e) => setVoiceName(e.target.value)} />

            <div style={{ marginTop: 18 }}>
              <button className="btn primary" onClick={start} disabled={running}>
                {running ? "Training…" : "Start fine-tune ▸"}
              </button>
            </div>
            {error && <div className="error-bar">{error}</div>}

            {job && job.state !== "idle" && (
              <div style={{ marginTop: 18 }}>
                <div className="metric-row" style={{ margin: "0 0 8px" }}>
                  <span className={`metric-chip ${job.state === "error" ? "fail" : job.state === "done" ? "pass" : "warn"}`}>
                    {job.state}
                  </span>
                  {job.stage && <span className="metric-chip neutral">{STAGE_LABELS[job.stage] || job.stage}</span>}
                </div>
                <div className="progress-track">
                  <div className="progress-fill" style={{ width: `${(job.progress * 100).toFixed(0)}%` }} />
                </div>
                <div className="hint" style={{ marginTop: 6 }}>{job.message}</div>
                {running && job.log_tail?.length > 0 && (
                  <pre className="log-tail">{job.log_tail.join("\n")}</pre>
                )}
                {job.state === "done" && (
                  <div className="hint" style={{ marginTop: 8, color: "var(--green)" }}>
                    ✓ Find your fine-tuned voice in the Voices tab and take it to Generate.
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="panel">
            <span className="panel-label">Training settings</span>
            <Slider name="SoVITS epochs" value={sovitsEpochs} min={1} max={25} step={1}
                    onChange={setSovitsEpochs} format={(v) => `${v}`}
                    hint="Timbre model. 8 is a good default; more ≠ always better." />
            <Slider name="GPT epochs" value={gptEpochs} min={1} max={50} step={1}
                    onChange={setGptEpochs} format={(v) => `${v}`}
                    hint="Prosody model. 15 is a good default." />
            <div className="hint" style={{ marginTop: 14 }}>
              Rough CPU time on this Mac: ~10-25 min per SoVITS epoch and ~2-5 min per GPT
              epoch for a 10-minute dataset. Defaults ≈ overnight. You can keep using
              instant voices while it runs.
            </div>
          </div>
        </div>
      )}
    </>
  );
}
