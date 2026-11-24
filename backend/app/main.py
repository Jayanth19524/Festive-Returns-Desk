"""FastAPI app for Garba Returns Desk. All data is SIMULATED."""
import base64, hmac, os
from fastapi import Depends, FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from . import cases, db, flags, languages, sarvam_service as sv
from . import config  # noqa: F401

app = FastAPI(title="Garba Returns Desk (SIMULATED data)")
db.init()


@app.middleware("http")
async def tunnel_guard(request: Request, call_next):
    """Requests that arrive through the public tunnel (cloudflared adds cf-connecting-ip) may ONLY reach the
    NudgeBee callback routes. Voice intake, owner screens and config stay local."""
    if request.headers.get("cf-connecting-ip") and not request.url.path.startswith("/api/workflow/"):
        return JSONResponse({"detail": "not available through the public tunnel"}, status_code=403)
    return await call_next(request)


class CaseIn(BaseModel):
    order_id: str | None = None
    reason_category: str = "other"
    claimed_condition: str = "unknown"
    transcript: str = ""
    language: str = "hi-IN"


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/config")
def get_config():
    """The Flagsmith values in effect right now."""
    return flags.load()


@app.get("/api/panel")
def panel():
    """Live decision panel: fixed demo scenarios re-decided with the current Flagsmith values."""
    return cases.panel()


@app.post("/api/intake")
async def intake(audio: UploadFile = File(...)):
    """Customer's spoken reason -> transcript -> structured case -> decision -> spoken reply."""
    data = await audio.read()
    try:
        transcript, detected = sv.transcribe(data, audio.filename or "audio.webm", audio.content_type or "audio/webm")
        if not transcript:
            raise HTTPException(422, "No speech detected")
        fields = sv.extract(transcript)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"Sarvam call failed: {str(e)[:300]}")
    lang = languages.get(detected)["code"]
    case = cases.create_case(fields, transcript, lang)
    reply = cases.REPLIES[case["decision"]][lang]
    try:
        wav = base64.b64encode(sv.speak(reply, lang)).decode()
    except Exception:
        wav = None  # voice reply is a nice-to-have; the decision stands without it
    return {"transcript": transcript, "detected_language": detected, "fields": fields, "case": case,
            "reply_text": reply, "reply_audio_wav_b64": wav}


@app.post("/api/cases")
def create_case(body: CaseIn):
    """Same as intake but from already-structured text (owner demo, tests, and the prompt-injection demo)."""
    fields = {"order_id": (body.order_id or "").upper() or None, "reason_category": body.reason_category,
              "claimed_condition": body.claimed_condition}
    return cases.create_case(fields, body.transcript, body.language)


@app.get("/api/cases")
def list_cases():
    with db.conn() as c:
        ids = [r[0] for r in c.execute("SELECT id FROM cases WHERE status!='seed_history' ORDER BY id DESC LIMIT 50")]
        return [cases.get(c, i) for i in ids]


@app.get("/api/cases/{cid}")
def one_case(cid: int):
    with db.conn() as c:
        case = cases.get(c, cid)
    if not case:
        raise HTTPException(404, "no such case")
    return case


@app.post("/api/demo/reset")
def reset():
    db.reset()
    return {"ok": True}


# ---- NudgeBee callback (the only route the public tunnel should expose; Bearer token required) ----
def workflow_auth(authorization: str = Header(default="")):
    token = os.getenv("WORKFLOW_API_TOKEN", "")
    if not token or not hmac.compare_digest(authorization, f"Bearer {token}"):
        raise HTTPException(401, "bad or missing workflow token")


@app.post("/api/workflow/cases/{cid}/{action}", dependencies=[Depends(workflow_auth)])
def workflow_callback(cid: int, action: str):
    if action not in ("refund", "hold", "reject"):
        raise HTTPException(404, "unknown action")
    return cases.execute(cid, action)


@app.get("/api/workflow/cases/{cid}/validate", dependencies=[Depends(workflow_auth)])
def workflow_validate(cid: int):
    """Workflow step 1: does the case exist and is it waiting for execution? The decision comes from OUR database."""
    with db.conn() as c:
        case = cases.get(c, cid)
        if not case or case["status"] == "seed_history":
            return {"ok": False, "decision": "invalid", "reason": "case not found"}
        ok = case["status"] == "awaiting_workflow" and not case["refund"]
        db.log_event(c, cid, "workflow_validate", f"ok={ok} decision={case['decision']} status={case['status']}")
        return {"ok": ok, "decision": case["decision"] if ok else "invalid", "status": case["status"],
                "amount_inr": case["order"]["amount_inr"] if case["order"] else 0}


@app.post("/api/cases/{cid}/owner/{action}")
def owner_action(cid: int, action: str):
    """Owner screen buttons. Local only: the tunnel guard blocks this path for outside traffic."""
    if action not in ("approve", "reject"):
        raise HTTPException(404, "unknown action")
    return cases.owner_decide(cid, action)
