#!/usr/bin/env bash
# Delete a scaffolded golden-path project end to end, so it can be
# recreated cleanly from the RHDH template. Surfaces covered:
#
#   1. Dev Spaces factory workspace(s) whose project points at the repo
#   2. (--wipe-volume) the per-user common PVC — WARNING: wipes the
#      project volumes of ALL workspaces in the user namespace
#   3. RHDH catalog Location (entity follows via orphan delete strategy)
#   4. Argo CD Application project-<name> and the <name>-dev namespace
#   5. SonarQube project history
#   6. GitHub repository (needs delete_repo scope; warns if denied)
#   7. Quay repository (robot usually lacks admin; prints manual URL)
#
# Usage:
#   ./scripts/delete-scaffolded-project.sh <name> [--yes] [--wipe-volume] [--keep-repo]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"

REPO_OWNER="${REPO_OWNER:-adnan-drina}"
WORKSPACE_NS="${WORKSPACE_NS:-wksp-ai-developer}"
QUAY_ORG="${QUAY_ORG:-rhoai3-coding-demo}"

NAME="${1:-}"
[[ -z "$NAME" || "$NAME" == --* ]] && { log_error "Usage: $0 <name> [--yes] [--wipe-volume] [--keep-repo]"; exit 1; }
shift
FLAG_YES=false; FLAG_WIPE=false; FLAG_KEEP_REPO=false
for arg in "$@"; do
  case "$arg" in
    --yes)         FLAG_YES=true ;;
    --wipe-volume) FLAG_WIPE=true ;;
    --keep-repo)   FLAG_KEEP_REPO=true ;;
    *) log_error "Unknown flag: $arg"; exit 1 ;;
  esac
done

load_env
check_oc_logged_in

log_step "Deleting scaffolded project '${NAME}'"
echo "  repo:       ${REPO_OWNER}/${NAME} $($FLAG_KEEP_REPO && echo '(KEPT)')"
echo "  namespace:  ${NAME}-dev + Argo app project-${NAME}"
echo "  workspace:  factory workspace(s) in ${WORKSPACE_NS}"
$FLAG_WIPE && echo "  volume:     claim-devworkspace in ${WORKSPACE_NS} (ALL workspace volumes!)"
if [[ "$FLAG_YES" != "true" ]]; then
  read -r -p "Continue? [y/N] " ans
  [[ "$ans" == "y" || "$ans" == "Y" ]] || exit 0
fi

# --- 1. Factory workspaces referencing the repo ---
log_step "Dev Spaces workspaces"
# macOS ships bash 3.2 (no mapfile) — stay portable.
WORKSPACES=$(oc get devworkspace -n "$WORKSPACE_NS" -o json \
  | jq -r --arg r "/${NAME}" '.items[] | select([.spec.template.projects[]?.git.remotes.origin // ""] | any(endswith($r) or endswith($r + ".git"))) | .metadata.name')
if [[ -z "$WORKSPACES" ]]; then
  log_info "No workspace references ${NAME}"
else
  for ws in $WORKSPACES; do
    oc patch devworkspace "$ws" -n "$WORKSPACE_NS" --type merge -p '{"spec":{"started":false}}' >/dev/null 2>&1 || true
    oc delete devworkspace "$ws" -n "$WORKSPACE_NS" --wait=true
    log_success "Deleted workspace ${ws}"
  done
fi

# --- 2. Optional volume wipe ---
if [[ "$FLAG_WIPE" == "true" ]]; then
  log_step "Wiping per-user workspace volume (${WORKSPACE_NS})"
  for i in $(seq 1 30); do
    [[ "$(oc get pods -n "$WORKSPACE_NS" --no-headers 2>/dev/null | grep -c '^workspace' || true)" == "0" ]] && break
    sleep 5
  done
  oc delete pvc claim-devworkspace -n "$WORKSPACE_NS" --wait=false 2>/dev/null || log_info "PVC already absent"
  # Completed job/cleanup pods hold pvc-protection — clear them.
  oc get pods -n "$WORKSPACE_NS" --no-headers 2>/dev/null \
    | awk '/Completed|Succeeded/{print $1}' \
    | xargs -r oc delete pod -n "$WORKSPACE_NS" >/dev/null 2>&1 || true
  for i in $(seq 1 36); do
    oc get pvc claim-devworkspace -n "$WORKSPACE_NS" >/dev/null 2>&1 || break
    sleep 5
  done
  oc get pvc claim-devworkspace -n "$WORKSPACE_NS" >/dev/null 2>&1 \
    && log_warn "PVC still terminating — check holder pods" \
    || log_success "Workspace volume deleted"
fi

# --- 3. RHDH catalog Location (entity follows via orphan delete) ---
log_step "RHDH catalog"
LOC_IDS=$(oc exec -n rhdh backstage-psql-developer-hub-0 -- psql -d backstage_plugin_catalog -tAc \
  "select id from locations where target like '%/${NAME}/%'" 2>/dev/null || true)
if [[ -z "$LOC_IDS" ]]; then
  log_info "No catalog Location references ${NAME}"
else
  # No externalAccess API token is provisioned, so the Location row is
  # removed directly; the catalog's orphan strategy (delete) removes the
  # entity on the next processing loop (~2 min).
  for id in $LOC_IDS; do
    oc exec -n rhdh backstage-psql-developer-hub-0 -- psql -d backstage_plugin_catalog -c \
      "delete from locations where id='${id}'" >/dev/null
    log_success "Deleted catalog Location ${id}"
  done
  log_info "Component entity disappears on the next catalog processing cycle"
fi

# --- 4. Argo app + project namespace ---
log_step "Argo CD application and namespace"
oc delete application "project-${NAME}" -n openshift-gitops --wait=false 2>/dev/null \
  && log_success "Deleted Argo app project-${NAME}" || log_info "Argo app already absent"
oc delete ns "${NAME}-dev" --wait=false 2>/dev/null \
  && log_success "Namespace ${NAME}-dev deletion started" || log_info "Namespace already absent"

# --- 5. SonarQube project ---
log_step "SonarQube"
SONAR_USER=$(oc get secret sonarqube-admin -n sonarqube -o jsonpath='{.data.username}' 2>/dev/null | base64 -d || true)
SONAR_PASS=$(oc get secret sonarqube-admin -n sonarqube -o jsonpath='{.data.password}' 2>/dev/null | base64 -d || true)
SONAR_HOST=$(oc get route sonarqube -n sonarqube -o jsonpath='{.spec.host}' 2>/dev/null || true)
if [[ -n "$SONAR_USER" && -n "$SONAR_HOST" ]]; then
  HTTP_CODE=$(curl -sk -o /dev/null -w '%{http_code}' -u "${SONAR_USER}:${SONAR_PASS}" \
    -X POST "https://${SONAR_HOST}/api/projects/delete?project=${NAME}")
  case "$HTTP_CODE" in
    204|404) log_success "SonarQube project clean (${HTTP_CODE})" ;;
    *)       log_warn "SonarQube delete returned HTTP ${HTTP_CODE}" ;;
  esac
else
  log_warn "SonarQube credentials/route not found — skipping"
fi

# --- 6. GitHub repository ---
if [[ "$FLAG_KEEP_REPO" != "true" ]]; then
  log_step "GitHub repository"
  if gh repo delete "${REPO_OWNER}/${NAME}" --yes 2>/dev/null; then
    log_success "Deleted ${REPO_OWNER}/${NAME}"
  else
    log_warn "Could not delete ${REPO_OWNER}/${NAME} (PAT lacks delete_repo scope?)"
    log_warn "Delete manually: https://github.com/${REPO_OWNER}/${NAME}/settings"
  fi
fi

# --- 7. Quay repository ---
log_step "Quay"
if [[ -n "${QUAY_ROBOT_TOKEN:-}" ]]; then
  HTTP_CODE=$(curl -s -o /dev/null -w '%{http_code}' \
    -H "Authorization: Bearer ${QUAY_ROBOT_TOKEN}" \
    -X DELETE "https://quay.io/api/v1/repository/${QUAY_ORG}/${NAME}")
  case "$HTTP_CODE" in
    204|404) log_success "Quay repository clean (${HTTP_CODE})" ;;
    *) log_warn "Quay delete returned ${HTTP_CODE} (robot lacks admin?) — delete manually: https://quay.io/repository/${QUAY_ORG}/${NAME}?tab=settings" ;;
  esac
else
  log_info "QUAY_ROBOT_TOKEN unset — skipping (repo may not exist anyway)"
fi

log_step "Done"
echo "  Recreate anytime from the RHDH template (Create → agentic-quarkus-scaffold)."
