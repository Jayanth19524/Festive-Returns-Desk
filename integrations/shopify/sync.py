"""Shopify Data Synchronizer for Festive Returns Desk.

Fetches products and orders from Shopify (or offline CSV / mock data),
maps them to the contract shapes, and ingests them into Festive Returns Desk
via HTTP API or direct DB upsert.

Usage:
  # Ingest from mock demo datasets (Diwali & Eid) via running API
  python3 -m integrations.shopify.sync --source mock

  # Ingest from CSV files
  python3 -m integrations.shopify.sync --source csv --products-file sample_data/products_sample.csv --orders-file sample_data/orders_sample.csv

  # Ingest from live Shopify store
  python3 -m integrations.shopify.sync --source shopify

  # Direct DB mode (if server is not running)
  python3 -m integrations.shopify.sync --source mock --dest db
"""
import argparse
import csv
import json
import logging
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add repo root to sys.path so we can import internal modules when running standalone
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Optional dotenv loading
try:
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env")
except ImportError:
    pass

from integrations.shopify.client import ShopifyClient, ShopifyAPIError
from integrations.shopify.mapper import (
    map_csv_order,
    map_csv_product,
    map_shopify_order,
    map_shopify_product,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("shopify_sync")

SAMPLE_DATA_DIR = Path(__file__).resolve().parent / "sample_data"


def load_csv(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"JSON file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def post_to_ingest_api(endpoint: str, payload: Dict[str, Any], api_base: str, token: str) -> Dict[str, Any]:
    url = f"{api_base.rstrip('/')}/api/ingest/{endpoint.lstrip('/')}"
    data_bytes = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data_bytes,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Ingest API failed ({e.code}) at {url}: {err}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error connecting to Ingest API at {url}: {e.reason}") from e


def direct_db_upsert(products: List[Dict[str, Any]], orders: List[Dict[str, Any]]) -> Dict[str, int]:
    """Fallback direct database upsert using backend/app/db.py."""
    from backend.app import db
    db.init()
    with db.conn() as c:
        p_count = db.upsert_products(c, products) if products else 0
        o_count = db.upsert_orders(c, orders) if orders else 0
    return {"products": p_count, "orders": o_count}


def run_sync(
    source: str = "mock",
    dest: str = "api",
    api_url: Optional[str] = None,
    token: Optional[str] = None,
    products_file: Optional[str] = None,
    orders_file: Optional[str] = None,
    limit: int = 50
) -> Dict[str, Any]:
    """Execute sync pipeline from chosen source to chosen destination."""
    logger.info("Starting Shopify sync [source=%s, dest=%s]", source, dest)

    products: List[Dict[str, Any]] = []
    orders: List[Dict[str, Any]] = []

    if source == "shopify":
        client = ShopifyClient()
        logger.info("Fetching products from Shopify store %s...", client.shop_domain)
        raw_products = client.get_products(limit=limit)
        products = [map_shopify_product(p) for p in raw_products]
        logger.info("Mapped %d products from Shopify", len(products))

        logger.info("Fetching orders from Shopify store %s...", client.shop_domain)
        raw_orders = client.get_orders(limit=limit)
        orders = [map_shopify_order(o) for o in raw_orders]
        logger.info("Mapped %d orders from Shopify", len(orders))

    elif source == "csv":
        p_path = Path(products_file) if products_file else SAMPLE_DATA_DIR / "products_sample.csv"
        o_path = Path(orders_file) if orders_file else SAMPLE_DATA_DIR / "orders_sample.csv"

        logger.info("Loading products from CSV: %s", p_path)
        raw_products = load_csv(p_path)
        products = [map_csv_product(p) for p in raw_products]

        logger.info("Loading orders from CSV: %s", o_path)
        raw_orders = load_csv(o_path)
        orders = [map_csv_order(o) for o in raw_orders]

    elif source == "mock":
        p_path = Path(products_file) if products_file else SAMPLE_DATA_DIR / "shopify_products_mock.json"
        o_path = Path(orders_file) if orders_file else SAMPLE_DATA_DIR / "shopify_orders_mock.json"

        logger.info("Loading simulated Shopify products: %s", p_path)
        raw_p_data = load_json(p_path)
        raw_products = raw_p_data.get("products", []) if isinstance(raw_p_data, dict) else raw_p_data
        products = [map_shopify_product(p) for p in raw_products]

        logger.info("Loading simulated Shopify orders: %s", o_path)
        raw_o_data = load_json(o_path)
        raw_orders = raw_o_data.get("orders", []) if isinstance(raw_o_data, dict) else raw_o_data
        orders = [map_shopify_order(o) for o in raw_orders]
    else:
        raise ValueError(f"Unknown source: {source}")

    logger.info("Extracted %d products and %d orders", len(products), len(orders))

    # Destinations
    if dest == "api":
        base = api_url or f"http://localhost:{os.getenv('APP_PORT', '8200')}"
        auth_token = token or os.getenv("INGEST_API_TOKEN", "dev-ingest-token-12345")

        logger.info("Ingesting products via API %s...", base)
        res_p = post_to_ingest_api("products", {"products": products}, base, auth_token)
        logger.info("Ingested products response: %s", res_p)

        logger.info("Ingesting orders via API %s...", base)
        res_o = post_to_ingest_api("orders", {"orders": orders}, base, auth_token)
        logger.info("Ingested orders response: %s", res_o)
        return {"products_upserted": len(products), "orders_upserted": len(orders), "dest": "api"}

    elif dest == "db":
        logger.info("Upserting directly into SQLite database...")
        res = direct_db_upsert(products, orders)
        logger.info("Direct DB upsert result: %s", res)
        return {"products_upserted": res["products"], "orders_upserted": res["orders"], "dest": "db"}
    else:
        raise ValueError(f"Unknown destination: {dest}")


def main():
    parser = argparse.ArgumentParser(description="Sync Shopify products and orders into Festive Returns Desk.")
    parser.add_argument("--source", choices=["shopify", "csv", "mock"], default="mock",
                        help="Data source: shopify (live API), csv (local files), or mock (sample JSON)")
    parser.add_argument("--dest", choices=["api", "db"], default="api",
                        help="Destination: api (HTTP ingest routes) or db (direct SQLite)")
    parser.add_argument("--api-url", default=None, help="Base URL for Festive Returns Desk API (default http://localhost:8200)")
    parser.add_argument("--token", default=None, help="Bearer token for Ingest API (defaults to INGEST_API_TOKEN env var)")
    parser.add_argument("--products-file", default=None, help="Path to products CSV or JSON")
    parser.add_argument("--orders-file", default=None, help="Path to orders CSV or JSON")
    parser.add_argument("--limit", type=int, default=50, help="Max items to fetch from Shopify API")

    args = parser.parse_args()

    try:
        result = run_sync(
            source=args.source,
            dest=args.dest,
            api_url=args.api_url,
            token=args.token,
            products_file=args.products_file,
            orders_file=args.orders_file,
            limit=args.limit
        )
        print(f"\n[SUCCESS] Sync completed successfully: {result['products_upserted']} products, {result['orders_upserted']} orders.")
    except Exception as e:
        logger.error("Sync failed: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
