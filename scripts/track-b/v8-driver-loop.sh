#!/usr/bin/env bash
# Agent wake loop for V9 (Track B) autonomous monitoring.
# Emits a sentinel every INTERVAL so the Cursor agent re-inspects the run.
#
# North star (AGENTS.md): autonomous, swift, hardened, durable, fully
# functional migration — no compromises, no assumptions, no cutting corners.
# Prefer fix + re-run (multiple partial runs) over one broken completion.
#
# Default INTERVAL=120 (2 minutes).
#
# O-DRV2: if outer-loop is DOWN and the story ledger is incomplete, auto-restart
# it (no sticky RUN_BASE). Agent wake is not enough — downtime must self-heal.
#
# O-DRV3: after every new T-NNN / T-NNN sensor-fix commit, emit CRITICAL until
# the agent completes a *detailed* task analysis and clears the pending file.
#
# O-DRV4: EVERY tick requires a user-visible chat pulse — SCRIPT-PROOFED.
# Writing only tmp/V9-CHAT-PULSE.ack is NOT enough (agents faked ack without
# chatting). Required proof per tick:
#   1. Post 2-5 lines in the user chat (human-visible).
#   2. Write tmp/V9-CHAT-PULSE.body with: first line `tick: <ts>`, then ≥2
#      non-empty content lines matching what was posted.
#   3. Write tmp/V9-CHAT-PULSE.ack containing the same <ts>.
#   Prefer: bash tmp/v9-chat-pulse.sh <tick-ts> <<'EOF' ... EOF
# Overdue if ack missing/old OR body missing/mismatched/too short.
#
# O-DRV5: after every new M-milestone completion (M1/M2/M3/M4/M5 — git subjects
# and/or outer-loop OK END lines), emit CRITICAL until the agent completes a
# *comprehensive* milestone gate (freeze harness, full quality-advance loop)
# and clears tmp/V9-M-ANALYSIS-PENDING.md. Not docs-only — script-enforced.
set -uo pipefail
INTERVAL="${V8_DRIVER_INTERVAL:-120}"
STALE_SECS="${V8_CHAT_PULSE_STALE_SECS:-$((INTERVAL * 2 + 30))}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
STATUS="${ROOT}/tmp/V8-DRIVER-STATUS.md"
ANALYZED_SHA_FILE="${ROOT}/tmp/V9-TASK-ANALYSIS.sha"
PENDING_FILE="${ROOT}/tmp/V9-TASK-ANALYSIS-PENDING.md"
M_ANALYZED_SHA_FILE="${ROOT}/tmp/V9-M-ANALYSIS.sha"
M_PENDING_FILE="${ROOT}/tmp/V9-M-ANALYSIS-PENDING.md"
OUTER_M_WATERMARK="${ROOT}/tmp/V9-OUTER-M-WATERMARK"
CHAT_ACK="${ROOT}/tmp/V9-CHAT-PULSE.ack"
CHAT_BODY="${ROOT}/tmp/V9-CHAT-PULSE.body"
CHAT_PENDING="${ROOT}/tmp/V9-CHAT-PULSE-PENDING.md"
CHAT_LOG="${ROOT}/tmp/V9-CHAT-PULSE-LOG.md"
DEBT_PENDING="${ROOT}/tmp/V9-DEBT-HOLD-PENDING.md"
ESC_PENDING="${ROOT}/tmp/V9-ESCALATION-PENDING.md"
HAND_PENDING="${ROOT}/tmp/V9-HANDFIX-PENDING.md"
ADV_PENDING="${ROOT}/tmp/V9-ADVANCE-PENDING.md"
AUTO_RESTART="${V8_AUTO_RESTART:-1}"
# shellcheck disable=SC1091
source "${ROOT}/scripts/track-b/lib-quality-gates.sh"
qg_refuse_retired_wave5_harness
# shellcheck disable=SC1091
source "${ROOT}/scripts/lib.sh"
# lib.sh enables `set -e`; the wake loop must survive a failed tick
# (oc blips, empty greps) or the driver dies silently with an empty log.
set +e
set -uo pipefail
POD="$(qg_ws_pod)"
CTR="$(qg_ws_ctr)"
NS="$(qg_ws_ns)"
# shellcheck disable=SC1091
source "${ROOT}/scripts/track-b/lib-quality-gates.sh"
load_env >/dev/null
set +e
set -uo pipefail
# Always prefer explicit V8_WS_* over stale .env defaults after load_env.
POD="${V8_WS_POD:-$POD}"
CTR="${V8_WS_CONTAINER:-$CTR}"
NS="${V8_WS_NS:-$NS}"

ensure_oc_session() {
  if oc whoami >/dev/null 2>&1; then
    return 0
  fi
  echo "O-DRV-OC: unauthorized — attempting .env re-login"
  set -a
  # shellcheck disable=SC1091
  [ -f "${ROOT}/.env" ] && source "${ROOT}/.env"
  set +a
  if [ -n "${OPENSHIFT_API_URL:-}" ] && [ -n "${OPENSHIFT_USER:-}" ] && [ -n "${OPENSHIFT_PASSWORD:-}" ]; then
    oc login "$OPENSHIFT_API_URL" -u "$OPENSHIFT_USER" -p "$OPENSHIFT_PASSWORD" \
      --insecure-skip-tls-verify=true >/dev/null 2>&1 || true
  fi
  oc whoami >/dev/null 2>&1
}

sha_file_validated() {
  local f="$1"
  [ -f "$f" ] && grep -qE '^# validated:' "$f"
}

restart_outer_if_needed() {
  local snap="$1"
  [ "$AUTO_RESTART" = "1" ] || return 0
  echo "$snap" | grep -q 'outer=DOWN' || return 0
  if echo "$snap" | grep -q 'S05,complete'; then
    return 0
  fi
  # O-DRV2-DONE: intentional outer-complete / abort markers must not be
  # overwritten by blind auto-restart (operator pivot, STOP_AFTER_*, FAIL).
  if ensure_oc_session >/dev/null 2>&1; then
    if oc exec -n "$NS" "$POD" -c "$CTR" -- bash -lc \
      'test -s /tmp/outer-loop-done' 2>/dev/null; then
      echo "O-DRV2: outer=DOWN but /tmp/outer-loop-done present — NOT auto-restarting"
      return 0
    fi
  fi
  # Refuse auto-restart while honesty gates are open
  if [ -f "$DEBT_PENDING" ] || [ -f "$ESC_PENDING" ] || [ -f "$ADV_PENDING" ] || [ -f "$HAND_PENDING" ]; then
    echo "O-DRV2: outer=DOWN but debt/escalation/advance/handfix pending — NOT auto-restarting"
    return 0
  fi
  if [ "${V9_ALLOW_OPEN_BANK:-0}" != "1" ]; then
    if ! bash "${ROOT}/scripts/track-b/v9-bank-gate.sh" honesty >/dev/null 2>&1; then
      echo "O-DRV2: outer=DOWN but honesty bank ⬜ open — NOT auto-restarting (run v9-bank-gate.sh)"
      return 0
    fi
  fi
  # O-DRV2-FAILHOLD: if the latest outer phase line is X FAIL, do not
  # blind-restart into the same failure (and do not skip a RED uncommitted
  # M3 plan into M4). Once a newer START/OK line appears, auto-restart may
  # resume.
  if ensure_oc_session >/dev/null 2>&1; then
    if oc exec -n "$NS" "$POD" -c "$CTR" -- bash -lc \
      'last=$(grep -E "X FAIL|> START|OK END|OK GATE" /tmp/outer-loop.log 2>/dev/null | tail -1)
       echo "$last" | grep -q "X FAIL"' 2>/dev/null; then
      echo "O-DRV2: outer=DOWN after latest X FAIL — NOT auto-restarting (fix HOLD first)"
      printf 'AGENT_LOOP_TICK_v8driver_CRITICAL {"ts":"%s","prompt":"O-DRV2-FAILHOLD: outer DOWN after X FAIL. FIRST: chat pulse + O-DRV4 ack. Then diagnose /tmp/outer-loop.log, bank, durableize, only then preflight --start."}\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
      return 0
    fi
  fi
  echo "O-DRV2: outer=DOWN — auto-restarting outer-loop on $POD"
  ensure_oc_session || { echo "O-DRV2: oc login failed — cannot restart"; return 0; }
  # O-OUTERSTALE: use lock PID (kill -0), never pgrep -f (oc-exec false match).
  oc exec -n "$NS" "$POD" -c "$CTR" -- bash -lc '
    cd /projects/modernized || exit 1
    test -x .hermes/harness/outer-loop.sh || exit 1
    lock=/tmp/outer-loop.lock
    if [ -f "$lock" ]; then
      pid=$(tr -dc "0-9" <"$lock" 2>/dev/null || true)
      if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        echo "O-OUTERSTALE: outer already alive pid=$pid — skip restart"
        exit 0
      fi
      rm -f "$lock"
      echo "O-OUTERSTALE cleared dead pid=${pid:-empty} ($lock)"
    fi
    : >> /tmp/outer-loop.log
    nohup env -u RUN_BASE -u RESUME_RUN_BASE -u RESUME_STORY \
      WORKER_FIRST=true OUTER_LOOP_PLAIN=1 \
      .hermes/harness/outer-loop.sh >> /tmp/outer-loop.log 2>&1 &
    echo restarted_pid=$!
  ' || echo "O-DRV2: auto-restart failed"
  printf 'AGENT_LOOP_TICK_v8driver_CRITICAL {"ts":"%s","prompt":"OUTER-LOOP WAS DOWN — driver auto-restarted. FIRST: post a 2-5 line chat pulse and ack O-DRV4 (tmp/V9-CHAT-PULSE.ack). Then inspect; verify RUN_BASE not sticky; quality-advance; keep driving."}\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}

strip_oc_noise() {
  sed -E \
    -e 's/\x1b\[[0-9;]*[A-Za-z]//g' \
    -e 's/\x1b\][^\x07]*\x07//g' \
    -e 's/\]633;P;HasRichCommandDetection=True//g' \
    -e 's/HasRichCommandDetection=True//g' \
    -e 's/\]633;[^[:space:]]*//g' \
    | tr -d '\000-\010\013\014\016-\037'
}

oc_git() {
  oc exec -n "$NS" "$POD" -c "$CTR" -- \
    git -C /projects/modernized "$@" 2>/dev/null | strip_oc_noise
}

workspace_head_sha() {
  local candidates c
  candidates=$(oc_git rev-parse HEAD)
  candidates="${candidates}"$'\n'"$(oc_git log -1 --format=%H)"
  printf '%s\n' "$candidates" | grep -oE '[0-9a-f]{40}' | while read -r c; do
    if oc_git cat-file -t "$c" 2>/dev/null | grep -qx commit; then
      printf '%s\n' "$c"
      break
    fi
  done | head -1
}

# O-DRV4: return 0 if pulse is missing, stale, or lacks body proof.
# Exit 1 only when ack is fresh AND body proves a real chat pulse for that ts.
chat_pulse_overdue() {
  python3 - "$CHAT_ACK" "$CHAT_BODY" "$STALE_SECS" <<'PY'
import sys, datetime, re
ack_path, body_path, stale = sys.argv[1], sys.argv[2], int(sys.argv[3])

def parse_ts(raw: str):
    raw = raw.strip()
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ"):
        try:
            return datetime.datetime.strptime(raw, fmt).replace(tzinfo=datetime.timezone.utc)
        except ValueError:
            pass
    return None

try:
    ack = open(ack_path).read().strip()
except OSError:
    sys.exit(0)  # overdue — no ack
t = parse_ts(ack)
if t is None:
    sys.exit(0)
age = (datetime.datetime.now(datetime.timezone.utc) - t).total_seconds()
if age > stale:
    sys.exit(0)

# Body proof: tick line must match ack; ≥2 non-empty content lines after it.
try:
    body = open(body_path, encoding="utf-8", errors="replace").read()
except OSError:
    sys.exit(0)  # overdue — ack without body (fake pulse)
lines = [ln.rstrip() for ln in body.splitlines()]
if not lines or not re.match(r"^tick:\s*", lines[0], re.I):
    sys.exit(0)
tick_ts = re.sub(r"^tick:\s*", "", lines[0], flags=re.I).strip()
if tick_ts != ack:
    sys.exit(0)  # body for a different tick
content = [ln for ln in lines[1:] if ln.strip()]
if len(content) < 2:
    sys.exit(0)  # too thin — not a real 2–5 line pulse
sys.exit(1)  # not overdue
PY
}

write_chat_pulse_pending() {
  local ts="$1" snap="$2" overdue="$3" age_note="$4"
  {
    echo "# V9 CHAT PULSE PENDING (O-DRV4) — P0, every tick — SCRIPT-PROOFED"
    echo
    echo "- tick: \`${ts}\`"
    echo "- overdue: \`${overdue}\`"
    echo "- stale_after_s: \`${STALE_SECS}\`"
    echo "- last_ack: \`$(tr -d '[:space:]' <"$CHAT_ACK" 2>/dev/null || echo NONE)\`"
    echo "- body_proof: \`$( [ -f "$CHAT_BODY" ] && echo present || echo MISSING )\`"
    echo "- note: ${age_note}"
    echo
    echo "## You MUST do this before anything else (memory is not enough)"
    echo
    echo "1. Post a **2-5 line chat update to the user** (story/task, HEAD, RED/escalation/HOLD)."
    echo "2. Record the SAME text as body proof + ack (do **not** ack without chatting):"
    echo
    echo '```bash'
    echo "bash tmp/v9-chat-pulse.sh '${ts}' <<'PULSE'"
    echo "<paste the same 2-5 lines you posted in chat>"
    echo "PULSE"
    echo '```'
    echo
    echo "Bare \`printf … > tmp/V9-CHAT-PULSE.ack\` **does not clear** this pending —"
    echo "\`chat_pulse_overdue\` requires \`tmp/V9-CHAT-PULSE.body\` with matching tick + ≥2 lines."
    echo
    echo "3. Then O-DRV3 / O-DRV5 / O-DRV6 pending files if present."
    echo
    echo "## Live snapshot"
    echo
    echo '```'
    echo "$snap" | head -20
    echo '```'
  } >"$CHAT_PENDING"

  {
    echo "- \`${ts}\` overdue=${overdue} ack_was=$(tr -d '[:space:]' <"$CHAT_ACK" 2>/dev/null || echo NONE) body=$( [ -f "$CHAT_BODY" ] && echo yes || echo NO )"
  } >>"$CHAT_LOG"
}

refresh_task_analysis_pending() {
  local last_sha new_commits head_sha head_short anomaly_on_new
  last_sha=""
  if [ -f "$ANALYZED_SHA_FILE" ]; then
    last_sha=$(grep -oE '[0-9a-f]{40}' "$ANALYZED_SHA_FILE" | head -1)
  fi

  head_sha=$(workspace_head_sha)
  head_short=$(oc_git log -1 --format='%h %s' | grep -E '^[0-9a-f]{7,40} ' | head -1)

  new_commits=""
  if [ -n "$last_sha" ] && [ -n "$head_sha" ] && [ "$last_sha" != "$head_sha" ]; then
    # T-NNN work + sensor-fix + debt tips (O-DRV3 / O-DEBTMSUBJ: include
    # milestone debt subjects like `debt: m5-evaluate milestone RED`, not only
    # `debt: T-NNN`).
    new_commits=$(oc_git log --oneline --no-merges "${last_sha}..${head_sha}" \
      | grep -E '^[0-9a-f]{7,40} (T-[0-9]|debt: )' || true)
  elif [ -z "$last_sha" ] && echo "$head_short" | grep -qE '^[0-9a-f]{7,40} (T-[0-9]|debt: )'; then
    new_commits="$head_short"
  fi

  if [ -n "$last_sha" ] && [ -n "$head_sha" ] && [ "$last_sha" = "$head_sha" ] \
    && [ -z "$new_commits" ]; then
    # Only trust clears that went through v9-clear-task-analysis.sh
    if sha_file_validated "$ANALYZED_SHA_FILE"; then
      rm -f "$PENDING_FILE"
    fi
    return 0
  fi

  if [ -z "$new_commits" ]; then
    return 0
  fi

  anomaly_on_new=0
  echo "$new_commits" | grep -qiE 'sensor fix|Already satisfied|style-autofix|escalat|debt: ' \
    && anomaly_on_new=1

  {
    echo "# V9 task analysis PENDING (O-DRV3) — SCRIPT-CLEARED ONLY"
    echo
    echo "- written: \`$(date -u +%Y-%m-%dT%H:%M:%SZ)\`"
    echo "- workspace_HEAD: \`${head_sha:-unknown}\`"
    echo "- last_analyzed_sha: \`${last_sha:-none}\`"
    echo "- anomaly_on_new_commits: \`${anomaly_on_new}\`"
    echo
    echo "## Commits to analyze (detailed — not a one-liner)"
    echo
    echo '```'
    echo "$new_commits"
    echo '```'
    echo
    echo "## Clear path (memory is not enough)"
    echo
    echo '```bash'
    echo "bash scripts/track-b/v9-capture-diff.sh --oc ${head_sha:-HEAD}"
    echo "# write detailed docs/V10-QUALITY-GATE.md section (code + action quality)"
    echo "# ALSO append Implementing note citing this sha in tmp/KAI-WAVE5-REVIEW.md"
    echo "bash scripts/track-b/v9-clear-task-analysis.sh ${head_sha:-SHA}"
    echo '```'
    echo
    echo "Bare \`echo SHA > tmp/V9-TASK-ANALYSIS.sha\` does **not** clear —"
    echo "sha file must contain \`# validated:\` from the clear script."
    echo "Clear also requires an Implementing note in \`tmp/KAI-WAVE5-REVIEW.md\`"
    echo "that cites the sha (Wave-1 handshake — gate log alone fails)."
    echo
    echo "## Mandatory checklist"
    echo
    echo "1. Capture diff evidence + **read the generated code**."
    echo "2. AI code quality vs task goal/acceptance/legacy."
    echo "3. AI action quality: worker / mechan / MiniMax / sfix."
    echo "4. Bank every durable gap (⬜). Write Implementing note in review doc."
    echo "5. Clear via script above (not bare sha write)."
    echo
    echo "If MiniMax escalation: clear \`tmp/V9-ESCALATION-PENDING.md\` first"
    echo "via \`v9-clear-escalation.sh\`."
  } >"$PENDING_FILE"
}

# O-DRV5: detect new M1–M5 / story-spec / story-complete milestones.
refresh_milestone_analysis_pending() {
  local last_sha head_sha new_m outer_line prev_wm
  last_sha=""
  if [ -f "$M_ANALYZED_SHA_FILE" ]; then
    last_sha=$(grep -oE '[0-9a-f]{40}' "$M_ANALYZED_SHA_FILE" | head -1)
  fi
  # Fall back to task-analyzed tip so we don't replay entire history on first boot.
  if [ -z "$last_sha" ] && [ -f "$ANALYZED_SHA_FILE" ]; then
    last_sha=$(grep -oE '[0-9a-f]{40}' "$ANALYZED_SHA_FILE" | head -1)
  fi

  head_sha=$(workspace_head_sha)
  new_m=""
  if [ -n "$last_sha" ] && [ -n "$head_sha" ] && [ "$last_sha" != "$head_sha" ]; then
    new_m=$(oc_git log --oneline --no-merges "${last_sha}..${head_sha}" \
      | grep -E '^[0-9a-f]{7,40} (M1 |M2 sequence:|M5 evaluate:|S0[0-9] spec:|S0[0-9] story complete:)' \
      || true)
  fi

  # Outer-loop OK END markers (covers M3/M4 that may not always commit a unique subject).
  outer_line=$(oc exec -n "$NS" "$POD" -c "$CTR" -- bash -lc \
    'grep -E "OK END[[:space:]]+(M[1-5]|M4/M5)" /tmp/outer-loop.log 2>/dev/null | tail -1' \
    2>/dev/null | strip_oc_noise || true)
  prev_wm=""
  [ -f "$OUTER_M_WATERMARK" ] && prev_wm=$(tr -d '\n' <"$OUTER_M_WATERMARK")
  if [ -n "$outer_line" ] && [ "$outer_line" != "$prev_wm" ]; then
    if [ -n "$new_m" ]; then
      new_m="${new_m}"$'\n'"OUTER: ${outer_line}"
    else
      new_m="OUTER: ${outer_line}"
    fi
    printf '%s\n' "$outer_line" >"$OUTER_M_WATERMARK"
  fi

  if [ -n "$last_sha" ] && [ -n "$head_sha" ] && [ "$last_sha" = "$head_sha" ] \
    && [ -z "$new_m" ]; then
    if sha_file_validated "$M_ANALYZED_SHA_FILE"; then
      rm -f "$M_PENDING_FILE"
    fi
    return 0
  fi

  if [ -z "$new_m" ]; then
    return 0
  fi

  {
    echo "# V9 MILESTONE analysis PENDING (O-DRV5) — SCRIPT-CLEARED ONLY"
    echo
    echo "- written: \`$(date -u +%Y-%m-%dT%H:%M:%SZ)\`"
    echo "- workspace_HEAD: \`${head_sha:-unknown}\`"
    echo "- last_m_analyzed_sha: \`${last_sha:-none}\`"
    echo
    echo "## Milestones to review (COMPREHENSIVE — freeze harness)"
    echo
    echo '```'
    echo "$new_m"
    echo '```'
    echo
    echo "## Clear path"
    echo
    echo '```bash'
    echo "# write comprehensive docs/V10-QUALITY-GATE.md with **Verdict:** ADVANCE|HOLD|ABORT"
    echo "# ALSO append Implementing note citing this sha in tmp/KAI-WAVE5-REVIEW.md"
    echo "bash scripts/track-b/v9-clear-m-analysis.sh ${head_sha:-SHA}"
    echo '```'
    echo
    echo "Bare sha write does **not** clear — needs \`# validated:\` from clear script."
    echo "Clear also requires an Implementing note in \`tmp/KAI-WAVE5-REVIEW.md\`"
    echo "that cites the sha (Wave-1 handshake)."
  } >"$M_PENDING_FILE"
}

# O-DRV6: unresolved debt RED — HEAD or ledger or recent debt commits.
refresh_debt_hold_pending() {
  local head_subj debt_hits ledger_n
  head_subj=$(oc_git log -1 --format='%s' | head -1)
  # O-DEBTMSUBJ: match any `debt: … RED` tip (task or milestone/m5-evaluate).
  debt_hits=$(oc_git log --oneline -20 | grep -E 'debt: .*RED' || true)
  ledger_n=$(oc exec -n "$NS" "$POD" -c "$CTR" -- bash -lc \
    'grep -c "^## " migration/debt.md 2>/dev/null || echo 0' 2>/dev/null | strip_oc_noise | tr -d '[:space:]')
  ledger_n=${ledger_n:-0}
  if echo "$head_subj" | grep -qE 'debt: .*RED' \
    || [ -n "$debt_hits" ] \
    || { [ "$ledger_n" -gt 0 ] 2>/dev/null; }; then
    {
      echo "# V9 DEBT HOLD PENDING (O-DRV6) — do not advance on unresolved sensor debt"
      echo
      echo "- written: \`$(date -u +%Y-%m-%dT%H:%M:%SZ)\`"
      echo "- HEAD subject: \`${head_subj}\`"
      echo "- debt_ledger_entries: \`${ledger_n}\`"
      echo
      echo "## Required"
      echo
      echo "1. Chat pulse (O-DRV4) first."
      echo "2. Harness should have frozen (O-DEBTFRZ) — do not nurse past RED."
      echo "3. O-DRV3 gate + durableize + re-run."
      echo "4. Clear only when ledger has no \`##\` entries **and** HOLD/ABORT written,"
      echo "   via deleting this file after gate proof (driver re-checks ledger)."
      echo
      echo "Recent debt commits:"
      echo '```'
      echo "$debt_hits"
      echo '```'
    } >"$DEBT_PENDING"
    return 0
  fi
  rm -f "$DEBT_PENDING"
}

# O-DRV7: MiniMax-over-Qwen escalation → blocking pending until RCA clear script.
# O-DRV7DET: supervisor stamps escalation only in log_task lines
# ("committed via MiniMax escalation"), not in git subjects — detect from
# /tmp/supervisor.log (+ outer-loop), with commit-subject grep as secondary.
refresh_escalation_pending() {
  local last_sha head_sha esc_commits esc_logs task seen_file log_wm log_line log_key
  [ -f "$ESC_PENDING" ] && return 0
  seen_file="${ROOT}/tmp/V9-ESCALATION-SEEN.sha"
  log_wm="${ROOT}/tmp/V9-ESCALATION-LOG.wm"
  last_sha=""
  if [ -f "$ANALYZED_SHA_FILE" ]; then
    last_sha=$(grep -oE '[0-9a-f]{40}' "$ANALYZED_SHA_FILE" | head -1)
  fi
  head_sha=$(workspace_head_sha)
  [ -n "$head_sha" ] || return 0

  esc_commits=""
  if [ -n "$last_sha" ] && [ "$last_sha" != "$head_sha" ]; then
    esc_commits=$(oc_git log --format='%h %s' --no-merges "${last_sha}..${head_sha}" \
      | grep -iE 'via MiniMax escalation|MiniMax escalation' || true)
  fi

  # Primary: supervisor/outer log lines (O-DRV7DET)
  esc_logs=$(oc exec -n "$NS" "$POD" -c "$CTR" -- bash -lc \
    'grep -E "committed via MiniMax escalation|Actor:.*escalation" /tmp/supervisor.log /tmp/outer-loop.log 2>/dev/null | tail -30' \
    2>/dev/null | strip_oc_noise || true)
  log_line=""
  if [ -n "$esc_logs" ]; then
    log_line=$(echo "$esc_logs" | tail -1)
    log_key=$(printf '%s' "$log_line" | shasum -a 256 2>/dev/null | awk '{print $1}')
    if [ -f "$log_wm" ] && [ -n "$log_key" ] && grep -qxF "$log_key" "$log_wm" 2>/dev/null; then
      log_line=""  # already issued pending for this log event
    fi
  fi

  # Already issued pending for this HEAD tip (commit-subject path)
  if [ -z "$log_line" ] && [ -z "$esc_commits" ]; then
    return 0
  fi
  if [ -z "$log_line" ] && [ -f "$seen_file" ] && grep -q "$head_sha" "$seen_file" 2>/dev/null; then
    return 0
  fi

  task=$( { echo "$log_line"; echo "$esc_commits"; } | grep -oE 'T-[0-9]+' | head -1 || echo T-NNN)
  {
    echo "# V9 ESCALATION PENDING (O-DRV7) — MiniMax-over-Qwen"
    echo
    echo "- written: \`$(date -u +%Y-%m-%dT%H:%M:%SZ)\`"
    echo "- task_hint: \`${task}\`"
    echo "- workspace_HEAD: \`${head_sha}\`"
    echo
    echo "## Evidence"
    echo '```'
    [ -n "$log_line" ] && echo "LOG: $log_line"
    [ -n "$esc_commits" ] && echo "$esc_commits"
    echo '```'
    echo
    echo "## Clear (required — blocks O-DRV3 clear)"
    echo
    echo '```bash'
    echo "bash scripts/track-b/v9-clear-escalation.sh ${task} \\"
    echo "  --qwen-cause '...' --bank-id O-XXX --retest '...'"
    echo '```'
    echo
    echo "Must include Qwen log RCA + bank id + retest note. MiniMax GREEN ≠ clear."
  } >"$ESC_PENDING"
  printf '%s\n' "$head_sha" >"$seen_file"
  if [ -n "${log_key:-}" ]; then
    printf '%s\n' "$log_key" >"$log_wm"
  fi
}

# O-ADV: story-complete without ADVANCE verdict → pending
refresh_advance_pending() {
  local last_sha head_sha story_line story
  [ -f "$ADV_PENDING" ] && return 0
  last_sha=""
  if [ -f "$M_ANALYZED_SHA_FILE" ]; then
    last_sha=$(grep -oE '[0-9a-f]{40}' "$M_ANALYZED_SHA_FILE" | head -1)
  fi
  head_sha=$(workspace_head_sha)
  story_line=""
  if [ -n "$last_sha" ] && [ -n "$head_sha" ] && [ "$last_sha" != "$head_sha" ]; then
    story_line=$(oc_git log --oneline --no-merges "${last_sha}..${head_sha}" \
      | grep -E 'S0[0-9] story complete:' | head -1 || true)
  fi
  [ -n "$story_line" ] || return 0
  story=$(echo "$story_line" | grep -oE 'S0[0-9]' | head -1)
  [ -n "$story" ] || return 0
  if bash "${ROOT}/scripts/track-b/v9-advance-gate.sh" check "$story" >/dev/null 2>&1; then
    return 0
  fi
  bash "${ROOT}/scripts/track-b/v9-advance-gate.sh" pending "$story" || true
}

tick() {
  local ts snap prompt_kind prompt overdue=0 age_note="ack fresh or first tick"
  ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  ensure_oc_session || {
    echo "O-DRV-OC: still unauthorized — tick degraded"
    printf 'AGENT_LOOP_TICK_v8driver_CRITICAL {"ts":"%s","prompt":"OC LOGIN FAILED — fix .env OPENSHIFT_* / re-login; driver cannot observe workspace."}\n' "$ts"
    return 0
  }
  snap=$(oc exec -n "$NS" "$POD" -c "$CTR" -- bash -lc '
    cd /projects/modernized
    # O-OUTERSTALE: lock-PID liveness (pgrep -f false-matches oc-exec)
    OL=DOWN
    if [ -f /tmp/outer-loop.lock ]; then
      _opid=$(tr -dc "0-9" </tmp/outer-loop.lock 2>/dev/null || true)
      if [ -n "$_opid" ] && kill -0 "$_opid" 2>/dev/null; then OL=UP
      else rm -f /tmp/outer-loop.lock; fi
    fi
    SUP=$(pgrep -f "harness/supervisor\.sh" >/dev/null && echo UP || echo DOWN)
    H=$(pgrep -f "venv/bin/python.*hermes chat" >/dev/null && echo UP || echo DOWN)
    OC=$(pgrep -f "[o]pencode (run|serve)" >/dev/null && echo UP || echo DOWN)
    HEAD=$(git log -1 --format="%h %s")
    HETIME=$(ps -o etime= -p $(pgrep -f "venv/bin/python.*hermes chat" | head -1) 2>/dev/null | tr -d " " || echo -)
    STORY=$(tail -n +2 migration/story-state.csv 2>/dev/null | paste -sd, - || echo none)
    JAVA=$(find src/main/java -type f 2>/dev/null | wc -l | tr -d " ")
    SPECS=$(ls -d specs/S0* 2>/dev/null | xargs -n1 basename 2>/dev/null | paste -sd, - || echo none)
    SUP_LAST=$(grep -E "^\[20|batch:|sensor|SHIP|FAIL|success|ALREADY|sensor-fix|already committed|escalat|O-ESCW|pipeline|style-autofix|SENSOR RED" /tmp/supervisor.log 2>/dev/null | tail -8 | tr "\n" " | ")
    OUTER_LAST=$(grep -E "^\[20" /tmp/outer-loop.log 2>/dev/null | tail -5 | tr "\n" " | ")
    echo "outer=$OL supervisor=$SUP hermes=$H opencode=$OC hermes_etime=$HETIME java=$JAVA"
    echo "head=$HEAD"
    echo "story_state=$STORY"
    echo "specs=$SPECS"
    echo "outer_tail=$OUTER_LAST"
    echo "sup_tail=$SUP_LAST"
  ' 2>/dev/null | strip_oc_noise | sed -E 's/sk-[A-Za-z0-9_-]+/[REDACTED]/g' || echo "oc_exec_failed")

  restart_outer_if_needed "$snap"
  refresh_task_analysis_pending
  refresh_milestone_analysis_pending
  refresh_debt_hold_pending
  refresh_escalation_pending
  refresh_advance_pending
  bash "${ROOT}/scripts/track-b/v9-handfix-detect.sh" >/dev/null 2>&1 || true

  if chat_pulse_overdue; then
    overdue=1
    age_note="ACK/BODY MISSING, STALE, OR BODY LACKS PROOF — agent silent or faked ack (O-DRV4 P0)"
  fi
  # Always (re)write pulse pending so the required ack ts is this tick.
  write_chat_pulse_pending "$ts" "$snap" "$overdue" "$age_note"

  {
    echo "# V9 driver status (2-minute ticks)"
    echo
    echo "- tick: \`${ts}\`"
    echo "- interval: ${INTERVAL}s"
    echo "- auto_restart: ${AUTO_RESTART}"
    echo "- driver_pid: \`$$\`"
    echo "- chat_pulse_overdue: **$( [ "$overdue" = 1 ] && echo YES || echo no )** (O-DRV4 body+transcript)"
    echo "- chat_pulse_pending: **YES** → \`tmp/V9-CHAT-PULSE-PENDING.md\` (use \`tmp/v9-chat-pulse.sh\`)"
    echo "- last_chat_ack: \`$(tr -d '[:space:]' <"$CHAT_ACK" 2>/dev/null || echo NONE)\`"
    echo "- chat_body_proof: \`$( [ -f "$CHAT_BODY" ] && echo present || echo MISSING )\`"
    if [ -f "$PENDING_FILE" ]; then
      echo "- task_analysis_pending: **YES** → \`tmp/V9-TASK-ANALYSIS-PENDING.md\` (O-DRV3 clear script)"
    else
      echo "- task_analysis_pending: no"
    fi
    if [ -f "$M_PENDING_FILE" ]; then
      echo "- milestone_analysis_pending: **YES** → \`tmp/V9-M-ANALYSIS-PENDING.md\` (O-DRV5 clear script)"
    else
      echo "- milestone_analysis_pending: no"
    fi
    if [ -f "$DEBT_PENDING" ]; then
      echo "- debt_hold_pending: **YES** → \`tmp/V9-DEBT-HOLD-PENDING.md\` (O-DRV6)"
    else
      echo "- debt_hold_pending: no"
    fi
    if [ -f "$ESC_PENDING" ]; then
      echo "- escalation_pending: **YES** → \`tmp/V9-ESCALATION-PENDING.md\` (O-DRV7)"
    else
      echo "- escalation_pending: no"
    fi
    if [ -f "$HAND_PENDING" ]; then
      echo "- handfix_pending: **YES** → \`tmp/V9-HANDFIX-PENDING.md\` (O-HAND)"
    else
      echo "- handfix_pending: no"
    fi
    if [ -f "$ADV_PENDING" ]; then
      echo "- advance_pending: **YES** → \`tmp/V9-ADVANCE-PENDING.md\` (O-ADV)"
    else
      echo "- advance_pending: no"
    fi
    echo "- last_analyzed_sha: \`$(grep -oE '[0-9a-f]{40}' "$ANALYZED_SHA_FILE" 2>/dev/null | head -1 || echo none)\` validated=$(sha_file_validated "$ANALYZED_SHA_FILE" && echo yes || echo NO)"
    echo "- last_m_analyzed_sha: \`$(grep -oE '[0-9a-f]{40}' "$M_ANALYZED_SHA_FILE" 2>/dev/null | head -1 || echo none)\` validated=$(sha_file_validated "$M_ANALYZED_SHA_FILE" && echo yes || echo NO)"
    echo
    echo '```'
    echo "$snap"
    echo '```'
  } >"$STATUS"

  # Every tick CRITICAL (O-DRV4). Urgency escalates for overdue / debt / escalations.
  prompt_kind="AGENT_LOOP_TICK_v8driver_CRITICAL"
  if [ "$overdue" = "1" ]; then
    prompt="O-DRV4 CHAT PULSE OVERDUE (P0). Post in chat THEN bash tmp/v9-chat-pulse.sh ${ts} (transcript fidelity). Then pendings."
  elif [ -f "$DEBT_PENDING" ]; then
    prompt="O-DRV4 pulse ${ts} FIRST; O-DRV6 DEBT HOLD — freeze/durableize/re-run. Clear scripts only."
  elif [ -f "$ESC_PENDING" ]; then
    prompt="O-DRV4 pulse ${ts} FIRST; O-DRV7 ESCALATION — v9-clear-escalation.sh after Qwen RCA+bank+retest."
  elif [ -f "$ADV_PENDING" ]; then
    prompt="O-DRV4 pulse ${ts} FIRST; O-ADV — write ADVANCE in docs/V10-QUALITY-GATE.md then v9-advance-gate.sh clear."
  elif [ -f "$M_PENDING_FILE" ]; then
    prompt="O-DRV4 pulse ${ts} FIRST; O-DRV5 — v9-clear-m-analysis.sh after comprehensive gate+Verdict."
  elif [ -f "$PENDING_FILE" ]; then
    prompt="O-DRV4 pulse ${ts} FIRST; O-DRV3 — v9-capture-diff.sh + gate entry + v9-clear-task-analysis.sh."
  else
    prompt="O-DRV4: chat + tmp/v9-chat-pulse.sh ${ts}. Quality clears are script-only (see scripts/track-b/)."
  fi

  printf '%s {"ts":"%s","interval_s":%s,"prompt":"%s"}\n' \
    "$prompt_kind" "$ts" "$INTERVAL" "$prompt"
  echo "$snap" | head -8
  echo "O-DRV4: chat pulse REQUIRED this tick (ack ts=${ts}; body+transcript proof)"
  if [ "$overdue" = "1" ]; then
    echo "O-DRV4: OVERDUE — previous pulse missing body proof or too old"
  fi
  [ -f "$DEBT_PENDING" ] && echo "O-DRV6: debt HOLD PENDING"
  [ -f "$ESC_PENDING" ] && echo "O-DRV7: escalation PENDING"
  [ -f "$ADV_PENDING" ] && echo "O-ADV: advance PENDING"
  [ -f "$HAND_PENDING" ] && echo "O-HAND: handfix PENDING"
  [ -f "$PENDING_FILE" ] && echo "O-DRV3: task analysis PENDING"
  [ -f "$M_PENDING_FILE" ] && echo "O-DRV5: milestone analysis PENDING"
}

# Seed ack on start so the first INTERVAL window is the budget (not immediately overdue).
if [ ! -f "$CHAT_ACK" ]; then
  date -u +%Y-%m-%dT%H:%M:%SZ >"$CHAT_ACK"
fi
: >>"$CHAT_LOG"
echo "# chat pulse log (O-DRV4) — append-only" >>"$CHAT_LOG"

# set -e must not kill the wake loop if a single tick helper returns non-zero
# (grep -q misses, oc flakes, etc.). Tick failures are logged; the driver stays up.
run_tick() {
  if ! tick; then
    echo "O-DRV: tick returned non-zero (ignored — loop continues)" >&2
  fi
}

run_tick
while true; do
  sleep "$INTERVAL"
  run_tick
done
