"use client";

import { useEffect, useState } from "react";
import { api, type AIConfig } from "@/lib/api";
import { getFallback, getModel, setFallback, setModel } from "@/lib/store";

export default function AIPage() {
  const [models, setModels] = useState<AIConfig[]>([]);
  const [selected, setSelected] = useState("");
  const [fallback, setFb] = useState(false);
  const [queue, setQueue] = useState<{ active: boolean; queued: number; max_concurrency: number } | null>(null);
  const [health, setHealth] = useState<any>(null);

  useEffect(() => {
    api.aiModels().then((m) => {
      setModels(m);
      setSelected(getModel() || m[0]?.id || "");
    }).catch(() => {});
    setFb(getFallback());
    const iv = setInterval(() => {
      api.aiQueue().then(setQueue).catch(() => {});
      fetch("/health").then((r) => r.json()).then(setHealth).catch(() => {});
    }, 5000);
    api.aiQueue().then(setQueue).catch(() => {});
    fetch("/health").then((r) => r.json()).then(setHealth).catch(() => {});
    return () => clearInterval(iv);
  }, []);

  const localModels = models.filter((m) => m.local);
  const cloudModels = models.filter((m) => !m.local);

  return (
    <div>
      <h1 className="page-title">AI</h1>

      <div className="grid grid-2" style={{ marginBottom: 14 }}>
        <div className="card">
          <div className="card-title">Preferred AI Model</div>
          <select
            value={selected}
            onChange={(e) => { setSelected(e.target.value); setModel(e.target.value); }}
            style={{ background: "var(--panel2)", border: "1px solid var(--border)", color: "var(--text)", padding: "8px 10px", borderRadius: 6, width: "100%" }}
          >
            {localModels.length > 0 && <optgroup label="LOCAL">{localModels.map((m) => (
              <option key={m.id} value={m.id}>{m.name}</option>
            ))}</optgroup>}
            {cloudModels.length > 0 && <optgroup label="CLOUD">{cloudModels.map((m) => (
              <option key={m.id} value={m.id}>{m.name}</option>
            ))}</optgroup>}
          </select>
          <div className="muted" style={{ marginTop: 8, fontSize: 11 }}>
            Model dipilih otomatis digunakan untuk Analyze, Chat, Summarize, dan Explain Financials.
          </div>
        </div>
        <div className="card">
          <div className="card-title">Local AI Queue</div>
          <div>
            {queue ? (
              <>
                <div>Active: <strong>{queue.active ? "Yes" : "No"}</strong></div>
                <div>Queued: <strong>{queue.queued}</strong></div>
                <div>Max concurrency: <strong>{queue.max_concurrency}</strong> (1 Ollama inference on CPU)</div>
              </>
            ) : <div className="muted">Memuat…</div>}
          </div>
          <div style={{ marginTop: 10 }}>
            <label style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 13 }}>
              <input type="checkbox" checked={fallback} onChange={(e) => { setFallback(e.target.checked); setFb(e.target.checked); }} />
              Allow AI fallback (auto-switch ke cloud saat model local gagal)
            </label>
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-title">System Health</div>
        <div className="stat-strip">
          <div className="stat">
            <div className="label">Backend</div>
            <div className="value">{health ? health.status : "-"}</div>
          </div>
          <div className="stat">
            <div className="label">Database</div>
            <div className="value">{health ? health.database : "-"}</div>
          </div>
          <div className="stat">
            <div className="label">9Router</div>
            <div className="value">{health ? health.nine_router : "-"}</div>
          </div>
          <div className="stat">
            <div className="label">Ollama</div>
            <div className="value">{health ? health.ollama : "-"}</div>
          </div>
        </div>
      </div>
    </div>
  );
}