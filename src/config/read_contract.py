from . import CONTRACT_PATH
from pathlib import Path
import logging
import yaml

logger = logging.getLogger(__name__)

def read_contract(contract_path: Path | str = CONTRACT_PATH) -> dict:
    try:
        with open(contract_path, 'r', encoding='utf-8') as f:
            contract = yaml.safe_load(f)
            logger.info(f"Data Contract loaded successfully")
            return contract['contract']

    except FileNotFoundError:
        logger.error(f"Data Contract file not found: {contract_path}")
        raise
    except yaml.YAMLError as e:
        logger.error(f"Error parsing Data Contract YAML: {e}")
        raise