import usePoll from "../usePoll.js";
import { Card, SectionTitle, inr } from "../ui.jsx";

// Return Intelligence: why customers return, how much is preventable, and what to fix first. All from our own database.
export default function Insights({ compact = false }) {
  const { data: ins } = usePoll("/api/insights", 5000);
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
      {!compact && (
        <Card className="p-5">
          <SectionTitle>Most-returned products</SectionTitle>
          <div className="divide-y divide-line text-sm">
            {ins.worst_items.map((i) => (
              <div key={i.item} className="flex justify-between py-2"><span>{i.item}</span><span className="text-muted">{i.count} returns · mostly {i.main_reason.replaceAll("_", " ")}</span></div>
            ))}
          </div>
          <p className="mt-3 text-xs text-muted">Simulated data. “Preventable” counts size and description returns; it is a baseline to measure against, not a claim that any return was prevented.</p>
        </Card>
      )}
    </div>
  );
}
