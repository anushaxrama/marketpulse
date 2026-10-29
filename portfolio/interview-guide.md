# Interview guide

## 1. Why use a historical feed?

It makes the default system runnable without paid credentials while retaining real provenance. The provider downloads official daily minute-bar archives and checks their published hashes. The UI labels historical replay throughout; processing an old event today does not make it live.

## 2. What does one event represent?

An executed one-minute OHLCV bar for one symbol. `MarketEvent` carries close price, open/high/low, base-asset volume, UTC timestamps, schema version, source mode, and payload hash. Quote snapshots cannot enter this bar loader as executed volume.

## 3. How are Kafka partitions chosen?

The three registered symbols map to explicit partitions 0, 1, and 2, with the symbol also used as the message key. This preserves each symbol's source-delivery order locally. Increasing partitions changes ordering assumptions and requires a migration plan; the fixed mapping is not general elastic partitioning.

## 4. Which IDs solve which problems?

Topic/partition/offset identifies a delivery. A deterministic event hash identifies a source observation. A replay ID identifies the dataset, scenario, window, watermark, and seed. A UUID identifies an individual experiment and its checkpoints. Keeping these separate makes retries and comparisons explainable.

## 5. Why two Spark queries?

The raw query audits and validates before curated publication. The window query consumes accepted events and applies actual event-time state. The transactional outbox bridges the first database commit and Kafka publication without pretending those systems share a transaction.

## 6. What does the watermark guarantee?

It controls Spark state eligibility using observed event time. It does not measure wall-clock freshness and does not guarantee every old event enters an aggregate. In the late experiment the held first bars remain in accepted facts while actual Spark watermark-drop counters explain their absence from windows.

## 7. Why can the last window remain provisional?

Available-now processing ends on a bounded snapshot. No later event necessarily advances the watermark beyond the tail. Update mode therefore exposes the observed aggregate without claiming every final window is closed.

## 8. Where is idempotency implemented?

PostgreSQL facts use `(run_id,event_id)` and a symbol/minute uniqueness constraint. Sink batch records use `(run_id,stage,batch_id)` in the same transaction as writes. Window values replace complete observed aggregates rather than adding a retry's volume again.

## 9. Is the entire pipeline exactly once?

No. Outbox publication is at least once: a crash after Kafka acknowledgement but before recording `sent_at` can resend a message. The window's unique event/value set suppresses identical redelivery while its state remains eligible. Kafka, Spark, PostgreSQL, and Snowflake have separate commit boundaries.

## 10. What recovery was actually exercised?

A first nonempty window batch commits, a durable fault marker is written, and an exception interrupts acknowledgement. The same query restarts from its checkpoint; the sink ledger makes the repeated callback a no-op. This is not evidence of disk-loss recovery or multi-node failover.

## 11. How do you handle malformed or conflicting events?

Pydantic and loader checks reject unsupported versions, nonfinite/invalid prices, bad timestamps, and incompatible bar values. The delivery ledger retains a reason. Dead-letter records go through the outbox. An existing identity with different content is quarantined rather than silently overwriting accepted facts.

## 12. What happens if publication stops halfway?

The first raw offsets are committed before publishing. A retry retains them, so earlier deliveries stay inside the audit boundary. Actual input count is measured from broker offset differences after publication, including repeated deliveries. A regression fixture exercises interrupted publication.

## 13. How does Snowflake loading work?

The optional exporter serializes accepted rows, stages a JSON file, uses COPY into staging, validates counts and identity conflicts, then executes MERGE plus a batch-ledger write transaction. Explicit execution permission and existing account resources are required. The code is implemented, but real account behavior remains unverified without credentials.

## 14. Does Snowflake enforce the same uniqueness as PostgreSQL?

No. Snowflake constraints are informational in this path. Export jobs must be serialized and conflicts checked explicitly. Concurrent account-level exporters are not tested. PostgreSQL uniqueness tests cannot substitute for a real Snowflake integration test.

## 15. Why use decimal strings in the API?

Stored financial values remain decimal in validation, Spark, and PostgreSQL. JSON responses serialize Decimal as strings rather than silently converting to binary floating point. The browser converts values only for visualization and display; it is not the analytical storage layer.

## 16. How are gaps and volatility handled?

A log return exists only when observations are exactly one minute apart. Gaps are flagged, not filled. Twenty-bar moving measures require a contiguous 19-minute span. Realized volatility is the square root of summed available squared log returns, separate from rolling sample standard deviation and without annualization.

## 17. How are anomaly flags explained and tested?

The current return is compared with 20 preceding available returns using a z-score and a denominator floor. The dashboard uses a 3.5 threshold. Labeled synthetic spike tests verify the prior baseline and gap tests verify missing-return behavior. Regime changes, sparse history, and multiple comparisons limit interpretation.

## 18. What do the measurements mean?

Replay runtime includes publishing, JVM startup, both streaming queries, and database work on one local driver. Curation delay runs from replay ingestion timestamp to fact load timestamp. Kafka lag is sampled at completion. None is exchange-to-user live latency or sustained cluster throughput.

## 19. What would you change for a larger deployment?

Replace bounded driver-side collection with distributed sink/staging work, use durable shared checkpoints, authenticated job submission, managed secrets, replicated brokers, retention budgets, and external exporters. Capacity and cost estimates need real event volume, retention, source licensing, region, and uptime assumptions before provisioning.

## 20. What evidence is strongest and what remains uncertain?

The strongest local evidence is real Kafka/Spark scenario execution, source checksum lineage, transactional rollback/retry tests, exact independent OHLCV comparisons, and browser tests over populated warehouse data. Snowflake account execution, licensed live feeds, hosted authentication, distributed failure recovery, and long-running load remain unverified. The status JSON keeps those distinctions machine readable.
