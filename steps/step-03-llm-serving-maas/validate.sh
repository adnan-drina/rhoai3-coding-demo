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

# --- MaaS Prerequisites ---
log_step "MaaS Operator Prerequisites"
check_csv_succeeded "openshift-lws-operator" "leader"
check_csv_succeeded "rhcl-operator" "rhcl"
check_crd_exists "authpolicies.kuadrant.io"
check_warn "Kuadrant ready" \
    "oc get kuadrant kuadrant -n kuadrant-system -o jsonpath='{.status.conditions[?(@.type==\"Ready\")].status}'" \
    "True"
check_warn "maas-default-gateway exists" \
    "oc get gateway maas-default-gateway -n openshift-ingress -o jsonpath='{.metadata.name}'" \
    "maas-default-gateway"

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

# --- Observability ---
log_step "Grafana"
check_csv_succeeded "grafana" "grafana"
check "Grafana instance exists" \
    "oc get grafana grafana -n grafana -o jsonpath='{.metadata.name}'" \
    "grafana"
check "MaaS dashboard exists" \
    "oc get grafanadashboard maas-usage -n grafana -o jsonpath='{.metadata.name}'" \
    "maas-usage"

# --- Summary ---
echo ""
validation_summary
