#!/usr/bin/env bash
# Retire one registered GitLab project (a template-created application or migration run, never a stage-owned import
# such as Coolstore). In order: an immutable retirement record (ConfigMap retired-project-NAME in app-platform-build),
# stop the DevWorkspaces that clone it, archive the GitLab project (the persistent guard: the reconciler cannot
# recreate its resources), run the platform retirement pipeline for a migration run, then delete its Applications
# project-NAME and runtime-NAME, its cross-namespace grants, delivery reader Secret and listener binding, and its
# namespace. Kept: the GitLab repository (archived), workspace PVCs, delivery history; no GitHub/Quay deletion.
# Without --yes it only prints the plan (read-only) and refuses; safe to rerun (every step accepts the retired state).
# Needs GITLAB_OPERATOR_TOKEN_FILE, a file holding your scoped GitLab operator token.
# Usage: stages/070-advanced-app-platform/demo-reset/delete-project.sh NAME [--yes]
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"
NAME="" CONFIRMED=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --yes) CONFIRMED=true; shift ;;
    -*) sed -n 's/^# Usage: //p' "$0" >&2; exit 1 ;;
    *) [[ -z "$NAME" ]] || { sed -n 's/^# Usage: //p' "$0" >&2; exit 1; }; NAME=$1; shift ;;
  esac
done
[[ -n "$NAME" ]] || { sed -n 's/^# Usage: //p' "$0" >&2; exit 1; }
[[ "$NAME" =~ ^[a-z][a-z0-9-]{2,40}$ ]] || { log_error "Invalid project name"; exit 1; }
load_env
check_oc_logged_in
source "$SCRIPT_DIR/lifecycle.sh"
BUILD_NS=app-platform-build
GITOPS_NS=openshift-gitops

# ── Read-only: registration, project identity, workspaces, retirement record and pipeline ────────────────────────────
log_step "Retire project $NAME: plan"
lifecycle_read_platform
lifecycle_read_registration "$NAME"
lifecycle_read_token
lifecycle_check_project retire "$NAME"
WORKSPACES=$(lifecycle_matching_workspaces)
KIND=$(printf '%s' "$REGISTRATION" | jq -r '.kind')
PROJECT_ID=$(printf '%s' "$PROJECT" | jq -r '.id')
TOMBSTONE=$(lifecycle_tombstone "$NAME")
RECORD=$(oc get configmap "retired-project-$NAME" -n "$BUILD_NS" --ignore-not-found -o json)
if [[ -n "$RECORD" ]]; then
  # An existing record must carry exactly this registration.
  printf '%s' "$RECORD" | jq -e --argjson want "$TOMBSTONE" '(.data // {} | keys) == ["retirement.json"]
    and (.data["retirement.json"] | fromjson) == ($want.data["retirement.json"] | fromjson)' >/dev/null ||
    { log_error "Retirement record identity changed"; exit 1; }
fi
# Retirement PipelineRun of a migration run: identity fixed by the run name, its registered commit and project id.
RUN=$(jq -n -c --arg name "$NAME" --arg commit "$(printf '%s' "$REGISTRATION" | jq -r '.initial_commit')" \
  --arg pid "$PROJECT_ID" '{apiVersion: "tekton.dev/v1", kind: "PipelineRun",
    metadata: {name: ("retire-" + $name), namespace: "app-platform-build"},
    spec: {taskRunTemplate: {serviceAccountName: "migration-run-provisioner"}, pipelineRef: {name: "provision-migration-run"},
      params: [{name: "run-name", value: $name}, {name: "scaffold-commit", value: $commit}, {name: "mode", value: "retire"},
               {name: "request-project-id", value: $pid}]}}')
log_info "Project:    $GITLAB_WORKLOAD_GROUP/$NAME (GitLab id $PROJECT_ID, kind $KIND, namespace $PROJECT_NS)"
log_info "Record:     ConfigMap $BUILD_NS/retired-project-$NAME ($([[ -n "$RECORD" ]] && echo present || echo create))"
while read -r namespace name; do
  [[ -z "$name" ]] || log_info "Stop:       DevWorkspace $namespace/$name"
done <<<"$WORKSPACES"
log_info "Archive:    GitLab project ($([[ $(printf '%s' "$PROJECT" | jq -r '.archived // false') == true ]] && echo already archived || echo archive))"
[[ "$KIND" != migration ]] || log_info "Pipeline:   PipelineRun $BUILD_NS/retire-$NAME (provision-migration-run, mode retire)"
log_info "Delete:     Applications project-$NAME, runtime-$NAME; grants, delivery reader, listener binding; namespace $PROJECT_NS"
if [[ "$CONFIRMED" != true ]]; then
  log_error "Pass --yes after reviewing the registered project and retained data."
  exit 1
fi

# ── Writes ───────────────────────────────────────────────────────────────────────────────────────────────────────
log_step "Retire project $NAME"
if [[ -z "$RECORD" ]]; then
  printf '%s' "$TOMBSTONE" | oc create -f - >/dev/null
  log_success "Retirement record retired-project-$NAME created"
fi
# Stop matching workspaces; retain their PVCs and local changes.
lifecycle_stop_workspaces "$WORKSPACES"
# Archiving is the persistent retirement guard: the reconciler cannot recreate resources for this project, even after
# its namespace is gone.
if [[ $(printf '%s' "$PROJECT" | jq -r '.archived // false') != true ]]; then
  gitlab POST "projects/$PROJECT_ID/archive" </dev/null >/dev/null
  log_success "GitLab project archived"
fi
if [[ "$KIND" == migration ]]; then
  RECORDED=$(oc get pipelinerun "retire-$NAME" -n "$BUILD_NS" --ignore-not-found -o json)
  [[ -n "$RECORDED" ]] || RECORDED=$(printf '%s' "$RUN" | oc create -f - -o json)
  printf '%s' "$RECORDED" | jq -e --argjson want "$RUN" '(.spec.params | map({(.name): .value}) | add)
      == ($want.spec.params | map({(.name): .value}) | add) and .spec.pipelineRef == $want.spec.pipelineRef' >/dev/null ||
    { log_error "Existing retirement PipelineRun has another identity"; exit 1; }
  if printf '%s' "$RECORDED" | jq -e 'any(.status.conditions[]?; .type == "Succeeded" and .status == "False")' >/dev/null; then
    log_error "Retirement pipeline failed; preserve it, repair its cause and review a native retry. Namespace retained."
    exit 1
  fi
  oc wait pipelinerun "retire-$NAME" -n "$BUILD_NS" --for=condition=Succeeded --timeout=600s
fi
for app in "project-$NAME" "runtime-$NAME"; do
  oc delete application "$app" -n "$GITOPS_NS" --ignore-not-found
done
# Child Applications have no destructive finalizers. Remove only their registered cross-namespace grants; repository
# and delivery history remain.
oc delete rolebinding "$NAME.inputs" "$NAME.runs" -n "$BUILD_NS" --ignore-not-found
oc delete role "$NAME.runs" -n "$BUILD_NS" --ignore-not-found
oc delete rolebinding "$NAME.delivery" "$NAME.readback" -n "$GITOPS_NS" --ignore-not-found
oc delete role "$NAME.delivery" "$NAME.readback" -n "$GITOPS_NS" --ignore-not-found
oc delete secret "gitlab-delivery-reader-$NAME" -n "$GITOPS_NS" --ignore-not-found
oc delete clusterrolebinding "$NAME.listener" --ignore-not-found
oc delete namespace "$PROJECT_NS" --ignore-not-found
log_success "Project retired. GitLab repository archived; workspace PVCs and delivery history retained."
