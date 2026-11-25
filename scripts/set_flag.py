#!/usr/bin/env python3
"""Change a flag through Flagsmith's admin API (same effect as editing it in the dashboard; used for tests/demo).
  .venv/bin/python scripts/set_flag.py auto_refund_limit_inr 1000
  .venv/bin/python scripts/set_flag.py refunds_enabled off
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from app import flagsmith_admin  # noqa: E402

name, value = sys.argv[1], sys.argv[2]
flagsmith_admin.set_flag(name, value.lower() == "on" if value.lower() in ("on", "off") else value)
print(f"set {name} = {value}")
