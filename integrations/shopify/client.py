"""Shopify Admin REST API client using Python standard library.

Official documentation:
- REST Admin API: https://shopify.dev/docs/api/admin-rest/2024-01
- Products endpoint: https://shopify.dev/docs/api/admin-rest/2024-01/resources/product#get-products
- Orders endpoint: https://shopify.dev/docs/api/admin-rest/2024-01/resources/order#get-orders
- Order update (tags/notes): https://shopify.dev/docs/api/admin-rest/2024-01/resources/order#put-orders-order-id
"""
import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

API_VERSION = "2024-01"


class ShopifyAPIError(Exception):
    """Exception raised for Shopify API call failures."""
    def __init__(self, status_code: int, message: str, response_body: str = ""):
        self.status_code = status_code
        self.message = message
        self.response_body = response_body
        super().__init__(f"Shopify API Error ({status_code}): {message}")


class ShopifyClient:
    """Client for Shopify Admin REST API.
    
    Uses standard library urllib.request to avoid external HTTP dependencies.
    """

    def __init__(self, shop_domain: Optional[str] = None, access_token: Optional[str] = None):
        domain = shop_domain or os.getenv("SHOPIFY_SHOP_DOMAIN", "")
        # Normalize domain to hostname only (strip https:// and trailing slashes)
        domain = domain.replace("https://", "").replace("http://", "").strip("/")
        if domain and not domain.endswith(".myshopify.com"):
            domain = f"{domain}.myshopify.com"
        self.shop_domain = domain
        self.access_token = access_token or os.getenv("SHOPIFY_ACCESS_TOKEN", "")

    @property
    def base_url(self) -> str:
        if not self.shop_domain:
            raise ValueError("SHOPIFY_SHOP_DOMAIN is not set or provided.")
        return f"https://{self.shop_domain}/admin/api/{API_VERSION}"

    def _request(self, endpoint: str, method: str = "GET", data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not self.access_token:
            raise ValueError("SHOPIFY_ACCESS_TOKEN is not set or provided.")

        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        headers = {
            "X-Shopify-Access-Token": self.access_token,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "FestiveReturnsDesk-ShopifyConnector/1.0"
        }

        body_bytes = None
        if data is not None:
            body_bytes = json.dumps(data).encode("utf-8")

        req = urllib.request.Request(url, data=body_bytes, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                call_limit = resp.headers.get("X-Shopify-Shop-Api-Call-Limit", "")
                if call_limit:
                    logger.debug("Shopify API Call Limit: %s", call_limit)
                resp_bytes = resp.read()
                return json.loads(resp_bytes.decode("utf-8")) if resp_bytes else {}
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            raise ShopifyAPIError(e.code, f"HTTP {e.code} on {method} {url}: {e.reason}", response_body=err_body) from e
        except urllib.error.URLError as e:
            raise ShopifyAPIError(0, f"Network error connecting to Shopify ({url}): {e.reason}") from e

    def get_products(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch products from Shopify Admin REST API.
        
        Requires `read_products` scope.
        Doc: https://shopify.dev/docs/api/admin-rest/2024-01/resources/product#get-products
        """
        res = self._request(f"products.json?limit={limit}")
        return res.get("products", [])

    def get_orders(self, status: str = "any", limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch orders from Shopify Admin REST API.
        
        Requires `read_orders` scope.
        Doc: https://shopify.dev/docs/api/admin-rest/2024-01/resources/order#get-orders
        """
        res = self._request(f"orders.json?status={status}&limit={limit}")
        return res.get("orders", [])

    def tag_order(self, order_id: str | int, new_tags: List[str], note_append: Optional[str] = None) -> Dict[str, Any]:
        """Optionally write return reason/status back to a Shopify Order.
        
        Requires `write_orders` scope.
        Doc: https://shopify.dev/docs/api/admin-rest/2024-01/resources/order#put-orders-order-id
        """
        # First retrieve existing tags so we don't overwrite them
        order_data = self._request(f"orders/{order_id}.json").get("order", {})
        existing_tags_str = order_data.get("tags", "")
        existing_tags = [t.strip() for t in existing_tags_str.split(",") if t.strip()]

        combined_tags = list(dict.fromkeys(existing_tags + new_tags))
        payload: Dict[str, Any] = {"order": {"id": order_id, "tags": ", ".join(combined_tags)}}

        if note_append:
            existing_note = order_data.get("note", "") or ""
            updated_note = f"{existing_note}\n{note_append}".strip() if existing_note else note_append
            payload["order"]["note"] = updated_note

        return self._request(f"orders/{order_id}.json", method="PUT", data=payload)
