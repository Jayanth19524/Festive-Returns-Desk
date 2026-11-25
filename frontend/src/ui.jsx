// Small shared pieces: money, badges, cards, sponsor tags. Everything visual lives in index.css tokens.
import { createContext } from "react";
export const ShopContext = createContext({});
export const inr = (n) => "₹" + Number(n || 0).toLocaleString("en-IN", { maximumFractionDigits: 0 });

const DECISION = {
  approve: ["Auto-approved", "bg-ok-bg text-ok"],
  hold: ["Needs you", "bg-warn-bg text-warn"],
  reject: ["Rejected", "bg-bad-bg text-bad"],
};
export const DecisionBadge = ({ d }) => {
  const [label, cls] = DECISION[d] || [d, "bg-line text-ink"];
  return <span className={`inline-block whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-semibold ${cls}`}>{label}</span>;
};

const STATUS = {
  approved_refunded: ["Refunded", "bg-ok-bg text-ok"], held: ["Waiting for you", "bg-warn-bg text-warn"],
  rejected: ["Rejected", "bg-bad-bg text-bad"], awaiting_workflow: ["Workflow running", "bg-gold-soft text-warn"],
};
export const StatusBadge = ({ s }) => {
  const [label, cls] = STATUS[s] || [s, "bg-line text-ink"];
  return <span className={`inline-block whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-semibold ${cls}`}>{label}</span>;
};

export const Card = ({ className = "", children }) => (
  <div className={`rounded-2xl border border-line bg-paper shadow-[0_1px_2px_rgba(59,22,54,0.04)] ${className}`}>{children}</div>
);

export const Kpi = ({ label, value, sub, tone = "plain" }) => (
  <Card className="p-4">
    <p className="text-xs font-medium uppercase tracking-wide text-muted">{label}</p>
    <p className={`display num mt-1 text-3xl font-semibold ${tone === "warn" ? "text-warn" : tone === "ok" ? "text-ok" : "text-plum"}`}>{value}</p>
    {sub && <p className="mt-1 text-xs text-muted">{sub}</p>}
  </Card>
);

export const SectionTitle = ({ children, hint }) => (
  <div className="mb-3 flex items-baseline justify-between gap-2">
    <h2 className="display text-lg font-semibold text-plum">{children}</h2>
    {hint && <span className="text-xs text-muted">{hint}</span>}
  </div>
);

// Who did the work. Colours identify the sponsor; "ours" is our own code.
export const WHO = {
  sarvam: { label: "Sarvam AI", cls: "bg-orange-100 text-orange-800", dot: "#ea580c" },
  flagsmith: { label: "Flagsmith", cls: "bg-violet-100 text-violet-800", dot: "#7c3aed" },
  nudgebee: { label: "NudgeBee", cls: "bg-amber-100 text-amber-900", dot: "#d9a400" },
  ours: { label: "Our code", cls: "bg-plum/10 text-plum", dot: "#3b1636" },
  owner: { label: "Owner", cls: "bg-gold-soft text-warn", dot: "#b8923a" },
  customer: { label: "Customer", cls: "bg-stone-100 text-stone-700", dot: "#78716c" },
};
export const WhoTag = ({ who }) => {
  const w = WHO[who] || WHO.ours;
  return <span className={`inline-block whitespace-nowrap rounded-md px-2 py-0.5 text-xs font-semibold ${w.cls}`}>{w.label}</span>;
};

export const Button = ({ kind = "plain", className = "", ...p }) => {
  const k = { primary: "bg-plum text-white hover:bg-plum-2", gold: "bg-gold text-white hover:opacity-90", ok: "bg-ok text-white hover:opacity-90",
    bad: "bg-bad text-white hover:opacity-90", plain: "border border-line bg-paper text-ink hover:bg-ivory" }[kind];
  return <button {...p} className={`rounded-xl px-3.5 py-2 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-40 ${k} ${className}`} />;
};
