#!/usr/bin/env bash
# Shared steps of the GitLab project lifecycle task scripts reset-coolstore.sh and delete-project.sh; sourced by them
# after scripts/lib.sh, load_env and check_oc_logged_in, never run on its own. Everything here up to
# lifecycle_stop_workspaces is read-only: the platform GitLab configuration, the immutable project registration, the
# GitLab project identity checks, the DevWorkspaces that clone the project and, for a reset, the commit that restores
# the registered baseline. Repository history is always kept: no force push, no branch rewrite.

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

# ── Registration and identity checks ─────────────────────────────────────────────────────────────────────────────
# Sets GITLAB_BASE_URL and GITLAB_WORKLOAD_GROUP from the platform configuration.
lifecycle_read_platform() {
    local config
    config=$(oc get configmap gitlab-platform-config -n app-platform-build -o json | jq -c '.data["platform.json"] | fromjson')
    GITLAB_BASE_URL=$(printf '%s' "$config" | jq -er '.GITLAB_BASE_URL')
    GITLAB_WORKLOAD_GROUP=$(printf '%s' "$config" | jq -er '.GITLAB_WORKLOAD_GROUP')
}

# Sets PROJECT_NS and REGISTRATION (JSON) for NAME: the live project-registration ConfigMap, or the immutable
# retirement record once the project namespace is gone.
lifecycle_read_registration() {
    local name=$1 live packet
    if [[ "$name" == coolstore-inventory-service ]]; then PROJECT_NS=coolstore-dev; else PROJECT_NS="$name-dev"; fi
    if live=$(oc get configmap project-registration -n "$PROJECT_NS" -o json 2>"$LIFECYCLE_TMP/stderr"); then
        REGISTRATION=$(printf '%s' "$live" | jq -c '.data["registration.json"] | fromjson')
        return 0
    fi
    grep -q '(NotFound)' "$LIFECYCLE_TMP/stderr" || { cat "$LIFECYCLE_TMP/stderr" >&2; die "Registration lookup failed"; }
    packet=$(oc get configmap "retired-project-$name" -n app-platform-build -o json | jq -c '.data["retirement.json"] | fromjson') ||
        die "No registration and no retirement record for $name"
    printf '%s' "$packet" | jq -e --arg n "$name" --arg ns "$PROJECT_NS" '.name == $n and .namespace == $ns' >/dev/null ||
        die "Foreign retirement record"
    REGISTRATION=$(printf '%s' "$packet" | jq -c '.registration')
}

# Sets PROJECT (JSON) after checking it is exactly the registered project inside the registered workload group, and
# that ACTION is allowed for its kind.
lifecycle_check_project() {
    local action=$1 name=$2
    PROJECT=$(gitlab GET "projects/$(printf '%s' "$REGISTRATION" | jq -r '.project_id')")
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

# Stop the matching workspaces; their PVCs and local changes stay. Never wipes a volume or touches another workspace.
lifecycle_stop_workspaces() {
    local namespace name
    while read -r namespace name; do
        [[ -n "$name" ]] || continue
        oc patch devworkspace "$name" -n "$namespace" --type=merge -p '{"spec":{"started":false}}' >/dev/null
        log_success "Stopped DevWorkspace $namespace/$name (PVC and local changes retained)"
    done <<<"$1"
}

# ── Reset: the commit that restores the registered baseline (same rules as golden_actions in
#    gitops/stages/070-advanced-app-platform/070-gitlab/bootstrap-scm.py) ────────────────────────────────────────
# Unsafe paths and authoring debris refuse the whole commit.
GOLDEN_PATH_CHECK='.[] | .path
    | if startswith("/") or (split("/") | index("..")) or (split("/") | index(".git")) then error("Unsafe golden file path")
      elif (split("/") | index("__pycache__")) or startswith(".hermes/_park/") then error("Authoring debris in the golden tree")
      elif endswith("run-chaos-matrix.py") then error("Forbidden execution fixture in golden")
      else empty end'

# Writes the commit actions (JSON array) to $LIFECYCLE_TMP/actions.json: create/update every registered baseline file
# whose blob or executable bit differs from main, delete every main file the baseline does not have.
lifecycle_reset_actions() {
    local pid commit page rows dir path blob executable
    pid=$(printf '%s' "$PROJECT" | jq -r '.id')
    commit=$(printf '%s' "$REGISTRATION" | jq -r '.initial_commit')
    [[ $(printf '%s' "$PROJECT" | jq -r '.archived // false') != true ]] || die "Archived project cannot be reset"

    # The registered baseline: regular files of the archive at the registered commit (top directory stripped).
    gitlab GET "projects/$pid/repository/archive.tar.gz?sha=$commit" "$LIFECYCLE_TMP/baseline.tar.gz"
    tar -tzf "$LIFECYCLE_TMP/baseline.tar.gz" | jq -R -s -e 'split("\n") | map(select(. != ""))
        | all(startswith("/") or (split("/") | index("..")) | not)' >/dev/null || die "Unsafe golden file path"
    dir="$LIFECYCLE_TMP/baseline"
    mkdir "$dir"
    tar -xzf "$LIFECYCLE_TMP/baseline.tar.gz" -C "$dir" --strip-components 1
    while IFS= read -r path; do
        blob=$(git hash-object --stdin <"$dir/$path")
        if [[ -x "$dir/$path" ]]; then executable=true; else executable=false; fi
        jq -n -c --arg p "$path" --arg b "$blob" --argjson x "$executable" '{path: $p, id: $b, executable: $x}'
    done < <(cd "$dir" && find . -type f | sed 's|^\./||' | LC_ALL=C sort) | jq -s -c . >"$LIFECYCLE_TMP/baseline.json"
    jq -e "[$GOLDEN_PATH_CHECK] | length == 0" "$LIFECYCLE_TMP/baseline.json" >/dev/null

    # Current main: blobs of the recursive tree, bounded to 30 pages of 100.
    echo '[]' >"$LIFECYCLE_TMP/current.json"
    for page in $(seq 1 31); do
        [[ "$page" -le 30 ]] || die "Reset exceeds bounded inventory"
        rows=$(gitlab GET "projects/$pid/repository/tree?ref=main&recursive=true&per_page=100&page=$page")
        printf '%s' "$rows" | jq -c --slurpfile all "$LIFECYCLE_TMP/current.json" \
            '$all[0] + [.[] | select(.type == "blob") | {path, id, mode}]' >"$LIFECYCLE_TMP/current.next"
        mv "$LIFECYCLE_TMP/current.next" "$LIFECYCLE_TMP/current.json"
        [[ $(printf '%s' "$rows" | jq 'length') -ge 100 ]] || break
    done

    # Changed or new baseline files carry their content; files only on main are deleted.
    jq -c --slurpfile cur "$LIFECYCLE_TMP/current.json" '($cur[0] | map({key: .path, value: .}) | from_entries) as $c
        | .[] | $c[.path] as $old
        | select(($old != null and $old.id == .id and (($old.mode == "100755") == .executable)) | not)
        | {action: (if $old then "update" else "create" end), file_path: .path, executable}' \
        "$LIFECYCLE_TMP/baseline.json" | while IFS= read -r row; do
        path=$(printf '%s' "$row" | jq -r '.file_path')
        base64 <"$dir/$path" | tr -d '\n' >"$LIFECYCLE_TMP/content.b64"
        printf '%s' "$row" | jq -c --rawfile content "$LIFECYCLE_TMP/content.b64" \
            '{action, file_path, content: $content, encoding: "base64", execute_filemode: .executable}'
    done >"$LIFECYCLE_TMP/actions.jsonl"
    jq -c --slurpfile base "$LIFECYCLE_TMP/baseline.json" '($base[0] | map(.path)) as $keep
        | [.[].path | select(. as $p | $keep | index($p) | not)] | sort | .[] | {action: "delete", file_path: .}' \
        "$LIFECYCLE_TMP/current.json" >>"$LIFECYCLE_TMP/actions.jsonl"
    jq -s -c . "$LIFECYCLE_TMP/actions.jsonl" >"$LIFECYCLE_TMP/actions.json"
    [[ $(wc -c <"$LIFECYCLE_TMP/actions.json") -le 10000000 ]] || die "Golden publication exceeds one bounded atomic commit"
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
