# Festive Returns Desk

A returns desk for a one-person seller after a festival rush. The demo scenario is ethnic wear after Navratri and garba season; set `FESTIVE_SEASON` in `.env` (Diwali, Eid, Christmas, Pongal...) and the owner screen shows which season is on. A customer **speaks** their return reason in
Gujarati, Hindi or Kannada. The app turns it into a structured case, a **deterministic risk rule** decides
(auto-approve / hold / reject), a **NudgeBee** workflow executes the decision and records every step, and the owner
tunes the thresholds live in **Flagsmith**, including a one-switch refund freeze. Built for Festive Hacks (WeMakeDevs x WeAreDevelopers India).

> **All customers, orders, returns and refunds in this project are SIMULATED seed data.** No real people, payments or
> products are involved, and no money moves. The UI says so too. There are no photos in this version.

## Status: what works, honestly
| Piece | Status |
|---|---|
| Voice intake (Saaras v4 -> Sarvam 105B -> Bulbul v4 Flash) in Gujarati / Hindi / Kannada / English | Works, tested on synthetic audio (see Limitations) |
| Risk rule + live Flagsmith thresholds + freeze switch | Works; a Flagsmith edit changes decisions on screen in ~2 s (tested) |
| Web app (React + Tailwind): command centre, returns desk, return intelligence, live architecture page, customer view, demo controls | Works |
| Demo storefront "Festive Boutique" (`#/shop`): browse festive listings by season, pick a size, place a demo order (no payment), then start a return from the order | Works. It is our own demo store, NOT Shopify. Listings are the same table a Shopify sync fills |
| Photo evidence + AI (IBM Bob): the customer must add a photo; a vision model describes it; findings can only RAISE the risk score. AI action plan on Return intelligence | Code and fake-model tests are done. **Not yet run against the real IBM model** (needs your key; whether the model accepts images is unverified) |
| Return Intelligence (why customers return, what to fix, preventable share) | Works: plain database aggregation and fixed advice text, no LLM |
| NudgeBee workflow | Works: published, run end to end for approve, hold and reject cases through a guarded public tunnel; runs visible in NudgeBee Executions (`docs/NUDGEBEE.md`) |
| Touch ID (WebAuthn) approval for refunds above `hold_above_inr` | Built. Server-side verification is tested with a *software* authenticator (18 unit tests + an HTTP run). A real platform-authenticator registration and approval were also run once in the app's browser pane on the author's Mac (₹14,500 case released, ledger shows "owner (Touch ID)") |

## Who it is for
An **add-on for small sellers' existing stores** (Instagram, WhatsApp, Shopify or their own site), not a standalone shop. It handles the returns side: voice intake, a consistent decision, refund execution and an audit trail, plus Return Intelligence on why customers return. Marketplaces (Amazon, Flipkart, Myntra) run returns and refunds themselves, so this is not for them.

## Sponsors and their roles
| Sponsor | Role in this app |
|---|---|
| **Sarvam AI** | Saaras v4 speech-to-text (language auto-detected), Sarvam 105B turns the transcript into `{order_id, reason_category, claimed_condition, language}`, Bulbul v4 Flash speaks the decision back in the customer's language |
| **Flagsmith** | `refunds_enabled` (freeze switch) plus remote config `auto_refund_limit_inr`, `hold_above_inr`, `max_returns_per_customer_30d`, `wardrobing_keywords_risk_weight`. Read live (1 s cache) |
| **IBM Bob** (extra, not a hackathon sponsor) | Reads the customer's photo and writes the AI action plan. Never decides a refund |
| **NudgeBee** | Webhook-triggered workflow per case: validate, switch (approve / hold / reject), HTTP callback into our app, notify. Every run is visible in its Executions tab |

**Design rule:** the refund decision is plain code (`backend/app/risk.py`), never the LLM. The LLM only extracts fields. NudgeBee orchestrates; it does not score risk.

## Architecture
```
 Customer (browser mic)                         Owner (browser)
        | audio                                      | reads /api/panel, /api/cases (polls every 2 s)
        v                                            v
  FastAPI + SQLite  ------ reads live values ------> Flagsmith (self-hosted, localhost:8000)
   1. Saaras v4 STT  (Sarvam)
   2. 105B -> JSON   (Sarvam)   only extracts fields
   3. risk.py decides           deterministic, logs reasons + Flagsmith values in effect
   4. webhook  --------------------------------->  NudgeBee workflow (self-hosted, localhost:3000)
        ^                                              validate -> switch -> HTTP -> notify
        |   POST /api/workflow/cases/{id}/refund|hold|reject  (Bearer token, via public tunnel)
        +----------------------------------------------+
   5. callback re-checks the stored decision AND the live freeze flag, then writes the refund ledger
   6. Bulbul v4 Flash speaks the decision back
```
UI pages: **Command centre** (what needs you, rules in effect), **Returns desk** (queue + case detail + Touch ID), **Return intelligence**, **How it works** (problem, solution, a live replay of any real case showing which sponsor ran each step and how long it took), **Customer view** (voice), plus floating **Demo controls**.

Files: `backend/app/` (`risk.py` rule, `flags.py` Flagsmith, `webauthn_owner.py` Touch ID check, `sarvam_service.py`, `cases.py` lifecycle, `db.py` schema + seed, `nudgebee.py` webhook client, `main.py` routes), `frontend/src/` (`Owner.jsx`, `Customer.jsx`), `nudgebee/garba-return-desk.json` (imported as `garba-return-desk-final`), `scripts/`.

## Setup
Needs Python 3.11, Node 18+, Docker. Replace paths as needed.
1. `cp .env.example .env` and fill it in (never commit `.env`). Generate `WORKFLOW_API_TOKEN` with `openssl rand -hex 24`.
2. **Flagsmith**: if one is already on port 8000, reuse it. Otherwise `docker compose up -d`, open http://localhost:8000, sign up, create a project and environment, and copy the Server-side Environment Key and (for seeding only) an API token into `.env`.
3. Create the flags: `python3 scripts/seed_flagsmith.py` (idempotent).
4. Backend: `python3.11 -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/uvicorn backend.app.main:app --port 8200`
5. Frontend: `cd frontend && npm install && npm run dev` then open http://localhost:5174 (owner) and http://localhost:5174/#/customer. `localhost` is required for the microphone.
6. **NudgeBee**: follow `docs/NUDGEBEE.md` (self-hosted Community, integration, secret, import `nudgebee/garba-return-desk.json` (imported as `garba-return-desk-final`), public tunnel). Then `bash scripts/fire_webhook.sh`.
7. Check services: `python3 scripts/check_services.py`. Tests: `.venv/bin/python -m unittest backend.tests_risk backend.tests_webauthn -v`.

Simulate a returns surge (60 simulated orders, real NudgeBee runs, optional real voice): `.venv/bin/python scripts/simulate_surge.py --n 40 --voice 4`. A 20-return run settled in 19 s (4 auto-approved, 10 held, 6 rejected).

Public tunnel for NudgeBee: `./scripts/tunnel.sh` (quick tunnels drop and get a new address; run it again, no API restart needed).

Change a value live: Flagsmith dashboard (or `python3 scripts/set_flag.py auto_refund_limit_inr 1000`, `python3 scripts/set_flag.py refunds_enabled off`).

## Limitations (honest)
- **Voice accuracy is only lightly tested.** The three test phrases (Gujarati, Hindi, Kannada; `scripts/test_intake.py`) used synthetic Bulbul audio, which is cleaner than real phone audio. All 9 extracted fields were right, but that is 3 samples. Spoken order IDs over noise are the weak spot; unknown IDs are rejected by the rule, not guessed.
- The LLM can be talked into **extracting** a field wrongly (e.g. "unworn" for a worn item). That can only lower the risk score for a case whose amount is still capped by `auto_refund_limit_inr`; it cannot lift the cap, skip the freeze switch, or approve above the limit. Photos/evidence are not implemented.
- **Touch ID (WebAuthn):** verified server-side with the `cryptography` package (challenge, origin, rpIdHash, user-verified flag, ES256 signature, counter). Attestation is not checked and the first key registered from the local machine is trusted. Challenges live in memory, so a server restart invalidates pending ones. The relying-party id is `localhost`, so it works on `localhost` only (no tunnel needed; do not use the tunnel URL for the owner screen). Tested on one Mac only.
- Spoken replies in Gujarati/Hindi/Kannada are short machine-written sentences. A native speaker should review them.
- The refund ledger is a database table; nothing is paid out. Flagsmith's freeze is flipped in its dashboard (the owner screen shows it and links there).
- NudgeBee: the brief's `Inputs.webhook_json` was empty on the tested install; we parse `Inputs.webhook_payload` with a JSONata `data.transform` instead. Its HTTP task refuses private IPs, so a public tunnel (guarded: only `/api/workflow/*` with a Bearer token) is required.
- Who it is for: sellers who control their own refunds (own website, Instagram, WhatsApp). On Amazon, Flipkart or Myntra the marketplace runs returns and pays refunds, so this cannot plug into them (to our understanding; check each platform's policy). It could only help a marketplace seller decide which returns to dispute.

## AI assistance disclosure
This project was built with **Claude Code** (Anthropic's AI coding assistant) working with the author. Claude Code wrote and edited the code, scripts and docs under the author's direction and ran the tests described here; the author is responsible for the result. Sponsor APIs were checked against their official documentation. The product's refund decisions are made by deterministic code, not by an LLM.

## Demo product images
Eleven demo listings show product photos that are **hotlinked** (not downloaded or redistributed) from the shops that host them: elanstore.in, Myntra, Etsy, Saira's Boutique, bindyaa.com, arabicattire.com, arrssilks.com, keraloom.in, princenprincess.in, ramrajcotton.in. Credit to those shops; used for a hackathon demo only. A dead or blocked link falls back to a gradient tile, as do the listings without a link.
