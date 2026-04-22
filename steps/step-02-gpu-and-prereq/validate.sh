#!/usr/bin/env bash
# Step 02: GPU Infrastructure & Prerequisites — Validation Script
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/validate-lib.sh"

echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║  Step 02: GPU Infrastructure & Prerequisites — Validation      ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""

# --- Argo CD Application ---
log_step "Argo CD Application"
check_argocd_app "step-02-gpu-and-prereq"

# --- CRDs ---
log_step "Required CRDs"
check_crd_exists "nodefeaturediscoveries.nfd.openshift.io"
check_crd_exists "clusterpolicies.nvidia.com"
check_crd_exists "knativeservings.operator.knative.dev"
check_crd_exists "leaderworkersetoperators.operator.openshift.io"
check_crd_exists "authpolicies.kuadrant.io"
check_crd_exists "certificates.cert-manager.io"

# --- Operator CSVs ---
log_step "Operator CSVs"
check_csv_succeeded "openshift-nfd" "nfd"
check_csv_succeeded "nvidia-gpu-operator" "gpu"
check_csv_succeeded "openshift-serverless" "serverless"
check_csv_succeeded "openshift-lws-operator" "leader"
check_csv_succeeded "rhcl-operator" "rhcl"
check_csv_succeeded "cert-manager-operator" "cert-manager"

# --- KnativeServing ---
log_step "KnativeServing"
check "KnativeServing ready" \
    "oc get knativeserving knative-serving -n knative-serving -o jsonpath='{.status.conditions[?(@.type==\"Ready\")].status}'" \
    "True"

# --- Kuadrant ---
log_step "Kuadrant"
check_warn "Kuadrant ready" \
    "oc get kuadrant kuadrant -n kuadrant-system -o jsonpath='{.status.conditions[?(@.type==\"Ready\")].status}'" \
    "True"

# --- Authorino ---
log_step "Authorino"
check_warn "Authorino pods ready" \
    "oc get pods -n kuadrant-system -l authorino-resource=authorino --no-headers 2>/dev/null | grep -c Running || echo 0" \
    "1"

# --- MaaS Gateway ---
log_step "MaaS Gateway"
check_warn "maas-default-gateway exists" \
    "oc get gateway maas-default-gateway -n openshift-ingress -o jsonpath='{.metadata.name}'" \
    "maas-default-gateway"

# --- GPU MachineSets ---
log_step "GPU MachineSets"
MS_COUNT=$(oc get machineset -n openshift-machine-api --no-headers 2>/dev/null \
    | grep -c "gpu" || echo "0")
if [[ "$MS_COUNT" -ge 1 ]]; then
    echo -e "${GREEN}[PASS]${NC} GPU MachineSets found: $MS_COUNT"
    VALIDATE_PASS=$((VALIDATE_PASS + 1))
else
    echo -e "${RED}[FAIL]${NC} No GPU MachineSets found"
    VALIDATE_FAIL=$((VALIDATE_FAIL + 1))
fi

GPU_NODES=$(oc get nodes -l node-role.kubernetes.io/gpu --no-headers 2>/dev/null | wc -l | tr -d ' ')
if [[ "$GPU_NODES" -ge 1 ]]; then
    echo -e "${GREEN}[PASS]${NC} GPU nodes available: $GPU_NODES"
    VALIDATE_PASS=$((VALIDATE_PASS + 1))
else
    echo -e "${YELLOW}[WARN]${NC} GPU nodes available: $GPU_NODES (may take 5-10 min to provision)"
    VALIDATE_WARN=$((VALIDATE_WARN + 1))
fi

# --- Summary ---
echo ""
validation_summary
