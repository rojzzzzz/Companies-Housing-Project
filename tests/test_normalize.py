"""Aggregation, JSON input, CSV output, and normalization orchestration."""

import copy
import importlib
import json
import logging
from unittest.mock import AsyncMock

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from src.config.read_contract import read_contract
from src.extract import extract
from src.transform import normalize


@pytest.mark.parametrize("as_string", [False, True], ids=["path", "string"])
def test_get_data_reads_unicode_json(tmp_path, as_string):
    path = tmp_path / "raw.json"
    data = {"00123456": {"company_name": "Café Ltd"}}
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    assert normalize.get_data(str(path) if as_string else path) == data


def test_get_data_missing_file_is_logged_and_raised(tmp_path, caplog):
    with caplog.at_level(logging.ERROR), pytest.raises(FileNotFoundError):
        normalize.get_data(tmp_path / "missing.json")
    assert "Raw data file not found" in caplog.text


def test_get_data_rejects_malformed_json(tmp_path):
    path = tmp_path / "invalid.json"
    path.write_text("{broken", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        normalize.get_data(path)


@pytest.mark.parametrize(
    "builder",
    [
        normalize.get_company_tables,
        normalize.get_officers_tables,
        normalize.get_filings_tables,
        normalize.get_psc_tables,
    ],
)
def test_aggregators_reject_empty_dataset(builder):
    with pytest.raises(ValueError):
        builder({})


def test_get_company_tables_combines_companies_with_fresh_indexes(raw_data):
    tables = normalize.get_company_tables(raw_data)
    assert tables["company"]["company_number"].tolist() == ["00123456", "00987654"]
    assert len(tables["previous_company_names"]) == 2
    assert len(tables["sic_code"]) == 4
    for df in tables.values():
        assert df.index.tolist() == list(range(len(df)))


def test_get_officers_tables_preserves_company_relationships(raw_data):
    df = normalize.get_officers_tables(raw_data)["officers"]
    assert df[["company_number", "person_number"]].to_dict("records") == [
        {"company_number": "00123456", "person_number": "person-1"},
        {"company_number": "00987654", "person_number": "person-2"},
    ]


def test_get_filings_tables_adds_contract_company_number_to_capital(raw_data):
    tables = normalize.get_filings_tables(raw_data)
    assert set(tables) == {"filings", "capital"}
    assert tables["filings"]["transaction_id"].tolist() == ["filing-1", "filing-2"]
    capital = tables["capital"]
    assert capital["company_number"].tolist() == [
        "00123456",
        "00123456",
        "00987654",
        "00987654",
    ]
    assert capital["transaction_id"].tolist() == [
        "filing-1",
        "filing-1",
        "filing-2",
        "filing-2",
    ]
    expected = read_contract()["silver_schema"]["filings"]["tables"]["capital"][
        "columns"
    ]
    assert set(capital.columns) == set(expected)


def test_get_psc_tables_preserves_parent_links(raw_data):
    tables = normalize.get_psc_tables(raw_data)
    assert len(tables["psc"]) == 2
    assert len(tables["psc_nature"]) == 4
    assert set(tables["psc_nature"]["psc_id"]) == set(tables["psc"]["link_self"])


def test_get_tables_returns_all_eight_tables_without_mutating_input(raw_data):
    original = copy.deepcopy(raw_data)
    groups = normalize.get_tables(raw_data)
    assert [set(group) for group in groups] == [
        {"company", "previous_company_names", "sic_code"},
        {"officers"},
        {"filings", "capital"},
        {"psc", "psc_nature"},
    ]
    assert raw_data == original


@pytest.mark.parametrize("as_string", [False, True], ids=["path", "string"])
def test_save_as_csv_round_trips_without_index(tmp_path, as_string):
    df = pd.DataFrame({"name": ["Café, Ltd", 'Example "Quoted" Ltd'], "value": [1, 2]})
    path = tmp_path / "table.csv"
    normalize.save_as_csv(df, str(path) if as_string else path)
    assert_frame_equal(pd.read_csv(path), df)


def test_save_as_csv_propagates_write_errors(tmp_path, caplog):
    with caplog.at_level(logging.ERROR), pytest.raises(OSError):
        normalize.save_as_csv(
            pd.DataFrame({"id": [1]}), tmp_path / "missing" / "table.csv"
        )
    assert "Failed to save DataFrame" in caplog.text


def test_make_csv_creates_nested_folder_and_reports_file_count(tmp_path):
    tables = {"first": pd.DataFrame({"id": [1]}), "second": pd.DataFrame({"id": [2]})}
    staging = tmp_path / "nested" / "staging"
    assert normalize.make_csv(tables, staging, "example") == 2
    assert {path.name for path in (staging / "example").iterdir()} == {
        "first.csv",
        "second.csv",
    }
    assert_frame_equal(pd.read_csv(staging / "example" / "first.csv"), tables["first"])


def test_make_csv_can_replace_existing_files(tmp_path):
    normalize.make_csv({"table": pd.DataFrame({"id": [1]})}, tmp_path, "example")
    assert (
        normalize.make_csv({"table": pd.DataFrame({"id": [2]})}, tmp_path, "example")
        == 1
    )
    assert pd.read_csv(tmp_path / "example" / "table.csv")["id"].tolist() == [2]


def test_make_csv_handles_no_tables(tmp_path):
    assert normalize.make_csv({}, tmp_path, "empty") == 0
    assert list((tmp_path / "empty").iterdir()) == []


@pytest.mark.integration
def test_main_writes_all_tables_to_correct_schemas_regardless_of_contract_order(
    raw_data, tmp_path, monkeypatch, caplog
):
    raw_path = tmp_path / "raw.json"
    extract.save_data(raw_data, raw_path)
    monkeypatch.setattr(
        normalize, "get_data", lambda: json.loads(raw_path.read_text(encoding="utf-8"))
    )
    staging = tmp_path / "staging"
    monkeypatch.setattr(normalize, "STAGING_DIR", staging)
    schema = read_contract()["silver_schema"]
    schema = dict(reversed(list(schema.items())))

    with caplog.at_level(logging.INFO):
        normalize.main(schema)

    expected_paths = {
        f"{schema_name}/{table_name}.csv"
        for schema_name, group in schema.items()
        for table_name in group["tables"]
    }
    assert {
        path.relative_to(staging).as_posix() for path in staging.rglob("*.csv")
    } == expected_paths
    for schema_name, group in schema.items():
        for table_name, contract in group["tables"].items():
            df = pd.read_csv(staging / schema_name / f"{table_name}.csv", dtype=str)
            assert set(df.columns) == set(contract["columns"])
            assert not df.empty
    assert "Total CSV files created: 8" in caplog.text


def test_main_requires_expected_schema_names(raw_data, tmp_path, monkeypatch):
    monkeypatch.setattr(normalize, "get_data", lambda: raw_data)
    monkeypatch.setattr(normalize, "STAGING_DIR", tmp_path)
    with pytest.raises(ValueError, match="Missing schema contract for 'company_info'"):
        normalize.main({})


def test_importing_normalize_does_not_fetch_or_write_data(monkeypatch):
    fetch = AsyncMock(side_effect=AssertionError("Import must not fetch data"))
    monkeypatch.setattr(extract, "fetch_data", fetch)
    importlib.reload(normalize)
    fetch.assert_not_called()
