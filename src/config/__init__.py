from dotenv import load_dotenv
from pathlib import Path
import logging
import os

from .logging_config import configure_logging

load_dotenv()
configure_logging()
logger = logging.getLogger(__name__)

def get_env(name: str):
    value = os.getenv(name)
    if not value:
        raise ValueError(f"Missing required environment variable {name}")
    return value

API_KEY = get_env("API_KEY")

#Postgres configuration
DB_CREDENTIALS ={
    "host": get_env("POSTGRES_HOST"),
    "dbname": get_env("POSTGRES_DB"),
    "user": get_env("POSTGRES_USER"),
    "password": get_env("POSTGRES_PASSWORD"),
    "port": int(get_env("POSTGRES_PORT"))
}

#Directory paths
CONTRACT_PATH = Path(__file__).parents[2] / "data" / "contract.yml"
DATA_DIR = Path(__file__).parents[2] / "data" 

RAW_FILE = DATA_DIR / "raw" /"raw_data.json"
STAGING_DIR = DATA_DIR / "staging"
SQL_DIR = Path(__file__).parents[2] / "sql"

TABLE_NAMES = ['company', 'previous_company_names', 'sic_code',
               'capital', 'filings',
               'officers',
               'psc_nature', 'psc']