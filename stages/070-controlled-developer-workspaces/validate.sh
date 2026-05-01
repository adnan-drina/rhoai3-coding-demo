#!/usr/bin/env bash
# Stage 070: Dev Spaces — Validation Script
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/validate-lib.sh"

echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║  Stage 070: Dev Spaces & AI Code Assistant — Validation          ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""

log_step "Argo CD Application"
check_argocd_app "070-controlled-developer-workspaces"

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

log_step "Pre-Provisioned Workspace Namespaces"
for ns in wksp-kubeadmin wksp-ai-admin wksp-ai-developer; do
    check "Workspace namespace exists: $ns" \
        "oc get namespace $ns -o jsonpath='{.metadata.name}'" \
        "$ns"
    check "Workspace DevWorkspace exists: $ns/exercises" \
        "oc get devworkspace exercises -n $ns -o jsonpath='{.metadata.name}'" \
        "exercises"
    check_warn "Workspace DevWorkspace is not failed: $ns/exercises" \
        "oc get devworkspace exercises -n $ns -o jsonpath='{.status.phase}'" \
        "Stopped"
done

check "ai-admin workspace edit RoleBinding exists" \
    "oc get rolebinding wksp-edit-ai-admin -n wksp-ai-admin -o jsonpath='{.subjects[0].name}'" \
    "ai-admin"
check "ai-admin workspace RoleBinding grants edit" \
    "oc get rolebinding wksp-edit-ai-admin -n wksp-ai-admin -o jsonpath='{.roleRef.name}'" \
    "edit"
check "ai-developer workspace edit RoleBinding exists" \
    "oc get rolebinding wksp-edit-ai-developer -n wksp-ai-developer -o jsonpath='{.subjects[0].name}'" \
    "ai-developer"
check "ai-developer workspace RoleBinding grants edit" \
    "oc get rolebinding wksp-edit-ai-developer -n wksp-ai-developer -o jsonpath='{.roleRef.name}'" \
    "edit"

echo ""
validation_summary
