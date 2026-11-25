"""Vision/text model client for the photo check: any OpenAI-compatible chat endpoint. Standard library only.

Default: Google AI Studio's Gemini through its OpenAI-compatible address (per Google's docs: base URL
https://generativelanguage.googleapis.com/v1beta/openai/ , `Authorization: Bearer <key>`, images as base64 data URIs in `image_url`).
Default model: gemini-3.5-flash-lite (listed as Stable, free tier, image input). Override with LLM_BASE_URL / LLM_MODEL.
Not confirmed by the docs we read: JSON mode on this address, so we do NOT send `response_format`; the prompt asks for JSON and we validate it.
PRIVACY: Google says content sent on the free tier may be used to improve its products. Use demo photos only, or a paid key, for real customers.
If LLM_API_KEY is not set, `configured()` is False and nothing pretends to work.
"""
import json, os, re, time, urllib.error, urllib.request
from dotenv import load_dotenv
from .config import ROOT

DEFAULT_BASE = "https://generativelanguage.googleapis.com/v1beta/openai"
DEFAULT_MODEL = "gemini-3.5-flash-lite"


class LLMError(Exception):
    pass


def _env():
    load_dotenv(ROOT / ".env", override=True)  # pick up a key added while the app runs
    return os.getenv("LLM_API_KEY", ""), (os.getenv("LLM_BASE_URL") or DEFAULT_BASE).rstrip("/"), os.getenv("LLM_MODEL") or DEFAULT_MODEL


def configured() -> bool:
    return bool(_env()[0])


def model_name() -> str:
    return _env()[2]


def chat(messages: list[dict], max_tokens: int = 700, timeout: float = 90.0, retries: int = 1) -> str:
    key, base, model = _env()
    if not key:
        raise LLMError("No vision model is configured (set LLM_API_KEY in .env)")
    body = json.dumps({"model": model, "messages": messages, "temperature": 0, "max_tokens": max_tokens}).encode()
    req = urllib.request.Request(f"{base}/chat/completions", data=body, method="POST",
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    last = ""
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())["choices"][0]["message"]["content"] or ""
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}: {e.read().decode(errors='replace')[:300].replace(key, '<key>')}"
            if e.code in (429, 500, 502, 503, 504) and attempt < retries:
                time.sleep(2 * (attempt + 1)); continue
            break
        except (urllib.error.URLError, TimeoutError, KeyError, IndexError, ValueError) as e:
            last = str(e)[:300]
            if attempt < retries:
                time.sleep(2 * (attempt + 1)); continue
    raise LLMError(f"model request failed: {last}")


def parse_json(text: str) -> dict:
    text = re.sub(r"^```(?:json)?|```$", "", (text or "").strip(), flags=re.M).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            raise LLMError(f"model did not return JSON: {text[:160]!r}")
        return json.loads(m.group(0))
