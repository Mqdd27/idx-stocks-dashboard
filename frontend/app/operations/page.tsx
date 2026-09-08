"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { usePolling } from "@/lib/usePolling";

export default function OperationsPage() {
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState("");
  const load = () => api.operationsHealth().then(setData).catch((caught) => setError(caught.message));
  usePolling(load, 30000);

  if (!data) return <div><h1 className="page-title">OPERATIONS HEALTH</h1>{error ? <div className="terminal-error">{error}</div> : <div className="terminal-loading">LOADING OPERATIONS STATUS</div>}</div>;
  const quality = data.data_quality || {};
  return <div><h1 className="page-title">OPERATIONS HEALTH</h1>{error && <div className="terminal-error">{error}</div>}<div className="grid grid-4"><Metric label="CALENDAR" value={data.calendar.fresh ? "FRESH" : "STALE"} tone={data.calendar.fresh ? "pos" : "neg"} /><Metric label="COLLECTOR" value={data.collector.stale ? "STALE" : "LIVE"} tone={data.collector.stale ? "neg" : "pos"} /><Metric label="BATCH" value={data.batch.status} tone={data.batch.failed ? "neg" : ""} /><Metric label="TELEGRAM FAILURES" value={data.telegram.failed_count} tone={data.telegram.failed_count ? "neg" : "pos"} /></div><div className="card"><div className="card-title">DATA QUALITY</div><div className="grid grid-4">{["price", "news", "ratios", "collector"].map((key) => <Metric key={key} label={key.toUpperCase()} value={quality[key]?.stale ? "STALE" : "FRESH"} tone={quality[key]?.stale ? "neg" : "pos"} />)}</div><table className="dense-table"><tbody>{["price", "news", "ratios", "collector"].map((key) => <tr key={key}><td>{key.toUpperCase()} last update</td><td>{quality[key]?.last_updated || "—"}</td><td>Threshold {quality[key]?.max_age_seconds ? `${Math.round(quality[key].max_age_seconds / 60)} min` : "—"}</td></tr>)}</tbody></table><p className="muted">Rekomendasi diblokir hanya saat market buka dan PRICE atau COLLECTOR stale.</p></div><div className="card"><div className="card-title">CALENDAR & COLLECTOR</div><table className="dense-table"><tbody><tr><td>Calendar source</td><td>{data.calendar.source || "—"}</td></tr><tr><td>Last calendar sync</td><td>{data.calendar.last_sync || "—"}</td></tr><tr><td>Last intraday update</td><td>{data.collector.last_intraday || "—"}</td></tr></tbody></table></div><div className="card"><div className="card-title">BATCH QUEUE</div><p>{data.batch.id ? `#${data.batch.id} · ${data.batch.completed}/${data.batch.total} completed · ${data.batch.failed} failed` : "NO BATCH"}</p></div>{data.telegram.failures.length > 0 && <div className="card"><div className="card-title">TELEGRAM DELIVERY FAILURES</div><div className="table-scroll"><table className="dense-table"><thead><tr><th>TYPE</th><th>DATE</th><th>ERROR</th></tr></thead><tbody>{data.telegram.failures.map((row: any) => <tr key={row.id}><td>{row.message_type}</td><td>{row.target_date}</td><td className="neg">{row.last_error}</td></tr>)}</tbody></table></div></div>}</div>;
}

function Metric({ label, value, tone = "" }: { label: string; value: unknown; tone?: string }) { return <div className="card"><div className="muted">{label}</div><strong className={`metric-value ${tone}`}>{String(value)}</strong></div>; }
