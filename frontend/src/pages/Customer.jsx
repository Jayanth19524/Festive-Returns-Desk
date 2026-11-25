import { useEffect, useRef, useState } from "react";
import { Card, DecisionBadge } from "../ui.jsx";

const LANGS = ["ગુજરાતી", "हिन्दी", "ಕನ್ನಡ", "English"];

// What the shopper sees: one big button, speak in your own language, hear the answer.
export default function Customer({ orderId }) {
  const [order, setOrder] = useState(null);
  useEffect(() => { setOrder(null); if (orderId) fetch(`/api/orders/${orderId}`).then((r) => (r.ok ? r.json() : null)).then(setOrder).catch(() => {}); }, [orderId]);
  const [rec, setRec] = useState(false), [busy, setBusy] = useState(false), [res, setRes] = useState(null), [err, setErr] = useState(null);
  const mr = useRef(null), chunks = useRef([]);
  const [photo, setPhoto] = useState(null);          // {blob, url}: the shopper's photo of the item, shrunk to a JPEG in the browser

  async function pick(file) {
    if (!file) return;
    const bmp = await createImageBitmap(file);
    const k = Math.min(1, 1024 / Math.max(bmp.width, bmp.height));
    const cv = document.createElement("canvas"); cv.width = Math.round(bmp.width * k); cv.height = Math.round(bmp.height * k);
    cv.getContext("2d").drawImage(bmp, 0, 0, cv.width, cv.height);
    const blob = await new Promise((ok) => cv.toBlob(ok, "image/jpeg", 0.85));
    setPhoto({ blob, url: URL.createObjectURL(blob) });
  }

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
    const f = new FormData(); f.append("audio", blob, "return.webm"); if (photo) f.append("photo", photo.blob, "item.jpg"); if (orderId) f.append("order_id", orderId);
    try {
      const r = await fetch("/api/intake", { method: "POST", body: f }); const j = await r.json();
      if (!r.ok) throw new Error(j.detail || `HTTP ${r.status}`);
      setRes(j); if (j.reply_audio_wav_b64) new Audio("data:audio/wav;base64," + j.reply_audio_wav_b64).play().catch(() => {});
    } catch (e) { setErr(e.message); }
    setBusy(false);
  }

  if (order?.return) {
    return (
      <div className="mx-auto max-w-sm"><Card className="p-6 text-center">
        <p className="display text-xl font-semibold text-plum">A return for {order.id} is already {order.return.status === "approved_refunded" ? "approved and refunded" : order.return.status === "rejected" ? "closed" : "in review"}</p>
        <p className="mt-2 text-sm text-muted">{order.item}</p><a className="mt-4 inline-block text-sm font-semibold text-plum-3" href="#/shop/orders">Back to my orders</a>
      </Card></div>
    );
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
        <div className="border-b border-line px-6 py-5">
          <p className="text-sm font-semibold text-plum">Step 1 · Show us the item</p>
          <p className="text-xs text-muted">A clear photo of the whole item (and the problem, if there is one). In this demo the photo may be analysed by an AI service: use a demo photo.</p>
          <label className="mt-3 flex cursor-pointer items-center gap-3 rounded-xl border border-dashed border-gold bg-ivory p-3 text-sm">
            {photo ? <img src={photo.url} alt="your item" className="h-16 w-16 rounded-lg object-cover" /> : <span className="flex h-16 w-16 items-center justify-center rounded-lg bg-gold-soft text-2xl">📷</span>}
            <span className="font-semibold">{photo ? "Change photo" : "Take or upload a photo"}</span>
            <input type="file" accept="image/*" capture="environment" className="hidden" onChange={(e) => pick(e.target.files?.[0]).catch((x) => setErr("Could not read that photo: " + x.message))} />
          </label>
        </div>
        <div className="px-6 py-6 text-center">
          <p className="mb-3 text-sm font-semibold text-plum">Step 2 · Tell us why</p>
          <button onClick={rec ? () => { mr.current?.stop(); setRec(false); } : start} disabled={busy || !photo}
            className={`mx-auto flex h-28 w-28 items-center justify-center rounded-full border-4 border-paper text-3xl text-white shadow-lg transition ${rec ? "animate-pulse bg-bad" : "bg-gold hover:opacity-90"} disabled:bg-stone-400`}>
            {busy ? "…" : rec ? "■" : "🎤"}
          </button>
          <p className="mt-3 text-sm text-muted">{busy ? "Looking at your photo and listening…" : rec ? "Listening… tap to finish" : photo ? "Tap and speak (up to 30 seconds)" : "Add a photo first"}</p>
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
