#!/usr/bin/env bash
# Shared functions of sandboxes/create.sh and sandboxes/qualify.sh; sourced, never run. They hold the guarded persona
# and bootstrap sessions, the pinned OpenShell CLI over an owned gateway tunnel, the owner-only setup journal, and the
# owned sandbox setup itself (preflight, inventory, global policy, provisioning, check). Read-only unless a caller runs
# setup_policy_input with APPLY=true or setup_provision. Credentials stay in memory, pipes and the private temporary CLI
# profiles the CLI reads them from; nothing here prints one.
# Usage: source "$SCRIPT_DIR/native.sh" (from create.sh or qualify.sh)
[[ "${BASH_SOURCE[0]}" != "$0" ]] || { sed -n 's/^# Usage: //p' "$0" >&2; exit 1; }

STAGE060=gitops/stages/060-agent-runtime-and-agentops
RUNTIME_PATH=$STAGE060/060-openshell-runtime
PINS="$REPO_ROOT/$RUNTIME_PATH/chart/source-pins.json"
SANDBOXES="$REPO_ROOT/stages/060-agent-runtime-and-agentops/sandboxes"
# The default owner: ai-admin in ai-agents, the workspace's native administrator, who also manages its profiles,
# providers and templates. owner_select switches to the developer path.
OWNER=ai-admin WORKSPACE=ai-agents MEMBER_ROLE=admin SETUP_ROLE=owner
IMAGE_NAMESPACE=ai-agents
MODEL=publishers/internal-models/models/qwen3-8-27b
SOURCE_COMMIT=12cec59bf4c36c305032143eb90870bd16d8820b
STATE_ROOT="$HOME/.local/state/rhoai3-coding-demo/060-sandboxes"

# fail MESSAGE: refuse; the first refusal is also kept in $WORK/failure (subshells included) for a receipt.
fail() {
  [[ -z "${WORK:-}" || -e "$WORK/failure" ]] || printf '%s' "$*" >"$WORK/failure" 2>/dev/null || true
  echo "[FAIL] $*" >&2
  exit 1
}
# File mode (octal) and owner uid, macOS or Linux stat.
file_mode() { stat -f %Lp "$1" 2>/dev/null || stat -c %a "$1"; }
file_owner() { stat -f %u "$1" 2>/dev/null || stat -c %u "$1"; }
# Owner-only: a regular file or directory, not a symlink, with no group or other permission bits.
private_path() { [[ -e "$1" && ! -L "$1" ]] && [[ $(file_mode "$1") == *00 ]]; }
# Canonical JSON digest: sorted keys, compact, ASCII (the Python helpers' json.dumps(sort_keys=True)).
digest() { jq -acSj . | shasum -a 256 | cut -d' ' -f1; }
sha256_text() { printf '%s' "$1" | shasum -a 256 | cut -d' ' -f1; }
iso_epoch() { ruby -rtime -e 'printf("%.6f\n", Time.iso8601(ARGV[0]).to_r)' "$1"; }
iso_epoch_ms() { ruby -rtime -e 'puts((Time.iso8601(ARGV[0]).to_r * 1000).floor)' "$1"; }
random_secret() { openssl rand -base64 48 | tr '+/' '-_' | tr -d '=\n'; }

# ── Work directory, background processes and cleanup ─────────────────────────────────────────────────────────────
# work_init: a private work directory for sessions and background processes (a subshell may start its own).
work_init() {
  WORK=$(mktemp -d "${TMPDIR:-/tmp}/060-sandboxes.XXXXXX")
  chmod 700 "$WORK"
  : >"$WORK/pids"
}
work_init
# native_cleanup: stop tunnels, return a refreshed persona token, remove private profiles. Callers run it on EXIT.
native_cleanup() {
  local pid
  while read -r pid; do kill "$pid" 2>/dev/null || true; done <"$WORK/pids"
  session_return_persona_token || true
  rm -rf "$WORK"
}
# bounded SECONDS COMMAND...: run COMMAND, killed after SECONDS (there is no timeout(1) on macOS).
bounded() {
  local seconds=$1 pid watcher rc=0
  shift
  "$@" &
  pid=$!
  (sleep "$seconds"; kill "$pid" 2>/dev/null) >/dev/null 2>&1 &
  watcher=$!
  wait "$pid" || rc=$?
  kill "$watcher" 2>/dev/null || true
  wait "$watcher" 2>/dev/null || true
  return "$rc"
}

# ── Guarded sessions ─────────────────────────────────────────────────────────────────────────────────────────────
# guarded KUBECONFIG: a private kubeconfig whose session passes the project cluster guard.
guarded() {
  [[ -n "$1" ]] && private_path "$1" && [[ -f "$1" ]] || fail "Private session input must exist with private permissions"
  (export KUBECONFIG="$1"; check_oc_logged_in) >/dev/null 2>&1 || fail "Project cluster guard rejected session"
}
# boc / poc: oc as the bootstrap administrator / as the persona, bounded; a failure is a refusal.
boc() { KUBECONFIG="$BOOTSTRAP_KUBECONFIG" oc --request-timeout=10s "$@" 2>/dev/null || fail "Guarded native API read failed"; }
poc() { KUBECONFIG="$PERSONA_KUBECONFIG" oc --request-timeout=10s "$@" 2>/dev/null || fail "Guarded native API read failed"; }
bget() { boc get "$1" "$2" -n "$3" -o json; }
# persona_session PERSONA: the persona kubeconfig is guarded, is exactly PERSONA, targets the bootstrap API server;
# its OpenShift token is kept in USER_TOKEN (memory only).
persona_session() {
  guarded "$PERSONA_KUBECONFIG"
  [[ $(poc whoami) == "$1" ]] || fail "Session is not the exact requested persona"
  USER_TOKEN=$(poc whoami -t)
  guarded "$BOOTSTRAP_KUBECONFIG"
  [[ $(poc whoami --show-server) == $(boc whoami --show-server) ]] || fail "Persona and bootstrap target different clusters"
}
# resolve_cli: the pinned OpenShell CLI (RHOAI_STAGE060_OPENSHELL_CLI, default the pinned install path).
resolve_cli() {
  CLI=${RHOAI_STAGE060_OPENSHELL_CLI:-$HOME/.local/share/rhoai3-demo/openshell-$(jq -r '.cliRelease' "$PINS")/bin/openshell}
  [[ -f "$CLI" && $(shasum -a 256 "$CLI" | cut -d' ' -f1) == $(jq -r '.cliBinarySha256' "$PINS") ]] ||
    fail "Install the pinned OpenShell CLI at $CLI or set RHOAI_STAGE060_OPENSHELL_CLI (source-pins.json cliBinarySha256)"
}
# source_guard REVISION FILE...: each file equals its published content at REVISION.
source_guard() {
  local revision=$1 path
  shift
  for path in "$@"; do
    git -C "$REPO_ROOT" show "$revision:${path#"$REPO_ROOT"/}" 2>/dev/null | cmp -s - "$path" || fail "Published helper or input differs: ${path#"$REPO_ROOT"/}"
  done
}

# ── HTTP (MaaS API) ──────────────────────────────────────────────────────────────────────────────────────────────
# http METHOD URL [TOKEN_VARIABLE] [BODY]: sets HTTP_STATUS and HTTP_BODY. The bearer is read from the named variable
# and reaches curl through a --config pipe; redirects are not followed.
http() {
  local method=$1 url=$2 token=${3:-} body=${4:-} out data=()
  [[ -z "$body" ]] || data=(-H 'Content-Type: application/json' --data-binary @-)
  if [[ -n "$token" ]]; then
    out=$(printf '%s' "$body" | curl -s --max-time "${HTTP_TIMEOUT:-30}" -X "$method" ${data[@]+"${data[@]}"} -w '\n%{http_code}' \
      --config <(printf 'header = "Authorization: Bearer %s"\n' "${!token}") "$url") || out=$'\n000'
  else
    out=$(printf '%s' "$body" | curl -s --max-time "${HTTP_TIMEOUT:-30}" -X "$method" ${data[@]+"${data[@]}"} -w '\n%{http_code}' "$url") ||
      out=$'\n000'
  fi
  HTTP_STATUS=${out##*$'\n'}
  HTTP_BODY=${out%$'\n'*}
}

# ── Native gateway sessions (admin = bootstrap platform administrator, owner = the genuine persona login) ──────────
# A session is a private XDG_CONFIG_HOME holding the gateway metadata, CA and OIDC token, over its own tunnel.
gateway_forward() {
  local log port
  log=$(mktemp "$WORK/forward.XXXXXX")
  KUBECONFIG="$BOOTSTRAP_KUBECONFIG" oc --request-timeout=10s port-forward -n openshell service/openshell :8080 --address=127.0.0.1 >"$log" 2>&1 &
  echo "$!" >>"$WORK/pids"
  for _ in $(seq 1 75); do
    port=$(sed -n 's/^Forwarding from 127.0.0.1:\([0-9]*\) .*/\1/p' "$log" | head -1)
    [[ -n "$port" ]] && { echo "$port"; return 0; }
    sleep 0.2
  done
  fail "Native gateway tunnel unavailable"
}
# session_open ROLE [PERSONA_HOME]: ROLE admin (bootstrap token minted here) or owner (copied persona login).
session_open() {
  local role=$1 persona=${2:-} port home dir metadata
  ISSUER=$(bget configmap openshell-identity openshell | jq -r '.data.issuer')
  [[ "$ISSUER" == https://*/realms/openshell ]] || fail "Unexpected native issuer"
  port=$(gateway_forward)
  home="$WORK/native-$role"
  dir="$home/openshell/gateways/openshell"
  mkdir -p "$home/openshell/gateways"
  if [[ -n "$persona" ]]; then
    [[ -d "$persona/openshell/gateways/openshell" ]] || fail "Genuine native persona session is missing"
    cp -Rp "$persona/openshell/gateways/openshell" "$dir"
    jq -e --arg i "$ISSUER" '.oidc_issuer == $i and .oidc_client_id == "openshell-cli"' "$dir/metadata.json" >/dev/null 2>&1 ||
      fail "Foreign native persona session"
    metadata=$(cat "$dir/metadata.json")
  else
    mkdir -p "$dir/mtls"
    metadata=$(jq -n -c --arg i "$ISSUER" '{name: "openshell", is_remote: true, auth_mode: "oidc", oidc_issuer: $i,
      oidc_client_id: "openshell-bootstrap", oidc_audience: "openshell-gateway"}')
  fi
  mkdir -p "$dir/mtls"
  printf '%s' "$metadata" | jq -c --argjson p "$port" '. + {gateway_endpoint: "https://127.0.0.1:\($p)", gateway_port: $p}' >"$dir/metadata.json"
  echo openshell >"$home/openshell/active_gateway"
  boc get secret openshell-server-tls -n openshell -o jsonpath='{.data.ca\.crt}' | base64 -d >"$dir/mtls/ca.crt"
  if [[ "$role" == owner ]]; then
    OWNER_PERSONA_HOME=$persona
    OWNER_VERIFIED=false
  else
    echo 0 >"$home/.expires"
    session_refresh
  fi
}
# session_refresh: a fresh bootstrap platform-administrator token for the admin session, 45 s before expiry.
session_refresh() {
  local home="$WORK/native-admin" token claims
  (( $(date +%s) < $(cat "$home/.expires") - 45 )) && return 0
  token=$(bget secret openshell-auth keycloak |
    jq -j '"grant_type=client_credentials&client_id=openshell-bootstrap&client_secret=\(.data["bootstrap-client-secret"] | @base64d | @uri)"' |
    curl -s --max-time 15 --data-binary @- "$ISSUER/protocol/openid-connect/token" | jq -r '.access_token // empty')
  [[ -n "$token" ]] || fail "Bootstrap token request failed"
  claims=$(printf '%s' "$token" | cut -d. -f2 | tr '_-' '/+' | awk '{ while (length($0) % 4) $0 = $0 "="; print }' | base64 -d)
  printf '%s' "$claims" | jq -e --arg i "$ISSUER" '.iss == $i and (.realm_access.roles // [] | index("openshell-platform-admin")) != null' >/dev/null ||
    fail "Native bootstrap identity differs"
  (umask 077; TOKEN=$token jq -n -c --arg i "$ISSUER" --argjson exp "$(printf '%s' "$claims" | jq '.exp')" \
    '{access_token: $ENV.TOKEN, expires_at: $exp, issuer: $i, client_id: "openshell-bootstrap"}' >"$home/openshell/gateways/openshell/oidc_token.json")
  printf '%s' "$claims" | jq '.exp' >"$home/.expires"
}
# session_return_persona_token: once the owner identity was verified, return the CLI-refreshed token to the
# persona's login (exclusive create, then rename).
session_return_persona_token() {
  [[ "${OWNER_VERIFIED:-false}" == true && -n "${OWNER_PERSONA_HOME:-}" ]] || return 0
  local target="$OWNER_PERSONA_HOME/openshell/gateways/openshell/oidc_token.json"
  [[ -f "$target" ]] && private_path "$target" || { echo "[FAIL] Unsafe original native credential path" >&2; return 1; }
  (set -C; umask 077; cat "$WORK/native-owner/openshell/gateways/openshell/oidc_token.json" >"${target%.json}.refresh-pending") &&
    mv "${target%.json}.refresh-pending" "$target"
}
# ncli ROLE WORKSPACE|- SECONDS ARG...: the pinned CLI in a session; stderr (errors, credentials) is suppressed.
ncli() {
  local role=$1 workspace=$2 seconds=$3 command
  shift 3
  [[ "$role" == admin ]] && session_refresh
  command=("$CLI" --gateway openshell)
  [[ "$workspace" == - ]] || command+=(--workspace "$workspace")
  (export XDG_CONFIG_HOME="$WORK/native-$role"; bounded "$seconds" "${command[@]}" "$@" 2>/dev/null) ||
    fail "Bounded native operation failed: $1 ${2:-}; raw errors/credentials suppressed"
}
# ncli_status ROLE WORKSPACE|- SECONDS ARG...: like ncli, but returns the CLI's status and keeps its stderr in
# $WORK/ncli.stderr (for checks on a refusal's rendering; never printed).
ncli_status() {
  local role=$1 workspace=$2 seconds=$3 command
  shift 3
  [[ "$role" == admin ]] && session_refresh
  command=("$CLI" --gateway openshell)
  [[ "$workspace" == - ]] || command+=(--workspace "$workspace")
  (export XDG_CONFIG_HOME="$WORK/native-$role"; bounded "$seconds" "${command[@]}" "$@" 2>"$WORK/ncli.stderr")
}
# ncli_background ROLE WORKSPACE ARG...: start a long-running CLI command (a relay); sets BACKGROUND_PID.
ncli_background() {
  local role=$1 workspace=$2
  shift 2
  (export XDG_CONFIG_HOME="$WORK/native-$role"; exec "$CLI" --gateway openshell --workspace "$workspace" "$@") >/dev/null 2>&1 &
  BACKGROUND_PID=$!
  echo "$BACKGROUND_PID" >>"$WORK/pids"
}

# ── Owned sandbox identity (Kubernetes objects behind a native sandbox) ─────────────────────────────────────────────
# sandbox_identity NATIVE_JSON NAME WORKSPACE IMAGE running|stopped: prints {sandboxUid, pvcs}; on a refusal prints
# "REFUSED: <reason>" and returns 1 (callers wait on the transient reasons).
sandbox_identity() {
  local native=$1 name=$2 workspace=$3 image=$4 state=$5 resources resource pods pvcs
  printf '%s' "$native" | jq -e --arg n "$name" --arg w "$workspace" '.name == $n and .workspace == $w' >/dev/null ||
    { echo "REFUSED: Owned native name/workspace differs"; return 1; }
  if [[ "$state" == running ]]; then
    case "$(printf '%s' "$native" | jq -r '.phase // ""')" in
      Starting|Provisioning) echo "REFUSED: Owned native sandbox is starting"; return 1 ;;
      Ready) ;;
      *) echo "REFUSED: Owned native sandbox is not Ready; terminal or unexpected lifecycle state"; return 1 ;;
    esac
  else
    [[ $(printf '%s' "$native" | jq -r '.phase // ""') == Stopped ]] || { echo "REFUSED: Owned native sandbox did not reach Stopped"; return 1; }
  fi
  resources=$(boc get sandboxes -n "$workspace" -o json) || { echo "REFUSED: Guarded native API read failed"; return 1; }
  resource=$(printf '%s' "$resources" | jq -c --arg id "$(printf '%s' "$native" | jq -r '.id')" \
    '[.items[] | select(.metadata.labels["openshell.ai/sandbox-id"] == $id)] | if length == 1 then .[0] else empty end')
  [[ -n "$resource" ]] || { echo "REFUSED: Exact owned Kubernetes Sandbox is ambiguous"; return 1; }
  pods=$(boc get pods -n "$workspace" -o json | jq -c --arg uid "$(printf '%s' "$resource" | jq -r '.metadata.uid')" \
    '[.items[] | select(any(.metadata.ownerReferences[]?; .uid == $uid and .controller))]') || { echo "REFUSED: Guarded native API read failed"; return 1; }
  if [[ "$state" == running ]]; then
    printf '%s' "$pods" | jq -e 'length == 1 and .[0].status.phase == "Running"' >/dev/null || { echo "REFUSED: Owned workload is not Running"; return 1; }
    printf '%s' "$pods" | jq -e '.[0] | .metadata.annotations["openshift.io/scc"] == "restricted-v2"
      and .spec.serviceAccountName == "openshell-sandbox" and .spec.automountServiceAccountToken == false' >/dev/null ||
      { echo "REFUSED: Native restricted workload identity differs"; return 1; }
    printf '%s' "$pods" | jq -e --arg i "$image" '[.[0].spec.containers[] | select(.name == "agent")] | length == 1 and .[0].image == $i' >/dev/null ||
      { echo "REFUSED: Owned immutable workload image differs"; return 1; }
    printf '%s' "$pods" | jq -e '[.[0].status.containerStatuses[]? | select(.name == "agent")] | length == 1 and .[0].ready == true' >/dev/null ||
      { echo "REFUSED: Actual agent image is not ready"; return 1; }
    printf '%s' "$pods" | jq -e --arg d "${image#*@}" '[.[0].status.containerStatuses[] | select(.name == "agent")][0].imageID // "" | endswith($d)' >/dev/null ||
      { echo "REFUSED: Actual immutable agent image differs"; return 1; }
  else
    printf '%s' "$pods" | jq -e 'length == 0' >/dev/null || { echo "REFUSED: Stopped sandbox workload remains"; return 1; }
  fi
  printf '%s' "$resource" | jq -e '(.spec.volumeClaimTemplates // []) | length > 0' >/dev/null || { echo "REFUSED: Native sandbox lacks persistent storage"; return 1; }
  pvcs=$(boc get pvc -n "$workspace" -o json | jq -c --arg uid "$(printf '%s' "$resource" | jq -r '.metadata.uid')" \
    '[.items[] | select(any(.metadata.ownerReferences[]?; .uid == $uid))]') || { echo "REFUSED: Guarded native API read failed"; return 1; }
  jq -n -e --argjson r "$resource" --argjson p "$pvcs" '($p | length) == ($r.spec.volumeClaimTemplates | length) and all($p[]; .status.phase == "Bound")' >/dev/null ||
    { echo "REFUSED: Owned PVC identity is ambiguous"; return 1; }
  if [[ "$state" == running ]]; then
    jq -n -e --argjson pod "$(printf '%s' "$pods" | jq -c '.[0]')" --argjson p "$pvcs" \
      '([$pod.spec.volumes[]? | .persistentVolumeClaim.claimName // empty] | unique) == ([$p[].metadata.name] | unique)' >/dev/null ||
      { echo "REFUSED: Mounted PVC is outside owned persistent storage"; return 1; }
  fi
  jq -n -c --argjson r "$resource" --argjson p "$pvcs" '{sandboxUid: $r.metadata.uid, pvcs: ([$p[] | [.metadata.name, .metadata.uid]] | sort)}'
}

# ── Owned setup: runtime values and the owner-only recovery journal ─────────────────────────────────────────────────
# owner_select ai-admin|ai-developer: the hosting workspace and the persona's native role there. ai-developer is a
# workspace user of openshell-developer: the platform administrator session manages that workspace's profile,
# provider and template, the developer mints the key on their own subscription and owns the sandbox.
owner_select() {
  case "$1" in
    ai-admin) OWNER=ai-admin WORKSPACE=ai-agents MEMBER_ROLE=admin SETUP_ROLE=owner ;;
    ai-developer) OWNER=ai-developer WORKSPACE=openshell-developer MEMBER_ROLE=user SETUP_ROLE=admin ;;
    *) return 1 ;;
  esac
}
# runtime_select opencode|hermes
runtime_select() {
  case "$1" in
    opencode)
      NAME=opencode PROVIDER=opencode-maas-qwen38 SUBSCRIPTION=opencode-private-qwen38 IMAGE_TAG=opencode-runtime:1.18.16
      CONFIG_SOURCE=config.json CONFIG_DESTINATION=workspace/opencode.json LISTENER=server-password ;;
    hermes)
      NAME=hermes PROVIDER=hermes-maas-qwen38 SUBSCRIPTION=hermes-private-qwen38 IMAGE_TAG=hermes-runtime-api:0.20.5-api
      CONFIG_SOURCE=config.yaml CONFIG_DESTINATION=state/hermes/config.yaml LISTENER=server-key ;;
    *) return 1 ;;
  esac
  INPUTS="$SANDBOXES/$NAME"
  POLICY_FILE="$SANDBOXES/global-policy.yaml"
  SUBSCRIPTION_FILE="$REPO_ROOT/$RUNTIME_PATH/$NAME/subscription.yaml"
  TEMPLATE_FILE="$INPUTS/template.json" CONFIG_FILE="$INPUTS/$CONFIG_SOURCE" OVERRIDES=()
  # The developer's OpenCode: its own subscription, and a template and config sized for interactive work.
  if [[ "$OWNER" == ai-developer ]]; then
    [[ "$NAME" == opencode ]] || return 1
    SUBSCRIPTION=opencode-developer-qwen38
    SUBSCRIPTION_FILE="$REPO_ROOT/$RUNTIME_PATH/opencode/developer-subscription.yaml"
    TEMPLATE_FILE="$INPUTS/developer/template.json" CONFIG_FILE="$INPUTS/developer/$CONFIG_SOURCE"
    OVERRIDES=("$TEMPLATE_FILE" "$CONFIG_FILE")
  fi
  TEMPLATE=$(cat "$TEMPLATE_FILE")
  IMAGE=$(printf '%s' "$TEMPLATE" | jq -r '.image')
  IMAGE_DIGEST=${IMAGE#*@}
}
# state_save FIELDS_JSON: merge the object into the journal (atomic, owner-only). With READONLY_STATE=true it only
# checks that every field already has that value (qualification and the client never advance ownership).
state_save() {
  local fields=$1
  printf '%s' "$fields" | jq -e 'type == "object"' >/dev/null 2>&1 || fail "Journal update is not a JSON object"
  if [[ "${READONLY_STATE:-false}" == true ]]; then
    jq -n -e --argjson s "$STATE" --argjson f "$fields" 'all($f | to_entries[]; $s[.key] == .value)' >/dev/null || fail "$READONLY_MESSAGE"
    return 0
  fi
  STATE=$(jq -n -c --argjson s "$STATE" --argjson f "$fields" --arg w "$WORKSPACE" '$s + $f + {workspace: $w}')
  (umask 077; printf '%s' "$STATE" >"$STATE_DIR/state.pending")
  mv "$STATE_DIR/state.pending" "$JOURNAL"
}
state() { printf '%s' "$STATE" | jq -r "$@"; }

# setup_init: sessions, pins and the journal (Setup.__init__). Needs RUNTIME, PERSONA_KUBECONFIG, BOOTSTRAP_KUBECONFIG,
# STATE_DIR.
setup_init() {
  runtime_select "$RUNTIME" || fail "Owner $OWNER has no $RUNTIME sandbox path"
  persona_session "$OWNER"
  resolve_cli
  [[ $(jq -r '.sourceCommit' "$PINS") == "$SOURCE_COMMIT" ]] || fail "Native CLI/source pin differs"
  GATEWAY_PIN=$(jq -c '.images.gateway' "$PINS")
  (umask 077; mkdir -p "$STATE_DIR")
  [[ -d "$STATE_DIR" ]] && private_path "$STATE_DIR" || fail "Use an owner-only recovery directory"
  JOURNAL="$STATE_DIR/state.json"
  [[ ! -e "$JOURNAL" ]] || private_path "$JOURNAL" || fail "Unsafe recovery journal"
  STATE=$(cat "$JOURNAL" 2>/dev/null || echo '{}')
  state -e --arg w "$WORKSPACE" '. == {} or .workspace == $w' >/dev/null || fail "Foreign recovery state"
  RECEIPT=$(jq -n -c --arg o "$OWNER" --arg w "$WORKSPACE" --arg n "$NAME" --arg m "$MODEL" '{owner: $o, workspace: $w, sandbox: $n, model: $m, checks: {}, changes: []}')
}
# setup_preflight REVISION SOURCE_FILE...: read-only; the runtime revision, published sources, pinned gateway, the
# dedicated subscription, the rehomed image, the MaaS host and the model visible to the owner.
setup_preflight() {
  local revision=$1 gateway desired subscription file sources=()
  shift
  bget applications.argoproj.io 060-openshell-runtime openshift-gitops | jq -e --arg rev "$revision" '.spec.source.targetRevision == $rev
    and .status.sync.revision == $rev and .status.sync.status == "Synced" and .status.health.status == "Healthy" and .operation == null' >/dev/null ||
    fail "Exact runtime revision is not ready"
  for file in "$INPUTS"/*; do
    if [[ -f "$file" ]]; then sources+=("$file"); fi
  done
  source_guard "$revision" "$@" "$POLICY_FILE" "$PINS" "${sources[@]}" ${OVERRIDES[@]+"${OVERRIDES[@]}"}
  bget statefulset openshell openshell | jq -e --argjson pin "$GATEWAY_PIN" '.spec.template.spec.containers[0].image as $i
    | ($i | split("@")[0] | split(":")[0]) == $pin.repository and ($i | endswith("@" + $pin.amd64Digest)) and .status.readyReplicas == 1' >/dev/null ||
    fail "Gateway does not match the ready pinned runtime"
  desired=$(yaml_json <"$SUBSCRIPTION_FILE" | jq -c '.[0].spec')
  subscription=$(bget maassubscription "$SUBSCRIPTION" models-as-a-service)
  printf '%s' "$subscription" | jq -e --argjson d "$desired" '.spec == $d' >/dev/null ||
    fail "Dedicated subscription differs from its complete reviewed scope"
  printf '%s' "$subscription" | jq -e --arg o "$OWNER" '.spec.owner == {users: [$o]} and (.spec.modelRefs | length) == 1
    and .spec.modelRefs[0].name == "qwen3-8-27b" and .spec.modelRefs[0].namespace == "internal-models"' >/dev/null ||
    fail "Private subscription scope differs"
  printf '%s' "$subscription" | jq -e '.metadata.generation as $g
    | any(.status.conditions[]?; .type == "Ready" and .status == "True" and .observedGeneration == $g)' >/dev/null ||
    fail "Dedicated subscription is not Ready"
  bget imagestreamtag "$IMAGE_TAG" "$IMAGE_NAMESPACE" | jq -e --arg d "$IMAGE_DIGEST" '.image.metadata.name == $d' >/dev/null ||
    fail "Rehomed immutable image is absent"
  gateway=$(bget gateway maas-default-gateway openshift-ingress)
  HOST=$(printf '%s' "$gateway" | jq -r '[.spec.listeners[] | select(.name == "api") | .hostname] | if length == 1 then .[0] else empty end')
  [[ -n "$HOST" ]] || fail "Common MaaS listener is ambiguous"
  API="https://$HOST"
  bget llminferenceservice qwen3-8-27b internal-models | jq -e '.spec | tostring | contains("--max-model-len=262144")' >/dev/null ||
    fail "OpenCode context limit differs from actual serving configuration"
  http GET "$API/v1/models" USER_TOKEN
  [[ "$HTTP_STATUS" == 200 ]] && printf '%s' "$HTTP_BODY" | jq -e --arg m "$MODEL" 'any(.data[]?; .id == $m and .ready)' >/dev/null ||
    fail "Canonical Qwen model is not available to $OWNER"
  http GET "$API/v1/subscriptions" USER_TOKEN
  [[ "$HTTP_STATUS" == 200 ]] && printf '%s' "$HTTP_BODY" | jq -e --arg s "$SUBSCRIPTION" '[(. // [])[] | select(.subscription_id_header == $s)] | length == 1' >/dev/null ||
    fail "Dedicated native subscription is not discoverable"
  SUBSCRIPTION_HEADER=$SUBSCRIPTION
}
# setup_inventory: the genuine owner, the hosting workspace, the recovery binding, fleet, policy, providers, templates.
setup_inventory() {
  local identity members workspaces workspace_id binding inputs file providers templates
  identity=$(ncli owner - 30 whoami -o json)
  members=$(ncli admin - 30 workspace member list --workspace "$WORKSPACE" -o json)
  jq -n -e --argjson i "$identity" --argjson m "$members" --arg o "$OWNER" --arg r "$MEMBER_ROLE" '($m.next_page_token // "") == ""
    and ($m.members | length) == 1 and $m.members[0].role == $r and $m.members[0].subject == $i.subject and $i.display_name == $o' >/dev/null 2>&1 ||
    fail "Genuine immutable workspace owner differs"
  printf '%s' "$identity" | jq -e '(.roles // [] | index("openshell-user")) != null and (.roles // [] | index("openshell-platform-admin")) == null' >/dev/null ||
    fail "Native owner role is outside the reviewed workspace scope"
  workspaces=$(ncli admin - 30 workspace list -o json)
  printf '%s' "$workspaces" | jq -e '(.next_page_token // "") == ""' >/dev/null || fail "Workspace inventory incomplete"
  workspace_id=$(printf '%s' "$workspaces" | jq -r --arg w "$WORKSPACE" '[.workspaces[] | select(.name == $w)] | if length == 1 then .[0].id else empty end')
  [[ -n "$workspace_id" ]] || fail "Native hosting workspace is ambiguous"
  inputs='{}'
  for file in "$INPUTS"/*; do
    if [[ -f "$file" ]]; then inputs=$(printf '%s' "$inputs" | jq -c --arg k "$(basename "$file")" --rawfile v "$file" '. + {($k): $v}'); fi
  done
  for file in ${OVERRIDES[@]+"${OVERRIDES[@]}"}; do
    inputs=$(printf '%s' "$inputs" | jq -c --arg k "developer/$(basename "$file")" --rawfile v "$file" '. + {($k): $v}')
  done
  inputs=$(printf '%s' "$inputs" | jq -c --rawfile v "$POLICY_FILE" '. + {"global-policy.yaml": $v}')
  binding=$(jq -n -c --arg server "$(boc whoami --show-server)" --arg issuer "$(bget configmap openshell-identity openshell | jq -r '.data.issuer')" \
    --arg gateway "$(bget statefulset openshell openshell | jq -r '.metadata.uid')" --arg ns "$(boc get namespace "$WORKSPACE" -o jsonpath='{.metadata.uid}')" \
    --arg ws "$workspace_id" --arg subject "$(printf '%s' "$identity" | jq -r '.subject')" --arg hash "$(printf '%s' "$inputs" | digest)" \
    '{server: $server, issuer: $issuer, gateway_uid: $gateway, namespace_uid: $ns, workspace_id: $ws, subject: $subject, source_input_hash: $hash}')
  state -e --argjson b "$binding" '.binding == null or .binding == $b' >/dev/null ||
    fail "Recovery cluster/owner/workspace/source binding differs; overwrite refused"
  OWNER_VERIFIED=true
  state_save "$(jq -n -c --argjson b "$binding" '{binding: $b}')"
  FLEET=$(ncli admin - 30 sandbox list --all-workspaces -o json)
  printf '%s' "$FLEET" | jq -e '(.next_page_token // "") == ""' >/dev/null || fail "Fleet inventory is incomplete"
  POLICY=$(ncli admin - 30 policy get --global --full -o json)
  providers=$(ncli "$SETUP_ROLE" "$WORKSPACE" 30 provider list -o json)
  templates=$(ncli "$SETUP_ROLE" "$WORKSPACE" 30 sandbox template list -o json)
  jq -n -e --argjson p "$providers" --argjson t "$templates" '($p.next_page_token // "") == "" and ($t.next_page_token // "") == ""' >/dev/null ||
    fail "Native provider/template inventory incomplete"
  PROVIDERS=$(printf '%s' "$providers" | jq -c '.providers')
  TEMPLATES=$(printf '%s' "$templates" | jq -c '.templates')
}
# setup_policy_input: the complete intended gateway-global policy (INTENDED). It is set only with APPLY=true, an empty
# fleet, an unchanged no-network original and the reviewed EXPECTED_POLICY_HASH.
setup_policy_input() {
  local authored original current fleet applied
  authored=$(sed "s/__MAAS_COMMON_HOST__/$HOST/g" "$POLICY_FILE" | yaml_json | jq -c '.[0]')
  original=$(state -c --argjson p "$POLICY" '.original_policy // $p.policy')
  jq -n -e --argjson o "$original" --argjson a "$authored" '($o.filesystem_policy // {}) as $f | $f.include_workdir == false
    and $f.read_write == $a.filesystem_policy.read_write and (($f.read_only // []) - $a.filesystem_policy.read_only) == []
    and $o.landlock == $a.landlock' >/dev/null || fail "Original filesystem or Landlock denials differ"
  INTENDED=$(jq -n -c --argjson o "$original" --argjson a "$authored" \
    '$o + {filesystem_policy: $a.filesystem_policy, landlock: $a.landlock, network_policies: $a.network_policies}')
  jq -n -e --argjson p "$POLICY" --argjson i "$INTENDED" '$p.policy == $i' >/dev/null && return 0
  [[ "${APPLY:-false}" == true ]] && jq -n -e --argjson f "$FLEET" --argjson o "$original" --argjson p "$POLICY" --arg h "${EXPECTED_POLICY_HASH:-}" \
    '($f.sandboxes // [] | length) == 0 and ($o.network_policies // {}) == {} and $p.hash == $h' >/dev/null ||
    fail "Durable global policy requires the reviewed unchanged empty-fleet baseline"
  state_save "$(jq -n -c --argjson o "$original" --argjson p "$POLICY" '{original_policy: $o, original_policy_hash: $p.hash}')"
  (umask 077; printf '%s' "$INTENDED" >"$STATE_DIR/policy.json")
  current=$(ncli admin - 30 policy get --global --full -o json)
  jq -n -e --argjson c "$current" --argjson p "$POLICY" '$c.hash == $p.hash' >/dev/null || fail "Concurrent global policy change; refused"
  fleet=$(ncli admin - 30 sandbox list --all-workspaces -o json)
  printf '%s' "$fleet" | jq -e '(.next_page_token // "") == "" and .sandboxes == []' >/dev/null ||
    fail "Concurrent fleet change before global policy update; refused"
  ncli admin - 30 policy set --global --yes --policy "$STATE_DIR/policy.json" >/dev/null
  applied=$(ncli admin - 30 policy get --global --full -o json)
  jq -n -e --argjson a "$applied" --argjson i "$INTENDED" '$a.policy == $i' >/dev/null || fail "Applied global policy differs"
  state_save "$(jq -n -c --argjson a "$applied" '{applied_policy_hash: $a.hash}')"
  # The applied policy is now the current one, so the second call in setup_provision passes. (The Python helper kept
  # its pre-update copy and refused there as a "concurrent change"; a rerun then completed.)
  POLICY=$applied
  RECEIPT=$(printf '%s' "$RECEIPT" | jq -c '.changes += ["durable-global-policy"]')
}
provider_digest() { jq -c 'if has("credential_keys") then .credential_keys |= sort else . end
  | if has("config_keys") then .config_keys |= sort else . end' | digest; }
# Python truthiness: null, false, 0, "", [] and {} are all false (jq treats only null and false so).
FALSY='def falsy: . == null or . == false or . == 0 or . == "" or . == [] or . == {}; '
sandbox_record() { jq -c '{id, name, workspace, labels, created_from_workload_template, restart_policy, policy_source}'; }

# setup_provision (create.sh --apply): profile, persistent MaaS key, provider, template, global policy, sandbox, files.
setup_provision() {
  local profiles exported found created expiry expiry_s metadata provider template arguments owned current upload password command
  local sandbox key_name
  # Provider profile: imported once, then pinned by its exported digest.
  (umask 077; sed "s/__MAAS_COMMON_HOST__/$HOST/g" "$INPUTS/profile.yaml" >"$STATE_DIR/profile.yaml")
  profiles=$(ncli "$SETUP_ROLE" "$WORKSPACE" 30 profile list -o json)
  if printf '%s' "$profiles" | jq -e --arg p "$PROVIDER" 'any(.[]; .id == $p) | not' >/dev/null; then
    ncli "$SETUP_ROLE" "$WORKSPACE" 30 profile lint -f "$STATE_DIR/profile.yaml" >/dev/null
    state_save '{"profile_pending": true}'
    ncli "$SETUP_ROLE" "$WORKSPACE" 30 profile import -f "$STATE_DIR/profile.yaml" >/dev/null
    exported=$(ncli "$SETUP_ROLE" "$WORKSPACE" 30 profile export "$PROVIDER" -o json)
    state_save "$(jq -n -c --arg h "$(printf '%s' "$exported" | digest)" '{profile_hash: $h, profile_pending: false}')"
  else
    exported=$(ncli "$SETUP_ROLE" "$WORKSPACE" 30 profile export "$PROVIDER" -o json)
    [[ $(state '.profile_hash // ""') == $(printf '%s' "$exported" | digest) ]] || fail "Existing profile is foreign or changed; import refused"
  fi
  # Provider: a 30-day persistent key on the dedicated subscription, held only by the native encrypted provider.
  found=$(printf '%s' "$PROVIDERS" | jq -c --arg p "$PROVIDER" '[.[] | select(.name == $p)]')
  if [[ $(printf '%s' "$found" | jq length) == 0 ]]; then
    state -e '(.key_id // null) == null and (.key_pending // false) == false' >/dev/null ||
      fail "Pending owned key requires explicit recovery/revocation before another mint"
    key_name="$NAME-runtime-qwen38"
    state_save "$(jq -n -c --arg k "$key_name" '{key_pending: true, key_name: $k}')"
    http POST "$API/v1/api-keys" USER_TOKEN "$(jq -n -c --arg n "$key_name" --arg s "$SUBSCRIPTION_HEADER" \
      '{name: $n, subscription: $s, expiresIn: "30d", ephemeral: false}')"
    created=$HTTP_BODY
    [[ "$HTTP_STATUS" == 201 ]] && printf '%s' "$created" | jq -e '(.id // "") != ""' >/dev/null || fail "Native persistent key creation failed"
    state_save "$(jq -n -c --arg id "$(printf '%s' "$created" | jq -r '.id')" '{key_id: $id, key_pending: true}')"
    printf '%s' "$created" | jq -e --arg s "$SUBSCRIPTION_HEADER" '.subscription == $s and .ephemeral == false and (.key // "") != ""' >/dev/null ||
      fail "Persistent key binding differs"
    KEY=$(printf '%s' "$created" | jq -r '.key')
    expiry=$(printf '%s' "$created" | jq -r '.expiresAt | if type == "string" then . else "" end')
    created=""
    expiry_s=0
    [[ -z "$expiry" ]] || expiry_s=$(iso_epoch "$expiry")
    jq -n -e --argjson e "$expiry_s" --argjson now "$(date +%s)" '$now + 86400 < $e and $e <= $now + 31 * 86400' >/dev/null ||
      fail "Native key expiry is outside the reviewed 30-day duration"
    state_save "$(jq -n -c --arg e "$expiry" --arg o "$OWNER" --arg s "$SUBSCRIPTION_HEADER" --arg h "$(sha256_text "$KEY")" \
      '{key_expiry: $e, key_owner: $o, key_subscription: $s, key_hash: $h}')"
    http GET "$API/v1/api-keys/$(state '.key_id')" USER_TOKEN
    metadata=$HTTP_BODY
    [[ "$HTTP_STATUS" == 200 ]] && printf '%s' "$metadata" | jq -e --arg o "$OWNER" --arg s "$SUBSCRIPTION" '.username == $o and .subscription == $s
      and .status == "active" and (.tenant // "") != ""' >/dev/null || fail "New persistent key owner/scope metadata differs"
    state_save "$(jq -n -c --arg t "$(printf '%s' "$metadata" | jq -r '.tenant')" '{key_tenant: $t}')"
    if [[ "$NAME" == hermes ]]; then
      http GET "$API/v1/models" KEY
      [[ "$HTTP_STATUS" == 200 ]] && printf '%s' "$HTTP_BODY" | jq -e --arg m "$MODEL" '[.data[]?.id] == [$m]' >/dev/null ||
        fail "Dedicated retained key exposes unexpected model authority"
      state_save "$(jq -n -c --arg m "$MODEL" '{key_model_scope: [$m]}')"
    fi
    (export MAAS_API_KEY="$KEY"; ncli "$SETUP_ROLE" "$WORKSPACE" 30 provider create --name "$PROVIDER" --type "$PROVIDER" --credential MAAS_API_KEY \
      --config owner=rhoai3-coding-demo --config "maas_key_id=$(state '.key_id')") >/dev/null
    unset KEY
    ncli "$SETUP_ROLE" "$WORKSPACE" 30 provider update "$PROVIDER" --credential-expires-at "MAAS_API_KEY=$(iso_epoch_ms "$expiry")" --wait >/dev/null
    provider=$(ncli "$SETUP_ROLE" "$WORKSPACE" 30 provider list -o json | jq -c --arg p "$PROVIDER" '[.providers[] | select(.name == $p)]')
    [[ $(printf '%s' "$provider" | jq length) == 1 ]] || fail "Created provider is ambiguous"
    state_save "$(jq -n -c --arg id "$(printf '%s' "$provider" | jq -r '.[0].id')" --arg h "$(printf '%s' "$provider" | jq -c '.[0]' | provider_digest)" \
      '{provider_id: $id, provider_hash: $h, key_pending: false}')"
  else
    jq -n -e --argjson f "$found" --argjson s "$STATE" '($f | length) == 1 and $s.provider_id == $f[0].id' >/dev/null &&
      [[ $(state '.provider_hash // ""') == $(printf '%s' "$found" | jq -c '.[0]' | provider_digest) ]] ||
      fail "Foreign or changed provider; adoption refused"
  fi
  # Sandbox template: the reviewed image, resources, environment and labels.
  found=$(printf '%s' "$TEMPLATES" | jq -c --arg n "$NAME" '[.[] | select(.name == $n)]')
  if [[ $(printf '%s' "$found" | jq length) == 0 ]]; then
    arguments=(sandbox template create "$NAME" --image "$IMAGE" --cpu "$(printf '%s' "$TEMPLATE" | jq -r '.cpu')"
      --memory "$(printf '%s' "$TEMPLATE" | jq -r '.memory')" -o json)
    while IFS= read -r item; do arguments+=(--env "$item"); done < <(printf '%s' "$TEMPLATE" | jq -r '.env | to_entries[] | "\(.key)=\(.value)"')
    while IFS= read -r item; do arguments+=(--label "$item"); done < <(printf '%s' "$TEMPLATE" | jq -r '.labels | to_entries[] | "\(.key)=\(.value)"')
    template=$(ncli "$SETUP_ROLE" "$WORKSPACE" 30 "${arguments[@]}")
    state_save "$(jq -n -c --arg id "$(printf '%s' "$template" | jq -r '.id')" --arg h "$(printf '%s' "$template" | digest)" '{template_id: $id, template_hash: $h}')"
  else
    jq -n -e --argjson f "$found" --argjson s "$STATE" --argjson t "$TEMPLATE" "$FALSY"'($f | length) == 1 and $f[0] as $x | $s.template_id == $x.id
      and $x.image == $t.image and $x.environment == $t.env and $x.resources == {cpu: $t.cpu, memory: $t.memory} and $x.labels == $t.labels
      and ($x.driver_config | falsy) and ($x.startup | falsy)' >/dev/null &&
      [[ $(printf '%s' "$found" | jq -c '.[0]' | digest) == $(state '.template_hash // ""') ]] ||
      fail "Foreign or changed template; takeover refused"
  fi
  setup_policy_input
  # Sandbox: an existing owned one only needs an unchanged record; a new one is created, then given its files.
  owned=$(printf '%s' "$FLEET" | jq -c --arg n "$NAME" --arg w "$WORKSPACE" '[.sandboxes[]? | select(.name == $n and .workspace == $w)]')
  if [[ $(printf '%s' "$owned" | jq length) != 0 ]]; then
    jq -n -e --argjson o "$owned" --argjson s "$STATE" '($o | length) == 1 and $o[0].id == $s.sandbox_id' >/dev/null ||
      fail "Foreign or pending unknown sandbox; takeover refused"
    if state -e '(.sandbox_pending // false) | not' >/dev/null; then
      current=$(ncli owner "$WORKSPACE" 30 sandbox get "$NAME" -o json)
      jq -n -e --argjson r "$(printf '%s' "$current" | sandbox_record)" --argjson s "$STATE" '$r == $s.sandbox_record' >/dev/null ||
        fail "Existing owned sandbox provenance changed"
      return 0
    fi
  else
    state -e '(.sandbox_id // null) == null' >/dev/null || fail "Existing owned sandbox disappeared; preserving recovery state"
  fi
  upload="$STATE_DIR/upload"
  (umask 077; mkdir -p "$upload/state/auth" "$upload/workspace")
  password="$upload/state/auth/$LISTENER"
  [[ -e "$password" ]] || (umask 077; random_secret >"$password")
  private_path "$password" || fail "Unsafe local listener secret"
  cp "$INPUTS/start.sh" "$upload/state/start.sh"
  chmod 700 "$upload/state/start.sh"
  (umask 077; mkdir -p "$(dirname "$upload/$CONFIG_DESTINATION")"; sed "s/__MAAS_COMMON_HOST__/$HOST/g" "$CONFIG_FILE" >"$upload/$CONFIG_DESTINATION")
  state_save "$(jq -n -c --arg p "$password" '{server_key_path: $p}')"
  if [[ $(printf '%s' "$owned" | jq length) == 0 ]]; then
    state -e '(.sandbox_pending // false) | not' >/dev/null || fail "Unknown create outcome; exact-ID review required, new creation refused"
    state_save '{"sandbox_pending": true}'
    command='for attempt in {1..180}; do if [[ -f /sandbox/state/setup-ready ]]; then exec /bin/bash /sandbox/state/start.sh; fi; sleep 1; done; exit 1'
    created=$(ncli owner "$WORKSPACE" 240 sandbox create --name "$NAME" --template "$NAME" --provider "$PROVIDER" --no-auto-providers \
      --approval-mode manual --detach --restart-policy on-failure --label "demo.rhoai.io/runtime=$NAME" -o json -- /bin/bash -c "$command")
    printf '%s' "$created" | jq -e '(.id // "") != ""' >/dev/null || fail "Creation reply lacks exact native sandbox ID; preserve pending state"
    state_save "$(jq -n -c --arg id "$(printf '%s' "$created" | jq -r '.id')" '{sandbox_id: $id}')"
  fi
  sandbox=$(ncli owner "$WORKSPACE" 30 sandbox get "$NAME" -o json)
  [[ $(printf '%s' "$sandbox" | jq -r '.id') == $(state '.sandbox_id') ]] || fail "Sandbox changed before authenticated upload"
  ncli owner "$WORKSPACE" 90 sandbox upload "$NAME" "$upload/state" /sandbox --no-git-ignore >/dev/null
  ncli owner "$WORKSPACE" 90 sandbox upload "$NAME" "$upload/workspace" /sandbox --no-git-ignore >/dev/null
  ncli owner "$WORKSPACE" 30 sandbox exec --name "$NAME" --no-tty --no-login-shell -- /bin/bash -c "set -euo pipefail; test -f /sandbox/state/start.sh; \
test -f /sandbox/$CONFIG_DESTINATION; test ! -L /sandbox/state/auth/$LISTENER; test -s /sandbox/state/auth/$LISTENER; \
test \"\$(stat -c %a /sandbox/state/auth/$LISTENER)\" = 600; test \"\$(stat -c %u /sandbox/state/auth/$LISTENER)\" = \"\$(id -u)\"; \
umask 077; printf ready > /sandbox/state/.setup-ready; mv /sandbox/state/.setup-ready /sandbox/state/setup-ready" >/dev/null
  sandbox=$(ncli owner "$WORKSPACE" 30 sandbox get "$NAME" -o json)
  state_save "$(jq -n -c --argjson r "$(printf '%s' "$sandbox" | sandbox_record)" '{sandbox_pending: false, sandbox_record: $r}')"
  RECEIPT=$(printf '%s' "$RECEIPT" | jq -c --arg n "$NAME" '.changes += ["persistent-" + $n]')
}
# setup_key_metadata: the owned key is active, unexpired and exactly as minted.
setup_key_metadata() {
  local metadata native_expiry recorded_expiry
  http GET "$API/v1/api-keys/$(state '.key_id // ""')" USER_TOKEN
  metadata=$HTTP_BODY
  [[ "$HTTP_STATUS" == 200 ]] && printf '%s' "$metadata" | jq -e --argjson s "$STATE" --arg n "$NAME-runtime-qwen38" --arg sub "$SUBSCRIPTION" --arg o "$OWNER" \
    '.id == $s.key_id and .name == $n and .username == $o and .subscription == $sub and .ephemeral == false and .status == "active"
     and .tenant == $s.key_tenant' >/dev/null || fail "Owned key metadata/owner/model subscription is not active"
  native_expiry=$(iso_epoch "$(printf '%s' "$metadata" | jq -r '.expirationDate // ""')" 2>/dev/null) || fail "Owned key expiry is unreadable"
  recorded_expiry=$(iso_epoch "$(state '.key_expiry // ""')" 2>/dev/null) || fail "Recorded key expiry is unreadable"
  [[ "$native_expiry" == "$recorded_expiry" ]] || fail "Key expiry differs from native creation metadata"
  jq -n -e --argjson e "$native_expiry" --argjson now "$(date +%s)" '$e > $now' >/dev/null || fail "Owned key expired; explicit reviewed rotation required"
}
# setup_check: read-only; the owned sandbox, the durable policy, the owned provider and key are exactly as recorded.
setup_check() {
  local sandbox policy providers
  sandbox=$(ncli owner "$WORKSPACE" 30 sandbox get "$NAME" -o json)
  jq -n -e --argjson x "$sandbox" --argjson r "$(printf '%s' "$sandbox" | sandbox_record)" --argjson s "$STATE" \
    '$x.id == $s.sandbox_id and $r == $s.sandbox_record' >/dev/null || fail "Owned sandbox identity/provenance/restart policy differs"
  printf '%s' "$sandbox" | jq -e --arg n "$NAME" '.restart_policy == "on-failure" and .policy_source == "global"
    and .created_from_workload_template.name == $n' >/dev/null || fail "Sandbox native template/global-policy contract differs"
  policy=$(ncli admin - 30 policy get --global --full -o json)
  jq -n -e --argjson p "$policy" --argjson i "$INTENDED" '$p.policy == $i' >/dev/null || fail "Durable policy changed"
  providers=$(ncli "$SETUP_ROLE" "$WORKSPACE" 30 provider list -o json)
  printf '%s' "$providers" | jq -e '(.next_page_token // "") == ""' >/dev/null || fail "Provider check inventory incomplete"
  providers=$(printf '%s' "$providers" | jq -c --argjson s "$STATE" --arg p "$PROVIDER" '[.providers[] | select(.id == $s.provider_id and .name == $p)]')
  [[ $(printf '%s' "$providers" | jq length) == 1 ]] && printf '%s' "$providers" | jq -e --arg p "$PROVIDER" '.[0].type == $p' >/dev/null &&
    [[ $(printf '%s' "$providers" | jq -c '.[0]' | provider_digest) == $(state '.provider_hash // ""') ]] ||
    fail "Owned provider type/credentials/config/expiry metadata differs"
  setup_key_metadata
  RECEIPT=$(printf '%s' "$RECEIPT" | jq -c --argjson s "$STATE" --arg id "$(printf '%s' "$sandbox" | jq -r '.id')" \
    '.checks += {native_identity: true, persistent_policy: true, owned_provider: true}
     | . + {sandbox_id: $id, provider_id: $s.provider_id, key_id: $s.key_id, key_expiry: $s.key_expiry, subscription: $s.key_subscription}')
}
