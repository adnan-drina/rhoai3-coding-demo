#!/usr/bin/env bash
# Record a completed EvalHub job on a registered model version in the model registry, as the logged-in user.
# RHOAI 3.5 shows a model version's custom properties on its details page ("Editing model version metadata",
# Properties); the registry API also accepts metric artifacts and experiment runs, but the 3.5 dashboard does not render
# those. Changes one model version: writes one evalhub.<metric> property per numeric benchmark metric plus the job,
# experiment and MLflow references, merged with the properties already on the version. Safe to rerun: a rerun rewrites
# the same evalhub.* properties (and evalhub.recorded_at). Refuses a job that is not completed and an unreadable version.
# Usage: stages/050-model-evaluation/evaluation/record.sh --job JOB_ID --model-version VERSION_ID [--tenant NS] [--registry NAME]
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"

JOB="" MV="" TENANT="evaluated-models" REGISTRY="demo-registry"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --job) JOB="${2:-}"; shift 2 ;;
    --model-version) MV="${2:-}"; shift 2 ;;
    --tenant) TENANT="${2:-}"; shift 2 ;;
    --registry) REGISTRY="${2:-}"; shift 2 ;;
    *) sed -n 's/^# Usage: //p' "$0" >&2; exit 1 ;;
  esac
done
[[ -n "$JOB" && -n "$MV" ]] || { echo '[FAIL] --job and --model-version are required' >&2; sed -n 's/^# Usage: //p' "$0" >&2; exit 1; }
load_env
check_oc_logged_in

# ── Read the job and the model version ────────────────────────────────────────
T="--request-timeout=10s"
EVALHUB_URL="https://$(oc $T get route evalhub -n evalhub -o jsonpath='{.spec.host}')"
REGISTRY_URL="https://$(oc $T get route "${REGISTRY}-https" -n rhoai-model-registries -o jsonpath='{.spec.host}')/api/model_registry/v1alpha3"
TOKEN="$(oc whoami -t)"
# The token reaches curl only through --config, never as an argument.
auth_config() { printf 'header = "Authorization: Bearer %s"\n' "$TOKEN"; }
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
curl -sS -m 60 --config <(auth_config) -H "X-Tenant: $TENANT" "$EVALHUB_URL/api/v1/evaluations/jobs/$JOB" >"$WORK/job.json"
curl -sS -m 60 --config <(auth_config) "$REGISTRY_URL/model_versions/$MV" >"$WORK/mv.json"

state="$(jq -r '.status.state // "None"' "$WORK/job.json")"
[[ "$state" == completed ]] || { echo "[FAIL] job $(jq -r '.resource.id // "None"' "$WORK/job.json") is $state, not completed" >&2; exit 1; }
jq -e 'has("name")' "$WORK/mv.json" >/dev/null || { echo "[FAIL] model version not readable: $(jq -c . "$WORK/mv.json" | head -c 200)" >&2; exit 1; }

# ── Properties: existing ones kept, evalhub.* written ─────────────────────────
# Numeric metrics (booleans count as 0/1) become doubles, except the all.* aggregates; the rest are strings.
RECORDED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)" jq -c --slurpfile mv "$WORK/mv.json" '
  def s: {metadataType: "MetadataStringValue", string_value: tostring};
  def d: {metadataType: "MetadataDoubleValue", double_value: (if type == "boolean" then (if . then 1 else 0 end) else . end)};
  def truthy: . != null and . != false and . != 0 and . != "" and . != [] and . != {};
  . as $job | (.results // {}) as $res
  | reduce ($res.benchmarks // [] | .[] | .metrics // {} | to_entries[]
      | select((.value | type == "number" or type == "boolean") and (.key | startswith("all.") | not))) as $m
      ($mv[0].customProperties // {}; .["evalhub." + $m.key] = ($m.value | d))
  | if ($res.test | type) == "object" and ($res.test | has("passed"))
    then .["evalhub.pass"] = (if ($res.test.passed | truthy) then "true" else "false" end | s) else . end
  | .["evalhub.job_id"] = ($job.resource.id | s)
  | .["evalhub.job_name"] = ($job.name // "" | s)
  | .["evalhub.model_name"] = ($job.model.name // "" | s)
  | .["evalhub.benchmarks"] = ([$job.benchmarks // [] | .[] | (.provider_id // "") + ":" + (.id // "")] | join(",") | s)
  | if ($job.experiment.name | truthy) then .["evalhub.mlflow_experiment"] = ($job.experiment.name | s) else . end
  | if ($res.mlflow_experiment_url | truthy) then .["evalhub.mlflow_experiment_url"] = ($res.mlflow_experiment_url | s) else . end
  | .["evalhub.recorded_at"] = ($ENV.RECORDED_AT | s)
  | {customProperties: .}' "$WORK/job.json" >"$WORK/patch.json"
echo "properties to write: $(jq -r '[.customProperties | keys_unsorted[] | select(startswith("evalhub."))] | join(", ")' "$WORK/patch.json")"

# ── Write (the only change) ───────────────────────────────────────────────────
code="$(curl -sS -m 60 -o "$WORK/mv.json" -w '%{http_code}' -X PATCH --config <(auth_config) -H 'Content-Type: application/json' \
  --data-binary "@$WORK/patch.json" "$REGISTRY_URL/model_versions/$MV")"
[[ "$code" == "200" ]] || { echo "[FAIL] registry returned HTTP $code: $(head -c 400 "$WORK/mv.json")" >&2; exit 1; }
jq -r '"recorded on model version \(.id) \(.name // "None") (\([.customProperties // {} | keys[] | select(startswith("evalhub."))] | length) evalhub properties)"' "$WORK/mv.json"
