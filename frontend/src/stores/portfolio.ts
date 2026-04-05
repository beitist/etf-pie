import { create } from "zustand";
import type { CountryLimit, ETFProfile, Position } from "../types";
import { getETFProfile } from "../lib/api";

interface PortfolioState {
  totalAmount: number;
  mode: "percent" | "euro";
  positions: Position[];
  limits: CountryLimit[];
  setTotalAmount: (amount: number) => void;
  toggleMode: () => void;
  addPosition: (isin: string, name: string) => void;
  removePosition: (isin: string) => void;
  setWeight: (isin: string, weight: number) => void;
  loadETFData: (isin: string) => Promise<void>;
  addLimit: (limit: CountryLimit) => void;
  removeLimit: (country: string) => void;
}

export const usePortfolioStore = create<PortfolioState>((set, get) => ({
  totalAmount: 1000,
  mode: "percent",
  positions: [],
  limits: [{ country: "USA", max: 60 }],

  setTotalAmount: (amount) => {
    set({ totalAmount: amount });
    // Recalculate euro amounts
    set((state) => ({
      positions: state.positions.map((p) => ({
        ...p,
        euroAmount: (p.weight / 100) * amount,
      })),
    }));
  },

  toggleMode: () =>
    set((state) => ({
      mode: state.mode === "percent" ? "euro" : "percent",
    })),

  addPosition: (isin, name) => {
    const { positions, totalAmount } = get();
    if (positions.some((p) => p.isin === isin)) return;

    const count = positions.length + 1;
    const equalWeight = Math.round((100 / count) * 100) / 100;
    const remainder = 100 - equalWeight * count;

    const newPositions: Position[] = [
      ...positions.map((p) => ({
        ...p,
        weight: equalWeight,
        euroAmount: (equalWeight / 100) * totalAmount,
      })),
      {
        isin,
        name,
        weight: equalWeight + remainder,
        euroAmount: ((equalWeight + remainder) / 100) * totalAmount,
        etfData: null,
      },
    ];

    set({ positions: newPositions });
    get().loadETFData(isin);
  },

  removePosition: (isin) => {
    const { positions, totalAmount } = get();
    const remaining = positions.filter((p) => p.isin !== isin);
    if (remaining.length === 0) {
      set({ positions: [] });
      return;
    }
    const totalWeight = remaining.reduce((s, p) => s + p.weight, 0);
    const scale = totalWeight > 0 ? 100 / totalWeight : 1;
    set({
      positions: remaining.map((p) => ({
        ...p,
        weight: Math.round(p.weight * scale * 100) / 100,
        euroAmount: ((p.weight * scale) / 100) * totalAmount,
      })),
    });
  },

  setWeight: (isin, newWeight) => {
    const { positions, totalAmount } = get();
    const clamped = Math.max(0, Math.min(100, newWeight));
    const others = positions.filter((p) => p.isin !== isin);
    const othersTotal = others.reduce((s, p) => s + p.weight, 0);
    const remaining = 100 - clamped;

    set({
      positions: positions.map((p) => {
        if (p.isin === isin) {
          return {
            ...p,
            weight: clamped,
            euroAmount: (clamped / 100) * totalAmount,
          };
        }
        // Proportionally adjust others
        const scale = othersTotal > 0 ? remaining / othersTotal : 0;
        const w = Math.round(p.weight * scale * 100) / 100;
        return {
          ...p,
          weight: w,
          euroAmount: (w / 100) * totalAmount,
        };
      }),
    });
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
}));
