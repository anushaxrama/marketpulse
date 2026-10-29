# Replay and sink recovery sequence

```mermaid
sequenceDiagram
  participant U as Local user
  participant API as API queue
  participant W as Replay worker
  participant K as Kafka
  participant S as Spark
  participant P as PostgreSQL
  U->>API: Confirm bounded historical replay
  API->>P: Insert queued run
  W->>P: Claim work under single-worker lock
  W->>K: Publish source envelopes
  S->>K: Read raw offsets
  S->>P: Commit audit, unique facts, outbox, batch ID
  W->>K: Publish outbox with acknowledgement
  S->>K: Read curated events
  S->>P: Commit window values and batch ID
  Note over S,P: Local fault can interrupt after this commit
  S->>P: Retry same batch after checkpoint restart
  P-->>S: Already committed; no-op
  W->>P: Reconcile facts, windows, drops, and offsets
  API-->>U: Return actual completed outcome
```
