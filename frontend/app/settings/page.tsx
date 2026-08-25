"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { getFallback, getModel, setFallback } from "@/lib/store";

export default function SettingsPage() {
  const [model, setModelState] = useState("");

  const [health, setHealth] = useState<any>(null);
  const [fallback, setFallbackState] = useState(false);

  useEffect(() => {
    setModelState(getModel() || "");
    setFallbackState(getFallback());
    fetch("/health").then((r) => r.json()).then(setHealth).catch(() => {});
  }, []);

  return <div>
    <h1 className="page-title">Settings</h1>
    <div className="grid grid-2">
      <div className="card">
        <div className="card-title">AI Settings</div>
        <div style={{ marginBottom: 12 }}>
          <div className="muted" style={{ marginBottom: 4 }}>Default AI Model</div>
          <input value={model} onChange={(e) => setModelState(e.target.value)} disabled style={{ background: "var(--panel2)", border: "1px solid var(--border)", color: "var(--text)", padding: "7px 10px", borderRadius: 6, width: "100%" }} />
          <div className="muted" style={{ fontSize: 11, marginTop: 4 }}>Ubah lewat selector model di top bar — preferensi disimpan di browser.</div>
        </div>
        <label style={{ display: "flex", gap: 8, alignItems: "center" }}><input type="checkbox" checked={fallback} onChange={(e) => { setFallbackState(e.target.checked); setFallback(e.target.checked); }} /> Allow AI fallback</label>
      </div>
      <div className="card">
        <div className="card-title">Infrastructure</div>
        <table><tbody><tr><td className="muted">Backend API</td><td>127.0.0.1:8200</td></tr><tr><td className="muted">Frontend</td><td>127.0.0.1:3100 (Next.js)</td></tr><tr><td className="muted">9Router</td><td>127.0.0.1:20128</td></tr><tr><td className="muted">Ollama</td><td>127.0.0.1:11434 (localhost only)</td></tr><tr><td className="muted">PostgreSQL</td><td>127.0.0.1:5432 (db: stocks)</td></tr><tr><td className="muted">Health</td><td>{health ? `${health.status} · db ${health.database} · 9router ${health.nine_router} · ollama ${health.ollama}` : "-"}</td></tr></tbody></table>
      </div>
    </div>
  </div>;
}
function Stat({ label, value }: { label: string; value: string }) { return <div className="stat"><div className="label">{label}</div><div className="value">{value}</div></div>; }
function Rows({ rows, empty }: { rows: any[]; empty: string }) { return rows.length === 0 ? <p className="muted">{empty}</p> : <div className="table-scroll"><table><thead><tr><th>Ticker</th><th>Decision</th><th>Signal</th><th>Status</th><th>Runtime</th><th>Date</th></tr></thead><tbody>{rows.map((r) => <tr key={r.id}><td className="sym-badge">{r.symbol}</td><td>{r.decision || "-"}</td><td>{r.action || "-"}</td><td>{r.status}</td><td>{r.runtime_seconds ? `${Number(r.runtime_seconds).toFixed(1)}s` : "-"}</td><td>{String(r.date || r.created_at || "").slice(0, 10)}</td></tr>)}</tbody></table></div>; }
