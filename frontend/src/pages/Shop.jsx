import { useEffect, useState } from "react";
import usePoll from "../usePoll.js";
import { Button, Card, inr } from "../ui.jsx";

// "Festive Boutique": the demo storefront a shopper sees. Listings come from the same table a Shopify sync fills. No payments.
const SEASON = {
  diwali: ["Diwali", "🪔", "from-amber-500 to-orange-700"], navratri: ["Navratri", "💃", "from-fuchsia-600 to-purple-800"],
  eid: ["Eid", "🌙", "from-emerald-600 to-teal-800"], pongal: ["Pongal", "🌾", "from-orange-500 to-red-700"], christmas: ["Christmas", "🎄", "from-red-600 to-green-800"],
};
const mine = () => { try { return JSON.parse(localStorage.getItem("frd_orders") || "[]"); } catch { return []; } };
const remember = (id) => { try { localStorage.setItem("frd_orders", JSON.stringify([id, ...mine().filter((x) => x !== id)].slice(0, 20))); } catch { /* private mode: fine */ } };
const labelM = (k) => k.replace("_cm", " (cm)").replace("_m", " (m)").replaceAll("_", " ");

export function StoreShell({ children, season }) {
  const shop = usePoll("/api/shop", 30000).data || {};
  return (
    <div className="min-h-screen bg-ivory">
      <div className="bg-gold-soft px-4 py-1.5 text-center text-xs font-semibold text-warn">Demo store · no real payments or deliveries</div>
      <header className="bg-plum text-ivory">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-4">
          <a href="#/shop" className="display text-2xl font-semibold">Festive Boutique</a>
          <nav className="flex items-center gap-4 text-sm">
            <a href="#/shop" className="hover:text-gold-soft">Shop</a><a href="#/shop/orders" className="hover:text-gold-soft">My orders</a>
            <a href="#/" className="rounded-full bg-white/15 px-3 py-1 text-xs">Owner view →</a>
          </nav>
        </div>
        {season !== false && <div className="mx-auto max-w-6xl px-4 pb-4 text-sm text-gold-soft">🪔 Now: {shop.season || "festive season"}. Free returns within 15 days.</div>}
      </header>
      <main className="mx-auto max-w-6xl p-4 lg:p-8">{children}</main>
      <footer className="mx-auto max-w-6xl px-4 pb-10 text-xs text-muted">Returns by Festive Returns Desk: speak in your own language, get a clear answer.</footer>
    </div>
  );
}

function Tile({ p, big }) {
  const [name, icon, grad] = SEASON[p.season] || ["Festive", "✨", "from-plum to-plum-3"];
  return (
    <div className={`relative flex ${big ? "h-80" : "h-52"} items-end overflow-hidden rounded-2xl bg-gradient-to-br ${grad} p-3 text-white`}>
      <span className="absolute right-3 top-2 text-4xl opacity-90">{icon}</span>
      <span className="rounded-full bg-black/25 px-2.5 py-0.5 text-xs font-semibold">{name}</span>
    </div>
  );
}

export default function Shop({ sku }) {
  const { data: products } = usePoll("/api/storefront/products", 20000);
  const shop = usePoll("/api/shop", 30000).data || {};
  const [season, setSeason] = useState("all");
  if (!products) return <StoreShell><p className="text-muted">Loading…</p></StoreShell>;
  if (sku) {
    const p = products.find((x) => x.sku === sku);
    return <StoreShell>{p ? <Product p={p} /> : <p>Product not found. <a className="underline" href="#/shop">Back to shop</a></p>}</StoreShell>;
  }
  const now = Object.keys(SEASON).find((k) => (shop.season || "").toLowerCase().includes(k));   // the season the shop is in right now comes first
  const seasons = [...new Set(products.map((p) => p.season).filter(Boolean))].sort((x, y) => (y === now) - (x === now) || x.localeCompare(y));
  const list = products.filter((p) => season === "all" || p.season === season).sort((x, y) => (y.season === now) - (x.season === now));
  return (
    <StoreShell>
      <h1 className="display text-3xl font-semibold text-plum">Festive collections</h1>
      <p className="mb-4 text-muted">Handcrafted ethnic wear for every celebration.</p>
      <div className="mb-5 flex flex-wrap gap-2">
        {["all", ...seasons].map((s) => (
          <button key={s} onClick={() => setSeason(s)} className={`rounded-full px-4 py-1.5 text-sm font-semibold ${season === s ? "bg-plum text-white" : "border border-line bg-paper"}`}>
            {s === "all" ? "All" : `${SEASON[s]?.[1] || ""} ${SEASON[s]?.[0] || s}`}
          </button>
        ))}
      </div>
      <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-4">
        {list.map((p) => (
          <a key={p.sku} href={`#/shop/${p.sku}`} className="group block">
            <Tile p={p} />
            <p className="mt-2 line-clamp-2 font-semibold group-hover:text-plum-3">{p.title}</p>
            <p className="num text-sm text-muted">{inr(p.price_inr)}</p>
          </a>
        ))}
      </div>
    </StoreShell>
  );
}

function Product({ p }) {
  const [size, setSize] = useState(null);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const hasM = Object.keys(p.measurements).length > 0;
  async function order() {
    setBusy(true); setErr("");
    try {
      const r = await fetch("/api/storefront/orders", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ sku: p.sku, size, name: name || "Guest" }) });
      const j = await r.json(); if (!r.ok) throw new Error(j.detail || r.status);
      remember(j.order_id); location.hash = `#/shop/placed/${j.order_id}`;
    } catch (e) { setErr(e.message); }
    setBusy(false);
  }
  return (
    <div className="grid gap-8 md:grid-cols-2">
      <Tile p={p} big />
      <div>
        <p className="font-mono text-xs text-muted">{p.sku}</p>
        <h1 className="display text-3xl font-semibold text-plum">{p.title}</h1>
        <p className="num mt-1 text-2xl font-semibold">{inr(p.price_inr)}</p>
        <p className="mt-3 text-sm">{p.description}</p>

        <p className="mt-5 text-sm font-semibold">Size</p>
        <div className="mt-1 flex flex-wrap gap-2">
          {p.sizes.map((s) => <button key={s} onClick={() => setSize(s)} className={`min-w-12 rounded-xl border px-3 py-2 text-sm font-semibold ${size === s ? "border-plum bg-plum text-white" : "border-line bg-paper"}`}>{s}</button>)}
        </div>
        <Card className="mt-4 p-3 text-sm">
          <p className="font-semibold">Size guide</p>
          {hasM ? <p className="mt-1 text-muted">{Object.entries(p.measurements).map(([k, v]) => `${labelM(k)}: ${v}`).join(" · ")}</p>
                : <p className="mt-1 text-warn">The seller has not listed garment measurements for this item. If unsure, message the shop before ordering.</p>}
        </Card>

        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Your name (optional)" className="mt-4 w-full rounded-xl border border-line bg-paper px-3 py-2 text-sm" />
        <Button kind="primary" className="mt-3 w-full !py-3" disabled={!size || busy} onClick={order}>{busy ? "Placing order…" : size ? "Place demo order" : "Choose a size"}</Button>
        {err && <p className="mt-2 text-sm text-bad">{err}</p>}
        <p className="mt-2 text-xs text-muted">Demo store: no payment is taken and nothing is shipped.</p>
      </div>
    </div>
  );
}

export function Placed({ id }) {
  const { data: o } = usePoll(`/api/orders/${id}`, 30000);
  return (
    <StoreShell>
      <Card className="mx-auto max-w-lg p-6 text-center">
        <p className="text-4xl">🎉</p>
        <h1 className="display mt-2 text-2xl font-semibold text-plum">Thank you for your order</h1>
        <p className="mt-1 text-muted">Order <b className="font-mono text-ink">{id}</b>{o ? ` · ${o.item} · ${inr(o.amount_inr)}` : ""}</p>
        <p className="mt-3 text-sm">In this demo your order is “delivered” the next day. If it does not fit or is not right, return it in your own language:</p>
        <a href={`#/customer/${id}`} className="mt-4 inline-block rounded-xl bg-gold px-5 py-3 font-semibold text-white">↩ Start a return</a>
        <p className="mt-4"><a className="text-sm font-semibold text-plum-3" href="#/shop/orders">My orders</a> · <a className="text-sm font-semibold text-plum-3" href="#/shop">Keep shopping</a></p>
      </Card>
    </StoreShell>
  );
}

export function MyOrders() {
  const [orders, setOrders] = useState(null);
  useEffect(() => {
    Promise.all(mine().map((id) => fetch(`/api/orders/${id}`).then((r) => (r.ok ? r.json() : null)).catch(() => null))).then((x) => setOrders(x.filter(Boolean)));
  }, []);
  return (
    <StoreShell>
      <h1 className="display text-3xl font-semibold text-plum">My orders</h1>
      {!orders ? <p className="mt-3 text-muted">Loading…</p> : !orders.length ? <p className="mt-3 text-muted">No orders yet on this device. <a className="underline" href="#/shop">Go shopping</a>.</p> : (
        <div className="mt-4 space-y-3">
          {orders.map((o) => (
            <Card key={o.id} className="flex flex-wrap items-center gap-3 p-4">
              <div className="min-w-0 flex-1"><p className="font-semibold">{o.item}</p><p className="text-sm text-muted"><span className="font-mono">{o.id}</span> · {inr(o.amount_inr)}</p></div>
              {o.return ? <span className="rounded-full bg-gold-soft px-3 py-1 text-xs font-semibold text-warn">Return {o.return.status === "approved_refunded" ? "approved and refunded" : o.return.status === "rejected" ? "not accepted" : "in review"}</span>
                        : <a href={`#/customer/${o.id}`} className="rounded-xl border border-line bg-paper px-4 py-2 text-sm font-semibold hover:bg-ivory">Return this</a>}
            </Card>
          ))}
        </div>
      )}
    </StoreShell>
  );
}
