"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { fmtNum, fmtVol, pct, cls } from "@/lib/format";

export default function WatchlistPage() {
  const [items, setItems] = useState<any[]>([]);
  const [loaded, setLoaded] = useState(false);

  const load = useCallback(() => {
    api.watchlist().then((w) => { setItems(w.data); setLoaded(true); }).catch(() => setLoaded(true));
  }, []);

  useEffect(() => {
    load();
    const iv = setInterval(load, 10000);
    return () => clearInterval(iv);
  }, [load]);

  async function remove(symbol: string) {
    await api.watchlistRemove(symbol);
    load();
  }

  if (!loaded) return <div className="empty-state"><span className="spin" /> Memuat…</div>;

  return (
    <div>
      <h1 className="page-title">Watchlist</h1>
      {items.length === 0 ? (
        <div className="empty-state card">
          Watchlist kosong. Buka halaman saham lalu klik "Add to Watchlist" untuk menambahkan.
        </div>
      ) : (
        <div className="card">
          <table>
            <thead>
              <tr>
                <th>Symbol</th><th className="num">Price</th><th className="num">Change %</th>
                <th className="num">Volume</th><th className="num">PER</th><th className="num">PBV</th>
                <th className="num">ROE</th><th>Note</th><th></th>
              </tr>
            </thead>
            <tbody>
              {items.map((it) => (
                <tr key={it.symbol}>
                  <td><Link href={`/stock/${it.symbol}`} className="sym-badge">{it.symbol}</Link></td>
                  <td className="num">{it.price ? fmtNum(it.price.close) : "-"}</td>
                  <td className={`num ${cls(it.price?.change_pct)}`}>{it.price ? pct(it.price.change_pct) : "-"}</td>
                  <td className="num">{it.price ? fmtVol(it.price.volume) : "-"}</td>
                  <td className="num">{it.ratios?.per != null ? fmtNum(it.ratios.per) : "-"}</td>
                  <td className="num">{it.ratios?.pbv != null ? fmtNum(it.ratios.pbv) : "-"}</td>
                  <td className="num">{it.ratios?.roe != null ? fmtNum(it.ratios.roe) + "%" : "-"}</td>
                  <td className="muted" style={{ maxWidth: 180, overflow: "hidden", textOverflow: "ellipsis" }}>{it.note || ""}</td>
                  <td><button className="btn btn-sm" onClick={() => remove(it.symbol)}>✕</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}