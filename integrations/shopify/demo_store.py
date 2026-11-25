"""A SIMULATED Shopify store with a story, in the same raw shape Shopify's Admin API returns, so it goes through the real mapper.

Everything here is fake: 27 listings across five festivals (Diwali, Navratri, Eid, Pongal, Christmas), 150 orders, a returns history,
and a few repeat returners. The story baked in (and labelled as simulated everywhere it is shown): listings WITHOUT measurements get
returned for size far more often than listings with them. Deterministic: the same data every run.
"""
import random
from datetime import datetime, timedelta, timezone

# sku, title, product_type, season, price, sizes, measurement sentence (None = the seller never wrote measurements)
PRODUCTS = [
    ("LEH-204", "Maroon Zari Bridal Lehenga", "Lehenga", "diwali", 6999, ["S", "M", "L"], None),
    ("LEH-212", "Emerald Velvet Wedding Lehenga", "Lehenga", "diwali", 9499, ["S", "M", "L", "XL"], "Waist 72 cm, length 104 cm, blouse bust 88 cm."),
    ("SAR-310", "Banarasi Silk Saree Red Butta", "Saree", "diwali", 4999, ["Free Size"], "Length 5.5 m."),
    ("SAR-318", "Kanjivaram Temple Border Saree", "Saree", "diwali", 7499, ["Free Size"], None),
    ("KUR-102", "Royal Emerald Silk Kurta Set", "Kurta Set", "diwali", 1899, ["M", "L", "XL"], "Chest 104 cm, length 110 cm."),
    ("KUR-110", "Mustard Chanderi Kurta Set", "Kurta Set", "diwali", 2499, ["S", "M", "L", "XL"], None),
    ("SHR-405", "Midnight Navy Sherwani", "Sherwani", "diwali", 8999, ["38", "40", "42", "44"], "Chest 102 cm, shoulder 46 cm."),
    ("DUP-020", "Zari Net Dupatta", "Dupatta", "diwali", 799, ["Free Size"], None),
    ("CHO-501", "Mirror-work Chaniya Choli", "Chaniya Choli", "navratri", 3200, ["S", "M", "L"], None),
    ("CHO-508", "Bandhani Chaniya Choli", "Chaniya Choli", "navratri", 2800, ["S", "M", "L", "XL"], "Waist 70 cm, blouse bust 86 cm, length 98 cm."),
    ("CHO-515", "Embroidered Navratri Lehenga Choli", "Chaniya Choli", "navratri", 4200, ["S", "M", "L"], None),
    ("KED-601", "Gamthi Kediyu Set", "Kediyu", "navratri", 1200, ["M", "L", "XL"], "Chest 102 cm, length 84 cm."),
    ("KED-606", "Block Print Kediyu", "Kediyu", "navratri", 1450, ["M", "L", "XL"], None),
    ("DUP-030", "Bandhani Dupatta", "Dupatta", "navratri", 650, ["Free Size"], "Length 220 cm."),
    ("JWL-040", "Oxidised Garba Jewellery Set", "Accessories", "navratri", 900, ["Free Size"], None),
    ("ANA-301", "Ivory Chikankari Anarkali Gown", "Anarkali", "eid", 4499, ["S", "M", "L", "XL"], "Bust 96 cm, length 130 cm."),
    ("SHA-310", "Pastel Gharara Set", "Sharara", "eid", 5200, ["S", "M", "L"], None),
    ("KUR-210", "White Lucknowi Kurta Pyjama", "Kurta Set", "eid", 1899, ["M", "L", "XL"], "Chest 104 cm."),
    ("ABA-220", "Embroidered Festive Abaya", "Abaya", "eid", 3600, ["52", "54", "56"], None),
    ("SAR-501", "Kanjivaram Crimson Temple Silk Saree", "Saree", "pongal", 5200, ["Free Size"], None),
    ("SAR-507", "Kerala Kasavu Saree", "Saree", "pongal", 2900, ["Free Size"], "Length 5.5 m."),
    ("VES-510", "Cotton Veshti Set", "Kurta Set", "pongal", 1500, ["M", "L", "XL"], "Waist 96 cm."),
    ("PAV-520", "Pattu Pavadai Girls Set", "Lehenga", "pongal", 2200, ["4-5Y", "6-7Y", "8-9Y"], None),
    ("GWN-701", "Velvet Festive Gown", "Gown", "christmas", 3900, ["S", "M", "L"], "Bust 92 cm, waist 74 cm, length 125 cm."),
    ("FUS-710", "Fusion Cape Kurta Set", "Kurta Set", "christmas", 2600, ["S", "M", "L"], None),
    ("SAR-720", "Red Georgette Party Saree", "Saree", "christmas", 2400, ["Free Size"], None),
    ("COA-730", "Embroidered Nehru Jacket Set", "Kurta Set", "christmas", 1800, ["M", "L", "XL"], "Chest 104 cm."),
]
FIRST = ["Aarav", "Meera", "Kavya", "Rohan", "Anita", "Divya", "Imran", "Hetal", "Suresh", "Priya", "Neha", "Vikram", "Sana", "Farah", "Lakshmi",
         "Arjun", "Isha", "Karthik", "Zoya", "Pooja", "Nikhil", "Deepa", "Rahul", "Ananya", "Mohan", "Tara", "Yash", "Riya", "Kabir", "Sneha"]
LAST = ["Patel", "Shah", "Rao", "Desai", "Khan", "Mehta", "Iyer", "Nair", "Reddy", "Joshi", "Sharma", "Gupta", "Kulkarni", "Naidu", "Pillai"]
# Product photos hotlinked (not downloaded) from the shops that host them; demo only. SKUs not listed keep a gradient tile.
IMAGES = {
    "KUR-102": "https://elanstore.in/cdn/shop/files/Radianceemeraldgreenkurtaset-1_1200x1200.jpg?v=1767634859",
    "DUP-020": "https://assets.myntassets.com/h_200%2Cw_200%2Cc_fill%2Cg_auto/h_1440%2Cq_75%2Cw_1080/v1/assets/images/2025/SEPTEMBER/14/ww6XBIIK_cff826b3cbf7484887b5e0c4e5a67de9.jpg",
    "SHR-405": "https://i.etsystatic.com/41419909/r/il/184f74/6711086280/il_fullxfull.6711086280_dtp5.jpg",
    "SHA-310": "https://cdn.shopify.com/s/files/1/1105/1322/products/LightPinkDesignerEmbroideredPartyWearGhararaSuit_1_-Saira_sBoutique.jpg?v=1631336756",
    "ANA-301": "https://bindyaa.com/cdn/shop/files/5583_1500x1500_a45bbd58-7ad0-4df4-a1be-f96d24cab592.webp?v=1740266529&width=533",
    "ABA-220": "https://www.arabicattire.com/cdn/shop/products/NHF590_1_1200x1200.jpg?v=1643987393",
    "KUR-210": "https://cdn.shopify.com/s/files/1/0605/2770/6169/products/184A7391.jpg?v=1674888683",
    "SAR-501": "https://arrssilks.com/cdn/shop/files/Gemini_Generated_Image_nh4z0nnh4z0nnh4z.png?v=1780903499&width=1400",
    "SAR-507": "https://keraloom.in/cdn/shop/products/KPLYHLKS3A.jpg?v=1701769426&width=1445",
    "PAV-520": "https://princenprincess.in/cdn/shop/products/kids-red-big-border-traditional-pattu-pavadai-ppp1104prince-n-princess-3326460.jpg?v=1769596510&width=1600",
    "VES-510": "https://ramrajcotton.in/cdn/shop/files/5_017416a3-ef2d-4a0f-8946-d08c3bc0a874_1.jpg?v=1731919538",
}
NO_MEAS = {p[0] for p in PRODUCTS if p[6] is None}
REPEAT_CUSTOMERS = 3  # customers who already returned 3 times this month (for the repeat-returner demo)


def _iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def build(now=None, seed=11):
    """Returns (raw_products, raw_orders, history, repeat_customer_ids). Raw shapes match Shopify's Admin REST responses."""
    now = now or datetime.now(timezone.utc)
    r = random.Random(seed)
    raw_products = []
    for i, (sku, title, ptype, season, price, sizes, meas) in enumerate(PRODUCTS):
        body = f"<p>{title} for the {season.title()} season. Handcrafted festive wear. {meas or ''}</p>"
        raw_products.append({
            "id": 9000 + i, "title": title, "product_type": ptype, "body_html": body,
            "tags": f"festive, ethnic, season:{season}", "images": [{"id": 800 + i, "src": IMAGES[sku]}] if sku in IMAGES else [],
            "options": [{"name": "Size", "values": sizes}],
            "variants": [{"id": 700 + i, "sku": sku, "title": sizes[0], "price": f"{price}.00", "option1": sizes[0]}],
        })
    customers = [(100 + i, r.choice(FIRST), r.choice(LAST)) for i in range(70)]
    raw_orders, history, number = [], [], 2001   # SHP-2001.. (the small mock sample uses SHP-1041..1045)
    fresh_quota = 34
    for n in range(150):
        sku, title, _t, season, price, _s, meas = PRODUCTS[r.choices(range(len(PRODUCTS)), weights=[3 if p[3] in ("diwali", "navratri") else 2 for p in PRODUCTS])[0]]
        cid, first, last = customers[n % len(customers)]
        fresh = n < fresh_quota                       # recent orders: nothing returned yet, ready for the live demo
        days = r.randint(2, 9) if fresh else r.randint(16, 70)
        delivered = now - timedelta(days=days)
        raw_orders.append({
            "id": 5000 + number, "order_number": number, "total_price": f"{price}.00", "created_at": _iso(delivered - timedelta(days=3)),
            "customer": {"id": cid, "first_name": first, "last_name": last},
            "line_items": [{"id": 6000 + number, "product_id": 9000, "sku": sku, "title": title, "price": f"{price}.00", "quantity": 1}],
            "fulfillments": [{"id": 7000 + number, "status": "success", "created_at": _iso(delivered), "updated_at": _iso(delivered)}],
        })
        if not fresh and r.random() < (0.48 if sku in NO_MEAS else 0.13):   # the story: missing measurements -> more returns
            w = [("wrong_size", 58), ("not_as_described", 14), ("damaged", 10), ("changed_mind", 12), ("worn_once", 6)] if sku in NO_MEAS else \
                [("wrong_size", 22), ("not_as_described", 20), ("damaged", 14), ("changed_mind", 28), ("worn_once", 16)]
            reason = r.choices([x[0] for x in w], weights=[x[1] for x in w])[0]
            if reason == "wrong_size" and _s == ["Free Size"]:   # a free-size item cannot be the wrong size
                reason = "not_as_described"
            filed_days_ago = max(1, days - r.randint(1, 12))
            history.append({"order_id": f"SHP-{number}", "customer_id": f"SHP-C-{cid}", "reason": reason,
                            "condition": {"worn_once": "worn", "damaged": "damaged"}.get(reason, "unworn"), "days_ago": filed_days_ago})
        number += 1
    repeat = [f"SHP-C-{c[0]}" for c in customers[:REPEAT_CUSTOMERS]]
    return raw_products, raw_orders, history, repeat
