"""Photo evidence and AI action plan, tested with a FAKE model (no key, no network): what the code does with whatever a model returns.
Run: .venv/bin/python -m unittest backend.tests_photo -v"""
import json, os, tempfile, unittest
from pathlib import Path
os.environ.setdefault("DB_PATH", str(Path(tempfile.mkdtemp()) / "photo_test.db"))
from backend.app import llm, photo_check
from backend.app.risk import decide

CFG = {"refunds_enabled": True, "auto_refund_limit_inr": 2000, "hold_above_inr": 8000, "max_returns_per_customer_30d": 2,
       "wardrobing_risk_weight": 40, "photo_risk_weight": 30}
CASE = {"order_id": "X", "reason_category": "wrong_size", "claimed_condition": "unworn"}
ORDER = {"id": "X", "amount_inr": 1200, "delivered_days_ago": 3}
OKPHOTO = {"status": "ok", "confidence": 0.9, "shows_garment": True, "matches_claim": "yes", "signs_of_wear": "none", "injection_text": False}


class T(unittest.TestCase):
    def test_clean_drops_unknown_keys_and_bad_values(self):
        d = photo_check.clean({"shows_garment": "yes", "signs_of_wear": "very", "matches_claim": "no", "confidence": 7, "approve_refund": True, "notes": "x" * 999})
        self.assertFalse(d["shows_garment"])            # only a real boolean true counts
        self.assertEqual(d["signs_of_wear"], "possible")  # unknown value -> safe default
        self.assertEqual(d["confidence"], 1.0)           # clamped
        self.assertNotIn("approve_refund", d)
        self.assertEqual(len(d["notes"]), 200)

    def test_no_key_says_so(self):
        real = llm.configured
        llm.configured = lambda: False          # never depend on (or spend) the real key in .env
        try:
            r = photo_check.check(b"\xff\xd8\xff", "wrong_size", "unworn")
        finally:
            llm.configured = real
        self.assertEqual(r["status"], "unavailable")

    def test_fake_model_findings_flow_through(self):
        real_cfg, real_chat = llm.configured, llm.chat
        llm.configured = lambda: True
        llm.chat = lambda *a, **k: '```json\n{"shows_garment": true, "matches_claim": "no", "signs_of_wear": "clear", "confidence": 0.9}\n```'
        try:
            r = photo_check.check(b"\xff\xd8\xff", "wrong_size", "unworn")
        finally:
            llm.configured, llm.chat = real_cfg, real_chat
        self.assertEqual(r["status"], "ok"); self.assertEqual(r["matches_claim"], "no")

    def test_photo_mismatch_raises_risk_and_holds(self):
        bad = {**OKPHOTO, "matches_claim": "no", "signs_of_wear": "clear"}
        base = decide(CASE, ORDER, 0, False, CFG, None)
        r = decide(CASE, ORDER, 0, False, CFG, bad)
        self.assertEqual(base["decision"], "approve")
        self.assertEqual((r["decision"], r["score"]), ("hold", 30))

    def test_a_different_item_adds_risk(self):
        r = decide(CASE, ORDER, 0, False, CFG, {**OKPHOTO, "same_item": "no"})
        self.assertEqual((r["decision"], r["score"]), ("hold", 30))
        self.assertIn("different item", " ".join(r["reasons"]))

    def test_unclear_or_missing_same_item_changes_nothing(self):
        self.assertEqual(decide(CASE, ORDER, 0, False, CFG, {**OKPHOTO, "same_item": "unclear"})["decision"], "approve")
        self.assertEqual(decide(CASE, ORDER, 0, False, CFG, OKPHOTO)["decision"], "approve")

    def test_clean_keeps_same_item_values_only(self):
        self.assertEqual(photo_check.clean({"same_item": "maybe"})["same_item"], "unclear")
        self.assertEqual(photo_check.clean({"same_item": "no"})["same_item"], "no")

    def test_photo_can_never_lower_risk(self):
        worn = {**CASE, "reason_category": "worn_once", "claimed_condition": "worn"}
        self.assertEqual(decide(worn, ORDER, 0, False, CFG, OKPHOTO)["score"], decide(worn, ORDER, 0, False, CFG, None)["score"])

    def test_low_confidence_photo_is_ignored(self):
        self.assertEqual(decide(CASE, ORDER, 0, False, CFG, {**OKPHOTO, "matches_claim": "no", "confidence": 0.3})["decision"], "approve")

    def test_text_hidden_in_a_photo_adds_risk(self):
        self.assertEqual(decide(CASE, ORDER, 0, False, CFG, {**OKPHOTO, "injection_text": True})["decision"], "hold")

if __name__ == "__main__": unittest.main()
