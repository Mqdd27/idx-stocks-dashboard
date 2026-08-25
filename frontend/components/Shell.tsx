"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import ModelSelector from "./ModelSelector";
import { api } from "@/lib/api";

const NAV = [
  { href: "/", icon: "◧", label: "Market" },
  { href: "/watchlist", icon: "★", label: "Watchlist" },
  { href: "/calendar", icon: "▦", label: "Calendar" },
  { href: "/screener", icon: "⌕", label: "Screener" },
  { href: "/news", icon: "☰", label: "News" },
  { href: "/ai", icon: "◉", label: "AI" },
  { href: "/auto-trade", icon: "↗", label: "Auto Trade" },
  { href: "/ai-trading", icon: "◈", label: "AI Trading" },
  { href: "/settings", icon: "⚙", label: "Settings" },
];

export default function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <h1><span>Stocks</span> IDX</h1>
          <small>Indonesia Market Dashboard</small>
        </div>
        <nav className="nav">
          {NAV.map((n) => (
            <Link key={n.href} href={n.href} className={pathname === n.href ? "active" : ""}>
              <span className="nav-icon">{n.icon}</span>
              {n.label}
            </Link>
          ))}
        </nav>
        <div className="sidebar-footer">
          Data: Yahoo Finance / Google News RSS
          <br />
          AI: 9Router + Ollama
        </div>
      </aside>
      <div className="main">
        <div className="topbar">
          <SearchBox />
          <MarketStatusChip />
          <ThemeToggle />
          <ModelSelector />
        </div>
        <div className="content">{children}</div>
      </div>
    </div>
  );
}

function SearchBox() {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<any[]>([]);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const query = q.trim();
    if (!query) {
      setResults([]);
      setOpen(false);
      return;
    }
    const controller = new AbortController();
    const t = setTimeout(() => {
      api.stocks(query, controller.signal).then((hits) => {
        setResults(hits);
        setOpen(true);
      }).catch((error) => {
        if (error.name !== "AbortError") setResults([]);
      });
    }, 200);
    return () => { clearTimeout(t); controller.abort(); };
  }, [q]);

  return (
    <div className="search-box">
      <input
        placeholder="Cari saham… (BBCA, Bank Central Asia)"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        onFocus={() => results.length > 0 && setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
      />
      {open && results.length > 0 && (
        <div className="search-results">
          {results.map((r) => (
            <Link key={r.symbol} href={`/stock/${r.symbol}`} onClick={() => { setOpen(false); setQ(""); }}>
              <span className="sym">{r.symbol}</span>{" "}
              <span className="nm">{r.company_name}</span>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

function MarketStatusChip() {
  const [status, setStatus] = useState<any>(null);
  useEffect(() => { const check = () => api.marketStatus().then(setStatus).catch(() => setStatus(null)); check(); const iv = setInterval(check, 60000); return () => clearInterval(iv); }, []);
  const label = status?.status === "BREAK" ? "Market Break" : status?.status === "PUBLIC_HOLIDAY" || status?.status === "EXCHANGE_HOLIDAY" || status?.status === "WEEKEND" ? "Market Holiday" : status?.is_open ? "Market Open" : "Market Closed";
  return <div className="market-status" title={status?.reason || "IDX market status"}><span className={`dot ${status?.is_open ? "" : "closed"}`} />{status ? label : "…"}</div>;
}

function ThemeToggle() {
  const [light, setLight] = useState(false);
  useEffect(() => {
    const saved = localStorage.getItem("theme") || "dark";
    setLight(saved === "light");
    document.documentElement.classList.toggle("light-theme", saved === "light");
  }, []);
  const toggle = (value: boolean) => {
    setLight(value);
    localStorage.setItem("theme", value ? "light" : "dark");
    document.documentElement.classList.toggle("light-theme", value);
  };
  return <label className="theme-toggle" title={light ? "Light mode" : "Dark mode"}>
    <span>{light ? "Light" : "Dark"}</span>
    <input type="checkbox" checked={light} onChange={(e) => toggle(e.target.checked)} />
  </label>;
}
