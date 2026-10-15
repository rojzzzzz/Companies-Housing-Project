from src.config.read_contract import read_contract
from src.config import RAW_FILE, API_KEY
from pathlib import Path
import logging
import asyncio
import httpx
import json
import time

logger = logging.getLogger(__name__)

contract = read_contract()
url = contract.get("base_url")
companies = [company.get("code") for company in contract.get("companies")]
collection_endpoints = contract.get("collection_endpoints")

if not url or not companies or not collection_endpoints:
    logger.error("Missing required configuration in the contract.")
    raise ValueError("Missing required configuration in the contract.")

def save_data(data: dict, path: Path | str = RAW_FILE) -> None:
    """Saves the data to the specified RAW_PATH as a JSON file"""
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
            logger.info(f"Data saved successfully to {path}")
    except Exception as e:
        logger.error(f"Error saving data to {path}: {e}")
        raise

async def get_company_data(company_code: int) -> dict:  
    """Fetches all the data for a given company from the API and returns it as a dictionary."""

    company_data = {}
    base_url = f"{url}/{company_code}"
    logger.info(f"Starting to fetch data for company {company_code}...")

    async with httpx.AsyncClient(auth=(API_KEY, "")) as client:
        async def request_data(endpoint: str, params: dict | None = None) -> dict:
            try:
                if params is None:
                    response = await client.get(endpoint)
                else:
                    response = await client.get(endpoint, params=params)
                
                response.raise_for_status()
                logger.info(f"Successfully fetched data from {endpoint}")
                return response.json()

            except httpx.HTTPStatusError as e:
                status_code = e.response.status_code
                request_url = e.request.url

                if status_code == 404:
                    logger.warning(f"Data not found for {request_url}.")
                    raise
                elif status_code == 429:
                    logger.warning(f"Rate limit exceeded for {request_url}.")
                    raise
                elif 500 <= status_code < 600:
                    logger.error(f"Server error {status_code} for {request_url}.")
                    raise
                else:
                    logger.error(f"HTTP error {status_code} for {request_url}: {e.response.text}")
                    raise
            
            except httpx.RequestError as e:
                logger.error(f"Request error for {e.request.url}: {str(e)}")
                raise
        
        async def get_collection(endpoint: str) -> dict:
            """Fetches all items from a paginated collection endpoint and returns them as a list."""

            items = []
            start_index = 0
            while True:
                page = await request_data(endpoint, params={"start_index": start_index, 'items_per_page': 500})
                current_items = page.get("items")
                if not current_items:
                    break
                
                items.extend(current_items)
                start_index += len(current_items)

                total = page.get('total_results') or page.get('total_count')
                if total is not None and start_index >= total:
                    break
            
            return items
        
        company = await request_data(base_url)
        collection_tasks = {name: get_collection(f"{base_url}/{endpoint}") for name, endpoint in collection_endpoints.items()}

        results = await asyncio.gather(*collection_tasks.values())

        company_data = {
            "company": company,
            **dict(zip(collection_tasks.keys(), results))
        }

        logger.info(f"Successfully retrieved collections for {company_code}")
        return company_data
            

async def fetch_data() -> None:
    """Orchestrator function to fetch data from the API for all companies and endpoints."""

    start = time.perf_counter()
    logger.info("Starting to fetch data...")
    data = {company_code: await get_company_data(company_code) for company_code in companies}

    save_data(data)
    duration = time.perf_counter() - start
    logger.info("All data has been successfully fetched and saved to the raw file.")
    logger.info(f"Data fetching completed in {duration:.2f} seconds.")
    
