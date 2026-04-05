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
}
