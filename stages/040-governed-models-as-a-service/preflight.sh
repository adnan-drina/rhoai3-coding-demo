#!/usr/bin/env bash
# Read-only Stage 040 prerequisites before the first write: Stages 010 and 030 reconciled and delegating what Stage 040
# owns; existing Applications, namespaces and objects already Stage 040's; the Gateway's certificate source; provider
# credentials available; a retained MaaS database consistent with its credentials and URI.
# Prints "fresh" (no database yet) or "retained" on stdout; errors go to stderr. Secret values are compared, never
# printed or passed as arguments.
# Usage: stages/040-governed-models-as-a-service/preflight.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/shared/lib.sh"
load_env >&2
check_oc_logged_in >&2

STAGE_APPS="$REPO_ROOT/scripts/shared/stage_apps.py"
DB_NS=models-as-a-service-db
fail() { echo "ERROR: $*" >&2; exit 1; }
read_optional() { oc --request-timeout=10s get "$@" --ignore-not-found -o json; }
secret_present() { [[ -n "$(oc --request-timeout=10s get secret "$1" -n "$2" --ignore-not-found -o jsonpath='{.metadata.uid}')" ]]; }
# Exact tracking id of the Stage 040 component that renders KIND NAME [NAMESPACE].
expected_tracking() {
    local owner group=${4:-}
    owner=$(python3 "$STAGE_APPS" owner 040 "$1" "$2" ${3:+"$3"} --group "$group" 2>/dev/null) || return 1
    echo "$owner:$group/$1:${3:-openshift-gitops}/$2"
}
# An existing object must carry its exact Stage 040 tracking id, no owner and no deletion.
require_ours() {
    local kind=$1 resource=$2 name=$3 namespace=${4:-} group=${5:-} live expected
    live=$(read_optional "$resource" "$name" ${namespace:+-n "$namespace"})
    [[ -z "$live" ]] && return 0
    expected=$(expected_tracking "$kind" "$name" "$namespace" "$group") || fail "$kind $name is not rendered by Stage 040"
    jq -e --arg t "$expected" '.metadata.annotations["argocd.argoproj.io/tracking-id"] == $t
        and (.metadata.ownerReferences // [] | length) == 0 and .metadata.deletionTimestamp == null' <<<"$live" >/dev/null ||
        fail "existing $kind $name requires a reviewed adoption"
}

# Prerequisite stages and the fields Stage 010 delegates to Stage 040.
python3 "$STAGE_APPS" status 010 >/dev/null || fail "Stage 010 must be reconciled first"
python3 "$STAGE_APPS" status 030 --repo-url "$GIT_REPO_URL" >/dev/null || fail "Stage 030 must be reconciled from this repository first"
delegated=$(python3 "$STAGE_APPS" delegated 010 DataScienceCluster default-dsc --group datasciencecluster.opendatahub.io)
for field in aigateway ogx; do
    grep -qx "/spec/components/$field" <<<"$delegated" || fail "Stage 010 must delegate /spec/components/$field"
done
delegated=$(python3 "$STAGE_APPS" delegated 010 OdhDashboardConfig odh-dashboard-config redhat-ods-applications --group opendatahub.io)
for field in genAiStudio genAiTracing modelAsService vLLMDeploymentOnMaaS externalModels llmdTemplates guardrails \
    agentConfigManagement promptManagement; do
    grep -qx "/spec/dashboardConfig/$field" <<<"$delegated" || fail "Stage 010 must delegate dashboardConfig.$field"
done
[[ -z "$(read_optional applications.argoproj.io 040-governed-models-as-a-service -n openshift-gitops)" ]] ||
    fail "Retired single Stage 040 Application still exists; finish the component move (docs/OPERATIONS.md)"

# Existing Applications and rendered objects; namespaces must also be tracked (preflight accepts untracked ones).
python3 "$STAGE_APPS" preflight 040 --repo-url "$GIT_REPO_URL" >&2
for ns in models-as-a-service internal-models "$DB_NS" kuadrant-system external-models openshift-lws-operator; do
    require_ours Namespace namespace "$ns"
done
# The namespace-label helper keeps its exact, narrow RBAC.
rbac=$(read_optional clusterrole prepare-maas-route-access)
[[ -z "$rbac" ]] || jq -e '.rules == [{apiGroups: [""], resources: ["namespaces"],
    resourceNames: ["redhat-ods-applications", "redhat-ai-gateway-infra"], verbs: ["get", "patch"]}]' <<<"$rbac" >/dev/null ||
    fail "Namespace-label permission scope differs"
binding=$(read_optional clusterrolebinding prepare-maas-route-access)
[[ -z "$binding" ]] || jq -e '.roleRef == {apiGroup: "rbac.authorization.k8s.io", kind: "ClusterRole", name: "prepare-maas-route-access"}
    and .subjects == [{kind: "ServiceAccount", name: "prepare-maas-route-access", namespace: "redhat-ods-applications"}]' \
    <<<"$binding" >/dev/null || fail "Namespace-label binding differs"

# The Gateway terminates TLS with the cluster's cert-manager ingress certificate (referenced, not copied).
[[ $(oc --request-timeout=10s get ingresscontrollers.operator.openshift.io default -n openshift-ingress-operator \
    -o jsonpath='{.spec.defaultCertificate.name}') == cert-manager-ingress-cert ]] || fail "Ingress certificate source requires review"
[[ $(oc --request-timeout=10s get secret cert-manager-ingress-cert -n openshift-ingress \
    -o go-template='{{if index .data "tls.crt"}}crt{{end}}|{{if index .data "tls.key"}}key{{end}}') == "crt|key" ]] ||
    fail "Gateway certificate Secret is incomplete"

# Provider credentials: an existing Secret (metadata only) or the key in the environment.
secret_present openai-provider-api-key external-models || secret_present openai-provider-api-key models-as-a-service ||
    [[ -n "${OPENAI_API_KEY:-}${RHOAI_OPENAI_API_KEY:-}" ]] || fail "Authorized OpenAI provider credential must be available"
secret_present anthropic-provider-api-key external-models || [[ -n "${ANTHROPIC_API_KEY:-}" ]] ||
    fail "Authorized Anthropic provider credential must be available"
secret_present nvidia-provider-api-key external-models || [[ -n "${NVIDIA_API_KEY:-}" ]] ||
    fail "Authorized NVIDIA provider credential must be available"

# Retained database: credentials, configuration, workload and storage must be consistent, or all absent.
database=$(read_optional statefulset maas-postgres -n "$DB_NS")
pvcs='[]'
[[ -n "$(read_optional namespace "$DB_NS")" ]] && pvcs=$(oc --request-timeout=10s get pvc -n "$DB_NS" -o json | jq -c '.items')
credential=false; secret_present maas-postgres-credentials "$DB_NS" && credential=true
config=false; secret_present maas-db-config redhat-ai-gateway-infra && config=true
legacy=false; secret_present maas-db-config redhat-ods-applications && legacy=true
[[ "$credential" == true || ( -z "$database" && "$pvcs" == '[]' && "$config" == false && "$legacy" == false ) ]] ||
    fail "Partial retained database forbids credential generation"
if [[ "$credential" == true ]]; then
    components=$(python3 "$STAGE_APPS" names 040 --all | jq -R . | jq -s -c .)
    runtime_ok='.metadata as $m | ($m.ownerReferences // [] | length) == 0 and $m.deletionTimestamp == null
        and ($m.annotations["argocd.argoproj.io/tracking-id"] // "" | . == "" or (split(":")[0] as $a | $apps | index($a)))'
    secret=$(oc --request-timeout=10s get secret maas-postgres-credentials -n "$DB_NS" -o json)
    printf '%s' "$secret" | jq -e --argjson apps "$components" "$runtime_ok"' and (.data | map_values(@base64d)
        | .POSTGRESQL_USER == "maas" and .POSTGRESQL_DATABASE == "maas" and (.POSTGRESQL_PASSWORD // "") != "")' >/dev/null ||
        fail "Existing database credential ownership or contract differs"
    MAAS_DB_URI=$(printf '%s' "$secret" | jq -r '.data | map_values(@base64d) | "postgresql://\(.POSTGRESQL_USER | @uri):"
        + "\(.POSTGRESQL_PASSWORD | @uri)@maas-postgres.models-as-a-service-db.svc.cluster.local:5432/\(.POSTGRESQL_DATABASE | @uri)?sslmode=disable"')
    export MAAS_DB_URI
    for pair in redhat-ai-gateway-infra:$config redhat-ods-applications:$legacy; do
        [[ "${pair#*:}" == true ]] || continue
        oc --request-timeout=10s get secret maas-db-config -n "${pair%%:*}" -o json |
            jq -e --argjson apps "$components" "$runtime_ok"' and (.data.DB_CONNECTION_URL // "" | @base64d) == $ENV.MAAS_DB_URI' \
            >/dev/null || fail "Existing MaaS database configuration in ${pair%%:*} differs; restore the original matching credentials"
    done
fi
[[ -z "$database" ]] || require_ours StatefulSet statefulset maas-postgres "$DB_NS" apps
jq -e --argjson db "${database:-null}" 'all(.[]; .metadata.name == "data-maas-postgres-0" and .status.phase == "Bound"
    and .metadata.deletionTimestamp == null and $db != null
    and all(.metadata.ownerReferences[]?; .uid == $db.metadata.uid))' <<<"$pvcs" >/dev/null ||
    fail "Unexpected or unavailable retained database storage"
[[ $(oc --request-timeout=10s get storageclass gp3-csi -o jsonpath='{.provisioner}') == ebs.csi.aws.com ]] ||
    fail "Reviewed gp3 storage unavailable"

if [[ "$credential" == false && -z "$database" && "$pvcs" == '[]' && "$config" == false ]]; then echo fresh; else echo retained; fi
