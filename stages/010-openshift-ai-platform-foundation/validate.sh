#!/usr/bin/env bash
# validate.sh — Stage 010: RHOAI Base Platform
# Proves all foundation components are healthy and the RHOAI dashboard is reachable.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

PASS=0
FAIL=0
WARN=0

# Shared fail-closed environment and cluster identity guard.
REPO_ROOT="$ROOT_DIR"
# shellcheck source=../../scripts/shared/lib.sh
source "$ROOT_DIR/scripts/shared/lib.sh"
load_env
check_oc_logged_in


check() {
  local label="$1"
  local result="$2"
  if [[ "$result" == "pass" ]]; then
    echo "✓ $label"
    (( PASS++ )) || true
  else
    echo "✗ $label  ($result)"
    (( FAIL++ )) || true
  fi
}

# A missing or expired persona session is not a platform fault: warn and say how to refresh it.
warn() {
  echo "! $1  ($2)"
  (( WARN++ )) || true
}

# Dex emits OpenShift Group membership; direct Kubernetes role bindings do not
# grant Argo CD permissions. Verify the operator-reconciled policy, not just CR intent.
GITOPS_ACCESS=$(oc --request-timeout=10s get group rhoai-gitops-admins -o json 2>/dev/null |
  jq -r 'if (.users // []) | index("admin") then "pass" else "admin membership missing" end' || echo "group inspection failed")
check "GitOps SSO administrator group" "$GITOPS_ACCESS"
GITOPS_POLICY=$(oc --request-timeout=10s get configmap argocd-rbac-cm -n openshift-gitops -o json 2>/dev/null |
  jq -r '.data // {} | if ((."policy.csv" // "") | split("\n") | map(gsub("\\s"; "")) | index("g,rhoai-gitops-admins,role:admin"))
      and ((.scopes // "") | contains("groups")) and ((."policy.default" // "") | test("^\\s*$"))
    then "pass" else "mapping missing or broad default policy" end' || echo "policy inspection failed")
check "GitOps reconciled group policy with empty default" "$GITOPS_POLICY"

csv_phase_from_subscription() {
  local namespace="$1" subscription="$2"
  local installed_csv
  installed_csv=$(oc get subscription "$subscription" -n "$namespace" \
    -o jsonpath='{.status.installedCSV}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
  if [[ -z "$installed_csv" ]]; then
    echo ""
    return
  fi
  oc get csv "$installed_csv" -n "$namespace" \
    -o jsonpath='{.status.phase}' --insecure-skip-tls-verify=true 2>/dev/null || echo ""
}

native_ready() {
  local kind="$1" name="$2" require_generation="$3"
  oc --request-timeout="${RHOAI_OC_REQUEST_TIMEOUT:-10s}" get "$kind" "$name" -o json 2>/dev/null |
    jq -r --arg gen "$require_generation" '(.status // {}) as $s
      | if $s.phase == "Ready" and any($s.conditions[]?; .type == "Ready" and .status == "True")
          and ($gen == "false" or ($s.observedGeneration // 0) >= (.metadata.generation // 1))
        then "pass" else "native Ready/current-generation contract not satisfied" end' ||
    echo "native status unavailable"
}

# ── 1. OpenShift GitOps operator ─────────────────────────────────────────────
GITOPS_CSV=$(csv_phase_from_subscription openshift-operators openshift-gitops-operator)
[[ "$GITOPS_CSV" == "Succeeded" ]] && R="pass" || R="phase=${GITOPS_CSV:-not found}"
check "OpenShift GitOps operator CSV Succeeded" "$R"

# ── 2. ArgoCD instance Available ─────────────────────────────────────────────
ARGOCD_PHASE=$(oc get argocd openshift-gitops -n openshift-gitops \
  -o jsonpath='{.status.phase}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
[[ "$ARGOCD_PHASE" == "Available" ]] && R="pass" || R="phase=${ARGOCD_PHASE:-not found}"
check "ArgoCD instance Available" "$R"

# ── 3. Component Applications Synced + Healthy at one revision ──────────────
STAGE_APPS="$ROOT_DIR/scripts/shared/stage_apps.py"
revision_args=()
[[ -n "${RHOAI_STAGE010_EXPECTED_REVISION:-}" ]] && revision_args=(--revision "$RHOAI_STAGE010_EXPECTED_REVISION")
if APP_STATUS=$(python3 "$STAGE_APPS" status 010 ${revision_args[@]+"${revision_args[@]}"} 2>&1); then R="pass"
else R="$(printf '%s\n' "$APP_STATUS" | grep -E '^(  - |ERROR)' | head -3 | tr '\n' ' ')"; fi
check "Stage 010 component Applications (all seven) Synced/Healthy at one revision" "$R"

# ── 4. ODF operator ───────────────────────────────────────────────────────────
ODF_CSV=$(csv_phase_from_subscription openshift-storage odf-operator)
[[ "$ODF_CSV" == "Succeeded" ]] && R="pass" || R="phase=${ODF_CSV:-not found}"
check "ODF operator CSV Succeeded" "$R"

# ── 5. NooBaa Ready ───────────────────────────────────────────────────────────
NOOBAA_PHASE=$(oc get noobaa noobaa -n openshift-storage \
  -o jsonpath='{.status.phase}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
[[ "$NOOBAA_PHASE" == "Ready" ]] && R="pass" || R="phase=${NOOBAA_PHASE:-not found}"
check "NooBaa phase Ready" "$R"

# ── 6. RHOAI operator ────────────────────────────────────────────────────────
RHOAI_CSV=$(csv_phase_from_subscription redhat-ods-operator rhods-operator)
[[ "$RHOAI_CSV" == "Succeeded" ]] && R="pass" || R="phase=${RHOAI_CSV:-not found}"
check "RHOAI operator CSV Succeeded" "$R"

# ── 7. RHOAI observability prerequisite operators ────────────────────────────
python3 "$ROOT_DIR/scripts/platform/check-operator-policy.py" "$ROOT_DIR/gitops/stages/010-openshift-ai-platform-foundation" --verify

COO_CSV=$(csv_phase_from_subscription openshift-cluster-observability-operator cluster-observability-operator)
[[ "$COO_CSV" == "Succeeded" ]] && R="pass" || R="phase=${COO_CSV:-not found}"
check "Cluster Observability Operator CSV Succeeded" "$R"

OTEL_CSV=$(csv_phase_from_subscription openshift-opentelemetry-operator opentelemetry-product)
[[ "$OTEL_CSV" == "Succeeded" ]] && R="pass" || R="phase=${OTEL_CSV:-not found}"
check "Red Hat build of OpenTelemetry Operator CSV Succeeded" "$R"

TEMPO_CSV=$(csv_phase_from_subscription openshift-tempo-operator tempo-product)
[[ "$TEMPO_CSV" == "Succeeded" ]] && R="pass" || R="phase=${TEMPO_CSV:-not found}"
check "Tempo Operator CSV Succeeded" "$R"

# ── 8. DSCInitialization Ready ────────────────────────────────────────────────
check "DSCInitialization phase and condition Ready" "$(native_ready dscinitialization default-dsci false)"

# ── 9. RHOAI observability stack and dashboard flag ──────────────────────────
OBS_MGMT=$(oc get dscinitialization default-dsci \
  -o jsonpath='{.spec.monitoring.managementState}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
OBS_NS=$(oc get dscinitialization default-dsci \
  -o jsonpath='{.spec.monitoring.namespace}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
[[ "$OBS_MGMT" == "Managed" && "$OBS_NS" == "redhat-ods-monitoring" ]] \
  && R="pass" || R="managementState=${OBS_MGMT:-missing} namespace=${OBS_NS:-missing}"
check "RHOAI observability stack configured in DSCInitialization" "$R"

OBS_METRICS_REPLICAS=$(oc get dscinitialization default-dsci \
  -o jsonpath='{.spec.monitoring.metrics.replicas}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
OBS_METRICS_SIZE=$(oc get dscinitialization default-dsci \
  -o jsonpath='{.spec.monitoring.metrics.storage.size}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
OBS_TRACES_BACKEND=$(oc get dscinitialization default-dsci \
  -o jsonpath='{.spec.monitoring.traces.storage.backend}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
OBS_TRACES_RATIO=$(oc get dscinitialization default-dsci \
  -o jsonpath='{.spec.monitoring.traces.sampleRatio}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
[[ "$OBS_METRICS_REPLICAS" == "1" && "$OBS_METRICS_SIZE" == "5Gi" ]] \
  && R="pass" || R="metricsReplicas=${OBS_METRICS_REPLICAS:-missing} metricsSize=${OBS_METRICS_SIZE:-missing}"
check "RHOAI observability metrics configured" "$R"
[[ "$OBS_TRACES_BACKEND" == "pv" && "$OBS_TRACES_RATIO" == "0.1" ]] \
  && R="pass" || R="tracesBackend=${OBS_TRACES_BACKEND:-missing} sampleRatio=${OBS_TRACES_RATIO:-missing}"
check "RHOAI observability traces configured" "$R"

OBS_DASHBOARD=$(oc get odhdashboardconfig odh-dashboard-config -n redhat-ods-applications \
  -o jsonpath='{.spec.dashboardConfig.observabilityDashboard}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
[[ "$OBS_DASHBOARD" == "true" ]] && R="pass" || R="observabilityDashboard=${OBS_DASHBOARD:-missing}"
check "RHOAI Observability dashboard menu enabled" "$R"

# Native observability functional acceptance replaces legacy workaround-presence checks.
validate_persona() {
  local label="$1" kubeconfig="$2" expected_user="$3" actual_user server permission guarded_server
  local refresh="run scripts/platform/refresh-persona-logins.sh"
  if [[ -z "$kubeconfig" || ! -f "$kubeconfig" ]]; then
    warn "$label real authenticated session" "no persona session; $refresh"
    return
  fi
  server=$(oc --kubeconfig="$kubeconfig" --request-timeout="${RHOAI_OC_REQUEST_TIMEOUT:-10s}" whoami --show-server 2>/dev/null || true)
  actual_user=$(oc --kubeconfig="$kubeconfig" --request-timeout="${RHOAI_OC_REQUEST_TIMEOUT:-10s}" whoami 2>/dev/null || true)
  guarded_server=$(oc --request-timeout="${RHOAI_OC_REQUEST_TIMEOUT:-10s}" whoami --show-server)
  if [[ "$server" == "$guarded_server" && -z "$actual_user" ]]; then
    warn "$label real authenticated session" "session expired; $refresh"
    return
  fi
  if [[ "$server" != "$guarded_server" || "$actual_user" != "$expected_user" ]]; then
    check "$label real authenticated session" "identity or cluster mismatch"
    return
  fi
  permission=$(oc --kubeconfig="$kubeconfig" --request-timeout="${RHOAI_OC_REQUEST_TIMEOUT:-10s}" auth can-i update deployments.apps -n demo-sandbox 2>/dev/null || true)
  [[ "$permission" == yes ]] && R="pass" || R="project permission denied"
  check "$label real session project access" "$R"
}
validate_persona administrator "${RHOAI_ADMIN_KUBECONFIG:-}" "${RHOAI_ADMIN_USER:-}"
validate_persona developer "${RHOAI_DEVELOPER_KUBECONFIG:-}" "${RHOAI_DEVELOPER_USER:-}"

# ── 10. DataScienceCluster Ready ──────────────────────────────────────────────
check "DataScienceCluster Ready at current generation" "$(native_ready datasciencecluster default-dsc true)"

# ── 12. RHOAI Dashboard route responds ───────────────────────────────────────
DASHBOARD_HOST=$(oc get route rhods-dashboard -n redhat-ods-applications \
  -o jsonpath='{.spec.host}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
if [[ -n "$DASHBOARD_HOST" ]]; then
  HTTP_CODE=$(curl -sk -o /dev/null -w "%{http_code}" "https://$DASHBOARD_HOST" 2>/dev/null || echo "000")
  [[ "$HTTP_CODE" =~ ^(200|301|302|303)$ ]] && R="pass" || R="http=$HTTP_CODE"
  check "RHOAI Dashboard route reachable (https://$DASHBOARD_HOST)" "$R"
else
  check "RHOAI Dashboard route reachable" "route not found"
fi

# Native Auth and foundation component ownership.
check "Native Auth Ready at current generation" "$(native_ready auth.services.platform.opendatahub.io auth true)"
# Later stages enable components 010-rhoai-platform delegates through ignoreDifferences.
# Dashboard and workbenches are Managed; the listed components stay Removed unless Stage 010 delegated the field.
delegated=$(python3 "$ROOT_DIR/scripts/shared/stage_apps.py" delegated 010 DataScienceCluster default-dsc \
  --group datasciencecluster.opendatahub.io 2>/dev/null | sed -n 's#^/spec/components/##p' | jq -R . | jq -s -c . || echo '[]')
COMPONENT_CHECK=$(oc --request-timeout=15s get datasciencecluster default-dsc -o json 2>/dev/null |
  jq -r --argjson delegated "$delegated" '.spec.components as $c
    | ["ogx", "aigateway", "mcplifecycleoperator", "sparkoperator", "trainer"] - $delegated | . as $removed
    | if all(("dashboard", "workbenches"); $c[.].managementState == "Managed")
        and all($removed[]; $c[.].managementState == "Removed")
      then "pass" else "component ownership mismatch" end' || echo "component inspection failed")
check "Foundation component ownership" "$COMPONENT_CHECK"

# Existing provider authentication and explicit group membership.
IDP=$(oc get oauth cluster -o jsonpath='{.spec.identityProviders[*].name}' 2>/dev/null || true)
[[ -n "$IDP" ]] && R="pass" || R="no identity provider"
check "Existing identity provider configured" "$R"
: "${RHOAI_ADMIN_USER:?Set existing RHOAI_ADMIN_USER for access validation}"
: "${RHOAI_DEVELOPER_USER:?Set existing RHOAI_DEVELOPER_USER for access validation}"
for mapping in "rhods-admins:$RHOAI_ADMIN_USER" "rhoai-developers:$RHOAI_DEVELOPER_USER"; do
  group="${mapping%%:*}"; user="${mapping#*:}"
  members=$(oc get group "$group" -o jsonpath='{.users[*]}' 2>/dev/null || true)
  if printf '%s\n' "$members" | tr ' ' '\n' | grep -Fxq "$user"; then R="pass"; else R="membership missing"; fi
  check "Configured persona in $group" "$R"
done

# ── 15. demo-sandbox data science project exists ─────────────────────────────
DS_LABEL=$(oc get namespace demo-sandbox \
  -o jsonpath='{.metadata.labels.opendatahub\.io/dashboard}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
[[ "$DS_LABEL" == "true" ]] && R="pass" || R="dashboard-label=${DS_LABEL:-missing}"
check "demo-sandbox data science project present" "$R"

# ── 16. environment Keycloak ready (prerequisite, not owned by GitOps) ───────
KC_READY=$(oc get keycloak keycloak -n keycloak \
  -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
[[ "$KC_READY" == "True" ]] && R="pass" || R="ready=${KC_READY:-not found}"
check "Environment Keycloak keycloak/keycloak Ready" "$R"

# ── 17. OpenShift login uses the environment Keycloak (rhbk provider) ────────
IDP_TYPE=$(oc get oauth cluster -o jsonpath='{.spec.identityProviders[?(@.name=="rhbk")].type}' \
  --insecure-skip-tls-verify=true 2>/dev/null || echo "")
[[ "$IDP_TYPE" == "OpenID" ]] && R="pass" || R="identity-provider=${IDP_TYPE:-missing}"
check "OpenShift OAuth rhbk identity provider present" "$R"

# ── 18. RHOAI admins can manage demo-sandbox ─────────────────────────────────
ADMIN_RB=$(oc get rolebinding rhods-admins-admin -n demo-sandbox \
  -o jsonpath='{.roleRef.name}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
[[ "$ADMIN_RB" == "admin" ]] && R="pass" || R="rolebinding=${ADMIN_RB:-missing}"
check "rhods-admins admin on demo-sandbox" "$R"

if "$SCRIPT_DIR/validate-sandbox-storage.sh"; then
  check "Models/Workbench S3 connection configuration" pass
else
  check "Models/Workbench S3 connection configuration" "bucket/connection configuration not ready"
fi

if "$SCRIPT_DIR/validate-console-observability.sh"; then
  check "Native Perses console integration" pass
else
  check "Native Perses console integration" "console component not ready"
fi
if "$SCRIPT_DIR/validate-foundation-services.sh"; then
  check "Native foundation services" pass
else
  check "Native foundation services" "functional checks failed"
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "Results: ${PASS} passed, ${WARN} warnings, ${FAIL} failed"
(( FAIL > 0 )) && exit 1
(( WARN > 0 )) && exit 2
exit 0
