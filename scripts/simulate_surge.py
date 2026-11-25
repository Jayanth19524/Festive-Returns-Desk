#!/usr/bin/env python3
"""Simulate a post-Navratri returns surge against the running app. ALL DATA IS SIMULATED.

  .venv/bin/python scripts/simulate_surge.py --n 40 --voice 4

--n      how many returns to file (max 60: one per simulated order GRD-2001..2060; resets the DB first)
--voice  how many of them go through the REAL voice pipeline (Bulbul makes synthetic speech -> Saaras -> 105B -> rule -> NudgeBee).
         The rest are filed as already-structured cases (same rule, same NudgeBee workflow, no Sarvam calls).
Prints the outcome mix, the refunds issued, and how long the surge took.
"""
import argparse, io, json, random, sys, time, urllib.request, uuid
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
from app import sarvam_service as sv  # noqa: E402  (loads .env)

API = "http://localhost:8200"
# (reason_category, claimed_condition, weight) : a realistic mix, wrong size is the most common
MIX = [("wrong_size", "unworn", 40), ("changed_mind", "unworn", 20), ("damaged", "damaged", 15),
       ("worn_once", "worn", 20), ("not_as_described", "unknown", 5)]
PHRASES = {  # spoken sentences per language and reason; {id} is the order id
    "gu-IN": {"wrong_size": "મારો ઓર્ડર {id} છે. સાઈઝ ખોટી છે, મેં તે પહેરી નથી.",
              "worn_once": "મારો ઓર્ડર {id} છે. મેં તે ગરબામાં એક વાર પહેર્યું હતું, હવે પાછું આપવું છે.",
              "damaged": "મારો ઓર્ડર {id} છે. કપડું ફાટેલું આવ્યું છે.",
              "changed_mind": "મારો ઓર્ડર {id} છે. મને પસંદ નથી આવ્યું, પાછું આપવું છે.",
              "not_as_described": "મારો ઓર્ડર {id} છે. ફોટા કરતાં રંગ અલગ છે."},
    "hi-IN": {"wrong_size": "मेरा ऑर्डर {id} है। साइज़ गलत है, मैंने इसे पहना नहीं है।",
              "worn_once": "मेरा ऑर्डर {id} है। मैंने इसे एक बार गरबा में पहना था, अब वापस करना है।",
              "damaged": "मेरा ऑर्डर {id} है। कपड़ा फटा हुआ आया है।",
              "changed_mind": "मेरा ऑर्डर {id} है। मुझे पसंद नहीं आया, वापस करना है।",
              "not_as_described": "मेरा ऑर्डर {id} है। फोटो से रंग अलग है।"},
    "kn-IN": {"wrong_size": "ನನ್ನ ಆರ್ಡರ್ {id}. ಸೈಜ್ ತಪ್ಪಾಗಿದೆ, ನಾನು ಇದನ್ನು ಧರಿಸಿಲ್ಲ.",
              "worn_once": "ನನ್ನ ಆರ್ಡರ್ {id}. ನಾನು ಇದನ್ನು ಗರ್ಬಾದಲ್ಲಿ ಒಮ್ಮೆ ಧರಿಸಿದ್ದೆ, ಈಗ ವಾಪಸ್ ಕೊಡಬೇಕು.",
              "damaged": "ನನ್ನ ಆರ್ಡರ್ {id}. ಬಟ್ಟೆ ಹರಿದು ಬಂದಿದೆ.",
              "changed_mind": "ನನ್ನ ಆರ್ಡರ್ {id}. ನನಗೆ ಇಷ್ಟವಾಗಲಿಲ್ಲ, ವಾಪಸ್ ಕೊಡಬೇಕು.",
              "not_as_described": "ನನ್ನ ಆರ್ಡರ್ {id}. ಫೋಟೋಗಿಂತ ಬಣ್ಣ ಬೇರೆ ಇದೆ."},
}


def call(path, body=None, files=None):
    if files:
        b = uuid.uuid4().hex
        data = (f"--{b}\r\nContent-Disposition: form-data; name=\"audio\"; filename=\"r.wav\"\r\nContent-Type: audio/wav\r\n\r\n").encode() + files + f"\r\n--{b}--\r\n".encode()
        req = urllib.request.Request(API + path, data=data, method="POST", headers={"Content-Type": f"multipart/form-data; boundary={b}"})
    else:
        req = urllib.request.Request(API + path, method="POST" if body is not None else "GET",
                                     data=json.dumps(body).encode() if body is not None else None, headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=120).read())


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--n", type=int, default=40); ap.add_argument("--voice", type=int, default=4)
    a = ap.parse_args(); n = min(a.n, 60); rnd = random.Random(42)
    call("/api/demo/reset", {})
    t0 = time.time(); voice_ok = voice_fail = 0
    reasons = rnd.choices([m[:2] for m in MIX], weights=[m[2] for m in MIX], k=n)
    for i, (reason, cond) in enumerate(reasons):
        oid = f"GRD-{2001 + i}"
        if i < a.voice:
            lang = ["gu-IN", "hi-IN", "kn-IN"][i % 3]
            try:
                r = call("/api/intake", files=sv.speak(PHRASES[lang][reason].format(id=oid), lang))
                voice_ok += 1
                print(f"  voice {oid} {lang}: heard '{r['transcript'][:50]}…' -> {r['fields']['reason_category']}/{r['fields']['claimed_condition']} -> {r['case']['decision']}")
                continue
            except Exception as e:  # report, do not hide
                voice_fail += 1; print(f"  voice {oid} FAILED: {e}")
        call("/api/cases", {"order_id": oid, "reason_category": reason, "claimed_condition": cond, "language": rnd.choice(list(PHRASES))})
    filed = time.time() - t0
    print(f"\nfiled {n} returns in {filed:.1f}s ({voice_ok} via real voice, {voice_fail} voice failures). Waiting for NudgeBee to finish…")
    for _ in range(40):  # wait until nothing is still awaiting the workflow
        st = call("/api/stats")
        if not st["by_status"].get("awaiting_workflow"): break
        time.sleep(3)
    print(f"all settled {time.time() - t0:.0f}s after the first return\n")
    print("decisions     :", st["by_decision"]); print("case status   :", st["by_status"])
    print(f"refunds issued: {st['refund_count']} totalling Rs {st['refunded_inr']:,.0f}")
    print(f"waiting for you: Rs {st['held_value_inr']:,.0f} of held refunds")


if __name__ == "__main__":
    main()
