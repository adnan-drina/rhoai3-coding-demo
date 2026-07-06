#!/usr/bin/env bash
# benchmark-guidellm.sh - vLLM serving capacity benchmark (GuideLLM)
# Runs GuideLLM in-cluster against the live Nemotron LLMInferenceService
# workload Service (direct engine endpoint, bypassing MaaS quotas so the
# model itself is measured) and copies results to gitignored runs/ for
# review. scripts/analyze-guidellm.py turns the JSON into a capacity report
# (optimal load, max stable concurrency, breaking point, business planning
# metrics). This is intentionally not part of every deploy.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "$ROOT_DIR/.env"
  set +a
fi

MODEL_NS="${RHOAI_MAAS_NAMESPACE:-models-as-a-service}"
MODEL_NAME="${RHOAI_MAAS_NEMOTRON_MODEL_NAME:-nemotron-3-nano-30b-a3b}"
MODEL_ID="${RHOAI_NEMOTRON_GUIDELLM_MODEL_ID:-$MODEL_NAME}"
GUIDELLM_PROCESSOR="${RHOAI_NEMOTRON_GUIDELLM_PROCESSOR:-nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-FP8}"
GUIDELLM_IMAGE="${RHOAI_GUIDELLM_IMAGE:-ghcr.io/vllm-project/guidellm:v0.5.0}"
# Benchmark profiles:
#   users    - stepped concurrent-user levels; finds max stable concurrency
#              and the breaking point (default)
#   sweep    - GuideLLM sweep from synchronous to max throughput; finds the
#              throughput envelope and the optimal-load knee
#   custom   - raw RHOAI_GUIDELLM_RATE_TYPE / RHOAI_GUIDELLM_RATE passthrough
GUIDELLM_PROFILE="${RHOAI_GUIDELLM_PROFILE:-users}"
GUIDELLM_RATE_TYPE="${RHOAI_GUIDELLM_RATE_TYPE:-}"
GUIDELLM_RATE="${RHOAI_GUIDELLM_RATE:-}"
GUIDELLM_MAX_SECONDS="${RHOAI_GUIDELLM_MAX_SECONDS:-60}"
# Default to GuideLLM synthetic data: controlled, reproducible token shapes
# are the right load model for capacity planning and remove any dependency
# on a namespace-local prompt PVC. RAG-chatbot-shaped prompts (~1200 input
# tokens of retrieved context, ~256 output tokens) approximate a guarded
# answer turn. Override RHOAI_GUIDELLM_DATA with /data/prompts.csv (plus
# RHOAI_GUIDELLM_DATA_PVC) to replay a fixed corpus instead.
GUIDELLM_DATA="${RHOAI_GUIDELLM_DATA:-prompt_tokens=1200,output_tokens=256}"
GUIDELLM_OUTPUTS="${RHOAI_GUIDELLM_OUTPUTS:-benchmark-results.json,benchmark-results.csv}"
GUIDELLM_DATA_PVC="${RHOAI_GUIDELLM_DATA_PVC:-benchmark-data}"
GUIDELLM_TIMEOUT="${RHOAI_GUIDELLM_TIMEOUT:-40m}"
KEEP_RESOURCES="${RHOAI_GUIDELLM_KEEP_RESOURCES:-false}"
# Direct engine endpoint (LLMInferenceService workload Service). The KServe
# workload Service terminates TLS on 8000 (self-signed), so the target is
# https and the job disables cert verification. Override
# RHOAI_GUIDELLM_TARGET to benchmark another path (for example the MaaS
# gateway, which measures governance quotas rather than the model).
GUIDELLM_TARGET="${RHOAI_GUIDELLM_TARGET:-https://${MODEL_NAME}-kserve-workload-svc.${MODEL_NS}.svc.cluster.local:8000/v1}"

case "$GUIDELLM_PROFILE" in
  users)
    GUIDELLM_RATE_TYPE="${GUIDELLM_RATE_TYPE:-concurrent}"
    GUIDELLM_RATE="${GUIDELLM_RATE:-1,2,4,8,16,32,64,128}"
    ;;
  sweep)
    GUIDELLM_RATE_TYPE="${GUIDELLM_RATE_TYPE:-sweep}"
    GUIDELLM_RATE="${GUIDELLM_RATE:-10}"
    ;;
  custom)
    if [[ -z "$GUIDELLM_RATE_TYPE" || -z "$GUIDELLM_RATE" ]]; then
      echo "ERROR: custom profile needs RHOAI_GUIDELLM_RATE_TYPE and RHOAI_GUIDELLM_RATE." >&2
      exit 1
    fi
    ;;
  *)
    echo "ERROR: unknown RHOAI_GUIDELLM_PROFILE '${GUIDELLM_PROFILE}' (users|sweep|custom)." >&2
    exit 1
    ;;
esac

if [[ -z "${RHOAI_EXPECTED_API_SERVER:-}" ]]; then
  echo "ERROR: RHOAI_EXPECTED_API_SERVER is not set." >&2
  exit 1
fi

ACTUAL_SERVER=$(oc whoami --show-server 2>/dev/null || true)
if [[ "$ACTUAL_SERVER" != *"$RHOAI_EXPECTED_API_SERVER"* ]]; then
  echo "ERROR: Active cluster ($ACTUAL_SERVER) does not match RHOAI_EXPECTED_API_SERVER." >&2
  exit 1
fi

echo "✓ Cluster guard passed: $ACTUAL_SERVER"

for cmd in oc jq python3; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "ERROR: required command not found: $cmd" >&2
    exit 1
  fi
done

LLMISVC_READY=$(oc get llminferenceservice "$MODEL_NAME" -n "$MODEL_NS" \
  -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' \
  --insecure-skip-tls-verify=true 2>/dev/null || true)
if [[ "$LLMISVC_READY" != "True" ]]; then
  echo "ERROR: LLMInferenceService ${MODEL_NS}/${MODEL_NAME} is not Ready (un-park the environment first)." >&2
  exit 1
fi

if [[ "$GUIDELLM_DATA" == /data/* ]]; then
  if ! oc get pvc "$GUIDELLM_DATA_PVC" -n "$MODEL_NS" --insecure-skip-tls-verify=true >/dev/null 2>&1; then
    echo "ERROR: expected benchmark data PVC ${MODEL_NS}/${GUIDELLM_DATA_PVC} is missing." >&2
    echo "       Reconcile 030-private-model-serving before running the benchmark." >&2
    exit 1
  fi
fi

RUN_ID="$(date -u +%Y%m%d%H%M%S)"
JOB_NAME="guidellm-${GUIDELLM_PROFILE}-${RUN_ID}"
PVC_NAME="guidellm-results-${RUN_ID}"
COPY_JOB="guidellm-copy-${RUN_ID}"
RESULTS_DIR="${ROOT_DIR}/runs/stage-210-guidellm/${RUN_ID}"

mkdir -p "$RESULTS_DIR"

echo "── Creating GuideLLM results PVC ──"
oc apply -f - --insecure-skip-tls-verify=true <<EOF
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: ${PVC_NAME}
  namespace: ${MODEL_NS}
  labels:
    app.kubernetes.io/part-of: rhoai3-coding-demo
    app.kubernetes.io/name: guidellm
    demo.rhoai.io/stage: "210"
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 5Gi
EOF

# The prompt data PVC is mounted only when replaying a /data/* file corpus;
# synthetic data (the default) needs no volume.
DATA_MOUNT=""
DATA_VOLUME=""
if [[ "$GUIDELLM_DATA" == /data/* ]]; then
  DATA_MOUNT=$'            - name: data\n              mountPath: /data\n              readOnly: true'
  DATA_VOLUME=$'        - name: data\n          persistentVolumeClaim:\n            claimName: '"${GUIDELLM_DATA_PVC}"
fi

# The KServe workload Service uses a self-signed cert; disable GuideLLM's
# httpx verification for https targets (demo self-signed policy). Passed as
# an extra arg pair only when needed so http targets stay unaffected.
BACKEND_ARGS_MOUNT=""
if [[ "$GUIDELLM_TARGET" == https://* ]]; then
  BACKEND_ARGS_MOUNT=$'            - --backend-args\n            - \'{"verify": false}\''
fi

echo "── Running GuideLLM benchmark job ──"
echo "  Target:  ${GUIDELLM_TARGET}"
echo "  Data:    ${GUIDELLM_DATA}"
echo "  Profile: ${GUIDELLM_PROFILE} (${GUIDELLM_RATE_TYPE} ${GUIDELLM_RATE}, ${GUIDELLM_MAX_SECONDS}s per level)"
oc apply -f - --insecure-skip-tls-verify=true <<EOF
apiVersion: batch/v1
kind: Job
metadata:
  name: ${JOB_NAME}
  namespace: ${MODEL_NS}
  labels:
    app.kubernetes.io/part-of: rhoai3-coding-demo
    app.kubernetes.io/name: guidellm
    demo.rhoai.io/stage: "210"
spec:
  backoffLimit: 0
  template:
    metadata:
      labels:
        app.kubernetes.io/name: guidellm
        demo.rhoai.io/stage: "210"
    spec:
      restartPolicy: Never
      containers:
        - name: guidellm
          image: ${GUIDELLM_IMAGE}
          imagePullPolicy: IfNotPresent
          env:
            - name: HOME
              value: /results
            - name: HF_HOME
              value: /tmp/hf-cache
            - name: TRANSFORMERS_CACHE
              value: /tmp/hf-cache
            - name: XDG_CACHE_HOME
              value: /tmp
          args:
            - benchmark
            - run
            - --target
            - "${GUIDELLM_TARGET}"
            - --model
            - "${MODEL_ID}"
            - --processor
            - "${GUIDELLM_PROCESSOR}"
${BACKEND_ARGS_MOUNT}
            - --data
            - '${GUIDELLM_DATA}'
            - --rate-type
            - "${GUIDELLM_RATE_TYPE}"
            - --rate
            - "${GUIDELLM_RATE}"
            - --max-seconds
            - "${GUIDELLM_MAX_SECONDS}"
            - --output-dir
            - /results
            - --outputs
            - "${GUIDELLM_OUTPUTS}"
          volumeMounts:
            - name: cache
              mountPath: /tmp/hf-cache
            - name: results
              mountPath: /results
${DATA_MOUNT}
      volumes:
        - name: cache
          emptyDir: {}
        - name: results
          persistentVolumeClaim:
            claimName: ${PVC_NAME}
${DATA_VOLUME}
EOF

if ! oc wait -n "$MODEL_NS" --for=condition=complete "job/${JOB_NAME}" \
  "--timeout=${GUIDELLM_TIMEOUT}" --insecure-skip-tls-verify=true; then
  echo "ERROR: GuideLLM job did not complete successfully." >&2
  oc logs -n "$MODEL_NS" "job/${JOB_NAME}" --insecure-skip-tls-verify=true || true
  echo "Temporary resources retained for inspection: job/${JOB_NAME}, pvc/${PVC_NAME}" >&2
  exit 1
fi

oc logs -n "$MODEL_NS" "job/${JOB_NAME}" --insecure-skip-tls-verify=true || true

echo "── Copying GuideLLM results to ${RESULTS_DIR} ──"
oc apply -f - --insecure-skip-tls-verify=true <<EOF
apiVersion: batch/v1
kind: Job
metadata:
  name: ${COPY_JOB}
  namespace: ${MODEL_NS}
  labels:
    app.kubernetes.io/part-of: rhoai3-coding-demo
    app.kubernetes.io/name: guidellm-copy
    demo.rhoai.io/stage: "210"
spec:
  backoffLimit: 0
  template:
    metadata:
      labels:
        app.kubernetes.io/name: guidellm-copy
        demo.rhoai.io/stage: "210"
    spec:
      restartPolicy: Never
      containers:
        - name: copy
          image: registry.access.redhat.com/ubi9/ubi-minimal:latest
          command:
            - /bin/sh
            - -c
            - sleep 3600
          volumeMounts:
            - name: results
              mountPath: /results
      volumes:
        - name: results
          persistentVolumeClaim:
            claimName: ${PVC_NAME}
EOF

COPY_POD=""
for _ in $(seq 1 60); do
  COPY_POD=$(oc get pod -n "$MODEL_NS" -l "batch.kubernetes.io/job-name=${COPY_JOB}" \
    -o jsonpath='{.items[0].metadata.name}' --insecure-skip-tls-verify=true 2>/dev/null || true)
  if [[ -n "$COPY_POD" ]]; then
    COPY_READY=$(oc get pod "$COPY_POD" -n "$MODEL_NS" \
      -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' \
      --insecure-skip-tls-verify=true 2>/dev/null || true)
    [[ "$COPY_READY" == "True" ]] && break
  fi
  sleep 2
done
if [[ -z "$COPY_POD" || "${COPY_READY:-}" != "True" ]]; then
  echo "ERROR: copy job pod did not become Ready." >&2
  exit 1
fi

IFS=',' read -r -a OUTPUT_FILES <<<"$GUIDELLM_OUTPUTS"
for output_file in "${OUTPUT_FILES[@]}"; do
  output_file="${output_file#"${output_file%%[![:space:]]*}"}"
  output_file="${output_file%"${output_file##*[![:space:]]}"}"
  oc exec -n "$MODEL_NS" "$COPY_POD" -c copy --insecure-skip-tls-verify=true \
    -- cat "/results/${output_file}" >"${RESULTS_DIR}/${output_file}"
done

if [[ "$KEEP_RESOURCES" != "true" ]]; then
  echo "── Cleaning temporary GuideLLM resources ──"
  oc delete job "$COPY_JOB" -n "$MODEL_NS" --ignore-not-found \
    --insecure-skip-tls-verify=true >/dev/null
  oc delete job "$JOB_NAME" -n "$MODEL_NS" --ignore-not-found \
    --insecure-skip-tls-verify=true >/dev/null
  oc delete pvc "$PVC_NAME" -n "$MODEL_NS" --ignore-not-found \
    --insecure-skip-tls-verify=true >/dev/null
else
  echo "✓ Temporary resources retained: job/${JOB_NAME}, job/${COPY_JOB}, pvc/${PVC_NAME}"
fi

if [[ -f "${RESULTS_DIR}/benchmark-results.json" ]]; then
  echo "── Generating capacity report ──"
  python3 "${SCRIPT_DIR}/scripts/analyze-guidellm.py" \
    "${RESULTS_DIR}/benchmark-results.json" \
    --output "${RESULTS_DIR}/capacity-report.md" || \
    echo "! capacity report generation failed; raw results remain in ${RESULTS_DIR}" >&2
fi

echo "✓ GuideLLM benchmark complete"
echo "  Results: ${RESULTS_DIR}"
[[ -f "${RESULTS_DIR}/capacity-report.md" ]] && echo "  Capacity report: ${RESULTS_DIR}/capacity-report.md"
