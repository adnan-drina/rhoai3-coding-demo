#!/usr/bin/env bash
# Stage 050: MLflow, EvalHub, evaluation content and the model qualification pipeline, at one reviewed published
# revision. Before the first write: Stage 010-040 prerequisites and the adoption preflight. After the Applications:
# the database credentials and the MLflow tracking address the services need (Argo CD owns every workload and CR).
# Running an evaluation is a separate step (dashboard Develop & train → Evaluations).
# Usage: stages/050-model-evaluation/deploy.sh [--revision REF]   (REF defaults to GIT_REPO_BRANCH, then HEAD)
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"
load_env
check_oc_logged_in
require_env GIT_REPO_URL "reviewed Stage 050 source repository"
assert_required_env
ref="${GIT_REPO_BRANCH:-HEAD}"
if [[ "${1:-}" == --revision && $# -eq 2 ]]; then ref="$2"; elif [[ $# -ne 0 ]]; then sed -n 's/^# Usage: //p' "$0" >&2; exit 1; fi
STAGE_APPS="$REPO_ROOT/scripts/stage-apps.sh"
APPS=redhat-ods-applications
MANAGED_BY=stage050-ai-services-setup
fail() { log_error "$*"; exit 1; }
read_json() { oc --request-timeout=10s get "$@" --ignore-not-found -o json; }

revision=$("$STAGE_APPS" select 050 --ref "$ref" --repo-url "$GIT_REPO_URL")

# ── Read-only preflight ───────────────────────────────────────────────────────
"$STAGE_APPS" preflight 050 --repo-url "$GIT_REPO_URL"
"$STAGE_APPS" status 010 --repo-url "$GIT_REPO_URL" >/dev/null || fail "Stage 010 must be reconciled first"
dashboard_fields=$("$STAGE_APPS" delegated 010 OdhDashboardConfig odh-dashboard-config "$APPS" --group opendatahub.io)
dsc_fields=$("$STAGE_APPS" delegated 010 DataScienceCluster default-dsc --group datasciencecluster.opendatahub.io)
for field in /spec/dashboardConfig/disableLMEval /spec/dashboardConfig/globalProjectPrompts /spec/globalMLflowNamespaces; do
  grep -qx "$field" <<<"$dashboard_fields" || fail "Stage 010 has not delegated $field (evaluation/global prompt configuration)"
done
for field in /spec/components/trustyai /spec/components/mlflowoperator; do
  grep -qx "$field" <<<"$dsc_fields" || fail "Stage 010 has not delegated $field"
done
read_json odhdashboardconfig odh-dashboard-config -n "$APPS" | jq -e '.spec.globalMLflowNamespaces // [] | . == [] or . == ["ai-curated-prompts"]' >/dev/null ||
  fail "Foreign global prompt configuration requires a reviewed merge before deployment"
# Serving and MaaS stay reconciled from source; stopped model compute is allowed.
for app in 030-private-model-serving $("$STAGE_APPS" names 040); do
  [[ $(oc --request-timeout=10s get applications.argoproj.io "$app" -n openshift-gitops -o jsonpath='{.status.sync.status}' 2>/dev/null) == Synced ]] ||
    fail "$app must be Synced before Stage 050"
done
read_json datasciencecluster default-dsc | jq -e '.spec.components.kserve.managementState == "Managed"
  and any(.status.conditions[]?; .type == "KserveReady" and .status == "True")' >/dev/null || fail "Stage 030 KServe must be Managed and KserveReady"
oc --request-timeout=10s get crd inferenceservices.serving.kserve.io >/dev/null || fail "KServe InferenceServices API is absent"
read_json configmap inferenceservice-config -n "$APPS" | jq -e '(.data.deploy // "{}" | fromjson | .defaultDeploymentMode) == "RawDeployment"' >/dev/null ||
  fail "Native KServe defaultDeploymentMode must be RawDeployment"
read_json argocd openshift-gitops -n openshift-gitops | jq -e '.spec.extraConfig["resource.customizations.health.mlflow.opendatahub.io_MLflow"] // ""
  | . as $h | all("Available", "MLflowOperatorReady", "Migration", "observedGeneration"; . as $w | $h | contains($w))' >/dev/null || fail "Install the reviewed native MLflow health gate (Stage 010) before Stage 050"
# Retained storage must be the bound, exact objects; the runtime MLflow connection must be this setup's own.
pvc=$(read_json pvc mlflow-postgresql -n "$APPS")
[[ -z "$pvc" ]] || jq -e '.status.phase == "Bound"' <<<"$pvc" >/dev/null || fail "Retained MLflow PVC is not Bound"
obc=$(read_json objectbucketclaim rhoai-mlflow-artifacts -n "$APPS")
[[ -z "$obc" ]] || jq -e '.status.phase == "Bound" and .spec.bucketName == "rhoai-mlflow-artifacts"' <<<"$obc" >/dev/null || fail "Retained artifact bucket differs"
connection=$(read_json configmap evalhub-mlflow-connection -n evalhub)
[[ -z "$connection" ]] || jq -e --arg m "$MANAGED_BY" '.metadata | (.ownerReferences // [] | length) == 0 and .deletionTimestamp == null
  and (.annotations["argocd.argoproj.io/tracking-id"] // "") == "" and .labels["app.kubernetes.io/managed-by"] == $m' <<<"$connection" >/dev/null ||
  fail "Runtime MLflow connection ConfigMap has foreign ownership"
# A database with neither storage nor workload is new: its credentials may be generated once, after the Applications
# create the storage. Existing storage without its credential Secret is retained data whose credentials must be restored.
fresh=""
for pair in mlflow:"$APPS" evalhub:evalhub; do
  feature=${pair%%:*} ns=${pair#*:}
  storage=$(oc --request-timeout=10s get pvc,statefulset "$feature-postgresql" -n "$ns" --ignore-not-found -o name)
  secret=$(oc --request-timeout=10s get secret "$feature-db-credentials" -n "$ns" --ignore-not-found -o name)  # metadata only
  [[ -n "$secret" || -z "$storage" ]] || fail "Existing $feature PostgreSQL lacks its credentials; restore them instead of generating a password"
  [[ -n "$storage" ]] || fresh+=" $feature"
done

# ── First change: the component Applications at the reviewed commit ─────────
# The services need their database credentials before they become healthy, so the setup runs before the wait.
"$STAGE_APPS" deploy 050 --revision "$revision" --repo-url "$GIT_REPO_URL" --no-wait

# wait_until SECONDS LABEL COMMAND...: poll every 5 s.
wait_until() {
  local deadline=$((SECONDS + $1)) label=$2; shift 2
  log_info "Waiting for $label"
  until "$@"; do (( SECONDS < deadline )) || fail "Timed out waiting for $label; inspect operator and Argo CD status"; sleep 5; done
}
namespace_active() { [[ $(oc --request-timeout=10s get namespace "$1" -o jsonpath='{.status.phase}' 2>/dev/null) == Active ]]; }
wait_until 300 "namespace $APPS" namespace_active "$APPS"
wait_until 300 "namespace evalhub" namespace_active evalhub

# Database credentials: reuse a valid unowned Secret, or generate one for a fresh database. The password lives in
# memory and reaches jq through its environment and oc through stdin; it is never printed or passed as an argument.
# Private same-namespace database transport is plaintext (demo boundary); URI mode overrides the chart's PGSSLMODE.
URI_JQ='def uri($f; $ns; $u; $p; $d): (if $f == "mlflow" then "postgresql" else "postgres" end)
  + "://\($u | @uri):\($p | @uri)@\($f)-postgresql.\($ns).svc.cluster.local:5432/\($d | @uri)?sslmode=disable";
  def urikey($f): if $f == "mlflow" then "backend-store-uri" else "db-url" end;'
for pair in mlflow:"$APPS" evalhub:evalhub; do
  feature=${pair%%:*} ns=${pair#*:} name="$feature-db-credentials"
  if [[ -n "$(oc --request-timeout=10s get secret "$name" -n "$ns" --ignore-not-found -o name)" ]]; then
    oc --request-timeout=10s get secret "$name" -n "$ns" -o json | jq -e --arg f "$feature" --arg ns "$ns" "$URI_JQ"'
      .metadata as $m | (.data | map_values(@base64d)) as $d
      | (($m.ownerReferences // [] | length) == 0 and $m.deletionTimestamp == null and ($m.annotations["argocd.argoproj.io/tracking-id"] // "") == "")
      and ($d["database-password"] // "") != "" and ($d["database-user"] // "" | test("^[A-Za-z_][A-Za-z0-9_]*$"))
      and ($d["database-name"] // "" | test("^[A-Za-z_][A-Za-z0-9_]*$"))
      and $d[urikey($f)] == uri($f; $ns; $d["database-user"]; $d["database-password"]; $d["database-name"])' >/dev/null ||
      fail "$name is foreign, or its user, database or URI does not match the demo endpoint; no values changed"
    log_info "Reusing $feature database credentials"
    continue
  fi
  [[ " $fresh " == *" $feature "* ]] || fail "Existing $feature PostgreSQL lacks its Secret; restore the original credentials"
  PASSWORD=$(openssl rand -hex 24) jq -n --arg f "$feature" --arg ns "$ns" --arg name "$name" --arg m "$MANAGED_BY" "$URI_JQ"'
    {apiVersion: "v1", kind: "Secret", type: "Opaque",
     metadata: {name: $name, namespace: $ns, labels: {"app.kubernetes.io/part-of": "rhoai-platform", "app.kubernetes.io/name": $name,
       "app.kubernetes.io/component": "configuration", "app.kubernetes.io/managed-by": $m}},
     stringData: ({"database-user": $f, "database-password": $ENV.PASSWORD, "database-name": $f}
       + {(urikey($f)): uri($f; $ns; $f; $ENV.PASSWORD; $f)})}' | oc --request-timeout=10s create -f - >/dev/null ||
    fail "Could not create $name"
  log_info "$feature database credentials created"
done

# The bucket claim publishes the internal HTTPS endpoint the service CA trusts, and its credential keys.
bucket_ready() {
  local name=rhoai-mlflow-artifacts keys
  read_json objectbucketclaim "$name" -n "$APPS" | jq -e --arg n "$name" '.status.phase == "Bound" and .spec.bucketName == $n' >/dev/null || return 1
  read_json configmap "$name" -n "$APPS" | jq -e --arg n "$name" '.data | .BUCKET_NAME == $n and .BUCKET_PORT == "443"
    and (.BUCKET_HOST // "" | test("\\.openshift-storage\\.svc(\\.cluster\\.local)?$"))' >/dev/null || return 1
  [[ -n "$(oc --request-timeout=10s get configmap mlflow-service-ca -n "$APPS" -o jsonpath='{.data.service-ca\.crt}' 2>/dev/null)" ]] || return 1
  keys=$(oc --request-timeout=10s get secret "$name" -n "$APPS" -o go-template='{{range $k, $v := .data}}{{$k}}{{"\n"}}{{end}}' 2>/dev/null) || return 1
  grep -qx AWS_ACCESS_KEY_ID <<<"$keys" && grep -qx AWS_SECRET_ACCESS_KEY <<<"$keys"
}
wait_until 900 "the bound MLflow artifact bucket and trusted S3 endpoint" bucket_ready
# MLflow Available, its OperatorReady and Migration conditions at the CR generation (Available omits it), and its
# one operator-owned Deployment current.
mlflow_available() {
  local mlflow
  mlflow=$(read_json mlflows.mlflow.opendatahub.io mlflow)
  [[ -n "$mlflow" ]] || return 1
  jq -e '.metadata.generation as $g | any(.status.conditions[]?; .type == "Available" and .status == "True")
    and ([.status.conditions[]? | select((.type == "MLflowOperatorReady" or .type == "Migration") and .status == "True"
      and .observedGeneration == $g) | .type] | unique | length) == 2
    and (.status.address.url // "" | test("^https://[^/@:]+(:[0-9]+)?(/|$)"))' <<<"$mlflow" >/dev/null || return 1
  read_json deployments -n "$APPS" | jq -e --arg uid "$(jq -r '.metadata.uid' <<<"$mlflow")" '[.items[]
    | select(any(.metadata.ownerReferences[]?; .kind == "MLflow" and .uid == $uid and .controller == true))]
    | length == 1 and (.[0] | (.spec.replicas // 1) as $n | .status as $s | $n > 0 and $s.observedGeneration == .metadata.generation
      and ($s.readyReplicas // 0) >= $n and ($s.updatedReplicas // 0) == $n and ($s.replicas // 0) == $n and ($s.availableReplicas // 0) == $n)' >/dev/null
}
wait_until 900 "MLflow Available at its current generation" mlflow_available
# Publish MLflow's native address for EvalHub (runtime ConfigMap owned by this setup, not by Argo CD).
tracking_uri=$(oc --request-timeout=10s get mlflows.mlflow.opendatahub.io mlflow -o jsonpath='{.status.address.url}')
jq -n --arg uri "$tracking_uri" --arg m "$MANAGED_BY" '{apiVersion: "v1", kind: "ConfigMap",
  metadata: {name: "evalhub-mlflow-connection", namespace: "evalhub", labels: {"app.kubernetes.io/part-of": "rhoai-platform",
    "app.kubernetes.io/name": "evalhub-mlflow-connection", "app.kubernetes.io/component": "configuration", "app.kubernetes.io/managed-by": $m}},
  data: {"tracking-uri": $uri}}' | oc --request-timeout=10s apply -f - >/dev/null || fail "Could not publish the MLflow tracking address"

"$STAGE_APPS" wait 050 --revision "$revision" --repo-url "$GIT_REPO_URL" --timeout 1200
evalhub_ready() { [[ $(oc --request-timeout=10s get evalhub evalhub -n evalhub -o jsonpath='{.status.ready}' 2>/dev/null) == True ]]; }
wait_until 900 "EvalHub ready" evalhub_ready
# EvalHub probes MLflow workspace support once at start; started before MLflow answered, it sends no workspace header
# and every job fails "Workspace context is required" (TROUBLESHOOTING). The operator owns the Deployment, so restart
# by deleting the pod.
evalhub_probe() { oc --request-timeout=10s logs -n evalhub deploy/evalhub -c evalhub 2>/dev/null |
  grep 'MLflow workspace support probed' | tail -1; }
evalhub_probed() { [[ -n $(evalhub_probe) ]]; }
evalhub_workspaces() { evalhub_probe | grep -q '"workspaces_enabled":true'; }
wait_until 120 "EvalHub MLflow workspace probe" evalhub_probed
if ! evalhub_workspaces; then
  log_warn "EvalHub started before MLflow answered; restarting its pod"
  oc --request-timeout=30s delete pod -n evalhub -l app=eval-hub,component=api --wait=true
  wait_until 900 "EvalHub ready" evalhub_ready
  wait_until 300 "EvalHub MLflow workspace probe" evalhub_workspaces
fi

# Stage 040's Studio hook registers the Ops Assistant prompt in MLflow, which this stage installs; on a fresh install
# that hook deferred. Re-run 040-genai-studio's hooks at Stage 040's deployed revision now that MLflow is ready.
studio_revision=$(oc --request-timeout=10s get applications.argoproj.io 040-genai-studio -n openshift-gitops -o jsonpath='{.spec.source.targetRevision}')
"$STAGE_APPS" sync 040 --app 040-genai-studio --resync
"$STAGE_APPS" wait 040 --app 040-genai-studio --revision "$studio_revision" --repo-url "$GIT_REPO_URL" --timeout 600

# ── Model registry record of the risk assessment model ───────────────────────
# Registered the way Stage 040 registers its models: one registered model per checkpoint, one version per immutable
# revision with its source artifact, the labels and properties of model-registry-metadata.json (a label is a string
# property with an empty value), and the InferenceService linked to the record. Never overwrites an artifact.
register_risk_model() {
  local dir="$REPO_ROOT/gitops/stages/050-model-evaluation/050-model-qualification" name=gemma-2-9b-abliterated
  local ns=evaluated-models host base meta uri title rev model mid version vid artifacts current desired isvc
  host=$(oc --request-timeout=10s get modelregistries.modelregistry.opendatahub.io demo-registry -n rhoai-model-registries \
    -o jsonpath='{.status.hosts[0]}')
  base="https://$host/api/model_registry/v1alpha3"
  api() {  # PATH [BODY [METHOD]]: authenticated, CA-verified registry call; prints the JSON response
    printf 'header = "Authorization: Bearer %s"\n' "$(oc whoami -t)" |
      curl --config - -sf --max-time 20 -H 'Content-Type: application/json' ${3:+-X "$3"} ${2:+--data "$2"} "$base$1" ||
      fail "authenticated registry request failed"
  }
  uri=$(oc kustomize "$dir" | yaml_json | jq -r --arg n "$name" '.[] | select(.kind == "InferenceService" and .metadata.name == $n)
    | .spec.predictor.model.storageUri')
  title=${uri##*/}; title=${title%%:*}; rev=${uri##*:}
  [[ ${#rev} == 40 ]] || fail "$name source must be immutable"
  meta=$(jq -c -e --arg t "$title" '.[$t]' "$dir/model-registry-metadata.json") || fail "$title registry metadata missing"
  model=$(api "/registered_models?pageSize=500" | jq -c --arg t "$title" '[.items[] | select(.name == $t)]')
  [[ $(jq length <<<"$model") -le 1 ]] || fail "ambiguous registered model name $title"
  if [[ $(jq length <<<"$model") == 0 ]]; then
    model=$(api /registered_models "$(jq -n --arg t "$title" --arg l "${uri#*://}" '{name: $t, owner: "rhoai3-coding-demo",
      description: ("Risk assessment helper (Garak intents SDG and judge) without safety alignment, served only in the "
      + "admin project evaluated-models. Pinned model artifact (\($l | split(":")[0])). Not a qualification candidate.")}')")
  else
    model=$(jq -c '.[0]' <<<"$model")
  fi
  mid=$(jq -r '.id' <<<"$model")
  version=$(api "/registered_models/$mid/versions?pageSize=500" | jq -c --arg v "source-$rev" '[.items[] | select(.name == $v)]')
  [[ $(jq length <<<"$version") -le 1 ]] || fail "ambiguous registered model version source-$rev"
  if [[ $(jq length <<<"$version") == 0 ]]; then
    version=$(api /model_versions "$(jq -n --arg v "source-$rev" --arg m "$mid" --arg r "$rev" \
      '{name: $v, registeredModelId: $m, description: "BF16 weights. Immutable source \($r)"}')")
  else
    version=$(jq -c '.[0]' <<<"$version")
  fi
  vid=$(jq -r '.id' <<<"$version")
  artifacts=$(api "/model_versions/$vid/artifacts" | jq -c '.items // []')
  jq -e --arg u "$uri" 'length == 0 or (length == 1 and .[0].uri == $u)' <<<"$artifacts" >/dev/null ||
    fail "existing $title artifact differs; no overwrite"
  [[ $(jq length <<<"$artifacts") == 1 ]] || api "/model_versions/$vid/artifacts" "$(jq -n --arg u "$uri" '{name: "model-source",
    uri: $u, artifactType: "model-artifact", modelFormatName: "vLLM", modelFormatVersion: "1"}')" >/dev/null
  current=$(jq -S -c '.customProperties // {}' <<<"$model")
  # Labels become exactly the declared set; declared properties are set, other properties stay.
  desired=$(jq -S -c --argjson m "$meta" 'with_entries(select(.value != {metadataType: "MetadataStringValue",
    string_value: ""})) + ($m.labels | map({key: ., value: {metadataType: "MetadataStringValue", string_value: ""}})
    | from_entries) + ($m.properties | with_entries(.value = {metadataType: "MetadataStringValue",
    string_value: .value}))' <<<"$current")
  [[ "$desired" == "$current" ]] || api "/registered_models/$mid" "$(jq -c '{customProperties: .}' <<<"$desired")" PATCH >/dev/null
  # Link the InferenceService (Git owns it; the id labels are delegated) to the record.
  isvc=$(read_json inferenceservice "$name" -n "$ns")
  jq -e --arg u "$uri" '.spec.predictor.model.storageUri == $u
    and (.metadata.annotations["argocd.argoproj.io/tracking-id"] // "" | startswith("050-model-qualification:"))' <<<"$isvc" >/dev/null ||
    fail "$name source or ownership differs"
  jq -c --arg m "$mid" --arg v "$vid" '[{op: "test", path: "/metadata/resourceVersion", value: .metadata.resourceVersion},
    {op: "add", path: "/metadata/labels", value: ((.metadata.labels // {}) + {"modelregistry.opendatahub.io/name": "demo-registry",
      "modelregistry.opendatahub.io/registered-model-id": $m, "modelregistry.opendatahub.io/model-version-id": $v})}]' <<<"$isvc" |
    oc --request-timeout=10s patch inferenceservice "$name" -n "$ns" --type=json --patch-file=/dev/stdin >/dev/null ||
    fail "$name registry linkage patch failed"
  log_success "Registered $name as $title (model $mid, version $vid) and linked its InferenceService"
}
register_risk_model

# Exit 2 (services ready, no evaluation evidence) is the expected result of a deployment.
export RHOAI_STAGE050_EXPECTED_REVISION="$revision"
deadline=$((SECONDS + 900))
until result=0; "$SCRIPT_DIR/validate.sh" >/dev/null 2>&1 || result=$?; [[ "$result" == 0 || "$result" == 2 ]]; do
  (( SECONDS < deadline )) || { "$SCRIPT_DIR/validate.sh" || true; fail "Stage 050 services did not reconcile"; }
  sleep 10
done
log_success "Stage 050 reconciled at ${revision:0:12}; evaluation execution remains a separate step."
