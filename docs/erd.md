# Local model relationships

```mermaid
erDiagram
  DATASETS ||--o{ RUNS : configures
  RUNS ||--o{ DELIVERIES : audits
  RUNS ||--o{ FACT_BARS : isolates
  SYMBOLS ||--o{ FACT_BARS : labels
  RUNS ||--o{ STREAM_WINDOWS : aggregates
  RUNS ||--o{ BATCHES : commits
  RUNS ||--o{ PROGRESS : measures
  RUNS ||--o{ FAULTS : records
  FACT_BARS ||--o{ OUTBOX : publishes
  DATASETS { text id PK }
  RUNS { uuid id PK text dataset_id FK text replay_id text scenario text status }
  FACT_BARS { uuid run_id PK text event_id PK text symbol FK timestamp event_time decimal close decimal volume }
  DELIVERIES { text topic PK int partition PK bigint offset_id PK uuid run_id FK text status }
  STREAM_WINDOWS { uuid run_id PK text symbol PK timestamp window_start PK int bar_count decimal volume }
```

The diagram shows logical outbox/run associations; not every operational relationship is a declared foreign key. Fact and active-run relationships are enforced in PostgreSQL. Snowflake does not enforce the same uniqueness constraints.
