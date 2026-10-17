export interface Instrument {
  symbol: string;
  name: string;
  last: number;
  as_of: string;
  change_1d: number | null;
  change_1w: number | null;
  change_1m: number | null;
  change_3m: number | null;
  change_ytd: number | null;
  change_1y: number | null;
  above_sma50: boolean | null;
  above_sma200: boolean | null;
  from_52w_high: number | null;
  volatility_1m: number | null;
  spark: number[];
}

export interface MarketOverview {
  fetched_at: string;
  source: string;
  groups: { title: string; items: Instrument[] }[];
  missing: string[];
}
