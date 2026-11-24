"""Languages the customer can speak back to us. Voices are from the Bulbul v4 Flash catalogue
(docs.sarvam.ai/api/api-guides-tutorials/text-to-speech/voices)."""
LANGUAGES = {
    "gu-IN": {"name": "Gujarati", "voice": "pooja_gu_customer"},
    "hi-IN": {"name": "Hindi", "voice": "ritu_hi_conversation"},
    "kn-IN": {"name": "Kannada", "voice": "chaitra_kn_conversation"},
    "en-IN": {"name": "English", "voice": "simran_en_customer"},
}
FALLBACK = "hi-IN"  # used if speech-to-text cannot tell the language


def get(code: str | None) -> dict:
    code = code if code in LANGUAGES else FALLBACK
    return {"code": code, **LANGUAGES[code]}
