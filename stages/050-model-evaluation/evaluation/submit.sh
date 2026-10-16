#!/usr/bin/env bash
# Submit, follow or inspect a governed EvalHub evaluation of a MaaS model, as the logged-in user (who needs the Stage
# 050 evaluator Role in the tenant). Submitting creates one EvalHub job in the tenant (RHOAI 3.5 "Evaluating AI
# systems": REST job submission, API-key model authentication through the tenant Secret, MLflow experiment tracking,
# OCI export of the results). Each run submits a new job; --status and --dry-run change nothing and are safe to rerun.
# Defaults run the Coding v1 benchmark (lighteval lcb:codegeneration_v6) with the non-thinking sampling the Qwen model
# cards recommend, bounded by --num-examples. lighteval samples 16 generations per problem and each job must finish
# inside the adapter's one-hour limit (Stage 050 README), so choose --num-examples from the measured per-problem time.
# Usage: stages/050-model-evaluation/evaluation/submit.sh --model-name ID [options] | --status JOB_ID [--wait]   (--help lists the options)
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"

usage() {
  cat <<'USAGE'
Usage:
  submit.sh --model-name <maas model id> [options]
  submit.sh --status <job id> [--wait]

Options:
  --model-name NAME        MaaS model id, e.g. publishers/internal-models/models/qwen3-8-27b (required to submit)
  --model-url URL          OpenAI-compatible base URL (default: the MaaS gateway api listener)
  --secret-ref NAME        Tenant Secret with the api-key (default: evalhub-model-auth-maas)
  --tenant NS              EvalHub tenant namespace (default: evaluated-models)
  --no-oci-export          Do not export result artifacts to the internal registry (default: export, 3.5 guide 2.19)
  --queue NAME             Kueue LocalQueue in the tenant (default: lq-cpu-default; '' to submit without a queue)
  --name NAME              Job name (default: <collection or benchmark>-<model>-<UTC timestamp>)
  --experiment NAME        MLflow experiment (default: model-evaluations)
  --collection ID          Submit a native collection unbounded instead of the benchmark (no parameters apply)
  --provider ID            EvalHub provider id (default: lighteval)
  --benchmark ID           Benchmark id within the provider (default: lcb:codegeneration_v6)
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

MODEL_NAME="" MODEL_URL="" SECRET_REF="evalhub-model-auth-maas" TENANT="evaluated-models" QUEUE="lq-cpu-default"
OCI_EXPORT="true" NAME="" EXPERIMENT="model-evaluations" COLLECTION="" PROVIDER="lighteval"
BENCHMARK="lcb:codegeneration_v6" NUM_EXAMPLES="" CONCURRENT="1" MAX_NEW_TOKENS="512" TEMPERATURE="0.7" TOP_P="0.8"
THRESHOLD="0.25" STATUS_ID="" WAIT="false" DRY_RUN="false"
SYSTEM_PROMPT="Answer with the complete Python program in a single \`\`\`python code block and nothing else."
while [[ $# -gt 0 ]]; do
  case "$1" in
    --model-name) MODEL_NAME="${2:-}"; shift 2 ;;
    --model-url) MODEL_URL="${2:-}"; shift 2 ;;
    --secret-ref) SECRET_REF="${2:-}"; shift 2 ;;
    --tenant) TENANT="${2:-}"; shift 2 ;;
    --queue) QUEUE="${2:-}"; shift 2 ;;
    --no-oci-export) OCI_EXPORT="false"; shift ;;
    --name) NAME="${2:-}"; shift 2 ;;
    --experiment) EXPERIMENT="${2:-}"; shift 2 ;;
    --collection) COLLECTION="${2:-}"; shift 2 ;;
    --provider) PROVIDER="${2:-}"; shift 2 ;;
    --benchmark) BENCHMARK="${2:-}"; shift 2 ;;
    --num-examples) NUM_EXAMPLES="${2:-}"; shift 2 ;;
    --concurrent-requests) CONCURRENT="${2:-}"; shift 2 ;;
    --max-new-tokens) MAX_NEW_TOKENS="${2:-}"; shift 2 ;;
    --temperature) TEMPERATURE="${2:-}"; shift 2 ;;
    --top-p) TOP_P="${2:-}"; shift 2 ;;
    --threshold) THRESHOLD="${2:-}"; shift 2 ;;
    --system-prompt) SYSTEM_PROMPT="${2:-}"; shift 2 ;;
    --status) STATUS_ID="${2:-}"; shift 2 ;;
    --wait) WAIT="true"; shift ;;
    --dry-run) DRY_RUN="true"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "[FAIL] unknown option: $1" >&2; usage >&2; exit 1 ;;
  esac
done
load_env
check_oc_logged_in

# ── EvalHub API as the logged-in user ─────────────────────────────────────────
EVALHUB_URL="https://$(oc get route evalhub -n evalhub --request-timeout=10s -o jsonpath='{.spec.host}')"
[[ "$EVALHUB_URL" != "https://" ]] || { echo '[FAIL] EvalHub route not found' >&2; exit 1; }
TOKEN="$(oc whoami -t)"
# The token reaches curl only through --config, never as an argument.
auth_config() { printf 'header = "Authorization: Bearer %s"\n' "$TOKEN"; }
api_get() {
  curl -sS -m 60 -X GET --config <(auth_config) -H "X-Tenant: $TENANT" -H 'Accept: application/json' "$EVALHUB_URL$1"
}
# One line per job, benchmark state, metric set, test result, MLflow link and message (None for an absent value).
show_job() {
  jq -r 'def s: if . == null then "None" else tostring end;
    def msg: if (.message | type) == "object" then (.message.message // "") else (.message // "") end;
    (.status // {}) as $st | (.results // {}) as $res
    | "job \(.resource.id | s) name \(.name | s) state \($st.state | s)",
      ($st.benchmarks // [] | .[] | "  benchmark \(.provider_id | s) \(.id | s) \(.status | s) \(msg | s)"),
      ($res.benchmarks // [] | .[] | "  metrics \(.id | s) \(.metrics | tojson)"),
      (if ($res.test // null) | . != null and . != false and . != {} then "  test \($res.test | tojson)" else empty end),
      (if ($res.mlflow_experiment_url // "") != "" then "  mlflow \($res.mlflow_experiment_url)" else empty end),
      (if ($st.message | type) == "object" and ($st.message.message // "") != "" then "  message \($st.message.message)" else empty end)'
}
wait_job() {
  local id="$1" state
  while :; do
    state="$(api_get "/api/v1/evaluations/jobs/$id" | jq -r '.status.state // ""')"
    echo "$(date -u +%H:%M:%SZ) state=$state"
    case "$state" in completed|failed|cancelled|partially_failed) break ;; esac
    sleep 60
  done
  api_get "/api/v1/evaluations/jobs/$id" | show_job
}

if [[ -n "$STATUS_ID" ]]; then
  if [[ "$WAIT" == "true" ]]; then wait_job "$STATUS_ID"; else api_get "/api/v1/evaluations/jobs/$STATUS_ID" | show_job; fi
  exit 0
fi

# ── Request body ──────────────────────────────────────────────────────────────
[[ -n "$MODEL_NAME" ]] || { echo '[FAIL] --model-name is required' >&2; usage >&2; exit 1; }
if [[ -z "$MODEL_URL" ]]; then
  host="$(oc get gateway maas-default-gateway -n openshift-ingress --request-timeout=10s \
    -o jsonpath='{.spec.listeners[?(@.name=="api")].hostname}')"
  [[ -n "$host" ]] || { echo '[FAIL] MaaS gateway api hostname not found; pass --model-url' >&2; exit 1; }
  MODEL_URL="https://$host"
fi
# Collections mix providers; Inspect, Garak and GuideLLM need the /v1 base URL and LightEval accepts it.
if [[ -n "$COLLECTION" && "$MODEL_URL" != */v1 ]]; then MODEL_URL="${MODEL_URL%/}/v1"; fi
# Tag runs with the accelerator serving the model (performance results are per GPU node).
short="${MODEL_NAME##*/}"
node="$(oc get pods -n internal-models --request-timeout=10s -o json 2>/dev/null | jq -r --arg m "$short" '[.items[]
  | select((.metadata.name | startswith($m + "-kserve-")) and (.metadata.name | contains("router") | not)
    and .status.phase == "Running") | .spec.nodeName // ""][0] // ""' 2>/dev/null || true)"
ACCEL=""
if [[ -n "$node" ]]; then
  ACCEL="$(oc get node "$node" --request-timeout=10s -o jsonpath='{.metadata.labels.nvidia\.com/gpu\.product}' 2>/dev/null || true)"
fi
bench="${BENCHMARK//[^a-zA-Z0-9]/-}"
[[ -n "$NAME" ]] || NAME="${COLLECTION:-$bench}-${short}-$(date -u +%Y%m%dT%H%M%SZ)"

OCI_HOST=""
if [[ "$OCI_EXPORT" == "true" ]]; then
  OCI_HOST="$(oc get route default-route -n openshift-image-registry --request-timeout=10s -o jsonpath='{.spec.host}' 2>/dev/null || true)"
  [[ -n "$OCI_HOST" ]] || echo "[WARN] internal registry route not found; submitting without OCI export" >&2
fi
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
# Experiment tags make MLflow history queryable by model, benchmark and source (3.5 guide 2.20, ExperimentConfig.tags);
# a collection carries its own weights and pass criteria; the queue is RHOAI 3.5 Evaluating AI systems 2.8/2.10.
MODEL_NAME="$MODEL_NAME" MODEL_URL="$MODEL_URL" SECRET_REF="$SECRET_REF" NAME="$NAME" EXPERIMENT="$EXPERIMENT" \
COLLECTION="$COLLECTION" PROVIDER="$PROVIDER" BENCHMARK="$BENCHMARK" NUM_EXAMPLES="$NUM_EXAMPLES" CONCURRENT="$CONCURRENT" \
MAX_NEW_TOKENS="$MAX_NEW_TOKENS" TEMPERATURE="$TEMPERATURE" TOP_P="$TOP_P" THRESHOLD="$THRESHOLD" SYSTEM_PROMPT="$SYSTEM_PROMPT" \
QUEUE="$QUEUE" OCI_HOST="$OCI_HOST" ACCEL="$ACCEL" TENANT_NS="$TENANT" jq -n '$ENV as $e
  | ($e.COLLECTION | if . != "" then . else $e.BENCHMARK end) as $subject
  | {name: $e.NAME, tags: ["agentic-coding", $subject],
     model: {url: $e.MODEL_URL, name: $e.MODEL_NAME, auth: {secret_ref: $e.SECRET_REF}},
     experiment: {name: $e.EXPERIMENT, tags: [
       {key: "model", value: ($e.MODEL_NAME | split("/") | last)},
       {key: "benchmark", value: ($e.COLLECTION | if . != "" then . else $e.PROVIDER + ":" + $e.BENCHMARK end)},
       {key: "access_path", value: "maas"},
       {key: "submitted_by", value: "submit-evaluation.sh"}]}}
  | if $e.OCI_HOST != "" then .exports = {oci: {coordinates: {oci_host: $e.OCI_HOST,
      oci_repository: ($e.TENANT_NS + "/evaluation-results")}, k8s: {connection: "evalhub-oci-registry"}}} else . end
  | if $e.QUEUE != "" then .queue = {kind: "kueue", name: $e.QUEUE} else . end
  | if $e.COLLECTION != "" then .collection = {id: $e.COLLECTION} else .pass_criteria = {threshold: ($e.THRESHOLD | tonumber)} end
  | if $e.ACCEL != "" then .experiment.tags += [{key: "accelerator", value: $e.ACCEL}]
    else
      (if $e.PROVIDER == "lighteval" then
        {provider: "endpoint", num_few_shot: 0, parameters: {concurrent_requests: ($e.CONCURRENT | tonumber), api_max_retry: 1,
          generation_parameters: {temperature: ($e.TEMPERATURE | tonumber), top_p: ($e.TOP_P | tonumber),
            max_new_tokens: ($e.MAX_NEW_TOKENS | tonumber)}}}
        | if $e.SYSTEM_PROMPT != "" then .parameters.system_prompt = $e.SYSTEM_PROMPT else . end
       else {} end) as $params
      | ($params | if $e.NUM_EXAMPLES != "" then .num_examples = ($e.NUM_EXAMPLES | tonumber) else . end) as $params
      | .benchmarks = [{id: $e.BENCHMARK, provider_id: $e.PROVIDER, pass_criteria: {threshold: ($e.THRESHOLD | tonumber)},
          parameters: $params}]
    end' >"$WORK/body.json"
if [[ "$DRY_RUN" == "true" ]]; then cat "$WORK/body.json"; exit 0; fi
oc get secret "$SECRET_REF" -n "$TENANT" --request-timeout=10s -o name >/dev/null ||
  { echo "[FAIL] Secret $TENANT/$SECRET_REF missing; sync Stage 050 (provision-evalhub-model-auth)" >&2; exit 1; }

# ── Submit (the only write) ───────────────────────────────────────────────────
code="$(curl -sS -m 60 -o "$WORK/response.json" -w '%{http_code}' -X POST --config <(auth_config) -H "X-Tenant: $TENANT" \
  -H 'Content-Type: application/json' --data-binary "@$WORK/body.json" "$EVALHUB_URL/api/v1/evaluations/jobs")"
[[ "$code" == "202" || "$code" == "201" ]] || { echo "[FAIL] EvalHub returned HTTP $code: $(head -c 600 "$WORK/response.json")" >&2; exit 1; }
JOB_ID="$(jq -r '.resource.id' "$WORK/response.json")"
log_info "Submitted $NAME as job $JOB_ID (tenant $TENANT, experiment $EXPERIMENT)"
log_info "Follow it in the dashboard (Develop & train -> Evaluations) or with: $0 --status $JOB_ID --wait"
if [[ "$WAIT" == "true" ]]; then wait_job "$JOB_ID"; fi
exit 0
