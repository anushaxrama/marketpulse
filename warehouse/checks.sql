SELECT 'invalid_ohlc' AS check_name,count(*)::bigint AS failures FROM marts.fact_bars
WHERE open<=0 OR close<=0 OR high<greatest(open,close) OR low>least(open,close) OR volume<0
UNION ALL SELECT 'duplicate_bar_identity',count(*) FROM
 (SELECT run_id,event_id FROM marts.fact_bars GROUP BY 1,2 HAVING count(*)>1) d
UNION ALL SELECT 'duplicate_symbol_minute',count(*) FROM
 (SELECT run_id,symbol,event_time FROM marts.fact_bars GROUP BY 1,2,3 HAVING count(*)>1) d
UNION ALL SELECT 'missing_run_relationship',count(*) FROM marts.fact_bars b LEFT JOIN ops.runs r ON r.id=b.run_id WHERE r.id IS NULL
UNION ALL SELECT 'missing_symbol_relationship',count(*) FROM marts.fact_bars b LEFT JOIN marts.dim_symbols s USING(symbol) WHERE s.symbol IS NULL
UNION ALL SELECT 'unknown_mode',count(*) FROM marts.fact_bars WHERE source_mode NOT IN ('historical_replay','synthetic_test','live','delayed')
UNION ALL SELECT 'accepted_fact_mismatch',count(*) FROM ops.runs r WHERE r.status='completed' AND
 (SELECT count(*) FROM raw.deliveries d WHERE d.run_id=r.id AND d.status='accepted')<>(SELECT count(*) FROM marts.fact_bars b WHERE b.run_id=r.id)
UNION ALL SELECT 'unpublished_outbox',count(*) FROM ops.outbox o JOIN ops.runs r ON r.id=o.run_id WHERE r.status='completed' AND o.sent_at IS NULL
UNION ALL SELECT 'off_minute_bar',count(*) FROM marts.fact_bars WHERE event_time<>date_trunc('minute',event_time)
UNION ALL SELECT 'invalid_stream_window',count(*) FROM marts.stream_windows WHERE bar_count<=0 OR open<=0 OR close<=0 OR volume<0 OR window_end<=window_start;
