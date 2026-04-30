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

log_step "MTA Core Pods"
check_warn "mta-ui pod running" \
  "oc get pods -n openshift-mta --no-headers 2>/dev/null | grep -c 'mta-ui.*Running'" \
  "1"
check_warn "mta-hub pod running" \
  "oc get pods -n openshift-mta --no-headers 2>/dev/null | grep -c 'mta-hub.*Running'" \
  "1"

log_step "Red Hat Developer Lightspeed (AI)"
check "kai-api-keys Secret exists" \
  "oc get secret kai-api-keys -n openshift-mta -o jsonpath='{.metadata.name}'" \
  "kai-api-keys"
check_warn "kai pod running" \
  "oc get pods -n openshift-mta --no-headers 2>/dev/null | grep -cE 'kai-[a-z0-9].*Running'" \
  "1"

log_step "MTA UI Route"
MTA_ROUTE=$(oc get route -n openshift-mta --no-headers 2>/dev/null | grep mta | awk '{print $2}' | head -1)
if [[ -n "$MTA_ROUTE" ]]; then
    echo -e "${GREEN}[PASS]${NC} MTA UI: https://${MTA_ROUTE}"
    VALIDATE_PASS=$((VALIDATE_PASS + 1))
else
    echo -e "${YELLOW}[WARN]${NC} MTA UI route not found"
    VALIDATE_WARN=$((VALIDATE_WARN + 1))
fi

echo ""
validation_summary
