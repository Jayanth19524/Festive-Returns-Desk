#!/usr/bin/env bash
# (Re)start the public tunnel NudgeBee needs to call back into this app, and write its address into .env.
# Quick tunnels drop now and then and get a NEW address each time: just run this again. No API restart needed.
set -euo pipefail
cd "$(dirname "$0")/.."
pkill -f "cloudflared tunnel --url http://localhost:${APP_PORT:-8200}" 2>/dev/null || true
sleep 1
nohup cloudflared tunnel --url "http://localhost:${APP_PORT:-8200}" > /tmp/cf_garba.log 2>&1 &
for _ in $(seq 1 30); do
  URL=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' /tmp/cf_garba.log | head -1 || true)
  [ -n "$URL" ] && break; sleep 1
done
[ -n "${URL:-}" ] || { echo "tunnel did not start; see /tmp/cf_garba.log"; exit 1; }
python3 - "$URL" <<'PY'
import re, sys
s = open(".env").read()
s = re.sub(r"(?m)^PUBLIC_API_BASE_URL=.*$", "PUBLIC_API_BASE_URL=" + sys.argv[1], s)
open(".env", "w").write(s)
PY
echo "tunnel: $URL  (written to .env; DNS can take ~30 s)"
