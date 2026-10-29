import csv
import hashlib
import io
import json
import time
import zipfile
from collections.abc import Iterator
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Protocol

import httpx

from marketpulse.config import DATA, DAY, SYMBOLS
from marketpulse.contracts import MarketEvent, digest, identity


class Provider(Protocol):
    def fetch_history(self, day: str) -> tuple[list[MarketEvent], dict]: ...
    def subscribe_or_poll(self) -> Iterator[MarketEvent]: ...
    def normalize(self, symbol: str, row: list[str], lineage: dict[str, str]) -> MarketEvent: ...
    def rate_limit(self) -> None: ...
    def health_check(self) -> dict: ...


def fetch_bytes(url: str, *, retries: int = 4, client: httpx.Client | None = None) -> bytes:
    owned = client is None
    client = client or httpx.Client(timeout=httpx.Timeout(30, connect=10), follow_redirects=False)
    try:
        for attempt in range(retries):
            try:
                with client.stream("GET", url) as response:
                    if response.status_code == 429 or response.status_code >= 500:
                        delay = min(float(response.headers.get("Retry-After", 2**attempt)), 15)
                        if attempt + 1 == retries:
                            response.raise_for_status()
                        time.sleep(delay)
                        continue
                    response.raise_for_status()
                    if int(response.headers.get("Content-Length", "0")) > 20_000_000:
                        raise ValueError("Source exceeds the daily archive byte budget")
                    chunks = []
                    size = 0
                    for chunk in response.iter_bytes():
                        size += len(chunk)
                        if size > 20_000_000:
                            raise ValueError("Source exceeds the daily archive byte budget")
                        chunks.append(chunk)
                    return b"".join(chunks)
            except (httpx.TimeoutException, httpx.NetworkError):
                if attempt + 1 == retries:
                    raise
                time.sleep(min(2**attempt, 8))
        raise RuntimeError("Source retries exhausted")
    finally:
        if owned:
            client.close()


class BinanceArchive:
    """Official historical 1-minute spot bars. Never labels archives as live quotes."""

    provider = "binance_vision"

    def rate_limit(self) -> None:
        time.sleep(0.2)

    def normalize(self, symbol: str, row: list[str], lineage: dict[str, str]) -> MarketEvent:
        if len(row) != 12:
            raise ValueError("Expected the official 12-column spot kline schema")
        stamp = int(row[0])
        scale = 1_000_000 if stamp >= 100_000_000_000_000 else 1_000
        event_time = datetime.fromtimestamp(stamp / scale, timezone.utc)
        return MarketEvent(
            event_id=identity(self.provider, symbol, "bar_1m", str(stamp)),
            provider=self.provider,
            provider_event_id=str(stamp),
            symbol=symbol,
            exchange="Binance Spot",
            event_type="bar_1m",
            event_time_utc=event_time,
            ingestion_time_utc=datetime.now(timezone.utc),
            price=Decimal(row[4]),
            open=Decimal(row[1]),
            high=Decimal(row[2]),
            low=Decimal(row[3]),
            volume=Decimal(row[5]),
            currency="USDT",
            source_mode="historical_replay",
            raw_payload_hash=digest(row),
            lineage=lineage,
        )

    def fetch_history(self, day: str = DAY) -> tuple[list[MarketEvent], dict]:
        date.fromisoformat(day)
        if day != DAY:
            raise ValueError(f"This bounded demo registry currently permits {DAY} only")
        root = DATA / "landing"
        root.mkdir(parents=True, exist_ok=True)
        events: list[MarketEvent] = []
        sources = []
        for symbol in SYMBOLS:
            name = f"{symbol}-1m-{day}.zip"
            url = f"https://data.binance.vision/data/spot/daily/klines/{symbol}/1m/{name}"
            self.rate_limit()
            checksum = fetch_bytes(url + ".CHECKSUM").decode().split()[0]
            if len(checksum) != 64:
                raise ValueError("Invalid upstream SHA-256 checksum")
            path = root / (checksum + ".zip")
            blob = path.read_bytes() if path.exists() else fetch_bytes(url)
            if hashlib.sha256(blob).hexdigest() != checksum:
                raise ValueError("Archive checksum mismatch; cached file is not trusted")
            with zipfile.ZipFile(io.BytesIO(blob)) as archive:
                names = archive.infolist()
                if len(names) != 1 or names[0].file_size > 20_000_000:
                    raise ValueError("Unexpected archive structure or expanded size")
                rows = list(csv.reader(io.StringIO(archive.read(names[0]).decode())))
            if not rows:
                raise ValueError("Empty source archive")
            lineage = {
                "url": url,
                "archive_sha256": checksum,
                "dataset_day": day,
                "license": "CC BY-NC-SA 4.0; Binance Vision Dataset Terms",
            }
            normalized = [self.normalize(symbol, row, lineage) for row in rows]
            if any(e.event_time_utc.date().isoformat() != day for e in normalized):
                raise ValueError("Archive rows do not match the requested day")
            path.write_bytes(blob)
            events.extend(normalized)
            sources.append(
                dict(symbol=symbol, url=url, sha256=checksum, bytes=len(blob), rows=len(rows))
            )
        events.sort(key=lambda e: (e.event_time_utc, e.symbol))
        dataset_id = digest({"day": day, "sources": sources, "schema_version": 1})[:24]
        manifest = {
            "id": dataset_id,
            "day": day,
            "sources": sources,
            "events": len(events),
            "mode": "historical_replay",
            "granularity": "1-minute OHLCV",
            "currency": "USDT",
            "attribution": "Binance Vision",
            "license_url": "https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md",
        }
        normalized_text = "\n".join(e.model_dump_json() for e in events) + "\n"
        manifest["normalized_sha256"] = hashlib.sha256(normalized_text.encode()).hexdigest()
        (DATA / "events.jsonl").write_text(normalized_text)
        (DATA / "dataset.json").write_text(json.dumps(manifest, indent=2))
        return events, manifest

    def subscribe_or_poll(self) -> Iterator[MarketEvent]:
        raise NotImplementedError("Historical archive adapter has no live subscription")
        yield

    def health_check(self) -> dict:
        return {
            "provider": self.provider,
            "mode": "historical_replay",
            "network_checked": False,
            "live_supported": False,
        }


def load_dataset() -> tuple[list[MarketEvent], dict]:
    path = DATA / "dataset.json"
    if not path.exists():
        return BinanceArchive().fetch_history()
    manifest = json.loads(path.read_text())
    normalized = (DATA / "events.jsonl").read_bytes()
    if hashlib.sha256(normalized).hexdigest() != manifest["normalized_sha256"]:
        raise ValueError("Normalized replay cache checksum mismatch")
    events = [MarketEvent.model_validate_json(line) for line in normalized.decode().splitlines()]
    if len(events) != manifest["events"]:
        raise ValueError("Normalized cache length mismatch")
    # Verify immutable upstream bytes even when using normalized replay cache.
    for source in manifest["sources"]:
        file = DATA / "landing" / (source["sha256"] + ".zip")
        if hashlib.sha256(file.read_bytes()).hexdigest() != source["sha256"]:
            raise ValueError("Cached original archive changed")
    return events, manifest
