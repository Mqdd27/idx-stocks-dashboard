"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { fmtBig, fmtVol } from "@/lib/format";

export default function BrokerActivityPage() {
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState("");
  useEffect(() => { api.brokerActivity().then(setData).catch((caught) => setError(caught.message)); }, []);
  if (error) return <div><h1 className="page-title">BROKER ACTIVITY</h1><div className="terminal-error">BROKER ACTIVITY UNAVAILABLE · {error}</div></div>;
  if (!data) return <div><h1 className="page-title">BROKER ACTIVITY</h1><div className="terminal-loading">LOADING IDX BROKER ACTIVITY…</div></div>;
  return <div><div className="terminal-page-head"><div><h1 className="page-title">BROKER ACTIVITY</h1><span className="muted">MARKET-WIDE EOD · IDX GETBROKERSUMMARY · DATA THROUGH {data.trading_date || "—"}</span></div></div><div className="card"><p className="muted">Total broker activity across IDX. This source has no ticker breakdown and no buy/sell direction; it is not broker flow or foreign flow.</p><div className="table-scroll"><table className="dense-table"><thead><tr><th>#</th><th>CODE</th><th>BROKER</th><th className="num">VOLUME</th><th className="num">VALUE</th><th className="num">FREQUENCY</th><th>COLLECTED AT</th></tr></thead><tbody>{data.data.length ? data.data.map((row: any, index: number) => <tr key={row.broker_code}><td>{index + 1}</td><td className="ticker-link">{row.broker_code}</td><td>{row.broker_name || "—"}</td><td className="num">{fmtVol(row.volume)}</td><td className="num">Rp {fmtBig(row.value)}</td><td className="num">{row.frequency?.toLocaleString("id-ID") || "—"}</td><td className="data-time">{row.collected_at ? new Date(row.collected_at).toLocaleString("id-ID") : "—"}</td></tr>) : <tr><td colSpan={7} className="terminal-empty">NO BROKER ACTIVITY DATA</td></tr>}</tbody></table></div></div></div>;
}
