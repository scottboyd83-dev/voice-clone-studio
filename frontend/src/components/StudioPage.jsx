import React, { useEffect, useRef, useState } from "react";
import { api } from "../api.js";
import AudioPlayer from "./AudioPlayer.jsx";
import Recorder from "./Recorder.jsx";

const GOAL_MINS = 15; // GPT-SoVITS sweet spot: 10-20 min of clean speech

export default function StudioPage() {
  const [scripts, setScripts] = useState([]);
  const [stats, setStats] = useState(null);
  const [idx, setIdx] = useState(null); // current prompt index
  const [review, setReview] = useState(null); // take being reviewed after recording
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);

  const refresh = async () => {
    const [s, st] = await Promise.all([api.listScripts(), api.studioStats()]);
    setScripts(s);
    setStats(st);
    // land on the first un-recorded prompt on first load
    setIdx((cur) => cur ?? Math.max(0, s.findIndex((x) => x.takes === 0)));
    return s;
  };

  useEffect(() => { refresh().catch(() => {}); }, []);

  const current = idx !== null ? scripts[idx] : null;

  const onRecorded = async (blob) => {
    setUploading(true);
    setError(null);
    try {
      const take = await api.createTake(current.script_id, blob);
      setReview(take);
      await refresh();
    } catch (e) {
      setError(e.message);
    } finally {
      setUploading(false);
    }
  };

  const retake = async () => {
    if (review) await api.deleteTake(review.id).catch(() => {});
    setReview(null);
    refresh();
  };

  const keepAndNext = () => {
    setReview(null);
    // advance to next prompt without a take, wrapping; stay if all covered
    const next = scripts.findIndex((s, i) => i > idx && s.takes === 0);
    setIdx(next !== -1 ? next : Math.min(idx + 1, scripts.length - 1));
  };

  const mins = stats ? stats.total_secs / 60 : 0;
  const pct = Math.min(100, (mins / GOAL_MINS) * 100);

  return (
    <>
      <h2 className="page-title">Recording Studio</h2>
      <p className="page-sub">
        Read prompts, pass the quality check, build a training dataset. Aim for ~{GOAL_MINS} minutes —
        that's the sweet spot for fine-tuning. Multiple takes of the same prompt all count.
      </p>

      {stats && (
        <div className="panel" style={{ marginBottom: 18 }}>
          <span className="panel-label">Session progress</span>
          <div className="studio-stats">
            <div className="stat"><b>{stats.takes}</b><span>takes kept</span></div>
            <div className="stat"><b>{mins.toFixed(1)}</b><span>minutes recorded</span></div>
            <div className="stat"><b>{stats.scripts_covered}/{stats.scripts_total}</b><span>prompts covered</span></div>
          </div>
          <div className="progress-track" title={`${pct.toFixed(0)}% of ${GOAL_MINS} min goal`}>
            <div className="progress-fill" style={{ width: `${pct}%` }} />
          </div>
        </div>
      )}

      {current && (
        <div className="panel">
          <span className="panel-label">
            Prompt {idx + 1} / {scripts.length}
          </span>
          <div className="prompt-head">
            <span className={`cat-badge ${current.category}`}>{current.category}</span>
            {current.takes > 0 && <span className="hint">{current.takes} take(s) kept ✓</span>}
            <span style={{ flex: 1 }} />
            <button className="btn small" disabled={idx === 0}
                    onClick={() => { setReview(null); setIdx(idx - 1); }}>← Prev</button>
            <button className="btn small" disabled={idx >= scripts.length - 1}
                    onClick={() => { setReview(null); setIdx(idx + 1); }}>Skip →</button>
          </div>

          <div className="script-card">
            <div className="label">Read this aloud{current.category === "expressive" ? " — with feeling" : ""}</div>
            <div className="text">{current.text}</div>
          </div>

          {!review ? (
            <>
              <Recorder key={current.script_id} onRecorded={onRecorded} />
              {uploading && <div className="hint" style={{ marginTop: 8 }}>Analyzing take…</div>}
            </>
          ) : (
            <TakeReview take={review} onKeep={keepAndNext} onRetake={retake} />
          )}
          {error && <div className="error-bar">{error}</div>}
        </div>
      )}

      <DatasetPanel stats={stats} />
      <RecentTakes onChanged={refresh} />
    </>
  );
}

function TakeReview({ take, onKeep, onRetake }) {
  const m = take.metrics || {};
  return (
    <div>
      <div className="metric-row">
        <span className={`metric-chip ${m.level}`}>
          {m.level === "pass" ? "✓ quality pass" : m.level === "warn" ? "△ check quality" : "✗ quality fail"}
        </span>
        <span className="metric-chip neutral">{m.duration_secs?.toFixed(1)}s</span>
        <span className="metric-chip neutral">SNR {m.snr_db?.toFixed(0)} dB</span>
        <span className="metric-chip neutral">clip {m.clip_pct?.toFixed(2)}%</span>
      </div>
      {m.issues?.length > 0 && (
        <ul className="issue-list">
          {m.issues.map((i, k) => <li key={k}>{i}</li>)}
        </ul>
      )}
      <div style={{ margin: "12px 0" }}>
        <AudioPlayer src={api.takeAudioUrl(take.id)} />
      </div>
      <div style={{ display: "flex", gap: 10 }}>
        <button className="btn primary" onClick={onKeep}>
          {m.level === "fail" ? "Keep anyway & next" : "Keep & next ▸"}
        </button>
        <button className="btn" onClick={onRetake}>Retake</button>
      </div>
    </div>
  );
}

function DatasetPanel({ stats }) {
  const [job, setJob] = useState(null);
  const [error, setError] = useState(null);
  const timer = useRef(null);

  const poll = () => api.datasetStatus().then((s) => {
    setJob(s);
    if (s.state !== "running" && timer.current) {
      clearInterval(timer.current);
      timer.current = null;
    }
  }).catch(() => {});

  useEffect(() => {
    poll();
    return () => timer.current && clearInterval(timer.current);
  }, []);

  const build = async () => {
    setError(null);
    try {
      await api.datasetBuild();
      timer.current = setInterval(poll, 1500);
      poll();
    } catch (e) {
      setError(e.message);
    }
  };

  const running = job?.state === "running";
  const manifest = job?.manifest;

  return (
    <div className="panel" style={{ marginTop: 18 }}>
      <span className="panel-label">Training dataset</span>
      <div style={{ display: "flex", gap: 14, alignItems: "center", flexWrap: "wrap" }}>
        <button className="btn primary" onClick={build} disabled={running || !stats?.takes}>
          {running ? "Building…" : "Build dataset ▸"}
        </button>
        <span className="hint">
          Normalizes every kept take, verifies it with Whisper, and exports a GPT-SoVITS-ready
          filelist. Misread takes are excluded automatically.
        </span>
      </div>

      {running && (
        <div style={{ marginTop: 14 }}>
          <div className="progress-track">
            <div className="progress-fill" style={{ width: `${(job.progress * 100).toFixed(0)}%` }} />
          </div>
          <div className="hint" style={{ marginTop: 6 }}>{job.message}</div>
        </div>
      )}
      {job?.state === "error" && <div className="error-bar">{job.message}</div>}
      {error && <div className="error-bar">{error}</div>}

      {manifest && !running && (
        <div className="manifest">
          <div className="hint" style={{ marginBottom: 4 }}>
            Latest build · {new Date(manifest.created_at * 1000).toLocaleString()}
          </div>
          <div className="metric-row">
            <span className="metric-chip pass">{manifest.segments} segments</span>
            <span className="metric-chip neutral">{(manifest.total_secs / 60).toFixed(1)} min</span>
            {manifest.flagged.length > 0 && (
              <span className="metric-chip warn">{manifest.flagged.length} flagged</span>
            )}
            {manifest.excluded.length > 0 && (
              <span className="metric-chip fail">{manifest.excluded.length} excluded</span>
            )}
          </div>
          <div className="hint" style={{ marginTop: 6 }}>
            → <code>{manifest.path}</code>
          </div>
          {manifest.flagged.length > 0 && (
            <details style={{ marginTop: 8 }}>
              <summary className="hint" style={{ cursor: "pointer" }}>
                Flagged takes (kept, but Whisper heard something different)
              </summary>
              <ul className="issue-list">
                {manifest.flagged.map((f) => (
                  <li key={f.id}>
                    expected “{f.text}” — heard “{f.heard}” ({(f.score * 100).toFixed(0)}%)
                  </li>
                ))}
              </ul>
            </details>
          )}
        </div>
      )}
    </div>
  );
}

function RecentTakes({ onChanged }) {
  const [takes, setTakes] = useState([]);
  const [open, setOpen] = useState(false);

  const load = () => api.listTakes().then(setTakes).catch(() => {});
  useEffect(() => { if (open) load(); }, [open]);

  const remove = async (id) => {
    await api.deleteTake(id);
    load();
    onChanged();
  };

  return (
    <div className="panel" style={{ marginTop: 18 }}>
      <span className="panel-label">Takes</span>
      <button className="btn small" onClick={() => setOpen(!open)}>
        {open ? "Hide takes" : "Browse all takes"}
      </button>
      {open && takes.map((t) => (
        <div className="history-item" key={t.id} style={{ marginTop: 12 }}>
          <div className="top">
            <div className="gen-text">“{t.text}”</div>
            <div className="meta">
              {t.duration_secs?.toFixed(1)}s · {t.metrics?.level}
              {t.verify_score != null && ` · verify ${(t.verify_score * 100).toFixed(0)}%`}
            </div>
          </div>
          <AudioPlayer src={api.takeAudioUrl(t.id)} />
          <div className="actions">
            <button className="btn small danger" onClick={() => remove(t.id)}>Delete</button>
          </div>
        </div>
      ))}
    </div>
  );
}
