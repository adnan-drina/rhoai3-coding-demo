#!/usr/bin/env bash
# Step 03: LLM Serving + MaaS - Deploy
# Applies the ArgoCD Application. The upstream maas-controller runs alongside
# the RHOAI operator and uses models-as-a-service for MaaS policy CRs.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"

STEP_NAME="step-03-llm-serving-maas"

load_env
check_oc_logged_in

log_step "Step 03: LLM Serving + MaaS"

# Provision credential secrets from .env before ArgoCD syncs.
# ignoreDifferences in the Application prevents selfHeal from reverting these.
log_step "Provisioning credential secrets"

ensure_namespace "maas"
ensure_namespace "coding-assistant"

if [[ -n "${OPENAI_API_KEY:-}" ]]; then
    ensure_secret_from_env "openai-api-key" "maas" "api-key=${OPENAI_API_KEY}"
    oc label secret openai-api-key -n maas inference.networking.k8s.io/bbr-managed=true --overwrite
    log_success "openai-api-key provisioned in maas namespace"
else
    log_info "OPENAI_API_KEY not set — external models will use placeholder (inference will fail)"
fi

if [[ -n "${SLACK_BOT_TOKEN:-}" ]]; then
    ensure_secret_from_env "slack-mcp-credentials" "coding-assistant" "SLACK_BOT_TOKEN=${SLACK_BOT_TOKEN}"
    log_success "slack-mcp-credentials provisioned"
else
    log_info "SLACK_BOT_TOKEN not set — Slack MCP skipped"
fi

if [[ -n "${BRIGHTDATA_API_TOKEN:-}" ]]; then
    ensure_secret_from_env "brightdata-mcp-credentials" "coding-assistant" "API_TOKEN=${BRIGHTDATA_API_TOKEN}"
    log_success "brightdata-mcp-credentials provisioned"
else
    log_info "BRIGHTDATA_API_TOKEN not set — BrightData MCP skipped"
fi

log_step "Applying ArgoCD Application"
oc apply -f "$REPO_ROOT/gitops/argocd/app-of-apps/${STEP_NAME}.yaml"
log_success "ArgoCD Application '${STEP_NAME}' applied"

log_info "ArgoCD handles orchestration via sync waves:"
log_info "  Wave 0-5:    LWS, RHCL, CNPG, Grafana operators + instances"
log_info "  Wave 5-6:    Project namespaces + user RBAC"
log_info "  Wave 9:      Tier-to-group mapping ConfigMap"
log_info "  Wave 12-14:  Upstream maas-controller, PostgreSQL, RBAC"
log_info "  Wave 15-18:  Models, MaaSModelRefs, ExternalModel, policies"
log_info "  Wave 20-22:  Grafana, Gateway hostname patch, model registry seed"
echo ""
log_info "Monitor progress:"
echo "  oc get application ${STEP_NAME} -n openshift-gitops -w"
echo "  oc get llminferenceservice -n maas"
echo "  oc get kuadrant -n kuadrant-system"
echo ""
