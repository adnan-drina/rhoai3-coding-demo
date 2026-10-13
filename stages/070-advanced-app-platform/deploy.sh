#!/usr/bin/env bash
# Stage 070: native GitOps developer-platform installation.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/shared/lib.sh"
STAGE_NAME="070-advanced-app-platform"
load_env
check_oc_logged_in
"$REPO_ROOT/scripts/platform/require-node-sizing.sh"

log_step "Stage 070: GitLab and advanced application platform"
# Preconditions are read-only. Do not generate shared GitHub credentials or
# start models/workspaces. Native hooks own the scoped integration identities.
REGISTRY_AVAILABLE=$(oc get clusteroperator image-registry \
  -o jsonpath='{.status.conditions[?(@.type=="Available")].status}')
REGISTRY_MANAGED=$(oc get configs.imageregistry.operator.openshift.io cluster \
  -o jsonpath='{.spec.managementState}')
if [[ "$REGISTRY_AVAILABLE" != True || "$REGISTRY_MANAGED" != Managed ]]; then
  log_error "Internal registry must be Managed and Available before deployment."
  exit 1
fi
oc get configs.imageregistry.operator.openshift.io cluster -o json | python3 -c '
import json, sys
storage = json.load(sys.stdin).get("spec", {}).get("storage", {})
if not isinstance(storage, dict) or not storage or "emptyDir" in storage:
    sys.exit("Internal registry must declare persistent storage; emptyDir or absent storage is refused.")
'
oc get storageclass gp3-csi -o json | python3 -c '
import json,sys
annotations=json.load(sys.stdin)["metadata"].get("annotations",{})
if annotations.get("storageclass.kubernetes.io/is-default-class") != "true":
    sys.exit("gp3-csi must be the default: MTA 8.3 uses default-class RWO claims; rwo_storage_class is not a supported parameter.")
'
oc get storageclass openshift-storage.noobaa.io >/dev/null
oc get route s3 -n openshift-storage >/dev/null
oc get keycloak keycloak -n keycloak -o json | python3 -c '
import json,sys
conditions=json.load(sys.stdin).get("status",{}).get("conditions",[])
if not any(c.get("type")=="Ready" and c.get("status")=="True" for c in conditions):
    sys.exit("Existing keycloak/keycloak must be Ready; do not create a second identity service.")
'
oc get crd sandboxes.agents.x-k8s.io >/dev/null

# First cluster mutation: install the single Argo CD owner. Publish/review the
# configured source revision before invoking this script; local edits are not
# a deployment source. Credentials and chart migrations are native sync hooks.
apply_stage_app "$STAGE_NAME"

log_info "Argo CD installs identity clients, GitLab/NooBaa storage, Dev Spaces,"
log_info "Pipelines/TAS, SonarQube, Developer Hub and MTA 8.3 with AI components."
log_info "GitLab enrollment owns project listeners and build seeding; Tekton"
log_info "promotes image digests into delivery Git, which Argo CD reconciles."
log_info "Models remain at their operator-selected scale. No model call is made."
log_info "Monitor: oc get application ${STAGE_NAME} -n openshift-gitops"
log_info "Validate platform: ./stages/${STAGE_NAME}/validate.sh"
log_info "Model/IDE/native-agent validation requires models to be scaled up separately."
