"""SQLite storage + SIMULATED seed data (fake customers, orders; no real people or payments)."""
import json, os, sqlite3
from datetime import datetime, timedelta, timezone
from .config import ROOT

DB_PATH = ROOT / os.getenv("DB_PATH", "garba.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (id TEXT PRIMARY KEY, name TEXT);
CREATE TABLE IF NOT EXISTS orders (id TEXT PRIMARY KEY, customer_id TEXT, item TEXT, amount_inr REAL, delivered_days_ago INTEGER);
CREATE TABLE IF NOT EXISTS cases (
  id INTEGER PRIMARY KEY AUTOINCREMENT, order_id TEXT, customer_id TEXT, created_at TEXT,
  transcript TEXT, language TEXT, reason_category TEXT, claimed_condition TEXT,
  decision TEXT, score REAL, reasons TEXT, flags_in_effect TEXT, signed_approval_required INTEGER,
  status TEXT);          -- awaiting_workflow | approved_refunded | held | rejected | refund_blocked | seed_history
CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, case_id INTEGER, at TEXT, step TEXT, detail TEXT);
CREATE TABLE IF NOT EXISTS owner_credentials (credential_id TEXT PRIMARY KEY, public_key TEXT, sign_count INTEGER);
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
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init():
    with conn() as c:
        c.executescript(SCHEMA)
        if c.execute("SELECT COUNT(*) FROM customers").fetchone()[0]:
            return
        c.executemany("INSERT INTO customers VALUES (?,?)", CUSTOMERS)
        c.executemany("INSERT INTO orders VALUES (?,?,?,?,?)", ORDERS)
        for cust, days in HISTORY.items():
            for d in days:
                at = (datetime.now(timezone.utc) - timedelta(days=d)).isoformat(timespec="seconds")
                c.execute("INSERT INTO cases (order_id,customer_id,created_at,decision,status,reasons,flags_in_effect) "
                          "VALUES (?,?,?,?,?,?,?)", (f"OLD-{cust}-{d}", cust, at, "approve", "seed_history", "[]", "{}"))


def reset():
    DB_PATH.unlink(missing_ok=True)
    init()


def returns_30d(c, customer_id) -> int:
    since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat(timespec="seconds")
    return c.execute("SELECT COUNT(*) FROM cases WHERE customer_id=? AND created_at>=?", (customer_id, since)).fetchone()[0]


def log_event(c, case_id, step, detail=""):
    c.execute("INSERT INTO events (case_id,at,step,detail) VALUES (?,?,?,?)", (case_id, now(), step, detail))


def row(r):
    d = dict(r)
    for k in ("reasons", "flags_in_effect"):
        if k in d and isinstance(d[k], str):
            d[k] = json.loads(d[k] or "null")
    return d
