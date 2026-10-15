#!/usr/bin/env bash
# Stage 070: the developer platform (identity clients, GitLab and its NooBaa storage, Dev Spaces, Pipelines and
# Trusted Artifact Signer, SonarQube, Developer Hub, MTA 8.3 with its AI components) at one reviewed published
# revision. Read-only preconditions first; the components deploy sequentially (deploy-mode sequential). Credentials and
# chart migrations are native sync hooks; models stay at their operator-selected scale and no model call is made.
# STAGE070_RESYNC=true re-runs every component's hooks; STAGE070_SYNC_TIMEOUT sets the per-component wait (s).
# Usage: stages/070-advanced-app-platform/deploy.sh [--revision <published ref or commit>]
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"
STAGE_NAME="070-advanced-app-platform"
load_env
check_oc_logged_in
if [[ "${1:-}" == --revision && $# -eq 2 ]]; then
  GIT_REPO_BRANCH="$2"
elif [[ $# -ne 0 ]]; then
  sed -n 's/^# Usage: //p' "$0" >&2; exit 1
fi
require_env GIT_REPO_URL "reviewed Stage 070 source repository"
assert_required_env
STAGE_APPS="$REPO_ROOT/scripts/stage-apps.sh"
REVISION=$("$STAGE_APPS" select 070 --ref "${GIT_REPO_BRANCH:-HEAD}" --repo-url "$GIT_REPO_URL" \
  --extra stages/120-ai-agentic-development/scaffold-repo/agentic-quarkus-scaffold \
  --extra stages/130-ai-autonomous-migration/scaffold-repo/quarkus-migration-scaffold)
# The GitLab hub publishes those two goldens from this revision, so they must be the reviewed, published source too.
require_node_sizing
# Read-only: the Automatic Dev Spaces Subscription (openshift-operators) offers the reviewed channel and minimum.
check_operator_policy "$REPO_ROOT/gitops/stages/070-advanced-app-platform/070-devspaces"

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
oc get configs.imageregistry.operator.openshift.io cluster -o json | jq -e '.spec.storage | type == "object" and length > 0 and (has("emptyDir") | not)' >/dev/null ||
  { log_error "Internal registry must declare persistent storage; emptyDir or absent storage is refused."; exit 1; }
oc get storageclass gp3-csi -o json | jq -e '.metadata.annotations["storageclass.kubernetes.io/is-default-class"] == "true"' >/dev/null ||
  { log_error "gp3-csi must be the default: MTA 8.3 uses default-class RWO claims; rwo_storage_class is not a supported parameter."; exit 1; }
oc get storageclass openshift-storage.noobaa.io >/dev/null
oc get route s3 -n openshift-storage >/dev/null
oc get keycloak keycloak -n keycloak -o json | jq -e 'any(.status.conditions[]?; .type == "Ready" and .status == "True")' >/dev/null ||
  { log_error "Existing keycloak/keycloak must be Ready; do not create a second identity service."; exit 1; }
oc get crd sandboxes.agents.x-k8s.io >/dev/null

# This release is for a fresh install. Do not allow an old realm namespace
# to disappear through pruning or put PostgreSQL 16 onto a known PG15 volume.
LEGACY_REALM=$(oc get namespace rhbk --ignore-not-found -o jsonpath='{.metadata.name}')
if [[ -n "$LEGACY_REALM" ]]; then
  log_error "Legacy rhbk namespace exists. Protect/export it and review the realm migration before deploying this fresh-install release."
  exit 1
fi
SONAR_DATABASE_IMAGE=$(oc get deployment sonardb -n sonarqube --ignore-not-found -o jsonpath='{.spec.template.spec.containers[0].image}')
if [[ "$SONAR_DATABASE_IMAGE" == *postgresql-15* ]]; then
  log_error "SonarQube uses PostgreSQL 15. Back up and migrate its data before the PostgreSQL 16 release; an image swap is refused."
  exit 1
fi

# First cluster mutation: install the component Argo CD owners. Publish/review the
# configured source revision before invoking this script; local edits are not
# a deployment source. Credentials and chart migrations are native sync hooks.
# The components declare deploy-mode sequential: each is applied, synced and waited for before the next, because
# sync waves order hooks only inside one Application. A component already synced at this commit is not re-synced;
# pass STAGE070_RESYNC=true to re-run every component's hooks.
"$STAGE_APPS" deploy 070 --revision "$REVISION" --repo-url "$GIT_REPO_URL" \
  --timeout "${STAGE070_SYNC_TIMEOUT:-3600}" ${STAGE070_RESYNC:+--resync}

log_info "Argo CD installs identity clients, GitLab/NooBaa storage, Dev Spaces,"
log_info "Pipelines/TAS, SonarQube, Developer Hub and MTA 8.3 with AI components."
log_info "GitLab enrollment owns project listeners and build seeding; Tekton"
log_info "promotes image digests into delivery Git, which Argo CD reconciles."
log_info "Models remain at their operator-selected scale. No model call is made."
log_info "Monitor: oc get applications.argoproj.io -n openshift-gitops -l demo.rhoai.io/stage=070"
log_info "Validate platform: ./stages/${STAGE_NAME}/validate.sh"
log_info "Model/IDE/native-agent validation requires models to be scaled up separately."
