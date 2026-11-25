"""Tests for the simulated demo store, measurement parsing and the listing-level return analysis.
Run: .venv/bin/python -m unittest integrations.shopify.test_demo_store -v"""
import os
import tempfile

os.environ["FRD_TESTING"] = "1"
import unittest
from pathlib import Path

os.environ.setdefault("DB_PATH", str(Path(tempfile.mkdtemp()) / "demo_store_test.db"))  # never touch the real database
from fastapi.testclient import TestClient  # noqa: E402

from backend.app import db  # noqa: E402
from backend.app.main import app  # noqa: E402
from integrations.shopify import demo_store  # noqa: E402
from integrations.shopify.mapper import map_shopify_product, parse_measurements  # noqa: E402


class T(unittest.TestCase):
    def setUp(self):
        db.reset()   # reset() loads the demo store
        self.client = TestClient(app)

    def test_parse_measurements(self):
        self.assertEqual(parse_measurements("Waist 74 cm, length 102 cm. Blouse bust: 88 cm"),
                         {"blouse_bust_cm": 88, "waist_cm": 74, "length_cm": 102})
        self.assertEqual(parse_measurements("Length: 5.5 metres"), {"length_m": 5.5})
        self.assertEqual(parse_measurements("beautiful festive wear"), {})

    def test_listing_text_without_a_measurement_field_is_still_understood(self):
        raw = {"title": "Test Lehenga", "body_html": "<p>Waist 70 cm, length 100 cm</p>", "variants": [{"sku": "T-1", "price": "999"}]}
        self.assertEqual(map_shopify_product(raw)["measurements"], {"waist_cm": 70, "length_cm": 100})

    def test_demo_store_is_deterministic_and_has_five_festivals(self):
        a, b = demo_store.build(seed=11), demo_store.build(seed=11)
        self.assertEqual(len(a[1]), len(b[1]))
        self.assertEqual([h["reason"] for h in a[2]], [h["reason"] for h in b[2]])
        seasons = self.client.get("/api/catalogue").json()["seasons"]
        self.assertEqual(seasons, ["christmas", "diwali", "eid", "navratri", "pongal"])

    def test_loading_twice_changes_nothing(self):
        before = self.client.get("/api/insights").json()["total_returns"]
        db.load_demo_store()
        self.assertEqual(self.client.get("/api/insights").json()["total_returns"], before)

    def test_history_is_not_in_the_owner_queue_but_is_in_the_insights(self):
        self.assertEqual(self.client.get("/api/cases").json(), [])
        self.assertEqual(self.client.get("/api/stats").json()["by_decision"], {})
        self.assertGreater(self.client.get("/api/insights").json()["total_returns"], 10)

    def test_missing_measurements_returns_more_for_size(self):
        r = self.client.get("/api/insights").json()["listings"]
        self.assertGreater(r["missing_measurements"], 5)
        self.assertGreater(r["size_return_rate_pct"]["without_measurements"], r["size_return_rate_pct"]["with_measurements"])
        self.assertTrue(all(f["size_returns"] > 0 for f in r["fix_first"]))

    def test_order_lookup_for_the_return_link(self):
        o = self.client.get("/api/orders/shp-2001").json()
        self.assertEqual(o["id"], "SHP-2001")
        self.assertEqual(self.client.get("/api/orders/nope").status_code, 404)


if __name__ == "__main__":
    unittest.main()
