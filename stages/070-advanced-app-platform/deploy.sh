#!/usr/bin/env bash
# Stage 070: native GitOps developer-platform installation.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/shared/lib.sh"
STAGE_NAME="070-advanced-app-platform"
load_env
check_oc_logged_in
if [[ "${1:-}" == --revision && $# -eq 2 ]]; then
  GIT_REPO_BRANCH="$2"
elif [[ $# -ne 0 ]]; then
  echo "Usage: $0 [--revision <published ref or commit>]" >&2; exit 1
fi
require_env GIT_REPO_URL "reviewed Stage 070 source repository"
assert_required_env
REVISION=$(python3 "$SCRIPT_DIR/application.py" select --revision "${GIT_REPO_BRANCH:-HEAD}" --repo-url "$GIT_REPO_URL")
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

# This release is for a fresh install. Do not allow an old realm namespace
# to disappear through pruning or put PostgreSQL 16 onto a known PG15 volume.
LEGACY_REALM=$(oc get namespace rhbk --ignore-not-found -o jsonpath='{.metadata.name}')
if [[ -n "$LEGACY_REALM" ]]; then
  log_error "Legacy rhbk namespace exists. Protect/export it and review the realm migration before deploying this fresh-install release."
  exit 1
fi
SONAR_DATABASE_IMAGE=$(oc get deployment postgresql -n sonarqube --ignore-not-found -o jsonpath='{.spec.template.spec.containers[0].image}')
if [[ "$SONAR_DATABASE_IMAGE" == *postgresql-15* ]]; then
  log_error "SonarQube uses PostgreSQL 15. Back up and migrate its data before the PostgreSQL 16 release; an image swap is refused."
  exit 1
fi

# First cluster mutation: install the component Argo CD owners. Publish/review the
# configured source revision before invoking this script; local edits are not
# a deployment source. Credentials and chart migrations are native sync hooks.
# Components deploy one at a time in their deploy order (application.py): sync waves
# order hooks only inside one Application.
python3 "$SCRIPT_DIR/application.py" deploy --revision "$REVISION" --repo-url "$GIT_REPO_URL" --timeout "${STAGE070_SYNC_TIMEOUT:-3600}"

log_info "Argo CD installs identity clients, GitLab/NooBaa storage, Dev Spaces,"
log_info "Pipelines/TAS, SonarQube, Developer Hub and MTA 8.3 with AI components."
log_info "GitLab enrollment owns project listeners and build seeding; Tekton"
log_info "promotes image digests into delivery Git, which Argo CD reconciles."
log_info "Models remain at their operator-selected scale. No model call is made."
log_info "Monitor: oc get applications.argoproj.io -n openshift-gitops -l demo.rhoai.io/stage=070"
log_info "Validate platform: ./stages/${STAGE_NAME}/validate.sh"
log_info "Model/IDE/native-agent validation requires models to be scaled up separately."
