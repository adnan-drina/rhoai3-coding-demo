#!/usr/bin/env bash
# Stage 010: bootstraps OpenShift GitOps, deploys the foundation components (ODF, RHOAI, observability, access) at one
# reviewed published revision, then the three script-deployed components (sandbox storage, console observability, the
# shared MLflow tracking service) and the demo group membership of the existing provider identities.
# --component deploys only one script-deployed component, at its own revision, after its read-only adoption preflight.
# Usage: stages/010-openshift-ai-platform-foundation/deploy.sh [--revision REF] [--component 010-sandbox-storage|010-console-observability|010-mlflow]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Shared fail-closed environment and cluster identity guard.
REPO_ROOT="$ROOT_DIR"
# shellcheck source=../../scripts/lib.sh
source "$ROOT_DIR/scripts/lib.sh"
load_env
check_oc_logged_in
# Use a reviewed published revision; never silently deploy old main content.
COMPONENT=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --revision) GIT_REPO_BRANCH="${2:?}"; shift 2 ;;
    --component) COMPONENT="${2:?}"; shift 2 ;;
    *) sed -n 's/^# Usage: //p' "$0" >&2; exit 1 ;;
  esac
done
require_env GIT_REPO_URL "repository URL containing the reviewed Stage 010 source"
assert_required_env
STAGE_APPS="$ROOT_DIR/scripts/stage-apps.sh"
# The reviewed, published commit; Applications are pinned to it even when the input was a branch.
selected_commit=$("$STAGE_APPS" select 010 --ref "${GIT_REPO_BRANCH:-HEAD}" --repo-url "$GIT_REPO_URL" \
  --extra gitops/bootstrap)

# ── 010-mlflow runtime: database credentials and readiness (Argo CD owns every workload and CR) ──────────────────
APPS=redhat-ods-applications
MLFLOW_MANAGED_BY=stage010-mlflow-setup
fail() { log_error "$*"; exit 1; }
read_json() { oc --request-timeout=10s get "$@" --ignore-not-found -o json; }
# wait_until SECONDS LABEL COMMAND...: poll every 5 s.
wait_until() {
  local deadline=$((SECONDS + $1)) label=$2; shift 2
  log_info "Waiting for $label"
  until "$@"; do (( SECONDS < deadline )) || fail "Timed out waiting for $label; inspect operator and Argo CD status"; sleep 5; done
}
# Read-only, before the first write. Retained storage must be the bound, exact objects; a database with neither
# storage nor workload is new, and its credentials may be generated once. Existing storage without its credential
# Secret is retained data whose credentials must be restored.
mlflow_preflight() {
  local pvc obc storage secret dashboard_fields dsc_fields field
  dashboard_fields=$("$STAGE_APPS" delegated 010 OdhDashboardConfig odh-dashboard-config "$APPS" --group opendatahub.io)
  dsc_fields=$("$STAGE_APPS" delegated 010 DataScienceCluster default-dsc --group datasciencecluster.opendatahub.io)
  for field in /spec/dashboardConfig/globalProjectPrompts /spec/globalMLflowNamespaces; do
    grep -qx "$field" <<<"$dashboard_fields" || fail "010-rhoai-platform has not delegated $field (global prompt configuration)"
  done
  grep -qx /spec/components/mlflowoperator <<<"$dsc_fields" || fail "010-rhoai-platform has not delegated /spec/components/mlflowoperator"
  read_json odhdashboardconfig odh-dashboard-config -n "$APPS" | jq -e '.spec.globalMLflowNamespaces // [] | . == [] or . == ["ai-curated-prompts"]' >/dev/null ||
    fail "Foreign global prompt configuration requires a reviewed merge before deployment"
  read_json argocd openshift-gitops -n openshift-gitops | jq -e '.spec.extraConfig["resource.customizations.health.mlflow.opendatahub.io_MLflow"] // ""
    | . as $h | all("Available", "MLflowOperatorReady", "Migration", "observedGeneration"; . as $w | $h | contains($w))' >/dev/null ||
    fail "Install the reviewed native MLflow health gate (gitops/bootstrap) first"
  pvc=$(read_json pvc mlflow-postgresql -n "$APPS")
  [[ -z "$pvc" ]] || jq -e '.status.phase == "Bound"' <<<"$pvc" >/dev/null || fail "Retained MLflow PVC is not Bound"
  obc=$(read_json objectbucketclaim rhoai-mlflow-artifacts -n "$APPS")
  [[ -z "$obc" ]] || jq -e '.status.phase == "Bound" and .spec.bucketName == "rhoai-mlflow-artifacts"' <<<"$obc" >/dev/null || fail "Retained artifact bucket differs"
  storage=$(oc --request-timeout=10s get pvc,statefulset mlflow-postgresql -n "$APPS" --ignore-not-found -o name)
  secret=$(oc --request-timeout=10s get secret mlflow-db-credentials -n "$APPS" --ignore-not-found -o name)  # metadata only
  [[ -n "$secret" || -z "$storage" ]] || fail "Existing MLflow PostgreSQL lacks its credentials; restore them instead of generating a password"
}
# After the Application: reuse a valid unowned credential Secret, or generate one for a fresh database. The password
# lives in memory and reaches jq through its environment and oc through stdin; it is never printed or passed as an
# argument. Private same-namespace database transport is plaintext (demo boundary).
mlflow_runtime() {
  local name=mlflow-db-credentials uri_jq
  uri_jq='def uri($ns; $u; $p; $d): "postgresql://\($u | @uri):\($p | @uri)@mlflow-postgresql.\($ns).svc.cluster.local:5432/\($d | @uri)?sslmode=disable";'
  namespace_active() { [[ $(oc --request-timeout=10s get namespace "$APPS" -o jsonpath='{.status.phase}' 2>/dev/null) == Active ]]; }
  wait_until 300 "namespace $APPS" namespace_active
  if [[ -n "$(oc --request-timeout=10s get secret "$name" -n "$APPS" --ignore-not-found -o name)" ]]; then
    oc --request-timeout=10s get secret "$name" -n "$APPS" -o json | jq -e --arg ns "$APPS" "$uri_jq"'
      .metadata as $m | (.data | map_values(@base64d)) as $d
      | (($m.ownerReferences // [] | length) == 0 and $m.deletionTimestamp == null and ($m.annotations["argocd.argoproj.io/tracking-id"] // "") == "")
      and ($d["database-password"] // "") != "" and ($d["database-user"] // "" | test("^[A-Za-z_][A-Za-z0-9_]*$"))
      and ($d["database-name"] // "" | test("^[A-Za-z_][A-Za-z0-9_]*$"))
      and $d["backend-store-uri"] == uri($ns; $d["database-user"]; $d["database-password"]; $d["database-name"])' >/dev/null ||
      fail "$name is foreign, or its user, database or URI does not match the demo endpoint; no values changed"
    log_info "Reusing MLflow database credentials"
  else
    [[ -z "$(oc --request-timeout=10s get pvc,statefulset mlflow-postgresql -n "$APPS" --ignore-not-found -o name)" ]] ||
      [[ -n "${MLFLOW_FRESH:-}" ]] || fail "Existing MLflow PostgreSQL lacks its Secret; restore the original credentials"
    PASSWORD=$(openssl rand -hex 24) jq -n --arg ns "$APPS" --arg name "$name" --arg m "$MLFLOW_MANAGED_BY" "$uri_jq"'
      {apiVersion: "v1", kind: "Secret", type: "Opaque",
       metadata: {name: $name, namespace: $ns, labels: {"app.kubernetes.io/part-of": "rhoai-platform", "app.kubernetes.io/name": $name,
         "app.kubernetes.io/component": "configuration", "app.kubernetes.io/managed-by": $m}},
       stringData: {"database-user": "mlflow", "database-password": $ENV.PASSWORD, "database-name": "mlflow",
         "backend-store-uri": uri($ns; "mlflow"; $ENV.PASSWORD; "mlflow")}}' | oc --request-timeout=10s create -f - >/dev/null ||
      fail "Could not create $name"
    log_info "MLflow database credentials created"
  fi
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
}

# One script-deployed component: read-only adoption preflight, apply, sync (an unchanged render gets no automatic
# sync operation), the component's runtime step, wait, then that component's validation (console readiness follows
# Argo CD health by minutes).
deploy_component() {
  local app="$1" deadline
  "$STAGE_APPS" preflight 010 --repo-url "$GIT_REPO_URL" --app "$app"
  if [[ "$app" == 010-mlflow ]]; then
    mlflow_preflight
    [[ -n "$(oc --request-timeout=10s get pvc,statefulset mlflow-postgresql -n "$APPS" --ignore-not-found -o name)" ]] || MLFLOW_FRESH=1
  fi
  "$STAGE_APPS" apply 010 --app "$app" --revision "$selected_commit" --repo-url "$GIT_REPO_URL"
  "$STAGE_APPS" sync 010 --app "$app"
  # MLflow needs its database credentials before it can become healthy.
  [[ "$app" != 010-mlflow ]] || mlflow_runtime
  "$STAGE_APPS" wait 010 --app "$app" --revision "$selected_commit" --repo-url "$GIT_REPO_URL" --timeout 1200
  deadline=$((SECONDS + 600))
  until "$SCRIPT_DIR/validate.sh" --component "$app" >/dev/null 2>&1; do
    if (( SECONDS >= deadline )); then "$SCRIPT_DIR/validate.sh" --component "$app"; return 1; fi
    sleep 10
  done
  log_success "$app deployed and validated at ${selected_commit:0:12}"
}
case "$COMPONENT" in
  "") ;;
  010-sandbox-storage|010-console-observability|010-mlflow) deploy_component "$COMPONENT"; exit 0 ;;
  *) echo "Unknown script-deployed component $COMPONENT" >&2; exit 1 ;;
esac
check_operator_policy "$ROOT_DIR/gitops/stages/010-openshift-ai-platform-foundation"
check_operator_policy "$ROOT_DIR/gitops/bootstrap/overlays/operator"
# Read-only preflight runs before the first bootstrap/Application write.
# The model registry namespace belongs to Stage 030; never let a foundation component take it back.
registry_ns=$(oc --request-timeout=10s get namespace rhoai-model-registries --ignore-not-found -o json)
if [[ -n "$registry_ns" ]] && ! jq -e \
    '.metadata.annotations["argocd.argoproj.io/tracking-id"] // "" | startswith("030-private-model-serving:")' \
    <<<"$registry_ns" >/dev/null; then
  echo "ERROR: Registry namespace exists but is not owned by Stage 030" >&2
  exit 1
fi

# Fail fast if the nodes are too small for the demo stack, before any changes.
require_node_sizing

# ── Portable wait helper (no GNU `timeout` dependency; macOS lacks it) ─────────
# wait_for <timeout-seconds> <label> <command...>
# Polls the command every 10s until it exits 0 or the deadline passes.
wait_for() {
  local timeout_s="$1" label="$2"; shift 2
  local deadline=$(( SECONDS + timeout_s ))
  until "$@"; do
    if (( SECONDS >= deadline )); then
      echo ""
      echo "ERROR: timed out after ${timeout_s}s waiting for ${label}." >&2
      return 1
    fi
    sleep 10
    echo -n "."
  done
  echo ""
}

argocd_available() {
  oc get argocd openshift-gitops -n openshift-gitops \
    -o jsonpath='{.status.phase}' --insecure-skip-tls-verify=true 2>/dev/null \
    | grep -q Available
}

# ── Step 1: Bootstrap OpenShift GitOps operator ───────────────────────────────
echo ""
echo "── Step 1: Installing OpenShift GitOps operator ──"
# Apply the operator overlay (base Subscription + baseline-pinned channel).
# Never apply bootstrap/base directly: its channel is a placeholder.
oc apply -k "$ROOT_DIR/gitops/bootstrap/overlays/operator" --insecure-skip-tls-verify=true

echo "   Waiting for openshift-gitops-operator CSV to reach Succeeded …"
check_operator_policy "$ROOT_DIR/gitops/bootstrap/overlays/operator" --wait 900

echo "✓ OpenShift GitOps operator ready"

# ── Step 2: Wait for default ArgoCD instance to be Available ─────────────────
echo ""
echo "── Step 2: Waiting for ArgoCD instance to become available ──"
wait_for 300 "ArgoCD instance Available" argocd_available || exit 1

echo "✓ ArgoCD instance available"

# ── Step 3: Apply bootstrap overlay (resource tracking + AppProject) ──────────
echo ""
echo "── Step 3: Configuring ArgoCD and creating AppProject rhoai-demo ──"
oc apply -k "$ROOT_DIR/gitops/bootstrap/overlays/demo" --insecure-skip-tls-verify=true
echo "✓ ArgoCD configured (annotation resource tracking)"
echo "✓ AppProject rhoai-demo created"

# ── Step 4: Apply the Stage 010 component Applications at the reviewed revision ──
echo ""
echo "── Step 4: Applying Stage 010 component Argo CD Applications ──"
echo "  Argo CD syncs ODF and RHOAI; this takes 10–20 minutes."
"$STAGE_APPS" deploy 010 --revision "$selected_commit" --repo-url "$GIT_REPO_URL"
check_operator_policy "$ROOT_DIR/gitops/stages/010-openshift-ai-platform-foundation" --wait 1800

deploy_component 010-sandbox-storage
deploy_component 010-console-observability
deploy_component 010-mlflow

# ── Step 5: Persona accounts and demo group membership ──────────────────────
# The personas sign in through the environment's Keycloak realm `sso` (the OpenShift `rhbk` provider). A fresh
# environment ships only `admin` there, so a missing persona account is created with its .env password
# (AI_ADMIN_PASSWORD, AI_DEVELOPER_PASSWORD). An existing account, its password, OAuth and the realm settings are
# never changed. Uses the Keycloak Admin REST API with the operator's initial admin credential.
keycloak_admin_token() {
  oc get secret keycloak-initial-admin -n keycloak -o json \
    | jq -j '"grant_type=password&client_id=admin-cli&username=\(.data.username | @base64d | @uri)"
             + "&password=\(.data.password | @base64d | @uri)"' \
    | curl -sSk --fail --data-binary @- "https://${KEYCLOAK_HOST}/realms/master/protocol/openid-connect/token" \
    | jq -r '.access_token'
}
ensure_persona_account() {
  local user="$1" first="$2" last="$3" password_var="$4" token count
  token=$(keycloak_admin_token)
  count=$(curl -sSk --fail --config <(printf 'header = "Authorization: Bearer %s"\n' "$token") \
    "https://${KEYCLOAK_HOST}/admin/realms/sso/users?username=${user}&exact=true" | jq 'length')
  if [[ "$count" != 0 ]]; then
    log_success "Keycloak account $user exists in realm sso (unchanged)"
    return
  fi
  [[ -n "${!password_var:-}" ]] || { log_error "Set $password_var in .env to create the $user account"; return 1; }
  PERSONA_PASSWORD="${!password_var}" jq -n --arg user "$user" --arg first "$first" --arg last "$last" \
    '{username: $user, enabled: true, emailVerified: true, email: "\($user)@rhoai3-demo.local",
      firstName: $first, lastName: $last,
      credentials: [{type: "password", value: $ENV.PERSONA_PASSWORD, temporary: false}]}' \
    | curl -sSk --fail -o /dev/null --config <(printf 'header = "Authorization: Bearer %s"\n' "$token") \
        -H 'Content-Type: application/json' --data-binary @- "https://${KEYCLOAK_HOST}/admin/realms/sso/users"
  log_success "Keycloak account $user created in realm sso"
}
# Existing provider identities join the demo groups (rhods-admins is operator-owned, so membership is not in GitOps).
if [[ -n "${RHOAI_ADMIN_USER:-}" && -n "${RHOAI_DEVELOPER_USER:-}" ]]; then
  KEYCLOAK_HOST=$(oc get route keycloak -n keycloak -o jsonpath='{.spec.host}')
  ensure_persona_account "$RHOAI_ADMIN_USER" AI Admin AI_ADMIN_PASSWORD
  ensure_persona_account "$RHOAI_DEVELOPER_USER" AI Developer AI_DEVELOPER_PASSWORD
  for persona in "$RHOAI_ADMIN_USER" "$RHOAI_DEVELOPER_USER"; do
    oc get user "$persona" >/dev/null 2>&1 || log_warn "$persona has not completed a first provider login yet"
  done
  oc adm groups add-users rhods-admins "$RHOAI_ADMIN_USER"
  oc adm groups add-users rhoai-developers "$RHOAI_DEVELOPER_USER"
else
  log_warn "RHOAI_ADMIN_USER/RHOAI_DEVELOPER_USER not set: demo group membership not assigned"
fi

# ── Step 6: Report Argo CD console URL ───────────────────────────────────────
ARGOCD_URL=$(oc get route openshift-gitops-server -n openshift-gitops \
  -o jsonpath='{.spec.host}' 2>/dev/null || true)
if [[ -n "$ARGOCD_URL" ]]; then
  echo ""
  echo "  Argo CD console: https://$ARGOCD_URL"
  echo "  Applications:    https://$ARGOCD_URL/applications?labels=demo.rhoai.io%2Fstage%3D010"
fi

echo ""
echo "Run ./validate.sh to confirm all components are healthy."
