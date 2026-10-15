#!/usr/bin/env bash
# Model-free qualification of the token-required Studio MCP entry (OpenShift-MCP-ReadWrite): both personas discover
# it in Gen AI Studio, connect and list its tools with their own session; a missing session bearer is refused. Then
# direct calls to its Route (router CA verified): the developer reads their own project, is denied the hosting project,
# and an invalid bearer is rejected. Writes a private receipt. Browser and model-generated invocation are separate.
# Usage: stages/040-governed-models-as-a-service/qualify-catalog-mcp.sh --admin-kubeconfig FILE \
#   --developer-kubeconfig FILE --receipt FILE [--bootstrap-kubeconfig FILE] [--state FILE]
#   [--expected-stage040-revision SHA] [--expected-stage060-revision SHA]
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/shared/lib.sh"

KEY=OpenShift-MCP-ReadWrite
NS=redhat-ods-applications
UI_HOST=odh-dashboard-gen-ai-ui.redhat-ods-applications.svc
BOOT="${KUBECONFIG:-$HOME/.kube/config}" ADMIN="" DEVELOPER="" RECEIPT="" PUBLISH_ARGS=()
fail() { echo "FAIL $*"; exit 1; }
while [[ $# -gt 0 ]]; do
    case "$1" in
        --bootstrap-kubeconfig) BOOT=${2:-}; shift 2 ;;
        --admin-kubeconfig) ADMIN=${2:-}; shift 2 ;;
        --developer-kubeconfig) DEVELOPER=${2:-}; shift 2 ;;
        --receipt) RECEIPT=${2:-}; shift 2 ;;
        --state|--expected-stage040-revision|--expected-stage060-revision) PUBLISH_ARGS+=("$1" "${2:-}"); shift 2 ;;
        *) sed -n 's/^# Usage: //p; s/^#   /  /p' "$0" >&2; exit 1 ;;
    esac
done
[[ -n "$ADMIN" && -n "$DEVELOPER" && -n "$RECEIPT" ]] || fail "--admin-kubeconfig, --developer-kubeconfig and --receipt are required"
[[ ! -e "$RECEIPT" ]] || fail "Receipt already exists"
export KUBECONFIG="$BOOT"
load_env >/dev/null
check_oc_logged_in >/dev/null || fail "Project cluster guard rejected session"

# The published entry must be current (same checks as publish-catalog-mcp.sh --validate).
"$SCRIPT_DIR/publish-catalog-mcp.sh" --key "$KEY" --validate --bootstrap-kubeconfig "$BOOT" ${PUBLISH_ARGS[@]+"${PUBLISH_ARGS[@]}"} >/dev/null ||
    fail "Published Studio catalog entry is not current"
ENDPOINT=$(oc --request-timeout=10s get configmap gen-ai-aa-mcp-servers -n "$NS" -o json | jq -r --arg k "$KEY" '.data[$k] | fromjson | .url')
WORK=$(mktemp -d)
umask 077
jq -n '{passed: false, checks: {}, personas: {}}' >"$WORK/receipt.json"
receipt() { jq "$@" "$WORK/receipt.json" >"$WORK/receipt.next" && mv "$WORK/receipt.next" "$WORK/receipt.json"; }
FORWARD=""
finish() {
    local status=$?
    if [[ -n "$FORWARD" ]]; then kill "$FORWARD" 2>/dev/null && wait "$FORWARD" 2>/dev/null; receipt '.owned_forwards_closed = true'; fi
    [[ $status == 0 ]] && receipt '.passed = true'
    (set -o noclobber; cat "$WORK/receipt.json" >"$RECEIPT")
    rm -rf "$WORK"
}
trap finish EXIT
stop() { receipt --arg f "$1" '.failure = $f'; fail "$1"; }

# Persona sessions: the exact persona, tokens in memory only.
for pair in "$ADMIN:ai-admin" "$DEVELOPER:ai-developer"; do
    [[ $(KUBECONFIG="${pair%:*}" oc --request-timeout=10s whoami 2>/dev/null) == "${pair##*:}" ]] ||
        stop "Session ${pair%:*} is not a current ${pair##*:} login (scripts/platform/refresh-persona-logins.sh)"
done
ADMIN_TOKEN=$(KUBECONFIG="$ADMIN" oc --request-timeout=10s whoami -t)
DEVELOPER_TOKEN=$(KUBECONFIG="$DEVELOPER" oc --request-timeout=10s whoami -t)

# Gen AI Studio backend over a port-forward, TLS verified with the service CA for its service name.
oc --request-timeout=10s get configmap mlflow-service-ca -n "$NS" -o jsonpath='{.data.service-ca\.crt}' >"$WORK/service-ca.crt"
oc port-forward -n "$NS" service/odh-dashboard-gen-ai-ui :8143 --address=127.0.0.1 >"$WORK/forward.log" 2>&1 &
FORWARD=$!
for _ in $(seq 1 75); do
    PORT=$(sed -n 's/^Forwarding from 127.0.0.1:\([0-9]*\) .*/\1/p' "$WORK/forward.log" | head -1)
    [[ -n "$PORT" ]] && break
    sleep 0.2
done
[[ -n "${PORT:-}" ]] || stop "Owned Studio forward unavailable"
# GET a Studio path as CALLER (token), optionally with an MCP bearer; prints "<status>" and leaves the body in $WORK/body.
studio() {
    local path=$1 caller=$2 bearer=${3:-}
    sleep 1
    { printf 'header = "X-Forwarded-Access-Token: %s"\n' "$caller"; [[ -n "$bearer" ]] && printf 'header = "X-MCP-Bearer: Bearer %s"\n' "$bearer"; true; } |
        curl --config - -s --max-time 30 --max-filesize 1048576 --cacert "$WORK/service-ca.crt" --resolve "$UI_HOST:$PORT:127.0.0.1" \
        -H 'Accept: application/json' -o "$WORK/body" -w '%{http_code}' "https://$UI_HOST:$PORT$path" || echo 000
}
query=$(jq -rn --arg u "$ENDPOINT" '"namespace=demo-sandbox&server_url=\($u | @uri)"')
for user in ai-admin ai-developer; do
    token=$ADMIN_TOKEN; [[ "$user" == ai-developer ]] && token=$DEVELOPER_TOKEN
    [[ $(studio "/api/v1/aaa/mcps?namespace=demo-sandbox" "$token") == 200 ]] &&
        jq -e --arg k "$KEY" --arg u "$ENDPOINT" 'any(.data.servers[]?; .name == $k and .url == $u)' "$WORK/body" >/dev/null ||
        stop "Studio discovery entry is not discoverable for $user"
    [[ $(studio "/api/v1/mcp/status?$query" "$token" "$token") == 200 ]] && jq -e '.data.status == "connected"' "$WORK/body" >/dev/null ||
        stop "Per-session Studio status is not connected for $user"
    [[ $(studio "/api/v1/mcp/tools?$query" "$token" "$token") == 200 ]] && jq -e '.data.status == "success"
        and ([.data.tools[].name] | index("pods_get") and index("pods_list_in_namespace"))' "$WORK/body" >/dev/null ||
        stop "Studio tool inventory for $user lacks the reviewed pod tools"
    receipt --arg u "$user" --argjson n "$(jq '.data.tools | length' "$WORK/body")" \
        '.personas[$u] = {discovery_http: 200, status: "connected", tools_http: 200, tools_count: $n}'
done
code=$(studio "/api/v1/mcp/status?$query" "$DEVELOPER_TOKEN")
[[ "$code" =~ ^40[13]$ ]] || jq -e '.data.status == "error" and .data.error_details.code == "unauthorized" or .error.code == "unauthorized"' \
    "$WORK/body" >/dev/null || stop "A missing per-session MCP bearer was not refused"
receipt '.checks.missing_session_bearer_rejected = true'

# Direct JSON-RPC to the Route, verified against the public router CA (never its private key).
oc --request-timeout=10s get secret router-ca -n openshift-ingress-operator -o jsonpath='{.data.tls\.crt}' | base64 -d >"$WORK/router-ca.crt"
# tools/call pods_list_in_namespace NAMESPACE as TOKEN; prints the status, body (JSON or the SSE data line) in $WORK/rpc.
rpc() {
    local namespace=$1 token=$2 id=$3 status
    sleep 0.6
    status=$(printf 'header = "Authorization: Bearer %s"\n' "$token" | curl --config - -s --max-time 20 --cacert "$WORK/router-ca.crt" \
            -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' -H 'MCP-Protocol-Version: 2025-03-26' \
            --data-binary @<(jq -n -c --arg ns "$namespace" --argjson id "$id" '{jsonrpc: "2.0", id: $id, method: "tools/call",
                params: {name: "pods_list_in_namespace", arguments: {namespace: $ns}}}') \
            -o "$WORK/raw" -w '%{http_code}' "$ENDPOINT" || echo 000)
    { jq -e . "$WORK/raw" 2>/dev/null || sed -n 's/^data: //p' "$WORK/raw" | jq -c --argjson id "$id" 'select(.id == $id)'; } >"$WORK/rpc" 2>/dev/null || true
    echo "$status"
}
denied() {
    [[ "$1" =~ ^40[13]$ ]] || jq -e '(has("error") or .result.isError == true)
        and (tostring | ascii_downcase | contains("forbidden") or contains("the server has asked for the client to provide credentials"))' \
        "$WORK/rpc" >/dev/null 2>&1
}
[[ $(rpc demo-sandbox "$DEVELOPER_TOKEN" 1) == 200 ]] && jq -e 'has("result") and (.result.isError | not)' "$WORK/rpc" >/dev/null ||
    stop "Developer own-project direct read failed"
denied "$(rpc mcp-servers "$DEVELOPER_TOKEN" 2)" || stop "Developer hosting-project direct read was not forbidden"
denied "$(rpc demo-sandbox synthetic-invalid-studio-qualification 3)" || stop "Invalid bearer resource call was not rejected"
receipt '.checks += {verified_bff_tls: true, verified_direct_tls: true, both_session_tool_lists: true, developer_workload_read: true,
    developer_hosting_denied: true, invalid_resource_bearer_denied: true}'
echo "PASS Studio session discovery/tools and bounded direct caller permission checks. Browser/model-generated invocation is separate."
