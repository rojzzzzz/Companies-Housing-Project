from src.config import STAGING_DIR, SQL_DIR, DB_CREDENTIALS
from contextlib import closing
from psycopg2 import sql
from pathlib import Path
import psycopg2
import logging
import csv

logger = logging.getLogger(__name__)

def create_tables(cur, sql_path: Path | str = SQL_DIR) -> None:
    try:
        for file in sorted(Path(sql_path).rglob("*.sql")):
            query = file.read_text(encoding="utf-8")

            cur.execute(query)

            cur.execute(
                sql.SQL("TRUNCATE TABLE {}").format(
                    sql.Identifier("staging", file.stem)
                )
            )

            logger.info(
                f"Table staging.{file.stem} initialized successfully."
            )

    except psycopg2.Error:
        logger.exception("Error initializing staging tables")
        raise
    
def get_columns(path: Path | str) -> list[str]:
    with open(path, "r", encoding='utf-8') as f:
        columns = next(csv.reader(f), None)

    if not columns:
        raise ValueError(f"CSV file is empty: {path}")

    return columns

def build_copy_query(table: str, columns: list[str]):
    if not columns:
        raise ValueError(f"No columns provided for table {table}")

    return sql.SQL(
        "COPY {} ({}) FROM STDIN WITH (FORMAT CSV, HEADER TRUE)"
    ).format(
        sql.Identifier("staging", table),
        sql.SQL(", ").join(sql.Identifier(col) for col in columns)
    )

def loader():
    try:
        with closing(psycopg2.connect(**DB_CREDENTIALS)) as conn:
            with conn:      
                with conn.cursor() as cur:
                    cur.execute("""CREATE SCHEMA IF NOT EXISTS staging""")
                    create_tables(cur, SQL_DIR)
                    for file in sorted(STAGING_DIR.rglob('*.csv')):
                        table_columns = get_columns(file)

                        c_query = build_copy_query(file.stem, table_columns)
                        with open(file, 'r', encoding='utf-8') as f:
                            cur.copy_expert(c_query, f, size=8192)

                        logger.info(f"Data from {file} loaded successfully into staging.{file.stem}.")

    except Exception as e:
        logger.exception(f"Error in loader function: {e}")
        raise
    
