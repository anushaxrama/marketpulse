# Measured local replay results

Measurements captured on October 29, 2026, on an ARM64 macOS host using Docker Desktop, Spark 4.0.4 `local[2]`, three Kafka partitions, and PostgreSQL 16. Other local projects shared the host. These are eight single-run observations, not a capacity test or a controlled comparison of scenario overhead.

Each run reads the same 4,320 official one-minute Binance Vision bars for January 6, 2025. Archives were cached before these runs. Runtime includes Kafka publication, JVM/Spark initialization, two available-now streaming queries, sink writes, and reconciliation. Queue wait and initial image/source downloads are excluded.

## Scenario measurements

| Scenario | Runtime, s | Accepted / s | Curation p50, s | Curation p95, s | Duplicate / invalid / late | Kafka backlog at completion |
| --- | ---: | ---: | ---: | ---: | --- | ---: |
| baseline | 29.68 | 145.6 | 12.22 | 20.79 | 0 / 0 / 0 | 0 |
| duplicate | 24.50 | 176.4 | 8.17 | 16.29 | 44 / 0 / 0 | 0 |
| late | 26.20 | 164.9 | 8.16 | 16.68 | 0 / 0 / 3 | 0 |
| reorder | 24.77 | 174.4 | 8.30 | 16.81 | 0 / 0 / 0 | 0 |
| outage | 25.89 | 166.9 | 8.36 | 16.76 | 0 / 0 / 0 | 0 |
| restart | 25.57 | 169.0 | 8.54 | 16.89 | 0 / 0 / 0 | 0 |
| warehouse_retry | 27.67 | 156.1 | 9.99 | 19.29 | 0 / 0 / 0 | 0 |
| poison | 26.40 | 163.6 | 8.23 | 17.10 | 0 / 1 / 0 | 0 |

Curation delay is measured per accepted bar from its replay ingestion timestamp to fact insertion timestamp. It includes buffering and Spark startup, and is not exchange-to-user latency. Accepted/s divides unique bars by the whole measured runtime, rather than selecting a fast Spark micro-batch. Zero backlog is a completion-time offset observation, not a claim that the topic remains idle forever.

Every scenario retained 4,320 unique facts with the same identity fingerprint. Duplicate delivery produced 44 extra records (44/4,364 = 1.008% of deliveries). The poison experiment produced one invalid synthetic envelope. The late experiment retained all source facts but represented 4,317 bars in windows and recorded three actual Spark watermark exclusions.

## Recovery boundary

| Scenario | Seconds from durable injected fault to completed replay |
| --- | ---: |
| restart | 3.336 |
| warehouse_retry | 3.259 |

These intervals include checkpoint retry and reconciliation after a committed sink batch lost acknowledgement. They are individual observations, not a recovery SLA or a measurement of host/process/broker failover. The one-second producer pause experiment is documented separately and should not be interpreted as an external provider outage.

## Window variants

| Window / watermark | Observed windows | Accepted facts | Runtime, s |
| --- | ---: | ---: | ---: |
| 1m / 2m | 4320 | 4320 | 25.11 |
| 5m / 10m | 864 | 4320 | 29.68 |
| 15m / 30m | 288 | 4320 | 24.61 |

All nine latest no-drop scenario/window configurations passed exact comparison of open, high, low, close, volume, and bar count against independent PostgreSQL aggregation. The late experiment is excluded from this particular equality check because its window membership intentionally differs from the accepted fact set.

## Analytical lookup

The captured lookup selected 60 ordered BTCUSDT close observations from the baseline run using `bars_time_idx`. This is one cached-buffer observation, not a latency distribution.
PostgreSQL planning: **0.266 ms**; execution: **0.040 ms**. Client wall time including a new connection and EXPLAIN: **12.05 ms**.

This lookup does not measure a full rolling-feature API response, cold storage, concurrent users, or network deployment. No before/after speedup is claimed.

## Reproduce and inspect

Run `make verify` to execute fresh scenarios. Run `uv run python scripts/verify_windows.py` after completing baseline 1m/2m and 15m/30m variants. `make benchmark` queues another measured baseline. Runtime varies with Docker allocation, cache state, and other host work.

Evidence: [stream runs and query plan](evidence/streaming-verification.json), [independent window comparisons](evidence/window-reference.json), [fault observations](evidence/recovery-observations.json). Reports derived from source observations retain [Binance Vision attribution and source-data terms](data-license.md).
