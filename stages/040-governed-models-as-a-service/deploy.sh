#!/usr/bin/env bash
# Stage 040: Governed Models-as-a-Service - Deploy
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"

STAGE_NAME="040-governed-models-as-a-service"

load_env
check_oc_logged_in

log_step "Stage 040: Governed Models-as-a-Service"

oc apply -f "$REPO_ROOT/gitops/argocd/app-of-apps/${STAGE_NAME}.yaml"
log_success "ArgoCD Application '${STAGE_NAME}' applied"

log_info "ArgoCD handles orchestration via sync waves:"
log_info "  Wave 0-10:   Connectivity Link, CNPG, Grafana, Kuadrant, Authorino"
log_info "  Wave 12-14:  upstream MaaS controller, PostgreSQL, RBAC"
log_info "  Wave 15-18:  local MaaSModelRefs, auth policy, subscription"
log_info "  Wave 20-22:  gateway hostname, Grafana datasource, maas-api patch"
echo ""
log_info "Monitor progress:"
echo "  oc get application ${STAGE_NAME} -n openshift-gitops -w"
echo "  oc get maasmodelref -n maas"
echo "  oc get maasauthpolicy,maassubscription -n models-as-a-service"
echo ""
log_info "Stage validation runs a short GuideLLM MaaS load test by default when a MaaS API key is available."
log_info "Tune it with GUIDELLM_MODEL, GUIDELLM_PROFILE, GUIDELLM_RATE, GUIDELLM_MAX_SECONDS, GUIDELLM_REQUESTS, and GUIDELLM_DATA."
log_info "Set GUIDELLM_SKIP_LOAD_TEST=true to skip the load test during validation."
