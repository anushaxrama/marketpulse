"""Independently compare Spark windows with PostgreSQL aggregation of accepted bars."""

import json
from datetime import datetime, timezone
from pathlib import Path

from marketpulse.db import query


def main():
    runs = query(
        "SELECT DISTINCT ON(scenario,window_minutes,watermark_minutes) id,scenario,window_minutes,watermark_minutes "
        "FROM ops.runs WHERE status='completed' AND (result->>'late_dropped_from_windows')::integer=0 "
        "ORDER BY scenario,window_minutes,watermark_minutes,created_at DESC"
    )
    results = []
    for run in runs:
        mismatch = query(
            """WITH reference AS (
            SELECT symbol,date_bin(%s::interval,event_time,'2000-01-01'::timestamptz) window_start,
              count(*) bar_count,(array_agg(open ORDER BY event_time))[1] open,
              (array_agg(close ORDER BY event_time DESC))[1] close,
              max(high) high,min(low) low,sum(volume) volume
            FROM marts.fact_bars WHERE run_id=%s GROUP BY 1,2
            ), observed AS (SELECT * FROM marts.stream_windows WHERE run_id=%s)
            SELECT count(*) mismatches FROM reference r FULL JOIN observed o USING(symbol,window_start)
            WHERE r.bar_count IS DISTINCT FROM o.bar_count OR r.open IS DISTINCT FROM o.open
               OR r.close IS DISTINCT FROM o.close OR r.high IS DISTINCT FROM o.high
               OR r.low IS DISTINCT FROM o.low OR r.volume IS DISTINCT FROM o.volume""",
            (f"{run['window_minutes']} minutes", run["id"], run["id"]),
        )[0]["mismatches"]
        assert mismatch == 0, (run, mismatch)
        results.append({**run, "ohlcv_mismatches": mismatch})
    assert {r["window_minutes"] for r in results} == {1, 5, 15}
    output = Path(__file__).resolve().parents[1] / "docs/evidence/window-reference.json"
    output.write_text(
        json.dumps(
            {
                "captured_at_utc": datetime.now(timezone.utc).isoformat(),
                "reference": "Independent PostgreSQL date_bin and ordered OHLCV aggregation; exact numeric comparison; runs with watermark exclusions are deliberately excluded.",
                "runs": results,
            },
            indent=2,
            default=str,
        )
        + "\n"
    )
    print(f"Verified exact OHLCV for {len(results)} scenario/window configurations")


if __name__ == "__main__":
    main()
