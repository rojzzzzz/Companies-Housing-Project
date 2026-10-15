"""Extraction with deterministic HTTP responses and no live API calls."""

import asyncio
import json
import logging
import runpy
from unittest.mock import AsyncMock, Mock

import httpx
import pytest

from src.config import read_contract as contract_module
from src.extract import extract


@pytest.fixture
def mock_api(monkeypatch):
    """Retain real httpx response handling while replacing its transport."""
    client_class = httpx.AsyncClient
    monkeypatch.setattr(extract, "url", "https://example.test/company")
    monkeypatch.setattr(extract, "API_KEY", "test-api-key")
    monkeypatch.setattr(
        extract,
        "collection_endpoints",
        {"officers": "officers", "filings": "filing-history"},
    )

    def install(handler):
        def client_factory(**kwargs):
            return client_class(transport=httpx.MockTransport(handler), **kwargs)

        monkeypatch.setattr(extract.httpx, "AsyncClient", client_factory)

    return install


@pytest.mark.parametrize("as_string", [False, True], ids=["path", "string"])
def test_save_data_writes_readable_unicode_json(tmp_path, as_string):
    path = tmp_path / "raw.json"
    data = {"00123456": {"name": "Café & Sons", "active": True, "optional": None}}
    extract.save_data(data, str(path) if as_string else path)
    text = path.read_text(encoding="utf-8")
    assert json.loads(text) == data
    assert "Café" in text
    assert "\n    " in text


def test_save_data_overwrites_previous_content(tmp_path):
    path = tmp_path / "raw.json"
    path.write_text('{"old": true}', encoding="utf-8")
    extract.save_data({"new": []}, path)
    assert json.loads(path.read_text(encoding="utf-8")) == {"new": []}


def test_save_data_propagates_filesystem_errors(tmp_path, caplog):
    with caplog.at_level(logging.ERROR), pytest.raises(FileNotFoundError):
        extract.save_data({}, tmp_path / "missing" / "raw.json")
    assert "Error saving data" in caplog.text


def test_save_data_rejects_non_json_values(tmp_path):
    with pytest.raises(TypeError):
        extract.save_data({"invalid": object()}, tmp_path / "raw.json")


@pytest.mark.parametrize("total_key", ["total_results", "total_count"])
def test_get_company_data_paginates_and_preserves_collection_names(mock_api, total_key):
    calls = []

    def handler(request):
        calls.append(request)
        assert request.headers["authorization"] == "Basic dGVzdC1hcGkta2V5Og=="
        if request.url.path == "/company/00123456":
            return httpx.Response(200, json={"company_number": "00123456"})
        assert request.url.params["items_per_page"] == "500"
        start = int(request.url.params["start_index"])
        if request.url.path.endswith("/officers"):
            items = [{"id": 1}, {"id": 2}] if start == 0 else [{"id": 3}]
            return httpx.Response(200, json={"items": items, total_key: 3})
        return httpx.Response(
            200, json={"items": [{"transaction_id": "filing-1"}], total_key: 1}
        )

    mock_api(handler)
    result = asyncio.run(extract.get_company_data("00123456"))
    assert result == {
        "company": {"company_number": "00123456"},
        "officers": [{"id": 1}, {"id": 2}, {"id": 3}],
        "filings": [{"transaction_id": "filing-1"}],
    }
    officer_starts = [
        request.url.params["start_index"]
        for request in calls
        if request.url.path.endswith("/officers")
    ]
    assert officer_starts == ["0", "2"]
    assert len(calls) == 4


@pytest.mark.parametrize("empty_page", [{"items": []}, {}, {"items": None}])
def test_get_company_data_stops_at_empty_pages_without_totals(mock_api, empty_page):
    starts = []

    def handler(request):
        if request.url.path == "/company/00123456":
            return httpx.Response(200, json={"company_number": "00123456"})
        start = int(request.url.params["start_index"])
        starts.append(start)
        page = {"items": [{"id": 1}]} if start == 0 else empty_page
        return httpx.Response(200, json=page)

    mock_api(handler)
    result = asyncio.run(extract.get_company_data("00123456"))
    assert result["officers"] == result["filings"] == [{"id": 1}]
    assert sorted(starts) == [0, 0, 1, 1]


@pytest.mark.parametrize(
    "status, message",
    [
        (404, "Data not found"),
        (429, "Rate limit exceeded"),
        (500, "Server error 500"),
        (503, "Server error 503"),
        (401, "HTTP error 401"),
    ],
)
@pytest.mark.parametrize(
    "failure_path", ["/company/00123456", "/company/00123456/officers"]
)
def test_get_company_data_propagates_http_errors(
    mock_api, caplog, status, message, failure_path
):
    def handler(request):
        if request.url.path == failure_path:
            return httpx.Response(status, text="API failure")
        return httpx.Response(200, json={"items": []})

    mock_api(handler)
    with (
        caplog.at_level(logging.WARNING),
        pytest.raises(httpx.HTTPStatusError) as error,
    ):
        asyncio.run(extract.get_company_data("00123456"))
    assert error.value.response.status_code == status
    assert message in caplog.text


def test_get_company_data_propagates_connection_errors(mock_api, caplog):
    def handler(request):
        raise httpx.ConnectError("Connection refused", request=request)

    mock_api(handler)
    with caplog.at_level(logging.ERROR), pytest.raises(httpx.ConnectError):
        asyncio.run(extract.get_company_data("00123456"))
    assert "Request error" in caplog.text


def test_get_company_data_rejects_invalid_json(mock_api):
    mock_api(lambda request: httpx.Response(200, text="not JSON"))
    with pytest.raises(json.JSONDecodeError):
        asyncio.run(extract.get_company_data("00123456"))


def test_fetch_data_saves_all_companies_once(monkeypatch):
    fetch = AsyncMock(
        side_effect=[
            {"company": {"company_number": "001"}},
            {"company": {"company_number": "002"}},
        ]
    )
    save = Mock()
    monkeypatch.setattr(extract, "companies", ["001", "002"])
    monkeypatch.setattr(extract, "get_company_data", fetch)
    monkeypatch.setattr(extract, "save_data", save)

    asyncio.run(extract.fetch_data())

    assert [call.args for call in fetch.await_args_list] == [("001",), ("002",)]
    save.assert_called_once_with(
        {
            "001": {"company": {"company_number": "001"}},
            "002": {"company": {"company_number": "002"}},
        }
    )


def test_fetch_data_does_not_save_partial_results(monkeypatch):
    fetch = AsyncMock(side_effect=[{"company": {}}, RuntimeError("API failed")])
    save = Mock()
    monkeypatch.setattr(extract, "companies", ["001", "002"])
    monkeypatch.setattr(extract, "get_company_data", fetch)
    monkeypatch.setattr(extract, "save_data", save)

    with pytest.raises(RuntimeError, match="API failed"):
        asyncio.run(extract.fetch_data())
    save.assert_not_called()


def test_fetch_data_propagates_save_errors(monkeypatch):
    monkeypatch.setattr(extract, "companies", ["001"])
    monkeypatch.setattr(
        extract, "get_company_data", AsyncMock(return_value={"company": {}})
    )
    monkeypatch.setattr(extract, "save_data", Mock(side_effect=OSError("Disk full")))
    with pytest.raises(OSError, match="Disk full"):
        asyncio.run(extract.fetch_data())


@pytest.mark.parametrize(
    "field, value",
    [
        ("base_url", None),
        ("base_url", ""),
        ("companies", []),
        ("collection_endpoints", {}),
    ],
)
def test_extraction_import_rejects_missing_contract_configuration(
    monkeypatch, field, value
):
    contract = {
        "base_url": "https://example.test/company",
        "companies": [{"code": "00123456"}],
        "collection_endpoints": {"officers": "officers"},
    }
    contract[field] = value
    monkeypatch.setattr(contract_module, "read_contract", lambda: contract)
    with pytest.raises(
        ValueError, match="Missing required configuration in the contract"
    ):
        runpy.run_path(extract.__file__)
