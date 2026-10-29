import json

import httpx
import pytest

from services.ingestor import providers


def test_retries_429_and_503_but_not_404(monkeypatch):
    monkeypatch.setattr(providers.time, "sleep", lambda _: None)
    statuses = iter([429, 503, 200])
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(next(statuses), content=b"ok", headers={"Retry-After": "0"})

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        assert providers.fetch_bytes("https://example.test/source", client=client) == b"ok"
    assert len(calls) == 3
    calls.clear()
    with httpx.Client(
        transport=httpx.MockTransport(lambda req: calls.append(req) or httpx.Response(404))
    ) as client:
        with pytest.raises(httpx.HTTPStatusError):
            providers.fetch_bytes("https://example.test/missing", client=client)
    assert len(calls) == 1


def test_archive_size_budget():
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, headers={"Content-Length": "99999999"})
        )
    ) as client:
        with pytest.raises(ValueError, match="budget"):
            providers.fetch_bytes("https://example.test/too-big", client=client)


def test_corrupt_normalized_cache_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(providers, "DATA", tmp_path)
    (tmp_path / "dataset.json").write_text(json.dumps({"normalized_sha256": "a" * 64}))
    (tmp_path / "events.jsonl").write_text("{}")
    with pytest.raises(ValueError, match="checksum"):
        providers.load_dataset()


def test_spark_offset_shapes_normalize_without_evaluation():
    from services.warehouse_loader.postgres import normalize_offsets

    assert normalize_offsets("None") is None
    assert normalize_offsets("null") is None
    assert normalize_offsets(None) is None
    expected = {"market.raw.v1": {"0": 12, "1": 0, "2": 4}}
    assert normalize_offsets(expected) == expected
    assert normalize_offsets(json.dumps(expected)) == expected
    assert normalize_offsets(str(expected)) == expected
    with pytest.raises((ValueError, SyntaxError)):
        normalize_offsets("__import__('os').system('unsafe')")
