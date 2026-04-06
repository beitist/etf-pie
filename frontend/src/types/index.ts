export interface Allocation {
  name: string;
  weight: number;
}

export interface Holding {
  name: string;
  weight: number;
  country: string;
  sector: string;
}

export interface MarketCap {
  large: number;
  mid: number;
  small: number;
  micro: number;
}

export interface ETFProfile {
  name: string;
  isin: string;
  wkn: string;
  ter: number;
  replication: string;
  distribution: string;
  fund_size: string;
  currency: string;
  domicile: string;
  issuer: string;
  asset_class: string;
  benchmark: string;
  return_1m: number;
  return_3m: number;
  return_6m: number;
  return_1y: number;
  return_3y: number;
  return_5y: number;
  return_ytd: number;
  volatility_1y: number;
  proxy_isin: string;
  cheaper_isin: string;
  cheaper_name: string;
  cheaper_ter: number;
  countries: Allocation[];
  sectors: Allocation[];
  holdings: Holding[];
  market_cap: MarketCap;
}

export interface ETFSearchResult {
  name: string;
  isin: string;
  wkn: string;
  ter: number;
  replication: string;
  distribution: string;
}

export interface ChartPoint {
  date: string;
  close: number;
}

export interface Position {
  isin: string;
  name: string;
  weight: number;
  euroAmount: number;
  etfData: ETFProfile | null;
}

export interface CountryLimit {
  country: string;
  max: number;
}

export interface Portfolio {
  totalAmount: number;
  mode: "percent" | "euro";
  positions: Position[];
  limits: CountryLimit[];
}

export interface AggregatedData {
  countries: Allocation[];
  sectors: Allocation[];
  holdings: Allocation[];
  marketCap: MarketCap;
  coverage: number; // % of portfolio that has allocation data (0-100)
}
