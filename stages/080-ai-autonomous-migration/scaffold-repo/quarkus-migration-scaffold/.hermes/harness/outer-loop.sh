#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Stage 080 OUTER LOOP — drives the full M-process end-to-end:
#   M1 ANALYZE (analyze.sh + architecture-profile session, rubric-gated)
#   M2 SEQUENCE (roadmap + briefs session, roadmap-lint-gated)
#   M3-ALL (O-M3ALL): author/lint EVERY story plan, then whole-set lint,
#           BEFORE any M4 (K1 partition / Port coverage / later-class)
#   per story: M3-JIT re-lint (waterfall antidote; amend→whole-set) +
#              M4/M5 (one supervisor.sh child run with computed story env)
#
# Waterfall antidotes are mandatory (JIT + amend window + delta-as-signal).
# Do not add M3_ALL_SKIP_JIT / WATERFALL_OPTIONAL escape hatches.
#
# The outer loop owns STORY ITERATION and the M1/M2/M3 gates; supervisor.sh
# stays the proven per-story execution engine. Story state persists in
# migration/story-state.csv (committed), so a relaunch resumes cleanly.
#
# Run inside the migration workspace:
#   nohup .hermes/harness/outer-loop.sh >> /tmp/outer-loop.log 2>&1 &
# Progress (single sink):  tail -f /tmp/outer-loop.log
#   (/tmp/outer-loop-nohup.log is unused — L-N1; supervisor: /tmp/supervisor.log)
# ---------------------------------------------------------------------------
set -u
export PATH=$HOME/.opencode/bin:$HOME/.local/bin:$PATH
cd /projects/modernized

# O-PIDREG / O-OCGROUP (F-74 F2/F3)
# shellcheck source=session-registry.sh
. "$(cd "$(dirname "$0")" && pwd)/session-registry.sh"
SUPERVISOR_LOG=/tmp/outer-loop.log

# Same two-writer protection as the supervisor (O-SUPFLOCK / O-OUTERFLOCK).
# F-18: bare pgrep -f matches oc-exec -lc probe text — observer-induced
# refuse-to-start. Hold outer flock for process life; probe supervisor lock
# without keeping it (child supervisor.sh must be able to acquire).
# O-LOCKSTALE: clear lock files whose recorded PID is dead before flock.
clear_stale_pid_lock() { # $1=lockfile
  local lock="$1" pid=""
  [ -f "$lock" ] || return 0
  pid=$(tr -d '[:space:]' <"$lock" 2>/dev/null || true)
  if [[ "$pid" =~ ^[0-9]+$ ]] && ! kill -0 "$pid" 2>/dev/null; then
    rm -f "$lock"
    echo "O-LOCKSTALE cleared pid=${pid} ($lock)" >&2
  fi
}
OUTER_LOCK="${OUTER_LOCK:-/tmp/outer-loop.lock}"
clear_stale_pid_lock "$OUTER_LOCK"
exec 8>"$OUTER_LOCK"
if ! flock -n 8; then
  clear_stale_pid_lock "$OUTER_LOCK"
  exec 8>"$OUTER_LOCK"
  if ! flock -n 8; then
    echo "FATAL: another outer loop holds $OUTER_LOCK — refusing to start" >&2
    exit 1
  fi
fi
printf '%s\n' "$$" >&8
SUPERVISOR_LOCK="${SUPERVISOR_LOCK:-/tmp/supervisor.lock}"
clear_stale_pid_lock "$SUPERVISOR_LOCK"
exec 9>"$SUPERVISOR_LOCK"
if ! flock -n 9; then
  clear_stale_pid_lock "$SUPERVISOR_LOCK"
  exec 9>"$SUPERVISOR_LOCK"
  if ! flock -n 9; then
    echo "FATAL: a supervisor holds $SUPERVISOR_LOCK — refusing to start" >&2
    exit 1
  fi
fi
# Release supervisor lock so the M4 child can take it.
flock -u 9
exec 9>&-

ORCH_PROVIDER="${ORCH_PROVIDER:-custom:maas-m2}"
ORCH_MODEL="${ORCH_MODEL:-minimax-m2}"
WORKER_MODEL="${WORKER_MODEL:-qwen27b/qwen3-6-27b}"
SESSION_TIMEOUT="${SESSION_TIMEOUT:-2700}"
HEARTBEAT_SECS="${OUTER_LOOP_HEARTBEAT_SECS:-60}"
# O-M3ROUTE / O-M3WORKER: M3 SPECIFY open-ended doc draft → MiniMax first
# (Qwen is 0-for-3 on M3; file-level harvest remains worker-first in M4).
# Set WORKER_M3_FIRST=true to restore Qwen-draft + MiniMax backstop.
WORKER_M3_FIRST="${WORKER_M3_FIRST:-false}"
M3_WORKER_ATTEMPTS="${M3_WORKER_ATTEMPTS:-2}"
M3_ORCH_BACKSTOP="${M3_ORCH_BACKSTOP:-2}"
# O-M3ALL: after M2, author all story plans before any M4 (default on).
# Set M3_ALL=0 only for emergency single-story resume diagnostics.
# After whole-set GREEN: freeze-predictions + OPERATOR_GATE (M3_ALL_OPERATOR_AUTO=1
# auto-approves the gate for non-interactive / instrument runs).
M3_ALL="${M3_ALL:-1}"
LOG=/tmp/outer-loop.log
STATE=migration/story-state.csv
HARNESS=.hermes/harness
SKILLDIR=.hermes/skills/migration-harness
# L-P1: OUTER_LOOP_PLAIN=1 for terminals that mangle unicode markers
PLAIN="${OUTER_LOOP_PLAIN:-0}"
# O-PKEXAMPLE: package rename examples from migration.yaml (not Coolstore literals).
LEGACY_PKG=$(python3 -c "import re; t=open('migration.yaml').read(); m=re.search(r'legacyPackage:\s*(\S+)',t); print(m.group(1) if m else 'LEGACY_PKG')" 2>/dev/null || echo LEGACY_PKG)
TARGET_PKG=$(python3 -c "import re; t=open('migration.yaml').read(); m=re.search(r'targetPackage:\s*(\S+)',t); print(m.group(1) if m else 'TARGET_PKG')" 2>/dev/null || echo TARGET_PKG)
PKG_RENAME_HINT="PACKAGE RENAME: full prefix ${LEGACY_PKG}.X → ${TARGET_PKG}.X (from migration.yaml); never invent ${TARGET_PKG}.coolstore or other specimen leftovers."

# Demo-facing model labels (codes alone are not enough — V6 logging notes).
orch_label() {
  case "${ORCH_MODEL}" in
    *minimax*) echo "orchestrator MiniMax M2 (Hermes)" ;;
    *) echo "orchestrator ${ORCH_MODEL} (Hermes)" ;;
  esac
}
worker_label() {
  case "${WORKER_MODEL}" in
    *qwen*) echo "coding worker Qwen3.6 27B (OpenCode)" ;;
    *) echo "coding worker ${WORKER_MODEL} (OpenCode)" ;;
  esac
}

_sym() { # $1=pretty $2=plain
  if [ "$PLAIN" = "1" ]; then echo "$2"; else echo "$1"; fi
}

# O-LOGSTORY: when inside a story loop, prefix every log() line with "SID ▸".
# STORY_TAG is empty for M1/M2 and between stories — do not set at call sites.
STORY_TAG="${STORY_TAG:-}"
log() { echo "[$(date -u +%F' '%T)]${STORY_TAG:+ $STORY_TAG}$([ -n "${STORY_TAG:-}" ] && echo ' ▸') $*" >> "$LOG"; }
phase_start() { # $1=code+title  [$2=extra]
  log "$(_sym '▶' '>') START  $1"
  [ -n "${2:-}" ] && log "         $2"
}
phase_ok() { log "$(_sym '✓' 'OK') END    $1"; }
phase_fail() { log "$(_sym '✗' 'X') FAIL   $1"; }
phase_gate() { # $1=name $2=RED|GREEN $3=detail
  if [ "$2" = "GREEN" ]; then log "$(_sym '✓' 'OK') GATE   $1 — GREEN${3:+ — $3}"
  else log "$(_sym '✗' 'X') GATE   $1 — RED${3:+ — $3}"; fi
}
phase_retry() { log "$(_sym '↻' 'R') RETRY  $1"; }

# O-LOGBRIEF / O-LOGEPILOG — emission-only story banners (wake#376).
# Pure log UX: no control-flow changes. Derive from brief/spec/tasks + git.
_log_rule() { # $1=left text → pad with ═ to ~70 cols
  local left="$1" pad="" i
  i=${#left}
  while [ "$i" -lt 70 ]; do pad="${pad}═"; i=$((i + 1)); done
  log "${left}${pad}"
}

_story_title_human() {
  # Prefer brief H1 "S03: Data Access Layer"; else humanize slug after SID-.
  local t="" slug="${SLUG:-$SID}"
  if [ -n "${BRIEF:-}" ] && [ -f "$BRIEF" ]; then
    t=$(sed -nE 's/^#[[:space:]]*S[0-9]+:[[:space:]]*(.+)$/\1/p' "$BRIEF" | head -1)
  fi
  if [ -z "$t" ] && [ -f "specs/${slug}/spec.md" ]; then
    t=$(sed -nE 's/^#[[:space:]]*S[0-9]+:[[:space:]]*(.+)$/\1/p' "specs/${slug}/spec.md" | head -1)
    [ -n "$t" ] || t=$(sed -nE 's/^#[[:space:]]*(.+)$/\1/p' "specs/${slug}/spec.md" | head -1)
  fi
  if [ -z "$t" ]; then
    t=$(printf '%s' "$slug" | sed -E "s/^${SID}-//; s/-/ /g")
  fi
  printf '%s' "$t"
}

_story_goal_line() {
  # One sentence — brief Goal & position prose, else first task **Goal**, else title.
  # Must not equal the raw slug (instrument + operator ask).
  local slug="${SLUG:-$SID}" goal="" line
  if [ -n "${BRIEF:-}" ] && [ -f "$BRIEF" ]; then
    goal=$(awk '
      BEGIN { in_sec=0 }
      /^## Goal/ { in_sec=1; next }
      /^## / { if (in_sec) exit }
      in_sec && NF && $0 !~ /^<!--/ && $0 !~ /^What this story/ {
        gsub(/^[[:space:]]+|[[:space:]]+$/, ""); print; exit
      }
    ' "$BRIEF")
  fi
  if [ -z "$goal" ] && [ -f "specs/${slug}/spec.md" ]; then
    goal=$(awk '
      NR==1 { next }
      /^## / { if (seen) exit; next }
      NF && $0 !~ /^<!--/ && $0 !~ /^#/ {
        gsub(/^[[:space:]]+|[[:space:]]+$/, ""); print; exit
      }
    ' "specs/${slug}/spec.md")
  fi
  if [ -z "$goal" ] && [ -n "${SPEC_TASKS:-}" ] && [ -f "$SPEC_TASKS" ]; then
    goal=$(sed -nE 's/^\*\*Goal\*\*[[:space:]]*:[[:space:]]*(.+)$/\1/p' "$SPEC_TASKS" | head -1)
  fi
  [ -n "$goal" ] || goal=$(_story_title_human)
  # Guard lazy slug fallback — never emit GOAL equal to slug.
  if [ "$goal" = "$slug" ] || [ "$goal" = "$SID" ]; then
    goal=$(_story_title_human)
  fi
  # Truncate to one readable line.
  line=$(printf '%s' "$goal" | tr '\n' ' ' | sed -E 's/[[:space:]]+/ /g; s/^(.{160}).*/\1…/')
  printf '%s' "$line"
}

_story_done_line() {
  local deploy="${DEPLOY:-false}" done=""
  if [ -n "${BRIEF:-}" ] && [ -f "$BRIEF" ]; then
    done=$(awk '
      BEGIN { in_sec=0 }
      /^## Done-criteria/ { in_sec=1; next }
      /^## / { if (in_sec) exit }
      in_sec && /^- / {
        sub(/^-[[:space:]]*/, "");
        gsub(/^[[:space:]]+|[[:space:]]+$/, "");
        if ($0 !~ /^</ && length($0) > 8) { print; exit }
      }
    ' "$BRIEF")
  fi
  if [ -z "$done" ]; then
    if [ "$deploy" = "true" ]; then
      done="milestone sensor GREEN + factory pipeline green + acceptance path serving"
    else
      done="milestone sensor GREEN + story scope clean of forbidden Spring residue (deploy=false)"
    fi
  fi
  printf '%s' "$done" | tr '\n' ' ' | sed -E 's/[[:space:]]+/ /g; s/^(.{160}).*/\1…/'
}

emit_story_brief() {
  # O-LOGBRIEF: banner after M4/M5 phase_start — GOAL/SCOPE/OWNS/PLAN/PORT/BUDGET/DONE.
  local title goal scope_txt owns_n owns_ids plan_line port_line done_line
  local budget_line="—" budget_n="" kind_s="" inc_s=""
  local tasks_f="${SPEC_TASKS:-}"
  local n_files=0 n_tasks=0 rewrite=0 infer=0
  local create=0 modify=0 remove=0 structure=0 verify=0
  local port_re=0 port_rn=0
  title=$(_story_title_human)
  goal=$(_story_goal_line)
  done_line=$(_story_done_line)
  # O-SEATBUDGET: publish derived/declared budget + arm overrun marker.
  if [ -f migration/roadmap.md ] && [ -f "$HARNESS/seat-budget.py" ]; then
    local inv_f="migration/findings-inventory.md" der=""
    [ -f "$inv_f" ] || inv_f="/dev/null"
    der=$(python3 "$HARNESS/seat-budget.py" from-story \
      migration/roadmap.md "$inv_f" "$SID" 2>/dev/null || true)
    if [ -n "$der" ]; then
      budget_n=$(printf '%s' "$der" | awk -F'\t' '{print $1}')
      kind_s=$(printf '%s' "$der" | sed -nE 's/.*kind=([^[:space:]]+).*/\1/p')
      inc_s=$(printf '%s' "$der" | sed -nE 's/.*incidents=([0-9]+).*/\1/p')
      budget_line="${budget_n} seats (kind=${kind_s} × incidents=${inc_s} / unit=${SEAT_BUDGET_INCIDENTS_PER_UNIT:-10}; over@${SEAT_BUDGET_OVER_FACTOR:-2}×)"
      printf '%s\n' "$budget_n" > "/tmp/story-seat-budget-${SID}"
    fi
  fi
  if [ -z "$budget_n" ] && [ -f migration/roadmap.md ]; then
    budget_n=$(awk -v sid="$SID" '
      $0 ~ "^## "sid {p=1; next}
      p && /^## / {exit}
      p && /^- seat-budget:/ {
        sub(/^- seat-budget:[[:space:]]*/, ""); print; exit
      }
    ' migration/roadmap.md)
    if [ -n "$budget_n" ]; then
      budget_line="${budget_n} seats (roadmap seat-budget)"
      printf '%s\n' "$budget_n" > "/tmp/story-seat-budget-${SID}"
    fi
  fi
  if [ -n "$SCOPE" ]; then
    n_files=$(printf '%s' "$SCOPE" | tr ', ' '\n' | grep -c . || true)
  fi
  scope_txt="${SCOPE:-—}"
  [ "${#scope_txt}" -gt 90 ] && scope_txt="${scope_txt:0:87}…"
  scope_txt="${scope_txt} — ${n_files} paths · deploy=${DEPLOY:-false}"
  owns_ids="${FINDINGS:-}"
  owns_n=$(printf '%s' "$owns_ids" | tr ', ' '\n' | grep -c . || true)
  if [ -n "$tasks_f" ] && [ -f "$tasks_f" ]; then
    eval "$(python3 - "$tasks_f" <<'PY'
import re, sys
text = open(sys.argv[1], encoding="utf-8", errors="replace").read()
tasks = re.findall(r"(?m)^####\s+(T-\d+):", text)
rewrite = len(re.findall(r"(?im)^\*\*Class\*\*\s*:\s*rewrite\b", text))
infer = len(re.findall(r"(?im)^\*\*Class\*\*\s*:\s*infer\b", text))
shapes = {k: len(re.findall(rf"(?im)^\*\*Shape\*\*\s*:\s*{k}\b", text))
          for k in ("create", "modify", "remove", "structure", "verify")}
port_re = len(re.findall(r"(?im)^\*\*Port\*\*\s*:\s*reimplement\b", text))
port_rn = len(re.findall(r"(?im)^\*\*Port\*\*\s*:\s*rename\b", text))
print(f"n_tasks={len(tasks)}")
print(f"rewrite={rewrite}")
print(f"infer={infer}")
for k, v in shapes.items():
    print(f"{k}={v}")
print(f"port_re={port_re}")
print(f"port_rn={port_rn}")
PY
)"
    plan_line="${n_tasks:-0} tasks · class: ${rewrite} rewrite ${infer} infer · shape: ${create} create ${modify} modify ${remove} remove ${structure} structure ${verify} verify"
    port_line="${port_re} reimplement · ${port_rn} rename"
  else
    plan_line="tasks.md missing — plan counts unavailable"
    port_line="—"
  fi
  _log_rule "══ ${SID} (${STORY_IDX}/${STORY_COUNT}) — ${title} "
  log "${SID} GOAL    ${goal}"
  log "${SID} SCOPE   ${scope_txt}"
  log "${SID} OWNS    ${owns_n} findings — $(printf '%s' "$owns_ids" | tr ',' '/' | tr -d ' ')"
  [ -n "$owns_ids" ] && log "${SID} OWNS    ids: ${owns_ids}"
  log "${SID} PLAN    ${plan_line}"
  log "${SID} PORT    ${port_line}"
  log "${SID} BUDGET  ${budget_line}"
  log "${SID} DONE    when ${done_line}"
}

_fmt_duration() { # $1=seconds
  local s="${1:-0}" h m
  [ "$s" -lt 0 ] && s=0
  h=$((s / 3600)); m=$(((s % 3600) / 60))
  if [ "$h" -gt 0 ]; then printf '%dh%02dm' "$h" "$m"
  else printf '%dm' "$m"; fi
}

emit_story_epilog() { # $1=outcome label (complete|debt-freeze|failed|…)
  # O-LOGEPILOG: measured end-of-story summary — RESULT/CODE/TESTS/FIND/COST/HEAD.
  local outcome="${1:-complete}" elapsed=0 dur title
  local total=0 shipped=0 debt_note="" shortstat="" java_now=0
  local tests_now=0 asserts_now=0 seats=0 seats_w=0 seats_e=0
  local sensor_red=0 sfix_n=0 m3_rev=0
  local owned_n=0 head_s find_line
  local base="${STORY_RUN_BASE:-}"
  title=$(_story_title_human)
  if [ -n "${STORY_T0:-}" ]; then
    elapsed=$(( $(date -u +%s) - STORY_T0 ))
  fi
  dur=$(_fmt_duration "$elapsed")
  head_s=$(git rev-parse --short HEAD 2>/dev/null || echo unknown)
  if [ -n "${SPEC_TASKS:-}" ] && [ -f "$SPEC_TASKS" ]; then
    total=$(grep -cE '^#### T-[0-9]+' "$SPEC_TASKS" 2>/dev/null || echo 0)
  fi
  if [ -n "$base" ]; then
    shipped=$(git log --oneline "${base}..HEAD" 2>/dev/null \
      | grep -cE '^[0-9a-f]+ T-[0-9]+:' || true)
    shortstat=$(git diff --shortstat "${base}..HEAD" 2>/dev/null \
      | sed -E 's/^ *//' || true)
  fi
  [ -n "$shortstat" ] || shortstat="no delta"
  java_now=$(find src/main -name '*.java' 2>/dev/null | wc -l | tr -d ' ')
  tests_now=$(grep -RInE '@Test\b' src/test 2>/dev/null | wc -l | tr -d ' ')
  asserts_now=$(grep -RInE 'assert[A-Z(]|assertThat\(' src/test 2>/dev/null | wc -l | tr -d ' ')
  # COST seats = story-keyed OpenCode JSON files (claimed→measured).
  seats=$(ls /tmp/oc-"${SID}"-*.json 2>/dev/null | wc -l | tr -d ' ')
  seats_e=$(ls /tmp/oc-"${SID}"-*.json 2>/dev/null \
    | xargs -n1 basename 2>/dev/null \
    | grep -ciE 'escalat|minimax|orch' || true)
  if [ "$seats" -gt "$seats_e" ]; then seats_w=$((seats - seats_e)); else seats_w=0; fi
  if [ -f /tmp/supervisor.log ]; then
    sensor_red=$(grep -cE "SENSOR RED|milestone sensor RED|task sensor RED" /tmp/supervisor.log 2>/dev/null || true)
    sfix_n=$(grep -cE 'sensor-fix|sfix dispatch|SFIX' /tmp/supervisor.log 2>/dev/null || true)
  fi
  if [ -n "$base" ]; then
    m3_rev=$(git log --oneline "${base}..HEAD" 2>/dev/null | grep -cE "${SID} spec:" || true)
  else
    m3_rev=$(git log --oneline -20 2>/dev/null | grep -cE "${SID} spec:" || true)
  fi
  owned_n=$(printf '%s' "${FINDINGS:-}" | tr ', ' '\n' | grep -c . || true)
  if [ -f migration/debt.md ] && grep -qE "${SID}|T-[0-9]+" migration/debt.md 2>/dev/null; then
    debt_note=$(grep -oE 'T-[0-9]+' migration/debt.md 2>/dev/null | head -1 || true)
    [ -n "$debt_note" ] && debt_note=" · ${debt_note} → migration/debt.md"
  fi
  find_line="${owned_n} owned"
  case "$outcome" in
    success*|story-gate-passed*|complete*) find_line="${owned_n} owned → resolved (story complete)" ;;
    debt-freeze*) find_line="${owned_n} owned · debt-freeze (see migration/debt.md)" ;;
    *) find_line="${owned_n} owned · outcome=${outcome}" ;;
  esac
  _log_rule "══ ${SID} ${outcome} — ${dur} "
  log "${SID} RESULT  ${shipped}/${total} tasks shipped${debt_note}"
  log "${SID} CODE    ${shortstat} · src/main .java=${java_now}"
  log "${SID} TESTS   @Test ${tests_now} · asserts ${asserts_now}"
  log "${SID} FIND    ${find_line}"
  log "${SID} COST    ${seats} seats (${seats_w} worker · ${seats_e} escalation) · ${sensor_red} sensor RED · ${sfix_n} sfix · ${m3_rev} M3 revisions"
  log "${SID} HEAD    ${head_s}"
}

# Bounded session runner for the M1/M2/M3 authoring gates. Simpler than
# the supervisor's classifier on purpose: these are single-artifact
# sessions with deterministic lints behind them — one attempt plus one
# retry, then the loop stops and reports (a defective plan must never
# reach execution ungated).
# Logs Actor + sparse heartbeats; session rc ≠ gate success (V6 notes).
_outer_heartbeat_start() { # $1=title $2=t0 $3=slog $4=kind → sets hb_pid
  local title="$1" t0="$2" slog="$3" kind="${4:-orchestrator}"
  cat > /tmp/outer-loop-heartbeat.sh <<'HBEOF'
#!/usr/bin/env bash
# outer-loop-heartbeat — not the outer loop itself
SECS="${1:-60}"; TITLE="${2:-session}"; T0="${3:-0}"; SLOG="${4:-/tmp/outer.log}"; LOG="${5:-/tmp/outer-loop.log}"; KIND="${6:-orchestrator}"
while true; do
  sleep "$SECS"
  now=$(date +%s); elapsed=$((now - T0))
  if [ "$KIND" = "orchestrator" ] && grep -qE "429|Too Many Requests|Rate limit|rate.?limit" "$SLOG" 2>/dev/null; then
    echo "[$(date -u +%F' '%T)] …        ${TITLE} waiting on MiniMax rate limit (${elapsed}s) — details ${SLOG}" >> "$LOG"
  else
    echo "[$(date -u +%F' '%T)] …        ${TITLE} still working on ${KIND} (${elapsed}s) — details ${SLOG}" >> "$LOG"
  fi
done
HBEOF
  chmod +x /tmp/outer-loop-heartbeat.sh
  /tmp/outer-loop-heartbeat.sh "$HEARTBEAT_SECS" "$title" "$t0" "$slog" "$LOG" "$kind" &
  hb_pid=$!
}

mchat() { # $1=tag $2=prompt [$3=phase title for heartbeats]
  local tag="$1" prompt="$2" title="${3:-$1}" t0 now rc hb_pid slog wpid
  t0=$(date +%s)
  slog="/tmp/outer-${tag}.log"
  log "         Actor: $(orch_label) — session ${tag} → ${slog}"
  _outer_heartbeat_start "$title" "$t0" "$slog" orchestrator
  setsid timeout "$SESSION_TIMEOUT" hermes chat --provider "$ORCH_PROVIDER" --model "$ORCH_MODEL" -q "$prompt" \
    < /dev/null > "$slog" 2>&1 &
  wpid=$!
  session_register "$tag" "$wpid"
  wait "$wpid"
  rc=$?
  session_reap_group "$tag" "$wpid" "session-end"
  kill "$hb_pid" 2>/dev/null || true
  wait "$hb_pid" 2>/dev/null || true
  now=$(date +%s)
  if grep -qE "429|Too Many Requests|Rate limit|rate.?limit" "$slog" 2>/dev/null; then
    # O-ORCH429BACKOFF / O-M2-429: do not claim a backoff here — callers
    # (M2/M3) must NOT-spend + sleep themselves (session≠gate).
    log "         ${title}: MiniMax rate limit seen in session log (hermes_rc=${rc}) — caller must NOT-spend + backoff"
  fi
  log "·        ${title} session finished ($((now - t0))s, hermes_rc=${rc}) — checking gate next (session≠gate)"
  return $rc
}

# O-M3QWENSTALL: OpenCode JSON log has write/edit tools (not bash/read-only).
_m3_log_has_write() {
  local slog="$1"
  [ -f "$slog" ] || return 1
  grep -qE '"tool"\s*:\s*"(edit|write|Write|Edit)"' "$slog" 2>/dev/null \
    || grep -qE '"name"\s*:\s*"(edit|write|Write|Edit)"' "$slog" 2>/dev/null
}

# O-M3WORKER: OpenCode/Qwen seat for M3 SPECIFY (plan-lint gated).
# O-M3EMPTY: set M3_EXPECT_TASKS=specs/<slug>/tasks.md before wchat; if still
# missing after M3_EMPTY_ABORT_SECS (default 360), abort the seat and return 1
# so the attempt is spent (unlike O-M3KILL 137/143).
# O-M3QWENSTALL: M3_STALL_ABORT_SECS (default 120) kills read-only seats with
# no tasks.md and zero write/edit tools — before burning a second 360s worker.
wchat() { # $1=tag $2=prompt [$3=phase title] [$4=extra -f file ...]
  local tag="$1" prompt="$2" title="${3:-$1}" t0 now rc hb_pid slog tp watch_pid stall_pid
  shift 3 || true
  t0=$(date +%s)
  slog="/tmp/outer-${tag}.log"
  rm -f "/tmp/m3-empty-abort-${tag}"
  log "         Actor: $(worker_label) — session ${tag} → ${slog}"
  _outer_heartbeat_start "$title" "$t0" "$slog" worker
  # O-PIDREG/O-OCGROUP: setsid + register; group-TERM reaps serve children.
  # shellcheck disable=SC2086
  setsid timeout "$SESSION_TIMEOUT" opencode run "$prompt" \
    -m "$WORKER_MODEL" --auto --format json \
    -f AGENTS.md \
    -f "${SKILLDIR}/PLANNING.md" \
    "$@" \
    < /dev/null > "$slog" 2>&1 &
  tp=$!
  session_register "$tag" "$tp"
  watch_pid=""
  stall_pid=""
  if [ -n "${M3_EXPECT_TASKS:-}" ]; then
    (
      # O-M3QWENSTALL: read-thrash with zero writes — abort at 120s default.
      # Preseeded skeleton still counts as stalled until worker writes/edits
      # (or replaces the O-M3QWENSTALL preseed marker).
      stall_s="${M3_STALL_ABORT_SECS:-120}"
      step=15
      elapsed=0
      _m3_tasks_real() {
        [ -f "$M3_EXPECT_TASKS" ] || return 1
        ! grep -q 'O-M3QWENSTALL preseed' "$M3_EXPECT_TASKS" 2>/dev/null
      }
      while [ "$elapsed" -lt "$stall_s" ]; do
        sleep "$step"
        elapsed=$((elapsed + step))
        _m3_tasks_real && exit 0
        _m3_log_has_write "$slog" && exit 0
      done
      if ! _m3_tasks_real && ! _m3_log_has_write "$slog"; then
        echo "[$(date -u +%F' '%T)]          O-M3QWENSTALL: abort — no real tasks.md mutate, 0 writes after ${stall_s}s" >> "$LOG"
        touch "/tmp/m3-empty-abort-${tag}"
        kill "$tp" 2>/dev/null || true
      fi
    ) &
    stall_pid=$!
    (
      # O-M3EMPTY: final backstop when tasks.md never lands (or stays preseed)
      abort_s="${M3_EMPTY_ABORT_SECS:-360}"
      sleep "$abort_s"
      if [ ! -f "$M3_EXPECT_TASKS" ] \
        || grep -q 'O-M3QWENSTALL preseed' "$M3_EXPECT_TASKS" 2>/dev/null; then
        echo "[$(date -u +%F' '%T)]          O-M3EMPTY: abort — ${M3_EXPECT_TASKS} missing/preseed after ${abort_s}s" >> "$LOG"
        touch "/tmp/m3-empty-abort-${tag}"
        kill "$tp" 2>/dev/null || true
      fi
    ) &
    watch_pid=$!
  fi
  wait "$tp"
  rc=$?
  session_reap_group "$tag" "$tp" "session-end"
  if [ -n "$stall_pid" ]; then
    kill "$stall_pid" 2>/dev/null || true
    wait "$stall_pid" 2>/dev/null || true
  fi
  if [ -n "$watch_pid" ]; then
    kill "$watch_pid" 2>/dev/null || true
    wait "$watch_pid" 2>/dev/null || true
  fi
  if [ -f "/tmp/m3-empty-abort-${tag}" ]; then
    rc=1
  fi
  kill "$hb_pid" 2>/dev/null || true
  wait "$hb_pid" 2>/dev/null || true
  now=$(date +%s)
  log "·        ${title} session finished ($((now - t0))s, worker_rc=${rc}) — checking gate next (session≠gate)"
  return $rc
}

# O-TMPARCHIVE: PVC-side copy of forensic /tmp (success AND fail — W4-029b).
# EXIT trap so debt-freeze / X FAIL / signal paths archive before /tmp recycle.
_TMPARCHIVE_DONE=0
archive_tmp_forensics() {
  [ "${_TMPARCHIVE_DONE:-0}" = "1" ] && return 0
  _TMPARCHIVE_DONE=1
  local _arch_root _arch
  _arch_root="${RUN_ARCHIVE_ROOT:-/projects/modernized/migration/run-archives}"
  _arch="${_arch_root}/$(date -u +%Y%m%dT%H%M%SZ)-$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
  mkdir -p "$_arch" 2>/dev/null || true
  if [ -d "$_arch" ]; then
    shopt -s nullglob
    for p in \
      /tmp/supervisor.log /tmp/outer-loop.log /tmp/kill-ledger.log \
      /tmp/findings-delta.txt /tmp/outer-git-push.log \
      /tmp/escalation-cause-*.txt /tmp/oc-*.json /tmp/oc-*.err \
      /tmp/sensor-*.log /tmp/sonar-violations.txt
    do
      cp -a "$p" "$_arch/" 2>/dev/null || true
    done
    shopt -u nullglob
    printf 'head=%s\narchived_at=%s\n' \
      "$(git rev-parse HEAD 2>/dev/null || true)" \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$_arch/ARCHIVE.txt" 2>/dev/null || true
    if declare -F log >/dev/null 2>&1; then
      log "O-TMPARCHIVE — forensic /tmp → ${_arch}"
    else
      echo "[$(date -u +%F' '%T)] O-TMPARCHIVE — forensic /tmp → ${_arch}" >> /tmp/outer-loop.log 2>/dev/null || true
    fi
  elif declare -F log >/dev/null 2>&1; then
    log "WARN: O-TMPARCHIVE — could not create ${_arch}"
  fi
}
trap 'archive_tmp_forensics' EXIT

fail_run() { phase_fail "$1"; echo "outer-failed: $1" > /tmp/outer-loop-done; exit 1; }

# O-UXLOG-TRUNC (Poll 77 U1): never wipe the demo narrative on relaunch.
# Append; rotate only when the file is huge (~5 MiB).
if [ -s "$LOG" ]; then
  _log_sz=$(wc -c <"$LOG" 2>/dev/null | tr -d ' ' || echo 0)
  if [ "${_log_sz:-0}" -gt 5000000 ]; then
    mv "$LOG" "${LOG}.prev.$(date -u +%Y%m%dT%H%M%SZ)" 2>/dev/null || true
  fi
  {
    echo ""
    echo "[$(date -u +%F' '%T)] ——— RESUME outer-loop (append; prior narrative preserved) ———"
  } >> "$LOG"
else
  : > "$LOG"
fi
phase_start "Outer loop — autonomous migration" \
  "Models: $(orch_label) · $(worker_label) | progress: $LOG | resume: $STATE"

# O-STAMP-AUTO: derive migration.yaml from legacy tree before M1 ground truth.
LEGACY_ROOT="${LEGACY_ROOT:-/projects/legacy}"
if [ -d "$LEGACY_ROOT" ]; then
  phase_start "M1 contract stamp — auto-derived specimen contract (O-STAMP-AUTO)"
  if python3 "$HARNESS/contract-stamp.py" stamp --legacy "$LEGACY_ROOT" --yaml migration.yaml --write \
      >> "$LOG" 2>&1; then
    if git diff --quiet migration.yaml 2>/dev/null; then
      log "         contract-stamp: migration.yaml already current"
    else
      git add migration.yaml
      if git commit -m "M1 contract: auto-derived specimen stamp" >> "$LOG" 2>&1; then
        log "         contract-stamp: committed migration.yaml"
      else
        log "         contract-stamp: migration.yaml updated (commit skipped — review tree)"
      fi
    fi
  else
    fail_run "M1 contract stamp — contract-stamp.py failed (see $LOG)"
  fi
  if ! python3 "$HARNESS/contract-stamp-gate.py" --legacy "$LEGACY_ROOT" --yaml migration.yaml >> "$LOG" 2>&1; then
    fail_run "M1 contract stamp gate — O-STAMP-GATE RED (see $LOG)"
  fi
  phase_ok "M1 contract stamp — O-STAMP-GATE GREEN"
else
  log "WARN: LEGACY_ROOT $LEGACY_ROOT missing — skipping O-STAMP-AUTO"
fi

# ------------------------------------------------------------- M1 ANALYZE
phase_start "M1 ANALYZE — establish migration ground truth (MTA + recipes)" \
  "Actor: harness scripts (no LLM)"
if [ -f migration/mta-findings.json ]; then
  phase_ok "M1 ANALYZE — ground truth already present"
else
  "$HARNESS/analyze.sh" > /tmp/outer-m1-analyze.log 2>&1 \
    || fail_run "M1 ANALYZE — ground truth unavailable (see /tmp/outer-m1-analyze.log)"
  # L-D1: enumerate key M1 deliverables
  log "         • migration/mta-findings.json (+ findings-inventory.md, dependency-order.md, recipe-log.md)"
  [ -d migration/staging ] && log "         • migration/staging/ ($(find migration/staging -type f 2>/dev/null | wc -l | tr -d ' ') files)"
  phase_ok "M1 ANALYZE — ground truth ready (details /tmp/outer-m1-analyze.log; HEAD $(git rev-parse --short HEAD 2>/dev/null || echo ?))"
fi

if [ -f migration/architecture-profile.md ]; then
  phase_ok "M1 PROFILE — architecture-profile.md already present"
else
  for ATTEMPT in 1 2; do
    phase_start "M1 PROFILE — architecture profile (class roles & target contract) [attempt ${ATTEMPT}/2]"
    mchat "m1-profile-a${ATTEMPT}" \
"Use the migration-harness skill and read ANALYSIS.md in its directory. The analysis bundle is committed (migration/mta-findings.json, findings-inventory.md, dependency-order.md, recipe-log.md). Execute the M1 profile step ONLY: read the legacy code under /projects/legacy and write migration/architecture-profile.md per ANALYSIS.md. A deterministic rubric gates it — verify yourself with: python3 ${HARNESS}/profile-rubric.py migration/architecture-profile.md /projects/legacy (must exit 0 — it cross-checks that every CDI/JAX-RS class is classified REDESIGN in section 7) BEFORE committing. Finish with ONE commit whose message STARTS with 'M1 profile:'. DO NOT PUSH. Keep the session packet tight — cite legacy paths; do not paste whole files into the profile (O-CTX)." \
      "M1 PROFILE"
    if [ -f migration/architecture-profile.md ] && python3 "$HARNESS/profile-rubric.py" migration/architecture-profile.md /projects/legacy > /tmp/profile-rubric.txt 2>&1; then
      # Mechanical closure: commit if the session forgot.
      [ -n "$(git status --porcelain migration/)" ] && git add migration/ && git commit -q -m "M1 profile: outer-loop mechanical commit of rubric-green profile" 2>/dev/null
      phase_gate "M1 PROFILE rubric" GREEN "architecture-profile.md; commit $(git rev-parse --short HEAD)"
      log "         • migration/architecture-profile.md (§7 class roles + target contract)"
      phase_ok "M1 PROFILE — architecture-profile.md rubric-green; commit $(git rev-parse --short HEAD)"
      break
    fi
    phase_gate "M1 PROFILE rubric" RED "see /tmp/profile-rubric.txt"
    [ "$ATTEMPT" = "2" ] && fail_run "M1 PROFILE failed the rubric twice"
    phase_retry "M1 PROFILE — bouncing once"
    git checkout -q -- migration/ 2>/dev/null || true
  done
fi

# ------------------------------------------------------------ M2 SEQUENCE
# O-M2-429 / O-ORCH429BACKOFF: real backoff when MiniMax 429s mid-seat
# (default 900s). Override M2_429_BACKOFF_SECS for instruments.
M2_429_BACKOFF_SECS="${M2_429_BACKOFF_SECS:-900}"
M2_COMPOSE="${M2_COMPOSE:-1}"
roadmap_green() {
  # O-PORTDERIVE: pass architecture-profile.md so §7 REDESIGN ↔ brief contract is gated
  [ -f migration/roadmap.md ] && python3 "$HARNESS/roadmap-lint.py" migration/roadmap.md migration/findings-inventory.md /projects/legacy migration/architecture-profile.md > /tmp/roadmap-lint.txt 2>&1
}
m2_compose_bookkeeping() {
  # O-M2COMPOSE: deterministic partition + seat-budget + brief stubs + K3 rows
  [ "${M2_COMPOSE}" = "1" ] || return 0
  [ -f "$HARNESS/m2-compose.py" ] || return 0
  local mode="${1:-fill}"
  if python3 "$HARNESS/m2-compose.py" --root . --mode "$mode" \
      > /tmp/m2-compose.txt 2>&1; then
    log "         O-M2COMPOSE ${mode}: $(tail -1 /tmp/m2-compose.txt 2>/dev/null || true)"
    return 0
  fi
  log "         O-M2COMPOSE ${mode} RED — see /tmp/m2-compose.txt"
  return 1
}
if roadmap_green; then
  phase_ok "M2 SEQUENCE — roadmap already present and lint-green"
else
  # O-M2COMPOSE skeleton-first: unique-owner partition + brief stubs before seat
  if [ "${M2_COMPOSE}" = "1" ] && [ ! -f migration/roadmap.md ]; then
    phase_start "M2 SEQUENCE — skeleton-first compose (O-M2COMPOSE)"
    if m2_compose_bookkeeping skeleton; then
      phase_gate "M2 SEQUENCE compose" GREEN "$(tail -1 /tmp/m2-compose.txt 2>/dev/null || true)"
    else
      phase_gate "M2 SEQUENCE compose" RED "see /tmp/m2-compose.txt"
      fail_run "O-M2COMPOSE skeleton-first RED (see /tmp/m2-compose.txt)"
    fi
  elif [ "${M2_COMPOSE}" = "1" ] && [ -f migration/roadmap.md ]; then
    # Refresh bookkeeping on a partial/prior RED roadmap before the seat
    m2_compose_bookkeeping fill || true
  fi
  ATTEMPT=1
  M2_MAX_ATTEMPTS=2
  # O-M2RETRYINLINE: bound inlined lint so the retry prompt stays usable.
  M2_RETRY_LINT_LINES="${M2_RETRY_LINT_LINES:-80}"
  M2_RETRY_LINT_BYTES="${M2_RETRY_LINT_BYTES:-8000}"
  while [ "$ATTEMPT" -le "$M2_MAX_ATTEMPTS" ]; do
    phase_start "M2 SEQUENCE — cut migration into dependency-ordered stories [attempt ${ATTEMPT}/${M2_MAX_ATTEMPTS}]"
    P="Use the migration-harness skill and read SEQUENCING.md and BRIEF-TEMPLATE.md in its directory. M1 is committed. Execute M2 ONLY: read migration/architecture-profile.md, migration/dependency-order.md, migration/findings-inventory.md and migration.yaml, then write migration/roadmap.md plus one brief per story under migration/briefs/ exactly per SEQUENCING.md. A deterministic m2-compose.py pass already seeded unique-owner findings partition, brief section stubs, non-mandatory decision rows, last-story deploy, and computed seat-budget when kind is set (O-M2COMPOSE) — do NOT re-arithmetic seat-budget (publish the compose/lint value) and do NOT dual-own or claim recipe-executed findings. Each brief carries its classes' roles and, for REDESIGN classes, their target contract from architecture-profile section 7 (SEQUENCING.md 'One quality model'). Declare story kind: rename|reimplement|mixed when findings include OPEN DESIGN or scope names a §7 REDESIGN class (O-STORYKIND). Every 'In scope' code quote is the REAL legacy code — quote it from /projects/legacy, never invent methods or annotations the class does not have (the lint cross-checks each quoted method/annotation against the legacy source). Story scope must list real code/test paths (no ceremonial name-only scopes). A deterministic lint gates the result — verify yourself with: python3 ${HARNESS}/roadmap-lint.py migration/roadmap.md migration/findings-inventory.md /projects/legacy migration/architecture-profile.md (must exit 0; LINT:O-PORTDERIVE = brief must carry REDESIGN target contract from profile §7; LINT:O-SEATBUDGET = seat-budget must match kind×incidents) BEFORE committing. Finish with ONE commit whose message STARTS with 'M2 sequence:'. DO NOT PUSH. ${PKG_RENAME_HINT}"
    if [ "$ATTEMPT" -gt 1 ]; then
      # O-M2RETRYINLINE: put bounded lint in the prompt — do not rely on the
      # seat re-reading /tmp/roadmap-lint.txt (v3 death mode / path-only miss).
      _lint_inline=""
      if [ -f /tmp/roadmap-lint.txt ]; then
        _lint_inline="$(
          head -c "${M2_RETRY_LINT_BYTES}" /tmp/roadmap-lint.txt \
            | head -n "${M2_RETRY_LINT_LINES}"
        )"
      fi
      [ -n "${_lint_inline}" ] || _lint_inline="(roadmap-lint.txt empty or missing — re-run roadmap-lint.py locally)"
      P="Use the migration-harness skill and read SEQUENCING.md in its directory. A previous M2 attempt failed its lint. O-M2RETRYINLINE — fix EVERY line below (inlined; do not skip by skipping a file read):
---BEGIN ROADMAP-LINT---
${_lint_inline}
---END ROADMAP-LINT---
(Full output also at /tmp/roadmap-lint.txt if truncated.) LINT:fabrication = quote real legacy methods/annotations only. LINT:coverage dual-owner / orphan = each mandatory finding in exactly one story; remove duplicate claims and out-of-place scope paths. LINT:substance ceremonial = every story scope lists real code/test paths. LINT:deploy = last story deploy=true. LINT:O-PORTDERIVE = brief must name REDESIGN classes with target contracts from architecture-profile §7. LINT:O-STORYKIND = OPEN DESIGN / §7 REDESIGN stories must declare kind: rename|reimplement|mixed (mixed needs split/justification). LINT:O-SEATBUDGET = seat-budget must equal kind×incidents (publish same N in brief; m2-compose fill will rewrite the arithmetic). Fix every lint finding in migration/roadmap.md and the briefs, verify python3 ${HARNESS}/roadmap-lint.py migration/roadmap.md migration/findings-inventory.md /projects/legacy migration/architecture-profile.md exits 0, and commit with prefix 'M2 sequence:'. DO NOT PUSH. ${PKG_RENAME_HINT}"
    fi
    mchat "m2-sequence-a${ATTEMPT}" "$P" "M2 SEQUENCE"
    # O-M2COMPOSE fill after seat — kill coverage/briefs/deploy/seat-budget bookkeeping
    m2_compose_bookkeeping fill || true
    if roadmap_green; then
      [ -n "$(git status --porcelain migration/)" ] && git add migration/ && git commit -q -m "M2 sequence: outer-loop mechanical commit of lint-green roadmap" 2>/dev/null
      phase_gate "M2 SEQUENCE roadmap-lint" GREEN "commit $(git rev-parse --short HEAD)"
      # O-EVIDLIVE / K3: roadmap adopt/defer exercised — seed per-story ledger rows.
      if [ -f "$HARNESS/evidence-liveness.sh" ] && [ -f migration/roadmap.md ]; then
        _k3n=$(grep -cE '(: defer|: adopt|defer \([^\)]+\)|: *defer|: *adopt)' migration/roadmap.md 2>/dev/null || true)
        _k3n=${_k3n:-0}
        if [ "${_k3n:-0}" -gt 0 ] 2>/dev/null; then
          for _sid in $(grep -E '^## S[0-9]+' migration/roadmap.md | sed -E 's/^## (S[0-9]+).*/\1/'); do
            bash "$HARNESS/evidence-liveness.sh" record "$_sid" K3 "$_k3n" "roadmap-lint GREEN adopt/defer" \
              >> "$LOG" 2>&1 || true
          done
        fi
      fi
      # Name concrete briefs for the demo log.
      log "         • migration/roadmap.md ($(grep -cE '^## S[0-9]' migration/roadmap.md 2>/dev/null || echo 0) stories)"
      for b in migration/briefs/S*.md; do
        [ -f "$b" ] && log "         • $(basename "$b" .md) brief generated"
      done
      phase_ok "M2 SEQUENCE — roadmap + briefs lint-green; commit $(git rev-parse --short HEAD)"
      break
    fi
    # O-M2-429: hermes_rc=0 after rate-limit is NOT seat success — do not burn attempt
    if grep -qE "429|Too Many Requests|Rate limit|rate.?limit" \
        "/tmp/outer-m2-sequence-a${ATTEMPT}.log" 2>/dev/null; then
      log "         O-M2-429: MiniMax rate-limited — attempt ${ATTEMPT} NOT spent; backoff ${M2_429_BACKOFF_SECS}s"
      phase_retry "M2 SEQUENCE — quota; sleeping ${M2_429_BACKOFF_SECS}s (O-M2-429)"
      sleep "${M2_429_BACKOFF_SECS}"
      continue
    fi
    phase_gate "M2 SEQUENCE roadmap-lint" RED "full findings /tmp/roadmap-lint.txt"
    [ "$ATTEMPT" -ge "$M2_MAX_ATTEMPTS" ] && fail_run "M2 SEQUENCE failed its lint twice"
    ATTEMPT=$((ATTEMPT + 1))
    phase_retry "M2 SEQUENCE — bouncing once"
  done
fi

# ---------------------------------------------------------- story loop
[ -f "$STATE" ] || { echo "story,outcome,epoch" > "$STATE"; git add "$STATE"; git commit -q -m "Outer loop: story state ledger" 2>/dev/null || true; }
story_done() { grep -q "^$1,complete" "$STATE" 2>/dev/null; }

STORIES=$(python3 "$HARNESS/parse-roadmap.py" migration/roadmap.md)
[ -n "$STORIES" ] || fail_run "roadmap parsed to zero stories"
STORY_IDS=$(echo "$STORIES" | cut -d'|' -f1 | tr '\n' ' ')
STORY_COUNT=$(echo "$STORIES" | grep -c . || echo 0)
# O-UXLOG-TRUNC: resume banner with ledger progress (demo-facing).
DONE_N=$(awk -F, '$2=="complete"{n++} END{print n+0}' "$STATE" 2>/dev/null || echo 0)
if [ "${DONE_N:-0}" -gt 0 ]; then
  DONE_LIST=$(awk -F, '$2=="complete"{printf "%s ",$1}' "$STATE" 2>/dev/null)
  log "         Resuming: ${DONE_N} of ${STORY_COUNT} stories complete (${DONE_LIST})— continuing at next incomplete"
fi
# O-M3ALL: two-pass story loop — (1) author all plans + whole-set lint,
# then (2) JIT re-lint + M4/M5. Waterfall antidotes stay mandatory.
M3_ALL_PASSES="author execute"
[ "${M3_ALL}" = "1" ] || M3_ALL_PASSES="execute"

for M3_ALL_PASS in $M3_ALL_PASSES; do
if [ "$M3_ALL_PASS" = "author" ]; then
  phase_start "M3-ALL author — ${STORY_COUNT} story plans before any M4 (O-M3ALL)" \
    "Whole-set lint after this pass; M4 refused until PLAN-SET OK"
  # O-M3ALL skeleton-first: one deterministic compose after M2 before any
  # model seat. Creates/refreshes skeleton tasks.md (Owns/Oracle/Port/Assumes
  # slots); never overwrites a non-skeleton authored plan.
  if [ "${M3_ALL_COMPOSE:-1}" = "1" ]; then
    phase_start "M3-ALL skeleton-first compose (O-M3ALL)"
    if python3 "$HARNESS/m3-all-compose.py" --root . \
        > /tmp/m3-all-compose.txt 2>&1; then
      phase_gate "M3-ALL compose" GREEN "$(tail -1 /tmp/m3-all-compose.txt)"
      phase_ok "M3-ALL skeleton-first compose — see /tmp/m3-all-compose.txt"
    else
      phase_gate "M3-ALL compose" RED "see /tmp/m3-all-compose.txt"
      fail_run "O-M3ALL skeleton-first compose RED (see /tmp/m3-all-compose.txt)"
    fi
  fi
else
  phase_start "Story loop — ${STORY_COUNT} stories (${STORY_IDS}) [O-M3ALL execute: JIT+M4]"
fi

STORY_IDX=0
while IFS='|' read -r SID DEPLOY FINDINGS SCOPE; do
  [ -n "$SID" ] || continue
  STORY_IDX=$((STORY_IDX + 1))
  # O-LOGSTORY: story identity on every log() line for this SID (cleared below).
  STORY_TAG="$SID"
  SLUG_HINT=$(ls migration/briefs/${SID}-*.md 2>/dev/null | head -1 | xargs -n1 basename 2>/dev/null | sed 's/\.md$//' || echo "$SID")
  story_done "$SID" && { phase_ok "${SID} (${SLUG_HINT}) — already complete; skipping"; STORY_TAG=""; continue; }

  # -------------------------------------------------------- M3 SPECIFY
  # O-M3SKIP: never treat "tasks.md exists" as GREEN. Untracked/half-written
  # specs after a failed M3 (or auto-restart) must re-lint; only skip mchat
  # when plan-lint is already green.
  SPEC_TASKS=$(ls specs/${SID}-*/tasks.md 2>/dev/null | head -1)
  BRIEF=$(ls migration/briefs/${SID}-*.md 2>/dev/null | head -1)
  [ -n "$BRIEF" ] || fail_run "$SID has no brief under migration/briefs/"
  SLUG=$(basename "$BRIEF" .md)
  M3_DONE=0
  # O-M3ACCEPT: plan-lint must know deploy vs non-deploy (roadmap flag).
  # O-M3DTOSCOPE: pass roadmap scope so plan-lint ignores out-of-story files (dto/).
  M3_LINT_CMD="python3 ${HARNESS}/plan-lint.py specs/${SLUG}/tasks.md migration/mta-findings.json --findings-scope ${FINDINGS} --profile migration/architecture-profile.md --story-deploy ${DEPLOY} --story-scope '${SCOPE}'"
  if [ -n "$SPEC_TASKS" ] \
    && python3 "$HARNESS/plan-lint.py" "$SPEC_TASKS" migration/mta-findings.json \
         --findings-scope "$FINDINGS" --profile migration/architecture-profile.md \
         --story-deploy "$DEPLOY" --story-scope "$SCOPE" \
         > /tmp/plan-lint.txt 2>&1; then
    [ -n "$(git status --porcelain specs/)" ] \
      && git add specs/ \
      && git commit -q -m "${SID} spec: outer-loop mechanical commit of lint-green spec" 2>/dev/null
    phase_gate "M3 SPECIFY ${SID} plan-lint" GREEN "commit $(git rev-parse --short HEAD)"
    phase_ok "M3 SPECIFY — ${SLUG} spec already present and plan-lint-green ($SPEC_TASKS); commit $(git rev-parse --short HEAD)"
    M3_DONE=1
  elif [ -n "$SPEC_TASKS" ]; then
    phase_gate "M3 SPECIFY ${SID} plan-lint" RED "present spec failed lint — /tmp/plan-lint.txt (O-M3SKIP will re-run M3)"
    log "         O-M3SKIP: ${SPEC_TASKS} present but plan-lint RED — entering M3 fix attempts (not skipping to M4)"
  fi
  if [ "$M3_DONE" != "1" ]; then
    # O-M3WORKER: Qwen drafts (≤M3_WORKER_ATTEMPTS), then MiniMax backstop
    # (≤M3_ORCH_BACKSTOP). plan-lint remains the gate — session≠success.
    # O-M3KILL: SIGKILL must NOT spend an attempt.
    m3_build_prompt() { # $1=fresh|fix — sets P from brief or plan-lint RED fix
      local mode="${1:-fresh}"
      # O-M3EMPTY: if tasks.md never landed, always use fresh create prompt —
      # "fix specs/<slug>/" misleads when the directory does not exist.
      if [ "$mode" = "fix" ] && [ ! -f "specs/${SLUG}/tasks.md" ]; then
        mode=fresh
      fi
      P="Use the migration-harness skill and read PLANNING.md in its directory. Execute M3 ONLY for story ${SID}: read the brief ${BRIEF} (it is authoritative — the decided shapes and contracts are IN it), migration/architecture-profile.md for context, and the legacy code it cites under /projects/legacy. O-M3FIRSTWRITE (mandatory): in the FIRST tool batch, mkdir -p specs/${SLUG}/ and WRITE specs/${SLUG}/tasks.md (TASKS-TEMPLATE skeleton) before any other reads beyond the brief — supervisor aborts read-only seats after ~${M3_STALL_ABORT_SECS:-120}s with zero writes (O-M3QWENSTALL). Then refine plan.md/spec.md and run plan-lint. O-SPECREIMPL: every REDESIGN/OPEN DESIGN class named in spec.md must appear in some task with **Port**: reimplement. Write specs/${SLUG}/spec.md, plan.md and tasks.md per PLANNING.md, scoped STRICTLY to this story (create the directory if missing). Every task MUST have **Class**: rewrite|infer and **Shape**: create|modify|remove|structure|verify (O-M3CLASSFMT). O-M3PLANEXISTS: do NOT schedule Spring Boot parent/BOM/actuator→Quarkus converts when pom.xml already has Quarkus BOM/quarkus-smallrye-health — omit dead tasks. Story file scope=${SCOPE} — do not harvest dto/entity classes outside that scope. A deterministic lint gates the plan — verify yourself with: ${M3_LINT_CMD} (must exit 0) BEFORE committing. Finish with ONE commit whose message STARTS with '${SID} spec:'. DO NOT PUSH. ${PKG_RENAME_HINT} ACCEPTANCE (O-M3ACCEPT): story deploy=${DEPLOY}. If deploy=false, do NOT task migration.yaml acceptance.path with a Java @Path/endpoint — defer to the deploy story (S-AC1/G-OK); omitting the path from tasks is OK. If deploy=true, task the full literal acceptance.path with real @Path substance (no MinimalAcceptanceEndpoint / status-map placeholders)."
      if [ "$mode" = "fix" ]; then
        P="Use the migration-harness skill and read PLANNING.md in its directory. A previous M3 attempt for ${SID} left a plan that fails plan-lint — the findings are in /tmp/plan-lint.txt (read it with your file tools). Fix every finding in specs/${SLUG}/ (create specs/${SLUG}/{spec,plan,tasks}.md from the brief if tasks.md is missing). Every task MUST have **Class**: rewrite|infer and **Shape**: create|modify|remove|structure|verify. Drop O-PLANEXISTS-dead Spring→Quarkus converts already satisfied by the scaffold. Scope=${SCOPE}. Verify ${M3_LINT_CMD} exits 0, and commit with prefix '${SID} spec:'. DO NOT PUSH. ${PKG_RENAME_HINT} ACCEPTANCE (O-M3ACCEPT): deploy=${DEPLOY} — if false, do not schedule endpoint substance for acceptance.path; if true, task the full literal path with real @Path (no status-map / MinimalAcceptanceEndpoint)."
      fi
    }
    m3_lint_green() {
      SPEC_TASKS=$(ls specs/${SID}-*/tasks.md 2>/dev/null | head -1)
      [ -n "$SPEC_TASKS" ] || return 1
      python3 "$HARNESS/plan-lint.py" "$SPEC_TASKS" migration/mta-findings.json \
        --findings-scope "$FINDINGS" --profile migration/architecture-profile.md \
        --story-deploy "$DEPLOY" --story-scope "$SCOPE" > /tmp/plan-lint.txt 2>&1
    }
    m3_write_lint_evidence() {
      # O-M3EVID: never `|| echo missing` on plan-lint RED — write real findings.
      {
        echo "Lint command: ${M3_LINT_CMD}"
        if [ -z "${SPEC_TASKS:-}" ]; then
          echo "tasks.md missing entirely"
        else
          python3 "$HARNESS/plan-lint.py" "$SPEC_TASKS" migration/mta-findings.json \
            --findings-scope "$FINDINGS" --profile migration/architecture-profile.md \
            --story-deploy "$DEPLOY" --story-scope "$SCOPE" 2>&1 || true
        fi
      } > /tmp/plan-lint.txt
    }

    # --- Phase A: Qwen worker attempts (default 2) ---
    # O-M3QUOTA-GATE: if a prior session left lint-green, advance before any seat.
    if [ "${WORKER_M3_FIRST:-true}" = "true" ]; then
      ATTEMPT=1
      while [ "$ATTEMPT" -le "${M3_WORKER_ATTEMPTS:-2}" ]; do
        if m3_lint_green; then
          [ -n "$(git status --porcelain specs/)" ] && git add specs/ && git commit -q -m "${SID} spec: outer-loop mechanical commit of lint-green spec" 2>/dev/null
          phase_gate "M3 SPECIFY ${SID} plan-lint" GREEN "commit $(git rev-parse --short HEAD)"
          phase_ok "M3 SPECIFY — ${SLUG} plan-lint-green via worker path; commit $(git rev-parse --short HEAD)"
          M3_DONE=1
          break
        fi
        phase_start "M3 SPECIFY — plan story ${SLUG} (${STORY_IDX}/${STORY_COUNT}) [worker attempt ${ATTEMPT}/${M3_WORKER_ATTEMPTS}]"
        log "         O-M3WORKER: draft/fix via $(worker_label) (plan-lint verifier; MiniMax backstop if still RED)"
        SPEC_TASKS=$(ls specs/${SID}-*/tasks.md 2>/dev/null | head -1)
        # O-M3QWENSTALL: mechan-preseed tasks.md skeleton before Qwen seat so the
        # worker mutates an existing file (0-write explore stalls burned 120s→MiniMax).
        if [ -z "$SPEC_TASKS" ] && [ ! -f "specs/${SLUG}/tasks.md" ]; then
          mkdir -p "specs/${SLUG}"
          cat > "specs/${SLUG}/tasks.md" <<EOF
# ${SLUG} Tasks

#### T-001: TODO — replace from brief (O-M3QWENSTALL preseed)
**Class**: rewrite
**Shape**: modify
**Findings**:
**Goal**: Replace this skeleton from ${BRIEF} in the FIRST tool batch (write/edit this file)
**Target design**:
- pom.xml → pom.xml
**Acceptance**: plan-lint green; sensors green

# O-M3SHAPEPATCH / O-M3CLASSFMT: every T-NNN needs **Class**: rewrite|infer
# and **Shape**: create|modify|remove|structure|verify (not free-form verbs).
# O-M3PLANEXISTS: do NOT schedule Spring Boot parent/BOM/actuator converts when
# the Quarkus scaffold already satisfies them — verify pom.xml first and omit.
EOF
          log "         O-M3QWENSTALL: preseeded specs/${SLUG}/tasks.md skeleton before worker seat"
          SPEC_TASKS="specs/${SLUG}/tasks.md"
        fi
        # O-M3EMPTY: attempt>1 with no tasks.md must stay on fresh create, not fix.
        if [ -n "$SPEC_TASKS" ]; then m3_build_prompt fix; else m3_build_prompt fresh; fi
        M3_EXPECT_TASKS="specs/${SLUG}/tasks.md"
        export M3_EXPECT_TASKS
        wchat "m3-${SID}-w${ATTEMPT}" "$P" "M3 SPECIFY ${SID} (worker)" \
          -f "$BRIEF" -f migration/architecture-profile.md
        mchat_rc=$?
        unset M3_EXPECT_TASKS
        if [ -f "/tmp/m3-empty-abort-m3-${SID}-w${ATTEMPT}" ]; then
          log "         O-M3EMPTY/O-M3QWENSTALL: worker produced no tasks.md — attempt ${ATTEMPT} spent (early abort)"
          m3_write_lint_evidence
          phase_gate "M3 SPECIFY ${SID} plan-lint" RED "O-M3EMPTY early abort — /tmp/plan-lint.txt"
          phase_retry "M3 SPECIFY ${SID} — empty write; advancing"
          if [ "$ATTEMPT" -eq 1 ] && [ "${M3_SKIP_W2_ON_EMPTY:-true}" = "true" ]; then
            log "         O-M3QWENSTALL: w1 read-only/empty — skip w2, MiniMax backstop next"
            ATTEMPT="${M3_WORKER_ATTEMPTS:-2}"
          fi
          ATTEMPT=$((ATTEMPT + 1))
          continue
        fi
        if [ "$mchat_rc" -eq 137 ] || [ "$mchat_rc" -eq 143 ]; then
          # O-M3KILLGREEN: tip/operator may have landed a lint-green tasks.md while
          # the seat was thrashing — check gate before infinite kill-retry.
          if m3_lint_green; then
            [ -n "$(git status --porcelain specs/)" ] && git add specs/ && git commit -q -m "${SID} spec: outer-loop mechanical commit of lint-green spec" 2>/dev/null
            phase_gate "M3 SPECIFY ${SID} plan-lint" GREEN "commit $(git rev-parse --short HEAD)"
            phase_ok "M3 SPECIFY — ${SLUG} plan-lint-green after O-M3KILL (tip already green); commit $(git rev-parse --short HEAD)"
            M3_DONE=1
            break
          fi
          log "         O-M3KILL: worker M3 killed (rc=${mchat_rc}) — attempt ${ATTEMPT} NOT spent"
          phase_retry "M3 SPECIFY ${SID} — worker session killed; not counting as lint fail"
          continue
        fi
        if m3_lint_green; then
          [ -n "$(git status --porcelain specs/)" ] && git add specs/ && git commit -q -m "${SID} spec: outer-loop mechanical commit of lint-green spec" 2>/dev/null
          phase_gate "M3 SPECIFY ${SID} plan-lint" GREEN "commit $(git rev-parse --short HEAD)"
          phase_ok "M3 SPECIFY — ${SLUG} plan-lint-green after Qwen; commit $(git rev-parse --short HEAD)"
          M3_DONE=1
          break
        fi
        m3_write_lint_evidence
        phase_gate "M3 SPECIFY ${SID} plan-lint" RED "worker attempt ${ATTEMPT} — /tmp/plan-lint.txt"
        phase_retry "M3 SPECIFY ${SID} — Qwen plan still RED"
        ATTEMPT=$((ATTEMPT + 1))
      done
    fi

    # --- Phase B: MiniMax backstop (default 1) when worker path did not green ---
    if [ "$M3_DONE" != "1" ] && [ "${M3_ORCH_BACKSTOP:-1}" -ge 1 ]; then
      ATTEMPT=1
      while [ "$ATTEMPT" -le "${M3_ORCH_BACKSTOP:-1}" ]; do
        if m3_lint_green; then
          [ -n "$(git status --porcelain specs/)" ] && git add specs/ && git commit -q -m "${SID} spec: outer-loop mechanical commit of lint-green spec" 2>/dev/null
          phase_gate "M3 SPECIFY ${SID} plan-lint" GREEN "commit $(git rev-parse --short HEAD)"
          phase_ok "M3 SPECIFY — ${SLUG} plan-lint-green; commit $(git rev-parse --short HEAD)"
          M3_DONE=1
          break
        fi
        if [ "${WORKER_M3_FIRST:-true}" = "true" ]; then
          phase_start "M3 SPECIFY — plan story ${SLUG} (${STORY_IDX}/${STORY_COUNT}) [MiniMax backstop ${ATTEMPT}/${M3_ORCH_BACKSTOP}]"
          log "         O-M3WORKER: MiniMax backstop after Qwen plan-lint RED"
          seat_tag="orch${ATTEMPT}"
          seat_label="M3 SPECIFY ${SID} (orch backstop)"
        else
          # O-M3ROUTE: MiniMax drafts first (Qwen 0-for-N on open-ended M3).
          phase_start "M3 SPECIFY — plan story ${SLUG} (${STORY_IDX}/${STORY_COUNT}) [MiniMax draft ${ATTEMPT}/${M3_ORCH_BACKSTOP}]"
          log "         O-M3ROUTE: MiniMax draft (WORKER_M3_FIRST=false)"
          seat_tag="a${ATTEMPT}"
          seat_label="M3 SPECIFY ${SID}"
        fi
        SPEC_TASKS=$(ls specs/${SID}-*/tasks.md 2>/dev/null | head -1)
        if [ -n "$SPEC_TASKS" ]; then m3_build_prompt fix; else m3_build_prompt fresh; fi
        mchat "m3-${SID}-${seat_tag}" "$P" "$seat_label"
        mchat_rc=$?
        if [ "$mchat_rc" -eq 137 ] || [ "$mchat_rc" -eq 143 ]; then
          log "         O-M3KILL: orch M3 killed (rc=${mchat_rc}) — backstop NOT spent"
          phase_retry "M3 SPECIFY ${SID} — orch session killed; not counting"
          continue
        fi
        if m3_lint_green; then
          [ -n "$(git status --porcelain specs/)" ] && git add specs/ && git commit -q -m "${SID} spec: outer-loop mechanical commit of lint-green spec" 2>/dev/null
          phase_gate "M3 SPECIFY ${SID} plan-lint" GREEN "commit $(git rev-parse --short HEAD)"
          phase_ok "M3 SPECIFY — ${SLUG} plan-lint-green after MiniMax; commit $(git rev-parse --short HEAD)"
          M3_DONE=1
          break
        fi
        if grep -qE "429|Too Many Requests|Rate limit|rate.?limit" "/tmp/outer-m3-${SID}-${seat_tag}.log" 2>/dev/null; then
          log "         O-M3QUOTA: MiniMax rate-limited — NOT spent; backoff 15m"
          phase_retry "M3 SPECIFY ${SID} — quota; sleeping 900s"
          sleep 900
          continue
        fi
        m3_write_lint_evidence
        phase_gate "M3 SPECIFY ${SID} plan-lint" RED "MiniMax attempt ${ATTEMPT} — /tmp/plan-lint.txt"
        ATTEMPT=$((ATTEMPT + 1))
      done
    fi

    if [ "$M3_DONE" != "1" ]; then
      fail_run "M3 SPECIFY ${SID} failed plan-lint after M3 attempts (WORKER_M3_FIRST=${WORKER_M3_FIRST:-true})"
    fi
  fi

  # O-M3ALL author pass: no M4 until every story plan exists + whole-set GREEN.
  if [ "$M3_ALL_PASS" = "author" ]; then
    phase_ok "M3-ALL author — ${SID} plan ready (defer M4 until whole-set lint)"
    STORY_TAG=""
    continue
  fi

  # ----------------------------------------------------- M3-ALL JIT (waterfall)
  # Mandatory antidotes: JIT re-lint; Owns/Port/Shape amend → whole-set re-lint;
  # plan-vs-reality delta is first-class (never suppress).
  phase_start "M3-ALL JIT — re-lint ${SID} before M4 (waterfall antidote)"
  set +e
  bash "$HARNESS/m3-all-lint.sh" --mode=jit --story "$SID" --root . \
    > /tmp/m3-all-jit.txt 2>&1
  _m3all_rc=$?
  set -e
  if [ "$_m3all_rc" = "3" ]; then
    log "         O-M3ALL-AMEND: Owns/Port/Shape changed — whole-set re-lint"
    bash "$HARNESS/m3-all-lint.sh" --mode=whole-set --root . \
      > /tmp/m3-all-whole.txt 2>&1 \
      || fail_run "O-M3ALL whole-set RED after ${SID} amend (see /tmp/m3-all-whole.txt)"
    phase_gate "M3-ALL whole-set (post-amend)" GREEN "amend re-lint OK"
  elif [ "$_m3all_rc" != "0" ]; then
    phase_gate "M3-ALL JIT ${SID}" RED "see /tmp/m3-all-jit.txt"
    fail_run "O-M3ALL JIT RED for ${SID} (see /tmp/m3-all-jit.txt)"
  else
    phase_gate "M3-ALL JIT ${SID}" GREEN "waterfall antidote"
  fi

  # ----------------------------------------------------- M4/M5 EXECUTE
  # One supervisor child per story with computed env. Default RUN_BASE=HEAD
  # at story start keeps every phase prefix story-scoped (no cross-story
  # commit-range collisions). Mid-story resume after pod bounce MUST be
  # story-scoped: set RESUME_STORY=<SID> and RESUME_RUN_BASE=<sha> together.
  # A bare sticky RUN_BASE across stories reuses T-00N prefixes from earlier
  # stories and false-skips the next story's work (V8 S02 empty ship).
  # PRESERVE_CHECK follows deploy: preserve surfaces are enforced where they
  # ship. Fidelity is ALWAYS on under the single quality model — harvest
  # classes need it; redesign classes are exempt by the harvest-fidelity
  # discriminator (no story-class waiver).
  PC=on; [ "$DEPLOY" = "true" ] || PC=off
  # Later-story class guard (V5 T-004): simple class names owned by stories
  # AFTER this one — the supervisor's scope sensor reverts any of these that
  # a task in THIS story creates in src/main (fabrication of a later-story
  # REDESIGN class). Derived from the roadmap scope of subsequent stories.
  LATER_CLASSES=$(echo "$STORIES" | awk -F'|' -v cur="$SID" 'seen{print $4} $1==cur{seen=1}' \
    | tr ', ' '\n' | sed -E 's/\.java$//; s#.*[./]##' | grep -E '^[A-Z][A-Za-z0-9]*$' | sort -u | tr '\n' ' ')
  # O-HOTSWAP: supervisor may pause on /tmp/harness-update; re-enter M4
  # without recording S0N,failed (mid-task deploy is not a story failure).
  HOTSWAP_TRIES=0
  while true; do
  rm -f /tmp/supervisor-done /tmp/harness-update-ack
  if [ -n "${RESUME_RUN_BASE:-}" ] && [ "${RESUME_STORY:-}" = "$SID" ]; then
    STORY_RUN_BASE="$RESUME_RUN_BASE"
    log "         O-RESUME: using RESUME_RUN_BASE=$(git rev-parse --short "$STORY_RUN_BASE") for $SID only"
    # O-RESUMEHIDE: a RESUME_RUN_BASE tip that sits *after* earlier T-NNN commits
    # hides those tips from committed() (RUN_BASE..HEAD) → ceremonial ALREADY
    # COMPLETE replay (Wave4 S01 resume @1efdd65 re-tipped T-001/T-002). Walk
    # base back so every in-story T-NNN tip is an ancestor-or-equal of the range
    # start (O-RESUMEBASEEXCL still counts the tip at RUN_BASE itself).
    if [ -f "$SPEC_TASKS" ]; then
      _floor=$(git log -1 --format=%H --grep="story complete" "${STORY_RUN_BASE}^" 2>/dev/null || true)
      [ -n "$_floor" ] || _floor=$(git rev-list --max-parents=0 HEAD | tail -1)
      _hidden=""
      while read -r _tid; do
        [ -n "$_tid" ] || continue
        _tsha=$(git log -1 --format=%H --grep="^${_tid}:" "${_floor}..HEAD" 2>/dev/null || true)
        [ -n "$_tsha" ] || continue
        # Already visible in RUN_BASE..HEAD, or is the RUN_BASE tip itself.
        if git log --oneline "${STORY_RUN_BASE}..HEAD" 2>/dev/null | grep -qE "^[0-9a-f]+ ${_tid}:"; then
          continue
        fi
        if [ "$(git rev-parse "$STORY_RUN_BASE")" = "$_tsha" ] \
          || git log -1 --format=%s "$STORY_RUN_BASE" 2>/dev/null | grep -qE "^${_tid}:"; then
          continue
        fi
        # Tip is a strict ancestor of RESUME tip → hidden; walk to its parent.
        if git merge-base --is-ancestor "$_tsha" "$STORY_RUN_BASE" 2>/dev/null; then
          _cand=$(git rev-parse "${_tsha}^" 2>/dev/null || true)
          [ -n "$_cand" ] || continue
          STORY_RUN_BASE="$_cand"
          _hidden="${_hidden} ${_tid}"
        fi
      done < <(grep -oE 'T-[0-9]+' "$SPEC_TASKS" 2>/dev/null | sort -u)
      if [ -n "$_hidden" ]; then
        log "         O-RESUMEHIDE: walked RESUME_RUN_BASE back to $(git rev-parse --short "$STORY_RUN_BASE") (hidden tips:${_hidden})"
      fi
    fi
  else
    # O-M4REPLAY: mid-story restart with RUN_BASE=HEAD re-dispatches already
    # committed T-NNN (empty RUN_BASE..HEAD → committed() always false).
    # If this story's spec exists and T-NNN commits already follow it, resume
    # from the spec's parent so those tasks stay "committed".
    SPEC_SHA=$(git log -1 --format=%H --grep="^${SID} spec:" 2>/dev/null || true)
    if [ -n "$SPEC_SHA" ] && [ -f "$SPEC_TASKS" ] \
      && git log --oneline "${SPEC_SHA}..HEAD" 2>/dev/null | grep -qE '^[0-9a-f]+ T-[0-9]+:'; then
      STORY_RUN_BASE=$(git rev-parse "${SPEC_SHA}^" 2>/dev/null || git rev-parse "$SPEC_SHA")
      # O-SPECREBASE: a mid-story `S0N spec:` recommit (e.g. DTO-first plan
      # fix) can sit *after* earlier T-NNN. SPEC^ then hides those commits from
      # committed() → false replay (Wave2 T-002 after T-007 sensor-fix restart).
      # Walk base back to the parent of any task commit that exists in history
      # but is missing from SPEC^..HEAD.
      # O-SPECREBASE: only rewrite tasks already progressed in SPEC..HEAD
      # (max T-NNN). Ignoring higher ids avoids walking into prior stories'
      # reused T-00N subjects (Wave2 false base → old T-007/T-008).
      # O-COMMITID/O-SPECREBASE: only subject-leading `T-NNN:` — never bare
      # `(T-005)` inside plan commit subjects (v2 false walk to prior-story T-005).
      _maxn=0
      while read -r _ht; do
        _hn=${_ht#T-}; _hn=$((10#${_hn}))
        [ "$_hn" -gt "$_maxn" ] && _maxn=$_hn
      done < <(git log --oneline "${SPEC_SHA}..HEAD" 2>/dev/null \
        | grep -E '^[0-9a-f]+ T-[0-9]+:' | grep -oE 'T-[0-9]+' | sort -u)
      # Floor: prior story-complete (or repo root) — never match T-NNN from older stories.
      _floor=$(git log -1 --format=%H --grep="story complete" "${SPEC_SHA}^" 2>/dev/null || true)
      [ -n "$_floor" ] || _floor=$(git rev-list --max-parents=0 HEAD | tail -1)
      _hidden=""
      while read -r _tid; do
        [ -n "$_tid" ] || continue
        _tn=${_tid#T-}; _tn=$((10#${_tn}))
        [ "$_tn" -le "$_maxn" ] || continue
        _tsha=$(git log -1 --format=%H --grep="^${_tid}:" "${_floor}..HEAD" 2>/dev/null || true)
        [ -n "$_tsha" ] || continue
        if ! git log --oneline "${STORY_RUN_BASE}..HEAD" 2>/dev/null | grep -qE "^[0-9a-f]+ ${_tid}:"; then
          _cand=$(git rev-parse "${_tsha}^" 2>/dev/null || true)
          [ -n "$_cand" ] || continue
          if git merge-base --is-ancestor "$_cand" "$STORY_RUN_BASE" 2>/dev/null; then
            STORY_RUN_BASE="$_cand"
            _hidden="${_hidden} ${_tid}"
          fi
        fi
      done < <(grep -oE 'T-[0-9]+' "$SPEC_TASKS" 2>/dev/null | sort -u)
      if [ -n "$_hidden" ]; then
        log "         O-SPECREBASE: walked run_base back to $(git rev-parse --short "$STORY_RUN_BASE") (pre-spec tasks:${_hidden})"
      fi
      log "         O-M4REPLAY: auto resume base=$(git rev-parse --short "$STORY_RUN_BASE") from ${SID} spec (T-NNN already present)"
    else
      # O-M4REPLAYNOSPEC: no "^${SID} spec:" commit (mechanical lint-green
      # commit or atypical subject) — still resume from prior story-complete
      # when T-NNN tips already exist, else HEAD false-replays the whole story.
      _floor=$(git log -1 --format=%H --grep="story complete" 2>/dev/null || true)
      [ -n "$_floor" ] || _floor=$(git rev-list --max-parents=0 HEAD | tail -1)
      _t1=$(git log --reverse --format=%H --grep="^T-001:" "${_floor}..HEAD" 2>/dev/null | head -1 || true)
      if [ -n "$_t1" ] && git log --oneline "${_floor}..HEAD" 2>/dev/null | grep -qE "^[0-9a-f]+ T-[0-9]+:"; then
        STORY_RUN_BASE=$(git rev-parse "${_t1}^")
        log "         O-M4REPLAYNOSPEC: no ${SID} spec: tip — resume base=$(git rev-parse --short "$STORY_RUN_BASE") from T-001^ (floor=$(git rev-parse --short "$_floor"))"
      else
        STORY_RUN_BASE="$(git rev-parse HEAD)"
      fi
    fi
  fi
  if [ "$HOTSWAP_TRIES" -eq 0 ]; then
    phase_start "M4/M5 EXECUTE — implement & ship ${SLUG_HINT} (${STORY_IDX}/${STORY_COUNT})" \
      "Models: $(orch_label) · $(worker_label) | deploy=${DEPLOY} findings=${FINDINGS} preserve=${PC} later-classes=$(echo $LATER_CLASSES | wc -w | tr -d ' ') | supervisor: /tmp/supervisor.log | run_base=$(git rev-parse --short "$STORY_RUN_BASE")"
    # O-LOGBRIEF: operator-facing story summary (GOAL≠slug; PORT early).
    STORY_T0=$(date -u +%s)
    emit_story_brief
    log "         Note: M4 rewrite+infer coding → $(worker_label) first; MiniMax only for orch/escalation (WORKER_FIRST) — supervisor.log records actor"
  else
    log "         O-HOTSWAP: re-entering M4/M5 for ${SID} (attempt $((HOTSWAP_TRIES+1)); run_base=$(git rev-parse --short "$STORY_RUN_BASE"))"
  fi
  env RUN_BASE="$STORY_RUN_BASE" \
      STORY_ID="$SID" \
      STORY_SPEC_PREFIX="${SID} spec" \
      PLAN_SCOPE="$FINDINGS" \
      STORY_DEPLOY="$DEPLOY" \
      STORY_TASKS="$SPEC_TASKS" \
      STORY_SCOPE="$SCOPE" \
      LATER_CLASSES="$LATER_CLASSES" \
      PRESERVE_CHECK="$PC" \
      "$HARNESS/supervisor.sh" < /dev/null >> /tmp/supervisor-nohup.log 2>&1
  OUTCOME=$(cat /tmp/supervisor-done 2>/dev/null || echo "no-done-marker")
  # O-HOTSWAP-INFLIGHT: keep a sticky marker across re-enter attempts. Clearing
  # harness-update-ack before a successful supervisor start used to turn a
  # failed re-exec (e.g. O-SUPCMDLINE false positive) into false S0N,failed
  # on the *second* no-done-marker (Wave2 2026-07-31).
  if [ "$OUTCOME" = "no-done-marker" ] \
    && { [ -f /tmp/harness-update-ack ] || [ -f /tmp/hotswap-inflight ]; }; then
    HOTSWAP_TRIES=$((HOTSWAP_TRIES + 1))
    # O-HOTSWAPBUDGET (R-218 recovery): was 3 — rapid kill+re-enter races
    # burned the budget in <1s and false-failed S03. Allow 8 + settle delay.
    if [ "$HOTSWAP_TRIES" -gt 8 ]; then
      log "         O-HOTSWAP: exceeded re-enter budget — treating as failure"
      rm -f /tmp/hotswap-inflight /tmp/harness-update /tmp/harness-update-ack
    else
      log "         O-HOTSWAP: harness update pause ended without done marker — re-entering (not failed)"
      touch /tmp/hotswap-inflight
      rm -f /tmp/harness-update /tmp/harness-update-ack /tmp/supervisor-pause
      # O-FGRETRO: mid-run probe deploy may invalidate prior ALREADY COMPLETE skips.
      touch /tmp/probe-reeval-needed
      # O-HOTSWAPLOCK (R-227): drop stale flock + longer settle — rapid kill+re-enter
      # left /tmp/supervisor.lock held and burned the re-enter budget (S03).
      rm -f /tmp/supervisor.lock
      sleep 15
      continue
    fi
  fi
  rm -f /tmp/hotswap-inflight
  break
  done
  case "$OUTCOME" in
    debt-freeze*)
      # O-DEBTFRZ: supervisor froze on unresolved task/milestone debt — do NOT
      # mark the story complete or continue to dependents.
      phase_fail "M4/M5 EXECUTE — ${SLUG_HINT} debt-freeze (O-DEBTFRZ); HEAD $(git rev-parse --short HEAD)"
      emit_story_epilog "debt-freeze"
      echo "${SID},debt-freeze,$(date -u +%s)" >> "$STATE"
      git add "$STATE" && git commit -q -m "${SID} story HOLD: debt-freeze (O-DEBTFRZ)" 2>/dev/null || true
      fail_run "$SID debt-freeze (O-DEBTFRZ) — fix debt, durableize, re-run; do not advance"
      ;;
    m3-lint-hold*|plan-lint-hold*)
      # O-M3LINTPROCEED: exhausted m3-lint with plan still RED — HOLD/re-M3,
      # never treat as execute success or silent M4 advance.
      phase_fail "M4/M5 EXECUTE — ${SLUG_HINT} m3-lint-hold (O-M3LINTPROCEED); HEAD $(git rev-parse --short HEAD)"
      emit_story_epilog "m3-lint-hold"
      echo "${SID},m3-lint-hold,$(date -u +%s)" >> "$STATE"
      git add "$STATE" && git commit -q -m "${SID} story HOLD: m3-lint-hold (O-M3LINTPROCEED)" 2>/dev/null || true
      fail_run "$SID m3-lint-hold (O-M3LINTPROCEED) — plan-lint RED after revision; re-M3, do not advance to M4"
      ;;
    success*|story-gate-passed*)
      # O-REVHOLD: review HOLD must not become story-complete in the ledger
      if [ -f migration/HOLD ] || [ -f /tmp/review-hold ]; then
        phase_fail "M4/M5 EXECUTE — ${SLUG_HINT} review-hold (O-REVHOLD); HEAD $(git rev-parse --short HEAD)"
        emit_story_epilog "review-hold"
        echo "${SID},review-hold,$(date -u +%s)" >> "$STATE"
        git add "$STATE" && git commit -q -m "${SID} story HOLD: review-hold (O-REVHOLD)" 2>/dev/null || true
        fail_run "$SID review-hold (O-REVHOLD) — clear migration/HOLD after durableize; do not advance"
      fi
      phase_ok "M4/M5 EXECUTE — ${SLUG_HINT} complete (${OUTCOME}); HEAD $(git rev-parse --short HEAD)"
      emit_story_epilog "complete"
      echo "${SID},complete,$(date -u +%s)" >> "$STATE"
      git add "$STATE" && git commit -q -m "${SID} story complete: ${OUTCOME}" 2>/dev/null || true
      # Outer loop (automated): apply Retro's "Brief updates" section to
      # remaining incomplete briefs only. Skills/harness stay human-only.
      REMAINING_BRIEFS=""
      while IFS='|' read -r RSID _ _ _; do
        [ -n "$RSID" ] || continue
        story_done "$RSID" && continue
        B=$(ls migration/briefs/${RSID}-*.md 2>/dev/null | head -1)
        [ -n "$B" ] && REMAINING_BRIEFS="${REMAINING_BRIEFS} ${B}"
      done <<< "$STORIES"
      if [ -f migration/retro-proposals.md ] && [ -n "$(echo "$REMAINING_BRIEFS" | tr -d ' ')" ]; then
        phase_start "BRIEF REFRESH — apply retro updates after ${SID}"
        mchat "brief-refresh-${SID}" \
"Use the migration-harness skill. Read migration/retro-proposals.md and apply ONLY the section titled '## Brief updates (auto-applicable)' to these remaining briefs:${REMAINING_BRIEFS}. Also read migration/discovered.md (K9) if present — fold clearly actionable out-of-scope needs into those remaining briefs when they fit; leave the rest listed. Do not edit completed-story briefs, specs, skills, or harness scripts. If nothing actionable, make no file changes. If you change briefs, finish with ONE commit whose message STARTS with 'Brief refresh:'. DO NOT PUSH." \
          "BRIEF REFRESH" \
          || log "         brief refresh session failed — continuing (non-blocking)"
        [ -n "$(git status --porcelain migration/briefs/)" ] \
          && git add migration/briefs/ && git commit -q -m "Brief refresh: outer-loop mechanical commit after ${SID}" 2>/dev/null || true
        phase_ok "BRIEF REFRESH — done after ${SID}"
      else
        log "         BRIEF REFRESH — nothing to apply after ${SID}"
      fi
      ;;
    *)
      # A failed story blocks its dependents by construction (dependency
      # order) — stop the run with the evidence preserved rather than
      # building on a red foundation. Resume later: story-state.csv keeps
      # completed stories; relaunch outer-loop.sh to continue.
      phase_fail "M4/M5 EXECUTE — ${SLUG_HINT} (${OUTCOME})"
      emit_story_epilog "failed"
      echo "${SID},failed,$(date -u +%s)" >> "$STATE"
      git add "$STATE" && git commit -q -m "${SID} story FAILED: ${OUTCOME}" 2>/dev/null || true
      git push origin main >> "$LOG" 2>&1 || true
      fail_run "$SID did not ship (${OUTCOME}) — run stopped before dependent stories"
      ;;
  esac
  STORY_TAG=""
done <<< "$STORIES"
STORY_TAG=""

if [ "$M3_ALL_PASS" = "author" ]; then
  phase_start "M3-ALL whole-set lint — K1 / Port / later-class / Oracle / Assumes (O-M3ALL)"
  if bash "$HARNESS/m3-all-lint.sh" --mode=whole-set --root . \
      > /tmp/m3-all-whole.txt 2>&1; then
    phase_gate "M3-ALL whole-set" GREEN "$(grep -E 'PLAN-SET OK|OK:' /tmp/m3-all-whole.txt | tail -3 | tr '\n' '; ')"
    # Prediction freeze + operator gate between whole-set GREEN and first M4.
    phase_start "M3-ALL freeze-predictions + OPERATOR_GATE (O-M3ALL)"
    bash "$HARNESS/m3-all-lint.sh" --mode=freeze-predictions --root . \
      > /tmp/m3-all-predictions.txt 2>&1 \
      || fail_run "O-M3ALL freeze-predictions failed (see /tmp/m3-all-predictions.txt)"
    if bash "$HARNESS/m3-all-lint.sh" --mode=operator-gate --root . \
        > /tmp/m3-all-operator-gate.txt 2>&1; then
      phase_gate "M3-ALL OPERATOR_GATE" GREEN "$(tail -1 /tmp/m3-all-operator-gate.txt)"
      phase_ok "M3-ALL — whole-plan-set GREEN + predictions frozen + OPERATOR_GATE; proceeding to JIT+M4"
    else
      phase_gate "M3-ALL OPERATOR_GATE" RED "see /tmp/m3-all-operator-gate.txt"
      fail_run "O-M3ALL OPERATOR_GATE RED — approve migration/.m3-all-operator-gate after reviewing predictions (or M3_ALL_OPERATOR_AUTO=1)"
    fi
  else
    phase_gate "M3-ALL whole-set" RED "see /tmp/m3-all-whole.txt"
    fail_run "O-M3ALL whole-set RED — fix plans before any M4 (see /tmp/m3-all-whole.txt)"
  fi
fi
done  # M3_ALL_PASS

phase_ok "Outer loop — all stories shipped; HEAD $(git rev-parse --short HEAD)"
# Keep git remote chatter out of the demo narrative (L-SHIPLOG) — one summary line.
if git push origin main >> /tmp/outer-git-push.log 2>&1; then
  log "         git push: origin/main @ $(git rev-parse --short HEAD) (details /tmp/outer-git-push.log)"
else
  log "         git push: failed — see /tmp/outer-git-push.log (non-fatal at run end)"
fi
# O-TMPARCHIVE — archive via EXIT trap (success path); explicit call keeps log order.
archive_tmp_forensics
echo "outer-complete" > /tmp/outer-loop-done
log "========== RUN COMPLETE — outer-loop exited; marker /tmp/outer-loop-done =========="
log "         Further supervisor activity (e.g. SHIP_ONLY) is NOT a new outer-loop run."
exit 0
