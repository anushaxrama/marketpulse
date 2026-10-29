import json
from datetime import datetime, timezone
from decimal import Decimal

import psycopg
import pytest
from conftest import event
from fastapi.testclient import TestClient

from services.warehouse_loader.postgres import audit_batch, window_batch


def delivery(run, evt, offset):
    return {
        "topic": "market.raw.v1",
        "partition": 0,
        "offset": offset,
        "value": json.dumps({"run_id": run, "event": evt.model_dump(mode="json")}),
    }


def test_duplicate_poison_conflict_and_exact_batch_retry(db, run):
    a = event()
    changed = event(raw_payload_hash="b" * 64)
    rows = [
        delivery(run, a, 0),
        delivery(run, a, 1),
        delivery(run, changed, 2),
        {"topic": "market.raw.v1", "partition": 0, "offset": 3, "value": "{bad-json"},
    ]
    audit_batch(run, 0, rows)
    audit_batch(run, 0, rows)
    assert db.query("SELECT count(*) n FROM marts.fact_bars")[0]["n"] == 1
    assert {
        r["status"]: r["n"]
        for r in db.query("SELECT status,count(*) n FROM raw.deliveries GROUP BY status")
    } == {"accepted": 1, "duplicate": 1, "conflict": 1, "invalid": 1}
    assert db.query("SELECT count(*) n FROM ops.outbox")[0]["n"] == 3


def test_database_failure_rolls_back_entire_microbatch(db, run):
    with db.connection() as conn:
        conn.execute(
            """CREATE FUNCTION raw.reject_fixture() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NEW.provider='explode' THEN RAISE EXCEPTION 'injected test failure'; END IF; RETURN NEW; END $$"""
        )
        conn.execute(
            "CREATE TRIGGER fail_fixture BEFORE INSERT ON marts.fact_bars FOR EACH ROW EXECUTE FUNCTION raw.reject_fixture()"
        )
    with pytest.raises(psycopg.Error):
        audit_batch(
            run, 0, [delivery(run, event(), 0), delivery(run, event(1, provider="explode"), 1)]
        )
    assert db.query("SELECT count(*) n FROM marts.fact_bars")[0]["n"] == 0
    assert db.query("SELECT count(*) n FROM raw.deliveries")[0]["n"] == 0
    assert db.query("SELECT count(*) n FROM ops.batches")[0]["n"] == 0


def test_window_sink_commit_is_idempotent(db, run):
    with db.connection() as conn:
        conn.execute("UPDATE ops.runs SET scenario='warehouse_retry' WHERE id=%s", (run,))
    row = {
        "symbol": "BTCUSDT",
        "window": {
            "start": datetime(2025, 1, 6, tzinfo=timezone.utc),
            "end": datetime(2025, 1, 6, 0, 5, tzinfo=timezone.utc),
        },
        "events": [
            {
                "event_id": "a",
                "event_time": datetime(2025, 1, 6, tzinfo=timezone.utc),
                "open": Decimal("100"),
                "price": Decimal("101"),
                "high": Decimal("102"),
                "low": Decimal("99"),
                "volume": Decimal("2.5"),
            }
        ],
    }
    assert window_batch(run, 0, [row]) is True
    assert window_batch(run, 0, [row]) is False
    assert db.query("SELECT sum(volume) n FROM marts.stream_windows")[0]["n"] == Decimal("2.5")
    assert db.query("SELECT count(*) n FROM ops.faults")[0]["n"] == 1


def test_api_empty_bounds_decimal_and_lab_gate(db, run, monkeypatch):
    from services.api.app import app

    client = TestClient(app)
    assert client.get("/health").status_code == 200
    assert client.get("/api/overview").json()["run"] is None
    assert client.get("/api/series?symbol=BOGUS").status_code == 422
    assert client.get("/api/series?run_id=not-a-uuid").status_code == 422
    assert client.get("/api/series?limit=999999").status_code == 422
    assert client.get("/api/series?hours=2").status_code == 422
    monkeypatch.setenv("MP_LAB_ENABLED", "false")
    assert (
        client.post("/api/lab/replays", json={"dataset_id": "synthetic-fixture"}).status_code == 403
    )
    audit_batch(run, 0, [delivery(run, event(), 0), delivery(run, event(1), 1)])
    with db.connection() as conn:
        conn.execute("UPDATE ops.runs SET status='completed' WHERE id=%s", (run,))
    rows = client.get("/api/series?hours=24&run_id=" + run).json()
    assert rows[0]["close"] == "100.100000000000"
    assert rows[0]["log_return"] is None
    assert client.get("/api/series?symbol=BTCUSDT%27%3Bdrop%20table").status_code == 422
    monkeypatch.setenv("MP_LAB_ENABLED", "true")
    for _ in range(3):
        assert (
            client.post("/api/lab/replays", json={"dataset_id": "synthetic-fixture"}).status_code
            == 202
        )
    assert (
        client.post("/api/lab/replays", json={"dataset_id": "synthetic-fixture"}).status_code == 409
    )


def test_gap_returns_are_not_interpolated(db, run):
    audit_batch(run, 0, [delivery(run, event(), 0), delivery(run, event(2, price="100.5"), 1)])
    rows = db.query("SELECT * FROM marts.bar_features ORDER BY event_time")
    assert rows[1]["gap_before"] is True
    assert rows[1]["log_return"] is None


def test_equivalent_runs_have_stable_identity_and_replay_plan(db, run):
    from marketpulse.replay import enqueue, scenario_events

    enqueue("synthetic-fixture")
    rows = db.query("SELECT replay_id FROM ops.runs ORDER BY created_at")
    assert rows[0]["replay_id"] == rows[1]["replay_id"]
    events = [event(i) for i in range(12)]
    assert scenario_events(events, "reorder") == scenario_events(events, "reorder")
    assert len(scenario_events(events, "duplicate")) == 13


def test_interrupted_publisher_keeps_initial_offsets_and_counts_retries(db, run, monkeypatch):
    from types import SimpleNamespace

    from marketpulse import replay

    events = [event(), event(1)]
    monkeypatch.setattr(replay, "load_dataset", lambda: (events, {"id": "synthetic-fixture"}))
    sent = []
    state = {"fail": True}

    class Consumer:
        def __init__(self, **kwargs):
            pass

        def end_offsets(self, partitions):
            return {
                p: sum(1 for row in sent if row["partition"] == p.partition)
                if p.topic == "market.raw.v1"
                else 0
                for p in partitions
            }

        def close(self):
            pass

    class Producer:
        def send(self, topic, **kwargs):
            if len(sent) == 1 and state["fail"]:
                state["fail"] = False
                raise RuntimeError("injected producer interruption")
            sent.append(kwargs)
            return SimpleNamespace(get=lambda **kwargs: None)

        def flush(self, **kwargs):
            pass

        def close(self):
            pass

    monkeypatch.setattr(replay, "KafkaConsumer", Consumer)
    monkeypatch.setattr(replay, "producer", Producer)
    row = db.query("SELECT * FROM ops.runs WHERE id=%s", (run,))[0]
    with pytest.raises(RuntimeError, match="producer interruption"):
        replay.publish_run(row)
    first = db.query("SELECT * FROM ops.runs WHERE id=%s", (run,))[0]
    replay.publish_run(first)
    final = db.query("SELECT * FROM ops.runs WHERE id=%s", (run,))[0]
    assert first["config"]["raw_offsets"] == final["config"]["raw_offsets"]
    assert final["input_count"] == 3
    assert final["config"]["published"] is True


def test_anomaly_baseline_excludes_current_spike_and_realized_volatility_is_measured(db, run):
    rows = [delivery(run, event(i, price="100"), i) for i in range(30)]
    rows.append(delivery(run, event(30, price="110", high="111"), 30))
    audit_batch(run, 0, rows)
    features = db.query("SELECT * FROM marts.bar_features ORDER BY event_time")
    assert features[20]["anomaly_score"] is None
    assert features[29]["anomaly_score"] == 0
    assert features[-1]["baseline_n"] == 20
    assert features[-1]["anomaly_score"] > Decimal("3.5")
    assert features[-1]["realized_volatility"] > 0
    assert features[29]["realized_volatility"] == 0
