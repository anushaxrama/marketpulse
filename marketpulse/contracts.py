import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .config import SYMBOLS


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def identity(provider: str, symbol: str, event_type: str, provider_event_id: str) -> str:
    return digest([1, provider, symbol, event_type, provider_event_id])


class MarketEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    provider: str = Field(min_length=1, max_length=64)
    provider_event_id: str | None = Field(default=None, min_length=1, max_length=128)
    symbol: str
    exchange: str = Field(min_length=1, max_length=64)
    event_type: Literal["bar_1m", "quote", "trade"]
    event_time_utc: datetime
    ingestion_time_utc: datetime
    price: Decimal = Field(gt=0, max_digits=28, decimal_places=12)
    volume: Decimal | None = Field(default=None, ge=0, max_digits=28, decimal_places=12)
    currency: Literal["USD", "USDT", "EUR", "GBP"]
    source_mode: Literal["historical_replay", "live", "delayed", "synthetic_test"]
    source_delay_minutes: int | None = Field(default=None, ge=0)
    schema_version: Literal[1] = 1
    raw_payload_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    open: Decimal | None = Field(default=None, gt=0, max_digits=28, decimal_places=12)
    high: Decimal | None = Field(default=None, gt=0, max_digits=28, decimal_places=12)
    low: Decimal | None = Field(default=None, gt=0, max_digits=28, decimal_places=12)
    lineage: dict[str, str]

    @field_validator("symbol")
    @classmethod
    def registered_symbol(cls, value: str) -> str:
        if value not in SYMBOLS:
            raise ValueError("Symbol must be in the configured symbol registry")
        return value

    @field_validator("event_time_utc", "ingestion_time_utc")
    @classmethod
    def utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("Timezone offset is required")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def semantic_contract(self) -> "MarketEvent":
        if self.event_id != identity(
            self.provider,
            self.symbol,
            self.event_type,
            self.provider_event_id or self.event_time_utc.isoformat(),
        ):
            raise ValueError("Event identity does not match provider identity fields")
        if self.event_type == "quote" and self.volume is not None:
            raise ValueError("Quote snapshots cannot carry executed volume")
        if self.event_type == "bar_1m":
            if self.volume is None or self.open is None or self.high is None or self.low is None:
                raise ValueError("OHLCV fields are required for one-minute bars")
            if (
                not self.low
                <= min(self.open, self.price)
                <= max(self.open, self.price)
                <= self.high
            ):
                raise ValueError("Invalid OHLC bounds")
            if self.event_time_utc.second or self.event_time_utc.microsecond:
                raise ValueError("One-minute bar opens must align to minute boundaries")
        if self.source_mode == "delayed" and self.source_delay_minutes is None:
            raise ValueError("Delayed feeds require a declared delay")
        return self
