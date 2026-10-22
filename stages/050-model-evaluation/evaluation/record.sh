#!/usr/bin/env bash
# Record a completed EvalHub job on a registered model version in the model registry, as the logged-in user.
# RHOAI 3.5 shows a model version's custom properties on its details page ("Editing model version metadata",
# Properties). The version gets references to the evidence rather than copies of it, keyed per benchmark
# (evalhub.<benchmark>.<field>): the EvalHub job and its results page in the dashboard, a one-line verdict (primary
# metric, threshold and direction, pass or fail), the MLflow experiment and run, and for pipeline-mode providers
# (garak-kfp) a link to the pipeline run. A recording replaces only its own benchmarks' properties; the version's
# other properties are kept. Refuses a job that is not completed, an unreadable version, and
# a Garak result without per-probe metrics (the adapter skipped the results download, so the score is empty).
# Usage: stages/050-model-evaluation/evaluation/record.sh --job JOB_ID --model-version VERSION_ID [--tenant NS] [--registry NAME] [--dry-run]
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"

JOB="" MV="" TENANT="evaluated-models" REGISTRY="demo-registry" DRY_RUN="false"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --job) JOB="${2:-}"; shift 2 ;;
    --model-version) MV="${2:-}"; shift 2 ;;
    --tenant) TENANT="${2:-}"; shift 2 ;;
    --registry) REGISTRY="${2:-}"; shift 2 ;;
    --dry-run) DRY_RUN="true"; shift ;;
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
# A Garak benchmark always reports one <probe>_asr metric per probe; only the aggregate means no results were read.
empty="$(jq -r '[.results.benchmarks // [] | .[] | select((.provider_id // "") | startswith("garak"))
  | select([.metrics // {} | keys[] | select(endswith("_asr"))] | length == 0) | .id] | join(",")' "$WORK/job.json")"
[[ -z "$empty" ]] || { echo "[FAIL] benchmark(s) $empty carry no per-probe results: the adapter skipped the results download (job without a model auth Secret?); not recording an empty score" >&2; exit 1; }

# Score direction per benchmark: the job's own primary_score, else the provider catalog (jobs submitted without it).
LOWER='{}'
for pb in $(jq -r '.benchmarks // [] | .[] | "\(.provider_id)/\(.id)"' "$WORK/job.json"); do
  lower="$(jq -r --arg b "${pb#*/}" '[.benchmarks // [] | .[] | select(.id == $b) | .primary_score.lower_is_better // empty][0] // empty' "$WORK/job.json")"
  [[ -n "$lower" ]] || lower="$(curl -sS -m 60 --config <(auth_config) -H "X-Tenant: $TENANT" "$EVALHUB_URL/api/v1/evaluations/providers/${pb%%/*}" |
    jq -r --arg b "${pb#*/}" '[.benchmarks // [] | .[] | select(.id == $b) | .primary_score.lower_is_better // false][0] // false')"
  LOWER="$(jq -c --arg b "${pb#*/}" --argjson v "$lower" '.[$b] = $v' <<<"$LOWER")"
done

# ── Pipeline runs of pipeline-mode benchmarks (garak-kfp names its run evalhub-garak-<job id>) ──────────────────
DASHBOARD="https://$(oc $T get route data-science-gateway -n openshift-ingress -o jsonpath='{.spec.host}')"
EVALUATION_URL="$DASHBOARD/evaluation/$TENANT/results/$JOB"
PIPELINE_URLS=""
if jq -e '[.benchmarks // [] | .[] | select(.provider_id == "garak-kfp")] | length > 0' "$WORK/job.json" >/dev/null; then
  KFP_URL="https://$(oc $T get route ds-pipeline-dspa -n "$TENANT" -o jsonpath='{.spec.host}')"
  filter="$(jq -rn --arg n "evalhub-garak-$JOB" '{predicates: [{key: "display_name", operation: "EQUALS", string_value: $n}]} | tojson | @uri')"
  PIPELINE_URLS="$(curl -sS -m 60 --config <(auth_config) "$KFP_URL/apis/v2beta1/runs?namespace=$TENANT&page_size=20&filter=$filter" |
    jq -r --arg d "$DASHBOARD" --arg ns "$TENANT" '[.runs // [] | .[] | "\($d)/develop-train/pipelines/runs/\($ns)/runs/\(.run_id)"] | join(" ")')"
  [[ -n "$PIPELINE_URLS" ]] || echo "[WARN] no pipeline run named evalhub-garak-$JOB found in $TENANT" >&2
fi

# ── Properties, keyed per benchmark: evalhub.<benchmark>.<field> ─────────────────────────────────────────────
# Recording a job replaces the properties of its own benchmarks only, so the latest result of each benchmark stays
# side by side (avid_security next to intents). Flat evalhub.<field> keys from older recordings are removed; the
# version's other properties are kept.
RECORDED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)" PIPELINE_URLS="$PIPELINE_URLS" EVALUATION_URL="$EVALUATION_URL" jq -c --slurpfile mv "$WORK/mv.json" --argjson lower "$LOWER" '
  def s: {metadataType: "MetadataStringValue", string_value: tostring};
  def truthy: . != null and . != false and . != 0 and . != "" and . != [] and . != {};
  . as $job | (.results // {}) as $res
  | ([$res.benchmarks // [] | .[] | {key: .id, value: .}] | from_entries) as $results
  | [$job.benchmarks // [] | .[] | .id] as $ids
  | ($mv[0].customProperties // {} | with_entries(select(
      (.key | startswith("evalhub.") | not)
      or ((.key | ltrimstr("evalhub.") | contains(".")) and ([.key | startswith("evalhub." + $ids[] + ".")] | any | not)))))
  | reduce ($job.benchmarks // [] | .[]) as $b (.;
      ("evalhub." + $b.id + ".") as $k | ($results[$b.id] // {}) as $r | ($r.test // null) as $t
      | .[$k + "job_id"] = ($job.resource.id | s)
      | .[$k + "job_name"] = ($job.name // "" | s)
      | .[$k + "evaluation_url"] = ($ENV.EVALUATION_URL | s)
      | .[$k + "provider"] = ($b.provider_id // "" | s)
      | .[$k + "model_name"] = ($job.model.name // "" | s)
      | if $t != null then
          .[$k + "result"] = ("\($t.primary_score_metric // "score") \($t.primary_score) (threshold \($t.threshold), "
            + (if $lower[$b.id] then "lower" else "higher" end) + " is better) " + (if $t.pass then "pass" else "fail" end) | s)
          | .[$k + "pass"] = (if $t.pass then "true" else "false" end | s)
        else . end
      | if ($job.experiment.name | truthy) then .[$k + "mlflow_experiment"] = ($job.experiment.name | s) else . end
      | if ($r.mlflow_run_id | truthy) then .[$k + "mlflow_run_id"] = ($r.mlflow_run_id | s) else . end
      | if $b.provider_id == "garak-kfp" and $ENV.PIPELINE_URLS != "" then .[$k + "pipeline_run_url"] = ($ENV.PIPELINE_URLS | s) else . end
      | .[$k + "recorded_at"] = ($ENV.RECORDED_AT | s))
  | {customProperties: .}' "$WORK/job.json" >"$WORK/patch.json"
jq -r '.customProperties | to_entries[] | select(.key | startswith("evalhub.")) | "  \(.key) = \(.value.string_value)"' "$WORK/patch.json"

# ── Write (the only change) ───────────────────────────────────────────────────
[[ "$DRY_RUN" == "false" ]] || { echo "dry run: model version $MV not changed"; exit 0; }
code="$(curl -sS -m 60 -o "$WORK/mv.json" -w '%{http_code}' -X PATCH --config <(auth_config) -H 'Content-Type: application/json' \
  --data-binary "@$WORK/patch.json" "$REGISTRY_URL/model_versions/$MV")"
[[ "$code" == "200" ]] || { echo "[FAIL] registry returned HTTP $code: $(head -c 400 "$WORK/mv.json")" >&2; exit 1; }
jq -r '"recorded on model version \(.id) \(.name // "None") (\([.customProperties // {} | keys[] | select(startswith("evalhub."))] | length) evalhub properties)"' "$WORK/mv.json"
