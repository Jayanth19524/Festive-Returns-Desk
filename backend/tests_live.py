"""Live monitor: surge detection and the counterfactual flag suggestions. Run: .venv/bin/python -m unittest backend.tests_live -v
Uses a throw-away database and never starts a NudgeBee run."""
import os, tempfile, unittest
from pathlib import Path
os.environ["FRD_TESTING"] = "1"
os.environ.setdefault("DB_PATH", str(Path(tempfile.mkdtemp()) / "live_test.db"))
from backend.app import cases, db, flags, live

CFG = {"refunds_enabled": True, "auto_refund_limit_inr": 2000, "hold_above_inr": 8000, "max_returns_per_customer_30d": 2,
       "wardrobing_risk_weight": 40, "photo_risk_weight": 30}


class T(unittest.TestCase):
    def setUp(self):
        self._load = flags.load
        flags.load = lambda: {"cfg": dict(CFG), "flags": {}, "status": "test", "live": True}
        db.reset()

    def tearDown(self):
        flags.load = self._load

    def _file(self, n, reason, cond):
        with db.conn() as c:
            orders = [r[0] for r in c.execute("SELECT o.id FROM orders o WHERE o.source IN ('shopify','demo-store') AND o.delivered_days_ago<=15 "
                                              "AND o.customer_id NOT IN (SELECT customer_id FROM cases WHERE status='seed_history') "
                                              "AND o.id NOT IN (SELECT order_id FROM cases WHERE status!='seed_history') ORDER BY o.id LIMIT ?", (n,))]
        for oid in orders:
            cases.create_case({"order_id": oid, "reason_category": reason, "claimed_condition": cond}, "t", "en-IN")
        return len(orders)

    def test_calm_means_no_suggestions_and_no_surge(self):
        self._file(2, "wrong_size", "unworn")
        s = live.snapshot()
        self.assertFalse(s["surge"]); self.assertEqual(live.suggest(), [])

    def test_surge_is_detected_by_pace(self):
        self._file(live.SURGE_AT, "wrong_size", "unworn")
        self.assertTrue(live.snapshot()["surge"])

    def test_wardrobing_suggestion_is_computed_not_guessed(self):
        self._file(4, "worn_once", "worn"); self._file(2, "wrong_size", "unworn")
        s = next(x for x in live.suggest() if x["flag"] == "wardrobing_keywords_risk_weight")
        self.assertGreater(s["proposed"], s["current"])
        self.assertIn("rejected", s["effect"])

    def test_freeze_is_suggested_only_at_twice_the_surge_level(self):
        self._file(live.SURGE_AT, "wrong_size", "unworn")
        self.assertFalse(any(x["flag"] == "refunds_enabled" for x in live.suggest()))
        self._file(live.SURGE_AT, "wrong_size", "unworn")
        self.assertTrue(any(x["flag"] == "refunds_enabled" for x in live.suggest()))


    def test_complaint_flow_and_reversal_respects_the_freeze(self):
        self._file(1, "worn_once", "worn")
        with db.conn() as c:
            cid = c.execute("SELECT id FROM cases WHERE status NOT IN ('seed_history','history') ORDER BY id DESC LIMIT 1").fetchone()[0]
        r = cases.add_complaint(cid, "consumer helpline", "wants a refund"); self.assertTrue(r["ok"])
        self.assertEqual(len(cases.case_file(cid)["complaints"]), 1)
        flags.load = lambda: {"cfg": {**CFG, "refunds_enabled": False}, "flags": {}, "status": "test", "live": True}
        self.assertFalse(cases.resolve_complaint(r["id"], "reversed", "x")["ok"])          # frozen: no refund can be issued
        flags.load = lambda: {"cfg": dict(CFG), "flags": {}, "status": "test", "live": True}
        self.assertTrue(cases.resolve_complaint(r["id"], "goodwill", "store credit")["ok"])
        self.assertFalse(cases.resolve_complaint(r["id"], "goodwill", "again")["ok"])      # already resolved

    def test_clear_sim_removes_only_simulated_returns(self):
        self._file(2, "wrong_size", "unworn")
        with db.conn() as c:
            ids = [r[0] for r in c.execute("SELECT id FROM cases WHERE status NOT IN ('seed_history','history')")]
            c.execute("UPDATE cases SET origin='sim' WHERE id=?", (ids[0],))
        self.assertEqual(live.clear_sim(), 1)
        with db.conn() as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM cases WHERE status NOT IN ('seed_history','history')").fetchone()[0], 1)


    def test_every_product_can_get_a_run_and_the_runs_view_is_honest(self):
        from fastapi.testclient import TestClient
        from backend.app.main import app
        with db.conn() as c:
            skus = [r[0] for r in c.execute("SELECT sku FROM products")]
            made = [live._order_for(c, s) for s in skus]
        self.assertEqual(len(made), len(skus)); self.assertTrue(all(m.startswith("SHP-") for m in made))
        cases.create_case({"order_id": made[0], "reason_category": "wrong_size", "claimed_condition": "unworn"}, "t", "en-IN")
        d = TestClient(app).get(f"/api/products/{skus[0]}/returns").json()
        kinds = {x["kind"] for x in d["items"]}
        self.assertIn("imported history", kinds)
        imported = [x for x in d["items"] if x["kind"] == "imported history"]
        self.assertTrue(all(not x["nudgebee_ran"] for x in imported))       # imported history never claims a workflow run
        self.assertEqual(TestClient(app).get("/api/products/NOPE/returns").status_code, 404)

if __name__ == "__main__": unittest.main()
