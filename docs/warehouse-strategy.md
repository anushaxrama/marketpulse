# Warehouse strategy

## Local PostgreSQL

Numbered migrations apply once under an advisory lock. The first migration creates operational and fact storage, the second adds feature views, and the third adds realized-volatility output without editing an already-applied schema contract.

The primary fact key is `(run_id,event_id)`, with a second uniqueness constraint on `(run_id,symbol,event_time)`. A B-tree on run, symbol, and event time supports bounded symbol queries. Source and run relationships are enforced locally. The ten SQL checks in `warehouse/checks.sql` cover OHLC bounds, uniqueness, relationships, modes, accepted/fact counts, outbox completion, minute alignment, and window shape.

`marts.stream_windows` stores complete observed window values. Upserts and their batch-ledger row commit together. There is no additive update that could double volume on a repeated batch.

## Optional Snowflake

`services/warehouse_loader/snowflake.py` uses the official Python connector. It requires an existing account, user, private-key file, warehouse, database, and schema. It does not create a warehouse, user, key, role, or paid service.

The explicit CLI command is:

```sh
uv sync --frozen --extra snowflake
uv run marketpulse snowflake --run-id YOUR_COMPLETED_RUN_UUID --execute
```

The exporter reads one local run's curated rows and calculates a SHA-256 batch ID from its serialized content. It creates an internal stage and target/ledger tables in the supplied schema, uploads compressed JSON, COPYs into a session-local staging table, and validates the stage count. Conflicting existing event hashes abort the merge. MERGE and batch-ledger insertion share a transaction.

A repeated serialized export returns `already_loaded` from the ledger. Snowflake key constraints do not enforce uniqueness, so this implementation requires serialized exporters. Concurrent account-level exports and account-specific permissions remain unverified. Staging/COPY happen outside the final MERGE transaction; staging objects can remain after a failure and need retention/cleanup.

Snowflake timestamps use `TIMESTAMP_TZ`; financial values use `NUMBER(28,12)`. PostgreSQL query plans, indexes, and constraints do not demonstrate Snowflake clustering behavior or cost. No clustering key or warehouse-size improvement is claimed without an account measurement.

## Verification status and teardown

The source code and SQL path exist, and configuration guards are tested. The actual account integration test is skipped unless `MP_TEST_SNOWFLAKE=true` and `MP_SNOWFLAKE_TEST_RUN_ID` identify an explicitly permitted run. No credentials were supplied during the local build, so PUT/COPY/MERGE account execution remains unverified.

A user running this path needs CREATE STAGE/TABLE and usage privileges in the configured existing resources, plus permission to use that warehouse. Those commands can consume credits. After testing, remove only this project's stage files and objects according to the account's retention policy. Never drop the user's database, schema, or shared warehouse as an automatic cleanup step.
