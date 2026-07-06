#!/usr/bin/env bash
# Stage 050: Dev Spaces + AI Code Assistant - Deploy
# Applies the ArgoCD Application.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"

STAGE_NAME="050-controlled-developer-workspaces"

load_env
check_oc_logged_in

log_step "Stage 050: Dev Spaces & AI Code Assistant"

apply_stage_app "$STAGE_NAME"

log_info "Monitor progress:"
echo "  oc get application ${STAGE_NAME} -n openshift-gitops -w"
echo "  oc get checluster devspaces -n openshift-devspaces"
echo ""
