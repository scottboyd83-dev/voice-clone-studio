import React, { useEffect, useState } from "react";
import { api } from "../api.js";
import AudioPlayer from "./AudioPlayer.jsx";

export default function HistoryPage({ voices }) {
  const [items, setItems] = useState([]);
  const [filter, setFilter] = useState("");

  const load = () => api.listGenerations(filter || null).then(setItems).catch(() => {});
  useEffect(() => { load(); /* eslint-disable-line */ }, [filter]);

  const voiceName = (id) => voices.find((v) => v.id === id)?.name || "(deleted voice)";

  const remove = async (id) => {
    await api.deleteGeneration(id);
    load();
  };

  return (
    <>
      <h2 className="page-title">History</h2>
      <p className="page-sub">Every generation, with the exact settings that produced it.</p>

      <div style={{ marginBottom: 18, maxWidth: 320 }}>
        <select value={filter} onChange={(e) => setFilter(e.target.value)}>
          <option value="">All voices</option>
          {voices.map((v) => <option key={v.id} value={v.id}>{v.name}</option>)}
        </select>
      </div>

      {items.length === 0 ? (
        <div className="empty">
          <div className="big">Nothing here yet.</div>
          Generations land here automatically.
        </div>
      ) : (
        items.map((g) => (
          <div className="history-item" key={g.id}>
            <div className="top">
              <div className="gen-text">“{g.text}”</div>
              <div className="meta">
                {voiceName(g.voice_id)} · {new Date(g.created_at * 1000).toLocaleString()}
              </div>
            </div>
            <div className="settings-line">
              speed {g.settings.speed}× · {g.settings.nfe_step} steps · adherence{" "}
              {g.settings.cfg_strength} · seed {g.seed} · {g.duration_secs?.toFixed(1)}s
            </div>
            <AudioPlayer src={api.genAudioUrl(g.id)} />
            <div className="actions">
              <a className="btn small" style={{ textDecoration: "none" }}
                 href={api.genAudioUrl(g.id, "wav")} download>Download wav</a>
              <a className="btn small" style={{ textDecoration: "none" }}
                 href={api.genAudioUrl(g.id, "mp3")} download>mp3</a>
              <button className="btn small danger" onClick={() => remove(g.id)}>Delete</button>
            </div>
          </div>
        ))
      )}
    </>
  );
}
