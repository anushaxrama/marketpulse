# Local operations

## Startup

`make demo` builds the images, starts the isolated stack, enables local lab launch, and waits for a baseline replay. The API applies schema migrations before serving. The worker prepares the dataset, creates explicit Kafka topics, and processes queued runs one at a time.

Ports: dashboard 8031, API 8030, PostgreSQL 5546, Kafka's host listener 19094. Host bindings are loopback-only. Internal clients use service names, not the host listener.

```sh
docker compose ps
docker compose logs --tail 100 runner
docker compose logs --tail 50 api
docker compose exec -T api marketpulse validate
```

## Recovery

| Symptom | Inspect and respond |
| --- | --- |
| Dashboard cannot load | Check API health and the dashboard's server-side API URL. A failed request must show an error, not invented results. |
| Dataset never appears | Inspect worker source/checksum logs, source availability, DNS, and rate limits. Fix the issue and restart the worker; do not substitute generated prices. |
| Kafka fails on first start | The project includes a one-shot volume ownership initializer. Confirm it exited successfully and the broker health check passed. |
| A replay fails | Read its durable run error and worker logs. Earlier committed facts and audit records remain inspectable. Use a fresh instance for a new experiment. |
| Worker process restarts | Its single-worker lock prevents concurrent execution; interrupted running records are requeued. The same instance retains checkpoint and source offsets. |
| Late-window count is nonzero | Compare it with curated count and window count. Historical facts are intentionally retained. |
| Pending outbox rows | Check broker reachability. Publication resumes from unsent records; a repeated send can occur around acknowledgement. |
| Lab form rejects an origin | Configure the exact allowed loopback origins with `MP_DASHBOARD_ORIGINS`. Do not replace the allowlist with an unrestricted wildcard. |
| Database tests refuse a URL | Use a disposable database named `marketpulse_test`. Tests deliberately refuse the application database. |

## Bounded replay

The registered source is January 6, 2025. A run is capped at 10,000 source events, and at most three records can be queued/running. The browser cannot choose arbitrary code, paths, provider URLs, or symbols. Use the CLI/adapter implementation for deliberate source extensions with a new manifest and verification.

A default replay can use substantial local CPU for Java startup, state processing, and SQL writes. Queue status is not a completion percentage. Failed records are retained, including failures found during development. Do not delete history to make the ledger appear uniformly successful.

## Stop and preserve

```sh
make stop
docker compose down
```

These preserve named data volumes. Deliberate `docker compose down -v` removes this project's database, source archives, Kafka log, and checkpoints. Back up state before removing it if the experiment history matters.

Logs and artifacts can include diagnostic context. The committed evidence is generated from selected aggregate fields and excludes credentials and personal filesystem paths.
