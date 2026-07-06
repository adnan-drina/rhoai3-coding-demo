#!/usr/bin/env bash
# Audit that the active demo no longer depends on retired MaaS workarounds.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

source "$REPO_ROOT/scripts/lib.sh"

load_env
check_oc_logged_in

PASS=0
WARN=0
FAIL=0

pass() {
  echo -e "${GREEN}[PASS]${NC} $1"
  PASS=$((PASS + 1))
}

warn() {
  echo -e "${YELLOW}[WARN]${NC} $1"
  WARN=$((WARN + 1))
}

fail() {
  echo -e "${RED}[FAIL]${NC} $1"
  if [[ -n "${2:-}" ]]; then
    printf '%s\n' "$2" | sed 's/^/  /'
  fi
  FAIL=$((FAIL + 1))
}

require_oc() {
  if ! command -v oc >/dev/null 2>&1; then
    fail "OpenShift CLI is available" "oc command not found"
    return 1
  fi
}

no_output_check() {
  local label="$1"
  local cmd="$2"
  local output

  output="$(eval "$cmd" 2>/dev/null || true)"
  if [[ -z "$output" ]]; then
    pass "$label"
  else
    fail "$label" "$output"
  fi
}

echo "MaaS cleanup audit"
echo ""

log_step "Local GitOps manifests"
no_output_check "Active MaaS GitOps manifests do not reference retired 3.3 or hybrid resources" \
  "rg -n 'maas-controller-upstream|tokens-bridge|maas-api-tokens|tier-to-group-mapping|alpha\\.maas\\.opendatahub\\.io/tiers|quay\\.io/opendatahub/maas-api|tier-free-users|tier-premium-users|tier-enterprise-users' '$REPO_ROOT/gitops/stages/030-private-model-serving' '$REPO_ROOT/gitops/stages/040-governed-models-as-a-service' '$REPO_ROOT/gitops/stages/050-approved-external-model-access'"

if ! require_oc; then
  echo ""
  echo "AUDIT: ${PASS} passed, ${WARN} warnings, ${FAIL} failed"
  exit 1
fi

log_step "Cluster retired MaaS resources"
no_output_check "No tokens-bridge or legacy token route resources are live" \
  "oc get deploy,svc,route,httproute,authpolicy,configmap,secret -A --no-headers | rg -i 'tokens-bridge|maas-api-tokens'"
no_output_check "No 3.3 tier mapping ConfigMap is live" \
  "oc get configmap -A --no-headers | rg -i 'tier-to-group-mapping'"
no_output_check "No 3.3 tier OpenShift groups are live" \
  "oc get group --no-headers | awk '{print \$1}' | rg '^tier-'"
no_output_check "No upstream MaaS controller or image override is live" \
  "oc get deployment -A -o jsonpath='{range .items[*]}{.metadata.namespace}{\"/\"}{.metadata.name}{\"\\t\"}{range .spec.template.spec.containers[*]}{.image}{\" \"}{end}{\"\\n\"}{end}' | rg -i 'maas-controller-upstream|tokens-bridge|quay\\.io/opendatahub/maas-api'"
no_output_check "Old community Grafana namespace is not live" \
  "oc get namespace grafana --no-headers"
no_output_check "Old community Grafana monitoring binding is not live" \
  "oc get clusterrolebinding grafana-sa-cluster-monitoring-view --no-headers"

log_step "Current MaaS ownership"
MAAS_API_IMAGE="$(oc get deployment maas-api -n redhat-ods-applications -o jsonpath='{.spec.template.spec.containers[0].image}' 2>/dev/null || true)"
MAAS_CONTROLLER_IMAGE="$(oc get deployment maas-controller -n redhat-ods-applications -o jsonpath='{.spec.template.spec.containers[0].image}' 2>/dev/null || true)"
MAAS_IMAGES="$(printf 'maas-api=%s\nmaas-controller=%s\n' "$MAAS_API_IMAGE" "$MAAS_CONTROLLER_IMAGE")"
if [[ "$MAAS_API_IMAGE" == *"registry.redhat.io/rhoai/odh-maas-api-rhel9"* && "$MAAS_CONTROLLER_IMAGE" == *"registry.redhat.io/rhoai/odh-maas-controller-rhel9"* ]]; then
  pass "MaaS API and controller are operator-owned Red Hat images"
else
  fail "MaaS API and controller are operator-owned Red Hat images" "$MAAS_IMAGES"
fi

SUBSCRIPTION_GROUPS="$(oc get maassubscription demo-models-subscription -n models-as-a-service -o jsonpath='{.spec.owner.groups[*].name}' 2>/dev/null || true)"
if [[ "$SUBSCRIPTION_GROUPS" == *"rhoai-users"* && "$SUBSCRIPTION_GROUPS" != *"tier-"* ]]; then
  pass "Demo MaaSSubscription uses RHOAI groups instead of 3.3 tiers"
else
  fail "Demo MaaSSubscription uses RHOAI groups instead of 3.3 tiers" "$SUBSCRIPTION_GROUPS"
fi

log_step "Residual cluster-wide CRDs"
GRAFANA_CR_INSTANCES="$(oc get grafanas,grafanadashboards,grafanadatasources,grafanafolders,grafanaalertrulegroups,grafanacontactpoints,grafananotificationpolicies,grafananotificationpolicyroutes,grafananotificationtemplates,grafanalibrarypanels,grafanamanifests,grafanaserviceaccounts -A --no-headers 2>/dev/null || true)"
if [[ -z "$GRAFANA_CR_INSTANCES" ]]; then
  pass "No community Grafana custom resources are live"
else
  fail "No community Grafana custom resources are live" "$GRAFANA_CR_INSTANCES"
fi

GRAFANA_CRDS="$(oc get crd --no-headers 2>/dev/null | awk '{print $1}' | rg '^grafana.*\.grafana\.integreatly\.org$' || true)"
if [[ -n "$GRAFANA_CRDS" ]]; then
  warn "Community Grafana CRDs remain installed cluster-wide; no Grafana instances are live"
else
  pass "Community Grafana CRDs are absent"
fi

echo ""
echo "AUDIT: ${PASS} passed, ${WARN} warnings, ${FAIL} failed"

if [[ "$FAIL" -gt 0 ]]; then
  exit 1
fi
