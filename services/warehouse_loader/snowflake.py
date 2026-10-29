"""Optional Snowflake export. Requires explicit CLI opt-in and existing warehouse resources."""

import hashlib
import json
import os
import tempfile
from pathlib import Path
from uuid import UUID

from marketpulse.db import query


def export_run(run_id: str) -> dict:
    UUID(run_id)
    required = [
        "SNOWFLAKE_ACCOUNT",
        "SNOWFLAKE_USER",
        "SNOWFLAKE_PRIVATE_KEY_FILE",
        "SNOWFLAKE_WAREHOUSE",
        "SNOWFLAKE_DATABASE",
        "SNOWFLAKE_SCHEMA",
    ]
    if any(not os.getenv(k) for k in required):
        raise ValueError(
            "Snowflake configuration is incomplete; no warehouse resources are provisioned automatically"
        )
    import snowflake.connector

    records = query(
        "SELECT run_id,event_id,symbol,event_time,open,high,low,close,volume,currency,provider,payload_hash,source_mode FROM marts.fact_bars WHERE run_id=%s ORDER BY event_id",
        (run_id,),
    )
    if not records:
        raise ValueError("No curated run rows to export")
    content = "\n".join(json.dumps(row, default=str, sort_keys=True) for row in records) + "\n"
    batch_id = hashlib.sha256(content.encode()).hexdigest()
    conn = snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        private_key_file=os.environ["SNOWFLAKE_PRIVATE_KEY_FILE"],
        warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
        database=os.environ["SNOWFLAKE_DATABASE"],
        schema=os.environ["SNOWFLAKE_SCHEMA"],
        login_timeout=20,
        network_timeout=60,
    )
    try:
        with conn.cursor() as cur:
            for statement in (
                (Path(__file__).resolve().parents[2] / "warehouse/snowflake.sql")
                .read_text()
                .split(";")
            ):
                if statement.strip():
                    cur.execute(statement)
            if cur.execute(
                "SELECT 1 FROM MP_LOAD_BATCHES WHERE BATCH_ID=%s", (batch_id,)
            ).fetchone():
                return {"status": "already_loaded", "batch_id": batch_id, "rows": len(records)}
            cur.execute("CREATE TEMP TABLE MP_STAGE_EVENTS (PAYLOAD VARIANT)")
            with tempfile.TemporaryDirectory(prefix="marketpulse-sf-") as folder:
                file = Path(folder) / "bars.json"
                file.write_text(content)
                uri = file.as_uri().replace("'", "''")
                cur.execute(f"PUT '{uri}' @MP_STAGE/{batch_id} AUTO_COMPRESS=TRUE OVERWRITE=FALSE")
                cur.execute(
                    f"COPY INTO MP_STAGE_EVENTS FROM @MP_STAGE/{batch_id}/ FILES=('bars.json.gz') FILE_FORMAT=(TYPE=JSON) ON_ERROR=ABORT_STATEMENT"
                )
            staged = cur.execute("SELECT COUNT(*) FROM MP_STAGE_EVENTS").fetchone()[0]
            if staged != len(records):
                raise ValueError("Snowflake stage count does not reconcile")
            cur.execute("BEGIN")
            try:
                # Serialize this exporter operationally; Snowflake primary-key constraints are informational.
                conflict = cur.execute(
                    """SELECT COUNT(*) FROM MP_FACT_BARS t JOIN MP_STAGE_EVENTS s ON t.RUN_ID=s.PAYLOAD:run_id::string AND t.EVENT_ID=s.PAYLOAD:event_id::string WHERE t.PAYLOAD_HASH<>s.PAYLOAD:payload_hash::string"""
                ).fetchone()[0]
                if conflict:
                    raise ValueError(
                        "Existing Snowflake event identity has conflicting source content"
                    )
                cur.execute("""MERGE INTO MP_FACT_BARS t USING (SELECT PAYLOAD FROM MP_STAGE_EVENTS QUALIFY ROW_NUMBER() OVER(PARTITION BY PAYLOAD:run_id::string,PAYLOAD:event_id::string ORDER BY PAYLOAD:payload_hash::string)=1) s
                ON t.RUN_ID=s.PAYLOAD:run_id::string AND t.EVENT_ID=s.PAYLOAD:event_id::string
                WHEN NOT MATCHED THEN INSERT(RUN_ID,EVENT_ID,SYMBOL,EVENT_TIME,OPEN,HIGH,LOW,CLOSE,VOLUME,CURRENCY,PROVIDER,PAYLOAD_HASH,SOURCE_MODE)
                VALUES(s.PAYLOAD:run_id::string,s.PAYLOAD:event_id::string,s.PAYLOAD:symbol::string,TO_TIMESTAMP_TZ(s.PAYLOAD:event_time::string),s.PAYLOAD:open::NUMBER(28,12),s.PAYLOAD:high::NUMBER(28,12),s.PAYLOAD:low::NUMBER(28,12),s.PAYLOAD:close::NUMBER(28,12),s.PAYLOAD:volume::NUMBER(28,12),s.PAYLOAD:currency::string,s.PAYLOAD:provider::string,s.PAYLOAD:payload_hash::string,s.PAYLOAD:source_mode::string)""")
                cur.execute(
                    "INSERT INTO MP_LOAD_BATCHES(BATCH_ID,RUN_ID,ROW_COUNT) VALUES(%s,%s,%s)",
                    (batch_id, run_id, len(records)),
                )
                cur.execute("COMMIT")
            except Exception:
                cur.execute("ROLLBACK")
                raise
            return {
                "status": "loaded",
                "batch_id": batch_id,
                "rows": len(records),
                "run_id": run_id,
            }
    finally:
        conn.close()
