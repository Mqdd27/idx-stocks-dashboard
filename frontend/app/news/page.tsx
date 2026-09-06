"use client";

import { useEffect, useRef, useState } from "react";
import {
  NewsError,
  NewsItem,
  NewsList,
  NewsLoading,
} from "@/components/NewsContent";
import { api } from "@/lib/api";

type Feed = { data: NewsItem[]; sources: string[] };
type Tab = "stock" | "market";
const RETRIES = [800, 1600];

async function retry<T>(load: () => Promise<T>): Promise<T> {
  let error: unknown;
  for (let attempt = 0; attempt <= RETRIES.length; attempt += 1) {
    try {
      return await load();
    } catch (caught) {
      error = caught;
    }
    if (attempt < RETRIES.length)
      await new Promise((resolve) =>
        window.setTimeout(resolve, RETRIES[attempt]),
      );
  }
  throw error;
}

function status(updatedAt: Date | null, error: string) {
  return updatedAt
    ? `sukses ${updatedAt.toLocaleTimeString("id-ID", { hour12: false })}`
    : error
      ? "gagal"
      : "memuat";
}

export default function NewsPage() {
  const [tab, setTab] = useState<Tab>("stock");
  const [selected, setSelected] = useState("");
  const [rows, setRows] = useState<NewsItem[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [stockError, setStockError] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [matches, setMatches] = useState<any[]>([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [feed, setFeed] = useState<Feed>({ data: [], sources: [] });
  const [feedLoaded, setFeedLoaded] = useState(false);
  const [feedError, setFeedError] = useState("");
  const [feedUpdatedAt, setFeedUpdatedAt] = useState<Date | null>(null);
  const [sentiment, setSentiment] = useState("all");
  const [source, setSource] = useState("");
  const [days, setDays] = useState("7");
  const searchRef = useRef<HTMLInputElement>(null);

  const selectStock = (symbol: string) => {
    setSelected(symbol);
    setSearchQuery(symbol);
    setShowDropdown(false);
    searchRef.current?.blur();
  };
  const refresh = () => {
    setRefreshing(true);
    setRefreshKey(Date.now());
  };

  useEffect(() => {
    let active = true;
    Promise.all([api.watchlist(), api.overview()])
      .then(([watchlist, overview]) => {
        const symbol = watchlist.data[0]?.symbol || overview.gainers[0]?.symbol;
        if (active && symbol) selectStock(symbol);
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (tab !== "market") return;
    let active = true;
    setFeedLoaded(false);
    setFeedError("");
    retry(() =>
      api.newsFeed(
        sentiment,
        source || undefined,
        Number(days),
        refreshKey || undefined,
      ),
    )
      .then((result) => {
        if (active) {
          setFeed(result);
          setFeedUpdatedAt(new Date());
        }
      })
      .catch((error) => {
        if (active)
          setFeedError(
            error instanceof Error
              ? error.message
              : "Permintaan gagal setelah 3 percobaan.",
          );
      })
      .finally(() => {
        if (active) setFeedLoaded(true);
      });
    return () => {
      active = false;
    };
  }, [tab, sentiment, source, days, refreshKey]);

  useEffect(() => {
    if (!selected) return;
    let active = true;
    setLoaded(false);
    setStockError("");
    retry(() => api.news(selected, refreshKey || undefined))
      .then((result) => {
        if (active) {
          setRows(result.data);
          setUpdatedAt(new Date());
        }
      })
      .catch((error) => {
        if (active)
          setStockError(
            error instanceof Error
              ? error.message
              : "Permintaan gagal setelah 3 percobaan.",
          );
      })
      .finally(() => {
        if (active) {
          setLoaded(true);
          setRefreshing(false);
        }
      });
    return () => {
      active = false;
    };
  }, [selected, refreshKey]);

  const searchStocks = (query: string) => {
    setSearchQuery(query);
    if (!query.trim()) {
      setMatches([]);
      setShowDropdown(false);
      return;
    }
    const controller = new AbortController();
    window.setTimeout(
      () =>
        api
          .stocks(query, controller.signal)
          .then((hits) => {
            setMatches(hits);
            setShowDropdown(true);
          })
          .catch(() => {
            setMatches([]);
            setShowDropdown(false);
          }),
      180,
    );
  };

  return (
    <div>
      <div className="terminal-page-head">
        <div>
          <h1 className="page-title">News</h1>
          <span className="muted">
            {tab === "stock"
              ? `Stock: ${status(updatedAt, stockError)}`
              : `Market: ${status(feedUpdatedAt, feedError)}`}
          </span>
        </div>
        <button
          className="btn"
          type="button"
          onClick={refresh}
          disabled={refreshing}
        >
          {refreshing ? "MEMUAT..." : "REFRESH"}
        </button>
      </div>
      <div className="tabs">
        <button
          className={tab === "stock" ? "active" : ""}
          onClick={() => setTab("stock")}
        >
          STOCK NEWS
        </button>
        <button
          className={tab === "market" ? "active" : ""}
          onClick={() => setTab("market")}
        >
          MARKET FEED
        </button>
      </div>
      {tab === "market" ? (
        <MarketFeed
          feed={feed}
          loaded={feedLoaded}
          error={feedError}
          sentiment={sentiment}
          source={source}
          days={days}
          onSentiment={setSentiment}
          onSource={setSource}
          onDays={setDays}
          onRetry={refresh}
        />
      ) : (
        <StockNews
          selected={selected}
          rows={rows}
          loaded={loaded}
          error={stockError}
          query={searchQuery}
          matches={matches}
          showDropdown={showDropdown}
          searchRef={searchRef}
          onSearch={searchStocks}
          onSelect={selectStock}
          onDropdown={setShowDropdown}
          onRetry={refresh}
        />
      )}
    </div>
  );
}

function MarketFeed({
  feed,
  loaded,
  error,
  sentiment,
  source,
  days,
  onSentiment,
  onSource,
  onDays,
  onRetry,
}: {
  feed: Feed;
  loaded: boolean;
  error: string;
  sentiment: string;
  source: string;
  days: string;
  onSentiment: (value: string) => void;
  onSource: (value: string) => void;
  onDays: (value: string) => void;
  onRetry: () => void;
}) {
  return (
    <section className="terminal-panel">
      <header className="terminal-panel-head">
        <div>
          <span className="terminal-panel-code">MKT</span>
          <h2>MARKET FEED</h2>
        </div>
      </header>
      <div
        style={{
          display: "flex",
          gap: 8,
          flexWrap: "wrap",
          margin: "0 0 12px",
        }}
      >
        <select
          aria-label="Filter sentimen"
          value={sentiment}
          onChange={(event) => onSentiment(event.target.value)}
        >
          <option value="all">SEMUA SENTIMEN</option>
          <option value="positive">POSITIF</option>
          <option value="negative">NEGATIF</option>
          <option value="neutral">NETRAL</option>
        </select>
        <select
          aria-label="Filter sumber"
          value={source}
          onChange={(event) => onSource(event.target.value)}
        >
          <option value="">SEMUA SUMBER</option>
          {feed.sources.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
        <select
          aria-label="Filter tanggal"
          value={days}
          onChange={(event) => onDays(event.target.value)}
        >
          <option value="1">24 JAM</option>
          <option value="7">7 HARI</option>
          <option value="30">30 HARI</option>
        </select>
      </div>
      <span className="muted">
        Watchlist dan top gainers. URL/headline duplikat disatukan. Sentimen
        adalah label kata kunci, bukan analisis investasi.
      </span>
      {!loaded ? (
        <NewsLoading>Memuat market feed...</NewsLoading>
      ) : error ? (
        <NewsError message={error} onRetry={onRetry} />
      ) : (
        <NewsList rows={feed.data} aggregate />
      )}
    </section>
  );
}

function StockNews({
  selected,
  rows,
  loaded,
  error,
  query,
  matches,
  showDropdown,
  searchRef,
  onSearch,
  onSelect,
  onDropdown,
  onRetry,
}: {
  selected: string;
  rows: NewsItem[];
  loaded: boolean;
  error: string;
  query: string;
  matches: any[];
  showDropdown: boolean;
  searchRef: React.RefObject<HTMLInputElement | null>;
  onSearch: (query: string) => void;
  onSelect: (symbol: string) => void;
  onDropdown: (value: boolean) => void;
  onRetry: () => void;
}) {
  return (
    <section className="terminal-panel">
      <header className="terminal-panel-head">
        <div>
          <span className="terminal-panel-code">STK</span>
          <h2>STOCK NEWS</h2>
        </div>
      </header>
      <div className="search-box terminal-search">
        <span className="command-prefix">CMD</span>
        <input
          ref={searchRef}
          aria-label="Cari kode atau nama saham"
          placeholder="TICKER / COMPANY  [ / ]"
          value={query}
          onChange={(event) => onSearch(event.target.value.toUpperCase())}
          onFocus={() => {
            if (matches.length) onDropdown(true);
          }}
          onBlur={() => setTimeout(() => onDropdown(false), 150)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && matches[0])
              onSelect(matches[0].symbol);
            if (event.key === "Escape") onDropdown(false);
          }}
        />
        {showDropdown && matches.length > 0 && (
          <div className="search-results terminal-search-results">
            {matches.map((item) => (
              <button
                key={item.symbol}
                type="button"
                onMouseDown={() => onSelect(item.symbol)}
              >
                <strong>{item.symbol}</strong> {item.company_name}
              </button>
            ))}
          </div>
        )}
      </div>
      <span className="muted">
        Sumber: Google News RSS. Konten berita adalah data eksternal tidak
        terverifikasi.
      </span>
      {!selected ? (
        <div className="empty-state">Menentukan saham default...</div>
      ) : !loaded ? (
        <NewsLoading>Memuat...</NewsLoading>
      ) : error ? (
        <NewsError message={error} onRetry={onRetry} />
      ) : (
        <NewsList rows={rows} />
      )}
    </section>
  );
}
