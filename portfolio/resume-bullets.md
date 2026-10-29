# Resume bullets

Use the version relevant to the role. Keep the historical-replay and local-verification context when discussing the project. Do not describe the optional Snowflake path as an operated production integration.

## Data Engineer

- Built a Kafka and PySpark Structured Streaming pipeline for 4,320 official one-minute market bars, with decimal-safe event contracts, event-time windows, watermarks, and source checksum verification.
- Implemented transactional PostgreSQL sinks, a curated-event outbox, raw delivery auditing, and a replay lab to inspect duplicates, late events, and recovery after a committed warehouse batch.

## Analytics Engineer

- Modeled bar facts, symbol/provider/session dimensions, stream windows, and data-quality records in version-controlled PostgreSQL SQL, with ten data checks and explicit gap handling.
- Defined adjacent log returns, contiguous moving averages, unannualized volatility, and prior-baseline anomaly scores; compared Spark OHLCV windows against independent SQL aggregation.

## Data Analyst

- Built a market-data dashboard that compares three crypto spot symbols while showing source dates, USDT quote units, executed base-asset volume, and historical replay status.
- Connected exploratory return flags with their statistical method and sample requirements, and exposed duplicate, invalid, and late-event counts alongside market charts.

## Backend / Software Engineer

- Developed a typed FastAPI and Next.js application with validated query parameters, decimal-string responses, bounded job submission, an origin-checked proxy, keyboard chart inspection, and CSV export.
- Tested transactional rollback, idempotent batch retries, malformed payload isolation, API failure states, and desktop/mobile user journeys; packaged the full local stack in Docker Compose with CI checks.

## Quantified claims to use carefully

The dataset size is a project input, not a business impact metric. Measured replay runtime and curation-delay percentiles are in `docs/benchmarks.md`. They include startup on one local machine and should not be turned into sustained production throughput or percentage improvements.
