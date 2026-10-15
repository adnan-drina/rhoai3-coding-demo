#!/usr/bin/env bash
# Read-only native Stage 040 readiness: component Applications, the six operators, GPU LocalQueues, AIGateway/OGX/
# KServe and dashboard flags, the MaaS database, Authorino TLS, the Gateway and its listener isolation, the local
# model and its routes, serving templates, external providers and models, MaaS governance objects, and the Studio
# catalog entries. No HTTP, provider calls or writes; no Secret value or command error reaches the output.
# RHOAI_STAGE040_EXPECTED_REVISION pins the components to one commit (deploy.sh sets it).
# Usage: stages/040-governed-models-as-a-service/validate-native.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/shared/validate-lib.sh"

STAGE_APPS="$REPO_ROOT/scripts/shared/stage_apps.py"
TIMEOUT="${RHOAI_OC_REQUEST_TIMEOUT:-10s}"
read_json() { oc --request-timeout="$TIMEOUT" get "$@" -o json; }
python3 "$REPO_ROOT/scripts/platform/check-operator-policy.py" "$REPO_ROOT/gitops/stages/040-governed-models-as-a-service" --verify

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

DESIRED=$(oc kustomize "$REPO_ROOT/gitops/stages/040-governed-models-as-a-service" |
    ruby -ryaml -rjson -e 'puts JSON.generate(YAML.load_stream(STDIN.read).compact)')
desired_of() { jq -c --arg k "$1" '[.[] | select(.kind == $k)]' <<<"$DESIRED"; }

components_reconciled() {
    python3 "$STAGE_APPS" status 040 ${RHOAI_STAGE040_EXPECTED_REVISION:+--revision "$RHOAI_STAGE040_EXPECTED_REVISION"} \
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
    models=$(desired_of LLMInferenceService)
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
    jq -e --argjson n "$(jq length <<<"$models")" '[.items[] | select(any(.spec.parentRefs[]?; .name == "maas-default-gateway"))]
        | length == $n' <<<"$routes" >/dev/null || { echo "extra inference route"; return; }
    if [[ "$parked" == true ]]; then echo yes-parked; else echo yes; fi
}
serving_templates() {
    local d name ns tracking
    while IFS= read -r d; do
        name=$(jq -r '.metadata.name' <<<"$d"); ns=$(jq -r '.metadata.namespace' <<<"$d")
        tracking=$(python3 "$STAGE_APPS" owner 040 LLMInferenceServiceConfig "$name" "$ns" --group serving.kserve.io)
        read_json llminferenceserviceconfigs.serving.kserve.io "$name" -n "$ns" | jq -e --argjson d "$d" \
            --arg t "$tracking:serving.kserve.io/LLMInferenceServiceConfig:$ns/$name" '.spec == $d.spec
            and (.metadata.ownerReferences // [] | length) == 0 and .metadata.deletionTimestamp == null
            and .metadata.annotations["argocd.argoproj.io/tracking-id"] == $t
            and (.metadata.labels as $live | all($d.metadata.labels | to_entries[]; $live[.key] == .value))
            and (if $d.metadata.labels["opendatahub.io/config-type"] == "router"
                 then .metadata.annotations["opendatahub.io/supported-topologies"] == "[\"workload-single-node\"]" else true end)' \
            >/dev/null || { echo "$name"; return; }
    done < <(desired_of LLMInferenceServiceConfig | jq -c '.[]')
    read_json llminferenceserviceconfigs.serving.kserve.io -n redhat-ods-applications | jq -e '[.items[]
        | select(.metadata.labels["opendatahub.io/config-type"] == "accelerator" and (.metadata.name | endswith("single-node-template-nvidia-cuda")))]
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
studio_catalog() {
    python3 "$SCRIPT_DIR/publish-catalog-mcp.py" --validate --defer-if-absent >/dev/null 2>&1 &&
        python3 "$SCRIPT_DIR/publish-catalog-mcp.py" --key OpenShift-MCP-ReadWrite --validate --defer-if-absent >/dev/null 2>&1 &&
        echo yes || echo no
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
check "Declared MaaS subscriptions and auth policies Active and Ready (quota enforcement is functional acceptance)" governance yes
check "Studio catalog entries current, or deferred until Stage 060 deploys the MCP servers" studio_catalog yes
validation_summary
