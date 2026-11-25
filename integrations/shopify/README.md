# Shopify Connector for Festive Returns Desk

Connects small sellers' existing Shopify stores (or offline CSV exports) to **Festive Returns Desk**. It extracts products, sizes, prices, and festival season tags, maps orders to our standardized format (`SHP-<order_number>`), and ingests them idempotently into the database so customers can file return requests via voice or text.

> **SIMULATED DEMO DATA:** All demo products, orders, and customer names used in this module are **SIMULATED**. No real customers, payments, or money are involved.

---

## 1. Quick Start (One Command Sync)

You can run the sync either against a running Festive Returns Desk server or directly into the local SQLite database.

### Option 0: Demo store (what the live demo uses)
A simulated festive boutique with a story: 27 listings across Diwali, Navratri, Eid, Pongal and Christmas, 150 orders, a returns history and a few repeat
returners. Listings without garment measurements are returned for size far more often (simulated, labelled as such). It goes through the real mapper.
```bash
python3 -m integrations.shopify.sync --source demo        # or the "Sync Shopify" button in the app, or "Reset demo data" (which reloads it)
```

### Option A: Mock Mode (Recommended for testing)
Imports pre-packaged simulated products and orders covering both **Diwali** and **Eid** collections:
```bash
# Ingest directly into the database (works without running the backend)
python3 -m integrations.shopify.sync --source mock --dest db

# Or ingest via the running backend HTTP API (default port 8200)
python3 -m integrations.shopify.sync --source mock --dest api
```

### Option B: Offline CSV Mode (Fast Path)
If you do not have live Shopify API credentials, export your products and orders as CSV and run:
```bash
python3 -m integrations.shopify.sync \
  --source csv \
  --products-file integrations/shopify/sample_data/products_sample.csv \
  --orders-file integrations/shopify/sample_data/orders_sample.csv \
  --dest db
```

### Option C: Live Shopify Dev Store
To sync from a real Shopify development store:
1. Ensure `.env` contains:
   ```env
   SHOPIFY_SHOP_DOMAIN=your-dev-store.myshopify.com
   SHOPIFY_ACCESS_TOKEN=shpat_xxxxxxxxxxxxxxxxxxxx
   INGEST_API_TOKEN=your-random-ingest-token
   ```
2. Run:
   ```bash
   python3 -m integrations.shopify.sync --source shopify --dest api
   ```

Re-running any of these commands is strictly **idempotent**: existing items are updated and no duplicate records are created.

---

## 1b. Live Shopify: what is verified and what is not (read before relying on it)
Checked against shopify.dev on the build day (a read of the docs pages, no live store was available):
- **API version:** the old default `2024-01` is no longer supported. Shopify supports each stable version for at least 12 months; supported when checked: `2026-01`, `2026-04`, `2026-07`, `2026-10` (latest). The client now defaults to `2026-04` and reads `SHOPIFY_API_VERSION` from `.env`.
- **REST is legacy:** Shopify marks the REST Admin API as a legacy API (since 1 Oct 2024) and requires GraphQL for NEW public apps. A custom/private app is not covered by that sentence, but a migration to GraphQL is the safer long-term path.
- **Not confirmed in the docs we could read:** `GET products.json` and `orders.json` for the current version, the `shpat_` token format, and `PUT orders/{id}.json` for tags. Also, new admin-created custom apps can no longer be created (new custom apps go through the Dev Dashboard).
- **Never run against a real store here.** The connector's live path (`--source shopify`) is unit-tested only against mapped sample data. Treat it as UNVERIFIED until it has pulled from a real development store.
- **Measurements:** a Shopify product has no measurement field. The mapper reads measurements from the description text (`Waist 74 cm`, `Length 5.5 m`, `Blouse bust 88 cm`) when the product has no `measurements` field. If a seller keeps them in metafields, that needs a small extension.
- **Currency:** prices are taken as INR without checking the order currency.

---

## 2. Official Shopify API Documentation & Endpoints Relied On

We strictly use Shopify's official Admin REST API version `2024-01` via standard library `urllib` (no undocumented endpoints or third-party wrappers):

1. **Authentication:**
   - **Header:** `X-Shopify-Access-Token: <access_token>`
   - **Doc:** [Shopify Custom App Authentication](https://shopify.dev/docs/apps/build/authentication-authorization/access-tokens)

2. **Products Sync:**
   - **Endpoint:** `GET https://{shop}.myshopify.com/admin/api/2024-01/products.json?limit=50`
   - **Scope:** `read_products`
   - **Doc:** [Shopify Admin REST - Product Resource](https://shopify.dev/docs/api/admin-rest/2024-01/resources/product#get-products)
   - **Fields extracted:** `id`, `title`, `product_type`, `body_html`, `tags`, `images.src`, `options[name="Size"].values`, `variants[].sku`, `variants[].price`.

3. **Orders Sync:**
   - **Endpoint:** `GET https://{shop}.myshopify.com/admin/api/2024-01/orders.json?status=any&limit=50`
   - **Scope:** `read_orders`
   - **Doc:** [Shopify Admin REST - Order Resource](https://shopify.dev/docs/api/admin-rest/2024-01/resources/order#get-orders)
   - **Fields extracted:** `id`, `order_number`, `total_price`, `customer.id`, `customer.first_name`, `customer.last_name`, `line_items[0].sku`, `line_items[0].title`, `fulfillments[].updated_at`.
   - **Privacy rule:** Payment details, card numbers, and street addresses are intentionally never parsed or stored.

4. **Return Tag Write-back (Optional):**
   - **Endpoint:** `PUT https://{shop}.myshopify.com/admin/api/2024-01/orders/{order_id}.json`
   - **Scope:** `write_orders`
   - **Doc:** [Shopify Admin REST - Update Order](https://shopify.dev/docs/api/admin-rest/2024-01/resources/order#put-orders-order-id)
   - Appends tags such as `return:wrong_size` or notes to the Shopify order without overwriting existing merchant tags.

---

## 3. Festival-Agnostic Tagging

This module **never hardcodes any festival or season**. Products are associated with festive seasons dynamically via Shopify tags:
* Tag format: `season:<festival_name>` (e.g., `season:diwali`, `season:eid`, `season:pongal`, `season:christmas`).
* The extractor in `integrations/shopify/mapper.py` (`extract_season`) parses whatever season tag the seller assigns.
* Current active store season is configured via `FESTIVE_SEASON` in `.env`.

---

## 4. Contract Schema Alignment

The sync tool maps data to the exact schema agreed with the seller dashboard team:

### Product Contract
```json
{
  "sku": "LEH-204",
  "title": "Maroon Zari Bridal Lehenga (SIMULATED)",
  "category": "lehenga",
  "price_inr": 6999,
  "season": "diwali",
  "image_urls": ["https://..."],
  "sizes": ["S", "M", "L"],
  "measurements": { "waist_cm": 74, "length_cm": 102 },
  "description": "Intricately embroidered velvet lehenga set...",
  "source": "shopify"
}
```

### Order Contract
```json
{
  "id": "SHP-1042",
  "customer": { "id": "SHP-C-72", "name": "Pooja Sharma (SIMULATED)" },
  "item_sku": "LEH-204",
  "item": "Maroon Zari Bridal Lehenga (SIMULATED)",
  "amount_inr": 6999,
  "delivered_at": "2026-11-20",
  "source": "shopify"
}
```

---

## 5. Filing Returns on Synced Orders

Once orders are imported, customer returns work natively with the existing risk engine:

```bash
# File a return for synced order SHP-1041
curl -X POST http://localhost:8200/api/cases \
  -H "Content-Type: application/json" \
  -d '{
    "order_id": "SHP-1041",
    "reason_category": "wrong_size",
    "claimed_condition": "unworn",
    "transcript": "Kurta is too tight around the chest",
    "language": "hi-IN"
  }'
```
`backend/app/risk.py` deterministically evaluates the case based on delivery date, price limit, and customer return history, outputting `approve`, `hold`, or `reject`.

---

## 6. Running Tests

Run the dedicated test suite:
```bash
.venv/bin/python -m unittest integrations.shopify.test_shopify_sync -v
```
All 7 tests verify mapping accuracy, privacy preservation, multi-festival tag extraction, sync idempotency, and return creation.

---

## 7. PR Description Summary

### What Was Built
1. `integrations/shopify/client.py`: Standard library Shopify Admin REST API client for products, orders, and order tagging.
2. `integrations/shopify/mapper.py`: Dynamic mapper converting Shopify payloads/CSVs into contract `Product` and `Order` shapes, extracting `season:*` tags dynamically.
3. `integrations/shopify/sync.py`: Single-command CLI supporting Live Shopify API, offline CSV, and mock JSON datasets.
4. `integrations/shopify/sample_data/`: Simulated datasets for Diwali, Eid, and Pongal demo listings and orders.
5. `integrations/shopify/test_shopify_sync.py`: Automated test suite for idempotency, season neutrality, mapping, and return filing.
6. Ingest endpoints (`POST /api/ingest/products`, `POST /api/ingest/orders`) in `backend/app/main.py` and `db.py` schema with Bearer token authentication.

### What Was Intentionally NOT Guessed
1. **Photo Vision Models:** As noted in the brief, product intelligence / vision model selection is open; we did not bind or assume any vision model.
2. **Shopify GraphQL vs REST:** Kept to the stable Admin REST API `2024-01` to minimize dependency complexity.
3. **Refund Decisions:** Maintained strict boundary — no refund decision logic exists in the Shopify integration; all decisions remain in `backend/app/risk.py`.
