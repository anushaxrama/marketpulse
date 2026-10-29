-- Choose the latest completed baseline; all output is historical, USDT quoted.
WITH chosen AS (
 SELECT id FROM ops.runs WHERE status='completed' AND scenario='baseline' ORDER BY created_at DESC LIMIT 1
)
SELECT b.symbol,count(*) observed_minutes,min(b.event_time) first_event,max(b.event_time) last_event,
 (array_agg(b.close ORDER BY b.event_time DESC))[1] last_close,
 sum(b.volume) executed_base_asset_volume
FROM marts.fact_bars b JOIN chosen r ON b.run_id=r.id GROUP BY b.symbol;

-- Prior-baseline exploratory return observations, not buy or sell signals.
WITH chosen AS (
 SELECT id FROM ops.runs WHERE status='completed' AND scenario='baseline' ORDER BY created_at DESC LIMIT 1
)
SELECT symbol,event_time,log_return,anomaly_score,baseline_n,realized_volatility,rolling_volatility
FROM marts.bar_features f JOIN chosen r ON f.run_id=r.id
WHERE abs(anomaly_score)>=3.5 ORDER BY abs(anomaly_score) DESC LIMIT 20;

-- Compare actual delivery decisions separately from market fact counts.
SELECT r.id,r.scenario,r.status,d.status delivery_decision,count(*) deliveries
FROM ops.runs r JOIN raw.deliveries d ON d.run_id=r.id
WHERE r.status='completed' GROUP BY r.id,r.scenario,r.status,d.status ORDER BY r.id;
