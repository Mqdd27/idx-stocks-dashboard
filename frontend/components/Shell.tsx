"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import ModelSelector from "./ModelSelector";
import { api } from "@/lib/api";

const NAV = [
  { href: "/", key: "MKT", label: "Market", hint: "G M" },
  { href: "/watchlist", key: "MON", label: "Monitor", hint: "G W" },
  { href: "/screener", key: "SCR", label: "Screener", hint: "G S" },
  { href: "/news", key: "NWS", label: "News" },
  { href: "/calendar", key: "CAL", label: "Calendar" },
  { href: "/auto-trade", key: "SIM", label: "Paper Trade" },
  { href: "/ai-trading", key: "AIR", label: "AI Research" },
  { href: "/ai-auto-trade", key: "AAT", label: "AI Auto" },
  { href: "/settings", key: "CFG", label: "Settings" },
];

export default function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [collapsed, setCollapsed] = useState(false);
  const [clock, setClock] = useState("");
  const [health, setHealth] = useState<any>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const chordRef = useRef("");

  useEffect(() => {
    const tick = () => setClock(new Intl.DateTimeFormat("id-ID", { timeZone: "Asia/Jakarta", hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false }).format(new Date()));
    tick(); const timer = setInterval(tick, 1000); return () => clearInterval(timer);
  }, []);
  useEffect(() => {
    fetch("/health").then((r) => r.json()).then(setHealth).catch(() => setHealth(null));
  }, []);
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement;
      const typing = target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.tagName === "SELECT" || target.isContentEditable;
      if (!typing && (event.key === "/" || ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k"))) { event.preventDefault(); searchRef.current?.focus(); return; }
      if (typing) return;
      const key = event.key.toLowerCase();
      if (key === "g") { chordRef.current = "g"; window.setTimeout(() => { chordRef.current = ""; }, 1000); return; }
      if (chordRef.current === "g") {
        const routes: Record<string, string> = { m: "/", w: "/watchlist", s: "/screener" };
        if (routes[key]) { event.preventDefault(); router.push(routes[key]); }
        chordRef.current = "";
      }
    };
    window.addEventListener("keydown", handler); return () => window.removeEventListener("keydown", handler);
  }, [router]);

  return <div className={`app-shell terminal-shell ${collapsed ? "nav-collapsed" : ""}`}>
    <aside className="sidebar terminal-sidebar">
      <div className="sidebar-brand terminal-brand"><img className="brand-mark" src="/icon.svg" alt="STX Stocks IDX" /><div><h1>STOCKS IDX</h1><small>INDONESIA EQUITY TERMINAL</small></div></div>
      <button className="nav-collapse" onClick={() => setCollapsed((v) => !v)} aria-label={collapsed ? "Expand navigation" : "Collapse navigation"}>{collapsed ? ">" : "<"}</button>
      <nav className="nav terminal-nav" aria-label="Primary">
        {NAV.map((item) => <Link key={item.href} href={item.href} title={item.label} className={pathname === item.href ? "active" : ""}>
          <span className="nav-code">{item.key}</span><span className="nav-label">{item.label}</span>{item.hint && <kbd>{item.hint}</kbd>}
        </Link>)}
      </nav>
      <div className="sidebar-footer terminal-sidebar-footer"><span>DATA</span><b>YF / GNEWS</b><span>AI</span><b>9ROUTER</b></div>
    </aside>
    <div className="main terminal-main">
      <header className="topbar terminal-command-bar">
        <button className="mobile-nav-button" onClick={() => setCollapsed((v) => !v)} aria-label="Toggle navigation">MENU</button>
        <SearchBox inputRef={searchRef} />
        <MarketStatusChip />
        <span className="terminal-clock" aria-label="Waktu Jakarta">JKT {clock || "--:--:--"}</span>
        <span className={`connection-state ${health?.status === "ok" ? "ok" : "error"}`} title="Backend / database / 9Router status">{health?.status === "ok" ? "SYS OK" : "SYS --"}</span>
        <ModelSelector />
      </header>
      <main className="content terminal-content">{children}</main>
    </div>
  </div>;
}

function SearchBox({ inputRef }: { inputRef: React.RefObject<HTMLInputElement | null> }) {
  const router = useRouter();
  const [q, setQ] = useState(""); const [results, setResults] = useState<any[]>([]); const [open, setOpen] = useState(false);
  useEffect(() => {
    const query = q.trim(); if (!query) { setResults([]); setOpen(false); return; }
    const controller = new AbortController(); const timer = setTimeout(() => api.stocks(query, controller.signal).then((hits) => { setResults(hits); setOpen(true); }).catch((error) => { if (error.name !== "AbortError") setResults([]); }), 180);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [q]);
  const navigate = (symbol: string) => { setOpen(false); setQ(""); router.push(`/stock/${symbol}`); };
  return <div className="search-box terminal-search"><span className="command-prefix">CMD</span><input ref={inputRef} aria-label="Cari kode atau nama saham" placeholder="TICKER / COMPANY  [ / ]" value={q} onChange={(e) => setQ(e.target.value.toUpperCase())} onFocus={() => results.length > 0 && setOpen(true)} onBlur={() => setTimeout(() => setOpen(false), 150)} onKeyDown={(e) => { if (e.key === "Enter" && results[0]) navigate(results[0].symbol); if (e.key === "Escape") { setOpen(false); inputRef.current?.blur(); } }} />
    {open && results.length > 0 && <div className="search-results terminal-search-results">{results.map((r) => <button key={r.symbol} onMouseDown={() => navigate(r.symbol)}><strong>{r.symbol}</strong><span>{r.company_name}</span><em>{r.sector || "IDX"}</em></button>)}</div>}</div>;
}

function MarketStatusChip() {
  const [status, setStatus] = useState<any>(null);
  useEffect(() => { const check = () => api.marketStatus().then(setStatus).catch(() => setStatus(null)); check(); const timer = setInterval(check, 60000); return () => clearInterval(timer); }, []);
  const state = status?.is_open ? "open" : status?.status === "BREAK" ? "break" : ["PUBLIC_HOLIDAY", "EXCHANGE_HOLIDAY", "WEEKEND"].includes(status?.status) ? "holiday" : "closed";
  return <span className={`terminal-market-badge ${state}`} title={status?.reason || "IDX market status"}>IDX {status?.status || "--"}</span>;
}
