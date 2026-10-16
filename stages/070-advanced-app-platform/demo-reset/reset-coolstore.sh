#!/usr/bin/env bash
# Reset the Coolstore demo: restore the registered GitLab baseline of coolstore-inventory-service with one normal
# commit on main (history kept, no force push) and stop the DevWorkspaces that clone it (their PVCs and local changes
# are kept). The commit fires one expected pipeline run in coolstore-dev. Changes: that commit and spec.started=false
# on the matching workspaces. Without --yes it only prints the plan (read-only) and refuses; safe to rerun (a reset of
# an already restored main commits nothing). Needs GITLAB_OPERATOR_TOKEN_FILE, a file holding your scoped GitLab
# operator token (never part of a developer workspace).
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

# ── Read-only: registration, project identity, workspaces and the restoring commit ─────────────────────────────────
log_step "Coolstore demo reset: plan"
lifecycle_read_platform
lifecycle_read_registration "$NAME"
lifecycle_read_token
lifecycle_check_project reset-coolstore "$NAME"
WORKSPACES=$(lifecycle_matching_workspaces)
lifecycle_reset_actions
INITIAL_COMMIT=$(printf '%s' "$REGISTRATION" | jq -r '.initial_commit')
log_info "Project:    $GITLAB_WORKLOAD_GROUP/$NAME (GitLab id $(printf '%s' "$PROJECT" | jq -r '.id'))"
log_info "Baseline:   registered commit ${INITIAL_COMMIT:0:12}"
log_info "Commit:     $(jq -r 'group_by(.action) | map("\(length) \(.[0].action)") | join(", ") | if . == "" then "none (main matches the baseline)" else . end' \
  "$LIFECYCLE_TMP/actions.json")"
while read -r namespace name; do
  [[ -z "$name" ]] || log_info "Stop:       DevWorkspace $namespace/$name"
done <<<"$WORKSPACES"
if [[ "$CONFIRMED" != true ]]; then
  log_error "Pass --yes after reviewing the registered project and retained data."
  exit 1
fi

# ── Writes: stop the matching workspaces, then one normal commit ─────────────────────────────────────────────────────
log_step "Coolstore demo reset"
lifecycle_stop_workspaces "$WORKSPACES"
if [[ $(jq 'length' "$LIFECYCLE_TMP/actions.json") -gt 0 ]]; then
  RESULT=$(jq -c '{branch: "main", commit_message: "chore: restore registered Coolstore baseline", actions: .}' \
    "$LIFECYCLE_TMP/actions.json" | gitlab POST "projects/$(printf '%s' "$PROJECT" | jq -r '.id')/repository/commits")
  log_success "Baseline restored by normal commit: $(printf '%s' "$RESULT" | jq -r '.id')"
  log_info "One pipeline run for the commit starts in coolstore-dev."
else
  log_success "Repository already matches its registered baseline"
fi
log_info "Workspace data retained. Review local changes before reopening/pulling main."
