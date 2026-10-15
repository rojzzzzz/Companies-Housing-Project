"""Nested API records are flattened without losing identifiers or values."""

import copy

import pandas as pd
import pytest

from src.config import table_columns
from src.config.read_contract import read_contract


def test_company_tables_flattens_nested_fields(company_data):
    tables = table_columns.company_tables(company_data["company"])
    assert set(tables) == {"company", "previous_company_names", "sic_code"}
    row = tables["company"].iloc[0]
    expected = {
        "company_number": "00123456",
        "company_name": "Example & Sons Ltd",
        "company_type": "ltd",
        "accounting_reference_day": "31",
        "accounting_reference_month": "12",
        "last_accounts_made_up_to": "2024-12-31",
        "next_accounts_due_on": "2026-09-30",
        "confirmation_next_due": "2026-02-01",
        "address_line_1": "1 Example Street",
        "link_self": "/company/00123456",
    }
    assert row[list(expected)].to_dict() == expected
    assert bool(row["can_file"]) is True
    assert bool(row["has_charges"]) is False
    assert bool(row["next_accounts_overdue"]) is False


def test_company_tables_expands_previous_names_and_sic_codes(company_data):
    tables = table_columns.company_tables(company_data["company"])
    assert tables["previous_company_names"].to_dict("records") == [
        {
            "name": "Former Example Ltd",
            "effective_from": "2020-01-01",
            "ceased_on": "2021-01-01",
            "company_number": "00123456",
        }
    ]
    assert tables["sic_code"].to_dict("records") == [
        {"company_number": "00123456", "sic_code": "62012"},
        {"company_number": "00123456", "sic_code": "62020"},
    ]


def test_company_tables_accepts_absent_optional_fields():
    tables = table_columns.company_tables({"company_number": "00123456"})
    assert tables["company"].loc[0, "company_number"] == "00123456"
    assert pd.isna(tables["company"].loc[0, "next_accounts_due_on"])
    assert tables["previous_company_names"].empty
    assert tables["sic_code"].empty


def test_company_tables_requires_company_identifier():
    with pytest.raises(KeyError, match="company_number"):
        table_columns.company_tables({})


def test_officers_tables_flattens_birth_address_and_verification(company_data):
    df = table_columns.officers_tables(company_data)
    expected = {
        "company_number": "00123456",
        "person_number": "person-1",
        "name": "Jane Example",
        "birth_month": 5,
        "birth_year": 1980,
        "address_locality": "London",
        "address_postal_code": "EX1 1AA",
        "verification_start_on": "2025-01-01",
        "verification_end_on": "2025-02-01",
    }
    assert df.loc[0, list(expected)].to_dict() == expected


def test_filings_tables_links_multiple_capital_rows_to_filing(company_data):
    filings, capital = table_columns.filings_tables(company_data)
    assert filings.loc[0, "company_number"] == "00123456"
    assert filings.loc[0, "description_value"] == "Statement of capital"
    assert filings.loc[0, "made_up_date"] == "2024-01-01"
    assert bool(filings.loc[0, "paper_filed"]) is False
    assert capital.to_dict("records") == [
        {"transaction_id": "filing-1", "currency": "GBP", "figure": "100.00"},
        {"transaction_id": "filing-1", "currency": "EUR", "figure": "200.00"},
    ]


def test_psc_tables_expands_control_natures_with_parent_link(company_data):
    psc, natures = table_columns.psc_tables(company_data)
    assert psc.loc[0, "company_number"] == "00123456"
    assert psc.loc[0, "birth_year"] == 1980
    assert psc.loc[0, "forename"] == "Jane"
    assert bool(psc.loc[0, "ceased"]) is False
    assert natures.to_dict("records") == [
        {"psc_id": "/company/00123456/psc/person-1", "nature_of_control": nature}
        for nature in company_data["persons_with_significant_control"][0][
            "natures_of_control"
        ]
    ]


def test_psc_tables_preserves_corporate_registration_fields(company_data):
    company_data["persons_with_significant_control"] = [
        {
            "name": "Example Holdings Ltd",
            "kind": "corporate-entity-person-with-significant-control",
            "identification": {
                "legal_form": "Limited company",
                "legal_authority": "Companies Act 2006",
                "country_registered": "United Kingdom",
                "place_registered": "England",
                "registration_number": "00888888",
            },
        }
    ]
    psc, natures = table_columns.psc_tables(company_data)
    assert psc.loc[0, "country_registered"] == "United Kingdom"
    assert psc.loc[0, "registration_number"] == "00888888"
    assert psc.loc[0, "legal_form"] == "Limited company"
    assert pd.isna(psc.loc[0, "birth_year"])
    assert natures.empty


@pytest.mark.parametrize(
    "builder, collection",
    [
        (table_columns.officers_tables, "officers"),
        (table_columns.filings_tables, "filings"),
        (table_columns.psc_tables, "persons_with_significant_control"),
    ],
)
def test_collection_builders_accept_empty_collections(
    company_data, builder, collection
):
    company_data[collection] = []
    result = builder(company_data)
    frames = result if isinstance(result, list) else [result]
    assert all(frame.empty for frame in frames)


@pytest.mark.parametrize(
    "builder, collection, optional_column",
    [
        (table_columns.officers_tables, "officers", "birth_year"),
        (table_columns.filings_tables, "filings", "description_value"),
        (table_columns.psc_tables, "persons_with_significant_control", "legal_form"),
    ],
)
def test_collection_builders_accept_missing_optional_fields(
    company_data, builder, collection, optional_column
):
    company_data[collection] = [{}]
    result = builder(company_data)
    df = result[0] if isinstance(result, list) else result
    assert df.loc[0, "company_number"] == "00123456"
    assert pd.isna(df.loc[0, optional_column])


@pytest.mark.parametrize(
    "builder, collection",
    [
        (table_columns.officers_tables, "officers"),
        (table_columns.filings_tables, "filings"),
        (table_columns.psc_tables, "persons_with_significant_control"),
    ],
)
def test_collection_builders_reject_missing_collections(
    company_data, builder, collection
):
    del company_data[collection]
    with pytest.raises(KeyError, match=collection):
        builder(company_data)


def test_table_builders_do_not_mutate_input(company_data):
    original = copy.deepcopy(company_data)
    table_columns.company_tables(company_data["company"])
    table_columns.officers_tables(company_data)
    table_columns.filings_tables(company_data)
    table_columns.psc_tables(company_data)
    assert company_data == original


def test_populated_tables_match_declared_contract_columns(company_data):
    schema = read_contract()["silver_schema"]
    frames = {
        "company_info": table_columns.company_tables(company_data["company"]),
        "officers": {"officers": table_columns.officers_tables(company_data)},
        "filings": {"filings": table_columns.filings_tables(company_data)[0]},
        "psc": dict(zip(("psc", "psc_nature"), table_columns.psc_tables(company_data))),
    }
    # Capital receives its company_number in the aggregation stage.
    for schema_name, tables in frames.items():
        for table_name, df in tables.items():
            assert set(df.columns) == set(
                schema[schema_name]["tables"][table_name]["columns"]
            )
