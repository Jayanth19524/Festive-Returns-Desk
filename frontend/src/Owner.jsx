import usePoll from "./usePoll.js";

const act = (id, action) => fetch(`/api/cases/${id}/owner/${action}`, { method: "POST" }).then((r) => r.json()).then((j) => !j.ok && alert(j.error));

const COLORS = { approve: "bg-green-100 text-green-800", hold: "bg-amber-100 text-amber-900", reject: "bg-red-100 text-red-800" };
const Badge = ({ d }) => <span className={`rounded px-2 py-0.5 text-xs font-bold ${COLORS[d] || "bg-stone-200"}`}>{String(d).toUpperCase()}</span>;
const inr = (n) => "₹" + Number(n).toLocaleString("en-IN");

export default function Owner() {
  const { data: panel, error } = usePoll("/api/panel", 2000);
  const { data: cases } = usePoll("/api/cases", 2000);
  if (!panel) return <p>{error ? `Cannot reach the API: ${error}` : "Loading…"}</p>;
  const c = panel.config;
  return (
    <div className="space-y-6">
      {/* Freeze status + thresholds in effect (live from Flagsmith) */}
      <section className="grid gap-3 sm:grid-cols-2">
        <div className={`rounded border-2 p-4 ${c.refunds_enabled ? "border-green-600 bg-green-50" : "border-red-600 bg-red-50"}`}>
          <p className="text-sm text-stone-600">Refund switch (Flagsmith: refunds_enabled)</p>
          <p className="text-2xl font-bold">{c.refunds_enabled ? "REFUNDS ON" : "FROZEN: all refunds held"}</p>
          <a className="text-sm underline" href="http://localhost:8000" target="_blank" rel="noreferrer">Open Flagsmith to flip it</a>
        </div>
        <div className="rounded border bg-white p-4 text-sm">
          <p className="mb-1 font-semibold">Thresholds in effect <span className={panel.live ? "text-green-700" : "text-red-700"}>({panel.status})</span></p>
          <ul className="grid grid-cols-2 gap-x-2">
            <li>Auto-refund up to</li><li className="font-mono">{inr(c.auto_refund_limit_inr)}</li>
            <li>Hold above</li><li className="font-mono">{inr(c.hold_above_inr)}</li>
            <li>Max returns / 30 days</li><li className="font-mono">{c.max_returns_per_customer_30d}</li>
            <li>Wardrobing risk weight</li><li className="font-mono">{c.wardrobing_risk_weight}</li>
          </ul>
        </div>
      </section>

      {/* Live decision panel: change a value in Flagsmith and watch these flip within seconds */}
      <section>
        <h2 className="mb-2 font-semibold">Live decision panel <span className="text-sm font-normal text-stone-500">(what each sample return would get right now)</span></h2>
        <div className="divide-y rounded border bg-white">
          {panel.scenarios.map((s) => (
            <div key={s.order_id} className="flex flex-wrap items-center gap-2 p-2 text-sm">
              <span className="w-20 font-mono">{s.order_id}</span><span className="flex-1 min-w-48">{s.label}</span>
              <Badge d={s.decision} /><span className="w-full text-xs text-stone-500 sm:w-auto sm:max-w-sm">{s.reasons.join("; ")}</span>
            </div>
          ))}
        </div>
      </section>

      {/* Case queue */}
      <section>
        <h2 className="mb-2 font-semibold">Case queue</h2>
        {!cases?.length && <p className="text-sm text-stone-500">No cases yet. Use the Customer screen, or run scripts/fire_webhook.sh.</p>}
        <div className="space-y-2">
          {cases?.map((k) => (
            <details key={k.id} className="rounded border bg-white p-2 text-sm">
              <summary className="flex cursor-pointer flex-wrap items-center gap-2">
                <span className="font-mono">#{k.id}</span><span className="font-mono">{k.order_id}</span>
                <span>{k.order?.item} {k.order && inr(k.order.amount_inr)}</span>
                <Badge d={k.decision} /><span className="rounded bg-stone-200 px-2 text-xs">{k.status}</span>
                {k.refund && <span className="text-green-700">refunded {inr(k.refund.amount_inr)}</span>}
              </summary>
              <p className="mt-2 text-stone-600">“{k.transcript || "(entered without voice)"}” → {k.reason_category}, {k.claimed_condition}</p>
              <p className="mt-1"><b>Why:</b> {k.reasons.join("; ")}</p>
              <p className="mt-1 text-xs text-stone-500">Flagsmith values at that moment: {JSON.stringify(k.flags_in_effect?.cfg)}</p>
              {k.status === "held" && (
                <div className="mt-2 flex gap-2">
                  <button onClick={() => act(k.id, "approve")} className="rounded bg-green-700 px-3 py-1 text-white">Approve refund</button>
                  <button onClick={() => act(k.id, "reject")} className="rounded bg-red-700 px-3 py-1 text-white">Reject</button>
                  {k.signed_approval_required ? <span className="self-center text-xs text-amber-800">Above hold limit: needs signed approval (not built yet)</span> : null}
                </div>
              )}
              <ol className="mt-2 list-decimal pl-5 text-xs text-stone-600">
                {k.events.map((e, i) => <li key={i}><b>{e.step}</b> {e.detail.slice(0, 160)}</li>)}
              </ol>
            </details>
          ))}
        </div>
      </section>
    </div>
  );
}
