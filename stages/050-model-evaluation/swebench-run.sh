#!/usr/bin/env bash
# SWE-bench for a governed MaaS model, in three steps:
#   agents  one Job per instance runs mini-swe-agent inside the instance's own SWE-bench image against the
#           MaaS endpoint and uploads its prediction to the tenant bucket (swebench/<run>/preds/<id>.json);
#   merge   collects the predictions into swebench/<run>/predictions.jsonl (SWE-bench predictions format);
#   submit  posts the EvalHub job for the community swebench provider with the documented S3 test-data
#           reference (RHOAI 3.5 "Evaluating AI systems", Use custom data from S3) and MLflow tracking.
# Prerequisites: Stage 050 synced (swebench provider, RBAC, swebench-agent ConfigMap, evalhub-s3-test-data
# Secret), the anyuid SCC binding from stages/050-model-evaluation/README.md, and `swebench` listed in the
# EvalHub CR providers. The merge step runs in the cluster so no object-storage credential leaves it.
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
  swebench-run.sh agents --model-name <maas model id> --run <run id> [--subset verified|lite] [--count N | --instances id1,id2]
  swebench-run.sh status --run <run id>
  swebench-run.sh merge  --run <run id>
  swebench-run.sh submit --run <run id> --model-name <maas model id> [--subset verified|lite] [--experiment NAME] [--wait]

Options:
  --model-name NAME   MaaS model id, e.g. publishers/internal-models/models/qwen3-8-27b-int4
  --run ID            Run id (lowercase, digits, dashes); bucket prefix swebench/<run>/
  --subset NAME       verified (default, 500 instances) or lite (300)
  --count N           First N instances of the subset in dataset order (default 10)
  --instances LIST    Explicit comma-separated instance ids instead of --count
  --tenant NS         EvalHub tenant namespace (default: demo-sandbox)
  --experiment NAME   MLflow experiment (default: agentic-coding-qualification)
  --wait              submit only: poll the EvalHub job until it ends
USAGE
}

CMD="${1:-}"; [[ -n "$CMD" ]] && shift || { usage; exit 1; }
MODEL_NAME=""; RUN=""; SUBSET="verified"; COUNT="10"; INSTANCES=""; TENANT="demo-sandbox"; EXPERIMENT="agentic-coding-qualification"; WAIT="false"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --model-name) MODEL_NAME="$2"; shift 2;; --run) RUN="$2"; shift 2;; --subset) SUBSET="$2"; shift 2;; --count) COUNT="$2"; shift 2;;
    --instances) INSTANCES="$2"; shift 2;; --tenant) TENANT="$2"; shift 2;; --experiment) EXPERIMENT="$2"; shift 2;; --wait) WAIT="true"; shift;;
    -h|--help) usage; exit 0;; *) echo "[FAIL] unknown option: $1" >&2; usage; exit 1;;
  esac
done
[[ "$RUN" =~ ^[a-z0-9][a-z0-9-]{0,40}$ ]] || { echo '[FAIL] --run must be lowercase letters, digits and dashes' >&2; exit 1; }
case "$SUBSET" in verified) DATASET="princeton-nlp/SWE-bench_Verified"; BENCH="swebench_verified";; lite) DATASET="princeton-nlp/SWE-bench_Lite"; BENCH="swebench_lite";; *) echo '[FAIL] --subset must be verified or lite' >&2; exit 1;; esac
MINI_SWE_AGENT_VERSION="2.4.6"
T="--request-timeout=10s"

instance_ids() { # dataset order, first COUNT, or the explicit list
  if [[ -n "$INSTANCES" ]]; then tr ',' '\n' <<<"$INSTANCES" | sed '/^$/d'; return; fi
  curl -sS -m 60 "https://datasets-server.huggingface.co/rows?dataset=$(python3 -c 'import sys,urllib.parse; print(urllib.parse.quote(sys.argv[1], safe=""))' "$DATASET")&config=default&split=test&offset=0&length=$COUNT" \
    | python3 -c 'import json,sys; [print(r["row"]["instance_id"]) for r in json.load(sys.stdin)["rows"]]'
}
image_for() { python3 -c 'import sys; print(("docker.io/swebench/sweb.eval.x86_64." + sys.argv[1].replace("__", "_1776_") + ":latest").lower())' "$1"; }

case "$CMD" in
  agents)
    [[ -n "$MODEL_NAME" ]] || { echo '[FAIL] --model-name is required' >&2; exit 1; }
    host="$(oc $T get gateway maas-default-gateway -n openshift-ingress -o jsonpath='{.spec.listeners[?(@.name=="api")].hostname}')"
    [[ -n "$host" ]] || { echo '[FAIL] MaaS gateway api hostname not found' >&2; exit 1; }
    for s in evalhub-model-auth-maas evalhub-s3-test-data; do oc $T get secret "$s" -n "$TENANT" -o name >/dev/null || { echo "[FAIL] Secret $TENANT/$s missing; sync Stage 050" >&2; exit 1; }; done
    oc $T get configmap swebench-agent -n "$TENANT" -o name >/dev/null || { echo "[FAIL] ConfigMap $TENANT/swebench-agent missing; sync Stage 050" >&2; exit 1; }
    oc $T get serviceaccount swebench-agent -n "$TENANT" -o name >/dev/null || { echo "[FAIL] ServiceAccount $TENANT/swebench-agent missing" >&2; exit 1; }
    n=0
    while read -r iid; do
      [[ -n "$iid" ]] || continue
      safe="$(python3 -c 'import re,sys; print(re.sub(r"[^a-z0-9-]", "-", sys.argv[1].lower())[:40].strip("-"))' "$iid")"
      RUN="$RUN" IID="$iid" SAFE="$safe" IMAGE="$(image_for "$iid")" SUBSET="$SUBSET" MODEL_NAME="$MODEL_NAME" HOST="$host" TENANT="$TENANT" VER="$MINI_SWE_AGENT_VERSION" python3 - <<'PY' | oc apply -f -
import json, os
e = os.environ
job = {"apiVersion": "batch/v1", "kind": "Job", "metadata": {"name": f"swebench-{e['RUN']}-{e['SAFE']}", "namespace": e["TENANT"],
       "labels": {"app.kubernetes.io/name": "swebench-agent", "swebench.rhoai.io/run": e["RUN"], "swebench.rhoai.io/subset": e["SUBSET"]},
       "annotations": {"swebench.rhoai.io/instance": e["IID"], "swebench.rhoai.io/model": e["MODEL_NAME"]}},
  "spec": {"backoffLimit": 0, "activeDeadlineSeconds": 7200, "ttlSecondsAfterFinished": 172800, "template": {"metadata": {"labels": {"app.kubernetes.io/name": "swebench-agent", "swebench.rhoai.io/run": e["RUN"]}},
    "spec": {"restartPolicy": "Never", "serviceAccountName": "swebench-agent",
      "containers": [{"name": "agent", "image": e["IMAGE"], "imagePullPolicy": "IfNotPresent", "command": ["/bin/bash", "/config/run-instance.sh"],
        "env": [{"name": "INSTANCE_ID", "value": e["IID"]}, {"name": "SUBSET", "value": e["SUBSET"]}, {"name": "SPLIT", "value": "test"}, {"name": "RUN_ID", "value": e["RUN"]},
                {"name": "MODEL_NAME", "value": "openai/" + e["MODEL_NAME"]}, {"name": "OPENAI_API_BASE", "value": "https://" + e["HOST"] + "/v1"},
                {"name": "OPENAI_API_KEY", "valueFrom": {"secretKeyRef": {"name": "evalhub-model-auth-maas", "key": "api-key"}}},
                {"name": "MINI_SWE_AGENT_VERSION", "value": e["VER"]}],
        "envFrom": [{"secretRef": {"name": "evalhub-s3-test-data"}}],
        "resources": {"requests": {"cpu": "1", "memory": "2Gi"}, "limits": {"cpu": "4", "memory": "8Gi"}},
        "volumeMounts": [{"name": "config", "mountPath": "/config"}, {"name": "out", "mountPath": "/out"}]}],
      "volumes": [{"name": "config", "configMap": {"name": "swebench-agent"}}, {"name": "out", "emptyDir": {}}]}}}}
print(json.dumps(job))
PY
      n=$((n + 1))
    done < <(instance_ids)
    log_info "Created $n agent Jobs for run $RUN (model $MODEL_NAME, subset $SUBSET). Follow with: $0 status --run $RUN"
    ;;
  status)
    oc $T get jobs -n "$TENANT" -l "swebench.rhoai.io/run=$RUN" -o custom-columns='JOB:.metadata.name,INSTANCE:.metadata.annotations.swebench\.rhoai\.io/instance,ACTIVE:.status.active,SUCCEEDED:.status.succeeded,FAILED:.status.failed,START:.status.startTime'
    ;;
  merge)
    # Runs inside the tenant with the provisioned S3 Secret: lists swebench/<run>/preds/, writes predictions.jsonl.
    oc $T delete job "swebench-merge-$RUN" -n "$TENANT" --ignore-not-found >/dev/null
    RUN="$RUN" TENANT="$TENANT" python3 - <<'PY' | oc apply -f -
import json, os
e = os.environ
script = r'''
import json, os, boto3
s3 = boto3.client("s3", endpoint_url=os.environ["AWS_S3_ENDPOINT"], aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"], aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"], region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))
bucket, run = os.environ["AWS_S3_BUCKET"], os.environ["RUN_ID"]; prefix = f"swebench/{run}/preds/"
keys = [o["Key"] for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix) for o in page.get("Contents", [])]
lines, empty = [], 0
for k in sorted(keys):
    entry = json.loads(s3.get_object(Bucket=bucket, Key=k)["Body"].read())
    if not entry.get("model_patch"): empty += 1
    lines.append(json.dumps(entry))
body = ("\n".join(lines) + "\n").encode()
s3.put_object(Bucket=bucket, Key=f"swebench/{run}/predictions.jsonl", Body=body)
print(f"merged {len(lines)} predictions ({empty} empty) into s3://{bucket}/swebench/{run}/predictions.jsonl")
'''
job = {"apiVersion": "batch/v1", "kind": "Job", "metadata": {"name": f"swebench-merge-{e['RUN']}", "namespace": e["TENANT"], "labels": {"app.kubernetes.io/name": "swebench-agent", "swebench.rhoai.io/run": e["RUN"]}},
  "spec": {"backoffLimit": 1, "ttlSecondsAfterFinished": 3600, "template": {"spec": {"restartPolicy": "Never",
    "containers": [{"name": "merge", "image": "registry.redhat.io/rhoai/odh-pipeline-runtime-datascience-cpu-py312-rhel9@sha256:6552d908bb1daf0ac4b4ecf23e08a0eb7c99c84e9f3d84b25fa1a5f7a8a0cf4c",
      "command": ["python3", "-c", script], "env": [{"name": "RUN_ID", "value": e["RUN"]}], "envFrom": [{"secretRef": {"name": "evalhub-s3-test-data"}}],
      "resources": {"requests": {"cpu": "100m", "memory": "256Mi"}, "limits": {"cpu": "500m", "memory": "512Mi"}}}]}}}}
print(json.dumps(job))
PY
    oc $T wait --for=condition=complete "job/swebench-merge-$RUN" -n "$TENANT" --timeout=300s >/dev/null && oc $T logs "job/swebench-merge-$RUN" -n "$TENANT" | tail -3
    ;;
  submit)
    [[ -n "$MODEL_NAME" ]] || { echo '[FAIL] --model-name is required' >&2; exit 1; }
    EVALHUB_URL="https://$(oc $T get route evalhub -n evalhub -o jsonpath='{.spec.host}')"; TOKEN="$(oc whoami -t)"
    bucket="$(oc $T get secret evalhub-s3-test-data -n "$TENANT" -o jsonpath='{.data.AWS_S3_BUCKET}' | base64 -d)"
    host="$(oc $T get gateway maas-default-gateway -n openshift-ingress -o jsonpath='{.spec.listeners[?(@.name=="api")].hostname}')"
    ids="$(oc $T get jobs -n "$TENANT" -l "swebench.rhoai.io/run=$RUN,app.kubernetes.io/name=swebench-agent" -o jsonpath='{range .items[*]}{.metadata.annotations.swebench\.rhoai\.io/instance}{"\n"}{end}' | sed '/^$/d' | sort -u)"
    [[ -n "$ids" ]] || { echo "[FAIL] no agent Jobs found for run $RUN" >&2; exit 1; }
    BODY="$(mktemp)"; RESP="$(mktemp)"; trap 'rm -f "$BODY" "$RESP"' EXIT
    RUN="$RUN" MODEL_NAME="$MODEL_NAME" HOST="$host" BUCKET="$bucket" BENCH="$BENCH" IDS="$ids" EXPERIMENT="$EXPERIMENT" python3 - > "$BODY" <<'PY'
import json, os
e = os.environ; ids = [i for i in e["IDS"].split("\n") if i]
body = {"name": f"swebench-{e['BENCH'].split('_')[1]}-{e['MODEL_NAME'].split('/')[-1]}-{e['RUN']}", "tags": ["stage-050", "coding", "swebench"],
        "model": {"url": "https://" + e["HOST"], "name": e["MODEL_NAME"], "auth": {"secret_ref": "evalhub-model-auth-maas"}},
        "experiment": {"name": e["EXPERIMENT"]},
        "benchmarks": [{"id": e["BENCH"], "provider_id": "swebench",
                        "parameters": {"predictions_path": "/test_data/predictions.jsonl", "instance_ids": ids, "split": "test", "max_workers": 4, "timeout_per_instance": 1800, "k8s_registry": "docker.io/swebench"},
                        "test_data_ref": {"s3": {"bucket": e["BUCKET"], "key": f"swebench/{e['RUN']}", "secret_ref": "evalhub-s3-test-data"}}}]}
print(json.dumps(body))
PY
    code="$(curl -sS -m 60 -o "$RESP" -w '%{http_code}' -X POST -H "Authorization: Bearer $TOKEN" -H "X-Tenant: $TENANT" -H 'Content-Type: application/json' --data-binary "@$BODY" "$EVALHUB_URL/api/v1/evaluations/jobs")"
    [[ "$code" == "202" || "$code" == "201" ]] || { echo "[FAIL] EvalHub returned HTTP $code: $(head -c 600 "$RESP")" >&2; exit 1; }
    JOB_ID="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["resource"]["id"])' < "$RESP")"
    log_info "Submitted SWE-bench grading job $JOB_ID for run $RUN ($(wc -l <<<"$ids" | tr -d ' ') instances)"
    [[ "$WAIT" == "true" ]] && "$SCRIPT_DIR/submit-evaluation.sh" --status "$JOB_ID" --wait
    ;;
  *) usage; exit 1;;
esac
