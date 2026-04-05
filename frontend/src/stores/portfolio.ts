import { create } from "zustand";
import type { CountryLimit, ETFProfile, Position } from "../types";
import { getETFProfile } from "../lib/api";

interface PortfolioState {
  positions: Position[];
  limits: CountryLimit[];
  // Computed
  totalAmount: number;
  // Actions
  addPosition: (isin: string, name: string) => void;
  removePosition: (isin: string) => void;
  setEuroAmount: (isin: string, euro: number) => void;
  loadETFData: (isin: string) => Promise<void>;
  addLimit: (limit: CountryLimit) => void;
  removeLimit: (country: string) => void;
  getShareURL: () => string;
  loadFromURL: () => void;
}

function recalcWeights(positions: Position[]): Position[] {
  const total = positions.reduce((s, p) => s + p.euroAmount, 0);
  return positions.map((p) => ({
    ...p,
    weight: total > 0 ? (p.euroAmount / total) * 100 : 0,
  }));
}

function encodePortfolio(positions: Position[]): string {
  if (positions.length === 0) return "";
  const p = positions.map((pos) => `${pos.isin}:${pos.euroAmount}`).join(",");
  return `#p=${p}`;
}

function decodePortfolio(hash: string): { entries: { isin: string; euro: number }[] } | null {
  if (!hash || !hash.startsWith("#")) return null;
  const params = new URLSearchParams(hash.slice(1));
  const p = params.get("p");
  if (!p) return null;
  const entries = p.split(",").map((s) => {
    const [isin, val] = s.split(":");
    return { isin, euro: Number(val) };
  }).filter((e) => e.isin && !isNaN(e.euro));
  if (entries.length === 0) return null;
  return { entries };
}

export const usePortfolioStore = create<PortfolioState>((set, get) => ({
  positions: [],
  limits: [{ country: "USA", max: 60 }],
  totalAmount: 0,

  addPosition: (isin, name) => {
    const { positions } = get();
    if (positions.some((p) => p.isin === isin)) return;

    const newPos: Position = {
      isin,
      name,
      weight: 0,
      euroAmount: 100,
      etfData: null,
    };

    const updated = recalcWeights([...positions, newPos]);
    const total = updated.reduce((s, p) => s + p.euroAmount, 0);
    set({ positions: updated, totalAmount: total });
    get().loadETFData(isin);
  },

  removePosition: (isin) => {
    const { positions } = get();
    const remaining = positions.filter((p) => p.isin !== isin);
    const updated = recalcWeights(remaining);
    const total = updated.reduce((s, p) => s + p.euroAmount, 0);
    set({ positions: updated, totalAmount: total });
  },

  setEuroAmount: (isin, euro) => {
    const { positions } = get();
    const clamped = Math.max(0, euro);
    const updated = recalcWeights(
      positions.map((p) =>
        p.isin === isin ? { ...p, euroAmount: clamped } : p
      )
    );
    const total = updated.reduce((s, p) => s + p.euroAmount, 0);
    set({ positions: updated, totalAmount: total });
  },

  loadETFData: async (isin) => {
    try {
      const data: ETFProfile = await getETFProfile(isin);
      set((state) => ({
        positions: state.positions.map((p) =>
          p.isin === isin ? { ...p, etfData: data, name: data.name } : p
        ),
      }));
    } catch (e) {
      console.error("Failed to load ETF data:", isin, e);
    }
  },

  addLimit: (limit) =>
    set((state) => ({
      limits: [
        ...state.limits.filter((l) => l.country !== limit.country),
        limit,
      ],
    })),

  removeLimit: (country) =>
    set((state) => ({
      limits: state.limits.filter((l) => l.country !== country),
    })),

  getShareURL: () => {
    const { positions } = get();
    const hash = encodePortfolio(positions);
    return `${window.location.origin}${window.location.pathname}${hash}`;
  },

  loadFromURL: () => {
    const decoded = decodePortfolio(window.location.hash);
    if (!decoded) return;
    const { entries } = decoded;
    const positions: Position[] = entries.map((e) => ({
      isin: e.isin,
      name: e.isin,
      weight: 0,
      euroAmount: e.euro,
      etfData: null,
    }));
    const updated = recalcWeights(positions);
    const total = updated.reduce((s, p) => s + p.euroAmount, 0);
    set({ positions: updated, totalAmount: total });
    for (const e of entries) {
      get().loadETFData(e.isin);
    }
  },
}));
