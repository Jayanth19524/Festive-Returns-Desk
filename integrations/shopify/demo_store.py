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
# Product photos hotlinked (not downloaded) from the shops that host them; demo only. If a link is dead the shop shows a gradient tile.
IMAGES = {
    "CHO-515": "https://hatkebride.com/cdn/shop/files/11022_7__cropped.jpg?v=1754424952",
    "CHO-501": "https://manvansh.com/cdn/shop/files/manvanshtrendsnavratrilehengacholi_11_1800x1800.jpg?v=1752580440",
    "CHO-508": "https://wholetex.sgp1.cdn.digitaloceanspaces.com/full/navratri-cotton-traditional-mirror-work-kurta-kediya-5364.jpg",
    "KED-606": "https://www.suratsuit.in/product-img/Kediya-Vol-1-With-Magic-Slub-C-1723890244.jpeg",
    "KED-601": "https://wholetex.sgp1.cdn.digitaloceanspaces.com/full/navratri-cotton-traditional-mirror-work-kurta-kediya-5364.jpg",
    "JWL-040": "https://purnjewels.com/cdn/shop/files/1A3A786E-F7B3-4706-8204-8A4E0EF4071C.jpg?v=1757306053",
    "DUP-030": "https://khatrijamnadas.com/cdn/shop/files/3349-1_1080x.jpg?v=1765538411",
    "GWN-701": "https://medias.utsavfashion.com/media/catalog/product/cache/1/image/1000x/040ec09b1e35df139433887a97daa66f/e/m/embroidered-velvet-gown-in-maroon-v1-tve1594.jpg",
    "FUS-710": "https://aurayafashion.com/cdn/shop/files/1-262.jpg?v=1757081557",
    "SAR-720": "https://www.ethnicplus.in/cdn/shop/files/1010_1.jpg?v=1780773414",
    "COA-730": "https://laromaniofficial.com/cdn/shop/files/1107Cream-min.jpg?v=1756903931",
    "LEH-212": "https://img.perniaspopupshop.com/catalog/product/p/r/PREV042518_1.jpg?impolicy=zoomimage",
    "SHR-405": "https://i.etsystatic.com/41419909/r/il/184f74/6711086280/il_fullxfull.6711086280_dtp5.jpg",
    "SAR-318": "https://serasilkexports.com/assets/temple-green-gold.png",
    "LEH-204": "https://kundansbridalcouture.com/cdn/shop/files/Full-length_view_of_a_bride_wearing_a_maroon_bridal_lehenga.png?v=1779021354&width=1200",
    "SAR-310": "https://thesilkroot.com/cdn/shop/files/IMG-20251128-WA0269.jpg?v=1764318352",
    "KUR-110": "https://imagescdn.jaypore.com/img/app/product/3/39618810-12626703.jpg",
    "KUR-102": "https://elanstore.in/cdn/shop/files/Radianceemeraldgreenkurtaset-1_1200x1200.jpg?v=1767634859",
    "DUP-020": "https://assets.myntassets.com/h_200%2Cw_200%2Cc_fill%2Cg_auto/h_1440%2Cq_75%2Cw_1080/v1/assets/images/2025/SEPTEMBER/14/ww6XBIIK_cff826b3cbf7484887b5e0c4e5a67de9.jpg",
    "SHA-310": "https://in.kalkifashion.com/cdn/shop/files/baby-pink-zardosi-sharara-suit-with-dupatta-sg298279-1_9d9c4d5a-d2dd-4381-b7ab-6bf0d9602fbc_500x.jpg?v=1774344173",
    "ANA-301": "https://bindyaa.com/cdn/shop/files/5583_1500x1500_a45bbd58-7ad0-4df4-a1be-f96d24cab592.webp?v=1740266529&width=533",
    "ABA-220": "https://www.nazneen.in/image/cache/catalog/1199%20to%201265/NHF1212/MHF1212%20%281%29-1000x1000.JPG",
    "KUR-210": "https://cdn.shopify.com/s/files/1/0605/2770/6169/products/184A7391.jpg?v=1674888683",
    "SAR-501": "https://arrssilks.com/cdn/shop/files/Gemini_Generated_Image_nh4z0nnh4z0nnh4z.png?v=1780903499&width=1400",
    "SAR-507": "https://assets.ajio.com/medias/sys_master/root/20240731/QUxI/66a976586f60443f31daeae7/-473Wx593H-700246425-cream-MODEL.jpg",
    "PAV-520": "https://chuttipattu.com/cdn/shop/files/CPM_0370_01.jpg?v=1761146933&width=1946",
    "VES-510": "https://sethukrishna.com/cdn/shop/files/MenFullSleeveWhiteColourShirtandPocketDhotiwithAngavastramSet.jpg?v=1691491823&width=2400",
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
