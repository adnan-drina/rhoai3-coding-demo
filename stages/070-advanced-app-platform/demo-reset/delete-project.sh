#!/usr/bin/env bash
# Remove one registered GitLab project (a template-created application or migration run, never a stage-owned import
# such as Coolstore) so the demo shows no trace of it and its name can be used again. In order: a retirement record
# (ConfigMap retired-project-NAME in app-platform-build) so an interrupted run can resume, delete the DevWorkspaces that
# clone it (with their storage), archive the GitLab project (the reconciler then cannot recreate its resources), run the
# platform retirement pipeline for a migration run, delete its Applications project-NAME and runtime-NAME, its
# cross-namespace grants, delivery reader Secret, listener binding, workspace scanner credential mirror
# (NAME-sonar-credentials in the persona workspace namespaces) and its namespace, then delete its migration-run receipt
# and lifecycle PipelineRuns, its delivery repository rhoai-delivery/NAME-deployment and the GitLab project itself.
# The Developer Hub catalog drops the component within a minute, once the GitLab discovery provider no longer finds
# it. Its SonarQube project (analysis history) and analysis token go too, and so do its runs stored in Tekton Results
# (the project namespace's runs and the lifecycle PipelineRuns), which the OpenShift console keeps listing otherwise.
# The retirement record goes last. Not touched: GitHub and Quay. A name with nothing registered any more is checked
# for leftovers of an earlier removal (SonarQube project, stored runs) and those are removed.
# Without --yes it only prints the plan (read-only) and refuses; safe to rerun (every step accepts the removed state).
# Acts as the GitLab user demo-operator (token in Secret gitlab-system/gitlab-demo-operator), as the SonarQube
# administrator (Secret sonarqube/sonarqube-admin) and, for Tekton Results, as the logged-in oc user.
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
RUN_NS=wksp-ai-developer

# ── Read-only: registration, project identity, workspaces, retirement record and pipeline ────────────────────────────
log_step "Remove project $NAME: plan"
lifecycle_read_platform
lifecycle_read_registration "$NAME"
lifecycle_read_token
lifecycle_read_sonar
lifecycle_read_sonar_project "$NAME"
lifecycle_open_results
LIFECYCLE_RUNS=("provision-$NAME" "retire-$NAME")
STORED=$(lifecycle_list_results all "$PROJECT_NS"; lifecycle_list_results all "$BUILD_NS" "${LIFECYCLE_RUNS[@]}")
if [[ -z "$REGISTRATION" ]]; then
  [[ -z $(gitlab_find "projects/$(printf '%s' "$GITLAB_WORKLOAD_GROUP/$NAME" | jq -sRr @uri)") ]] ||
    die "GitLab project $GITLAB_WORKLOAD_GROUP/$NAME exists without a registration; inspect it by hand"
  # Only orphans: a run still in the cluster is never removed from the archive here.
  STORED=$(lifecycle_list_results orphans "$PROJECT_NS"; lifecycle_list_results orphans "$BUILD_NS" "${LIFECYCLE_RUNS[@]}")
  if [[ -z "$SONAR_PROJECT$SONAR_TOKENS$STORED" ]]; then
    log_success "Nothing registered under $NAME: already removed"
    exit 0
  fi
  # A project removed before this cleanup existed keeps its Sonar history (a new project of this name would inherit
  # it) and its stored runs.
  [[ -z "$SONAR_PROJECT$SONAR_TOKENS" ]] ||
    log_info "SonarQube:  delete leftover project $NAME$([[ -n "$SONAR_TOKENS" ]] && echo " and token(s) $(tr '\n' ' ' <<<"$SONAR_TOKENS")")"
  [[ -z "$STORED" ]] || log_info "Results:    delete $(grep -c . <<<"$STORED") leftover stored run(s) of $PROJECT_NS and $BUILD_NS/{provision,retire}-$NAME"
  [[ "$CONFIRMED" == true ]] || { log_error "Pass --yes after reviewing the plan."; exit 1; }
  lifecycle_delete_sonar_project "$NAME"
  lifecycle_delete_results "$STORED"
  exit 0
fi
lifecycle_check_project retire "$NAME"
lifecycle_read_delivery "$NAME"
WORKSPACES=$(lifecycle_matching_workspaces)
KIND=$(printf '%s' "$REGISTRATION" | jq -r '.kind')
PROJECT_ID=$(printf '%s' "$REGISTRATION" | jq -r '.project_id')
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
ARCHIVED=$(printf '%s' "$PROJECT" | jq -r '.archived // false')
log_info "Project:    $GITLAB_WORKLOAD_GROUP/$NAME (GitLab id $PROJECT_ID, kind $KIND, namespace $PROJECT_NS)"
log_info "Record:     ConfigMap $BUILD_NS/retired-project-$NAME ($([[ -n "$RECORD" ]] && echo present || echo create); deleted at the end)"
while read -r namespace name; do
  [[ -z "$name" ]] || log_info "Delete:     DevWorkspace $namespace/$name and its storage"
done <<<"$WORKSPACES"
if [[ -z "$PROJECT" ]]; then
  log_info "GitLab:     project already deleted (resuming)"
else
  log_info "Archive:    GitLab project ($([[ "$ARCHIVED" == true ]] && echo already archived || echo archive))"
fi
[[ "$KIND" != migration ]] || log_info "Pipeline:   PipelineRun $BUILD_NS/retire-$NAME (provision-migration-run, mode retire)"
log_info "Delete:     Applications project-$NAME, runtime-$NAME; grants, delivery reader, listener binding, scanner credential mirror; namespace $PROJECT_NS"
[[ "$KIND" != migration ]] || log_info "Delete:     ConfigMap $RUN_NS/migration-run-$NAME; PipelineRuns $BUILD_NS/provision-$NAME, retire-$NAME"
log_info "Delete:     Tekton Results: $(grep -c . <<<"$STORED" || true) stored run(s) of $PROJECT_NS and $BUILD_NS/{provision,retire}-$NAME"
log_info "Delete:     SonarQube project $NAME ($([[ -n "$SONAR_PROJECT" ]] && echo "analysis history" || echo "none")); token(s): $([[ -n "$SONAR_TOKENS" ]] && tr '\n' ' ' <<<"$SONAR_TOKENS" || echo none)"
log_info "Delete:     GitLab delivery repository $(printf '%s' "$DELIVERY" | jq -r '.path_with_namespace // "(none)"')"
[[ -z "$PROJECT" ]] || log_info "Delete:     GitLab project $GITLAB_WORKLOAD_GROUP/$NAME (permanently; the catalog drops it within a minute)"
if [[ "$CONFIRMED" != true ]]; then
  log_error "Pass --yes after reviewing the plan. Deleted repositories and workspaces cannot be recovered."
  exit 1
fi

# ── Writes ───────────────────────────────────────────────────────────────────────────────────────────────────────
log_step "Remove project $NAME"
if [[ -z "$RECORD" ]]; then
  printf '%s' "$TOMBSTONE" | oc create -f - >/dev/null
  log_success "Retirement record retired-project-$NAME created"
fi
lifecycle_delete_workspaces "$WORKSPACES"
# Archiving keeps the reconciler from recreating resources for this project while they are removed.
if [[ -n "$PROJECT" && "$ARCHIVED" != true ]]; then
  gitlab POST "projects/$PROJECT_ID/archive" </dev/null >/dev/null
  log_success "GitLab project archived"
fi
if [[ "$KIND" == migration ]]; then
  RECEIPT=$(oc get configmap "migration-run-$NAME" -n "$RUN_NS" --ignore-not-found -o json)
  # The receipt is deleted only after a successful retirement, so a missing receipt means the pipeline already ran.
  if [[ -n "$RECEIPT" ]]; then
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
fi
for app in "project-$NAME" "runtime-$NAME"; do
  oc delete application "$app" -n "$GITOPS_NS" --ignore-not-found
done
# Child Applications have no destructive finalizers. Remove their registered cross-namespace grants.
oc delete rolebinding "$NAME.inputs" "$NAME.runs" -n "$BUILD_NS" --ignore-not-found
oc delete role "$NAME.runs" -n "$BUILD_NS" --ignore-not-found
oc delete rolebinding "$NAME.delivery" "$NAME.readback" -n "$GITOPS_NS" --ignore-not-found
oc delete role "$NAME.delivery" "$NAME.readback" -n "$GITOPS_NS" --ignore-not-found
oc delete secret "gitlab-delivery-reader-$NAME" -n "$GITOPS_NS" --ignore-not-found
oc delete clusterrolebinding "$NAME.listener" --ignore-not-found
# The reconciler mirrors the project's SonarQube token into the requester's workspace namespace for the scanner.
for ws_ns in "${WORKSPACE_NAMESPACES[@]}"; do
  oc delete secret "$NAME-sonar-credentials" -n "$ws_ns" --ignore-not-found
done
oc delete namespace "$PROJECT_NS" --ignore-not-found
# A migration run's receipt would refuse a new run of the same name; its lifecycle runs are history.
if [[ "$KIND" == migration ]]; then
  oc delete configmap "migration-run-$NAME" -n "$RUN_NS" --ignore-not-found
  oc delete pipelinerun "provision-$NAME" "retire-$NAME" -n "$BUILD_NS" --ignore-not-found
fi
# The archive keeps deleted runs; the project's are orphans now (namespace and lifecycle PipelineRuns are gone).
lifecycle_open_results
STORED=$(lifecycle_list_results orphans "$PROJECT_NS"; lifecycle_list_results orphans "$BUILD_NS" "${LIFECYCLE_RUNS[@]}")
lifecycle_delete_results "$STORED"
# The Sonar project would be reused too: its history moves the new-code period of a new project of the same name.
lifecycle_delete_sonar_project "$NAME"
# The delivery repository would be reused by a new project of the same name, and its promotion record would refuse
# that project's first image (promotion only moves forward along one source history).
[[ -z "$DELIVERY" ]] || lifecycle_delete_gitlab_project "$(printf '%s' "$DELIVERY" | jq -r '.id')"
[[ -z "$PROJECT" ]] || lifecycle_delete_gitlab_project "$PROJECT_ID"
oc delete configmap "retired-project-$NAME" -n "$BUILD_NS" --ignore-not-found
log_success "Project $NAME removed. The name is free for a new project from the Developer Hub template."
