#!/usr/bin/env bash
# Stage 060 validation (read-only): the five component Applications, the agent console's dashboard flag and
# read-only discovery permissions, the native MCP lifecycle operator, the two native OpenShift MCP servers, and that
# the three agent sandboxes exist (ai-agents opencode and hermes, openshell-developer opencode).
# Full-stage acceptance (persona handshake, agent lifecycle) is pending by design, so a complete run exits 2 at best;
# --component checks one component and exits 0 when it passes. --static checks only the repository render.
# Usage: stages/060-agent-runtime-and-agentops/validate.sh [--static | --component 060-agent-console|060-mcp-platform|060-agent-tools]
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"
COMPONENT=""
case "${1:-}" in
  --static) "$REPO_ROOT/scripts/stage-apps.sh" check-static 060; exit 0 ;;
  --component) COMPONENT=${2:?}; [[ $# -eq 2 ]] || { sed -n 's/^# Usage: //p' "$0" >&2; exit 1; } ;;
  "") ;;
  *) sed -n 's/^# Usage: //p' "$0" >&2; exit 1 ;;
esac
load_env
check_oc_logged_in
GITOPS=gitops/stages/060-agent-runtime-and-agentops
read_json() { oc --request-timeout=10s get "$@" --ignore-not-found -o json 2>/dev/null || true; }
yes_no() { jq -e "$@" >/dev/null 2>&1 && echo yes || echo no; }
# Application at its pinned immutable revision: Synced, Healthy, and its last operation a successful sync of it.
reconciled() {
  read_json applications.argoproj.io "$1" -n openshift-gitops | yes_no --arg repo "$GIT_REPO_URL" --arg path "$GITOPS/$1" --arg rev "${RHOAI_STAGE060_EXPECTED_REVISION:-}" '
    .spec as $s | .status as $st | $s.source.repoURL == $repo and $s.source.path == $path and $s.project == "rhoai-demo"
    and ($rev == "" or $s.source.targetRevision == $rev) and $s.sources == null and (.metadata.ownerReferences // [] | length) == 0
    and $s.destination == {server: "https://kubernetes.default.svc", namespace: "openshift-gitops"}
    and $st.sync.status == "Synced" and $st.sync.revision == $s.source.targetRevision and $st.health.status == "Healthy"
    and $st.operationState.phase == "Succeeded" and $st.operationState.syncResult.revision == $s.source.targetRevision
    and $st.operationState.syncResult.source.path == $s.source.path'
}

# ── 060-agent-console: AgentOps flag; personas discover only their own workspace, read-only ──────────────────
validate_console() {
  record "060-agent-console reconciled from this repository" "$(reconciled 060-agent-console)"
  record "Dashboard AgentOps enabled" "$(read_json odhdashboardconfig odh-dashboard-config -n redhat-ods-applications |
    yes_no '.spec.dashboardConfig.agentOps == true')"
  can() { oc --request-timeout=10s auth can-i "$1" "$2" -n "$3" --as="$4" 2>/dev/null || true; }
  discovery() {
    local user=$1 own=$2 foreign=$3 resource verb
    for resource in sandboxes.agents.x-k8s.io services; do
      for verb in get list; do [[ $(can "$verb" "$resource" "$own" "$user") == yes ]] || { echo "cannot $verb $resource in $own"; return; }; done
    done
    for verb in create delete; do [[ $(can "$verb" sandboxes.agents.x-k8s.io "$own" "$user") == no ]] || { echo "may $verb sandboxes"; return; }; done
    [[ $(can list sandboxes.agents.x-k8s.io "$foreign" "$user") == no ]] || { echo "may list sandboxes in $foreign"; return; }
    echo yes
  }
  check "ai-admin discovers openshell-admin read-only, not openshell-developer" "discovery ai-admin openshell-admin openshell-developer" yes
  check "ai-developer discovers openshell-developer read-only, not openshell-admin" "discovery ai-developer openshell-developer openshell-admin" yes
}

# ── 060-mcp-platform: the native MCP lifecycle operator, its API and its current workload ──────────────────────
validate_mcp_platform() {
  local dsc component deployments image
  record "060-mcp-platform reconciled from this repository" "$(reconciled 060-mcp-platform)"
  dsc=$(read_json datasciencecluster default-dsc)
  component=$(read_json mcplifecycleoperators.components.platform.opendatahub.io default)
  deployments=$(oc --request-timeout=10s get deployments -n redhat-ods-applications -l app.kubernetes.io/name=mcp-lifecycle-operator -o json 2>/dev/null || echo '{}')
  image=$(jq -r '.image' "$REPO_ROOT/$GITOPS/060-mcp-platform/operator-source.json")
  record "MCP lifecycle component Managed and MCPLifecycleOperatorReady" "$(yes_no '.spec.components.mcplifecycleoperator.managementState == "Managed"
    and any(.status.conditions[]?; .type == "MCPLifecycleOperatorReady" and .status == "True")' <<<"$dsc")"
  record "MCPLifecycleOperator owned by the current DataScienceCluster and Ready at its generation" "$(jq -n -e \
    --argjson c "${component:-null}" --argjson d "$dsc" '$c != null and $c.metadata.deletionTimestamp == null and $c.spec.managementState == "Managed"
    and any($c.metadata.ownerReferences[]?; .uid == $d.metadata.uid and .kind == "DataScienceCluster" and .controller == true)
    and $c.status.observedGeneration == $c.metadata.generation
    and any($c.status.conditions[]?; .type == "Ready" and .status == "True" and .observedGeneration == $c.metadata.generation)' >/dev/null && echo yes || echo no)"
  record "One operator Deployment, owned by the component, at the reviewed image, rolled out" "$(jq -n -e --argjson ds "$deployments" \
    --argjson c "${component:-null}" --arg image "$image" '($ds.items // []) | length == 1 and (.[0] | (.spec.replicas // 1) as $n | .status as $s
    | .metadata.deletionTimestamp == null and any(.metadata.ownerReferences[]?; .uid == $c.metadata.uid and .kind == "MCPLifecycleOperator" and .controller == true)
    and ([.spec.template.spec.containers[].image] | index($image)) != null
    and $n > 0 and $s.observedGeneration == .metadata.generation
    and all("replicas", "updatedReplicas", "readyReplicas", "availableReplicas"; ($s[.] // 0) == $n))' >/dev/null && echo yes || echo no)"
  record "MCPServer API established and served (mcp.x-k8s.io v1alpha1)" "$(read_json crd mcpservers.mcp.x-k8s.io | yes_no '.spec.group == "mcp.x-k8s.io"
    and any(.spec.versions[]; .name == "v1alpha1" and .served) and any(.status.conditions[]?; .type == "Established" and .status == "True")')"
}

# ── 060-agent-tools: the token-less read-only server and the token-bearing read-write server ──────────────────
# TOML subset of config.toml (key = value, [table], [[array-table]]) as JSON; values are TOML literals JSON shares.
toml_json() {
  awk '/^[[:space:]]*(#|$)/ { next }
    /^\[\[.*\]\]$/ { t = substr($0, 3, length($0) - 4); n[t]++; prefix = "\"" t "\"," (n[t] - 1) ","; next }
    /^\[.*\]$/ { prefix = "\"" substr($0, 2, length($0) - 2) "\","; next }
    { k = $0; sub(/[[:space:]]*=.*/, "", k); v = $0; sub(/^[^=]*=[[:space:]]*/, "", v); print "[[" prefix "\"" k "\"]," v "]" }' |
    jq -n 'reduce inputs as [$path, $value] ({}; setpath($path; $value))'
}
MCP_IMAGE="registry.redhat.io/openshift-mcp-tech-preview/openshift-mcp-server-rhel9@sha256:855466299c3178f7d9f96a1511005ca6161b8cc6b294df9907c234ce8ecfd0f2"
# check_server NAME READ_ONLY REQUIRE_OAUTH ROUTE SERVICE_ACCOUNT
check_server() {
  local name=$1 read_only=$2 oauth=$3 route=$4 sa=$5 server child obj resource deployment rsuids
  server=$(read_json mcpservers.mcp.x-k8s.io "$name" -n mcp-servers)
  [[ -n "$server" ]] || { echo "MCPServer $name absent"; return; }
  obj=$(read_json route "$name" -n mcp-servers)
  if [[ "$route" == true ]]; then
    jq -e --arg n "$name" '.metadata.annotations["argocd.argoproj.io/tracking-id"] == "060-agent-tools:route.openshift.io/Route:mcp-servers/\($n)"
      and (.metadata.ownerReferences // [] | length) == 0 and .spec.tls == {termination: "edge", insecureEdgeTerminationPolicy: "Redirect"}
      and .spec.to.name == $n and .spec.port.targetPort == 8080
      and any(.status.ingress[]?.conditions[]?; .type == "Admitted" and .status == "True")' <<<"${obj:-null}" >/dev/null 2>&1 ||
      { echo "HTTPS edge Route differs or is not admitted"; return; }
  else
    [[ -z "$obj" ]] || { echo "token-less server must not have a Route"; return; }
  fi
  oc --request-timeout=10s get configmap "$name" -n mcp-servers -o jsonpath='{.data.config\.toml}' | toml_json |
    jq -e --argjson ro "$read_only" --argjson oauth "$oauth" '.stateless == true and .skip_jwt_verification == true and .disable_dynamic_client_registration == true
      and .require_oauth == $oauth and .read_only == $ro and ($ro or .disable_destructive == false)
      and .cluster_auth_mode == "passthrough" and .cluster_provider_strategy == "in-cluster" and .require_tls == false
      and .toolsets == ["core", "config"] and (.enabled_tools // [] | length) == 0 and (.disabled_tools // [] | length) == 0
      and .denied_resources == [{group: "", version: "v1", kind: "Secret"}]' >/dev/null || { echo "caller-auth/read-only/tool policy differs"; return; }
  jq -e --arg image "$MCP_IMAGE" '.spec.source.containerImage.ref == $image and .spec.config.port == 8080 and .spec.config.path == "/mcp"
    and ([.status.conditions[]? | select(.type == "Ready")] | length == 1 and .[0].status == "True" and .[0].observedGeneration == $ARGS.named.g)' \
    --argjson g "$(jq '.metadata.generation' <<<"$server")" <<<"$server" >/dev/null || { echo "image, handshake configuration or readiness differs"; return; }
  for resource in deployment service networkpolicy; do
    read_json "$resource" "$name" -n mcp-servers | jq -e --arg uid "$(jq -r '.metadata.uid' <<<"$server")" \
      'any(.metadata.ownerReferences[]?; .uid == $uid and .kind == "MCPServer" and .controller == true)' >/dev/null 2>&1 ||
      { echo "$resource is not controlled by the MCPServer"; return; }
  done
  deployment=$(read_json deployment "$name" -n mcp-servers)
  jq -e --arg sa "$sa" --arg image "$MCP_IMAGE" '(.spec.replicas // 1) as $n | .status as $s | .spec.template.spec.serviceAccountName == $sa
    and (.spec.template.spec.containers | length == 1 and .[0].image == $image) and $s.observedGeneration == .metadata.generation
    and all("replicas", "updatedReplicas", "readyReplicas", "availableReplicas"; ($s[.] // 0) == $n)' <<<"$deployment" >/dev/null ||
    { echo "Deployment service account, image or rollout differs"; return; }
  # Every ready Pod runs the reviewed amd64 artifact under the expected service account.
  child=$(jq -r '.amd64_image_digest' "$REPO_ROOT/$GITOPS/060-agent-tools/catalog-source.json")
  rsuids=$(read_json replicasets -n mcp-servers | jq -c --arg uid "$(jq -r '.metadata.uid' <<<"$deployment")" '[.items[]
    | select(any(.metadata.ownerReferences[]?; .uid == $uid and .controller == true)) | .metadata.uid]')
  read_json pods -n mcp-servers | jq -e --argjson rs "$rsuids" --argjson d "$deployment" --arg sa "$sa" --arg child "$child" '
    [.items[] | select(.metadata.deletionTimestamp == null and any(.metadata.ownerReferences[]?; (.uid | IN($rs[])) and .controller == true))] as $pods
    | ($pods | length) == ($d.spec.replicas // 1) and all($pods[]; .spec.serviceAccountName == $sa and .status.phase == "Running"
      and any(.status.containerStatuses[]?; .name == $d.spec.template.spec.containers[0].name and .ready == true and (.imageID | endswith("@" + $child))))' \
    >/dev/null || { echo "ready Pods differ from the reviewed amd64 artifact or service account"; return; }
  echo yes
}
validate_agent_tools() {
  local ns binding
  record "060-agent-tools reconciled from this repository" "$(reconciled 060-agent-tools)"
  ns=$(read_json namespace mcp-servers)
  record "MCP hosting project tracked, named and visible in the dashboard" "$(yes_no '.metadata.annotations["argocd.argoproj.io/tracking-id"]
    == "060-agent-tools:/Namespace:openshift-gitops/mcp-servers" and .metadata.annotations["openshift.io/display-name"] == "MCP servers"
    and .metadata.labels["opendatahub.io/dashboard"] == "true"' <<<"${ns:-null}")"
  binding=$(read_json rolebinding mcp-host-admin -n mcp-servers)
  record "Hosting project grants admin only to ai-admin" "$(yes_no '.roleRef == {apiGroup: "rbac.authorization.k8s.io", kind: "ClusterRole", name: "admin"}
    and .subjects == [{apiGroup: "rbac.authorization.k8s.io", kind: "User", name: "ai-admin"}]' <<<"${binding:-null}")"
  check "openshift-mcp-server: token-less, read-only, in-cluster only" "check_server openshift-mcp-server true false false openshift-mcp-server-ro" yes
  check "openshift-mcp-server-rw: token required, read-write, HTTPS Route" "check_server openshift-mcp-server-rw false true true openshift-mcp-server" yes
}

case "$COMPONENT" in
  "")
    log_step "Stage 060 component Applications"
    check_stage_applications 060 "${RHOAI_STAGE060_EXPECTED_REVISION:-}"
    validate_console; validate_mcp_platform; validate_agent_tools
    # The agent sandboxes are created by the opt-in sandboxes/create.sh (persona sessions), never by deploy.sh; a
    # missing one is a pending provisioning step, so name the command that creates it.
    log_step "Agent sandboxes (sandboxes/create.sh)"
    for sandbox in ai-agents/opencode ai-agents/hermes openshell-developer/opencode; do
      ns=${sandbox%/*} name=${sandbox#*/}
      if oc --request-timeout=10s get sandboxes.agents.x-k8s.io "$name" -n "$ns" -o name >/dev/null 2>&1; then
        record "Agent sandbox $sandbox exists" pass
      else
        owner=""; [[ "$ns" == openshell-developer ]] && owner=" --owner ai-developer"
        record_warn "Agent sandbox $sandbox exists" "pending: sandboxes/create.sh $name$owner --revision SHA --apply"
      fi
    done
    record_warn "Full-stage acceptance" "persona handshake and agent lifecycle remain pending by design" ;;
  060-agent-console) validate_console ;;
  060-mcp-platform) validate_mcp_platform ;;
  060-agent-tools) validate_agent_tools ;;
  *) echo "Unknown component $COMPONENT" >&2; exit 1 ;;
esac
echo "Scope: configuration, ownership and readiness; MCP protocol, caller isolation and browser workflows are not qualified here."
validation_summary
