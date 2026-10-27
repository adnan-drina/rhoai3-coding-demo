#!/usr/bin/env bash
# Stage 040: MaaS operators, database, Gateway and policies, MaaS, models, access and Gen AI Studio, at one reviewed
# published revision. Before the first write: Stages 010 and 030 reconciled and delegating what Stage 040 owns, the
# adoption preflight, provider credentials available, and a retained MaaS database consistent with its credentials.
# Then: the component Applications; provider and database credentials created in the cluster (never in Git); the
# Studio catalog entries for the Stage 060 MCP servers (studio-mcp/publish.sh; deferred until Stage 060 deploys them); the model registry
# records of the deployed models and their prepared alternates. Secret values travel only through pipes and jq's
# environment: never Git, arguments or output.
# RHOAI_STAGE040_ROTATE_PROVIDER_SECRET=true replaces the OpenAI provider key in place from OPENAI_API_KEY.
# --component 040-showback-demo reconciles only the optional showback bundle, with shared prerequisites read-only.
# A default deployment also reconciles that bundle at the same revision once it is installed.
# Team access, offer dashboards and external metering come from source; no keys are minted.
# Usage: stages/040-governed-models-as-a-service/deploy.sh [--revision REF] [--component 040-showback-demo]
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"
ref="${GIT_REPO_BRANCH:-HEAD}" COMPONENT=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --revision) ref="${2:?}"; shift 2 ;;
    --component) COMPONENT="${2:?}"; shift 2 ;;
    *) sed -n 's/^# Usage: //p' "$0" >&2; exit 1 ;;
  esac
done
[[ -z "$COMPONENT" || "$COMPONENT" == 040-showback-demo ]] || { log_error "Unknown Stage 040 component: $COMPONENT"; exit 1; }
load_env
check_oc_logged_in
require_env GIT_REPO_URL "reviewed Stage 040 source repository"
assert_required_env
STAGE_APPS="$REPO_ROOT/scripts/stage-apps.sh"

# The MaaS controller deliberately delegates customization of this file through managed=false.
# Keep its ownership, pre-processing profile and other data. Refuse an unreviewed third profile.
# enabled=false restores the reviewed baseline while retaining the metering database.
showback_metering_profile() {
    local action=$1 desired config baseline candidate target live current patch updated
    desired=$(oc kustomize "$REPO_ROOT/gitops/stages/040-governed-models-as-a-service/040-showback-demo" |
        ruby -ryaml -rjson -e 'puts JSON.generate(YAML.load_stream(STDIN.read).compact)')
    config=$(jq -c '.[] | select(.kind == "ConfigMap" and .metadata.name == "showback-external-metering-profile")' <<<"$desired")
    [[ -n "$config" ]] || return 0
    jq -e '.data.enabled == "true" or .data.enabled == "false"' <<<"$config" >/dev/null || {
        log_error "External metering requires an explicit source activation state"; return 1;
    }
    baseline=$(jq -ce '.data["baseline.json"] | fromjson' <<<"$config")
    candidate=$(jq -ce '.data["profile.json"] | fromjson' <<<"$config")
    target=$baseline
    [[ $(jq -r '.data.enabled' <<<"$config") != true ]] || target=$candidate
    live=$(oc --request-timeout=10s get configmap payload-processing-plugins -n openshift-ingress -o json)
    jq -e '.metadata.annotations["opendatahub.io/managed"] == "false"
        and any(.metadata.ownerReferences[]?; .kind == "Config" and .name == "default")
        and (.data["custom-pre-processing-ipp-config.yaml"] | type == "string" and length > 0)' <<<"$live" >/dev/null || {
        log_error "MaaS processing profile is not the expected delegated default-tenant configuration"; return 1;
    }
    current=$(jq -r '.data["custom-ipp-config.yaml"]' <<<"$live" |
        ruby -ryaml -rjson -e 'puts JSON.generate(YAML.load(STDIN.read))')
    jq -e --argjson baseline "$baseline" --argjson candidate "$candidate" \
        '. == $baseline or . == $candidate' <<<"$current" >/dev/null || {
        log_error "Processing profile differs from the reviewed baseline and metering profile; refusing to overwrite it"; return 1;
    }
    [[ "$action" == activate ]] || return 0
    if jq -e --argjson target "$target" '. == $target' <<<"$current" >/dev/null; then
        oc rollout status deployment/payload-processing -n openshift-ingress --timeout=180s >/dev/null
        log_info "MaaS metering profile matches source and existing rollout is ready; event delivery must still be verified"
        return 0
    fi
    if [[ $(jq -r '.data.enabled' <<<"$config") == true ]]; then
        oc rollout status deployment/showback-external-metering -n redhat-ods-monitoring --timeout=180s >/dev/null
    fi
    # Test the resource version atomically so an intervening administrator edit cannot be overwritten.
    patch=$(jq -n --arg rv "$(jq -r '.metadata.resourceVersion' <<<"$live")" --arg profile "$target" \
        '[{op:"test",path:"/metadata/resourceVersion",value:$rv},
          {op:"replace",path:"/data/custom-ipp-config.yaml",value:$profile}]')
    printf '%s' "$patch" | oc patch configmap payload-processing-plugins -n openshift-ingress \
        --type=json --patch-file=/dev/stdin >/dev/null
    updated=$(oc --request-timeout=10s get configmap payload-processing-plugins -n openshift-ingress -o json)
    jq -e --argjson before "$live" --arg profile "$target" '
        .data["custom-ipp-config.yaml"] == $profile
        and (del(.data["custom-ipp-config.yaml"], .metadata.resourceVersion, .metadata.managedFields)
          == ($before | del(.data["custom-ipp-config.yaml"], .metadata.resourceVersion, .metadata.managedFields)))' \
        <<<"$updated" >/dev/null || { log_error "Processing profile readback or preservation check failed"; return 1; }
    oc rollout restart deployment/payload-processing -n openshift-ingress >/dev/null
    oc rollout status deployment/payload-processing -n openshift-ingress --timeout=180s >/dev/null
    log_success "Reviewed external-metering profile loaded; existing MaaS identity and access controls preserved"
}

# ── Read-only preflight; prints "fresh" (no MaaS database yet) or "retained" ───────────────────────────────────
stage_preflight() {

    DB_NS=models-as-a-service-db
    fail() { echo "ERROR: $*" >&2; exit 1; }
    read_optional() { oc --request-timeout=10s get "$@" --ignore-not-found -o json; }
    secret_present() { [[ -n "$(oc --request-timeout=10s get secret "$1" -n "$2" --ignore-not-found -o jsonpath='{.metadata.uid}')" ]]; }
    # Exact tracking id of the Stage 040 component that renders KIND NAME [NAMESPACE].
    expected_tracking() {
        local owner group=${4:-}
        owner=$("$STAGE_APPS" owner 040 "$1" "$2" ${3:+"$3"} --group "$group" 2>/dev/null) || return 1
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
    "$STAGE_APPS" status 010 >/dev/null || fail "Stage 010 must be reconciled first"
    "$STAGE_APPS" status 030 --repo-url "$GIT_REPO_URL" >/dev/null || fail "Stage 030 must be reconciled from this repository first"
    delegated=$("$STAGE_APPS" delegated 010 DataScienceCluster default-dsc --group datasciencecluster.opendatahub.io)
    for field in aigateway ogx; do
        grep -qx "/spec/components/$field" <<<"$delegated" || fail "Stage 010 must delegate /spec/components/$field"
    done
    delegated=$("$STAGE_APPS" delegated 010 OdhDashboardConfig odh-dashboard-config redhat-ods-applications --group opendatahub.io)
    for field in genAiStudio genAiTracing modelAsService vLLMDeploymentOnMaaS externalModels llmdTemplates guardrails \
        agentConfigManagement promptManagement; do
        grep -qx "/spec/dashboardConfig/$field" <<<"$delegated" || fail "Stage 010 must delegate dashboardConfig.$field"
    done
    [[ -z "$(read_optional applications.argoproj.io 040-governed-models-as-a-service -n openshift-gitops)" ]] ||
        fail "Retired single Stage 040 Application still exists; finish the component move (docs/OPERATIONS.md)"

    # Existing Applications and rendered objects; namespaces must also be tracked (preflight accepts untracked ones).
    # The OLSConfig singleton is the reviewed adoption of the provisioner's object (checked below), so the generic
    # guard skips that kind.
    "$STAGE_APPS" preflight 040 --repo-url "$GIT_REPO_URL" --skip-kind OLSConfig >&2
    # Reviewed adoption: OLSConfig cluster is either already 040-openshift-lightspeed's or the provisioner's original
    # (untracked, unowned, not being deleted); anything else stops the deployment.
    ols=$(read_optional olsconfigs.ols.openshift.io cluster)
    [[ -z "$ols" ]] || jq -e --arg t "040-openshift-lightspeed:ols.openshift.io/OLSConfig:openshift-gitops/cluster" '
        (.metadata.ownerReferences // [] | length) == 0 and .metadata.deletionTimestamp == null
        and ((.metadata.annotations["argocd.argoproj.io/tracking-id"] // "") | . == $t or . == "")' <<<"$ols" >/dev/null ||
        fail "existing OLSConfig cluster has another owner; adopt it only after review"
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
        components=$("$STAGE_APPS" names 040 --all | jq -R . | jq -s -c .)
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
}

# ── One external provider credential Secret in external-models ────────────────────────────────────────────────
# Reuses an existing owned Secret, copies the prior one from models-as-a-service, or creates it from OPENAI_API_KEY,
# ANTHROPIC_API_KEY or NVIDIA_API_KEY.
provider_secret() {

    NS=external-models
    APP=040-external-models
    NAME=$1
    ROTATE=$(tr '[:upper:]' '[:lower:]' <<<"${RHOAI_STAGE040_ROTATE_PROVIDER_SECRET:-false}")
    fail() { echo "ERROR: $*" >&2; exit 1; }
    case "$NAME" in
        openai-provider-api-key) KEY_VAR=OPENAI_API_KEY ;;
        anthropic-provider-api-key) KEY_VAR=ANTHROPIC_API_KEY ;;
        nvidia-provider-api-key) KEY_VAR=NVIDIA_API_KEY ;;
        *) fail "Unreviewed provider credential $NAME" ;;
    esac
    [[ "$ROTATE" == true || "$ROTATE" == false ]] || fail "Rotation flag must be explicitly true or false"
    [[ "$ROTATE" == false || "$NAME" == openai-provider-api-key ]] || fail "Explicit rotation is scoped to the OpenAI provider"
    # The OpenAI key may also come from the older RHOAI_OPENAI_API_KEY name.
    if [[ "$NAME" == openai-provider-api-key && -z "${OPENAI_API_KEY:-}" && -n "${RHOAI_OPENAI_API_KEY:-}" ]]; then
        export OPENAI_API_KEY="$RHOAI_OPENAI_API_KEY"
    fi
    export KEY_VAR
    read_secret() { oc --request-timeout=10s get secret "$NAME" -n "$1" --ignore-not-found -o json; }

    # The provider namespace comes from 040-external-models; wait for it (up to 5 minutes).
    for attempt in $(seq 1 60); do
        tracking=$(oc --request-timeout=10s get namespace "$NS" --ignore-not-found \
            -o jsonpath='{.metadata.annotations.argocd\.argoproj\.io/tracking-id}{"|"}{.metadata.uid}')
        if [[ "$tracking" == *"|"?* ]]; then
            [[ "${tracking%|*}" == "$APP:/Namespace:openshift-gitops/$NS" ]] || fail "Provider namespace ownership differs"
            break
        fi
        (( attempt < 60 )) || fail "Provider namespace did not reconcile"
        sleep 5
    done

    target=$(read_secret "$NS")
    if [[ -n "$target" ]]; then
        components=$("$REPO_ROOT/scripts/stage-apps.sh" names 040 --all | jq -R . | jq -s -c .)
        printf '%s' "$target" | jq -e --argjson apps "$components" '.metadata as $m
            | ($m.annotations["argocd.argoproj.io/tracking-id"] // "" | . == "" or (split(":")[0] as $a | $apps | index($a)))
            and ($m.ownerReferences // [] | length) == 0 and $m.deletionTimestamp == null
            and (.data["api-key"] // "" | length) > 0 and (.data["api-key"] | @base64d | length) > 0
            and $m.labels["inference.llm-d.ai/ipp-managed"] == "true"' >/dev/null ||
            fail "Existing provider credential is foreign, incomplete or lacks its native label"
        if [[ "$ROTATE" == true ]]; then
            [[ -n "${OPENAI_API_KEY:-}" ]] || fail "Fresh authorized OpenAI credential is unavailable"
            # JSON patch guarded by uid and resourceVersion; the new value comes from jq's environment.
            printf '%s' "$target" | jq -c '[{op: "test", path: "/metadata/uid", value: .metadata.uid},
                {op: "test", path: "/metadata/resourceVersion", value: .metadata.resourceVersion},
                {op: "replace", path: "/data/api-key", value: ($ENV.OPENAI_API_KEY | @base64)}]' |
                oc --request-timeout=10s patch secret "$NAME" -n "$NS" --type=json --patch-file=/dev/stdin >/dev/null ||
                fail "Scoped provider credential rotation failed; response suppressed"
            read_secret "$NS" | jq -e --slurpfile before <(printf '%s' "$target") '$before[0] as $before
                | .metadata.uid == $before.metadata.uid
                and .metadata.labels == $before.metadata.labels and .type == $before.type
                and .data == ($before.data + {"api-key": ($ENV.OPENAI_API_KEY | @base64)})' >/dev/null ||
                fail "Provider identity, labels or readback differ after rotation"
            echo "PASS Authorized OpenAI credential matches the retained native Secret; identity and labels preserved."
        else
            echo "PASS Existing native provider credential reused without rotation."
        fi
        return 0
    fi

    [[ "$ROTATE" == false ]] || fail "Explicit rotation requires the existing owned provider credential"
    # New Secret: the prior credential from models-as-a-service if present, else the key from the environment.
    prior=$(read_secret models-as-a-service)
    if [[ -n "$prior" ]]; then
        printf '%s' "$prior" | jq -e '.metadata.deletionTimestamp == null and (.data["api-key"] // "" | @base64d | length) > 0' >/dev/null ||
            fail "Prior authorized credential is terminating or incomplete"
        source_json="$prior"
    else
        [[ -n "${!KEY_VAR:-}" ]] || fail "Authorized provider credential is unavailable ($KEY_VAR)"
        source_json=$(jq -n '{data: {"api-key": ($ENV[$ENV.KEY_VAR] | @base64)}}')
    fi
    printf '%s' "$source_json" | jq --arg name "$NAME" --arg ns "$NS" '{apiVersion: "v1", kind: "Secret", type: "Opaque",
        metadata: {name: $name, namespace: $ns,
            labels: {"inference.llm-d.ai/ipp-managed": "true", "app.kubernetes.io/part-of": "rhoai3-coding-demo"}},
        data: {"api-key": .data["api-key"]}}' |
        oc --request-timeout=10s create -f - >/dev/null || fail "Native provider credential creation failed; inspect ownership before retry"
    echo "PASS Authorized provider credential supplied through private standard input."
}

# ── MaaS database credentials (never rotated) and the connection URI ─────────────────────────────────────────
# --fresh-database: the preflight saw a clean install, so a StatefulSet created since then may be adopted.
setup_database() {

    FRESH=false
    [[ "${1:-}" == --fresh-database ]] && FRESH=true
    NS=models-as-a-service-db
    APP=040-maas-database
    INFRA=redhat-ai-gateway-infra
    fail() { echo "ERROR: $*" >&2; exit 1; }
    read_secret() { oc --request-timeout=10s get secret "$1" -n "$2" --ignore-not-found -o json; }
    namespace_exists() { [[ -n "$(oc --request-timeout=10s get namespace "$1" --ignore-not-found -o name)" ]]; }
    COMPONENTS=$("$REPO_ROOT/scripts/stage-apps.sh" names 040 --all | jq -R . | jq -s -c .)
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
}

# ── Model registry records: one registered model per checkpoint, one version per immutable revision ──────────
# Each model's labels and properties come from model-registry-metadata.json beside its manifest: Qwen, its prepared
# format alternates and Mistral.
register_model_cards() {

    NS=internal-models
    REGISTRY=demo-registry
    LOCAL_MODELS="$REPO_ROOT/gitops/stages/040-governed-models-as-a-service/040-local-models"
    local revision
    fail() { echo "ERROR: registry publication stopped: $*" >&2; exit 1; }
    yaml_stream_json() { ruby -ryaml -rjson -e 'puts JSON.generate(YAML.load_stream(STDIN.read).compact)'; }

    revision="${RHOAI_STAGE040_EXPECTED_REVISION:-$(git -C "$REPO_ROOT" rev-parse HEAD)}"
    [[ "$revision" =~ ^[0-9a-f]{40}$ ]] || fail "reviewed immutable source differs"
    "$REPO_ROOT/scripts/stage-apps.sh" status 040 --revision "$revision" \
        --repo-url "$GIT_REPO_URL" >/dev/null || fail "Stage 040 must reconcile before model registration"
    host=$(oc --request-timeout=10s get modelregistries.modelregistry.opendatahub.io "$REGISTRY" -n rhoai-model-registries \
        -o jsonpath='{.status.hosts[0]}')
    BASE="https://$host/api/model_registry/v1alpha3"
    TOKEN=$(oc whoami -t)  # memory only: reaches curl through --config on stdin

    # Authenticated, CA-verified registry call; redirects are not followed. Prints the JSON response.
    api() {
        local path=$1 body=${2:-} method=${3:-}
        printf 'header = "Authorization: Bearer %s"\n' "$TOKEN" |
            curl --config - -sf --max-time 20 -H 'Content-Type: application/json' ${method:+-X "$method"} \
                ${body:+--data "$body"} "$BASE$path" || fail "authenticated registry request failed"
    }
    # Every item of a paginated listing (at most 100 pages), as one JSON array.
    items() {
        local path=$1 cursor="" page all='[]'
        for _ in $(seq 1 100); do
            page=$(api "$path${cursor:+?nextPageToken=$(jq -rn --arg c "$cursor" '$c | @uri')}")
            all=$(jq -c --argjson all "$all" '$all + (.items // [])' <<<"$page")
            cursor=$(jq -r '.nextPageToken // ""' <<<"$page")
            [[ -z "$cursor" ]] && { echo "$all"; return; }
        done
        fail "registry pagination exceeded its bound"
    }
    # Ensure model, version and artifact for one pinned source URI and the labels and properties METADATA_FILE
    # declares for that checkpoint (keyed by registered model name); prints "<title> <model id> <version id>".
    register() {
        local uri=$1 meta_file=$2 meta title revision quant model version artifacts current desired
        title=${uri##*/}
        title=${title%%:*}
        revision=${uri##*:}
        [[ ${#revision} == 40 ]] || fail "model source must be immutable"
        case "$(tr '[:lower:]' '[:upper:]' <<<"$title")" in
            *-NVFP4) quant="NVFP4 (FP4 weights, FP8 attention)" ;;
            *-FP8) quant="FP8 block-128" ;;
            *-INT4) quant="INT4 W4A16" ;;
            *) quant="unquantized" ;;
        esac
        meta=$(jq -c -e --arg t "$title" '.[$t]' "$meta_file") || fail "$title registry metadata missing in $meta_file"
        model=$(items /registered_models | jq -c --arg t "$title" '[.[] | select(.name == $t)]')
        [[ $(jq length <<<"$model") -le 1 ]] || fail "ambiguous registered model name"
        if [[ $(jq length <<<"$model") == 0 ]]; then
            local location=${uri#*://}
            model=$(api /registered_models "$(jq -n --arg t "$title" --arg q "$quant" --arg l "${location%%:*}" '{name: $t,
                owner: "rhoai3-coding-demo", description: ("Quantization: \($q). Pinned model artifact used by the project (\($l)). "
                + "Runtime and GPU compatibility are qualified separately; this is not a Red Hat validated-model claim.")}')")
        else
            model=$(jq -c '.[0]' <<<"$model")
        fi
        local model_id
        model_id=$(jq -r '.id' <<<"$model")
        version=$(items "/registered_models/$model_id/versions" | jq -c --arg v "source-$revision" '[.[] | select(.name == $v)]')
        [[ $(jq length <<<"$version") -le 1 ]] || fail "ambiguous registered model version"
        if [[ $(jq length <<<"$version") == 0 ]]; then
            version=$(api /model_versions "$(jq -n --arg v "source-$revision" --arg m "$model_id" --arg q "$quant" --arg r "$revision" \
                '{name: $v, registeredModelId: $m, description: "Quantization: \($q). Immutable source \($r)"}')")
        else
            version=$(jq -c '.[0]' <<<"$version")
        fi
        local version_id
        version_id=$(jq -r '.id' <<<"$version")
        artifacts=$(items "/model_versions/$version_id/artifacts")
        jq -e --arg u "$uri" 'length == 0 or (length == 1 and .[0].uri == $u)' <<<"$artifacts" >/dev/null ||
            fail "existing version artifact differs; no overwrite"
        if [[ $(jq length <<<"$artifacts") == 0 ]]; then
            api "/model_versions/$version_id/artifacts" "$(jq -n --arg u "$uri" '{name: "model-source", uri: $u,
                artifactType: "model-artifact", modelFormatName: "vLLM", modelFormatVersion: "1"}')" >/dev/null
        fi
        # A label is a string custom property with an empty value (the form the dashboard shows and searches). The
        # labels become exactly the declared set; declared properties are set and other properties (evaluation
        # results) stay.
        current=$(api "/registered_models/$model_id" | jq -S -c '.customProperties // {}')
        desired=$(jq -S -c --argjson m "$meta" 'with_entries(select(.value != {metadataType: "MetadataStringValue",
            string_value: ""})) + ($m.labels | map({key: ., value: {metadataType: "MetadataStringValue", string_value: ""}})
            | from_entries) + ($m.properties | with_entries(.value = {metadataType: "MetadataStringValue",
            string_value: .value}))' <<<"$current")
        [[ "$desired" == "$current" ]] || api "/registered_models/$model_id" \
            "$(jq -c '{customProperties: .}' <<<"$desired")" PATCH >/dev/null
        echo "$title $model_id $version_id"
    }

    # Ensure the registry InferenceService record of one deployment, in the form the registry controller writes for
    # InferenceServices: serving environment = namespace, name = "<name>/<uid>". A record's name and registered model
    # are immutable, so after a format switch the old checkpoint's record is set UNDEPLOYED and the new one is named
    # "<name>/<uid>/<model id>". Prints the record id.
    deployment_record() {
        local name=$1 uid=$2 model_id=$3 version_id=$4 state=$5 env records record stale record_name
        env=$(items /serving_environments | jq -r --arg n "$NS" '[.[] | select(.name == $n)] | if length == 1 then .[0].id else "" end')
        [[ -n "$env" ]] || env=$(api /serving_environments "$(jq -n --arg n "$NS" '{name: $n}')" | jq -r '.id')
        records=$(items "/serving_environments/$env/inference_services" | jq -c --arg n "$name/$uid" \
            '[.[] | select(.name == $n or (.name | startswith($n + "/")))]')
        for stale in $(jq -r --arg m "$model_id" '.[] | select(.registeredModelId != $m and .desiredState != "UNDEPLOYED") | .id' <<<"$records"); do
            api "/inference_services/$stale" '{"desiredState": "UNDEPLOYED"}' PATCH >/dev/null
        done
        record=$(jq -c --arg m "$model_id" '[.[] | select(.registeredModelId == $m)]' <<<"$records")
        [[ $(jq length <<<"$record") -le 1 ]] || fail "ambiguous registry deployment record $name"
        if [[ $(jq length <<<"$record") == 0 ]]; then
            record_name="$name/$uid"
            [[ $(jq length <<<"$records") == 0 ]] || record_name="$name/$uid/$model_id"
            api /inference_services "$(jq -n --arg n "$record_name" --arg e "$env" --arg m "$model_id" --arg v "$version_id" \
                --arg s "$state" '{name: $n, servingEnvironmentId: $e, registeredModelId: $m, modelVersionId: $v,
                runtime: "llm-d", desiredState: $s}')" | jq -r '.id'
        else
            record=$(jq -r '.[0].id' <<<"$record")
            api "/inference_services/$record" "$(jq -n --arg v "$version_id" --arg s "$state" \
                '{modelVersionId: $v, runtime: "llm-d", desiredState: $s}')" PATCH >/dev/null
            echo "$record"
        fi
    }

    # Deployed models: register the source Git declares and link the deployment to its record.
    local targets=("qwen3-8-27b|040-local-models|$LOCAL_MODELS" "mistral-small4-119b|040-local-models|$LOCAL_MODELS")
    local target app dir rendered
    active=""
    for target in "${targets[@]}"; do
        IFS='|' read -r name app dir <<<"$target"
        rendered=$(oc kustomize "$dir" | yaml_stream_json)
        uri=$(jq -r --arg n "$name" '.[] | select(.kind == "LLMInferenceService" and .metadata.name == $n) | .spec.model.uri' <<<"$rendered")
        llmi=$(oc --request-timeout=10s get llminferenceservices.serving.kserve.io "$name" -n "$NS" --ignore-not-found -o json)
        [[ -n "$llmi" ]] || fail "$name deployment absent"
        jq -e --arg u "$uri" --arg app "$app:" '.spec.model.uri == $u
            and (.metadata.annotations["argocd.argoproj.io/tracking-id"] // "" | startswith($app))
            and (.metadata.generation | type) == "number" and .status.observedGeneration == .metadata.generation' \
            <<<"$llmi" >/dev/null || fail "$name source, ownership or readiness differs"
        parked=$(jq -r '.spec.replicas == 0' <<<"$llmi")
        [[ "$parked" == true ]] || jq -e 'any(.status.conditions[]?; .type == "Ready" and .status == "True")' <<<"$llmi" >/dev/null ||
            fail "active model $name must be Ready before registry publication"
        registered=$(register "$uri" "$dir/model-registry-metadata.json")  # captured, so a failure stops the script (set -e)
        read -r title model_id version_id <<<"$registered"
        active+=" $name=$uri"
        existing=$(jq -r '.metadata.labels["modelregistry.opendatahub.io/registered-model-id"] // ""' <<<"$llmi")
        if [[ -n "$existing" && "$existing" != "$model_id" ]]; then
            # Relink only for a format switch: the linked record must be another checkpoint, never a same-name duplicate.
            linked=$(api "/registered_models/$existing" | jq -r '.name // "?"')
            [[ "$linked" != "$title" ]] || fail "existing model registry identity differs; no reassignment"
            echo "NOTE Format switch: deployment relinked from $linked to $title"
        fi
        # The registry's own controller records only serving.kserve.io InferenceServices (it labels them
        # inference-service-id); write the same record for this LLMInferenceService so the registry lists the deployment.
        serving_record=$(deployment_record "$name" "$(jq -r '.metadata.uid' <<<"$llmi")" "$model_id" "$version_id" \
            "$([[ "$parked" == true ]] && echo UNDEPLOYED || echo DEPLOYED)")
        jq -c --arg r "$REGISTRY" --arg m "$model_id" --arg v "$version_id" --arg i "$serving_record" '[
            {op: "test", path: "/metadata/resourceVersion", value: .metadata.resourceVersion},
            {op: "add", path: "/metadata/labels", value: ((.metadata.labels // {}) + {"modelregistry.opendatahub.io/name": $r,
                "modelregistry.opendatahub.io/registered-model-id": $m, "modelregistry.opendatahub.io/model-version-id": $v,
                "modelregistry.opendatahub.io/inference-service-id": $i})}]' \
            <<<"$llmi" | oc --request-timeout=10s patch llminferenceservices.serving.kserve.io "$name" -n "$NS" \
            --type=json --patch-file=/dev/stdin >/dev/null || fail "deployment linkage patch failed"
        if [[ "$parked" == true ]]; then
            echo "PASS Registered pinned metadata; parked runtime not qualified: $name -> $title"
        else
            echo "PASS Registered pinned source and native deployment linkage: $name -> $title"
        fi
    done

    # Prepared alternates: each format component registers its artifact (no deployment linkage), so the registry
    # lists every build that can be switched on.
    for component in "$LOCAL_MODELS"/components/*/; do
        component=$(basename "$component")
        alt_work=$(mktemp -d)
        cp -R "$LOCAL_MODELS" "$alt_work/local-models"
        printf '\ncomponents:\n  - components/%s\n' "$component" >>"$alt_work/local-models/kustomization.yaml"
        alternates=$(oc kustomize "$alt_work/local-models" | yaml_stream_json |
            jq -r '.[] | select(.kind == "LLMInferenceService") | "\(.metadata.name)=\(.spec.model.uri)"')
        rm -rf "$alt_work"
        for entry in $alternates; do
            [[ "$active" == *" $entry"* ]] && continue
            registered=$(register "${entry#*=}" "$LOCAL_MODELS/model-registry-metadata.json")
            read -r title _ _ <<<"$registered"
            echo "PASS Registered prepared alternate (component $component, not deployed): $title"
        done
    done
}


# Reconcile the optional showback component at REVISION (also from a default deployment once it is installed, so the
# Stage 040 readiness check compares it with the same source).
deploy_showback() {
    local revision=$1
    "$STAGE_APPS" preflight 040 --repo-url "$GIT_REPO_URL" --app 040-showback-demo
    # Shared namespaces and APIs remain owned by their existing platform components.
    for ns in models-as-a-service redhat-ods-monitoring internal-models; do
        oc --request-timeout=10s get namespace "$ns" -o json | jq -e '.status.phase == "Active"' >/dev/null || {
            log_error "Showback requires the existing active namespace $ns"; exit 1;
        }
    done
    oc --request-timeout=10s get crd maassubscriptions.maas.opendatahub.io maasauthpolicies.maas.opendatahub.io \
        persesdashboards.perses.dev servicemonitors.monitoring.coreos.com -o json |
        jq -e '.items | length == 4 and all(.[]; any(.status.conditions[]?; .type == "Established" and .status == "True"))' \
        >/dev/null || { log_error "Showback requires established MaaS, Perses and ServiceMonitor APIs"; exit 1; }
    showback_metering_profile preflight
    # Team access and dashboards come from source; both local models keep their owner, 040-local-models.
    "$STAGE_APPS" apply 040 --app 040-showback-demo --revision "$revision" --repo-url "$GIT_REPO_URL"
    "$STAGE_APPS" sync 040 --app 040-showback-demo
    "$STAGE_APPS" wait 040 --app 040-showback-demo --revision "$revision" --repo-url "$GIT_REPO_URL" --timeout 900
    showback_metering_profile activate
    RHOAI_STAGE040_SHOWBACK_EXPECTED_REVISION="$revision" "$SCRIPT_DIR/validate.sh" --component 040-showback-demo
}

if [[ "$COMPONENT" == 040-showback-demo ]]; then
    revision=$("$STAGE_APPS" select 040 --ref "$ref" --repo-url "$GIT_REPO_URL")
    deploy_showback "$revision"
    log_success "Showback component reconciled; generate demo load with showback-demo/generate-load.sh to populate the dashboards."
    exit 0
fi

revision=$("$STAGE_APPS" select 040 --ref "$ref" --repo-url "$GIT_REPO_URL" \
)
export RHOAI_STAGE040_EXPECTED_REVISION="$revision"

# Read-only: operator channels, prerequisites and ownership, serving state, node sizing.
check_operator_policy "$REPO_ROOT/gitops/stages/040-governed-models-as-a-service"
state=$(stage_preflight)
if [[ -n "$("$STAGE_APPS" names 040 | xargs oc --request-timeout=10s get applications.argoproj.io -n openshift-gitops --ignore-not-found -o name)" ]]; then
  check_serving_prerequisites 040
else
  "$REPO_ROOT/stages/020-gpu-infrastructure-private-ai/validate.sh" --readiness
fi
require_node_sizing

# The Gateway listener hostnames depend on this cluster's ingress domain; they reach the Gateway component as a
# Kustomize patch on its Application, so Git stays cluster-neutral.
work=$(mktemp -d); trap 'rm -rf "$work"' EXIT
oc --request-timeout=10s get ingresscontroller default -n openshift-ingress-operator -o json | jq -c '
  (.status.domain // "") as $d
  | if ($d | test("^[a-z0-9.-]+$")) | not then error("the default ingress domain is unavailable") else . end
  | {"040-gateway-governance": [{target: {group: "gateway.networking.k8s.io", version: "v1", kind: "Gateway",
      name: "maas-default-gateway", namespace: "openshift-ingress"},
    patch: ("[" + ([["maas", "qwen3-8-maas", "mistral-small4-maas"] | to_entries[]
      | "{\"op\": \"replace\", \"path\": \"/spec/listeners/\(.key)/hostname\", \"value\": \"\(.value).\($d)\"}"] | join(", ")) + "]")}]}' \
  > "$work/gateway-patches.json"
# OpenShift Lightspeed (operator preinstalled by the provisioner): the Qwen provider URL is this cluster's MaaS api
# listener; the provisioner's Azure OpenAI provider keeps its endpoint, read from the live OLSConfig (never committed),
# or the entry is dropped when the environment has none.
oc --request-timeout=10s get crd olsconfigs.ols.openshift.io >/dev/null ||
  { log_error "OpenShift Lightspeed operator (OLSConfig API) is not installed; 040-openshift-lightspeed needs it"; exit 1; }
azure_url=$(oc --request-timeout=10s get olsconfig cluster --ignore-not-found -o json |
  jq -r '[.spec.llm.providers[]? | select(.name == "Azure" and .type == "azure_openai") | .url][0] // ""')
[[ -z "$azure_url" || "$azure_url" =~ ^https://[a-z0-9.-]+/?$ ]] || { log_error "Unexpected Azure OpenAI endpoint in the live OLSConfig"; exit 1; }
oc --request-timeout=10s get ingresscontroller default -n openshift-ingress-operator -o json | jq -c --arg azure "$azure_url" \
  --slurpfile g "$work/gateway-patches.json" '(.status.domain) as $d | $g[0] + {"040-openshift-lightspeed": [{target: {group: "ols.openshift.io",
    version: "v1alpha1", kind: "OLSConfig", name: "cluster"}, patch: ([{op: "replace", path: "/spec/llm/providers/0/url",
    value: "https://maas.\($d)/v1"}] + (if $azure == "" then [{op: "remove", path: "/spec/llm/providers/1"}]
    else [{op: "replace", path: "/spec/llm/providers/1/url", value: $azure}] end) | tojson)}]}' > "$work/patches.json"

# First change: the component Applications at the reviewed commit. Their hooks wait for the credentials below
# (040-maas-database's wait-db-credentials Job), so set those up before waiting.
"$STAGE_APPS" deploy 040 --revision "$revision" --repo-url "$GIT_REPO_URL" --kustomize-patches "$work/patches.json" --no-wait
for secret in openai-provider-api-key anthropic-provider-api-key nvidia-provider-api-key; do
  provider_secret "$secret"
done
# Read-only: Automatic InstallPlans resolve to the reviewed channel and minimum versions.
check_operator_policy "$REPO_ROOT/gitops/stages/040-governed-models-as-a-service" --wait 900
if [[ "$state" == fresh ]]; then setup_database --fresh-database; else setup_database; fi
"$STAGE_APPS" wait 040 --revision "$revision" --repo-url "$GIT_REPO_URL" --timeout 2400
# An installed optional showback component follows the same revision (it never auto-syncs on its own).
if [[ -n "$(oc --request-timeout=10s get applications.argoproj.io 040-showback-demo -n openshift-gitops --ignore-not-found -o name)" ]]; then
  deploy_showback "$revision"
fi

# The enable-maas hook turns on Gen AI tracing; re-run the maas-platform hooks once if it is still off.
if [[ "$(oc --request-timeout=10s get odhdashboardconfig odh-dashboard-config -n redhat-ods-applications -o jsonpath='{.spec.dashboardConfig.genAiTracing}')" != true ]]; then
  "$STAGE_APPS" sync 040 --app 040-maas-platform --resync
  "$STAGE_APPS" wait 040 --app 040-maas-platform --revision "$revision" --repo-url "$GIT_REPO_URL" --timeout 900
fi

# Publish the OpenShift MCP servers to the AI asset catalog (deferred while Stage 060 has not deployed them).
"$SCRIPT_DIR/studio-mcp/publish.sh" --defer-if-absent

deadline=$((SECONDS + 900))
# Exit 2 (warnings only) is ready: a warning reports user state, such as a playground created before its state mount.
until ready_rc=0; RHOAI_STAGE040_SKIP_REGISTRY=true "$SCRIPT_DIR/validate.sh" --readiness || ready_rc=$?; (( ready_rc == 0 || ready_rc == 2 )); do
  (( SECONDS < deadline )) || { log_error "Stage 040 readiness timed out; inspect the operator and component conditions."; exit 1; }
  sleep 10
done
# Register the deployed model and its prepared format alternates in the model registry (idempotent, never overwrites).
register_model_cards

log_success "Stage 040 reconciled at ${revision:0:12}; authenticated inference and Studio acceptance are separate (validate.sh --functional)."
