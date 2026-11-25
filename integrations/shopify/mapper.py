"""Data mapping from Shopify REST/CSV models to Festive Returns Desk contract shapes.

Contract Shapes:
Product = {
  "sku": "LEH-204", "title": "Maroon Bridal Lehenga", "category": "lehenga",
  "price_inr": 6999, "season": "diwali" | null,
  "image_urls": ["https://..."],
  "sizes": ["S","M","L"],
  "measurements": { "waist_cm": 74, "length_cm": 102, "blouse_bust_cm": 88 },
  "description": "free text from the listing",
  "source": "shopify"
}

Order = {
  "id": "SHP-1042", "customer": {"id": "SHP-C-77", "name": "Simulated customer"},
  "item_sku": "LEH-204", "item": "Maroon Bridal Lehenga", "amount_inr": 6999,
  "delivered_at": "2026-11-20", "source": "shopify"
}
"""
import re
from typing import Any, Dict, List, Optional


def extract_season(tags_input: Any) -> Optional[str]:
    """Extract festival season from tags dynamically.
    
    Checks for patterns like 'season:diwali', 'season:eid', 'season:christmas', 'season:pongal'.
    Festival-agnostic: never hardcodes any specific festival name.
    """
    if not tags_input:
        return None
    
    tag_list: List[str] = []
    if isinstance(tags_input, str):
        tag_list = [t.strip() for t in tags_input.split(",") if t.strip()]
    elif isinstance(tags_input, list):
        tag_list = [str(t).strip() for t in tags_input if t]

    for tag in tag_list:
        clean = tag.strip().lower()
        if clean.startswith("season:"):
            return clean.split("season:", 1)[1].strip()
        if clean.startswith("festival:"):
            return clean.split("festival:", 1)[1].strip()

    return None


def infer_category(title: str, product_type: str = "") -> str:
    """Infer category (lehenga | saree | kurta | blouse | other)."""
    text = f"{title} {product_type}".lower()
    if "lehenga" in text or "chaniya" in text:
        return "lehenga"
    if "saree" in text or "sari" in text:
        return "saree"
    if "kurta" in text or "kurti" in text or "kediyu" in text:
        return "kurta"
    if "blouse" in text or "choli" in text:
        return "blouse"
    return "other"


def strip_html(html_str: str) -> str:
    """Strip basic HTML tags from descriptions."""
    if not html_str:
        return ""
    clean = re.sub(r"<[^>]+>", " ", html_str)
    return " ".join(clean.split()).strip()


_MEASURE = [  # (key, regex): "Waist: 74 cm", "Blouse bust 88 cm", "Length 5.5 m" ...
    ("blouse_bust_cm", r"blouse\s*(?:bust|chest)\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*cm"),
    ("waist_cm", r"waist\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*cm"),
    ("bust_cm", r"(?<!blouse )bust\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*cm"),
    ("chest_cm", r"(?<!blouse )chest\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*cm"),
    ("shoulder_cm", r"shoulder\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*cm"),
    ("length_cm", r"length\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*cm"),
    ("length_m", r"length\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*m(?:etres?|eters?)?\b"),
]


def parse_measurements(text: str) -> Dict[str, float]:
    """Pull garment measurements out of listing text. Heuristic: a Shopify product has no measurement field of its own,
    so sellers usually type them into the description. Anything not found is simply missing (and reported as such)."""
    found: Dict[str, float] = {}
    low = (text or "").lower()
    for key, rx in _MEASURE:
        m = re.search(rx, low)
        if m:
            found[key] = float(m.group(1)) if "." in m.group(1) else int(m.group(1))
    return found


def map_shopify_product(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Map a Shopify Admin REST product object into the contract Product shape."""
    variants = raw.get("variants") or []
    first_variant = variants[0] if variants else {}
    
    sku = first_variant.get("sku") or f"SKU-{raw.get('id', 'UNKNOWN')}"
    title = raw.get("title", "Untitled Product")
    category = infer_category(title, raw.get("product_type", ""))
    
    try:
        price_inr = round(float(first_variant.get("price", 0)))
    except (ValueError, TypeError):
        price_inr = 0

    season = extract_season(raw.get("tags"))
    images = raw.get("images") or []
    image_urls = [img.get("src") for img in images if isinstance(img, dict) and img.get("src")]

    # Extract sizes from options or variants
    sizes: List[str] = []
    options = raw.get("options") or []
    for opt in options:
        if opt.get("name", "").lower() in ("size", "sizes"):
            sizes.extend(opt.get("values", []))
    if not sizes and variants:
        # Fallback to variant titles/options if no Size option exists
        for v in variants:
            v_title = v.get("title", "")
            if v_title and v_title != "Default Title" and v_title not in sizes:
                sizes.append(v_title)

    description = strip_html(raw.get("body_html") or raw.get("description") or "")

    # Measurements: incomplete by default unless explicitly supplied in metafields/mock
    measurements = raw.get("measurements") or parse_measurements(description)

    return {
        "sku": sku,
        "title": title,
        "category": category,
        "price_inr": price_inr,
        "season": season,
        "image_urls": image_urls,
        "sizes": sizes,
        "measurements": measurements,
        "description": description,
        "source": "shopify"
    }


def map_shopify_order(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Map a Shopify Admin REST order object into the contract Order shape.
    
    Strictly avoids storing payment card or address data.
    """
    order_id_num = raw.get("order_number") or raw.get("id") or "0"
    shp_order_id = f"SHP-{order_id_num}"

    raw_cust = raw.get("customer") or {}
    cust_id_num = raw_cust.get("id") or raw.get("id") or "GUEST"
    first = raw_cust.get("first_name", "") or ""
    last = raw_cust.get("last_name", "") or ""
    full_name = f"{first} {last}".strip() or "Simulated customer"

    customer = {
        "id": f"SHP-C-{cust_id_num}",
        "name": full_name
    }

    line_items = raw.get("line_items") or []
    first_item = line_items[0] if line_items else {}
    item_sku = first_item.get("sku") or f"SKU-{first_item.get('product_id', 'UNKNOWN')}"
    item_title = first_item.get("title") or first_item.get("name") or "Simulated item"

    try:
        amount_inr = round(float(raw.get("total_price") or raw.get("current_total_price") or 0))
    except (ValueError, TypeError):
        amount_inr = 0

    # Determine delivered_at date (YYYY-MM-DD)
    fulfillments = raw.get("fulfillments") or []
    delivered_at = None
    if fulfillments:
        # Latest fulfillment updated_at or created_at
        del_timestamp = fulfillments[-1].get("updated_at") or fulfillments[-1].get("created_at")
        if del_timestamp:
            delivered_at = str(del_timestamp)[:10]

    if not delivered_at:
        created_at = raw.get("created_at")
        if created_at:
            delivered_at = str(created_at)[:10]

    return {
        "id": shp_order_id,
        "customer": customer,
        "item_sku": item_sku,
        "item": item_title,
        "amount_inr": amount_inr,
        "delivered_at": delivered_at,
        "source": "shopify"
    }


def map_csv_product(row: Dict[str, Any]) -> Dict[str, Any]:
    """Map a row from a products CSV into the contract Product shape."""
    sku = row.get("sku") or row.get("SKU") or f"SKU-{abs(hash(row.get('title', '')))}"
    title = row.get("title") or row.get("Title") or "Untitled Product"
    category = row.get("category") or infer_category(title, row.get("product_type", ""))
    
    try:
        price_inr = round(float(row.get("price_inr") or row.get("price") or row.get("Price") or 0))
    except (ValueError, TypeError):
        price_inr = 0

    raw_tags = row.get("tags") or row.get("Tags") or ""
    season = row.get("season") or extract_season(raw_tags)

    image_urls = []
    raw_images = row.get("image_urls") or row.get("images") or row.get("Image Src") or ""
    if raw_images:
        image_urls = [img.strip() for img in raw_images.split(";") if img.strip()]

    sizes = []
    raw_sizes = row.get("sizes") or row.get("Sizes") or ""
    if raw_sizes:
        sizes = [s.strip() for s in raw_sizes.split(",") if s.strip()]

    # Parse optional measurements JSON if supplied
    measurements = {}
    import json
    raw_meas = row.get("measurements", "")
    if raw_meas and isinstance(raw_meas, str) and raw_meas.startswith("{"):
        try:
            measurements = json.loads(raw_meas)
        except Exception:
            measurements = {}

    return {
        "sku": sku,
        "title": title,
        "category": category,
        "price_inr": price_inr,
        "season": season,
        "image_urls": image_urls,
        "sizes": sizes,
        "measurements": measurements,
        "description": row.get("description") or row.get("Description") or "",
        "source": "shopify"
    }


def map_csv_order(row: Dict[str, Any]) -> Dict[str, Any]:
    """Map a row from an orders CSV into the contract Order shape."""
    raw_id = str(row.get("id") or row.get("order_id") or row.get("Order ID") or "0")
    order_id = raw_id if raw_id.startswith("SHP-") else f"SHP-{raw_id}"

    raw_cid = str(row.get("customer_id") or row.get("Customer ID") or "1")
    cid = raw_cid if raw_cid.startswith("SHP-C-") else f"SHP-C-{raw_cid}"
    cname = row.get("customer_name") or row.get("Customer Name") or "Simulated customer"

    try:
        amount_inr = round(float(row.get("amount_inr") or row.get("total_price") or row.get("Total") or 0))
    except (ValueError, TypeError):
        amount_inr = 0

    delivered_at = row.get("delivered_at") or row.get("Delivered Date")

    return {
        "id": order_id,
        "customer": {"id": cid, "name": cname},
        "item_sku": row.get("item_sku") or row.get("SKU"),
        "item": row.get("item") or row.get("Item") or "Simulated item",
        "amount_inr": amount_inr,
        "delivered_at": str(delivered_at)[:10] if delivered_at else None,
        "source": "shopify"
    }
