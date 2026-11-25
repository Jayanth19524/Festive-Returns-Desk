import usePoll from "../usePoll.js";
import { Card, DecisionBadge, Kpi, SectionTitle, StatusBadge, inr } from "../ui.jsx";
import Insights from "./Insights.jsx";

// The command centre: what needs the owner now, what was handled automatically, and the rules in effect.
export default function Overview() {
  const { data: st } = usePoll("/api/stats", 2000);
  const { data: panel } = usePoll("/api/panel", 2000);
  const { data: cases } = usePoll("/api/cases", 2000);
  if (!st || !panel) return <p className="text-muted">Loading…</p>;
  const c = panel.config;
  const needs = (cases || []).filter((k) => k.status === "held").sort((a, b) => (b.order?.amount_inr || 0) - (a.order?.amount_inr || 0));
  const handled = (st.by_decision.approve || 0) + (st.by_decision.reject || 0);
  const total = Object.values(st.by_decision).reduce((a, b) => a + b, 0);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="display text-3xl font-semibold text-plum">Returns command centre</h1>
        <p className="text-muted">What needs you, what was handled for you, and the rules in effect right now.</p>
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Kpi label="Needs your decision" value={st.by_status.held || 0} sub={`${inr(st.held_value_inr)} waiting`} tone="warn" />
        <Kpi label="Handled for you" value={handled} sub={total ? `${Math.round((100 * handled) / total)}% of all returns` : "no returns yet"} tone="ok" />
        <Kpi label="Refunded" value={inr(st.refunded_inr)} sub={`${st.refund_count} refunds`} />
        <Kpi label="Cases today" value={total} sub="simulated returns" />
      </div>

      <div className="grid gap-6 lg:grid-cols-5">
        <div className="min-w-0 space-y-6 lg:col-span-3">
          <section>
            <SectionTitle hint={needs.length ? "largest first" : ""}>Needs you</SectionTitle>
            {!needs.length && <Card className="p-6 text-center text-muted">Nothing is waiting for you. 🎉 Use “Demo controls” to file a return.</Card>}
            <div className="space-y-2">
              {needs.slice(0, 5).map((k) => (
                <a key={k.id} href={`#/desk/${k.id}`} className="pop block">
                  <Card className="flex flex-wrap items-center gap-3 p-3 transition hover:border-gold">
                    <div className="min-w-0 flex-1">
                      <p className="font-semibold">{k.order?.item} <span className="num text-muted">{inr(k.order?.amount_inr)}</span></p>
                      <p className="truncate text-sm text-muted">{k.reasons[0]}</p>
                    </div>
                    {k.signed_approval_required ? <span className="rounded-md bg-gold-soft px-2 py-0.5 text-xs font-semibold text-warn">🔒 Touch ID</span> : null}
                    <DecisionBadge d={k.decision} />
                  </Card>
                </a>
              ))}
            </div>
            {needs.length > 5 && <a href="#/desk" className="mt-2 inline-block text-sm font-semibold text-plum-3">See all {needs.length} →</a>}
          </section>

          <section>
            <SectionTitle hint="live from Flagsmith">What would happen right now</SectionTitle>
            <Card className="divide-y divide-line">
              {panel.scenarios.map((s) => (
                <div key={s.order_id} className="flex flex-wrap items-center gap-2 px-4 py-2.5 text-sm">
                  <span className="min-w-48 flex-1">{s.label}</span><DecisionBadge d={s.decision} />
                </div>
              ))}
            </Card>
            <p className="mt-2 text-xs text-muted">Change a value in Flagsmith (or in Demo controls) and these flip within seconds.</p>
          </section>

          <section>
            <SectionTitle>Recent activity</SectionTitle>
            <Card className="divide-y divide-line">
              {(cases || []).slice(0, 6).map((k) => (
                <a key={k.id} href={`#/desk/${k.id}`} className="flex flex-wrap items-center gap-2 px-4 py-2.5 text-sm hover:bg-ivory">
                  <span className="num w-10 text-muted">#{k.id}</span><span className="min-w-40 flex-1">{k.order?.item || k.order_id}</span>
                  <StatusBadge s={k.status} />
                </a>
              ))}
              {!cases?.length && <p className="p-4 text-sm text-muted">No activity yet.</p>}
            </Card>
          </section>
        </div>

        <div className="min-w-0 space-y-6 lg:col-span-2">
          <section>
            <SectionTitle>Rules in effect</SectionTitle>
            <Card className={`p-4 ${c.refunds_enabled ? "" : "border-bad bg-bad-bg"}`}>
              <p className={`display text-xl font-semibold ${c.refunds_enabled ? "text-ok" : "text-bad"}`}>{c.refunds_enabled ? "Refunds are on" : "Refunds are FROZEN"}</p>
              <p className="text-xs text-muted">Flagsmith · refunds_enabled. {c.refunds_enabled ? "" : "Every case is held until you turn it back on."}</p>
              <dl className="mt-3 grid grid-cols-2 gap-y-1.5 text-sm">
                <dt className="text-muted">Auto-refund up to</dt><dd className="num text-right font-semibold">{inr(c.auto_refund_limit_inr)}</dd>
                <dt className="text-muted">Touch ID above</dt><dd className="num text-right font-semibold">{inr(c.hold_above_inr)}</dd>
                <dt className="text-muted">Max returns / 30 days</dt><dd className="num text-right font-semibold">{c.max_returns_per_customer_30d}</dd>
                <dt className="text-muted">“Worn” risk points</dt><dd className="num text-right font-semibold">{c.wardrobing_risk_weight}</dd>
              </dl>
            </Card>
          </section>
          <section>
            <SectionTitle>Return intelligence</SectionTitle>
            <Insights compact />
            <a href="#/insights" className="mt-2 inline-block text-sm font-semibold text-plum-3">Full analysis →</a>
          </section>
        </div>
      </div>
    </div>
  );
}
