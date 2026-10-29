CREATE SCHEMA IF NOT EXISTS ops;
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS marts;
CREATE TABLE IF NOT EXISTS ops.schema_migrations(version integer PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS ops.datasets (
 id text PRIMARY KEY, day date NOT NULL, manifest jsonb NOT NULL, events integer NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS ops.runs (
 id uuid PRIMARY KEY, replay_id text NOT NULL, dataset_id text NOT NULL REFERENCES ops.datasets(id),
 scenario text NOT NULL, status text NOT NULL DEFAULT 'queued', window_minutes integer NOT NULL,
 watermark_minutes integer NOT NULL, speed integer NOT NULL DEFAULT 0,
 created_at timestamptz NOT NULL DEFAULT now(), started_at timestamptz, finished_at timestamptz,
 input_count integer, expected_count integer, error text, elapsed_seconds double precision,
 config jsonb NOT NULL DEFAULT '{}', result jsonb NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS raw.deliveries (
 topic text NOT NULL, partition integer NOT NULL, offset_id bigint NOT NULL,
 run_id uuid NOT NULL REFERENCES ops.runs(id), event_id text, status text NOT NULL,
 reason text, payload jsonb, received_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(topic,partition,offset_id)
);
CREATE TABLE IF NOT EXISTS marts.dim_symbols (
 symbol text PRIMARY KEY, base_asset text NOT NULL, currency text NOT NULL,
 exchange text NOT NULL, session text NOT NULL DEFAULT '24/7 UTC; no exchange holidays'
);
INSERT INTO marts.dim_symbols(symbol,base_asset,currency,exchange) VALUES
 ('BTCUSDT','BTC','USDT','Binance Spot'),('ETHUSDT','ETH','USDT','Binance Spot'),('SOLUSDT','SOL','USDT','Binance Spot') ON CONFLICT DO NOTHING;
CREATE TABLE IF NOT EXISTS marts.fact_bars (
 run_id uuid NOT NULL REFERENCES ops.runs(id), event_id text NOT NULL, symbol text NOT NULL REFERENCES marts.dim_symbols(symbol),
 event_time timestamptz NOT NULL, ingested_at timestamptz NOT NULL, loaded_at timestamptz NOT NULL DEFAULT now(),
 open numeric(28,12) NOT NULL CHECK(open>0), high numeric(28,12) NOT NULL CHECK(high>0), low numeric(28,12) NOT NULL CHECK(low>0),
 close numeric(28,12) NOT NULL CHECK(close>0), volume numeric(28,12) NOT NULL CHECK(volume>=0),
 provider text NOT NULL, currency text NOT NULL, payload_hash text NOT NULL, source_mode text NOT NULL,
 lineage jsonb NOT NULL, PRIMARY KEY(run_id,event_id), UNIQUE(run_id,symbol,event_time)
);
CREATE INDEX IF NOT EXISTS bars_time_idx ON marts.fact_bars(run_id,symbol,event_time);
CREATE TABLE IF NOT EXISTS ops.outbox (
 run_id uuid NOT NULL, event_id text NOT NULL, topic text NOT NULL, payload jsonb NOT NULL,
 sent_at timestamptz, PRIMARY KEY(run_id,event_id,topic)
);
CREATE TABLE IF NOT EXISTS ops.batches (
 run_id uuid NOT NULL, stage text NOT NULL, batch_id bigint NOT NULL, row_count integer NOT NULL,
 committed_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(run_id,stage,batch_id)
);
CREATE TABLE IF NOT EXISTS marts.stream_windows (
 run_id uuid NOT NULL REFERENCES ops.runs(id), symbol text NOT NULL,
 window_start timestamptz NOT NULL, window_end timestamptz NOT NULL,
 bar_count integer NOT NULL, open numeric(28,12) NOT NULL, close numeric(28,12) NOT NULL,
 high numeric(28,12) NOT NULL, low numeric(28,12) NOT NULL, volume numeric(28,12) NOT NULL,
 updated_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(run_id,symbol,window_start)
);
CREATE TABLE IF NOT EXISTS ops.progress (
 run_id uuid NOT NULL, stage text NOT NULL, batch_id bigint NOT NULL,
 input_rows bigint NOT NULL, dropped_by_watermark bigint NOT NULL, watermark text,
 input_rate double precision, processed_rate double precision, duration_ms bigint,
 offsets jsonb NOT NULL, recorded_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(run_id,stage,batch_id)
);
CREATE TABLE IF NOT EXISTS ops.faults (
 run_id uuid NOT NULL, fault text NOT NULL, injected_at timestamptz NOT NULL DEFAULT now(),
 details jsonb NOT NULL DEFAULT '{}', PRIMARY KEY(run_id,fault)
);
INSERT INTO ops.schema_migrations(version) VALUES(1) ON CONFLICT DO NOTHING;
