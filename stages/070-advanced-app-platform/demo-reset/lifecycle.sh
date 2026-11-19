#!/usr/bin/env bash
# Shared steps of the GitLab project lifecycle task scripts reset-coolstore.sh and delete-project.sh; sourced by them
# after scripts/lib.sh, load_env and check_oc_logged_in, never run on its own. The readers cover the platform GitLab
# configuration, the immutable project registration, the GitLab project identity checks, the delivery repository and
# the DevWorkspaces that clone the project. The two writers, lifecycle_delete_workspaces and
# lifecycle_delete_gitlab_project, run only after a script's --yes: the demo-reset scripts leave no trace of earlier
# demo runs.

WORKSPACE_NAMESPACES=(wksp-ai-developer wksp-ai-admin)
LIFECYCLE_TMP=$(mktemp -d)
trap 'rm -rf "$LIFECYCLE_TMP"' EXIT

die() { log_error "$*"; exit 1; }

# ── GitLab API (the demo-operator token from Secret gitlab-system/gitlab-demo-operator, written by the 070-gitlab
#    bootstrap; never printed, never a process argument) ───────────────────────────────────────────────────────────
lifecycle_read_token() {
    GITLAB_TOKEN=$(oc get secret gitlab-demo-operator -n gitlab-system -o json 2>/dev/null | jq -j '.data.token // "" | @base64d') ||
        die "Secret gitlab-system/gitlab-demo-operator is unreadable; sync 070-gitlab so its bootstrap creates it"
    GITLAB_TOKEN="${GITLAB_TOKEN//[$'\t\r\n ']/}"
    [[ -n "$GITLAB_TOKEN" ]] || die "Secret gitlab-system/gitlab-demo-operator holds no token"
}

# gitlab METHOD PATH [OUTFILE]: JSON body (if any) on stdin for POST; the response goes to stdout, or to OUTFILE for a
# binary download. A non-2xx status stops the script; the response body is not printed.
gitlab() {
    local method=$1 path=$2 out=${3:-} code body=()
    [[ "$method" == GET ]] || body=(-H 'Content-Type: application/json' --data-binary @-)
    if [[ -n "$out" ]]; then
        code=$(curl -sS --max-time 60 -X "$method" -o "$out" -w '%{http_code}' ${body[@]+"${body[@]}"} \
            --config <(printf 'header = "PRIVATE-TOKEN: %s"\n' "$GITLAB_TOKEN") "$GITLAB_BASE_URL/api/v4/$path") ||
            die "GitLab $method ${path%%\?*} failed"
        [[ "$code" == 2?? ]] || die "GitLab $method ${path%%\?*} returned HTTP $code"
        return 0
    fi
    local response
    response=$(curl -sS --max-time 60 -X "$method" -w '\n%{http_code}' ${body[@]+"${body[@]}"} \
        --config <(printf 'header = "PRIVATE-TOKEN: %s"\n' "$GITLAB_TOKEN") "$GITLAB_BASE_URL/api/v4/$path") ||
        die "GitLab $method ${path%%\?*} failed"
    code=${response##*$'\n'}
    [[ "$code" == 2?? ]] || die "GitLab $method ${path%%\?*} returned HTTP $code"
    printf '%s' "${response%$'\n'*}"
}

# gitlab_find PATH: like `gitlab GET PATH`, but prints nothing for HTTP 404 (a deleted or invisible object).
gitlab_find() {
    local response code
    response=$(curl -sS --max-time 60 -w '\n%{http_code}' \
        --config <(printf 'header = "PRIVATE-TOKEN: %s"\n' "$GITLAB_TOKEN") "$GITLAB_BASE_URL/api/v4/$1") ||
        die "GitLab GET ${1%%\?*} failed"
    code=${response##*$'\n'}
    [[ "$code" == 404 ]] && return 0
    [[ "$code" == 2?? ]] || die "GitLab GET ${1%%\?*} returned HTTP $code"
    printf '%s' "${response%$'\n'*}"
}

# Delete a GitLab project for good. GitLab first marks it for deletion (and renames it); a second DELETE with
# permanently_remove and the new full path removes it at once, so the name is free for the next demo run.
lifecycle_delete_gitlab_project() {
    local pid=$1 row
    row=$(gitlab_find "projects/$pid")
    [[ -n "$row" ]] || { log_success "GitLab project $pid already deleted"; return 0; }
    if [[ $(printf '%s' "$row" | jq -r '.marked_for_deletion_on // empty') == "" ]]; then
        gitlab DELETE "projects/$pid" </dev/null >/dev/null
        row=$(gitlab_find "projects/$pid")
    fi
    if [[ -n "$row" ]]; then
        gitlab DELETE "projects/$pid?permanently_remove=true&full_path=$(printf '%s' "$row" |
            jq -r '.path_with_namespace | @uri')" </dev/null >/dev/null
    fi
    for _ in $(seq 1 30); do
        [[ -n $(gitlab_find "projects/$pid") ]] || { log_success "GitLab project $pid deleted"; return 0; }
        sleep 5
    done
    die "GitLab project $pid is still present after deletion"
}

# Sets DELIVERY (JSON, or empty when the project has none) for NAME: the platform-owned runtime repository
# rhoai-delivery/NAME-deployment. demo-operator reads it as Owner of the delivery group (070-gitlab bootstrap).
lifecycle_read_delivery() {
    local name=$1 group
    group=$(oc get configmap gitlab-platform-config -n app-platform-build -o json |
        jq -er '.data["platform.json"] | fromjson | .GITLAB_DELIVERY_GROUP')
    [[ -n $(gitlab_find "groups/$(printf '%s' "$group" | jq -sRr @uri)") ]] ||
        die "demo-operator cannot see GitLab group $group; sync 070-gitlab so its bootstrap adds the membership"
    DELIVERY=$(gitlab_find "projects/$(printf '%s' "$group/$name-deployment" | jq -sRr @uri)")
}

# ── Registration and identity checks ─────────────────────────────────────────────────────────────────────────────
# Sets GITLAB_BASE_URL and GITLAB_WORKLOAD_GROUP from the platform configuration.
lifecycle_read_platform() {
    local config
    config=$(oc get configmap gitlab-platform-config -n app-platform-build -o json | jq -c '.data["platform.json"] | fromjson')
    GITLAB_BASE_URL=$(printf '%s' "$config" | jq -er '.GITLAB_BASE_URL')
    GITLAB_WORKLOAD_GROUP=$(printf '%s' "$config" | jq -er '.GITLAB_WORKLOAD_GROUP')
}

# Sets PROJECT_NS and REGISTRATION (JSON) for NAME: the live project-registration ConfigMap, or the immutable
# retirement record once the project namespace is gone. REGISTRATION is empty when neither exists (fully removed).
lifecycle_read_registration() {
    local name=$1 live packet
    if [[ "$name" == coolstore-inventory-service ]]; then PROJECT_NS=coolstore-dev; else PROJECT_NS="$name-dev"; fi
    if live=$(oc get configmap project-registration -n "$PROJECT_NS" -o json 2>"$LIFECYCLE_TMP/stderr"); then
        REGISTRATION=$(printf '%s' "$live" | jq -c '.data["registration.json"] | fromjson')
        return 0
    fi
    grep -q '(NotFound)' "$LIFECYCLE_TMP/stderr" || { cat "$LIFECYCLE_TMP/stderr" >&2; die "Registration lookup failed"; }
    packet=$(oc get configmap "retired-project-$name" -n app-platform-build --ignore-not-found -o json)
    [[ -n "$packet" ]] || { REGISTRATION=""; return 0; }
    packet=$(printf '%s' "$packet" | jq -c '.data["retirement.json"] | fromjson')
    printf '%s' "$packet" | jq -e --arg n "$name" --arg ns "$PROJECT_NS" '.name == $n and .namespace == $ns' >/dev/null ||
        die "Foreign retirement record"
    REGISTRATION=$(printf '%s' "$packet" | jq -c '.registration')
}

# Sets PROJECT (JSON) after checking it is exactly the registered project inside the registered workload group, and
# that ACTION is allowed for its kind.
lifecycle_check_project() {
    local action=$1 name=$2
    PROJECT=$(gitlab_find "projects/$(printf '%s' "$REGISTRATION" | jq -r '.project_id')")
    # A retirement that already deleted the GitLab project resumes from its retirement record.
    if [[ -z "$PROJECT" && "$action" == retire ]] && oc get configmap "retired-project-$name" -n app-platform-build >/dev/null 2>&1; then
        return 0
    fi
    [[ -n "$PROJECT" ]] || die "Registered GitLab project $(printf '%s' "$REGISTRATION" | jq -r '.project_id') is missing"
    printf '%s' "$PROJECT" | jq -e --argjson row "$REGISTRATION" \
        '$row.project_id == .id and $row.repo_url == .http_url_to_repo' >/dev/null ||
        die "GitLab project differs from its immutable registration"
    printf '%s' "$PROJECT" | jq -e --argjson row "$REGISTRATION" --arg name "$name" \
        '.path == $name and ($row.initial_commit | type == "string" and test("^[0-9a-f]{40}$"))' >/dev/null ||
        die "Unbound project lifecycle request"
    printf '%s' "$PROJECT" | jq -e --arg want "$GITLAB_WORKLOAD_GROUP/$name" '.path_with_namespace == $want' >/dev/null ||
        die "Lifecycle target is outside the registered workload group"
    local kind
    kind=$(printf '%s' "$REGISTRATION" | jq -r '.kind')
    if [[ "$action" == reset-coolstore ]]; then
        [[ "$name" == coolstore-inventory-service && "$kind" == imported-application ]] ||
            die "Reset is limited to the ordinary Coolstore demo, never a migration run"
    elif [[ "$kind" != application && "$kind" != migration ]]; then
        die "Stage-owned imported applications cannot be retired by the project helper"
    fi
}

# ── Workspaces ───────────────────────────────────────────────────────────────────────────────────────────────────
# "namespace name" of every DevWorkspace in the persona namespaces whose project clones the registered repository.
lifecycle_matching_workspaces() {
    local namespace repo
    repo=$(printf '%s' "$REGISTRATION" | jq -r '.repo_url')
    for namespace in "${WORKSPACE_NAMESPACES[@]}"; do
        oc get devworkspaces -n "$namespace" -o json | jq -r --arg repo "$repo" '.items[]
            | select([.spec.template.projects // [] | .[] | .git.remotes.origin?] | index($repo))
            | "\(.metadata.namespace) \(.metadata.name)"'
    done
}

# Delete the matching workspaces and wait until they are gone. A per-workspace PVC (storage-<workspace id>) is owned by
# its DevWorkspace and goes with it; on the shared per-user claim the operator's cleanup removes the workspace's folder.
# Never touches another workspace.
lifecycle_delete_workspaces() {
    local namespace name
    while read -r namespace name; do
        [[ -n "$name" ]] || continue
        oc delete devworkspace "$name" -n "$namespace" --ignore-not-found --wait=true --timeout=300s >/dev/null
        log_success "Deleted DevWorkspace $namespace/$name and its storage"
    done <<<"$1"
}

# Retirement record (immutable ConfigMap) written before anything is removed; its text matches the former Python
# helper's json.dumps(sort_keys=True), so records written by either are the same.
PY_JSON='def py: if type == "object" then "{" + (to_entries | sort_by(.key) | map((.key | tojson) + ": " + (.value | py))
    | join(", ")) + "}" elif type == "array" then "[" + (map(py) | join(", ")) + "]" else tojson end;'
lifecycle_tombstone() {
    local name=$1
    jq -n -c --arg name "$name" --arg ns "$PROJECT_NS" --argjson row "$REGISTRATION" "$PY_JSON"'
        {apiVersion: "v1", kind: "ConfigMap", metadata: {name: ("retired-project-" + $name), namespace: "app-platform-build"},
         immutable: true, data: {"retirement.json": ({name: $name, namespace: $ns, registration: $row} | py)}}'
}
