// Thin API client. Vite proxies /api to the FastAPI backend on :8000.

async function check(res) {
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch { /* not json */ }
    throw new Error(detail);
  }
  return res.json();
}

export const api = {
  status: () => fetch("/api/status").then(check),
  warmup: () => fetch("/api/warmup", { method: "POST" }).then(check),

  listVoices: () => fetch("/api/voices").then(check),
  createVoice: ({ name, description, refText, blob, filename }) => {
    const fd = new FormData();
    fd.append("name", name);
    fd.append("description", description || "");
    fd.append("ref_text", refText || "");
    fd.append("audio_file", blob, filename);
    return fetch("/api/voices", { method: "POST", body: fd }).then(check);
  },
  deleteVoice: (id) => fetch(`/api/voices/${id}`, { method: "DELETE" }).then(check),
  voiceRefUrl: (id) => `/api/voices/${id}/reference`,

  generate: (payload) =>
    fetch("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }).then(check),
  listGenerations: (voiceId) =>
    fetch(`/api/generations${voiceId ? `?voice_id=${voiceId}` : ""}`).then(check),
  deleteGeneration: (id) => fetch(`/api/generations/${id}`, { method: "DELETE" }).then(check),
  genAudioUrl: (id, format = "wav") => `/api/generations/${id}/audio?format=${format}`,
};
