# Festive Returns Desk: Chrome extension

Adds our returns desk to a real Shopify store, without changing the store's theme:
- **On the shop (customers):** a gold **"↩ Start a return"** button on every page. On an order page it passes the order number along, so the customer only has to say why.
- **On the Shopify admin (the owner):** a live badge, **"Returns Desk · N need you"**, that opens the Returns desk. Green when nothing is waiting.
- **Toolbar popup:** needs-your-decision count, value waiting, refunded total, and links to the Returns desk and the customer page.

## Install (Chrome)
1. Run the app: API on port 8200 and the web app on 5174 (see the main README).
2. Open `chrome://extensions`, switch on **Developer mode**, click **Load unpacked**, choose this `extension/` folder.
3. Open your Shopify store (`https://<your-store>.myshopify.com`) and your admin (`https://admin.shopify.com/store/<your-store>`).

## Scope and limits (honest)
- It talks to `http://localhost:8200` and links to `http://localhost:5174`, so it works on the machine that runs the app. For other devices, put both behind a public address and change `APP`/`API` at the top of `content.js` and `background.js`.
- The order-number detection on the shop reads the page text ("Order #1042") and is a best-effort guess; if it finds nothing the customer is asked to say the order number.
- Not published to the Chrome Web Store. Not tested against every Shopify theme; the button is a fixed element and should not depend on the theme.
