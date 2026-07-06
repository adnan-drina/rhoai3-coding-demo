#!/usr/bin/env bash
# validate.sh — Stage 110: RHOAI Base Platform
# Proves all foundation components are healthy and the RHOAI dashboard is reachable.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

PASS=0
FAIL=0

# ── Load local environment ────────────────────────────────────────────────────
if [[ -f "$ROOT_DIR/.env" ]]; then
  # set -a so values like KUBECONFIG are exported to oc child processes,
  # not just set as local shell variables.
  set -a
  # shellcheck source=/dev/null
  source "$ROOT_DIR/.env"
  set +a
fi

# ── OpenShift safety guard ────────────────────────────────────────────────────
if [[ -z "${RHOAI_EXPECTED_API_SERVER:-}" ]]; then
  echo "ERROR: RHOAI_EXPECTED_API_SERVER is not set. Set it in .env." >&2
  exit 1
fi
ACTUAL_SERVER=$(oc whoami --show-server 2>/dev/null || true)
if [[ "$ACTUAL_SERVER" != *"$RHOAI_EXPECTED_API_SERVER"* ]]; then
  echo "ERROR: Active cluster ($ACTUAL_SERVER) does not match guard." >&2
  exit 1
fi

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

# ── 1. OpenShift GitOps operator ─────────────────────────────────────────────
GITOPS_CSV=$(csv_phase_from_subscription openshift-operators openshift-gitops-operator)
[[ "$GITOPS_CSV" == "Succeeded" ]] && R="pass" || R="phase=${GITOPS_CSV:-not found}"
check "OpenShift GitOps operator CSV Succeeded" "$R"

# ── 2. ArgoCD instance Available ─────────────────────────────────────────────
ARGOCD_PHASE=$(oc get argocd openshift-gitops -n openshift-gitops \
  -o jsonpath='{.status.phase}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
[[ "$ARGOCD_PHASE" == "Available" ]] && R="pass" || R="phase=${ARGOCD_PHASE:-not found}"
check "ArgoCD instance Available" "$R"

# ── 3. ArgoCD Application Synced + Healthy ────────────────────────────────────
APP_SYNC=$(oc get applications.argoproj.io 010-openshift-ai-platform-foundation -n openshift-gitops \
  -o jsonpath='{.status.sync.status}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
APP_HEALTH=$(oc get applications.argoproj.io 010-openshift-ai-platform-foundation -n openshift-gitops \
  -o jsonpath='{.status.health.status}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
[[ "$APP_SYNC" == "Synced" ]] && R="pass" || R="sync=${APP_SYNC:-not found}"
check "Argo CD Application Synced" "$R"
[[ "$APP_HEALTH" == "Healthy" ]] && R="pass" || R="health=${APP_HEALTH:-not found}"
check "Argo CD Application Healthy" "$R"

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
EXPECTED_COO_CSV="cluster-observability-operator.v1.4.0"
COO_INSTALLED_CSV=$(oc get subscription cluster-observability-operator -n openshift-cluster-observability-operator \
  -o jsonpath='{.status.installedCSV}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
[[ "$COO_INSTALLED_CSV" == "$EXPECTED_COO_CSV" ]] && R="pass" || R="installedCSV=${COO_INSTALLED_CSV:-not found} expected=${EXPECTED_COO_CSV}"
check "Cluster Observability Operator CSV matches RHOAI 3.4 compatibility policy" "$R"

COO_CSV=$(csv_phase_from_subscription openshift-cluster-observability-operator cluster-observability-operator)
[[ "$COO_CSV" == "Succeeded" ]] && R="pass" || R="phase=${COO_CSV:-not found}"
check "Cluster Observability Operator CSV Succeeded" "$R"

COO_MEMORY_LIMIT=$(oc get subscription cluster-observability-operator -n openshift-cluster-observability-operator \
  -o jsonpath='{.spec.config.resources.limits.memory}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
[[ "$COO_MEMORY_LIMIT" == "1Gi" ]] && R="pass" || R="memoryLimit=${COO_MEMORY_LIMIT:-missing}"
check "Cluster Observability Operator resource policy protects Perses operator" "$R"

OTEL_CSV=$(csv_phase_from_subscription openshift-opentelemetry-operator opentelemetry-product)
[[ "$OTEL_CSV" == "Succeeded" ]] && R="pass" || R="phase=${OTEL_CSV:-not found}"
check "Red Hat build of OpenTelemetry Operator CSV Succeeded" "$R"

TEMPO_CSV=$(csv_phase_from_subscription openshift-tempo-operator tempo-product)
[[ "$TEMPO_CSV" == "Succeeded" ]] && R="pass" || R="phase=${TEMPO_CSV:-not found}"
check "Tempo Operator CSV Succeeded" "$R"

# ── 8. DSCInitialization Ready ────────────────────────────────────────────────
DSCI_PHASE=$(oc get dscinitialization default-dsci \
  -o jsonpath='{.status.phase}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
[[ "$DSCI_PHASE" == "Ready" ]] && R="pass" || R="phase=${DSCI_PHASE:-not found}"
check "DSCInitialization phase Ready" "$R"

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

OBS_TLS_SECRET=$(oc get secret prometheus-web-tls-ca -n redhat-ods-monitoring \
  -o jsonpath='{.data.service-ca\.crt}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
[[ -n "$OBS_TLS_SECRET" ]] && R="pass" || R="secret=missing"
check "RHOAI observability Prometheus web TLS CA Secret present" "$R"

OBS_PERSES_NETPOL=$(oc get networkpolicy perses-backend-operator-access -n redhat-ods-monitoring \
  -o jsonpath='{.metadata.name}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
[[ "$OBS_PERSES_NETPOL" == "perses-backend-operator-access" ]] && R="pass" || R="networkpolicy=${OBS_PERSES_NETPOL:-missing}"
check "Perses backend operator access NetworkPolicy present" "$R"

ADMIN_PERSES_DASHBOARDS=$(oc auth can-i list persesdashboards.perses.dev \
  --as=ai-admin --as-group=rhods-admins --all-namespaces \
  --insecure-skip-tls-verify=true 2>/dev/null || echo "no")
[[ "$ADMIN_PERSES_DASHBOARDS" == "yes" ]] && R="pass" || R="can-i=${ADMIN_PERSES_DASHBOARDS:-no}"
check "ai-admin can discover Perses dashboards" "$R"

ADMIN_PERSES_DATASOURCES=$(oc auth can-i list persesdatasources.perses.dev \
  --as=ai-admin --as-group=rhods-admins --all-namespaces \
  --insecure-skip-tls-verify=true 2>/dev/null || echo "no")
[[ "$ADMIN_PERSES_DATASOURCES" == "yes" ]] && R="pass" || R="can-i=${ADMIN_PERSES_DATASOURCES:-no}"
check "ai-admin can discover Perses datasources" "$R"

ADMIN_PROMETHEUS_API=$(oc auth can-i create prometheuses/k8s --subresource=api \
  --as=ai-admin --as-group=rhods-admins -n openshift-monitoring \
  --insecure-skip-tls-verify=true 2>/dev/null || echo "no")
[[ "$ADMIN_PROMETHEUS_API" == "yes" ]] && R="pass" || R="can-i=${ADMIN_PROMETHEUS_API:-no}"
check "ai-admin can query OpenShift monitoring Prometheus API" "$R"

OBS_READY=$(oc get monitoring.services.platform.opendatahub.io default-monitoring \
  -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
OBS_STACK_READY=$(oc get monitoring.services.platform.opendatahub.io default-monitoring \
  -o jsonpath='{.status.conditions[?(@.type=="MonitoringStackAvailable")].status}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
OBS_OTEL_READY=$(oc get monitoring.services.platform.opendatahub.io default-monitoring \
  -o jsonpath='{.status.conditions[?(@.type=="OpenTelemetryCollectorAvailable")].status}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
OBS_PERSES_READY=$(oc get monitoring.services.platform.opendatahub.io default-monitoring \
  -o jsonpath='{.status.conditions[?(@.type=="PersesAvailable")].status}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
OBS_TEMPO_READY=$(oc get monitoring.services.platform.opendatahub.io default-monitoring \
  -o jsonpath='{.status.conditions[?(@.type=="TempoAvailable")].status}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
[[ "$OBS_READY" == "True" && "$OBS_STACK_READY" == "True" && "$OBS_OTEL_READY" == "True" && "$OBS_PERSES_READY" == "True" && "$OBS_TEMPO_READY" == "True" ]] \
  && R="pass" || R="Ready=${OBS_READY:-missing} MonitoringStack=${OBS_STACK_READY:-missing} OpenTelemetryCollector=${OBS_OTEL_READY:-missing} Perses=${OBS_PERSES_READY:-missing} Tempo=${OBS_TEMPO_READY:-missing}"
check "RHOAI observability service Ready with metrics, traces, and Perses" "$R"

OBS_CLUSTER_DASHBOARD=$(oc get persesdashboard dashboard-0-cluster-admin -n redhat-ods-monitoring \
  -o jsonpath='{.status.conditions[?(@.type=="Available")].status}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
[[ "$OBS_CLUSTER_DASHBOARD" == "True" ]] && R="pass" || R="available=${OBS_CLUSTER_DASHBOARD:-missing}"
check "RHOAI Cluster Perses dashboard available" "$R"

OBS_MODEL_DASHBOARD=$(oc get persesdashboard dashboard-1-model -n redhat-ods-monitoring \
  -o jsonpath='{.status.conditions[?(@.type=="Available")].status}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
[[ "$OBS_MODEL_DASHBOARD" == "True" ]] && R="pass" || R="available=${OBS_MODEL_DASHBOARD:-missing}"
check "RHOAI Model Perses dashboard available" "$R"

OBS_PODS=$(oc get pods -n redhat-ods-monitoring --no-headers \
  --insecure-skip-tls-verify=true 2>/dev/null \
  | grep -E 'alertmanager-data-science-monitoringstack|data-science-collector|prometheus-data-science-monitoringstack|tempo-data-science|thanos-querier-data-science' \
  | wc -l | tr -d ' ')
[[ "${OBS_PODS:-0}" -ge 3 ]] && R="pass" || R="matchingPods=${OBS_PODS:-0}"
check "RHOAI observability stack pods present" "$R"

# ── 10. DataScienceCluster Ready ──────────────────────────────────────────────
DSC_PHASE=$(oc get datasciencecluster default-dsc \
  -o jsonpath='{.status.phase}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
[[ "$DSC_PHASE" == "Ready" ]] && R="pass" || R="phase=${DSC_PHASE:-not found}"
check "DataScienceCluster phase Ready" "$R"

# ── 11. Model Registry operator running ──────────────────────────────────────
MR_READY=$(oc get deployment model-registry-operator-controller-manager \
  -n redhat-ods-applications \
  -o jsonpath='{.status.readyReplicas}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
[[ "${MR_READY:-0}" -ge 1 ]] && R="pass" || R="readyReplicas=${MR_READY:-0}"
check "Model Registry operator running" "$R"

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

# ── 13. htpasswd identity provider configured ────────────────────────────────
IDP=$(oc get oauth cluster \
  -o jsonpath='{.spec.identityProviders[*].name}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
[[ "$IDP" == *"demo-htpasswd"* ]] && R="pass" || R="idps=${IDP:-none}"
check "htpasswd identity provider configured" "$R"

# ── 14. ai-admin is a RHOAI administrator ────────────────────────────────────
ADMINS=$(oc get group rhods-admins \
  -o jsonpath='{.users}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
[[ "$ADMINS" == *"ai-admin"* ]] && R="pass" || R="rhods-admins=${ADMINS:-empty}"
check "ai-admin in rhods-admins (RHOAI admin)" "$R"

# ── 15. demo-sandbox data science project exists ─────────────────────────────
DS_LABEL=$(oc get namespace demo-sandbox \
  -o jsonpath='{.metadata.labels.opendatahub\.io/dashboard}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
[[ "$DS_LABEL" == "true" ]] && R="pass" || R="dashboard-label=${DS_LABEL:-missing}"
check "demo-sandbox data science project present" "$R"

# ── 16. demo-sandbox object bucket bound ─────────────────────────────────────
OBC_PHASE=$(oc get obc demo-sandbox-bucket -n demo-sandbox \
  -o jsonpath='{.status.phase}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
[[ "$OBC_PHASE" == "Bound" ]] && R="pass" || R="phase=${OBC_PHASE:-not found}"
check "demo-sandbox ObjectBucketClaim Bound" "$R"

# ── 17. demo-sandbox S3 connection present ───────────────────────────────────
CONN_LABEL=$(oc get secret demo-sandbox-s3 -n demo-sandbox \
  -o jsonpath='{.metadata.labels.opendatahub\.io/dashboard}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
[[ "$CONN_LABEL" == "true" ]] && R="pass" || R="connection=${CONN_LABEL:-missing}"
check "demo-sandbox S3 connection present" "$R"

# ── 18. RHOAI admins can manage demo-sandbox ─────────────────────────────────
ADMIN_RB=$(oc get rolebinding rhods-admins-admin -n demo-sandbox \
  -o jsonpath='{.roleRef.name}' --insecure-skip-tls-verify=true 2>/dev/null || echo "")
[[ "$ADMIN_RB" == "admin" ]] && R="pass" || R="rolebinding=${ADMIN_RB:-missing}"
check "rhods-admins admin on demo-sandbox" "$R"

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "Results: ${PASS} passed, ${FAIL} failed"
[[ "$FAIL" -eq 0 ]] && exit 0 || exit 1
