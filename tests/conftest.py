import os
from urllib.parse import urlparse

import psycopg
import pytest

from marketpulse.contracts import MarketEvent, digest, identity


def event(minute=0, **changes):
    values = dict(
        provider="synthetic_fixture",
        provider_event_id=str(minute),
        symbol="BTCUSDT",
        exchange="synthetic test exchange",
        event_type="bar_1m",
        event_time_utc=f"2025-01-06T00:{minute:02}:00+00:00",
        ingestion_time_utc="2026-10-29T00:00:00+00:00",
        price="100.10",
        open="100",
        high="101",
        low="99",
        volume="2.25",
        currency="USDT",
        source_mode="synthetic_test",
        raw_payload_hash=digest(["fixture", minute]),
        lineage={"fixture": "synthetic test; not market observations"},
    )
    values.update(changes)
    values["event_id"] = identity(
        values["provider"], values["symbol"], values["event_type"], values["provider_event_id"]
    )
    return MarketEvent.model_validate(values)


@pytest.fixture
def db(monkeypatch):
    url = os.getenv("MP_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set MP_TEST_DATABASE_URL to a disposable marketpulse_test database")
    if urlparse(url).path != "/marketpulse_test":
        raise RuntimeError("Tests require the explicit marketpulse_test database")
    from marketpulse import db

    monkeypatch.setattr(db, "DATABASE_URL", url)
    with psycopg.connect(url) as conn:
        conn.execute("DROP SCHEMA IF EXISTS raw CASCADE")
        conn.execute("DROP SCHEMA IF EXISTS marts CASCADE")
        conn.execute("DROP SCHEMA IF EXISTS ops CASCADE")
    db.migrate()
    return db


@pytest.fixture
def run(db):
    from marketpulse.replay import enqueue

    with db.connection() as conn:
        conn.execute(
            "INSERT INTO ops.datasets(id,day,manifest,events) VALUES('synthetic-fixture','2025-01-06','{}',2)"
        )
    return enqueue("synthetic-fixture")
