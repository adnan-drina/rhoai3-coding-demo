#!/usr/bin/env bash
# Stage 040: MaaS operators, database, Gateway and policies, MaaS, models, access and Gen AI Studio, at one reviewed
# published revision. Before the first write: Stages 010 and 030 reconciled and delegating what Stage 040 owns, the
# adoption preflight, provider credentials available, and a retained MaaS database consistent with its credentials.
# Then: the component Applications; provider and database credentials created in the cluster (never in Git); the
# Studio catalog entries for the Stage 060 MCP servers (deferred until Stage 060 deploys them); the model registry
# records of the deployed model and its prepared alternates. Secret values travel only through pipes and jq's
# environment: never Git, arguments or output.
# --replace-studio-mcp applies a reviewed change of an already published Studio catalog entry.
# RHOAI_STAGE040_ROTATE_PROVIDER_SECRET=true replaces the OpenAI provider key in place from OPENAI_API_KEY.
# Usage: stages/040-governed-models-as-a-service/deploy.sh [--revision REF] [--replace-studio-mcp]
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"
ref="${GIT_REPO_BRANCH:-HEAD}" REPLACE_STUDIO_MCP=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --revision) ref="${2:?}"; shift 2 ;;
    --replace-studio-mcp) REPLACE_STUDIO_MCP=true; shift ;;
    *) sed -n 's/^# Usage: //p' "$0" >&2; exit 1 ;;
  esac
done
load_env
check_oc_logged_in
require_env GIT_REPO_URL "reviewed Stage 040 source repository"
assert_required_env
STAGE_APPS="$REPO_ROOT/scripts/stage-apps.sh"

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
    "$STAGE_APPS" preflight 040 --repo-url "$GIT_REPO_URL" >&2
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

# ── One Studio MCP discovery entry for a Stage 060 server, with its private ownership journal ─────────────────
# Usage: publish_studio_mcp [--key OpenShift-MCP|OpenShift-MCP-ReadWrite] [--defer-if-absent] [--replace]
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
    [[ -n "$EXPECTED_040" || "$VALIDATE" == false ]] || EXPECTED_040=$(jq -r '.spec.source.targetRevision' <<<"$app")
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

# ── Model registry records: one registered model per checkpoint, one version per immutable revision ──────────
register_model_cards() {

    NS=internal-models
    REGISTRY=demo-registry
    LOCAL_MODELS="$REPO_ROOT/gitops/stages/040-governed-models-as-a-service/040-local-models"
    fail() { echo "ERROR: registry publication stopped: $*" >&2; exit 1; }
    yaml_stream_json() { ruby -ryaml -rjson -e 'puts JSON.generate(YAML.load_stream(STDIN.read).compact)'; }

    revision="${RHOAI_STAGE040_EXPECTED_REVISION:-$(git -C "$REPO_ROOT" rev-parse HEAD)}"
    [[ "$revision" =~ ^[0-9a-f]{40}$ ]] || fail "reviewed immutable source differs"
    "$REPO_ROOT/scripts/stage-apps.sh" status 040 --revision "$revision" --repo-url "$GIT_REPO_URL" >/dev/null ||
        fail "Stage 040 must reconcile before model registration"
    host=$(oc --request-timeout=10s get modelregistries.modelregistry.opendatahub.io "$REGISTRY" -n rhoai-model-registries \
        -o jsonpath='{.status.hosts[0]}')
    BASE="https://$host/api/model_registry/v1alpha3"
    TOKEN=$(oc whoami -t)  # memory only: reaches curl through --config on stdin

    # Authenticated, CA-verified registry call; redirects are not followed. Prints the JSON response.
    api() {
        local path=$1 body=${2:-}
        printf 'header = "Authorization: Bearer %s"\n' "$TOKEN" |
            curl --config - -sf --max-time 20 -H 'Content-Type: application/json' ${body:+--data "$body"} "$BASE$path" ||
            fail "authenticated registry request failed"
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
    # Ensure model, version and artifact for one pinned source URI; prints "<title> <model id> <version id>".
    register() {
        local uri=$1 title revision quant model version artifacts
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
        echo "$title $model_id $version_id"
    }

    # Deployed models: register the source Git declares and link the deployment to its record.
    rendered=$(oc kustomize "$LOCAL_MODELS" | yaml_stream_json)
    active=""
    for name in qwen3-8-27b; do
        uri=$(jq -r --arg n "$name" '.[] | select(.kind == "LLMInferenceService" and .metadata.name == $n) | .spec.model.uri' <<<"$rendered")
        llmi=$(oc --request-timeout=10s get llminferenceservices.serving.kserve.io "$name" -n "$NS" -o json)
        jq -e --arg u "$uri" '.spec.model.uri == $u
            and (.metadata.annotations["argocd.argoproj.io/tracking-id"] // "" | startswith("040-local-models:"))
            and (.metadata.generation | type) == "number" and .status.observedGeneration == .metadata.generation' \
            <<<"$llmi" >/dev/null || fail "$name source, ownership or readiness differs"
        parked=$(jq -r '.spec.replicas == 0' <<<"$llmi")
        [[ "$parked" == true ]] || jq -e 'any(.status.conditions[]?; .type == "Ready" and .status == "True")' <<<"$llmi" >/dev/null ||
            fail "active model $name must be Ready before registry publication"
        registered=$(register "$uri")  # captured, so a failure stops the script (set -e)
        read -r title model_id version_id <<<"$registered"
        active+=" $name=$uri"
        existing=$(jq -r '.metadata.labels["modelregistry.opendatahub.io/registered-model-id"] // ""' <<<"$llmi")
        if [[ -n "$existing" && "$existing" != "$model_id" ]]; then
            # Relink only for a format switch: the linked record must be another checkpoint, never a same-name duplicate.
            linked=$(api "/registered_models/$existing" | jq -r '.name // "?"')
            [[ "$linked" != "$title" ]] || fail "existing model registry identity differs; no reassignment"
            echo "NOTE Format switch: deployment relinked from $linked to $title"
        fi
        jq -c --arg r "$REGISTRY" --arg m "$model_id" --arg v "$version_id" '[
            {op: "test", path: "/metadata/resourceVersion", value: .metadata.resourceVersion},
            {op: "add", path: "/metadata/labels", value: ((.metadata.labels // {}) + {"modelregistry.opendatahub.io/name": $r,
                "modelregistry.opendatahub.io/registered-model-id": $m, "modelregistry.opendatahub.io/model-version-id": $v})}]' \
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
            registered=$(register "${entry#*=}")
            read -r title _ _ <<<"$registered"
            echo "PASS Registered prepared alternate (component $component, not deployed): $title"
        done
    done
}


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
    patch: ("[" + ([["maas", "qwen3-8-maas"] | to_entries[]
      | "{\"op\": \"replace\", \"path\": \"/spec/listeners/\(.key)/hostname\", \"value\": \"\(.value).\($d)\"}"] | join(", ")) + "]")}]}' \
  > "$work/patches.json"

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

# The enable-maas hook turns on Gen AI tracing; re-run the maas-platform hooks once if it is still off.
if [[ "$(oc --request-timeout=10s get odhdashboardconfig odh-dashboard-config -n redhat-ods-applications -o jsonpath='{.spec.dashboardConfig.genAiTracing}')" != true ]]; then
  "$STAGE_APPS" sync 040 --app 040-maas-platform --resync
  "$STAGE_APPS" wait 040 --app 040-maas-platform --revision "$revision" --repo-url "$GIT_REPO_URL" --timeout 900
fi

# Publish the OpenShift MCP servers to the AI asset catalog (deferred while Stage 060 has not deployed them).
publish_studio_mcp --defer-if-absent ${REPLACE_STUDIO_MCP:+--replace}
publish_studio_mcp --key OpenShift-MCP-ReadWrite --defer-if-absent ${REPLACE_STUDIO_MCP:+--replace}

deadline=$((SECONDS + 900))
until "$SCRIPT_DIR/validate.sh" --readiness; do
  (( SECONDS < deadline )) || { log_error "Stage 040 readiness timed out; inspect the operator and component conditions."; exit 1; }
  sleep 10
done
# Register the deployed model and its prepared format alternates in the model registry (idempotent, never overwrites).
register_model_cards

log_success "Stage 040 reconciled at ${revision:0:12}; authenticated inference and Studio acceptance are separate (validate.sh --functional)."
