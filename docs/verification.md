# Verification record

Checked locally on October 29, 2026. Source code, isolated fixtures, actual streaming experiments, and account-dependent integrations have different evidence boundaries.

## Local checks

| Check | Observed outcome |
| --- | --- |
| Python contracts, provider, warehouse, API, and recovery tests | **33 passed, 1 skipped**, 2.03 seconds on final local run |
| Skipped test | Real Snowflake account round trip; no account credentials supplied |
| Python lint and formatting | Ruff passed; 25 files formatted correctly |
| Python types | Mypy passed across 17 source files |
| Frontend types and formatting | TypeScript and Prettier passed |
| Chart helper tests | **2 passed** |
| Desktop/mobile browser journeys | **8 passed**, 11.0 seconds on release build |
| Actual Kafka/Spark scenario suite | **8 completed and reconciled** |
| Warehouse data checks | **10 checks, zero failures** |
| Independent OHLCV reference | **9 scenario/window configurations, zero exact-value mismatches** |
| Isolated clean source and fresh volumes | Completed; 4,320 accepted bars and 864 five-minute windows |
| Base Python dependency audit | No known vulnerabilities reported across 20 locked base packages |
| Frontend production dependency audit | No advisories reported; 60 dependencies including optional platform packages |

The Python run emits a Starlette/httpx TestClient deprecation warning. Tests pass, but a future dependency update should address that compatibility warning. Audits are observations of the package databases at the time of execution, not guarantees. They do not cover container operating-system packages, JVM connector vulnerabilities, or the optional Snowflake dependency set.

Browser journeys cover all six views, document overflow, runtime errors, symbol/range changes, keyboard inspection, downloaded CSV contents, empty search, injected API outage/recovery, local-form confirmation, and theme persistence. They use desktop and mobile Chromium. Mobile emulation is not real-device Safari testing. Form workflow tests stub their submission response to avoid unbounded job creation; a separate real browser launch queued and completed the 15m/30m baseline run `079da867-8d5c-4eaf-9578-55863d152e68` through the actual proxy/API/worker path.

## Commands executed

```sh
MP_TEST_DATABASE_URL=postgresql://marketpulse:marketpulse_local@127.0.0.1:5546/marketpulse_test .venv/bin/pytest -q
.venv/bin/ruff check marketpulse services tests scripts infra
.venv/bin/ruff format --check marketpulse services tests scripts infra
.venv/bin/mypy marketpulse services
pnpm --dir apps/dashboard typecheck
pnpm --dir apps/dashboard format:check
pnpm --dir apps/dashboard test
PLAYWRIGHT_USE_CHROME=1 pnpm --dir apps/dashboard test:e2e
.venv/bin/python scripts/verify_streaming.py
.venv/bin/python scripts/verify_windows.py
docker compose build api runner dashboard
```

The Docker frontend build runs `pnpm build`. Python auditing used a base requirements export from the frozen uv lock with pip-audit 2.9.0. Frontend auditing used `pnpm --dir apps/dashboard audit --prod --json`.

## Actual streaming outcomes

The [scenario evidence](evidence/streaming-verification.json) retains run IDs, deterministic replay IDs, source checksums, Spark progress-derived counts, latency percentiles, runtime, reconciliation, data checks, and the query plan.

Every scenario accepted 4,320 unique source bars with the same event-ID fingerprint. Duplicate delivery produced 44 audited duplicates. Poison delivery produced one invalid synthetic envelope and a dead-letter outbox record. A separate read of the actual Kafka dead-letter topic found exactly one matching record for the final poison run, with its rejection reason and original delivery offset; see [broker evidence](evidence/deadletter-observation.json). Late arrival produced three actual Spark watermark drops with all 4,320 facts retained. Restart and warehouse retry each recorded the injected post-commit acknowledgement failure and completed without doubled window values.

Independent SQL uses `date_bin`, ordered open/close selection, extrema, decimal volume sum, and count. It compares those values with actual Spark sink results. The [reference evidence](evidence/window-reference.json) includes 1m/2m, 5m/10m, and 15m/30m baseline configurations. Late runs are excluded from this equality check because their window membership deliberately excludes old events; their completeness is checked separately using actual watermark counts.

Failed development attempts remain in the local ledger. An offset-telemetry parser initially rejected Spark 4's dictionary-string and null initial-offset representations after processing had occurred. Focused regression tests and final fresh successful runs followed the fix. The evidence selects completed final runs; it does not erase earlier failures or count them as successful.

## Clean setup

A Git archive of implementation commit `e71cfc95ab2c02495b97e402ff61bf8c3d5d4645` was extracted into an empty temporary directory. No native virtual environment, frontend modules, source cache, checkpoint, or database was copied. Docker reused dependency-layer build cache, so this is not an uncached image-download benchmark.

A separate Compose project named `marketpulse-clean` used new broker, database, and replay-data volumes. A temporary override removed host-port bindings to coexist with the main demo; internal service names and application commands stayed the same. The start and demo commands are recorded exactly in [clean-checkout evidence](evidence/clean-checkout.json).

The clean stack downloaded and verified the source archives, completed a baseline, returned all three symbols through the dashboard proxy, and passed ten SQL checks. It produced 4,320 accepted facts, 864 windows, zero Kafka backlog at completion, and the same identity fingerprint as the main stack. Start through verification took 57.53 seconds with built images. The baseline itself took 35.85 seconds. Initial image builds and downloads are excluded.

Only the disposable `marketpulse-clean` resources were removed afterward. The main local worker was restored. The default loopback ports were separately exercised in the release browser suite.

## Verification boundaries

Snowflake's actual COPY/MERGE behavior, licensed live subscriptions, cloud deployment, multi-broker replication, distributed Spark recovery, checkpoint disk loss, long-running throughput, authentication, and real-device accessibility are not verified. No hosted URL is claimed. See [benchmarks](benchmarks.md), [streaming semantics](streaming-semantics.md), and the [status JSON](../portfolio/project-status.json).

## GitHub CI

[Implementation CI run #1](https://github.com/anushaxrama/marketpulse/actions/runs/40965637194) passed on GitHub in 1m 1s for commit `e71cfc9`. It runs isolated PostgreSQL/Python checks, frontend type/format/helper/build checks, Compose validation, and dependency audits. The real-stream and populated-browser suites are documented local checks, not silently claimed as part of this shorter CI job. GitHub reported a Node 20 action-runtime deprecation annotation while running those actions under Node 24; the job completed successfully.
