#!/usr/bin/env bash
# Creates a low-risk simulated case (the app then calls the NudgeBee webhook itself), and shows how to fire it by hand.
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; source .env; set +a
API=http://localhost:${APP_PORT:-8200}
echo "1) Create a case (the app dispatches it to NudgeBee):"
curl -s -X POST "$API/api/cases" -H 'content-type: application/json' \
  -d '{"order_id":"GRD-1008","reason_category":"wrong_size","claimed_condition":"unworn"}' | python3 -c "import sys,json;d=json.load(sys.stdin);print(' case',d['id'],d['decision'],d['status']);[print('  ',e['step'],'|',e['detail'][:110]) for e in d['events']]"
echo
echo "2) Or fire the webhook by hand for an existing case id (replace 12):"
echo "curl -X POST '\$NUDGEBEE_WEBHOOK_URL' -H 'content-type: application/json' -d '{\"case_id\":12,\"api_base\":\"'\$PUBLIC_API_BASE_URL'\"}'"
