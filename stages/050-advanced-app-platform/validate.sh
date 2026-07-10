#!/usr/bin/env bash
# Stage 050: Advanced Application Platform — Validation Script
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/validate-lib.sh"

echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║  Stage 050: Advanced Application Platform                         ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""

log_step "Argo CD Application"
check_argocd_app "050-advanced-app-platform"

log_step "Trusted-delivery operators"
check_csv_succeeded "openshift-operators" "Red Hat OpenShift Pipelines"
check_csv_succeeded "openshift-operators" "Red Hat Trusted Artifact Signer"

log_step "Pipelines runtime"
check "TektonConfig ready" \
  "oc get tektonconfig config -o jsonpath='{.status.conditions[?(@.type==\"Ready\")].status}'" \
  "True"
check_warn "Securesign instance exists (arrives with stage implementation)" \
  "oc get securesign -A --no-headers 2>/dev/null | wc -l | tr -d ' '" \
  "1"

log_step "Shared push pipeline"
check "app-platform-push pipeline exists" \
  "oc get pipeline app-platform-push -n app-platform-build -o jsonpath='{.metadata.name}'" \
  "app-platform-push"
check "EventListener exists" \
  "oc get eventlistener app-platform-listener -n app-platform-build -o jsonpath='{.metadata.name}'" \
  "app-platform-listener"
check_warn "GitHub webhook secret provisioned (set GITHUB_WEBHOOK_SECRET in .env)" \
  "oc get secret github-webhook-secret -n app-platform-build -o jsonpath='{.metadata.name}' 2>/dev/null || echo missing" \
  "github-webhook-secret"

log_step "SonarQube"
check "SonarQube deployment ready" \
  "oc get deployment sonarqube -n sonarqube -o jsonpath='{.status.readyReplicas}'" \
  "1"
check "Quality-gate scanner credentials provisioned" \
  "oc get secret sonarqube-credentials -n app-platform-build -o jsonpath='{.metadata.name}' 2>/dev/null || echo missing" \
  "sonarqube-credentials"

log_step "Dev Spaces (devspaces component)"
check "CheCluster phase Active" \
  "oc get checluster devspaces -n openshift-devspaces -o jsonpath='{.status.chePhase}'" \
  "Active"

log_step "MigIQ (migiq component)"
check "Tackle CR exists" \
  "oc get tackle mta -n openshift-mta -o jsonpath='{.metadata.name}'" \
  "mta"

log_step "RHDH Operator"
check_csv_succeeded "rhdh-operator" "rhdh"

log_step "RHDH Instance"
check "Backstage CR exists" \
  "oc get backstage developer-hub -n rhdh -o jsonpath='{.metadata.name}'" \
  "developer-hub"
check "RHDH app config mounted by Backstage CR" \
  "oc get backstage developer-hub -n rhdh -o jsonpath='{.spec.application.appConfig.configMaps[0].name}'" \
  "app-config-rhdh"
check "RHDH dynamic plugins config mounted by Backstage CR" \
  "oc get backstage developer-hub -n rhdh -o jsonpath='{.spec.application.dynamicPluginsConfigMapName}'" \
  "dynamic-plugins-rhdh"

log_step "RHDH Deployment"
RHDH_DEPLOY=$(oc get deployment -n rhdh --no-headers 2>/dev/null | grep backstage | awk '{print $1}' | head -1 || echo "")
if [[ -n "$RHDH_DEPLOY" ]]; then
    check "RHDH deployment ready" \
      "oc get deployment ${RHDH_DEPLOY} -n rhdh -o jsonpath='{.status.readyReplicas}'" \
      "1"
else
    echo -e "${RED}[FAIL]${NC} RHDH deployment not found"
    VALIDATE_FAIL=$((VALIDATE_FAIL + 1))
fi

log_step "RHDH Route"
RHDH_ROUTE=$(oc get route -n rhdh --no-headers 2>/dev/null | grep backstage | awk '{print $2}' | head -1 || echo "")
if [[ -n "$RHDH_ROUTE" ]]; then
    check_http_code "RHDH UI: https://${RHDH_ROUTE}" "https://${RHDH_ROUTE}" "200,302"
else
    echo -e "${YELLOW}[WARN]${NC} RHDH route not found"
    VALIDATE_WARN=$((VALIDATE_WARN + 1))
fi

log_step "RHDH Secrets (non-placeholder)"
check_secret_value "RHDH_BASE_URL" "rhdh" "rhdh-secrets" "RHDH_BASE_URL"
check_secret_value "RHDH_OIDC_CLIENT_SECRET" "rhdh" "rhdh-secrets" "RHDH_OIDC_CLIENT_SECRET"
check_secret_value "SESSION_SECRET" "rhdh" "rhdh-secrets" "SESSION_SECRET"

CATALOG_URL=$(oc get secret rhdh-secrets -n rhdh -o jsonpath='{.data.RHDH_CATALOG_URL}' 2>/dev/null | base64 -d 2>/dev/null || echo "")
APP_REPO_URL=$(oc get application 050-advanced-app-platform -n openshift-gitops -o jsonpath='{.spec.source.repoURL}' 2>/dev/null || echo "")
APP_TARGET_REVISION=$(oc get application 050-advanced-app-platform -n openshift-gitops -o jsonpath='{.spec.source.targetRevision}' 2>/dev/null || echo "")
REPO_NO_GIT="${APP_REPO_URL%.git}"
EXPECTED_CATALOG_URL=""
if [[ "$REPO_NO_GIT" =~ ^https://github.com/([^/]+)/([^/]+)$ ]] && [[ -n "$APP_TARGET_REVISION" ]]; then
    EXPECTED_CATALOG_URL="https://raw.githubusercontent.com/${BASH_REMATCH[1]}/${BASH_REMATCH[2]}/${APP_TARGET_REVISION}/gitops/stages/050-advanced-app-platform/base/rhdh/catalog/all.yaml"
fi
if [[ "$CATALOG_URL" == "/opt/app-root/src/catalog/all.yaml" ]]; then
    echo -e "${GREEN}[PASS]${NC} RHDH_CATALOG_URL uses generated runtime catalog: ${CATALOG_URL}"
    VALIDATE_PASS=$((VALIDATE_PASS + 1))
elif [[ -n "$EXPECTED_CATALOG_URL" ]] && [[ "$CATALOG_URL" == "$EXPECTED_CATALOG_URL" ]]; then
    echo -e "${GREEN}[PASS]${NC} RHDH_CATALOG_URL matches Argo CD source: ${CATALOG_URL}"
    VALIDATE_PASS=$((VALIDATE_PASS + 1))
elif [[ -n "$CATALOG_URL" ]] && [[ "$CATALOG_URL" != *"placeholder"* ]]; then
    echo -e "${YELLOW}[WARN]${NC} RHDH_CATALOG_URL is set but does not match Argo CD source: ${CATALOG_URL}"
    VALIDATE_WARN=$((VALIDATE_WARN + 1))
else
    echo -e "${RED}[FAIL]${NC} RHDH_CATALOG_URL is placeholder or missing"
    VALIDATE_FAIL=$((VALIDATE_FAIL + 1))
fi

RUNTIME_CATALOG=$(oc get configmap catalog-runtime-rhdh -n rhdh -o jsonpath='{.data.all\.yaml}' 2>/dev/null || echo "")
if [[ "$RUNTIME_CATALOG" == *"devspaces"* && "$RUNTIME_CATALOG" == *"placeholder.example.com"* ]]; then
    echo -e "${RED}[FAIL]${NC} Runtime catalog still contains Dev Spaces placeholder"
    VALIDATE_FAIL=$((VALIDATE_FAIL + 1))
elif [[ "$RUNTIME_CATALOG" == *"feature/coolstore-inventory-service-plan"* ]] || \
     [[ "$RUNTIME_CATALOG" == *"coolstore-inventory-service/tree/feature"* ]]; then
    echo -e "${RED}[FAIL]${NC} Runtime catalog still points coolstore-inventory-service at the retired feature branch"
    VALIDATE_FAIL=$((VALIDATE_FAIL + 1))
elif [[ "$RUNTIME_CATALOG" == *"#https://github.com/adnan-drina/getting-started-ai-coding"* ]] && \
     [[ "$RUNTIME_CATALOG" == *"#https://github.com/rhpds/mca-coolstore"* ]] && \
     [[ "$RUNTIME_CATALOG" == *"#https://github.com/adnan-drina/coolstore-inventory-service"* ]]; then
    echo -e "${GREEN}[PASS]${NC} Runtime catalog contains generated component-specific Dev Spaces links"
    VALIDATE_PASS=$((VALIDATE_PASS + 1))
else
    echo -e "${YELLOW}[WARN]${NC} Runtime catalog not found or missing component-specific Dev Spaces links"
    VALIDATE_WARN=$((VALIDATE_WARN + 1))
fi
if [[ "$RUNTIME_CATALOG" == *"https://rhdh.placeholder.example.com"* || "$RUNTIME_CATALOG" == *"__RHOAI3_DEMO_REVISION__"* ]]; then
    echo -e "${RED}[FAIL]${NC} Runtime catalog still contains TechDocs placeholders"
    VALIDATE_FAIL=$((VALIDATE_FAIL + 1))
elif [[ "$RUNTIME_CATALOG" == *"/docs/default/component/getting-started-ai-coding"* ]] && \
     [[ "$RUNTIME_CATALOG" == *"/docs/default/component/coolstore-inventory-service"* ]] && \
     [[ "$RUNTIME_CATALOG" == *"/docs/default/component/coolstore"* ]] && \
     [[ "$RUNTIME_CATALOG" == *"backstage.io/techdocs-ref"* ]]; then
    echo -e "${GREEN}[PASS]${NC} Runtime catalog contains generated TechDocs links"
    VALIDATE_PASS=$((VALIDATE_PASS + 1))
else
    echo -e "${YELLOW}[WARN]${NC} Runtime catalog not found or missing TechDocs links"
    VALIDATE_WARN=$((VALIDATE_WARN + 1))
fi

log_step "RHDH Configuration"
check "RHDH config uses OIDC sign-in" \
  "oc get configmap app-config-rhdh -n rhdh -o jsonpath='{.data.app-config-rhdh\\.yaml}'" \
  "signInPage: oidc"
check "RHDH config references demo catalog" \
  "oc get configmap app-config-rhdh -n rhdh -o jsonpath='{.data.app-config-rhdh\\.yaml}'" \
  'target: ${RHDH_CATALOG_URL}'
check "RHDH config enables local TechDocs builder for demo use" \
  "oc get configmap app-config-rhdh -n rhdh -o jsonpath='{.data.app-config-rhdh\\.yaml}'" \
  "techdocs:"
check "RHDH dynamic plugins config exists" \
  "oc get configmap dynamic-plugins-rhdh -n rhdh -o jsonpath='{.data.dynamic-plugins\\.yaml}'" \
  "dynamic-plugins.default.yaml"

log_step "ConsoleLink"
CL_HREF=$(oc get consolelink rhdh -o jsonpath='{.spec.href}' 2>/dev/null || echo "")
if [[ -n "$CL_HREF" ]] && [[ "$CL_HREF" != *"placeholder"* ]]; then
    echo -e "${GREEN}[PASS]${NC} ConsoleLink: ${CL_HREF}"
    VALIDATE_PASS=$((VALIDATE_PASS + 1))
else
    echo -e "${YELLOW}[WARN]${NC} ConsoleLink href is placeholder or missing"
    VALIDATE_WARN=$((VALIDATE_WARN + 1))
fi

echo ""
validation_summary
