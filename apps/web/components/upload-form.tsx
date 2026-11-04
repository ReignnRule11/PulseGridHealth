"use client";

import { useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function UploadForm() {
  const [file, setFile] = useState<File | null>(null);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) return;
    setBusy(true);
    setMessage("");
    try {
      const data = new FormData();
      data.append("file", file);
      const response = await fetch(`${API}/api/v1/observations/import`, { method: "POST", body: data });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail ?? "Import failed");
      setMessage(`Imported ${result.accepted}; duplicates ${result.duplicates}; rejected ${result.rejected}; new candidate alerts ${result.alerts_created}.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Import failed");
    } finally {
      setBusy(false);
    }
  }

  return <form onSubmit={submit} className="upload">
    <label htmlFor="dataset">Import aggregate CSV dataset</label>
    <input id="dataset" type="file" accept=".csv,text/csv" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
    <button type="submit" disabled={!file || busy}>{busy ? "Importing…" : "Import CSV"}</button>
    <p aria-live="polite">{message}</p>
  </form>;
}
