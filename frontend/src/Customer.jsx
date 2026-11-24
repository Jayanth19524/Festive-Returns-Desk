import { useRef, useState } from "react";

// Customer screen: hold the mic button, speak the return reason in Gujarati / Hindi / Kannada, hear the decision.
export default function Customer() {
  const [recording, setRecording] = useState(false);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const rec = useRef(null);
  const chunks = useRef([]);

  async function start() {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      rec.current = new MediaRecorder(stream);
      chunks.current = [];
      rec.current.ondataavailable = (e) => chunks.current.push(e.data);
      rec.current.onstop = () => { stream.getTracks().forEach((t) => t.stop()); send(new Blob(chunks.current, { type: rec.current.mimeType })); };
      rec.current.start();
      setRecording(true);
    } catch (e) { setError("Microphone not available: " + e.message); }
  }
  const stop = () => { rec.current?.stop(); setRecording(false); };

  async function send(blob) {
    setBusy(true); setResult(null);
    const form = new FormData();
    form.append("audio", blob, "return.webm");
    try {
      const r = await fetch("/api/intake", { method: "POST", body: form });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || `HTTP ${r.status}`);
      setResult(j);
      if (j.reply_audio_wav_b64) new Audio("data:audio/wav;base64," + j.reply_audio_wav_b64).play().catch(() => {});
    } catch (e) { setError(e.message); }
    setBusy(false);
  }

  return (
    <div className="mx-auto max-w-md space-y-4 text-center">
      <p className="text-stone-600">Press and speak: your order number (like GRD-1001) and why you are returning it. Gujarati, Hindi, Kannada or English. Up to 30 seconds.</p>
      <button
        onClick={recording ? stop : start} disabled={busy}
        className={`h-32 w-32 rounded-full text-lg font-semibold text-white shadow-lg ${recording ? "animate-pulse bg-red-600" : "bg-orange-600"} disabled:bg-stone-400`}>
        {busy ? "Working…" : recording ? "Stop" : "🎤 Speak"}
      </button>
      {error && <p className="rounded bg-red-100 p-2 text-red-800">{error}</p>}
      {result && (
        <div className="space-y-2 rounded border bg-white p-4 text-left">
          <p className="text-sm text-stone-500">We heard ({result.detected_language}):</p>
          <p className="text-lg">{result.transcript}</p>
          <p className="text-sm text-stone-500">Reply:</p>
          <p className="text-lg font-semibold">{result.reply_text}</p>
          <p className="text-xs text-stone-500">Decision: {result.case.decision.toUpperCase()}. Case #{result.case.id}</p>
        </div>
      )}
    </div>
  );
}
