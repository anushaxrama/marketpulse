# Architecture decisions

## 01: Historical minute bars for the default demo

A reproducible source without a market-data key makes the local system reviewable. Official archives include checksums and usable one-minute OHLCV records. The tradeoff is explicit: the demo cannot claim current exchange prices, tick-level sequencing, or licensed live-feed behavior. The default adapter raises an unsupported-operation error for a live subscription.

## 02: PostgreSQL for local evaluation

PostgreSQL provides decimal arithmetic, transactions, constraints, SQL windows, and useful query plans without a paid warehouse. Operational identities and outbox records can share a transaction with the accepted bar facts. Snowflake export is implemented separately, and PostgreSQL test success is not treated as Snowflake compatibility proof.

## 03: Two Spark queries and a transactional outbox

The audit query retains all raw delivery decisions and unique facts. The window query can then apply real event-time state eviction without deleting late facts from the audit trail. The outbox avoids a database-commit/Kafka-publish gap. At-least-once outbox delivery is handled with bounded identity sets in the window state.

This adds a second Kafka topic and a publication ledger. It also makes the different durability boundaries visible and testable rather than claiming one transaction across all systems.

## 04: Fixed symbol partitions for this bounded registry

BTCUSDT, ETHUSDT, and SOLUSDT map to partitions 0, 1, and 2. The Kafka key remains the symbol. This makes partition ordering and replay batches reproducible and avoids accidental timestamp skew from hash collisions in a three-symbol test. A larger symbol universe needs a versioned partition-assignment strategy, skew monitoring, and explicit resharding behavior.

## 05: New checkpoint for each experiment instance

Window and watermark changes alter stateful-query semantics. Each new replay gets a fresh checkpoint; only recovery of the same instance reuses its state. A configuration-derived replay ID supports comparison while the instance UUID keeps state isolated.

## 06: Update-mode windows

The dashboard should show the final observed tail of a bounded dataset without generating artificial market records to advance time. Update mode provides provisional values. Only windows behind the measured watermark are eligible for state eviction. The final open tail is documented rather than called finalized.

## 07: Decimal storage and string-valued API prices

Prices and volumes use decimal types in Python, Spark, PostgreSQL, and Snowflake DDL. API serialization keeps them as strings. JavaScript numbers are used only for chart coordinates and formatted display. No trading, order sizing, or monetary settlement calculation runs in the browser.

## 08: Local control plane with bounded launch

The browser submits predefined scenarios and allowed settings. It cannot submit code, paths, SQL, symbols outside the registry, or arbitrary provider URLs. The worker queue is capped and disabled for browser launch unless explicitly enabled. Production authentication and multi-tenant scheduling would require a different control plane.
