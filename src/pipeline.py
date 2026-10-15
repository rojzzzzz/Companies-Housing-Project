import asyncio
from pathlib import Path


def extract():
    from src.config import RAW_FILE
    from src.extract.extract import fetch_data

    Path(RAW_FILE).parent.mkdir(parents=True, exist_ok=True)
    asyncio.run(fetch_data())


def normalize():
    from src.config.read_contract import read_contract
    from src.transform.normalize import main

    main(read_contract()["silver_schema"])


def validate():
    from src.config.read_contract import read_contract
    from src.transform.validate import validate as check_dataset

    result = check_dataset(read_contract())
    if result.health not in {"HEALTHY", "WARNING"}:
        raise RuntimeError(f"Loading blocked by data quality: {result.health}")


def load():
    from src.load.load import loader
    loader()


def main():
    extract()
    normalize()
    validate()
    load()


if __name__ == "__main__":
    main()
