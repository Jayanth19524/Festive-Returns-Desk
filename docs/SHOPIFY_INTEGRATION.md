# Shopify integration: handoff for the teammate

You are building the **Shopify side**. The other teammate builds the **seller dashboard** in the same repo. This file is the
contract between the two so you can work separately. Read it fully, then read `README.md` once.

Repo: https://github.com/Jayanth19524/Festive-Returns-Desk (public). Clone it and work on a branch (`shopify`), not on `main`.

## 1. What the product is (one paragraph)
**Festive Returns Desk** is an *add-on* for small sellers' existing stores (Instagram, WhatsApp, Shopify), not a standalone shop.
It takes a customer's return (spoken in their language), decides refund / hold / reject with deterministic code, runs the refund
through a NudgeBee workflow, and shows the seller *why* customers return and what to fix. Shopify is the first store we connect.
**It is festival-agnostic**: garba / Navratri is only the demo example. Nothing you write may hard-code garba. The current season is
the env var `FESTIVE_SEASON` (Diwali, Eid, Christmas, Pongal...), and products carry a season tag.

## 2. Hard rules (from the hackathon brief and the owner)
- **All data in the demo is SIMULATED.** Use a Shopify development store / fake products and fake customers. Label them as demo data. No real customers, no real money.
- **Do NOT invent Shopify API details.** Read Shopify's official docs before using any endpoint, webhook, scope or SDK, and write what you found in your PR
  (links + the exact calls you use). If a doc is unclear, say so and ask; do not guess. Nothing in this file is a verified Shopify fact.
- **Refund decisions stay in `backend/app/risk.py`** (deterministic). An LLM may only *extract* fields from text. Never let Shopify data or any model output
  decide a refund by itself.
- **Ask before adding a dependency** that is not already in `requirements.txt` / `frontend/package.json`.
- **No secrets in git.** Shopify tokens go in `.env` (gitignored); add the *names* (not values) to `.env.example`.
- Keep files small and readable; the owner must be able to explain every file.
- Sponsors used by the whole app: Sarvam (voice + extraction), Flagsmith (live thresholds), NudgeBee (workflow). You do not have to touch them, but do not break them.

## 3. What already exists (you can call it today)
Backend is FastAPI + SQLite (`backend/app/`). Run it: `.venv/bin/uvicorn backend.app.main:app --port 8200` (setup in README).

| Route | Purpose |
|---|---|
| `POST /api/cases` | File a return from structured data: `{order_id, reason_category, claimed_condition, transcript?, language?}` -> decision + case |
| `POST /api/intake` | Same, from a spoken audio file (Sarvam) |
| `GET /api/cases`, `GET /api/cases/{id}` | List / read cases (reasons, Flagsmith values at that moment, event timeline) |
| `GET /api/insights` | Return Intelligence: reasons ranked, preventable share, fixes, worst items |
| `GET /api/stats`, `GET /api/panel`, `GET /api/config`, `GET /api/shop` | Dashboard numbers, live decision panel, Flagsmith values, current festive season |
| `POST /api/demo/reset` | Wipes the DB back to the 68 simulated orders (also clears the registered Touch ID key) |

Allowed `reason_category`: `wrong_size`, `worn_once`, `damaged`, `not_as_described`, `changed_mind`, `other`.
Allowed `claimed_condition`: `unworn`, `worn`, `damaged`, `unknown`.

Current tables (`backend/app/db.py`): `customers(id, name)`, `orders(id, customer_id, item, amount_inr, delivered_days_ago)`,
`cases(...)`, `events(...)`, `refunds(...)`. Seed data is fake. Note `orders` has **no product table, no season, no size/measurement fields yet**.

## 4. What you build: the Shopify connector
A small module that gets **products and orders from a Shopify store into our app**, and (optionally) **return reasons back out**.
Put it in a new folder `integrations/shopify/` (Python, so it can reuse our code) with its own short README. Suggested scope, in priority order:

1. **Order sync.** Read orders from a Shopify dev store and upsert them into our `orders`/`customers`.
   Map: Shopify order -> `id` (use a stable prefix, e.g. `SHP-<order number>`), customer -> `customers`, line item title -> `item`,
   total in INR -> `amount_inr`, delivery/fulfilment date -> `delivered_days_ago` (we will move this to a real date; see section 6).
2. **Product sync.** Read products and variants (title, SKU, price, images, tags, sizes) into the proposed `products` table (section 5).
3. **Season tagging.** A product belongs to a festival through a Shopify **tag** or collection (e.g. tag `season:diwali`). Map it to our `season` field.
   Do not hard-code festivals: read whatever tag the seller uses.
4. **Return capture (optional, only if time).** When a customer files a return in our app, optionally write the reason back (tag or note on the Shopify order).
   Confirm in Shopify's docs what is allowed first.
5. **Customer-facing fit assistant on the product page (stretch).** A shareable link or embed that shows the product's warnings and fit notes
   (e.g. "the blouse is fitted: confirm your blouse measurement"). This depends on the Product Intelligence profile (section 5), which the dashboard teammate owns.

Fastest path if Shopify auth is slow: **CSV import** of products and orders using the same mapping, so the loop works without the Shopify API.
Build the CSV path first if you lose more than 20 minutes on Shopify auth, and tell the owner.

## 5. The contract between you and the dashboard (agree on this first)
These ingest endpoints do **not exist yet**. Proposed shapes; the dashboard owner will implement them in `backend/app/main.py` (or you can, in a separate PR, if you agree).
All ingest calls need `Authorization: Bearer <INGEST_API_TOKEN>` (new env var, same pattern as `WORKFLOW_API_TOKEN`).

```
POST /api/ingest/products     body: {"products": [Product, ...]}   (upsert by sku)
POST /api/ingest/orders       body: {"orders":   [Order, ...]}     (upsert by id)

Product = {
  "sku": "LEH-204", "title": "Maroon Bridal Lehenga", "category": "lehenga",   // lehenga | saree | kurta | blouse | other
  "price_inr": 6999, "season": "diwali" | null,
  "image_urls": ["https://..."],
  "sizes": ["S","M","L"],
  "measurements": { "waist_cm": 74, "length_cm": 102, "blouse_bust_cm": 88 },   // any may be missing: missing = a finding for the seller
  "description": "free text from the listing",
  "source": "shopify"
}
Order = {
  "id": "SHP-1042", "customer": {"id": "SHP-C-77", "name": "Simulated customer"},
  "item_sku": "LEH-204", "item": "Maroon Bridal Lehenga", "amount_inr": 6999,
  "delivered_at": "2026-11-20", "source": "shopify"
}
```
Rules: idempotent (same payload twice changes nothing), reject unknown fields politely, never store card or address data (we do not need it).
`Product.measurements` being incomplete is intentional: the dashboard reports "N listings have incomplete sizing" (that is the Return Intelligence "fix" for wrong-size returns).

## 6. Things the dashboard teammate will change (so you are not surprised)
- `orders.delivered_days_ago` becomes a real `delivered_at` date; return window logic stays in `risk.py` (default 15 days, will become an env var).
- A `products` table and a per-product "intelligence profile" (extracted fabric, fit, blouse type, transparency, colour) generated from photos + description,
  reviewed by the seller before publishing. Photo understanding needs a vision model that is **not yet chosen** (sponsor question open): do not build against any model yet.
- `GET /api/insights` will start using `item_sku` and `season` so fixes can name specific products (e.g. "add blouse measurements to these 12 listings").

## 7. Definition of done for your part
- [ ] `integrations/shopify/README.md` says exactly how to connect a dev store (or use the CSV path), with the official-doc links you relied on.
- [ ] One command imports N demo products and orders into a running app, and `GET /api/cases` + `POST /api/cases` work with a synced order id.
- [ ] Re-running the import creates no duplicates.
- [ ] Works for any festival: demonstrate with two different season tags, not only garba.
- [ ] No secrets committed; `.env.example` updated; all demo data labelled SIMULATED.
- [ ] A short PR description: what you built, what you could not verify, and the unclear Shopify points you decided not to guess.

## 8. Honest metric language (important for the pitch)
Do not claim a return was "prevented" just because a customer saw a warning. Report **historical baseline vs later period**, clearly labelled, or leave
"preventable returns" as "awaiting measured results". Illustrative numbers must say "illustrative demo data".

## 9. Who to ask
The owner (repo owner) decides scope and any new dependency or model. Questions about the return decision, Flagsmith or NudgeBee: read `README.md` and
`docs/NUDGEBEE.md`; do not change `backend/app/risk.py`, `cases.py` execution paths, or `nudgebee/` without asking.
