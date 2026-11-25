import { useContext } from "react";
import usePoll from "../usePoll.js";
import { Card, SectionTitle, ShopContext, WhoTag, inr } from "../ui.jsx";

const nice = (s) => s.replaceAll("_", " ");

// Return Intelligence: what returns cost, what to do with each item, and which changes save the most. All numbers come from our data.
export default function Insights({ compact = false }) {
  const shop = useContext(ShopContext);
  const { data: ins } = usePoll("/api/insights", 5000);
  const { data: ai } = usePoll("/api/insights/ai", 60000);
  if (!ins) return <p className="text-muted">Loading…</p>;
  if (!ins.total_returns) {
    return <Card className="p-6 text-center text-muted">No returns yet. File a few from “Demo controls” (bottom right) to see patterns appear.</Card>;
  }
  const it = ins.intel;
  const max = Math.max(1, ...it.weekly_returns);

  if (compact) {
    return (
      <div className="space-y-4">
        <Card className="bg-gradient-to-br from-plum to-plum-2 p-5 text-ivory">
          <p className="text-xs font-semibold uppercase tracking-wide text-gold-soft">Estimated loss from returns</p>
          <p className="display num mt-1 text-4xl font-semibold">{inr(it.net_loss_inr)}</p>
          <p className="mt-1 text-sm text-ivory/80">{it.returns} returns · {it.return_rate_pct}% of orders. {it.actions[0] ? `Biggest saving: ${it.actions[0].title.toLowerCase()} (about ${inr(it.actions[0].impact_inr)}).` : ""}</p>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Card className="p-4"><p className="text-xs font-medium uppercase tracking-wide text-muted">Returns</p><p className="display num mt-1 text-3xl font-semibold text-plum">{it.returns}</p><p className="mt-1 text-xs text-muted">{it.return_rate_pct}% of {it.orders} orders</p></Card>
        <Card className="p-4"><p className="text-xs font-medium uppercase tracking-wide text-muted">Estimated net loss</p><p className="display num mt-1 text-3xl font-semibold text-bad">{inr(it.net_loss_inr)}</p><p className="mt-1 text-xs text-muted">≈ {inr(it.avg_loss_per_return_inr)} per return</p></Card>
        <Card className="p-4"><p className="text-xs font-medium uppercase tracking-wide text-muted">Recovered by resale</p><p className="display num mt-1 text-3xl font-semibold text-ok">{inr(it.recovered_inr)}</p><p className="mt-1 text-xs text-muted">of {inr(it.refunded_inr)} refunded</p></Card>
        <Card className="p-4"><p className="text-xs font-medium uppercase tracking-wide text-muted">Savings available</p><p className="display num mt-1 text-3xl font-semibold text-plum">{inr(it.actions.reduce((a, x) => a + x.impact_inr, 0))}</p><p className="mt-1 text-xs text-muted">if you do the actions below</p></Card>
      </div>

      <section>
        <SectionTitle hint="largest saving first">Do this to lose less</SectionTitle>
        <div className="space-y-3">
          {it.actions.map((a, i) => (
            <Card key={a.key} className="p-4">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <p className="font-semibold text-plum">{i + 1}. {a.title}</p>
                <span className="num rounded-full bg-ok-bg px-3 py-1 text-sm font-bold text-ok">≈ {inr(a.impact_inr)} saved</span>
              </div>
              <p className="mt-1 text-sm text-muted"><b className="text-ink">Why:</b> {a.basis}</p>
              <p className="mt-1 text-sm"><b>What to do:</b> {a.do}</p>
              {!!a.skus?.length && <p className="mt-1 font-mono text-xs text-muted">{a.skus.join(" · ")}</p>}
            </Card>
          ))}
        </div>
      </section>

      <Card className="border-orange-200 p-5">
        <div className="mb-1 flex items-center gap-2"><h2 className="display text-lg font-semibold text-plum">Your week, in plain words</h2><WhoTag who="sarvam" /><span className="text-xs text-muted">{ai?.model}</span></div>
        {!ai ? <p className="text-sm text-muted">Writing…</p> : !ai.plan ? <p className="text-sm text-muted">{ai.error || ai.message || "Not available right now."} The figures above stand on their own.</p> : (
          <>
            <p className="font-semibold">{ai.plan.headline}</p>
            <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm">{ai.plan.this_week.map((t, i) => <li key={i}>{t}</li>)}</ol>
            <p className="mt-2 rounded-lg bg-warn-bg px-3 py-2 text-sm text-warn"><b>Watch out:</b> {ai.plan.watch_out}</p>
            <p className="mt-2 text-xs text-muted">Written by Sarvam 105B from the numbers above. Any number it uses that is not in our data is rejected automatically.</p>
          </>)}
      </Card>

      <section>
        <SectionTitle hint="what to do with each returned item">How to handle returns</SectionTitle>
        <Card className="divide-y divide-line">
          {it.playbook.map((p) => (
            <div key={p.action} className="p-4 text-sm">
              <div className="flex flex-wrap items-center justify-between gap-2"><p className="font-semibold text-plum">{p.label}</p>
                <p className="num text-muted">{p.count} items · {inr(p.value_inr)} · recover ≈ {inr(p.recoverable_inr)}</p></div>
              <ol className="mt-1 list-decimal pl-5 text-muted">{p.steps.map((s) => <li key={s}>{s}</li>)}</ol>
            </div>
          ))}
        </Card>
      </section>

      {ins.rejections?.rejected > 0 && (
        <section>
          <SectionTitle hint="if a rejected customer complains">Rejections and complaint risk</SectionTitle>
          <Card className="p-4">
            <div className="grid grid-cols-2 gap-3 text-center sm:grid-cols-5">
              {[["Rejected", ins.rejections.rejected, "text-bad"], ["Well documented", ins.rejections.by_evidence.strong, "text-ok"], ["Partly", ins.rejections.by_evidence.medium, "text-warn"],
                ["Thin", ins.rejections.by_evidence.weak, "text-bad"], ["Complaints open", ins.rejections.complaints.open, "text-plum"]].map(([k, v, c]) => (
                <div key={k}><p className="text-xs uppercase tracking-wide text-muted">{k}</p><p className={`display num text-2xl font-semibold ${c}`}>{v}</p></div>))}
            </div>
            {!!ins.rejections.exposed.length && <>
              <p className="mt-3 text-sm"><b>{ins.rejections.exposed.length}</b> rejected returns (worth {inr(ins.rejections.exposed_value_inr)}) rest on a risk score more than on checkable facts, so they are the likeliest to turn into a complaint. Fix them early:</p>
              <div className="mt-2 divide-y divide-line text-sm">{ins.rejections.exposed.map((e) => (
                <div key={e.case_id} className="flex flex-wrap items-center gap-2 py-2"><span className="min-w-40 flex-1"><b>{e.item}</b> <span className="num text-muted">{inr(e.amount_inr)}</span><span className="block text-xs text-muted">{e.goodwill}</span></span>
                  <span className={`rounded-md px-2 py-0.5 text-xs font-semibold ${e.level === "weak" ? "bg-bad-bg text-bad" : "bg-warn-bg text-warn"}`}>{e.level}</span><a href={`#/desk/${e.case_id}`} className="text-xs font-semibold text-plum-3">Open →</a></div>))}</div></>}
            <p className="mt-3 text-xs text-muted">Every case has a printable evidence file (what the customer said, the rule and limits in force, the photo, the full timeline). Strength is a checklist of what we can show, not legal advice. Complaints so far: {ins.rejections.complaints.total} ({ins.rejections.complaints.reversed} refunded after complaint, {ins.rejections.complaints.goodwill} goodwill, {ins.rejections.complaints.upheld} rejection stood).</p>
          </Card>
        </section>
      )}

      <div className="grid gap-6 md:grid-cols-2">
        <Card className="p-5">
          <SectionTitle hint="last 8 weeks">Returns per week</SectionTitle>
          <div className="flex h-28 items-end gap-2">
            {it.weekly_returns.map((n, i) => (
              <div key={i} className="flex flex-1 flex-col items-center gap-1"><span className="num text-xs text-muted">{n}</span>
                <div className="w-full rounded-t-md bg-gold" style={{ height: `${(n / max) * 80 + 2}px` }} /></div>
            ))}
          </div>
          <p className="mt-1 text-xs text-muted">oldest → this week</p>
        </Card>
        <Card className="p-5">
          <SectionTitle>By festive season</SectionTitle>
          <div className="space-y-2 text-sm">
            {it.seasons.map((s) => (
              <div key={s.season} className="flex items-center justify-between"><span className="capitalize">{s.season}</span>
                <span className="num text-muted">{s.returns} returns{s.return_rate_pct != null ? ` · ${s.return_rate_pct}% of orders` : ""}</span></div>
            ))}
          </div>
        </Card>
      </div>

      <Card className="p-5">
        <SectionTitle hint={`${ins.total_returns} returns analysed`}>Why customers return</SectionTitle>
        <div className="space-y-4">
          {ins.reasons.map((r) => (
            <div key={r.reason}>
              <div className="flex justify-between text-sm"><b className="capitalize">{nice(r.reason)}</b><span className="num text-muted">{r.count} returns · {r.share_pct}% · {inr(r.value_inr)}</span></div>
              <div className="mt-1 h-2 rounded-full bg-line"><div className="h-2 rounded-full bg-gold" style={{ width: `${r.share_pct}%` }} /></div>
              <p className="mt-1.5 rounded-lg bg-ivory px-3 py-2 text-sm"><span className="font-semibold text-plum">What to fix: </span>{r.fix}</p>
            </div>
          ))}
        </div>
      </Card>

      {ins.listings && (
        <Card className="p-5">
          <SectionTitle hint="from your catalogue">Listings to fix first</SectionTitle>
          <p className="mb-3 text-sm"><b>{ins.listings.missing_measurements} of {ins.listings.total}</b> listings have no garment measurements. Wrong-size returns per order:
            <b className="text-bad"> {ins.listings.size_return_rate_pct.without_measurements}%</b> without vs <b className="text-ok">{ins.listings.size_return_rate_pct.with_measurements}%</b> with.</p>
          <div className="divide-y divide-line text-sm">
            {ins.listings.fix_first.map((f) => (
              <div key={f.sku} className="flex flex-wrap items-center gap-2 py-2"><span className="font-mono text-xs text-muted">{f.sku}</span><span className="min-w-40 flex-1">{f.title}</span>
                <span className="num text-muted">{f.size_returns} wrong-size / {f.orders} orders</span><span className="rounded-md bg-warn-bg px-2 py-0.5 text-xs font-semibold text-warn">Add measurements</span></div>
            ))}
          </div>
        </Card>
      )}

      {!!it.repeat_returners.length && (
        <Card className="p-5">
          <SectionTitle hint={`${it.repeat_share_pct}% of refunded value`}>Repeat returners</SectionTitle>
          <div className="divide-y divide-line text-sm">{it.repeat_returners.map((c) => <div key={c.customer} className="flex justify-between py-2"><span className="font-mono text-xs">{c.customer}</span><span className="num text-muted">{c.returns} returns · {inr(c.value_inr)}</span></div>)}</div>
        </Card>
      )}

      <Card className="bg-ivory p-5">
        <SectionTitle>How these numbers are made</SectionTitle>
        <ul className="list-disc space-y-1 pl-5 text-sm text-muted">
          <li>Counts, rates, seasons, repeat returners and the measurement comparison are computed from the returns and orders in our database.</li>
          <li>Money figures are <b>estimates</b> from these assumptions: ₹{it.assumptions.reverse_shipping_inr} return shipping + ₹{it.assumptions.handling_inr} handling per return; resale recovery of {it.assumptions.recovery_pct.unworn}% for unworn, {it.assumptions.recovery_pct.worn}% for worn, {it.assumptions.recovery_pct.damaged}% for damaged items; {it.assumptions.exchange_accept_pct}% of wrong-size customers accepting an exchange. Replace them with your own costs.</li>
          <li>“Savings available” is a planning estimate, not a measured result and not a claim that any return was prevented.{shop.data_source !== "live" ? " The returns shown are demo data." : ""}</li>
        </ul>
      </Card>
    </div>
  );
}
