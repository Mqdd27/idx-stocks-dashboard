"use client";

import { useEffect, useState } from "react";
import { api, PaperCandidate, PaperLog, PaperSummary, PaperTrade } from "@/lib/api";

const money = (value?: number | null) => value == null ? "-" : `Rp ${value.toLocaleString("id-ID", { maximumFractionDigits: 0 })}`;
const number = (value?: number | null) => value == null ? "-" : value.toLocaleString("id-ID", { maximumFractionDigits: 2 });
const timestamp = (value?: string | null) => value ? new Date(value).toLocaleString("id-ID") : "-";

export default function AutoTradePage() {
  const [summary, setSummary] = useState<PaperSummary | null>(null);
  const [positions, setPositions] = useState<PaperTrade[]>([]);
  const [history, setHistory] = useState<PaperTrade[]>([]);
  const [candidates, setCandidates] = useState<PaperCandidate[]>([]);
  const [logs, setLogs] = useState<PaperLog[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = async (includeCandidates = false) => {
    setError("");
    try {
      const [s, p, h, l] = await Promise.all([api.paperSummary(), api.paperPositions(), api.paperHistory(), api.paperLogs()]);
      setSummary(s); setPositions(p.data); setHistory(h.data); setLogs(l.data);
    } catch { setError("Data portfolio paper trading belum tersedia."); }
    if (includeCandidates) {
      try {
        const c = await api.paperCandidates();
        setCandidates(c.data);
      } catch { setError("Signal kandidat belum tersedia; portfolio tetap dapat digunakan."); }
    }
  };
  useEffect(() => {
    load(false);
    const timer = window.setInterval(() => load(false), 30000);
    return () => window.clearInterval(timer);
  }, []);

  const toggle = async () => {
    if (!summary) return;
    setBusy(true); setError("");
    try { await api.paperToggle(!summary.enabled); await load(); } catch { setError("Gagal mengubah status bot."); } finally { setBusy(false); }
  };
  const run = async () => {
    setBusy(true); setError("");
    try { await api.paperRun(); await load(); } catch { setError("Gagal menjalankan simulasi."); } finally { setBusy(false); }
  };

  const noTrade = candidates.filter((c) => c.action !== "buy");
  return <div>
    <div className="auto-trade-head">
      <div><h1 className="page-title">Auto Trade</h1><p className="muted">Strategi otomatis untuk evaluasi, bukan rekomendasi investasi.</p></div>
      <div className="paper-label" role="status">PAPER TRADING · SIMULATION ONLY</div>
    </div>
    {error && <div className="analysis-err" role="alert">{error}</div>}
    <div className="card paper-notice"><strong>SIMULASI SAJA</strong><span>Tidak ada order broker nyata. Hasil historis dan simulasi tidak menjamin profit.</span></div>
    <div className="auto-actions card"><div><strong>Paper bot</strong><span className={`status ${summary?.enabled ? "on" : "off"}`}>{summary?.enabled ? "Aktif" : "Nonaktif"}</span><p className="muted">{summary?.enabled ? "Aktif mengizinkan /run dan entry simulasi baru." : "Nonaktif memblokir entry baru; posisi terbuka tetap dimonitor dan ditutup oleh summary/run."}</p></div><div className="action-buttons"><button className="btn" onClick={toggle} disabled={!summary || busy} aria-pressed={summary?.enabled}>{summary?.enabled ? "Matikan bot" : "Aktifkan bot"}</button><button className="btn btn-primary" onClick={run} disabled={!summary?.enabled || busy}>Jalankan simulasi</button></div></div>
    {!summary ? <div className="empty-state">Memuat data…</div> : <>
      <div className="grid grid-4 auto-summary"><Stat label="Equity simulasi" value={money(summary.equity)} /><Stat label="Cash tersedia" value={money(summary.cash)} /><Stat label="Unrealized P/L" value={money(summary.unrealized_pnl)} tone={summary.unrealized_pnl >= 0 ? "pos" : "neg"} /><Stat label="Posisi terbuka" value={number(summary.open_positions)} /></div>
      <div className="grid grid-2"><TradeTable title="Open positions" rows={positions} open /><CandidateTable candidates={candidates} noTrade={noTrade} /></div>
       <div className="card"><div className="card-title">Trade history</div><TradeTableBody rows={history} /></div>
       <div className="card paper-log"><div className="card-title">Bot activity log · realtime</div>{logs.length === 0 ? <p className="muted">Belum ada aktivitas.</p> : <div className="table-scroll"><table><thead><tr><th>Waktu</th><th>Event</th><th>Symbol</th><th>Detail</th></tr></thead><tbody>{logs.map((log) => <tr key={log.id}><td>{new Date(log.created_at).toLocaleString("id-ID")}</td><td className="sym-badge">{log.event_type}</td><td>{log.symbol || "-"}</td><td>{JSON.stringify(log.payload)}</td></tr>)}</tbody></table></div>}</div>
     </>}
  </div>;
}

function Stat({ label, value, tone = "" }: { label: string; value: string; tone?: string }) { return <div className="stat"><div className="label">{label}</div><div className={`value ${tone}`}>{value}</div></div>; }
function TradeTable({ title, rows, open }: { title: string; rows: PaperTrade[]; open?: boolean }) { return <div className="card"><div className="card-title">{title}</div><TradeTableBody rows={rows} open={open} /></div>; }
function TradeTableBody({ rows, open }: { rows: PaperTrade[]; open?: boolean }) { return rows.length === 0 ? <p className="muted">Belum ada data.</p> : <div className="table-scroll"><table><thead><tr><th>Symbol</th><th>Entry time</th><th>Entry</th><th>Current</th><th>LOT</th><th>{open ? "Stop / Target" : "Exit time"}</th><th>{open ? "Setup / Confidence" : "Exit price"}</th><th>P/L</th></tr></thead><tbody>{rows.map((r) => <tr key={r.id}><td className="sym-badge">{r.symbol}</td><td>{timestamp(r.entry_timestamp)}</td><td className="num">{number(r.entry_price)}</td><td className="num">{number(r.current_price)}</td><td className="num">{number(r.quantity)}</td><td className={open ? "num" : ""}>{open ? `${number(r.stop_loss)} / ${number(r.take_profit)}` : timestamp(r.exit_timestamp)}</td><td className="num">{open ? `Setup ${number(r.score)} / ${number(r.confidence_score)}` : number(r.exit_price)}</td><td className={`num ${(r.pnl ?? r.unrealized_pnl ?? 0) >= 0 ? "pos" : "neg"}`}>{money(r.pnl ?? r.unrealized_pnl)}</td></tr>)}</tbody></table></div>; }
function CandidateTable({ candidates, noTrade }: { candidates: PaperCandidate[]; noTrade: PaperCandidate[] }) { return <div className="card"><div className="card-title">Candidates & no-trade reasons</div>{candidates.length === 0 ? <p className="muted">Belum ada kandidat.</p> : <div className="table-scroll"><table><thead><tr><th>Symbol</th><th>Action</th><th>Score</th><th>Reason</th></tr></thead><tbody>{candidates.slice(0, 12).map((c) => <tr key={c.symbol}><td className="sym-badge">{c.symbol}</td><td className={c.action === "buy" ? "pos" : "muted"}>{c.action}</td><td className="num">{number(c.score)}</td><td>{c.reason}</td></tr>)}</tbody></table></div>}<p className="muted candidate-note">{noTrade.length} kandidat tidak memenuhi filter.</p></div>; }
