from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import psycopg
from psycopg.rows import dict_row

from .config import DATABASE_URL, ROOT


@contextmanager
def connection() -> Iterator[psycopg.Connection[dict[str, Any]]]:
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        conn.execute("SET TIME ZONE 'UTC'")
        conn.execute("SET statement_timeout='30s'")
        yield conn


def migrate() -> None:
    with connection() as conn:
        conn.execute("SELECT pg_advisory_xact_lock(739134)")
        conn.execute("CREATE SCHEMA IF NOT EXISTS ops")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS ops.schema_migrations(version integer PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
        )
        applied = {
            r["version"]
            for r in conn.execute("SELECT version FROM ops.schema_migrations").fetchall()
        }
        for path in sorted((ROOT / "warehouse").glob("[0-9]*.sql")):
            version = int(path.name.split("_")[0])
            if version not in applied:
                conn.execute(path.read_text())


def query(sql: str, params: Any = None) -> list[dict[str, Any]]:
    with connection() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        return list(conn.execute(sql, params).fetchall())
