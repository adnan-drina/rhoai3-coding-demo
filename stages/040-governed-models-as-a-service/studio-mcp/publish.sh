#!/usr/bin/env bash
# Publish the Gen AI Studio catalog entries (discovery keys of ConfigMap gen-ai-aa-mcp-servers) for the Stage 060 MCP
# servers: OpenShift-MCP (read-only, in-cluster) and OpenShift-MCP-ReadWrite (public Route). deploy.sh runs this with
# --defer-if-absent on every deploy; a repeat is a no-op. Writes only the one ConfigMap field per key, guarded by uid and
# resourceVersion, and records its ownership in a private journal under ~/.local/state/rhoai3-coding-demo/studio-mcp/.
# Run it yourself with --replace to apply a reviewed change of an already published entry (a different URL or
# description); without --replace a changed entry fails. Without --key both entries are published.
# Usage: stages/040-governed-models-as-a-service/studio-mcp/publish.sh [--key OpenShift-MCP|OpenShift-MCP-ReadWrite] [--replace] [--defer-if-absent]
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"
load_env
check_oc_logged_in
require_env GIT_REPO_URL "reviewed Stage 040 source repository"

# ── One Studio MCP discovery entry for a Stage 060 server, with its private ownership journal ─────────────────
publish_studio_mcp() {

    APP=040-genai-studio
    SOURCE=gitops/stages/040-governed-models-as-a-service/040-genai-studio
    NS=redhat-ods-applications
    CM=gen-ai-aa-mcp-servers
    KEY=OpenShift-MCP
    VALIDATE=false DEFER=false REPLACE=false DELEGATE=false STATE="${RHOAI_STUDIO_MCP_STATE:-}"
    KUBE="${KUBECONFIG:-$HOME/.kube/config}"
    EXPECTED_040="${RHOAI_STAGE040_EXPECTED_REVISION:-}"
    EXPECTED_060="${RHOAI_STAGE060_EXPECTED_REVISION:-}"
    fail() { echo "FAIL $*"; exit 1; }
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --key) KEY=${2:-}; shift 2 ;;
            --validate) VALIDATE=true; shift ;;
            --defer-if-absent) DEFER=true; shift ;;
            --replace) REPLACE=true; shift ;;
            --delegate) DELEGATE=true; shift ;;
            --state) STATE=${2:-}; shift 2 ;;
            --bootstrap-kubeconfig) KUBE=${2:-}; shift 2 ;;
            --expected-stage040-revision) EXPECTED_040=${2:-}; shift 2 ;;
            --expected-stage060-revision) EXPECTED_060=${2:-}; shift 2 ;;
            *) fail "unknown Studio catalog option $1" ;;
        esac
    done
    # Discovery key -> endpoint source and native object. "mcpserver": the in-cluster address the lifecycle operator
    # reports (token-less server, no Route). "route": the public HTTPS edge (token-required server).
    case "$KEY" in
        OpenShift-MCP)
            SOURCE_KIND=mcpserver; SERVER=openshift-mcp-server
            DESCRIPTION='Read-only OpenShift MCP tools, no token needed: without one the server acts as its bounded service account (view on the demo projects, cluster and node summaries); with your own OpenShift token it acts as you. In-cluster endpoint for the playground and workspaces. Secret resources and write operations are denied.' ;;
        OpenShift-MCP-ReadWrite)
            SOURCE_KIND=route; SERVER=openshift-mcp-server-rw
            DESCRIPTION='Read-write OpenShift MCP tools using your own OpenShift session token: create, update, scale and delete resources within your own project permissions. Secret resources are denied.' ;;
        *) fail "unknown key $KEY" ;;
    esac

    # Guarded session: a private kubeconfig, the repository's cluster guard.
    # True when no group or other permission bit is set (mode & 077 == 0).
    private_mode() { [[ -z "$(find "$1" -maxdepth 0 \( -perm -001 -o -perm -002 -o -perm -004 -o -perm -010 -o -perm -020 -o -perm -040 \))" ]]; }
    [[ -f "$KUBE" ]] && private_mode "$KUBE" ||
        fail "Private session input must exist with private permissions"
    export KUBECONFIG="$KUBE"
    load_env >/dev/null
    check_oc_logged_in >/dev/null || fail "Project cluster guard rejected session"
    read_optional() { oc --request-timeout=10s get "$@" --ignore-not-found -o json; }
    # JSON patch guarded by uid and resourceVersion; ops on stdin; prints the patched object.
    guarded_patch() {
        local kind=$1 name=$2 namespace=$3 before=$4
        jq -c --argjson b "$before" '[{op: "test", path: "/metadata/uid", value: $b.metadata.uid},
            {op: "test", path: "/metadata/resourceVersion", value: $b.metadata.resourceVersion}] + .' |
            oc --request-timeout=10s patch "$kind" "$name" -n "$namespace" --type=json --patch-file=/dev/stdin -o json ||
            fail "Exact owned patch failed; response suppressed"
    }

    # Stage 060 runtime: absent means defer; otherwise its pinned revision must be reviewed and its MCP stack qualified.
    backend=$(read_optional applications.argoproj.io 060-agent-tools -n openshift-gitops)
    if [[ -z "$backend" ]]; then
        [[ "$DEFER" == true ]] || fail "Stage060 catalog runtime is absent"
        echo "DEFERRED Studio catalog entry: deploy and qualify the separately owned Stage060 runtime first."
        return 0
    fi
    pinned=$(jq -r '.spec.source.targetRevision' <<<"$backend")
    if [[ -z "$EXPECTED_060" ]]; then
        EXPECTED_060=$pinned
        # Publishing accepts Stage 060's own pinned commit only when it is part of origin/main (published and reviewed).
        if [[ "$VALIDATE" == false ]]; then
            git -C "$REPO_ROOT" fetch -q origin main 2>/dev/null || true
            [[ "$pinned" =~ ^[0-9a-f]{40}$ ]] && git -C "$REPO_ROOT" merge-base --is-ancestor "$pinned" origin/main ||
                fail "Stage060 pinned revision is not part of origin/main; supply --expected-stage060-revision"
        fi
    fi
    [[ "$EXPECTED_060" =~ ^[0-9a-f]{40}$ && "$pinned" == "$EXPECTED_060" ]] || fail "Stage060 source differs from supplied reviewed revision"
    RHOAI_STAGE060_EXPECTED_REVISION="$pinned" "$REPO_ROOT/stages/060-agent-runtime-and-agentops/validate.sh" --component 060-agent-tools \
        >/dev/null 2>&1 || fail "Current catalog native ownership/configuration/readiness gate failed"
    if [[ "$SOURCE_KIND" == route ]]; then
        host=$(oc --request-timeout=10s get route "$SERVER" -n mcp-servers -o jsonpath='{.spec.host}')
        [[ "$host" =~ ^[a-z0-9.-]+$ ]] || fail "Qualified Route host is absent"
        url="https://$host/mcp"
    else
        url=$(oc --request-timeout=10s get mcpservers.mcp.x-k8s.io "$SERVER" -n mcp-servers -o jsonpath='{.status.address.url}')
        [[ "$url" == "http://$SERVER.mcp-servers.svc.cluster.local:8080/mcp" ]] || fail "Native in-cluster MCP address differs from the reviewed form"
    fi
    VALUE=$(jq -n -c -S --arg u "$url" --arg d "$DESCRIPTION" '{url: $u, transport: "streamable-http", description: $d}')

    # The 040-genai-studio Application: this repository, reconciled at the reviewed revision, preserving delegated fields.
    app=$(oc --request-timeout=10s get applications.argoproj.io "$APP" -n openshift-gitops -o json)
    if [[ -z "$EXPECTED_040" ]]; then
        # Run alone (not from deploy.sh): the deployed revision, which a publish accepts only when it is on origin/main.
        EXPECTED_040=$(jq -r '.spec.source.targetRevision' <<<"$app")
        if [[ "$VALIDATE" == false ]]; then
            git -C "$REPO_ROOT" fetch -q origin main 2>/dev/null || true
            [[ "$EXPECTED_040" =~ ^[0-9a-f]{40}$ ]] && git -C "$REPO_ROOT" merge-base --is-ancestor "$EXPECTED_040" origin/main ||
                fail "Stage040 deployed revision is not part of origin/main; supply --expected-stage040-revision"
        fi
    fi
    [[ "$EXPECTED_040" =~ ^[0-9a-f]{40}$ ]] || fail "Stage040 source differs from supplied reviewed revision"
    jq -e --arg repo "$GIT_REPO_URL" --arg path "$SOURCE" --arg rev "$EXPECTED_040" '.spec as $spec | .spec.source as $src | .status as $s
        | (.metadata.ownerReferences // [] | length) == 0 and .metadata.deletionTimestamp == null and .operation == null
        and $spec.project == "rhoai-demo" and ($spec.sources | not) and $src.repoURL == $repo and $src.path == $path
        and $spec.destination == {server: "https://kubernetes.default.svc", namespace: "openshift-gitops"}
        and $src.targetRevision == $rev and $s.sync.status == "Synced" and $s.sync.revision == $rev and $s.health.status == "Healthy"
        and $s.operationState.phase == "Succeeded" and $s.operationState.syncResult.revision == $rev
        and $s.operationState.syncResult.source.repoURL == $src.repoURL and $s.operationState.syncResult.source.path == $src.path
        and ($spec.syncPolicy.syncOptions // [] | index("RespectIgnoreDifferences=true"))' <<<"$app" >/dev/null ||
        fail "Stage040 Application is foreign, busy, not reconciled at the reviewed revision, or lacks field preservation"
    cm=$(oc --request-timeout=10s get configmap "$CM" -n "$NS" -o json)
    jq -e --arg t "$APP:/ConfigMap:$NS/$CM" '(.metadata.ownerReferences // [] | length) == 0 and .metadata.deletionTimestamp == null
        and .metadata.annotations["argocd.argoproj.io/tracking-id"] == $t' <<<"$cm" >/dev/null ||
        fail "Studio discovery ConfigMap is not the exact Stage040 input"

    # The Application must leave exactly this field to us (ignoreDifferences); --delegate adds that handoff once.
    FIELD=$(jq -n -c --arg cm "$CM" --arg ns "$NS" --arg k "$KEY" '{group: "", kind: "ConfigMap", name: $cm, namespace: $ns, jsonPointers: ["/data/" + $k]}')
    if ! jq -e --argjson f "$FIELD" 'any(.spec.ignoreDifferences[]?; (. + {group: (.group // "")}) == $f)' <<<"$app" >/dev/null; then
        [[ "$DELEGATE" == true && "$VALIDATE" == false ]] || fail "Exact Studio field delegation is absent (040-genai-studio ignoreDifferences in Git)"
        patched=$(jq -c --argjson f "$FIELD" '[{op: "test", path: "/spec", value: .spec},
            {op: "add", path: "/spec/ignoreDifferences", value: ((.spec.ignoreDifferences // []) + [$f])}]' <<<"$app" |
            guarded_patch applications.argoproj.io "$APP" openshift-gitops "$app")
        jq -e --argjson before "$app" --argjson f "$FIELD" '.spec == ($before.spec + {ignoreDifferences: (($before.spec.ignoreDifferences // []) + [$f])})' \
            <<<"$patched" >/dev/null || fail "Unexpected Application change"
    fi

    # Private ownership journal per published key: {application, cm_uid, key, value_sha256}.
    CM_UID=$(jq -r '.metadata.uid' <<<"$cm")
    JOURNAL="${STATE:-$HOME/.local/state/rhoai3-coding-demo/studio-mcp/$CM_UID-$KEY.json}"
    JOURNAL="${JOURNAL/#\~/$HOME}"
    IDENTITY=$(jq -n -c --arg a "$APP" --arg u "$CM_UID" --arg k "$KEY" --arg sha "$(printf '%s' "$VALUE" | shasum -a 256 | cut -d' ' -f1)" \
        '{application: $a, cm_uid: $u, key: $k, value_sha256: $sha}')
    journal() {
        [[ ! -L "$JOURNAL" ]] || fail "Ownership journal cannot be a symlink"
        (umask 077; mkdir -p "$(dirname "$JOURNAL")")
        private_mode "$(dirname "$JOURNAL")" || fail "Ownership journal directory must be private"
        if [[ -e "$JOURNAL" ]]; then
            private_mode "$JOURNAL" && jq -e --argjson id "$IDENTITY" '. == $id' "$JOURNAL" >/dev/null ||
                fail "Retained Studio field ownership differs"
            return
        fi
        (umask 077; set -o noclobber; jq . <<<"$IDENTITY" >"$JOURNAL")
    }
    OLD=$(jq -c '.data // {}' <<<"$cm")
    if [[ "$VALIDATE" == true ]]; then
        jq -e --arg k "$KEY" --argjson v "$VALUE" 'has($k) and (.[$k] | fromjson) == $v' <<<"$OLD" >/dev/null ||
            fail "Studio catalog field is missing or drifted"
        [[ -e "$JOURNAL" ]] || fail "Retained Studio field journal is absent"
        journal
        echo "PASS Exact Studio catalog configuration; session authentication is separate."
        return 0
    fi
    present=$(jq -r --arg k "$KEY" 'has($k)' <<<"$OLD")
    [[ "$present" == false || -e "$JOURNAL" ]] || fail "Existing Studio catalog field has no retained ownership journal"
    changed=$(jq -r --arg k "$KEY" --argjson v "$VALUE" 'has($k) and (.[$k] | fromjson) != $v' <<<"$OLD")
    if [[ "$changed" == true ]]; then
        # A reviewed change of a published field: explicit --replace, journal rewritten, value replaced in place.
        [[ "$REPLACE" == true ]] || fail "Existing Studio catalog field differs; pass --replace for a reviewed change"
        jq -e --arg k "$KEY" '.key == $k' "$JOURNAL" >/dev/null || fail "Retained journal belongs to another field"
        rm -f "$JOURNAL"
    fi
    journal
    if [[ "$present" == true && "$changed" == false ]]; then
        echo "PASS Studio catalog publication repeat was a no-op."
        return 0
    fi
    # An empty data map is omitted by the API server, so the first key must create the map itself.
    op=add; [[ "$changed" == true ]] && op=replace
    after=$(jq -c --arg k "$KEY" --arg v "$VALUE" --arg op "$op" --argjson cm "$cm" \
        'if $cm | has("data") then [{op: "test", path: "/data", value: .}, {op: $op, path: "/data/" + $k, value: $v}]
         else [{op: "add", path: "/data", value: {($k): $v}}] end' <<<"$OLD" | guarded_patch configmap "$CM" "$NS" "$cm")
    jq -e --arg u "$CM_UID" --argjson old "$OLD" --arg k "$KEY" --arg v "$VALUE" '.metadata.uid == $u and .data == ($old + {($k): $v})' \
        <<<"$after" >/dev/null || fail "Unexpected discovery ConfigMap change"
    echo "PASS $([[ "$changed" == true ]] && echo Replaced || echo Added) the single nonsecret Studio catalog field; other entries retained."
}

# Both entries unless one --key is named; every other option applies to each entry.
if [[ " $* " == *" --key "* ]]; then
    publish_studio_mcp "$@"
else
    publish_studio_mcp --key OpenShift-MCP "$@"
    publish_studio_mcp --key OpenShift-MCP-ReadWrite "$@"
fi
