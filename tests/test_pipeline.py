"""Local integration from raw JSON through validation to mocked database loading."""

import copy
import csv
from functools import partial

import pandas as pd
import pytest

from src.config.read_contract import read_contract
from src.extract.extract import save_data
from src.load import load
from src.transform import normalize
from src.transform import validate as validation


@pytest.mark.integration
def test_raw_data_normalizes_validates_and_loads_all_eight_tables(
    raw_data, tmp_path, monkeypatch, database
):
    raw_path = tmp_path / "raw.json"
    staging = tmp_path / "staging"
    save_data(raw_data, raw_path)
    monkeypatch.setattr(normalize, "get_data", partial(normalize.get_data, raw_path))
    monkeypatch.setattr(normalize, "STAGING_DIR", staging)
    monkeypatch.setattr(validation, "STAGING_DIR", staging)
    monkeypatch.setattr(load, "STAGING_DIR", staging)

    # Use the real schema columns, with quality rules suited to synthetic data.
    # This tests stage compatibility rather than the health of live companies.
    schema = copy.deepcopy(read_contract()["silver_schema"])
    keys = {
        "company": ["company_number"],
        "previous_company_names": ["company_number", "effective_from"],
        "sic_code": ["company_number", "sic_code"],
        "officers": ["company_number", "person_number"],
        "filings": ["company_number", "transaction_id"],
        "capital": ["company_number", "transaction_id", "currency"],
        "psc": ["link_self"],
        "psc_nature": ["psc_id", "nature_of_control"],
    }
    for group in schema.values():
        for name, table_contract in group["tables"].items():
            rule = {"columns": keys[name], "min": 1.0, "warning": 1.0}
            table_contract["quality"] = {
                "completeness": [copy.deepcopy(rule)],
                "uniqueness": [copy.deepcopy(rule)],
            }

    normalize.main(schema)
    dataset = validation.validate({"silver_schema": schema})

    assert dataset.health == "HEALTHY"
    assert {table.name for table in dataset.tables} == set(keys)
    assert all(table.passed_quality_checks for table in dataset.tables)
    assert sum(len(table.quality_results) for table in dataset.tables) == 16

    # Leading zeros must survive the raw-to-CSV stages.
    companies = pd.read_csv(staging / "company_info" / "company.csv", dtype=str)
    assert companies["company_number"].tolist() == ["00123456", "00987654"]

    _, connection, cursor = database
    copied = {}

    def capture_copy(query, stream, *, size):
        assert size == 8192
        table_name = query.seq[1].strings[1]
        copied[table_name] = list(csv.DictReader(stream))

    cursor.copy_expert.side_effect = capture_copy
    load.loader()
    assert set(copied) == set(keys)
    assert {name: len(rows) for name, rows in copied.items()} == {
        "company": 2,
        "previous_company_names": 2,
        "sic_code": 4,
        "officers": 2,
        "filings": 2,
        "capital": 4,
        "psc": 2,
        "psc_nature": 4,
    }
    assert [row["company_number"] for row in copied["company"]] == [
        "00123456",
        "00987654",
    ]
    connection.__exit__.assert_called_once_with(None, None, None)
    connection.close.assert_called_once_with()
