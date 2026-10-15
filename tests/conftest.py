"""Shared synthetic data and isolation for the pipeline test suite."""

import copy
import os
from unittest.mock import MagicMock, Mock

import httpx
import psycopg2
import pytest

# Configuration is loaded at import time: isolate credentials and log settings
# before importing any pipeline module, even when a developer has a .env file.
_test_environment = {
    "API_KEY": "test-api-key",
    "POSTGRES_HOST": "database.test",
    "POSTGRES_DB": "test_pipeline",
    "POSTGRES_USER": "test_user",
    "POSTGRES_PASSWORD": "test-password",
    "POSTGRES_PORT": "5432",
    "LOG_LEVEL": "INFO",
    "LOG_FILE": "",
}
_original_environment = {name: os.environ.get(name) for name in _test_environment}
os.environ.update(_test_environment)


def pytest_unconfigure(config):
    """Restore the caller's environment when pytest finishes."""
    for name, value in _original_environment.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value


@pytest.fixture(autouse=True)
def block_live_http(monkeypatch):
    """Fail immediately if a test attempts a real HTTP request."""

    def reject_request(*args, **kwargs):
        raise AssertionError("Live HTTP is disabled; use httpx.MockTransport.")

    async def reject_async_request(*args, **kwargs):
        reject_request()

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", reject_request)
    monkeypatch.setattr(
        httpx.AsyncHTTPTransport, "handle_async_request", reject_async_request
    )


@pytest.fixture(autouse=True)
def block_live_database(monkeypatch):
    """Loader tests must explicitly supply a mocked connection."""

    def reject_connection(*args, **kwargs):
        raise AssertionError("Live PostgreSQL is disabled; mock psycopg2.connect.")

    monkeypatch.setattr(psycopg2, "connect", reject_connection)


@pytest.fixture
def database(monkeypatch):
    """Mock the connection and cursor contexts used by the PostgreSQL loader."""
    from src.load import load

    connection = MagicMock(spec=psycopg2.extensions.connection)
    cursor = MagicMock(spec=psycopg2.extensions.cursor)
    connection.__enter__.return_value = connection
    connection.__exit__.return_value = False
    connection.cursor.return_value.__enter__.return_value = cursor
    connection.cursor.return_value.__exit__.return_value = False
    connect = Mock(return_value=connection)
    monkeypatch.setattr(load.psycopg2, "connect", connect)
    return connect, connection, cursor


@pytest.fixture
def company_data():
    """One fictional company with every collection and nested optional fields."""
    return {
        "company": {
            "company_number": "00123456",
            "company_name": "Example & Sons Ltd",
            "company_status": "active",
            "type": "ltd",
            "jurisdiction": "england-wales",
            "date_of_creation": "2020-01-01",
            "can_file": True,
            "has_charges": False,
            "accounts": {
                "accounting_reference_date": {"day": "31", "month": "12"},
                "last_accounts": {
                    "made_up_to": "2024-12-31",
                    "period_start_on": "2024-01-01",
                    "period_end_on": "2024-12-31",
                    "type": "micro-entity",
                },
                "next_accounts": {"due_on": "2026-09-30", "overdue": False},
            },
            "confirmation_statement": {"next_due": "2026-02-01"},
            "registered_office_address": {
                "address_line_1": "1 Example Street",
                "locality": "London",
                "postal_code": "EX1 1AA",
                "country": "United Kingdom",
            },
            "previous_company_names": [
                {
                    "name": "Former Example Ltd",
                    "effective_from": "2020-01-01",
                    "ceased_on": "2021-01-01",
                }
            ],
            "sic_codes": ["62012", "62020"],
            "links": {"self": "/company/00123456"},
        },
        "officers": [
            {
                "person_number": "person-1",
                "name": "Jane Example",
                "officer_role": "director",
                "appointed_on": "2020-01-01",
                "date_of_birth": {"month": 5, "year": 1980},
                "address": {"locality": "London", "postal_code": "EX1 1AA"},
                "links": {
                    "self": "/company/00123456/appointments/person-1",
                    "appointment": "/officers/person-1/appointments",
                },
                "identity_verification_details": {
                    "appointment_verification_start_on": "2025-01-01",
                    "appointment_verification_end_on": "2025-02-01",
                },
            }
        ],
        "filings": [
            {
                "transaction_id": "filing-1",
                "type": "SH01",
                "date": "2024-01-01",
                "pages": 2,
                "paper_filed": False,
                "description_values": {
                    "description": "Statement of capital",
                    "made_up_date": "2024-01-01",
                    "capital": [
                        {"currency": "GBP", "figure": "100.00"},
                        {"currency": "EUR", "figure": "200.00"},
                    ],
                },
                "links": {"self": "/company/00123456/filing-history/filing-1"},
            }
        ],
        "persons_with_significant_control": [
            {
                "name": "Jane Example",
                "kind": "individual-person-with-significant-control",
                "ceased": False,
                "notified_on": "2020-01-01",
                "date_of_birth": {"year": 1980},
                "name_elements": {"forename": "Jane", "surname": "Example"},
                "links": {"self": "/company/00123456/psc/person-1"},
                "natures_of_control": [
                    "ownership-of-shares-75-to-100-percent",
                    "voting-rights-75-to-100-percent",
                ],
            }
        ],
    }


@pytest.fixture
def raw_data(company_data):
    """Two companies with distinct identifiers, for aggregation tests."""
    second = copy.deepcopy(company_data)
    second["company"]["company_number"] = "00987654"
    second["company"]["company_name"] = "Second Example Ltd"
    second["filings"][0]["transaction_id"] = "filing-2"
    second["officers"][0]["person_number"] = "person-2"
    second["officers"][0]["links"]["self"] = "/company/00987654/appointments/person-2"
    second["persons_with_significant_control"][0]["links"]["self"] = (
        "/company/00987654/psc/person-2"
    )
    return {"00123456": company_data, "00987654": second}
