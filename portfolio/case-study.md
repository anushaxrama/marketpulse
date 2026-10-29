# MarketPulse case study

## The problem

A price chart can look convincing while hiding a broken feed. Duplicate messages can inflate volume, an old event can change a closed interval, and a retry can write the same batch twice. MarketPulse pairs a market view with the operational records needed to explain those outcomes.

The project targets event-time processing and recovery. SignalFlow and AtlasIQ cover different engineering problems; this repository concentrates on Kafka, Spark watermarks, transactional warehouse sinks, and reproducible delivery experiments.

## Constraints

The default demonstration had to run without a paid account or market-data key. It also needed a real, attributable dataset rather than invented prices. I chose official Binance Vision one-minute spot bars for BTCUSDT, ETHUSDT, and SOLUSDT on January 6, 2025. That gives 4,320 source identities across three continuously traded markets.

This choice limits the claim: it is historical bar replay, not live tick processing. The source's non-commercial attribution and share-alike terms also apply to data derivatives. Source dates, quote asset, granularity, and license context remain visible in the application.

## Architecture

Python verifies archive checksums and normalizes decimal values into versioned events. Kafka assigns one partition to each registered symbol. A bounded Spark streaming query audits raw deliveries and writes accepted facts plus an outbox in a PostgreSQL transaction. The outbox publishes curated records to Kafka. A second Spark query applies event-time windows and a watermark before writing full window values through an idempotent sink.

FastAPI serves warehouse results. Next.js provides six views: market overview, symbol exploration, streaming operations, replay experiments, catalog, and architecture. The replay form is disabled by default and requires an explicit local flag and confirmation.

PostgreSQL makes the complete demonstration accessible locally. A separate Snowflake exporter implements stage, COPY, validation, MERGE, and a batch ledger, but account execution remains unverified because no credentials were supplied.

## Decisions that mattered

### Keep delivery identity separate from market identity

Raw records use `(topic, partition, offset)` so every delivery receives an audit decision. Accepted facts use `(run_id, event_id)`, with another uniqueness boundary on symbol and event minute. A duplicate can therefore increase delivery count without increasing market volume.

The loader in `services/warehouse_loader/postgres.py` records `(run_id, stage, batch_id)` in the same transaction as its writes. A repeated committed Spark callback can return without adding rows. The outbox has a different boundary: a crash after Kafka acknowledgement but before marking the row sent can resend it. The documentation calls that at least once.

### Use real Spark state

The window transformation in `services/stream_processor/processor.py` includes:

```python
parsed.withWatermark("event_time", f"{run['watermark_minutes']} minutes")
```

It groups by run, symbol, and event-time window, retaining unique event/value structs. The sink sorts those events to calculate open and close and sums decimal volume. This is bounded local state, not a claim that collecting events is suitable for unlimited tick traffic.

No synthetic future bar forces the last watermark forward. The replay's final update-mode windows can remain provisional. The late experiment retains the audited source facts while recording actual Spark watermark exclusions from the window view.

### Make recovery observable

The restart experiment commits a window batch, writes a durable fault marker, and raises before Spark receives successful acknowledgement. Restarting the query with the same checkpoint repeats the callback. The sink ledger suppresses the repeated write.

The warehouse-retry option exercises that same boundary. They are two named lab scenarios, not two independent infrastructure-failure mechanisms. Losing a broker, losing a checkpoint disk, and distributed failover remain outside the demonstrated scope.

### Define market calculations precisely

The SQL model only calculates a log return when the prior observation is exactly one minute earlier:

```sql
CASE WHEN event_time-prior_time=interval '1 minute'
     THEN ln(close/prior_close) END AS log_return
```

Missing intervals are visible rather than forward filled. Moving averages and volatility require a contiguous 20-bar span. The anomaly score compares the current return with 20 preceding available returns, so the current observation does not contaminate its own baseline. Synthetic spike and gap fixtures test that behavior. A flag is exploratory and never presented as a trading recommendation.

## Problems found during implementation

The Kafka image could not write its new named volume under its normal user. An isolated initialization service now sets ownership only on that broker volume.

Spark 4 progress objects returned offsets in both JSON-compatible and Python-literal forms, including null initial offsets. The first telemetry implementation failed after otherwise processed runs. A safe mapping parser now handles those representations, rejects non-mappings, and has focused regression tests. Failed development attempts remain in the local ledger.

Changing a chart from 24 hours to one hour retained an out-of-range inspection index. Clamping the active bar and synchronizing loading state fixed the runtime failure. Browser tests exercise the smaller series with keyboard input.

The containerized frontend's internal origin differed from its public loopback address. An explicit origin allowlist fixed legitimate replay submissions while preserving cross-origin rejection. A real browser launch was checked through the proxy after the fix.

## Testing and outcomes

The checked-in [verification report](../docs/verification.md) and [benchmark report](../docs/benchmarks.md) record exact counts, commands, run IDs, timings, and limitations. They link to machine-readable evidence rather than copying a performance claim without its conditions.

Tests cover event contracts, timestamp normalization, provider retry behavior, corrupt caches, SQL rollback, duplicate/conflicting records, API bounds, sink retries, missing intervals, synthetic anomalies, frontend helpers, and desktop/mobile journeys. Real Kafka and Spark runs validate the delivery scenarios separately from isolated fixtures. Independent PostgreSQL aggregation checks window OHLCV values exactly.

The useful outcome is a reproducible local system in which the same historical identities can be followed through changing delivery conditions. It is not a production market-data service, and it does not establish investment performance.

## Lessons

A replay ID and a run instance ID solve different problems. Configuration identity helps comparison; separate instance IDs and checkpoints preserve experiment isolation.

An aggregate can be complete relative to its watermark policy while excluding a valid historical fact. Keeping the audit and window views separate makes that policy visible.

Recovery claims need a named commit boundary and evidence. A batch ledger test supports a narrower, more defensible claim than saying the entire pipeline is exactly once.
