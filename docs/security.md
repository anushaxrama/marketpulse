# Security and scope

The stack is a local development environment. Host ports bind to loopback; Kafka uses plaintext inside its isolated network and has a replication factor of one. The default database credentials are public development values. Production access controls, TLS, broker authentication, managed secrets, backups, and external alerting are not implemented by these defaults.

The dashboard proxies only an explicit API path allowlist. Lab POST requests require an allowed origin and a small request body. FastAPI accepts predefined scenarios/settings, parameterizes SQL, bounds query sizes, and limits request rate. The queue and single-worker lock prevent an unlimited number of simultaneous Spark jobs. No Docker socket is mounted into the API or dashboard.

Snowflake configuration remains on the server. There are no `NEXT_PUBLIC` secrets. The optional exporter requires an explicit CLI execution flag and existing account resources. It does not provision billable infrastructure.

Raw source files and normalized caches have checksums. ZIP expansion and byte budgets are bounded. Invalid/unknown fields, price bounds, volume semantics, timezone requirements, and identity conflicts are checked before facts are accepted. Offset strings are parsed as JSON or restricted literals, never evaluated as code.

Dependency checks cover the pinned base Python requirements and production frontend packages. A clean package advisory result does not audit every JVM jar, operating-system package, optional Snowflake dependency, or deployment configuration. The CI workflow reruns those package checks. No claim of a full security audit is made.

The test suite uses an explicitly named disposable database and labels synthetic records. Source-mode labels, source dates, and data terms remain visible. The application has no trading credentials, order-execution endpoints, or recommendation engine.
