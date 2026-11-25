chrome.runtime.sendMessage({ type: "stats" }, (r) => {
  const el = document.getElementById("body");
  if (!r || !r.ok) { el.innerHTML = "<small>The app is not running. Start it with <code>uvicorn backend.app.main:app --port 8200</code>.</small>"; return; }
  document.getElementById("season").textContent = r.shop.season;
  const s = r.stats, rupee = (n) => "₹" + Number(n).toLocaleString("en-IN");
  el.innerHTML = `<div class="row"><span>Need your decision</span><b>${s.by_status.held || 0}</b></div>
    <div class="row"><span>Waiting</span><b>${rupee(s.held_value_inr)}</b></div>
    <div class="row"><span>Refunded</span><b>${rupee(s.refunded_inr)}</b></div>`;
});
