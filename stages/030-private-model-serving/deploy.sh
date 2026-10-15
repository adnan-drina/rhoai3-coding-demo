#!/usr/bin/env bash
# Publish native KServe/discovery only; never repoint Stage 010 or seed models.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$ROOT_DIR/scripts/shared/lib.sh"
REPO_ROOT="${RHOAI_ENV_ROOT:-$ROOT_DIR}"
load_env
check_oc_logged_in
require_env GIT_REPO_URL "reviewed Stage 030 source repository"
assert_required_env
ref="${GIT_REPO_BRANCH:-HEAD}"
if [[ "${1:-}" == --revision && $# -eq 2 ]]; then ref="$2"; elif [[ $# -ne 0 ]]; then echo "Usage: $0 [--revision REF]" >&2; exit 1; fi
STAGE_APPS="$ROOT_DIR/scripts/shared/stage_apps.py"
revision=$(python3 "$STAGE_APPS" select 030 --ref "$ref" --repo-url "$GIT_REPO_URL" \
  --extra scripts/platform/require-node-sizing.sh --extra scripts/platform/validate-serving-update.py)
# Read-only prerequisites precede even sizing and the first Application write.
fail() { echo "ERROR: $*" >&2; exit 1; }
read_optional() { oc --request-timeout=10s get "$@" --ignore-not-found -o json; }
REG_NS=rhoai-model-registries
python3 "$STAGE_APPS" status 010 >/dev/null || fail "Stage 010 must be reconciled first"
delegated_dsc=$(python3 "$STAGE_APPS" delegated 010 DataScienceCluster default-dsc --group datasciencecluster.opendatahub.io)
for field in kserve modelregistry; do
  grep -qx "/spec/components/$field" <<<"$delegated_dsc" || fail "Foundation has not delegated /spec/components/$field"
done
delegated_dashboard=$(python3 "$STAGE_APPS" delegated 010 OdhDashboardConfig odh-dashboard-config redhat-ods-applications \
  --group opendatahub.io)
for field in agentsCatalog disableModelCatalog disableModelRegistry toolCalling mcpCatalog mcpRegistry; do
  grep -qx "/spec/dashboardConfig/$field" <<<"$delegated_dashboard" || fail "Foundation has not delegated dashboardConfig.$field"
done
# Existing Application identity and rendered objects (an existing registry namespace must also be tracked).
python3 "$STAGE_APPS" preflight 030 --repo-url "$GIT_REPO_URL"
registry_ns=$(read_optional namespace "$REG_NS")
if [[ -n "$registry_ns" ]]; then
  jq -e '(.metadata.annotations["argocd.argoproj.io/tracking-id"] // "" | startswith("030-private-model-serving:"))
    and .metadata.deletionTimestamp == null' <<<"$registry_ns" >/dev/null || fail "Registry namespace is not owned by Stage 030"
fi
# Existing deployments keep their native registry database; a partial leftover forbids a clean recreation.
registry_crd=$(read_optional customresourcedefinition modelregistries.modelregistry.opendatahub.io)
registry=""
[[ -n "$registry_crd" ]] && registry=$(read_optional modelregistries.modelregistry.opendatahub.io demo-registry -n "$REG_NS")
claim=$(read_optional pvc demo-registry-postgres-storage -n "$REG_NS")
credential=$(read_optional secret demo-registry-postgres-credentials -n "$REG_NS" | jq -c '{metadata}' 2>/dev/null || true)
if [[ -n "$registry" ]]; then
  expected_spec=$(ruby -ryaml -rjson -e 'puts JSON.generate(YAML.load_file(ARGV[0])["spec"])' \
    "$ROOT_DIR/gitops/stages/030-private-model-serving/030-private-model-serving/model-discovery/registry/modelregistry-demo.yaml")
  jq -e --argjson spec "$expected_spec" '.spec == $spec' <<<"$registry" >/dev/null ||
    fail "Existing registry native spec differs from reviewed source"
  uid=$(jq -r '.metadata.uid' <<<"$registry")
  controlled='any(.metadata.ownerReferences[]?; .uid == $uid and .controller == true)'
  [[ -n "$claim" ]] && jq -e --arg uid "$uid" ".metadata.deletionTimestamp == null and .status.phase == \"Bound\" and $controlled" \
    <<<"$claim" >/dev/null || fail "Existing registry database missing or foreign"
  [[ -n "$credential" ]] && jq -e --arg uid "$uid" "$controlled" <<<"$credential" >/dev/null ||
    fail "Existing registry credential missing or foreign"
elif [[ -n "$claim" || -n "$credential" ]]; then
  fail "Partial retained registry database forbids clean recreation"
fi
# Platform monitoring configuration belongs to 010-observability-operators.
for config in openshift-monitoring/cluster-monitoring-config openshift-user-workload-monitoring/user-workload-monitoring-config; do
  cm=$(read_optional configmap "${config#*/}" -n "${config%%/*}")
  [[ -z "$cm" ]] || jq -e '.metadata.annotations["argocd.argoproj.io/tracking-id"] // ""
    | startswith("010-observability-operators:")' <<<"$cm" >/dev/null ||
    fail "Platform monitoring configuration must be owned by 010-observability-operators"
done
oc --request-timeout=10s get storageclass gp3-csi -o jsonpath='{.provisioner}' | grep -qx ebs.csi.aws.com ||
  fail "Reviewed native monitoring storage class unavailable"
oc --request-timeout=10s get namespace redhat-ods-applications openshift-gitops >/dev/null
echo "PASS Read-only foundation ownership/delegation and native storage prerequisites"
"$SCRIPT_DIR/preflight-agent-catalog.sh"
if [[ -n "$(oc --request-timeout=10s get application 030-private-model-serving -n openshift-gitops --ignore-not-found -o jsonpath='{.metadata.uid}')" ]]; then
  # An existing discovery update must not start deliberately parked GPU capacity.
  python3 "$ROOT_DIR/scripts/platform/validate-serving-update.py" 030
else
  "$ROOT_DIR/stages/020-gpu-infrastructure-private-ai/validate.sh" --readiness
fi
"$ROOT_DIR/scripts/platform/require-node-sizing.sh"
# First change: this stage's own Application at the reviewed commit; deploy applies, syncs and waits for it.
python3 "$STAGE_APPS" deploy 030 --revision "$revision" --repo-url "$GIT_REPO_URL"
for _ in $(seq 1 120); do
  if "$SCRIPT_DIR/validate.sh"; then exit 0; fi
  sleep 5
done
echo "ERROR: native Stage 030 service readiness timed out after Application reconciliation." >&2
exit 1
