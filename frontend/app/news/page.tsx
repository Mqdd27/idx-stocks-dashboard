"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";

export default function NewsPage() {
  const [selected, setSelected] = useState("");
  const [rows, setRows] = useState<any[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [matches, setMatches] = useState<any[]>([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const searchRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    let active = true;
    Promise.all([api.watchlist(), api.overview()]).then(([watchlist, overview]) => {
      const symbol = watchlist.data[0]?.symbol || overview.gainers[0]?.symbol;
      if (active && symbol) selectStock(symbol);
    }).catch(() => {});
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!selected) return;
    let active = true;
    setRows([]);
    setLoaded(false);
    api.news(selected, refreshKey > 0 ? refreshKey : undefined)
      .then((r) => { if (active) { setRows(r.data); setLoaded(true); setUpdatedAt(new Date()); } })
      .catch(() => { if (active) setLoaded(true); })
      .finally(() => { if (active) setRefreshing(false); });
    return () => { active = false; };
  }, [selected, refreshKey]);

  const handleSearchChange = (query: string) => {
    setSearchQuery(query);
    if (!query.trim()) { setMatches([]); setShowDropdown(false); return; }
    const controller = new AbortController();
    const timer = setTimeout(() => api.stocks(query, controller.signal).then((hits) => { setMatches(hits); setShowDropdown(true); }).catch(() => { setMatches([]); setShowDropdown(false); }), 180);
    return () => { clearTimeout(timer); controller.abort(); };
  };

  const selectStock = (symbol: string) => {
    setSelected(symbol);
    setSearchQuery(symbol);
    setShowDropdown(false);
    searchRef.current?.blur();
  };

  const refresh = () => {
    if (!selected) return;
    setRefreshing(true);
    setRefreshKey(Date.now());
  };

  return (
    <div>
      <div className="terminal-page-head"><div><h1 className="page-title">News</h1><span className="muted">{updatedAt ? `Diperbarui ${updatedAt.toLocaleTimeString("id-ID", { hour12: false })}` : "Memuat feed"}</span></div><button className="btn" type="button" onClick={refresh} disabled={!selected || refreshing}>{refreshing ? "MEMUAT..." : "REFRESH"}</button></div>
      <div className="card" style={{ marginBottom: 14 }}>
        <div className="card-title">Pilih saham</div>
        <div className="search-box terminal-search">
          <span className="command-prefix">CMD</span>
          <input ref={searchRef} aria-label="Cari kode atau nama saham" placeholder="TICKER / COMPANY  [ / ]" value={searchQuery} onChange={(e) => { handleSearchChange(e.target.value.toUpperCase()); }} onFocus={() => { if (matches.length > 0) setShowDropdown(true); }} onBlur={() => setTimeout(() => setShowDropdown(false), 150)} onKeyDown={(e) => { if (e.key === "Enter" && matches[0]) selectStock(matches[0].symbol); if (e.key === "Escape") { setShowDropdown(false); searchRef.current?.blur(); } }} style={{ background: "var(--panel2)", border: "1px solid var(--border)", color: "var(--text)", padding: "7px 10px", borderRadius: 6, width: "100%", fontFamily: "var(--mono)" }} />
          {showDropdown && matches.length > 0 && <div className="search-results terminal-search-results" style={{ maxHeight: 300, overflowY: "auto" }}>{matches.map((s) => <button key={s.symbol} type="button" onMouseDown={() => selectStock(s.symbol)} style={{ display: "flex", alignItems: "center", gap: 8, width: "100%", padding: "6px 10px", background: "transparent", border: "none", textAlign: "left", color: "var(--text)", fontFamily: "var(--mono)", fontSize: 13 }}><strong style={{ color: "var(--amber)" }}>{s.symbol}</strong><span>{s.company_name}</span><em style={{ color: "var(--muted)" }}>{s.sector || "IDX"}</em></button>)}</div>}
        </div>
        <span className="muted" style={{ marginTop: 8, display: "block", fontSize: 11 }}>Default: saham pertama di watchlist, atau top gainer bila watchlist kosong. Sumber: Google News RSS (public feed). Konten berita diperlakukan sebagai data eksternal yang tidak terverifikasi.</span>
      </div>
      {!selected && <div className="empty-state card">Menentukan saham default...</div>}
      {selected && !loaded && <div className="empty-state"><span className="spin" /> Memuat...</div>}
      {selected && loaded && rows.length === 0 && <div className="empty-state card">Belum ada berita tersedia untuk {selected}.</div>}
      {selected && loaded && rows.length > 0 && <div className="card">{rows.map((n, i) => <div className="news-item" key={i}><a href={n.url} target="_blank" rel="noopener noreferrer" className="t">{n.title}</a><div className="m">{n.source} {n.published_at ? " - " + new Date(n.published_at).toLocaleString("id-ID") : ""}</div>{n.summary && <div className="muted" style={{ marginTop: 3 }}>{n.summary}</div>}</div>)}</div>}
    </div>
  );
}
