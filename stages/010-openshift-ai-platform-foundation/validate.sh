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
check_argocd_app "010-openshift-ai-platform-foundation"

log_step "Platform Dependencies"
check_crd_exists "certificates.cert-manager.io"

log_step "Red Hat OpenShift AI Operator"
check_csv_succeeded "redhat-ods-operator" "Red Hat OpenShift AI"

log_step "RHOAI Observability Prerequisites"
check_csv_succeeded "openshift-operators" "Cluster Observability Operator"
check_csv_succeeded "openshift-operators" "Red Hat build of OpenTelemetry"
check_csv_succeeded "openshift-operators" "Tempo Operator"

log_step "Demo Persona Identity"
check "Demo htpasswd Secret exists" \
    "oc get secret demo-htpasswd -n openshift-config -o jsonpath='{.metadata.name}'" \
    "demo-htpasswd"
check "Demo OAuth identity provider configured" \
    "oc get oauth cluster -o jsonpath='{range .spec.identityProviders[?(@.name==\"demo-htpasswd\")]}{.type}{end}'" \
    "HTPasswd"
check "Demo OAuth identity provider uses demo Secret" \
    "oc get oauth cluster -o jsonpath='{range .spec.identityProviders[?(@.name==\"demo-htpasswd\")]}{.htpasswd.fileData.name}{end}'" \
    "demo-htpasswd"
check "RHOAI admin group includes ai-admin" \
    "oc get group rhoai-admins -o jsonpath='{.users[*]}'" \
    "ai-admin"
check "RHOAI users group includes ai-admin" \
    "oc get group rhoai-users -o jsonpath='{.users[*]}'" \
    "ai-admin"
check "RHOAI users group includes ai-developer" \
    "oc get group rhoai-users -o jsonpath='{.users[*]}'" \
    "ai-developer"

if oc get user ai-admin ai-developer &>/dev/null; then
    echo -e "${GREEN}[PASS]${NC} OpenShift User records exist for demo personas"
    VALIDATE_PASS=$((VALIDATE_PASS + 1))
else
    echo -e "${YELLOW}[INFO]${NC} OpenShift User records are created after first successful login; validating OAuth IdP and groups instead"
fi

log_step "DSCInitialization"
check "DSCInitialization exists" \
    "oc get dscinitializations --no-headers 2>/dev/null | wc -l | tr -d ' '" \
    "1"
check "DSCInitialization monitoring managed" \
    "oc get dsci default-dsci -o jsonpath='{.spec.monitoring.managementState}{\" \"}{.spec.monitoring.namespace}'" \
    "Managed redhat-ods-monitoring"
check "RHOAI monitoring CR Ready" \
    "oc get monitoring default-monitoring -o jsonpath='{.status.phase}'" \
    "Ready"
check "RHOAI monitoring stack available" \
    "oc get monitoringstack data-science-monitoringstack -n redhat-ods-monitoring -o jsonpath='{.status.conditions[?(@.type==\"Available\")].status}'" \
    "True"
check "Prometheus web TLS CA Secret exists" \
    "test -n \"\$(oc get secret prometheus-web-tls-ca -n redhat-ods-monitoring -o jsonpath='{.data.service-ca\\.crt}')\" && echo true" \
    "true"
check_pods_ready "redhat-ods-monitoring" "app.kubernetes.io/component=prometheus" 1
check_pods_ready "redhat-ods-monitoring" "app.kubernetes.io/component=alertmanager" 2
check_pods_ready "redhat-ods-monitoring" "app.kubernetes.io/component=opentelemetry-collector" 1
check_pods_ready "redhat-ods-monitoring" "app.kubernetes.io/component=tempo" 1

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
check "Observability dashboard enabled" \
    "oc get odhdashboardconfig odh-dashboard-config -n redhat-ods-applications -o jsonpath='{.spec.dashboardConfig.observabilityDashboard}'" \
    "true"

log_step "RHOAI Observability Dashboards"
check "Perses backend operator access policy exists" \
    "oc get networkpolicy perses-backend-operator-access -n redhat-ods-monitoring -o jsonpath='{.spec.ingress[0].from[0].namespaceSelector.matchLabels.kubernetes\\.io/metadata\\.name}{\" \"}{.spec.ingress[0].from[0].podSelector.matchLabels.app\\.kubernetes\\.io/name}'" \
    "openshift-operators perses-operator"
check "Cluster Perses dashboard reconciled" \
    "oc get persesdashboard dashboard-0-cluster-admin -n redhat-ods-monitoring -o jsonpath='{.status.conditions[?(@.type==\"Available\")].status}'" \
    "True"
check "Model Perses dashboard reconciled" \
    "oc get persesdashboard dashboard-1-model -n redhat-ods-monitoring -o jsonpath='{.status.conditions[?(@.type==\"Available\")].status}'" \
    "True"
check "MaaS usage Perses dashboard reconciled" \
    "oc get persesdashboard dashboard-3-maas-usage-admin -n redhat-ods-applications -o jsonpath='{.status.conditions[?(@.type==\"Available\")].status}'" \
    "True"
check "Kuadrant MaaS datasource reconciled" \
    "oc get persesdatasource kuadrant-prometheus-datasource -n redhat-ods-applications -o jsonpath='{.status.conditions[?(@.type==\"Available\")].status}'" \
    "True"
check "Demo admin can list Perses dashboards" \
    "oc auth can-i list persesdashboards.perses.dev --as=ai-admin --as-group=rhoai-admins --as-group=rhoai-users -n redhat-ods-applications" \
    "yes"
check "Demo admin can list Perses dashboards across namespaces" \
    "oc auth can-i list persesdashboards.perses.dev --as=ai-admin --as-group=rhoai-admins --as-group=rhoai-users --all-namespaces" \
    "yes"
check "Demo admin can list Perses datasources" \
    "oc auth can-i list persesdatasources.perses.dev --as=ai-admin --as-group=rhoai-admins --as-group=rhoai-users -n redhat-ods-applications" \
    "yes"
check "Demo admin can list Perses datasources across namespaces" \
    "oc auth can-i list persesdatasources.perses.dev --as=ai-admin --as-group=rhoai-admins --as-group=rhoai-users --all-namespaces" \
    "yes"
check "Demo admin can access OpenShift monitoring Prometheus API" \
    "oc auth can-i get prometheuses/k8s --subresource=api --as=ai-admin --as-group=rhoai-admins --as-group=rhoai-users -n openshift-monitoring" \
    "yes"
check "Demo admin can query OpenShift monitoring Prometheus API" \
    "oc auth can-i create prometheuses/k8s --subresource=api --as=ai-admin --as-group=rhoai-admins --as-group=rhoai-users -n openshift-monitoring" \
    "yes"

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
