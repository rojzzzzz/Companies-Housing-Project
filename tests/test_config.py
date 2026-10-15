"""Environment configuration and YAML contract loading."""

import logging
import runpy
from unittest.mock import Mock

import pytest
import yaml

from src import config
from src.config import get_env, logging_config
from src.config.read_contract import read_contract


def test_get_env_returns_configured_value(monkeypatch):
    monkeypatch.setenv("PIPELINE_TEST_VALUE", "configured")
    assert get_env("PIPELINE_TEST_VALUE") == "configured"


@pytest.mark.parametrize("value", [None, ""])
def test_get_env_rejects_missing_or_empty_values(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("PIPELINE_TEST_VALUE", raising=False)
    else:
        monkeypatch.setenv("PIPELINE_TEST_VALUE", value)
    with pytest.raises(
        ValueError, match="Missing required environment variable PIPELINE_TEST_VALUE"
    ):
        get_env("PIPELINE_TEST_VALUE")


@pytest.mark.parametrize("as_string", [False, True], ids=["path", "string"])
def test_read_contract_returns_inner_contract(tmp_path, as_string):
    path = tmp_path / "contract.yml"
    path.write_text(
        "version: 1\ncontract:\n  name: Café dataset\n  companies: []\n",
        encoding="utf-8",
    )
    assert read_contract(str(path) if as_string else path) == {
        "name": "Café dataset",
        "companies": [],
    }


def test_read_contract_missing_file_is_logged_and_raised(tmp_path, caplog):
    with caplog.at_level(logging.ERROR), pytest.raises(FileNotFoundError):
        read_contract(tmp_path / "missing.yml")
    assert "Data Contract file not found" in caplog.text


def test_read_contract_rejects_malformed_yaml(tmp_path, caplog):
    path = tmp_path / "invalid.yml"
    path.write_text("contract: [unterminated", encoding="utf-8")
    with caplog.at_level(logging.ERROR), pytest.raises(yaml.YAMLError):
        read_contract(path)
    assert "Error parsing Data Contract YAML" in caplog.text


def test_read_contract_requires_contract_key(tmp_path):
    path = tmp_path / "invalid.yml"
    path.write_text("version: 1", encoding="utf-8")
    with pytest.raises(KeyError, match="contract"):
        read_contract(path)


def test_project_contract_defines_all_pipeline_schemas():
    contract = read_contract()
    assert contract["base_url"].startswith("https://")
    assert all(isinstance(company["code"], str) for company in contract["companies"])
    assert set(contract["silver_schema"]) == {
        "company_info",
        "officers",
        "filings",
        "psc",
    }


@pytest.fixture
def execute_config(monkeypatch):
    """Execute configuration in a separate namespace without .env or log effects."""
    monkeypatch.setattr("dotenv.load_dotenv", Mock())
    monkeypatch.setattr(logging_config, "configure_logging", Mock())
    return lambda: runpy.run_path(config.__file__, run_name="src.config.__init__")


def test_database_credentials_are_read_from_environment(execute_config, monkeypatch):
    for name, value in {
        "POSTGRES_HOST": "localhost",
        "POSTGRES_DB": "portfolio",
        "POSTGRES_USER": "portfolio_user",
        "POSTGRES_PASSWORD": "fictional-password",
        "POSTGRES_PORT": "6543",
    }.items():
        monkeypatch.setenv(name, value)
    result = execute_config()
    assert result["DB_CREDENTIALS"] == {
        "host": "localhost",
        "dbname": "portfolio",
        "user": "portfolio_user",
        "password": "fictional-password",
        "port": 6543,
    }
    assert isinstance(result["DB_CREDENTIALS"]["port"], int)


@pytest.mark.parametrize(
    "name",
    [
        "API_KEY",
        "POSTGRES_HOST",
        "POSTGRES_DB",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_PORT",
    ],
)
@pytest.mark.parametrize("value", [None, ""], ids=["missing", "empty"])
def test_config_requires_each_credential(execute_config, monkeypatch, name, value):
    if value is None:
        monkeypatch.delenv(name, raising=False)
    else:
        monkeypatch.setenv(name, value)
    with pytest.raises(
        ValueError, match=f"Missing required environment variable {name}"
    ):
        execute_config()


def test_config_rejects_non_numeric_postgres_port(execute_config, monkeypatch):
    monkeypatch.setenv("POSTGRES_PORT", "not-a-port")
    with pytest.raises(ValueError, match="invalid literal"):
        execute_config()


def test_config_loads_dotenv_before_configuring_logging(execute_config, monkeypatch):
    calls = []
    monkeypatch.setattr("dotenv.load_dotenv", lambda: calls.append("dotenv"))
    monkeypatch.setattr(
        logging_config, "configure_logging", lambda: calls.append("logging")
    )
    execute_config()
    assert calls == ["dotenv", "logging"]


def test_config_paths_and_credentials_are_isolated():
    assert config.API_KEY == "test-api-key"
    assert config.DB_CREDENTIALS["host"] == "database.test"
    assert config.DB_CREDENTIALS["password"] == "test-password"
    assert config.SQL_DIR == config.DATA_DIR.parent / "sql"
    assert config.STAGING_DIR == config.DATA_DIR / "staging"
