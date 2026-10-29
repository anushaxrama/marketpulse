"""Execute genuine local experiments and retain aggregate, secret-free evidence."""

import argparse
import json
import platform
import time
from datetime import datetime, timezone
from pathlib import Path

from marketpulse.db import query
from marketpulse.replay import enqueue


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scenarios",
        default="baseline,duplicate,late,reorder,outage,restart,warehouse_retry,poison",
    )
    parser.add_argument("--reuse-completed", action="store_true")
    args = parser.parse_args()
    dataset = query("SELECT id,manifest FROM ops.datasets ORDER BY created_at DESC LIMIT 1")[0]
    records = []
    for scenario in args.scenarios.split(","):
        previous = query(
            "SELECT * FROM ops.runs WHERE dataset_id=%s AND scenario=%s AND status='completed' AND window_minutes=5 AND watermark_minutes=10 ORDER BY created_at DESC LIMIT 1",
            (dataset["id"], scenario),
        )
        if args.reuse_completed and previous:
            run = previous[0]
        else:
            run_id = enqueue(dataset["id"], scenario)
            deadline = time.monotonic() + 1200
            while time.monotonic() < deadline:
                run = query("SELECT * FROM ops.runs WHERE id=%s", (run_id,))[0]
                if run["status"] in ("completed", "failed"):
                    break
                time.sleep(2)
            else:
                raise TimeoutError("Local replay did not finish in time")
        assert run["status"] == "completed", (scenario, run["error"])
        result = run["result"]
        assert result["reconciled"] and result["accepted"] == 4320, (scenario, result)
        if scenario == "duplicate":
            assert result["duplicates"] == 44
        if scenario == "late":
            assert result["late_dropped_from_windows"] == 3
        if scenario == "poison":
            assert result["invalid"] == 1
        if scenario in ("restart", "warehouse_retry"):
            assert any(f["fault"] == "after_window_commit" for f in result["faults"])
        records.append(
            {
                k: run[k]
                for k in [
                    "id",
                    "replay_id",
                    "scenario",
                    "window_minutes",
                    "watermark_minutes",
                    "input_count",
                    "expected_count",
                    "elapsed_seconds",
                    "created_at",
                    "finished_at",
                    "result",
                ]
            }
        )
        print(scenario, run["id"], result["accepted"], flush=True)
    assert len({r["result"]["event_id_fingerprint"] for r in records}) == 1
    checks = query((Path(__file__).resolve().parents[1] / "warehouse/checks.sql").read_text())
    assert not any(c["failures"] for c in checks), checks
    chosen = records[0]["id"]
    started = time.perf_counter()
    plan = query(
        "EXPLAIN(ANALYZE,BUFFERS,FORMAT JSON) SELECT event_time,close FROM marts.fact_bars WHERE run_id=%s AND symbol='BTCUSDT' ORDER BY event_time LIMIT 60",
        (chosen,),
    )
    seconds = time.perf_counter() - started
    output = Path(__file__).resolve().parents[1] / "docs/evidence"
    output.mkdir(parents=True, exist_ok=True)
    evidence = {
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "environment": {
            "system": platform.system(),
            "machine": platform.machine(),
            "python": platform.python_version(),
            "spark": "4.0.4",
            "scala_connector": "2.13",
            "source_day": "2025-01-06",
            "note": "Local Docker Desktop; one Spark driver local[2]. Includes JVM startup, queue processing and database writes; not a sustained production load test.",
        },
        "dataset": dataset["manifest"],
        "runs": records,
        "sql_checks": checks,
        "query_plan": plan,
        "query_with_connection_seconds": seconds,
        "limits": [
            "Snowflake account integration is unverified without credentials.",
            "Live and delayed provider subscriptions are not implemented.",
            "Mobile tests emulate Chromium, not real-device Safari.",
        ],
    }
    (output / "streaming-verification.json").write_text(
        json.dumps(evidence, indent=2, default=str) + "\n"
    )


if __name__ == "__main__":
    main()
