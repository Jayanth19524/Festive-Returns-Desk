"""Hands each decided case to the NudgeBee workflow. NudgeBee runs the steps; it never computes risk (risk.py does)."""
import json, os, urllib.error, urllib.request
from . import config  # noqa: F401


def dispatch(case_id: int, res: dict, order: dict | None, language: str) -> dict:
    url = os.getenv("NUDGEBEE_WEBHOOK_URL", "")
    api_base = os.getenv("PUBLIC_API_BASE_URL", "").rstrip("/")
    if not url or not api_base:
        return {"sent": False, "detail": "NudgeBee not configured (NUDGEBEE_WEBHOOK_URL / PUBLIC_API_BASE_URL empty): case NOT executed"}
    payload = {"case_id": case_id, "decision": res["decision"], "order_id": order["id"] if order else None,
               "amount_inr": order["amount_inr"] if order else 0, "language": language,
               "signed_approval_required": res["signed_approval_required"], "api_base": api_base}
    req = urllib.request.Request(url, method="POST", data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return {"sent": True, "detail": f"webhook accepted by NudgeBee (HTTP {r.status}): {r.read().decode()[:200]}"}
    except (urllib.error.URLError, OSError) as e:
        return {"sent": False, "detail": f"NudgeBee webhook failed: {e}"}
