#!/usr/bin/env bash
# Step 05: MTA — Validation Script
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/validate-lib.sh"

echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║  Step 05: AI-Assisted Application Modernization (MTA 8.1)     ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""

log_step "Argo CD Application"
check_argocd_app "step-05-mta"

log_step "MTA Operator"
check_csv_succeeded "openshift-mta" "mta-operator"

log_step "MTA Instance"
check "Tackle CR exists" \
  "oc get tackle mta -n openshift-mta -o jsonpath='{.metadata.name}'" \
  "mta"

log_step "MTA Core Deployments"
check "mta-ui deployment ready" \
  "oc get deployment mta-ui -n openshift-mta -o jsonpath='{.status.readyReplicas}'" \
  "1"
check "mta-hub deployment ready" \
  "oc get deployment mta-hub -n openshift-mta -o jsonpath='{.status.readyReplicas}'" \
  "1"

log_step "Red Hat Developer Lightspeed (AI)"
check "kai-api deployment ready" \
  "oc get deployment kai-api -n openshift-mta -o jsonpath='{.status.readyReplicas}'" \
  "1"
check "llm-proxy deployment ready" \
  "oc get deployment llm-proxy -n openshift-mta -o jsonpath='{.status.readyReplicas}'" \
  "1"

log_step "Tackle AI Conditions"
check "Tackle KaiAPIKeysConfigured" \
  "oc get tackle mta -n openshift-mta -o jsonpath='{.status.conditions[?(@.type==\"KaiAPIKeysConfigured\")].status}'" \
  "True"
check "Tackle LLMProxyReady" \
  "oc get tackle mta -n openshift-mta -o jsonpath='{.status.conditions[?(@.type==\"LLMProxyReady\")].status}'" \
  "True"
check "Tackle KaiSolutionServerReady" \
  "oc get tackle mta -n openshift-mta -o jsonpath='{.status.conditions[?(@.type==\"KaiSolutionServerReady\")].status}'" \
  "True"

log_step "MaaS Credentials (non-placeholder)"
MAAS_URL=$(oc get secret kai-api-keys -n openshift-mta -o jsonpath='{.data.OPENAI_API_BASE}' 2>/dev/null | base64 -d 2>/dev/null || echo "")
if [[ -n "$MAAS_URL" ]] && [[ "$MAAS_URL" != *"placeholder"* ]]; then
    echo -e "${GREEN}[PASS]${NC} OPENAI_API_BASE: ${MAAS_URL}"
    VALIDATE_PASS=$((VALIDATE_PASS + 1))
else
    echo -e "${RED}[FAIL]${NC} OPENAI_API_BASE is placeholder or missing (got: ${MAAS_URL:-empty})"
    VALIDATE_FAIL=$((VALIDATE_FAIL + 1))
fi

MAAS_KEY=$(oc get secret kai-api-keys -n openshift-mta -o jsonpath='{.data.OPENAI_API_KEY}' 2>/dev/null | base64 -d 2>/dev/null || echo "")
if [[ -n "$MAAS_KEY" ]] && [[ "$MAAS_KEY" != *"REPLACE"* ]]; then
    echo -e "${GREEN}[PASS]${NC} OPENAI_API_KEY: set (sk-oai-...)"
    VALIDATE_PASS=$((VALIDATE_PASS + 1))
else
    echo -e "${RED}[FAIL]${NC} OPENAI_API_KEY is placeholder or missing"
    VALIDATE_FAIL=$((VALIDATE_FAIL + 1))
fi

log_step "MTA UI Route"
MTA_ROUTE=$(oc get route mta -n openshift-mta -o jsonpath='{.spec.host}' 2>/dev/null || echo "")
if [[ -n "$MTA_ROUTE" ]]; then
    HTTP_CODE=$(curl -sk -o /dev/null -w "%{http_code}" "https://${MTA_ROUTE}" 2>/dev/null || echo "000")
    if [[ "$HTTP_CODE" == "200" ]] || [[ "$HTTP_CODE" == "302" ]]; then
        echo -e "${GREEN}[PASS]${NC} MTA UI: https://${MTA_ROUTE} (HTTP ${HTTP_CODE})"
        VALIDATE_PASS=$((VALIDATE_PASS + 1))
    else
        echo -e "${YELLOW}[WARN]${NC} MTA UI: https://${MTA_ROUTE} (HTTP ${HTTP_CODE})"
        VALIDATE_WARN=$((VALIDATE_WARN + 1))
    fi
else
    echo -e "${YELLOW}[WARN]${NC} MTA UI route not found"
    VALIDATE_WARN=$((VALIDATE_WARN + 1))
fi

echo ""
validation_summary
