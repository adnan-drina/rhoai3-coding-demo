#!/usr/bin/env bash
# Run a short GuideLLM benchmark against a MaaS-published model.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"

load_env
check_oc_logged_in

GUIDELLM_NAMESPACE="${GUIDELLM_NAMESPACE:-maas}"
GUIDELLM_IMAGE="${GUIDELLM_IMAGE:-ghcr.io/vllm-project/guidellm:latest}"
GUIDELLM_MODEL="${1:-${GUIDELLM_MODEL:-nemotron-3-nano-30b-a3b}}"
GUIDELLM_PROFILE="${GUIDELLM_PROFILE:-constant}"
GUIDELLM_RATE="${GUIDELLM_RATE:-1}"
GUIDELLM_MAX_SECONDS="${GUIDELLM_MAX_SECONDS:-20}"
GUIDELLM_REQUESTS="${GUIDELLM_REQUESTS:-5}"
GUIDELLM_MAX_ERRORS="${GUIDELLM_MAX_ERRORS:-3}"
GUIDELLM_PROMPT="${GUIDELLM_PROMPT:-Explain why governed model access matters for enterprise software teams. Keep the answer concise.}"
GUIDELLM_OUTPUT_TOKENS="${GUIDELLM_OUTPUT_TOKENS:-64}"
GUIDELLM_DATA="${GUIDELLM_DATA:-}"
GUIDELLM_PROCESSOR="${GUIDELLM_PROCESSOR:-gpt2}"
GUIDELLM_REQUEST_TYPE="${GUIDELLM_REQUEST_TYPE:-chat_completions}"
GUIDELLM_TIMEOUT_SECONDS="${GUIDELLM_TIMEOUT_SECONDS:-300}"

if [[ -z "${GUIDELLM_TARGET:-}" ]]; then
    MAAS_HOST="$(oc get gateway maas-default-gateway -n openshift-ingress \
        -o jsonpath='{.spec.listeners[0].hostname}' 2>/dev/null || true)"
    if [[ -z "$MAAS_HOST" || "$MAAS_HOST" == *placeholder* ]]; then
        log_warn "Cannot resolve MaaS Gateway host; skipping GuideLLM load test"
        exit 2
    fi
    GUIDELLM_TARGET="https://${MAAS_HOST}/maas/${GUIDELLM_MODEL}"
fi

API_KEY="${GUIDELLM_API_KEY:-${MAAS_API_KEY:-}}"
if [[ -z "$API_KEY" ]]; then
    API_KEY="$(oc get secret kai-api-keys -n openshift-mta \
        -o jsonpath='{.data.OPENAI_API_KEY}' 2>/dev/null | base64 -d 2>/dev/null || true)"
fi

if [[ -z "$API_KEY" || "$API_KEY" == REPLACE_* ]]; then
    log_warn "No MaaS API key available; set GUIDELLM_API_KEY or deploy Stage 080 to create kai-api-keys"
    exit 2
fi

if ! oc get namespace "$GUIDELLM_NAMESPACE" >/dev/null 2>&1; then
    log_warn "Namespace ${GUIDELLM_NAMESPACE} does not exist; skipping GuideLLM load test"
    exit 2
fi

RUN_ID="$(date -u +%Y%m%d%H%M%S)"
MODEL_SAFE="$(echo "$GUIDELLM_MODEL" | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9-' '-' | sed 's/--*/-/g; s/^-//; s/-$//')"
JOB_NAME="guidellm-${MODEL_SAFE}-${RUN_ID}"
JOB_NAME="${JOB_NAME:0:63}"
JOB_NAME="${JOB_NAME%-}"
SECRET_NAME="${JOB_NAME}-token"
RESULTS_NAME="${JOB_NAME}-results"

cleanup() {
    oc delete secret "$SECRET_NAME" -n "$GUIDELLM_NAMESPACE" --ignore-not-found >/dev/null 2>&1 || true
}
trap cleanup EXIT

log_step "GuideLLM load test"
log_info "Model: ${GUIDELLM_MODEL}"
log_info "Target: ${GUIDELLM_TARGET}"
log_info "Profile: ${GUIDELLM_PROFILE}, rate: ${GUIDELLM_RATE}, max seconds: ${GUIDELLM_MAX_SECONDS}"
log_info "Request samples: ${GUIDELLM_REQUESTS}"
if [[ -n "$GUIDELLM_DATA" ]]; then
    log_info "Data source: ${GUIDELLM_DATA}"
else
    log_info "Prompt: ${GUIDELLM_PROMPT}"
    log_info "Requested output tokens: ${GUIDELLM_OUTPUT_TOKENS}"
fi

oc create secret generic "$SECRET_NAME" -n "$GUIDELLM_NAMESPACE" \
    --from-literal=api-key="$API_KEY" \
    --dry-run=client -o yaml | oc apply -f - >/dev/null

cat <<EOF | oc apply -f - >/dev/null
apiVersion: batch/v1
kind: Job
metadata:
  name: ${JOB_NAME}
  namespace: ${GUIDELLM_NAMESPACE}
  labels:
    app.kubernetes.io/name: guidellm-load-test
    app.kubernetes.io/part-of: rhoai3-coding-demo
    demo.rhoai.io/stage: "040"
    demo.rhoai.io/model: ${MODEL_SAFE}
spec:
  backoffLimit: 0
  ttlSecondsAfterFinished: 3600
  template:
    metadata:
      labels:
        app.kubernetes.io/name: guidellm-load-test
        demo.rhoai.io/stage: "040"
    spec:
      restartPolicy: Never
      containers:
        - name: guidellm
          image: ${GUIDELLM_IMAGE}
          imagePullPolicy: IfNotPresent
          env:
            - name: LOADTEST_API_KEY
              valueFrom:
                secretKeyRef:
                  name: ${SECRET_NAME}
                  key: api-key
            - name: GUIDELLM__LOGGING__CONSOLE_LOG_LEVEL
              value: INFO
            - name: LOADTEST_PROMPT
              value: |-
                ${GUIDELLM_PROMPT}
            - name: LOADTEST_OUTPUT_TOKENS
              value: "${GUIDELLM_OUTPUT_TOKENS}"
            - name: LOADTEST_REQUESTS
              value: "${GUIDELLM_REQUESTS}"
            - name: LOADTEST_DATA
              value: |-
                ${GUIDELLM_DATA}
          command:
            - /bin/sh
            - -c
          args:
            - |
              set -eu
              if [ -n "\${LOADTEST_DATA}" ]; then
                DATA_ARG="\${LOADTEST_DATA}"
              else
                python - <<'PY'
              import json
              import os
              samples = int(os.environ["LOADTEST_REQUESTS"])
              row = {
                  "prompt": os.environ["LOADTEST_PROMPT"],
                  "output_tokens_count": int(os.environ["LOADTEST_OUTPUT_TOKENS"]),
              }
              with open("/tmp/guidellm-data.jsonl", "w", encoding="utf-8") as handle:
                  for _ in range(samples):
                      handle.write(json.dumps(row) + "\n")
              PY
                DATA_ARG="/tmp/guidellm-data.jsonl"
              fi
              guidellm benchmark \\
                --target "${GUIDELLM_TARGET}" \\
                --backend-type openai_http \\
                --backend-kwargs "{\"api_key\":\"\${LOADTEST_API_KEY}\",\"verify\":false}" \\
                --model "${GUIDELLM_MODEL}" \\
                --processor "${GUIDELLM_PROCESSOR}" \\
                --request-type "${GUIDELLM_REQUEST_TYPE}" \\
                --profile "${GUIDELLM_PROFILE}" \\
                --rate "${GUIDELLM_RATE}" \\
                --max-seconds "${GUIDELLM_MAX_SECONDS}" \\
                --max-errors "${GUIDELLM_MAX_ERRORS}" \\
                --data "\${DATA_ARG}"
EOF

log_info "Waiting for GuideLLM job ${JOB_NAME}..."
elapsed=0
while true; do
    status="$(oc get job "$JOB_NAME" -n "$GUIDELLM_NAMESPACE" \
        -o jsonpath='{.status.conditions[?(@.type=="Complete")].status} {.status.conditions[?(@.type=="Failed")].status}' 2>/dev/null || true)"
    if [[ "$status" == *"True "* || "$status" == "True " ]]; then
        break
    fi
    if [[ "$status" == *" True"* ]]; then
        oc logs "job/${JOB_NAME}" -n "$GUIDELLM_NAMESPACE" --tail=-1 || true
        log_error "GuideLLM load test job failed"
        exit 1
    fi
    if [[ "$elapsed" -ge "$GUIDELLM_TIMEOUT_SECONDS" ]]; then
        oc logs "job/${JOB_NAME}" -n "$GUIDELLM_NAMESPACE" --tail=120 || true
        log_error "Timed out waiting for GuideLLM load test job"
        exit 1
    fi
    sleep 5
    elapsed=$((elapsed + 5))
done

RESULTS_FILE="/tmp/${JOB_NAME}.log"
oc logs "job/${JOB_NAME}" -n "$GUIDELLM_NAMESPACE" --tail=-1 | tee "$RESULTS_FILE"

oc create configmap "$RESULTS_NAME" -n "$GUIDELLM_NAMESPACE" \
    --from-file=summary.log="$RESULTS_FILE" \
    --from-literal=model="$GUIDELLM_MODEL" \
    --from-literal=target="$GUIDELLM_TARGET" \
    --from-literal=profile="$GUIDELLM_PROFILE" \
    --from-literal=rate="$GUIDELLM_RATE" \
    --from-literal=max-seconds="$GUIDELLM_MAX_SECONDS" \
    --from-literal=requests="$GUIDELLM_REQUESTS" \
    --from-literal=data="${GUIDELLM_DATA:-inline-prompt}" \
    --from-literal=output-tokens="$GUIDELLM_OUTPUT_TOKENS" \
    --from-literal=processor="$GUIDELLM_PROCESSOR" \
    --dry-run=client -o yaml | oc apply -f - >/dev/null
oc label configmap "$RESULTS_NAME" -n "$GUIDELLM_NAMESPACE" \
    app.kubernetes.io/name=guidellm-load-test \
    app.kubernetes.io/part-of=rhoai3-coding-demo \
    demo.rhoai.io/stage=040 \
    demo.rhoai.io/model="$MODEL_SAFE" \
    --overwrite >/dev/null

rm -f "$RESULTS_FILE"
log_success "GuideLLM load test completed; results stored in ConfigMap ${GUIDELLM_NAMESPACE}/${RESULTS_NAME}"
