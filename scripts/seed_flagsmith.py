#!/usr/bin/env python3
"""Create the five Festive Returns Desk flags in the self-hosted Flagsmith (idempotent: existing flags are left untouched).

Needs a Master API key (Flagsmith dashboard: Organisation Settings -> API Keys) in FLAGSMITH_ADMIN_KEY.
That key is only for this one-off setup; the running app uses the server-side environment key.

    python3 scripts/seed_flagsmith.py
"""
import json, os, sys, urllib.error, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for line in (ROOT / ".env").read_text().splitlines() if (ROOT / ".env").exists() else []:
    if line.strip() and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

BASE = os.getenv("FLAGSMITH_API_URL", "http://localhost:8000/api/v1/").rstrip("/")
KEY = os.getenv("FLAGSMITH_ADMIN_KEY", "")

# name, enabled by default, initial value, description
FLAGS = [
    ("refunds_enabled", True, None, "FREEZE SWITCH. OFF = no refund is issued; every case is held"),
    ("auto_refund_limit_inr", True, "2000", "Refunds up to this amount (INR) may be auto-approved when risk is low"),
    ("hold_above_inr", True, "8000", "Refunds above this amount (INR) always wait for the owner's signed approval"),
    ("max_returns_per_customer_30d", True, "2", "Returns in the last 30 days at or above this count add risk"),
    ("wardrobing_keywords_risk_weight", True, "40", "Risk points added when the case looks like worn-then-returned (wardrobing)"),
    ("photo_mismatch_risk_weight", True, "30", "Risk points added when the customer's photo does not support their claim (never lowers risk)"),
]


SCHEME = "Api-Key"  # organisation Master API key; a personal user token needs "Token" (auto-detected in main)


def call(method, path, body=None):
    req = urllib.request.Request(BASE + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": f"{SCHEME} {KEY}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:300]


def main():
    if not KEY:
        sys.exit("FLAGSMITH_ADMIN_KEY is not set (Flagsmith dashboard -> Organisation Settings -> API Keys).")
    global SCHEME
    st, projects = call("GET", "/projects/")
    if st == 401:  # maybe a personal token rather than a Master API key
        SCHEME = "Token"
        st, projects = call("GET", "/projects/")
        if st == 200:
            print("(authenticated with a personal user token)")
    if st != 200:
        sys.exit(f"Could not list projects: HTTP {st} {projects}")
    if len(projects) != 1:
        sys.exit(f"Expected exactly 1 project, found {len(projects)}: {[p['name'] for p in projects]}. Set it up with one project.")
    pid = projects[0]["id"]
    print(f"Project: {projects[0]['name']} (id {pid})")
    st, existing = call("GET", f"/projects/{pid}/features/?page_size=100")
    have = {f["name"] for f in (existing["results"] if st == 200 else [])}
    for name, enabled, value, desc in FLAGS:
        if name in have:
            print(f"  exists   {name}")
            continue
        st, r = call("POST", f"/projects/{pid}/features/",
                     {"name": name, "default_enabled": enabled, "initial_value": value, "description": desc})
        print(f"  {'created ' if st in (200, 201) else 'FAILED  '} {name}" + ("" if st in (200, 201) else f"  HTTP {st}: {r}"))


if __name__ == "__main__":
    main()
