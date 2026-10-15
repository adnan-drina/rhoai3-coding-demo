#!/usr/bin/env bash
# Runtime MaaS database credentials: reuses maas-postgres-credentials if present (never rotates a database password),
# otherwise generates them, then ensures maas-db-config (the connection URI) in redhat-ai-gateway-infra.
# --fresh-database: deploy.sh's preflight saw a clean install, so a StatefulSet created since then may be adopted.
# Values travel only through the environment and pipes; nothing is printed.
# Usage: stages/040-governed-models-as-a-service/setup-database.sh [--fresh-database]
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/shared/lib.sh"
load_env
check_oc_logged_in

FRESH=false
case "${1:-}" in
    --fresh-database) FRESH=true ;;
    "") ;;
    *) echo "Usage: $0 [--fresh-database]" >&2; exit 1 ;;
esac
NS=models-as-a-service-db
APP=040-maas-database
INFRA=redhat-ai-gateway-infra
fail() { echo "ERROR: $*" >&2; exit 1; }
read_secret() { oc --request-timeout=10s get secret "$1" -n "$2" --ignore-not-found -o json; }
namespace_exists() { [[ -n "$(oc --request-timeout=10s get namespace "$1" --ignore-not-found -o name)" ]]; }
COMPONENTS=$(python3 "$REPO_ROOT/scripts/shared/stage_apps.py" names 040 --all | jq -R . | jq -s -c .)
# Unowned, not terminating, and untracked or tracked by a Stage 040 component.
safe_secret() {
    jq -e --argjson apps "$COMPONENTS" '.metadata as $m | ($m.ownerReferences // [] | length) == 0
        and $m.deletionTimestamp == null
        and ($m.annotations["argocd.argoproj.io/tracking-id"] // "" | . == "" or (split(":")[0] as $a | $apps | index($a)))' \
        >/dev/null
}
# A runtime Secret from {key: value} JSON on stdin.
create_secret() {
    jq --arg name "$1" --arg ns "$2" '{apiVersion: "v1", kind: "Secret", type: "Opaque", stringData: .,
        metadata: {name: $name, namespace: $ns, labels: {"app.kubernetes.io/name": $name,
            "app.kubernetes.io/component": "configuration", "app.kubernetes.io/part-of": "rhoai3-coding-demo",
            "app.kubernetes.io/managed-by": "stage040-runtime"}}}' |
        oc --request-timeout=10s create -f - >/dev/null || fail "Native database API operation failed; no credential details returned"
}

for attempt in $(seq 1 60); do
    tracking=$(oc --request-timeout=10s get namespace "$NS" --ignore-not-found \
        -o jsonpath='{.metadata.uid}{"|"}{.metadata.annotations.argocd\.argoproj\.io/tracking-id}')
    if [[ -n "${tracking%%|*}" ]]; then
        [[ "${tracking#*|}" == "$APP:/Namespace:openshift-gitops/$NS" ]] || fail "Database namespace not owned by Stage 040"
        break
    fi
    (( attempt < 60 )) || fail "Database namespace readiness timed out"
    sleep 5
done

existing=$(read_secret maas-postgres-credentials "$NS")
config=""
namespace_exists "$INFRA" && config=$(read_secret maas-db-config "$INFRA")
[[ -n "$existing" || -z "$config" ]] || fail "Partial retained database configuration forbids credential generation"
if [[ -n "$existing" ]]; then
    printf '%s' "$existing" | safe_secret || fail "Runtime database Secret ownership or tracking differs"
    credentials=$(printf '%s' "$existing" | jq -c '.data | map_values(@base64d)
        | {user: .POSTGRESQL_USER, password: .POSTGRESQL_PASSWORD, database: .POSTGRESQL_DATABASE}') ||
        fail "Existing database Secret has missing or invalid keys"
    printf '%s' "$credentials" | jq -e '.user == "maas" and .database == "maas" and (.password // "") != ""' >/dev/null ||
        fail "Existing database credentials differ from the reviewed contract"
    echo "Reusing existing MaaS database credentials"
else
    claims=$(oc --request-timeout=10s get pvc -n "$NS" -o json | jq '.items | length')
    workload=$(oc --request-timeout=10s get statefulset maas-postgres -n "$NS" --ignore-not-found -o json)
    [[ "$FRESH" == true || ( "$claims" == 0 && -z "$workload" ) ]] || fail "Retained database has no credentials; restore the original Secret"
    if [[ "$FRESH" == true ]]; then
        [[ "$claims" == 0 ]] || fail "Storage appeared after the clean-install preflight; refusing new credentials"
        [[ -z "$workload" ]] || jq -e --arg app "$APP" '.metadata.annotations["argocd.argoproj.io/tracking-id"] // ""
            | startswith($app + ":")' <<<"$workload" >/dev/null || fail "Foreign PostgreSQL workload appeared"
    fi
    MAAS_DB_PASSWORD=$(openssl rand -hex 24)
    export MAAS_DB_PASSWORD
    credentials=$(jq -n -c '{user: "maas", password: $ENV.MAAS_DB_PASSWORD, database: "maas"}')
    unset MAAS_DB_PASSWORD
    printf '%s' "$credentials" | jq '{POSTGRESQL_USER: .user, POSTGRESQL_PASSWORD: .password, POSTGRESQL_DATABASE: .database}' |
        create_secret maas-postgres-credentials "$NS"
fi
# Percent-encoded like Python's quote(safe=""): jq @uri keeps only unreserved characters.
MAAS_DB_URI=$(printf '%s' "$credentials" | jq -r --arg ns "$NS" \
    '"postgresql://\(.user | @uri):\(.password | @uri)@maas-postgres.\($ns).svc.cluster.local:5432/\(.database | @uri)?sslmode=disable"')
export MAAS_DB_URI

for attempt in $(seq 1 120); do
    namespace_exists "$INFRA" && break
    (( attempt < 120 )) || fail "Native AIGateway infrastructure namespace readiness timed out"
    sleep 5
done
config=$(read_secret maas-db-config "$INFRA")
if [[ -n "$config" ]]; then
    printf '%s' "$config" | safe_secret || fail "Runtime database configuration ownership or tracking differs"
    printf '%s' "$config" | jq -e '(.data.DB_CONNECTION_URL // "" | @base64d) == $ENV.MAAS_DB_URI' >/dev/null ||
        fail "Existing MaaS DB URI differs; restore the matching original configuration"
else
    jq -n '{DB_CONNECTION_URL: $ENV.MAAS_DB_URI}' | create_secret maas-db-config "$INFRA"
fi
echo "PASS MaaS runtime database configuration; plaintext transport remains namespace-scoped demo intent"
