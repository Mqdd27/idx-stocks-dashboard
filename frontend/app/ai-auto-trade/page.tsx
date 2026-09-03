"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { usePolling } from "@/lib/usePolling";

export default function AIAutoTradePage() {
  const [status, setStatus] = useState<any>(null);
  const [runs, setRuns] = useState<any[]>([]);
  const [models, setModels] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = () => Promise.all([api.aiAutoTradeStatus(), api.aiAutoTradeRuns(), api.aiTradingStatus()])
    .then(([s, r, ai]) => { setStatus(s); setRuns(r); setModels(ai.available_models || []); })
    .catch((e) => setError(e.message));

  usePolling(load, 10000);

  const update = async (patch: Record<string, unknown>) => {
    setBusy(true); setError("");
    try { const result = await api.aiAutoTradeConfig(patch); setStatus((current: any) => current ? { ...current, ...result } : current); await load(); }
    catch (e: any) { setError(e.message); }
    finally { setBusy(false); }
  };
  const run = async () => {
    setBusy(true); setError("");
    try { await api.aiAutoTradeRun(); await load(); }
    catch (e: any) { setError(e.message); }
    finally { setBusy(false); }
  };
  const choices = models.filter((m) => m === "Com" || m.startsWith("cx/") || m.startsWith("gemini/") || m.startsWith("openai/"));
  const canRun = status?.enabled && status?.ai_trading_enabled && status?.paper_trading_enabled && status?.market?.is_open && !status?.active_run_id;

  return <div>
    <div className="auto-trade-head"><div><h1 className="page-title">AI Auto Trade</h1><p className="muted">Scanner teknikal → TradingAgents → validasi deterministik → posisi paper.</p></div><div className="paper-label">PAPER TRADING ONLY</div></div>
    {error && <div className="analysis-err">{error}</div>}
    <div className="grid grid-4 auto-summary">
      <Stat label="AI Auto Trade" value={status?.enabled ? "Aktif" : "Nonaktif"}/>
      <Stat label="Pasar IDX" value={status?.market?.status || "-"}/>
      <Stat label="Run aktif" value={status?.active_run_id ? `#${status.active_run_id}` : "Tidak ada"}/>
      <Stat label="Posisi paper" value={String(status?.open_positions ?? "-")}/>
    </div>
    <div className="card ai-auto-config">
      <div><strong>Konfigurasi pipeline</strong><p className="muted">Maksimal satu analisis berjalan; setiap kandidat diproses berurutan.</p></div>
      <label className="ai-auto-toggle"><input type="checkbox" checked={Boolean(status?.enabled)} disabled={busy} onChange={(e) => update({ enabled: e.target.checked })}/> Aktif</label>
      <label>Kandidat<select className="ai-select" value={status?.max_candidates || 3} onChange={(e) => update({ max_candidates: Number(e.target.value) })}>{[1,2,3,4,5].map((n) => <option key={n}>{n}</option>)}</select></label>
      <label>Quick model<select className="ai-select" value={status?.quick_model || ""} onChange={(e) => update({ quick_model: e.target.value })}>{choices.map((m) => <option key={m}>{m}</option>)}</select></label>
      <label>Deep model<select className="ai-select" value={status?.deep_model || ""} onChange={(e) => update({ deep_model: e.target.value })}>{choices.map((m) => <option key={m}>{m}</option>)}</select></label>
      <button className="btn btn-primary" disabled={!canRun || busy} onClick={run}>{status?.active_run_id ? "Sedang berjalan" : "Jalankan sekarang"}</button>
    </div>
    {(!status?.ai_trading_enabled || !status?.paper_trading_enabled) && <div className="card paper-notice"><strong>Belum siap</strong><span>AI Trading dan Paper Bot harus aktif sebelum pipeline dapat membuka posisi simulasi.</span></div>}
    <div className="card"><div className="card-title">Riwayat Pipeline</div>{runs.length === 0 ? <p className="muted">Belum ada run.</p> : <div className="table-scroll"><table><thead><tr><th>Run</th><th>Status</th><th>Kandidat</th><th>Trade</th><th>Mulai</th><th>Selesai</th></tr></thead><tbody>{runs.map((r) => <tr key={r.id}><td>#{r.id}</td><td>{r.status}</td><td>{r.candidates?.map((c:any) => c.symbol).join(", ") || "-"}</td><td>{r.trades_created}</td><td>{stamp(r.started_at || r.created_at)}</td><td>{stamp(r.finished_at)}</td></tr>)}</tbody></table></div>}</div>
    {runs[0]?.results?.length > 0 && <div className="card"><div className="card-title">Hasil Run Terbaru #{runs[0].id}</div><div className="table-scroll"><table><thead><tr><th>Ticker</th><th>Keputusan AI</th><th>Sinyal</th><th>Trade</th><th>Alasan gate</th></tr></thead><tbody>{runs[0].results.map((r:any) => <tr key={r.symbol}><td className="sym-badge">{r.symbol}</td><td>{r.decision || "-"}</td><td>{r.action}</td><td className={r.trade_opened ? "pos" : "muted"}>{r.trade_opened ? "Dibuka" : "Tidak"}</td><td>{r.reason}</td></tr>)}</tbody></table></div></div>}
  </div>;
}

function Stat({label,value}:{label:string;value:string}) { return <div className="stat"><div className="label">{label}</div><div className="value">{value}</div></div>; }
function stamp(value?: string | null) { return value ? new Date(value).toLocaleString("id-ID") : "-"; }
