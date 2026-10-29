from datetime import datetime, timezone
from decimal import Decimal

import pytest
from conftest import event
from pydantic import ValidationError

from marketpulse.contracts import MarketEvent
from services.ingestor.providers import BinanceArchive


@pytest.mark.parametrize(
    "changes",
    [
        {"price": "0"},
        {"price": "NaN"},
        {"price": "Infinity"},
        {"volume": "-1"},
        {"currency": "DOGE"},
        {"schema_version": 2},
        {"symbol": "UNREGISTERED"},
        {"low": "102"},
        {"high": "99"},
        {"event_time_utc": "2025-01-06T00:00:01Z"},
        {"event_time_utc": "2025-01-06T00:00:00"},
        {"source_mode": "delayed", "source_delay_minutes": None},
    ],
)
def test_rejects_invalid_contract(changes):
    with pytest.raises(ValidationError):
        event(**changes)


def test_decimal_prices_are_not_binary_floats():
    assert event().price == Decimal("100.10")
    assert isinstance(event().price, Decimal)


def test_quote_cannot_claim_executed_volume():
    with pytest.raises(ValidationError):
        event(event_type="quote")
    assert event(event_type="quote", volume=None).volume is None


def test_identity_must_match_namespace():
    payload = event().model_dump()
    payload["event_id"] = "a" * 64
    with pytest.raises(ValidationError):
        MarketEvent.model_validate(payload)


@pytest.mark.parametrize(
    "local,expected",
    [
        ("2025-03-09T01:59:00-05:00", "2025-03-09T06:59:00+00:00"),
        ("2025-03-09T03:00:00-04:00", "2025-03-09T07:00:00+00:00"),
        ("2025-11-02T01:30:00-04:00", "2025-11-02T05:30:00+00:00"),
        ("2025-11-02T01:30:00-05:00", "2025-11-02T06:30:00+00:00"),
    ],
)
def test_explicit_offsets_preserve_dst_instants(local, expected):
    assert event(event_time_utc=local).event_time_utc.isoformat() == expected


def test_official_timestamp_microseconds_and_milliseconds():
    row = [
        "1736121600000000",
        "100",
        "101",
        "99",
        "100.10",
        "2.25",
        "1736121659999999",
        "225.225",
        "10",
        "1",
        "100",
        "0",
    ]
    adapter = BinanceArchive()
    a = adapter.normalize("BTCUSDT", row, {"fixture": "synthetic schema test"})
    row[0] = "1736121600000"
    b = adapter.normalize("BTCUSDT", row, {"fixture": "synthetic schema test"})
    assert a.event_time_utc == b.event_time_utc == datetime(2025, 1, 6, tzinfo=timezone.utc)
    with pytest.raises(ValueError):
        adapter.normalize("BTCUSDT", row[:3], {})
