import usePoll from "../usePoll.js";
import { Button, inr } from "../ui.jsx";

const when = (iso) => new Date(iso).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "medium" });

// A printable evidence file for ONE case: use it if a customer complains about a decision. Print or "Save as PDF" from the browser.
export default function CaseFile({ id }) {
  const { data: f, error } = usePoll(`/api/cases/${id}/file`, 60000);
  if (!f) return <p className="p-8 text-muted">{error ? "Could not load this case file." : "Loading…"}</p>;
  const h = f.how_it_was_decided, cfg = h.limits_in_force || {};
  const Row = ({ k, children }) => <div className="grid grid-cols-3 gap-3 border-b border-line py-2 text-sm"><dt className="font-semibold text-muted">{k}</dt><dd className="col-span-2">{children}</dd></div>;
  return (
    <div className="mx-auto max-w-3xl bg-white p-8 text-ink print:p-0">
      <div className="mb-6 flex items-start justify-between gap-3 print:hidden">
        <a href={`#/desk/${f.case_id}`} className="text-sm font-semibold text-plum-3">← Back to the case</a>
        <Button kind="primary" onClick={() => window.print()}>Print / Save as PDF</Button>
      </div>
      <h1 className="display text-3xl font-semibold text-plum">Return case file #{f.case_id}</h1>
      <p className="text-sm text-muted">Festive Returns Desk · generated {when(f.generated_at)}</p>

      <h2 className="display mt-6 text-xl font-semibold text-plum">1. The order</h2>
      <dl><Row k="Order">{f.order?.id} · {f.order?.item}</Row><Row k="Amount">{inr(f.order?.amount_inr)}</Row><Row k="Delivered">{f.order?.delivered_days_ago} days before the return was filed</Row><Row k="Customer">{f.customer_id}</Row></dl>

      <h2 className="display mt-6 text-xl font-semibold text-plum">2. What the customer said</h2>
      <p className="mt-2 rounded-lg bg-ivory p-3 text-sm">“{f.customer_statement || "(filed without a recorded statement)"}” <span className="text-muted">({f.language})</span></p>
      <p className="mt-2 text-sm">Understood as: reason <b>{f.understood_as.reason.replaceAll("_", " ")}</b>, condition <b>{f.understood_as.condition}</b>.</p>

      <h2 className="display mt-6 text-xl font-semibold text-plum">3. The decision</h2>
      <dl><Row k="Outcome"><b className="uppercase">{f.decision}</b> (status: {f.status.replaceAll("_", " ")})</Row><Row k="Risk score">{f.risk_score}</Row>
        <Row k="Reasons"><ul className="list-disc pl-5">{f.reasons.map((r, i) => <li key={i}>{r}</li>)}</ul></Row>
        <Row k="Decided by">{h.by}. {h.ai_role}.</Row>
        <Row k="Rules in force">Return window {h.return_window_days} days. Auto-refund up to {inr(cfg.auto_refund_limit_inr)}; owner approval above {inr(cfg.hold_above_inr)}; repeat-return limit {cfg.max_returns_per_customer_30d} per 30 days; worn-item points {cfg.wardrobing_risk_weight}; refunds {cfg.refunds_enabled ? "on" : "frozen"}. (Source: {h.limits_source}.)</Row></dl>

      <h2 className="display mt-6 text-xl font-semibold text-plum">4. Photo evidence</h2>
      {f.photo.on_file ? (
        <div className="mt-2 flex gap-4"><img src={f.photo.url} alt="customer's photo" className="h-40 w-32 rounded-lg object-cover" />
          <div className="text-sm">{f.photo.check?.status === "ok" ? <><p>Model: {f.photo.check.model}, confidence {Math.round(f.photo.check.confidence * 100)}%</p>
            <p>Wear: {f.photo.check.signs_of_wear}. Damage: {f.photo.check.visible_damage ? "visible" : "none seen"}. Matches the claim: {f.photo.check.matches_claim}.</p><p className="text-muted">{f.photo.check.notes}</p></>
            : <p className="text-muted">{f.photo.check?.detail || "Photo kept; not analysed."}</p>}</div></div>
      ) : <p className="mt-2 text-sm text-muted">No photo on file for this case.</p>}

      <h2 className="display mt-6 text-xl font-semibold text-plum">5. Timeline</h2>
      <ol className="mt-2 space-y-1 text-sm">{f.timeline.map((e, i) => <li key={i}><span className="font-mono text-xs text-muted">{when(e.at)}</span> · <b>{e.step.replaceAll("_", " ")}</b> · {e.detail.slice(0, 200)}</li>)}</ol>

      {f.evidence && <>
        <h2 className="display mt-6 text-xl font-semibold text-plum">6. How well the rejection is documented: {f.evidence.level}</h2>
        <ul className="mt-2 list-disc pl-5 text-sm">{f.evidence.why.map((w) => <li key={w}>{w}</li>)}</ul>
        {f.evidence.goodwill && <p className="mt-2 rounded-lg bg-gold-soft p-3 text-sm">Suggested before it escalates: {f.evidence.goodwill}.</p>}</>}

      {!!f.complaints.length && <>
        <h2 className="display mt-6 text-xl font-semibold text-plum">7. Complaints</h2>
        <ul className="mt-2 space-y-1 text-sm">{f.complaints.map((c) => <li key={c.id}>{when(c.filed_at)} · {c.channel} · {c.summary} · <b>{c.status === "open" ? "open" : `${c.outcome}${c.note ? `: ${c.note}` : ""}`}</b></li>)}</ul></>}

      <p className="mt-8 border-t border-line pt-3 text-xs text-muted">This file records what happened and what the system knew at the time. It is not legal advice.</p>
    </div>
  );
}
