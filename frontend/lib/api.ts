export interface PriceInfo {
  date: string | null;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  previous_close: number | null;
  volume: number | null;
  change: number | null;
  change_pct: number | null;
  live?: boolean;
}

export interface Ratios {
  period: string | null;
  period_type: string | null;
  eps: number | null;
  per: number | null;
  pbv: number | null;
  roe: number | null;
  roa: number | null;
  der: number | null;
  npm: number | null;
  gross_margin: number | null;
  operating_margin: number | null;
  dividend_yield: number | null;
  revenue_growth: number | null;
  net_income_growth: number | null;
}

export interface Stock {
  symbol: string;
  company_name: string;
  sector: string | null;
  subsector: string | null;
  listing_date: string | null;
  website: string | null;
  price: PriceInfo | null;
  ratios: Ratios | null;
}

export interface AIConfig {
  id: string;
  name: string;
  provider: string;
  local: boolean;
  usable?: boolean;
}

export interface PaperSummary {
  paper_only: true;
  enabled: boolean;
  cash: number;
  equity: number;
  unrealized_pnl: number;
  open_positions: number;
  exposure: number;
  realized_pnl: number;
  win_rate: number;
  expectancy: number;
}

export interface PaperTrade {
  id: number;
  symbol: string;
  entry_date: string;
  entry_timestamp: string;
  exit_date?: string | null;
  exit_timestamp?: string | null;
  status: string;
  entry_price: number;
  exit_price?: number | null;
  quantity: number;
  stop_loss: number;
  take_profit: number;
  score: number;
  reason: string;
  fees: number;
  pnl?: number | null;
  current_price?: number | null;
  unrealized_pnl?: number | null;
  unrealized_pnl_percent?: number | null;
  confidence_score?: number | null;
}

export interface PaperLog {
  id: number;
  event_type: string;
  symbol?: string | null;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface PaperCandidate {
  symbol: string;
  action: string;
  score: number;
  stop: number | null;
  target: number | null;
  rr: number;
  reason: string;
}

export interface Technicals {
  last_price: number;
  previous_close: number;
  change: number;
  change_pct: number | null;
  high_52w: number | null;
  low_52w: number | null;
  sma5: number | null;
  sma10: number | null;
  sma20: number | null;
  sma50: number | null;
  sma100: number | null;
  sma200: number | null;
  ema12: number | null;
  ema26: number | null;
  rsi14: number | null;
  macd: { macd: number; signal: number; histogram: number } | null;
  bollinger: { middle: number; upper: number; lower: number } | null;
  atr14: number | null;
  volume_avg_20: number | null;
  support_resistance: { support: number; resistance: number; pivot: number } | null;
  above_sma200: boolean | null;
}

const GET_CACHE = new Map<string, { expires: number; value: unknown }>();
const GET_INFLIGHT = new Map<string, Promise<unknown>>();
const GET_CHANNEL = typeof window !== "undefined" && "BroadcastChannel" in window ? new BroadcastChannel("stocks-api-cache") : null;
GET_CHANNEL?.addEventListener("message", (event) => {
  const { url, value, expires } = event.data || {};
  if (url && expires && value !== undefined) GET_CACHE.set(url, { expires, value });
});

async function jfetch<T>(url: string, init?: RequestInit): Promise<T> {
  if (!init?.method || init.method === "GET") {
    const cached = GET_CACHE.get(url);
    if (cached && cached.expires > Date.now()) return cached.value as T;
    if (typeof window !== "undefined") {
      try {
        const shared = JSON.parse(localStorage.getItem(`stocks.api.${url}`) || "null");
        if (shared?.expires > Date.now()) { GET_CACHE.set(url, shared); return shared.value as T; }
      } catch {}
    }
    const pending = GET_INFLIGHT.get(url);
    if (pending) return pending as Promise<T>;
    const request = fetch(url, init).then(async (resp) => {
      if (!resp.ok) throw new Error(`${resp.status}`);
      const value = await resp.json();
      const cached = { expires: Date.now() + 5000, value };
      GET_CACHE.set(url, cached);
      if (typeof window !== "undefined") { try { localStorage.setItem(`stocks.api.${url}`, JSON.stringify(cached)); } catch {} }
      GET_CHANNEL?.postMessage({ url, ...cached });
      GET_INFLIGHT.delete(url);
      return value;
    }).catch((error) => { GET_INFLIGHT.delete(url); throw error; });
    GET_INFLIGHT.set(url, request);
    return request as Promise<T>;
  }
  let resp = await fetch(url, init);
  if (resp.status === 401 && typeof window !== "undefined" && !url.includes("/api/admin/login")) {
    const token = window.prompt("Admin token diperlukan untuk aksi ini");
    if (token) {
      const login = await fetch("/api/admin/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ token }) });
      if (login.ok) resp = await fetch(url, init);
    }
  }
  if (!resp.ok) {
    let detail = "";
    try {
      const j = await resp.json();
      detail = j.detail || j.error || "";
    } catch {
      /* ignore */
    }
    throw new Error(`${resp.status} ${detail}`.trim());
  }
  const value = await resp.json();
  GET_CACHE.clear();
  GET_INFLIGHT.clear();
  if (typeof window !== "undefined") {
    for (let index = localStorage.length - 1; index >= 0; index -= 1) {
      const key = localStorage.key(index);
      if (key?.startsWith("stocks.api.")) localStorage.removeItem(key);
    }
  }
  return value;
}

export const api = {
  stocks: (query?: string, signal?: AbortSignal) => {
    const params = new URLSearchParams();
    if (query?.trim()) params.set("q", query.trim());
    params.set("limit", "8");
    return jfetch<Stock[]>(`/api/stocks?${params}`, { signal });
  },
  stock: (symbol: string) => jfetch<Stock>(`/api/stocks/${symbol}`),
  prices: (symbol: string, range: string) =>
    jfetch<{ data: Array<{ time: string; open: number; high: number; low: number; close: number; volume: number }> }>(
      `/api/stocks/${symbol}/prices?range=${range.toLowerCase()}&interval=1d`
    ),
  financials: (symbol: string, periodType: "annual" | "quarterly") =>
    jfetch<{ data: any[] }>(`/api/stocks/${symbol}/financials?period_type=${periodType}`),
  ratios: (symbol: string) => jfetch<{ data: any[] }>(`/api/stocks/${symbol}/ratios`),
  technicals: (symbol: string) => jfetch<{ technicals: Technicals | null }>(`/api/stocks/${symbol}/technicals`),
  news: (symbol: string) => jfetch<{ data: any[] }>(`/api/stocks/${symbol}/news`),
  aiWatchlistToday: () => jfetch<any>("/api/ai-watchlist/today"),
  aiWatchlistAgents: () => jfetch<any>("/api/ai-watchlist/trading-agents"),
  aiWatchlistPaper: () => jfetch<any>("/api/ai-watchlist/paper"),
  aiWatchlistHistory: () => jfetch<any>("/api/ai-watchlist/history"),
  aiWatchlistRefresh: () => jfetch<any>("/api/ai-watchlist/refresh", { method: "POST" }),
  notificationStatus: () => jfetch<any>("/api/recommendations/notifications/status"),
  strategyPerformance: (strategy: string, period: string, method?: string, date?: string) => jfetch<any>(`/api/recommendations/strategy-performance/${strategy}?period=${period}${method ? `&method=${method}` : ""}${date ? `&date=${date}` : ""}`),
  recommendationsToday: () => jfetch<any>("/api/recommendations/today"),
  recommendationsScreener: (strategy: string, method?: string) => jfetch<any>(`/api/recommendations/screener/${strategy}${method ? `?method=${method}` : ""}`),
  recommendationsStrategy: (strategy: string, method?: string) => jfetch<any>(`/api/recommendations/strategy/${strategy}${method ? `?method=${method}` : ""}`),
  stockTradeIdeas: (symbol: string) => jfetch<any>(`/api/recommendations/stocks/${symbol}/trade-ideas`),
  overview: () => jfetch<any>("/api/market/overview"),
  marketStatus: () => jfetch<any>("/api/market/status"),
  marketCalendarStatus: () => jfetch<any>("/api/market/calendar/status"),
  operationsHealth: () => jfetch<any>("/api/operations/health"),
  strategyPerformanceTrades: (strategy: string, period: string, method?: string, date?: string) => jfetch<any>(`/api/recommendations/strategy-performance/${strategy}/trades?period=${period}${method ? `&method=${method}` : ""}${date ? `&date=${date}` : ""}`),
  marketCalendar: (start: string, end: string) => jfetch<any>(`/api/market/calendar?start_date=${start}&end_date=${end}`),
  marketHolidays: () => jfetch<any>("/api/market/holidays"),
  marketEvents: (start: string, end: string) => jfetch<any>(`/api/market/events?start_date=${start}&end_date=${end}`),
  aiAutoTradeStatus: () => jfetch<any>("/api/ai-auto-trade/status"),
  aiAutoTradeRuns: () => jfetch<any[]>("/api/ai-auto-trade/runs"),
  aiAutoTradeConfig: (config: Record<string, unknown>) => jfetch<any>("/api/ai-auto-trade/config", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(config) }),
  aiAutoTradeRun: () => jfetch<any>("/api/ai-auto-trade/run", { method: "POST" }),
  aiTradingStatus: () => jfetch<any>("/api/ai-trading/status"),
  aiTradingJobs: () => jfetch<any[]>("/api/ai-trading/jobs"),
  aiTradingHistory: () => jfetch<any[]>("/api/ai-trading/history"),
  aiTradingAnalysis: (ticker: string) => jfetch<any>(`/api/ai-trading/analysis/${ticker}`),
  aiTradingBatches: () => jfetch<any[]>("/api/ai-trading/batches"),
  aiTradingBatchStart: (batch_size: number) => jfetch<any>("/api/ai-trading/batches", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ batch_size }) }),
  aiTradingBatchResume: (id: number) => jfetch<any>(`/api/ai-trading/batches/${id}/resume`, { method: "POST" }),
  aiTradingAnalyze: (ticker: string, quick_model?: string, deep_model?: string) => jfetch<any>(`/api/ai-trading/analyze/${ticker}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ quick_model, deep_model }) }),
  paperSummary: () => jfetch<PaperSummary>("/api/paper-trading/summary"),
  paperPositions: () => jfetch<{ data: PaperTrade[] }>("/api/paper-trading/positions"),
  paperHistory: () => jfetch<{ data: PaperTrade[] }>("/api/paper-trading/history"),
  paperLogs: () => jfetch<{ data: PaperLog[] }>("/api/paper-trading/logs?limit=50"),
  paperCandidates: () => jfetch<{ data: PaperCandidate[] }>("/api/paper-trading/candidates"),
  paperToggle: (enabled: boolean) => jfetch<{ paper_only: true; enabled: boolean }>("/api/paper-trading/toggle", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ enabled }) }),
  paperRun: () => jfetch<{ status: string; created?: number }>("/api/paper-trading/run", { method: "POST" }),
  screener: (params: URLSearchParams) => jfetch<{ data: any[]; generated_at?: string; market?: any }>(`/api/screener?${params.toString()}`),
  watchlist: () => jfetch<{ data: any[] }>("/api/watchlist"),
  watchlistAdd: (symbol: string, note?: string) =>
    jfetch("/api/watchlist", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action: "add", symbol, note }) }),
  watchlistRemove: (symbol: string) =>
    jfetch("/api/watchlist", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action: "remove", symbol }) }),
  aiModels: () => jfetch<AIConfig[]>("/api/ai/models"),
  aiQueue: () => jfetch<{ active: boolean; queued: number; max_concurrency: number }>("/api/ai/queue-status"),
  cloudFallbackModel: async (): Promise<string> => {
    const models = await jfetch<AIConfig[]>("/api/ai/models").catch(() => []);
    const cloud = models.find((m) => !m.local && m.usable !== false);
    return cloud ? cloud.id : "qwen3.5:2b";
  },
  aiAnalyze: (symbol: string, model: string) =>
    jfetch<{ analysis: string; model: string; provider: string; generated_at: string }>("/api/ai/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symbol, model }),
    }),
  aiAnalyzeStream: async (
    symbol: string,
    model: string,
    onDelta: (d: string) => void,
    onDone: (meta: { model: string; provider: string; generated_at: string }) => void,
    onError: (msg: string, provider?: string) => void,
  ): Promise<void> => {
    const resp = await fetch("/api/ai/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symbol, model, stream: true }),
    });
    if (!resp.ok) {
      let detail = "";
      try {
        const j = await resp.json();
        detail = j.detail || j.error || "";
      } catch {
        /* ignore */
      }
      throw new Error(`${resp.status} ${detail}`.trim());
    }
    const reader = resp.body?.getReader();
    if (!reader) return;
    const decoder = new TextDecoder();
    let buf = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      const lines = buf.split("\n");
      buf = lines.pop() ?? "";
      for (const line of lines) {
        const t = line.trim();
        if (!t.startsWith("data:")) continue;
        let p: any;
        try {
          p = JSON.parse(t.slice(5).trim());
        } catch {
          continue;
        }
        if (p.delta) onDelta(p.delta);
        else if (p.error) {
          onError(String(p.error), p.provider);
          return;
        } else if (p.done) {
          onDone({ model: p.model, provider: p.provider, generated_at: p.generated_at });
          return;
        }
      }
    }
  },
  aiSummarize: (symbol: string, model: string) =>
    jfetch<{ summary: string; model: string }>("/api/ai/summarize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symbol, model }),
    }),
};