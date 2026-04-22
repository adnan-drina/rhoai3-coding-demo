#!/usr/bin/env bash
# Step 04: Observability — Validation Script
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/validate-lib.sh"

echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║  Step 04: Observability — Validation                           ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""

log_step "Argo CD Application"
check_argocd_app "step-04-observability"

log_step "Grafana Operator"
check_csv_succeeded "grafana" "grafana"

log_step "Grafana Instance"
check "Grafana instance exists" \
    "oc get grafana grafana -n grafana -o jsonpath='{.metadata.name}'" \
    "grafana"

log_step "Grafana Route"
check "Grafana route exists" \
    "oc get route -n grafana --no-headers 2>/dev/null | wc -l | tr -d ' '" \
    "1"

log_step "MaaS Dashboard"
check "MaaS dashboard exists" \
    "oc get grafanadashboard maas-usage -n grafana -o jsonpath='{.metadata.name}'" \
    "maas-usage"

echo ""
validation_summary
