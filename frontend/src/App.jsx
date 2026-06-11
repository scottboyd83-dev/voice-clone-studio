import React, { useEffect, useState } from "react";
import { api } from "./api.js";
import VoiceLibrary from "./components/VoiceLibrary.jsx";
import GeneratePage from "./components/GeneratePage.jsx";
import HistoryPage from "./components/HistoryPage.jsx";

const TABS = [
  { id: "voices", label: "Voices" },
  { id: "generate", label: "Generate" },
  { id: "history", label: "History" },
];

export default function App() {
  const [tab, setTab] = useState("voices");
  const [voices, setVoices] = useState([]);
  const [modelLoaded, setModelLoaded] = useState(false);
  const [warming, setWarming] = useState(false);
  // voice preselected when jumping from library to generate
  const [activeVoiceId, setActiveVoiceId] = useState(null);

  const refreshVoices = () => api.listVoices().then(setVoices).catch(() => {});

  useEffect(() => {
    refreshVoices();
    // kick off model load immediately so first generation isn't cold
    api.status().then((s) => {
      setModelLoaded(s.model_loaded);
      if (!s.model_loaded) {
        setWarming(true);
        api.warmup().catch(() => {});
      }
    }).catch(() => {});
  }, []);

  // poll status while warming
  useEffect(() => {
    if (!warming || modelLoaded) return;
    const t = setInterval(() => {
      api.status().then((s) => {
        if (s.model_loaded) { setModelLoaded(true); setWarming(false); }
      }).catch(() => {});
    }, 2000);
    return () => clearInterval(t);
  }, [warming, modelLoaded]);

  const gotoGenerate = (voiceId) => {
    setActiveVoiceId(voiceId);
    setTab("generate");
  };

  return (
    <>
      <header className="masthead">
        <div>
          <h1>Voice <span className="accent">Clone</span> Studio</h1>
          <div className="sub">Local · Private · F5-TTS on Apple Silicon</div>
        </div>
        <div className="led-status">
          <span className={`led ${modelLoaded ? "on" : warming ? "loading" : ""}`} />
          {modelLoaded ? "Engine ready" : warming ? "Loading engine…" : "Engine idle"}
        </div>
      </header>

      <nav className="tabs">
        {TABS.map((t, i) => (
          <button
            key={t.id}
            className={`tab ${tab === t.id ? "active" : ""}`}
            onClick={() => setTab(t.id)}
          >
            <span className="num">{String(i + 1).padStart(2, "0")}</span>
            {t.label}
          </button>
        ))}
      </nav>

      <main key={tab}>
        {tab === "voices" && (
          <VoiceLibrary voices={voices} onChanged={refreshVoices} onUse={gotoGenerate} />
        )}
        {tab === "generate" && (
          <GeneratePage
            voices={voices}
            initialVoiceId={activeVoiceId}
            modelLoaded={modelLoaded}
          />
        )}
        {tab === "history" && <HistoryPage voices={voices} />}
      </main>

      <footer className="colophon">
        <span>All audio stays on this machine</span>
        <span>Phase 1 · Instant clone</span>
      </footer>
    </>
  );
}
