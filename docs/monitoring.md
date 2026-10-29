# Monitoring

The run ledger retains input/unique expectations, actual audit decisions, runtime, reconciliation, curation-delay percentiles, and the event-ID fingerprint. The Spark progress table stores input and processed rates, trigger durations, source offsets, actual watermark, and actual watermark-drop counts. Those measurements feed the operations page.

Historical event age is separate from processing delay. The source's January 2025 date remains visible even when a replay finishes today. Curation lag is measured from the replay's ingestion timestamp to PostgreSQL fact commit, so it includes producer buffering and Spark startup. It is not exchange-to-user live latency.

Kafka catch-up lag is measured against the broker's offsets at completion. It is a point-in-time experiment measurement; another run can append new topic records later. The UI must not turn a completed run's zero backlog into a claim of perpetual current-feed health.

`/health` tests the database, not the entire topology. Prometheus-compatible metrics are available at `/metrics`. A production deployment would add broker, JVM/state-store, host, durable-storage, and API latency exporters plus alert delivery. The local repository does not claim those external alerts are running.

Useful operational conditions include failed replay status, nonzero outbox backlog, unreconciled accepted/window counts, unexpected watermark drops, and source checksum/schema failures. Thresholds depend on the permitted source and replay settings; historical data age alone is not a live-feed incident in replay mode.
