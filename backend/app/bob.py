"""IBM Bob inference gateway client (OpenAI-compatible chat completions). Uses only the standard library.

Set in .env (names as used in the NammaPulse project):  BOB_API_KEY, BOB_BASE_URL (e.g. https://<gateway>/v1), BOB_MODEL.
If they are not set, `configured()` is False and callers say so plainly: nothing here pretends to work without a key.
The request format is the standard chat-completions one; image input uses `image_url` content parts. Whether the model behind
your gateway accepts images is NOT verified here: a rejected request is reported as an error, never hidden.
"""
import json, os, re, time, urllib.error, urllib.request
from dotenv import load_dotenv
from .config import ROOT


class BobError(Exception):
    pass


def _env():
    load_dotenv(ROOT / ".env", override=True)  # pick up a key added while the app runs
    return os.getenv("BOB_API_KEY", ""), os.getenv("BOB_BASE_URL", "").rstrip("/"), os.getenv("BOB_MODEL", "")


def configured() -> bool:
    key, base, model = _env()
    return bool(key and base and model)


def model_name() -> str:
    return _env()[2]


def chat(messages: list[dict], max_tokens: int = 700, timeout: float = 90.0, retries: int = 1) -> str:
    key, base, model = _env()
    if not (key and base and model):
        raise BobError("IBM Bob is not configured (set BOB_API_KEY, BOB_BASE_URL and BOB_MODEL in .env)")
    body = json.dumps({"model": model, "messages": messages, "temperature": 0, "max_tokens": max_tokens}).encode()
    req = urllib.request.Request(f"{base}/chat/completions", data=body, method="POST",
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    last = ""
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())["choices"][0]["message"]["content"] or ""
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}: {e.read().decode(errors='replace')[:300]}"
            if e.code in (429, 500, 502, 503, 504) and attempt < retries:
                time.sleep(1.5 * (attempt + 1)); continue
            break
        except (urllib.error.URLError, TimeoutError, KeyError, IndexError, ValueError) as e:
            last = str(e)[:300]
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1)); continue
    raise BobError(f"Bob request failed: {last}")


def parse_json(text: str) -> dict:
    text = re.sub(r"^```(?:json)?|```$", "", (text or "").strip(), flags=re.M).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            raise BobError(f"model did not return JSON: {text[:160]!r}")
        return json.loads(m.group(0))
