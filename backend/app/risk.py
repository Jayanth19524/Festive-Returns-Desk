"""The refund decision. Plain deterministic code: no LLM, no network, no randomness.

Inputs: the structured case (fields extracted from speech), the order and customer facts from OUR database,
and the live Flagsmith config. Customer words can only change the extracted fields, never these rules.
"""
RETURN_WINDOW_DAYS = 15
APPROVE_BELOW_SCORE = 30   # risk score under this may be auto-approved
REJECT_FROM_SCORE = 70     # risk score at or over this is rejected


def decide(case: dict, order: dict | None, returns_30d: int, already_returned: bool, cfg: dict, photo: dict | None = None) -> dict:
    """Returns {decision: approve|hold|reject, score, reasons[], signed_approval_required}."""
    reasons, score = [], 0
    if order is None:
        return _out("reject", 0, ["Order id not found in our records"])
    if already_returned:
        return _out("reject", 0, ["This order already has a return case"])
    if order["delivered_days_ago"] > RETURN_WINDOW_DAYS:
        return _out("reject", 0, [f"Delivered {order['delivered_days_ago']} days ago; window is {RETURN_WINDOW_DAYS} days"])

    if case["reason_category"] == "worn_once" or case["claimed_condition"] == "worn":
        score += cfg["wardrobing_risk_weight"]
        reasons.append(f"Item worn before return (wardrobing signal, +{cfg['wardrobing_risk_weight']:g})")
    if returns_30d >= cfg["max_returns_per_customer_30d"]:
        score += 30
        reasons.append(f"{returns_30d} earlier returns in 30 days (limit {cfg['max_returns_per_customer_30d']}), +30")
    w = cfg.get("photo_risk_weight", 30)
    if photo and photo.get("status") == "ok" and photo.get("confidence", 0) >= 0.6:
        # Photo evidence can only RAISE risk, never lower it: a photo (or text hidden in one) cannot talk the rules into paying.
        why = []
        if not photo["shows_garment"]:
            why.append("the photo does not show the item")
        if photo["matches_claim"] == "no":
            why.append("the photo does not match what the customer said")
        if photo["signs_of_wear"] == "clear" and case["claimed_condition"] != "worn" and case["reason_category"] != "worn_once":
            why.append("the item shows clear signs of wear but was described as unworn")
        if photo["injection_text"]:
            why.append("the photo contains text that tries to instruct the system")
        if why:
            score += w
            reasons.append(f"Photo check: {'; '.join(why)} (+{w:g})")
    amount = order["amount_inr"]

    if not cfg["refunds_enabled"]:
        return _out("hold", score, reasons + ["Refunds are FROZEN by the owner (Flagsmith refunds_enabled is OFF)"])
    if score >= REJECT_FROM_SCORE:
        return _out("reject", score, reasons + [f"Risk score {score:g} is at or over {REJECT_FROM_SCORE}"])
    if amount > cfg["hold_above_inr"]:
        return _out("hold", score, reasons + [f"Amount ₹{amount:g} is above hold limit ₹{cfg['hold_above_inr']:g}: needs owner's signed approval"],
                    signed=True)
    if score >= APPROVE_BELOW_SCORE:
        return _out("hold", score, reasons + [f"Risk score {score:g} is {APPROVE_BELOW_SCORE} or more: owner review"])
    if amount > cfg["auto_refund_limit_inr"]:
        return _out("hold", score, reasons + [f"Amount ₹{amount:g} is above auto-refund limit ₹{cfg['auto_refund_limit_inr']:g}: owner review"])
    return _out("approve", score, reasons + [f"Low risk (score {score:g}) and ₹{amount:g} is within auto-refund limit ₹{cfg['auto_refund_limit_inr']:g}"])


def _out(decision, score, reasons, signed=False):
    return {"decision": decision, "score": score, "reasons": reasons, "signed_approval_required": signed}
