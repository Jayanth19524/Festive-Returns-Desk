import { useEffect, useState } from "react";
import usePoll from "./usePoll.js";
import Overview from "./pages/Overview.jsx";
import Desk from "./pages/Desk.jsx";
import Insights from "./pages/Insights.jsx";
import Catalogue from "./pages/Catalogue.jsx";
import Architecture from "./pages/Architecture.jsx";
import Customer from "./pages/Customer.jsx";
import Shop, { MyOrders, Placed, StoreShell } from "./pages/Shop.jsx";
import DemoPanel from "./DemoPanel.jsx";
import { ShopContext } from "./ui.jsx";

const NAV = [
  ["", "Command centre", "◧"], ["desk", "Returns desk", "☰"], ["catalogue", "Store catalogue", "▦"], ["insights", "Return intelligence", "◔"],
  ["architecture", "How it works", "⌘"], ["shop", "Demo store ↗", "🛍"],
];

// Hash router: #/ , #/desk/13 , #/insights , #/architecture , #/customer
export default function App() {
  const [hash, setHash] = useState(location.hash);
  useEffect(() => {
    const on = () => setHash(location.hash);
    addEventListener("hashchange", on);
    return () => removeEventListener("hashchange", on);
  }, []);
  const [, route = "", arg, arg2] = hash.replace("#", "").split("/");
  const shop = usePoll("/api/shop", 8000).data || {};
  const season = shop.season;
  const panel = usePoll("/api/panel", 3000).data;
  const frozen = panel && !panel.config.refunds_enabled;

  // The storefront and the customer's return page are what a SHOPPER sees: no owner sidebar.
  if (route === "shop") {
    return arg === "orders" ? <MyOrders /> : arg === "placed" ? <Placed id={arg2} /> : <Shop sku={arg} />;
  }
  if (route === "customer") return <StoreShell season={false}><Customer orderId={arg} /></StoreShell>;
  return (
    <ShopContext.Provider value={shop}>
    <div className="min-h-screen lg:flex">
      <aside className="bg-plum text-ivory lg:sticky lg:top-0 lg:h-screen lg:w-64 lg:shrink-0">
        <div className="flex items-center justify-between gap-3 px-5 py-4 lg:block lg:py-6">
          <div>
            <p className="display text-xl font-semibold leading-tight">Festive<br className="hidden lg:block" /> Returns Desk</p>
            {season && <p className="mt-1 text-xs text-gold-soft">🪔 {season}</p>}
          </div>
        </div>
        <nav className="flex gap-1 overflow-x-auto px-3 pb-3 lg:block lg:space-y-1 lg:pb-0">
          {NAV.map(([r, label, icon]) => (
            <a key={r} href={`#/${r}`} className={`flex items-center gap-2 whitespace-nowrap rounded-xl px-3 py-2 text-sm font-medium transition ${route === r ? "bg-white/15 text-white" : "text-ivory/70 hover:bg-white/10"}`}>
              <span className="w-4 text-center text-gold">{icon}</span>{label}
            </a>
          ))}
        </nav>
        <div className="hidden px-5 pt-6 text-xs text-ivory/60 lg:block">
          <p className="mb-2 font-semibold uppercase tracking-wide text-ivory/40">Powered by</p>
          <p>● Sarvam AI · voice + language</p><p>● Flagsmith · live rules</p><p>● NudgeBee · refund workflow</p>
        </div>
      </aside>

      <main className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2 border-b border-line bg-paper/80 px-4 py-2 text-xs backdrop-blur lg:px-8">
          <span className={`rounded-full px-2.5 py-1 font-semibold ${frozen ? "bg-bad-bg text-bad" : "bg-ok-bg text-ok"}`}>{frozen ? "● Refunds FROZEN" : "● Refunds on"}</span>
          <span className={`rounded-full px-2.5 py-1 font-semibold ${shop.ai_configured ? "bg-blue-100 text-blue-800" : "bg-line text-muted"}`}>IBM Bob {shop.ai_configured ? "on" : "not connected"}</span>
          <span className={`rounded-full px-2.5 py-1 font-semibold ${panel?.live ? "bg-violet-100 text-violet-800" : "bg-bad-bg text-bad"}`}>
            Flagsmith {panel ? (panel.live ? "live" : "NOT live") : "…"}
          </span>
          <span className="ml-auto rounded-full bg-gold-soft px-2.5 py-1 font-semibold text-warn">
            {shop.data_source === "live" ? `Connected: ${shop.store} · test mode, refunds are recorded not paid` : "Demo data · no real money"}
          </span>
        </div>
        <div className="mx-auto max-w-6xl p-4 lg:p-8">
          {route === "" && <Overview />}
          {route === "desk" && <Desk selected={arg ? Number(arg) : null} />}
          {route === "catalogue" && <Catalogue />}
          {route === "insights" && <Insights />}
          {route === "architecture" && <Architecture />}
        </div>
      </main>
      <DemoPanel />
    </div>
    </ShopContext.Provider>
  );
}
