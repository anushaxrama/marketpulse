import os
import time
from collections import defaultdict, deque
from decimal import Decimal
from typing import Literal
from uuid import UUID

import psycopg
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from marketpulse.db import query
from marketpulse.replay import SCENARIOS, enqueue

app = FastAPI(
    title="MarketPulse API",
    version="0.1.0",
    description="Historical 1-minute market bars, Spark event-time windows, and local replay reliability. Prices are USDT, not USD. No order execution.",
)
limits: dict[str, deque] = defaultdict(deque)


def response(data):
    return JSONResponse(jsonable_encoder(data, custom_encoder={Decimal: str, UUID: str}))


@app.middleware("http")
async def protections(request: Request, call_next):
    key = request.client.host if request.client else "local"
    now = time.monotonic()
    bucket = limits[key]
    while bucket and bucket[0] < now - 60:
        bucket.popleft()
    if len(bucket) >= 240:
        return JSONResponse(
            status_code=429,
            content={"detail": "Local API request budget exceeded. Retry in a minute."},
            headers={"Retry-After": "60"},
        )
    bucket.append(now)
    result = await call_next(request)
    result.headers["X-Content-Type-Options"] = "nosniff"
    result.headers["Cache-Control"] = "no-store"
    result.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return result


@app.exception_handler(psycopg.Error)
async def database_unavailable(request, exc):
    return JSONResponse(
        status_code=503,
        content={
            "detail": "Warehouse unavailable or not migrated. Start the local services and inspect runner logs."
        },
    )


def chosen_run(run_id: UUID | None = None):
    if run_id:
        rows = query("SELECT * FROM ops.runs WHERE id=%s", (run_id,))
    else:
        rows = query(
            "SELECT * FROM ops.runs WHERE status='completed' ORDER BY (scenario='baseline') DESC,created_at DESC LIMIT 1"
        )
    if not rows:
        return None
    return rows[0]


def require_run(run_id):
    run = chosen_run(run_id)
    if not run:
        raise HTTPException(
            404, "No replay is available yet. Run make demo or inspect the local runner."
        )
    if run["status"] != "completed":
        raise HTTPException(409, "Replay has not completed; use the run ledger for progress.")
    return run


@app.get("/health")
def health():
    query("SELECT 1")
    return {"status": "ok", "database": "reachable"}


@app.get("/api/overview")
def overview(run_id: UUID | None = None):
    run = chosen_run(run_id)
    datasets = query(
        "SELECT id,day,events,manifest FROM ops.datasets ORDER BY created_at DESC LIMIT 1"
    )
    if not run:
        return response(
            {
                "run": None,
                "dataset": datasets[0] if datasets else None,
                "symbols": [],
                "status": "Preparing historical replay; no market results yet",
                "lab_enabled": os.getenv("MP_LAB_ENABLED") == "true",
            }
        )
    symbols = query(
        """SELECT b.symbol,count(*) bars,min(event_time) first_event,max(event_time) last_event,
    (array_agg(close ORDER BY event_time))[1] first_close,(array_agg(close ORDER BY event_time DESC))[1] last_close,
    sum(volume) base_volume FROM marts.fact_bars b WHERE run_id=%s GROUP BY symbol ORDER BY symbol""",
        (run["id"],),
    )
    for symbol in symbols:
        symbol["return_pct"] = (symbol["last_close"] / symbol["first_close"] - 1) * 100
    return response(
        {
            "run": run,
            "dataset": datasets[0] if datasets else None,
            "symbols": symbols,
            "lab_enabled": os.getenv("MP_LAB_ENABLED") == "true",
            "source_mode": "historical_replay",
            "currency": "USDT",
            "granularity": "1-minute OHLCV bars",
        }
    )


@app.get("/api/series")
def series(
    symbol: Literal["BTCUSDT", "ETHUSDT", "SOLUSDT"] = "BTCUSDT",
    run_id: UUID | None = None,
    hours: int = Query(24, ge=1, le=24),
    limit: int = Query(1440, ge=1, le=1440),
    offset: int = Query(0, ge=0, le=10000),
):
    if hours not in (1, 6, 12, 24):
        raise HTTPException(422, "Time window must be 1, 6, 12, or 24 hours")
    run = require_run(run_id)
    rows = query(
        """SELECT * FROM marts.bar_features WHERE run_id=%s AND symbol=%s AND
    event_time>=(SELECT max(event_time) FROM marts.fact_bars WHERE run_id=%s AND symbol=%s)-(%s*interval '1 hour')+interval '1 minute'
    ORDER BY event_time LIMIT %s OFFSET %s""",
        (run["id"], symbol, run["id"], symbol, hours, limit, offset),
    )
    return response(rows)


@app.get("/api/windows")
def windows(
    symbol: Literal["BTCUSDT", "ETHUSDT", "SOLUSDT"] = "BTCUSDT",
    run_id: UUID | None = None,
    limit: int = Query(300, ge=1, le=1500),
):
    run = require_run(run_id)
    return response(
        query(
            "SELECT * FROM marts.stream_windows WHERE run_id=%s AND symbol=%s ORDER BY window_start LIMIT %s",
            (run["id"], symbol, limit),
        )
    )


@app.get("/api/operations")
def operations(run_id: UUID | None = None):
    run = chosen_run(run_id)
    if not run:
        return response({"run": None, "deliveries": [], "progress": [], "batches": []})
    return response(
        {
            "run": run,
            "deliveries": query(
                "SELECT status,count(*) count FROM raw.deliveries WHERE run_id=%s GROUP BY status",
                (run["id"],),
            ),
            "progress": query(
                "SELECT * FROM ops.progress WHERE run_id=%s ORDER BY stage,batch_id", (run["id"],)
            ),
            "batches": query(
                "SELECT stage,count(*) committed_batches,sum(row_count) written_rows FROM ops.batches WHERE run_id=%s GROUP BY stage",
                (run["id"],),
            ),
            "outbox_pending": query(
                "SELECT count(*) count FROM ops.outbox WHERE run_id=%s AND sent_at IS NULL",
                (run["id"],),
            )[0]["count"],
            "quality": query(
                "SELECT status,reason,count(*) count FROM raw.deliveries WHERE run_id=%s AND status IN ('invalid','conflict') GROUP BY status,reason LIMIT 25",
                (run["id"],),
            ),
        }
    )


@app.get("/api/runs")
def runs(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0, le=10000)):
    return response(
        query("SELECT * FROM ops.runs ORDER BY created_at DESC LIMIT %s OFFSET %s", (limit, offset))
    )


@app.get("/api/catalog")
def catalog():
    return response(
        {
            "symbols": query("SELECT * FROM marts.dim_symbols ORDER BY symbol"),
            "datasets": query("SELECT * FROM ops.datasets ORDER BY created_at DESC"),
            "schema_versions": query("SELECT * FROM ops.schema_migrations ORDER BY version"),
            "lab_enabled": os.getenv("MP_LAB_ENABLED") == "true",
            "scenarios": SCENARIOS,
            "definitions": {
                "price": "One-minute close in USDT. USDT is a quote asset, not a USD conversion.",
                "volume": "Executed base-asset volume within an OHLCV bar. Never derived from quotes.",
                "returns": "Log returns only for adjacent observed one-minute bars; gaps are not filled.",
                "volatility": "Realized volatility is the square root of summed squared available log returns; the rolling standard deviation is separate. Unannualized sample standard deviation of available log returns in a contiguous 20-bar window.",
                "anomaly": "Current log return against 20 preceding available log returns, z-score threshold 3.5. Exploratory, multiple-testing and regime caveats apply.",
                "freshness": "Historical event time and current processing time are separate. A recent replay is not a fresh exchange feed.",
                "watermark": "Spark event-time watermark controls stream-window state. Late bars remain in the audited fact table even when excluded from window aggregates.",
                "licensed_adapter": "Provider protocol exists; live exchange subscriptions are not implemented or verified.",
                "snowflake": "Optional staged COPY/MERGE exporter; account execution is unverified without credentials.",
            },
        }
    )


class ReplayRequest(BaseModel):
    dataset_id: str
    scenario: Literal[
        "baseline", "duplicate", "late", "reorder", "outage", "restart", "warehouse_retry", "poison"
    ] = "baseline"
    window_minutes: Literal[1, 5, 15] = 5
    watermark_minutes: Literal[2, 10, 30] = 10
    speed: Literal[0, 100, 500, 1000] = 0


@app.post("/api/lab/replays", status_code=202)
def launch(body: ReplayRequest):
    if os.getenv("MP_LAB_ENABLED") != "true":
        raise HTTPException(
            403,
            "Local lab is disabled. Start Compose with MP_LAB_ENABLED=true only in your local demo environment.",
        )
    try:
        run_id = enqueue(
            body.dataset_id, body.scenario, body.window_minutes, body.watermark_minutes, body.speed
        )
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"run_id": run_id, "status": "queued", "source_mode": "historical_replay"}


@app.get("/metrics", include_in_schema=False)
def metrics():
    rows = query("SELECT status,count(*) count FROM ops.runs GROUP BY status")
    text = "# HELP marketpulse_runs_total Recorded replay runs by current status\n# TYPE marketpulse_runs_total gauge\n"
    text += "".join(
        f'marketpulse_runs_total{{status="{r["status"]}"}} {r["count"]}\n' for r in rows
    )
    return Response(text, media_type="text/plain; version=0.0.4")
