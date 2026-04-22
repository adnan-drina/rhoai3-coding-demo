#!/usr/bin/env bash
# Step 05: Dev Spaces — Validation Script
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/validate-lib.sh"

echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║  Step 04: Dev Spaces & AI Code Assistant — Validation          ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""

log_step "Argo CD Application"
check_argocd_app "step-04-devspaces"

log_step "Dev Spaces Operator"
check_csv_succeeded "openshift-devspaces" "devspaces"

log_step "CheCluster"
check "CheCluster phase Active" \
    "oc get checluster devspaces -n openshift-devspaces -o jsonpath='{.status.chePhase}'" \
    "Active"

log_step "Dev Spaces URL"
DEVSPACES_URL=$(oc get checluster devspaces -n openshift-devspaces -o jsonpath='{.status.cheURL}' 2>/dev/null || echo "")
if [[ -n "$DEVSPACES_URL" ]]; then
    echo -e "${GREEN}[PASS]${NC} Dev Spaces URL: $DEVSPACES_URL"
    VALIDATE_PASS=$((VALIDATE_PASS + 1))
else
    echo -e "${RED}[FAIL]${NC} Dev Spaces URL not available"
    VALIDATE_FAIL=$((VALIDATE_FAIL + 1))
fi

echo ""
validation_summary
