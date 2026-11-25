import { useEffect, useRef, useState } from "react";
import { Card, DecisionBadge } from "../ui.jsx";

const LANGS = ["ગુજરાતી", "हिन्दी", "ಕನ್ನಡ", "English"];

// What the shopper sees: one big button, speak in your own language, hear the answer.
export default function Customer({ orderId }) {
  const [order, setOrder] = useState(null);
  useEffect(() => { setOrder(null); if (orderId) fetch(`/api/orders/${orderId}`).then((r) => (r.ok ? r.json() : null)).then(setOrder).catch(() => {}); }, [orderId]);
  const [rec, setRec] = useState(false), [busy, setBusy] = useState(false), [res, setRes] = useState(null), [err, setErr] = useState(null);
  const mr = useRef(null), chunks = useRef([]);

  async function start() {
    setErr(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mr.current = new MediaRecorder(stream); chunks.current = [];
      mr.current.ondataavailable = (e) => chunks.current.push(e.data);
      mr.current.onstop = () => { stream.getTracks().forEach((t) => t.stop()); send(new Blob(chunks.current, { type: mr.current.mimeType })); };
      mr.current.start(); setRec(true);
    } catch (e) { setErr("Microphone not available: " + e.message); }
  }
  async function send(blob) {
    setBusy(true); setRes(null);
    const f = new FormData(); f.append("audio", blob, "return.webm"); if (orderId) f.append("order_id", orderId);
    try {
      const r = await fetch("/api/intake", { method: "POST", body: f }); const j = await r.json();
      if (!r.ok) throw new Error(j.detail || `HTTP ${r.status}`);
      setRes(j); if (j.reply_audio_wav_b64) new Audio("data:audio/wav;base64," + j.reply_audio_wav_b64).play().catch(() => {});
    } catch (e) { setErr(e.message); }
    setBusy(false);
  }

  return (
    <div className="mx-auto max-w-sm">
      <Card className="overflow-hidden">
        <div className="bg-gradient-to-br from-plum to-plum-2 px-6 pb-8 pt-6 text-center text-ivory">
          <p className="text-xs font-semibold uppercase tracking-wide text-gold-soft">Your return</p>
          <h1 className="display mt-1 text-2xl font-semibold">Tell us what happened</h1>
          <p className="mt-1 text-sm text-ivory/80">{order ? "Just tell us why you are returning it." : "Speak in your language. Say your order number and why you are returning it."}</p>
          {order && (
            <div className="mx-auto mt-3 max-w-xs rounded-xl bg-white/10 p-3 text-left text-sm">
              <p className="text-xs text-gold-soft">Your order {order.id}</p><p className="font-semibold">{order.item}</p>
              <p className="num text-ivory/80">₹{Number(order.amount_inr).toLocaleString("en-IN")} · delivered {order.delivered_days_ago} days ago</p>
            </div>
          )}
          <div className="mt-3 flex flex-wrap justify-center gap-1.5">{LANGS.map((l) => <span key={l} className="rounded-full bg-white/15 px-2.5 py-0.5 text-xs">{l}</span>)}</div>
        </div>
        <div className="px-6 py-6 text-center">
          <button onClick={rec ? () => { mr.current?.stop(); setRec(false); } : start} disabled={busy}
            className={`mx-auto -mt-16 flex h-28 w-28 items-center justify-center rounded-full border-4 border-paper text-3xl text-white shadow-lg transition ${rec ? "animate-pulse bg-bad" : "bg-gold hover:opacity-90"} disabled:bg-stone-400`}>
            {busy ? "…" : rec ? "■" : "🎤"}
          </button>
          <p className="mt-3 text-sm text-muted">{busy ? "Understanding your request…" : rec ? "Listening… tap to finish" : "Tap and speak (up to 30 seconds)"}</p>
          <p className="mt-1 text-xs text-muted">{order ? "Example: “The blouse is too tight, I have not worn it.”" : "Example: “My order is SHP-2002, the size is wrong, I have not worn it.”"}</p>
          {err && <p className="mt-3 rounded-xl bg-bad-bg p-2 text-sm text-bad">{err}</p>}
        </div>
        {res && (
          <div className="pop space-y-3 border-t border-line bg-ivory px-6 py-5 text-left">
            <div><p className="text-xs font-semibold uppercase tracking-wide text-muted">We heard</p><p className="mt-0.5">{res.transcript}</p></div>
            <div><p className="text-xs font-semibold uppercase tracking-wide text-muted">Our answer</p><p className="display mt-0.5 text-lg font-semibold text-plum">{res.reply_text}</p></div>
            <div className="flex items-center gap-2"><DecisionBadge d={res.case.decision} /><span className="text-xs text-muted">Case #{res.case.id}</span></div>
          </div>
        )}
      </Card>
    </div>
  );
}
