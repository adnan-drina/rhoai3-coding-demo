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
ROOT="$(cd "$(dirname "$0")/../.." ROOT="/Users/adrina/Sandbox/rhoai3-coding-demo"ROOT="/Users/adrina/Sandbox/rhoai3-coding-demo" pwd)"
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
POD="${V8_WS_POD:-workspace2daa86efaa344a9d-6d99c65d69-66dtd}"
CTR=development-tooling
NS=wksp-ai-developer
AUTO_RESTART="${V8_AUTO_RESTART:-1}"
# shellcheck disable=SC1091
source "${ROOT}/scripts/lib.sh"
load_env >/dev/null

restart_outer_if_needed() {
  local snap="$1"
  [ "$AUTO_RESTART" = "1" ] || return 0
  echo "$snap" | grep -q 'outer=DOWN' || return 0
  if echo "$snap" | grep -q 'S05,complete'; then
    return 0
  fi
  echo "O-DRV2: outer=DOWN — auto-restarting outer-loop on $POD"
  oc exec -n "$NS" "$POD" -c "$CTR" -- bash -lc '
    cd /projects/modernized || exit 1
    test -x .hermes/harness/outer-loop.sh || exit 1
    pgrep -f "harness/outer-loop\.sh" >/dev/null && exit 0
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
    # T-NNN work + sensor-fix + debt: T-NNN (O-DRV3 must not skip debt REDs)
    new_commits=$(oc_git log --oneline --no-merges "${last_sha}..${head_sha}" \
      | grep -E '^[0-9a-f]{7,40} (T-[0-9]|debt: T-[0-9])' || true)
  elif [ -z "$last_sha" ] && echo "$head_short" | grep -qE '^[0-9a-f]{7,40} (T-[0-9]|debt: T-[0-9])'; then
    new_commits="$head_short"
  fi

  if [ -n "$last_sha" ] && [ -n "$head_sha" ] && [ "$last_sha" = "$head_sha" ] \
    && [ -z "$new_commits" ]; then
    rm -f "$PENDING_FILE"
    return 0
  fi

  if [ -z "$new_commits" ]; then
    return 0
  fi

  anomaly_on_new=0
  echo "$new_commits" | grep -qiE 'sensor fix|Already satisfied|style-autofix|escalat|debt: T-' \
    && anomaly_on_new=1

  {
    echo "# V9 task analysis PENDING (O-DRV3) — do not clear without a gate entry"
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
    echo "## Mandatory checklist (stage-080-quality-advance task gate)"
    echo
    echo "CRUCIAL: judge AI-generated **code quality** and AI **action quality** —"
    echo "sensor GREEN alone is not a pass."
    echo
    echo "1. \`git show --stat\` + full diff — **read the generated code** (bodies, not titles)."
    echo "2. AI code quality vs task goal/acceptance/legacy (fidelity, real tests, no stubs)."
    echo "3. AI action quality: worker / mechan / O-ESCW / MiniMax / style-autofix / sfix — right action?"
    echo "4. If RED / partial / sfix / escalation: supervisor + dimension logs."
    echo "5. Root cause, harness smells, process-performance waste (quota/thrash/silence)."
    echo "6. Bank every durable gap NOW in \`docs/V7-FUTURE-IMPROVEMENTS.md\` (⬜) — never ask."
    echo "7. Detailed entry in \`docs/V9-QUALITY-GATE.md\` (code + actions + why + bank + next)."
    echo "8. Clear: write \`tmp/V9-TASK-ANALYSIS.sha\` + delete this file."
    echo
    echo "## If MiniMax took over from Qwen (escalation) — MANDATORY"
    echo
    echo "1. Capture escalation in the gate (task id + path)."
    echo "2. Read Qwen logs: \`/tmp/oc-T-NNN.err\` + \`/tmp/oc-T-NNN.json\` + pre-escalation supervisor."
    echo "3. State why the worker failed; review what MiniMax changed."
    echo "4. Durableize (bank ⬜ → implement harness/skill) so MiniMax is not needed next time."
    echo "5. Retest / re-run proof that Qwen completes without takeover for that failure class."
    echo "   MiniMax GREEN alone is NOT closure."
    echo
    echo "Also complete O-DRV4 chat pulse (tmp/V9-CHAT-PULSE-PENDING.md) every tick."
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
    rm -f "$M_PENDING_FILE"
    return 0
  fi

  if [ -z "$new_m" ]; then
    return 0
  fi

  {
    echo "# V9 MILESTONE analysis PENDING (O-DRV5) — comprehensive gate"
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
    echo "## Mandatory checklist (stage-080-quality-advance Milestone M gate)"
    echo
    echo "CRUCIAL: comprehensively judge AI-generated **code quality** and AI **action**"
    echo "quality across this milestone — sensor/pipeline GREEN alone is not a pass."
    echo
    echo "1. **Freeze** outer-loop / supervisor (and keep V8_AUTO_RESTART=0) while reviewing."
    echo "2. Evidence: commits, specs/roadmap/tasks, src/main+test, sensors, escalations —"
    echo "   read code bodies; sample AI outputs; note process performance (waste/thrash)."
    echo "3. Verdict ADVANCE | HOLD | ABORT in \`docs/V9-QUALITY-GATE.md\` (full template),"
    echo "   including explicit AI code-quality and AI-action-quality notes."
    echo "4. Bank every durable gap NOW (⬜) — never ask."
    echo "5. Implement honesty-blocking bank rows before resume / next story."
    echo "6. Clear: write reviewed HEAD to \`tmp/V9-M-ANALYSIS.sha\` and delete this file."
    echo
    echo "Do NOT advance to the next story/M on sensor GREEN alone."
  } >"$M_PENDING_FILE"
}

# O-DRV6: unresolved `debt: T-NNN … RED` must HOLD the agent — not silent advance.
refresh_debt_hold_pending() {
  local head_subj debt_hits
  head_subj=$(oc_git log -1 --format='%s' | head -1)
  debt_hits=$(oc_git log --oneline -15 | grep -E 'debt: T-[0-9].*RED' || true)
  if echo "$head_subj" | grep -qE 'debt: T-[0-9].*RED' || [ -n "$debt_hits" ]; then
    # Only pending if HEAD is debt RED or recent debt not yet cleared by a later GREEN sensor fix
    if echo "$head_subj" | grep -qE 'debt: T-[0-9].*RED'; then
      {
        echo "# V9 DEBT HOLD PENDING (O-DRV6) — do not advance on unresolved sensor debt"
        echo
        echo "- written: \`$(date -u +%Y-%m-%dT%H:%M:%SZ)\`"
        echo "- HEAD subject: \`${head_subj}\`"
        echo
        echo "## Required"
        echo
        echo "1. Chat pulse (O-DRV4 body proof) first."
        echo "2. Freeze or HOLD narrative: advancing past task-sensor RED as debt is a"
        echo "   process smell — root-cause the failures, durableize, re-run proof."
        echo "3. Detailed O-DRV3 gate entry for the debted T-NNN (code + Qwen/MiniMax RCA)."
        echo "4. Clear this file only after HEAD is no longer \`debt: T-… RED\` **or**"
        echo "   a HOLD/ABORT decision is written in \`docs/V9-QUALITY-GATE.md\`."
        echo
        echo "Recent debt commits:"
        echo '```'
        echo "$debt_hits"
        echo '```'
      } >"$DEBT_PENDING"
      return 0
    fi
  fi
  rm -f "$DEBT_PENDING"
}

tick() {
  local ts snap prompt_kind prompt overdue=0 age_note="ack fresh or first tick"
  ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  snap=$(oc exec -n "$NS" "$POD" -c "$CTR" -- bash -lc '
    cd /projects/modernized
    OL=$(pgrep -f "harness/outer-loop\.sh" >/dev/null && echo UP || echo DOWN)
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
    echo "- chat_pulse_overdue: **$( [ "$overdue" = 1 ] && echo YES || echo no )** (O-DRV4 body-proof)"
    echo "- chat_pulse_pending: **YES** → \`tmp/V9-CHAT-PULSE-PENDING.md\` (use \`tmp/v9-chat-pulse.sh\`)"
    echo "- last_chat_ack: \`$(tr -d '[:space:]' <"$CHAT_ACK" 2>/dev/null || echo NONE)\`"
    echo "- chat_body_proof: \`$( [ -f "$CHAT_BODY" ] && echo present || echo MISSING )\`"
    if [ -f "$PENDING_FILE" ]; then
      echo "- task_analysis_pending: **YES** → \`tmp/V9-TASK-ANALYSIS-PENDING.md\` (O-DRV3)"
    else
      echo "- task_analysis_pending: no"
    fi
    if [ -f "$M_PENDING_FILE" ]; then
      echo "- milestone_analysis_pending: **YES** → \`tmp/V9-M-ANALYSIS-PENDING.md\` (O-DRV5)"
    else
      echo "- milestone_analysis_pending: no"
    fi
    if [ -f "$DEBT_PENDING" ]; then
      echo "- debt_hold_pending: **YES** → \`tmp/V9-DEBT-HOLD-PENDING.md\` (O-DRV6)"
    else
      echo "- debt_hold_pending: no"
    fi
    echo "- last_analyzed_sha: \`$(grep -oE '[0-9a-f]{40}' "$ANALYZED_SHA_FILE" 2>/dev/null | head -1 || echo none)\`"
    echo "- last_m_analyzed_sha: \`$(grep -oE '[0-9a-f]{40}' "$M_ANALYZED_SHA_FILE" 2>/dev/null | head -1 || echo none)\`"
    echo
    echo '```'
    echo "$snap"
    echo '```'
  } >"$STATUS"

  # Every tick CRITICAL (O-DRV4). Urgency escalates for overdue / debt / task / milestone.
  prompt_kind="AGENT_LOOP_TICK_v8driver_CRITICAL"
  if [ "$overdue" = "1" ]; then
    prompt="O-DRV4 CHAT PULSE OVERDUE (P0). Post 2-5 lines in chat THEN bash tmp/v9-chat-pulse.sh ${ts} with the SAME text (body proof). Ack-only is invalid. Then O-DRV6/O-DRV5/O-DRV3 pendings. Never go idle."
  elif [ -f "$DEBT_PENDING" ]; then
    prompt="O-DRV4 pulse via tmp/v9-chat-pulse.sh ${ts} FIRST; then O-DRV6 DEBT HOLD (tmp/V9-DEBT-HOLD-PENDING.md) — do not advance past debt RED; analyze + durableize + re-run. Then O-DRV3/O-DRV5."
  elif [ -f "$M_PENDING_FILE" ]; then
    prompt="O-DRV4 pulse via tmp/v9-chat-pulse.sh ${ts} FIRST; then O-DRV5 COMPREHENSIVE MILESTONE GATE (tmp/V9-M-ANALYSIS-PENDING.md). Never skip M gates."
  elif [ -f "$PENDING_FILE" ]; then
    prompt="O-DRV4 pulse via tmp/v9-chat-pulse.sh ${ts} FIRST; then O-DRV3 DETAILED TASK ANALYSIS (tmp/V9-TASK-ANALYSIS-PENDING.md). Bank gaps. Never stay silent."
  else
    prompt="O-DRV4 MANDATORY: chat 2-5 lines + bash tmp/v9-chat-pulse.sh ${ts} (body proof). Script enforces O-DRV3/5/6 — memory is not enough. Never go idle."
  fi

  printf '%s {"ts":"%s","interval_s":%s,"prompt":"%s"}\n' \
    "$prompt_kind" "$ts" "$INTERVAL" "$prompt"
  echo "$snap" | head -8
  echo "O-DRV4: chat pulse REQUIRED this tick (ack ts=${ts}; body proof required)"
  if [ "$overdue" = "1" ]; then
    echo "O-DRV4: OVERDUE — previous pulse missing body proof or too old"
  fi
  if [ -f "$DEBT_PENDING" ]; then
    echo "O-DRV6: debt HOLD PENDING"
  fi
  if [ -f "$PENDING_FILE" ]; then
    echo "O-DRV3: task analysis PENDING"
  fi
  if [ -f "$M_PENDING_FILE" ]; then
    echo "O-DRV5: milestone analysis PENDING"
  fi
}

# Seed ack on start so the first INTERVAL window is the budget (not immediately overdue).
if [ ! -f "$CHAT_ACK" ]; then
  date -u +%Y-%m-%dT%H:%M:%SZ >"$CHAT_ACK"
fi
: >>"$CHAT_LOG"
echo "# chat pulse log (O-DRV4) — append-only" >>"$CHAT_LOG"

tick
while true; do
  sleep "$INTERVAL"
  tick
done
