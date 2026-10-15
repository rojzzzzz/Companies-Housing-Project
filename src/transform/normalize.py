"""Transforms the raw data stored as a JSON file into a normalized format for further processing and analysis."""

from src.config import RAW_FILE, STAGING_DIR
from src.extract.extract import fetch_data
from src.config.read_contract import read_contract
from src.config import table_columns
from pathlib import Path
import pandas as pd
import asyncio
import logging
import json
import time

logger = logging.getLogger(__name__)

def get_data(path: Path | str = RAW_FILE) -> dict:
    """Extracts the raw data from the JSON file and returns it as a dictionary."""
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            logger.info(f"Successfully loaded raw data")
            return data

    except FileNotFoundError:
        logger.error(f"Raw data file not found at {path}. Check the path")
        raise

def get_company_tables(data: dict) -> dict:
    """Extracts the company tables from the raw data and returns them as a dictionary."""

    company_tables_by_id = {company_id: table_columns.company_tables(company_info['company']) for company_id, company_info
                            in data.items()}

    if not company_tables_by_id:
        logger.error("No company info tables were created. Check the raw data for missing company information.")
        raise ValueError(company_tables_by_id)

    else:
        table_keys = next(iter(company_tables_by_id.values())).keys()
        company_info_tables = {
            table_key: pd.concat(
                [df[table_key] for df in company_tables_by_id.values()], ignore_index=True)
                for table_key in table_keys
            }

    logger.info(f"Successfully created the company info tables for {company_info_tables.keys()}")
    return company_info_tables

def get_officers_tables(data: dict) -> dict:
    """Extracts the officers tables from the raw data and returns them as a dictionary."""

    officers_dfs = {company_id: table_columns.officers_tables(company_info) for company_id, company_info in data.items()}
    if not officers_dfs:
        logger.error("No officers tables were created. Check the raw data for missing officer information.")
        raise ValueError(officers_dfs)

    officers_dfs['officers'] = pd.concat([df for df in officers_dfs.values()], ignore_index=True)
    officers_dfs = {'officers': officers_dfs['officers']}

    logger.info(f"Successfully created the officers tables for {officers_dfs.keys()}")
    return officers_dfs

def get_filings_tables(data: dict) -> dict:
    """Extracts the filings tables from the raw data and returns them as a dictionary."""

    filings_dfs = {company_id: table_columns.filings_tables(company_info) for company_id, company_info in data.items()}

    if not filings_dfs:
        logger.error("No filings tables were created. Check the raw data for missing filing information.")
        raise ValueError(filings_dfs)

    filings = pd.concat([df[0] for df in filings_dfs.values()], ignore_index=True)

    for company_code in filings_dfs.keys():
        filings_dfs[company_code] = filings_dfs[company_code][1]

    for key, df in filings_dfs.items():
        df['company_number'] = key

    capital = pd.concat([df for df in filings_dfs.values()], ignore_index=True)
    capital['figure'] = capital['figure'].str.replace(',', '.', regex=False)
    filings_dfs = {'filings': filings, 'capital': capital}
    logger.info(f"Successfully created the filings tables for {filings_dfs.keys()}")
    return filings_dfs

def get_psc_tables(data: dict) -> dict:
    """Extracts the PSC tables from the raw data and returns them as a dictionary."""

    psc_dfs = {company_id: table_columns.psc_tables(company_info) for company_id, company_info in data.items()}

    if not psc_dfs:
        logger.error("No PSC tables were created. Check the raw data for missing PSC information.")
        raise ValueError(psc_dfs)

    psc_tables = {}
    psc_tables['psc'] = pd.concat([dfs[0] for dfs in psc_dfs.values()], ignore_index=True)
    psc_tables['psc_nature'] = pd.concat([dfs[1] for dfs in psc_dfs.values()], ignore_index=True)

    logger.info(f"Successfully created the PSC tables: {psc_tables.keys()}")
    return psc_tables

def save_as_csv(df: pd.DataFrame, path: Path | str) -> None:
    """Saves the given DataFrame as a CSV file at the specified path."""
    
    try:
        df.to_csv(path, index=False)
    except Exception as e:
        logger.error(f"Failed to save DataFrame to {path}: {e}")
        raise

def make_csv(company_tables: dict, staging_path: Path | str, folder_name: str) -> int:
    """Saves the given company tables as CSV files in the specified staging path and folder name."""

    files_created = 0
    path = f"{staging_path}/{folder_name}"
    Path(path).mkdir(parents=True, exist_ok=True)

    for key, df in company_tables.items():
        save_as_csv(df, f"{path}/{key}.csv")
        files_created += 1

    return files_created

def get_tables(data: dict) -> list:
    tables = []
    tables.append(get_company_tables(data))
    tables.append(get_officers_tables(data))
    tables.append(get_filings_tables(data))
    tables.append(get_psc_tables(data))
    return tables

def main(schema_contract: dict) -> None:
    """Main function to execute the data normalization process."""
    
    logger.info("Starting the data normalization process...")
    start = time.perf_counter()

    data = get_data()
    tables = get_tables(data)

    files_created = 0
    staging_folders = ("company_info", "officers", "filings", "psc")
    for folder_name, table in zip(staging_folders, tables):
        if folder_name not in schema_contract:
            raise ValueError(f"Missing schema contract for '{folder_name}'.")
        files_created += make_csv(table, STAGING_DIR, folder_name)

    duration = time.perf_counter() - start
    logger.info(f"Data normalization process completed in {duration:.2f} seconds.")
    logger.info(f"Total CSV files created: {files_created}")

if __name__ == "__main__":
    asyncio.run(fetch_data())
    main(read_contract()["silver_schema"])
