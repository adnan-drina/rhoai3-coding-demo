#!/usr/bin/env bash
# Stage 050 validation: component Applications, MLflow and EvalHub storage, TLS, tokens and configured RBAC, and an
# authenticated EvalHub discovery call. Read-only (local port-forwards only); never submits an evaluation.
# --job-id with --mlflow-run-id also proves one completed evaluation and its MLflow run.
# Exit 0: everything passed, including a completed evaluation; 1: a check failed; 2: services ready, evaluation
# evidence not supplied or not complete.
# Usage: stages/050-model-evaluation/validate.sh [--job-id ID --mlflow-run-id RUN]
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"
JOB_ID="" RUN_ID=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --job-id) JOB_ID=${2:-}; shift 2 ;;
    --mlflow-run-id) RUN_ID=${2:-}; shift 2 ;;
    *) sed -n 's/^# Usage: //p' "$0" >&2; exit 1 ;;
  esac
done
if [[ -n "$JOB_ID$RUN_ID" ]]; then
  [[ "$JOB_ID" =~ ^[A-Za-z0-9_-]+$ && "$RUN_ID" =~ ^[a-fA-F0-9]{32}$ ]] ||
    { echo "Provide both a valid --job-id and a 32-character --mlflow-run-id" >&2; exit 1; }
fi
load_env
check_oc_logged_in

APPS=redhat-ods-applications
TENANT=evaluated-models
BUCKET=rhoai-mlflow-artifacts
read_json() { oc --request-timeout=10s get "$@" -o json 2>/dev/null || echo '{}'; }
# Secret key names only; credential values never reach the validator.
secret_keys() {
  oc --request-timeout=10s get secret "$1" -n "$2" -o go-template='{{range $k, $v := .data}}{{$k}}{{"\n"}}{{end}}' 2>/dev/null || true
}
has_keys() { local name=$1 ns=$2 key keys; shift 2; keys=$(secret_keys "$name" "$ns"); for key in "$@"; do grep -qx "$key" <<<"$keys" || return 1; done; }
yes_no() { jq -e "$@" >/dev/null && echo yes || echo no; }
# jq: a workload with current, fully ready replicas.
FRESH='def fresh: (.spec.replicas // 1) as $n | .status as $s | $n > 0 and .metadata.generation != null
  and $s.observedGeneration == .metadata.generation and ($s.readyReplicas // 0) >= $n
  and ($s.updatedReplicas // 0) == $n and ($s.replicas // 0) == $n and ($s.availableReplicas // 0) == $n;'

# ── Component Applications ────────────────────────────────────────────────────
check_stage_applications 050 "${RHOAI_STAGE050_EXPECTED_REVISION:-}"
# A deliberately stopped candidate model (serving.kserve.io/stop) leaves 050-model-qualification Suspended;
# nothing else may be unhealthy.
parked_only() {
  local app resource
  app=$(read_json applications.argoproj.io 050-model-qualification -n openshift-gitops)
  [[ $(jq -r '.status.health.status // ""' <<<"$app") == Suspended ]] || { echo yes; return; }
  while IFS= read -r resource; do
    [[ $(jq -r '.health' <<<"$resource") == "Suspended" && $(jq -r '.kind' <<<"$resource") == InferenceService ]] || { echo no; return; }
    [[ $(oc --request-timeout=10s get inferenceservice "$(jq -r '.name' <<<"$resource")" -n "$(jq -r '.namespace' <<<"$resource")" \
      -o jsonpath='{.metadata.annotations.serving\.kserve\.io/stop}' 2>/dev/null) == true ]] || { echo no; return; }
  done < <(jq -c '.status.resources[]? | {kind, name, namespace, health: (.health.status // "Healthy")} | select(.health != "Healthy")' <<<"$app")
  echo yes
}
check "050-model-qualification is Suspended only by a stopped candidate InferenceService" parked_only yes
# The risk assessment model is registered once (pinned version and artifact, the labels and properties of
# model-registry-metadata.json) and its InferenceService is linked to that record.
risk_model_record() {
  local dir="$REPO_ROOT/gitops/stages/050-model-evaluation/050-model-qualification" name=gemma-2-9b-abliterated
  local host meta uri title rev model mid vid isvc
  host=$(oc --request-timeout=10s get modelregistries.modelregistry.opendatahub.io demo-registry -n rhoai-model-registries \
    -o jsonpath='{.status.hosts[0]}' 2>/dev/null) || { echo "demo-registry unreadable"; return; }
  registry() {
    printf 'header = "Authorization: Bearer %s"\n' "$(oc whoami -t)" |
      curl --config - -sf --max-time 20 "https://$host/api/model_registry/v1alpha3$1"
  }
  uri=$(oc kustomize "$dir" | yaml_json | jq -r --arg n "$name" '.[] | select(.kind == "InferenceService" and .metadata.name == $n)
    | .spec.predictor.model.storageUri')
  title=${uri##*/}; title=${title%%:*}; rev=${uri##*:}
  meta=$(jq -c -e --arg t "$title" '.[$t]' "$dir/model-registry-metadata.json") || { echo "$title metadata missing"; return; }
  model=$(registry '/registered_models?pageSize=500' | jq -c --arg t "$title" '[.items[] | select(.name == $t)]') ||
    { echo "registry listing failed"; return; }
  [[ $(jq length <<<"$model") == 1 ]] || { echo "$title not registered exactly once"; return; }
  jq -e --argjson m "$meta" '.[0].customProperties // {} | . as $p
    | ([to_entries[] | select(.value == {metadataType: "MetadataStringValue", string_value: ""}) | .key] | sort) == ($m.labels | sort)
    and all($m.properties | to_entries[]; $p[.key].string_value == .value)' <<<"$model" >/dev/null ||
    { echo "$title labels or properties differ from model-registry-metadata.json"; return; }
  mid=$(jq -r '.[0].id' <<<"$model")
  vid=$(registry "/registered_models/$mid/versions?pageSize=500" | jq -r --arg v "source-$rev" \
    '[.items[] | select(.name == $v)] | if length == 1 then .[0].id else "" end')
  [[ -n "$vid" ]] || { echo "$title version source-$rev not registered exactly once"; return; }
  registry "/model_versions/$vid/artifacts" | jq -e --arg u "$uri" '[.items[] | .uri] == [$u]' >/dev/null ||
    { echo "$title artifact differs"; return; }
  isvc=$(read_json inferenceservice "$name" -n "$TENANT")
  jq -e --arg m "$mid" --arg v "$vid" '.metadata.labels // {} | .["modelregistry.opendatahub.io/name"] == "demo-registry"
    and .["modelregistry.opendatahub.io/registered-model-id"] == $m and .["modelregistry.opendatahub.io/model-version-id"] == $v' \
    <<<"$isvc" >/dev/null || { echo "InferenceService $name not linked to $title"; return; }
  echo yes
}
check "Risk assessment model registered with its labels and linked to its InferenceService" risk_model_record yes
# Stage 020 owns the ClusterQueues; this stage owns the consumer LocalQueues in the tenant.
for queue in lq-gpu-reserved-demo lq-gpu-rtxpro6000; do
  record "LocalQueue $queue Active in $TENANT" "$(read_json localqueue "$queue" -n "$TENANT" |
    yes_no 'any(.status.conditions[]?; .type == "Active" and .status == "True")')"
done

# ── Dashboard and MLflow ──────────────────────────────────────────────────────
record "Evaluation/global prompt dashboard configuration" "$(read_json odhdashboardconfig odh-dashboard-config -n "$APPS" |
  yes_no '.spec | .dashboardConfig.disableLMEval == false and .dashboardConfig.globalProjectPrompts == true
    and .globalMLflowNamespaces == ["ai-curated-prompts"]')"
record "Curated prompt workspace references the shared native MLflow" "$(read_json namespace ai-curated-prompts |
  yes_no '.metadata.labels["opendatahub.io/global-mlflow-workspace"] == "mlflow"')"
for pair in mlflow:"$APPS":backend-store-uri evalhub:evalhub:db-url; do
  IFS=: read -r feature ns uri_key <<<"$pair"
  record "$feature PostgreSQL current and ready" "$(read_json statefulset "$feature-postgresql" -n "$ns" |
    yes_no "$FRESH"' fresh and (.status.currentRevision // "") != "" and .status.currentRevision == .status.updateRevision')"
  record "$feature durable gp3 PostgreSQL PVC Bound" "$(read_json pvc "$feature-postgresql" -n "$ns" |
    yes_no '.status.phase == "Bound" and .spec.storageClassName == "gp3-csi"')"
  has_keys "$feature-db-credentials" "$ns" database-user database-password database-name "$uri_key" && R=pass || R="keys missing"
  record "$feature database Secret has its required keys" "$R"
done
record "MLflow artifact ObjectBucketClaim bound to its exact bucket" "$(read_json objectbucketclaim "$BUCKET" -n "$APPS" |
  yes_no --arg b "$BUCKET" '.status.phase == "Bound" and .spec.bucketName == $b')"
has_keys "$BUCKET" "$APPS" AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY && R=pass || R="keys missing"
record "MLflow artifact credentials provisioned by the claim" "$R"
record "MLflow artifact endpoint is the internal HTTPS service" "$(read_json configmap "$BUCKET" -n "$APPS" |
  yes_no --arg b "$BUCKET" '.data | .BUCKET_NAME == $b and .BUCKET_PORT == "443"
    and (.BUCKET_HOST // "" | test("\\.openshift-storage\\.svc(\\.cluster\\.local)?$"))')"
record "MLflow service CA bundle injected" "$(read_json configmap mlflow-service-ca -n "$APPS" | yes_no '(.data["service-ca.crt"] // "") != ""')"
MLFLOW=$(read_json mlflows.mlflow.opendatahub.io mlflow)
record "MLflow Available at its current generation" "$(yes_no '.metadata.generation as $g | $g != null
  and any(.status.conditions[]?; .type == "Available" and .status == "True")
  and ([.status.conditions[]? | select((.type == "MLflowOperatorReady" or .type == "Migration") and .status == "True"
       and .observedGeneration == $g) | .type] | unique | length) == 2' <<<"$MLFLOW")"
record "MLflow uses the PostgreSQL Secret and proxied claim artifacts" "$(yes_no --arg b "$BUCKET" '.spec
  | .backendStoreUriFrom == {name: "mlflow-db-credentials", key: "backend-store-uri"} and .serveArtifacts == true
  and .artifactsDestination == "s3://\($b)/artifacts" and (.defaultArtifactRoot // "mlflow-artifacts:/") == "mlflow-artifacts:/"' <<<"$MLFLOW")"
# The operator-owned server Deployment carries the custom resource's name (EvalHub with spec.mcp also owns evalhub-mcp).
owned_deployment() {
  read_json deployments -n "$3" | jq -c --arg kind "$1" --argjson cr "$2" "$FRESH"' [.items[]
    | select(.metadata.name == $cr.metadata.name and any(.metadata.ownerReferences[]?;
        .kind == $kind and .uid == $cr.metadata.uid and .controller == true))]
    | if length == 1 and (.[0] | fresh) then .[0] else {} end'
}
MLFLOW_DEPLOYMENT=$(owned_deployment MLflow "$MLFLOW" "$APPS")
record "MLflow has one current operator-owned Deployment" "$(yes_no 'length > 0' <<<"$MLFLOW_DEPLOYMENT")"
record "MLflow workload uses the backend Secret and verifies S3 TLS" "$(yes_no --arg b "$BUCKET" '[.spec.template.spec.containers[]?] as $c
  | ([$c[].env[]?] | map({key: .name, value: (.value // "")}) | from_entries) as $env
  | any($c[].env[]?; .valueFrom.secretKeyRef.name == "mlflow-db-credentials" and .valueFrom.secretKeyRef.key == "backend-store-uri")
  and ($env.AWS_CA_BUNDLE // "") != "" and $env.MLFLOW_S3_IGNORE_TLS == "false"
  and any($c[].envFrom[]?; .secretRef.name == $b)' <<<"$MLFLOW_DEPLOYMENT")"

# ── EvalHub ───────────────────────────────────────────────────────────────────
HUB=$(read_json evalhubs.trustyai.opendatahub.io evalhub -n evalhub)
record "Native EvalHub multi-tenant PostgreSQL ready" "$(yes_no '.status.ready == "True" and .status.phase == "Ready"
  and .spec.tenancy == "multi" and .spec.database.type == "postgresql" and .spec.database.secret == "evalhub-db-credentials"
  and ((.spec.database | keys) - ["type", "secret", "maxIdleConns", "maxOpenConns"] | length) == 0
  and (.spec.database.maxIdleConns // 5) == 5 and (.spec.database.maxOpenConns // 25) == 25' <<<"$HUB")"
HUB_DEPLOYMENT=$(owned_deployment EvalHub "$HUB" evalhub)
record "EvalHub has one current operator-owned Deployment" "$(yes_no 'length > 0' <<<"$HUB_DEPLOYMENT")"
SERVICE_ACCOUNT=$(jq -r '.spec.template.spec.serviceAccountName // ""' <<<"$HUB_DEPLOYMENT")
record "EvalHub tracks the ready MLflow address" "$(jq -n -e --argjson d "$HUB_DEPLOYMENT" --argjson m "$MLFLOW" \
  --argjson cm "$(read_json configmap evalhub-mlflow-connection -n evalhub)" '($m.status.address.url // "") as $u
  | $u != "" and $cm.data["tracking-uri"] == $u
  and any($d.spec.template.spec.containers[]?.env[]?; .name == "MLFLOW_TRACKING_URI"
      and .valueFrom.configMapKeyRef == {name: "evalhub-mlflow-connection", key: "tracking-uri"})' >/dev/null && echo yes || echo no)"
record "EvalHub database Secret mounted read-only" "$(yes_no '.spec.template.spec as $p
  | [$p.volumes[]? | select(.secret.secretName == "evalhub-db-credentials" and any(.secret.items[]?; .key == "db-url" and .path == "db-url")) | .name] as $v
  | any($p.containers[]?; .name == "evalhub" and any(.volumeMounts[]?; (.name | IN($v[])) and .mountPath == "/etc/evalhub/secrets" and .readOnly == true))' <<<"$HUB_DEPLOYMENT")"
record "EvalHub mounts the MLflow service CA and a short-lived projected token" "$(jq -n -e --argjson d "$HUB_DEPLOYMENT" \
  --argjson ca "$(read_json configmap evalhub-service-ca -n evalhub)" '$d.spec.template.spec as $p
  | ([$p.containers[]?.env[]?] | map({key: .name, value: (.value // "")}) | from_entries) as $env
  | [$p.containers[]?.volumeMounts[]?] as $mounts
  | $env.MLFLOW_CA_CERT_PATH == "/etc/evalhub/ca/service-ca.crt" and $env.MLFLOW_TOKEN_PATH == "/var/run/secrets/mlflow/token"
  and $env.MLFLOW_WORKSPACE == "evalhub" and (($env.MLFLOW_INSECURE_SKIP_VERIFY // "false") | ascii_downcase) != "true"
  and any($p.volumes[]?; .name == "service-ca" and .configMap.name == "evalhub-service-ca")
  and any($p.volumes[]?; .name == "mlflow-token" and any(.projected.sources[]?; .serviceAccountToken.path == "token"
      and (.serviceAccountToken.expirationSeconds // 0) > 0 and .serviceAccountToken.expirationSeconds <= 3600))
  and any($mounts[]; .name == "service-ca" and .mountPath == "/etc/evalhub/ca")
  and any($mounts[]; .name == "mlflow-token" and .mountPath == "/var/run/secrets/mlflow")
  and ($ca.data["service-ca.crt"] // "") != ""' >/dev/null && echo yes || echo no)"
TENANT_LABEL=evalhub.trustyai.opendatahub.io/tenant
tenant_only() {
  local ns
  read_json namespace "$TENANT" | jq -e --arg l "$TENANT_LABEL" '.metadata.labels | has($l)' >/dev/null || { echo no; return; }
  for ns in demo-sandbox evalhub; do
    read_json namespace "$ns" | jq -e --arg l "$TENANT_LABEL" '.metadata.labels // {} | has($l) | not' >/dev/null || { echo no; return; }
  done
  echo yes
}
check "Evaluated Models is the only tenant; AI Coding Sandbox and the server namespace are not" tenant_only yes
record "Tenant discovery and callback service CA reconciled" "$(jq -n -e --argjson d "$(read_json configmap evalhub-discovery -n "$TENANT")" \
  --argjson ca "$(read_json configmap evalhub-service-ca -n "$TENANT")" '($d.data["evalhub.url"] // "") != "" and ($ca.data["service-ca.crt"] // "") != ""' \
  >/dev/null && echo yes || echo no)"
JOB_ACCOUNT=evalhub-evalhub-job
oc --request-timeout=10s get serviceaccount "$JOB_ACCOUNT" -n "$TENANT" >/dev/null 2>&1 && R=pass || R=missing
record "Tenant evaluation job service account exists" "$R"

# allowed USER GROUPS-CSV API-GROUP RESOURCE VERB NAMESPACE: a SubjectAccessReview for the exact attributes.
allowed() {
  jq -n --arg u "$1" --arg g "$2" --arg api "$3" --arg r "$4" --arg v "$5" --arg ns "$6" '{apiVersion: "authorization.k8s.io/v1",
    kind: "SubjectAccessReview", spec: {user: $u, groups: ($g | split(",")),
    resourceAttributes: {group: $api, resource: $r, verb: $v, namespace: $ns}}}' |
    oc --request-timeout=10s create -f - -o json 2>/dev/null | jq -e '.status.allowed == true' >/dev/null
}
all_allowed() { local user=$1 groups=$2 api=$3 resource=$4 ns=$5 verb; shift 5; for verb in "$@"; do allowed "$user" "$groups" "$api" "$resource" "$verb" "$ns" || return 1; done; }
SA_GROUPS=system:serviceaccounts,system:serviceaccounts:evalhub,system:authenticated
[[ -n "$SERVICE_ACCOUNT" ]] && all_allowed "system:serviceaccount:evalhub:$SERVICE_ACCOUNT" "$SA_GROUPS" mlflow.kubeflow.org experiments evalhub create get update && R=pass || R=denied
record "EvalHub service authorized for MLflow in its workspace" "$R"
# Started before MLflow answered, EvalHub sends no workspace header until restarted (TROUBLESHOOTING).
oc --request-timeout=10s logs -n evalhub deploy/evalhub -c evalhub 2>/dev/null | grep 'MLflow workspace support probed' |
  tail -1 | grep -q '"workspaces_enabled":true' && R=pass || R="not probed; delete the EvalHub pod"
record "EvalHub sends MLflow workspace headers" "$R"
[[ -n "$SERVICE_ACCOUNT" ]] && allowed "system:serviceaccount:evalhub:$SERVICE_ACCOUNT" "$SA_GROUPS" batch jobs create "$TENANT" && R=pass || R=denied
record "EvalHub service authorized to create tenant jobs" "$R"
all_allowed "system:serviceaccount:$TENANT:$JOB_ACCOUNT" "system:serviceaccounts,system:serviceaccounts:$TENANT,system:authenticated" \
  mlflow.kubeflow.org experiments "$TENANT" create get update && R=pass || R=denied
record "Tenant job authorized for MLflow experiment results" "$R"
admin_access() {
  local g=rhods-admins,system:authenticated
  all_allowed ai-admin "$g" trustyai.opendatahub.io evaluations "$TENANT" create get && all_allowed ai-admin "$g" trustyai.opendatahub.io providers "$TENANT" get &&
    all_allowed ai-admin "$g" trustyai.opendatahub.io collections "$TENANT" get && all_allowed ai-admin "$g" mlflow.kubeflow.org experiments "$TENANT" create get &&
    echo yes || echo no
}
check "Configured ai-admin group grants evaluation and MLflow access" admin_access yes
allowed ai-developer rhoai-developers,system:authenticated trustyai.opendatahub.io evaluations create "$TENANT" && R="developer may create evaluations" || R=pass
record "Developers have no evaluation access (Evaluated Models is admin-only)" "$R"

# ── Authenticated EvalHub API (and the selected evaluation, when supplied) ────
WORK=$(mktemp -d)
trap 'while read -r p; do kill "$p" 2>/dev/null || true; done <"$WORK/pids"; rm -rf "$WORK"' EXIT  # forwards started in check subshells are not children: kill, never wait
: >"$WORK/pids"
oc --request-timeout=10s get configmap evalhub-service-ca -n "$TENANT" -o jsonpath='{.data.service-ca\.crt}' >"$WORK/ca.crt" 2>/dev/null || true
# Port-forward the Service behind an HTTPS address; sets HOST, PORT and BASE (the address path) for api().
connect() {
  local url=$1 service=$2 ns=$3 rest
  [[ "$url" =~ ^https://([^/:@]+)(:([0-9]+))?(/.*)?$ ]] || return 1
  HOST=${BASH_REMATCH[1]} BASE=${BASH_REMATCH[4]%/}
  oc port-forward -n "$ns" "service/$service" ":${BASH_REMATCH[3]:-443}" --address=127.0.0.1 >"$WORK/forward-$service.log" 2>&1 &
  echo "$!" >>"$WORK/pids"
  disown "$!" 2>/dev/null || true  # the EXIT trap kills it; no job-termination notice
  for _ in $(seq 1 100); do
    PORT=$(sed -n 's/^Forwarding from 127.0.0.1:\([0-9]*\) .*/\1/p' "$WORK/forward-$service.log" | head -1)
    [[ -n "$PORT" ]] && return 0
    sleep 0.2
  done
  return 1
}
# GET PATH: the JSON body on HTTP 200 (bounded at 2 MiB); the caller's token reaches curl only through --config on stdin.
api() {
  local status
  status=$(printf 'header = "Authorization: Bearer %s"\n' "$(oc whoami --show-token)" |
    curl --config - -s --max-time 30 --max-filesize 2097152 --cacert "$WORK/ca.crt" --resolve "$HOST:$PORT:127.0.0.1" \
      -H "X-Tenant: $TENANT" -H "X-MLFLOW-WORKSPACE: $TENANT" -o "$WORK/body" -w '%{http_code}' "https://$HOST:$PORT$BASE/$1" || echo 000)
  [[ "$status" == 200 ]] && cat "$WORK/body"
}
DISCOVERY_URL=$(oc --request-timeout=10s get configmap evalhub-discovery -n "$TENANT" -o jsonpath='{.data.evalhub\.url}' 2>/dev/null || true)
discovery() {
  connect "$DISCOVERY_URL" evalhub evalhub || { echo "port-forward unavailable"; return; }
  [[ $(api api/v1/health | jq -r '.status // ""') == healthy ]] || { echo "health not healthy"; return; }
  local kind
  # ProviderResourceList and CollectionResourceList both list items[] with a resource id.
  for kind in "providers?benchmarks=true" collections; do
    api "api/v1/evaluations/$kind" | jq -e '(.items | type) == "array" and (.items | length) > 0
      and all(.items[]; (.resource.id // "") != "")' >/dev/null || { echo "no ${kind%%\?*} discovered"; return; }
  done
  echo yes
}
check "Authenticated EvalHub health, providers and collections with tenant and native CA" discovery yes

if [[ -z "$JOB_ID" ]]; then
  record_warn "Completed real evaluation" "none supplied (--job-id, --mlflow-run-id); service readiness is not evaluation proof"
else
  connect "$DISCOVERY_URL" evalhub evalhub
  JOB=$(api "api/v1/evaluations/jobs/$(jq -rn --arg j "$JOB_ID" '$j | @uri')" || echo '{}')
  STATE=$(jq -r --arg j "$JOB_ID" --arg t "$TENANT" 'if .resource.tenant == $t and .resource.id == $j then .status.state // "" else "identity or tenant differs" end' <<<"$JOB")
  if [[ "$STATE" == pending || "$STATE" == running ]]; then
    record_warn "Completed real evaluation" "selected evaluation has not completed"
  else
    record "Selected evaluation completed with one benchmark, a model and metrics, referencing the run" "$(jq -r --arg r "$RUN_ID" '
      if .status.state != "completed" then "state \(.status.state)"
      elif (.results.benchmarks | length) != 1 or (.results.benchmarks[0].metrics // {} | length) == 0 or (.model.name // "") == "" then "no single benchmark with metrics"
      elif .results.benchmarks[0].mlflow_run_id != $r then "result does not reference the selected MLflow run"
      else "pass" end' <<<"$JOB")"
    # EvalHub 1.0.0 may report the experiments collection URL without an id; then the experiment name resolves it.
    EXPERIMENT_ID=$(jq -r '.results.mlflow_experiment_url // "" | capture("/experiments/(?<id>[0-9]+)").id // ""' <<<"$JOB")
    EXPERIMENT_NAME=$(jq -r '.experiment.name // ""' <<<"$JOB")
    connect "$(jq -r '.status.address.url // ""' <<<"$MLFLOW")" mlflow "$APPS"
    if [[ -z "$EXPERIMENT_ID" && -n "$EXPERIMENT_NAME" ]]; then
      EXPERIMENT_ID=$(api "api/2.0/mlflow/experiments/get-by-name?experiment_name=$(jq -rn --arg n "$EXPERIMENT_NAME" '$n | @uri')" |
        jq -r '.experiment.experiment_id // ""' || true)
    fi
    record "Exact MLflow run FINISHED with metrics in the evaluation experiment" "$(api "api/2.0/mlflow/runs/get?run_id=$RUN_ID" |
      jq -r --arg r "$RUN_ID" --arg e "$EXPERIMENT_ID" '.run as $run | if $e != "" and $run.info.run_id == $r and $run.info.experiment_id == $e
        and $run.info.status == "FINISHED" and ($run.data.metrics // [] | length) > 0 then "pass" else "run, experiment or metrics differ" end' || echo "run not readable")"
    # A run whose model calls all failed still completes, with every score 0; prove the job's own endpoint and Secret
    # reach the model now, and do not accept an all-zero run as evaluation proof.
    model_answers() {
      local url name secret
      url=$(jq -r '.model.url // ""' <<<"$JOB"); name=$(jq -r '.model.name // ""' <<<"$JOB"); secret=$(jq -r '.model.auth.secret_ref // ""' <<<"$JOB")
      [[ "$url" == https://* && -n "$name" && -n "$secret" ]] || { echo "job model endpoint, name or Secret missing"; return; }
      [[ "$url" == */v1 ]] || url="${url%/}/v1"
      oc --request-timeout=10s get secret "$secret" -n "$TENANT" -o jsonpath='{.data.api-key}' | base64 -d |
        awk '{ printf "header = \"Authorization: Bearer %s\"\n", $0 }' |
        curl --config - -sk --max-time 60 -o "$WORK/answer" -w '%{http_code}' -H 'Content-Type: application/json' \
          --data-binary "$(jq -cn --arg m "$name" '{model: $m, messages: [{role: "user", content: "Reply with OK."}], max_tokens: 16}')" \
          "$url/chat/completions" > "$WORK/answer.code" || true
      [[ $(cat "$WORK/answer.code") == 200 ]] && jq -e '(.choices[0].message.content // "") | length > 0' "$WORK/answer" >/dev/null &&
        echo yes || echo "HTTP $(cat "$WORK/answer.code") without an answer"
    }
    check "Evaluated model answers through the job's endpoint with its tenant Secret" model_answers yes
    if jq -e '[.results.benchmarks[].metrics[]] | all(. == 0)' <<<"$JOB" >/dev/null; then
      record_warn "Evaluation scores" "every metric is 0; confirm the model answered during the run before accepting it"
    fi
  fi
fi
echo "Scope: service/storage configuration, configured-group authorization and API discovery; persona sessions and dashboard checks are separate."
validation_summary
