#!/usr/bin/env bash
# Stage 080: AI in Trusted Delivery - Deploy (base setup)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"

STAGE_NAME="080-ai-trusted-delivery"

load_env
check_oc_logged_in

log_step "Stage 080: AI in Trusted Delivery (base setup)"

apply_stage_app "$STAGE_NAME"

log_info "Base setup installs the trusted-delivery operators:"
log_info "  OpenShift Pipelines (pipelines-1.22) and Trusted Artifact Signer (stable-v1.4)"
log_info "Securesign instance, TPA, and the migrated-app pipeline arrive with the"
log_info "stage implementation (see stages/${STAGE_NAME}/README.md)."
echo ""
log_info "Monitor progress:"
echo "  oc get application ${STAGE_NAME} -n openshift-gitops -w"
echo "  oc get csv -n openshift-operators | grep -E 'pipelines|rhtas'"
