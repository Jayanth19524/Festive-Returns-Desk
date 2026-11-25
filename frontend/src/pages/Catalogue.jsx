import { useContext, useState } from "react";
import usePoll from "../usePoll.js";
import { Button, Card, SectionTitle, ShopContext, inr } from "../ui.jsx";

const SEASON_COLOR = { diwali: "bg-amber-100 text-amber-800", navratri: "bg-fuchsia-100 text-fuchsia-800", eid: "bg-emerald-100 text-emerald-800",
  pongal: "bg-orange-100 text-orange-800", christmas: "bg-red-100 text-red-800" };
const TILE = ["from-plum to-plum-3", "from-gold to-warn", "from-plum-2 to-gold", "from-plum-3 to-plum"];

// The synced store: listings with how complete their size information is, and what returned. Plus personal return links for orders.
export default function Catalogue() {
  const { data } = usePoll("/api/catalogue", 4000);
  const { data: orders } = usePoll("/api/orders?limit=12", 6000);
  const shop = useContext(ShopContext);
  const [season, setSeason] = useState("all");
  const [msg, setMsg] = useState("");
  const sync = async () => {
    setMsg("Syncing…");
    const r = await fetch(shop.shopify_configured ? "/api/shopify/sync" : "/api/demo/shopify-sync", { method: "POST" });
    const j = await r.json().catch(() => ({}));
    setMsg(r.ok ? (shop.shopify_configured ? "Synced from your Shopify store." : "Loaded the demo store.") : (j.detail || "Sync failed"));
  };
  const link = (id) => `${location.origin}/#/customer/${id}`;
  const copy = (id) => navigator.clipboard?.writeText(link(id)).then(() => setMsg(`Copied return link for ${id}`));

  if (!data) return <p className="text-muted">Loading…</p>;
  const list = data.listings.filter((v) => season === "all" || v.season === season);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="display text-3xl font-semibold text-plum">Store catalogue</h1>
          <p className="text-muted">{shop.data_source === "live" ? `Listings synced from ${shop.store}` : "Demo store data"}, and which ones are causing returns.</p>
        </div>
        <Button kind="primary" onClick={sync}>{shop.shopify_configured ? "⟳ Sync my Shopify store" : "⟳ Load demo store"}</Button>
      </div>
      {msg && <p className="rounded-xl bg-gold-soft px-3 py-2 text-sm text-warn">{msg}</p>}

      {!data.total ? (
        <Card className="p-8 text-center"><p className="display text-xl text-plum">No store connected yet</p>
          <p className="mt-1 text-muted">Connect your Shopify store (see integrations/shopify/README.md), or press the button to load the demo festive boutique.</p></Card>
      ) : (
        <>
          <div className="grid grid-cols-3 gap-3">
            <Card className="p-4"><p className="text-xs uppercase tracking-wide text-muted">Listings</p><p className="display num text-3xl font-semibold text-plum">{data.total}</p></Card>
            <Card className="p-4"><p className="text-xs uppercase tracking-wide text-muted">Without measurements</p><p className="display num text-3xl font-semibold text-warn">{data.incomplete}</p></Card>
            <Card className="p-4"><p className="text-xs uppercase tracking-wide text-muted">Festive seasons</p><p className="display num text-3xl font-semibold text-plum">{data.seasons.length}</p></Card>
          </div>

          <div className="flex flex-wrap gap-2">
            {["all", ...data.seasons].map((s) => (
              <button key={s} onClick={() => setSeason(s)} className={`rounded-full px-3.5 py-1.5 text-sm font-semibold capitalize ${season === s ? "bg-plum text-white" : "border border-line bg-paper"}`}>{s}</button>
            ))}
          </div>

          <div className="grid gap-3 md:grid-cols-2">
            {list.map((v, i) => (
              <Card key={v.sku} className={`flex gap-3 p-3 ${v.missing_measurements && v.size_returns ? "border-warn/40" : ""}`}>
                <div className={`flex h-20 w-16 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br ${TILE[i % TILE.length]} text-xs font-semibold text-white/90`}>{v.category}</div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-start justify-between gap-2"><p className="truncate font-semibold">{v.title}</p><p className="num font-semibold">{inr(v.price_inr)}</p></div>
                  <div className="mt-0.5 flex flex-wrap items-center gap-1.5 text-xs">
                    <span className="font-mono text-muted">{v.sku}</span>
                    {v.season && <span className={`rounded-full px-2 py-0.5 font-semibold capitalize ${SEASON_COLOR[v.season] || "bg-line"}`}>{v.season}</span>}
                    <span className="text-muted">{v.sizes.join(" · ")}</span>
                  </div>
                  <p className={`mt-1.5 text-xs font-semibold ${v.missing_measurements ? "text-warn" : "text-ok"}`}>
                    {v.missing_measurements ? "⚠ No garment measurements" : "✓ " + Object.entries(v.measurements).map(([k, x]) => `${k.replace("_cm", "").replace("_m", "").replace("_", " ")} ${x}`).join(" · ")}
                  </p>
                  <div className="mt-1.5 flex items-center gap-2 text-xs text-muted">
                    <span className="num">{v.orders} orders · {v.returns} returned</span>
                    {v.size_returns > 0 && <span className="rounded-md bg-bad-bg px-1.5 py-0.5 font-semibold text-bad">{v.size_returns} wrong size</span>}
                  </div>
                </div>
              </Card>
            ))}
          </div>

          <section>
            <SectionTitle hint="send to the customer in the order email, WhatsApp or Instagram">Personal return links</SectionTitle>
            <Card className="divide-y divide-line">
              {(orders || []).filter((o) => !o.returned).slice(0, 8).map((o) => (
                <div key={o.id} className="flex flex-wrap items-center gap-2 px-4 py-2.5 text-sm">
                  <span className="font-mono text-xs text-muted">{o.id}</span><span className="min-w-40 flex-1">{o.item}</span>
                  <span className="num text-muted">{inr(o.amount_inr)} · delivered {o.delivered_days_ago}d ago</span>
                  <Button className="!px-2.5 !py-1 text-xs" onClick={() => copy(o.id)}>Copy link</Button>
                  <a className="text-xs font-semibold text-plum-3" href={`#/customer/${o.id}`}>Open →</a>
                </div>
              ))}
            </Card>
          </section>
        </>
      )}
    </div>
  );
}
