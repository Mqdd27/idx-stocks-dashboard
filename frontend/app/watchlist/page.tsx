"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { cls, fmtNum, fmtVol, pct } from "@/lib/format";
import { usePolling } from "@/lib/usePolling";

type Alert = { price?: number; volume?: number };
type WatchlistItem = any;
type AlertMap = Record<string, Alert>;
const ALERT_KEY = "stocks.watchlist.alerts";

function readAlerts(): AlertMap {
  try { return JSON.parse(localStorage.getItem(ALERT_KEY) || "{}"); } catch { return {}; }
}

function alertHits(item: WatchlistItem, alert?: Alert): string[] {
  const price = item.price?.close;
  return [
    alert?.price != null && price != null && price >= alert.price ? `Harga ≥ ${fmtNum(alert.price)}` : "",
    alert?.volume != null && (item.price?.volume || 0) >= alert.volume ? `Volume ≥ ${fmtVol(alert.volume)}` : "",
  ].filter(Boolean);
}

export default function WatchlistPage() {
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [flashes, setFlashes] = useState<Record<string, "up" | "down">>({});
  const [alerts, setAlerts] = useState<AlertMap>({});
  const [hits, setHits] = useState<Record<string, string[]>>({});
  const [editing, setEditing] = useState("");
  const [note, setNote] = useState("");
  const prevPrices = useRef<Record<string, number>>({});
  const dragged = useRef("");

  useEffect(() => setAlerts(readAlerts()), []);

  const load = useCallback(() => {
    api.watchlist().then((response) => {
      const nextFlashes: Record<string, "up" | "down"> = {};
      const nextHits: Record<string, string[]> = {};
      for (const item of response.data) {
        const price = item.price?.close;
        const previous = prevPrices.current[item.symbol];
        if (price != null && previous != null && price !== previous) nextFlashes[item.symbol] = price > previous ? "up" : "down";
        if (price != null) prevPrices.current[item.symbol] = price;
        const itemHits = alertHits(item, alerts[item.symbol]);
        if (itemHits.length) nextHits[item.symbol] = itemHits;
      }
      setFlashes(nextFlashes);
      setHits(nextHits);
      setItems(response.data);
      setLoaded(true);
    }).catch(() => setLoaded(true));
  }, [alerts]);

  usePolling(load, 10000);

  const saveAlert = (symbol: string, value: Alert) => {
    const next = { ...alerts, [symbol]: value };
    if (!value.price && !value.volume) delete next[symbol];
    setAlerts(next);
    localStorage.setItem(ALERT_KEY, JSON.stringify(next));
  };

  const saveNote = async (symbol: string) => {
    await api.watchlistUpdate(symbol, note);
    setEditing("");
    load();
  };

  const reorder = async (target: string) => {
    const from = dragged.current;
    if (!from || from === target) return;
    const next = [...items];
    const start = next.findIndex((item) => item.symbol === from);
    const end = next.findIndex((item) => item.symbol === target);
    next.splice(end, 0, next.splice(start, 1)[0]);
    setItems(next);
    await api.watchlistReorder(next.map((item) => item.symbol));
  };

  if (!loaded) return <div className="empty-state"><span className="spin" /> Memuat…</div>;
  if (!items.length) return <div><h1 className="page-title">Watchlist</h1><div className="empty-state card">Watchlist kosong. Buka halaman saham lalu klik "Add to Watchlist" untuk menambahkan.</div></div>;

  return <div><h1 className="page-title">Watchlist</h1><div className="card"><div className="muted" style={{ marginBottom: 8 }}>Tarik baris untuk mengurutkan. Alert hanya aktif di browser ini saat halaman Watchlist terbuka.</div><div className="table-scroll"><table><thead><tr><th></th><th>Symbol</th><th className="num">Price</th><th className="num">Change %</th><th className="num">Volume</th><th className="num">PER</th><th>Note</th><th>Alert</th><th>Latest News</th><th></th></tr></thead><tbody>{items.map((item) => <WatchlistRow key={item.symbol} item={item} alert={alerts[item.symbol]} hits={hits[item.symbol]} flash={flashes[item.symbol]} editing={editing === item.symbol} note={note} onDragStart={() => { dragged.current = item.symbol; }} onDrop={() => reorder(item.symbol)} onEdit={() => { setEditing(item.symbol); setNote(item.note || ""); }} onNote={setNote} onSaveNote={() => saveNote(item.symbol)} onAlert={saveAlert} onRemove={async () => { await api.watchlistRemove(item.symbol); load(); }} />)}</tbody></table></div></div></div>;
}

function WatchlistRow({ item, alert, hits, flash, editing, note, onDragStart, onDrop, onEdit, onNote, onSaveNote, onAlert, onRemove }: { item: WatchlistItem; alert?: Alert; hits?: string[]; flash?: "up" | "down"; editing: boolean; note: string; onDragStart: () => void; onDrop: () => void; onEdit: () => void; onNote: (value: string) => void; onSaveNote: () => void; onAlert: (symbol: string, alert: Alert) => void; onRemove: () => void }) {
  return <tr draggable onDragStart={onDragStart} onDragOver={(event) => event.preventDefault()} onDrop={onDrop}><td className="muted">⋮⋮</td><td><Link href={`/stock/${item.symbol}`} className="sym-badge">{item.symbol}</Link>{hits && <div className="neg">{hits.join(" · ")}</div>}</td><td className={`num ${flash ? `flash-${flash}` : ""}`}>{item.price ? fmtNum(item.price.close) : "-"}</td><td className={`num ${cls(item.price?.change_pct)}`}>{item.price ? pct(item.price.change_pct) : "-"}</td><td className="num">{item.price ? fmtVol(item.price.volume) : "-"}</td><td className="num">{item.ratios?.per != null ? fmtNum(item.ratios.per) : "-"}</td><td>{editing ? <><input aria-label={`Catatan ${item.symbol}`} value={note} onChange={(event) => onNote(event.target.value)} /><button className="btn btn-sm" onClick={onSaveNote}>SAVE</button></> : <button className="btn btn-sm" onClick={onEdit}>{item.note || "NOTE"}</button>}</td><td><input aria-label={`Alert harga ${item.symbol}`} type="number" placeholder="Harga" defaultValue={alert?.price || ""} onBlur={(event) => onAlert(item.symbol, { ...alert, price: Number(event.target.value) || undefined })} /><input aria-label={`Alert volume ${item.symbol}`} type="number" placeholder="Volume" defaultValue={alert?.volume || ""} onBlur={(event) => onAlert(item.symbol, { ...alert, volume: Number(event.target.value) || undefined })} /></td><td style={{ maxWidth: 240, overflow: "hidden", textOverflow: "ellipsis" }}>{item.latest_news ? <a href={item.latest_news.url} target="_blank" rel="noopener noreferrer">{item.latest_news.title}</a> : <span className="muted">—</span>}</td><td><button className="btn btn-sm" onClick={onRemove}>✕</button></td></tr>;
}
