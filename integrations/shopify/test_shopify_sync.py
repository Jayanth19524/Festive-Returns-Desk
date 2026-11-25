"""Automated tests for Shopify integration: mapping, idempotency, festival neutrality, and returns creation."""
import os
import tempfile
import unittest
from pathlib import Path

# These tests call db.reset(), which deletes the database file: point them at a throw-away one BEFORE the app is imported.
os.environ.setdefault("DB_PATH", str(Path(tempfile.mkdtemp()) / "shopify_test.db"))
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient

from backend.app import db
from backend.app.main import app
from integrations.shopify.mapper import (
    extract_season,
    infer_category,
    map_csv_order,
    map_csv_product,
    map_shopify_order,
    map_shopify_product,
)
from integrations.shopify.sync import run_sync


class TestShopifyIntegration(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        os.environ["INGEST_API_TOKEN"] = "test-token-secret-xyz"
        os.environ["FESTIVE_SEASON"] = "Diwali"
        cls.client = TestClient(app)

    def setUp(self):
        db.reset()

    def test_festival_neutrality_and_season_extraction(self):
        """Verify season extraction is completely dynamic and festival-agnostic."""
        self.assertEqual(extract_season("ethnic, season:diwali, lehenga"), "diwali")
        self.assertEqual(extract_season("eid-special, season:eid, kurta"), "eid")
        self.assertEqual(extract_season("harvest, festival:pongal, silk"), "pongal")
        self.assertEqual(extract_season(["winter", "season:christmas"]), "christmas")
        self.assertIsNone(extract_season("casual, summer, cotton"))

    def test_category_inference(self):
        """Verify standard categories inference."""
        self.assertEqual(infer_category("Velvet Chaniya Choli"), "lehenga")
        self.assertEqual(infer_category("Banarasi Silk Saree"), "saree")
        self.assertEqual(infer_category("Lucknowi Kurta Set"), "kurta")
        self.assertEqual(infer_category("Designer Sleeveless Blouse"), "blouse")
        self.assertEqual(infer_category("Western Denim Jacket"), "other")

    def test_shopify_product_mapping(self):
        raw = {
            "id": 1101,
            "title": "Pink Organza Saree (SIMULATED)",
            "product_type": "Saree",
            "body_html": "<p>Delicate hand-painted organza saree. <em>(SIMULATED)</em></p>",
            "tags": "season:diwali, festive, handloom",
            "images": [{"src": "https://example.com/saree1.jpg"}],
            "options": [{"name": "Size", "values": ["Free Size"]}],
            "variants": [{"id": 2201, "sku": "SAR-101", "price": "4200.00"}],
            "measurements": {"length_m": 5.5}
        }
        product = map_shopify_product(raw)
        self.assertEqual(product["sku"], "SAR-101")
        self.assertEqual(product["category"], "saree")
        self.assertEqual(product["price_inr"], 4200)
        self.assertEqual(product["season"], "diwali")
        self.assertEqual(product["sizes"], ["Free Size"])
        self.assertEqual(product["image_urls"], ["https://example.com/saree1.jpg"])
        self.assertEqual(product["source"], "shopify")
        self.assertIn("organza saree", product["description"])

    def test_shopify_order_mapping_privacy(self):
        """Verify mapping strips all sensitive credit card and address information."""
        raw = {
            "id": 9901,
            "order_number": 9901,
            "total_price": "7500.00",
            "created_at": "2026-11-20T10:00:00Z",
            "customer": {
                "id": 8801,
                "first_name": "Rani",
                "last_name": "Mukherjee"
            },
            # Sensitive fields that MUST be ignored
            "payment_details": {"credit_card_number": "4111222233334444", "cvv": "123"},
            "billing_address": {"address1": "123 Secret St", "city": "Mumbai"},
            "line_items": [{"id": 3301, "sku": "LEH-500", "title": "Silk Lehenga"}],
            "fulfillments": [{"id": 4401, "updated_at": "2026-11-21T14:00:00Z"}]
        }
        order = map_shopify_order(raw)
        self.assertEqual(order["id"], "SHP-9901")
        self.assertEqual(order["customer"]["id"], "SHP-C-8801")
        self.assertEqual(order["customer"]["name"], "Rani Mukherjee")
        self.assertEqual(order["amount_inr"], 7500)
        self.assertEqual(order["item_sku"], "LEH-500")
        self.assertEqual(order["delivered_at"], "2026-11-21")
        # Ensure no payment or address leaks
        self.assertNotIn("payment_details", order)
        self.assertNotIn("credit_card", str(order))
        self.assertNotIn("Secret St", str(order))

    def test_ingest_auth_and_rejection_of_unknown_fields(self):
        """Verify 401 on bad auth, and polite rejection on unknown fields."""
        # 1. Missing / bad token
        res_no_auth = self.client.post("/api/ingest/products", json={"products": []})
        self.assertEqual(res_no_auth.status_code, 401)

        res_bad_auth = self.client.post("/api/ingest/products",
                                        headers={"Authorization": "Bearer wrong-token"},
                                        json={"products": []})
        self.assertEqual(res_bad_auth.status_code, 401)

        # 2. Reject unknown fields politely
        bad_payload = {
            "products": [
                {
                    "sku": "BAD-1",
                    "title": "Test",
                    "price_inr": 1000,
                    "unknown_field_xyz": "not allowed"
                }
            ]
        }
        res_unknown = self.client.post("/api/ingest/products",
                                       headers={"Authorization": "Bearer test-token-secret-xyz"},
                                       json=bad_payload)
        self.assertEqual(res_unknown.status_code, 422)

    def test_sync_idempotency(self):
        """Verify re-running sync creates zero duplicate products or orders."""
        # Direct DB sync with mock data
        res1 = run_sync(source="mock", dest="db")
        self.assertGreater(res1["products_upserted"], 0)
        self.assertGreater(res1["orders_upserted"], 0)

        with db.conn() as c:
            p_count1 = c.execute("SELECT COUNT(*) FROM products").fetchone()[0]
            o_count1 = c.execute("SELECT COUNT(*) FROM orders WHERE id LIKE 'SHP-%'").fetchone()[0]
            c_count1 = c.execute("SELECT COUNT(*) FROM customers WHERE id LIKE 'SHP-C-%'").fetchone()[0]

        # Second run with exact same data
        res2 = run_sync(source="mock", dest="db")
        self.assertEqual(res1["products_upserted"], res2["products_upserted"])

        with db.conn() as c:
            p_count2 = c.execute("SELECT COUNT(*) FROM products").fetchone()[0]
            o_count2 = c.execute("SELECT COUNT(*) FROM orders WHERE id LIKE 'SHP-%'").fetchone()[0]
            c_count2 = c.execute("SELECT COUNT(*) FROM customers WHERE id LIKE 'SHP-C-%'").fetchone()[0]

        self.assertEqual(p_count1, p_count2, "Products count must remain identical (no duplicates)")
        self.assertEqual(o_count1, o_count2, "Orders count must remain identical (no duplicates)")
        self.assertEqual(c_count1, c_count2, "Customers count must remain identical (no duplicates)")

    def test_return_case_against_synced_order(self):
        """Verify that a customer return can be filed against a synced Shopify order ID."""
        # Sync mock orders
        run_sync(source="mock", dest="db")

        # Order SHP-1041: KUR-102 (₹1899), delivered recently
        res = self.client.post("/api/cases", json={
            "order_id": "SHP-1041",
            "reason_category": "wrong_size",
            "claimed_condition": "unworn",
            "transcript": "Kurta is too tight around the chest",
            "language": "hi-IN"
        })
        self.assertEqual(res.status_code, 200)
        case = res.json()
        self.assertEqual(case["order_id"], "SHP-1041")
        self.assertEqual(case["customer_id"], "SHP-C-71")
        # Under ₹2000, unworn, delivered within 15 days -> auto approved
        self.assertEqual(case["decision"], "approve")

        # Check that it appears in GET /api/cases
        cases_list = self.client.get("/api/cases").json()
        matching = [k for k in cases_list if k["order_id"] == "SHP-1041"]
        self.assertTrue(len(matching) >= 1)


if __name__ == "__main__":
    unittest.main()
