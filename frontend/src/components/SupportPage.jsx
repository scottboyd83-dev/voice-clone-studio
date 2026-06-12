import React, { useState } from "react";

// Renders the standalone docs/ pages as-is; the backend serves them verbatim
// so docs/ stays the single source of truth (also openable/printable directly).
const DOCS = [
  { file: "user-guide.html", label: "Operator's Guide" },
  { file: "architecture.html", label: "Architecture" },
];

export default function SupportPage() {
  const [doc, setDoc] = useState(DOCS[0].file);

  return (
    <>
      <div style={{ display: "flex", alignItems: "baseline", gap: 14, flexWrap: "wrap" }}>
        <h2 className="page-title" style={{ marginBottom: 0 }}>Support</h2>
        <div style={{ display: "flex", gap: 8, marginLeft: "auto" }}>
          {DOCS.map((d) => (
            <button
              key={d.file}
              className={`btn small ${doc === d.file ? "primary" : ""}`}
              onClick={() => setDoc(d.file)}
            >
              {d.label}
            </button>
          ))}
          <a
            className="btn small"
            href={`/api/docs/${doc}`}
            target="_blank"
            rel="noreferrer"
            style={{ textDecoration: "none" }}
          >
            Open in new tab ↗
          </a>
        </div>
      </div>

      <iframe
        key={doc}
        src={`/api/docs/${doc}`}
        title="Voice Clone Studio documentation"
        style={{
          width: "100%",
          height: "calc(100vh - 230px)",
          minHeight: 480,
          marginTop: 16,
          border: "1px solid var(--line)",
          borderRadius: 6,
          background: "var(--bg)",
        }}
      />
    </>
  );
}
