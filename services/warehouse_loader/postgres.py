"""Transactional event audit, durable outbox, and retry-safe Spark window batches."""

import json
from decimal import Decimal
from typing import Any

from psycopg.types.json import Jsonb
from pydantic import ValidationError

from marketpulse.config import CURATED, DLQ
from marketpulse.contracts import MarketEvent
from marketpulse.db import connection


def audit_batch(run_id: str, batch_id: int, deliveries: list[dict[str, Any]]) -> None:
    with connection() as conn:
        conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (run_id,))
        if conn.execute(
            "SELECT 1 FROM ops.batches WHERE run_id=%s AND stage='raw' AND batch_id=%s",
            (run_id, batch_id),
        ).fetchone():
            return
        for delivery in deliveries:
            payload: dict = {}
            event: MarketEvent | None = None
            reason = None
            try:
                envelope = json.loads(delivery["value"])
                if not isinstance(envelope, dict):
                    raise ValueError("Kafka value must be a versioned event envelope")
                if envelope.get("run_id") != run_id:
                    continue
                payload = envelope
                event = MarketEvent.model_validate(envelope["event"])
                if event.event_type != "bar_1m":
                    raise ValueError("This warehouse version only serves one-minute OHLCV bars")
            except (ValidationError, ValueError, TypeError, KeyError) as exc:
                reason = str(exc)[:1000]
                if not payload:
                    payload = {"raw_text": delivery["value"][:10000]}
            if conn.execute(
                "SELECT 1 FROM raw.deliveries WHERE topic=%s AND partition=%s AND offset_id=%s",
                (delivery["topic"], delivery["partition"], delivery["offset"]),
            ).fetchone():
                continue
            status = "invalid" if reason else "accepted"
            if event and not reason:
                old = conn.execute(
                    "SELECT payload_hash,open,high,low,close,volume,currency,source_mode FROM marts.fact_bars WHERE run_id=%s AND event_id=%s",
                    (run_id, event.event_id),
                ).fetchone()
                if old:
                    status = (
                        "duplicate"
                        if old["payload_hash"] == event.raw_payload_hash
                        and (
                            old["open"],
                            old["high"],
                            old["low"],
                            old["close"],
                            old["volume"],
                            old["currency"],
                            old["source_mode"],
                        )
                        == (
                            event.open,
                            event.high,
                            event.low,
                            event.price,
                            event.volume,
                            event.currency,
                            event.source_mode,
                        )
                        else "conflict"
                    )
                    reason = (
                        "Existing event identity has different source content"
                        if status == "conflict"
                        else None
                    )
                else:
                    collision = conn.execute(
                        "SELECT 1 FROM marts.fact_bars WHERE run_id=%s AND symbol=%s AND event_time=%s",
                        (run_id, event.symbol, event.event_time_utc),
                    ).fetchone()
                    if collision:
                        status, reason = (
                            "conflict",
                            "Another identity already occupies this symbol/bar minute",
                        )
                    else:
                        conn.execute(
                            """INSERT INTO marts.fact_bars(run_id,event_id,symbol,event_time,ingested_at,open,high,low,close,volume,provider,currency,payload_hash,source_mode,lineage)
                        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                            (
                                run_id,
                                event.event_id,
                                event.symbol,
                                event.event_time_utc,
                                event.ingestion_time_utc,
                                event.open,
                                event.high,
                                event.low,
                                event.price,
                                event.volume,
                                event.provider,
                                event.currency,
                                event.raw_payload_hash,
                                event.source_mode,
                                Jsonb(event.lineage),
                            ),
                        )
                        conn.execute(
                            "INSERT INTO ops.outbox(run_id,event_id,topic,payload) VALUES(%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                            (run_id, event.event_id, CURATED, Jsonb(payload)),
                        )
            conn.execute(
                "INSERT INTO raw.deliveries(topic,partition,offset_id,run_id,event_id,status,reason,payload) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    delivery["topic"],
                    delivery["partition"],
                    delivery["offset"],
                    run_id,
                    event.event_id if event else None,
                    status,
                    reason,
                    Jsonb(payload),
                ),
            )
            if status in ("invalid", "conflict"):
                key = f"{delivery['topic']}:{delivery['partition']}:{delivery['offset']}"
                conn.execute(
                    "INSERT INTO ops.outbox(run_id,event_id,topic,payload) VALUES(%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                    (
                        run_id,
                        key,
                        DLQ,
                        Jsonb(
                            {
                                "run_id": run_id,
                                "reason": reason,
                                "original": payload,
                                "source_offset": key,
                            }
                        ),
                    ),
                )
        conn.execute(
            "INSERT INTO ops.batches(run_id,stage,batch_id,row_count) VALUES(%s,'raw',%s,%s)",
            (run_id, batch_id, len(deliveries)),
        )


def window_batch(run_id: str, batch_id: int, rows: list[dict]) -> bool:
    """Commit the sink then optionally fail once to test checkpoint replay after a commit."""
    with connection() as conn:
        conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (run_id,))
        if conn.execute(
            "SELECT 1 FROM ops.batches WHERE run_id=%s AND stage='windows' AND batch_id=%s",
            (run_id, batch_id),
        ).fetchone():
            return False
        for row in rows:
            events = sorted(row["events"], key=lambda e: (e["event_time"], e["event_id"]))
            if not events:
                continue
            window = row["window"]
            conn.execute(
                """INSERT INTO marts.stream_windows(run_id,symbol,window_start,window_end,bar_count,open,close,high,low,volume)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(run_id,symbol,window_start) DO UPDATE SET
            bar_count=excluded.bar_count,open=excluded.open,close=excluded.close,high=excluded.high,low=excluded.low,volume=excluded.volume,updated_at=now()""",
                (
                    run_id,
                    row["symbol"],
                    window["start"],
                    window["end"],
                    len(events),
                    events[0]["open"],
                    events[-1]["price"],
                    max(e["high"] for e in events),
                    min(e["low"] for e in events),
                    sum((e["volume"] for e in events), Decimal(0)),
                ),
            )
        conn.execute(
            "INSERT INTO ops.batches(run_id,stage,batch_id,row_count) VALUES(%s,'windows',%s,%s)",
            (run_id, batch_id, len(rows)),
        )
        run = conn.execute("SELECT scenario FROM ops.runs WHERE id=%s", (run_id,)).fetchone()
        if rows and run and run["scenario"] in ("restart", "warehouse_retry"):
            fault = conn.execute(
                "INSERT INTO ops.faults(run_id,fault,details) VALUES(%s,'after_window_commit',%s) ON CONFLICT DO NOTHING RETURNING fault",
                (run_id, Jsonb({"batch_id": batch_id, "sink_committed": True})),
            ).fetchone()
            return bool(fault)
    return False


def normalize_offsets(value):
    import ast

    if value is None:
        return None
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            value = ast.literal_eval(value)
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("Unexpected Spark Kafka offset representation: " + type(value).__name__)
    return {
        str(topic): {str(partition): int(offset) for partition, offset in offsets.items()}
        for topic, offsets in value.items()
    }


def save_progress(run_id: str, stage: str, progress: dict) -> None:
    operators = progress.get("stateOperators", [])
    watermark = progress.get("eventTime", {}).get("watermark")
    durations = progress.get("durationMs", {})
    with connection() as conn:
        conn.execute(
            """INSERT INTO ops.progress(run_id,stage,batch_id,input_rows,dropped_by_watermark,watermark,input_rate,processed_rate,duration_ms,offsets)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(run_id,stage,batch_id) DO NOTHING""",
            (
                run_id,
                stage,
                progress["batchId"],
                progress["numInputRows"],
                sum(s.get("numRowsDroppedByWatermark", 0) for s in operators),
                watermark,
                progress.get("inputRowsPerSecond", 0),
                progress.get("processedRowsPerSecond", 0),
                durations.get("triggerExecution", 0),
                Jsonb(
                    [
                        {
                            "start": normalize_offsets(s.get("startOffset")),
                            "end": normalize_offsets(s.get("endOffset")),
                            "latest": normalize_offsets(s.get("latestOffset")),
                        }
                        for s in progress.get("sources", [])
                    ]
                ),
            ),
        )
