"""PostgreSQL loading behavior with real SQL objects and mocked connections."""

import csv
import logging
from unittest.mock import Mock

import psycopg2
import pytest
from psycopg2 import sql

from src.load import load


@pytest.fixture
def load_paths(tmp_path, monkeypatch):
    """Use temporary SQL and staging folders for every loader test."""
    sql_dir = tmp_path / "sql"
    staging_dir = tmp_path / "staging"
    sql_dir.mkdir()
    staging_dir.mkdir()
    monkeypatch.setattr(load, "SQL_DIR", sql_dir)
    monkeypatch.setattr(load, "STAGING_DIR", staging_dir)
    return sql_dir, staging_dir


@pytest.mark.parametrize("as_string", [False, True], ids=["path", "string"])
def test_get_columns_reads_quoted_unicode_headers(tmp_path, as_string):
    path = tmp_path / "records.csv"
    columns = ["company_number", "name, display", 'quoted "name"', "Café"]
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(columns)
        writer.writerow(["00123456", "Example", "Quoted", "Value"])
    assert load.get_columns(str(path) if as_string else path) == columns


def test_get_columns_accepts_header_only_csv(tmp_path):
    path = tmp_path / "records.csv"
    path.write_text("company_number,name\n", encoding="utf-8")
    assert load.get_columns(path) == ["company_number", "name"]


@pytest.mark.parametrize("content", ["", "\n", "\r\n"])
def test_get_columns_rejects_empty_headers(tmp_path, content):
    path = tmp_path / "empty.csv"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError, match="CSV file is empty"):
        load.get_columns(path)


def test_get_columns_propagates_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        load.get_columns(tmp_path / "missing.csv")


@pytest.mark.parametrize(
    "table, columns",
    [
        ("company", ["company_number", "company_name"]),
        ('table"; DROP TABLE staging.company; --', ['odd"column', "name, display"]),
    ],
)
def test_build_copy_query_composes_identifiers_in_header_order(table, columns):
    query = load.build_copy_query(table, columns)
    assert isinstance(query, sql.Composed)
    prefix, target, opening, fields, suffix = query.seq
    assert prefix.string == "COPY "
    assert isinstance(target, sql.Identifier)
    assert target.strings == ("staging", table)
    assert opening.string == " ("
    assert [
        part.strings for part in fields.seq if isinstance(part, sql.Identifier)
    ] == [(column,) for column in columns]
    assert all(part.string == ", " for part in fields.seq if isinstance(part, sql.SQL))
    assert suffix.string == ") FROM STDIN WITH (FORMAT CSV, HEADER TRUE)"


def test_build_copy_query_requires_columns():
    with pytest.raises(ValueError, match="No columns provided for table company"):
        load.build_copy_query("company", [])


@pytest.mark.parametrize("as_string", [False, True], ids=["path", "string"])
def test_create_tables_executes_sorted_nested_sql_then_truncates(tmp_path, as_string):
    sql_dir = tmp_path / "sql"
    (sql_dir / "nested").mkdir(parents=True)
    (sql_dir / "a.sql").write_text(
        "CREATE TABLE staging.a (name TEXT); -- Café", encoding="utf-8"
    )
    (sql_dir / "nested" / "z.sql").write_text(
        "CREATE TABLE staging.z (id INT);", encoding="utf-8"
    )
    (sql_dir / "ignored.txt").write_text("not SQL", encoding="utf-8")
    cursor = Mock()

    load.create_tables(cursor, str(sql_dir) if as_string else sql_dir)

    queries = [call.args[0] for call in cursor.execute.call_args_list]
    assert queries[0] == "CREATE TABLE staging.a (name TEXT); -- Café"
    assert queries[2] == "CREATE TABLE staging.z (id INT);"
    assert len(queries) == 4
    for query, table in zip(queries[1::2], ["a", "z"]):
        assert query.seq[0].string == "TRUNCATE TABLE "
        assert query.seq[1].strings == ("staging", table)


def test_create_tables_handles_no_sql_files(tmp_path):
    cursor = Mock()
    load.create_tables(cursor, tmp_path)
    cursor.execute.assert_not_called()


@pytest.mark.parametrize("fail_on", [1, 2], ids=["ddl", "truncate"])
def test_create_tables_logs_and_propagates_database_errors(tmp_path, caplog, fail_on):
    (tmp_path / "a.sql").write_text(
        "CREATE TABLE staging.a (id INT);", encoding="utf-8"
    )
    (tmp_path / "b.sql").write_text(
        "CREATE TABLE staging.b (id INT);", encoding="utf-8"
    )
    error = psycopg2.ProgrammingError("Initialization failed")
    cursor = Mock()
    cursor.execute.side_effect = [None] * (fail_on - 1) + [error]
    with (
        caplog.at_level(logging.ERROR),
        pytest.raises(psycopg2.ProgrammingError) as caught,
    ):
        load.create_tables(cursor, tmp_path)
    assert caught.value is error
    assert cursor.execute.call_count == fail_on
    assert "Error initializing staging tables" in caplog.text


def test_loader_initializes_schema_and_copies_sorted_csvs(database, load_paths, caplog):
    connect, connection, cursor = database
    sql_dir, staging_dir = load_paths
    (sql_dir / "company.sql").write_text(
        "CREATE TABLE staging.company (id TEXT, name TEXT);", encoding="utf-8"
    )
    (staging_dir / "nested").mkdir()
    (staging_dir / "a.csv").write_text(
        'id,name\n00123456,"Café, Ltd"\n', encoding="utf-8"
    )
    (staging_dir / "nested" / "z.csv").write_text(
        "value,id\n42,00987654\n", encoding="utf-8"
    )
    (staging_dir / "ignored.txt").write_text("not CSV", encoding="utf-8")
    copied = []

    def capture_copy(query, stream, *, size):
        assert not stream.closed
        assert stream.encoding.lower() == "utf-8"
        copied.append((query, stream.read(), size, stream))

    cursor.copy_expert.side_effect = capture_copy
    with caplog.at_level(logging.INFO):
        load.loader()

    connect.assert_called_once_with(**load.DB_CREDENTIALS)
    assert cursor.execute.call_args_list[0].args == (
        "CREATE SCHEMA IF NOT EXISTS staging",
    )
    assert cursor.execute.call_args_list[1].args == (
        "CREATE TABLE staging.company (id TEXT, name TEXT);",
    )
    assert [item[0].seq[1].strings for item in copied] == [
        ("staging", "a"),
        ("staging", "z"),
    ]
    assert [
        part.strings
        for part in copied[1][0].seq[3].seq
        if isinstance(part, sql.Identifier)
    ] == [("value",), ("id",)]
    assert [item[1] for item in copied] == [
        'id,name\n00123456,"Café, Ltd"\n',
        "value,id\n42,00987654\n",
    ]
    assert all(item[2] == 8192 and item[3].closed for item in copied)
    connection.__exit__.assert_called_once_with(None, None, None)
    connection.cursor.return_value.__exit__.assert_called_once_with(None, None, None)
    connection.close.assert_called_once_with()
    assert "loaded successfully into staging.a" in caplog.text
    assert "loaded successfully into staging.z" in caplog.text


def test_loader_with_no_csvs_still_initializes_schema(database, load_paths):
    _, connection, cursor = database
    load.loader()
    cursor.execute.assert_called_once_with("CREATE SCHEMA IF NOT EXISTS staging")
    cursor.copy_expert.assert_not_called()
    connection.__exit__.assert_called_once_with(None, None, None)
    connection.close.assert_called_once_with()


def test_loader_propagates_connection_failure(load_paths, monkeypatch, caplog):
    error = psycopg2.OperationalError("Connection unavailable")
    connect = Mock(side_effect=error)
    monkeypatch.setattr(load.psycopg2, "connect", connect)
    with (
        caplog.at_level(logging.ERROR),
        pytest.raises(psycopg2.OperationalError) as caught,
    ):
        load.loader()
    assert caught.value is error
    assert "Error in loader function" in caplog.text


@pytest.mark.parametrize("stage", ["schema", "ddl", "truncate", "copy", "header"])
def test_loader_exits_transaction_with_error_and_closes_connection(
    database, load_paths, caplog, stage
):
    _, connection, cursor = database
    sql_dir, staging_dir = load_paths
    (sql_dir / "a.sql").write_text("CREATE TABLE staging.a (id INT);", encoding="utf-8")
    (staging_dir / "a.csv").write_text(
        "" if stage == "header" else "id\n1\n", encoding="utf-8"
    )
    (staging_dir / "z.csv").write_text("id\n2\n", encoding="utf-8")
    error = psycopg2.ProgrammingError("Database operation failed")
    if stage in {"schema", "ddl", "truncate"}:
        count = {"schema": 0, "ddl": 1, "truncate": 2}[stage]
        cursor.execute.side_effect = [None] * count + [error]
    elif stage == "copy":
        cursor.copy_expert.side_effect = error

    expected_error = ValueError if stage == "header" else psycopg2.ProgrammingError
    with caplog.at_level(logging.ERROR), pytest.raises(expected_error) as caught:
        load.loader()

    # psycopg2 performs rollback when its context manager receives an exception.
    # Assert that handoff, rather than pretending the mock is a real database.
    assert connection.__exit__.call_args.args[:2] == (expected_error, caught.value)
    assert connection.cursor.return_value.__exit__.call_args.args[:2] == (
        expected_error,
        caught.value,
    )
    connection.close.assert_called_once_with()
    assert cursor.copy_expert.call_count == (1 if stage == "copy" else 0)
    if stage == "copy":
        assert cursor.copy_expert.call_args.args[1].closed
    assert "Error in loader function" in caplog.text


def test_loader_closes_connection_when_commit_fails(database, load_paths):
    _, connection, _ = database
    connection.__exit__.side_effect = psycopg2.OperationalError("Commit failed")
    with pytest.raises(psycopg2.OperationalError, match="Commit failed"):
        load.loader()
    connection.close.assert_called_once_with()
