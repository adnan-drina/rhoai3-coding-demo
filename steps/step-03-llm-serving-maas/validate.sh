#!/usr/bin/env bash
# Step 03: LLM Serving + MaaS — Validation Script
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/validate-lib.sh"

echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║  Step 03: LLM Serving + MaaS — Validation                     ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""

# --- Argo CD Application ---
log_step "Argo CD Application"
check_argocd_app "step-03-llm-serving-maas"

# --- Namespace ---
log_step "Model Serving Namespace"
check "maas namespace exists" \
    "oc get namespace maas -o jsonpath='{.status.phase}'" \
    "Active"

# --- LLMInferenceServices ---
log_step "LLMInferenceServices"
for model in gpt-oss-20b nemotron-3-nano-30b-a3b; do
    check_warn "$model exists" \
        "oc get llminferenceservice $model -n maas -o jsonpath='{.metadata.name}'" \
        "$model"
done

# --- MaaS Groups ---
log_step "MaaS Tier Groups"
for group in tier-free-users tier-premium-users tier-enterprise-users; do
    check "$group group exists" \
        "oc get group $group -o jsonpath='{.metadata.name}'" \
        "$group"
done

# --- Summary ---
echo ""
validation_summary
