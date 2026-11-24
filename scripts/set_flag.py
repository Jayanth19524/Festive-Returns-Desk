#!/usr/bin/env python3
"""Change a flag through Flagsmith's admin API (same effect as editing it in the dashboard; used for tests/demo).
  python3 scripts/set_flag.py auto_refund_limit_inr 1000
  python3 scripts/set_flag.py refunds_enabled off
"""
import json, os, sys, urllib.request
from pathlib import Path
for l in (Path(__file__).resolve().parent.parent / ".env").read_text().splitlines():
    if "=" in l and not l.startswith("#"):
        k, v = l.split("=", 1); os.environ.setdefault(k.strip(), v.strip())
BASE = os.environ["FLAGSMITH_API_URL"].rstrip("/"); TOKEN = os.environ["FLAGSMITH_ADMIN_KEY"]


def call(method, path, body=None):
    for scheme in ("Token", "Api-Key"):
        req = urllib.request.Request(BASE + path, method=method, data=json.dumps(body).encode() if body else None,
                                     headers={"Authorization": f"{scheme} {TOKEN}", "Content-Type": "application/json"})
        try:
            return json.loads(urllib.request.urlopen(req, timeout=15).read() or b"null")
        except urllib.error.HTTPError as e:
            if e.code != 401: raise SystemExit(f"HTTP {e.code}: {e.read().decode()[:300]}")
    raise SystemExit("auth failed")


name, value = sys.argv[1], sys.argv[2]
env = call("GET", "/projects/1/environments/")
env = next(e["api_key"] for e in (env["results"] if isinstance(env, dict) else env) if e["name"] == "Development")
fs = call("GET", f"/environments/{env}/featurestates/?page_size=100")["results"]
feats = call("GET", "/projects/1/features/?page_size=100")["results"]
fid = next(f["id"] for f in feats if f["name"] == name)
fs = next(f for f in fs if f["feature"] == fid and f["identity"] is None and f["feature_segment"] is None)
if value.lower() in ("on", "off"):
    fs["enabled"] = value.lower() == "on"
else:
    fs["feature_state_value"] = value
call("PUT", f"/environments/{env}/featurestates/{fs['id']}/", fs)
print(f"set {name} = {value}")
