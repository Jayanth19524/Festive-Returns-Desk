"""Live rules from Flagsmith (self-hosted). The app never restarts to pick up a change.

  refunds_enabled                  boolean flag (freeze switch): OFF = no refund is issued
  auto_refund_limit_inr            remote config (number)
  hold_above_inr                   remote config (number)
  max_returns_per_customer_30d     remote config (number)
  wardrobing_keywords_risk_weight  remote config (number)

Every read asks the Flagsmith server (remote evaluation) with a 1-second cache. If Flagsmith is unreachable or a
flag is missing we use a default AND SAY SO (`source` per flag, `live` overall); defaults are never passed off as live.
"""
import os, time
from flagsmith import Flagsmith
from flagsmith.models import DefaultFlag
from . import config  # noqa: F401  (loads .env before os.getenv below)

API_URL = os.getenv("FLAGSMITH_API_URL", "http://localhost:8000/api/v1/")
ENV_KEY = os.getenv("FLAGSMITH_ENVIRONMENT_KEY", "")

# name -> (enabled, value) used only when Flagsmith cannot answer
DEFAULTS = {
    "refunds_enabled": (True, None),
    "auto_refund_limit_inr": (True, "2000"),
    "hold_above_inr": (True, "8000"),
    "max_returns_per_customer_30d": (True, "2"),
    "wardrobing_keywords_risk_weight": (True, "40"),
}
_client, _cache = None, {"t": 0.0, "v": None}


def _default_handler(name):
    enabled, value = DEFAULTS.get(name, (False, None))
    return DefaultFlag(enabled=enabled, value=value)


def _num(raw, fallback):
    try:
        return float(raw)
    except (TypeError, ValueError):
        return float(fallback)


def load() -> dict:
    """{cfg: plain dict the risk rule uses, flags: raw per-flag info, status: str, live: bool}. Cached 1 s."""
    global _client
    now = time.monotonic()
    if _cache["v"] is not None and now - _cache["t"] < 1.0:
        return _cache["v"]
    remote, status = None, "live from Flagsmith"
    if not ENV_KEY:
        status = "FLAGSMITH_ENVIRONMENT_KEY not set: defaults, NOT live"
    else:
        try:
            if _client is None:
                _client = Flagsmith(environment_key=ENV_KEY, api_url=API_URL, request_timeout_seconds=2,
                                    default_flag_handler=_default_handler)
            remote = _client.get_environment_flags()
        except Exception as e:
            status = f"Flagsmith unreachable ({type(e).__name__}): defaults, NOT live"
    flags = {}
    for name in DEFAULTS:
        f = _default_handler(name) if remote is None else remote.get_flag(name)
        is_default = remote is None or getattr(f, "is_default", False)
        flags[name] = {"enabled": bool(f.enabled), "value": f.value, "source": "default" if is_default else "flagsmith"}
    missing = [n for n, v in flags.items() if v["source"] == "default"]
    if remote is not None and missing:
        status = f"Flagsmith reachable, flags missing (defaults used): {', '.join(missing)}"
    cfg = {
        "refunds_enabled": flags["refunds_enabled"]["enabled"],
        "auto_refund_limit_inr": _num(flags["auto_refund_limit_inr"]["value"], 2000),
        "hold_above_inr": _num(flags["hold_above_inr"]["value"], 8000),
        "max_returns_per_customer_30d": int(_num(flags["max_returns_per_customer_30d"]["value"], 2)),
        "wardrobing_risk_weight": _num(flags["wardrobing_keywords_risk_weight"]["value"], 40),
    }
    out = {"cfg": cfg, "flags": flags, "status": status, "live": status == "live from Flagsmith"}
    _cache.update(t=now, v=out)
    return out
