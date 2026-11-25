// Talks to the Festive Returns Desk API. A service worker may call it directly (the page itself could not: CORS / mixed content).
const API = "http://localhost:8200";
chrome.runtime.onMessage.addListener((msg, _sender, reply) => {
  if (msg.type !== "stats") return false;
  Promise.all([fetch(`${API}/api/stats`).then((r) => r.json()), fetch(`${API}/api/shop`).then((r) => r.json())])
    .then(([stats, shop]) => reply({ ok: true, stats, shop }))
    .catch((e) => reply({ ok: false, error: String(e) }));
  return true;  // answer asynchronously
});
