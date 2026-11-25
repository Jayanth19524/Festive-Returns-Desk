# NudgeBee setup (self-hosted Community, http://localhost:3000)

NudgeBee **runs** each return case. It does not score risk: the app decides (`backend/app/risk.py`), the workflow
routes on the decision stored in our database and calls back into our API, and NudgeBee records every step.

```
POST webhook {case_id, api_base, ...}
  -> get_case_id, get_api_base (data.transform)
  -> validate_case      GET  {api}/api/workflow/cases/{id}/validate  (our DB says: approve | hold | reject | invalid)
  -> announce_decision  core.print
  -> branch_on_decision core.switch on that decision
       approve -> issue_refund POST .../refund -> notify_approved
       hold    -> hold_case    POST .../hold   -> notify_held
       reject  -> reject_case  POST .../reject -> notify_rejected
       other   -> invalid_case (print)
```
The callback re-checks the stored decision and re-reads the Flagsmith freeze flag at that moment, so a forged or stale call cannot issue a refund.

## Deviation from the brief (tell the judges)
The brief says the webhook body is at `Inputs.webhook_json`. On this install it arrived **empty**; only the raw text
`Inputs.webhook_payload` came through. The workflow parses it with a `data.transform` (JSONata) task. Not documented behaviour, observed behaviour.

## Lesson learned (cost an hour)
Switch branch tasks must **not** list the switch in `depends_on`: the engine then fails with
`missing dependencies detected: map[branch_on_decision-issue_refund:[branch_on_decision]]`. The `next` fields on the switch wire them. Tasks AFTER a branch
task (the notify prints) may depend on it normally. The editor strips such `depends_on` itself, which is why a workflow that had been through the editor worked.

## Status: done and run on this machine
The workflow `garba-return-desk-final` is published (Active) and was run end to end for approve, hold and reject cases (all three branches), through a public cloudflared tunnel.
Paused leftovers from the debugging (`garba-return-desk`, `-v2`, `-v3`) can be deleted in the UI.

## Steps that need the NudgeBee UI (about 10 minutes)
1. Start the port-forward if it is not up:
   `kubectl port-forward svc/app 3000:80 -n nudgebee --context kind-bhaavtide`
2. Sign in at http://localhost:3000 as `admin@bhaavtide.local`. Copy the password without printing it:
   `kubectl get secret nudgebee -n nudgebee --context kind-bhaavtide -o jsonpath='{.data.NEXTAUTH_DUMMY_CREDS_PASSWORD}' | base64 -d | pbcopy`
3. **Admin > Integrations > Automation Webhook > Add account**: name it exactly `garba`, tick the account, save. Copy the webhook URL
   (`http://localhost:3000/api/webhooks/workflow?token=...`) into `.env` as `NUDGEBEE_WEBHOOK_URL`.
4. **Automations > Configs > add a Secret** named `garba_token`. Value = `WORKFLOW_API_TOKEN` from `.env`
   (`grep ^WORKFLOW_API_TOKEN= .env | cut -d= -f2 | pbcopy`).
5. **Create Automation > Create from Code**: paste `nudgebee/garba-return-desk.json`. Open it in the editor, **Validate**, then **Publish** with version status **Active** (a Paused version silently ignores webhooks).
6. Public tunnel (NudgeBee's HTTP task refuses private IPs such as localhost):
   `cloudflared tunnel --url http://localhost:8200` -> put the `https://....trycloudflare.com` address in `.env` as `PUBLIC_API_BASE_URL`, restart the API.
   The API lets tunnel traffic reach only `/api/workflow/*`, and only with the Bearer token.
7. Fire a test run: `bash scripts/fire_webhook.sh` (creates a case, the app calls the webhook), then open **Executions** in NudgeBee to see every task's input and output.
Errors: `kubectl --context kind-bhaavtide -n nudgebee logs deploy/workflow-server --since=3m | grep '"level":"ERROR"'`
