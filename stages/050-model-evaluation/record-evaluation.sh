#!/usr/bin/env bash
# Record a completed EvalHub job on a registered model version in the model registry.
#
# RHOAI 3.5 shows a model version's custom properties on its details page ("Editing model version
# metadata", Properties); the registry API also accepts metric artifacts and experiment runs, but the
# 3.5 dashboard does not render those. This writes one property per benchmark metric plus the job,
# experiment and MLflow references, merging with the properties already on the version.
#
# Usage: record-evaluation.sh --job <evalhub job id> --model-version <registry model version id> [--tenant demo-sandbox]
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
# shellcheck source=../../scripts/shared/lib.sh
source "$REPO_ROOT/scripts/shared/lib.sh"
load_env
check_oc_logged_in
command -v python3 >/dev/null || { echo '[FAIL] python3 is required' >&2; exit 1; }

JOB=""; MV=""; TENANT="demo-sandbox"; REGISTRY="demo-registry"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --job) JOB="$2"; shift 2;; --model-version) MV="$2"; shift 2;; --tenant) TENANT="$2"; shift 2;; --registry) REGISTRY="$2"; shift 2;;
    -h|--help) sed -n '2,10p' "$0"; exit 0;; *) echo "[FAIL] unknown option: $1" >&2; exit 1;;
  esac
done
[[ -n "$JOB" && -n "$MV" ]] || { echo '[FAIL] --job and --model-version are required' >&2; exit 1; }
T="--request-timeout=10s"
EVALHUB_URL="https://$(oc $T get route evalhub -n evalhub -o jsonpath='{.spec.host}')"
REGISTRY_URL="https://$(oc $T get route "${REGISTRY}-https" -n rhoai-model-registries -o jsonpath='{.spec.host}')/api/model_registry/v1alpha3"
TOKEN="$(oc whoami -t)"
JOB_JSON="$(mktemp)"; MV_JSON="$(mktemp)"; PATCH="$(mktemp)"; trap 'rm -f "$JOB_JSON" "$MV_JSON" "$PATCH"' EXIT
curl -sS -m 60 -H "Authorization: Bearer $TOKEN" -H "X-Tenant: $TENANT" "$EVALHUB_URL/api/v1/evaluations/jobs/$JOB" > "$JOB_JSON"
curl -sS -m 60 -H "Authorization: Bearer $TOKEN" "$REGISTRY_URL/model_versions/$MV" > "$MV_JSON"
python3 - "$JOB_JSON" "$MV_JSON" "$PATCH" <<'PY'
import json, sys, datetime
job = json.load(open(sys.argv[1])); mv = json.load(open(sys.argv[2]))
state = (job.get("status") or {}).get("state")
if state != "completed":
    sys.exit(f"[FAIL] job {job.get('resource', {}).get('id')} is {state}, not completed")
if "name" not in mv:
    sys.exit("[FAIL] model version not readable: " + json.dumps(mv)[:200])
props = dict(mv.get("customProperties") or {})
def s(v): return {"metadataType": "MetadataStringValue", "string_value": str(v)}
def d(v): return {"metadataType": "MetadataDoubleValue", "double_value": float(v)}
res = job.get("results") or {}
for b in res.get("benchmarks") or []:
    bid = b.get("id") or ""
    for k, v in (b.get("metrics") or {}).items():
        if isinstance(v, (int, float)) and not k.startswith("all."):
            props[f"evalhub.{k}"] = d(v)
test = res.get("test") or {}
if isinstance(test, dict) and "passed" in test:
    props["evalhub.pass"] = s("true" if test.get("passed") else "false")
props["evalhub.job_id"] = s(job["resource"]["id"]); props["evalhub.job_name"] = s(job.get("name") or "")
props["evalhub.model_name"] = s((job.get("model") or {}).get("name") or "")
props["evalhub.benchmarks"] = s(",".join((x.get("provider_id") or "") + ":" + (x.get("id") or "") for x in (job.get("benchmarks") or [])))
if job.get("experiment", {}).get("name"): props["evalhub.mlflow_experiment"] = s(job["experiment"]["name"])
if res.get("mlflow_experiment_url"): props["evalhub.mlflow_experiment_url"] = s(res["mlflow_experiment_url"])
props["evalhub.recorded_at"] = s(datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
json.dump({"customProperties": props}, open(sys.argv[3], "w"))
print("properties to write:", ", ".join(k for k in props if k.startswith("evalhub.")))
PY
code="$(curl -sS -m 60 -o "$MV_JSON" -w '%{http_code}' -X PATCH -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' --data-binary "@$PATCH" "$REGISTRY_URL/model_versions/$MV")"
[[ "$code" == "200" ]] || { echo "[FAIL] registry returned HTTP $code: $(head -c 400 "$MV_JSON")" >&2; exit 1; }
python3 -c 'import json,sys; mv=json.load(open(sys.argv[1])); print("recorded on model version", mv["id"], mv.get("name"), "(" + str(sum(1 for k in (mv.get("customProperties") or {}) if k.startswith("evalhub."))) + " evalhub properties)")' "$MV_JSON"
