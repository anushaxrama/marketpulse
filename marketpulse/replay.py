import json
import random
import time
import uuid
from datetime import datetime, timezone

from kafka import KafkaConsumer, TopicPartition
from psycopg.types.json import Jsonb

from marketpulse.config import BROKERS, RAW, SYMBOLS
from marketpulse.contracts import MarketEvent, digest
from marketpulse.db import connection, query
from services.ingestor.kafka_io import producer
from services.ingestor.providers import load_dataset

SCENARIOS = (
    "baseline",
    "duplicate",
    "late",
    "reorder",
    "outage",
    "restart",
    "warehouse_retry",
    "poison",
)


def register_dataset() -> dict:
    events, manifest = load_dataset()
    with connection() as conn:
        conn.execute(
            "INSERT INTO ops.datasets(id,day,manifest,events) VALUES(%s,%s,%s,%s) ON CONFLICT(id) DO NOTHING",
            (manifest["id"], manifest["day"], Jsonb(manifest), len(events)),
        )
    return manifest


def enqueue(
    dataset_id: str,
    scenario: str = "baseline",
    window: int = 5,
    watermark: int = 10,
    speed: int = 0,
) -> str:
    if (
        scenario not in SCENARIOS
        or window not in (1, 5, 15)
        or watermark not in (2, 10, 30)
        or speed not in (0, 100, 500, 1000)
    ):
        raise ValueError("Unsupported bounded lab configuration")
    dataset = query("SELECT events FROM ops.datasets WHERE id=%s", (dataset_id,))
    if not dataset or dataset[0]["events"] > 10000:
        raise ValueError("Dataset is unavailable or exceeds the local event budget")
    run_id = str(uuid.uuid4())
    replay_id = digest([dataset_id, scenario, window, watermark, 42])[:24]
    with connection() as conn:
        conn.execute("SELECT pg_advisory_xact_lock(739135)")
        pending_row = conn.execute(
            "SELECT count(*) n FROM ops.runs WHERE status IN ('queued','running')"
        ).fetchone()
        assert pending_row is not None
        if pending_row["n"] >= 3:
            raise ValueError("Local replay queue is full")
        conn.execute(
            "INSERT INTO ops.runs(id,replay_id,dataset_id,scenario,window_minutes,watermark_minutes,speed,expected_count) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                run_id,
                replay_id,
                dataset_id,
                scenario,
                window,
                watermark,
                speed,
                dataset[0]["events"],
            ),
        )
    return run_id


def scenario_events(events: list[MarketEvent], scenario: str) -> list[dict]:
    ordered = [e.model_dump(mode="json") for e in events]
    if scenario == "duplicate":
        result = []
        for i, e in enumerate(ordered):
            result.append(e)
            if i % 100 == 0:
                result.append(dict(e))
        return result
    if scenario == "late":
        return ordered[3:] + ordered[:3]
    if scenario == "reorder":
        rng = random.Random(42)
        result = []
        for i in range(0, len(ordered), 9):
            block = ordered[i : i + 9]
            rng.shuffle(block)
            result.extend(block)
        return result
    return ordered


def publish_run(run: dict) -> None:
    run_id = str(run["id"])
    events, manifest = load_dataset()
    if manifest["id"] != run["dataset_id"]:
        raise ValueError("Registered replay dataset differs from the cached source dataset")
    client = KafkaConsumer(bootstrap_servers=BROKERS, enable_auto_commit=False)
    try:
        if run["config"].get("raw_offsets"):
            starts = run["config"]["raw_offsets"]
            curated_starts = run["config"].get("curated_offsets", "earliest")
        else:
            offsets = client.end_offsets([TopicPartition(RAW, i) for i in range(3)])
            starts = json.dumps({RAW: {str(p.partition): v for p, v in offsets.items()}})
            curated = client.end_offsets([TopicPartition("market.curated.v1", i) for i in range(3)])
            curated_starts = json.dumps(
                {"market.curated.v1": {str(p.partition): v for p, v in curated.items()}}
            )
    finally:
        client.close()
    emitted = scenario_events(events, run["scenario"])
    with connection() as conn:
        conn.execute(
            "UPDATE ops.runs SET config=config || %s,input_count=%s WHERE id=%s",
            (
                Jsonb({"raw_offsets": starts, "curated_offsets": curated_starts}),
                len(emitted) + (run["scenario"] == "poison"),
                run_id,
            ),
        )
    output = producer()
    try:
        if run["scenario"] == "outage":
            with connection() as conn:
                conn.execute(
                    "INSERT INTO ops.faults(run_id,fault,details) VALUES(%s,'producer_pause',%s) ON CONFLICT DO NOTHING",
                    (
                        run_id,
                        Jsonb(
                            {
                                "pause_seconds": 1,
                                "kind": "controlled local producer pause; no upstream outage claimed",
                            }
                        ),
                    ),
                )
            time.sleep(1)
        for event in emitted:
            event["ingestion_time_utc"] = datetime.now(timezone.utc).isoformat()
            output.send(
                RAW,
                key=event["symbol"],
                partition=SYMBOLS.index(event["symbol"]),
                value={"run_id": run_id, "event": event},
            ).get(timeout=30)
            if run["speed"]:
                time.sleep(1 / run["speed"])
        if run["scenario"] == "poison":
            invalid = {
                "run_id": run_id,
                "event": {"schema_version": 999, "price": "NaN", "source_mode": "synthetic_test"},
            }
            output.send(RAW, key=SYMBOLS[0], partition=0, value=invalid).get(timeout=30)
        output.flush(timeout=30)
        observer = KafkaConsumer(bootstrap_servers=BROKERS, enable_auto_commit=False)
        try:
            final_offsets = observer.end_offsets([TopicPartition(RAW, i) for i in range(3)])
            first_offsets = json.loads(starts)[RAW]
            actual_deliveries = sum(
                value - first_offsets[str(partition.partition)]
                for partition, value in final_offsets.items()
            )
        finally:
            observer.close()
        with connection() as conn:
            conn.execute(
                "UPDATE ops.runs SET config=config || %s,input_count=%s WHERE id=%s",
                (Jsonb({"published": True}), actual_deliveries, run_id),
            )
    finally:
        output.close()


def reconcile(run_id: str) -> dict:
    delivery_counts = query(
        "SELECT status,count(*) n FROM raw.deliveries WHERE run_id=%s GROUP BY status", (run_id,)
    )
    counts = {row["status"]: row["n"] for row in delivery_counts}
    actual = query("SELECT count(*) n FROM marts.fact_bars WHERE run_id=%s", (run_id,))[0]["n"]
    windows = query(
        "SELECT coalesce(sum(bar_count),0)::integer n,count(*) windows FROM marts.stream_windows WHERE run_id=%s",
        (run_id,),
    )[0]
    late = query(
        "SELECT coalesce(sum(dropped_by_watermark),0)::integer n FROM ops.progress WHERE run_id=%s AND stage='windows'",
        (run_id,),
    )[0]["n"]
    lag = query(
        """SELECT percentile_cont(.5) within group(order by extract(epoch from loaded_at-ingested_at)) p50,
    percentile_cont(.95) within group(order by extract(epoch from loaded_at-ingested_at)) p95 FROM marts.fact_bars WHERE run_id=%s""",
        (run_id,),
    )[0]
    run = query("SELECT * FROM ops.runs WHERE id=%s", (run_id,))[0]
    fingerprint = query(
        "SELECT md5(string_agg(event_id,',' ORDER BY event_id)) hash FROM marts.fact_bars WHERE run_id=%s",
        (run_id,),
    )[0]["hash"]
    good = (
        actual == run["expected_count"]
        and sum(counts.values()) == run["input_count"]
        and windows["n"] + late == actual
    )
    lag_at_completion = 0
    observer = KafkaConsumer(bootstrap_servers=BROKERS, enable_auto_commit=False)
    try:
        for stage, topic in [("raw", RAW), ("windows", "market.curated.v1")]:
            progress = query(
                "SELECT offsets FROM ops.progress WHERE run_id=%s AND stage=%s ORDER BY batch_id DESC LIMIT 1",
                (run_id, stage),
            )
            if not progress or not progress[0]["offsets"]:
                raise ValueError("Missing source offset evidence")
            end = progress[0]["offsets"][0]["end"]
            from services.warehouse_loader.postgres import normalize_offsets

            end = normalize_offsets(end)
            current = observer.end_offsets([TopicPartition(topic, i) for i in range(3)])
            lag_at_completion += sum(
                max(0, value - end[topic][str(partition.partition)])
                for partition, value in current.items()
            )
    finally:
        observer.close()
    result = {
        "kafka_lag_at_completion": lag_at_completion,
        "source_mode": "historical_replay",
        "accepted": actual,
        "duplicates": counts.get("duplicate", 0),
        "invalid": counts.get("invalid", 0),
        "conflicts": counts.get("conflict", 0),
        "delivered": sum(counts.values()),
        "window_bars": windows["n"],
        "windows": windows["windows"],
        "late_dropped_from_windows": late,
        "reconciled": good,
        "event_id_fingerprint": fingerprint,
        "lag_p50_seconds": lag["p50"],
        "lag_p95_seconds": lag["p95"],
        "expected_unique": run["expected_count"],
        "volume_unit": "base asset units; bars, not quote volume",
        "faults": query("SELECT fault,details FROM ops.faults WHERE run_id=%s", (run_id,)),
    }
    if run["scenario"] == "late" and late == 0:
        raise ValueError("Late experiment did not demonstrate an actual Spark watermark drop")
    if run["scenario"] in ("restart", "warehouse_retry") and not result["faults"]:
        raise ValueError("Restart experiment did not inject the expected commit-boundary failure")
    if not good:
        raise ValueError(json.dumps(result, default=str))
    return result


def execute(run_id: str) -> None:
    from services.stream_processor.processor import process

    started = time.perf_counter()
    with connection() as conn:
        conn.execute(
            "UPDATE ops.runs SET status='running',started_at=coalesce(started_at,now()),error=NULL WHERE id=%s",
            (run_id,),
        )
    try:
        run = query("SELECT * FROM ops.runs WHERE id=%s", (run_id,))[0]
        if not run["config"].get("published"):
            publish_run(run)
        run = query("SELECT * FROM ops.runs WHERE id=%s", (run_id,))[0]
        process(run)
        result = reconcile(run_id)
        seconds = time.perf_counter() - started
        result["accepted_events_per_second"] = result["accepted"] / seconds
        with connection() as conn:
            conn.execute(
                "UPDATE ops.runs SET status='completed',finished_at=now(),elapsed_seconds=%s,result=%s WHERE id=%s",
                (seconds, Jsonb(result), run_id),
            )
    except Exception as exc:
        with connection() as conn:
            conn.execute(
                "UPDATE ops.runs SET status='failed',finished_at=now(),error=%s,elapsed_seconds=%s WHERE id=%s",
                (str(exc)[-3000:], time.perf_counter() - started, run_id),
            )
        raise
