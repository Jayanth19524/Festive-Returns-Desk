"""SQLite storage + SIMULATED seed data (fake customers, orders; no real people or payments)."""
import json, os, sqlite3
from datetime import datetime, timedelta, timezone
from .config import ROOT

DB_PATH = ROOT / os.getenv("DB_PATH", "garba.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (id TEXT PRIMARY KEY, name TEXT);
CREATE TABLE IF NOT EXISTS orders (
  id TEXT PRIMARY KEY, customer_id TEXT, item TEXT, amount_inr REAL, delivered_days_ago INTEGER,
  item_sku TEXT, delivered_at TEXT, source TEXT
);
CREATE TABLE IF NOT EXISTS products (
  sku TEXT PRIMARY KEY, title TEXT, category TEXT, price_inr REAL, season TEXT,
  image_urls TEXT, sizes TEXT, measurements TEXT, description TEXT, source TEXT
);
CREATE TABLE IF NOT EXISTS cases (
  id INTEGER PRIMARY KEY AUTOINCREMENT, order_id TEXT, customer_id TEXT, created_at TEXT,
  transcript TEXT, language TEXT, reason_category TEXT, claimed_condition TEXT,
  decision TEXT, score REAL, reasons TEXT, flags_in_effect TEXT, signed_approval_required INTEGER,
  status TEXT, trace TEXT);          -- awaiting_workflow | approved_refunded | held | rejected | refund_blocked | seed_history
CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, case_id INTEGER, at TEXT, step TEXT, detail TEXT);
CREATE TABLE IF NOT EXISTS owner_credentials (credential_id TEXT PRIMARY KEY, public_key TEXT, sign_count INTEGER);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS refunds (id INTEGER PRIMARY KEY AUTOINCREMENT, case_id INTEGER UNIQUE, amount_inr REAL, issued_at TEXT, issued_by TEXT);
"""

CUSTOMERS = [("C1", "Meera Shah"), ("C2", "Kavya Rao"), ("C3", "Anita Patel"), ("C4", "Rohan Desai"),
             ("C5", "Divya N"), ("C6", "Imran Khan"), ("C7", "Hetal Mehta"), ("C8", "Suresh K")]
# id, customer, item, amount, delivered N days ago
ORDERS = [("GRD-1001", "C1", "Chaniya choli", 1800, 6), ("GRD-1002", "C2", "Lehenga", 5500, 5),
          ("GRD-1003", "C3", "Silk saree", 2400, 4), ("GRD-1004", "C4", "Bridal lehenga", 14500, 7),
          ("GRD-1005", "C5", "Kediyu", 1200, 3), ("GRD-1006", "C6", "Dupatta set", 600, 40),
          ("GRD-1007", "C7", "Chaniya choli", 3200, 5), ("GRD-1008", "C8", "Kurta set", 900, 2)]
# A bigger SIMULATED catalogue for surge tests: GRD-2001..2060, fixed seed so every run is the same.
import random as _random
_r = _random.Random(7)
_ITEMS = [("Chaniya choli", 1400, 3800), ("Lehenga", 3500, 9500), ("Silk saree", 1800, 6500), ("Kediyu", 900, 2200),
          ("Dupatta set", 500, 1200), ("Kurta set", 700, 2000), ("Bridal lehenga", 9000, 18000)]
for _i in range(60):
    _name, _lo, _hi = _r.choice(_ITEMS)
    CUSTOMERS.append((f"S{_i}", f"Simulated customer {_i + 1}"))
    ORDERS.append((f"GRD-{2001 + _i}", f"S{_i}", _name, round(_r.randint(_lo, _hi), -1), _r.choice([2, 3, 4, 5, 6, 8, 10, 12, 14, 20])))
# a few of them are repeat returners
HISTORY_EXTRA = {"S3": [15, 6], "S11": [22, 10, 2], "S27": [18, 7]}
# earlier returns (simulated history): customer -> days ago each was filed
HISTORY = {"C5": [20, 9], "C7": [25, 12, 4]}
HISTORY.update(HISTORY_EXTRA)


def now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init():
    with conn() as c:
        c.executescript(SCHEMA)
        # Ensure optional new columns exist if table was already created
        existing_cols = {r[1] for r in c.execute("PRAGMA table_info(orders)").fetchall()}
        for col, col_type in [("item_sku", "TEXT"), ("delivered_at", "TEXT"), ("source", "TEXT")]:
            if col not in existing_cols:
                c.execute(f"ALTER TABLE orders ADD COLUMN {col} {col_type}")

        for col in ("trace TEXT", "photo_path TEXT", "photo_check TEXT"):   # older databases were created before these columns existed
            try:
                c.execute(f"ALTER TABLE cases ADD COLUMN {col}")
            except Exception:
                pass
        if c.execute("SELECT COUNT(*) FROM customers").fetchone()[0]:
            return
        c.executemany("INSERT INTO customers VALUES (?,?)", CUSTOMERS)
        c.executemany("INSERT INTO orders (id, customer_id, item, amount_inr, delivered_days_ago) VALUES (?,?,?,?,?)", ORDERS)
        for cust, days in HISTORY.items():
            for d in days:
                at = (datetime.now(timezone.utc) - timedelta(days=d)).isoformat(timespec="seconds")
                c.execute("INSERT INTO cases (order_id,customer_id,created_at,decision,status,reasons,flags_in_effect) "
                          "VALUES (?,?,?,?,?,?,?)", (f"OLD-{cust}-{d}", cust, at, "approve", "seed_history", "[]", "{}"))


def upsert_products(c, products: list[dict]) -> int:
    """Upsert products by SKU. Idempotent."""
    count = 0
    for p in products:
        c.execute("""
            INSERT INTO products (sku, title, category, price_inr, season, image_urls, sizes, measurements, description, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(sku) DO UPDATE SET
                title=excluded.title,
                category=excluded.category,
                price_inr=excluded.price_inr,
                season=excluded.season,
                image_urls=excluded.image_urls,
                sizes=excluded.sizes,
                measurements=excluded.measurements,
                description=excluded.description,
                source=excluded.source
        """, (
            p["sku"],
            p.get("title", ""),
            p.get("category", "other"),
            float(p.get("price_inr", 0)),
            p.get("season"),
            json.dumps(p.get("image_urls") or []),
            json.dumps(p.get("sizes") or []),
            json.dumps(p.get("measurements") or {}),
            p.get("description", ""),
            p.get("source", "shopify")
        ))
        count += 1
    return count


def upsert_orders(c, orders: list[dict]) -> int:
    """Upsert orders by ID, also upserting customer info. Idempotent."""
    count = 0
    today = datetime.now(timezone.utc).date()
    for o in orders:
        cust = o.get("customer") or {}
        cid = cust.get("id") or f"CUST-{o['id']}"
        cname = cust.get("name", "Simulated customer")
        c.execute("INSERT INTO customers (id, name) VALUES (?, ?) ON CONFLICT(id) DO UPDATE SET name=excluded.name",
                  (cid, cname))

        delivered_at = o.get("delivered_at")
        delivered_days_ago = o.get("delivered_days_ago")
        if delivered_days_ago is None:
            if delivered_at:
                try:
                    del_date = datetime.fromisoformat(delivered_at).date()
                    delivered_days_ago = max(0, (today - del_date).days)
                except Exception:
                    delivered_days_ago = 0
            else:
                delivered_days_ago = 0

        c.execute("""
            INSERT INTO orders (id, customer_id, item, amount_inr, delivered_days_ago, item_sku, delivered_at, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                customer_id=excluded.customer_id,
                item=excluded.item,
                amount_inr=excluded.amount_inr,
                delivered_days_ago=excluded.delivered_days_ago,
                item_sku=excluded.item_sku,
                delivered_at=excluded.delivered_at,
                source=excluded.source
        """, (
            o["id"],
            cid,
            o.get("item", ""),
            float(o.get("amount_inr", 0)),
            int(delivered_days_ago),
            o.get("item_sku"),
            delivered_at,
            o.get("source", "shopify")
        ))
        count += 1
    return count


def set_meta(key: str, value: str) -> None:
    with conn() as c:
        c.execute("INSERT INTO meta (key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))


def get_meta(key: str, default: str = "") -> str:
    with conn() as c:
        r = c.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return r[0] if r else default


def load_demo_store() -> dict:
    """Load the SIMULATED Shopify demo store (listings, orders, a returns history, repeat returners). Idempotent."""
    from integrations.shopify import demo_store
    from integrations.shopify.mapper import map_shopify_order, map_shopify_product
    raw_p, raw_o, history, repeat = demo_store.build()
    init()
    with conn() as c:
        np_ = upsert_products(c, [map_shopify_product(p) for p in raw_p])
        no_ = upsert_orders(c, [map_shopify_order(o) for o in raw_o])
        added = 0
        for h in history:   # past returns: they feed Return Intelligence but are not in the owner's queue (status 'history')
            if c.execute("SELECT 1 FROM cases WHERE order_id=?", (h["order_id"],)).fetchone():
                continue
            at = (datetime.now(timezone.utc) - timedelta(days=h["days_ago"])).isoformat(timespec="seconds")
            c.execute("INSERT INTO cases (order_id,customer_id,created_at,transcript,language,reason_category,claimed_condition,decision,score,reasons,"
                      "flags_in_effect,signed_approval_required,status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                      (h["order_id"], h["customer_id"], at, "(imported return history)", "en-IN", h["reason"], h["condition"],
                       "reject" if h["reason"] == "worn_once" else "approve", 0, "[]", "{}", 0, "history"))
            added += 1
        for cust in repeat:  # three earlier returns this month -> the 'repeat returner' scenario
            for d in (3, 9, 17):
                oid = f"OLD-{cust}-{d}"
                if not c.execute("SELECT 1 FROM cases WHERE order_id=?", (oid,)).fetchone():
                    at = (datetime.now(timezone.utc) - timedelta(days=d)).isoformat(timespec="seconds")
                    c.execute("INSERT INTO cases (order_id,customer_id,created_at,decision,status,reasons,flags_in_effect) VALUES (?,?,?,?,?,?,?)",
                              (oid, cust, at, "approve", "seed_history", "[]", "{}"))
    set_meta("data_source", "demo")
    return {"products": np_, "orders": no_, "history_returns_added": added}


def reset():
    DB_PATH.unlink(missing_ok=True)
    init()
    if os.getenv("DEMO_STORE", "1") == "1":   # start every demo from the simulated Shopify store
        load_demo_store()


def returns_30d(c, customer_id) -> int:
    since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat(timespec="seconds")
    return c.execute("SELECT COUNT(*) FROM cases WHERE customer_id=? AND created_at>=?", (customer_id, since)).fetchone()[0]


def log_event(c, case_id, step, detail=""):
    c.execute("INSERT INTO events (case_id,at,step,detail) VALUES (?,?,?,?)", (case_id, now(), step, detail))


def row(r):
    d = dict(r)
    for k in ("reasons", "flags_in_effect", "trace", "photo_check"):
        if k in d and isinstance(d[k], str):
            d[k] = json.loads(d[k] or "null")
    return d
