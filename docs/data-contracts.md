# Event contract and source assumptions

## Canonical version 1

The Pydantic model is `marketpulse/contracts.py`. Unknown fields and unsupported schema versions are rejected.

| Field | Meaning |
| --- | --- |
| `event_id` | SHA-256 identity over contract version, provider, symbol, event type, and provider identity |
| `provider`, `exchange` | Provenance labels, not endorsement |
| `provider_event_id` | Source identity when present; a normalized UTC event-time fallback is supported for an adapter without one |
| `symbol` | Entry in the bounded registry |
| `event_type` | `bar_1m`, `trade`, or `quote` at the shared-contract level; the current warehouse accepts only `bar_1m` |
| `event_time_utc` | Time represented by the source event, normalized from an explicit timezone offset |
| `ingestion_time_utc` | Time emitted into the current replay; separate from historical event time |
| `price` | Positive finite decimal; close price for a bar |
| `open`, `high`, `low` | Required positive decimals for a bar; OHLC bounds are checked |
| `volume` | Nonnegative executed base-asset volume for a bar; forbidden on quote snapshots |
| `currency` | Allowed quote-asset label; the default archive is USDT |
| `source_mode` | `historical_replay`, `synthetic_test`, `live`, or `delayed`; a delayed event must declare its delay |
| `source_delay_minutes` | Nullable declared provider delay; historical replay does not masquerade as a delayed live feed |
| `schema_version` | Version 1 |
| `raw_payload_hash` | SHA-256 of the source row content |
| `lineage` | Archive URL, checksum, source day, and applicable data terms |

The provider's default identity is symbol plus source bar-open timestamp within its namespace. A changed payload with the same identity is quarantined as a conflict. It is not added as another bar or silently used to rewrite a previous accepted record within the run.

The official spot archives use microsecond timestamps from 2025 onward; earlier millisecond values are normalized separately. One-minute bar opens must align to a minute. Timezone-naive values are rejected. Unit tests cover explicit offsets across spring and fall DST transitions; the default source itself is UTC.

## Evolution

Version 1 has a strict schema. Introducing a new event type, decimal scale, source identity policy, or incompatible field requires a new contract and compatible topic/checkpoint plan. Do not reuse a stateful checkpoint after changing those semantics.

## Source limits

These are unadjusted crypto spot bars. Volume describes executed base-asset quantity within the bar, not order-book depth or quote volume. The selected symbols create survivorship and selection bias. Missing minutes are not filled, and the data does not establish a complete view of all venues or markets. Token redenominations, forks, and provider corrections are not automatically adjusted into comparable returns.

The market session is continuous UTC. No equity holiday closures or exchange-open claims are inferred. The historical source date and processing timestamp must both remain visible.
