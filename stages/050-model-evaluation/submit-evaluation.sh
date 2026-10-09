#!/usr/bin/env bash
# Submit, follow or inspect a governed EvalHub evaluation of a MaaS model.
#
# RHOAI 3.5 "Evaluating AI systems": REST job submission (2.10), API-key model authentication through
# the tenant Secret (2.15), MLflow experiment tracking (2.20) and job tracking (2.11). The caller's
# OpenShift token is used; the caller needs the Stage 050 evaluator Role in the tenant.
#
# Defaults run the Coding v1 benchmark (lighteval lcb:codegeneration_v6, the only member of the native
# coding-v1 collection) with the sampling the Qwen model cards recommend for non-thinking use, bounded by
# --num-examples. lighteval samples 16 generations per problem for this benchmark regardless of the
# collection definition, and each job must finish inside the adapter's one-hour limit (see the Stage 050
# README), so choose --num-examples from the measured per-problem time.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
# shellcheck source=../../scripts/shared/lib.sh
source "$REPO_ROOT/scripts/shared/lib.sh"
load_env
check_oc_logged_in
command -v python3 >/dev/null || { echo '[FAIL] python3 is required' >&2; exit 1; }

usage() {
  cat <<'USAGE'
Usage:
  submit-evaluation.sh --model-name <maas model id> [options]
  submit-evaluation.sh --status <job id> [--wait]

Options:
  --model-name NAME        MaaS model id, e.g. publishers/internal-models/models/qwen3-8-27b-int4 (required to submit)
  --model-url URL          OpenAI-compatible base URL (default: the MaaS gateway api listener)
  --secret-ref NAME        Tenant Secret with the api-key (default: evalhub-model-auth-maas)
  --tenant NS              EvalHub tenant namespace (default: demo-sandbox)
  --name NAME              Job name (default: coding-v1-<model>-<UTC timestamp>)
  --experiment NAME        MLflow experiment (default: agentic-coding-qualification)
  --collection ID          Submit a native collection unbounded instead of the benchmark (no parameters apply)
  --benchmark ID           lighteval benchmark id (default: lcb:codegeneration_v6)
  --num-examples N         Problems to evaluate (default: unset = full dataset)
  --concurrent-requests N  Parallel requests from the adapter (default: 1; the Qwen 3.8 server admits 2 sequences)
  --max-new-tokens N       Generation cap per sample (default: 512; each 16-sample request must finish inside the sidecar's request timeout)
  --temperature T          Sampling temperature (default: 0.7)
  --top-p P                Nucleus sampling (default: 0.8)
  --threshold T            Pass threshold on the primary score (default: 0.25, the coding-v1 definition)
  --system-prompt TEXT     System prompt prepended by the adapter (default: code-only answer; pass '' to disable)
  --status ID              Show a job instead of submitting
  --wait                   Poll until the job reaches a terminal state
  --dry-run                Print the request body and exit
USAGE
}

MODEL_NAME=""; MODEL_URL=""; SECRET_REF="evalhub-model-auth-maas"; TENANT="demo-sandbox"; NAME=""; EXPERIMENT="agentic-coding-qualification"
COLLECTION=""; BENCHMARK="lcb:codegeneration_v6"; NUM_EXAMPLES=""; CONCURRENT="1"; MAX_NEW_TOKENS="512"; TEMPERATURE="0.7"; TOP_P="0.8"
THRESHOLD="0.25"; SYSTEM_PROMPT="Answer with the complete Python program in a single \`\`\`python code block and nothing else."; STATUS_ID=""; WAIT="false"; DRY_RUN="false"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --model-name) MODEL_NAME="$2"; shift 2;; --model-url) MODEL_URL="$2"; shift 2;; --secret-ref) SECRET_REF="$2"; shift 2;;
    --tenant) TENANT="$2"; shift 2;; --name) NAME="$2"; shift 2;; --experiment) EXPERIMENT="$2"; shift 2;;
    --collection) COLLECTION="$2"; shift 2;; --benchmark) BENCHMARK="$2"; shift 2;; --num-examples) NUM_EXAMPLES="$2"; shift 2;;
    --concurrent-requests) CONCURRENT="$2"; shift 2;; --max-new-tokens) MAX_NEW_TOKENS="$2"; shift 2;;
    --temperature) TEMPERATURE="$2"; shift 2;; --top-p) TOP_P="$2"; shift 2;; --threshold) THRESHOLD="$2"; shift 2;;
    --system-prompt) SYSTEM_PROMPT="$2"; shift 2;;
    --status) STATUS_ID="$2"; shift 2;; --wait) WAIT="true"; shift;; --dry-run) DRY_RUN="true"; shift;;
    -h|--help) usage; exit 0;; *) echo "[FAIL] unknown option: $1" >&2; usage; exit 1;;
  esac
done

EVALHUB_URL="https://$(oc get route evalhub -n evalhub --request-timeout=10s -o jsonpath='{.spec.host}')"
[[ "$EVALHUB_URL" != "https://" ]] || { echo '[FAIL] EvalHub route not found' >&2; exit 1; }
TOKEN="$(oc whoami -t)"
api() { # method path [body-file]
  local body=(); [[ $# -ge 3 ]] && body=(-H 'Content-Type: application/json' --data-binary "@$3")
  curl -sS -m 60 -X "$1" -H "Authorization: Bearer $TOKEN" -H "X-Tenant: $TENANT" -H 'Accept: application/json' ${body[@]+"${body[@]}"} "$EVALHUB_URL$2"
}
show_job() {
  python3 -c '
import json, sys
j = json.load(sys.stdin); st = j.get("status") or {}
print("job", j["resource"]["id"], "name", j.get("name"), "state", st.get("state"))
for b in st.get("benchmarks") or []:
    print("  benchmark", b.get("provider_id"), b.get("id"), b.get("status"), (b.get("message") or {}).get("message", "") if isinstance(b.get("message"), dict) else (b.get("message") or ""))
res = j.get("results") or {}
for b in res.get("benchmarks") or []:
    print("  metrics", b.get("id"), json.dumps(b.get("metrics")))
if res.get("test"): print("  test", json.dumps(res["test"]))
if res.get("mlflow_experiment_url"): print("  mlflow", res["mlflow_experiment_url"])
msg = st.get("message"); 
if isinstance(msg, dict) and msg.get("message"): print("  message", msg["message"])
'
}
wait_job() {
  local id="$1" state
  while :; do
    state="$(api GET "/api/v1/evaluations/jobs/$id" | python3 -c 'import json,sys; print((json.load(sys.stdin).get("status") or {}).get("state",""))')"
    echo "$(date -u +%H:%M:%SZ) state=$state"
    case "$state" in completed|failed|cancelled|partially_failed) break;; esac
    sleep 60
  done
  api GET "/api/v1/evaluations/jobs/$id" | show_job
}

if [[ -n "$STATUS_ID" ]]; then
  if [[ "$WAIT" == "true" ]]; then wait_job "$STATUS_ID"; else api GET "/api/v1/evaluations/jobs/$STATUS_ID" | show_job; fi
  exit 0
fi

[[ -n "$MODEL_NAME" ]] || { echo '[FAIL] --model-name is required' >&2; usage; exit 1; }
if [[ -z "$MODEL_URL" ]]; then
  host="$(oc get gateway maas-default-gateway -n openshift-ingress --request-timeout=10s -o jsonpath='{.spec.listeners[?(@.name=="api")].hostname}')"
  [[ -n "$host" ]] || { echo '[FAIL] MaaS gateway api hostname not found; pass --model-url' >&2; exit 1; }
  MODEL_URL="https://$host"
fi
short="${MODEL_NAME##*/}"; [[ -n "$NAME" ]] || NAME="${COLLECTION:-coding-v1}-${short}-$(date -u +%Y%m%dT%H%M%SZ)"

BODY="$(mktemp)"; trap 'rm -f "$BODY"' EXIT
MODEL_NAME="$MODEL_NAME" MODEL_URL="$MODEL_URL" SECRET_REF="$SECRET_REF" NAME="$NAME" EXPERIMENT="$EXPERIMENT" COLLECTION="$COLLECTION" \
BENCHMARK="$BENCHMARK" NUM_EXAMPLES="$NUM_EXAMPLES" CONCURRENT="$CONCURRENT" MAX_NEW_TOKENS="$MAX_NEW_TOKENS" TEMPERATURE="$TEMPERATURE" \
TOP_P="$TOP_P" THRESHOLD="$THRESHOLD" SYSTEM_PROMPT="$SYSTEM_PROMPT" python3 - > "$BODY" <<'PY'
import json, os
e = os.environ
body = {"name": e["NAME"], "tags": ["stage-050", "coding"],
        "model": {"url": e["MODEL_URL"], "name": e["MODEL_NAME"], "auth": {"secret_ref": e["SECRET_REF"]}},
        "pass_criteria": {"threshold": float(e["THRESHOLD"])},
        "experiment": {"name": e["EXPERIMENT"]}}
if e["COLLECTION"]:
    body["collection"] = {"id": e["COLLECTION"]}
else:
    params = {"provider": "endpoint", "num_few_shot": 0,
              "parameters": {"concurrent_requests": int(e["CONCURRENT"]), "api_max_retry": 1,
                             "generation_parameters": {"temperature": float(e["TEMPERATURE"]), "top_p": float(e["TOP_P"]),
                                                       "max_new_tokens": int(e["MAX_NEW_TOKENS"])}}}
    if e["SYSTEM_PROMPT"]:
        params["parameters"]["system_prompt"] = e["SYSTEM_PROMPT"]
    if e["NUM_EXAMPLES"]:
        params["num_examples"] = int(e["NUM_EXAMPLES"])
    body["benchmarks"] = [{"id": e["BENCHMARK"], "provider_id": "lighteval", "pass_criteria": {"threshold": float(e["THRESHOLD"])}, "parameters": params}]
print(json.dumps(body, indent=2))
PY
if [[ "$DRY_RUN" == "true" ]]; then cat "$BODY"; exit 0; fi
oc get secret "$SECRET_REF" -n "$TENANT" --request-timeout=10s -o name >/dev/null || { echo "[FAIL] Secret $TENANT/$SECRET_REF missing; sync Stage 050 (provision-evalhub-model-auth)" >&2; exit 1; }

RESP="$(mktemp)"; trap 'rm -f "$BODY" "$RESP"' EXIT
code="$(curl -sS -m 60 -o "$RESP" -w '%{http_code}' -X POST -H "Authorization: Bearer $TOKEN" -H "X-Tenant: $TENANT" -H 'Content-Type: application/json' --data-binary "@$BODY" "$EVALHUB_URL/api/v1/evaluations/jobs")"
[[ "$code" == "202" || "$code" == "201" ]] || { echo "[FAIL] EvalHub returned HTTP $code: $(head -c 600 "$RESP")" >&2; exit 1; }
JOB_ID="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["resource"]["id"])' < "$RESP")"
log_info "Submitted $NAME as job $JOB_ID (tenant $TENANT, experiment $EXPERIMENT)"
log_info "Follow it in the dashboard (Develop & train -> Evaluations) or with: $0 --status $JOB_ID --wait"
[[ "$WAIT" == "true" ]] && wait_job "$JOB_ID"
exit 0
