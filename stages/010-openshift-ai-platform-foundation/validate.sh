#!/usr/bin/env bash
# Stage 010: Red Hat OpenShift AI Platform - Validation Script
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/validate-lib.sh"

echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║  Stage 010: Red Hat OpenShift AI Platform Validation            ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""

log_step "Argo CD Application"
SYNC=$(oc get application 010-openshift-ai-platform-foundation -n openshift-gitops -o jsonpath='{.status.sync.status}' 2>/dev/null || echo "NOT_FOUND")
HEALTH=$(oc get application 010-openshift-ai-platform-foundation -n openshift-gitops -o jsonpath='{.status.health.status}' 2>/dev/null || echo "NOT_FOUND")
if [[ "$SYNC" == "Synced" ]]; then
    echo -e "${GREEN}[PASS]${NC} Argo CD app sync: Synced"
    VALIDATE_PASS=$((VALIDATE_PASS + 1))
else
    echo -e "${YELLOW}[WARN]${NC} Argo CD app sync: $SYNC (operator-managed resources may drift)"
    VALIDATE_WARN=$((VALIDATE_WARN + 1))
fi
if [[ "$HEALTH" == "Healthy" ]]; then
    echo -e "${GREEN}[PASS]${NC} Argo CD app health: Healthy"
    VALIDATE_PASS=$((VALIDATE_PASS + 1))
else
    echo -e "${RED}[FAIL]${NC} Argo CD app health: $HEALTH"
    VALIDATE_FAIL=$((VALIDATE_FAIL + 1))
fi

log_step "Platform Dependencies"
check_crd_exists "certificates.cert-manager.io"
check_crd_exists "knativeservings.operator.knative.dev"
check "KnativeServing ready" \
    "oc get knativeserving knative-serving -n knative-serving -o jsonpath='{.status.conditions[?(@.type==\"Ready\")].status}'" \
    "True"

log_step "Red Hat OpenShift AI Operator"
check_csv_succeeded "redhat-ods-operator" "Red Hat OpenShift AI"

log_step "DSCInitialization"
check "DSCInitialization exists" \
    "oc get dscinitializations --no-headers 2>/dev/null | wc -l | tr -d ' '" \
    "1"

log_step "DataScienceCluster"
check "DataScienceCluster phase Ready" \
    "oc get datasciencecluster default-dsc -o jsonpath='{.status.phase}'" \
    "Ready"

log_step "Hardware Profiles"
HP_COUNT=$(oc get hardwareprofiles -n redhat-ods-applications --no-headers 2>/dev/null | wc -l | tr -d ' ')
if [[ "$HP_COUNT" -ge 1 ]]; then
    echo -e "${GREEN}[PASS]${NC} Hardware Profiles found: $HP_COUNT"
    VALIDATE_PASS=$((VALIDATE_PASS + 1))
else
    echo -e "${RED}[FAIL]${NC} No Hardware Profiles found"
    VALIDATE_FAIL=$((VALIDATE_FAIL + 1))
fi

log_step "GenAI Studio"
check "GenAI Studio enabled" \
    "oc get odhdashboardconfig odh-dashboard-config -n redhat-ods-applications -o jsonpath='{.spec.dashboardConfig.genAiStudio}'" \
    "true"

log_step "Dashboard Access"
DASHBOARD_HTTPROUTE=$(oc get httproute rhods-dashboard -n redhat-ods-applications -o jsonpath='{.metadata.name}' 2>/dev/null || echo "")
DASHBOARD_ROUTE=$(oc get route rhods-dashboard -n redhat-ods-applications -o jsonpath='{.spec.host}' 2>/dev/null || echo "")
if [[ -n "$DASHBOARD_HTTPROUTE" ]]; then
    echo -e "${GREEN}[PASS]${NC} Dashboard HTTPRoute exists (Red Hat OpenShift AI 3.x Gateway API)"
    VALIDATE_PASS=$((VALIDATE_PASS + 1))
elif [[ -n "$DASHBOARD_ROUTE" ]]; then
    echo -e "${GREEN}[PASS]${NC} Dashboard Route exists"
    VALIDATE_PASS=$((VALIDATE_PASS + 1))
else
    echo -e "${RED}[FAIL]${NC} Dashboard not accessible"
    VALIDATE_FAIL=$((VALIDATE_FAIL + 1))
fi

echo ""
validation_summary
