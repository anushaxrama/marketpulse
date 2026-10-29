CREATE OR REPLACE VIEW marts.dim_providers AS
 SELECT DISTINCT provider,currency,source_mode FROM marts.fact_bars;
CREATE OR REPLACE VIEW marts.dim_calendar AS
 SELECT DISTINCT event_time::date AS utc_date,extract(isodow from event_time)::integer AS weekday,
 '24/7 spot market; no equity-session calendar'::text AS session FROM marts.fact_bars;
CREATE OR REPLACE VIEW marts.fact_data_quality_events AS
 SELECT run_id,topic,partition,offset_id,event_id,status,reason,received_at FROM raw.deliveries WHERE status<>'accepted';
CREATE OR REPLACE VIEW marts.bar_features AS
WITH previous AS (
 SELECT *,lag(close) OVER w AS prior_close,lag(event_time) OVER w AS prior_time
 FROM marts.fact_bars WINDOW w AS(PARTITION BY run_id,symbol ORDER BY event_time)
), returns AS (
 SELECT *,CASE WHEN event_time-prior_time=interval '1 minute' THEN ln(close/prior_close) END AS log_return,
 CASE WHEN prior_time IS NOT NULL AND event_time-prior_time<>interval '1 minute' THEN true ELSE false END AS gap_before
 FROM previous
), features AS (
 SELECT *,count(log_return) OVER p AS baseline_n,avg(log_return) OVER p AS baseline_mean,
 stddev_samp(log_return) OVER p AS baseline_std,avg(close) OVER a AS moving_average_20,
 count(*) OVER a AS moving_n,first_value(event_time) OVER a AS moving_start,
 stddev_samp(log_return) OVER a AS rolling_volatility
 FROM returns
 WINDOW p AS(PARTITION BY run_id,symbol ORDER BY event_time ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING),
 a AS(PARTITION BY run_id,symbol ORDER BY event_time ROWS BETWEEN 19 PRECEDING AND CURRENT ROW)
)
SELECT run_id,event_id,symbol,event_time,open,high,low,close,volume,log_return,gap_before,
 CASE WHEN moving_n=20 AND event_time-moving_start=interval '19 minutes' THEN moving_average_20 END AS moving_average_20,
 CASE WHEN moving_n=20 AND event_time-moving_start=interval '19 minutes' THEN rolling_volatility END AS rolling_volatility,
 CASE WHEN baseline_n=20 AND log_return IS NOT NULL THEN (log_return-baseline_mean)/greatest(baseline_std,.00000001) END AS anomaly_score,
 baseline_n
FROM features;
INSERT INTO ops.schema_migrations(version) VALUES(2) ON CONFLICT DO NOTHING;
