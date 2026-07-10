#!/usr/bin/env bash
# Stage 050: Advanced Application Platform — Deploy
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"

STAGE_NAME="050-advanced-app-platform"

load_env
check_oc_logged_in

log_step "Stage 050: Advanced Application Platform"
log_info "Components: devspaces, pipelines, sonarqube, rhdh, migiq"

# --- Provision build-pipeline secrets from .env (never committed) ---
oc get namespace app-platform-build >/dev/null 2>&1 || oc create namespace app-platform-build

if [[ -n "${GITHUB_WEBHOOK_SECRET:-}" ]]; then
  oc create secret generic github-webhook-secret -n app-platform-build \
    --from-literal=token="${GITHUB_WEBHOOK_SECRET}" \
    --dry-run=client -o yaml | oc apply -f -
  log_info "github-webhook-secret provisioned"
else
  log_warn "GITHUB_WEBHOOK_SECRET not set in .env — webhook-triggered pipeline runs will fail until it is provisioned"
fi

if [[ -n "${GITHUB_TOKEN:-}" ]]; then
  oc create secret generic github-basic-auth -n app-platform-build \
    --from-literal=.git-credentials="https://token:${GITHUB_TOKEN}@github.com" \
    --from-literal=.gitconfig=$'[credential "https://github.com"]\n  helper = store' \
    --dry-run=client -o yaml | oc apply -f -
  log_info "github-basic-auth provisioned"
else
  # Empty secret keeps the PipelineRun workspace binding satisfied for public repos.
  oc get secret github-basic-auth -n app-platform-build >/dev/null 2>&1 || \
    oc create secret generic github-basic-auth -n app-platform-build \
      --from-literal=.git-credentials="" \
      --from-literal=.gitconfig=""
  log_info "GITHUB_TOKEN not set — github-basic-auth left empty (public repos only)"
fi

apply_stage_app "$STAGE_NAME"

log_info "ArgoCD handles orchestration via sync waves (per component):"
log_info "  devspaces:   operator -> CheCluster -> workspaces -> MaaS keys"
log_info "  pipelines:   Pipelines/TAS operators -> build namespace -> pipeline + triggers"
log_info "  sonarqube:   db secret hook -> PostgreSQL -> SonarQube -> PostSync gate/token job"
log_info "  rhdh:        operator -> config -> Backstage CR -> PostSync OIDC"
log_info "  migiq:       MTA operator -> Tackle -> Lightspeed/MaaS hooks"
log_info "RHDH OIDC brokers through the migiq MTA Keycloak; PostSync jobs wait, so"
log_info "ordering resolves within this one Application."
echo ""
log_info "Monitor progress:"
echo "  oc get application ${STAGE_NAME} -n openshift-gitops -w"
echo "  oc get csv -n openshift-operators | grep -E 'pipelines|rhtas'"
echo "  oc get checluster devspaces -n openshift-devspaces"
echo "  oc get pods -n sonarqube"
echo "  oc get pods -n rhdh"
echo "  oc get tackle mta -n openshift-mta"
echo ""
log_info "After deploy:"
echo "  oc get route -n rhdh                     # Developer Hub"
echo "  oc get route sonarqube -n sonarqube      # SonarQube"
echo "  oc get route app-platform-listener -n app-platform-build  # webhook URL"
echo ""
