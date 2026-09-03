"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { getFallback, getModel, setFallback } from "@/lib/store";

function stamp(value?: string) {
  return value ? new Date(value).toLocaleString("id-ID", { timeZone: "Asia/Jakarta" }) : "—";
}

export default function SettingsPage() {
  const [model, setModelState] = useState("");
  const [fallback, setFb] = useState(false);
  const [health, setHealth] = useState<any>(null);
  const [deliveries, setDeliveries] = useState<any>(null);
  const [deliveryError, setDeliveryError] = useState("");

  useEffect(() => {
    setModelState(getModel() || "");
    setFb(getFallback());
    fetch("/health").then((r) => r.json()).then(setHealth).catch(() => {});
    const load = () => api.notificationStatus().then(setDeliveries).then(() => setDeliveryError("")).catch(() => setDeliveryError("Delivery health unavailable."));
    load(); const timer = window.setInterval(load, 30000); return () => clearInterval(timer);
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
        <label style={{ display: "flex", gap: 8, alignItems: "center" }}><input type="checkbox" checked={fallback} onChange={(e) => { setFallback(e.target.checked); setFb(e.target.checked); }} />Allow AI fallback</label>
      </div>
      <div className="card">
        <div className="card-title">Infrastructure</div>
        <table><tbody>
          <tr><td className="muted">Backend API</td><td>127.0.0.1:8200</td></tr><tr><td className="muted">Frontend</td><td>Next.js</td></tr><tr><td className="muted">9Router</td><td>127.0.0.1:20128</td></tr><tr><td className="muted">Ollama</td><td>127.0.0.1:11434 (localhost only)</td></tr><tr><td className="muted">PostgreSQL</td><td>127.0.0.1:5432 (db: stocks)</td></tr><tr><td className="muted">Health</td><td>{health ? `${health.status} · db ${health.database} · 9router ${health.nine_router} · ollama ${health.ollama}` : "-"}</td></tr>
        </tbody></table>
      </div>
    </div>
    <div className="card" style={{ marginTop: 12 }}>
      <div className="card-title">NOTIFICATION DELIVERY HEALTH · {deliveries?.owner || "HERMES"}</div>
      {deliveryError && <div className="terminal-error">{deliveryError}</div>}
      {!deliveries && !deliveryError && <div className="terminal-loading"><span>LOADING DELIVERY STATUS</span></div>}
      {deliveries && <div className="table-scroll"><table className="dense-table"><thead><tr><th>TYPE</th><th>DATE / CYCLE</th><th>STATUS</th><th className="num">ATTEMPTS</th><th>DELIVERED</th><th>LAST ERROR</th></tr></thead><tbody>{deliveries.data?.length ? deliveries.data.map((row: any) => <tr key={row.id}><td>{row.message_type}</td><td>{row.target_date} · {row.cycle}</td><td className={row.status === "SENT" ? "pos" : row.status === "FAILED" ? "neg" : ""}>{row.status}</td><td className="num">{row.attempt_count}</td><td>{stamp(row.sent_at)}</td><td className="neg">{row.last_error || "—"}</td></tr>) : <tr><td colSpan={6} className="terminal-empty">NO DELIVERY RECORDS YET</td></tr>}</tbody></table></div>}
    </div>
  </div>;
}
