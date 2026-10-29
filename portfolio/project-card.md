# MarketPulse project card

**Short summary:** Historical market bars through Kafka and Spark, with an interactive lab for duplicate delivery, late data, and warehouse recovery.

**Long summary:** MarketPulse processes official one-minute spot archives through two Spark Structured Streaming queries and a transactional PostgreSQL sink. Its dashboard connects market movement with source provenance, watermark behavior, audit decisions, and replay reconciliation. Experiments use deterministic source/configuration identities and isolated checkpoints. An optional staged Snowflake exporter is implemented; account integration remains unverified.

**Tags:** Python, Kafka, PySpark, Structured Streaming, PostgreSQL, SQL, FastAPI, Next.js, React, TypeScript, Docker, data quality, event time, idempotency, optional Snowflake.

**Status:** Working local historical replay demonstration. See `project-status.json` and the verification evidence for tested scope.

**GitHub:** https://github.com/anushaxrama/marketpulse

**Local demonstration:** http://127.0.0.1:8031 after `make demo`. This is not a public hosted endpoint.

**Source terms:** Binance public-data attribution, CC BY-NC-SA 4.0 and dataset terms; see `docs/data-license.md`.
