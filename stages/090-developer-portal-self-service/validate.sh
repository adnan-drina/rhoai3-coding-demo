#!/usr/bin/env bash
# Stage 090: Developer Hub — Validation Script
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/validate-lib.sh"

echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║  Stage 090: Red Hat Developer Hub — Developer Portal             ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""

log_step "Argo CD Application"
check_argocd_app "090-developer-portal-self-service"

log_step "RHDH Operator"
check_csv_succeeded "rhdh-operator" "rhdh"

log_step "RHDH Instance"
check "Backstage CR exists" \
  "oc get backstage developer-hub -n rhdh -o jsonpath='{.metadata.name}'" \
  "developer-hub"

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
    HTTP_CODE=$(curl -sk -o /dev/null -w "%{http_code}" "https://${RHDH_ROUTE}" 2>/dev/null || echo "000")
    if [[ "$HTTP_CODE" == "200" ]] || [[ "$HTTP_CODE" == "302" ]]; then
        echo -e "${GREEN}[PASS]${NC} RHDH UI: https://${RHDH_ROUTE} (HTTP ${HTTP_CODE})"
        VALIDATE_PASS=$((VALIDATE_PASS + 1))
    else
        echo -e "${YELLOW}[WARN]${NC} RHDH UI: https://${RHDH_ROUTE} (HTTP ${HTTP_CODE})"
        VALIDATE_WARN=$((VALIDATE_WARN + 1))
    fi
else
    echo -e "${YELLOW}[WARN]${NC} RHDH route not found"
    VALIDATE_WARN=$((VALIDATE_WARN + 1))
fi

log_step "RHDH Secrets (non-placeholder)"
RHDH_URL=$(oc get secret rhdh-secrets -n rhdh -o jsonpath='{.data.RHDH_BASE_URL}' 2>/dev/null | base64 -d 2>/dev/null || echo "")
if [[ -n "$RHDH_URL" ]] && [[ "$RHDH_URL" != *"placeholder"* ]]; then
    echo -e "${GREEN}[PASS]${NC} RHDH_BASE_URL: ${RHDH_URL}"
    VALIDATE_PASS=$((VALIDATE_PASS + 1))
else
    echo -e "${RED}[FAIL]${NC} RHDH_BASE_URL is placeholder or missing"
    VALIDATE_FAIL=$((VALIDATE_FAIL + 1))
fi

OIDC_SECRET=$(oc get secret rhdh-secrets -n rhdh -o jsonpath='{.data.RHDH_OIDC_CLIENT_SECRET}' 2>/dev/null | base64 -d 2>/dev/null || echo "")
OIDC_SECRET_LC=$(printf '%s' "$OIDC_SECRET" | tr '[:upper:]' '[:lower:]')
if [[ -n "$OIDC_SECRET" ]] && [[ "$OIDC_SECRET_LC" != *"placeholder"* ]]; then
    echo -e "${GREEN}[PASS]${NC} RHDH_OIDC_CLIENT_SECRET: set"
    VALIDATE_PASS=$((VALIDATE_PASS + 1))
else
    echo -e "${RED}[FAIL]${NC} RHDH_OIDC_CLIENT_SECRET is placeholder or missing"
    VALIDATE_FAIL=$((VALIDATE_FAIL + 1))
fi

SESSION_SECRET=$(oc get secret rhdh-secrets -n rhdh -o jsonpath='{.data.SESSION_SECRET}' 2>/dev/null | base64 -d 2>/dev/null || echo "")
SESSION_SECRET_LC=$(printf '%s' "$SESSION_SECRET" | tr '[:upper:]' '[:lower:]')
if [[ -n "$SESSION_SECRET" ]] && [[ "$SESSION_SECRET_LC" != *"placeholder"* ]]; then
    echo -e "${GREEN}[PASS]${NC} SESSION_SECRET: set"
    VALIDATE_PASS=$((VALIDATE_PASS + 1))
else
    echo -e "${RED}[FAIL]${NC} SESSION_SECRET is placeholder or missing"
    VALIDATE_FAIL=$((VALIDATE_FAIL + 1))
fi

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
