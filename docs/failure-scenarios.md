# Failure experiments

The local lab changes delivery behavior around real historical bars. Synthetic financial fixtures remain in the test database, and the invalid envelope in the poison experiment is explicitly labeled synthetic.

- Duplicate delivery: the source identity is delivered 44 extra times in the default dataset. The raw ledger records each distinct Kafka offset; the curated fact count remains 4,320.
- Late arrival: the first bar of each symbol is held until the end. The default watermark experiment records three actual Spark drops from window aggregation, while all 4,320 facts remain.
- Reorder: a seeded shuffle changes three-minute delivery blocks. Default ten-minute tolerance should preserve the unique window representation.
- Producer pause: one second of deliberate local inactivity occurs before delivery. It is not evidence of a real provider outage.
- Checkpoint restart and warehouse retry: both interrupt after a committed window batch. A durable fault record prevents repeated injection, and restarting the query uses the same checkpoint and sink ledger.
- Poison envelope: an unsupported schema and invalid price are rejected and routed through the dead-letter outbox, never treated as a price or volume observation.

Fixture-level tests separately cover HTTP 429/503 retries, permanent 404 handling, byte budgets, corrupt caches, malformed payloads, source timestamp units, explicit-offset DST transitions, transaction rollback, identity conflicts, and interrupted producer publication. These unit/integration fixtures are not recorded as observed market incidents.

Expected and observed values are retained in the run records and generated verification evidence. A failed experiment remains failed until a genuinely successful new execution or recovery completes; the code does not substitute an expected result into the dashboard.
