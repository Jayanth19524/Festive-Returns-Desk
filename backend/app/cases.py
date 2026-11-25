"""Case lifecycle: create (decide + log) and execute (issue / hold / reject). All rules live in risk.py."""
import json, time
from datetime import datetime
from . import db, flags, risk, nudgebee

# Spoken replies per decision. Short on purpose. (Machine-written translations: a native speaker should review them.)
REPLIES = {
    "approve": {
        "gu-IN": "તમારું રિફંડ મંજૂર થઈ ગયું છે.", "hi-IN": "आपका रिफंड मंज़ूर हो गया है।",
        "kn-IN": "ನಿಮ್ಮ ರಿಫಂಡ್ ಅನುಮೋದನೆಯಾಗಿದೆ.", "en-IN": "Your refund is approved."},
    "hold": {
        "gu-IN": "તમારી વિનંતી માલિકની સમીક્ષા માટે રાખી છે. અમે જલ્દી જણાવીશું.",
        "hi-IN": "आपका अनुरोध मालिक की समीक्षा के लिए रखा गया है। हम जल्द बताएंगे।",
        "kn-IN": "ನಿಮ್ಮ ವಿನಂತಿಯನ್ನು ಮಾಲೀಕರ ಪರಿಶೀಲನೆಗೆ ಇಡಲಾಗಿದೆ. ನಾವು ಶೀಘ್ರದಲ್ಲೇ ತಿಳಿಸುತ್ತೇವೆ.",
        "en-IN": "Your request is held for the owner's review. We will tell you soon."},
    "reject": {
        "gu-IN": "માફ કરશો, આ રિટર્ન અમારી નીતિ મુજબ સ્વીકારી શકાય તેમ નથી.",
        "hi-IN": "क्षमा करें, यह रिटर्न हमारी नीति के अनुसार स्वीकार नहीं किया जा सकता।",
        "kn-IN": "ಕ್ಷಮಿಸಿ, ಈ ರಿಟರ್ನ್ ನಮ್ಮ ನೀತಿಯ ಪ್ರಕಾರ ಸ್ವೀಕರಿಸಲಾಗುವುದಿಲ್ಲ.",
        "en-IN": "Sorry, this return cannot be accepted under our policy."},
}


def evaluate(c, case: dict, cfg: dict, exclude_case_id=None) -> dict:
    """Look up facts in OUR database, then apply the deterministic rule."""
    order = c.execute("SELECT * FROM orders WHERE id=?", (case.get("order_id"),)).fetchone()
    order = dict(order) if order else None
    if order is None:
        return risk.decide(case, None, 0, False, cfg), None
    already = c.execute("SELECT 1 FROM cases WHERE order_id=? AND status!='seed_history' AND id IS NOT ?",
                        (order["id"], exclude_case_id)).fetchone() is not None
    n = db.returns_30d(c, order["customer_id"])
    return risk.decide(case, order, n, already, cfg), order


def _ms(t0):
    return round((time.perf_counter() - t0) * 1000, 1)


def create_case(case: dict, transcript: str = "", language: str = "hi-IN", trace: list | None = None) -> dict:
    """`trace` carries the timed steps that happened before this call (speech-to-text, extraction)."""
    trace = list(trace or [])
    t0 = time.perf_counter()
    live = flags.load()
    trace.append({"stage": "flags", "who": "flagsmith", "ms": _ms(t0), "ok": live["live"], "detail": live["status"], "data": live["cfg"]})
    t0 = time.perf_counter()
    with db.conn() as c:
        res, order = evaluate(c, case, live["cfg"])
        trace.append({"stage": "decide", "who": "ours", "ms": _ms(t0), "detail": f"{res['decision']} (score {res['score']:g})",
                      "data": {"decision": res["decision"], "score": res["score"], "reasons": res["reasons"]}})
        cur = c.execute(
            "INSERT INTO cases (order_id,customer_id,created_at,transcript,language,reason_category,claimed_condition,"
            "decision,score,reasons,flags_in_effect,signed_approval_required,status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (case.get("order_id"), order["customer_id"] if order else None, db.now(), transcript, language,
             case["reason_category"], case["claimed_condition"], res["decision"], res["score"], json.dumps(res["reasons"]),
             json.dumps({"cfg": live["cfg"], "source": live["status"]}), int(res["signed_approval_required"]), "awaiting_workflow"))
        cid = cur.lastrowid
        db.log_event(c, cid, "intake", f"fields from speech: {json.dumps(case, ensure_ascii=False)}")
        db.log_event(c, cid, "decision", f"{res['decision']} (score {res['score']:g}); " + "; ".join(res["reasons"]))
        db.log_event(c, cid, "flags_in_effect", json.dumps(live["cfg"]))
    t0 = time.perf_counter()
    out = nudgebee.dispatch(cid, res, order, language)  # hands execution to the NudgeBee workflow
    trace.append({"stage": "dispatch", "who": "nudgebee", "ms": _ms(t0), "ok": out["sent"], "detail": out["detail"]})
    with db.conn() as c:
        c.execute("UPDATE cases SET trace=? WHERE id=?", (json.dumps(trace), cid))
        db.log_event(c, cid, "nudgebee_dispatch", out["detail"])
        if not out["sent"]:
            # No workflow means nothing executes; a held case waits for the owner, others wait for the workflow.
            if res["decision"] != "approve":
                c.execute("UPDATE cases SET status=? WHERE id=?", ("held" if res["decision"] == "hold" else "rejected", cid))
        return get(c, cid)


def get(c, cid):
    r = c.execute("SELECT * FROM cases WHERE id=?", (cid,)).fetchone()
    if not r:
        return None
    d = db.row(r)
    d["events"] = [dict(e) for e in c.execute("SELECT at,step,detail FROM events WHERE case_id=? ORDER BY id", (cid,))]
    o = c.execute("SELECT * FROM orders WHERE id=?", (d["order_id"],)).fetchone()
    d["order"] = dict(o) if o else None
    d["refund"] = dict(x) if (x := c.execute("SELECT * FROM refunds WHERE case_id=?", (cid,)).fetchone()) else None
    return d


def execute(cid: int, action: str, by: str = "nudgebee-workflow") -> dict:
    """Called back by the NudgeBee workflow. It does NOT trust the workflow's word: the stored decision is checked
    again and the freeze flag is re-read live, so a stale or forged call cannot issue a refund."""
    live = flags.load()
    with db.conn() as c:
        case = get(c, cid)
        if not case or not case["order"] or case["status"] == "seed_history":
            return {"ok": False, "error": "case not found"}
        if case["refund"]:
            return {"ok": True, "status": case["status"], "note": "already refunded"}
        if action == "refund":
            if case["decision"] != "approve":
                db.log_event(c, cid, "refund_blocked", f"stored decision is {case['decision']}, not approve")
                return {"ok": False, "error": "decision is not approve"}
            if not live["cfg"]["refunds_enabled"]:
                c.execute("UPDATE cases SET status='held' WHERE id=?", (cid,))
                db.log_event(c, cid, "refund_blocked", "freeze switch is ON at execution time; case held")
                return {"ok": False, "status": "held", "error": "refunds frozen"}
            c.execute("INSERT INTO refunds (case_id,amount_inr,issued_at,issued_by) VALUES (?,?,?,?)",
                      (cid, case["order"]["amount_inr"], db.now(), by))
            c.execute("UPDATE cases SET status='approved_refunded' WHERE id=?", (cid,))
            db.log_event(c, cid, "refund_issued", f"₹{case['order']['amount_inr']:g} recorded in ledger by {by} (simulated payout)")
            return {"ok": True, "status": "approved_refunded"}
        if action in ("hold", "reject"):
            status = "held" if action == "hold" else "rejected"
            if case["decision"] != action:
                db.log_event(c, cid, "callback_mismatch", f"workflow asked {action}, stored decision is {case['decision']}; ignored")
                return {"ok": False, "error": "decision mismatch"}
            c.execute("UPDATE cases SET status=? WHERE id=?", (status, cid))
            db.log_event(c, cid, f"case_{status}", f"set by {by}")
            return {"ok": True, "status": status}
    return {"ok": False, "error": "unknown action"}


# Fixed demo scenarios for the live decision panel: each re-decided with the CURRENT Flagsmith values.
SCENARIOS = [
    ("GRD-1001", "wrong_size", "unworn", "Wrong size, unworn, ₹1,800"),
    ("GRD-1002", "worn_once", "worn", "Worn once at garba, ₹5,500"),
    ("GRD-1003", "damaged", "damaged", "Damaged saree, ₹2,400"),
    ("GRD-1004", "changed_mind", "unworn", "Changed mind, bridal lehenga ₹14,500"),
    ("GRD-1005", "wrong_size", "unworn", "Wrong size, 2 earlier returns, ₹1,200"),
    ("GRD-1007", "worn_once", "worn", "Worn, 3 earlier returns, ₹3,200"),
]


def panel() -> dict:
    live = flags.load()
    rows = []
    with db.conn() as c:
        for oid, reason, cond, label in SCENARIOS:
            o = c.execute("SELECT * FROM orders WHERE id=?", (oid,)).fetchone()
            case = {"order_id": oid, "reason_category": reason, "claimed_condition": cond}
            n = db.returns_30d(c, o["customer_id"])
            res = risk.decide(case, dict(o), n, False, live["cfg"])  # "what would happen if this came in now"
            rows.append({"order_id": oid, "label": label, **res})
    return {"config": live["cfg"], "status": live["status"], "live": live["live"], "flags": live["flags"], "scenarios": rows}


def owner_decide(cid: int, action: str, signed: bool = False) -> dict:
    """Owner clicks Approve / Reject on a HELD case. Refunds above hold_above_inr need a signed (Touch ID) approval,
    which is NOT built yet (README: Phase 5 skipped), so those stay held and say why."""
    live = flags.load()
    with db.conn() as c:
        case = get(c, cid)
        if not case or case["status"] != "held":
            return {"ok": False, "error": "only held cases can be decided by the owner"}
        if action == "reject":
            c.execute("UPDATE cases SET status='rejected' WHERE id=?", (cid,))
            db.log_event(c, cid, "owner_rejected", "owner rejected the held case")
            return {"ok": True, "status": "rejected"}
        if case["signed_approval_required"] and not signed:
            db.log_event(c, cid, "owner_approve_blocked", "amount is above the hold limit: needs a signed Touch ID approval ; nothing refunded")
            return {"ok": False, "error": "signed approval required (Touch ID)"}
        if not live["cfg"]["refunds_enabled"]:
            db.log_event(c, cid, "owner_approve_blocked", "refunds are frozen")
            return {"ok": False, "error": "refunds frozen"}
        c.execute("INSERT INTO refunds (case_id,amount_inr,issued_at,issued_by) VALUES (?,?,?,?)",
                  (cid, case["order"]["amount_inr"], db.now(), "owner (Touch ID)" if signed else "owner"))
        c.execute("UPDATE cases SET status='approved_refunded' WHERE id=?", (cid,))
        db.log_event(c, cid, "refund_issued", f"₹{case['order']['amount_inr']:g} recorded in ledger, approved by owner{' with Touch ID' if signed else ''} (simulated payout)")
        return {"ok": True, "status": "approved_refunded"}


def add_trace(cid: int, step: dict) -> None:
    """Append one timed step (used for the spoken reply, which happens after the case exists)."""
    with db.conn() as c:
        row = c.execute("SELECT trace FROM cases WHERE id=?", (cid,)).fetchone()
        steps = json.loads(row[0] or "[]") + [step]
        c.execute("UPDATE cases SET trace=? WHERE id=?", (json.dumps(steps), cid))


def _t(iso):
    return datetime.fromisoformat(iso).timestamp()


def steps(cid: int) -> dict | None:
    """The case as an ordered list of pipeline steps, for the live architecture page.
    Timed steps come from the stored trace; the NudgeBee and owner steps come from the event log."""
    with db.conn() as c:
        case = get(c, cid)
    if not case:
        return None
    tr = {t["stage"]: t for t in (case["trace"] or [])}
    ev = case["events"]
    first = lambda *names: next((e for e in ev if e["step"] in names), None)
    out = []
    if "extract" in tr:
        voice = "stt" in tr
        out.append({"key": "voice", "who": "customer", "title": "Customer speaks" if voice else "Customer message received", "ms": None,
                    "detail": "Return reason recorded on the customer screen (up to 30 s)." if voice else "A typed message (no audio) went through the same understanding step."})
        if voice:
            out.append({"key": "stt", "who": "sarvam", "title": "Speech to text · Saaras v4", "ms": tr["stt"]["ms"],
                        "detail": f"Heard ({tr['stt'].get('lang') or '?'}): {case['transcript']}"})
        out.append({"key": "extract", "who": "sarvam", "title": "Understand · Sarvam 105B", "ms": tr["extract"]["ms"],
                    "detail": f"Extracted only: order {case['order_id']}, reason {case['reason_category']}, condition {case['claimed_condition']}. Text said: {case['transcript'][:140]}. It cannot decide a refund."})
    else:
        out.append({"key": "voice", "who": "customer", "title": "Return filed", "ms": None,
                    "detail": f"Structured case filed without voice: {case['reason_category']} on {case['order_id']}."})
    f = tr.get("flags")
    out.append({"key": "flags", "who": "flagsmith", "title": "Read live rules · Flagsmith", "ms": f["ms"] if f else None,
                "detail": (f["detail"] + ". Thresholds: " + ", ".join(f"{k}={v}" for k, v in f["data"].items())) if f else ""})
    d = tr.get("decide")
    out.append({"key": "decide", "who": "ours", "title": "Decide · risk.py (plain code)", "ms": d["ms"] if d else None,
                "detail": f"{case['decision'].upper()} (score {case['score']:g}). " + "; ".join(case["reasons"])})
    dp = tr.get("dispatch")
    t_dispatch = _t(first("nudgebee_dispatch")["at"]) if first("nudgebee_dispatch") else None
    out.append({"key": "dispatch", "who": "nudgebee", "title": "Start workflow · NudgeBee webhook", "ms": dp["ms"] if dp else None,
                "detail": dp["detail"] if dp else ""})
    v = first("workflow_validate")
    if v:
        out.append({"key": "wf_validate", "who": "nudgebee", "title": "Workflow validates · calls back", "ms": round((_t(v["at"]) - t_dispatch) * 1000) if t_dispatch else None,
                    "detail": "NudgeBee asked our API (Bearer token, via the guarded tunnel): " + v["detail"]})
    a = next((e for e in ev if e["step"] in ("case_held", "case_rejected", "refund_blocked", "callback_mismatch")
              or (e["step"] == "refund_issued" and "nudgebee" in e["detail"])), None)
    if a:
        out.append({"key": "wf_action", "who": "nudgebee", "title": "Workflow routes · switch + callback",
                    "ms": round((_t(a["at"]) - t_dispatch) * 1000) if t_dispatch else None, "detail": a["step"].replace("_", " ") + ": " + a["detail"]})
    o = first("owner_rejected") or next((e for e in reversed(ev) if e["step"] == "refund_issued" and "owner" in e["detail"]), None)
    if o:
        out.append({"key": "owner", "who": "owner", "title": "Owner decides" + (" · Touch ID" if "Touch ID" in o["detail"] else ""), "ms": None, "detail": o["detail"]})
    tt = tr.get("tts")
    if tt:
        out.append({"key": "tts", "who": "sarvam", "title": "Spoken reply · Bulbul v4 Flash", "ms": tt["ms"], "detail": tt["detail"]})
    return {"case_id": cid, "order_id": case["order_id"], "decision": case["decision"], "status": case["status"], "steps": out}
