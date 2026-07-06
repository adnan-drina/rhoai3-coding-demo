#!/usr/bin/env bash
# Stage 070: MTA — Deploy
# Applies the ArgoCD Application for Migration Toolkit for Applications 8.1
# with Red Hat Developer Lightspeed configured to use MaaS models.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"

STAGE_NAME="070-ai-autonomous-migration"

load_env
check_oc_logged_in

log_step "Stage 070: Autonomous Application Migration (MTA 8.1)"

apply_stage_app "$STAGE_NAME"

log_info "ArgoCD handles orchestration via sync waves:"
log_info "  Wave 0-2:    MTA Operator (namespace, operatorgroup, subscription)"
log_info "  Wave 5:      kai-api-keys Secret (MaaS API key for LLM proxy)"
log_info "  Wave 10:     Tackle CR (MTA instance with AI config)"
log_info "  Wave 20:     Post-deploy Job (patches cluster-specific MaaS URL)"
echo ""
log_info "Monitor progress:"
echo "  oc get application ${STAGE_NAME} -n openshift-gitops -w"
echo "  oc get pods -n openshift-mta"
echo "  oc get tackle mta -n openshift-mta"
echo ""
log_info "After deploy, access MTA UI:"
echo "  oc get route -n openshift-mta"
echo "  Default login: admin / Passw0rd!"
echo ""
