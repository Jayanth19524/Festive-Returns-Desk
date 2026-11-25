"""Return Intelligence maths and the AI number guard. Run: .venv/bin/python -m unittest backend.tests_intel -v"""
import os, tempfile, unittest
from pathlib import Path
os.environ.setdefault("DB_PATH", str(Path(tempfile.mkdtemp()) / "intel_test.db"))
from backend.app import intel
from backend.app.main import numbers_in

def row(reason="wrong_size", cond="unworn", dec="approve", amt=1000, cust="C1", season="diwali", sku="A-1", days=3):
    return {"reason": reason, "condition": cond, "decision": dec, "amount": amt, "customer_id": cust, "season": season, "sku": sku, "days_ago": days}

class T(unittest.TestCase):
    def test_loss_unworn_recovers_most_but_pays_fees(self):
        l = intel.case_loss(1000, "unworn"); self.assertEqual((l["recovered"], l["fees"], l["net_loss"]), (950.0, 130, 180.0))

    def test_rejected_return_costs_nothing(self):
        self.assertEqual(intel.case_loss(1000, "unworn", refunded=False)["net_loss"], 0.0)

    def test_dispositions(self):
        self.assertEqual(intel.disposition("wrong_size", "unworn")["action"], "exchange_offer")
        self.assertEqual(intel.disposition("worn_once", "worn")["action"], "partial_refund")
        self.assertEqual(intel.disposition("damaged", "damaged")["action"], "repair")
        self.assertEqual(intel.disposition("changed_mind", "unworn")["action"], "restock")

    def test_photo_can_only_make_advice_more_cautious(self):
        worn_photo = {"status": "ok", "confidence": 0.9, "signs_of_wear": "clear", "visible_damage": False}
        self.assertEqual(intel.disposition("wrong_size", "unworn", worn_photo)["action"], "clean_resell")
        clean_photo = {"status": "ok", "confidence": 0.9, "signs_of_wear": "none", "visible_damage": False}
        self.assertEqual(intel.disposition("worn_once", "worn", clean_photo)["action"], "partial_refund")   # a clean photo does not undo the customer's own admission

    def test_damage_claim_with_a_clean_photo_means_inspect_first(self):
        clean = {"status": "ok", "confidence": 0.9, "visible_damage": False, "matches_claim": "no", "signs_of_wear": "none"}
        self.assertEqual(intel.disposition("damaged", "damaged", clean)["action"], "inspect_first")
        shows = {**clean, "visible_damage": True, "matches_claim": "yes"}
        self.assertEqual(intel.disposition("damaged", "damaged", shows)["action"], "repair")

    def test_measurement_action_uses_the_observed_gap(self):
        listings = [{"sku": "M1", "season": "diwali", "missing_measurements": True, "orders": 10, "size_returns": 4},
                    {"sku": "H1", "season": "diwali", "missing_measurements": False, "orders": 10, "size_returns": 0}]
        rows = [row(sku="M1") for _ in range(4)]
        out = intel.analyse(rows, listings, 20)
        a = next(x for x in out["actions"] if x["key"] == "measurements")
        self.assertGreater(a["impact_inr"], 0); self.assertEqual(a["skus"], ["M1"])

    def test_no_action_invented_without_data(self):
        out = intel.analyse([], [], 0)
        self.assertEqual((out["returns"], out["net_loss_inr"], out["actions"]), (0, 0, []))

    def test_repeat_returners_found(self):
        out = intel.analyse([row(cust="X", amt=500), row(cust="X", amt=700), row(cust="Y")], [], 10)
        self.assertEqual(out["repeat_returners"][0]["customer"], "X")

    def test_ai_number_guard(self):
        allowed = numbers_in('{"loss": 22163, "pct": 22.0, "n": 33}')
        self.assertIn("22163", allowed)
        self.assertEqual(numbers_in("You will save 99,999 rupees") - allowed, {"99999"})      # an invented figure is caught
        self.assertEqual(numbers_in("Loss is 22,163 over 33 returns") - allowed, set())          # figures from our data pass
        self.assertEqual(numbers_in("₹17,818 and 40%"), {"17818", "40"})


    def test_late_rejection_is_strong_because_it_rests_on_checkable_facts(self):
        e = intel.evidence_level({"reasons": ["Delivered 40 days ago; window is 15 days"], "transcript": "x"})
        self.assertEqual(e["level"], "strong"); self.assertIsNone(e["goodwill"])

    def test_score_based_rejection_without_evidence_is_weak_and_gets_a_goodwill_suggestion(self):
        e = intel.evidence_level({"reasons": ["Risk score 70 is at or over 70"], "transcript": "(typed return)", "claimed_condition": "unworn", "reason_category": "wrong_size"})
        self.assertEqual(e["level"], "weak"); self.assertIn("exchange", e["goodwill"])

    def test_admission_plus_photo_support_makes_it_strong(self):
        e = intel.evidence_level({"reasons": ["Risk score 70 is at or over 70"], "transcript": "I wore it", "claimed_condition": "worn", "reason_category": "worn_once",
                                  "photo_path": "a.jpg", "photo_check": {"status": "ok", "signs_of_wear": "clear"}})
        self.assertEqual(e["level"], "strong")

if __name__ == "__main__": unittest.main()
