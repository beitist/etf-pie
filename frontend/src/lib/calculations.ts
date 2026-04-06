import type { AggregatedData, Allocation, MarketCap, Position } from "../types";

export function aggregatePortfolio(positions: Position[]): AggregatedData {
  const activePositions = positions.filter((p) => p.etfData && p.weight > 0);

  // Calculate coverage: % of portfolio that has country data
  const totalWeight = activePositions.reduce((s, p) => s + p.weight, 0);
  const coveredWeight = activePositions
    .filter((p) => p.etfData!.countries.length > 0)
    .reduce((s, p) => s + p.weight, 0);
  const coverage = totalWeight > 0 ? Math.round((coveredWeight / totalWeight) * 100) : 0;

  // Only use positions that have data for allocation charts
  const withCountries = activePositions.filter((p) => p.etfData!.countries.length > 0);
  const withSectors = activePositions.filter((p) => p.etfData!.sectors.length > 0);
  const withHoldings = activePositions.filter((p) => p.etfData!.holdings.length > 0);

  const countries = aggregateAllocations(
    withCountries.map((p) => ({
      weight: p.weight / 100,
      items: p.etfData!.countries,
    }))
  );

  const sectors = aggregateAllocations(
    withSectors.map((p) => ({
      weight: p.weight / 100,
      items: p.etfData!.sectors,
    }))
  );

  const holdings = aggregateAllocations(
    withHoldings.map((p) => ({
      weight: p.weight / 100,
      items: p.etfData!.holdings.map((h) => ({
        name: h.name,
        weight: h.weight,
      })),
    }))
  );

  const marketCap = aggregateMarketCap(activePositions);

  return { countries, sectors, holdings, marketCap, coverage };
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

  // Convert all values from 0-1 to percent, pull out "Sonstige"/"Other"
  let sonstigePct = 0;
  const entries: { name: string; weight: number }[] = [];

  for (const [name, weight] of map.entries()) {
    const pct = Math.round(weight * 10000) / 100;
    if (name.toLowerCase() === "sonstige" || name.toLowerCase() === "other") {
      sonstigePct += pct;
    } else {
      entries.push({ name, weight: pct });
    }
  }

  entries.sort((a, b) => b.weight - a.weight);

  // Top 10 + "Sonstige" (source "Sonstige" + overflow beyond top 10)
  const top = entries.slice(0, 10);
  const overflow = entries.slice(10).reduce((sum, a) => sum + a.weight, 0);
  const totalSonstige = Math.round((sonstigePct + overflow) * 100) / 100;
  if (totalSonstige > 0) {
    top.push({ name: "Sonstige", weight: totalSonstige });
  }

  // Normalize to 100% (source data may not sum to 100)
  const total = top.reduce((s, a) => s + a.weight, 0);
  if (total > 0 && Math.abs(total - 100) > 0.5) {
    const scale = 100 / total;
    for (const item of top) {
      item.weight = Math.round(item.weight * scale * 100) / 100;
    }
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
