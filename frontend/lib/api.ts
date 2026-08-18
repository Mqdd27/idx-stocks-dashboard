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

async function jfetch<T>(url: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(url, init);
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
  return resp.json();
}

export const api = {
  stocks: () => jfetch<Stock[]>("/api/stocks"),
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
  overview: () => jfetch<any>("/api/market/overview"),
  screener: (params: URLSearchParams) => jfetch<{ data: any[] }>(`/api/screener?${params.toString()}`),
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
  aiSummarize: (symbol: string, model: string) =>
    jfetch<{ summary: string; model: string }>("/api/ai/summarize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symbol, model }),
    }),
};