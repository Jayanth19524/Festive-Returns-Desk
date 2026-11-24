#!/usr/bin/env python3
"""Phase 0 preflight: is every key and service reachable?

Stdlib only, so it runs before `pip install`. Exit code 0 only if all checks pass.
Run:  python3 scripts/check_services.py
"""
import json, os, socket, sys, urllib.error, urllib.request
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent


def load_env():
    """Tiny .env reader (real env vars win)."""
    p = ROOT / ".env"
    if p.exists():
        for line in p.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def http(url, method="GET", headers=None, body=None, timeout=15):
    req = urllib.request.Request(url, method=method, headers=headers or {},
                                 data=json.dumps(body).encode() if body is not None else None)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:300]


def check_sarvam():
    key = os.getenv("SARVAM_API_KEY")
    if not key:
        return False, "SARVAM_API_KEY not set"
    # One tiny chat call on sarvam-105b: proves the key works AND the model name is valid.
    status, text = http(
        "https://api.sarvam.ai/v1/chat/completions", "POST",
        {"api-subscription-key": key, "Content-Type": "application/json"},
        {"model": os.getenv("SARVAM_LLM_MODEL", "sarvam-105b"),
         "messages": [{"role": "user", "content": "Reply with: ok"}], "max_tokens": 8})
    return status == 200, f"HTTP {status}" + ("" if status == 200 else f": {text}")


def check_flagsmith():
    api = os.getenv("FLAGSMITH_API_URL", "http://localhost:8000/api/v1/").rstrip("/")
    base = api.split("/api/")[0]
    try:
        status, _ = http(base + "/health")
    except Exception as e:
        return False, f"server not reachable at {base} ({e}). Run: docker compose up -d"
    if status != 200:
        return False, f"/health returned HTTP {status}"
    key = os.getenv("FLAGSMITH_ENVIRONMENT_KEY")
    if not key:
        return False, "server is up, but FLAGSMITH_ENVIRONMENT_KEY not set (create project in UI first)"
    status, text = http(api + "/flags/", headers={"X-Environment-Key": key})
    if status != 200:
        return False, f"environment key rejected: HTTP {status}"
    return True, f"server up, key valid, {len(json.loads(text))} flags defined"


def check_nudgebee():
    url = os.getenv("NUDGEBEE_WEBHOOK_URL")
    if not url:
        return False, "NUDGEBEE_WEBHOOK_URL not set"
    u = urlparse(url)
    port = u.port or (443 if u.scheme == "https" else 80)
    try:
        socket.create_connection((u.hostname, port), timeout=10).close()
    except Exception as e:
        return False, f"cannot reach {u.hostname}:{port} ({e}). Is the NudgeBee port-forward up?"
    # We deliberately do NOT POST here: that would start a real workflow run.
    return True, f"{u.hostname}:{port} reachable (webhook not fired; first real run is Phase 3)"


def check_public_url():
    url = os.getenv("PUBLIC_API_BASE_URL")
    if not url:
        return False, "PUBLIC_API_BASE_URL not set (needed from Phase 3; NudgeBee blocks private IPs, so a public tunnel is needed)"
    return True, f"set to {url} (reachability is tested once the API runs, Phase 3)"


def main():
    load_env()
    checks = [("Sarvam AI", check_sarvam), ("Flagsmith", check_flagsmith),
              ("NudgeBee", check_nudgebee), ("Public tunnel URL", check_public_url)]
    failed = 0
    for name, fn in checks:
        try:
            ok, msg = fn()
        except Exception as e:
            ok, msg = False, f"unexpected error: {e}"
        print(f"{'PASS' if ok else 'FAIL'}  {name:<18} {msg}")
        failed += not ok
    print("\nAll checks passed." if not failed else f"\n{failed} check(s) failed.")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
