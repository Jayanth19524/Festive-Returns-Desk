#!/usr/bin/env bash
# Put the key you just COPIED (e.g. from Google AI Studio) into .env as LLM_API_KEY without ever printing it or pasting it in chat.
set -euo pipefail
cd "$(dirname "$0")/.."
KEY="$(pbpaste | tr -d '[:space:]')"
[ -n "$KEY" ] || { echo "Clipboard is empty: copy the key first."; exit 1; }
python3 - "$KEY" <<'PY'
import re, sys
key = sys.argv[1]
s = open(".env").read()
s = re.sub(r"(?m)^LLM_API_KEY=.*$", "LLM_API_KEY=" + key, s) if re.search(r"(?m)^LLM_API_KEY=", s) else s.rstrip("\n") + "\nLLM_API_KEY=" + key + "\n"
open(".env", "w").write(s)
PY
echo "LLM_API_KEY saved to .env (${#KEY} characters, not shown)."
