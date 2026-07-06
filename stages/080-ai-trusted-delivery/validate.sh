#!/usr/bin/env bash
# Stage 080: AI in Trusted Delivery - Validation (base setup)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/validate-lib.sh"

echo "Stage 080: AI in Trusted Delivery — Validation (base setup)"
echo ""

log_step "Argo CD Application"
check_argocd_app "080-ai-trusted-delivery"

log_step "Trusted-delivery operators"
check_csv_succeeded "openshift-operators" "Red Hat OpenShift Pipelines"
check_csv_succeeded "openshift-operators" "Red Hat Trusted Artifact Signer"

log_step "Pipelines runtime"
check "TektonConfig ready" \
  "oc get tektonconfig config -o jsonpath='{.status.conditions[?(@.type==\"Ready\")].status}'" \
  "True"

log_step "Implementation phase (expected pending in base setup)"
check_warn "Securesign instance exists (arrives with stage implementation)" \
  "oc get securesign -A --no-headers 2>/dev/null | wc -l | tr -d ' '" \
  "1"

echo ""
validation_summary
