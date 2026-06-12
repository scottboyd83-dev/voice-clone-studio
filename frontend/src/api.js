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

  // recording studio
  listScripts: () => fetch("/api/studio/scripts").then(check),
  createTake: (scriptId, blob) => {
    const fd = new FormData();
    fd.append("script_id", scriptId);
    fd.append("audio_file", blob, "take.webm");
    return fetch("/api/studio/takes", { method: "POST", body: fd }).then(check);
  },
  listTakes: () => fetch("/api/studio/takes").then(check),
  deleteTake: (id) => fetch(`/api/studio/takes/${id}`, { method: "DELETE" }).then(check),
  takeAudioUrl: (id) => `/api/studio/takes/${id}/audio`,
  studioStats: () => fetch("/api/studio/stats").then(check),

  // dataset
  datasetBuild: () => fetch("/api/dataset/build", { method: "POST" }).then(check),
  datasetStatus: () => fetch("/api/dataset/status").then(check),
  listDatasets: () => fetch("/api/datasets").then(check),

  // fine-tuning
  trainStart: (payload) =>
    fetch("/api/train", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }).then(check),
  trainStatus: () => fetch("/api/train/status").then(check),

  // speech-to-speech conversion
  convertStatus: () => fetch("/api/convert/status").then(check),
  convertWarmup: () => fetch("/api/convert/warmup", { method: "POST" }).then(check),
  convert: ({ voiceId, blob, filename, ...settings }) => {
    const fd = new FormData();
    fd.append("voice_id", voiceId);
    for (const [k, v] of Object.entries(settings)) fd.append(k, v);
    fd.append("audio_file", blob, filename || "recording.webm");
    return fetch("/api/convert", { method: "POST", body: fd }).then(check);
  },
  listConversions: (voiceId) =>
    fetch(`/api/conversions${voiceId ? `?voice_id=${voiceId}` : ""}`).then(check),
  deleteConversion: (id) => fetch(`/api/conversions/${id}`, { method: "DELETE" }).then(check),
  convAudioUrl: (id, which = "output") => `/api/conversions/${id}/audio?which=${which}`,
};
