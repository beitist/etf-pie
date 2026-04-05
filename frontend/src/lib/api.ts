import type { ChartPoint, ETFProfile, ETFSearchResult } from "../types";

const API_BASE = import.meta.env.VITE_API_URL || "/api";

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function searchETF(query: string): Promise<ETFSearchResult[]> {
  if (query.length < 2) return [];
  return fetchJson<ETFSearchResult[]>(
    `${API_BASE}/search?q=${encodeURIComponent(query)}`
  );
}

export async function getETFProfile(isin: string): Promise<ETFProfile> {
  return fetchJson<ETFProfile>(`${API_BASE}/etf/${isin}`);
}

export async function getChartData(
  isin: string,
  period = "2y"
): Promise<ChartPoint[]> {
  return fetchJson<ChartPoint[]>(
    `${API_BASE}/chart/${isin}?period=${period}`
  );
}
