"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { fmtNum, fmtVol, pct, cls } from "@/lib/format";

export default function MarketPage() {
  const [data, setData] = useState<any>(null);
  const [err, setErr] = useState(false);

  useEffect(() => {
    let alive = true;
    const load = () => {
      api.overview().then((d) => alive && setData(d)).catch(() => alive && setErr(true));
    };
    load();
    const iv = setInterval(load, 30000);
    return () => { alive = false; clearInterval(iv); };
  }, []);

  if (err) return <div className="empty-state">Gagal memuat data market.</div>;
  if (!data) return <div className="empty-state"><span className="spin" /> Memuat…</div>;

  const ihsg = data.ihsg?.price;

  return (
    <div>
      <h1 className="page-title">Market Overview</h1>
      <div className="grid grid-3" style={{ marginBottom: 14 }}>
        <div className="card">
          <div className="card-title">IHSG</div>
          <div className="price-big" style={{ color: ihsg?.change_pct != null && ihsg.change_pct >= 0 ? "var(--green)" : "var(--red)" }}>
            {ihsg ? fmtNum(ihsg.close) : "-"}
          </div>
          {ihsg && (
            <div className={`price-change ${cls(ihsg.change_pct)}`}>
              {ihsg.change != null && `${ihsg.change > 0 ? "+" : ""}${fmtNum(ihsg.change)}`} ({pct(ihsg.change_pct)})
            </div>
          )}
        </div>
        <div className="card">
          <div className="card-title">Total Volume</div>
          <div className="price-big">{fmtVol(data.total_volume)}</div>
        </div>
        <div className="card">
          <div className="card-title">Tickers</div>
          <div className="price-big">IDX</div>
        </div>
      </div>

      <div className="grid grid-3">
        <StockTable title="Top Gainers" rows={data.gainers} />
        <StockTable title="Top Losers" rows={data.losers} />
        <StockTable title="Most Active" rows={data.most_active} volume />
      </div>
    </div>
  );
}

function StockTable({ title, rows, volume }: { title: string; rows: any[]; volume?: boolean }) {
  return (
    <div className="card">
      <div className="card-title">{title}</div>
      <table>
        <thead>
          <tr><th>Symbol</th><th>Last</th><th>Chg %</th>{volume && <th>Volume</th>}</tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.symbol}>
              <td><Link href={`/stock/${r.symbol}`} className="sym-badge">{r.symbol}</Link></td>
              <td className="num">{fmtNum(r.close)}</td>
              <td className={`num ${cls(r.change_pct)}`}>{pct(r.change_pct)}</td>
              {volume && <td className="num">{fmtVol(r.volume)}</td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}