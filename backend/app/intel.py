"""Return Intelligence: what returns cost, what to do with each returned item, and which changes would save the most.

Pure functions over plain rows, no database or network, so every number can be traced and tested.
The money model rests on ASSUMPTIONS below. They are estimates a seller should replace with their own costs; the UI shows them.
"""
ASSUMPTIONS = {
    "reverse_shipping_inr": 90,    # pickup and transport of one returned parcel
    "handling_inr": 40,            # checking, steaming, repacking one item
    "recovery_pct": {"unworn": 95, "worn": 60, "damaged": 25, "unknown": 80},   # share of the price recovered by restocking / B-grade sale / salvage
    "exchange_accept_pct": 40,     # share of wrong-size returns that would take a size exchange when offered first
    "measurement_effect": "observed",  # the effect of adding measurements is measured from the seller's own data, not assumed
}
PREVENTABLE = ("wrong_size", "not_as_described")

# What to do with a returned item. Keyed by the situation; the steps are the seller's checklist.
PLAYBOOK = {
    "restock": ("Restock as new", ["Check tags and packaging", "Steam and fold", "Put back on sale in the same size"]),
    "exchange_offer": ("Offer a size exchange first", ["Ask if another size works (cheaper than a refund)", "Ship the new size, take the item back", "Refund only if they decline"]),
    "clean_resell": ("Clean and resell as B-grade", ["Inspect for stains and wear", "Dry-clean or steam", "List at a marked-down 'pre-loved' price"]),
    "repair": ("Repair or salvage", ["Photograph the damage", "Repair if the cost is below the resale gain", "Otherwise sell as a remnant or for parts"]),
    "partial_refund": ("Refund minus a wear deduction", ["Explain the no-worn policy politely", "Offer a partial refund or store credit", "Keep the photo as evidence"]),
    "inspect_first": ("Inspect on arrival before refunding", ["Compare the item with the customer's photo", "Photograph its real condition", "Refund or reject based on what you find"]),
    "review_listing": ("Fix the listing, then restock", ["Check the photo against the real colour and fabric", "Update the description or photos", "Restock once the listing is accurate"]),
}


def disposition(reason: str, condition: str, photo: dict | None = None) -> dict:
    """Deterministic recommendation for ONE returned item. A photo finding can only make the advice more cautious."""
    worn = condition == "worn" or reason == "worn_once"
    if (condition == "damaged" or reason == "damaged") and photo and photo.get("status") == "ok" and photo.get("confidence", 0) >= 0.6 \
            and not photo.get("visible_damage") and photo.get("matches_claim") == "no":
        label, steps = PLAYBOOK["inspect_first"]   # the photo does not show the claimed damage
        return {"action": "inspect_first", "label": label, "steps": steps, "recovery_pct": ASSUMPTIONS["recovery_pct"]["unknown"]}
    if photo and photo.get("status") == "ok" and photo.get("confidence", 0) >= 0.6:
        worn = worn or photo.get("signs_of_wear") == "clear"
        if photo.get("visible_damage"):
            condition = "damaged"
    if condition == "damaged" or reason == "damaged":
        key = "repair"
    elif worn:
        key = "partial_refund" if reason == "worn_once" or condition == "worn" else "clean_resell"
    elif reason == "wrong_size":
        key = "exchange_offer"
    elif reason == "not_as_described":
        key = "review_listing"
    else:
        key = "restock"
    label, steps = PLAYBOOK[key]
    state = "damaged" if key == "repair" else "worn" if worn else "unworn"
    return {"action": key, "label": label, "steps": steps, "recovery_pct": ASSUMPTIONS["recovery_pct"][state]}


def case_loss(amount: float, state: str, refunded: bool = True) -> dict:
    """Estimated cost of one return: what is refunded minus what is recovered, plus shipping and handling."""
    a = ASSUMPTIONS
    fees = a["reverse_shipping_inr"] + a["handling_inr"]
    if not refunded:   # a rejected return costs no refund
        return {"refund": 0.0, "recovered": 0.0, "fees": 0.0, "net_loss": 0.0}
    recovered = amount * a["recovery_pct"][state] / 100
    return {"refund": amount, "recovered": round(recovered, 2), "fees": fees, "net_loss": round(amount - recovered + fees, 2)}


def state_of(reason: str, condition: str) -> str:
    if condition == "damaged" or reason == "damaged":
        return "damaged"
    if condition == "worn" or reason == "worn_once":
        return "worn"
    return "unworn"


def analyse(rows: list[dict], listings: list[dict], total_orders: int) -> dict:
    """rows: one dict per return (reason, condition, decision, amount, customer_id, season, sku, days_ago). listings: from the catalogue."""
    n = len(rows)
    refunded = [r for r in rows if r["decision"] == "approve"]        # money out (or about to go out)
    pending = [r for r in rows if r["decision"] == "hold"]             # waiting for the owner: NOT counted as refunded
    loss = [case_loss(r["amount"], state_of(r["reason"], r["condition"])) for r in refunded]
    total_loss = round(sum(x["net_loss"] for x in loss))
    avg_loss = round(total_loss / len(refunded)) if refunded else 0
    out = {"returns": n, "orders": total_orders, "return_rate_pct": round(100 * n / total_orders, 1) if total_orders else 0,
           "refunded_returns": len(refunded), "pending_returns": len(pending), "pending_inr": round(sum(r["amount"] for r in pending)), "refunded_inr": round(sum(x["refund"] for x in loss)), "recovered_inr": round(sum(x["recovered"] for x in loss)),
           "fees_inr": round(sum(x["fees"] for x in loss)), "net_loss_inr": total_loss, "avg_loss_per_return_inr": avg_loss, "assumptions": ASSUMPTIONS}

    # how to handle: group every return by what should be done with the item
    pb = {}
    for r in refunded + pending:   # every item that comes back needs handling, whether or not the refund has been paid yet
        d = disposition(r["reason"], r["condition"])
        l = case_loss(r["amount"], state_of(r["reason"], r["condition"]))
        g = pb.setdefault(d["action"], {"action": d["action"], "label": d["label"], "steps": d["steps"], "count": 0, "value_inr": 0, "recoverable_inr": 0})
        g["count"] += 1; g["value_inr"] += round(r["amount"]); g["recoverable_inr"] += round(l["recovered"])
    out["playbook"] = sorted(pb.values(), key=lambda g: -g["value_inr"])

    # trend: returns per week for the last 8 weeks (0 = this week)
    weeks = [0] * 8
    for r in rows:
        w = int(r["days_ago"] // 7)
        if 0 <= w < 8:
            weeks[w] += 1
    out["weekly_returns"] = list(reversed(weeks))

    # who returns: repeat customers
    per = {}
    for r in refunded + pending:
        per.setdefault(r["customer_id"], []).append(r["amount"])
    rep = [{"customer": c, "returns": len(v), "value_inr": round(sum(v))} for c, v in per.items() if len(v) >= 2]
    out["repeat_returners"] = sorted(rep, key=lambda x: -x["value_inr"])[:5]
    out["repeat_share_pct"] = round(100 * sum(x["value_inr"] for x in rep) / max(1, sum(sum(v) for v in per.values())), 1)

    # by season
    ss = {}
    for r in rows:
        s = ss.setdefault(r["season"] or "other", {"season": r["season"] or "other", "returns": 0})
        s["returns"] += 1
    for lst in listings:
        s = ss.get(lst["season"] or "other")
        if s is not None:
            s["orders"] = s.get("orders", 0) + lst["orders"]
    out["seasons"] = sorted(({**s, "return_rate_pct": round(100 * s["returns"] / s["orders"], 1) if s.get("orders") else None} for s in ss.values()), key=lambda s: -s["returns"])

    out["actions"] = _actions(out, rows, listings, avg_loss)
    return out


def _actions(o: dict, rows: list[dict], listings: list[dict], avg_loss: int) -> list[dict]:
    """Ranked, each with a rupee estimate and the formula behind it. Estimates only count what the data supports."""
    acts = []
    miss = [v for v in listings if v["missing_measurements"]]
    have = [v for v in listings if not v["missing_measurements"]]
    o_miss, o_have = sum(v["orders"] for v in miss), sum(v["orders"] for v in have)
    if o_miss and o_have:
        rate = lambda g, o: sum(v["size_returns"] for v in g) / o
        gap = rate(miss, o_miss) - rate(have, o_have)
        avoid = round(gap * o_miss)
        if avoid > 0:
            acts.append({"key": "measurements", "title": f"Add garment measurements to {len(miss)} listings",
                         "impact_inr": avoid * avg_loss, "basis": f"{round(rate(miss, o_miss) * 100, 1)}% of orders on listings without measurements come back for size, vs {round(rate(have, o_have) * 100, 1)}% with them. Closing that gap avoids about {avoid} returns x ₹{avg_loss} average loss.",
                         "do": "Measure bust, waist, length and blouse for each; put them in the description and a size chart.",
                         "skus": [v["sku"] for v in sorted(miss, key=lambda v: -v["size_returns"]) if v["size_returns"]][:8]})
    size_ret = [r for r in rows if r["reason"] == "wrong_size" and r["decision"] != "reject"]
    if size_ret:
        value = sum(r["amount"] for r in size_ret)
        keep = round(value * ASSUMPTIONS["exchange_accept_pct"] / 100)
        acts.append({"key": "exchange_first", "title": "Offer a size exchange before any refund",
                     "impact_inr": keep, "basis": f"{len(size_ret)} wrong-size returns worth ₹{round(value):,}. If {ASSUMPTIONS['exchange_accept_pct']}% accept an exchange (an assumption), that sale is kept instead of refunded.",
                     "do": "The returns desk asks 'Would another size work?' before approving a refund; keep one spare of each fast-moving size."})
    worn = [r for r in rows if state_of(r["reason"], r["condition"]) == "worn" and r["decision"] != "reject"]
    if worn:
        value = sum(r["amount"] for r in worn)
        keep = round(value * 0.25)
        acts.append({"key": "worn_policy", "title": "Stop full refunds on worn items",
                     "impact_inr": keep, "basis": f"{len(worn)} refunded returns were worn, worth ₹{round(value):,}. A 25% wear deduction (an assumption) on those recovers about ₹{keep:,}.",
                     "do": "State the no-worn policy on every listing, keep the tags on, and refund minus a deduction (or store credit) when wear is visible in the photo."})
    if o["repeat_returners"]:
        rr = o["repeat_returners"]
        val = sum(x["value_inr"] for x in rr)
        acts.append({"key": "repeat", "title": f"Watch {len(rr)} repeat returners",
                     "impact_inr": round(val * 0.3), "basis": f"These customers returned 2+ items worth ₹{val:,}. Holding them for owner review cuts about 30% of that (an assumption).",
                     "do": "Keep 'max returns per customer (30 days)' low in Flagsmith so their next return is held for you."})
    dmg = [r for r in rows if r["reason"] == "damaged" and r["decision"] != "reject"]
    if dmg:
        value = sum(r["amount"] for r in dmg)
        acts.append({"key": "packing", "title": "Photograph and double-check items before dispatch",
                     "impact_inr": round(value * 0.5 * (1 - ASSUMPTIONS["recovery_pct"]["damaged"] / 100)), "basis": f"{len(dmg)} damaged returns worth ₹{round(value):,}. Catching half of them before dispatch avoids the refund minus the salvage value.",
                     "do": "Inspect and photograph each item when packing; the photo is also your evidence with the courier."})
    acts.sort(key=lambda a: -a["impact_inr"])
    return acts


def evidence_level(case: dict) -> dict:
    """How well a REJECTED return would stand up if the customer complained. Deterministic and explainable.
    strong = the rejection rests on facts anyone can check in the order records (late, duplicate, unknown order).
    Otherwise points are added for the customer's own words, a photo, a photo that supports the rejection, and an admission of wear."""
    reasons = " ".join(case.get("reasons") or [])
    policy = any(k in reasons for k in ("window is", "already has a return case", "not found in our records"))
    if policy:
        return {"level": "strong", "points": 4, "why": ["Rests on facts in the order records (delivery date, duplicate or unknown order)"],
                "goodwill": None}
    why, pts = [], 0
    if case.get("transcript") and case["transcript"] not in ("(typed return)", "(imported return history)"):
        pts += 1; why.append("The customer's own words are on file")
    photo = case.get("photo_check") or {}
    if case.get("photo_path"):
        pts += 1; why.append("A photo is on file")
        if photo.get("status") == "ok" and (photo.get("matches_claim") == "no" or photo.get("signs_of_wear") == "clear" or photo.get("injection_text")):
            pts += 1; why.append("The photo check supports the rejection")
    if case.get("claimed_condition") == "worn" or case.get("reason_category") == "worn_once":
        pts += 1; why.append("The customer said the item was worn")
    level = "strong" if pts >= 3 else "medium" if pts == 2 else "weak"
    goodwill = None if level == "strong" else "Offer a size exchange, store credit or a partial refund before it escalates"
    if not why:
        why = ["Little evidence beyond the risk score"]
    return {"level": level, "points": pts, "why": why, "goodwill": goodwill}
