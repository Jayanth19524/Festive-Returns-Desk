import { useState } from "react";
import usePoll from "../usePoll.js";
import { Button, Card, DecisionBadge, SectionTitle, WhoTag, inr } from "../ui.jsx";

const post = (u, b) => fetch(u, { method: "POST", headers: { "Content-Type": "application/json" }, body: b && JSON.stringify(b) }).then(async (r) => ({ ok: r.ok, j: await r.json().catch(() => ({})) }));
const SEV = { high: "border-bad bg-bad-bg", medium: "border-warn/40 bg-warn-bg/60" };

// Pace of returns over the last five minutes, with the surge level drawn as a dashed line.
function Pace({ series, level }) {
  const W = 600, H = 120, max = Math.max(level * 1.4, ...series, 1);
  const pts = series.map((v, i) => [(i / (series.length - 1)) * W, H - (v / max) * (H - 8) - 4]);
  const line = pts.map((p) => p.join(",")).join(" ");
  const ly = H - (level / max) * (H - 8) - 4;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full">
      <polygon points={`0,${H} ${line} ${W},${H}`} fill="#b8923a22" />
      <line x1="0" x2={W} y1={ly} y2={ly} stroke="#b3261e" strokeDasharray="6 5" strokeWidth="1.5" />
      <text x={W - 4} y={ly - 5} textAnchor="end" fontSize="11" fill="#b3261e" fontWeight="600">surge level ({level})</text>
      <polyline points={line} fill="none" stroke="#3b1636" strokeWidth="2.5" strokeLinejoin="round" />
      <circle cx={pts.at(-1)[0]} cy={pts.at(-1)[1]} r="4.5" fill="#3b1636" />
    </svg>
  );
}

export default function Live() {
  const { data: live } = usePoll("/api/live", 1500);
  const { data: sug } = usePoll("/api/live/suggestions", 2500);
  const { data: brief } = usePoll("/api/live/brief", 7000);
  const [applied, setApplied] = useState({});   // flag -> {from, to}
  const [note, setNote] = useState("");
  if (!live) return <p className="text-muted">Loading…</p>;
  const sim = live.simulation, w = live.last5;

  const apply = async (s) => {
    const v = (x) => (x === "on" || x === "off" ? x : String(x));
    const r = await post("/api/demo/flag", { name: s.flag, value: v(s.proposed) });
    if (r.ok) { setApplied((a) => ({ ...a, [s.flag]: { from: s.current, to: s.proposed } })); setNote(`Flagsmith updated: ${s.flag} → ${s.proposed}. New returns now follow it.`); }
    else setNote(r.j.detail || "Could not change the flag");
  };
  const undo = async (flag) => {
    const a = applied[flag]; const r = await post("/api/demo/flag", { name: flag, value: String(a.from) });
    if (r.ok) { setApplied(({ [flag]: _, ...rest }) => rest); setNote(`Flagsmith restored: ${flag} → ${a.from}`); }
  };

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div><h1 className="display text-3xl font-semibold text-plum">Live monitor</h1>
          <p className="text-muted">Returns arriving right now, how fast, and what to switch on or off when it gets busy.</p></div>
        <div className="flex flex-wrap items-center gap-2">
          {!sim.running && sim.filed > 0 && <Button onClick={async () => { await post("/api/demo/stream/clear"); setApplied({}); setNote("Simulated returns cleared: the intelligence pages are back to the base data."); }}>Clear simulated returns</Button>}
          {sim.running ? <Button kind="bad" onClick={() => post("/api/demo/stream/stop")}>■ Stop</Button>
            : <Button kind="primary" onClick={() => { setApplied({}); post("/api/demo/stream/start"); }}>▶ Start festive-rush simulation</Button>}
          <a href="http://localhost:3000/automation#executions" target="_blank" rel="noreferrer" className="rounded-xl border border-line bg-paper px-3.5 py-2 text-sm font-semibold hover:bg-ivory">Open NudgeBee runs ↗</a>
        </div>
      </div>

      <div className={`flex flex-wrap items-center gap-3 rounded-2xl border-2 p-4 ${live.surge ? "animate-pulse border-bad bg-bad-bg" : "border-ok/40 bg-ok-bg"}`}>
        <span className={`display text-xl font-semibold ${live.surge ? "text-bad" : "text-ok"}`}>{live.surge ? "⚠ Surge: returns are flooding in" : "Normal pace"}</span>
        <span className="text-sm"><b className="num">{live.in_window}</b> returns in the last {live.window_sec} s (alert at {live.surge_at})</span>
        {sim.phase !== "idle" && <span className="ml-auto rounded-full bg-paper px-3 py-1 text-xs font-semibold">Simulation: {sim.phase} · {sim.filed}/{sim.total} customers</span>}
      </div>

      <div className="grid gap-5 lg:grid-cols-5">
        <div className="space-y-5 lg:col-span-3">
          <Card className="p-4"><SectionTitle hint="returns in the trailing minute, last 5 minutes">Pace of returns</SectionTitle><Pace series={live.series} level={live.surge_at} /></Card>

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[["Waiting for you", live.waiting, `${inr(live.waiting_inr)}`, "text-warn"], ["Auto-approved", w.auto_approved, "last 5 min", "text-ok"],
              ["Held", w.held, "last 5 min", "text-warn"], ["Rejected", w.rejected, "last 5 min", "text-bad"]].map(([k, v, sub, c]) => (
              <Card key={k} className="p-3"><p className="text-xs uppercase tracking-wide text-muted">{k}</p><p className={`display num text-3xl font-semibold ${c}`}>{v}</p><p className="text-xs text-muted">{sub}</p></Card>
            ))}
          </div>

          <section>
            <SectionTitle hint="each one ran through Sarvam, Flagsmith and a NudgeBee workflow">Customers returning now</SectionTitle>
            <Card className="divide-y divide-line">
              {!live.feed.length && <p className="p-5 text-center text-sm text-muted">Nothing yet. Press “Start festive-rush simulation”.</p>}
              {live.feed.map((f) => (
                <a key={f.id} href={`#/desk/${f.id}`} className="pop flex flex-wrap items-center gap-2 px-4 py-2.5 text-sm hover:bg-ivory">
                  <span className="num w-12 text-xs text-muted">{f.ago_sec}s ago</span>
                  <span className="min-w-40 flex-1"><b>{f.item || f.order_id}</b> <span className="num text-muted">{inr(f.amount_inr)}</span><span className="ml-2 text-xs text-muted">{f.reason.replaceAll("_", " ")} · {f.language}</span></span>
                  <DecisionBadge d={f.decision} />
                  <span className={`rounded-md px-2 py-0.5 text-xs font-semibold ${f.nudgebee_steps ? "bg-amber-100 text-amber-900" : "bg-line text-muted"}`}>{f.nudgebee_steps ? "NudgeBee ✓" : "NudgeBee running…"}</span>
                </a>
              ))}
            </Card>
          </section>
        </div>

        <div className="space-y-4 lg:col-span-2">
          <SectionTitle hint="computed on the returns that just arrived">What to do now</SectionTitle>
          {brief?.text && (
            <Card className="border-orange-200 p-4 text-sm"><div className="mb-1 flex items-center gap-2"><WhoTag who="sarvam" /><span className="text-xs text-muted">{brief.model}</span></div>{brief.text}</Card>
          )}
          {note && <p className="rounded-xl bg-gold-soft px-3 py-2 text-sm text-warn">{note}</p>}
          {!sug?.length && !Object.keys(applied).length && <Card className="p-5 text-sm text-muted">No action needed. When returns surge, the flag changes that would help most appear here, each with its computed effect.</Card>}
          {Object.entries(applied).map(([flag, a]) => (
            <Card key={flag} className="border-ok/40 bg-ok-bg p-4 text-sm"><p className="font-semibold text-ok">Applied: {flag} {String(a.from)} → {String(a.to)}</p>
              <p className="text-muted">Flagsmith is updated. The next returns follow the new rule.</p><Button className="mt-2 !py-1 text-xs" onClick={() => undo(flag)}>Undo</Button></Card>
          ))}
          {(sug || []).filter((s) => !applied[s.flag]).map((s) => (
            <Card key={s.flag} className={`pop border p-4 ${SEV[s.severity] || ""}`}>
              <div className="flex items-start justify-between gap-2"><p className="font-semibold text-plum">{s.title}</p><span className="rounded-md bg-paper px-2 py-0.5 text-[11px] font-semibold uppercase text-muted">{s.severity}</span></div>
              <p className="mt-1 text-sm">{s.why}</p>
              <p className="mt-1.5 text-sm text-muted"><b className="text-ink">Effect:</b> {s.effect}</p>
              <div className="mt-2 flex flex-wrap items-center gap-2"><WhoTag who="flagsmith" /><span className="font-mono text-xs">{s.flag}: {String(s.current)} → {String(s.proposed)}</span>
                <Button kind="primary" className="ml-auto !py-1.5 text-xs" onClick={() => apply(s)}>Apply in Flagsmith</Button></div>
            </Card>
          ))}
          <p className="text-xs text-muted">Suggestions are recommendations: nothing changes until you press Apply. “Effect” re-runs the same plain-code rule on these returns under the new value.</p>
        </div>
      </div>
    </div>
  );
}
