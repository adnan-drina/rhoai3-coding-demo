#!/usr/bin/env bash
# Opt-in, bounded qualification of the Stage 060 agent runtime; never run by deploy.sh or validate.sh. Suites:
#   host       creates one temporary namespace with one restricted CPU Job running the pinned sandbox image's native
#              capability probe, verifies the receipt, then deletes the namespace (UID precondition). Leaves nothing.
#   inference  temporarily lets one OpenCode sandbox of ai-developer (openshell-developer) reach one governed MaaS
#              model: imports a run profile, sets the gateway-global policy, mints a one-hour ephemeral key, creates a
#              provider and sandbox, proves a generated, streamed reply and a cancelled generation, then removes all of
#              it, revokes the key and restores the exact original policy. Needs RHOAI_STAGE060_EXCLUSIVE_QUALIFICATION=
#              true, an empty fleet and the ai-developer sessions (RHOAI_STAGE060_PERSONA_KUBECONFIG, _PERSONA_CLI_HOME).
#              --cleanup finishes an interrupted run from its journal. Makes model calls.
#   opencode   on the existing owned OpenCode sandbox (create.sh): one synthetic coding task with one approved test
#   hermes     command, one application cancellation and a native stop/start; retains key, sandbox, sessions and the
#              fixture; changes no policy, provider, key or template. Makes model calls. hermes --confinement-only runs
#              the no-model negative checks instead.
#   client     the owner-only client check of both agents: authenticated listener access through the native relay,
#              missing and wrong credentials refused, reconnect keeps the retained identity. No model calls.
# --static checks the offline inputs only. Each live suite refuses on the first failed gate, keeps every owned object
# for review and writes an owner-only receipt; credentials never leave memory, pipes and private temporary CLI
# profiles. Rerunnable: each run uses new fixture, session and run names.
# Usage: stages/060-agent-runtime-and-agentops/sandboxes/qualify.sh host [EVIDENCE_DIR]
# Usage: stages/060-agent-runtime-and-agentops/sandboxes/qualify.sh inference --static|--run EVIDENCE_DIR|--cleanup EVIDENCE_DIR
# Usage: stages/060-agent-runtime-and-agentops/sandboxes/qualify.sh opencode|hermes --static
# Usage: stages/060-agent-runtime-and-agentops/sandboxes/qualify.sh opencode|hermes --run --revision SHA [--state-dir DIR] [--persona-home DIR] [--persona-kubeconfig FILE]
# Usage: stages/060-agent-runtime-and-agentops/sandboxes/qualify.sh hermes --confinement-only --revision SHA [--state-dir DIR] [--persona-home DIR] [--persona-kubeconfig FILE]
# Usage: stages/060-agent-runtime-and-agentops/sandboxes/qualify.sh client --check --revision SHA --receipt FILE [--state-root DIR] [--persona-home DIR] [--persona-kubeconfig FILE]
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"
usage() { sed -n 's/^# Usage: //p' "$0" >&2; exit 1; }
SUITE=${1:-}
[[ $# -gt 0 ]] && shift
source "$SCRIPT_DIR/native.sh"
QUALIFICATION="$SCRIPT_DIR/qualification"

# ── Shared helpers ────────────────────────────────────────────────────────────────────────────────────────────────
uuid_hex() { openssl rand -hex "${1:-16}"; }
free_port() { ruby -rsocket -e 's = TCPServer.new("127.0.0.1", 0); puts s.addr[1]; s.close'; }
port_open() { (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null; }
# private_receipt PATH JSON: exclusive owner-only create.
private_receipt() { (set -C; umask 077; printf '%s\n' "$2" | jq . >"$1"); }
# verify_fixture SOURCE: only an exact harmless AST is executed, locally and independently of the agent.
verify_fixture() {
  printf '%s' "$1" | python3 -I -c '
import ast, sys
source = sys.stdin.read()
def refuse(message):
    print(message); sys.exit(1)
if len(source.encode()) > 512: refuse("Fixture exceeds bounded size")
tree = ast.parse(source)
if ast.dump(tree, include_attributes=False) != ast.dump(ast.parse("def add(a, b):\n    return a + b\n"), include_attributes=False):
    refuse("Independent fixture structure differs")
scope = {"__builtins__": {}}
exec(compile(tree, "<synthetic-fixture>", "exec"), scope)
if not all(scope["add"](a, b) == r for a, b, r in ((2, 3, 5), (-2, 2, 0), (0, 0, 0), (7, -3, 4))): refuse("Independent synthetic test failed")
' >"$WORK/fixture.verdict" 2>&1 || fail "$(head -1 "$WORK/fixture.verdict")"
}
# Lock: one qualification per state directory (a stale lock of a dead process is taken over).
lock_take() {
  local lock=$1 holder
  if ! mkdir "$lock" 2>/dev/null; then
    holder=$(cat "$lock/pid" 2>/dev/null || true)
    [[ "$holder" =~ ^[1-9][0-9]*$ ]] && kill -0 "$holder" 2>/dev/null && fail "Another qualification holds $lock"
    rm -rf "$lock"
    mkdir "$lock" || fail "Another qualification holds $lock"
  fi
  echo $$ >"$lock/pid"
  LOCKS+=("$lock")
}
LOCKS=()
locks_release() { local lock; for lock in ${LOCKS[@]+"${LOCKS[@]}"}; do rm -rf "$lock"; done; }

# ── Receipt and gates (opencode, hermes) ──────────────────────────────────────────────────────────────────────────
receipt() { jq -c "$@" "$WORK/receipt.json" >"$WORK/receipt.next" && mv "$WORK/receipt.next" "$WORK/receipt.json"; }
# gate NAME true|false: record, refuse on false, keep the pending list current.
gate() {
  local value=false
  [[ "$2" == true ]] && value=true
  receipt --arg g "$1" --argjson v "$value" --argjson all "$GATES" '.checks[$g] = $v | .pendingGates = [$all[] as $x | select(.checks[$x] != true) | $x]'
  [[ "$value" == true ]] || fail "Gate failed: $1"
}
truth() { if "$@" >/dev/null 2>&1; then echo true; else echo false; fi; }

# ── Relay to the agent listener ───────────────────────────────────────────────────────────────────────────────────
# lrequest METHOD PATH [BODY] [AUTH] [SECONDS]: through the owner's native relay; sets L_STATUS and L_BODY (JSON or
# null). AUTH: default (the private listener secret), none, or wrong:VALUE. Returns 1 on a transport failure.
lrequest() {
  local method=$1 path=$2 body=${3:-} auth=${4:-default} seconds=${5:-20} url separator out credential="" data=()
  [[ "$path" == /* && "$path" != //* ]] || fail "Unreviewed native HTTP path"
  url="http://127.0.0.1:$LOCAL$path"
  if [[ "$NAME" == opencode ]]; then
    separator='?'
    [[ "$path" == *\?* ]] && separator='&'
    url+="${separator}directory=$(jq -rn --arg d "$DIRECTORY" '$d | @uri')"
  fi
  case "$auth" in default) credential=$SECRET ;; wrong:*) credential=${auth#wrong:} ;; esac
  [[ -z "$body" ]] || data=(--data-binary @-)
  out=$(printf '%s' "$body" | curl -s --max-time "$seconds" -X "$method" -H 'Content-Type: application/json' ${data[@]+"${data[@]}"} \
    -w '\n%{http_code}' --config <(listener_auth "$credential") "$url") || { L_STATUS=000; L_BODY=null; return 1; }
  L_STATUS=${out##*$'\n'}
  L_BODY=${out%$'\n'*}
  (( ${#L_BODY} <= 2097152 )) || fail "Bounded native HTTP response exceeded"
  L_BODY=$(printf '%s' "$L_BODY" | jq -c . 2>/dev/null || echo null)
  [[ -n "$L_BODY" ]] || L_BODY=null
}
listener_auth() {
  [[ -n "$1" ]] || return 0
  if [[ "$NAME" == opencode ]]; then printf 'user = "opencode:%s"\n' "$1"; else printf 'header = "Authorization: Bearer %s"\n' "$1"; fi
}
FORWARD_PID=""
close_forward() {
  [[ -n "$FORWARD_PID" ]] || return 0
  kill "$FORWARD_PID" 2>/dev/null || true
  wait "$FORWARD_PID" 2>/dev/null || true
  FORWARD_PID=""
}
# forward: the authenticated native relay to the loopback listener, then authenticated readiness (90 s).
forward() {
  local port=4096 deadline
  [[ "$NAME" == hermes ]] && port=8642
  close_forward
  LOCAL=$(free_port)
  ncli_background owner "$WORKSPACE" forward service "$NAME" --target-port "$port" --target-host 127.0.0.1 --local "127.0.0.1:$LOCAL"
  FORWARD_PID=$BACKGROUND_PID
  deadline=$((SECONDS + 90))
  while (( SECONDS < deadline )); do
    kill -0 "$FORWARD_PID" 2>/dev/null || fail "Authenticated relay closed"
    if lrequest GET "$(health_path)" "" default 3; then
      if [[ "$NAME" == opencode ]]; then
        [[ "$L_STATUS" == 200 ]] && printf '%s' "$L_BODY" | jq -e '.healthy == true and .version == "1.18.16"' >/dev/null && return 0
      else
        [[ "$L_STATUS" == 200 ]] && printf '%s' "$L_BODY" | jq -e 'type == "object" and .status == "ok" and .gateway_state == "running"
          and .platform == "hermes-agent"' >/dev/null && return 0
      fi
    fi
    sleep 0.5
  done
  fail "Authenticated native readiness deadline exceeded"
}
health_path() { if [[ "$NAME" == opencode ]]; then echo /global/health; else echo /health/detailed; fi; }

# ── Owned runtime (read-only setup binding) ───────────────────────────────────────────────────────────────────────
# native: the journal is unchanged and the owned native sandbox keeps its recorded ID.
native() {
  [[ -f "$JOURNAL" ]] && private_path "$JOURNAL" && [[ $(shasum -a 256 "$JOURNAL" | cut -d' ' -f1) == "$JOURNAL_SHA" ]] ||
    fail "Recovery journal changed during qualification"
  NATIVE=$(ncli owner "$WORKSPACE" 30 sandbox get "$NAME" -o json)
  [[ $(printf '%s' "$NATIVE" | jq -r '.id') == $(state '.sandbox_id') ]] || fail "Sandbox identity changed; lifecycle refused"
}
# identity running|stopped: the exact Kubernetes Sandbox, workload and PVCs behind the owned native sandbox.
identity() {
  local out
  native
  out=$(sandbox_identity "$NATIVE" "$NAME" "$WORKSPACE" "$IMAGE" "${1:-running}") || fail "${out#REFUSED: }"
  printf '%s' "$out"
}
# wait_identity running|stopped: as identity, waiting up to 90 s through the transient lifecycle states.
wait_identity() {
  local out deadline=$((SECONDS + 90))
  while true; do
    native
    if out=$(sandbox_identity "$NATIVE" "$NAME" "$WORKSPACE" "$IMAGE" "${1:-running}"); then printf '%s' "$out"; return 0; fi
    case "${out#REFUSED: }" in
      "Owned native sandbox is starting"|"Owned workload is not Running"|"Actual agent image is not ready"|"Stopped sandbox workload remains")
        (( SECONDS < deadline )) || fail "${out#REFUSED: }" ;;
      *) fail "${out#REFUSED: }" ;;
    esac
    sleep 0.5
  done
}
# sandbox_python PROGRAM [INTERPRETER]: a reviewed probe program inside the owned sandbox; prints its last JSON line.
# Hermes probes default to the agent's private interpreter; the shared /usr/bin/python3.11 is passed explicitly only by
# the check that proves it is denied (as in the original qualify-hermes.py).
sandbox_python() {
  local interpreter=${2:-$([[ "$NAME" == hermes ]] && echo "$HERMES_PYTHON" || echo /usr/bin/python3)} out
  [[ "$NAME" == opencode || "$interpreter" == "$HERMES_PYTHON" || "$interpreter" == /usr/bin/python3.11 ]] || fail "Unreviewed probe interpreter"
  native
  if ! out=$(ncli_status owner "$WORKSPACE" 40 sandbox exec --name "$NAME" --timeout 20 --no-tty --no-login-shell -- "$interpreter" -c "$1") ||
    (( ${#out} > 16384 )) || [[ -z "$out" ]]; then
    fail "Bounded native sandbox probe failed"
  fi
  printf '%s' "$out" | tail -1
}
# owned_setup RUNTIME: the setup journal read-only, its listener secret, the setup preflight, sessions and check.
owned_setup() {
  local message
  RUNTIME=$1
  [[ -d "$STATE_DIR" ]] && private_path "$STATE_DIR" || fail "Existing private setup state required"
  JOURNAL="$STATE_DIR/state.json"
  if [[ "$1" == hermes ]]; then message="Private setup journal required"; else message="Private existing recovery journal required"; fi
  [[ -f "$JOURNAL" ]] && private_path "$JOURNAL" || fail "$message"
  JOURNAL_SHA=$(shasum -a 256 "$JOURNAL" | cut -d' ' -f1)
  READONLY_STATE=true
  setup_init
  state -e '[to_entries[] | select((.key | endswith("_pending")) and .value)] | length == 0' >/dev/null || fail "Setup has pending ownership gates"
  local secret="$STATE_DIR/upload/state/auth/$LISTENER"
  [[ -f "$secret" ]] && private_path "$secret" && [[ $(file_owner "$secret") == $(id -u) ]] || fail "Private native listener credential required"
  SECRET=$(tr -d '\n' <"$secret")
  (( ${#SECRET} >= 32 )) || fail "Native listener credential is invalid"
  setup_preflight "$REVISION" "$SCRIPT_DIR/create.sh" "$SCRIPT_DIR/native.sh" "$SCRIPT_DIR/qualify.sh"
  session_open admin
  session_open owner "$PERSONA_HOME"
  setup_inventory
  setup_policy_input
  setup_check
}
# runtime_inputs: the agent holds only the native credential placeholder; its installed start script and config are the
# reviewed inputs; exactly the owned provider is attached.
# rendered_hash FILE: SHA-256 of an agent input as create.sh writes it (host substituted, trailing newline kept; a
# command substitution would drop that newline and never match the installed file).
rendered_hash() { sed "s/__MAAS_COMMON_HOST__/$HOST/g" "$1" | shasum -a 256 | cut -d' ' -f1; }
runtime_inputs() {
  local probe attached effective credential
  if [[ "$NAME" == opencode ]]; then
    probe=$(sandbox_python "import os,hashlib,json;v=os.environ.get('MAAS_API_KEY','');print(json.dumps({'present':bool(v),'placeholder':bool(__import__('re').fullmatch(r'openshell:resolve:env:(?:v[0-9]+_)?MAAS_API_KEY',v)),'hash':hashlib.sha256(v.encode()).hexdigest(),'config':hashlib.sha256(open('/sandbox/workspace/opencode.json','rb').read()).hexdigest(),'startup':hashlib.sha256(open('/sandbox/state/start.sh','rb').read()).hexdigest()}))")
    attached=$(ncli owner "$WORKSPACE" 30 sandbox provider list "$NAME" -o json)
    printf '%s' "$attached" | jq -e --arg p "$PROVIDER" '(.next_page_token // "") == "" and (.providers | length) == 1 and .providers[0].name == $p
      and .providers[0].type == $p and .providers[0].credential_keys == ["MAAS_API_KEY"]' >/dev/null || fail "Exact owned provider attachment differs"
    lrequest GET /config/providers || fail "Listener request transport failed"
    [[ "$L_STATUS" == 200 ]] && printf '%s' "$L_BODY" | jq -e 'type == "object" and (.providers // [] | length) == 1' >/dev/null ||
      fail "Effective agent provider is ambiguous"
    credential=$(printf '%s' "$L_BODY" | jq -r '.providers[0].options.apiKey // ""')
    gate placeholderNotRealKey "$(truth jq -n -e --argjson e "$L_BODY" --argjson p "$probe" --arg m "$MODEL" --arg h "$(sha256_text "$credential")" \
      --arg real "$(state '.key_hash')" '$e.providers[0] as $x | $x.id == "qwen38" and ($x.models // {} | keys) == [$m]
      and ($x.options.apiKey // "" | test("^openshell:resolve:env:(v[0-9]+_)?MAAS_API_KEY$")) and $h == $p.hash
      and $p.present and $p.placeholder and $p.hash != $real')"
    printf '%s' "$probe" | jq -e --arg c "$(rendered_hash "$INPUTS/config.json")" --arg s "$(shasum -a 256 "$INPUTS/start.sh" | cut -d' ' -f1)" \
      '.config == $c and .startup == $s' >/dev/null || fail "Installed startup/config differs from reviewed input"
  else
    setup_check  # the exact owned provider ID and hash remain mandatory
    probe=$(sandbox_python "import os,re,hashlib,json,pathlib;v=os.environ.get('MAAS_API_KEY','');c=pathlib.Path('/sandbox/state/hermes/config.yaml');s=pathlib.Path('/sandbox/state/start.sh');k=pathlib.Path('/sandbox/state/auth/server-key');assert all(p.is_file() and not p.is_symlink() for p in (c,s,k));print(json.dumps({'present':bool(v),'placeholder':bool(re.fullmatch(r'openshell:resolve:env:(?:v[0-9]+_)?MAAS_API_KEY',v)),'credentialHash':hashlib.sha256(v.encode()).hexdigest(),'configHash':hashlib.sha256(c.read_bytes()).hexdigest(),'startupHash':hashlib.sha256(s.read_bytes()).hexdigest(),'listenerHash':hashlib.sha256(k.read_text().strip().encode()).hexdigest(),'listenerPrivate':k.stat().st_mode&0o777==0o600 and k.stat().st_uid==os.getuid(),'privateInterpreter':os.readlink('/proc/self/exe')=='$HERMES_PYTHON'}))")
    attached=$(ncli owner "$WORKSPACE" 30 sandbox provider list "$NAME" -o json)
    # The pinned CLI omits the provider ID from an attachment; setup_check bound the exact ID and metadata.
    printf '%s' "$attached" | jq -e --arg p "$PROVIDER" 'type == "object" and (.next_page_token // "") == "" and (.providers | type) == "array"
      and (.providers | length) == 1 and (.providers[0] | type) == "object" and (.providers[0] | keys) == ["config_keys", "credential_keys", "name", "type"]
      and .providers[0].name == $p and .providers[0].type == $p and .providers[0].credential_keys == ["MAAS_API_KEY"]
      and (.providers[0].config_keys | type) == "array" and all(.providers[0].config_keys[]; type == "string")
      and (.providers[0].config_keys | sort) == ["maas_key_id", "owner"]' >/dev/null || fail "Exact owned provider attachment differs"
    gate runtimeInputs "$(truth jq -n -e --argjson p "$probe" --arg c "$(rendered_hash "$INPUTS/config.yaml")" --arg s "$(shasum -a 256 "$INPUTS/start.sh" | cut -d' ' -f1)" \
      --arg l "$(sha256_text "$SECRET")" --arg real "$(state '.key_hash')" '$p | type == "object" and .placeholder == true and .present == true
      and .credentialHash != $real and (.credentialHash | type) == "string" and (.credentialHash | test("^[0-9a-f]{64}$"))
      and .configHash == $c and .startupHash == $s and .listenerHash == $l and .listenerPrivate == true and .privateInterpreter == true')"
  fi
}

# ── OpenCode protocol ─────────────────────────────────────────────────────────────────────────────────────────────
OC_TEST_COMMAND='python3 -c "from qualification_add import add; assert add(2, 3) == 5; assert add(-2, 2) == 0"'
OC_GATES='["ownedRuntime","authenticatedHealth","invalidPasswordDenied","missingPasswordDenied","placeholderNotRealKey","codingTool",
  "exactTestApproval","generatedModel","streamedDeltas","independentTest","applicationAbort","filesystemDenied","egressDenied",
  "foreignWorkspaceDenied","persistentRestart","runningAtEnd"]'
# stream_start NAME PATH: an authenticated SSE reader in the background appending raw lines to NAME.sse; its exit
# status lands in NAME.rc and its headers in NAME.headers. stream_stop NAME ends it. An event's position is its time.
stream_start() {
  local name=$1 path=$2
  : >"$WORK/$name.sse"
  rm -f "$WORK/$name.rc" "$WORK/$name.pid"
  (
    curl -s -N -D "$WORK/$name.headers" --config <(listener_auth "$SECRET") "http://127.0.0.1:$LOCAL$path" >"$WORK/$name.sse" 2>/dev/null &
    reader=$!
    echo "$reader" >"$WORK/$name.pid"
    echo "$reader" >>"$WORK/pids"
    rc=0
    wait "$reader" || rc=$?
    echo "$rc" >"$WORK/$name.rc"
  ) &
  until [[ -s "$WORK/$name.pid" ]]; do sleep 0.05; done
}
stream_stop() {
  local pid
  pid=$(cat "$WORK/$1.pid" 2>/dev/null || true)
  if [[ "$pid" =~ ^[1-9][0-9]*$ ]]; then kill "$pid" 2>/dev/null || true; fi
}
stream_done() { [[ -f "$WORK/$1.rc" ]]; }
EVENTS_STOPPED=false
events_start() { stream_start events "/event?directory=$(jq -rn --arg d "$DIRECTORY" '$d | @uri')"; }
events_stop() {
  EVENTS_STOPPED=true
  stream_stop events
}
# events: [{type, sid, p}] in arrival order.
events() {
  jq -R -n -c '[inputs | select(startswith("data:")) | .[5:] | (try fromjson catch empty) | (.properties // {}) as $p
    | {type: (.type // ""), sid: ($p.sessionID // $p.part.sessionID // $p.info.sessionID), p: $p}]' <"$WORK/events.sse"
}
mark() { events | jq length; }
# event_error: the stream ended with an error while not stopped, or exceeded its bound.
event_error() {
  if (( $(wc -c <"$WORK/events.sse") > 2097152 )); then echo true; return; fi
  if [[ "$EVENTS_STOPPED" == false ]] && stream_done events && [[ $(cat "$WORK/events.rc") != 0 ]]; then echo true; return; fi
  echo false
}
OC_JQ='def deltas($s; $start; $end): . as $ev
  | [$ev[] | select(.sid == $s and .type == "message.updated" and .p.info.role == "assistant") | .p.info.id] as $a
  | [$ev[] | select(.sid == $s and .type == "message.part.updated" and .p.part.type == "text" and (.p.part.messageID | IN($a[]))) | .p.part.id] as $parts
  | [range(0; $ev | length) as $i | $ev[$i] | select($i >= $start and $i <= $end and .sid == $s and .type == "message.part.delta"
      and .p.field == "text" and (.p.delta | . != null and . != false and . != "") and (.p.messageID | IN($a[])) and (.p.partID | IN($parts[]))) | $i];
  def idle_after($s; $start): . as $ev | [range($start; $ev | length) as $i | $ev[$i] | select(.sid == $s and (.type == "session.idle"
      or (.type == "session.status" and .p.status.type == "idle")))] | length > 0;'
deltas_count() { events | jq --arg s "$1" --argjson a "${2:-0}" "$OC_JQ"'deltas($s; $a; 1e18) | length'; }
SESSIONS=()
oc_session() {
  lrequest POST /session '{}' || fail "Listener request transport failed"
  NEW_SESSION=$(printf '%s' "$L_BODY" | jq -r '.id // empty')
  [[ "$L_STATUS" == 200 && -n "$NEW_SESSION" ]] || fail "Synthetic session creation failed"
  SESSIONS+=("$NEW_SESSION")
}
oc_messages() {
  lrequest GET "/session/$1/message?limit=30" || fail "Listener request transport failed"
  [[ "$L_STATUS" == 200 ]] && printf '%s' "$L_BODY" | jq -e 'type == "array"' >/dev/null || fail "Owned session evidence unavailable"
  printf '%s' "$L_BODY"
}
# oc_prompt_start SESSION TEXT tools|notools: the prompt runs in the background; its reply lands in prompt-SESSION.
oc_prompt_start() {
  local body
  body=$(jq -n -c --arg m "$MODEL" --arg t "$2" --arg tools "$3" '{model: {providerID: "qwen38", modelID: $m}, parts: [{type: "text", text: $t}]}
    + if $tools == "notools" then {tools: (["bash", "edit", "write", "apply_patch", "read", "glob", "grep", "list", "task", "webfetch",
      "websearch", "skill", "question", "todowrite"] | map({(.): false}) | add)} else {} end')
  rm -f "$WORK/prompt-$1"
  (if lrequest POST "/session/$1/message" "$body" default 120; then printf '%s\n%s' "$L_STATUS" "$L_BODY"; else printf 'transport\nnull'; fi \
    >"$WORK/prompt-$1") &
  PROMPT_PID=$!
}
# prompt_outcome SESSION: {status, reply} or {transport}.
prompt_outcome() {
  if [[ -f "$WORK/prompt-$1" ]] && [[ $(head -1 "$WORK/prompt-$1") != transport ]]; then
    jq -n -c --argjson s "$(head -1 "$WORK/prompt-$1")" --argjson r "$(tail -n +2 "$WORK/prompt-$1")" '{status: $s, reply: $r}'
  else
    echo '{"transport": "error"}'
  fi
}
alive() { kill -0 "$1" 2>/dev/null; }
join_pid() {
  local deadline=$((SECONDS + $2))
  while alive "$1" && (( SECONDS < deadline )); do sleep 0.2; done
  ! alive "$1"
}
yes_no() { if "$@"; then echo true; else echo false; fi; }

oc_coding() {
  local approved=0 deadline permissions request messages allowed outcome
  oc_session
  CODING_SESSION=$NEW_SESSION
  oc_prompt_start "$CODING_SESSION" "Synthetic qualification only. Fix qualification_add.py so add returns the sum using an actual edit, write or apply_patch tool. Then run exactly this bash command once: $OC_TEST_COMMAND. Do not run other commands or modify other files. Finish with two short sentences explaining the fix." tools
  deadline=$((SECONDS + 120))
  while alive "$PROMPT_PID" && (( SECONDS < deadline )); do
    lrequest GET /permission || fail "Listener request transport failed"
    [[ "$L_STATUS" == 200 ]] && printf '%s' "$L_BODY" | jq -e 'type == "array"' >/dev/null || fail "Native permission inventory unavailable"
    permissions=$L_BODY
    while IFS= read -r request; do
      [[ -n "$request" ]] || continue
      allowed=false
      if (( approved == 0 )); then
        messages=$(oc_messages "$CODING_SESSION")
        allowed=$(truth jq -n -e --argjson r "$request" --argjson m "$messages" --arg s "$CODING_SESSION" --arg c "$OC_TEST_COMMAND" \
          '$r.sessionID == $s and $r.permission == "bash" and $r.metadata.command == $c and ($r.tool // {}) as $t
           | any($m[] | .parts[]?; .type == "tool" and .tool == "bash" and .messageID == $t.messageID and .callID == $t.callID
             and .state.input.command == $c)')
      fi
      lrequest POST "/permission/$(printf '%s' "$request" | jq -r '.id')/reply" \
        "$(jq -n -c --arg a "$allowed" '{reply: (if $a == "true" then "once" else "reject" end)}')" || fail "Listener request transport failed"
      [[ "$L_STATUS" == 200 && "$L_BODY" == true ]] || fail "One-time native permission reply failed"
      [[ "$allowed" == true ]] || fail "Unreviewed tool permission requested; rejected"
      approved=$((approved + 1))
    done < <(printf '%s' "$permissions" | jq -c --arg s "$CODING_SESSION" '.[] | select(.sessionID == $s)')
    sleep 0.2
  done
  outcome=$(prompt_outcome "$CODING_SESSION")
  ! alive "$PROMPT_PID" && printf '%s' "$outcome" | jq -e '.status == 200 and (.transport | not)' >/dev/null || fail "Coding task deadline/transport failed"
  oc_verify_coding "$(yes_no test "$approved" -eq 1)"
}
oc_verify_coding() {
  local messages source
  messages=$(oc_messages "$CODING_SESSION")
  gate codingTool "$(truth jq -n -e --argjson m "$messages" 'any($m[] | .parts[]?; .type == "tool" and (.tool | IN("edit", "write", "apply_patch"))
    and .state.status == "completed")')"
  gate exactTestApproval "$(truth jq -n -e --argjson m "$messages" --arg once "$1" --arg c "$OC_TEST_COMMAND" '$once == "true" and any($m[] | .parts[]?;
    .tool == "bash" and .state.status == "completed" and .state.input.command == $c and .state.metadata.exit == 0)')"
  gate generatedModel "$(truth jq -n -e --argjson m "$messages" --arg model "$MODEL" "$FALSY"'[$m[] | .info // {} | select(.role == "assistant")] as $a
    | ($a | length) > 0 and ($a | length) <= 4 and all($a[]; .providerID == "qwen38" and .modelID == $model and (.error | falsy)
      and (.tokens.output | type) == "number" and .tokens.output >= 0 and .tokens.output <= 1024) and any($a[]; .tokens.output > 0)')"
  gate streamedDeltas "$(yes_no test "$(deltas_count "$CODING_SESSION")" -ge 2 -a "$(event_error)" == false)"
  source=$(sandbox_python "import pathlib,json; p=pathlib.Path('$DIRECTORY/qualification_add.py'); assert p.is_file() and not p.is_symlink() and p.stat().st_size<=512; print(json.dumps(p.read_text()))" |
    jq -r .)
  verify_fixture "$source"
  FIXTURE_SHA=$(sha256_text "$source")
  receipt --arg h "$FIXTURE_SHA" '.fixtureSha256 = $h'
  gate independentTest true
}
oc_abort() {
  local session deadline generating=false text=false aborted_at status aborted status_http statuses settled fresh late=false outcome normalized returned
  oc_session
  session=$NEW_SESSION
  oc_prompt_start "$session" "Explain a Java null check in a short paragraph. Do not use tools." notools
  deadline=$((SECONDS + 30))
  while alive "$PROMPT_PID" && (( $(deltas_count "$session") == 0 )) && (( SECONDS < deadline )); do sleep 0.1; done
  lrequest GET /session/status || fail "Listener request transport failed"
  if alive "$PROMPT_PID" && [[ "$L_STATUS" == 200 ]] && printf '%s' "$L_BODY" | jq -e --arg s "$session" '.[$s].type == "busy"' >/dev/null; then
    generating=true
  fi
  (( $(deltas_count "$session") == 0 )) || text=true
  [[ "$generating" == true && "$text" == true ]] || fail "No active streamed application generation to abort"
  aborted_at=$(mark)
  lrequest POST "/session/$session/abort" || fail "Listener request transport failed"
  status=$L_STATUS aborted=$L_BODY
  join_pid "$PROMPT_PID" 45 || true
  lrequest GET /session/status || fail "Listener request transport failed"
  status_http=$L_STATUS statuses=$L_BODY
  settled=$(mark)
  sleep 1
  fresh=$(events | jq --arg s "$session" --argjson a "$aborted_at" "$OC_JQ"'idle_after($s; $a)')
  (( $(deltas_count "$session" "$settled") == 0 )) || late=true
  outcome=$(prompt_outcome "$session")
  returned=$(yes_no join_pid "$PROMPT_PID" 0)
  receipt --argjson g "$generating" --argjson t "$text" --arg ah "$status" --argjson ab "$aborted" --argjson o "$outcome" --arg sh "$status_http" \
    --argjson st "$statuses" --arg s "$session" --argjson fi "$fresh" --argjson late "$late" --argjson eh "$(yes_no test "$(event_error)" == false)" \
    --argjson returned "$returned" '.abortEvidence = {busyBeforeAbort: $g, assistantTextBeforeAbort: $t, abortHttp: ($ah | tonumber),
      abortAccepted: ($ab == true), promptReturned: $returned, promptHttp: $o.status,
      messageAbortedError: ((($o.reply // {}).info.error // {}).name == "MessageAbortedError"), statusHttp: ($sh | tonumber),
      statusMapContainsSession: (($st | type) == "object" and ($st | has($s))), freshIdleEvent: $fi, lateText: $late, eventTransportHealthy: $eh}'
  # Pinned 1.18.16 emits idle, then removes idle sessions from the status map; absence counts only with a fresh idle event.
  normalized=$(jq -n -c --argjson st "$statuses" --arg sh "$status_http" --arg s "$session" --argjson fi "$fresh" \
    'if $sh == "200" and ($st | type) == "object" and ($st | has($s) | not) and $fi then $st + {($s): {type: "idle"}} else $st end')
  gate applicationAbort "$(truth jq -n -e --argjson fi "$fresh" --argjson g "$generating" --argjson t "$text" --arg ah "$status" --argjson ab "$aborted" \
    --argjson o "$outcome" --arg sh "$status_http" --argjson st "$normalized" --arg s "$session" --argjson late "$late" --argjson returned "$returned" \
    --argjson ee "$(event_error)" '$fi and $returned and $g and $t and $ah == "200" and $ab == true and $o.status == 200 and ($o.transport | not)
     and ((($o.reply // {}).info.error // {}).name == "MessageAbortedError") and $sh == "200" and ($st | type) == "object"
     and $st[$s].type == "idle" and ($late | not) and ($ee | not)')"
}
oc_confinement() {
  local denied rc=0
  runtime_inputs
  denied=$(sandbox_python "import json,os,socket
r={}
for name,path,flags in [('read','/root/.opencode-qualification',os.O_RDONLY),('write','/etc/.opencode-qualification',os.O_WRONLY|os.O_CREAT|os.O_EXCL)]:
 try:
  fd=os.open(path,flags,0o600);os.close(fd);r[name]=False
 except OSError as e:r[name]=e.errno in (1,13)
for name,host,port in [('internet','1.1.1.1',443),('metadata','169.254.169.254',80),('wrongBinary','$HOST',443)]:
 s=socket.socket();s.settimeout(5)
 try:s.connect((host,port));r[name]=False
 except OSError as e:r[name]=e.errno in (1,13)
 finally:s.close()
print(json.dumps(r))")
  gate filesystemDenied "$(truth jq -n -e --argjson d "$denied" '$d.read == true and $d.write == true')"
  gate egressDenied "$(truth jq -n -e --argjson d "$denied" '$d.internet == true and $d.metadata == true and $d.wrongBinary == true')"
  # The pinned CLI renders the native PermissionDenied for a non-member workspace.
  ncli_status owner openshell-developer 30 sandbox list -o json >/dev/null || rc=$?
  gate foreignWorkspaceDenied "$(yes_no foreign_denied "$rc")"
}
foreign_denied() {
  (( $1 != 0 )) && grep -qi 'does not have permission' "$WORK/ncli.stderr" &&
    grep -Eq "not a member of workspace ['\"]?openshell-developer['\"]?([;[:space:]]|\$)" "$WORK/ncli.stderr"
}
oc_restart() {
  local baseline history marker persisted
  events_stop
  baseline=$(identity running)
  history=$(oc_messages "$CODING_SESSION" | digest)
  marker=$(uuid_hex 16)
  sandbox_python "import pathlib,json;p=pathlib.Path('$MARKER');assert not p.exists();p.write_text('$marker');print(json.dumps(True))" >/dev/null
  native
  close_forward
  STOPPED=true
  ncli owner "$WORKSPACE" 120 sandbox stop "$NAME" >/dev/null
  [[ $(wait_identity stopped) == "$baseline" ]] || fail "Stopped native/PVC identity changed"
  native
  ncli owner "$WORKSPACE" 180 sandbox start "$NAME" >/dev/null
  wait_identity running >/dev/null
  forward
  STOPPED=false
  persisted=$(sandbox_python "import pathlib,hashlib,json;p=pathlib.Path('$MARKER');f=pathlib.Path('$DIRECTORY/qualification_add.py');assert not p.is_symlink() and not f.is_symlink();print(json.dumps({'marker':p.read_text(),'fixture':hashlib.sha256(f.read_bytes()).hexdigest()}))")
  gate persistentRestart "$(truth jq -n -e --argjson p "$persisted" --arg m "$marker" --arg f "$FIXTURE_SHA" --arg i "$(identity running)" --arg b "$baseline" \
    --arg h "$(oc_messages "$CODING_SESSION" | digest)" --arg h0 "$history" '$i == $b and $p == {marker: $m, fixture: $f} and $h == $h0')"
}
run_opencode() {
  local deadline
  owned_setup opencode
  receipt --arg h "$JOURNAL_SHA" '.recoveryJournalSha256 = $h'
  native
  printf '%s' "$NATIVE" | jq -e --arg n "$NAME" --argjson i "$INTENDED" '.name == $n and .policy == $i' >/dev/null ||
    fail "Owned logical runtime or effective policy differs"
  wait_identity running >/dev/null
  gate ownedRuntime true
  sandbox_python "import pathlib,json; d=pathlib.Path('$DIRECTORY'); d.mkdir(mode=0o700); p=d/'qualification_add.py'; p.write_text('def add(a, b):\\n    return a - b\\n'); print(json.dumps(True))" >/dev/null
  forward
  gate authenticatedHealth true
  lrequest GET /global/health "" wrong:synthetic-invalid-password || true
  gate invalidPasswordDenied "$(yes_no test "$L_STATUS" == 401)"
  lrequest GET /global/health "" none || true
  gate missingPasswordDenied "$(yes_no test "$L_STATUS" == 401)"
  oc_confinement
  events_start
  deadline=$((SECONDS + 10))
  while (( $(mark) == 0 )) && [[ $(event_error) == false ]] && (( SECONDS < deadline )); do sleep 0.1; done
  (( $(mark) > 0 )) && [[ $(event_error) == false ]] || fail "Authenticated SSE transport unavailable"
  oc_coding
  oc_abort
  oc_restart
  setup_check
  identity running >/dev/null
  forward
  runtime_inputs
  gate runningAtEnd true
  receipt '.passed = (.pendingGates == [])'
}
opencode_finally() {
  local session
  events_stop
  if [[ -n "$FORWARD_PID" ]]; then
    for session in ${SESSIONS[@]+"${SESSIONS[@]}"}; do lrequest POST "/session/$session/abort" "" default 5 >/dev/null 2>&1 || true; done
  fi
  if [[ "${STOPPED:-false}" == true ]]; then
    if (native && ncli owner "$WORKSPACE" 180 sandbox start "$NAME" >/dev/null && forward && identity running >/dev/null) 2>/dev/null; then
      receipt '.checks.runningAtEnd = true'
    else
      receipt '.checks.runningAtEnd = false'
    fi
  fi
  close_forward
}

# ── Hermes protocol ───────────────────────────────────────────────────────────────────────────────────────────────
HERMES_PYTHON=/opt/hermes-venv/bin/python3.11
HERMES_PROVIDER=qwen38
HERMES_GATES='["ownedRuntime","runtimeInputs","authenticatedReady","missingKeyDenied","wrongKeyDenied","codingTool","fixedTest",
  "canonicalModel","streamedText","independentTest","applicationCancelled","persistentHistory","runningAtEnd"]'
HERMES_CONFINEMENT_GATES='["ownedRuntime","runtimeInputs","authenticatedReady","filesystemDenied","internetDenied","metadataDenied",
  "sharedInterpreterDenied","wrongMethodDenied","wrongPathDenied","runningAtEnd"]'
ACTIVE_RUNS=()
rejected_key() { [[ "$L_STATUS" == 401 ]] && printf '%s' "$L_BODY" | jq -e '(.error | type) == "object" and .error.code == "gateway_auth_failed"' >/dev/null; }
# run_status RUN SESSION: the exact native run (from L_STATUS/L_BODY); prints its status.
run_status() {
  [[ "$L_STATUS" == 200 ]] && printf '%s' "$L_BODY" | jq -e --arg r "$1" --arg s "$2" 'type == "object" and .object == "hermes.run" and .run_id == $r
    and .session_id == $s' >/dev/null || fail "Exact native run identity/status unavailable"
  printf '%s' "$L_BODY" | jq -r '.status // ""'
}
# run_events RUN: the run's events [{...}] in arrival order. run_errors RUN: the stream was refused, foreign or broken.
run_events() { jq -R -n -c '[inputs | select(startswith("data:")) | .[5:] | (try fromjson catch empty)]' <"$WORK/run-$1.sse"; }
run_errors() {
  local status
  status=$(sed -n '1s/^HTTP\/[0-9.]* \([0-9]*\).*/\1/p' "$WORK/run-$1.headers" 2>/dev/null)
  if [[ -s "$WORK/run-$1.headers" && "$status" != 200 ]] || { [[ -s "$WORK/run-$1.headers" ]] &&
      ! grep -qi '^content-type: *text/event-stream' "$WORK/run-$1.headers"; }; then echo true; return; fi
  if run_events "$1" | jq -e --arg r "$1" 'any(.[]; .run_id != $r)' >/dev/null; then echo true; return; fi
  if (( $(wc -c <"$WORK/run-$1.sse") > 2097152 )); then echo true; return; fi
  if stream_done "run-$1" && [[ $(cat "$WORK/run-$1.rc") != 0 ]]; then echo true; return; fi
  echo false
}
run_mark() { run_events "$1" | jq length; }
hermes_session() {
  local id
  id="hermes_qualification_$(uuid_hex 16)"
  lrequest POST /api/sessions "$(jq -n -c --arg i "$id" --arg m "$MODEL" --arg p "$HERMES_PROVIDER" '{id: $i, model: $m, provider: $p}')" ||
    fail "Listener request transport failed"
  [[ "$L_STATUS" == 201 ]] && printf '%s' "$L_BODY" | jq -e --arg i "$id" 'type == "object" and .object == "hermes.session" and .session.id == $i' >/dev/null ||
    fail "Exact native session creation failed"
  NEW_SESSION=$id
}
hermes_messages() {
  lrequest GET "/api/sessions/$1/messages?limit=30&order=oldest" || fail "Listener request transport failed"
  [[ "$L_STATUS" == 200 ]] && printf '%s' "$L_BODY" | jq -e --arg s "$1" 'type == "object" and .session_id == $s and (.data | type) == "array"
    and .pagination.returned == (.data | length) and (.data | length) < 30' >/dev/null || fail "Exact bounded stored session history unavailable"
  printf '%s' "$L_BODY" | jq -c '.data'
}
# hermes_start SESSION PROMPT: a new native run with its event reader; sets RUN.
hermes_start() {
  native
  runtime_inputs
  lrequest POST /v1/runs "$(jq -n -c --arg i "$2" --arg s "$1" --arg m "$MODEL" --arg p "$HERMES_PROVIDER" '{input: $i, session_id: $s, model: $m, provider: $p}')" ||
    fail "Listener request transport failed"
  [[ "$L_STATUS" == 202 ]] && printf '%s' "$L_BODY" | jq -e 'type == "object" and .status == "started" and (.run_id | type) == "string"
    and (.run_id | test("^run_[0-9a-f]{32}$"))' >/dev/null || fail "Native run creation response differs"
  RUN=$(printf '%s' "$L_BODY" | jq -r '.run_id')
  ACTIVE_RUNS+=("$RUN")
  stream_start "run-$RUN" "/v1/runs/$RUN/events"
}
HERMES_JQ='def terminal_test($cmd): . as $msgs
  | (reduce ($msgs[] | select(.role == "assistant") | (.tool_calls // [])[]) as $c ({}; . + {(($c.id // "null") | tostring): $c})) as $calls
  | if ([$calls[] | select(.function.name == "terminal")] | length) != 1 then false
    else [$msgs[] | select(.role == "tool") | ($calls[(.tool_call_id // "null") | tostring] // {}) as $call | select($call.function.name == "terminal")
          | {a: (try ($call.function.arguments // "{}" | fromjson) catch "invalid"), r: (try (.content // "{}" | fromjson) catch "invalid")}
          | select(.a != "invalid" and .r != "invalid")] as $pairs
    | if any($pairs[]; (.a | type) != "object" or (.r | type) != "object" or .a.command != $cmd) then false
      else ($pairs | length) == 1 and ($pairs[0].r.exit_code | type) == "number" and $pairs[0].r.exit_code == 0
        and ($pairs[0].r | has("error")) and $pairs[0].r.error == null end end;
  def permission_denied: type == "object" and (.errno | type) == "number" and (.errno == 1 or .errno == 13);
  def inspected_denial($method; $path; $host; $policy; $python):
    type == "object" and .status == 403 and .policyHeader == $policy and (.body | type) == "object"
    and .body.error == "policy_denied" and .body.policy == $policy and .body.layer == "l7" and .body.protocol == "rest"
    and .body.method == $method and .body.path == $path and .body.host == $host and .body.port == 443 and .body.binary == $python
    and .body.rule_missing == {type: "rest_allow", layer: "l7", method: $method, path: $path, host: $host, port: 443, binary: $python};'
hermes_seed_fixture() {
  sandbox_python "import pathlib,json;d=pathlib.Path('$DIRECTORY');d.mkdir(mode=0o700);(d/'qualification_add.py').write_text('def add(a,b):\\n return a-b\\n');print(json.dumps(True))" >/dev/null
}
hermes_verify_fixture() {
  local source
  source=$(sandbox_python "import pathlib,json;p=pathlib.Path('$FIXTURE');assert p.is_file() and not p.is_symlink() and p.stat().st_size<=512;print(json.dumps(p.read_text()))" |
    jq -r .)
  verify_fixture "$source"
  sha256_text "$source"
}
hermes_coding() {
  local approvals=0 handled=" " deadline phase="" final event index allowed stored events
  hermes_session
  CODING_SESSION=$NEW_SESSION
  receipt --arg s "$CODING_SESSION" '.codingSession = $s'
  hermes_start "$CODING_SESSION" "Synthetic qualification only. Use write_file or patch mode=replace with absolute path to fix $FIXTURE so add(a,b) returns their sum. Modify no other files. Run exactly this terminal command once: $HERMES_COMMAND. Do not run other commands or use background processes. End with two short sentences explaining the fix."
  receipt --arg r "$RUN" '.codingRun = $r'
  deadline=$((SECONDS + 120))
  while (( SECONDS < deadline )); do
    while IFS=$'\t' read -r index event; do
      [[ -n "$index" && "$handled" != *" $index "* ]] || continue
      allowed=$(truth jq -n -e --argjson e "$event" --argjson a "$approvals" --arg c "$HERMES_COMMAND" '$a == 0 and $e.command == $c and ($e.choices // [] | index("once")) != null')
      lrequest POST "/v1/runs/$RUN/approval" "$(jq -n -c --arg a "$allowed" '{choice: (if $a == "true" then "once" else "deny" end)}')" ||
        fail "Listener request transport failed"
      [[ "$allowed" == true && "$L_STATUS" == 200 ]] && printf '%s' "$L_BODY" | jq -e --arg r "$RUN" '.run_id == $r and .choice == "once" and .resolved == 1' >/dev/null ||
        fail "Unexpected or ambiguous command approval; retained state"
      approvals=$((approvals + 1))
      handled+="$index "
    done < <(run_events "$RUN" | jq -r 'to_entries[] | select(.value.event == "approval.request") | "\(.key)\t\(.value | tojson)"')
    lrequest GET "/v1/runs/$RUN" || fail "Listener request transport failed"
    final=$L_BODY
    phase=$(run_status "$RUN" "$CODING_SESSION")
    case "$phase" in completed|failed|cancelled) break ;; queued|running|waiting_for_approval) ;; *) fail "Unexpected coding run state" ;; esac
    sleep 0.2
  done
  join_stream "run-$RUN" 5
  receipt --argjson a "$(yes_no test "$approvals" -gt 0)" '.approvalRequested = $a'
  [[ "$phase" == completed && $(run_errors "$RUN") == false ]] && stream_done "run-$RUN" ||
    fail "Coding task did not complete within bounded native contract"
  events=$(run_events "$RUN")
  printf '%s' "$events" | jq -e 'any(.[]; .event == "run.completed")' >/dev/null || fail "Successful terminal SSE event missing"
  stored=$(hermes_messages "$CODING_SESSION")
  gate codingTool "$(truth jq -n -e --argjson m "$stored" --argjson e "$events" --arg f "$FIXTURE" '
    [$m[] | select(.role == "assistant") | (.tool_calls // [])[] | select(.function.name | IN("write_file", "patch"))] as $w
    | [$w[] | (try (.function.arguments // "{}" | fromjson | .path) catch "invalid")] as $paths
    | ($w | length) > 0 and ($paths | index("invalid")) == null and ($paths | length) == ($w | length) and all($paths[]; . == $f)
    and any($e[]; .event == "tool.completed" and (.tool | IN("write_file", "patch")) and .error == false)')"
  gate streamedText "$(truth jq -n -e --argjson e "$events" '[$e[] | select(.event == "message.delta" and (.delta | . != null and . != false and . != ""))] | length >= 2')"
  gate fixedTest "$(truth jq -n -e --argjson m "$stored" --arg c "$HERMES_COMMAND" "$HERMES_JQ"'$m | terminal_test($c)')"
  lrequest GET "/api/sessions/$CODING_SESSION" || fail "Listener request transport failed"
  gate canonicalModel "$(truth jq -n -e --arg st "$L_STATUS" --argjson s "$L_BODY" --argjson f "$final" --arg id "$CODING_SESSION" --arg m "$MODEL" \
    '$st == "200" and $s.session.id == $id and $s.session.model == $m and ($f.usage.output_tokens | type) == "number" and $f.usage.output_tokens > 0')"
  FIXTURE_SHA=$(hermes_verify_fixture)
  receipt --arg h "$FIXTURE_SHA" '.fixtureSha256 = $h'
  gate independentTest true
}
join_stream() {
  local deadline=$((SECONDS + $2))
  until stream_done "$1" || (( SECONDS >= deadline )); do sleep 0.2; done
}
hermes_cancel() {
  local session run deadline active=false text=false status stop_code reply final phase="" requested settled late tools events
  hermes_session
  session=$NEW_SESSION
  hermes_start "$session" "Explain Java null checks in three short paragraphs. Do not use tools."
  run=$RUN
  receipt --arg s "$session" --arg r "$run" '.cancellationSession = $s | .cancellationRun = $r'
  deadline=$((SECONDS + 30))
  while (( SECONDS < deadline )); do
    lrequest GET "/v1/runs/$run" || fail "Listener request transport failed"
    status=$L_BODY
    active=$(yes_no test "$(run_status "$run" "$session")" == running)
    text=$(truth jq -e 'any(.[]; .event == "message.delta" and (.delta | . != null and . != false and . != ""))' < <(run_events "$run"))
    [[ "$active" == true && "$text" == true ]] && break
    printf '%s' "$status" | jq -e '.status | IN("completed", "failed", "cancelled") | not' >/dev/null || fail "No active native generation to cancel"
    sleep 0.1
  done
  [[ "$active" == true && "$text" == true && $(run_errors "$run") == false ]] || fail "Active streaming cancellation precondition missing"
  requested=$(run_mark "$run")
  lrequest POST "/v1/runs/$run/stop" || fail "Listener request transport failed"
  stop_code=$L_STATUS reply=$L_BODY
  deadline=$((SECONDS + 45))
  while (( SECONDS < deadline )); do
    lrequest GET "/v1/runs/$run" || fail "Listener request transport failed"
    final=$L_BODY final_code=$L_STATUS
    phase=$(run_status "$run" "$session")
    case "$phase" in cancelled|completed|failed) break ;; running|stopping) ;; *) fail "Unexpected native stop state" ;; esac
    sleep 0.1
  done
  join_stream "run-$run" 5
  settled=$(run_mark "$run")
  sleep 1
  events=$(run_events "$run")
  late=$(truth jq -n -e --argjson e "$events" --argjson s "$settled" '[range($s; $e | length) as $i | $e[$i] | select(.event == "message.delta" and (.delta | . != null and . != false and . != ""))] | length > 0')
  tools=$(truth jq -n -e --argjson e "$events" 'any($e[]; .event == "tool.started")')
  receipt --argjson a "$active" --argjson t "$text" --arg c "$stop_code" --arg p "$phase" --argjson l "$late" --argjson u "$tools" \
    '.cancellation = {activeBeforeStop: $a, textBeforeStop: $t, stopHttp: ($c | tonumber), terminalStatus: $p, lateText: $l, unexpectedTools: $u}'
  gate applicationCancelled "$(truth jq -n -e --argjson a "$active" --argjson t "$text" --arg c "$stop_code" --argjson reply "$reply" --arg fc "$final_code" \
    --argjson f "$final" --arg r "$run" --arg s "$session" --argjson e "$events" --argjson q "$requested" --argjson l "$late" --argjson u "$tools" \
    --argjson err "$(run_errors "$run")" --argjson done "$(yes_no stream_done "run-$run")" '
    ([range($q; $e | length) as $i | $e[$i] | select(.run_id == $r and .event == "run.cancelled")] | length > 0) as $terminal
    | $a and $t and $c == "200" and $reply == {run_id: $r, status: "stopping"} and $fc == "200" and ($f | type) == "object"
      and $f.object == "hermes.run" and $f.run_id == $r and $f.session_id == $s and $f.status == "cancelled" and $f.last_event == "run.cancelled"
      and $terminal and ($err | not) and $done and ($l | not) and ($u | not)')"
}
hermes_confinement() {
  local names policy program probe shared
  names=$(printf '%s' "$INTENDED" | jq -c --arg p "$HERMES_PYTHON" '[.network_policies // {} | to_entries[] | select(.value.binaries == [{path: $p}]) | .key]')
  [[ "$names" == '["hermes_maas"]' ]] || fail "Exact inspected private interpreter policy differs"
  policy=hermes_maas
  # No credentials or inference payload. Only these exact newly created files may be removed, and only while their
  # inode still matches the open file.
  program="import os,socket,json,http.client,ssl
identifier='$IDENTIFIER';host='$HOST'
r={}
try:
 fd=os.open('/root/.hermes-confinement-'+identifier,os.O_RDONLY);os.close(fd);r['read']={'errno':None}
except OSError as e:r['read']={'errno':e.errno}
for name,directory in [('privateWrite','/opt/hermes-venv'),('systemWrite','/etc')]:
 path=directory+'/.hermes-confinement-'+identifier
 try:fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 except OSError as e:r[name]={'errno':e.errno};continue
 created=os.fstat(fd);cleaned=False
 try:
  actual=os.lstat(path)
  if (actual.st_dev,actual.st_ino)==(created.st_dev,created.st_ino):os.unlink(path);cleaned=True
 except OSError:pass
 finally:os.close(fd)
 r[name]={'errno':None,'unexpectedCreated':True,'cleaned':cleaned}
for name,address,port in [('internet','1.1.1.1',443),('metadata','169.254.169.254',80)]:
 socket_probe=socket.socket();socket_probe.settimeout(3)
 try:socket_probe.connect((address,port));r[name]={'errno':None}
 except OSError as e:r[name]={'errno':e.errno}
 finally:socket_probe.close()
for name,method,path in [('wrongMethod','GET','/v1/chat/completions'),('wrongPath','POST','/v1/models')]:
 connection=http.client.HTTPSConnection(host,443,timeout=6,context=ssl.create_default_context())
 try:
  connection.request(method,path,body=b'' if method=='POST' else None)
  response=connection.getresponse();raw=response.read(8193)
  r[name]={'status':response.status,'policyHeader':response.getheader('X-OpenShell-Policy'),
           'body':json.loads(raw) if len(raw)<=8192 else None}
 except Exception as e:r[name]={'transportFailure':type(e).__name__}
 finally:connection.close()
print(json.dumps(r))"
  probe=$(sandbox_python "$program")
  receipt --argjson p "$probe" '.confinement = ($p | map_values(with_entries(select(.key | IN("errno", "unexpectedCreated", "cleaned", "status", "transportFailure")))))'
  gate filesystemDenied "$(truth jq -n -e --argjson p "$probe" "$HERMES_JQ"'all($p.read, $p.privateWrite, $p.systemWrite; permission_denied)')"
  gate internetDenied "$(truth jq -n -e --argjson p "$probe" "$HERMES_JQ"'$p.internet | permission_denied')"
  gate metadataDenied "$(truth jq -n -e --argjson p "$probe" "$HERMES_JQ"'$p.metadata | permission_denied')"
  shared=$(sandbox_python "import socket,json;s=socket.socket();s.settimeout(3)
try:s.connect(('$HOST',443));r={'errno':None}
except OSError as e:r={'errno':e.errno}
finally:s.close()
print(json.dumps(r))" /usr/bin/python3.11)
  receipt --argjson s "$shared" '.confinement.sharedInterpreter = $s'
  gate sharedInterpreterDenied "$(truth jq -n -e --argjson s "$shared" "$HERMES_JQ"'$s | permission_denied')"
  gate wrongMethodDenied "$(truth jq -n -e --argjson p "$probe" --arg h "$HOST" --arg pol "$policy" --arg py "$HERMES_PYTHON" \
    "$HERMES_JQ"'$p.wrongMethod | inspected_denial("GET"; "/v1/chat/completions"; $h; $pol; $py)')"
  gate wrongPathDenied "$(truth jq -n -e --argjson p "$probe" --arg h "$HOST" --arg pol "$policy" --arg py "$HERMES_PYTHON" \
    "$HERMES_JQ"'$p.wrongPath | inspected_denial("POST"; "/v1/models"; $h; $pol; $py)')"
}
hermes_restart() {
  local baseline history marker saved
  baseline=$(identity running)
  history=$(hermes_messages "$CODING_SESSION" | digest)
  marker=$(uuid_hex 16)
  receipt --arg h "$history" '.historySha256BeforeRestart = $h'
  sandbox_python "import pathlib,json;p=pathlib.Path('$MARKER');assert not p.exists();p.write_text('$marker');print(json.dumps(True))" >/dev/null
  native
  close_forward
  STOPPED=true
  ncli owner "$WORKSPACE" 120 sandbox stop "$NAME" >/dev/null
  [[ $(wait_identity stopped) == "$baseline" ]] || fail "Stopped native sandbox/PVC identity changed"
  native
  ncli owner "$WORKSPACE" 180 sandbox start "$NAME" >/dev/null
  [[ $(wait_identity running) == "$baseline" ]] || fail "Restarted native sandbox/PVC identity changed"
  forward
  STOPPED=false
  lrequest GET "/api/sessions/$CODING_SESSION" || fail "Listener request transport failed"
  local code=$L_STATUS session=$L_BODY
  saved=$(sandbox_python "import pathlib,json;p=pathlib.Path('$MARKER');assert not p.is_symlink();print(json.dumps(p.read_text()))" | jq -r .)
  gate persistentHistory "$(truth jq -n -e --arg c "$code" --argjson s "$session" --arg id "$CODING_SESSION" --arg h "$(hermes_messages "$CODING_SESSION" | digest)" \
    --arg h0 "$history" --arg f "$(hermes_verify_fixture)" --arg f0 "$FIXTURE_SHA" --arg saved "$saved" --arg m "$marker" \
    '$c == "200" and $s.session.id == $id and $h == $h0 and $f == $f0 and $saved == $m')"
}
run_hermes() {
  local owned
  IDENTIFIER=$(uuid_hex 8)
  DIRECTORY="/sandbox/workspace/hermes-qualification-$IDENTIFIER"
  FIXTURE="$DIRECTORY/qualification_add.py"
  MARKER="$DIRECTORY/restart-marker"
  HERMES_COMMAND="cd $DIRECTORY && $HERMES_PYTHON -c \"from qualification_add import add; assert add(2, 3) == 5; assert add(-2, 2) == 0\""
  [[ "$CONFINEMENT_ONLY" == true ]] || receipt --arg f "$FIXTURE" --arg m "$MARKER" '.ownedFixture = $f | .ownedMarker = $m'
  owned_setup hermes
  owned=$(wait_identity running)
  receipt --argjson i "$owned" --argjson s "$STATE" '.ownedRuntimeIdentity = $i | .sandboxId = $s.sandbox_id | .providerId = $s.provider_id | .keyId = $s.key_id'
  gate ownedRuntime true
  runtime_inputs
  forward
  gate authenticatedReady true
  if [[ "$CONFINEMENT_ONLY" == true ]]; then
    hermes_confinement
  else
    lrequest GET /health/detailed "" none || true
    gate missingKeyDenied "$(yes_no rejected_key)"
    lrequest GET /health/detailed "" wrong:synthetic-invalid-key || true
    gate wrongKeyDenied "$(yes_no rejected_key)"
    hermes_seed_fixture
    hermes_coding
    hermes_cancel
    hermes_restart
  fi
  setup_check
  [[ $(identity running) == "$owned" ]] || fail "Owned Sandbox/PVC identity changed"
  forward
  runtime_inputs
  gate runningAtEnd true
  receipt --argjson g "$GATES" '.passed = all($g[] as $x | .checks[$x]; . == true)'
}
hermes_finally() {
  local run
  if [[ -n "$FORWARD_PID" ]]; then
    for run in ${ACTIVE_RUNS[@]+"${ACTIVE_RUNS[@]}"}; do lrequest POST "/v1/runs/$run/stop" "" default 5 >/dev/null 2>&1 || true; done
  fi
  if [[ "${STOPPED:-false}" == true ]]; then
    if (native && ncli owner "$WORKSPACE" 180 sandbox start "$NAME" >/dev/null && wait_identity running >/dev/null && forward) 2>/dev/null; then
      receipt '.checks.runningAtEnd = true'
    else
      receipt '.checks.runningAtEnd = false'
    fi
  fi
  close_forward
}

# ── Owner-only client check ───────────────────────────────────────────────────────────────────────────────────────
# client_check RUNTIME (in its own subshell and work directory): prints that agent's receipt.
client_check() {
  local before path
  work_init
  trap 'close_forward; native_cleanup' EXIT
  STATE_DIR="$STATE_ROOT_DIR/$1"
  DIRECTORY=/sandbox/workspace
  GATES='[]'
  echo '{}' >"$WORK/receipt.json"
  READONLY_MESSAGE="Client cannot advance setup ownership"
  [[ -d "$STATE_DIR" ]] && private_path "$STATE_DIR" || fail "Existing owner state required"
  owned_setup "$1"
  setup_check
  before=$(identity running)
  forward
  runtime_inputs
  path=$(health_path)
  lrequest GET "$path" "" none || true
  [[ "$L_STATUS" == 401 ]] || fail "Missing listener authentication not denied"
  if [[ "$NAME" == opencode ]]; then lrequest GET "$path" "" wrong:synthetic-wrong-password || true; else lrequest GET "$path" "" wrong:synthetic-wrong-key || true; fi
  [[ "$L_STATUS" == 401 ]] || fail "Wrong listener authentication not denied"
  close_forward
  forward
  [[ $(identity running) == "$before" ]] || fail "Client reconnect changed retained identity"
  [[ $(shasum -a 256 "$JOURNAL" | cut -d' ' -f1) == "$JOURNAL_SHA" ]] || fail "Owner recovery journal changed"
  jq -n -c --arg r "$1" --argjson s "$STATE" --argjson i "$before" '{runtime: $r, workspace: "ai-agents", ownerOnly: true, modelRequests: 0,
    checks: {authenticatedReady: true, missingAuthDenied: true, wrongAuthDenied: true, ownerRelayReconnected: true, retainedIdentity: true},
    nativeId: $s.sandbox_id, providerId: $s.provider_id, identity: $i}'
}
run_client() {
  local runtime agents="[]" agent
  [[ "$REVISION" =~ ^[0-9a-f]{40}$ ]] || fail "Immutable published client revision required"
  source_guard "$REVISION" "$SCRIPT_DIR/qualify.sh" "$SCRIPT_DIR/create.sh" "$SCRIPT_DIR/native.sh"
  for runtime in opencode hermes; do
    agent=$( (client_check "$runtime") ) || fail "Owner client proof failed; owned runtime/state preserved"
    agents=$(jq -n -c --argjson a "$agents" --argjson x "$agent" '$a + [$x]')
  done
  agents=$(jq -n -c --argjson a "$agents" '{scope: "ai-admin workspace-independent owner client; no developer/DevSpaces provisioning", agents: $a,
    passed: true, modelRequests: 0}')
  private_receipt "$RECEIPT_FILE" "$agents"
  printf '%s\n' "$agents"
}

# ── Inference qualification (ai-developer in openshell-developer) ─────────────────────────────────────────────────
I_PERSONA=ai-developer I_WORKSPACE=openshell-developer I_TEMPLATE=oc-transport-11816 I_PLACEHOLDER=__MAAS_QWEN38_HOST__
I_PROFILE_FILE="$QUALIFICATION/maas-qwen38-profile.yaml"
I_INFERENCE_POLICY="$QUALIFICATION/opencode-inference-policy.yaml"
I_TRANSPORT_POLICY="$QUALIFICATION/opencode-transport-policy.yaml"
I_REQUIRED='["directMaasCompletion","sandboxHoldsPlaceholderNotKey","effectivePolicyNamesReviewedEndpoint","generatedOutput",
  "streamedIncrementally","taskCancelled","confinementHeld"]'
inference_static() {
  local file
  for file in "$I_PROFILE_FILE" "$I_INFERENCE_POLICY"; do
    grep -qF "$I_PLACEHOLDER" "$file" || fail "$(basename "$file") must keep the host placeholder"
    grep -qF /v1/chat/completions "$file" || fail "$(basename "$file") must name the reviewed chat path"
  done
  ! grep -qF "$I_PLACEHOLDER" "$I_TRANSPORT_POLICY" && grep -qF 'network_policies: {}' "$I_TRANSPORT_POLICY" ||
    fail "The restore policy must stay the reviewed no-network policy"
  [[ $(jq -r '.cliBinarySha256 | length' "$PINS") == 64 ]] || fail "CLI pin is absent"
  echo "[OK] Inference qualification inputs are consistent; no cluster or model call was made"
}
# Evidence (sanitized: no tokens, keys, hostnames or reply text) and the private recovery journal of this run.
evidence() { jq -c "$@" "$WORK/evidence.json" >"$WORK/evidence.next" && mv "$WORK/evidence.next" "$WORK/evidence.json"; }
istate() { jq -r "$@" "$I_STATE_FILE"; }
istate_save() {
  printf '%s' "$1" | jq -e 'type == "object"' >/dev/null 2>&1 || fail "Journal update is not a JSON object"
  (umask 077; jq -c --argjson f "$1" '. + $f' "$I_STATE_FILE" >"$I_DIR/inference-state.pending")
  mv "$I_DIR/inference-state.pending" "$I_STATE_FILE"
}
# icli admin|persona WORKSPACE|- SECONDS ARG...: the pinned CLI in the bootstrap administrator's private profile or in
# the persona's own login; returns the CLI's status (stderr suppressed).
icli() {
  local role=$1 workspace=$2 seconds=$3 home command
  shift 3
  if [[ "$role" == admin ]]; then
    (( $(date +%s) <= $(cat "$I_ADMIN_HOME/.expires") - 45 )) || inference_refresh_admin
    home=$I_ADMIN_HOME
  else
    home=$I_PERSONA_HOME
  fi
  command=("$CLI" --gateway "$I_GATEWAY")
  [[ "$workspace" == - ]] || command+=(--workspace "$workspace")
  (export XDG_CONFIG_HOME="$home"; bounded "$seconds" "${command[@]}" "$@" 2>/dev/null)
}
inference_refresh_admin() {
  local token claims
  token=$(boc get secret openshell-auth -n keycloak -o json |
    jq -j '"grant_type=client_credentials&client_id=openshell-bootstrap&client_secret=\(.data["bootstrap-client-secret"] | @base64d | @uri)"' |
    curl -s --max-time 30 --data-binary @- "$I_ISSUER/protocol/openid-connect/token" | jq -r '.access_token // empty')
  [[ -n "$token" ]] || fail "Bootstrap token request failed"
  claims=$(printf '%s' "$token" | cut -d. -f2 | tr '_-' '/+' | awk '{ while (length($0) % 4) $0 = $0 "="; print }' | base64 -d)
  printf '%s' "$claims" | jq -e --arg i "$I_ISSUER" '.iss == $i and ((.aud | if type == "array" then . else [.] end) | index("openshell-gateway")) != null
    and (.realm_access.roles // [] | index("openshell-platform-admin")) != null' >/dev/null || fail "Bootstrap token claims are not the reviewed admin identity"
  (umask 077; TOKEN=$token jq -n -c --arg i "$I_ISSUER" --argjson exp "$(printf '%s' "$claims" | jq '.exp')" \
    '{access_token: $ENV.TOKEN, expires_at: $exp, issuer: $i, client_id: "openshell-bootstrap"}' >"$I_ADMIN_HOME/openshell/gateways/$I_GATEWAY/oidc_token.json")
  printf '%s' "$claims" | jq '.exp' >"$I_ADMIN_HOME/.expires"
}
inference_global_policy() {
  local policy
  policy=$(icli admin - 90 policy get --global --full -o json) || fail "Global policy read failed"
  printf '%s' "$policy" | jq -e '(.hash // "") != "" and (.policy | type) == "object"' >/dev/null || fail "Global policy payload/hash absent"
  printf '%s' "$policy"
}
# inference_resource KIND NAME: the one native object of that name in the workspace, or nothing; errors never
# establish absence.
inference_resource() {
  local list
  list=$(icli admin "$I_WORKSPACE" 90 "$1" list -o json) || fail "Resource inventory failed; absence not established"
  printf '%s' "$list" | jq -e '(.next_page_token // "") == ""' >/dev/null || fail "Resource inventory is paginated"
  printf '%s' "$list" | jq -e --arg k "${1}s" --arg n "$2" '[.[$k][] | select(.name == $n)] | length <= 1' >/dev/null || fail "Ambiguous native resource identity"
  printf '%s' "$list" | jq -c --arg k "${1}s" --arg n "$2" '[.[$k][] | select(.name == $n)][0] // empty'
}
# The pinned CLI's profile list reads every native page and emits a bare array.
inference_profile_present() {
  local catalog
  catalog=$(icli admin "$I_WORKSPACE" 90 profile list -o json) || fail "Complete profile catalog read failed"
  printf '%s' "$catalog" | jq -e 'type == "array" and all(.[]; type == "object" and (.id | type) == "string")' >/dev/null ||
    fail "Unexpected native profile catalog schema"
  printf '%s' "$catalog" | jq -e --arg p "$I_PROFILE" 'any(.[]; .id == $p)' >/dev/null
}
inference_python() {
  local out
  out=$(icli persona "$I_WORKSPACE" 60 sandbox exec --name "$I_SANDBOX" --timeout 40 --no-tty --no-login-shell -- /usr/bin/python3 -c "$1") &&
    [[ -n "$out" ]] || fail "Sandbox probe failed"
  printf '%s' "$out" | tail -1
}

inference_init() {
  I_DIR=$1
  (umask 077; mkdir -p "$I_DIR")
  [[ $(file_mode "$I_DIR") == *00 ]] || fail "Evidence directory must be private (mode 0700)"
  I_STATE_FILE="$I_DIR/inference-state.json"
  [[ ! -e "$I_STATE_FILE" ]] || private_path "$I_STATE_FILE" || fail "Recovery journal must be private"
  [[ -e "$I_STATE_FILE" ]] || (umask 077; echo '{}' >"$I_STATE_FILE")
  istate -e '. == {} or (.runId // "" | test("^[0-9a-f]{16}$"))' >/dev/null || fail "Legacy/unowned journal requires reviewed manual recovery"
  jq -n -c --arg t "$(date -u +%Y-%m-%dT%H:%M:%SZ)" --arg p "$I_PERSONA" --arg w "$I_WORKSPACE" --arg m "$MODEL" '{timestamp: $t, persona: $p,
    workspace: $w, model: $m, checks: {}, cleanup: {},
    scope: "one sandbox, one model, bounded prompts; no tool task, Hermes, catalog or tracing claim"}' >"$WORK/evidence.json"
  I_TEMP=$(mktemp -d "$I_DIR/inference-XXXXXX")
  I_RUN_ID=$(istate '.runId // empty')
  [[ -n "$I_RUN_ID" ]] || I_RUN_ID=$(uuid_hex 8)
  I_SANDBOX="oc-inference-$I_RUN_ID"
  I_PROVIDER="maas-probe-$I_RUN_ID" I_PROFILE="maas-probe-$I_RUN_ID"
  I_SESSIONS=() I_FORWARD_PID="" I_SERVICE_PID=""
}
inference_prepare() {
  local kubeconfig metadata endpoint identity members gateway
  BOOTSTRAP_KUBECONFIG=${KUBECONFIG:-$HOME/.kube/config}
  resolve_cli
  kubeconfig=${RHOAI_STAGE060_PERSONA_KUBECONFIG:-}
  [[ -n "$kubeconfig" && -f "$kubeconfig" ]] && private_path "$kubeconfig" || fail "Set RHOAI_STAGE060_PERSONA_KUBECONFIG to a private existing ai-developer login"
  PERSONA_KUBECONFIG=$kubeconfig
  (export KUBECONFIG="$kubeconfig"; check_oc_logged_in) >/dev/null 2>&1 || fail "Shared environment/login guard failed; RHOAI_EXPECTED_API_SERVER is required"
  [[ $(poc whoami --show-server) == $(boc whoami --show-server) ]] || fail "Persona and guarded administrative context target different API servers"
  [[ $(poc whoami) == "$I_PERSONA" ]] || fail "Persona kubeconfig is not $I_PERSONA"
  I_PERSONA_TOKEN=$(poc whoami -t)
  I_PERSONA_HOME=${RHOAI_STAGE060_PERSONA_CLI_HOME:-}
  I_GATEWAY=$(cat "$I_PERSONA_HOME/openshell/active_gateway" 2>/dev/null | tr -d '[:space:]' || true)
  [[ -n "$I_PERSONA_HOME" && -n "$I_GATEWAY" && -f "$I_PERSONA_HOME/openshell/gateways/$I_GATEWAY/metadata.json" ]] ||
    fail "Set RHOAI_STAGE060_PERSONA_CLI_HOME to an existing gateway login profile"
  metadata=$(cat "$I_PERSONA_HOME/openshell/gateways/$I_GATEWAY/metadata.json")
  endpoint=$(printf '%s' "$metadata" | jq -r '.gateway_endpoint // ""')
  [[ "$endpoint" =~ ^https://127\.0\.0\.1:([0-9]+)/?$ ]] || fail "Persona profile must use a local forwarded gateway endpoint"
  I_PORT=${BASH_REMATCH[1]}
  I_ISSUER=$(boc get configmap openshell-identity -n openshell -o jsonpath='{.data.issuer}')
  [[ "$I_ISSUER" == https://* ]] && printf '%s' "$metadata" | jq -e --arg i "$I_ISSUER" '.oidc_issuer == $i' >/dev/null ||
    fail "Persona profile issuer differs from the gateway issuer"
  lock_take "${TMPDIR:-/tmp}/openshell-inference-$(sha256_text "$I_ISSUER" | cut -c1-16).lock.d"
  gateway=$(boc get gateway.gateway.networking.k8s.io maas-default-gateway -n openshift-ingress -o json)
  I_HOST=$(printf '%s' "$gateway" | jq -r '[.spec.listeners[] | select(.name == "api") | .hostname][-1] // empty')
  [[ -n "$I_HOST" ]] || fail "MaaS gateway api listener is absent"
  I_API="https://$I_HOST"
  I_CHAT="$I_API/v1/chat/completions"
  # Reuse the operator's existing forward to the persona's local gateway port, or open one.
  if ! port_open "$I_PORT"; then
    KUBECONFIG="$BOOTSTRAP_KUBECONFIG" oc port-forward svc/openshell "$I_PORT:8080" -n openshell >/dev/null 2>&1 &
    I_FORWARD_PID=$!
    echo "$I_FORWARD_PID" >>"$WORK/pids"
    local deadline=$((SECONDS + 20))
    until port_open "$I_PORT"; do (( SECONDS < deadline )) || fail "Gateway port-forward did not open"; sleep 0.5; done
  fi
  identity=$(icli persona - 90 whoami -o json) || fail "Persona gateway session is absent or expired; run \`openshell gateway login\` again"
  printf '%s' "$identity" | jq -e --arg p "$I_PERSONA" '.display_name == $p and (.roles // [] | index("openshell-user")) != null' >/dev/null ||
    fail "Gateway session is not the expected workspace user"
  # A private bootstrap-administrator profile next to the persona's gateway entry (public CA certificate only).
  I_ADMIN_HOME="$I_TEMP/admin"
  mkdir -p "$I_ADMIN_HOME/openshell/gateways/$I_GATEWAY/mtls"
  boc get secret openshell-server-tls -n openshell -o jsonpath='{.data.ca\.crt}' | base64 -d >"$I_ADMIN_HOME/openshell/gateways/$I_GATEWAY/mtls/ca.crt"
  printf '%s' "$metadata" | jq -c '. + {oidc_client_id: "openshell-bootstrap"}' >"$I_ADMIN_HOME/openshell/gateways/$I_GATEWAY/metadata.json"
  printf '%s' "$I_GATEWAY" >"$I_ADMIN_HOME/openshell/active_gateway"
  echo 0 >"$I_ADMIN_HOME/.expires"
  inference_refresh_admin
  icli admin - 90 whoami -o json | jq -e '(.roles // [] | index("openshell-platform-admin")) != null' >/dev/null 2>&1 ||
    fail "Bootstrap identity is not a platform admin"
  members=$(icli admin - 90 workspace member list --workspace "$I_WORKSPACE" -o json) || fail "Curated workspace membership read failed"
  printf '%s' "$members" | jq -e '(.next_page_token // "") == "" and (.members // [] | length) == 1 and .members[0].role == "user"' >/dev/null ||
    fail "Expected one curated normal-user membership"
  jq -n -e --argjson i "$identity" --argjson m "$members" --arg p "$I_PERSONA" '($i.subject // "") != "" and $i.subject == $m.members[0].subject
    and $i.display_name == $p and ($i.roles | index("openshell-user")) != null and ($i.roles | index("openshell-platform-admin")) == null' >/dev/null ||
    fail "Persona subject/normal role differs from curated membership"
  istate -e --arg s "$(printf '%s' "$identity" | jq -r '.subject')" '(.subject // $s) == $s' >/dev/null ||
    fail "Recovery journal belongs to a different immutable persona"
  istate_save "$(jq -n -c --arg r "$I_RUN_ID" --arg s "$(printf '%s' "$identity" | jq -r '.subject')" '{runId: $r, subject: $s}')"
}
inference_preconditions() {
  local fleet original templates
  [[ "${RHOAI_STAGE060_EXCLUSIVE_QUALIFICATION:-}" == true ]] ||
    fail "Explicit exclusive gateway qualification window is required; global policy has no atomic CAS"
  bget statefulset openshell openshell | jq -e --arg d "$(jq -r '.images.gateway.amd64Digest' "$PINS")" '.status.readyReplicas == 1
    and (.spec.template.spec.containers[0].image | endswith($d))' >/dev/null || fail "Gateway is not ready on the pinned image"
  boc get sandboxes.agents.x-k8s.io -n "$I_WORKSPACE" -o json | jq -e '.items == []' >/dev/null ||
    fail "Workspace already has a Sandbox; refusing to share the qualification window"
  fleet=$(icli admin - 90 sandbox list --all-workspaces -o json) || fail "All-workspace sandbox inventory failed"
  printf '%s' "$fleet" | jq -e '(.next_page_token // "") == "" and .sandboxes == []' >/dev/null || fail "Global policy qualification requires an empty sandbox fleet"
  [[ -z "$(inference_resource provider "$I_PROVIDER")" ]] || fail "Run provider name exists"
  ! inference_profile_present || fail "Run profile name exists; refusing import"
  bget llminferenceservice qwen3-8-27b internal-models | jq -e 'any(.status.conditions[]?; .type == "Ready" and .status == "True")' >/dev/null ||
    fail "Model is not Ready"
  templates=$(icli persona "$I_WORKSPACE" 90 sandbox template list -o json) && printf '%s' "$templates" | jq -e --arg t "$I_TEMPLATE" 'any(.templates[]; .name == $t)' >/dev/null ||
    fail "Reviewed sandbox template is absent"
  original=$(inference_global_policy)
  printf '%s' "$original" | jq -e '(.policy.network_policies // {}) == {}' >/dev/null || fail "Qualification requires an existing no-network global policy"
  istate_save "$(printf '%s' "$original" | jq -c '{policyHashBefore: .hash, originalPolicy: .policy}')"
}
inference_render() {
  grep -qF "$I_PLACEHOLDER" "$1" || fail "$(basename "$1") lost its host placeholder"
  sed "s/$I_PLACEHOLDER/$I_HOST/g" "$1" >"$2"
}
inference_setup() {
  local authored intended exported applied created status
  inference_render "$I_PROFILE_FILE" "$I_TEMP/profile.yaml"
  sed -i.orig "s/^id: maas-qwen38\$/id: $I_PROFILE/" "$I_TEMP/profile.yaml" && rm -f "$I_TEMP/profile.yaml.orig"
  inference_render "$I_INFERENCE_POLICY" "$I_TEMP/inference-policy.yaml"
  # The pinned native serializer mirrors YAML and omits empty maps: keep every original field, add only the route.
  authored=$(yaml_json <"$I_TEMP/inference-policy.yaml" | jq -c '.[0]')
  istate -e --argjson a "$authored" '.originalPolicy.filesystem_policy == $a.filesystem_policy and .originalPolicy.landlock == $a.landlock' >/dev/null ||
    fail "Original hard filesystem policy differs from the reviewed qualification contract"
  intended=$(istate -c --argjson a "$authored" '.originalPolicy + {network_policies: $a.network_policies}')
  printf '%s' "$intended" >"$I_TEMP/inference-policy.yaml"
  icli admin "$I_WORKSPACE" 90 profile lint -f "$I_TEMP/profile.yaml" >/dev/null || fail "Gateway rejected the provider profile"
  istate_save '{"profilePending": true}'
  icli admin "$I_WORKSPACE" 90 profile import -f "$I_TEMP/profile.yaml" >/dev/null || fail "Provider profile import failed"
  exported=$(icli admin "$I_WORKSPACE" 90 profile export "$I_PROFILE" -o json) || fail "Created profile read failed"
  istate_save "$(jq -n -c --arg d "$(printf '%s' "$exported" | digest)" '{profile: true, profilePending: false, profileDigest: $d}')"
  [[ $(inference_global_policy | jq -r '.hash') == $(istate '.policyHashBefore') ]] || fail "Global policy changed before qualification"
  istate_save "$(jq -n -c --argjson i "$intended" '{policyPending: true, intendedPolicy: $i}')"
  icli admin - 90 policy set --global --yes --policy "$I_TEMP/inference-policy.yaml" >/dev/null || fail "Global policy update failed"
  applied=$(inference_global_policy)
  jq -n -e --argjson a "$applied" --argjson i "$intended" '$a.policy == $i' >/dev/null ||
    fail "Global policy readback differs from exact intended content; refusing further operations"
  istate_save "$(printf '%s' "$applied" | jq -c '{policy: true, policyPending: false, policyHashApplied: .hash, appliedPolicy: .policy}')"
  http GET "$I_API/v1/subscriptions" I_PERSONA_TOKEN
  [[ "$HTTP_STATUS" == 200 ]] && printf '%s' "$HTTP_BODY" | jq -e --arg s "personal-$I_PERSONA" 'any((. // [])[]; .subscription_id_header == $s)' >/dev/null ||
    fail "Persona cannot discover its MaaS subscription"
  istate_save '{"keyPending": true}'
  http POST "$I_API/v1/api-keys" I_PERSONA_TOKEN "$(jq -n -c --arg n "openshell-inference-$I_RUN_ID" --arg s "personal-$I_PERSONA" \
    '{name: $n, subscription: $s, expiresIn: "1h", ephemeral: true}')"
  created=$HTTP_BODY
  if [[ "$HTTP_STATUS" == 201 ]] && printf '%s' "$created" | jq -e '(.id // "") != ""' >/dev/null 2>&1; then
    istate_save "$(printf '%s' "$created" | jq -c '{keyId: .id, keyPending: false}')"
  fi
  [[ "$HTTP_STATUS" == 201 ]] && printf '%s' "$created" | jq -e '(.id // "") != "" and (.key // "") != "" and .ephemeral == true' >/dev/null 2>&1 ||
    fail "Ephemeral MaaS key creation failed"
  I_KEY=$(printf '%s' "$created" | jq -r '.key')
  created=""
  HTTP_TIMEOUT=120 http POST "$I_CHAT" I_KEY "$(jq -n -c --arg m "$MODEL" '{model: $m, messages: [{role: "user", content: "Reply with exactly OK."}], max_tokens: 8}')"
  status=$HTTP_STATUS
  evidence --argjson ok "$(yes_no test "$status" == 200 -a "$(printf '%s' "$HTTP_BODY" | jq -r '(.choices // []) | length > 0' 2>/dev/null)" == true)" \
    '.checks.directMaasCompletion = $ok'
  [[ $(jq -r '.checks.directMaasCompletion' "$WORK/evidence.json") == true ]] ||
    fail "MaaS did not return a valid chat-completion response (HTTP $status); OpenCode inference was not tested"
  istate_save '{"providerPending": true}'
  (export MAAS_API_KEY="$I_KEY"; icli admin "$I_WORKSPACE" 90 provider create --name "$I_PROVIDER" --type "$I_PROFILE" --credential MAAS_API_KEY) >/dev/null ||
    fail "Provider creation failed"
  created=$(inference_resource provider "$I_PROVIDER")
  [[ -n "$created" ]] && printf '%s' "$created" | jq -e '(.id // "") != ""' >/dev/null || fail "Created provider ID missing"
  istate_save "$(printf '%s' "$created" | jq -c '{provider: true, providerPending: false, providerId: .id}')"
}
inference_launch() {
  local config command created deadline
  config=$(jq -n -c --arg m "$MODEL" --arg base "https://$I_HOST/v1" '{"$schema": "https://opencode.ai/config.json", autoupdate: false, share: "disabled",
    enabled_providers: ["qwen38"], provider: {qwen38: {npm: "@ai-sdk/openai-compatible", name: "MaaS Qwen3.8",
      models: {($m): {name: "Qwen3.8 27B", limit: {context: 262144, output: 128}}},
      options: {apiKey: "{env:MAAS_API_KEY}", baseURL: $base, timeout: 60000}}},
    model: ("qwen38/" + $m), small_model: ("qwen38/" + $m), permission: {edit: "deny", bash: "deny", webfetch: "deny"}}')
  command="mkdir -p /sandbox/state /sandbox/tmp /sandbox/workspace && cd /sandbox/workspace && echo $(printf '%s' "$config" | base64 | tr -d '\n') | base64 -d > opencode.json && export OPENCODE_DISABLE_MODELS_FETCH=1 OPENCODE_EXPERIMENTAL_OUTPUT_TOKEN_MAX=128 && exec opencode serve --hostname 127.0.0.1 --port 4096"
  istate_save '{"sandboxPending": true}'
  icli persona "$I_WORKSPACE" 240 sandbox create --name "$I_SANDBOX" --template "$I_TEMPLATE" --provider "$I_PROVIDER" --no-auto-providers \
    --approval-mode manual --detach -o json -- /bin/bash -c "$command" >/dev/null || fail "Sandbox creation with the provider failed"
  created=$(icli persona "$I_WORKSPACE" 90 sandbox get "$I_SANDBOX" -o json) || fail "Created sandbox identity read failed"
  printf '%s' "$created" | jq -e '(.id // "") != ""' >/dev/null || fail "Created sandbox has no native ID"
  istate_save "$(printf '%s' "$created" | jq -c '{sandbox: true, sandboxPending: false, sandboxId: .id}')"
  LOCAL=$(free_port)
  (export XDG_CONFIG_HOME="$I_PERSONA_HOME"; exec "$CLI" --gateway "$I_GATEWAY" --workspace "$I_WORKSPACE" forward service "$I_SANDBOX" \
    --target-port 4096 --target-host 127.0.0.1 --local "127.0.0.1:$LOCAL") >/dev/null 2>&1 &
  I_SERVICE_PID=$!
  echo "$I_SERVICE_PID" >>"$WORK/pids"
  deadline=$((SECONDS + 90))
  while true; do
    if lrequest GET /global/health "" default 5 && [[ "$L_STATUS" == 200 ]] && printf '%s' "$L_BODY" | jq -e '.healthy' >/dev/null; then break; fi
    (( SECONDS < deadline )) || fail "OpenCode did not become healthy through the forward"
    sleep 2
  done
}
inference_checks() {
  local probe effective session second started finished reply parts info text numbers deadline status aborted returned outcome
  local status_http statuses generating=false active_text=false settled denied rc=0
  probe=$(inference_python "import os,hashlib,json;v=os.environ.get('MAAS_API_KEY','');print(json.dumps({'present':bool(v),'sha256':hashlib.sha256(v.encode()).hexdigest()}))")
  evidence --argjson ok "$(truth jq -n -e --argjson p "$probe" --arg k "$(sha256_text "$I_KEY")" '$p.present and $p.sha256 != $k')" \
    '.checks.sandboxHoldsPlaceholderNotKey = $ok'
  effective=$(icli persona "$I_WORKSPACE" 90 policy get "$I_SANDBOX" --full) || rc=$?
  evidence --argjson ok "$(truth jq -n -e --arg e "$effective" --arg h "$I_HOST" --argjson rc "$rc" '$rc == 0 and ($e | contains($h)) and ($e | contains("chat/completions"))')" \
    '.checks.effectivePolicyNamesReviewedEndpoint = $ok'
  stream_start events "/event?directory=$(jq -rn --arg d "$DIRECTORY" '$d | @uri')"
  deadline=$((SECONDS + 10))
  while (( $(mark) == 0 )) && (( SECONDS < deadline )); do sleep 0.2; done
  lrequest POST /session '{}' default 30 || fail "OpenCode session creation failed"
  session=$(printf '%s' "$L_BODY" | jq -r '.id // empty')
  [[ "$L_STATUS" == 200 && -n "$session" ]] || fail "OpenCode session creation failed"
  I_SESSIONS+=("$session")
  started=$(mark)
  lrequest POST "/session/$session/message" "$(jq -n -c --arg m "$MODEL" '{model: {providerID: "qwen38", modelID: $m},
    parts: [{type: "text", text: "Count from 1 to 30, separated by commas. Output only the numbers."}]}')" default 90 || fail "Listener request transport failed"
  finished=$(mark)
  status=$L_STATUS reply=$L_BODY
  parts=$(events | jq -c --arg s "$session" --argjson a "$started" --argjson b "$finished" "$OC_JQ"'deltas($s; $a; $b)')
  evidence --arg st "$status" --argjson r "$reply" --argjson parts "$parts" --argjson err "$(event_error)" --arg m "$MODEL" --argjson f "$finished" "$FALSY"'
    (($r // {}).info // {}) as $info | ([($r // {}).parts[]? | select(.type == "text") | .text // ""] | join("")) as $text
    | ([$text | gsub("\n"; ",") | split(",")[] | gsub("^\\s+|\\s+$"; "") | select(test("^[0-9]+$"))] | length) as $numbers
    | .checks.generated = {httpStatus: ($st | tonumber), error: ($info.error // {}).name, provider: $info.providerID, modelID: $info.modelID,
        replyCharacters: ($text | length), numbersInReply: $numbers, outputTokens: ($info.tokens.output // 0)}
    | .checks.generatedOutput = ($st == "200" and ($info.error | falsy) and $info.role == "assistant" and $info.providerID == "qwen38"
        and $info.modelID == $m and ($info.tokens.output | type) == "number" and $info.tokens.output > 0 and $info.tokens.output <= 128 and $numbers >= 20)
    | .checks.streaming = {partEvents: ($parts | length), spanSeconds: null, firstEventBeforeCompletionSeconds: null,
        ordering: "event positions; no sub-second clock"}
    | .checks.streamedIncrementally = (($parts | length) >= 2 and $parts[0] < $f and ($err | not))'
  # Cancellation: abort a long generation after its first streamed parts.
  lrequest POST /session '{}' default 30 || fail "Second OpenCode session creation failed"
  second=$(printf '%s' "$L_BODY" | jq -r '.id // empty')
  [[ "$L_STATUS" == 200 && -n "$second" ]] || fail "Second OpenCode session creation failed"
  I_SESSIONS+=("$second")
  rm -f "$WORK/prompt-$second"
  (if lrequest POST "/session/$second/message" "$(jq -n -c --arg m "$MODEL" '{model: {providerID: "qwen38", modelID: $m},
      parts: [{type: "text", text: "Explain a Java null check in a short paragraph."}]}')" default 90; then printf '%s\n%s' "$L_STATUS" "$L_BODY"
   else printf 'transport\nnull'; fi >"$WORK/prompt-$second") &
  PROMPT_PID=$!
  deadline=$((SECONDS + 30))
  while (( $(deltas_count "$second") == 0 )) && (( SECONDS < deadline )) && alive "$PROMPT_PID"; do sleep 0.3; done
  lrequest GET /session/status || true
  if alive "$PROMPT_PID" && [[ "$L_STATUS" == 200 ]] && printf '%s' "$L_BODY" | jq -e --arg s "$second" 'type == "object" and .[$s].type == "busy"' >/dev/null; then
    generating=true
  fi
  (( $(deltas_count "$second") == 0 )) || active_text=true
  [[ "$generating" == true && "$active_text" == true ]] || fail "No active assistant generation to cancel"
  local aborted_seconds=$SECONDS
  lrequest POST "/session/$second/abort" || true
  status=$L_STATUS aborted=$L_BODY
  join_pid "$PROMPT_PID" 45 || true
  returned=$(yes_no join_pid "$PROMPT_PID" 0)
  outcome=$(prompt_outcome "$second")
  lrequest GET /session/status || true
  status_http=$L_STATUS statuses=$L_BODY
  evidence --argjson g "$generating" --arg as "$status" --argjson ab "$aborted" --argjson ret "$returned" --argjson secs "$((SECONDS - aborted_seconds))" \
    --argjson o "$outcome" --arg sh "$status_http" --argjson st "$statuses" --arg s "$second" '.checks.cancellation = {wasGenerating: $g,
      abortAccepted: ($as == "200" and $ab == true), promptReturned: $ret, returnSeconds: $secs, error: ((($o.reply // {}).info.error // {}).name),
      idleAfterwards: ($sh == "200" and ($st | type) == "object" and $st[$s].type == "idle")}'
  settled=$(mark)
  sleep 1
  evidence --argjson ret "$returned" --argjson g "$generating" --argjson t "$active_text" --arg as "$status" --argjson ab "$aborted" --argjson o "$outcome" \
    --arg sh "$status_http" --argjson st "$statuses" --arg s "$second" --argjson late "$(deltas_count "$second" "$settled")" --argjson err "$(event_error)" \
    '.checks.taskCancelled = ($ret and $g and $t and $as == "200" and $ab == true and $o.status == 200 and ($o.transport | not)
      and ((($o.reply // {}).info.error // {}).name == "MessageAbortedError") and $sh == "200" and ($st | type) == "object"
      and $st[$s].type == "idle" and $late == 0 and ($err | not))'
  stream_stop events
  denied=$(inference_python "import json,socket
r={}
def attempt(key,host):
    s=socket.socket();s.settimeout(8)
    try:
        s.connect((host,443));r[key]=False
    except OSError as e:
        r[key]=e.errno in (1,13);r[key+'Errno']=e.errno
    finally:
        s.close()
attempt('internetDenied','1.1.1.1')
attempt('otherBinaryToModelDenied','$I_HOST')
print(json.dumps(r))")
  evidence --argjson d "$denied" '.checks.egressStillConfined = $d | .checks.confinementHeld = ($d.internetDenied == true and $d.otherBinaryToModelDenied == true)'
}
# inference_step NAME FUNCTION: every cleanup step is attempted; a failure is recorded, never hidden.
inference_step() {
  I_STEPS+=("$1")
  if ( "$2" ) >/dev/null 2>&1; then
    evidence --arg n "$1" '.cleanup[$n] = true'
  else
    evidence --arg n "$1" '.cleanup[$n] = false | .cleanup[$n + "Error"] = "Failure"'
  fi
}
I_STEPS=()
inference_delete_sandbox() {
  local resource deadline
  resource=$(inference_resource sandbox "$I_SANDBOX")
  [[ -n "$resource" ]] || return 0
  [[ $(printf '%s' "$resource" | jq -r '.id') == $(istate '.sandboxId') ]] || fail "Sandbox identity changed; refusing deletion"
  icli persona "$I_WORKSPACE" 120 sandbox delete "$I_SANDBOX" >/dev/null || fail "Native sandbox deletion failed"
  deadline=$((SECONDS + 120))
  while [[ -n "$(inference_resource sandbox "$I_SANDBOX")" ]]; do (( SECONDS < deadline )) || fail "Sandbox resources remain"; sleep 5; done
}
inference_delete_provider() {
  local resource
  resource=$(inference_resource provider "$I_PROVIDER")
  [[ -n "$resource" ]] || return 0
  [[ $(printf '%s' "$resource" | jq -r '.id') == $(istate '.providerId') ]] || fail "Provider identity changed; refusing deletion"
  icli admin "$I_WORKSPACE" 90 provider delete "$I_PROVIDER" >/dev/null || fail "Provider deletion failed"
  [[ -z "$(inference_resource provider "$I_PROVIDER")" ]]
}
inference_delete_profile() {
  local current
  inference_profile_present || return 0
  current=$(icli admin "$I_WORKSPACE" 90 profile export "$I_PROFILE" -o json) && [[ $(printf '%s' "$current" | digest) == $(istate '.profileDigest') ]] ||
    fail "Profile read/identity changed; refusing deletion"
  icli admin "$I_WORKSPACE" 90 profile delete "$I_PROFILE" >/dev/null || fail "Profile deletion failed"
  ! inference_profile_present
}
inference_restore_policy() {
  local fleet current
  fleet=$(icli admin - 90 sandbox list --all-workspaces -o json) || fail "Cannot prove an empty fleet before temporary-policy restoration"
  printf '%s' "$fleet" | jq -e '(.next_page_token // "") == "" and .sandboxes == []' >/dev/null ||
    fail "Active retained fleet; temporary global-policy restoration refused"
  current=$(inference_global_policy | jq -r '.hash')
  if [[ "$current" == $(istate '.policyHashBefore') ]]; then evidence '.cleanup.policyHashEqualsBefore = true'; return 0; fi
  [[ "$current" == $(istate '.policyHashApplied') ]] || fail "Concurrent global policy change; refusing overwrite"
  istate -c '.originalPolicy' >"$I_TEMP/original-policy.json"
  icli admin - 90 policy set --global --yes --policy "$I_TEMP/original-policy.json" >/dev/null || fail "Policy restore failed"
  if [[ $(inference_global_policy | jq -r '.hash') == $(istate '.policyHashBefore') ]]; then
    evidence '.cleanup.policyHashEqualsBefore = true'
  else
    evidence '.cleanup.policyHashEqualsBefore = false'
    fail "Restored global policy hash mismatch"
  fi
}
inference_revoke_key() {
  http DELETE "$I_API/v1/api-keys/$(istate '.keyId' | jq -Rr @uri)" I_PERSONA_TOKEN
  [[ "$HTTP_STATUS" == 200 ]] && printf '%s' "$HTTP_BODY" | jq -e '.status == "revoked"' >/dev/null || fail "Key revocation was not confirmed"
  if [[ -n "${I_KEY:-}" ]]; then
    HTTP_TIMEOUT=60 http POST "$I_CHAT" I_KEY "$(jq -n -c --arg m "$MODEL" '{model: $m, messages: [{role: "user", content: "OK"}], max_tokens: 4}')"
    evidence --argjson d "$(yes_no test "$HTTP_STATUS" == 401 -o "$HTTP_STATUS" == 403)" '.cleanup.revokedKeyDenied = $d'
  fi
}
inference_abort_session() { lrequest POST "/session/$1/abort" "" default 5 && [[ "$L_STATUS" == 200 && "$L_BODY" == true ]]; }
inference_cleanup() {
  local index=0 session pending
  for session in ${I_SESSIONS[@]+"${I_SESSIONS[@]}"}; do
    I_ABORT_SESSION=$session
    inference_step "sessionAbort-$index" inference_abort_current
    index=$((index + 1))
  done
  [[ -z "$I_SERVICE_PID" ]] || kill "$I_SERVICE_PID" 2>/dev/null || true
  I_STEPS+=(serviceClosed)
  evidence '.cleanup.serviceClosed = true'
  for pending in sandboxPending providerPending profilePending policyPending keyPending; do
    # A lost creation or update response establishes neither ownership nor an applied hash.
    if istate -e --arg p "$pending" '.[$p] == true' >/dev/null; then
      I_STEPS+=("$pending")
      evidence --arg p "$pending" '.cleanup[$p] = false'
    fi
  done
  if istate -e '.sandbox == true' >/dev/null; then inference_step sandboxDeleted inference_delete_sandbox; fi
  if istate -e '.provider == true' >/dev/null; then inference_step providerDeleted inference_delete_provider; fi
  if istate -e '.profile == true' >/dev/null; then inference_step profileDeleted inference_delete_profile; fi
  if istate -e '.policy == true' >/dev/null; then inference_step noNetworkPolicyRestored inference_restore_policy; fi
  if istate -e '(.keyId // "") != ""' >/dev/null; then inference_step keyRevoked inference_revoke_key; fi
  [[ -z "$I_FORWARD_PID" ]] || kill "$I_FORWARD_PID" 2>/dev/null || true
  I_STEPS+=(gatewayForwardClosed)
  evidence '.cleanup.gatewayForwardClosed = true'
  rm -rf "$I_TEMP"  # the temporary admin profile and the rendered files
  jq -e --argjson s "$(printf '%s\n' "${I_STEPS[@]}" | jq -R . | jq -s -c .)" 'all($s[] as $n | .cleanup[$n]; . == true) and (.cleanup.revokedKeyDenied // true)' \
    "$WORK/evidence.json" >/dev/null
}
inference_abort_current() { inference_abort_session "$I_ABORT_SESSION"; }
# inference_exit: on every exit (signals ignored meanwhile), clean up from the journal, then write the evidence.
inference_exit() {
  local rc=$? failure="" clean=false path
  set +e
  trap '' INT TERM ALRM
  [[ -z "${WATCHDOG_PID:-}" ]] || kill "$WATCHDOG_PID" 2>/dev/null
  [[ "$rc" == 0 ]] || failure=$(cat "$WORK/failure" 2>/dev/null || echo Error)
  [[ -z "$INTERRUPTED" ]] || failure=$INTERRUPTED
  rm -f "$WORK/failure"
  if [[ -n "${I_STATE_FILE:-}" ]]; then
    inference_cleanup && clean=true
    evidence --arg f "$failure" --argjson c "$clean" --argjson r "$I_REQUIRED" '.passed = ($f == "" and $c and all($r[] as $k | .checks[$k]; . == true))
      | if $f != "" then .failure = $f else . end'
    [[ "$clean" != true ]] || rm -f "$I_STATE_FILE"
    path="$I_DIR/inference-results-$(date -u +%Y%m%dT%H%M%SZ).json"
    private_receipt "$path" "$(cat "$WORK/evidence.json")"
    jq --argjson r "$I_REQUIRED" '{passed, checks: (.checks as $c | [$r[] | {(.): $c[.]}] | add), cleanup}' "$WORK/evidence.json"
    echo "Sanitized evidence saved to $path; no tokens, keys, hostnames or reply text included"
  fi
  native_cleanup
  locks_release
  if [[ -n "$failure" || "$clean" != true ]] || { [[ "$I_MODE" == --run ]] && ! jq -e '.passed' "$WORK/evidence.json" >/dev/null 2>&1; }; then
    echo "[FAIL] ${failure:-see sanitized evidence}" >&2
    exit 1
  fi
  if [[ "$I_MODE" == --run ]]; then echo "[PASS] Bounded inference qualification"; else echo "[OK] Interrupted run cleaned up"; fi
  exit 0
}
INTERRUPTED=""
run_inference() {
  I_MODE=$1
  [[ "$I_MODE" == --cleanup || ! -e "$2/inference-state.json" ]] || fail "A previous run left state in this directory; use --cleanup first"
  NAME=opencode SECRET="" DIRECTORY=/sandbox/workspace
  inference_init "$2"
  trap inference_exit EXIT
  trap 'INTERRUPTED="Termination requested"; exit 1' INT TERM
  trap 'INTERRUPTED="Qualification wall-clock deadline exceeded"; exit 1' ALRM
  (sleep 240; kill -ALRM $$) >/dev/null 2>&1 &
  WATCHDOG_PID=$!
  inference_prepare
  if [[ "$I_MODE" == --run ]]; then
    inference_preconditions
    inference_setup
    inference_launch
    inference_checks
  else
    istate -e '. != {}' >/dev/null || fail "No interrupted-run state in this directory"
  fi
}

# ── Host capability qualification ─────────────────────────────────────────────────────────────────────────────────
hoc() { oc --request-timeout=15s "$@"; }
host_cleanup() {
  local status=$?
  trap - EXIT
  if [[ -n "${NAMESPACE_UID:-}" ]]; then
    jq -n -c --arg uid "$NAMESPACE_UID" '{apiVersion: "v1", kind: "DeleteOptions", preconditions: {uid: $uid}, propagationPolicy: "Background"}' \
      >"$EVIDENCE_DIR/delete-options.json"
    if hoc delete --raw "/api/v1/namespaces/$PROBE_NS" -f "$EVIDENCE_DIR/delete-options.json" >"$EVIDENCE_DIR/delete-private.json" \
        2>"$EVIDENCE_DIR/delete-error-private.log" && hoc wait "namespace/$PROBE_NS" --for=delete --timeout=60s >"$EVIDENCE_DIR/cleanup.log" 2>&1; then
      echo "Owned namespace cleanup confirmed."
    else
      echo "Owned namespace cleanup failed; inspect private evidence." >&2
      status=1
    fi
  fi
  native_cleanup
  exit "$status"
}
run_host() {
  local pins deadline state
  [[ $# -le 1 ]] || usage
  umask 077
  EVIDENCE_DIR=${1:-$(mktemp -d "${TMPDIR:-/tmp}/openshell-qualification.XXXXXX")}
  mkdir -p "$EVIDENCE_DIR"
  chmod 700 "$EVIDENCE_DIR"
  PROBE_NS="openshell-qualification-$(date +%s)-$$"
  NAMESPACE_UID=""
  trap host_cleanup EXIT
  trap 'exit 130' INT
  trap 'exit 143' TERM
  # Never adopt an existing namespace; API errors fail closed.
  [[ -z "$(hoc get namespace "$PROBE_NS" --ignore-not-found -o name)" ]] || fail "Refusing existing namespace"
  hoc create namespace "$PROBE_NS" -o json >"$EVIDENCE_DIR/namespace-private.json"
  NAMESPACE_UID=$(jq -r '.metadata.uid' "$EVIDENCE_DIR/namespace-private.json")
  hoc get namespace "$PROBE_NS" -o json >"$EVIDENCE_DIR/namespace-private.json"
  hoc get nodes -o json >"$EVIDENCE_DIR/nodes-private.json"
  # One CPU worker; the namespace's own UID/GID; the pinned sandbox image's native capability probe.
  pins="$REPO_ROOT/$RUNTIME_PATH/chart/source-pins.json"
  jq -n -c --slurpfile ns "$EVIDENCE_DIR/namespace-private.json" --slurpfile nodes "$EVIDENCE_DIR/nodes-private.json" --slurpfile pins "$pins" \
    --arg name "$PROBE_NS" '
    $ns[0].metadata.annotations as $a
    | ($a["openshift.io/sa.scc.uid-range"] | split("/")[0] | split("-")[0] | tonumber) as $uid
    | (($a["openshift.io/sa.scc.supplemental-groups"] // $a["openshift.io/sa.scc.uid-range"]) | split("/")[0] | split("-")[0] | tonumber) as $gid
    | if $uid <= 0 or $gid <= 0 then error("namespace UID/GID range") else . end
    | ([$nodes[0].items[] | (.metadata.labels // {}) as $l | select(($l | has("node-role.kubernetes.io/worker"))
        and ($l | has("node-role.kubernetes.io/master") | not) and ($l | has("node-role.kubernetes.io/control-plane") | not)
        and $l["kubernetes.io/arch"] == "amd64" and (any(.spec.taints[]?; .effect == "NoSchedule" or .effect == "NoExecute") | not)
        and (.status.allocatable["nvidia.com/gpu"] // "0") == "0" and (.spec.unschedulable | not)
        and any(.status.conditions[]; .type == "Ready" and .status == "True")) | .metadata.name][0]
        // error("no ready amd64 CPU worker")) as $node
    | {"app.kubernetes.io/name": "openshell-host-qualification", "app.kubernetes.io/part-of": "rhoai3-coding-demo"} as $labels
    | {automountServiceAccountToken: false, restartPolicy: "Never", nodeSelector: {"kubernetes.io/hostname": $node},
       securityContext: {runAsNonRoot: true, runAsUser: $uid, runAsGroup: $gid, seccompProfile: {type: "RuntimeDefault"},
         sysctls: [{name: "net.ipv4.ip_unprivileged_port_start", value: "0"}]},
       containers: [{name: "probe", image: "\($pins[0].images.sandbox.repository)@\($pins[0].images.sandbox.amd64Digest)",
         command: ["/openshell-sandbox", "capability-probe"],
         securityContext: {allowPrivilegeEscalation: false, readOnlyRootFilesystem: true, capabilities: {drop: ["ALL"]}},
         resources: {requests: {cpu: "20m", memory: "64Mi"}, limits: {cpu: "200m", memory: "128Mi"}},
         volumeMounts: [{name: "temporary", mountPath: "/tmp"}]}],
       volumes: [{name: "temporary", emptyDir: {sizeLimit: "8Mi"}}]} as $spec
    | {job: {apiVersion: "batch/v1", kind: "Job", metadata: {name: "native-capability-probe", namespace: $name, labels: $labels},
         spec: {backoffLimit: 0, activeDeadlineSeconds: 180, template: {metadata: {labels: $labels}, spec: $spec}}},
       admission: {apiVersion: "v1", kind: "Pod", metadata: {name: "admission-only", namespace: $name}, spec: $spec}}' >"$EVIDENCE_DIR/probe.json"
  jq '.job' "$EVIDENCE_DIR/probe.json" >"$EVIDENCE_DIR/job-private.json"
  jq '.admission' "$EVIDENCE_DIR/probe.json" >"$EVIDENCE_DIR/admission-private.json"
  rm "$EVIDENCE_DIR/probe.json"
  jq -c . "$pins" >"$EVIDENCE_DIR/pins.json"
  hoc create --dry-run=server -f "$EVIDENCE_DIR/admission-private.json" -o json >"$EVIDENCE_DIR/admitted-private.json"
  hoc create -f "$EVIDENCE_DIR/job-private.json" >>"$EVIDENCE_DIR/create.log"
  # The native Job has a hard deadline; stop early on a recorded failure.
  deadline=$((SECONDS + 180))
  while (( SECONDS < deadline )); do
    hoc get job native-capability-probe -n "$PROBE_NS" -o json >"$EVIDENCE_DIR/job-status-private.json"
    state=$(jq -r 'if (.status.succeeded // 0) > 0 or (.status.failed // 0) > 0 then "done" else "waiting" end' "$EVIDENCE_DIR/job-status-private.json")
    [[ "$state" != waiting ]] && break
    sleep 3
  done
  hoc get pods -n "$PROBE_NS" -o json >"$EVIDENCE_DIR/pods-private.json"
  hoc logs job/native-capability-probe -n "$PROBE_NS" >"$EVIDENCE_DIR/native-result.log" 2>"$EVIDENCE_DIR/native-error.log" || true
  jq -e . "$EVIDENCE_DIR/native-result.log" >/dev/null 2>&1 || fail "Native capability result is not JSON"
  jq -n -e --slurpfile r "$EVIDENCE_DIR/native-result.log" '$r[0] as $r | all("qualified", "capabilities_zero", "no_new_privileges",
    "same_uid_self_protection", "child_core_limit_zero", "landlock_allow_deny", "seccomp_notification", "seccomp_addfd_send", "task_memory_copy",
    "connected_send_fast_path", "socket_virtualization", "socket_loopback_confinement", "dns_relay_bind", "udp_dns_round_trip",
    "tcp_dns_round_trip", "tcp_allow_round_trip", "tcp_deny_round_trip"; $r[.] == true)' >/dev/null || fail "Native capability check failed"
  jq -n -e --slurpfile r "$EVIDENCE_DIR/native-result.log" '$r[0] | .uid > 0 and .gid > 0 and .sandbox_dumpable == false' >/dev/null ||
    fail "Native identity or dumpable state differs"
  jq -n -e --slurpfile r "$EVIDENCE_DIR/native-result.log" '$r[0] | (has("seccomp_listener_mode") or has("wait_killable_recv")
    or has("task_memory_writes_disabled")) | not' >/dev/null || fail "Obsolete native capability schema"
  jq -n -e --slurpfile r "$EVIDENCE_DIR/native-result.log" --slurpfile pods "$EVIDENCE_DIR/pods-private.json" \
    --slurpfile job "$EVIDENCE_DIR/job-status-private.json" --slurpfile desired "$EVIDENCE_DIR/job-private.json" '
    $r[0] as $r | $pods[0].items as $p | $desired[0].spec.template.spec as $d
    | ($p | length) == 1 and $p[0].status.phase == "Succeeded"
    and any($p[0].metadata.ownerReferences[]?; .controller == true and .uid == $job[0].metadata.uid and .name == "native-capability-probe"
      and .kind == "Job" and .apiVersion == "batch/v1")
    and $p[0].metadata.annotations["openshift.io/scc"] == "restricted-v2"
    and $r.uid == $d.securityContext.runAsUser and $r.gid == $d.securityContext.runAsGroup
    and $p[0].spec.securityContext.runAsUser == $r.uid and $p[0].spec.securityContext.runAsGroup == $r.gid
    and $p[0].spec.containers[0].image == $d.containers[0].image
    and $p[0].status.containerStatuses[0].imageID == $d.containers[0].image' >/dev/null || fail "Native probe workload identity differs"
  jq --slurpfile pods "$EVIDENCE_DIR/pods-private.json" --slurpfile pins "$EVIDENCE_DIR/pins.json" '. + {pod_uid: $pods[0].items[0].metadata.uid,
    scc: $pods[0].items[0].metadata.annotations["openshift.io/scc"], image_digest: $pins[0].images.sandbox.amd64Digest,
    source_commit: $pins[0].sourceCommit, scope: "one CPU worker/profile; agent server/auth/controller/cross-pod CNI unqualified"}' \
    "$EVIDENCE_DIR/native-result.log" >"$EVIDENCE_DIR/receipt.json"
  echo "Native host capability PASS; socket loopback confinement verified. Receipt: $EVIDENCE_DIR/receipt.json"
}

# ── Static checks ─────────────────────────────────────────────────────────────────────────────────────────────────
opencode_static() {
  verify_fixture $'def add(a, b):\n    return a + b\n'
  jq -e --arg m "$MODEL" '.permission.bash == "ask" and .permission.webfetch == "deny" and .enabled_providers == ["qwen38"]
    and .provider.qwen38.models[$m].limit.output == 1024 and .agent.build.steps == 4' "$SANDBOXES/opencode/config.json" >/dev/null ||
    fail "Reviewed bounded provider/config differs"
  echo "[OK] Static inputs and independent fixture verifier passed; no cluster or inference calls"
}
hermes_static() {
  verify_fixture $'def add(a,b):\n return a+b\n'
  echo "[OK] Offline Hermes protocol verifier; no cluster/model calls"
}

# ── OpenCode / Hermes run: lock, deadline, receipt on every exit ──────────────────────────────────────────────────
INTERRUPTED=""
q_exit() {
  local rc=$? failure path passed
  set +e
  trap '' INT TERM ALRM
  [[ -z "${WATCHDOG_PID:-}" ]] || kill "$WATCHDOG_PID" 2>/dev/null
  if [[ "$SUITE" == opencode ]]; then opencode_finally; else hermes_finally; fi
  if [[ "$rc" != 0 || -n "$INTERRUPTED" ]]; then
    failure=${INTERRUPTED:-$(cat "$WORK/failure" 2>/dev/null)}
    if [[ "$INTERRUPTED" == "Termination requested" ]]; then
      receipt '.failureClass = "KeyboardInterrupt"'
    elif [[ -n "$failure" ]]; then
      receipt --arg f "$failure" '.failureClass = "RuntimeError" | .failure = $f'
    else
      receipt '.failureClass = "Error"'
    fi
  fi
  receipt --argjson g "$GATES" '.pendingGates = [$g[] as $x | select(.checks[$x] != true) | $x]'
  path="$STATE_DIR/qualification-$(uuid_hex 16).json"
  private_receipt "$path" "$(cat "$WORK/receipt.json")"
  jq -c . "$WORK/receipt.json"
  # Read the verdict before native_cleanup removes $WORK.
  passed=$(jq -r '.passed == true' "$WORK/receipt.json" 2>/dev/null || echo false)
  native_cleanup
  locks_release
  if [[ "$passed" != true ]]; then
    if [[ "$SUITE" == opencode ]]; then
      echo "[FAIL] Qualification incomplete; preserved setup state and retained key" >&2
    else
      echo "[FAIL] Qualification incomplete; owned sandbox/key/state retained" >&2
    fi
    exit 1
  fi
  exit 0
}
run_agent() {
  local mode=$1
  [[ -n "$REVISION" && -n "$PERSONA_HOME" && -n "$PERSONA_KUBECONFIG" ]] || fail "Exact revision and genuine private ai-admin sessions required"
  load_env
  check_oc_logged_in >/dev/null
  [[ -n "${KUBECONFIG:-}" ]] || fail "Set KUBECONFIG to the private bootstrap (cluster-admin) kubeconfig"
  BOOTSTRAP_KUBECONFIG=$KUBECONFIG
  STATE_DIR=${STATE_DIR:-$STATE_ROOT/$SUITE}
  [[ -d "$STATE_DIR" ]] && private_path "$STATE_DIR" || fail "Existing private setup state required"
  lock_take "$STATE_DIR/qualification.lock.d"
  CONFINEMENT_ONLY=false
  if [[ "$SUITE" == opencode ]]; then
    RUN_ID=$(uuid_hex 8)
    DIRECTORY="/sandbox/workspace/qualification-$RUN_ID"
    MARKER="/sandbox/state/opencode-qualification-$RUN_ID"
    GATES=$OC_GATES
    READONLY_MESSAGE="Recovery binding changed; qualification refused"
    jq -n -c --arg f "$DIRECTORY/qualification_add.py" --arg m "$MARKER" --argjson g "$GATES" '{scope: "one synthetic coding task, actual abort and persistent restart; no migration/catalog/tracing claim",
      checks: {}, passed: false, pendingGates: $g, ownedFixture: $f, ownedMarker: $m}' >"$WORK/receipt.json"
  else
    [[ "$mode" == --confinement-only ]] && CONFINEMENT_ONLY=true
    GATES=$HERMES_GATES
    [[ "$CONFINEMENT_ONLY" == true ]] && GATES=$HERMES_CONFINEMENT_GATES
    READONLY_MESSAGE="Setup ownership binding changed"
    jq -n -c --arg m "$MODEL" --argjson c "$CONFINEMENT_ONLY" '{scope: (if $c then "bounded no-model Hermes confinement supplement"
      else "one synthetic native Hermes task, application cancellation and retained history restart" end),
      checks: {}, passed: false, model: $m, modelProvider: "qwen38"}' >"$WORK/receipt.json"
  fi
  trap q_exit EXIT
  trap 'INTERRUPTED="Termination requested"; exit 1' INT TERM
  trap 'INTERRUPTED="Bounded qualification deadline exceeded"; exit 1' ALRM
  (sleep 600; kill -ALRM $$) >/dev/null 2>&1 &
  WATCHDOG_PID=$!
  if [[ "$SUITE" == opencode ]]; then run_opencode; else run_hermes; fi
}

# ── Dispatch ──────────────────────────────────────────────────────────────────────────────────────────────────────
trap native_cleanup EXIT
REVISION="" STATE_DIR="" RECEIPT_FILE="" STATE_ROOT_DIR=$STATE_ROOT MODE=""
PERSONA_HOME=${RHOAI_STAGE060_ADMIN_CLI_HOME:-} PERSONA_KUBECONFIG=${RHOAI_STAGE060_ADMIN_KUBECONFIG:-}
case "$SUITE" in
  host)
    load_env
    check_oc_logged_in
    run_host "$@" ;;
  inference)
    case "${1:-}" in
      --static) [[ $# -eq 1 ]] || usage; inference_static ;;
      --run|--cleanup) [[ $# -eq 2 ]] || usage; load_env; check_oc_logged_in >/dev/null; run_inference "$1" "$2" ;;
      *) usage ;;
    esac ;;
  opencode|hermes|client)
    while [[ $# -gt 0 ]]; do
      case "$1" in
        --static|--run|--check) MODE=$1; shift ;;
        --confinement-only) [[ "$SUITE" == hermes ]] || usage; MODE=$1; shift ;;
        --revision) REVISION=${2:-}; shift 2 ;;
        --state-dir) STATE_DIR=${2:-}; shift 2 ;;
        --state-root) STATE_ROOT_DIR=${2:-}; shift 2 ;;
        --receipt) RECEIPT_FILE=${2:-}; shift 2 ;;
        --persona-home) PERSONA_HOME=${2:-}; shift 2 ;;
        --persona-kubeconfig) PERSONA_KUBECONFIG=${2:-}; shift 2 ;;
        *) usage ;;
      esac
    done
    case "$SUITE:$MODE" in
      opencode:--static) opencode_static ;;
      hermes:--static) hermes_static ;;
      opencode:--run|hermes:--run|hermes:--confinement-only) run_agent "$MODE" ;;
      client:--check)
        [[ -n "$REVISION" && -n "$RECEIPT_FILE" && -n "$PERSONA_HOME" && -n "$PERSONA_KUBECONFIG" ]] || usage
        load_env
        check_oc_logged_in >/dev/null
        [[ -n "${KUBECONFIG:-}" ]] || fail "Set KUBECONFIG to the private bootstrap (cluster-admin) kubeconfig"
        BOOTSTRAP_KUBECONFIG=$KUBECONFIG
        run_client ;;
      *) usage ;;
    esac ;;
  *) usage ;;
esac
