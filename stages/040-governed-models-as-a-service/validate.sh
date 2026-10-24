#!/usr/bin/env bash
# Stage 040 validation. Default (--readiness), read-only: component Applications, the six operators, GPU LocalQueues,
# AIGateway/OGX/KServe and dashboard flags, the MaaS database, Authorino TLS, the Gateway and its listener isolation,
# the local model and its routes, serving templates, external providers and models, MaaS governance objects, the
# Studio catalog entries, and the gateway's network boundary. No HTTP to models, provider calls or writes; no Secret
# value or command error reaches the output. RHOAI_STAGE040_EXPECTED_REVISION pins the components to one commit.
# --functional additionally runs the bounded, explicit MaaS functional check as an existing persona login: one
# synthetic expiring API key, each reviewed model (fail-closed without and with an invalid key, a completion with usage,
# an incremental SSE stream, a GPT-6 Luna tool call, the local traffic metric), then the key revoked and refused.
# Functional inputs: RHOAI_STAGE040_PERSONA_KUBECONFIG (private ai-admin or ai-developer login, required),
#   RHOAI_STAGE040_MODEL (one model), RHOAI_STAGE040_SINGLE_COMPLETION=true (one completion, needs a model),
#   RHOAI_STAGE040_TEST_EXTERNAL=false (skip external models: result pending), RHOAI_STAGE040_SUBSCRIPTION,
#   RHOAI_STAGE040_CA_BUNDLE (extra CA file), RHOAI_STAGE040_EVIDENCE_PATH (new file under /private/tmp).
# Exit codes: 0 pass, 1 fail, 2 pending (functional only). API contract: shipped MaaS 563117f1/openapi3.yaml.
# --component 040-showback-demo checks the installed optional component: three team subscriptions and policies,
# the Mistral model (replicas are a demo-time choice), three offer dashboards, metering workloads, retained storage
# and the loaded IPP profile. Inference and event delivery are exercised by showback-demo/generate-load.sh.
# Usage: stages/040-governed-models-as-a-service/validate.sh [--readiness|--functional] [--component 040-showback-demo]
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"
MODE=--readiness COMPONENT=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --readiness|--functional) MODE=$1; shift ;;
        --component) COMPONENT=${2:?}; shift 2 ;;
        *) sed -n 's/^# Usage: //p' "$0" >&2; exit 1 ;;
    esac
done
[[ -z "$COMPONENT" || ( "$COMPONENT" == 040-showback-demo && "$MODE" == --readiness ) ]] || {
    sed -n 's/^# Usage: //p' "$0" >&2; exit 1;
}
load_env
check_oc_logged_in

STAGE_APPS="$REPO_ROOT/scripts/stage-apps.sh"
TIMEOUT="${RHOAI_OC_REQUEST_TIMEOUT:-10s}"
read_json() { oc --request-timeout="$TIMEOUT" get "$@" -o json; }

# jq definitions used by the checks.
DEFS='
def current: (.metadata.generation | type) == "number" and .status.observedGeneration == .metadata.generation
    and .metadata.deletionTimestamp == null;
def cond_fresh($t): .metadata.generation as $g | any(.status.conditions[]?; .type == $t and .status == "True" and .observedGeneration == $g);
def ready_cond($t): .metadata.generation as $root_generation | any(.status.conditions[]?; .type == $t and .status == "True"
    and (if has("observedGeneration") then .observedGeneration == $root_generation else true end));
def controlled_by($uid): any(.metadata.ownerReferences[]?; .uid == $uid and .controller == true);
def workload: current and (.spec.replicas // 1) as $n | .status as $s
    | $n > 0 and ($s.readyReplicas // 0) >= $n and ($s.updatedReplicas // 0) >= $n
    and (if .kind == "Deployment" then $s.replicas == $n and $s.updatedReplicas == $n and ($s.availableReplicas // 0) == $n else true end);
# Every authored field of $e is present and equal in the input (Kubernetes may add defaulted fields).
def covers($e): . as $a | if ($e | type) == "object" then ($a | type) == "object"
        and all($e | to_entries[]; . as $p | ($a | has($p.key)) and ($a[$p.key] | covers($p.value)))
    elif ($e | type) == "array" then ($a | type) == "array" and ($a | length) == ($e | length)
        and all(range(0; $e | length); . as $i | $a[$i] | covers($e[$i]))
    else $a == $e end;
def selects($labels): (.matchLabels // {} | to_entries | all(.value == $labels[.key]))
    and all(.matchExpressions[]?; . as $x | ($labels | has($x.key)) as $has
        | if $x.operator == "In" then $has and ($x.values | index($labels[$x.key])) != null
          elif $x.operator == "NotIn" then ($has | not) or ($x.values | index($labels[$x.key])) == null
          elif $x.operator == "Exists" then $has
          elif $x.operator == "DoesNotExist" then $has | not
          else false end);
'
jqd() { local n=$# filter="${!#}"; jq "${@:1:n-1}" "$DEFS $filter"; }
yes_no() { jqd "$@" >/dev/null && echo yes || echo no; }

SHOWBACK_DESIRED=$(oc kustomize "$REPO_ROOT/gitops/stages/040-governed-models-as-a-service/040-showback-demo" |
    ruby -ryaml -rjson -e 'puts JSON.generate(YAML.load_stream(STDIN.read).compact)')
# Source reconciliation is separate from model inference, MaaS access enforcement and actual report scraping.
showback_source_state() {
    local d kind ns name group live args tracking profile expected current
    "$STAGE_APPS" status 040 --app 040-showback-demo \
        ${RHOAI_STAGE040_SHOWBACK_EXPECTED_REVISION:+--revision "$RHOAI_STAGE040_SHOWBACK_EXPECTED_REVISION"} \
        >/dev/null 2>&1 || { echo "showback Application not Synced and Healthy at its reviewed revision"; return; }
    jq -e '[.[] | select(.metadata.labels["app.kubernetes.io/component"] == "external-metering")] as $metering |
        ([.[] | select(.kind == "MaaSSubscription") | .metadata.name] | sort)
            == ["team-engineering","team-marketing","team-support"]
        and ([.[] | select(.kind == "MaaSAuthPolicy") | .metadata.name] | sort)
            == ["team-engineering","team-marketing","team-support"]
        and ([.[] | select(.kind == "LLMInferenceService") | .metadata.name] == ["mistral-small4-119b"])
        and ([.[] | select(.kind == "PersesDashboard")] | length) == 3
        and all(.[]; .kind != "Job" and .kind != "CronJob" and .kind != "HorizontalPodAutoscaler"
            and .kind != "Config" and .kind != "LokiStack")
        and ([.[] | select(.kind == "Deployment") | .metadata.name] | sort)
            == ["showback-external-metering","showback-external-metering-db"]
        and all($metering[]; (.metadata.name | startswith("showback-external-metering"))
            and (.kind | IN("ConfigMap","Secret","Deployment","Service","PersistentVolumeClaim",
                "ServiceMonitor","NetworkPolicy","ImageStream")))
        and any($metering[]; .kind == "ConfigMap" and .metadata.name == "showback-external-metering-profile"
            and (.data.enabled | IN("true","false")))
        and any($metering[]; .kind == "PersistentVolumeClaim"
            and .metadata.annotations["argocd.argoproj.io/sync-options"] == "Prune=false,Delete=false")' \
        <<<"$SHOWBACK_DESIRED" >/dev/null || { echo "showback source has an invalid bundle"; return; }
    while IFS= read -r d; do
        kind=$(jq -r '.kind' <<<"$d"); ns=$(jq -r '.metadata.namespace // ""' <<<"$d")
        name=$(jq -r '.metadata.name' <<<"$d")
        group=$(jq -r '.apiVersion | if contains("/") then split("/")[0] else "" end' <<<"$d")
        args=("$(jq -r '.kind + (if (.apiVersion | contains("/")) then "." + (.apiVersion | split("/") | .[1] + "." + .[0]) else "" end)' <<<"$d")" "$name")
        [[ -z "$ns" ]] || args+=(-n "$ns")
        live=$(read_json "${args[@]}") || { echo "$kind $name unavailable"; return; }
        tracking="040-showback-demo:$group/$kind:${ns:-openshift-gitops}/$name"
        jqd -e --argjson d "$d" --arg t "$tracking" '.metadata.deletionTimestamp == null
            and (.metadata.ownerReferences // [] | length) == 0
            and .metadata.annotations["argocd.argoproj.io/tracking-id"] == $t
            and covers($d | if .kind == "ConfigMap" and .data == {} then del(.data)
                elif .kind == "LLMInferenceService" then del(.spec.replicas)
                elif .kind == "Secret" and .stringData != null
                    then .data = ((.data // {}) + (.stringData | map_values(@base64))) | del(.stringData)
                else . end)
            and (if .kind == "Deployment" then
                if $d.spec.replicas == 0 then .spec.replicas == 0 and (.status.replicas // 0) == 0
                    and (.status.readyReplicas // 0) == 0 and (.status.availableReplicas // 0) == 0
                else workload and ready_cond("Available") end else true end)
            and (if .kind == "PersistentVolumeClaim" then .status.phase == "Bound" else true end)' <<<"$live" >/dev/null || {
                    echo "$kind $name source, ownership or readiness differs"; return;
                }
    done < <(jq -c '.[]' <<<"$SHOWBACK_DESIRED")
    profile=$(jq -c '.[] | select(.kind == "ConfigMap" and .metadata.name == "showback-external-metering-profile")' \
        <<<"$SHOWBACK_DESIRED")
    if [[ -n "$profile" ]]; then
        expected=$(jq -c '.data | if .enabled == "true" then .["profile.json"] else .["baseline.json"] end | fromjson' \
            <<<"$profile")
        live=$(read_json configmap payload-processing-plugins -n openshift-ingress) || {
            echo "MaaS processing profile unavailable"; return;
        }
        jq -e '.metadata.annotations["opendatahub.io/managed"] == "false"
            and any(.metadata.ownerReferences[]?; .kind == "Config" and .name == "default")' <<<"$live" >/dev/null || {
            echo "MaaS processing profile ownership or delegation differs"; return;
        }
        current=$(jq -r '.data["custom-ipp-config.yaml"]' <<<"$live" |
            ruby -ryaml -rjson -e 'puts JSON.generate(YAML.load(STDIN.read))')
        jq -e --argjson expected "$expected" '. == $expected' <<<"$current" >/dev/null || {
            echo "MaaS processing profile differs from source activation state"; return;
        }
        read_json deployment payload-processing -n openshift-ingress | jqd -e 'workload and ready_cond("Available")' \
            >/dev/null || { echo "MaaS processing workload is not Ready"; return; }
    fi
    echo yes
}
if [[ "$COMPONENT" == 040-showback-demo ]]; then
    check "Optional showback Application owns the reviewed team, dashboard, model and metering bundle" showback_source_state yes
    echo "Scope: source reconciliation, workload/storage readiness and configured metering profile; demo load exercises inference and metering."
    validation_summary
    exit $?
fi

check_operator_policy "$REPO_ROOT/gitops/stages/040-governed-models-as-a-service" --verify
DESIRED=$(oc kustomize "$REPO_ROOT/gitops/stages/040-governed-models-as-a-service" |
    ruby -ryaml -rjson -e 'puts JSON.generate(YAML.load_stream(STDIN.read).compact)' |
    jq -c --argjson optional "$SHOWBACK_DESIRED" 'def id: [.apiVersion, .kind, .metadata.namespace, .metadata.name];
        ($optional | map(id)) as $excluded | map(select(id as $i | any($excluded[]; . == $i) | not))')
desired_of() { jq -c --arg k "$1" '[.[] | select(.kind == $k)]' <<<"$DESIRED"; }

components_reconciled() {
    "$STAGE_APPS" status 040 ${RHOAI_STAGE040_EXPECTED_REVISION:+--revision "$RHOAI_STAGE040_EXPECTED_REVISION"} \
        >/dev/null 2>&1 || { echo "components not reconciled"; return; }
    [[ -z "$(oc --request-timeout="$TIMEOUT" get applications.argoproj.io 040-governed-models-as-a-service \
        -n openshift-gitops --ignore-not-found -o name)" ]] && echo yes || echo "retired single Application still exists"
}
# The six Subscriptions match Git; each installed CSV succeeded and its Deployments are CSV-owned and available.
operators() {
    local subs sub live csv name ns dep
    subs=$(desired_of Subscription)
    [[ $(jq length <<<"$subs") == 6 ]] || { echo "operator selection incomplete"; return; }
    for sub in $(jq -r '.[] | "\(.metadata.namespace)/\(.metadata.name)"' <<<"$subs"); do
        ns=${sub%%/*}; name=${sub#*/}
        live=$(read_json subscription "$name" -n "$ns")
        jq -n -e --argjson d "$(jq -c --arg n "$name" '.[] | select(.metadata.name == $n)' <<<"$subs")" --argjson s "$live" \
            '$d.spec.installPlanApproval == "Automatic"
            and all("name", "channel", "source", "sourceNamespace", "startingCSV", "installPlanApproval"; $s.spec[.] == $d.spec[.])
            and ($s.status.installedCSV // "") != "" and $s.status.installedCSV == $s.status.currentCSV' >/dev/null ||
            { echo "$name differs or is pending"; return; }
        csv=$(read_json csv "$(jq -r '.status.installedCSV' <<<"$live")" -n "$ns")
        jq -e '.status.phase == "Succeeded"' <<<"$csv" >/dev/null || { echo "$name CSV not Succeeded"; return; }
        for dep in $(jq -r '.spec.install.spec.deployments[]?.name' <<<"$csv"); do
            # OLM references its CSV with controller: false; the workload itself must be current and available.
            read_json deployment "$dep" -n "$ns" | jqd -e --argjson csv "$csv" 'any(.metadata.ownerReferences[]?;
                .uid == $csv.metadata.uid and .name == $csv.metadata.name and .kind == "ClusterServiceVersion"
                and (.apiVersion | startswith("operators.coreos.com/"))) and workload' >/dev/null ||
                { echo "$dep not CSV-owned or not available"; return; }
        done
    done
    echo yes
}
local_queues() {
    for q in lq-gpu-reserved-demo lq-gpu-rtxpro6000; do
        read_json localqueue "$q" -n internal-models | jqd -e 'ready_cond("Active")' >/dev/null || { echo "$q"; return; }
    done
    echo yes
}
components_and_flags() {
    local dsc key
    dsc=$(read_json datasciencecluster default-dsc)
    jqd -e 'current and ready_cond("Ready") and .spec.components as $c
        | all("aigateway", "ogx", "kserve"; $c[.].managementState == "Managed")
        and $c.aigateway.modelsAsAService.managementState == "Managed"' <<<"$dsc" >/dev/null ||
        { echo "DSC not current/Ready or a component not Managed"; return; }
    for key in aigateway ogx kserve; do
        read_json "${key}s.components.platform.opendatahub.io" "default-$key" |
            jqd -e 'current and ready_cond("Ready") and .status.phase == "Ready"' >/dev/null || { echo "$key not Ready"; return; }
    done
    read_json odhdashboardconfig odh-dashboard-config -n redhat-ods-applications | jq -e '.spec.dashboardConfig as $f
        | all("genAiStudio", "genAiTracing", "modelAsService", "vLLMDeploymentOnMaaS", "externalModels", "llmdTemplates",
            "guardrails", "agentConfigManagement", "promptManagement"; $f[.] == true)' >/dev/null && echo yes || echo "dashboard flags"
}
# Secret keys are present, decodable and not placeholders; values are inspected only inside jq.
secret_keys() {
    local name=$1 ns=$2; shift 2
    read_json secret "$name" -n "$ns" | jq -e --args '(.data // {}) as $d | all($ARGS.positional[]; ($d[.] // "") as $v
            | ($v | length) > 0 and ($v | @base64d | ascii_downcase | (contains("placeholder") or contains("replace-me")) | not))' \
        "$@" >/dev/null
}
database() {
    read_json statefulset maas-postgres -n models-as-a-service-db | jqd -e 'workload' >/dev/null || { echo "StatefulSet not available"; return; }
    read_json pvc data-maas-postgres-0 -n models-as-a-service-db | jq -e '.status.phase == "Bound"
        and .metadata.deletionTimestamp == null and .spec.storageClassName == "gp3-csi"' >/dev/null || { echo "PVC"; return; }
    secret_keys maas-postgres-credentials models-as-a-service-db POSTGRESQL_USER POSTGRESQL_PASSWORD POSTGRESQL_DATABASE &&
        secret_keys maas-db-config redhat-ai-gateway-infra DB_CONNECTION_URL && echo yes || echo "credential keys"
}
authorino() {
    local cr uid
    cr=$(read_json authorino authorino -n kuadrant-system)
    # The selected Authorino CRD reports no status.observedGeneration.
    jqd -e 'ready_cond("Ready") and (.spec.listener.tls | covers({enabled: true, certSecretRef: {name: "authorino-server-cert"}}))
        and any(.spec.volumes.items[]?; .mountPath == "/etc/pki/tls/certs" and (.configMaps | index("authorino-service-ca"))
            and (.items | index({key: "service-ca.crt", path: "openshift-service-ca.crt"})))' <<<"$cr" >/dev/null ||
        { echo "Authorino TLS or CA mount"; return; }
    read_json configmap authorino-service-ca -n kuadrant-system | jq -e '.metadata.annotations["service.beta.openshift.io/inject-cabundle"] == "true"
        and (.data["service-ca.crt"] // "" | contains("BEGIN CERTIFICATE"))' >/dev/null || { echo "CA bundle"; return; }
    secret_keys authorino-server-cert kuadrant-system tls.crt tls.key || { echo "server certificate"; return; }
    uid=$(jq -r '.metadata.uid' <<<"$cr")
    read_json deployments -n kuadrant-system | jqd -e --arg uid "$uid" '[.items[] | select(controlled_by($uid))]
        | length > 0 and all(.[]; workload and (.spec.template.spec as $p
            | [$p.volumes[]? | select(tojson | contains("authorino-service-ca")) | .name] as $vols
            | any($p.containers[].volumeMounts[]?; (.name as $n | $vols | index($n)) and .mountPath == "/etc/pki/tls/certs")))' \
        >/dev/null && echo yes || echo "owned workload or CA projection"
}

GATEWAY=$(read_json gateway maas-default-gateway -n openshift-ingress)
CONTROLLER=$(read_json gatewayclass "$(jq -r '.spec.gatewayClassName' <<<"$GATEWAY")" | jq -r '.spec.controllerName // ""')
NAMESPACES=$(for n in models-as-a-service internal-models external-models redhat-ai-gateway-infra; do read_json namespace "$n"; done | jq -s -c 'INDEX(.metadata.name)')
# Route attached to maas-default-gateway's listener $section by the native controller, Accepted and ResolvedRefs now.
ROUTE_READY='def route_ready($section; $controller): .metadata.generation as $g | .metadata.namespace as $rns
    | $controller != "" and ([.status.parents[]? | select(.controllerName == $controller
        and (.parentRef.group // "gateway.networking.k8s.io") == "gateway.networking.k8s.io"
        and (.parentRef.kind // "Gateway") == "Gateway" and .parentRef.name == "maas-default-gateway"
        and (.parentRef.namespace // $rns) == "openshift-ingress"
        and (.parentRef.sectionName == null or .parentRef.sectionName == $section))] as $m
      | ($m | length) > 0 and all($m[]; .conditions as $c
          | all("Accepted", "ResolvedRefs"; . as $t | any($c[]; .type == $t and .status == "True" and .observedGeneration == $g))));'
gateway() {
    local expected
    expected=$(desired_of Gateway | jq -c '.[0]')
    jqd -e --argjson e "$expected" --argjson ns "$NAMESPACES" '
        cond_fresh("Accepted") and cond_fresh("Programmed") and .metadata.generation as $g
        | (.spec.listeners | map({key: .name, value: .}) | from_entries) as $l
        | ($l | keys) == ["api", "qwen3-8"]
        and ([$l[].hostname] | unique | length == 2 and all(.[]; . != null and (contains("*") | not) and (contains("placeholder") | not)))
        and ((.status.listeners // []) | map({key: .name, value: .}) | from_entries) as $st
        | all($l | to_entries[]; .key as $name | .value as $li
            | ($e.spec.listeners[] | select(.name == $name) | .allowedRoutes) == $li.allowedRoutes
            and $li.port == 443 and $li.protocol == "HTTPS" and $li.tls.mode == "Terminate"
            and all("Accepted", "ResolvedRefs"; . as $t | any($st[$name].conditions[]?; .type == $t and .status == "True" and .observedGeneration == $g))
            and (($st[$name].attachedRoutes // 0) | if $name == "api" then . >= 1 else . == 1 end)
            and all($ns | to_entries[]; .key as $n | .value.metadata.labels as $labels
                | ($li.allowedRoutes.namespaces.from == "Selector" and ($li.allowedRoutes.namespaces.selector // {} | selects($labels // {})))
                  == (if $name == "api" then ($n == "external-models" or $n == "redhat-ai-gateway-infra" or $n == "internal-models") else $n == "internal-models" end)))' \
        <<<"$GATEWAY" >/dev/null && echo yes || echo no
}
namespace_access() {
    local n
    for n in models-as-a-service internal-models external-models redhat-ai-gateway-infra redhat-ods-applications; do
        [[ $(oc --request-timeout="$TIMEOUT" get namespace "$n" -o jsonpath='{.metadata.labels.maas-gateway-access}') == true ]] ||
            { echo "$n lacks maas-gateway-access"; return; }
    done
    for n in internal-models external-models; do
        read_json rolebinding "rhods-admins-$n-admin" -n "$n" | jq -e '.roleRef == {apiGroup: "rbac.authorization.k8s.io", kind: "ClusterRole", name: "admin"}
            and .subjects == [{apiGroup: "rbac.authorization.k8s.io", kind: "Group", name: "rhods-admins"}]' >/dev/null ||
            { echo "$n administrator binding"; return; }
    done
    echo yes
}
api_routes() {
    read_json httproutes.gateway.networking.k8s.io -n redhat-ai-gateway-infra >"$WORK/api-routes.json"
    read_json httproutes.gateway.networking.k8s.io -n external-models >"$WORK/ext-routes.json"
    jq -s -e --arg c "$CONTROLLER" "$ROUTE_READY"' [.[].items[] | select(any(.spec.parentRefs[]?; .name == "maas-default-gateway"))]
        | all(.[]; all(.spec.parentRefs[] | select(.name == "maas-default-gateway"); .sectionName == null or .sectionName == "api")
              and route_ready("api"; $c))' "$WORK/api-routes.json" "$WORK/ext-routes.json" >/dev/null || { echo "non-model route"; return; }
    jq -e 'any(.items[]; any(.spec.parentRefs[]?; .name == "maas-default-gateway"))' "$WORK/api-routes.json" >/dev/null &&
        echo yes || echo "MaaS API route absent"
}
# The single local model: spec as reviewed (replicas delegated when ignored), Ready unless parked, owned workloads
# current (parked ones at zero), one owned route on exactly its listeners with the canonical model header.
local_model() {
    local models d name app delegated obj replicas parked workloads ready routes route sections
    # Models owned by the optional showback component (its dedicated model) are checked by showback_source_state.
    models=$(desired_of LLMInferenceService | jq -c --argjson sb "$SHOWBACK_DESIRED" \
        '([$sb[] | select(.kind == "LLMInferenceService") | .metadata.name]) as $own | map(select(.metadata.name as $n | $own | index($n) | not))')
    [[ $(jq length <<<"$models") == 1 ]] || { echo "local model scope differs"; return; }
    d=$(jq -c '.[0]' <<<"$models")
    name=$(jq -r '.metadata.name' <<<"$d")
    app=$(read_json application 040-local-models -n openshift-gitops)
    delegated=$(jq -r --arg n "$name" '(.spec.syncPolicy.syncOptions // [] | index("RespectIgnoreDifferences=true") != null)
        and any(.spec.ignoreDifferences[]?; .group == "serving.kserve.io" and .kind == "LLMInferenceService" and .name == $n
            and .namespace == "internal-models" and (.jsonPointers | index("/spec/replicas")))' <<<"$app")
    obj=$(read_json llminferenceservices.serving.kserve.io "$name" -n internal-models)
    jqd -e --argjson d "$d" --argjson del "$delegated" 'current and (.spec.replicas // 1 | type == "number" and . >= 0)
        and (.spec | covers(if $del then $d.spec | del(.replicas) else $d.spec end))
        and .spec.router.gateway.refs == $d.spec.router.gateway.refs' <<<"$obj" >/dev/null || { echo "model spec or listeners differ"; return; }
    replicas=$(jq '.spec.replicas // 1' <<<"$obj")
    parked=false; [[ "$replicas" == 0 && "$delegated" == true ]] && parked=true
    [[ "$parked" == true ]] || jqd -e 'ready_cond("Ready")' <<<"$obj" >/dev/null || { echo "model not Ready"; return; }
    # Workloads owned (transitively) by the model.
    # Workloads the model controls, directly or through a controlled workload (e.g. a LeaderWorkerSet).
    workloads=$(for k in deployments statefulsets leaderworkersets.leaderworkerset.x-k8s.io; do read_json "$k" -n internal-models; done |
        jq -s -c --arg uid "$(jq -r '.metadata.uid' <<<"$obj")" '[.[].items[]] as $all
        | def grow($owned): ([$all[] | select(any(.metadata.ownerReferences[]?; .controller == true and (.uid as $o | $owned | index($o))))
            | .metadata.uid] + $owned | unique) as $next | if ($next | length) == ($owned | length) then $owned else grow($next) end;
        grow([$uid]) as $owned
        | [$all[] | select((.metadata.uid as $x | $owned | index($x)) and (.kind == "Deployment" or .kind == "StatefulSet"))]')
    jqd -e --argjson parked "$parked" 'length > 0 and all(.[]; if $parked and (.spec.replicas // 1) == 0
        then current and (.status.replicas // 0) == 0 and (.status.readyReplicas // 0) == 0 and (.status.updatedReplicas // 0) == 0
             and (.status.availableReplicas // 0) == 0
        else workload end)' <<<"$workloads" >/dev/null || { echo "model workloads not current"; return; }
    routes=$(read_json httproutes.gateway.networking.k8s.io -n internal-models)
    route=$(jqd -c --arg uid "$(jq -r '.metadata.uid' <<<"$obj")" '[.items[] | select(controlled_by($uid))]' <<<"$routes")
    [[ $(jq length <<<"$route") == 1 ]] || { echo "model route ownership not unique"; return; }
    sections=$(jq -c '[.spec.router.gateway.refs[].sectionName] | unique' <<<"$d")
    jq -e --argjson s "$sections" --arg c "$CONTROLLER" --arg canonical "publishers/internal-models/models/$name" "$ROUTE_READY"' .[0] as $r
        | ($r.spec.parentRefs | length) == ($s | length) and ([$r.spec.parentRefs[].sectionName] | unique) == $s
        and all($r.spec.parentRefs[]; .name == "maas-default-gateway" and .namespace == "openshift-ingress"
            and (.group // "gateway.networking.k8s.io") == "gateway.networking.k8s.io" and (.kind // "Gateway") == "Gateway")
        and all($s[]; . as $sec | $r | route_ready($sec; $c))
        and (if ($s | index("api")) then any($r.spec.rules[].matches[]?; .path.value == "/v1/chat/completions"
            and any(.headers[]?; (.name | ascii_downcase) == "x-gateway-model-name" and (.type // "Exact") == "Exact"
                and .value == $canonical)) else true end)' <<<"$route" >/dev/null || { echo "model route listeners or header"; return; }
    # Every declared local model, including the showback dedicated model, owns exactly one gateway route.
    jq -e --argjson n "$(desired_of LLMInferenceService | jq length)" '[.items[] | select(any(.spec.parentRefs[]?; .name == "maas-default-gateway"))]
        | length == $n' <<<"$routes" >/dev/null || { echo "inference route count differs from the declared local models"; return; }
    if [[ "$parked" == true ]]; then echo yes-parked; else echo yes; fi
}
serving_templates() {
    local d name ns tracking
    while IFS= read -r d; do
        name=$(jq -r '.metadata.name' <<<"$d"); ns=$(jq -r '.metadata.namespace' <<<"$d")
        tracking=$("$STAGE_APPS" owner 040 LLMInferenceServiceConfig "$name" "$ns" --group serving.kserve.io)
        read_json llminferenceserviceconfigs.serving.kserve.io "$name" -n "$ns" | jq -e --argjson d "$d" \
            --arg t "$tracking:serving.kserve.io/LLMInferenceServiceConfig:$ns/$name" '.spec == $d.spec
            and (.metadata.ownerReferences // [] | length) == 0 and .metadata.deletionTimestamp == null
            and .metadata.annotations["argocd.argoproj.io/tracking-id"] == $t
            and (.metadata.labels as $live | all($d.metadata.labels | to_entries[]; $live[.key] == .value))
            and (if $d.metadata.labels["opendatahub.io/config-type"] == "router"
                 then .metadata.annotations["opendatahub.io/supported-topologies"] == "[\"workload-single-node\"]" else true end)' \
            >/dev/null || { echo "$name"; return; }
    done < <(desired_of LLMInferenceServiceConfig | jq -c '.[]')
    # The operator keeps the previous release's well-known templates after a z-stream update (v3-5-1-… beside
    # v3-5-2-…); check the one named for the installed release (rhods-operator.3.5.2 -> v3-5-2-).
    local prefix
    prefix=$(read_json subscription rhods-operator -n redhat-ods-operator | jq -r '.status.installedCSV // ""
        | sub("^rhods-operator\\."; "v") | gsub("\\."; "-") + "-"')
    read_json llminferenceserviceconfigs.serving.kserve.io -n redhat-ods-applications | jq -e --arg p "$prefix" '[.items[]
        | select(.metadata.labels["opendatahub.io/config-type"] == "accelerator"
            and (.metadata.name | startswith($p) and endswith("single-node-template-nvidia-cuda")))]
        | length == 1 and (.[0].metadata.annotations["opendatahub.io/support-status"] != "unsupported")
        and ([.[0].spec.template.containers[]? | select(.name == "main") | .image] | length == 1
            and (.[0] | test("^registry\\.redhat\\.io/.+@sha256:[0-9a-f]{64}$")))' >/dev/null && echo yes || echo "NVIDIA accelerator template"
}
external_models() {
    local api_host d kind ns name group obj sec route
    api_host=$(jq -r '.spec.listeners[] | select(.name == "api") | .hostname' <<<"$GATEWAY")
    while IFS= read -r d; do
        kind=$(jq -r '.kind' <<<"$d"); ns=$(jq -r '.metadata.namespace' <<<"$d"); name=$(jq -r '.metadata.name' <<<"$d")
        group=inference.opendatahub.io; [[ "$kind" == MaaSModelRef ]] && group=maas.opendatahub.io
        obj=$(read_json "$(tr '[:upper:]' '[:lower:]' <<<"$kind")s.$group" "$name" -n "$ns")
        jq -e '.status.phase == "Ready"' <<<"$obj" >/dev/null || { echo "$kind $name not Ready"; return; }
        case "$kind" in
            ExternalProvider|ExternalModel)
                jqd -e --argjson d "$d" 'cond_fresh("Ready") and (.spec | covers($d.spec))' <<<"$obj" >/dev/null ||
                    { echo "$kind $name spec or condition"; return; } ;;
        esac
        case "$kind" in
            ExternalProvider)
                sec=$(jq -r '.spec.auth.secretRef.name' <<<"$obj")
                secret_keys "$sec" "$ns" api-key || { echo "$name credential"; return; }
                [[ $(oc --request-timeout="$TIMEOUT" get secret "$sec" -n "$ns" -o jsonpath='{.metadata.labels.inference\.llm-d\.ai/ipp-managed}') == true ]] ||
                    { echo "$name credential label"; return; } ;;
            ExternalModel)
                route=$(jq -r '.status.httpRouteName // ""' <<<"$obj")
                [[ -n "$route" ]] || { echo "$name route status"; return; }
                read_json httproute "$route" -n "$ns" | jq -e --arg uid "$(jq -r '.metadata.uid' <<<"$obj")" --arg c "$CONTROLLER" \
                    "$ROUTE_READY"' any(.metadata.ownerReferences[]?; .uid == $uid and .controller == true) and route_ready("api"; $c)' \
                    >/dev/null || { echo "$name route"; return; } ;;
            MaaSModelRef)
                jqd -e --argjson d "$d" --arg ep "https://$api_host" --arg ns "$ns" 'cond_fresh("Ready") and cond_fresh("GovernanceAttached")
                    and cond_fresh("RuntimeReady") and .spec.modelRef == $d.spec.modelRef and .spec.tenantRef == $d.spec.tenantRef
                    and (.status.endpoint // "") != ""
                    and (if $ns == "external-models" then .status.endpoint == $ep
                         and (if $d.spec.endpointOverride then .spec.endpointOverride == $ep else (.spec.endpointOverride | not) end)
                         else true end)' <<<"$obj" >/dev/null || { echo "$name model reference"; return; } ;;
        esac
    done < <(jq -c '.[] | select(.kind == "ExternalProvider" or .kind == "ExternalModel" or .kind == "MaaSModelRef")' <<<"$DESIRED")
    echo yes
}
# References alone do not prove attachment: each declared subscription and auth policy must be Active and Ready.
governance() {
    local d resource
    while IFS= read -r d; do
        resource=maassubscriptions; [[ $(jq -r '.kind' <<<"$d") == MaaSAuthPolicy ]] && resource=maasauthpolicies
        read_json "$resource.maas.opendatahub.io" "$(jq -r '.metadata.name' <<<"$d")" -n "$(jq -r '.metadata.namespace' <<<"$d")" |
            jqd -e '.metadata.deletionTimestamp == null and .status.phase == "Active" and ready_cond("Ready")' >/dev/null ||
            { jq -r '"\(.kind) \(.metadata.name)"' <<<"$d"; return; }
    done < <(jq -c '.[] | select(.kind == "MaaSSubscription" or .kind == "MaaSAuthPolicy")' <<<"$DESIRED")
    echo yes
}
# The two Studio discovery entries Stage 040 publishes for the Stage 060 MCP servers: each field holds the endpoint the
# native server reports and has its private ownership journal (deferred while Stage 060 is not deployed).
studio_catalog() {
    local key server url value cm journal
    [[ -n "$(oc --request-timeout=10s get applications.argoproj.io 060-agent-tools -n openshift-gitops --ignore-not-found -o name)" ]] ||
        { echo yes; return; }
    RHOAI_STAGE060_EXPECTED_REVISION=$(oc --request-timeout=10s get applications.argoproj.io 060-agent-tools -n openshift-gitops \
        -o jsonpath='{.spec.source.targetRevision}') "$REPO_ROOT/stages/060-agent-runtime-and-agentops/validate.sh" --component 060-agent-tools \
        >/dev/null 2>&1 || { echo "Stage 060 MCP servers not ready"; return; }
    cm=$(read_json configmap gen-ai-aa-mcp-servers -n redhat-ods-applications)
    for key in OpenShift-MCP OpenShift-MCP-ReadWrite; do
        if [[ "$key" == OpenShift-MCP ]]; then
            url=$(oc --request-timeout=10s get mcpservers.mcp.x-k8s.io openshift-mcp-server -n mcp-servers -o jsonpath='{.status.address.url}')
            [[ "$url" == http://openshift-mcp-server.mcp-servers.svc.cluster.local:8080/mcp ]] || { echo "$key address differs"; return; }
        else
            url="https://$(oc --request-timeout=10s get route openshift-mcp-server-rw -n mcp-servers -o jsonpath='{.spec.host}')/mcp"
        fi
        jq -e --arg k "$key" --arg u "$url" '(.data[$k] // "{}" | fromjson) as $v | $v.url == $u and $v.transport == "streamable-http"' \
            <<<"$cm" >/dev/null || { echo "$key field missing or drifted"; return; }
        value=$(jq -r --arg k "$key" '.data[$k] | fromjson | tojson' <<<"$cm" | jq -c -S .)
        journal="$HOME/.local/state/rhoai3-coding-demo/studio-mcp/$(jq -r '.metadata.uid' <<<"$cm")-$key.json"
        [[ -f "$journal" && ! -L "$journal" ]] && jq -e --arg k "$key" --arg sha "$(printf '%s' "$value" | shasum -a 256 | cut -d' ' -f1)" \
            '.application == "040-genai-studio" and .key == $k and .value_sha256 == $sha' "$journal" >/dev/null ||
            { echo "$key has no matching ownership journal"; return; }
    done
    echo yes
}

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
check "Stage 040 components Synced and Healthy at one immutable revision; retired single Application absent" components_reconciled yes
check "Six selected operators match Git; CSVs Succeeded with available workloads" operators yes
check "GPU LocalQueues Active in internal-models" local_queues yes
check "AIGateway, OGX and KServe Managed and Ready; MaaS enabled; dashboard feature flags on" components_and_flags yes
check "MaaS PostgreSQL available on Bound gp3-csi storage; runtime credential keys present" database yes
check "Authorino TLS, CA bundle and owned workload projecting the service CA (live TLS requests pending)" authorino yes
check "Gateway Accepted/Programmed; listeners api and qwen3-8 isolated, TLS-terminated and current" gateway yes
check "MaaS namespaces admitted to the Gateway; hosting-project administrator bindings" namespace_access yes
check "MaaS API and external routes attached to the api listener only" api_routes yes
check "Local model: reviewed spec, workloads, single owned route on its listeners (parked compute is not inference)" local_model yes
check "Stage-owned serving templates and the pinned NVIDIA accelerator template" serving_templates yes
check "External providers, models and MaaS model references Ready with credentials and API endpoint" external_models yes
# The maas-gateway-boundary AdminNetworkPolicy, probed from every running gateway pod with a TCP connect (no HTTP, no
# model call): each destination the gateway needs is open, each other probed destination blocked.
gateway_boundary() {
    local kapi_node pods pod expect label host port r differs=""
    oc --request-timeout=10s get adminnetworkpolicy maas-gateway-boundary >/dev/null 2>&1 || { echo "AdminNetworkPolicy missing"; return; }
    kapi_node=$(oc --request-timeout=10s get nodes -l node-role.kubernetes.io/control-plane -o jsonpath='{.items[0].status.addresses[?(@.type=="InternalIP")].address}')
    pods=$(oc --request-timeout=10s get pods -n openshift-ingress -l gateway.networking.k8s.io/gateway-name=maas-default-gateway \
        --field-selector=status.phase=Running -o jsonpath='{.items[*].metadata.name}')
    [[ -n "$pods" ]] || { echo "no running gateway pod to probe from"; return; }
    for pod in $pods; do
        while IFS='|' read -r expect label host port; do
            if oc exec -n openshift-ingress "$pod" -c istio-proxy -- timeout 4 bash -c "</dev/tcp/$host/$port" >/dev/null 2>&1; then r=open; else r=blocked; fi
            [[ "$r" == "$expect" ]] || differs+="$label:$port $r; "
        done <<EOT
open|dns (openshift-dns)|dns-default.openshift-dns.svc.cluster.local|53
open|istiod xDS|istiod-openshift-gateway.openshift-ingress.svc.cluster.local|15012
open|authorino|authorino-authorino-authorization.kuadrant-system.svc.cluster.local|50051
open|limitador|limitador-limitador.kuadrant-system.svc.cluster.local|8081
open|kuadrant wasm module|kuadrant-operator-wasm.openshift-operators.svc.cluster.local|8082
open|payload-processing|payload-processing.openshift-ingress.svc.cluster.local|9004
open|payload-pre-processing|payload-pre-processing.openshift-ingress.svc.cluster.local|9004
open|maas-api|maas-api.redhat-ai-gateway-infra.svc.cluster.local|8443
open|public https (api.openai.com)|api.openai.com|443
open|public https (api.anthropic.com)|api.anthropic.com|443
open|public https (integrate.api.nvidia.com)|integrate.api.nvidia.com|443
blocked|kube-apiserver on node|$kapi_node|6443
blocked|kubelet on node|$kapi_node|10250
blocked|limitador http port (only grpc 8081 needed)|limitador-limitador.kuadrant-system.svc.cluster.local|8080
blocked|authorino oidc port (only 50051 needed)|authorino-authorino-authorization.kuadrant-system.svc.cluster.local|5001
blocked|public http (example.com:80)|example.com|80
EOT
    done
    [[ -z "$differs" ]] && echo yes || echo "differs: $differs"
}
check "Declared MaaS subscriptions and auth policies Active and Ready (quota enforcement is functional acceptance)" governance yes
showback_application=$(oc --request-timeout="$TIMEOUT" get applications.argoproj.io 040-showback-demo \
    -n openshift-gitops --ignore-not-found -o name) || {
        log_error "Cannot determine whether the optional showback Application is installed"; exit 1;
    }
if [[ -n "$showback_application" ]]; then
    check "Installed optional showback bundle matches its source" showback_source_state yes
fi
check "Studio catalog entries current, or deferred until Stage 060 deploys the MCP servers" studio_catalog yes
check "MaaS gateway AdminNetworkPolicy boundary: needed destinations open, others blocked" gateway_boundary yes
if [[ "$MODE" == --readiness ]]; then
    echo "Scope: native readiness only; authenticated inference, streaming, traffic and user Studio acceptance: --functional."
    validation_summary
    exit
fi
validation_summary || exit 1

# ── Functional check (explicit, bounded; never run by deployment polling) ──────────────────────────────────────
# Runs in a subshell: its own work directory, EXIT trap (revokes the synthetic key) and exit code.
functional() {

    fail() { echo "[FAIL] $*"; exit 1; }
    pending() { echo "[PENDING] $*"; exit 2; }

    # The developer persona session from Stage 010 personas/login.sh, unless another persona login is named.
    PERSONA="${RHOAI_STAGE040_PERSONA_KUBECONFIG:-${RHOAI_DEVELOPER_KUBECONFIG:-}}"
    PERSONA="${PERSONA/#\~/$HOME}"
    [[ -n "$PERSONA" ]] ||
        pending "Set RHOAI_DEVELOPER_KUBECONFIG (or RHOAI_STAGE040_PERSONA_KUBECONFIG) to a private ai-admin or ai-developer login"
    [[ -f "$PERSONA" && -z "$(find "$PERSONA" -maxdepth 0 \( -perm -001 -o -perm -002 -o -perm -004 -o -perm -010 -o -perm -020 -o -perm -040 \))" ]] ||
        fail "Persona kubeconfig must be a private existing login"
    KUBECONFIG="$PERSONA" bash -c 'source "$1/scripts/lib.sh"; load_env; check_oc_logged_in' guard "$REPO_ROOT" >/dev/null 2>&1 ||
        fail "Persona cluster guard failed"
    WHO=$(KUBECONFIG="$PERSONA" oc --request-timeout=10s whoami)
    [[ "$WHO" == ai-admin || "$WHO" == ai-developer ]] || fail "Persona is not an approved demo user"
    USER_TOKEN=$(KUBECONFIG="$PERSONA" oc --request-timeout=10s whoami -t)  # memory only
    ADMIN_TOKEN=$(oc whoami -t)  # memory only: Thanos metric reads

    GATEWAY=$(oc --request-timeout=10s get gateway maas-default-gateway -n openshift-ingress -o json)
    API_HOST=$(jq -r '.spec.listeners[] | select(.name == "api") | .hostname' <<<"$GATEWAY")
    LOCAL_HOST=$(jq -r '.spec.listeners[] | select(.name == "qwen3-8") | .hostname' <<<"$GATEWAY")
    BASE="https://$API_HOST"
    CA_ARGS=()
    [[ -n "${RHOAI_STAGE040_CA_BUNDLE:-}" ]] && CA_ARGS=(--cacert "$RHOAI_STAGE040_CA_BUNDLE")  # extra public CA only
    EVIDENCE="${RHOAI_STAGE040_EVIDENCE_PATH:-/private/tmp/stage040-functional-$(date -u +%Y%m%dT%H%M%SZ)-$(openssl rand -hex 4).json}"
    case "$(cd "$(dirname "$EVIDENCE")" 2>/dev/null && pwd -P)/" in /private/tmp/*) ;; *) fail "Use a new private evidence path under /private/tmp" ;; esac
    [[ ! -e "$EVIDENCE" && ! -L "$EVIDENCE" ]] || fail "Evidence path already exists"
    WORK=$(mktemp -d)
    umask 077

    # HTTPS request; credentials reach curl only through --config on stdin. Prints the HTTP status; body in $WORK/body.
    # Arguments: METHOD URL [token kind: user|key|invalid|none] [JSON body file]. Redirects are never followed.
    http() {
        local method=$1 url=$2 auth=${3:-none} body=${4:-} header=""
        case "$auth" in
            user) header="Authorization: Bearer $USER_TOKEN" ;;
            key) header="Authorization: Bearer $API_KEY" ;;
            admin) header="Authorization: Bearer $ADMIN_TOKEN" ;;
            invalid) header="Authorization: Bearer stage040-invalid-$(openssl rand -hex 16)" ;;
        esac
        { [[ -n "$header" ]] && printf 'header = "%s"\n' "$header"; true; } |
            curl --config - -s --max-time 90 ${CA_ARGS[@]+"${CA_ARGS[@]}"} -X "$method" -H 'Accept: application/json' \
                ${body:+-H 'Content-Type: application/json' --data-binary "@$body"} -o "$WORK/body" -w '%{http_code}' "$url" ||
            echo 000
    }
    # GET/POST expecting one status; prints the JSON body.
    api() {
        local status
        status=$(http "$@")
        [[ "$status" == "${EXPECT:-200}" ]] || { echo "HTTP $status" >&2; return 1; }
        cat "$WORK/body"
    }
    json_file() { local f; f=$(mktemp "$WORK/req.XXXX"); cat >"$f"; echo "$f"; }

    # Reuse the shared-stage source selected above; optional showback identities stay outside this acceptance scope.
    REFS=$(jq -c --arg sel "${RHOAI_STAGE040_MODEL:-}" '[.[] | select(.kind == "MaaSModelRef")
        | select($sel == "" or .metadata.name == $sel)] | sort_by([.metadata.namespace == "external-models", .metadata.name])' <<<"$DESIRED")
    SINGLE=$(tr '[:upper:]' '[:lower:]' <<<"${RHOAI_STAGE040_SINGLE_COMPLETION:-false}")
    [[ -z "${RHOAI_STAGE040_MODEL:-}" || $(jq length <<<"$REFS") == 1 ]] || fail "Selected model must uniquely match a reviewed model reference"
    [[ "$SINGLE" != true || -n "${RHOAI_STAGE040_MODEL:-}" ]] || fail "Single-completion qualification requires an explicit model"
    [[ $(jq length <<<"$REFS") -ge 1 && $(jq length <<<"$REFS") -le 5 ]] || fail "Functional model count exceeds the reviewed bounded scope"
    SUBSCRIPTION="${RHOAI_STAGE040_SUBSCRIPTION:-personal-$WHO}"
    api GET "$BASE/v1/subscriptions" user | jq -e --arg s "$SUBSCRIPTION" 'type == "array" and any(.[]; .subscription_id_header == $s)' \
        >/dev/null || fail "Persona cannot discover the intended subscription"

    # Sanitized evidence, written once on exit.
    jq -n --arg who "$WHO" --arg model "${RHOAI_STAGE040_MODEL:-}" --argjson single "$([[ "$SINGLE" == true ]] && echo true || echo false)" \
        '{timestamp: (now | todate), persona: $who, selected_model: (if $model == "" then null else $model end), single_completion: $single,
          scope: "bounded authenticated API only; Studio browser and per-request EPP selection remain separate",
          models: [], model_http_failures: [], key_revoked: false,
          not_qualified: (["quota enforcement", "per-request EPP invocation", "Studio visual acceptance"]
            + (if $single then ["streaming", "tool calling", "unselected models"] else [] end))}' >"$WORK/evidence.json"
    evidence() { jq "$@" "$WORK/evidence.json" >"$WORK/evidence.next" && mv "$WORK/evidence.next" "$WORK/evidence.json"; }
    FAILED=false
    PENDING_EXTERNAL=false
    KEY_ID=""
    API_KEY=""
    REVOKE_URL=""
    REVOKE_BODY=""
    finish() {
        local status=$? revoked
        if [[ -n "$KEY_ID" ]]; then
            revoked=$(api DELETE "$BASE/v1/api-keys/$(jq -rn --arg i "$KEY_ID" '$i | @uri')" user 2>/dev/null || echo '{}')
            if jq -e --arg i "$KEY_ID" '.id == $i and .status == "revoked"' <<<"$revoked" >/dev/null; then
                evidence '.key_revoked = true'
                if [[ -n "$REVOKE_URL" ]] && [[ $(http POST "$REVOKE_URL" key "$REVOKE_BODY") =~ ^40[13]$ ]]; then
                    evidence '.revoked_key_inference_denied = true'
                elif [[ -n "$REVOKE_URL" ]]; then
                    echo "[FAIL] Revoked synthetic key inference was not denied"; FAILED=true
                fi
            else
                echo "[FAIL] Synthetic key revocation failed; use the recorded synthetic key id for scoped cleanup"; FAILED=true
            fi
        fi
        [[ $status == 0 ]] || FAILED=true
        evidence --argjson failed "$FAILED" --argjson skipped "$PENDING_EXTERNAL" '.passed = (($failed | not) and ($skipped | not)) | .external_skipped = $skipped'
        set -o noclobber
        cat "$WORK/evidence.json" >"$EVIDENCE"
        rm -rf "$WORK"
        echo "Sanitized functional evidence saved to $EVIDENCE; no tokens, URLs or response text included"
        if [[ "$FAILED" == true ]]; then echo "[FAIL] One or more bounded checks failed"; exit 1; fi
        if [[ "$PENDING_EXTERNAL" == true ]]; then echo "[PENDING] External inference was skipped; full API acceptance pending"; exit 2; fi
        echo "[PASS] Bounded API functional checks and synthetic key revocation. Quota enforcement, Studio visual acceptance and per-request EPP selection remain unqualified."
        exit 0
    }
    trap finish EXIT

    created=$(jq -n --arg s "$SUBSCRIPTION" --arg n "stage040-validation-$(openssl rand -hex 6)" \
        '{name: $n, subscription: $s, expiresIn: "1h", ephemeral: true}' | json_file)
    EXPECT=201 api POST "$BASE/v1/api-keys" user "$created" >"$WORK/created.json" || { echo "[FAIL] Synthetic key creation failed"; exit 1; }
    KEY_ID=$(jq -r '.id // ""' "$WORK/created.json")
    [[ -n "$KEY_ID" ]] || { echo "[FAIL] Synthetic key identifier absent; expiry limits residual lifecycle risk"; exit 1; }
    jq -e --arg s "$SUBSCRIPTION" '(.key // "") != "" and .subscription == $s and .ephemeral == true' "$WORK/created.json" >/dev/null ||
        { echo "[FAIL] Synthetic key contract is incomplete"; exit 1; }
    API_KEY=$(jq -r '.key' "$WORK/created.json")
    rm -f "$WORK/created.json"
    evidence --arg id "$KEY_ID" '.synthetic_key_id = $id'  # identifier only, never the key or its prefix

    # Persona catalog, independent of the synthetic key.
    CATALOG=$(api GET "$BASE/v1/models" user) || { echo "[FAIL] Persona model catalog request failed"; exit 1; }
    jq -e '.data | type == "array"' <<<"$CATALOG" >/dev/null || { echo "[FAIL] Native model catalog response is invalid"; exit 1; }

    # Local Qwen traffic counter from the native Thanos route.
    counter() {
        local host query
        host=$(oc --request-timeout=10s get route thanos-querier -n openshift-monitoring -o jsonpath='{.spec.host}')
        query="sum(vllm:request_success_total{namespace=\"internal-models\",model_name=\"$1\"})"
        EXPECT=200 api GET "https://$host/api/v1/query?query=$(jq -rn --arg q "$query" '$q | @uri')" admin |
            jq -r 'if .status == "success" then ([.data.result[].value[1] | tonumber] | add // 0) else error("query") end'
    }
    # Streams a chat completion; proves incremental delivery from curl's per-chunk receive timestamps (wire arrival).
    stream_check() {
        local url=$1 body=$2 trace="$WORK/trace" out="$WORK/stream"
        printf 'header = "Authorization: Bearer %s"\n' "$API_KEY" |
            curl --config - -sN --max-time 120 ${CA_ARGS[@]+"${CA_ARGS[@]}"} -H 'Content-Type: application/json' \
                --data-binary "@$body" --trace-ascii "$trace" --trace-time -o "$out" -w '%{http_code} %{content_type}' "$url" \
            >"$WORK/stream.status" || return 1
        grep -q '^200 text/event-stream' "$WORK/stream.status" || return 1
        [[ $(wc -c <"$out") -le 2097152 ]] || return 1
        # SSE events: content fragments, a final usage, the [DONE] marker; no error events.
        sed -n 's/^data: *//p' "$out" | grep -v '^\[DONE\]$' | jq -s -e '
            (map(select(.error)) | length) == 0
            and ([.[].usage | select(.)] | last | .total_tokens // 0) > 0' >/dev/null || return 1
        grep -q '^data: *\[DONE\]' "$out" || return 1
        # Receive timestamps (HH:MM:SS.micro) of data chunks; at least two distinct, at least 20 ms apart.
        grep -E '^[0-9:.]+ <= Recv data' "$trace" | awk '{split($1, t, ":"); print t[1] * 3600 + t[2] * 60 + t[3]}' |
            awk 'NR == 1 {first = $1} {last = $1; n++} END {exit !(n >= 2 && last - first >= 0.02)}' || return 1
        sed -n 's/^data: *//p' "$out" | grep -v '^\[DONE\]$' | jq -s -c --arg sha "$(sed -n 's/^data: *//p' "$out" | grep -v '^\[DONE\]$' |
            jq -j '.choices[]?.delta | (.content // .reasoning_content // "")' | shasum -a 256 | cut -d' ' -f1)" '{
            content_chunks: ([.[].choices[]?.delta | select((.content // .reasoning_content // "") != "")] | length),
            total_tokens: ([.[].usage | select(.)] | last | .total_tokens), response_sha256: $sha,
            delivery: "incremental (curl receive timestamps)"}'
    }

    while IFS= read -r ref; do
        name=$(jq -r '.metadata.name' <<<"$ref")
        ns=$(jq -r '.metadata.namespace' <<<"$ref")
        external=false; [[ "$ns" == external-models ]] && external=true
        if [[ "$external" == true && $(tr '[:upper:]' '[:lower:]' <<<"${RHOAI_STAGE040_TEST_EXTERNAL:-true}") != true ]]; then
            PENDING_EXTERNAL=true; continue
        fi
        if [[ "$external" == true ]]; then
            model_id=$(jq -r '.spec.modelRef.name' <<<"$ref")
            host=$API_HOST
        else
            model_id=$(jq -r --arg ns "$ns" --arg n "$(jq -r '.spec.modelRef.name' <<<"$ref")" '[.[] | select(.kind == "LLMInferenceService"
                and .metadata.namespace == $ns and .metadata.name == $n)] | if length == 1 then "publishers/\($ns)/models/\(.[0].spec.model.name)" else "" end' <<<"$DESIRED")
            [[ -n "$model_id" && $(oc --request-timeout=10s get maasmodelrefs.maas.opendatahub.io "$name" -n "$ns" \
                -o jsonpath='{.status.resolvedModelAlias}') == "$model_id" ]] || { echo "[FAIL] Native local model alias differs"; exit 1; }
            host=$LOCAL_HOST
        fi
        endpoint=$(jq -r --arg m "$model_id" '.data[] | select(.id == $m and .ready == true) | .url' <<<"$CATALOG")
        [[ -n "$endpoint" ]] || { echo "[FAIL] Approved model $name is missing or not ready in the persona catalog"; exit 1; }
        # A local model is reachable on both of its listeners; native discovery advertises the shared api listener
        # (RHOAI 3.5.2) or the model's own compatibility listener. Any other host is wrong.
        [[ "$endpoint" == "https://$host"* || ( "$external" == false && "$endpoint" == "https://$API_HOST"* ) ]] ||
            { echo "[FAIL] Native model discovery selects the wrong listener hostname"; exit 1; }
        case "${endpoint%/}" in */v1) url="${endpoint%/}/chat/completions" ;; *) url="${endpoint%/}/v1/chat/completions" ;; esac
        payload=$(jq -n --arg m "$model_id" --arg name "$name" --argjson ext "$external" '{model: $m,
            messages: [{role: "user", content: "Reply with exactly OK."}]}
            + (if $name == "gpt-6-luna" then {max_completion_tokens: 32, reasoning_effort: "none"} else {max_tokens: 8} end)
            + (if $ext then {} else {chat_template_kwargs: {enable_thinking: false}} end)')
        body=$(json_file <<<"$payload")
        [[ $(http POST "$url" none "$body") =~ ^40[13]$ ]] || { echo "[FAIL] Unauthenticated inference did not fail closed"; exit 1; }
        [[ $(http POST "$url" invalid "$body") =~ ^40[13]$ ]] || { echo "[FAIL] Invalid synthetic key did not fail closed"; exit 1; }
        if [[ "$SINGLE" == true || ( "$external" == false && -z "$REVOKE_URL" ) ]]; then
            REVOKE_URL=$url
            REVOKE_BODY=$( [[ "$SINGLE" == true ]] && echo "$body" || jq '.max_tokens = 1' <<<"$payload" | json_file)
        fi
        before=0; [[ "$external" == false ]] && before=$(counter "$name")
        phase=completion
        result=""
        if response=$(api POST "$url" key "$body" 2>"$WORK/status"); then
            if ! jq -e '(.choices[0].message.content // "") != "" and (.usage.total_tokens // 0) > 0' <<<"$response" >/dev/null; then
                echo "[FAIL] Bounded completion or usage is absent for $name"; exit 1
            fi
            result=$(jq -c --arg n "$name" --arg id "$model_id" '{model: $n, catalog_id: $id, unauthenticated_denied: true,
                invalid_key_denied: true, completion_with_usage: true,
                usage: (.usage | with_entries(select(.key == "prompt_tokens" or .key == "completion_tokens" or .key == "total_tokens")))}' <<<"$response")
            if [[ "$SINGLE" == true ]]; then
                evidence --argjson r "$(jq -c '.streaming_and_tools_tested = false' <<<"$result")" '.models += [$r]'
                continue
            fi
            phase=stream
            stream_body=$(jq --arg name "$name" '.stream = true | .stream_options = {include_usage: true}
                | .messages = [{role: "user", content: "Count from 1 to 20, separated by commas. Do not think."}]
                | if $name == "gpt-6-luna" then .max_completion_tokens = 64 else .max_tokens = 64 end' <<<"$payload" | json_file)
            if streamed=$(stream_check "$url" "$stream_body"); then
                result=$(jq -c --argjson s "$streamed" '. + $s' <<<"$result")
                if [[ "$name" == gpt-6-luna ]]; then
                    phase=tool-call
                    tools=$(jq '.max_completion_tokens = 128 | .messages = [{role: "user", content: "Call report_status with status OK."}]
                        | .tools = [{type: "function", function: {name: "report_status", description: "Return a status",
                            parameters: {type: "object", properties: {status: {type: "string"}}, required: ["status"], additionalProperties: false}}}]
                        | .tool_choice = {type: "function", function: {name: "report_status"}}' <<<"$payload" | json_file)
                    if api POST "$url" key "$tools" 2>/dev/null | jq -e 'any(.choices[0].message.tool_calls[]?; .function.name == "report_status"
                        and (.function.arguments | fromjson | .status) == "OK")' >/dev/null; then
                        result=$(jq -c '.tool_call = true' <<<"$result")
                    else
                        response=""
                    fi
                fi
            else
                response=""
            fi
        else
            response=""
        fi
        if [[ -z "$response" || -z "$result" || ( "$phase" != completion && -z "$streamed" ) ]]; then
            evidence --arg n "$name" --arg id "$model_id" --arg p "$phase" '.model_http_failures += [{model: $n, catalog_id: $id, phase: $p}]'
            [[ -n "$result" ]] && evidence --argjson r "$result" '.models += [$r]'
            FAILED=true
            echo "[FAIL] Bounded $name $phase"
            continue
        fi
        if [[ "$external" == false ]]; then
            deadline=$((SECONDS + 90))
            until awk -v a="$(counter "$name")" -v b="$before" 'BEGIN {exit !(a > b)}'; do
                (( SECONDS < deadline )) || { echo "[FAIL] Local inference traffic counter did not increase"; exit 1; }
                sleep 5
            done
            # Observed topology fields, not proof that a request invoked the EPP.
            result=$(oc --request-timeout=10s get llminferenceservices.serving.kserve.io "$name" -n internal-models -o json |
                jq -c --argjson r "$result" '$r + {traffic_counter_increased: true, per_request_epp_selection: "not qualified by this API test",
                    native_scheduler: {inference_pool: .status.router.scheduler.inferencePool.name, epp_service: .status.router.scheduler.service.name,
                        workload: .status.workloads.scheduler.name, ready_replicas: .status.workloads.scheduler.readyReplicas}}')
        fi
        evidence --argjson r "$result" '.models += [$r]'
        echo "[PASS] Bounded $name authentication, completion, incremental SSE and usage$([[ "$external" == false ]] && echo " with traffic metric")"
    done < <(jq -c '.[]' <<<"$REFS")
}
( functional )
