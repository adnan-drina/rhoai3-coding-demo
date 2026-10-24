#!/usr/bin/env bash
# Component Applications of a stage: the shared Argo CD deploy engine for every stage deploy.sh and validate.sh.
#
# A stage keeps one Argo CD Application per component in gitops/applications/<name>.yaml (file name = metadata.name,
# which starts with the stage number), rendering gitops/stages/<NNN-stage>/<name>/. Components with a numeric
# demo.rhoai.io/deploy-order annotation deploy together at one reviewed revision, in that order; components with
# demo.rhoai.io/deploy-script are deployed by the stage deploy.sh separately (their own revision and procedure).
# A manual-sync deploy-script component may declare demo.rhoai.io/optional: 'true'; broad status reports its
# absence as not activated, while an explicit status --app still requires it to be present and reconciled.
# gitops/stages/<NNN-stage>/kustomization.yaml renders exactly the union of all components.
#
# Usage: scripts/stage-apps.sh COMMAND STAGE [options]
#   select STAGE --ref REF --repo-url URL [--extra PATH]...    reviewed, published commit of the stage source
#   deploy STAGE --revision SHA --repo-url URL [--resync] [--no-wait] [--timeout S] [--kustomize-patches FILE]
#   apply STAGE --app NAME... --revision SHA --repo-url URL [--kustomize-patches FILE]   apply only, no sync
#   sync STAGE [--app NAME]... [--resync]                       start syncs only
#   wait STAGE --revision SHA --repo-url URL [--app NAME]... [--timeout S]
#   status STAGE [--revision SHA] [--repo-url URL] [--app NAME]...   OK/FAIL; absent optional components SKIP
#   names STAGE [--all] [--reverse]                             deploy order (--reverse: deletion order)
#   applications STAGE --revision SHA --repo-url URL [--kustomize-patches FILE]   JSON List of pinned Applications
#   owner STAGE KIND NAME [NAMESPACE] [--group G]               component that renders the object
#   delegated STAGE KIND NAME [NAMESPACE] [--group G]           JSON pointers its live owner leaves to later stages
#   preflight STAGE --repo-url URL [--skip-kind K]... [--all] [--app NAME]...   read-only adoption guard before the first write
#   check-static STAGE                                          components disjoint and equal to the stage base
#   check-delegations                                           Stage 010 delegations match hook Job declarations
set -euo pipefail
REPO_ROOT="${REPO_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
NS=openshift-gitops
DESTINATION='{"server":"https://kubernetes.default.svc","namespace":"openshift-gitops"}'
# Cluster-scoped kinds (group/kind) that may omit metadata.namespace; their tracking ids use the destination namespace.
CLUSTER_SCOPED='["/Namespace","rbac.authorization.k8s.io/ClusterRole","rbac.authorization.k8s.io/ClusterRoleBinding",
 "user.openshift.io/Group","operator.openshift.io/Console","operator.openshift.io/LeaderWorkerSetOperator",
 "observability.openshift.io/UIPlugin","nvidia.com/ClusterPolicy","kueue.x-k8s.io/ClusterQueue","kueue.x-k8s.io/ResourceFlavor",
 "datasciencecluster.opendatahub.io/DataScienceCluster","dscinitialization.opendatahub.io/DSCInitialization",
 "services.platform.opendatahub.io/Auth","mlflow.opendatahub.io/MLflow","policy.networking.k8s.io/AdminNetworkPolicy",
 "policy.networking.k8s.io/BaselineAdminNetworkPolicy","imageregistry.operator.openshift.io/Config","oauth.openshift.io/OAuthClient",
 "console.openshift.io/ConsoleLink","admissionregistration.k8s.io/ValidatingAdmissionPolicy",
 "admissionregistration.k8s.io/ValidatingAdmissionPolicyBinding"]'
CACHE=$(mktemp -d)
trap 'rm -rf "$CACHE"' EXIT
die() { echo "ERROR: $*" >&2; exit 1; }
yaml_json() { ruby -ryaml -rjson -e 'puts JSON.generate(YAML.load_stream(STDIN.read).compact)'; }
# jq: tracking-id suffix "<group>/<kind>:<namespace>/<name>" (cluster-scoped objects use the destination namespace).
SUFFIX='def suffix: (if (.apiVersion | contains("/")) then (.apiVersion | split("/")[0]) else "" end) + "/" + .kind
    + ":" + (.metadata.namespace // "openshift-gitops") + "/" + .metadata.name;'

# Rendered objects of a repository path, as a JSON array (cached per process).
render() {
    local key="$CACHE/render-$(printf '%s' "$1" | shasum | cut -c1-16).json"
    if [[ ! -f "$key" ]]; then
        oc kustomize "$REPO_ROOT/$1" 2>/dev/null | yaml_json >"$key" || { rm -f "$key"; die "kustomize build failed for $1"; }
    fi
    cat "$key"
}
stage_dir() {
    local dirs=("$REPO_ROOT"/gitops/stages/"$1"-*/)
    [[ ${#dirs[@]} == 1 && -d "${dirs[0]}" ]] || die "Stage $1 has no GitOps source directory"
    basename "${dirs[0]}"
}
# Component Applications of a stage (deploy order, then name), validated; --all adds script-deployed ones.
components() {
    local stage=$1 all=${2:-false} key="$CACHE/components-$1.json" file
    if [[ ! -f "$key" ]]; then
        shopt -s nullglob
        local files=("$REPO_ROOT"/gitops/applications/"$stage"-*.yaml)
        shopt -u nullglob
        for file in ${files[@]+"${files[@]}"}; do
            yaml_json <"$file" | jq -c --arg file "$(basename "$file" .yaml)" 'if length != 1 or .[0].kind != "Application"
                then error("\($file).yaml must hold exactly one Application")
                elif .[0].metadata.name != $file then error("\($file).yaml must be named after its Application (metadata.name + .yaml)")
                else .[0] end'
        done | jq -s -c --arg stage "$stage" '
            if length == 0 then error("Stage \($stage) has no component Applications") else . end
            | map(if (.metadata.name | startswith($stage + "-")) and .metadata.labels["demo.rhoai.io/stage"] == $stage then .
                  else error("\(.metadata.name) must carry the stage prefix and label") end)
            | map(.metadata.annotations as $a | if (($a["demo.rhoai.io/deploy-order"] // "" | test("^[0-9]+$")) | not)
                  == (($a["demo.rhoai.io/deploy-script"] // "") == "")
                  then error("\(.metadata.name) needs either a numeric deploy-order or a deploy-script annotation") else . end)
            | map(.metadata.annotations as $a | if $a["demo.rhoai.io/optional"] != null and
                  ($a["demo.rhoai.io/optional"] != "true" or ($a["demo.rhoai.io/deploy-script"] // "") == ""
                   or .spec.syncPolicy.automated != null)
                  then error("\(.metadata.name): optional requires deploy-script and manual sync (no automated policy)") else . end)
            | if (map(.metadata.name) | unique | length) != length then error("Stage \($stage) component names must be unique") else . end
            | sort_by([(.metadata.annotations["demo.rhoai.io/deploy-order"] // "1000000" | tonumber), .metadata.name])' >"$key" ||
            { rm -f "$key"; exit 1; }
    fi
    if [[ "$all" == true ]]; then cat "$key"; else jq -c '[.[] | select(.metadata.annotations["demo.rhoai.io/deploy-order"])]' "$key"; fi
}
names() { components "$1" "${2:-false}" | jq -r '.[].metadata.name'; }
# {suffix: component} for every rendered object of every component; refuses an object two components render.
owners() {
    local stage=$1 key="$CACHE/owners-$1.json" app
    if [[ ! -f "$key" ]]; then
        for app in $(components "$stage" true | jq -r '.[] | "\(.metadata.name)=\(.spec.source.path)"'); do
            render "${app#*=}" | jq -c --arg app "${app%%=*}" "$SUFFIX"' [.[] | {key: suffix, value: $app}]'
        done | jq -s -c 'add // [] | group_by(.key) | map(if length > 1
            then error("\(.[0].key) is rendered by both \(.[0].value) and \(.[1].value)") else .[0] end) | from_entries' >"$key" ||
            { rm -f "$key"; exit 1; }
    fi
    cat "$key"
}
owner() {
    local key="$5/$2:${4:-$NS}/$3"
    owners "$1" | jq -er --arg k "$key" '.[$k] // empty' || die "$key is not rendered by any Stage $1 component"
}
get_application() { oc --request-timeout=10s get applications.argoproj.io "$1" -n "$NS" --ignore-not-found -o json; }

# Reasons (one per line) an Application is not exactly reconciled at an immutable revision; nothing when ready.
APP_PROBLEMS='def app_problems($rev; $repo; $path; $accepted; $dest): .metadata.name as $n | .spec as $spec | .status as $s
    | ($spec.source.targetRevision // "") as $target | ($s.operationState // {}) as $op
    | [ (if (.metadata.ownerReferences // [] | length) > 0 or .metadata.deletionTimestamp != null or $spec.sources != null
            then "\($n): foreign, terminating or multi-source" else empty end),
        (if $spec.project != "rhoai-demo" or $spec.destination != $dest then "\($n): project or destination differs" else empty end),
        (if $repo != "" and $spec.source.repoURL != $repo then "\($n): repository differs" else empty end),
        (if $path != "" and $spec.source.path != $path then "\($n): source path differs" else empty end),
        (if ($target | test("^[0-9a-f]{40}$") | not) or ($rev != "" and $target != $rev)
            then "\($n): revision is not the reviewed immutable commit" else empty end),
        (if ($spec.syncPolicy.syncOptions // [] | index("RespectIgnoreDifferences=true")) == null
            then "\($n): RespectIgnoreDifferences is off" else empty end),
        (if $s.sync.status != "Synced" or $s.sync.revision != $target then "\($n): not Synced at its revision" else empty end),
        (if ($accepted | index($s.health.status)) == null then "\($n): health \($s.health.status)" else empty end),
        (if $op.phase != "Succeeded" or $op.syncResult.revision != $target or $op.syncResult.source.path != $spec.source.path
            then "\($n): last operation is not a successful sync of this source" else empty end) ];'
# Problems across a stage's components; --all also checks script-deployed ones (validation always does).
stage_problems() {
    local stage=$1 revision=${2:-} repo=${3:-} all=${4:-false} desired name live order revisions=""
    shift 4
    desired=$(components "$stage" "$all") || return 1
    for name in "$@"; do
        jq -e --arg n "$name" 'any(.[]; .metadata.name == $n)' <<<"$desired" >/dev/null ||
            die "Unknown Stage $stage component: $name"
    done
    [[ $(jq length <<<"$desired") -gt 0 ]] || { echo "Stage $stage has no component Applications to check"; return; }
    while IFS= read -r want; do
        name=$(jq -r '.metadata.name' <<<"$want")
        if [[ $# -gt 0 ]] && ! printf '%s\n' "$@" | grep -qx "$name"; then continue; fi
        live=$(get_application "$name") || die "Application read failed"
        if [[ -z "$live" ]]; then
            if [[ $# -eq 0 ]] && jq -e '.metadata.annotations["demo.rhoai.io/optional"] == "true"' <<<"$want" >/dev/null; then
                echo "SKIP $name (not activated)"
            else
                echo "$name: missing"
            fi
            continue
        fi
        if jq -e '.metadata.annotations["demo.rhoai.io/optional"] == "true"' <<<"$want" >/dev/null &&
            ! jq -e '.spec.syncPolicy.automated == null' <<<"$live" >/dev/null; then
            echo "$name: optional component requires manual sync (no automated policy)"
        fi
        order=$(jq -r '.metadata.annotations["demo.rhoai.io/deploy-order"] // ""' <<<"$want")
        # Deploy-order components share the stage's one revision; a script-deployed one has its own.
        [[ -n "$order" ]] && revisions+="$(jq -r '.spec.source.targetRevision' <<<"$live")"$'\n'
        jq -r --argjson want "$want" --arg rev "$([[ -n "$order" || $# -gt 0 ]] && echo "$revision")" --arg repo "$repo" \
            "$APP_PROBLEMS"' ($want.metadata.annotations["demo.rhoai.io/accepted-health"] // "" | split(",") | map(gsub("^\\s+|\\s+$"; ""))
                | map(select(. != "")) + ["Healthy"]) as $acc
            | app_problems($rev; $repo; $want.spec.source.path; $acc; $want.spec.destination)[]' <<<"$live" ||
            die "$name: could not validate Application"
    done < <(jq -c '.[]' <<<"$desired")
    [[ $(printf '%s' "$revisions" | sort -u | grep -c .) -le 1 ]] || echo "components are at different revisions"
}

# Applications pinned to the revision and repository, with per-component Kustomize patches ({name: [patch...]}).
stamped() {
    local stage=$1 revision=$2 repo=$3 patches=${4:-} all=${5:-false}
    [[ "$revision" =~ ^[0-9a-f]{40}$ ]] || die "A 40-character commit SHA is required"
    components "$stage" "$all" | jq -c --arg rev "$revision" --arg repo "$repo" --argjson p "$( [[ -n "$patches" ]] && cat "$patches" || echo '{}')" '
        (($p | keys) - map(.metadata.name)) as $unknown
        | if ($unknown | length) > 0 then error("Patches for unknown components: \($unknown | join(", "))") else . end
        | map(.spec.source.repoURL = $repo | .spec.source.targetRevision = $rev
            | .metadata.name as $n | if $p[$n] then .spec.source.kustomize.patches = $p[$n] else . end)'
}
apply_app() { oc --request-timeout=15s apply -f - <<<"$1" || die "Could not apply $(jq -r '.metadata.name' <<<"$1")"; }
# One hook-strategy sync for each component whose last operation is not a successful sync of its current source
# (every one with resync). Carries the Application's own syncOptions and prune (a bare sync drops them); Argo CD
# reports Synced without an operation when the render is unchanged, so automated sync alone never runs hooks.
start_syncs() {
    local stage=$1 resync=$2; shift 2
    local all=false name app
    [[ $# -gt 0 ]] && all=true
    for name in $(names "$stage" "$all"); do
        if [[ $# -gt 0 ]] && ! printf '%s\n' "$@" | grep -qx "$name"; then continue; fi
        app=$(get_application "$name")
        [[ -n "$app" ]] || continue
        jq -e '.operation != null or (.status.operationState.phase == "Running" or .status.operationState.phase == "Terminating")' \
            <<<"$app" >/dev/null && continue
        if [[ "$resync" == false ]] && jq -e '(.status.operationState // {}) as $op | $op.phase == "Succeeded"
            and $op.syncResult.revision == .spec.source.targetRevision and $op.syncResult.source.path == .spec.source.path' \
            <<<"$app" >/dev/null; then continue; fi
        jq -c '{operation: ({initiatedBy: {username: "stage-deploy"}, sync: ({revision: .spec.source.targetRevision, syncStrategy: {hook: {}}}
            + (if (.spec.syncPolicy.syncOptions // []) | length > 0 then {syncOptions: .spec.syncPolicy.syncOptions} else {} end)
            + (if .spec.syncPolicy.automated.prune then {prune: true} else {} end))}
            + (if .spec.syncPolicy.retry then {retry: .spec.syncPolicy.retry} else {} end))}' <<<"$app" |
            oc --request-timeout=10s patch applications.argoproj.io "$name" -n "$NS" --type merge --patch-file=/dev/stdin >/dev/null ||
            die "Could not start a sync of $name"
        echo "$name"
    done
}
# Wait until every named component is reconciled at the revision; fail on a failed operation or the deadline.
wait_for() {
    local stage=$1 revision=$2 repo=$3 timeout=$4; shift 4
    local deadline=$((SECONDS + timeout)) desired problems name app want
    desired=$(components "$stage" true)
    while true; do
        problems=""
        for name in "$@"; do
            app=$(get_application "$name")
            if [[ -z "$app" ]]; then problems+="$name: missing; "; continue; fi
            jq -e --arg rev "$revision" '(.status.operationState // {}) as $op | .operation == null
                and ($op.syncResult.revision // $op.operation.sync.revision) == $rev and ($op.phase == "Failed" or $op.phase == "Error")' \
                <<<"$app" >/dev/null && die "$name: sync at ${revision:0:12} failed; inspect its hooks"
            want=$(jq -c --arg n "$name" '.[] | select(.metadata.name == $n)' <<<"$desired")
            problems+=$(jq -r --argjson want "$want" --arg rev "$revision" --arg repo "$repo" "$APP_PROBLEMS"'
                ($want.metadata.annotations["demo.rhoai.io/accepted-health"] // "" | split(",") | map(gsub("^\\s+|\\s+$"; ""))
                    | map(select(. != "")) + ["Healthy"]) as $acc
                | app_problems($rev; $repo; $want.spec.source.path; $acc; $want.spec.destination) | map(. + "; ") | join("")' <<<"$app")
        done
        [[ -z "$problems" ]] && return 0
        (( SECONDS < deadline )) || die "not reconciled in time: $problems"
        sleep 10
    done
}
# Apply every deploy-order component pinned to the revision, start syncs, and wait (sequential stages per group).
deploy() {
    local stage=$1 revision=$2 repo=$3 timeout=$4 resync=$5 wait=$6 patches=$7
    local apps groups group names_ app started
    apps=$(stamped "$stage" "$revision" "$repo" "$patches")
    if jq -e 'any(.[]; .metadata.annotations["demo.rhoai.io/deploy-mode"] == "sequential")' <<<"$apps" >/dev/null; then
        groups=$(jq -c 'group_by(.metadata.annotations["demo.rhoai.io/deploy-order"] | tonumber) | .[]' <<<"$apps")
        [[ "$wait" == true || $(wc -l <<<"$groups") -le 1 ]] || die "Stage $stage deploys sequentially and must wait between its groups"
    else
        groups=$(jq -c . <<<"$apps")
    fi
    while IFS= read -r group; do
        names_=$(jq -r '.[].metadata.name' <<<"$group")
        while IFS= read -r app; do apply_app "$app" | sed 's/^/  /'; done < <(jq -c '.[]' <<<"$group")
        started=$(start_syncs "$stage" "$resync" $names_ | paste -sd, - | sed 's/,/, /g')
        echo "applied $(paste -sd, - <<<"$names_" | sed 's/,/, /g') at ${revision:0:12}${started:+; started sync of $started}$([[ -n "$started" ]] || echo "; no sync needed")"
        [[ "$wait" == true ]] || return 0
        wait_for "$stage" "$revision" "$repo" "$timeout" $names_
        echo "PASS $(paste -sd, - <<<"$names_" | sed 's/,/, /g') Synced and Healthy at ${revision:0:12}"
    done <<<"$groups"
}
# The full commit of ref, provided the stage source in the checkout is exactly that commit (no edits, nothing
# untracked) and the configured repository advertises it: only reviewed, published source is deployed.
select_revision() {
    local stage=$1 ref=$2 repo=$3; shift 3
    local commit dir paths
    commit=$(git -C "$REPO_ROOT" rev-parse --verify "$ref^{commit}") || die "unknown ref $ref"
    dir=$(stage_dir "$stage")
    paths=("gitops/stages/$dir" ":(glob)gitops/applications/$stage-*.yaml" "stages/$dir" scripts/lib.sh scripts/stage-apps.sh "$@")
    git -C "$REPO_ROOT" diff --quiet "$commit" -- "${paths[@]}" || die "Stage $stage source differs from ${commit:0:12}; commit and publish it first"
    [[ -z "$(git -C "$REPO_ROOT" ls-files --others --exclude-standard -- "${paths[@]}")" ]] || die "Untracked Stage $stage source is not in ${commit:0:12}"
    git -C "$REPO_ROOT" ls-remote "$repo" | cut -f1 | grep -qx "$commit" || die "${commit:0:12} is not advertised by $repo (push it first)"
    echo "$commit"
}
delegated() {
    local stage=$1 kind=$2 name=$3 namespace=${4:-} group=${5:-} app
    app=$(get_application "$(owner "$stage" "$kind" "$name" "$namespace" "$group")")
    [[ -n "$app" ]] || return 0
    jq -r --arg g "$group" --arg k "$kind" --arg n "$name" --arg ns "$namespace" '
        if (.spec.syncPolicy.syncOptions // [] | index("RespectIgnoreDifferences=true")) == null then empty else
        [.spec.ignoreDifferences[]? | select((.group // "") == $g and .kind == $k and .name == $n
            and (.namespace // "") == $ns) | .jsonPointers[]?] | unique[] end' <<<"$app"
}
# Read-only adoption guard; prints problems (empty = safe to deploy). Existing Applications must have this
# repository's identity. Each rendered object must be absent, carry its component's exact tracking id (an operator
# may co-own it), or be an untracked, unowned Namespace. Kinds whose CRD is not installed cannot exist and are skipped.
preflight() {
    local stage=$1 repo=$2 all=$3 skip=$4 want name live obj kind args err; shift 4
    while IFS= read -r want; do
        name=$(jq -r '.metadata.name' <<<"$want")
        if [[ $# -gt 0 ]] && ! printf '%s\n' "$@" | grep -qx "$name"; then continue; fi
        live=$(get_application "$name")
        [[ -z "$live" ]] || jq -e --argjson want "$want" --arg repo "$repo" --argjson dest "$DESTINATION" '
            (.metadata.ownerReferences // [] | length) == 0 and .spec.sources == null and .spec.project == "rhoai-demo"
            and .spec.destination == $dest and .spec.source.repoURL == $repo and .spec.source.path == $want.spec.source.path' \
            <<<"$live" >/dev/null || echo "$name: existing Application has another owner, repository, project, destination or path"
        while IFS= read -r obj; do
            kind=$(jq -r '.kind' <<<"$obj")
            [[ ",$skip," == *",$kind,"* ]] && continue
            # Kind.version.group: a bare kind can resolve to another group (Console is in config and operator).
            args=(get "$(jq -r '.kind + (if (.apiVersion | contains("/")) then "." + (.apiVersion | split("/") | .[1] + "." + .[0]) else "" end)' <<<"$obj")"
                "$(jq -r '.metadata.name' <<<"$obj")" --ignore-not-found -o json)
            [[ "$(jq -r '.metadata.namespace // ""' <<<"$obj")" == "" ]] || args+=(-n "$(jq -r '.metadata.namespace' <<<"$obj")")
            if ! live=$(oc --request-timeout=10s "${args[@]}" 2>"$CACHE/err"); then
                err=$(cat "$CACHE/err")
                [[ "$err" == *"no matches for kind"* || "$err" == *"doesn't have a resource type"* ]] && continue
                jq -r "$SUFFIX"' suffix + ": could not be read"' <<<"$obj"; continue
            fi
            [[ -z "$live" ]] && continue
            owners "$stage" >"$CACHE/owners.json"
            jq -r --arg stage "$stage" --slurpfile owners "$CACHE/owners.json" --arg kind "$kind" "$SUFFIX"'
                (suffix) as $s | ($owners[0][$s] + ":" + $s) as $expected
                | (.metadata.annotations["argocd.argoproj.io/tracking-id"] // "") as $t
                | if $t == $expected then empty
                  elif (.metadata.ownerReferences // [] | length) > 0 then "\($s): owned by another object and not tracked by this stage"
                  elif $kind == "Namespace" and $t == "" then empty
                  else "\($s): exists without this stage'"'"'s tracking id (needs a reviewed adoption)" end' <<<"$live"
        done < <(render "$(jq -r '.spec.source.path' <<<"$want")" | jq -c '.[]')
    done < <(components "$stage" "$all" | jq -c '.[]')
}
# Components render disjoint object sets whose union equals the stage base render; namespaced objects set a namespace.
check_static() {
    local stage=$1 apps union base dir
    owners "$stage" >/dev/null
    apps=$(components "$stage" true)
    dir=$(jq -r '[.[].spec.source.path | split("/")[:-1] | join("/")] | unique | if length == 1 then .[0] else "" end' <<<"$apps")
    [[ -n "$dir" ]] || die "Stage $stage components must be folders of one stage directory"
    for path in $(jq -r '.[].spec.source.path' <<<"$apps"); do render "$path"; done | jq -s -c 'add' >"$CACHE/union.json"
    render "$dir" >"$CACHE/base.json"
    jq -n -e --slurpfile U0 "$CACHE/union.json" --slurpfile B0 "$CACHE/base.json" --argjson cs "$CLUSTER_SCOPED" "$SUFFIX"'
        $U0[0] as $u | $B0[0] as $b
        | ([$u[] | select(.metadata.namespace == null and ((if (.apiVersion | contains("/")) then (.apiVersion | split("/")[0]) else "" end)
            + "/" + .kind) as $gk | ($cs | index($gk)) == null) | "\(.kind)/\(.metadata.name)"]) as $unplaced
        | if ($unplaced | length) > 0 then error("namespaced objects must set metadata.namespace: \($unplaced | join(", "))") else . end
        | ($u | map({key: suffix, value: .}) | from_entries) as $U | ($b | map({key: suffix, value: .}) | from_entries) as $B
        | (($B | keys) - ($U | keys)) as $missing | (($U | keys) - ($B | keys)) as $extra
        | [($B | keys)[] | select($U[.] != null and $U[.] != $B[.])] as $changed
        | if ($missing + $extra + $changed | length) > 0
          then error("components differ from base: missing=\($missing) extra=\($extra) changed=\($changed)") else true end' \
        >/dev/null || exit 1
    echo "PASS Stage $stage: $(jq length <<<"$apps") components render $(jq length "$CACHE/union.json") objects, disjoint and equal to gitops/stages/$(basename "$dir")"
}
# Hook Jobs in later stages declare the shared-singleton fields they patch (demo.rhoai.io/writes-delegated,
# "Kind:/json/pointer"); 010-rhoai-platform must delegate exactly those fields, each to one writer.
check_delegations() {
    local delegated_fields writers stage path app
    delegated_fields=$(yaml_json <"$REPO_ROOT/gitops/applications/010-rhoai-platform.yaml" | jq -c '[.[0].spec.ignoreDifferences[]?
        | select(.kind == "DataScienceCluster" or .kind == "OdhDashboardConfig") | .kind as $k | .jsonPointers[] | "\($k):\(.)"] | unique')
    writers=$(for path in "$REPO_ROOT"/gitops/stages/0[2-9]0-*/; do
        stage=$(basename "$path" | cut -c1-3)
        compgen -G "$REPO_ROOT/gitops/applications/$stage-*.yaml" >/dev/null || continue
        for app in $(components "$stage" true | jq -r '.[] | "\(.metadata.name)=\(.spec.source.path)"'); do
            render "${app#*=}" | jq -c --arg app "${app%%=*}" '.[] | select(.kind == "Job") | ("\($app)/Job/\(.metadata.name)") as $n
                | (.metadata.annotations["demo.rhoai.io/writes-delegated"] // "" | split(",") | map(gsub("^\\s+|\\s+$"; "")) | map(select(. != ""))) as $d
                | if ($d | length) == 0 and (.spec.template.spec | tojson | ascii_downcase | test("patch\\s+(datasciencecluster|odhdashboardconfig)"))
                  then {problem: "\($n) patches a shared singleton but does not declare demo.rhoai.io/writes-delegated"}
                  else $d[] | {field: ., writer: $n} end'
        done
    done | jq -s -c .)
    jq -n -r --argjson d "$delegated_fields" --argjson w "$writers" '
        ([$w[] | select(.problem) | .problem]
         + ([$w[] | select(.field)] | group_by(.field) | map(.[0].field as $f | map(.writer) as $names
            | (if ($d | index($f)) == null then "\($f) is written by \($names | join(", ")) but 010-rhoai-platform does not delegate it" else empty end),
              (if ($names | length) > 1 then "\($f) has several writers: \($names | join(", "))" else empty end)) | flatten)
         + [$d[] | select(. as $f | [$w[] | select(.field) | .field] | index($f) == null)
            | "\(.) is delegated by 010-rhoai-platform but no hook Job declares that it writes it"]) as $p
        | if ($p | length) > 0 then error("delegation mismatch: \($p | join("; "))")
          else "PASS \($d | length) Stage 010 delegated fields, each written by exactly one declared hook Job" end' || exit 1
}

# ---- command line ----------------------------------------------------------------------------------------------
[[ $# -ge 1 ]] || { sed -n 's/^#   //p' "$0" >&2; exit 2; }
command=$1; shift
stage=""
[[ "$command" == check-delegations ]] || { stage=${1:-}; [[ "$stage" =~ ^[0-9]{3}$ ]] || die "STAGE must be three digits"; shift; }
revision="" repo="" ref=HEAD timeout=1800 resync=false wait=true patches="" all=false reverse=false group="" extra=() apps=() skip="" positional=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --revision) revision=$2; shift 2 ;;
        --repo-url) repo=$2; shift 2 ;;
        --ref) ref=$2; shift 2 ;;
        --timeout) timeout=$2; shift 2 ;;
        --resync) resync=true; shift ;;
        --no-wait) wait=false; shift ;;
        --kustomize-patches) patches=$2; shift 2 ;;
        --all) all=true; shift ;;
        --reverse) reverse=true; shift ;;
        --group) group=$2; shift 2 ;;
        --extra) extra+=("$2"); shift 2 ;;
        --app) apps+=("$2"); shift 2 ;;
        --skip-kind) skip+="$2,"; shift 2 ;;
        --*) die "unknown option $1" ;;
        *) positional+=("$1"); shift ;;
    esac
done
case "$command" in
    names) if [[ "$reverse" == true ]]; then names "$stage" "$all" | sed '1!G;h;$!d'; else names "$stage" "$all"; fi ;;
    select) select_revision "$stage" "$ref" "$repo" ${extra[@]+"${extra[@]}"} ;;
    deploy) deploy "$stage" "$revision" "$repo" "$timeout" "$resync" "$wait" "$patches" ;;
    apply)
        stamped "$stage" "$revision" "$repo" "$patches" true >"$CACHE/stamped.json"
        for app in "${apps[@]}"; do
            jq -e -c --arg n "$app" '.[] | select(.metadata.name == $n)' "$CACHE/stamped.json" >"$CACHE/one.json" ||
                die "Unknown Stage $stage component: $app"
            apply_app "$(cat "$CACHE/one.json")"
        done ;;
    sync) for name in $(start_syncs "$stage" "$resync" ${apps[@]+"${apps[@]}"}); do echo "started sync of $name"; done ;;
    wait)
        if [[ ${#apps[@]} -gt 0 ]]; then
            wait_for "$stage" "$revision" "$repo" "$timeout" "${apps[@]}"
            echo "PASS $(printf '%s, ' "${apps[@]}" | sed 's/, $//') Synced and Healthy at ${revision:0:12}"
        else
            wait_for "$stage" "$revision" "$repo" "$timeout" $(names "$stage")
            echo "PASS Stage $stage components Synced and Healthy at ${revision:0:12}"
        fi ;;
    applications) stamped "$stage" "$revision" "$repo" "$patches" | jq -c '{apiVersion: "v1", kind: "List", items: .}' ;;
    status)
        report=$(stage_problems "$stage" "$revision" "$repo" true ${apps[@]+"${apps[@]}"})
        problems=$(grep -v '^SKIP ' <<<"$report" || true)
        if [[ ${#apps[@]} -gt 0 ]]; then status_names=$(printf '%s\n' "${apps[@]}"); else status_names=$(names "$stage" true); fi
        for name in $status_names; do
            if grep -q "^$name:" <<<"$problems"; then echo "FAIL $name"
            elif grep -qx "SKIP $name (not activated)" <<<"$report"; then echo "SKIP $name (not activated)"
            else echo "OK   $name"; fi
        done
        [[ -z "$problems" ]] || { sed 's/^/  - /' <<<"$problems"; exit 1; } ;;
    owner) owner "$stage" "${positional[0]}" "${positional[1]}" "${positional[2]:-}" "$group" ;;
    delegated) delegated "$stage" "${positional[0]}" "${positional[1]}" "${positional[2]:-}" "$group" ;;
    preflight)
        [[ ${#apps[@]} -eq 0 ]] || all=true
        problems=$(preflight "$stage" "$repo" "$all" "$skip" ${apps[@]+"${apps[@]}"})
        [[ -z "$problems" ]] || sed 's/^/  - /' <<<"$problems"
        if [[ -z "$problems" ]]; then echo "PASS Stage $stage adoption preflight"; else echo "FAIL Stage $stage adoption preflight"; exit 1; fi ;;
    check-static) check_static "$stage" ;;
    check-delegations) check_delegations ;;
    *) die "unknown command $command" ;;
esac
