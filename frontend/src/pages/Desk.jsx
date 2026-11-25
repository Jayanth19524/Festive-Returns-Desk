import { useState } from "react";
const CH = ["consumer helpline", "consumer forum", "marketplace", "social media", "phone or WhatsApp", "other"];
import usePoll from "../usePoll.js";
import { Button, Card, DecisionBadge, SectionTitle, StatusBadge, WhoTag, inr } from "../ui.jsx";
import { approveWithTouchId, registerOwnerKey } from "../webauthn.js";

const STEP_WHO = { intake: "sarvam", decision: "ours", flags_in_effect: "flagsmith", nudgebee_dispatch: "nudgebee", workflow_validate: "nudgebee",
  case_held: "nudgebee", case_rejected: "nudgebee", refund_issued: "nudgebee", refund_blocked: "ours", callback_mismatch: "ours",
  owner_approve_blocked: "owner", owner_rejected: "owner" };
const FILTERS = [["held", "Needs you"], ["all", "All"], ["approved_refunded", "Refunded"], ["rejected", "Rejected"]];
const post = (u) => fetch(u, { method: "POST" }).then((r) => r.json());

export default function Desk({ selected }) {
  const { data: cases } = usePoll("/api/cases", 1500);
  const { data: wa } = usePoll("/api/webauthn/status", 4000);
  const [filter, setFilter] = useState("held");
  const [msg, setMsg] = useState("");
  const [cform, setCform] = useState({ channel: CH[0], summary: "" });
  const [draft, setDraft] = useState(null);
  if (!cases) return <p className="text-muted">Loading…</p>;

  const list = [...cases].filter((k) => filter === "all" || k.status === filter)
    .sort((a, b) => (b.status === "held") - (a.status === "held") || (b.order?.amount_inr || 0) - (a.order?.amount_inr || 0) || b.id - a.id);
  const cur = cases.find((k) => k.id === selected) || list[0];
  const counts = (f) => (f === "all" ? cases.length : cases.filter((k) => k.status === f).length);

  const run = async (fn) => { setMsg(""); try { const j = await fn(); if (j && j.ok === false) setMsg(j.error); } catch (e) { setMsg(e.message); } };

  return (
    <div>
      <h1 className="display mb-1 text-3xl font-semibold text-plum">Returns desk</h1>
      <p className="mb-4 text-muted">Work through the cases the rules could not settle alone. Largest first.</p>
      <div className="mb-4 flex flex-wrap gap-2">
        {FILTERS.map(([f, label]) => (
          <button key={f} onClick={() => setFilter(f)} className={`rounded-full px-3.5 py-1.5 text-sm font-semibold ${filter === f ? "bg-plum text-white" : "border border-line bg-paper"}`}>
            {label} <span className="num opacity-70">{counts(f)}</span>
          </button>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-5">
        <div className="min-w-0 space-y-2 lg:col-span-2">
          {!list.length && <Card className="p-6 text-center text-muted">No cases in this view.</Card>}
          {list.map((k) => (
            <a key={k.id} href={`#/desk/${k.id}`}>
              <Card className={`p-3 transition hover:border-gold ${cur?.id === k.id ? "border-plum ring-1 ring-plum" : ""}`}>
                <div className="flex items-start justify-between gap-2">
                  <p className="font-semibold">{k.order?.item || k.order_id}</p><p className="num font-semibold">{inr(k.order?.amount_inr)}</p>
                </div>
                <p className="mt-0.5 truncate text-sm text-muted">{k.reason_category.replaceAll("_", " ")} · {k.order_id}</p>
                <div className="mt-2 flex items-center gap-2"><StatusBadge s={k.status} />{k.signed_approval_required ? <span className="text-xs font-semibold text-warn">🔒 Touch ID</span> : null}</div>
              </Card>
            </a>
          ))}
        </div>

        {cur && (
          <div className="min-w-0 space-y-4 lg:col-span-3">
            <Card className="p-5">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-muted">Case #{cur.id} · {cur.order_id}</p>
                  <h2 className="display text-2xl font-semibold text-plum">{cur.order?.item} <span className="num">{inr(cur.order?.amount_inr)}</span></h2>
                </div>
                <div className="flex gap-2"><DecisionBadge d={cur.decision} /><StatusBadge s={cur.status} /></div>
              </div>

              <div className="mt-4 rounded-xl bg-ivory p-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-muted">What the customer said</p>
                <p className="mt-1">“{cur.transcript || "(filed without voice)"}”</p>
                <div className="mt-2 flex flex-wrap gap-1.5 text-xs">
                  <span className="rounded-md bg-orange-100 px-2 py-0.5 font-semibold text-orange-800">understood by Sarvam</span>
                  <span className="rounded-md bg-paper px-2 py-0.5 ring-1 ring-line">reason: {cur.reason_category.replaceAll("_", " ")}</span>
                  <span className="rounded-md bg-paper px-2 py-0.5 ring-1 ring-line">condition: {cur.claimed_condition}</span>
                  <span className="rounded-md bg-paper px-2 py-0.5 ring-1 ring-line">language: {cur.language}</span>
                </div>
              </div>

              <div className="mt-4">
                <p className="text-xs font-semibold uppercase tracking-wide text-muted">Why the rules decided this <span className="normal-case">(plain code, not AI)</span></p>
                <ul className="mt-1 list-disc space-y-0.5 pl-5 text-sm">{cur.reasons.map((r, i) => <li key={i}>{r}</li>)}</ul>
                <p className="mt-2 text-xs text-muted">Flagsmith values at that moment: auto-refund ≤ {inr(cur.flags_in_effect?.cfg?.auto_refund_limit_inr)}, Touch ID above {inr(cur.flags_in_effect?.cfg?.hold_above_inr)}, refunds {cur.flags_in_effect?.cfg?.refunds_enabled ? "on" : "frozen"}.</p>
              </div>

              {cur.photo_path && (
                <div className="mt-4 flex gap-3 rounded-xl border border-line p-3">
                  <img src={`/api/cases/${cur.id}/photo`} alt="customer's photo" className="h-32 w-28 shrink-0 rounded-lg object-cover" />
                  <div className="min-w-0 text-sm">
                    <p className="text-xs font-semibold uppercase tracking-wide text-muted">Customer's photo</p>
                    {cur.photo_check?.status === "ok" ? (
                      <>
                        <p className="mt-1"><WhoTag who="ibm" /> <span className="text-xs text-muted">{cur.photo_check.model} · confidence {Math.round(cur.photo_check.confidence * 100)}%</span></p>
                        <div className="mt-1.5 flex flex-wrap gap-1.5 text-xs">
                          <span className="rounded-md bg-ivory px-2 py-0.5 ring-1 ring-line">wear: {cur.photo_check.signs_of_wear}</span>
                          <span className="rounded-md bg-ivory px-2 py-0.5 ring-1 ring-line">damage: {cur.photo_check.visible_damage ? "visible" : "none seen"}</span>
                          <span className="rounded-md bg-ivory px-2 py-0.5 ring-1 ring-line">tags: {cur.photo_check.tags_attached}</span>
                          <span className={`rounded-md px-2 py-0.5 font-semibold ${cur.photo_check.matches_claim === "no" ? "bg-bad-bg text-bad" : cur.photo_check.matches_claim === "yes" ? "bg-ok-bg text-ok" : "bg-ivory ring-1 ring-line"}`}>matches claim: {cur.photo_check.matches_claim}</span>
                        </div>
                        <p className="mt-1.5 text-muted">{cur.photo_check.damage_description || cur.photo_check.notes}</p>
                        <p className="mt-1 text-xs text-muted">The model only describes the photo. A mismatch can add risk points; it can never approve anything.</p>
                      </>
                    ) : <p className="mt-1 text-muted">{cur.photo_check?.detail || "Not analysed."}</p>}
                  </div>
                </div>
              )}
              {cur.disposition && cur.status !== "rejected" && (
                <div className="mt-4 rounded-xl border border-gold/50 bg-gold-soft/40 p-3 text-sm">
                  <p className="text-xs font-semibold uppercase tracking-wide text-warn">What to do with the item</p>
                  <p className="mt-1 font-semibold text-plum">{cur.disposition.label} <span className="num font-normal text-muted">· about {cur.disposition.recovery_pct}% of the price recoverable</span></p>
                  <ol className="mt-1 list-decimal pl-5 text-muted">{cur.disposition.steps.map((x) => <li key={x}>{x}</li>)}</ol>
                </div>
              )}
              {cur.evidence && (
                <div className={`mt-4 rounded-xl border p-3 text-sm ${cur.evidence.level === "strong" ? "border-ok/40 bg-ok-bg" : cur.evidence.level === "medium" ? "border-warn/40 bg-warn-bg" : "border-bad/40 bg-bad-bg"}`}>
                  <p className="text-xs font-semibold uppercase tracking-wide text-muted">If this customer complains: evidence is <b className="text-ink">{cur.evidence.level}</b></p>
                  <ul className="mt-1 list-disc pl-5">{cur.evidence.why.map((w) => <li key={w}>{w}</li>)}</ul>
                  {cur.evidence.goodwill && <p className="mt-1 font-semibold text-plum">Suggested: {cur.evidence.goodwill}.</p>}
                  <div className="mt-2 flex flex-wrap gap-2">
                    <a href={`#/file/${cur.id}`} className="rounded-xl bg-plum px-3 py-1.5 text-xs font-semibold text-white">Open printable case file</a>
                    <Button className="!py-1.5 text-xs" onClick={async () => { setDraft(null); const r = await fetch(`/api/cases/${cur.id}/reply-draft`, { method: "POST" }); const j = await r.json(); setDraft(r.ok ? j : { error: j.detail }); }}>Draft a reply (customer's language)</Button>
                  </div>
                  {draft && (draft.error ? <p className="mt-2 text-bad">{draft.error}</p> : <p className="mt-2 rounded-lg bg-paper p-2"><b>{draft.language}:</b> {draft.text}<span className="mt-1 block text-xs text-muted">{draft.note}</span></p>)}
                </div>
              )}
              {cur.decision !== "approve" && (
                <div className="mt-4 rounded-xl border border-line p-3 text-sm">
                  <p className="text-xs font-semibold uppercase tracking-wide text-muted">Complaints</p>
                  {cur.complaints.map((k) => (
                    <div key={k.id} className="mt-1 flex flex-wrap items-center gap-2"><span className="rounded-md bg-gold-soft px-2 py-0.5 text-xs font-semibold text-warn">{k.channel}</span><span className="min-w-40 flex-1">{k.summary}</span>
                      {k.status === "open" ? ["upheld", "goodwill", "reversed"].map((o) => <Button key={o} className="!px-2 !py-1 text-xs" onClick={() => run(async () => { const r = await fetch(`/api/complaints/${k.id}/resolve`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ outcome: o, note: o === "upheld" ? "Rejection stands" : o === "goodwill" ? "Goodwill gesture agreed" : "Refund issued after complaint" }) }); return r.ok ? {} : { ok: false, error: (await r.json()).detail }; })}>{o === "upheld" ? "Rejection stands" : o === "goodwill" ? "Goodwill" : "Refund now"}</Button>)
                        : <span className="text-xs font-semibold text-ok">{k.outcome}</span>}
                    </div>
                  ))}
                  <div className="mt-2 flex flex-wrap gap-2">
                    <select value={cform.channel} onChange={(e) => setCform({ ...cform, channel: e.target.value })} className="rounded-lg border border-line bg-paper px-2 py-1 text-xs">{CH.map((c) => <option key={c}>{c}</option>)}</select>
                    <input value={cform.summary} onChange={(e) => setCform({ ...cform, summary: e.target.value })} placeholder="What did the customer say?" className="min-w-40 flex-1 rounded-lg border border-line bg-paper px-2 py-1 text-xs" />
                    <Button className="!px-2 !py-1 text-xs" onClick={() => run(async () => { const r = await fetch(`/api/cases/${cur.id}/complaint`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(cform) }); setCform({ ...cform, summary: "" }); return r.ok ? {} : { ok: false, error: "could not record" }; })}>Record a complaint</Button>
                  </div>
                </div>
              )}
              {cur.refund && <p className="mt-4 rounded-xl bg-ok-bg p-3 text-sm font-semibold text-ok">Refunded {inr(cur.refund.amount_inr)} · {cur.refund.issued_by} (recorded in the ledger, not paid out)</p>}

              {cur.status === "held" && (
                <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-line pt-4">
                  {cur.signed_approval_required ? (
                    wa && !wa.registered
                      ? <Button kind="gold" onClick={() => run(registerOwnerKey)}>Set up Touch ID (one time)</Button>
                      : <Button kind="ok" onClick={() => run(() => approveWithTouchId(cur.id))}>🔒 Approve with Touch ID</Button>
                  ) : <Button kind="ok" onClick={() => run(() => post(`/api/cases/${cur.id}/owner/approve`))}>Approve refund</Button>}
                  <Button kind="bad" onClick={() => run(() => post(`/api/cases/${cur.id}/owner/reject`))}>Reject</Button>
                  {cur.signed_approval_required && <span className="text-xs text-warn">Above the limit: only your fingerprint can release this.</span>}
                </div>
              )}
              {msg && <p className="mt-2 text-sm text-bad">{msg}</p>}
              <a href="#/architecture" className="mt-4 inline-block text-sm font-semibold text-plum-3">Watch this case move through the system →</a>
            </Card>

            <Card className="p-5">
              <SectionTitle>Audit trail</SectionTitle>
              <ol className="space-y-2">
                {cur.events.map((e, i) => (
                  <li key={i} className="flex gap-3 text-sm">
                    <span className="mt-0.5"><WhoTag who={STEP_WHO[e.step] || "ours"} /></span>
                    <span className="min-w-0"><b className="capitalize">{e.step.replaceAll("_", " ")}</b><span className="block break-words text-muted">{e.detail.slice(0, 220)}</span></span>
                  </li>
                ))}
              </ol>
            </Card>
          </div>
        )}
      </div>
    </div>
  );
}
