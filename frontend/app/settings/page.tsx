"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { getFallback, getModel, setFallback } from "@/lib/store";

export default function SettingsPage() {
  const [model, setModelState] = useState("");
  const [fallback, setFb] = useState(false);
  const [health, setHealth] = useState<any>(null);
  const [status, setStatus] = useState<any>(null);
  const [stocks, setStocks] = useState<any[]>([]);
  const [history, setHistory] = useState<any[]>([]);
  const [jobs, setJobs] = useState<any[]>([]);
  const [ticker, setTicker] = useState("");
  const [quick, setQuick] = useState("");
  const [deep, setDeep] = useState("");
  const [error, setError] = useState("");

  const loadAI = () => Promise.all([api.aiTradingStatus(), api.aiTradingHistory(), api.aiTradingJobs()])
    .then(([s, h, j]) => { setStatus(s); setQuick((v) => v || s.quick_model); setDeep((v) => v || s.deep_model); setHistory(h); setJobs(j); })
    .catch((e) => setError(e.message));

  useEffect(() => {
    setModelState(getModel() || "");
    setFb(getFallback());
    fetch("/health").then((r) => r.json()).then(setHealth).catch(() => {});
    api.stocks(undefined, undefined).then(setStocks).catch(() => {});
    loadAI();
    const timer = setInterval(loadAI, 10000);
    return () => clearInterval(timer);
  }, []);

  const run = async () => {
    try { await api.aiTradingAnalyze(ticker, quick, deep); loadAI(); }
    catch (e: any) { setError(e.message); }
  };

  const models = (status?.available_models || []).filter((m: string) => m.startsWith("cx/") || m.startsWith("gemini/") || m.startsWith("openai/"));

  return <div>
    <h1 className="page-title">Settings</h1>
    {error && <div className="analysis-err">{error}</div>}
    <div className="grid grid-2">
      <div className="card">
        <div className="card-title">AI Settings</div>
        <div style={{ marginBottom: 12 }}>
          <div className="muted" style={{ marginBottom: 4 }}>Default AI Model</div>
          <input value={model} onChange={(e) => setModelState(e.target.value)} disabled style={{ background: "var(--panel2)", border: "1px solid var(--border)", color: "var(--text)", padding: "7px 10px", borderRadius: 6, width: "100%" }} />
          <div className="muted" style={{ fontSize: 11, marginTop: 4 }}>Ubah lewat selector model di top bar — preferensi disimpan di browser.</div>
        </div>
        <label style={{ display: "flex", gap: 8, alignItems: "center" }}><input type="checkbox" checked={fallback} onChange={(e) => { setFallback(e.target.checked); setFb(e.target.checked); }} /> Allow AI fallback</label>
      </div>
      <div className="card">
        <div className="card-title">Infrastructure</div>
        <table><tbody><tr><td className="muted">Backend API</td><td>127.0.0.1:8200</td></tr><tr><td className="muted">Frontend</td><td>127.0.0.1:3100 (Next.js)</td></tr><tr><td className="muted">9Router</td><td>127.0.0.1:20128</td></tr><tr><td className="muted">Ollama</td><td>127.0.0.1:11434 (localhost only)</td></tr><tr><td className="muted">PostgreSQL</td><td>127.0.0.1:5432 (db: stocks)</td></tr><tr><td className="muted">Health</td><td>{health ? `${health.status} · db ${health.database} · 9router ${health.nine_router} · ollama ${health.ollama}` : "-"}</td></tr></tbody></table>
      </div>
    </div>
    <div className="auto-trade-head" style={{ marginTop: 24 }}><div><h2 className="section-title">AI Trading</h2><p className="muted">TradingAgents research and paper-trading signals.</p></div><div className="paper-label">PAPER TRADING ONLY</div></div>
    <div className="grid grid-4 auto-summary"><Stat label="Status" value={status?.enabled ? "Enabled" : "Disabled"} /><Stat label="9Router" value={status?.nine_router_reachable ? "Connected" : "Unavailable"} /><Stat label="Quick model" value={status?.quick_model || "-"} /><Stat label="Deep model" value={status?.deep_model || "-"} /></div>
    <div className="card auto-actions"><div><strong>Manual analysis</strong><p className="muted">Runs asynchronously and does not open a trade.</p></div><div className="action-buttons"><select className="ai-select ai-ticker" aria-label="IDX stock" value={ticker} onChange={(e) => setTicker(e.target.value)}><option value="">Select stock</option>{stocks.map((stock: any) => <option key={stock.symbol} value={stock.symbol}>{stock.symbol} — {stock.company_name}</option>)}</select><select className="ai-select" aria-label="Quick model" value={quick} onChange={(e) => setQuick(e.target.value)}>{models.map((m: string) => <option key={m}>{m}</option>)}</select><select className="ai-select" aria-label="Deep model" value={deep} onChange={(e) => setDeep(e.target.value)}>{models.map((m: string) => <option key={m}>{m}</option>)}</select><button className="btn btn-primary" disabled={!status?.enabled || !ticker} onClick={run}>Run analysis</button></div></div>
    <div className="card"><div className="card-title">Current jobs</div><Rows rows={jobs} empty="No active jobs." /></div>
    <div className="card"><div className="card-title">Analysis history</div><Rows rows={history} empty="No analyses yet." /></div>
  </div>;
}
function Stat({ label, value }: { label: string; value: string }) { return <div className="stat"><div className="label">{label}</div><div className="value">{value}</div></div>; }
function Rows({ rows, empty }: { rows: any[]; empty: string }) { return rows.length === 0 ? <p className="muted">{empty}</p> : <div className="table-scroll"><table><thead><tr><th>Ticker</th><th>Decision</th><th>Signal</th><th>Status</th><th>Runtime</th><th>Date</th></tr></thead><tbody>{rows.map((r) => <tr key={r.id}><td className="sym-badge">{r.symbol}</td><td>{r.decision || "-"}</td><td>{r.action || "-"}</td><td>{r.status}</td><td>{r.runtime_seconds ? `${Number(r.runtime_seconds).toFixed(1)}s` : "-"}</td><td>{String(r.date || r.created_at || "").slice(0, 10)}</td></tr>)}</tbody></table></div>; }
