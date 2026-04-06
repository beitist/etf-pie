import type { AggregatedData, Allocation, MarketCap, Position } from "../types";

export function aggregatePortfolio(positions: Position[]): AggregatedData {
  const activePositions = positions.filter((p) => p.etfData && p.weight > 0);

  const countries = aggregateAllocations(
    activePositions.map((p) => ({
      weight: p.weight / 100,
      items: p.etfData!.countries,
    }))
  );

  const sectors = aggregateAllocations(
    activePositions.map((p) => ({
      weight: p.weight / 100,
      items: p.etfData!.sectors,
    }))
  );

  const holdingsRaw = aggregateAllocations(
    activePositions.map((p) => ({
      weight: p.weight / 100,
      items: p.etfData!.holdings.map((h) => ({
        name: h.name,
        weight: h.weight,
      })),
    }))
  );
  // Normalize holdings to 100% (source data only covers top positions)
  const holdingsTotal = holdingsRaw.reduce((s, h) => s + h.weight, 0);
  const holdings = holdingsTotal > 0
    ? holdingsRaw.map((h) => ({
        ...h,
        weight: Math.round((h.weight / holdingsTotal) * 10000) / 100,
      }))
    : holdingsRaw;

  const marketCap = aggregateMarketCap(activePositions);

  return { countries, sectors, holdings, marketCap };
}

function aggregateAllocations(
  sources: { weight: number; items: Allocation[] }[]
): Allocation[] {
  const map = new Map<string, number>();

  for (const source of sources) {
    for (const item of source.items) {
      const key = item.name.trim();
      const current = map.get(key) || 0;
      map.set(key, current + source.weight * (item.weight / 100));
    }
  }

  // Pull out any existing "Sonstige"/"Other" entries and merge them
  let sonstigeWeight = 0;
  const entries = Array.from(map.entries()).filter(([name, weight]) => {
    if (name.toLowerCase() === "sonstige" || name.toLowerCase() === "other") {
      sonstigeWeight += weight;
      return false;
    }
    return true;
  });

  const result = entries
    .map(([name, weight]) => ({ name, weight: Math.round(weight * 10000) / 100 }))
    .sort((a, b) => b.weight - a.weight);

  // Top 10 + "Sonstige" (including source "Sonstige" entries + overflow)
  const top = result.slice(0, 10);
  const rest = result.slice(10).reduce((sum, a) => sum + a.weight, 0);
  const totalSonstige = Math.round((rest + sonstigeWeight * 100) * 100) / 100;
  if (totalSonstige > 0) {
    top.push({ name: "Sonstige", weight: totalSonstige });
  }
  return top;
}

function aggregateMarketCap(positions: Position[]): MarketCap {
  const mc: MarketCap = { large: 0, mid: 0, small: 0, micro: 0 };
  for (const p of positions) {
    if (!p.etfData) continue;
    const w = p.weight / 100;
    mc.large += w * p.etfData.market_cap.large;
    mc.mid += w * p.etfData.market_cap.mid;
    mc.small += w * p.etfData.market_cap.small;
    mc.micro += w * p.etfData.market_cap.micro;
  }
  mc.large = Math.round(mc.large * 100) / 100;
  mc.mid = Math.round(mc.mid * 100) / 100;
  mc.small = Math.round(mc.small * 100) / 100;
  mc.micro = Math.round(mc.micro * 100) / 100;
  return mc;
}

export function findOverlaps(
  positions: Position[]
): { name: string; etfs: string[] }[] {
  const holdingMap = new Map<string, Set<string>>();

  for (const p of positions) {
    if (!p.etfData) continue;
    for (const h of p.etfData.holdings) {
      const key = h.name.trim();
      if (!holdingMap.has(key)) holdingMap.set(key, new Set());
      holdingMap.get(key)!.add(p.etfData.name);
    }
  }

  return Array.from(holdingMap.entries())
    .filter(([, etfs]) => etfs.size > 1)
    .map(([name, etfs]) => ({ name, etfs: Array.from(etfs) }))
    .sort((a, b) => b.etfs.length - a.etfs.length);
}
