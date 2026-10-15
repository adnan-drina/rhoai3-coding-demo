#!/usr/bin/env bash
# Read-only data-plane probes as the logged-in administrator: an authenticated native metrics query, and one
# synthetic trace sent through the native OpenTelemetry collector and read back from Tempo by its ID.
# Creates no workloads (local port-forwards only). Persona sessions and dashboard UI acceptance are separate.
# Usage: stages/010-openshift-ai-platform-foundation/validate-foundation-services.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/shared/validate-lib.sh"

read_json() { oc --request-timeout=20s get "$@" -o json; }
TOKEN=$(oc whoami -t)  # memory only: reaches curl through --config on stdin, never an argument or a log line
WORK=$(mktemp -d)
# check() runs each probe in a subshell, so port-forward PIDs are recorded in a file for cleanup.
cleanup() {
    while read -r pid; do kill "$pid" 2>/dev/null || true; done < <(cat "$WORK/pids" 2>/dev/null)
    rm -rf "$WORK"
}
trap cleanup EXIT

# Authenticated HTTPS (demo certificates, -k) or plain HTTP to a local port-forward; prints the response body.
api() {
    local url=$1; shift
    printf 'header = "Authorization: Bearer %s"\n' "$TOKEN" |
        curl --config - -sk --max-time 20 -H 'Accept: application/json' "$@" "$url"
}

# Port-forward a Service port to a free local port; prints the local port.
forward() {
    local service=$1 namespace=$2 port=$3 log="$WORK/forward-$1-$3.log"
    oc -n "$namespace" port-forward "service/$service" ":$port" --address=127.0.0.1 >"$log" 2>&1 &
    echo "$!" >>"$WORK/pids"
    for _ in $(seq 1 50); do
        local local_port
        local_port=$(sed -n 's/^Forwarding from 127.0.0.1:\([0-9]*\) .*/\1/p' "$log" | head -1)
        if [[ -n "$local_port" ]]; then echo "$local_port"; return 0; fi
        sleep 0.1
    done
    return 1
}

dsci=$(read_json dscinitialization default-dsci)
NS=$(jq -r '.spec.monitoring.namespace' <<<"$dsci")
monitors=$(read_json monitorings.services.platform.opendatahub.io)

dsci_ready() {
    jq -e '.status.phase == "Ready" and any(.status.conditions[]?; .type == "Ready" and .status == "True")' \
        <<<"$dsci" >/dev/null && echo yes || echo no
}
monitoring_ready() {
    jq -e '(.items | length) == 1 and (.items[0] | .status.phase == "Ready"
        and .status.observedGeneration == .metadata.generation
        and any(.status.conditions[]?; .type == "Ready" and .status == "True"))' \
        <<<"$monitors" >/dev/null && echo yes || echo no
}
# The native namespace proxy needs the namespace parameter for its SAR and label filter. Recency is checked in
# PromQL on the server clock; an empty answer (Thanos during an observability resync) is retried for ~30 s.
metrics_query() {
    local port result query='up == 1 and (time() - timestamp(up) >= 0) and (time() - timestamp(up) <= 120)'
    port=$(forward data-science-prometheus-namespace-proxy "$NS" 8443) || { echo "no port-forward"; return; }
    for _ in 1 2 3 4 5 6; do
        result=$(api "https://127.0.0.1:$port/api/v1/query" -G --data-urlencode "query=$query" \
            --data-urlencode "namespace=$NS") || result='{}'
        if jq -e --arg ns "$NS" '.status == "success"
            and any(.data.result[]?; .metric.namespace == $ns and (.value[1] | tonumber) == 1)' \
            <<<"$result" >/dev/null 2>&1; then echo yes; return; fi
        sleep 5
    done
    jq -r '"status \(.status // "none"), \(.data.result // [] | length) samples"' <<<"$result" 2>/dev/null || echo no
}
collector_config() {
    read_json opentelemetrycollector data-science-collector -n "$NS" | jq -e '.spec.config | type == "object"
        and (.receivers.otlp.protocols | has("http"))
        and (.service.pipelines.traces.receivers | index("otlp") != null)' >/dev/null && echo yes || echo no
}
# Tempo authorizes a virtual resource that oc can-i can mis-map; a SubjectAccessReview checks the exact attributes.
collector_can_write_tempo() {
    local sa
    sa=$(read_json statefulset data-science-collector-collector -n "$NS" | jq -r '.spec.template.spec.serviceAccountName')
    jq -n --arg user "system:serviceaccount:$NS:$sa" --arg ns "$NS" '{apiVersion: "authorization.k8s.io/v1",
        kind: "SubjectAccessReview", spec: {user: $user,
        resourceAttributes: {group: "tempo.grafana.com", resource: $ns, name: "traces", verb: "create"}}}' |
        oc --request-timeout=20s create --raw /apis/authorization.k8s.io/v1/subjectaccessreviews -f - |
        jq -e '.status.allowed == true' >/dev/null && echo yes || echo no
}
# Send one synthetic span through the collector, then read it back from Tempo by its trace ID (up to 90 s).
trace_roundtrip() {
    local trace_id span_id start port endpoint host tempo_port url path body deadline
    trace_id=$(uuidgen | tr -d '-' | tr 'A-F' 'a-f')
    span_id=${trace_id:0:16}
    start=$(($(date +%s) * 1000000000))
    echo "[INFO] Synthetic trace ID $trace_id" >&2
    port=$(forward data-science-collector-collector "$NS" 4318) || { echo "no collector port-forward"; return; }
    body=$(jq -n --arg t "$trace_id" --arg s "$span_id" --arg start "$start" --arg end "$((start + 1000000))" \
        '{resourceSpans: [{resource: {attributes: [{key: "service.name", value: {stringValue: "foundation-validation"}}]},
          scopeSpans: [{scope: {name: "foundation-validation"}, spans: [{traceId: $t, spanId: $s,
          name: "foundation-roundtrip", kind: 1, startTimeUnixNano: $start, endTimeUnixNano: $end}]}]}]}')
    api "http://127.0.0.1:$port/v1/traces" -H 'Content-Type: application/json' --data "$body" |
        jq -e '(.partialSuccess.rejectedSpans // 0) == 0' >/dev/null || { echo "collector rejected the span"; return; }
    url=$(read_json persesdatasource tempo-datasource -n "$NS" | jq -r '.spec.config.plugin.spec.proxy.spec.url')
    [[ "$url" == https://* ]] || { echo "no Tempo datasource endpoint"; return; }
    endpoint=${url#https://}
    host=${endpoint%%/*}
    path=/${endpoint#*/}
    [[ "$endpoint" == */* ]] || path=/
    tempo_port=${host##*:}
    [[ "$host" == *:* ]] || tempo_port=443
    port=$(forward "${host%%.*}" "$NS" "$tempo_port") || { echo "no Tempo port-forward"; return; }
    deadline=$((SECONDS + 90))
    local encoded
    encoded=$(printf '%s' "$trace_id" | xxd -r -p | base64)
    while ((SECONDS < deadline)); do
        if api "https://127.0.0.1:$port${path%/}/api/traces/$trace_id" -H "X-Scope-OrgID: $NS" -f 2>/dev/null |
            jq -e --arg id "$trace_id" --arg b64 "$encoded" '[(.batches // .resourceSpans // [])[]
                | (.scopeSpans // .instrumentationLibrarySpans // [])[] | .spans[]?.traceId]
                | any(. as $x | ($x | ascii_downcase) == $id or $x == $b64)' >/dev/null 2>&1; then
            echo yes; return
        fi
        sleep 3
    done
    echo "trace not found in Tempo within 90 s"
}

check "DSCInitialization Ready" dsci_ready yes
check "Exactly one native Monitoring, Ready at its current generation" monitoring_ready yes
check "Authenticated native metrics query returns a recent healthy target in $NS" metrics_query yes
check "Collector exposes an OTLP/HTTP trace receiver" collector_config yes
check "Collector service account may write the native Tempo tenant" collector_can_write_tempo yes
check "One synthetic trace traverses the collector and is read back from Tempo by its exact ID" trace_roundtrip yes
echo "Scope: administrator data-plane probes; persona sessions and browser UI acceptance are separate."
validation_summary
