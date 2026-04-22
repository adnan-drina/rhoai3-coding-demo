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

# --- InferenceServices ---
log_step "InferenceServices"
for model in gpt-oss-20b nemotron-3-nano-30b-a3b; do
    check_warn "$model ready" \
        "oc get inferenceservice $model -n maas -o jsonpath='{.status.conditions[?(@.type==\"Ready\")].status}'" \
        "True"
done

# --- MaaS Groups ---
log_step "MaaS Tier Groups"
for group in maas-free maas-premium maas-enterprise; do
    check "$group group exists" \
        "oc get group $group -o jsonpath='{.metadata.name}'" \
        "$group"
done

# --- Summary ---
echo ""
validation_summary
