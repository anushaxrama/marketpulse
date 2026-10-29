import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.getenv("MP_DATA_DIR", str(ROOT / "data")))
DATABASE_URL = os.getenv(
    "MP_DATABASE_URL", "postgresql://marketpulse:marketpulse_local@127.0.0.1:5546/marketpulse"
)
BROKERS = os.getenv("MP_KAFKA_BROKERS", "localhost:19094")
SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT")
RAW = "market.raw.v1"
CURATED = "market.curated.v1"
DLQ = "market.deadletter.v1"
DAY = "2025-01-06"
