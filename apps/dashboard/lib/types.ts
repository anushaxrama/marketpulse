export type Result = {
  kafka_lag_at_completion: number;
  accepted: number;
  duplicates: number;
  invalid: number;
  conflicts: number;
  delivered: number;
  window_bars: number;
  windows: number;
  late_dropped_from_windows: number;
  reconciled: boolean;
  expected_unique: number;
  lag_p50_seconds: number;
  lag_p95_seconds: number;
  accepted_events_per_second: number;
  event_id_fingerprint: string;
  faults: { fault: string; details: Record<string, unknown> }[];
};
export type Run = {
  id: string;
  replay_id: string;
  dataset_id: string;
  scenario: string;
  status: string;
  window_minutes: number;
  watermark_minutes: number;
  speed: number;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  input_count: number;
  expected_count: number;
  error: string | null;
  elapsed_seconds: number | null;
  result: Partial<Result>;
};
export type Bar = {
  event_id: string;
  symbol: string;
  event_time: string;
  open: string;
  close: string;
  high: string;
  low: string;
  volume: string;
  log_return: string | null;
  moving_average_20: string | null;
  rolling_volatility: string | null;
  realized_volatility: string | null;
  anomaly_score: string | null;
  gap_before: boolean;
};
export type SymbolRow = {
  symbol: string;
  bars: number;
  first_event: string;
  last_event: string;
  first_close: string;
  last_close: string;
  base_volume: string;
  return_pct: string;
};
export type Dataset = {
  id: string;
  day: string;
  events: number;
  manifest: {
    sources: {
      symbol: string;
      url: string;
      sha256: string;
      bytes: number;
      rows: number;
    }[];
    license_url: string;
  };
};
export type Overview = {
  run: Run | null;
  dataset: Dataset | null;
  symbols: SymbolRow[];
  lab_enabled: boolean;
};
export type Progress = {
  stage: string;
  batch_id: number;
  input_rows: number;
  dropped_by_watermark: number;
  watermark: string | null;
  processed_rate: number;
  input_rate: number;
  duration_ms: number;
  offsets: unknown;
};
export type Operations = {
  run: Run | null;
  deliveries: { status: string; count: number }[];
  progress: Progress[];
  batches: { stage: string; committed_batches: number; written_rows: number }[];
  outbox_pending: number;
  quality: { status: string; reason: string; count: number }[];
};
export type Catalog = {
  symbols: {
    symbol: string;
    base_asset: string;
    currency: string;
    exchange: string;
    session: string;
  }[];
  datasets: Dataset[];
  definitions: Record<string, string>;
  lab_enabled: boolean;
  scenarios: string[];
};
