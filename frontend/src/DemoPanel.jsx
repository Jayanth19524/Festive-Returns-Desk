import { useState } from "react";
import usePoll from "./usePoll.js";
import { Button, inr } from "./ui.jsx";

const post = (u, b) => fetch(u, { method: "POST", headers: { "Content-Type": "application/json" }, body: b && JSON.stringify(b) }).then(async (r) => ({ ok: r.ok, j: await r.json().catch(() => ({})) }));
const SCEN = [["clean", "Clean return"], ["worn", "Worn once (garba)"], ["bridal", "₹14,500 bridal lehenga"], ["injection", "Prompt injection"], ["repeat", "Repeat returner"], ["expired", "Past 15 days"]];

// Floating demo controls: file simulated returns and flip Flagsmith values without leaving the app (local only).
export default function DemoPanel() {
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState("");
  const { data: panel } = usePoll("/api/panel", 2000);
  const c = panel?.config;
  const go = async (label, fn) => { setNote(label + "…"); const r = await fn(); setNote(r.ok ? `${label}: done` : `${label}: ${r.j.detail || "failed"}`); };
  const flag = (name, value) => go(`${name} → ${value}`, () => post("/api/demo/flag", { name, value: String(value) }));

  return (
    <div className="fixed bottom-4 right-4 z-50">
      {open && (
        <div className="pop mb-2 max-h-[80vh] w-80 overflow-y-auto rounded-2xl border border-line bg-paper p-4 shadow-2xl">
          <p className="display text-lg font-semibold text-plum">Demo controls</p>
          <p className="mb-3 text-xs text-muted">Simulated data. Local only.</p>

          <p className="text-xs font-semibold uppercase tracking-wide text-muted">A customer files a return</p>
          <div className="mt-1 grid grid-cols-2 gap-1.5">
            {SCEN.map(([n, label]) => <Button key={n} className="!px-2 !py-1.5 text-xs" onClick={() => go(label, () => post(`/api/demo/scenario/${n}`))}>{label}</Button>)}
          </div>

          <p className="mt-4 text-xs font-semibold uppercase tracking-wide text-muted">Live rules (Flagsmith)</p>
          {c && (
            <div className="mt-1 space-y-2 text-sm">
              <div className="flex items-center justify-between"><span>Refund freeze</span>
                <Button kind={c.refunds_enabled ? "bad" : "ok"} className="!py-1 text-xs" onClick={() => flag("refunds_enabled", c.refunds_enabled ? "off" : "on")}>{c.refunds_enabled ? "Freeze refunds" : "Unfreeze"}</Button></div>
              <div className="flex items-center justify-between gap-1"><span>Auto-refund ≤ {inr(c.auto_refund_limit_inr)}</span>
                <span className="flex gap-1">{[1000, 2000, 3000].map((v) => <Button key={v} className="!px-2 !py-1 text-xs" onClick={() => flag("auto_refund_limit_inr", v)}>{v}</Button>)}</span></div>
              <div className="flex items-center justify-between gap-1"><span>Touch ID above {inr(c.hold_above_inr)}</span>
                <span className="flex gap-1">{[5000, 8000, 15000].map((v) => <Button key={v} className="!px-2 !py-1 text-xs" onClick={() => flag("hold_above_inr", v)}>{v / 1000}k</Button>)}</span></div>
              <div className="flex items-center justify-between gap-1"><span>“Worn” points {c.wardrobing_risk_weight}</span>
                <span className="flex gap-1">{[0, 40, 60].map((v) => <Button key={v} className="!px-2 !py-1 text-xs" onClick={() => flag("wardrobing_keywords_risk_weight", v)}>{v}</Button>)}</span></div>
            </div>
          )}

          <p className="mt-4 text-xs font-semibold uppercase tracking-wide text-muted">Data</p>
          <div className="mt-1 flex gap-1.5">
            <Button className="!px-2 !py-1.5 text-xs" onClick={() => go("Reset data", () => post("/api/demo/reset"))}>Reset demo data</Button>
          </div>
          {note && <p className="mt-3 rounded-lg bg-ivory p-2 text-xs text-muted">{note}</p>}
        </div>
      )}
      <button onClick={() => setOpen(!open)} className="ml-auto flex items-center gap-2 rounded-full bg-gold px-4 py-3 text-sm font-semibold text-white shadow-lg hover:opacity-90">
        ⚙ Demo controls
      </button>
    </div>
  );
}
