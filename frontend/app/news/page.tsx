"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function NewsPage() {
  const [stocks, setStocks] = useState<any[]>([]);
  const [selected, setSelected] = useState("");
  const [rows, setRows] = useState<any[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    api.stocks().then((s) => setStocks(s)).catch(() => {});
  }, []);

  useEffect(() => {
    if (!selected) return;
    setLoaded(false);
    api.news(selected).then((r) => { setRows(r.data); setLoaded(true); }).catch(() => setLoaded(true));
  }, [selected]);

  return (
    <div>
      <h1 className="page-title">News</h1>
      <div className="card" style={{ marginBottom: 14 }}>
        <div className="card-title">Pilih saham</div>
        <select value={selected} onChange={(e) => setSelected(e.target.value)} style={{ background: "var(--panel2)", border: "1px solid var(--border)", color: "var(--text)", padding: "7px 10px", borderRadius: 6, minWidth: 200 }}>
          <option value="">— Pilih —</option>
          {stocks.filter((s) => s.symbol !== "IHSG").map((s) => (
            <option key={s.symbol} value={s.symbol}>{s.symbol} — {s.company_name}</option>
          ))}
        </select>
        <span className="muted" style={{ marginLeft: 10, fontSize: 11 }}>
          Sumber: Google News RSS (public feed). Konten berita diperlakukan sebagai data eksternal yang tidak terverifikasi.
        </span>
      </div>
      {!selected && <div className="empty-state card">Pilih saham untuk melihat berita.</div>}
      {selected && !loaded && <div className="empty-state"><span className="spin" /> Memuat…</div>}
      {selected && loaded && rows.length === 0 && (
        <div className="empty-state card">Belum ada berita tersedia untuk {selected}.</div>
      )}
      {selected && loaded && rows.length > 0 && (
        <div className="card">
          {rows.map((n, i) => (
            <div className="news-item" key={i}>
              <a href={n.url} target="_blank" rel="noopener noreferrer" className="t">{n.title}</a>
              <div className="m">{n.source} · {n.published_at ? new Date(n.published_at).toLocaleString("id-ID") : ""}</div>
              {n.summary && <div className="muted" style={{ marginTop: 3 }}>{n.summary}</div>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}