#!/usr/bin/env bash
# Reset the Coolstore demo to its registered starting point, with no trace of earlier runs:
#   - recreate the coolstore-inventory-service workspaces (DevWorkspaces deleted with their storage; 070-devspaces
#     recreates the Argo CD-owned seats from Git, stopped, and the script points them at the GitLab project again);
#   - delete every merge request and every branch except main in rhoai-workloads/coolstore-inventory-service;
#   - put main back on the registered initial commit when it moved: delete the PipelineRuns in coolstore-dev, clear the
#     delivery repository's promotion record (promotion only moves forward along one source history), then recreate
#     main at that commit and protect it as before. Creating main fires one pipeline run that builds and deploys it.
# Without --yes it only prints the plan (read-only) and refuses; safe to rerun (a reset of a clean demo changes nothing
# but the workspaces). Acts as the GitLab user demo-operator, whose token the 070-gitlab bootstrap keeps in Secret
# gitlab-system/gitlab-demo-operator (never in a developer workspace).
# Usage: stages/070-advanced-app-platform/demo-reset/reset-coolstore.sh [--yes]
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"
CONFIRMED=false
case "$*" in
  "") ;;
  --yes) CONFIRMED=true ;;
  *) sed -n 's/^# Usage: //p' "$0" >&2; exit 1 ;;
esac
load_env
check_oc_logged_in
source "$SCRIPT_DIR/lifecycle.sh"
NAME=coolstore-inventory-service
GITOPS_NS=openshift-gitops
SEAT_APP=070-devspaces
TEMP_BRANCH=demo-reset-baseline

# ── Read-only: registration, project identity, workspaces, GitLab history, pipeline history ───────────────────────────
log_step "Coolstore demo reset: plan"
lifecycle_read_platform
lifecycle_read_registration "$NAME"
[[ -n "$REGISTRATION" ]] || die "coolstore-dev has no project-registration; deploy Stage 070 first"
lifecycle_read_token
lifecycle_check_project reset-coolstore "$NAME"
[[ $(printf '%s' "$PROJECT" | jq -r '.archived // false') != true ]] || die "Archived project cannot be reset"
lifecycle_read_delivery "$NAME"
[[ -n "$DELIVERY" ]] || die "Delivery repository $NAME-deployment is missing"
PID=$(printf '%s' "$PROJECT" | jq -r '.id')
DID=$(printf '%s' "$DELIVERY" | jq -r '.id')
REPO_URL=$(printf '%s' "$PROJECT" | jq -r '.http_url_to_repo')
BASELINE=$(printf '%s' "$REGISTRATION" | jq -r '.initial_commit')
gitlab GET "projects/$PID/repository/commits/$BASELINE" >/dev/null
HEAD=$(gitlab GET "projects/$PID/repository/branches/main" | jq -r '.commit.id')
PROTECTION=$(gitlab GET "projects/$PID/protected_branches/main")
BRANCHES=$(gitlab GET "projects/$PID/repository/branches?per_page=100" | jq -r '.[].name | select(. != "main")')
MRS=$(gitlab GET "projects/$PID/merge_requests?state=all&per_page=100" | jq -r '.[].iid')
PROMOTION=$(gitlab GET "projects/$DID/repository/files/promotion.json?ref=main" | jq -c '.content | @base64d | fromjson')
WORKSPACES=$(lifecycle_matching_workspaces)
# Seats Argo CD recreates: the matching workspaces that 070-devspaces tracks.
SEATS=$(while read -r namespace name; do
  [[ -n "$name" ]] || continue
  oc get devworkspace "$name" -n "$namespace" -o json | jq -r --arg app "$SEAT_APP" \
    'select((.metadata.annotations["argocd.argoproj.io/tracking-id"] // "") | startswith($app + ":"))
     | "\(.metadata.namespace) \(.metadata.name)"'
done <<<"$WORKSPACES")
RUNS=$(oc get pipelinerun -n coolstore-dev -o name)

log_info "Project:    $GITLAB_WORKLOAD_GROUP/$NAME (GitLab id $PID)"
log_info "Baseline:   registered commit ${BASELINE:0:12}; main is at ${HEAD:0:12}$([[ "$HEAD" == "$BASELINE" ]] && echo ' (unchanged)')"
while read -r namespace name; do
  [[ -z "$name" ]] || log_info "Workspace:  delete $namespace/$name$(grep -qx "$namespace $name" <<<"$SEATS" && echo '; 070-devspaces recreates it stopped')"
done <<<"$WORKSPACES"
log_info "GitLab:     delete $(grep -c . <<<"$MRS" || true) merge request(s) and branch(es): $(tr '\n' ' ' <<<"$BRANCHES")"
if [[ "$HEAD" != "$BASELINE" ]]; then
  log_info "Pipelines:  delete $(grep -c . <<<"$RUNS" || true) PipelineRun(s) in coolstore-dev"
  log_info "Delivery:   reset promotion.json in $(printf '%s' "$DELIVERY" | jq -r '.path_with_namespace') (now ${PROMOTION:0:80})"
  log_info "Rewind:     recreate main at ${BASELINE:0:12}, protection as now; one pipeline run then deploys the baseline"
fi
if [[ "$CONFIRMED" != true ]]; then
  log_error "Pass --yes after reviewing the plan. Deleted workspaces, branches and merge requests cannot be recovered."
  exit 1
fi

# ── Writes ───────────────────────────────────────────────────────────────────────────────────────────────────────
log_step "Coolstore demo reset"
# Workspaces: hold 070-devspaces auto-sync while they are deleted, so Argo CD recreates them only afterwards.
if [[ -n "$WORKSPACES" ]]; then
  AUTOMATED=$(oc get application "$SEAT_APP" -n "$GITOPS_NS" -o json | jq -c '.spec.syncPolicy.automated // empty')
  restore_sync() {
    [[ -z "$AUTOMATED" ]] || oc patch application "$SEAT_APP" -n "$GITOPS_NS" --type=merge \
      -p "{\"spec\":{\"syncPolicy\":{\"automated\":$AUTOMATED}}}" >/dev/null
  }
  trap 'restore_sync; rm -rf "$LIFECYCLE_TMP"' EXIT
  [[ -z "$AUTOMATED" ]] || oc patch application "$SEAT_APP" -n "$GITOPS_NS" --type=json \
    -p '[{"op":"remove","path":"/spec/syncPolicy/automated"}]' >/dev/null
  lifecycle_delete_workspaces "$WORKSPACES"
  restore_sync
  trap 'rm -rf "$LIFECYCLE_TMP"' EXIT
  [[ -n "$AUTOMATED" ]] || log_warn "$SEAT_APP has no auto-sync; sync it to recreate the seats"
  while read -r namespace name; do
    [[ -n "$name" ]] || continue
    for _ in $(seq 1 60); do oc get devworkspace "$name" -n "$namespace" >/dev/null 2>&1 && break; sleep 5; done
    oc get devworkspace "$name" -n "$namespace" >/dev/null 2>&1 || die "$SEAT_APP did not recreate $namespace/$name"
    # Git holds a placeholder origin that the 070-gitlab bootstrap replaces once; restore it on the stopped seat.
    oc patch devworkspace "$name" -n "$namespace" --type=json -p "[{\"op\":\"replace\",
      \"path\":\"/spec/template/projects/0/git/remotes/origin\",\"value\":$(jq -n --arg u "$REPO_URL" '$u')}]" >/dev/null
    log_success "Recreated $namespace/$name (stopped, clones $REPO_URL on its next start)"
  done <<<"$SEATS"
fi
while read -r iid; do
  [[ -z "$iid" ]] || { gitlab DELETE "projects/$PID/merge_requests/$iid" </dev/null >/dev/null; log_success "Deleted merge request !$iid"; }
done <<<"$MRS"
while read -r branch; do
  [[ -n "$branch" ]] || continue
  gitlab DELETE "projects/$PID/repository/branches/$(printf '%s' "$branch" | jq -sRr @uri)" </dev/null >/dev/null
  log_success "Deleted branch $branch"
done <<<"$BRANCHES"
if [[ "$HEAD" == "$BASELINE" ]]; then
  log_success "main is on the registered baseline; nothing to rewind"
  exit 0
fi
# Clean pipeline history; the run for the baseline commit is recreated by the push below.
[[ -z "$RUNS" ]] || oc delete -n coolstore-dev $RUNS --wait=false >/dev/null
log_success "Deleted PipelineRuns in coolstore-dev"
if [[ "$PROMOTION" != "{}" ]]; then
  jq -n -c '{branch: "main", commit_message: "chore: reset promotion for the registered Coolstore baseline",
    actions: [{action: "update", file_path: "promotion.json", content: "{}"}]}' |
    gitlab POST "projects/$DID/repository/commits" >/dev/null
  log_success "Promotion record cleared"
fi
# GitLab has no ref update, and main is the default, protected branch: move the default to a temporary branch at the
# baseline, recreate main there, then restore default and protection.
[[ -n $(gitlab_find "projects/$PID/repository/branches/$TEMP_BRANCH") ]] ||
  jq -n -c --arg b "$TEMP_BRANCH" --arg r "$BASELINE" '{branch: $b, ref: $r}' | gitlab POST "projects/$PID/repository/branches" >/dev/null
jq -n -c --arg b "$TEMP_BRANCH" '{default_branch: $b}' | gitlab PUT "projects/$PID" >/dev/null
gitlab DELETE "projects/$PID/protected_branches/main" </dev/null >/dev/null
gitlab DELETE "projects/$PID/repository/branches/main" </dev/null >/dev/null
jq -n -c --arg r "$BASELINE" '{branch: "main", ref: $r}' | gitlab POST "projects/$PID/repository/branches" >/dev/null
jq -n -c '{default_branch: "main"}' | gitlab PUT "projects/$PID" >/dev/null
printf '%s' "$PROTECTION" | jq -c '{name: "main", allow_force_push: (.allow_force_push // false),
    push_access_level: (.push_access_levels[0].access_level), merge_access_level: (.merge_access_levels[0].access_level)}' |
  gitlab POST "projects/$PID/protected_branches" >/dev/null
gitlab DELETE "projects/$PID/repository/branches/$TEMP_BRANCH" </dev/null >/dev/null
log_success "main recreated at ${BASELINE:0:12} and protected"
for _ in $(seq 1 24); do
  oc get pipelinerun "gitlab-$PID-$BASELINE" -n coolstore-dev >/dev/null 2>&1 && break
  sleep 5
done
if oc get pipelinerun "gitlab-$PID-$BASELINE" -n coolstore-dev >/dev/null 2>&1; then
  log_success "PipelineRun coolstore-dev/gitlab-$PID-$BASELINE builds and deploys the baseline"
else
  log_warn "No PipelineRun for the baseline yet; check the coolstore-dev EventListener"
fi
