import os

import pytest

from services.warehouse_loader.snowflake import export_run


def test_snowflake_requires_existing_resource_configuration(monkeypatch):
    for name in [
        "SNOWFLAKE_ACCOUNT",
        "SNOWFLAKE_USER",
        "SNOWFLAKE_PRIVATE_KEY_FILE",
        "SNOWFLAKE_WAREHOUSE",
        "SNOWFLAKE_DATABASE",
        "SNOWFLAKE_SCHEMA",
    ]:
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(ValueError, match="configuration is incomplete"):
        export_run("00000000-0000-0000-0000-000000000001")


@pytest.mark.skipif(
    os.getenv("MP_TEST_SNOWFLAKE") != "true",
    reason="Optional real Snowflake integration requires explicit opt-in and existing account resources",
)
def test_snowflake_export_and_retry_real_account():
    run_id = os.environ["MP_SNOWFLAKE_TEST_RUN_ID"]
    first = export_run(run_id)
    second = export_run(run_id)
    assert first["status"] in ("loaded", "already_loaded")
    assert second["status"] == "already_loaded"
    assert first["batch_id"] == second["batch_id"]
