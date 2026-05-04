#!/usr/bin/env bash
# Stage 060: MCP Context Integrations - Deploy
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"

STAGE_NAME="060-mcp-context-integrations"

load_env
check_oc_logged_in

log_step "Stage 060: MCP Context Integrations"

log_step "Provisioning optional MCP credentials"
ensure_namespace "coding-assistant"
oc label namespace coding-assistant opendatahub.io/dashboard=true --overwrite
oc annotate namespace coding-assistant \
    openshift.io/display-name="Coding Assistant" \
    openshift.io/description="AI-assisted development with governed MaaS and MCP context" \
    --overwrite

if [[ -n "${SLACK_BOT_TOKEN:-}" ]]; then
    ensure_secret_from_env "slack-mcp-credentials" "coding-assistant" "SLACK_BOT_TOKEN=${SLACK_BOT_TOKEN}"
    log_success "slack-mcp-credentials provisioned"
else
    log_info "SLACK_BOT_TOKEN not set — Slack MCP will warn during validation"
fi

if [[ -n "${BRIGHTDATA_API_TOKEN:-}" ]]; then
    ensure_secret_from_env "brightdata-mcp-credentials" "coding-assistant" "API_TOKEN=${BRIGHTDATA_API_TOKEN}"
    log_success "brightdata-mcp-credentials provisioned"
else
    log_info "BRIGHTDATA_API_TOKEN not set — BrightData MCP will warn during validation"
fi

oc apply -f "$REPO_ROOT/gitops/argocd/app-of-apps/${STAGE_NAME}.yaml"
log_success "ArgoCD Application '${STAGE_NAME}' applied"

log_info "Monitor progress:"
echo "  oc get application ${STAGE_NAME} -n openshift-gitops -w"
echo "  oc get pods -n coding-assistant"
echo "  oc get configmap gen-ai-aa-mcp-servers -n redhat-ods-applications -o yaml"
echo ""
