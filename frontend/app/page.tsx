"use client";
import { useEffect, useRef, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function Home() {
  const [sessionId, setSessionId] = useState<string>("");
  const [datasetUri, setDatasetUri] = useState<string>("");
  const [target, setTarget] = useState<string>("");
  const [logs, setLogs] = useState<string[]>([]);
  const eventSourceRef = useRef<EventSource | null>(null);

  async function createSession() {
    const res = await fetch(`${API}/sessions`, { method: "POST" });
    const json = await res.json();
    setSessionId(json.id);
    setLogs((l) => l.concat([`session: ${json.id}`]));
  }

  async function uploadFile(file: File) {
    if (!sessionId) return alert("create session first");
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${API}/sessions/${sessionId}/upload`, {
      method: "POST",
      body: form,
    });
    const json = await res.json();
    setDatasetUri(json.dataset_uri);
    setLogs((l) => l.concat([`uploaded: ${json.filename}`]));
  }

  async function startRun() {
    if (!sessionId || !datasetUri || !target) return alert("missing fields");
    await fetch(`${API}/sessions/${sessionId}/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ goal: "profile", target, dataset_uri: datasetUri }),
    });
    if (eventSourceRef.current) eventSourceRef.current.close();
    const es = new EventSource(`${API}/sessions/${sessionId}/stream`);
    es.onmessage = (e) => setLogs((l) => l.concat([e.data]));
    eventSourceRef.current = es;
  }

  useEffect(() => {
    return () => eventSourceRef.current?.close();
  }, []);

  return (
    <main style={{ padding: 24, fontFamily: "Inter, sans-serif" }}>
      <h1>AutoML Chat Studio</h1>
      <div style={{ display: "flex", gap: 16, marginTop: 12 }}>
        <button onClick={createSession}>Create session</button>
        <input
          type="file"
          accept=".csv,text/csv"
          onChange={(e) => e.target.files && uploadFile(e.target.files[0])}
        />
        <input
          placeholder="target column"
          value={target}
          onChange={(e) => setTarget(e.target.value)}
        />
        <button onClick={startRun}>Start</button>
      </div>
      <p>session: {sessionId}</p>
      <p>dataset: {datasetUri}</p>
      <pre
        style={{
          marginTop: 16,
          background: "#111",
          color: "#0f0",
          padding: 12,
          height: 320,
          overflow: "auto",
        }}
      >
        {logs.join("\n\n")}
      </pre>
    </main>
  );
}


