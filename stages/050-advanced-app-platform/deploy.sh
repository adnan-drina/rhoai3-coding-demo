#!/usr/bin/env bash
# Stage 050: Advanced Application Platform — Deploy
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"

STAGE_NAME="050-advanced-app-platform"

load_env
check_oc_logged_in

log_step "Stage 050: Advanced Application Platform — Trusted Delivery + Developer Portal"

apply_stage_app "$STAGE_NAME"

log_info "ArgoCD handles orchestration via sync waves:"
log_info "  Operators:   OpenShift Pipelines (pipelines-1.22), Trusted Artifact"
log_info "               Signer (stable-v1.4), InstallPlan approval hook"
log_info "  Wave 0-2:    RHDH Operator (namespace, operatorgroup, subscription)"
log_info "  Wave 5:      app-config ConfigMap, rhdh-secrets, dynamic-plugins ConfigMap"
log_info "  Wave 10:     Backstage CR (RHDH instance)"
log_info "  Wave 15:     ConsoleLink (OpenShift launcher)"
log_info "  PostSync:    Configure OIDC auth via MTA Keycloak, patch secrets, restart"
echo ""
log_info "TRANSITION NOTE: RHDH OIDC still brokers through the MTA Keycloak"
log_info "deployed by stage 080 (ai-autonomous-migration). Until Phase 2 of"
log_info "docs/PLAN-advanced-app-platform-restructure.md lands platform RHBK"
log_info "here, the PostSync OIDC job needs stage 080 MTA/RHBK healthy first."
echo ""
log_info "Monitor progress:"
echo "  oc get application ${STAGE_NAME} -n openshift-gitops -w"
echo "  oc get csv -n openshift-operators | grep -E 'pipelines|rhtas'"
echo "  oc get pods -n rhdh"
echo "  oc get backstage developer-hub -n rhdh"
echo ""
log_info "After deploy, access Developer Hub:"
echo "  oc get route -n rhdh"
echo ""
