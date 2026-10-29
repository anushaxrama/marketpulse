# Deployment options and cost control

## A. Local Docker demo

This is the verified default. One broker, PostgreSQL, a local Spark driver, FastAPI, and Next.js run on the user's machine. Images and dependencies require initial downloads. Replays use local CPU, memory, and disk; the default dataset is three one-day minute-bar archives. No cloud resources are created.

Use `make stop` to stop compute while retaining data, or `docker compose down` to remove containers/network. Removing named volumes is a separate deliberate operation described in the runbook.

## B. Hosted system preparation

A hosted version would need an authenticated API/dashboard, a licensed data provider where applicable, durable object storage/checkpoints, managed Kafka or compatible brokers, Spark execution capacity, and an existing Snowflake account or another warehouse.

This build did not create or measure those resources. A useful cost estimate requires the actual provider, region, retention, event volume, replay frequency, worker uptime, and warehouse size. No dollar estimate is invented from the local demo.

Keep the control plane separate from data processing. Disable browser fault injection by default, enforce per-user budgets, authenticate job submission, isolate tenants, use managed secrets, and test checkpoint and database restoration. Version topics, contracts, and checkpoints when changing stateful semantics.

The optional Snowflake exporter can consume warehouse credits only when explicitly executed against the supplied resources. Set a warehouse auto-suspend policy and account budget/monitor before using it. Account configuration and commercial source licensing are user-owned deployment prerequisites, not automatically accepted or provisioned by this repository.

There is no verified hosted application URL. Local `127.0.0.1` links are not public demo endpoints.

## Estimation worksheet

Use the chosen provider's current regional rates rather than treating local throughput as a cloud quote:

| Cost | Billable units to estimate |
| --- | --- |
| Kafka | Broker/node hours, partition/storage retention, and inter-zone/network traffic |
| Spark | Driver and executor instance hours, startup frequency, and durable state/checkpoint storage |
| Snowflake | Configured warehouse credits per active hour multiplied by active runtime, plus storage and transfer |
| API/dashboard | Instance or request/CPU units, database connection capacity, and outbound traffic |
| Data | Provider subscription, exchange entitlements, and permitted redistribution/use |

Monthly estimate = sum of each expected unit quantity multiplied by its provider rate. Track startup and minimum billing intervals separately. For example, a continuously running component consumes roughly 720 instance-hours in a 30-day month; a replicated three-instance service consumes roughly 2,160 before autoscaling. Those are planning units, not price or sizing recommendations.

Begin with a fixed development budget, short retention, local or manual runs, and warehouse auto-suspend. Record actual billed usage before suggesting a production budget. This project has no measured cloud bill and no selected managed-service contract, so a dollar total would be unsupported.
