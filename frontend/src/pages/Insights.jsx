import { useContext } from "react";
import usePoll from "../usePoll.js";
import { Card, SectionTitle, ShopContext, WhoTag, inr } from "../ui.jsx";

// Return Intelligence: why customers return, how much is preventable, and what to fix first. All from our own database.
export default function Insights({ compact = false }) {
  const shop = useContext(ShopContext);
  const { data: ins } = usePoll("/api/insights", 5000);
  const { data: ai } = usePoll("/api/insights/ai", 60000);
  if (!ins) return <p className="text-muted">Loading…</p>;
  if (!ins.total_returns) {
    return <Card className="p-6 text-center text-muted">No returns yet. File a few from “Demo controls” (bottom right) to see patterns appear.</Card>;
  }
  const top = compact ? ins.reasons.slice(0, 3) : ins.reasons;
  return (
    <div className="space-y-4">
      <Card className="bg-gradient-to-br from-plum to-plum-2 p-5 text-ivory">
        <p className="text-xs font-semibold uppercase tracking-wide text-gold-soft">Preventable returns</p>
        <p className="display num mt-1 text-4xl font-semibold">{ins.preventable.share_pct}%</p>
        <p className="mt-1 text-sm text-ivory/80">{ins.preventable.count} of {ins.total_returns} returns (worth {inr(ins.preventable.value_inr)}) came from listing problems you can fix: size information or product description.</p>
      </Card>
      {!compact && (
        <Card className="border-blue-200 p-5">
          <div className="mb-1 flex items-center gap-2"><h2 className="display text-lg font-semibold text-plum">AI action plan</h2><WhoTag who="ibm" />{ai?.model && <span className="text-xs text-muted">{ai.model}</span>}</div>
          {!ai ? <p className="text-sm text-muted">Thinking…</p> : !ai.configured ? <p className="text-sm text-muted">{ai.message}</p>
            : ai.error ? <p className="text-sm text-bad">The AI plan could not be generated: {ai.error}</p> : !ai.plan ? <p className="text-sm text-muted">{ai.message}</p> : (
            <>
              <p className="font-semibold">{ai.plan.headline}</p>
              <ol className="mt-2 space-y-2">{ai.plan.actions.map((a, i) => (
                <li key={i} className="rounded-xl bg-ivory p-3 text-sm"><p className="font-semibold text-plum">{i + 1}. {a.title}</p><p className="text-muted">{a.why}</p>
                  {!!a.skus.length && <p className="mt-1 font-mono text-xs">{a.skus.join(" · ")}</p>}</li>))}</ol>
              <p className="mt-2 text-xs text-muted">Written by an AI model from the numbers on this page. The numbers themselves come from our database.</p>
            </>)}
        </Card>
      )}
      <Card className="p-5">
        <SectionTitle hint={`${ins.total_returns} returns analysed`}>Why customers return</SectionTitle>
        <div className="space-y-4">
          {top.map((r) => (
            <div key={r.reason}>
              <div className="flex justify-between text-sm"><b className="capitalize">{r.reason.replaceAll("_", " ")}</b><span className="num text-muted">{r.count} returns · {r.share_pct}% · {inr(r.value_inr)}</span></div>
              <div className="mt-1 h-2 rounded-full bg-line"><div className="h-2 rounded-full bg-gold" style={{ width: `${r.share_pct}%` }} /></div>
              <p className="mt-1.5 rounded-lg bg-ivory px-3 py-2 text-sm text-ink"><span className="font-semibold text-plum">What to fix: </span>{r.fix}</p>
            </div>
          ))}
        </div>
      </Card>
      {!compact && ins.listings && (
        <Card className="p-5">
          <SectionTitle hint="from your synced Shopify store">Listings to fix first</SectionTitle>
          <p className="mb-3 text-sm">
            <b>{ins.listings.missing_measurements} of {ins.listings.total}</b> listings have no garment measurements. Wrong-size returns per order:
            <b className="text-bad"> {ins.listings.size_return_rate_pct.without_measurements}%</b> without measurements vs
            <b className="text-ok"> {ins.listings.size_return_rate_pct.with_measurements}%</b> with them.
          </p>
          <div className="divide-y divide-line text-sm">
            {ins.listings.fix_first.map((f) => (
              <div key={f.sku} className="flex flex-wrap items-center gap-2 py-2">
                <span className="font-mono text-xs text-muted">{f.sku}</span><span className="min-w-40 flex-1">{f.title}</span>
                <span className="num text-muted">{f.size_returns} wrong-size returns / {f.orders} orders</span>
                <span className="rounded-md bg-warn-bg px-2 py-0.5 text-xs font-semibold text-warn">Add measurements</span>
              </div>
            ))}
          </div>
          <p className="mt-3 text-xs text-muted">{ins.listings.note} A baseline to measure against, not a claim that any return was prevented.{shop.data_source !== "live" ? " Demo data." : ""}</p>
        </Card>
      )}
      {!compact && (
        <Card className="p-5">
          <SectionTitle>Most-returned products</SectionTitle>
          <div className="divide-y divide-line text-sm">
            {ins.worst_items.map((i) => (
              <div key={i.item} className="flex justify-between py-2"><span>{i.item}</span><span className="text-muted">{i.count} returns · mostly {i.main_reason.replaceAll("_", " ")}</span></div>
            ))}
          </div>
          <p className="mt-3 text-xs text-muted">“Preventable” counts size and description returns; it is a baseline to measure against, not a claim that any return was prevented.</p>
        </Card>
      )}
    </div>
  );
}
