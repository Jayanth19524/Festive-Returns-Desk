// Runs on the shop (customers) and on the Shopify admin (the owner).
const APP = "http://localhost:5174";   // where the Festive Returns Desk web app runs
const isAdmin = location.hostname === "admin.shopify.com";

function pill(text, href, bottom, color) {
  const a = document.createElement("a");
  a.href = href; a.target = "_blank"; a.rel = "noopener"; a.textContent = text;
  Object.assign(a.style, { position: "fixed", right: "16px", bottom, zIndex: 2147483647, background: color, color: "#fff", padding: "12px 18px",
    borderRadius: "999px", font: "600 14px system-ui, sans-serif", textDecoration: "none", boxShadow: "0 6px 18px rgba(59,22,54,.35)" });
  document.body.appendChild(a);
  return a;
}

if (isAdmin) {
  // Owner view: a live badge with what needs a decision. Click to open the Returns Desk.
  const badge = pill("Returns Desk …", `${APP}/#/desk`, "16px", "#3b1636");
  const refresh = () => chrome.runtime.sendMessage({ type: "stats" }, (r) => {
    if (!r || !r.ok) { badge.textContent = "Returns Desk (offline)"; return; }
    const n = r.stats.by_status.held || 0;
    badge.textContent = n ? `Returns Desk · ${n} need you` : "Returns Desk · all clear";
    badge.style.background = n ? "#8a5a12" : "#1f7a4d";
  });
  refresh(); setInterval(refresh, 5000);
} else {
  // Customer view: a 'Start a return' button on every page of the store. If the page is an order page we pass the order number along.
  const m = location.href.match(/#?(?:order|orders)[\/=#-]*(\d{4,})/i) || document.body.innerText.match(/Order\s*#\s*(\d{4,})/i);
  const link = `${APP}/#/customer${m ? "/SHP-" + m[1] : ""}`;
  pill("↩ Start a return", link, "16px", "#b8923a");
}
