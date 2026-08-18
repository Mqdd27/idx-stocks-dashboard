"use client";

const MODEL_KEY = "stocks.ai.model";
const FALLBACK_KEY = "stocks.ai.fallback";

export function getModel(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(MODEL_KEY);
}

export function setModel(m: string) {
  localStorage.setItem(MODEL_KEY, m);
}

export function getFallback(): boolean {
  if (typeof window === "undefined") return false;
  return localStorage.getItem(FALLBACK_KEY) === "1";
}

export function setFallback(v: boolean) {
  localStorage.setItem(FALLBACK_KEY, v ? "1" : "0");
}

export function getWatchlist(): string[] {
  if (typeof window === "undefined") return [];
  try {
    return JSON.parse(localStorage.getItem("stocks.watchlist") || "[]");
  } catch {
    return [];
  }
}

export function setWatchlist(items: string[]) {
  localStorage.setItem("stocks.watchlist", JSON.stringify(items));
}