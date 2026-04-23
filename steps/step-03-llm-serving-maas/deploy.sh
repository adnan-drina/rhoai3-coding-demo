#!/usr/bin/env bash
# Step 03: LLM Serving + MaaS - Deploy
# Applies the ArgoCD Application. Kuadrant configuration, Gateway hostname
# patching, and Grafana SA setup are handled by in-cluster Jobs.
# MaaS API Developer Preview is applied separately (remote Kustomize base).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"

STEP_NAME="step-03-llm-serving-maas"

load_env
check_oc_logged_in

log_step "Step 03: LLM Serving + MaaS"

oc apply -f "$REPO_ROOT/gitops/argocd/app-of-apps/${STEP_NAME}.yaml"
log_success "ArgoCD Application '${STEP_NAME}' applied"

# MaaS API Developer Preview (remote Kustomize base, not in ArgoCD)
log_step "Deploying MaaS API (Developer Preview)..."
oc create namespace maas-api 2>/dev/null || true
oc apply -k "$REPO_ROOT/gitops/step-03-llm-serving-maas/base/maas/" 2>/dev/null \
    && log_success "MaaS API applied" \
    || log_warn "MaaS API apply failed (may need cluster-specific patching)"

log_info "ArgoCD handles all orchestration via sync waves:"
log_info "  Wave 0-5:    LWS, RHCL, CNPG, Grafana operators + instances"
log_info "  Wave 10-12:  Kuadrant CR + configuration Job (Authorino TLS)"
log_info "  Wave 15-18:  Gateway, models, RBAC, policies"
log_info "  Wave 20-22:  Grafana dashboard + SA token Job, Gateway hostname Job"

# Patch tier-to-group-mapping to include our demo groups (operator creates defaults)
log_step "Patching tier-to-group-mapping with demo groups..."
for i in $(seq 1 30); do
    if oc get configmap tier-to-group-mapping -n redhat-ods-applications &>/dev/null; then
        TIERS=$(cat <<'TIERS_EOF'
- name: free
  displayName: Free Tier
  level: 0
  groups:
    - tier-free-users
    - system:authenticated
- name: premium
  displayName: Premium Tier
  level: 1
  groups:
    - tier-premium-users
    - rhoai-users
- name: enterprise
  displayName: Enterprise Tier
  level: 2
  groups:
    - tier-enterprise-users
    - rhoai-admins
TIERS_EOF
)
        oc patch configmap tier-to-group-mapping -n redhat-ods-applications \
            --type merge -p "{\"data\":{\"tiers\":$(echo "$TIERS" | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()))')}}" 2>/dev/null \
            && log_success "tier-to-group-mapping patched with rhoai-admins and rhoai-users" \
            || log_warn "Failed to patch tier-to-group-mapping"
        break
    fi
    [ $((i % 10)) -eq 0 ] && log_info "Waiting for tier-to-group-mapping ConfigMap... ($i/30)"
    sleep 10
done

# Wire maas-api to database (operator may not set this automatically)
log_step "Ensuring maas-api has database connection..."
for i in $(seq 1 30); do
    if oc get deployment maas-api -n redhat-ods-applications &>/dev/null && \
       oc get secret maas-db-config -n redhat-ods-applications &>/dev/null; then
        HAS_DB=$(oc get deployment maas-api -n redhat-ods-applications \
            -o jsonpath='{.spec.template.spec.containers[0].env[?(@.name=="DB_CONNECTION_URL")].name}' 2>/dev/null)
        if [ -z "$HAS_DB" ]; then
            oc set env deployment/maas-api -n redhat-ods-applications --from=secret/maas-db-config 2>/dev/null \
                && log_success "DB_CONNECTION_URL added to maas-api" \
                || log_warn "Failed to add DB_CONNECTION_URL"
        else
            log_info "maas-api already has DB_CONNECTION_URL"
        fi
        break
    fi
    [ $((i % 10)) -eq 0 ] && log_info "Waiting for maas-api deployment... ($i/30)"
    sleep 10
done

echo ""
log_info "Monitor progress:"
echo "  oc get application ${STEP_NAME} -n openshift-gitops -w"
echo "  oc get llminferenceservice -n maas"
echo "  oc get kuadrant -n kuadrant-system"
echo ""
