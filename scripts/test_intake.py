#!/usr/bin/env python3
"""Phase 1 test: 3 phrases (Gujarati, Hindi, Kannada) -> Saaras STT -> 105B JSON -> Bulbul reply.

The test audio is SYNTHETIC (made with Bulbul TTS from the phrase below), because no recordings exist yet.
That is easier than real phone audio, so treat accuracy as an upper bound. Real recordings: pass --wav FILE=expected_lang.
Run:  .venv/bin/python scripts/test_intake.py
"""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from app import sarvam_service as sv  # noqa: E402

CASES = [  # (language, text spoken, expected case fields)
    ("gu-IN", "મારો ઓર્ડર GRD-1001 છે. ચણિયાચોળી મને ફિટ થતી નથી, સાઈઝ ખોટી છે. મેં તે પહેરી નથી.",
     {"order_id": "GRD-1001", "reason_category": "wrong_size", "claimed_condition": "unworn"}),
    ("hi-IN", "मेरा ऑर्डर GRD-1002 है। मैंने यह लहंगा एक बार गरबा में पहना था, अब वापस करना है।",
     {"order_id": "GRD-1002", "reason_category": "worn_once", "claimed_condition": "worn"}),
    ("kn-IN", "ನನ್ನ ಆರ್ಡರ್ GRD-1003. ಸೀರೆ ಹರಿದು ಬಂದಿದೆ, ಹಾಳಾಗಿದೆ. ದಯವಿಟ್ಟು ಹಣ ವಾಪಸ್ ಕೊಡಿ.",
     {"order_id": "GRD-1003", "reason_category": "damaged", "claimed_condition": "damaged"}),
]

for lang, text, want in CASES:
    print(f"\n=== {lang} ===\nspoken text : {text}")
    wav = sv.speak(text, lang)  # synthetic "customer"
    t0 = time.time(); transcript, detected = sv.transcribe(wav, "t.wav", "audio/wav"); t1 = time.time()
    case = sv.extract(transcript); t2 = time.time()
    reply = sv.speak("ok", detected or lang); t3 = time.time()
    print(f"STT         : {transcript}   (detected {detected}, {t1-t0:.1f}s)")
    print(f"105B JSON   : {case}   ({t2-t1:.1f}s)")
    print(f"TTS reply   : {len(reply)} bytes WAV ({t3-t2:.1f}s)")
    print(f"lang correct: {detected == lang}")
    for k, v in want.items():
        print(f"  {k:18} want={v!r:14} got={case[k]!r:14} {'OK' if case[k]==v else 'MISMATCH'}")
