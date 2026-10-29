# Streaming and recovery semantics

## Audit query

Spark reads `market.raw.v1` with explicit start offsets, `maxOffsetsPerTrigger=600`, and a checkpoint per run. Available-now mode consumes a bounded snapshot through the normal streaming source.

For every micro-batch, the loader obtains a transaction-scoped run lock. A committed `(run_id, raw, batch_id)` makes a retry a no-op. New raw offsets receive an audit decision. An accepted identity inserts a bar and an outbox row in the same transaction. Duplicate identities do not add facts. Conflicts and invalid envelopes create rejection decisions and dead-letter outbox records.

A failed database statement rolls the entire micro-batch back. A producer retry retains its first raw offsets, so earlier partially delivered messages remain within the audit boundary. Input delivery count comes from broker offsets after publication.

## Curated publication

The outbox publisher sends to Kafka and waits for acknowledgement before marking a row sent. A crash between those operations may resend a record. This is deliberate at-least-once behavior.

Within each raw micro-batch, accepted events are sent in event-time order. Late and reordered experiments change the actual source delivery sequence without modifying its prices or event timestamps.

## Window query

Spark parses decimal OHLCV fields, assigns a UTC timestamp column, applies `withWatermark`, and groups by run, symbol, and event-time window. `collect_set` retains bounded unique event/value structs per window. The sink calculates open/close from event-time order, high/low extrema, unique count, and exact decimal volume sum.

Watermarks follow Spark's observed event-time progress, not wall time. Late input can be excluded from aggregation after state is no longer eligible for updates. The audit fact remains present. Actual `numRowsDroppedByWatermark`, offset ranges, durations, and rates are retained from Spark progress records. Spark 4 offset representations are normalized as mappings, including null initial offsets, without executing strings as code.

Update-mode windows can remain provisional at the bounded replay's tail. No synthetic future bar is injected to finalize them. Different symbols can advance event time unevenly in a larger production feed; this bounded registry uses balanced symbol partitions for reproducible tests.

## Sink acknowledgement failure

The restart and warehouse-retry scenarios commit the first nonempty window batch and then deliberately raise before Spark receives a successful acknowledgement. The fault marker is itself durable. The query starts again with the same checkpoint, and the sink's committed batch ledger prevents the repeated callback from adding rows or volume.

This validates a specific crash boundary. It does not prove recovery from disk loss, a lost Kafka broker, corrupted checkpoints, or a multi-node outage.

## Reconciliation

For a completed run, raw decisions must sum to actual input deliveries. Unique accepted bar count must match expected source identities. Window bar count plus actual watermark drops must equal curated count. Event-ID fingerprints must match across successful scenarios using the same dataset.

The fingerprint checks identity sets. Independent SQL compares no-drop stream-window OHLCV values with a warehouse reference. Neither check is an end-to-end exactly-once guarantee across all external systems.
