"""Live intelligence: how fast returns are arriving, whether that is a surge, and which Flagsmith change would help most.

Suggestions are COUNTERFACTUALS: the same deterministic rule (risk.py) is re-run on the cases that just arrived under the proposed value,
so "this would clear 5 waiting cases" is a computed fact, not a guess. The seller applies a suggestion; nothing changes by itself.
Also here: a paced simulator of customers that files returns through the real pipeline (rule + Flagsmith + NudgeBee).
"""
import json, os, random, threading, time
from datetime import datetime, timedelta, timezone
from . import cases, db, flags, risk, sarvam_service as sv

WINDOW_SEC = int(os.getenv("SURGE_WINDOW_SEC", "60"))     # "how fast" is measured over this many seconds
SURGE_AT = int(os.getenv("SURGE_AT", "8"))                # this many returns inside the window = a surge
RECENT_SEC = 300                                          # suggestions look at the last five minutes


def _utc(iso):
    return datetime.fromisoformat(iso)


def _recent_cases(c, since_sec):
    since = (datetime.now(timezone.utc) - timedelta(seconds=since_sec)).isoformat(timespec="milliseconds")
    rows = c.execute("SELECT k.id, k.order_id, k.created_at, k.reason_category r, k.claimed_condition cd, k.decision, k.status, k.language, k.customer_id cu, "
                     "k.photo_check pc, o.amount_inr amt, o.item FROM cases k LEFT JOIN orders o ON o.id=k.order_id "
                     "WHERE k.status NOT IN ('seed_history','history') AND k.created_at>=? ORDER BY k.created_at DESC", (since,)).fetchall()
    return [dict(r) for r in rows]


def snapshot() -> dict:
    now = datetime.now(timezone.utc)
    with db.conn() as c:
        rec = _recent_cases(c, 600)
        held = c.execute("SELECT COUNT(*), COALESCE(SUM(o.amount_inr),0) FROM cases k JOIN orders o ON o.id=k.order_id WHERE k.status='held'").fetchone()
        steps = {r[0]: r[1] for r in c.execute("SELECT case_id, COUNT(*) FROM events WHERE step IN ('workflow_validate','refund_issued','case_held','case_rejected') GROUP BY case_id")}
    ts = [(now - _utc(r["created_at"])).total_seconds() for r in rec]
    in_window = sum(1 for t in ts if t <= WINDOW_SEC)
    series = []   # returns in the trailing window, sampled every 10 s for the last 5 minutes (oldest first)
    for back in range(300, -1, -10):
        series.append(sum(1 for t in ts if back <= t <= back + WINDOW_SEC))
    cfg = flags.load()["cfg"]
    feed = [{"id": r["id"], "order_id": r["order_id"], "item": r["item"], "amount_inr": r["amt"], "reason": r["r"], "decision": r["decision"], "status": r["status"],
             "language": r["language"], "ago_sec": round((now - _utc(r["created_at"])).total_seconds()), "nudgebee_steps": steps.get(r["id"], 0)} for r in rec[:12]]
    five = [r for r in rec if (now - _utc(r["created_at"])).total_seconds() <= RECENT_SEC]
    return {"window_sec": WINDOW_SEC, "surge_at": SURGE_AT, "in_window": in_window, "surge": in_window >= SURGE_AT, "series": series,
            "waiting": held[0], "waiting_inr": round(held[1]), "last5": {"returns": len(five), "auto_approved": sum(1 for r in five if r["decision"] == "approve"),
            "held": sum(1 for r in five if r["decision"] == "hold"), "rejected": sum(1 for r in five if r["decision"] == "reject")},
            "refunds_enabled": cfg["refunds_enabled"], "feed": feed, "simulation": dict(SIM)}


def _decision_under(c, r, cfg_variant):
    """What the rule would decide for this arrived case under a different Flagsmith configuration."""
    case = {"order_id": r["order_id"], "reason_category": r["r"], "claimed_condition": r["cd"]}
    photo = json.loads(r["pc"]) if r.get("pc") else None
    return cases.evaluate(c, case, cfg_variant, exclude_case_id=r["id"], photo=photo)[0]["decision"]


def suggest() -> list[dict]:
    """Ranked flag changes with a computed effect. Empty when things are calm."""
    snap = snapshot()
    cfg = flags.load()["cfg"]
    with db.conn() as c:
        rec = _recent_cases(c, RECENT_SEC)
        if not rec:
            return []
        now_dec = {r["id"]: r["decision"] for r in rec}
        waiting = [r for r in rec if r["status"] == "held" or r["decision"] == "hold"]
        worn = [r for r in rec if r["r"] == "worn_once" or r["cd"] == "worn"]
        per_cust = {}
        for r in rec:
            per_cust[r["cu"]] = per_cust.get(r["cu"], 0) + 1
        repeaters = [k for k, v in per_cust.items() if v >= 2]
        out = []

        def effect(flag, value):
            v = {**cfg, flag: value}
            changed = {"approve": 0, "hold": 0, "reject": 0}; value_inr = 0
            for r in rec:
                nd = _decision_under(c, r, v)
                if nd != now_dec[r["id"]]:
                    changed[nd] += 1
                    value_inr += r["amt"] or 0
            return changed, round(value_inr)

        if cfg["refunds_enabled"] and snap["in_window"] >= 2 * SURGE_AT:
            out.append({"flag": "refunds_enabled", "current": "on", "proposed": "off", "severity": "high",
                        "title": "Freeze refunds for a few minutes",
                        "why": f"{snap['in_window']} returns in the last {WINDOW_SEC} s is more than twice the surge level ({SURGE_AT}). Stop money moving while you look.",
                        "effect": f"Every new return waits for you; nothing is paid out until you switch refunds back on. {snap['last5']['auto_approved']} auto-approved in the last 5 min would have waited."})
        up = cfg["auto_refund_limit_inr"] + 1000
        ch, val = effect("auto_refund_limit_inr", up)
        if len(waiting) >= 3 and ch["approve"] >= 2:
            out.append({"flag": "auto_refund_limit_inr", "current": cfg["auto_refund_limit_inr"], "proposed": up, "severity": "medium",
                        "title": f"Raise the auto-refund limit to ₹{up:,.0f}",
                        "why": f"{len(waiting)} returns are waiting for you. These are low-risk ones held only because of their price.",
                        "effect": f"{ch['approve']} of the returns that just arrived (₹{val:,}) would be approved automatically instead of waiting. Risky ones still wait."})
        if len(worn) >= 2 and len(worn) / len(rec) >= 0.25:
            up_w = min(100, cfg["wardrobing_risk_weight"] + 30)
            ch, val = effect("wardrobing_risk_weight", up_w)
            out.append({"flag": "wardrobing_keywords_risk_weight", "current": cfg["wardrobing_risk_weight"], "proposed": up_w, "severity": "medium",
                        "title": "Treat 'worn once' returns as high risk",
                        "why": f"{len(worn)} of {len(rec)} recent returns are worn items ({round(100 * len(worn) / len(rec))}%), which looks like post-festival wardrobing.",
                        "effect": f"{ch['reject']} worn-item returns (₹{val:,}) would be rejected outright and {ch['hold']} more held, instead of reaching you as ordinary reviews."})
        if repeaters and cfg["max_returns_per_customer_30d"] > 1:
            lower = cfg["max_returns_per_customer_30d"] - 1
            ch, val = effect("max_returns_per_customer_30d", lower)
            if ch["hold"] + ch["reject"] > 0:
                out.append({"flag": "max_returns_per_customer_30d", "current": cfg["max_returns_per_customer_30d"], "proposed": lower, "severity": "medium",
                            "title": f"Lower the repeat-returner limit to {lower}",
                            "why": f"{len(repeaters)} customers returned more than once in the last 5 minutes.",
                            "effect": f"{ch['hold'] + ch['reject']} returns (₹{val:,}) from repeat returners would be held for your review instead of approved."})
        mism = [r for r in rec if r.get("pc") and json.loads(r["pc"]).get("matches_claim") == "no"]
        if len(mism) >= 2:
            up_p = min(100, cfg["photo_risk_weight"] + 30)
            ch, val = effect("photo_risk_weight", up_p)
            out.append({"flag": "photo_mismatch_risk_weight", "current": cfg["photo_risk_weight"], "proposed": up_p, "severity": "medium",
                        "title": "Weigh photo mismatches more", "why": f"{len(mism)} recent photos did not match what the customer said.",
                        "effect": f"{ch['hold'] + ch['reject']} returns (₹{val:,}) would move to review or rejection."})
    return out


# ------------------------------ the customers simulator ------------------------------
SIM = {"running": False, "phase": "idle", "filed": 0, "total": 0, "message": ""}
_stop = threading.Event()
PHRASES = {"gu-IN": {"wrong_size": "મારો ઓર્ડર {id} છે. સાઈઝ ખોટી છે, મેં તે પહેરી નથી.", "worn_once": "મારો ઓર્ડર {id} છે. મેં તે ગરબામાં એક વાર પહેર્યું હતું, હવે પાછું આપવું છે.",
                    "damaged": "મારો ઓર્ડર {id} છે. કપડું ફાટેલું આવ્યું છે.", "changed_mind": "મારો ઓર્ડર {id} છે. મને પસંદ નથી આવ્યું, પાછું આપવું છે."},
           "hi-IN": {"wrong_size": "मेरा ऑर्डर {id} है। साइज़ गलत है, मैंने इसे पहना नहीं है।", "worn_once": "मेरा ऑर्डर {id} है। मैंने इसे एक बार गरबा में पहना था, अब वापस करना है।",
                    "damaged": "मेरा ऑर्डर {id} है। कपड़ा फटा हुआ आया है।", "changed_mind": "मेरा ऑर्डर {id} है। मुझे पसंद नहीं आया, वापस करना है।"},
           "kn-IN": {"wrong_size": "ನನ್ನ ಆರ್ಡರ್ {id}. ಸೈಜ್ ತಪ್ಪಾಗಿದೆ, ನಾನು ಇದನ್ನು ಧರಿಸಿಲ್ಲ.", "worn_once": "ನನ್ನ ಆರ್ಡರ್ {id}. ನಾನು ಇದನ್ನು ಗರ್ಬಾದಲ್ಲಿ ಒಮ್ಮೆ ಧರಿಸಿದ್ದೆ, ಈಗ ವಾಪಸ್ ಕೊಡಬೇಕು.",
                    "damaged": "ನನ್ನ ಆರ್ಡರ್ {id}. ಬಟ್ಟೆ ಹರಿದು ಬಂದಿದೆ.", "changed_mind": "ನನ್ನ ಆರ್ಡರ್ {id}. ನನಗೆ ಇಷ್ಟವಾಗಲಿಲ್ಲ, ವಾಪಸ್ ಕೊಡಬೇಕು."}}
COND = {"worn_once": "worn", "damaged": "damaged"}
# phase name, seconds, number of returns, reason weights, share of repeat returners
PLAN = [("Normal day", 50, 5, {"wrong_size": 50, "changed_mind": 25, "damaged": 10, "worn_once": 15}, 0.0),
        ("Post-festival rush", 24, 16, {"wrong_size": 30, "worn_once": 40, "changed_mind": 20, "damaged": 10}, 0.25),
        ("After you act", 24, 6, {"wrong_size": 30, "worn_once": 40, "changed_mind": 20, "damaged": 10}, 0.25)]


def _free_orders(c, repeat: bool):
    cond = ("o.customer_id IN (SELECT customer_id FROM cases WHERE status='seed_history' GROUP BY customer_id HAVING COUNT(*)>=3)" if repeat
            else "o.customer_id NOT IN (SELECT customer_id FROM cases WHERE status='seed_history')")
    return [dict(r) for r in c.execute(
        f"SELECT o.id, o.amount_inr FROM orders o WHERE {cond} AND o.delivered_days_ago<=15 AND o.source IN ('shopify','demo-store') "
        "AND o.id NOT IN (SELECT order_id FROM cases WHERE status!='seed_history') ORDER BY o.id")]


def clear_sim() -> int:
    """Remove every return the simulator filed (and its events, refunds and complaints), so the next run, and the intelligence pages, start clean."""
    with db.conn() as c:
        ids = [r[0] for r in c.execute("SELECT id FROM cases WHERE origin='sim'")]
        for i in ids:
            for t in ("events", "refunds", "complaints"):
                c.execute(f"DELETE FROM {t} WHERE case_id=?", (i,))
            c.execute("DELETE FROM cases WHERE id=?", (i,))
    SIM.update(running=False, phase="idle", filed=0, total=0, message="")
    return len(ids)


def _file(order_id, reason, voice_lang=None):
    case = _file_inner(order_id, reason, voice_lang)
    with db.conn() as c:
        c.execute("UPDATE cases SET origin='sim' WHERE id=?", (case["id"],))
    return case


def _file_inner(order_id, reason, voice_lang=None):
    fields = {"order_id": order_id, "reason_category": reason, "claimed_condition": COND.get(reason, "unworn")}
    if voice_lang:   # the real voice pipeline: speak -> Saaras -> 105B (a synthetic customer voice, so this is an upper bound on accuracy)
        try:
            text = PHRASES[voice_lang][reason].format(id=order_id)
            wav = sv.speak(text, voice_lang)
            t0 = time.perf_counter(); heard, det = sv.transcribe(wav, "sim.wav", "audio/wav"); t1 = time.perf_counter()
            ext = sv.extract(heard); t2 = time.perf_counter()
            ext["order_id"] = order_id   # the order is known from the customer's return link
            trace = [{"stage": "stt", "who": "sarvam", "ms": round((t1 - t0) * 1000, 1), "lang": det}, {"stage": "extract", "who": "sarvam", "ms": round((t2 - t1) * 1000, 1)}]
            return cases.create_case(ext, heard, voice_lang, trace)
        except Exception:
            pass   # fall back to a typed return rather than stopping the demo
    return cases.create_case(fields, "(typed return)", "en-IN")


def _run(seed: int):
    rnd = random.Random(seed)
    total = sum(p[2] for p in PLAN)
    SIM.update(running=True, filed=0, total=total, phase="starting", message="")
    n = 0
    try:
        for name, secs, count, weights, repeat_share in PLAN:
            SIM["phase"] = name
            gap = secs / count
            for _ in range(count):
                if _stop.is_set():
                    return
                with db.conn() as c:
                    use_repeat = rnd.random() < repeat_share
                    pool = _free_orders(c, use_repeat) or _free_orders(c, False)
                if not pool:
                    SIM["message"] = "No free orders left: reset the demo data."
                    return
                o = rnd.choice(pool)
                reason = rnd.choices(list(weights), weights=list(weights.values()))[0]
                voice = ["gu-IN", "hi-IN", "kn-IN"][(n // 4) % 3] if n % 4 == 3 else None   # every 4th customer speaks
                if voice:   # speech + understanding takes a few seconds: do it beside the pacing so the rush stays a rush
                    threading.Thread(target=_file, args=(o["id"], reason, voice), daemon=True).start()
                else:
                    _file(o["id"], reason, None)
                n += 1; SIM["filed"] = n
                if _stop.wait(gap + rnd.uniform(-0.25, 0.25) * gap):
                    return
        SIM["phase"] = "done"
    finally:
        SIM["running"] = False
        if SIM["phase"] not in ("done",):
            SIM["phase"] = "stopped"


def start(seed: int = 7) -> dict:
    if SIM["running"]:
        return {"ok": False, "error": "already running"}
    _stop.clear()
    clear_sim()   # a new run never carries the previous one
    threading.Thread(target=_run, args=(seed,), daemon=True).start()
    return {"ok": True}


def stop() -> dict:
    _stop.set()
    return {"ok": True}


# ----- one return on every product: so every listing has a real run (rule + Flagsmith + NudgeBee) to look at -----
_ALL_REASONS = ["wrong_size", "changed_mind", "damaged", "not_as_described", "worn_once"]   # cycled across the products


def _order_for(c, sku):
    """A fresh, unreturned order of this product, or a new demo order (a shopper buys it today, delivered tomorrow)."""
    row = c.execute("SELECT o.id FROM orders o WHERE (o.item_sku=? OR o.item_sku LIKE ?) AND o.delivered_days_ago<=15 "
                    "AND o.customer_id NOT IN (SELECT customer_id FROM cases WHERE status='seed_history') "
                    "AND o.id NOT IN (SELECT order_id FROM cases WHERE status!='seed_history') ORDER BY o.id LIMIT 1", (sku, sku + "-%")).fetchone()
    if row:
        return row[0]
    p = c.execute("SELECT title, price_inr FROM products WHERE sku=?", (sku,)).fetchone()
    n = (c.execute("SELECT MAX(CAST(SUBSTR(id, 5) AS INTEGER)) FROM orders WHERE id LIKE 'SHP-%'").fetchone()[0] or 2000) + 1
    c.execute("INSERT INTO customers (id, name) VALUES (?, ?)", (f"DEMO-C-{n}", "Demo shopper"))
    c.execute("INSERT INTO orders (id, customer_id, item, amount_inr, delivered_days_ago, item_sku, delivered_at, source) VALUES (?,?,?,?,?,?,?,?)",
              (f"SHP-{n}", f"DEMO-C-{n}", p["title"], p["price_inr"], 1, sku, db.now()[:10], "demo-store"))
    return f"SHP-{n}"


def _run_all():
    with db.conn() as c:
        skus = [r[0] for r in c.execute("SELECT sku FROM products ORDER BY season, sku")]
    SIM.update(running=True, filed=0, total=len(skus), phase="One return on every product", message="")
    try:
        for i, sku in enumerate(skus):
            if _stop.is_set():
                return
            with db.conn() as c:
                oid = _order_for(c, sku)
            _file(oid, _ALL_REASONS[i % len(_ALL_REASONS)], None)
            SIM["filed"] = i + 1
            if _stop.wait(1.2):
                return
        SIM["phase"] = "done"
    finally:
        SIM["running"] = False
        if SIM["phase"] != "done":
            SIM["phase"] = "stopped"


def start_all() -> dict:
    if SIM["running"]:
        return {"ok": False, "error": "already running"}
    _stop.clear()
    clear_sim()
    threading.Thread(target=_run_all, daemon=True).start()
    return {"ok": True}
