"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { usePolling } from "@/lib/usePolling";
import { fmtNum, fmtVol, pct, cls } from "@/lib/format";

export default function WatchlistPage() {
  const [items, setItems] = useState<any[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [flashes, setFlashes] = useState<Record<string, "up" | "down">>({});
  const prevPrices = useRef<Record<string, number>>({});

  const load = useCallback(() => {
    api.watchlist().then((w) => {
      const newFlashes: Record<string, "up" | "down"> = {};
      for (const it of w.data) {
        const c = it.price?.close;
        const p = prevPrices.current[it.symbol];
        if (c != null && p != null && c !== p) newFlashes[it.symbol] = c > p ? "up" : "down";
        if (c != null) prevPrices.current[it.symbol] = c;
      }
      setFlashes(newFlashes);
      setItems(w.data);
      setLoaded(true);
    }).catch(() => setLoaded(true));
  }, []);

  usePolling(load, 10000);

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
                  <td
                    className={`num ${flashes[it.symbol] ? `flash-${flashes[it.symbol]}` : ""}`}
                    onAnimationEnd={() => setFlashes((f) => {
                      const n = { ...f };
                      delete n[it.symbol];
                      return n;
                    })}
                  >{it.price ? fmtNum(it.price.close) : "-"}</td>
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