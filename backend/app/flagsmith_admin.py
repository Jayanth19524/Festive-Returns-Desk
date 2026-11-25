"""Change a Flagsmith flag through its admin API. DEMO ONLY: it is what the demo-control buttons and scripts/set_flag.py use.
The running risk engine never needs this key; it reads flags with the server-side environment key."""
import json, os, urllib.error, urllib.request
from . import config  # noqa: F401  (loads .env)


def _call(method, path, body=None):
    base, token = os.environ["FLAGSMITH_API_URL"].rstrip("/"), os.environ["FLAGSMITH_ADMIN_KEY"]
    for scheme in ("Token", "Api-Key"):
        req = urllib.request.Request(base + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Authorization": f"{scheme} {token}", "Content-Type": "application/json"})
        try:
            return json.loads(urllib.request.urlopen(req, timeout=15).read() or b"null")
        except urllib.error.HTTPError as e:
            if e.code != 401:
                raise RuntimeError(f"Flagsmith HTTP {e.code}: {e.read().decode()[:200]}")
    raise RuntimeError("Flagsmith admin auth failed")


def set_flag(name: str, value) -> None:
    """value: True/False for refunds_enabled, a number or string for remote-config flags."""
    envs = _call("GET", "/projects/1/environments/")
    envs = envs["results"] if isinstance(envs, dict) else envs
    env = next(e["api_key"] for e in envs if e["name"] == "Development")
    feats = _call("GET", "/projects/1/features/?page_size=100")["results"]
    fid = next(f["id"] for f in feats if f["name"] == name)
    states = _call("GET", f"/environments/{env}/featurestates/?page_size=100")["results"]
    fs = next(f for f in states if f["feature"] == fid and f["identity"] is None and f["feature_segment"] is None)
    if isinstance(value, bool):
        fs["enabled"] = value
    else:
        fs["feature_state_value"] = str(value)
    _call("PUT", f"/environments/{env}/featurestates/{fs['id']}/", fs)
