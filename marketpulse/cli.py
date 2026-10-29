import argparse
import json
import time

import psycopg

from marketpulse.config import DATABASE_URL
from marketpulse.db import migrate, query
from marketpulse.replay import SCENARIOS, enqueue, execute, register_dataset


def worker(once: bool = False) -> None:
    from services.ingestor.kafka_io import topics

    with psycopg.connect(DATABASE_URL, autocommit=True) as guard:
        lock = guard.execute("SELECT pg_try_advisory_lock(739136)").fetchone()
        if not lock or not lock[0]:
            raise RuntimeError("Another MarketPulse worker owns the local execution lock")
        migrate()
        topics()
        register_dataset()
        guard.execute("UPDATE ops.runs SET status='queued' WHERE status='running'")
        while True:
            runs = query(
                "SELECT id FROM ops.runs WHERE status='queued' ORDER BY created_at LIMIT 1"
            )
            if runs:
                try:
                    execute(str(runs[0]["id"]))
                except Exception as exc:
                    print(
                        json.dumps(
                            {
                                "event": "run_failed",
                                "run_id": str(runs[0]["id"]),
                                "error_type": type(exc).__name__,
                            }
                        ),
                        flush=True,
                    )
            elif once:
                return
            else:
                time.sleep(2)


def main() -> None:
    parser = argparse.ArgumentParser(description="MarketPulse local historical replay platform")
    parser.add_argument(
        "command",
        choices=[
            "migrate",
            "validate",
            "prepare",
            "worker",
            "demo",
            "replay",
            "benchmark",
            "serve",
            "snowflake",
        ],
    )
    parser.add_argument("--scenario", choices=SCENARIOS, default="baseline")
    parser.add_argument("--window", type=int, choices=[1, 5, 15], default=5)
    parser.add_argument("--watermark", type=int, choices=[2, 10, 30], default=10)
    parser.add_argument("--speed", type=int, choices=[0, 100, 500, 1000], default=0)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--run-id")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Explicitly permit Snowflake SQL against the configured existing warehouse",
    )
    args = parser.parse_args()
    if args.command == "serve":
        migrate()
        import uvicorn

        uvicorn.run("services.api.app:app", host="0.0.0.0", port=8030)
    elif args.command == "migrate":
        migrate()
    elif args.command == "validate":
        from marketpulse.config import ROOT

        checks = query((ROOT / "warehouse/checks.sql").read_text())
        print(json.dumps(checks, indent=2))
        if any(c["failures"] for c in checks):
            raise SystemExit(1)
    elif args.command == "prepare":
        migrate()
        print(json.dumps(register_dataset(), indent=2))
    elif args.command == "worker":
        worker(args.once)
    elif args.command == "snowflake":
        from services.warehouse_loader.snowflake import export_run

        if not args.execute or not args.run_id:
            parser.error(
                "Snowflake requires --execute and --run-id; it can consume warehouse credits"
            )
        print(json.dumps(export_run(args.run_id)))
    else:
        # The Compose worker prepares the dataset and executes queued runs. CLI never starts a second Spark worker.
        deadline = time.monotonic() + 180
        while not (
            datasets := query("SELECT id FROM ops.datasets ORDER BY created_at DESC LIMIT 1")
        ):
            if time.monotonic() > deadline:
                raise TimeoutError("Dataset preparation did not complete; inspect runner logs")
            time.sleep(2)
        run_id = enqueue(datasets[0]["id"], args.scenario, args.window, args.watermark, args.speed)
        print("Replay queued: " + run_id, flush=True)
        deadline = time.monotonic() + 1200
        while time.monotonic() < deadline:
            run = query(
                "SELECT id,status,error,result,elapsed_seconds FROM ops.runs WHERE id=%s", (run_id,)
            )[0]
            if run["status"] in ("completed", "failed"):
                print(json.dumps(run, default=str, indent=2))
                if run["status"] == "failed":
                    raise SystemExit(1)
                return
            time.sleep(3)
        raise TimeoutError("Run did not complete; inspect durable run history and runner logs")


if __name__ == "__main__":
    main()
