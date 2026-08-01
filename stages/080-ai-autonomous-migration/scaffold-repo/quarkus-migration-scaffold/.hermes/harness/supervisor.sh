#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Stage 080 harness SUPERVISOR — drives the full autonomous migration:
#   M1 (ground truth) -> M3 (plan) -> M4 (task loop)
#   -> M5 evaluate (final sensors) -> M5 ship (ship through the factory gate)
#
# The supervisor owns LOOP CONTROL and FAILURE CLASSIFICATION; the
# orchestrator model owns judgment inside each session. Session outcomes
# are classified so platform faults (quota, stream stalls, context
# overflows) are retried WITHOUT burning the task's attempt budget, while
# genuine no-progress sessions consume attempts and fall through to the
# debt policy.
#
# Run inside the migration workspace:
#   nohup .hermes/harness/supervisor.sh > /tmp/supervisor-nohup.log 2>&1 &
# Progress:  tail -f /tmp/supervisor.log
# ---------------------------------------------------------------------------
set -u
export PATH=$HOME/.opencode/bin:$HOME/.local/bin:$PATH
cd /projects/modernized

# Single-instance guard (V3 incident: a failed-pull launch script started
# one supervisor, its retry started another — two writers on one tree).
# O-SUPCMDLINE / O-SUPFLOCK: never use bare pgrep -f (oc-exec -lc text and
# even argv-shaped matches false-positive → refuse start → no-done → false
# S0N,failed). Hold an exclusive flock for the life of this process.
SUPERVISOR_LOCK="${SUPERVISOR_LOCK:-/tmp/supervisor.lock}"
exec 9>"$SUPERVISOR_LOCK"
if ! flock -n 9; then
  echo "FATAL: another supervisor holds $SUPERVISOR_LOCK — refusing to start" >&2
  exit 1
fi
printf '%s\n' "$$" >&9
# Keep FD 9 open (flock) until process exit.

ORCH_PROVIDER="${ORCH_PROVIDER:-custom:maas-m2}"
ORCH_MODEL="${ORCH_MODEL:-minimax-m2}"
WORKER_MODEL="${WORKER_MODEL:-qwen27b/qwen3-6-27b}"
# V7: MiniMax is rate-limited; Qwen has unlimited tokens. Mechanical M4
# coding (rewrite + infer) goes to OpenCode/Qwen first. MiniMax/Hermes is
# for orchestration + escalation + capped rescues.
# O-SFIXWORKER: sensor-fix also goes to Qwen first; MiniMax rescues once
# if the triggering sensor is still RED (Wave2 budget: sfix was the
# heaviest MiniMax consumer and has a cheap verifier).
WORKER_FIRST="${WORKER_FIRST:-true}"
WORKER_SFIX_FIRST="${WORKER_SFIX_FIRST:-${WORKER_FIRST}}"
# O-SFIXWORKER: hard ceiling on MiniMax sfix rescues per post-commit (R-218).
SFIX_MINIMAX_RESCUE_MAX="${SFIX_MINIMAX_RESCUE_MAX:-1}"
SESSION_TIMEOUT="${SESSION_TIMEOUT:-2700}"
FIX_TIMEOUT="${FIX_TIMEOUT:-900}"
MAX_ATTEMPTS=2            # judgment attempts per stage (platform faults excluded)
MAX_PLATFORM_RETRIES=4    # consecutive platform-fault retries per stage
# O-DEBTFRZ: clear stale freeze from a prior supervisor death unless kept.
if [ "${V9_KEEP_DEBT_FREEZE:-0}" != "1" ]; then
  rm -f /tmp/debt-freeze /tmp/supervisor-pause
fi

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

RUN_BASE="${RUN_BASE:-$(git rev-parse HEAD)}"   # commits after this belong to THIS run (env-overridable for resume)
TASKS_SINCE_MILESTONE=0   # supervisor-enforced in-loop sonar cadence
SUPERVISOR_VERSION=$(md5sum "$0" 2>/dev/null | cut -c1-8)
LOG=/tmp/supervisor.log
OUTER_LOG="${OUTER_LOG:-/tmp/outer-loop.log}"
EVENTS=/tmp/supervisor-events.csv
METRICS=/tmp/supervisor-metrics.csv
[ -f "$EVENTS" ]  || echo "epoch,stage,attempt,class,action" > "$EVENTS"
[ -f "$METRICS" ] || echo "session,start,end,seconds,rc" > "$METRICS"

log()   { echo "[$(date -u +%F' '%T)] $*" >> "$LOG"; }
# Mirror demo-facing lines into the outer-loop narrative (tail -f /tmp/outer-loop.log).
# SHIP_ONLY must not emit M4 "Models:" lines that look like a live story run (L-SHIPLOG).
outer_log() { echo "[$(date -u +%F' '%T)] $*" >> "$OUTER_LOG"; }

log "supervisor start: version=${SUPERVISOR_VERSION} run_base=${RUN_BASE} orch=${ORCH_PROVIDER}/${ORCH_MODEL} worker=${WORKER_MODEL} worker_first=${WORKER_FIRST} ship_only=${SHIP_ONLY:-0}"
# O-WEDGERESUME: a fresh supervisor must not inherit /tmp/worker-wedge-skip
# from an aborted prior process (Wave2 T-019 / S03 abort) — that forced MiniMax
# for every later task even after tip advanced.
if [ -f /tmp/worker-wedge-skip ]; then
  log "O-WEDGERESUME: clearing stale worker-wedge-skip at supervisor start"
  rm -f /tmp/worker-wedge-skip
fi
# O-SENSORGATE (N12): install commit-msg hook so Hermes/opencode cannot land
# T-NNN tips on a RED task sensor (S02: 11 sensor_red_post_commit events).
if [ -f .hermes/harness/sensor-gate.py ]; then
  python3 .hermes/harness/sensor-gate.py install-hook "$PWD" >>"$LOG" 2>&1 \
    && log "O-SENSORGATE: commit-msg hook installed" \
    || log "WARN: O-SENSORGATE hook install failed"
fi
if [ "${SHIP_ONLY:-}" = "1" ]; then
  outer_log "> START  SHIP_ONLY — acceptance re-earn (not outer-loop; details ${LOG})"
  outer_log "         Models: $(orch_label) · $(worker_label) | mode=SHIP_ONLY (skip M1–M4 / evaluate)"
else
  outer_log "         Models: $(orch_label) · $(worker_label) | M4 coding → worker first (MiniMax escalation only)"
fi
# C1: per-run isolated Maven repo — factory-parity resolution for every sensor
.hermes/harness/sensors.sh seed >> "$LOG" 2>&1 || log "WARN: isolated repo seed failed — sensors fall back to red-on-use"
event() { echo "$(date -u +%s),$1,$2,$3,$4" >> "$EVENTS"; }

# K11: per-Findings-rule outcome for O-DRV5 / run-report aggregation.
record_rule_outcomes() { # $1=tid $2=outcome-token
  local tid="$1" outcome="$2" ids
  [ -n "${TASKS_FILE:-}" ] && [ -f "$TASKS_FILE" ] || return 0
  ids=$(python3 - "$TASKS_FILE" "$tid" <<'PY' 2>/dev/null || true
import re, sys
text = open(sys.argv[1], encoding="utf-8", errors="replace").read()
tid = sys.argv[2]
heads = list(re.finditer(r"^#{2,6}\s+(T[-A-Za-z0-9]*\d+)\s*:", text, re.M))
body = ""
for i, m in enumerate(heads):
    if m.group(1) != tid:
        continue
    end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
    body = text[m.end():end]
    break
ids = []
for m in re.finditer(r"(?im)^\s*-?\s*\*\*Findings\*\*:\s*(.+)$", body):
    ids.extend(re.findall(r"[a-z][a-z0-9_-]*-\d+", m.group(1), re.I))
print(" ".join(dict.fromkeys(ids)))
PY
)
  for rid in $ids; do
    [ -n "$rid" ] || continue
    event "$tid" 0 "rule:${rid}" "$outcome"
  done
}

# K9: seed forward-looking discovered channel (not debt).
ensure_discovered() {
  [ -f migration/discovered.md ] && return 0
  mkdir -p migration
  cat > migration/discovered.md <<'EOF'
# Discovered work (K9)

Forward-looking scope intelligence — **not** sensor debt (`migration/debt.md`).
Workers append out-of-scope needs here instead of acting on them.

| when (UTC) | task | file/area | need |
|---|---|---|---|
EOF
}

# Process contract only — ALL judgment guidance (packet rules, sensors,
# gate bars, dispatch discipline) lives in the migration-harness skill
# and AGENTS.md. The supervisor injects nothing but run configuration
# and the commit/ship contract.
RUN_CONTRACT="Run contract: the worker model for this run is WORKER_MODEL_PLACEHOLDER. DO NOT PUSH anywhere - the supervisor ships. Finish with ONE commit using the exact message prefix stated below.
O-ANTISCOPE: Other problems will be solved in subsequent steps — edit ONLY this task's Owns/Target paths; do not expand scope.
O-NULLACTION: If after a few honest attempts the issue cannot be solved without fabricating APIs or weakening tests, write /tmp/escalation-noaction-<tag>.txt with a one-line reason and STOP — that is success, not a burn.
O-ADDLINFO: End your session notes with ADDITIONAL-WORK: <bullets or none> (K9 feed)."
RUN_CONTRACT="${RUN_CONTRACT//WORKER_MODEL_PLACEHOLDER/$WORKER_MODEL}"

committed() {
  # O-FGRETRO: probe harden may invalidate prior ALREADY COMPLETE skips.
  if [ -f /tmp/fgretro-reopen.txt ] && grep -qx "$1" /tmp/fgretro-reopen.txt 2>/dev/null; then
    return 1
  fi
  git log --oneline "${RUN_BASE}..HEAD" | grep -q " $1:"
}

# O-T6b / O-T6c / O-STY / O-T1FINDINGS: never sweep harness, staging, or the
# kantra working inventory into T-NNN commits (R-219 T-004: findings-current
# alone became a wrong-title "Remove Spring deps" mechan commit).
# O-SPECFROZEN (R-229): stories marked complete in story-state.csv must not
# have their specs/*/ rewritten (M3 revision / confused worker gutted S01
# mid-S03 because dead-task lint noise). Last csv status wins.
complete_story_ids() {
  [ -f migration/story-state.csv ] || return 0
  awk -F, 'NF>=2 { st[$1]=$2 } END { for (s in st) if (st[s]=="complete") print s }' \
    migration/story-state.csv 2>/dev/null
}

# Paths under specs/<SID>-*/ or specs/<SID>/ for complete stories, excluding
# the in-flight STORY_TASKS file when that story is not yet complete.
frozen_spec_paths() {
  local sid d cur=""
  cur=$(printf '%s' "${STORY_TASKS:-${TASKS_FILE:-}}" | sed -n 's#^\(specs/[^/]*\)/.*#\1#p')
  for sid in $(complete_story_ids); do
    for d in specs/"${sid}"-*/ specs/"${sid}"/; do
      [ -d "$d" ] || continue
      # Never freeze the active story dir if it somehow flipped complete mid-run.
      case "$d" in "${cur}"|"${cur}/") continue ;; esac
      printf '%s\n' "$d"
    done
  done
}

restore_frozen_specs() {
  local d f
  for d in $(frozen_spec_paths); do
    git checkout -q HEAD -- "$d" 2>/dev/null || true
    # Drop untracked junk under frozen specs (should be rare).
    git clean -fdq -- "$d" 2>/dev/null || true
  done
}

stage_for_task_commit() {
  restore_frozen_specs
  git add -A
  git reset -q -- .hermes migration/staging \
    migration/mta-findings-current.json 2>/dev/null || true
  # Belt: never stage frozen complete-story specs even if restore raced.
  for d in $(frozen_spec_paths); do
    git reset -q HEAD -- "$d" 2>/dev/null || true
    git checkout -q HEAD -- "$d" 2>/dev/null || true
  done
}

# O-HOTSWAPRELOAD (R-227 / T-011): pause for /tmp/harness-update, then EXIT
# so outer-loop re-execs a fresh supervisor. In-process resume keeps stale
# function bodies — O-T1FINDESC was on disk but never ran live (T-011 tip
# still swept findings; zero O-T1FINDESC log lines in supervisor.log).
# Leaves harness-update-ack + hotswap-inflight; does NOT write supervisor-done.
hotswap_pause_gate() {
  local tag="${1:-}"
  local saw_update=0
  while [ -f /tmp/supervisor-pause ] || [ -f /tmp/harness-update ]; do
    if [ -f /tmp/harness-update ]; then
      saw_update=1
      touch /tmp/supervisor-pause
      printf 'paused\n' > /tmp/harness-update-ack
      touch /tmp/hotswap-inflight
      if [ -n "$tag" ]; then
        log "$tag: O-HOTSWAP pause for harness update"
      else
        log "O-HOTSWAP: /tmp/harness-update seen — paused for harness deploy (rm harness-update + supervisor-pause to resume)"
        outer_log "         O-HOTSWAP: supervisor paused for harness update — will resume mid-story (not failed)"
      fi
    elif [ -n "$tag" ]; then
      log "$tag: PAUSED (rm /tmp/supervisor-pause to continue)"
    else
      log "PAUSED (rm /tmp/supervisor-pause to continue)"
    fi
    sleep 30
  done
  if [ "$saw_update" -eq 1 ]; then
    log "O-HOTSWAPRELOAD: harness-update cleared — exiting for outer re-enter (fresh script load)"
    exit 0
  fi
}

# O-T1FINDESC (R-223): MiniMax/Hermes may `git commit` directly and bypass
# stage_for_task_commit, sweeping mta-findings-current.json into a T-NNN tip
# (S03 T-007). If HEAD includes that path, rewrite the tip without it.
scrub_findings_from_tip() {
  local msg files
  files=$(git diff-tree --no-commit-id --name-only -r HEAD 2>/dev/null || true)
  echo "$files" | grep -qx 'migration/mta-findings-current.json' || return 0
  # Only rewrite T-NNN / SNN tips — never chore/debt/run-report.
  # Note: ids are T-007 (hyphen), not T007 — do not use ^(T|S)[0-9]+.
  git log -1 --format=%s | grep -qE '^(T-[0-9]+|S[0-9]+):' || return 0
  msg=$(git log -1 --format=%B)
  log "O-T1FINDESC: tip includes mta-findings-current.json — rewriting commit without it"
  git reset --soft HEAD~1 >>"$LOG" 2>&1 || return 0
  git reset -q HEAD -- migration/mta-findings-current.json 2>/dev/null || true
  git checkout -q HEAD -- migration/mta-findings-current.json 2>/dev/null || true
  # Belt: never leave findings staged even if checkout missed.
  git reset -q HEAD -- migration/mta-findings-current.json 2>/dev/null || true
  if git diff --cached --name-only | grep -qx 'migration/mta-findings-current.json'; then
    git rm --cached -q migration/mta-findings-current.json 2>/dev/null || true
  fi
  if git diff --cached --quiet 2>/dev/null; then
    log "O-T1FINDESC: WARN — tip was findings-only after unstage; leaving uncommitted"
    return 0
  fi
  # Prefer -F file for multi-line subjects/bodies from MiniMax commits.
  local msgf
  msgf=$(mktemp)
  printf '%s\n' "$msg" >"$msgf"
  git commit -q -F "$msgf" >>"$LOG" 2>&1 \
    || git commit -F "$msgf" >>"$LOG" 2>&1 || true
  rm -f "$msgf"
}

# O-SPECFROZEN: rewrite tip if it mutated a complete story's specs/.
scrub_frozen_specs_from_tip() {
  local msg files d hit=0
  files=$(git diff-tree --no-commit-id --name-only -r HEAD 2>/dev/null || true)
  [ -n "$files" ] || return 0
  git log -1 --format=%s | grep -qE '^(T-[0-9]+|S[0-9]+|M3 revision):' || return 0
  for d in $(frozen_spec_paths); do
    d=${d%/}
    if echo "$files" | grep -q "^${d}/"; then
      hit=1
      break
    fi
  done
  [ "$hit" -eq 1 ] || return 0
  msg=$(git log -1 --format=%B)
  log "O-SPECFROZEN: tip mutates complete-story specs — rewriting commit without frozen paths"
  git reset --soft HEAD~1 >>"$LOG" 2>&1 || return 0
  for d in $(frozen_spec_paths); do
    git reset -q HEAD -- "$d" 2>/dev/null || true
    git checkout -q HEAD -- "$d" 2>/dev/null || true
  done
  if git diff --cached --quiet 2>/dev/null; then
    log "O-SPECFROZEN: WARN — tip was frozen-specs-only after unstage; leaving uncommitted"
    return 0
  fi
  local msgf
  msgf=$(mktemp)
  printf '%s\n' "$msg" >"$msgf"
  git commit -q -F "$msgf" >>"$LOG" 2>&1 \
    || git commit -F "$msgf" >>"$LOG" 2>&1 || true
  rm -f "$msgf"
  restore_frozen_specs
}

# O-HERMNEST: app git must never version the workspace harness. MiniMax
# `git add -A` during escalation swept .hermes/ (and nested harness/harness
# from a bad oc cp) into T-001 (V9 S04). Keep files on disk; drop from git.
ensure_hermes_gitignored() {
  if [ -f .gitignore ] && grep -qE '^\.hermes/?$' .gitignore 2>/dev/null; then
    return 0
  fi
  {
    echo ""
    echo "# Harness runtime — workspace-only; never commit (O-HERMNEST)"
    echo ".hermes/"
  } >> .gitignore
}

scrub_hermes_from_git() {
  rm -rf .hermes/harness/harness 2>/dev/null || true
  ensure_hermes_gitignored
  if [ -z "$(git ls-files .hermes 2>/dev/null)" ]; then
    # Still commit .gitignore if we just appended it and it is new dirt
    if git status --porcelain -- .gitignore 2>/dev/null | grep -q .; then
      git add .gitignore
      git commit -q -m "chore: gitignore .hermes (O-HERMNEST)" 2>/dev/null || true
    fi
    return 0
  fi
  git rm -r --cached -q .hermes 2>/dev/null || true
  git add .gitignore 2>/dev/null || true
  if ! git diff --cached --quiet 2>/dev/null; then
    git commit -q -m "chore: untrack .hermes from app git (O-HERMNEST)" 2>/dev/null \
      || git commit -m "chore: untrack .hermes from app git (O-HERMNEST)" >/dev/null 2>&1 || true
    log "O-HERMNEST: removed tracked .hermes/ from git (harness remains on disk)"
  fi
}

# O-ESCW2 / O-PKGDIR: paths outside harness noise (.hermes/, migration/staging/).
app_dirt() {
  git status --porcelain --untracked-files=all 2>/dev/null | awk '{
    p=$2
    if ($1 ~ /^R/ || $1 ~ /^C/) {
      for (i=1;i<=NF;i++) if ($i=="->") { p=$(i+1); break }
    }
    if (p !~ /^\.hermes\// && p !~ /^migration\/staging\//) print p
  }'
}

# O-PKGDIR: empty package dirs are invisible to git — drop a .gitkeep so
# mkdir-only package-structure work can commit (migration-general).
ensure_trackable_packages() {
  local d
  for d in $(find src/main/java src/test/java -type d 2>/dev/null); do
    [ -d "$d" ] || continue
    if [ -z "$(ls -A "$d" 2>/dev/null)" ]; then
      touch "$d/.gitkeep"
      log "O-PKGDIR: added $d/.gitkeep (empty package dir was uncommittable)"
    fi
  done
}

# O-STY: discard OpenRewrite mutations under migration/staging (fidelity baseline).
discard_staging_autofix() {
  git checkout -q -- migration/staging 2>/dev/null || true
  git reset -q -- migration/staging 2>/dev/null || true
}

# --- Story mode (redesign M-process, first outer-loop slice) --------------
# STORY_SPEC_PREFIX  commit prefix that satisfies the plan stage (e.g.
#                    "S01 spec") — M2/M3 authored the plan; M3 is
#                    skipped when that commit exists.
# PLAN_SCOPE         comma-separated finding ids this story owns — passed
#                    to plan-lint --findings-scope.
# STORY_DEPLOY       "false" → M5 stops at factory quality-gate success
#                    (no acceptance curls; non-deploy story).
# STORY_SCOPE        space-separated src/main files this story may MODIFY
#                    (new files and tests are always free) — enforced by
#                    the story-scope sensor (scope_enforce).
# All unset → legacy whole-app behavior. The outer loop
# (.hermes/harness/outer-loop.sh) computes all of these per story from
# migration/roadmap.md.
STORY_SPEC_PREFIX="${STORY_SPEC_PREFIX:-}"
PLAN_SCOPE="${PLAN_SCOPE:-}"
STORY_DEPLOY="${STORY_DEPLOY:-true}"
plan_stage_done() {
  # Story mode: an explicit STORY_TASKS file is authoritative — the outer
  # loop only sets it after M3 committed the spec (a revert in the range
  # must not resurrect M3).
  if [ -n "${STORY_TASKS:-}" ] && [ -f "${STORY_TASKS}" ]; then return 0; fi
  { committed "M3 spec" || { [ -n "$STORY_SPEC_PREFIX" ] && committed "$STORY_SPEC_PREFIX"; }; } \
    && ls specs/*/tasks.md >/dev/null 2>&1
}

# NOTE: match the worker by exact process name (-x). Command-line matching
# false-positives on hermes sessions whose loaded skill text quotes the
# `opencode run` invocation.
# V6 P2.1: residual kill/cap is 15m (was 60m). A healthy worker finishes
# inside the session's foreground timeout; anything still running after
# WORKER_WAIT_CAP is a zombie — kill and verify-and-commit.
WORKER_WAIT_CAP="${WORKER_WAIT_CAP:-900}"
wait_for_worker() {
  local waited=0
  while pgrep -x opencode >/dev/null 2>&1; do
    [ $waited -eq 0 ] && log "worker process still running — waiting for it before next session"
    sleep 30; waited=$((waited+30))
    if [ $waited -ge "$WORKER_WAIT_CAP" ]; then
      log "worker still running after ${WORKER_WAIT_CAP}s — killing zombie worker before proceeding (V6 P2.1)"
      pkill -9 -x opencode; sleep 2
      break
    fi
  done
}

classify() { # $1=rc $2=session-log -> failure class on stdout
  local rc="$1" f="$2"
  if grep -qE "429|Too Many Requests" "$f" 2>/dev/null; then echo quota; return; fi
  if grep -qE "maximum context length|VLLMValidationError" "$f" 2>/dev/null; then echo ctx_overflow; return; fi
  if grep -qE "unresponsive|stale attempts|ReadTimeout|stream drop|Connection to provider failed" "$f" 2>/dev/null; then echo stream_stall; return; fi
  [ "$rc" = "124" ] && { echo timeout; return; }
  if pgrep -x opencode >/dev/null 2>&1; then
    echo orphan_worker; return
  fi
  echo no_commit
}

orch() { # $1=tag $2=prompt ; logs to /tmp/sup-<tag>.log ; returns rc
  local tag="$1" prompt="$2" t0 t1 rc
  # Pause point (V3): operators touch /tmp/supervisor-pause for a clean
  # intervention window between sessions — no kills, no target/ races.
  # O-HOTSWAP / O-HOTSWAPRELOAD: see hotswap_pause_gate().
  hotswap_pause_gate ""
  wait_for_worker
  t0=$(date +%s)
  # Fix-class sessions are mechanical: a wedged style fix dies in 15
  # minutes, not 45 (measured: 45-min sfix for 8 style violations).
  local budget="$SESSION_TIMEOUT"
  ORCH_LAST_BUDGET="$SESSION_TIMEOUT"
  case "$tag" in *sfix*|*treefix*|*-lint*|*preflightfix*) budget="${FIX_TIMEOUT:-900}";; esac
  ORCH_LAST_BUDGET="$budget"
  timeout "$budget" hermes chat --provider "$ORCH_PROVIDER" --model "$ORCH_MODEL" -q "$prompt" \
    > "/tmp/sup-${tag}.log" 2>&1
  rc=$?
  t1=$(date +%s)
  echo "${tag},${t0},${t1},$((t1-t0)),rc=${rc}" >> "$METRICS"
  [ $((t1-t0)) -gt 1800 ] && { event "$tag" 0 slow_session "$((t1-t0))s"; log "$tag: SLOW session ($((t1-t0))s) — wedge candidate"; }
  return $rc
}

# O-SFIXWORKER: freeform OpenCode seat for sensor-fix. Same FIX_TIMEOUT as
# MiniMax sfix. Caller re-runs the triggering sensor to decide rescue.
run_worker_prompt() { # $1=tag $2=prompt ; logs /tmp/oc-<tag>.{json,err}
  local tag="$1" prompt="$2" t0 t1 rc budget
  wait_for_worker
  t0=$(date +%s)
  budget="${FIX_TIMEOUT:-900}"
  : > "/tmp/oc-${tag}.json"
  : > "/tmp/oc-${tag}.err"
  log "$tag: Actor: $(worker_label) — OpenCode session → /tmp/oc-${tag}.json"
  timeout "$budget" opencode run "$prompt" \
    -m "$WORKER_MODEL" --auto --format json \
    -f AGENTS.md \
    > "/tmp/oc-${tag}.json" 2>"/tmp/oc-${tag}.err"
  rc=$?
  wait_for_worker
  t1=$(date +%s)
  echo "${tag},${t0},${t1},$((t1-t0)),rc=${rc}" >> "$METRICS"
  return $rc
}

# --- Story-scope sensor (V4, redesign §11) --------------------------------
# STORY_SCOPE (space-separated project-relative files, set by the outer
# loop from roadmap scope) bounds which EXISTING src/main files a story
# may modify. Creating new files and editing tests stays free; modifying
# an out-of-scope src/main file is autonomously reverted. The post-commit
# sensors then judge the reverted tree — if the revert broke the task,
# the ordinary sensor-fix session repairs it WITHIN scope (the sfix
# prompt points at /tmp/scope-violation.txt). No human escalation.
scope_enforce() { # $1=commit-prefix
  local prefix="$1" f
  # (A) later-story-class guard (V5 T-004): a task must NOT create an
  # src/main class a LATER story owns — that fabricates it (no harvest
  # source) and poisons the later story. Reverts the added file; the
  # sensor-fix packet (via /tmp/scope-violation.txt) says use a test
  # double instead. LATER_CLASSES = simple class names, set by the outer
  # loop from the roadmap's later-story scope.
  if [ -n "${LATER_CLASSES:-}" ]; then
    local lviol="" keep="" f bn
    # O-ESCWSCOPE: also catch *modifications* to later-story classes (not only adds).
    for f in $(git diff --name-only HEAD~1..HEAD -- src/main/java/ 2>/dev/null); do
      bn=$(basename "$f" .java)
      case " ${LATER_CLASSES} " in *" ${bn} "*)
        # O-LATERCDI: do not strip a later-story producer if THIS story's scoped
        # classes already inject an interface it implements (S04 CartEndpoint
        # → ShoppingCartService before S05 Impl). Reverting leaves Arc
        # UnsatisfiedResolutionException and sfix↔scope thrash.
        if [ -n "${STORY_SCOPE:-}" ] && [ -f "$f" ] && \
           python3 - "$f" ${STORY_SCOPE} <<'PY' 2>/dev/null
import re, sys
later = open(sys.argv[1], encoding="utf-8", errors="replace").read()
ifaces = re.findall(r"\bimplements\s+([A-Za-z0-9_.,\s]+)", later)
names = []
for chunk in ifaces:
    names.extend(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", chunk))
if not names:
    sys.exit(1)
scope_txt = []
for p in sys.argv[2:]:
    try:
        scope_txt.append(open(p, encoding="utf-8", errors="replace").read())
    except OSError:
        pass
blob = "\n".join(scope_txt)
for n in names:
    if re.search(rf"\b{n}\b", blob) and re.search(
        rf"(inject\.Inject|@Inject|constructor|[,(]\s*{n}\s+\w+)", blob
    ):
        sys.exit(0)
sys.exit(1)
PY
        then
          keep="$keep $f"
          log "scope sensor: O-LATERCDI keep ${bn} — STORY_SCOPE injects an interface it implements"
        else
          lviol="$lviol $f"
        fi
        ;;
      esac
    done
    if [ -n "$lviol" ]; then
      event "scope" 0 later_story_class "${lviol# }"
      log "scope sensor: reverted src/main class(es) a LATER story owns:${lviol}"
      # S-LC: demo-visible — later-story fabrication must not hide in supervisor.log only
      outer_log "         SCOPE REVERT (S-LC/O-ESCWSCOPE): removed/reverted later-story class(es):${lviol} — keep them in migration/staging until their story"
      {
        echo "The story-scope sensor reverted src/main class(es) owned by a LATER story:${lviol}"
        echo "These REDESIGN classes are converted in a later story — do NOT create or mutate them now (O-ESCWSCOPE)."
        echo "Prefer migration/staging until the owning story; characterization tests use Mockito / test-local fakes — never the real src/main class."
        echo "Stay on this task's Owns/Target paths only."
      } > /tmp/scope-violation.txt
      for f in $lviol; do
        if git diff --name-only --diff-filter=A HEAD~1..HEAD -- "$f" 2>/dev/null | grep -q .; then
          git rm -q "$f" 2>/dev/null || rm -f "$f"
        else
          git checkout HEAD~1 -- "$f" 2>/dev/null || true
        fi
      done
      git add -A && git commit -q -m "${prefix} scope revert: removed later-story class(es) created early (${lviol# })" 2>/dev/null
    fi
  fi
  # (B) this-story path-scope check --------------------------------------
  [ -n "${STORY_SCOPE:-}" ] || return 0
  # Only path-form scope entries are enforceable (V4 first-run catch: M2
  # wrote class FQNs — enforcing those would mass-revert every edit).
  # Enforcement covers src/main/java only: resources (application
  # .properties) are shared story surface, not class ownership.
  local pathscope="" e
  for e in ${STORY_SCOPE}; do case "$e" in src/*) pathscope="$pathscope $e";; esac; done
  if [ -z "$pathscope" ]; then
    log "scope sensor: no path-form scope entries — enforcement skipped (informational scope)"
    return 0
  fi
  # O-GATESCOPE: M5 ship correction commits (Gate/Build/Preflight fix) may
  # edit src/main paths the factory named in /tmp/gate-violations.txt even
  # when those paths are outside STORY_SCOPE. Reverting them after a Gate
  # fix caused Sonar↔scope deadlock (Wave2 petclinic: DTO S6207 fixed then
  # reverted → BV tests RED → O-DEBTFRZ). Story tasks still cannot widen
  # scope this way — only ship-correction prefixes.
  local gate_allow=""
  case "$prefix" in
    "Gate fix"*|"Build fix"*|"Preflight fix"*)
      if [ -f /tmp/gate-violations.txt ]; then
        # shellcheck disable=SC2013
        gate_allow=$(grep -oE 'src/main/[^[:space:],:]+' /tmp/gate-violations.txt 2>/dev/null \
          | sed 's/[:].*$//' | sort -u | tr '\n' ' ')
      fi
      ;;
  esac
  local viol="" kept=""
  for f in $(git diff --name-only --diff-filter=M HEAD~1..HEAD -- src/main/java/ 2>/dev/null); do
    case " ${pathscope} " in *" $f "*) continue;; esac
    case " ${gate_allow} " in
      *" $f "*)
        kept="$kept $f"
        log "scope sensor: O-GATESCOPE keep $f — named in /tmp/gate-violations.txt"
        ;;
      *) viol="$viol $f";;
    esac
  done
  [ -n "$kept" ] && event "scope" 1 gatescope_keep "${kept# }"
  [ -n "$viol" ] || { rm -f /tmp/scope-violation.txt; return 0; }
  event "scope" 0 scope_violation "${viol# }"
  log "scope sensor: out-of-scope src/main edits reverted:${viol}"
  {
    echo "The story-scope sensor reverted out-of-scope src/main modifications:${viol}"
    echo "This story's src/main scope: ${STORY_SCOPE}"
    echo "Rule: finish the task WITHIN scope; if it genuinely requires an out-of-scope edit, record that need in migration/debt.md instead of making the edit."
    if [ -n "$gate_allow" ]; then
      echo "O-GATESCOPE: ship correction may keep src/main paths listed in /tmp/gate-violations.txt (kept:${kept:- none})."
    fi
  } > /tmp/scope-violation.txt
  git checkout HEAD~1 -- $viol 2>/dev/null
  git add -A && git commit -q -m "${prefix} scope revert: story-scope sensor reverted out-of-scope src/main edits (${viol# })" 2>/dev/null
}

# --- Debt ledger (V5 finding #4) --------------------------------------------
# A sensor that stays RED after its fix session is no longer swallowed as a
# bare log line (run-4: a milestone RED "recorded as debt" wrote NO artifact,
# so it reached M5/ship invisibly). Write a durable, reviewable entry to
# migration/debt.md and commit it. This is the record; the M5 ship gate
# INDEPENDENTLY blocks on the factory-uncatchable dimensions (fidelity,
# package) so unresolved debt of those kinds can never ship.
record_debt() { # $1=tag $2=sensor-kind $3=short-reason
  local tag="$1" kind="$2" reason="$3"
  [ -f migration/debt.md ] || printf '# Migration debt ledger\n\nUnresolved sensor REDs recorded by the supervisor: each is a defect that\nsurvived its fix session. The M5 ship gate blocks on fidelity/package debt.\n' > migration/debt.md
  {
    printf '\n## %s — %s RED\n' "$tag" "$kind"
    printf -- '- head: %s\n' "$(git rev-parse --short HEAD 2>/dev/null)"
    printf -- '- reason: %s\n' "$reason"
  } >> migration/debt.md
  git add migration/debt.md 2>/dev/null
  git commit -q -m "debt: ${tag} ${kind} RED (unresolved)" 2>/dev/null || true
  event "$tag" 0 debt_recorded "$kind"
  # O-DEBTFRZ: unresolved task/milestone debt must FREEZE — not continue to the
  # next task (V9 S04 T-002→T-003 silent advance). Ship-gate fidelity/package
  # debt at M5 still records; freeze applies to in-story task/milestone kinds.
  case "$kind" in
    task|milestone|sonar)
      touch /tmp/debt-freeze
      touch /tmp/supervisor-pause
      log "$tag: ${kind} RED recorded in migration/debt.md — O-DEBTFRZ FREEZE (do not continue to next task)"
      if [ -x .hermes/harness/freeze-harness.sh ]; then
        .hermes/harness/freeze-harness.sh >> "$LOG" 2>&1 || true
      fi
      ;;
    *)
      log "$tag: ${kind} RED recorded in migration/debt.md — continuing (ship gate blocks fidelity/package debt)"
      ;;
  esac
}

debt_frozen() { [ -f /tmp/debt-freeze ]; }

# Clear the ledger on a GREEN ship ONLY when no unresolved ## entries remain.
# V6 P2.5 / V5 S4: wiping debt on a "green" ship that still listed milestone
# REDs erased the audit trail (false cleanliness). Unresolved ## debt must
# survive ship for human review; only an empty/header-only ledger is a no-op.
clear_debt() {
  [ -f migration/debt.md ] || return 0
  if grep -q "^## " migration/debt.md 2>/dev/null; then
    event "m5-ship" 0 debt_retained unresolved
    log "debt ledger NOT cleared — unresolved ## entries remain (V6 P2.5); review migration/debt.md"
    return 0
  fi
  log "debt ledger has no unresolved ## entries — nothing to clear"
}

# --- Post-commit verification (extracted so the batch path shares it) -----
# Trust-but-verify (run-4 lesson: a session committed a red tree): the
# supervisor runs the sensors itself after EVERY commit. The milestone
# sensor (verify + the factory's sonar gate) is ENFORCED — not advisory —
# on every pom/config-touching commit and every 3rd task, so style
# violations die in-loop, not at the factory.
post_commit_verify() { # $1=commit-prefix $2=tag ; always returns 0
  local prefix="$1" tag="$2"
  # O-HERMNEST: strip any .hermes/ that MiniMax/worker just committed
  scrub_hermes_from_git
  TASKS_SINCE_MILESTONE=$((TASKS_SINCE_MILESTONE+1))
  local SENSOR_KIND=task
  if git show --stat HEAD | grep -qE "pom.xml|application.properties" || [ $TASKS_SINCE_MILESTONE -ge 3 ]; then
    SENSOR_KIND=milestone; TASKS_SINCE_MILESTONE=0
  fi
  log "$tag: post-commit verification (${SENSOR_KIND} sensor)"
  local _sense_t0 _sense_elapsed
  _sense_t0=$(date +%s)
  if ! .hermes/harness/sensors.sh "$SENSOR_KIND" >> "$LOG" 2>&1; then
    event "$tag" 0 sensor_red_post_commit verify
    # O-SONARBLEED: in-loop Sonar RED only on prior-task files — do not burn
    # MiniMax sfix editing ShippingServiceTest etc. for an unrelated T-NNN.
    case "$prefix" in
      T-*)
        if [ -n "${TASKS_FILE:-}" ] && [ -f .hermes/harness/sonar-task-scope.py ] \
          && [ -s /tmp/sonar-violations.txt ] \
          && grep -qE 'SENSOR RED:sonar|in-loop gate:|new violations' \
               /tmp/sensor-milestone.log /tmp/sensor-sonar.log /tmp/sensor-task.log 2>/dev/null; then
          if ! python3 .hermes/harness/sonar-task-scope.py "$TASKS_FILE" "$prefix" \
               /tmp/sonar-violations.txt > /tmp/sonar-scope.out 2>&1; then
            log "$tag: O-SONARBLEED — $(tr '\n' ' ' </tmp/sonar-scope.out) — skip sfix (out-of-task Sonar only)"
            event "$tag" 0 sonar_bleed_skip "$(tr '\n' ' ' </tmp/sonar-scope.out)"
            return 0
          fi
        fi
        ;;
    esac
    # Deterministic style-autofix first (V3 measured: 152 min of model
    # time went to mechanically-fixable style violations).
    .hermes/harness/style-autofix.sh >> "$LOG" 2>&1 || true
    if [ -n "$(git status --porcelain)" ]; then
      # The autofix's changes are deterministic OpenRewrite fixes — KEEP them
      # even when the full sensor is still RED. V5 run-4: the old path did
      # `git checkout -- .` here, discarding the autofix (e.g. the ArrayList
      # diamond) whenever OTHER violations it can't fix kept the sensor red —
      # so those fixes oscillated back every cycle (sonar 5->3->4, never
      # converging). Commit them; if they cleared the RED we are done, else
      # the sfix starts from the cleaner tree.
      # O-STY: never commit OpenRewrite edits under migration/staging/
      discard_staging_autofix
      if .hermes/harness/sensors.sh "$SENSOR_KIND" >> "$LOG" 2>&1; then
        stage_for_task_commit
        # O-SFIXCREDIT: autofix uses distinct prefix so sfix credit cannot
        # match an earlier autofix SHA (S04 T-003 false GREEN).
        git diff --cached --quiet || \
          git commit -q -m "${prefix} sensor autofix: deterministic style-autofix (OpenRewrite cleanup recipes)" 2>/dev/null
        event "$tag" 0 style_autofix resolved
        log "$tag: style-autofix resolved the red deterministically — no model session needed"
        return 0
      fi
      # KEEP the partial autofix only if the tree still COMPILES. An
      # OpenRewrite recipe can misfire (V5 run-4: RemoveUnusedImports stripped
      # a still-used HashSet import from an out-of-scope service) — committing
      # that broke the build. Never commit a non-compiling autofix: if it
      # broke compilation, revert it and let the sfix work from the original.
      if grep -qE "COMPILATION ERROR|cannot find symbol" /tmp/sensor-milestone.log /tmp/sensor-task.log 2>/dev/null; then
        git checkout -q -- . 2>/dev/null
        event "$tag" 0 style_autofix reverted_broke_build
        log "$tag: style-autofix broke compilation — reverted (never commit a non-compiling tree); sfix works from the original"
      else
        stage_for_task_commit
        if ! git diff --cached --quiet; then
          git commit -q -m "${prefix} sensor autofix: partial deterministic style-autofix (remaining violations to sfix)" 2>/dev/null
          event "$tag" 0 style_autofix partial
          log "$tag: style-autofix fixed some violations (committed, compiles); remaining go to a sfix session"
        fi
      fi
    fi
    log "$tag: committed but the ${SENSOR_KIND} sensor is RED — dispatching sensor-fix session"
    # K7: capture post-RED signature and diff vs pre-task baseline — NEW failures
    # are this commit's debt (cannot be waived as pre-existing / out of scope).
    local FSIG_BEFORE="/tmp/failure-sig-before-${prefix}.txt"
    local FSIG_AFTER="/tmp/failure-sig-after-${tag}.txt"
    local FDELTA="/tmp/failure-delta-${tag}.txt"
    if [ -f .hermes/harness/failure-sig.py ]; then
      python3 .hermes/harness/failure-sig.py capture "$FSIG_AFTER" \
        /tmp/sensor-task.log /tmp/sensor-milestone.log /tmp/sensor-sonar.log \
        /tmp/sonar-violations.txt >> "$LOG" 2>&1 || true
      python3 .hermes/harness/failure-sig.py diff \
        "${FSIG_BEFORE:-/dev/null}" "$FSIG_AFTER" > "$FDELTA" 2>/dev/null || true
      cp "$FDELTA" /tmp/failure-delta.txt 2>/dev/null || true
      log "$tag: K7 failure-delta — $(grep -m1 '^SUMMARY' "$FDELTA" 2>/dev/null || echo n/a)"
    else
      : > "$FDELTA"
    fi
    local K7_DELTA_NOTE=""
    if [ -s "$FDELTA" ] && grep -q '^NEW:' "$FDELTA" 2>/dev/null; then
      K7_DELTA_NOTE="
K7 FAILURE DELTA (authoritative — /tmp/failure-delta.txt): these failures are NEW since task start — you MUST fix them; claiming pre-existing/out-of-scope is REFUTED by data:
$(grep '^NEW:' "$FDELTA" | head -40)
"
    fi
    # Cheap-loop guidance (V4 finding #1: ~5100s of full `mvn clean verify`
    # inside fix sessions). Point the model at the dimension-specific cheap
    # recheck so it stops re-running the whole build per fix.
    # O-SFIXLOOP: hard-refuse milestone inside the session via /tmp/sensor-fix-mode
    # (prompt-only was ignored — V9 S03 T-008 ran milestone 5×).
    touch /tmp/sensor-fix-mode
    # O-SFIXCREDIT: require HEAD to move after sfix — prior autofix must not
    # satisfy committed("… sensor fix").
    PRE_SFIX_HEAD=$(git rev-parse HEAD)
    local SFIX_PROMPT
    SFIX_PROMPT="Use the migration-harness skill and read EXECUTION.md in its directory. The stage '${prefix}' was just committed but the supervisor's post-commit '${SENSOR_KIND}' sensor is RED — read /tmp/sensor-task.log, /tmp/sensor-milestone.log and /tmp/sensor-sonar.log for the exact errors (sonar violations are listed inline when the gate is red). If those logs show FINDINGS: or FINDINGS RED lines, the RED dimension is findings — fix those file:line incidents (typical: replace quarkus-micrometer* with quarkus-smallrye-metrics) and verify with .hermes/harness/sensors.sh findings; do NOT commit unrelated comment/test polish while FINDINGS is RED (O-SFIXWRONGDIM). If /tmp/scope-violation.txt exists, the story-scope sensor reverted out-of-scope edits — read it and repair WITHIN the story scope only. Diagnose and fix the ROOT CAUSE (typical: files harvested prematurely without their extension/dependency). PACKAGE DIRECTION IS ONE-WAY: this migration RENAMES the legacy package to the target package (migration.yaml legacyPackage -> targetPackage). The target package is ALWAYS correct; a file under the legacy package in src/main is the defect. If a class is in the wrong place, move it INTO the target package and rewrite its 'package'/imports to the target — NEVER move or revert a class into the legacy package, and NEVER rewrite target-package files back to the legacy package to 'match' staged source (migration/staging holds legacy-package source by design; fidelity already accounts for the rename). A 'harvest fidelity RED' is about drifted CONTENT, not the package. O-FIDELITYVALID / O-SFIXNOSPRING: Spring BindingResult/FieldError → Jakarta ConstraintViolation is an approved validation conversion — do NOT re-harvest Spring validation types or add org.springframework.* imports / spring-* pom deps to green-wash fidelity. Re-run .hermes/harness/sensors.sh fidelity after harness updates; if already GREEN, commit nothing for fidelity. add a dependency ONLY if this stage's findings require it. CHEAP FIX LOOP (O-SFIXLOOP — ENFORCED): fix ALL listed violations in ONE pass, then verify ONCE with the dimension-specific check — sonar violations: .hermes/harness/sensors.sh sonar; FINDINGS:/FINDINGS RED: .hermes/harness/sensors.sh findings; fidelity drift: .hermes/harness/sensors.sh fidelity; a legacy package under src/main: .hermes/harness/sensors.sh package; compile/test failure: .hermes/harness/sensors.sh task. DO NOT run .hermes/harness/sensors.sh milestone — it is REFUSED during this session (exits 2). Commit ONE commit starting '${prefix} sensor fix:' the moment your dimension check is green; do not polish further. O-SONARTIME: NEVER wrap .hermes/harness/sensors.sh in timeout <600s (sonar needs 2–3m; timeout 60 → exit 124). O-SFIXSCOPE: NEVER commit while the dimension check is still RED claiming failures are 'pre-existing' or 'out of scope' — fix them or stop without commit (V9 S04 T-003). For RestAssured RED: fix JSON paths under the collection property, empty-path 400 myths, and test isolation (EXECUTION O-RESTJSON/O-RESTEMPTY/O-TESTISO). S5976: prefer @ParameterizedTest + @CsvSource — never delete characterization cases (O-SFIXCOUNT/O-SFIXDIRTY).
${K7_DELTA_NOTE}${RUN_CONTRACT}"
    # O-SFIXWORKER: Qwen first (cheap verifier); MiniMax rescue capped by
    # SFIX_MINIMAX_RESCUE_MAX (default 1 — R-218 enforced integer, not a comment).
    if [ "${WORKER_SFIX_FIRST:-true}" = "true" ]; then
      log "$tag: O-SFIXWORKER — sensor-fix via $(worker_label) first (MiniMax rescue≤${SFIX_MINIMAX_RESCUE_MAX:-1} if ${SENSOR_KIND} still RED)"
      outer_log "         O-SFIXWORKER: sensor-fix → $(worker_label); MiniMax rescue≤${SFIX_MINIMAX_RESCUE_MAX:-1}"
      event "$tag" 0 sfix_worker_first "$SENSOR_KIND"
      run_worker_prompt "${tag}-sfix-w" "$SFIX_PROMPT" || true
      if .hermes/harness/sensors.sh "$SENSOR_KIND" >> "$LOG" 2>&1; then
        log "$tag: O-SFIXWORKER — ${SENSOR_KIND} GREEN after Qwen (skip MiniMax)"
        event "$tag" 0 sfix_worker_green "$SENSOR_KIND"
      else
        local _sfix_rescue=0
        while [ "$_sfix_rescue" -lt "${SFIX_MINIMAX_RESCUE_MAX:-1}" ]; do
          _sfix_rescue=$((_sfix_rescue + 1))
          log "$tag: O-SFIXWORKER — ${SENSOR_KIND} still RED after Qwen — MiniMax rescue ${_sfix_rescue}/${SFIX_MINIMAX_RESCUE_MAX}"
          outer_log "         O-SFIXWORKER: MiniMax rescue ${_sfix_rescue}/${SFIX_MINIMAX_RESCUE_MAX}"
          event "$tag" 0 sfix_minimax_rescue "${SENSOR_KIND}:${_sfix_rescue}"
          orch "${tag}-sfix-r${_sfix_rescue}" "$SFIX_PROMPT" || true
          if .hermes/harness/sensors.sh "$SENSOR_KIND" >> "$LOG" 2>&1; then
            log "$tag: O-SFIXWORKER — ${SENSOR_KIND} GREEN after MiniMax rescue ${_sfix_rescue}"
            break
          fi
        done
      fi
    else
      orch "${tag}-sfix" "$SFIX_PROMPT" || true
    fi
    rm -f /tmp/sensor-fix-mode
    # #6: re-verify the TRIGGERING sensor (${SENSOR_KIND}), not `task` — a
    # milestone-red (fidelity/sonar) is not cleared by a task-sensor green,
    # and a commit with the right prefix is not proof the red went away.
    if [ "$(git rev-parse HEAD)" != "$PRE_SFIX_HEAD" ] && committed "${prefix} sensor fix"; then
      # O-SFIXNOSPRING (F-21): sfix must not reintroduce Spring to green-wash
      # harvest fidelity (type-level inversion — BindingResult restore).
      if [ -f .hermes/harness/sfix-no-spring.py ] \
        && ! python3 .hermes/harness/sfix-no-spring.py "$PRE_SFIX_HEAD" HEAD >> "$LOG" 2>&1; then
        event "$tag" 0 sfix_spring_reintro verify
        log "$tag: O-SFIXNOSPRING — sensor-fix reintroduced Spring imports/deps — resetting"
        if git log -1 --format=%s | grep -qE 'sensor fix:'; then
          _red=$(git rev-parse HEAD)
          _arch="/tmp/strays/${tag}-sfix-spring-$(date -u +%Y%m%dT%H%M%SZ)"
          mkdir -p "$_arch"
          git show --stat "$_red" >"$_arch/stat.txt" 2>&1 || true
          git show "$_red" >"$_arch/full.diff" 2>&1 || true
          printf '%s\n' "$_red" >"$_arch/sha.txt"
          git reset --hard "$PRE_SFIX_HEAD" >> "$LOG" 2>&1 || true
        fi
        record_debt "$tag" "$SENSOR_KIND" "O-SFIXNOSPRING: sfix reintroduced Spring (commit reset)"
      # K7: commit message claiming pre-existing/out-of-scope while NEW delta
      # exists → machine-refute (same as still-RED path).
      elif [ -s "$FDELTA" ] && grep -q '^NEW:' "$FDELTA" 2>/dev/null \
        && git log -1 --format=%B | grep -qiE 'pre-existing|out of scope|out-of-scope|not introduced'; then
        event "$tag" 0 k7_refute_preexisting "$(grep -c '^NEW:' "$FDELTA" || true)"
        log "$tag: K7 refute — sfix claimed pre-existing/out-of-scope but failure-delta has NEW keys"
        if git log -1 --format=%s | grep -qE 'sensor fix:'; then
          _red=$(git rev-parse HEAD)
          _arch="/tmp/strays/${tag}-sfix-k7-$(date -u +%Y%m%dT%H%M%SZ)"
          mkdir -p "$_arch"
          cp "$FDELTA" "$_arch/failure-delta.txt" 2>/dev/null || true
          git show --stat "$_red" >"$_arch/stat.txt" 2>&1 || true
          printf '%s\n' "$_red" >"$_arch/sha.txt"
          git reset --hard HEAD~1 >> "$LOG" 2>&1 || true
          record_debt "$tag" "$SENSOR_KIND" "K7 refute: sfix claimed pre-existing despite NEW failure-delta"
        fi
      elif .hermes/harness/sensors.sh "$SENSOR_KIND" >> "$LOG" 2>&1; then
        log "$tag: sensor-fix committed and ${SENSOR_KIND} GREEN $(git log --oneline -1)"
      else
        # O-SFIXSCOPE: never keep a sensor-fix commit that left the sensor RED
        # (V9 S04 T-003: session claimed "pre-existing / out of scope" and committed).
        event "$tag" 0 sfix_committed_still_red verify
        if git log -1 --format=%s | grep -qE 'sensor fix:'; then
          # O-REDARCH: keep the red tip for RCA before hard-reset
          _red=$(git rev-parse HEAD)
          _arch="/tmp/strays/${tag}-sfix-red-$(date -u +%Y%m%dT%H%M%SZ)"
          mkdir -p "$_arch"
          git show --stat "$_red" >"$_arch/stat.txt" 2>&1 || true
          git show "$_red" >"$_arch/full.diff" 2>&1 || true
          git format-patch -1 "$_red" -o "$_arch" >>"$LOG" 2>&1 || true
          printf '%s\n' "$_red" >"$_arch/sha.txt"
          cp "$FDELTA" "$_arch/failure-delta.txt" 2>/dev/null || true
          log "$tag: O-SFIXSCOPE — archiving RED sensor-fix $_red → $_arch then resetting"
          git reset --hard HEAD~1 >> "$LOG" 2>&1 || true
          # O-SFIXPARTIAL: salvage in-scope hunks from the archive (do not
          # discard a whole Sonar/compile win because one residual remains).
          if [ -f .hermes/harness/sfix-partial-salvage.py ] \
            && [ -n "${TASKS_FILE:-}" ] && [ -f "$TASKS_FILE" ]; then
            if python3 .hermes/harness/sfix-partial-salvage.py \
                 "$_arch" "$TASKS_FILE" "$prefix" >>"$LOG" 2>&1; then
              if .hermes/harness/sensors.sh "$SENSOR_KIND" >> "$LOG" 2>&1; then
                stage_for_task_commit
                if ! git diff --cached --quiet; then
                  SKIP_SENSOR_GATE=1 git commit -m \
                    "${prefix} sensor fix: O-SFIXPARTIAL salvage of in-scope GREEN hunks" \
                    >/dev/null 2>&1 || true
                  if committed "${prefix} sensor fix"; then
                    log "$tag: O-SFIXPARTIAL — salvaged in-scope hunks; ${SENSOR_KIND} GREEN"
                    event "$tag" 0 sfix_partial_salvage ok
                  fi
                fi
              else
                log "$tag: O-SFIXPARTIAL — salvage still RED — discarding restored dirt"
                git checkout -q -- . 2>/dev/null || true
                git clean -fdq -- src/ 2>/dev/null || true
              fi
            fi
          fi
        fi
        record_debt "$tag" "$SENSOR_KIND" "sensor-fix committed but ${SENSOR_KIND} still RED (commit reset)"
      fi
    elif [ "$(git rev-parse HEAD)" = "$PRE_SFIX_HEAD" ] && committed "${prefix} sensor fix"; then
      log "$tag: O-SFIXCREDIT — sfix did not move HEAD (stale sensor-fix match ignored)"
      event "$tag" 0 sfix_no_new_commit credit
      # O-SFIXDIRTY: drop uncommitted thinning before next task
      if [ -n "$(git status --porcelain -- src/ 2>/dev/null)" ]; then
        log "$tag: O-SFIXDIRTY — discarding uncommitted sfix dirt under src/"
        git checkout -q -- src/ 2>/dev/null || true
        git clean -fdq -- src/ 2>/dev/null || true
      fi
      record_debt "$tag" "$SENSOR_KIND" "sensor-fix did not clear ${SENSOR_KIND} (no new commit)"
    elif [ -n "$(git status --porcelain)" ] && .hermes/harness/sensors.sh "$SENSOR_KIND" >> "$LOG" 2>&1; then
      # Mechanical closure — verifies the TRIGGERING sensor (#6), not task.
      # O-T6c: exclude .hermes/ (and staging) from escalation/sfix mechan commits.
      stage_for_task_commit
      if ! git diff --cached --quiet; then
        git commit -m "${prefix} sensor fix: supervisor mechanical commit of ${SENSOR_KIND}-green session work" >/dev/null 2>&1
        event "$tag" 0 mechanical_commit sfix_closure
        log "$tag: sensor-fix work was ${SENSOR_KIND}-GREEN but uncommitted — supervisor completed the commit"
      fi
    else
      # O-SFIXDIRTY: failed sfix must not leave thinned tests dirty for later commit
      if [ -n "$(git status --porcelain -- src/ 2>/dev/null)" ]; then
        log "$tag: O-SFIXDIRTY — discarding uncommitted sfix dirt under src/"
        git checkout -q -- src/ 2>/dev/null || true
        git clean -fdq -- src/ 2>/dev/null || true
      fi
      record_debt "$tag" "$SENSOR_KIND" "sensor-fix did not clear ${SENSOR_KIND}"
    fi
  else
    # O-UXLOG-SENSE (Poll 77 U3): GREEN sensors visible on the demo log.
    _sense_elapsed=$(( $(date +%s) - _sense_t0 ))
    case "$SENSOR_KIND" in
      milestone) outer_log "         ✓ SENSE milestone sensor GREEN after ${tag} (verify+sonar, ${_sense_elapsed}s)" ;;
      *)         outer_log "         ✓ SENSE task sensor GREEN after ${tag} (compile+test, ${_sense_elapsed}s)" ;;
    esac
  fi
  debt_frozen && return 1
  return 0
}

# O-SFIXSCOPE: a T-NNN / stage commit that leaves task sensor RED must not stand.
# Reset HEAD and return 1 so the caller does not treat it as success.
# O-REDARCH: archive the red tip to /tmp/strays/<tag>/ before hard-reset so
# escalation RCA still has the worker/MiniMax output.
# K12 — adversarial refute at MiniMax escalation commits + pre-push ship.
# Deterministic core (refute-diff.py); optional LLM when REFUTE_LLM=1.
refute_high_stakes() { # $1=sha $2=tag -> 0 pass, 1 refused
  local sha="${1:-HEAD}" tag="${2:-k12}"
  [ -f .hermes/harness/refute-diff.py ] || return 0
  local out="/tmp/refute-${tag}.txt"
  if ! python3 .hermes/harness/refute-diff.py "$sha" >"$out" 2>&1; then
    log "$tag: K12 REFUTED — $(tr '\n' ' ' <"$out")"
    event "$tag" 0 k12_refuted "$(head -3 "$out" | tr '\n' ';')"
    mkdir -p migration
    {
      echo "## K12 refute — $tag — $(date -u +%Y-%m-%dT%H:%M:%SZ)"
      echo ""
      echo "sha: $(git rev-parse --short "$sha" 2>/dev/null || echo "$sha")"
      echo ""
      cat "$out"
      echo ""
    } >> migration/refute-log.md
    git add migration/refute-log.md >/dev/null 2>&1 || true
    return 1
  fi
  log "$tag: K12 refute PASS ($(git rev-parse --short "$sha" 2>/dev/null || echo "$sha"))"
  if [ "${REFUTE_LLM:-0}" = "1" ]; then
    orch "refute-${tag}" \
"K12 adversarial refute. Bias to REJECT on uncertainty. Read git show ${sha} and migration/refute-log.md. Find fail-open catch, canned literal, never-called dependency, weakened assertion, ceremonial status map, ExceptionMapper<Exception>, mock fabrication. Write ONE line to migration/refute-verdict.txt: PASS or REFUTED:<reason>. Do not edit src/. Commit message must start with 'K12 refute:' only if you append evidence to migration/refute-log.md." \
      || true
    if [ -f migration/refute-verdict.txt ] && grep -qi '^REFUTED' migration/refute-verdict.txt; then
      log "$tag: K12 LLM REFUTED — $(tr '\n' ' ' < migration/refute-verdict.txt)"
      event "$tag" 0 k12_llm_refuted "$(head -1 migration/refute-verdict.txt)"
      return 1
    fi
  fi
  return 0
}

# O-WEDGESKIP: clear story-wide worker skip after any successful task commit
# so later tasks (e.g. CDI redesign) get Qwen again — not sticky MiniMax.
clear_worker_wedge_skip() {
  local story_key
  story_key=$(echo "${STORY_SPEC_PREFIX:-run}" | awk '{print $1}')
  [ -f /tmp/worker-wedge-skip ] || return 0
  grep -qxF "$story_key" /tmp/worker-wedge-skip 2>/dev/null || return 0
  grep -vxF "$story_key" /tmp/worker-wedge-skip > /tmp/worker-wedge-skip.tmp 2>/dev/null \
    && mv /tmp/worker-wedge-skip.tmp /tmp/worker-wedge-skip \
    || rm -f /tmp/worker-wedge-skip
  log "O-WEDGESKIP: cleared worker-wedge-skip for ${story_key} after successful commit"
}

refuse_red_task_commit() { # $1=prefix $2=tag -> 0 keep, 1 reset
  local prefix="$1" tag="$2" red_sha arch
  case "$prefix" in
    T-*|S*) ;;
    *) return 0 ;;
  esac
  git log -1 --format=%s | grep -qE "^${prefix}" || return 0
  if .hermes/harness/sensors.sh task > /tmp/sensor-task.log 2>&1; then
    return 0
  fi
  red_sha=$(git rev-parse HEAD)
  arch="/tmp/strays/${tag}-red-$(date -u +%Y%m%dT%H%M%SZ)"
  mkdir -p "$arch"
  git show --stat "$red_sha" >"$arch/stat.txt" 2>&1 || true
  git show "$red_sha" >"$arch/full.diff" 2>&1 || true
  git format-patch -1 "$red_sha" -o "$arch" >>"$LOG" 2>&1 || true
  printf '%s\n' "$red_sha" >"$arch/sha.txt"
  log "$tag: O-SFIXSCOPE — HEAD ${prefix} commit is task-RED — archiving $red_sha → $arch then resetting (never keep red commits)"
  event "$tag" 0 sfixscope_reset task_red
  git reset --hard HEAD~1 >> "$LOG" 2>&1 || true
  return 1
}

# run_stage <commit-prefix> <tag> <prompt> <retry-prompt> -> 0 committed / 1 exhausted
run_stage() {
  local prefix="$1" tag="$2" prompt="$3" rprompt="$4"
  local attempt=1 pf=0
  while [ $attempt -le $MAX_ATTEMPTS ]; do
    # O-ESCALGPLACE: a prior hung MiniMax session may have committed (possibly
    # with G-PLACE assertThat(true)) before sensors ran. Never treat an
    # existing prefix commit as success without refuse_red_task_commit.
    # early-commit-gate.py is the pure sensor-rc contract (instruments).
    if committed "$prefix"; then
      if refuse_red_task_commit "$prefix" "$tag"; then
        return 0
      fi
      attempt=$((attempt+1))
      continue
    fi
    local p="$prompt"; [ $attempt -gt 1 ] && p="$rprompt"
    orch "${tag}-a${attempt}p${pf}" "$p"; local rc=$?
    # O-NULLACTION (N17): honest stop without fabrication is success, not a burn.
    if [ -f "/tmp/escalation-noaction-${tag}.txt" ] || [ -f "/tmp/escalation-noaction-${prefix}.txt" ]; then
      local naf="/tmp/escalation-noaction-${tag}.txt"
      [ -f "$naf" ] || naf="/tmp/escalation-noaction-${prefix}.txt"
      log "$tag: O-NULLACTION — guard-refused no-action ($(tr '\n' ' ' <"$naf"))"
      event "$tag" "$attempt" null_action "$(head -1 "$naf" | tr '\n' ' ')"
      record_debt "$tag" null_action "O-NULLACTION: $(head -1 "$naf")"
      return 0
    fi
    if committed "$prefix"; then
      # O-T1FINDESC: strip kantra inventory if escalation/worker committed it.
      scrub_findings_from_tip
      # O-SPECFROZEN: strip complete-story spec mutations (R-229 S01 gutting).
      scrub_frozen_specs_from_tip
      event "$tag" "$attempt" success commit; log "$tag: committed $(git log --oneline -1)"
      # O-SFIXSCOPE: refuse red T-NNN commits (do not proceed to post_commit_verify as success)
      if ! refuse_red_task_commit "$prefix" "$tag"; then
        attempt=$((attempt+1))
        continue
      fi
      # O-MSGCLAIM: subject inventing class work not in the diff — reset tip
      # (S04 T-002 CatalogService claim with unchanged file).
      if [ -f .hermes/harness/msgclaim-check.py ] \
        && ! python3 .hermes/harness/msgclaim-check.py HEAD > /tmp/msgclaim.out 2>&1; then
        log "$tag: O-MSGCLAIM — $(cat /tmp/msgclaim.out 2>/dev/null | tr '\n' ' ') — resetting dishonest tip"
        event "$tag" "$attempt" msgclaim_reset "$(cat /tmp/msgclaim.out 2>/dev/null | tr '\n' ' ')"
        _red=$(git rev-parse HEAD)
        _arch="/tmp/strays/${tag}-msgclaim-$(date -u +%Y%m%dT%H%M%SZ)"
        mkdir -p "$_arch"
        git show --stat "$_red" >"$_arch/stat.txt" 2>&1 || true
        git show "$_red" >"$_arch/full.diff" 2>&1 || true
        printf '%s\n' "$_red" >"$_arch/sha.txt"
        git reset --hard HEAD~1 >> "$LOG" 2>&1 || true
        attempt=$((attempt+1))
        continue
      fi
      # O-GITBAK / O-SIMPLEDTO / O-POMUNC: refuse *.bak debris, thin-DTO+bak,
      # and MapStruct Java without mapstruct in pom (Wave2 T-005 62413ff).
      if [ -f .hermes/harness/commit-hygiene.py ] \
        && ! python3 .hermes/harness/commit-hygiene.py HEAD > /tmp/commit-hygiene.out 2>&1; then
        log "$tag: O-COMMITHYGIENE — $(cat /tmp/commit-hygiene.out 2>/dev/null | tr '\n' ' ') — resetting dishonest tip"
        event "$tag" "$attempt" commit_hygiene_reset "$(cat /tmp/commit-hygiene.out 2>/dev/null | tr '\n' ' ')"
        _red=$(git rev-parse HEAD)
        _arch="/tmp/strays/${tag}-hygiene-$(date -u +%Y%m%dT%H%M%SZ)"
        mkdir -p "$_arch"
        git show --stat "$_red" >"$_arch/stat.txt" 2>&1 || true
        git show "$_red" >"$_arch/full.diff" 2>&1 || true
        cp /tmp/commit-hygiene.out "$_arch/hygiene.txt" 2>/dev/null || true
        printf '%s\n' "$_red" >"$_arch/sha.txt"
        git reset --hard HEAD~1 >> "$LOG" 2>&1 || true
        attempt=$((attempt+1))
        continue
      fi
      # Escalation KPI: the orchestrator marks direct implementations with
      # an ESCALATED run-log row — count them for the retro.
      if tail -5 migration/run-log.md 2>/dev/null | grep -q "ESCALATED"; then
        event "$tag" "$attempt" escalated kpi; log "$tag: ESCALATED — orchestrator implemented directly (packet-quality KPI)"
        # N1: escalated code carries the full acceptance — flag main-source
        # commits that ship without test changes (coverage erosion source).
        if git show --stat HEAD | grep -q "src/main/" && ! git show --stat HEAD | grep -q "src/test/"; then
          event "$tag" "$attempt" escalated_untested kpi
          log "$tag: WARNING — escalated commit touches src/main with NO test changes (acceptance requires tests with code)"
        fi
      fi
      # The stage is sealed — any worker still running is a zombie whose
      # output can no longer land. Kill it now instead of waiting 60m.
      if pgrep -x opencode >/dev/null 2>&1; then
        log "$tag: killing residual worker (stage already committed)"
        pkill -9 -x opencode
      fi
      # Untracked-stray sweep (V3: sessions twice left broken uncommitted
      # test files that failed later builds) — committed work is the only
      # work. Strays are ARCHIVED to /tmp/strays/<tag>/ (S03 lesson: the
      # sweep deleted a brief-required test a later task could have
      # salvaged), keeping the tree clean without destroying work.
      # O-STRAYSCAFFOLD / O-STRAYPKGINFO (Wave2): never archive scaffold under
      # src/{main,test}/java/ — .gitkeep AND package-info.java. F-19: gitkeep-
      # only keep would wipe Qwen package-info on a thin MiniMax commit (same
      # class as T-001). Keep on disk; archive other src/ strays; write
      # KEPT-SCAFFOLD.txt (+ KEPT-GITKEEP.txt compat) for audit/escalation.
      KEEP_SCAFFOLD=""
      STRAYS=""
      while IFS= read -r f; do
        [ -n "$f" ] || continue
        if { [[ "$f" == src/main/java/* ]] || [[ "$f" == src/test/java/* ]]; } \
          && { [[ "$f" == *.gitkeep ]] || [[ "$f" == */package-info.java ]]; }; then
          KEEP_SCAFFOLD="${KEEP_SCAFFOLD}${f}"$'\n'
        else
          STRAYS="${STRAYS}${f}"$'\n'
        fi
      done < <(git ls-files --others --exclude-standard -- src/)
      if [ -n "$(echo "$STRAYS" | tr -d '[:space:]')" ]; then
        log "$tag: archiving untracked strays left by the session to /tmp/strays/${tag}/: $(echo "$STRAYS" | tr '\n' ' ')"
        mkdir -p "/tmp/strays/${tag}"
        printf '%s' "$STRAYS" | while IFS= read -r f; do
          [ -n "$f" ] || continue
          mkdir -p "/tmp/strays/${tag}/$(dirname "$f")"
          mv "$f" "/tmp/strays/${tag}/$f" 2>/dev/null || rm -f "$f"
        done
      fi
      if [ -n "$(echo "$KEEP_SCAFFOLD" | tr -d '[:space:]')" ]; then
        log "$tag: O-STRAYSCAFFOLD — keeping untracked java-tree scaffold (.gitkeep|package-info.java): $(echo "$KEEP_SCAFFOLD" | tr '\n' ' ')"
        mkdir -p "/tmp/strays/${tag}"
        printf '%s' "$KEEP_SCAFFOLD" > "/tmp/strays/${tag}/KEPT-SCAFFOLD.txt"
        printf '%s' "$KEEP_SCAFFOLD" > "/tmp/strays/${tag}/KEPT-GITKEEP.txt"
      fi
      scope_enforce "$prefix"
      post_commit_verify "$prefix" "$tag"
      return 0
    fi
    local cls; cls=$(classify "$rc" "/tmp/sup-${tag}-a${attempt}p${pf}.log")
    event "$tag" "$attempt" "$cls" retrying
    case "$cls" in
      quota)
        log "$tag: quota throttle — backing off 15m (attempt NOT burned)"
        # L-R1: surface MiniMax waits in the demo outer-loop narrative
        outer_log "         … waiting on MiniMax rate limit (900s backoff; attempt NOT burned) — tag=${tag}"
        sleep 900; pf=$((pf+1));;
      stream_stall|ctx_overflow)
        log "$tag: $cls — platform fault, retrying in 2m (attempt NOT burned)"
        sleep 120; pf=$((pf+1));;
      orphan_worker)
        # V6 P2.3: after residual kill/wait, ONLY verify-and-commit — do not
        # re-dispatch a full M4/opencode session (normal rprompt still may).
        log "$tag: session abandoned a running worker — waiting/killing residual, then verify-and-commit (no auto second opencode)"
        wait_for_worker
        case "$prefix" in
          T*|S*) prompt="$(verify_commit_prompt "$prefix")";;
          *)     prompt="$rprompt";;
        esac
        pf=$((pf+1));;
      timeout)
        log "$tag: session hit the ${ORCH_LAST_BUDGET:-$SESSION_TIMEOUT}s budget — attempt $attempt burned, partial work stays for the next attempt"
        attempt=$((attempt+1));;
      no_commit)
        log "$tag: session ended without commit — attempt $attempt burned"
        attempt=$((attempt+1));;
    esac
    if [ $pf -ge $MAX_PLATFORM_RETRIES ]; then
      log "$tag: $MAX_PLATFORM_RETRIES consecutive platform faults — burning an attempt to avoid an infinite loop"
      pf=0; attempt=$((attempt+1))
    fi
  done
  # Mechanical commit closure (cart run #2: fix sessions three times did
  # correct, sensor-green work and exhausted before the commit step — the
  # "T-003 pattern" — and each time a human closed a purely mechanical
  # step; the gate round even ended a run with the solution sitting
  # uncommitted). If the leftover tree passes the task sensor, the
  # supervisor completes the commit itself; the deeper gates (pre-push
  # preflight, factory) still guard everything downstream.
  if [ -n "$(git status --porcelain)" ]; then
    if .hermes/harness/sensors.sh task >> "$LOG" 2>&1; then
      # O-T6c: MiniMax escalation closure must not sweep .hermes/ into T-NNN:
      stage_for_task_commit
      if ! git diff --cached --quiet; then
        git commit -m "${prefix}: supervisor mechanical commit of sensor-green session work" >/dev/null 2>&1
        event "$tag" "$MAX_ATTEMPTS" mechanical_commit closure
        log "$tag: session work was sensor-GREEN but uncommitted — supervisor completed the commit ($(git log --oneline -1))"
        return 0
      fi
    fi
    # O-SENSORGATE (N12): never checkpoint a RED tree — that was 11 of the
    # S02 sensor_red_post_commit events. Leave dirt for the next attempt /
    # archive; do not create a RED tip.
    log "$tag: O-SENSORGATE — attempts exhausted with RED tree — refusing checkpoint commit (N12)"
    event "$tag" 0 sensor_gate_refuse_checkpoint red
    mkdir -p "/tmp/strays/${tag}-red-checkpoint"
    git status --porcelain > "/tmp/strays/${tag}-red-checkpoint/status.txt" 2>&1 || true
    git diff > "/tmp/strays/${tag}-red-checkpoint/diff.patch" 2>&1 || true
    return 1
  fi
  log "$tag: attempts exhausted with no session work in the tree"
  return 1
}

# ------------------------------------------------------------- Retro
# After a story/run closes, one bounded session writes proposals split
# into (a) brief updates the outer loop may auto-apply to remaining
# briefs and (b) skill/harness proposals for humans only. Retro never
# edits .hermes/skills/** or harness scripts; a failed retro never
# blocks the run outcome.
phase_f_retro() {
  committed "Retro" && return 0
  cp "$EVENTS" migration/retro-events.csv 2>/dev/null || true
  cp "$METRICS" migration/retro-metrics.csv 2>/dev/null || true
  git add migration/retro-*.csv >/dev/null 2>&1 || true
  # O-RETROAPPEND: archive prior proposals before overwrite so misdiagnoses
  # remain in migration/retro-history/ (V10 Poll 67 erased two records).
  local retro_label
  retro_label=$(echo "${STORY_SPEC_PREFIX:-run}" | awk '{print $1}')
  if [ -f .hermes/harness/archive-retro.py ]; then
    local archived
    archived=$(python3 .hermes/harness/archive-retro.py --label "$retro_label" 2>/dev/null || echo noop)
    [ "$archived" != "noop" ] && log "Retro: O-RETROAPPEND archived prior proposals → $archived"
    git add migration/retro-history/ >/dev/null 2>&1 || true
  fi
  orch "retro" \
"Use the migration-harness skill. The migration run/story is CLOSED — this is Retro. Evidence to read with your file tools: migration/run-report.md, migration/retro-events.csv, migration/retro-metrics.csv, migration/run-log.md, migration/debt.md, migration/discovered.md (K9 forward-looking scope — not debt), remaining briefs under migration/briefs/ (if any), migration/retro-history/ (prior story retros — do not delete), and the skill files PLANNING.md, EXECUTION.md, SHIPPING.md, MAPPINGS.md. Write migration/retro-proposals.md for THIS story only with EXACTLY these markdown sections (both required). Prior stories are already archived under migration/retro-history/ — do NOT delete that directory.

## Brief updates (auto-applicable)
Concrete edits for REMAINING story briefs only (not the story just finished). Fold actionable rows from migration/discovered.md when they fit. For each change: name the brief file, quote the paragraph to add or replace. Empty list is fine if nothing should change.

## Skill / harness proposals (human-only)
(1) the three costliest failure patterns of THIS story/run, citing evidence; (2) for each pattern one CONCRETE proposed change to a specific skill or sensor — quote exact text and name file/section; (3) ARTIFACT review of this story's commits (harvest fidelity, story-scope, fabrication); (4) harness waste. PROPOSE ONLY. Prefer evidence-based attribution over repeating prior archived misdiagnoses.

## K10 hints (optional)
For each Findings rule that this story solved cleanly, optionally run:
`python3 .hermes/harness/write-hint.py <rule-id> '<≤5 lines: before→after shape, no specimen class/package names>'`
Hints land in migration/hints/ and are injected into later task packets.

Do NOT modify any skill, harness script, or brief in this session — proposals file only. Finish with ONE commit whose message STARTS with 'Retro:' and includes migration/retro-history/ if present.
${RUN_CONTRACT}"
  committed "Retro" && log "Retro: retro proposals committed $(git log --oneline -1)" \
    || log "Retro: retro session did not commit — skipped (non-blocking)"
}

write_run_report() { # $1 = outcome line
  {
    echo "# Autonomous run report"
    echo ""
    # Stakeholder-readable summary first, telemetry after (MigIQ
    # adoption: the report is also the executive artifact).
    echo "## Executive summary"
    echo ""
    echo "Autonomous migration of $(basename "$(git remote get-url origin)" .git):"
    echo "$1. Findings delta and per-task detail: migration/run-log.md;"
    echo "debt: migration/debt.md. Orchestrator ${ORCH_PROVIDER}/${ORCH_MODEL},"
    echo "worker ${WORKER_MODEL}, $(awk -F, 'NR>1{n++}END{print n+0}' "$METRICS") model sessions."
    echo ""
    echo "- Outcome: $1"
    echo "- Supervisor version: ${SUPERVISOR_VERSION}; run base: ${RUN_BASE}"
    echo "- Orchestrator: ${ORCH_PROVIDER}/${ORCH_MODEL}; worker: ${WORKER_MODEL}"
    echo ""
    echo "## Sessions"
    echo ""
    echo "| session | seconds | rc |"
    echo "|---|---|---|"
    awk -F, 'NR>1 {printf "| %s | %s | %s |\n", $1, $4, $5}' "$METRICS"
    echo ""
    echo "- Escalations (KPI, from supervisor events): $(awk -F, '\$4=="escalated"' "$EVENTS" | wc -l | tr -d ' ') (untested: $(awk -F, '\$4=="escalated_untested"' "$EVENTS" | wc -l | tr -d ' '))"
    echo ""
    echo "## Classified events"
    echo ""
    echo '```'
    awk -F, 'NR>1 {print $4}' "$EVENTS" | sort | uniq -c | sort -rn
    echo '```'
    echo ""
    echo "## Per-rule outcomes (K11)"
    echo ""
    echo "| rule | outcomes |"
    echo "|---|---|"
    awk -F, '
      $4 ~ /^rule:/ {
        r=substr($4,6); o=$5; c[r]=c[r] (c[r]?", ":"") o
      }
      END { for (r in c) printf "| `%s` | %s |\n", r, c[r] }
    ' "$EVENTS" | sort
    if ! awk -F, '$4 ~ /^rule:/ {found=1} END{exit !found}' "$EVENTS" 2>/dev/null; then
      echo "| _(none recorded)_ | |"
    fi
    if [ -f migration/discovered.md ] && grep -qE '^\| 20' migration/discovered.md 2>/dev/null; then
      echo ""
      echo "## Discovered work (K9)"
      echo ""
      echo "See migration/discovered.md — $(grep -cE '^\| 20' migration/discovered.md 2>/dev/null || echo 0) row(s)."
    fi
  } > migration/run-report.md
  git add migration/run-report.md && git commit -q -m "Run report: $1" 2>/dev/null || true
}

# ---------------------------------------------------------------- M1
# SHIP_ONLY=1 — re-earn M5 ship/acceptance without replaying M1–M4 (O-FALSECOMPLETE).
# Requires STORY_DEPLOY + a tree that already implements the story. Does not
# mark story-state.csv; the caller (or outer-loop) records the supervisor-done
# outcome. Never use this to skip unfinished coding work.
if [ "${SHIP_ONLY:-}" = "1" ]; then
  log "SHIP_ONLY=1 — skipping M1–M4 and M5 evaluate; jumping to M5 ship"
  outer_log "         SHIP_ONLY: jumping to M5 ship (O-FALSECOMPLETE re-earn)"
else
# The harness owns the analysis end-to-end (2026-07-27 decision): M1
# ALWAYS runs its own kantra with the migration.yaml analysis contract —
# deterministic rule selection, reproducible ground truth. An IDE-run
# analysis is a demo/browsing aid, never the harness input.
if committed "M1 analyze" || [ -f migration/mta-findings.json ]; then
  log "M1: already present"
else
  # Extracted to analyze.sh (V4) so the outer loop can run the same step
  # before M2 sequencing; behavior unchanged.
  if .hermes/harness/analyze.sh >> "$LOG" 2>&1; then
    log "M1: committed by script — $(git log --oneline -1)"
  else
    log "FATAL: M1 ground truth unavailable"; write_run_report "m1-failed"; echo m1-failed > /tmp/supervisor-done; exit 1
  fi
fi

if plan_stage_done; then
  log "M3: already present"
else
  run_stage "M3 spec" "m3-spec" \
"Use the migration-harness skill and read PLANNING.md in its directory. M1 is committed. Execute M3 ONLY: read the legacy code under /projects/legacy and the findings (scripted extraction only), then write specs/001-migration/spec.md, plan.md and tasks.md per the skill. A deterministic plan lint gates the result (format, ids, ordering, design content, finding/preserve/acceptance coverage) — PLANNING.md states the rules it enforces.
${RUN_CONTRACT}
Finish with ONE commit whose message STARTS with 'M3 spec:'. Stop after M3." \
"Use the migration-harness skill and read PLANNING.md in its directory. Execute M3 ONLY; a previous attempt did not commit. If specs/001-migration/{spec,plan,tasks}.md exist and are complete, commit them with message starting 'M3 spec:'; otherwise finish writing them first. ${RUN_CONTRACT}" \
    || { log "FATAL: M3 failed"; echo m3-failed > /tmp/supervisor-done; exit 1; }
fi

# ------------------------------------------------------------- Plan lint
# Deterministic B2 gate: a defective plan is bounced ONCE for revision
# with the specific lint findings before M4 spends hours on it.
TASKS_FILE="${STORY_TASKS:-$(ls specs/*/tasks.md 2>/dev/null | head -1)}"
SCOPE_ARGS=""
[ -n "$PLAN_SCOPE" ] && SCOPE_ARGS="--findings-scope $PLAN_SCOPE"
# O-M3ACCEPT: supervisor must pass the same deploy flag outer-loop uses —
# otherwise a lint-green non-deploy plan is re-REDed here and burns m3-lint.
DEPLOY_ARGS="--story-deploy ${STORY_DEPLOY:-true}"
# O-SHAPEDECL: live M3 requires **Shape** on every task (instruments stay WARN).
export PLAN_LINT_REQUIRE_SHAPE="${PLAN_LINT_REQUIRE_SHAPE:-1}"
LINT_OUT=$(python3 .hermes/harness/plan-lint.py "$TASKS_FILE" migration/mta-findings.json $SCOPE_ARGS $DEPLOY_ARGS 2>&1)
if [ $? -ne 0 ] && ! committed "M3 revision"; then
  log "plan lint: revision required"; echo "$LINT_OUT" | head -20 >> "$LOG"
  printf '%s\n' "$LINT_OUT" > /tmp/plan-lint.txt
  run_stage "M3 revision" "m3-lint" \
"Use the migration-harness skill and read PLANNING.md and MAPPINGS.md in its directory. The plan lint REJECTED ${TASKS_FILE} — the findings are in /tmp/plan-lint.txt (read it with your file tools). Revise ONLY ${TASKS_FILE} (and sibling files in that same specs/<story>/ directory) to fix every lint finding: infer tasks must carry the decided target design (file mappings, signatures, annotations — cite MAPPINGS.md shapes). Do not renumber or remove completed work.
O-SPECFROZEN: NEVER edit specs/ for a story whose migration/story-state.csv last status is complete (e.g. S01 after S01,complete). Do not delete delivered tasks from finished stories.
${RUN_CONTRACT}
Commit prefix: 'M3 revision:'." \
"Use the migration-harness skill and read PLANNING.md in its directory. Finish revising ONLY ${TASKS_FILE} per /tmp/plan-lint.txt and commit with prefix 'M3 revision:'. O-SPECFROZEN: never mutate complete stories' specs/.
${RUN_CONTRACT}" \
    || log "plan lint: revision round exhausted — proceeding with the plan as-is (recorded)"
  LINT2=$(python3 .hermes/harness/plan-lint.py "$TASKS_FILE" migration/mta-findings.json $SCOPE_ARGS $DEPLOY_ARGS 2>&1) \
    && log "plan lint: PASS after revision" || log "plan lint: still failing after revision — proceeding, findings logged"
fi

# ---------------------------------------------------------------- M4
TASKS_FILE="${STORY_TASKS:-$(ls specs/*/tasks.md 2>/dev/null | head -1)}"
# Accept 3-6 hash heading levels and any T-style id — models format
# tasks.md differently no matter what the prompt mandates (run #3 lesson).
# Depth 2-6, matching plan-lint exactly — a '## T-001:' plan used to pass
# the lint and then FATAL here (audit finding: regex drift between the
# two parsers).
TASK_IDS=$(grep -E '^#{2,6} +T[-A-Za-z0-9]*[0-9]+:' "$TASKS_FILE" | sed -E 's/^#+ +(T[-A-Za-z0-9]*[0-9]+):.*/\1/')
[ -n "$TASK_IDS" ] || { log "FATAL: no task ids parsed from $TASKS_FILE"; echo no-tasks > /tmp/supervisor-done; exit 1; }
log "task list: $(echo $TASK_IDS | tr '\n' ' ')"

# Resume hygiene: a relaunch may inherit a red tree from work committed
# before post-commit verification existed (or from a failed sensor-fix).
# Verify once at loop entry; RED gets one evidence-driven fix session.
if ! .hermes/harness/sensors.sh task >> "$LOG" 2>&1; then
  event "loop-entry" 0 sensor_red_at_entry verify
  log "loop entry: tree sensor RED — dispatching tree-fix session before tasks"
  orch "treefix" \
"Use the migration-harness skill and read EXECUTION.md in its directory. The working tree is RED before task execution: .hermes/harness/sensors.sh task fails — read /tmp/sensor-task.log for the exact errors. Diagnose and fix the ROOT CAUSE (typical: files harvested prematurely without their extension/dependency, or into the wrong package — fix or revert them; add a dependency ONLY if already-committed task scope requires it). Run .hermes/harness/sensors.sh task until GREEN, then commit ONE commit whose message STARTS with 'Tree fix:'.
${RUN_CONTRACT}"
  committed "Tree fix" && log "loop entry: tree fix committed $(git log --oneline -1)" \
    || log "loop entry: tree-fix did not commit — proceeding on a red tree (recorded)"
fi

# Per-task class map (for batching): rewrite-class tasks are mechanical
# and consecutive ones share one session (improvement #17 — measured 12
# min/task mean is dominated by per-session ramp for mechanical work).
# O-CLASSPROMPT: same Class field parser as task-packet.py (**Class: rewrite**
# and **Class**: rewrite). Old regex treated **Class**: as non-match → false infer.
TASK_CLASSES=$(python3 - "$TASKS_FILE" <<'PYEOF'
import re, sys

def field(body: str, *names: str) -> str:
    for name in names:
        m = re.search(
            rf"^\*\*{re.escape(name)}\s*:\s*(.+?)\*\*\s*$", body, re.M | re.I
        )
        if m:
            return m.group(1).strip()
        m = re.search(
            rf"^\*\*{re.escape(name)}\*\*\s*:?\s*(.+)$", body, re.M | re.I
        )
        if m:
            return m.group(1).strip()
        m = re.search(rf"^{re.escape(name)}\s*:\s*(.+)$", body, re.M | re.I)
        if m:
            return m.group(1).strip()
    return ""

text = open(sys.argv[1], encoding="utf-8").read()
blocks = re.split(r"^#{2,6} +(T[-A-Za-z0-9]*\d+):", text, flags=re.M)
for i in range(1, len(blocks) - 1, 2):
    tid, body = blocks[i], blocks[i + 1]
    cls = field(body, "Class", "Type") or "infer"
    m = re.search(r"\b(rewrite|infer)\b", cls, re.I)
    print(f"{tid}:{(m.group(1).lower() if m else 'infer')}")
PYEOF
)
task_class() { echo "$TASK_CLASSES" | grep -m1 "^$1:" | cut -d: -f2; }

# Oracle from tasks.md (O-INFERABSENT) — absent|present; default present.
task_oracle() {
  python3 - "$TASKS_FILE" "$1" <<'PY' 2>/dev/null || echo present
import re, sys
path, tid = sys.argv[1], sys.argv[2]
text = open(path, encoding="utf-8", errors="replace").read()
heads = list(re.finditer(r"^#{2,6}\s+(T[-A-Za-z0-9]*\d+)\s*:", text, re.M))
body = ""
for i, m in enumerate(heads):
    if m.group(1) != tid:
        continue
    end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
    body = text[m.end():end]
    break
m = re.search(r"^\*\*Oracle\s*:\s*(.+?)\*\*\s*$", body, re.M | re.I)
if not m:
    m = re.search(r"^\*\*Oracle\*\*\s*:?\s*(.+)$", body, re.M | re.I)
if not m:
    m = re.search(r"^Oracle\s*:\s*(.+)$", body, re.M | re.I)
val = (m.group(1).strip().lower() if m else "")
print("absent" if val.startswith("absent") else "present")
PY
}

# Task title from tasks.md heading (demo log: T-001 + human description).
task_title() { # $1=task-id
  local tid="$1"
  [ -f "${TASKS_FILE:-}" ] || { echo "$tid"; return; }
  python3 -c "
import re, sys
tid, path = sys.argv[1], sys.argv[2]
text = open(path, encoding='utf-8', errors='replace').read()
m = re.search(r'^#{2,6}\s+' + re.escape(tid) + r'\s*:\s*(.+)$', text, re.M)
print(m.group(1).strip() if m else tid)
" "$tid" "$TASKS_FILE" 2>/dev/null || echo "$tid"
}

# Demo + supervisor: task progress with code AND description.
log_task() { # $1=START|END|SKIP|BATCH  $2=tid-or-ids  [$3=detail]
  local kind="$1" tid="$2" detail="${3:-}" title cls line
  case "$kind" in
    BATCH)
      line="▶ TASKS  batch rewrite — ${tid}${detail:+ — $detail}"
      ;;
    START)
      title=$(task_title "$tid"); cls=$(task_class "$tid")
      [ -n "$cls" ] || cls="?"
      line="▶ TASK   ${tid} — ${title} [class=${cls}]${detail:+ — ${detail}}"
      ;;
    END)
      title=$(task_title "$tid")
      line="✓ TASK   ${tid} — ${title}${detail:+ — ${detail}}"
      ;;
    SKIP)
      title=$(task_title "$tid")
      line="· TASK   ${tid} — ${title}${detail:+ — ${detail}}"
      ;;
    *)
      line="  TASK   ${tid}${detail:+ — ${detail}}"
      ;;
  esac
  log "$line"
  outer_log "$line"
}

# V6 P2.4 — already-complete fast path (strict probe).
# Probe lives in already-complete.py so instruments can lock the contract.
# V6 abort evidence: bash grepping the first Capitalized word as a class
# (`Convert`/`Port`) false-greened real CDI conversion tasks.
try_already_complete() { # $1=task-id → 0 if auto-committed
  local T="$1" reason kind detail
  committed "$T" && return 0
  [ -f "${TASKS_FILE:-}" ] || return 1
  [ -f .hermes/harness/already-complete.py ] || return 1
  reason=$(STORY_DEPLOY="${STORY_DEPLOY:-false}" ALREADY_COMPLETE_ROOT="$PWD" \
    python3 .hermes/harness/already-complete.py "$TASKS_FILE" "$T" 2>/dev/null) || return 1
  [ -n "$reason" ] || return 1
  kind=${reason%%:*}; detail=${reason#*:}
  case "$kind" in
    present)
      git commit --allow-empty -q -m "${T}: ALREADY COMPLETE — ${detail} already present (V6 P2.4)" 2>/dev/null \
        || git commit --allow-empty -m "${T}: ALREADY COMPLETE — ${detail} already present (V6 P2.4)" >/dev/null 2>&1
      event "$T" 0 already_complete "$detail"
      log "$T: ALREADY COMPLETE — ${detail} present; skipped opencode"
      return 0
      ;;
    absent|oracle-absent)
      # O-ACORACLE (Wave2 T-005): already-complete.py emits oracle-absent:<id>
      # when Findings are gone — was ignored (kind not in case) so worker ran
      # then O-T6d no-path-overlap → false MiniMax on an already-absent removal.
      git commit --allow-empty -q -m "${T}: ALREADY COMPLETE — ${detail} already absent (V6 P2.4)" 2>/dev/null \
        || git commit --allow-empty -m "${T}: ALREADY COMPLETE — ${detail} already absent (V6 P2.4)" >/dev/null 2>&1
      event "$T" 0 already_complete "absent:$detail"
      log "$T: ALREADY COMPLETE — ${detail} absent; skipped opencode"
      return 0
      ;;
    scaffold-presatisfied)
      # O-DESTBASE / O-JDBCSKIP class: probe returns 0 but kind was ignored → worker
      git commit --allow-empty -q -m "${T}: ALREADY COMPLETE — scaffold-presatisfied ${detail} (O-DESTBASE)" 2>/dev/null \
        || git commit --allow-empty -m "${T}: ALREADY COMPLETE — scaffold-presatisfied ${detail} (O-DESTBASE)" >/dev/null 2>&1
      event "$T" 0 already_complete "scaffold-presatisfied:$detail"
      log "$T: ALREADY COMPLETE — scaffold-presatisfied ${detail}; skipped opencode"
      return 0
      ;;
  esac
  return 1
}

# V6 P2.3 — verify-and-commit: never auto-launch a second opencode unless the
# tree is dirty AND the task sensor is RED.
verify_commit_prompt() { # $1=task-id
  local T="$1"
  cat <<EOF
Use the migration-harness skill and read EXECUTION.md in its directory. VERIFY-AND-COMMIT ONLY for task ${T} from ${TASKS_FILE}.
A previous attempt may have left partial work or an orphaned worker.
Rules (V6 P2.3):
1. Inspect git status --porcelain first.
2. Run .hermes/harness/sensors.sh task once.
3. Do NOT launch opencode unless the working tree is dirty AND that sensor is RED.
4. If sensors are GREEN: commit ONE commit whose message STARTS with '${T}:' describing the work. Do NOT invent allow-empty 'ALREADY COMPLETE' commits — that path is supervisor-only via already-complete.py (O-AC).
5. Never background a worker; never use python3 heredocs or python3 -c multi-line scripts — use bundled harness scripts only.
${RUN_CONTRACT}
EOF
}

# V7 model routing — OpenCode/Qwen does M4 coding; MiniMax not in this path.
run_worker_task() { # $1=task-id → 0 if committed
  local T="$1" packet rc
  committed "$T" && return 0
  [ -f .hermes/harness/task-packet.py ] || return 1
  wait_for_worker
  packet=$(python3 .hermes/harness/task-packet.py "$TASKS_FILE" "$T" "$WORKER_MODEL" 2>/tmp/task-packet.err) || {
    log "$T: task-packet.py failed — $(head -1 /tmp/task-packet.err 2>/dev/null)"
    return 1
  }
  [ -n "$packet" ] || return 1
  log_task START "$T" "Actor: $(worker_label) — MiniMax not used for coding"
  # O-WORKERWEDGE-RCA / O-WEDGESKIP: after a wedge kill, skip further Qwen
  # seats until the next successful story task commit (mechan/worker/escalation)
  # clears /tmp/worker-wedge-skip — do NOT burn MiniMax for the rest of the story.
  local story_key
  story_key=$(echo "${STORY_SPEC_PREFIX:-run}" | awk '{print $1}')
  if [ -f /tmp/worker-wedge-skip ] && grep -qxF "$story_key" /tmp/worker-wedge-skip 2>/dev/null; then
    log "$T: skip worker — prior wedge/thrash this story (O-WORKERWEDGE-RCA; clears on next task commit — O-WEDGESKIP)"
    echo "worker skipped — prior wedge class this story (O-WORKERWEDGE-RCA)" >> "/tmp/oc-${T}.err"
    WORKER_LAST_RC=143
    return 1
  fi
  # O-WORKERWEDGE / O-OCSTALL: hard timeout alone burns 1800s on a hung OpenCode
  # with a frozen session JSON. Run under timeout in the background and kill early
  # if /tmp/oc-${T}.json stops growing (default 300s unchanged).
  : > "/tmp/oc-${T}.json"
  : > "/tmp/oc-${T}.err"
  timeout 1800 opencode run "$packet" \
    -m "$WORKER_MODEL" --auto --format json \
    -f "$TASKS_FILE" -f AGENTS.md \
    > "/tmp/oc-${T}.json" 2>"/tmp/oc-${T}.err" &
  local wpid=$!
  local stale=0 last_sz=-1 sz
  local stale_limit="${WORKER_JSON_STALE_SECS:-300}"
  while kill -0 "$wpid" 2>/dev/null; do
    sleep 60
    sz=$(stat -c%s "/tmp/oc-${T}.json" 2>/dev/null || echo 0)
    if [ "$sz" -eq "$last_sz" ]; then
      stale=$((stale + 60))
    else
      stale=0
      last_sz=$sz
    fi
    # O-WORKERREAD / O-FIRSTMUT: kill early on read/glob thrash with zero
    # edit/write (bash alone does NOT count as mutate — R-222 T-007: 23 reads
    # + 2 bash + 0 edit escaped the old watch and burned to JSON_STALE).
    if [ -f .hermes/harness/worker-read-watch.py ] \
      && thrash=$(python3 .hermes/harness/worker-read-watch.py "/tmp/oc-${T}.json" 2>/dev/null); then
      log "$T: worker read-thrash — ${thrash} — killing early (O-WORKERREAD/O-FIRSTMUT)"
      {
        echo "worker read-thrash — ${thrash} (O-WORKERREAD/O-FIRSTMUT)"
        echo "abort: reads+globs exceeded with no edit/write — escalate or replan"
      } >> "/tmp/oc-${T}.err"
      kill "$wpid" 2>/dev/null || true
      sleep 2
      kill -9 "$wpid" 2>/dev/null || true
      pkill -9 -x opencode 2>/dev/null || true
      break
    fi
    if [ "$stale" -ge "$stale_limit" ]; then
      log "$T: worker wedged — no session JSON growth for ${stale}s — killing early (O-WORKERWEDGE)"
      {
        echo "worker wedged — no session output for ${stale}s (O-WORKERWEDGE)"
        echo "session JSON size frozen at ${sz} bytes"
      } >> "/tmp/oc-${T}.err"
      kill "$wpid" 2>/dev/null || true
      sleep 2
      kill -9 "$wpid" 2>/dev/null || true
      # also reap any orphaned opencode child of the timeout wrapper
      pkill -9 -x opencode 2>/dev/null || true
      break
    fi
    # O-KILLREASON / O-PAUSEWORKER: if operator HOLD appears mid-worker, stop
    # with an auditable .err (Wave2 T-003: external SIGTERM left .err empty).
    if [ -f /tmp/supervisor-pause ] || [ -f /tmp/debt-freeze ]; then
      local why="supervisor-pause"
      [ -f /tmp/debt-freeze ] && why="debt-freeze"
      [ -f /tmp/supervisor-pause ] && [ -f /tmp/debt-freeze ] && why="supervisor-pause+debt-freeze"
      log "$T: O-KILLREASON — killing worker (${why})"
      {
        echo "worker killed — ${why} (O-KILLREASON)"
        [ -f /tmp/supervisor-pause ] && { echo "--- /tmp/supervisor-pause ---"; head -n 20 /tmp/supervisor-pause; }
        [ -f /tmp/debt-freeze ] && { echo "--- /tmp/debt-freeze ---"; head -n 20 /tmp/debt-freeze; }
      } >> "/tmp/oc-${T}.err"
      kill "$wpid" 2>/dev/null || true
      sleep 2
      kill -9 "$wpid" 2>/dev/null || true
      pkill -9 -x opencode 2>/dev/null || true
      break
    fi
  done
  wait "$wpid" 2>/dev/null
  rc=$?
  WORKER_LAST_RC=$rc
  wait_for_worker
  # O-KILLREASON: if .err still empty after SIGTERM and freeze markers exist,
  # backfill (covers external pkill before this loop learned to write).
  if [ ! -s "/tmp/oc-${T}.err" ] && { [ -f /tmp/supervisor-pause ] || [ -f /tmp/debt-freeze ]; }; then
    {
      echo "worker exit rc=${rc} with empty .err during freeze (O-KILLREASON backfill)"
      [ -f /tmp/supervisor-pause ] && { echo "--- /tmp/supervisor-pause ---"; head -n 20 /tmp/supervisor-pause; }
    } >> "/tmp/oc-${T}.err"
  fi
  # O-WORKERWEDGE-RCA: classify kill/fail cause; skip further worker seats this story.
  if [ -f .hermes/harness/wedge-classify.py ] && [ -f "/tmp/oc-${T}.err" ]; then
    local wclass
    wclass=$(python3 .hermes/harness/wedge-classify.py \
      "/tmp/oc-${T}.err" "/tmp/oc-${T}.json" 2>/dev/null || echo OTHER)
    case "$wclass" in
      READ_THRASH|JSON_STALE|TRUNCATION)
        echo "$story_key" >> /tmp/worker-wedge-skip
        sort -u /tmp/worker-wedge-skip -o /tmp/worker-wedge-skip 2>/dev/null || true
        log "$T: O-WORKERWEDGE-RCA class=$wclass — further worker seats skipped this story"
        event "$T" 0 worker_wedge_class "$wclass"
        ;;
    esac
  fi
  # O-OCERR: OpenCode often leaves stderr empty; surefire noise is in the JSON.
  if [ ! -s "/tmp/oc-${T}.err" ] && [ -s "/tmp/oc-${T}.json" ]; then
    python3 - "/tmp/oc-${T}.json" "/tmp/oc-${T}.err" <<'PY' 2>/dev/null || true
import re, sys
src, dst = sys.argv[1], sys.argv[2]
raw = open(src, encoding="utf-8", errors="replace").read()
lines = []
for pat in (
    r"Tests run: [^\n\\]+",
    r"\[ERROR\][^\n\\]{0,240}",
    r"Expected status code[^\n\\]{0,120}",
    r"JSON path[^\n\\]{0,160}",
    r"BUILD FAILURE",
    r"COMPILATION ERROR",
):
    lines.extend(re.findall(pat, raw)[:20])
seen, out = set(), []
for ln in lines:
    if ln in seen:
        continue
    seen.add(ln)
    out.append(ln)
if out:
    open(dst, "w", encoding="utf-8").write(
        "O-OCERR extracted from opencode JSON (stderr was empty):\n"
        + "\n".join(out[:60])
        + "\n"
    )
PY
  fi
  log "$T: worker exit rc=${rc} (details /tmp/oc-${T}.err)"
  if committed "$T"; then
    return 0
  fi
  # Worker often leaves a green dirty tree without the required commit prefix.
  # O-PKGDIR: materialize empty package dirs before staging.
  ensure_trackable_packages
  if [ -n "$(app_dirt)" ]; then
    if .hermes/harness/sensors.sh task > /tmp/sensor-task.log 2>&1; then
      stage_for_task_commit
      if git diff --cached --quiet; then
        log "$T: O-T6e worker auto-commit skip — app dirt present but stage empty after excluding .hermes/staging (see git status)"
        return 1
      fi
      # O-T6d: do not attach this T-NNN title to an unrelated dirty tree
      if ! git diff --cached --name-only | python3 .hermes/harness/mechan-match.py "$TASKS_FILE" "$T" \
           > /tmp/mechan-match.out 2>&1; then
        log "$T: O-T6d skip worker auto-commit — staged paths mismatch task ($(cat /tmp/mechan-match.out 2>/dev/null | tr '\n' ' '))"
        git reset -q
        return 1
      fi
      git commit -q -m "${T}: $(task_title "$T") (worker $(worker_label))" 2>/dev/null \
        || git commit -m "${T}: $(task_title "$T") (worker $(worker_label))" >/dev/null 2>&1
      committed "$T" && return 0
      log "$T: O-T6e worker auto-commit failed — commit command did not produce '${T}:' prefix"
    else
      log "$T: O-T6e worker auto-commit skip — task sensor RED after worker (see /tmp/sensor-task.log)"
    fi
  else
    log "$T: O-T6e worker left no app dirt (only .hermes/staging or clean) — no auto-commit"
  fi
  return 1
}

# O-T6: dirty tree already satisfies the task sensor — commit without a model.
# O-T6b/c: stage everything except .hermes/ and migration/staging/.
# O-T6d: staged paths must match the task targets (no wrong-title commits).
try_mechan_commit() { # $1=task-id → 0 if committed
  local T="$1"
  committed "$T" && return 0
  [ -n "$(git status --porcelain 2>/dev/null)" ] || return 1
  if .hermes/harness/sensors.sh task > /tmp/sensor-task.log 2>&1; then
    stage_for_task_commit
    if git diff --cached --quiet; then
      log "$T: O-T6b skip mechan-commit — only .hermes/staging dirt (or empty stage)"
      return 1
    fi
    if ! git diff --cached --name-only | python3 .hermes/harness/mechan-match.py "$TASKS_FILE" "$T" \
         > /tmp/mechan-match.out 2>&1; then
      log "$T: O-T6d skip mechan-commit — staged paths mismatch task ($(cat /tmp/mechan-match.out 2>/dev/null | tr '\n' ' '))"
      git reset -q
      return 1
    fi
    git commit -q -m "${T}: $(task_title "$T") (mechanical verify-and-commit; O-T6)" 2>/dev/null \
      || git commit -m "${T}: $(task_title "$T") (mechanical verify-and-commit; O-T6)" >/dev/null 2>&1
    if committed "$T"; then
      log "$T: mechanical verify-and-commit (dirty+GREEN; O-T6)"
      clear_worker_wedge_skip
      return 0
    fi
  fi
  return 1
}

# O-ESCW (V9 S01): worker exits 0 on an already-satisfied POM/dep task, leaves a
# clean tree, and never commits — supervisor used to escalate to MiniMax just to
# write "Already satisfied". If the tree is clean and task sensor is GREEN,
# commit allow-empty here (no MiniMax).
# O-ESCW2 (V9 S03): .hermes/ + migration/staging-only dirt counts as clean.
# O-ESCW3 (V9 S03): never allow-empty when deliverables are still missing
# (characterization without src/test, missing Target .java) — T-008 false green.
try_worker_verified_noop() { # $1=task-id → 0 if committed
  local T="$1" why
  committed "$T" && return 0
  [ -z "$(app_dirt)" ] || return 1
  # O-ESCWCONVERT: only after a successful worker exit (rc=0). A wedged/killed
  # worker (rc=143/124/…) with a clean tree is incomplete — escalate, don't ESCW.
  [ "${WORKER_LAST_RC:-1}" = "0" ] || {
    log "$T: O-ESCW skip allow-empty — worker rc=${WORKER_LAST_RC:-unset} (not verified)"
    return 1
  }
  if ! why=$(ALREADY_COMPLETE_ROOT="$PWD" python3 .hermes/harness/escw-eligible.py \
       "$TASKS_FILE" "$T" 2>/tmp/escw-eligible.err); then
    log "$T: O-ESCW3 skip allow-empty — deliverables still required ($(cat /tmp/escw-eligible.err 2>/dev/null | tr '\n' ' '; echo "$why" | tr '\n' ' '))"
    return 1
  fi
  if .hermes/harness/sensors.sh task > /tmp/sensor-task.log 2>&1; then
    git commit --allow-empty -q \
      -m "${T}: Already satisfied (worker verified clean tree; O-ESCW)" 2>/dev/null \
      || git commit --allow-empty \
        -m "${T}: Already satisfied (worker verified clean tree; O-ESCW)" >/dev/null 2>&1
    committed "$T" && {
      log "$T: O-ESCW allow-empty already-satisfied commit (no MiniMax escalation)"
      return 0
    }
  fi
  return 1
}

run_task() { # $1=task id — worker-first, MiniMax escalation only if needed
  local T="$1"
  # O-REDATTRIB: sensors attribute G-CAT to the owning acceptance task.
  export CURRENT_TASK="$T"
  export STORY_TASKS="${TASKS_FILE:-${STORY_TASKS:-}}"
  # O-PAUSEWORKER / O-HOTSWAPRELOAD: gate worker tasks (WORKER_FIRST never
  # enters orch() alone). After harness-update, exit for outer re-enter.
  hotswap_pause_gate "$T"
  # K7: baseline failure signature before worker/commit (empty if green).
  if [ -f .hermes/harness/failure-sig.py ]; then
    python3 .hermes/harness/failure-sig.py capture "/tmp/failure-sig-before-${T}.txt" \
      /tmp/sensor-task.log /tmp/sensor-milestone.log /tmp/sensor-sonar.log \
      /tmp/sonar-violations.txt >> "$LOG" 2>&1 || true
  fi
  if debt_frozen; then
    log "$T: O-DEBTFRZ — skip (debt freeze active)"
    return 1
  fi
  if try_already_complete "$T"; then
    log_task SKIP "$T" "already complete (fast path); skipped worker"
    record_rule_outcomes "$T" "already_complete"
    scope_enforce "$T"
    post_commit_verify "$T" "$T"
    debt_frozen && return 1
    return 0
  fi
  # O-HARVESTSTALL: rewrite tasks with missing Target .java — harvest from
  # staging before worker so Qwen is not wedged on a clean tree (S05 T-001).
  if [ "$(task_class "$T")" = "rewrite" ] \
    && [ -f .hermes/harness/preseed-targets.py ]; then
    if PRESEED_ROOT="$PWD" python3 .hermes/harness/preseed-targets.py \
         "$TASKS_FILE" "$T" > /tmp/preseed-${T}.out 2>/tmp/preseed-${T}.err; then
      if grep -q '^seeded:' /tmp/preseed-${T}.out 2>/dev/null; then
        log "$T: O-HARVESTSTALL preseed — $(tr '\n' ' ' </tmp/preseed-${T}.out)"
      fi
    fi
  fi
  # O-PKGDIR before mechan: empty dirs → .gitkeep so mkdir work can commit
  ensure_trackable_packages
  # O-T6: untracked/dirty target tree already green — don't burn a model seat
  if try_mechan_commit "$T"; then
    log_task END "$T" "mechanical commit (O-T6) — $(git log --oneline -1 | cut -c1-80)"
    record_rule_outcomes "$T" "mechan"
    scope_enforce "$T"
    post_commit_verify "$T" "$T"
    debt_frozen && return 1
    return 0
  fi
  # O-INFERABSENT (R-231): infer + Oracle:absent is the S03 T-007/T-012 wedge
  # signature (high-read/0-write → JSON_STALE). Skip Qwen; escalate with
  # MiniMax-owned edits (O-ESCREOPENCODE) instead of burning 300s×N.
  local skip_worker=0
  if [ "$(task_class "$T")" = "infer" ] && [ "$(task_oracle "$T")" = "absent" ]; then
    skip_worker=1
    log "$T: O-INFERABSENT — skip worker (infer+Oracle:absent wedge signature)"
    {
      echo "O-INFERABSENT — worker skipped (infer + Oracle:absent)"
      echo "escalate with MiniMax-owned file edits; do not re-dispatch opencode"
    } > "/tmp/oc-${T}.err"
    WORKER_LAST_RC=143
    printf '%s\n' "$T" > "/tmp/escalation-no-opencode-${T}"
  fi
  if [ "$skip_worker" -eq 0 ] && [ "${WORKER_FIRST}" = "true" ] && run_worker_task "$T"; then
    # O-SFIXSCOPE: worker may commit then leave task RED — reset and escalate
    if refuse_red_task_commit "$T" "$T"; then
      scope_enforce "$T"
      post_commit_verify "$T" "$T"
      log_task END "$T" "committed via $(worker_label) — $(git log --oneline -1 | cut -c1-80)"
      record_rule_outcomes "$T" "worker_green"
      clear_worker_wedge_skip
      debt_frozen && return 1
      return 0
    fi
    log "$T: O-SFIXSCOPE reset worker RED commit — continuing to escalation path"
    record_rule_outcomes "$T" "worker_reset"
  fi
  # O-T6e: second mechan pass after worker (gitkeep / late writes / ESCW2 dirt)
  ensure_trackable_packages
  if try_mechan_commit "$T"; then
    log_task END "$T" "mechanical commit after worker (O-T6e) — $(git log --oneline -1 | cut -c1-80)"
    record_rule_outcomes "$T" "mechan"
    scope_enforce "$T"
    post_commit_verify "$T" "$T"
    debt_frozen && return 1
    return 0
  fi
  # O-ESCW: worker verified, nothing to change — close without MiniMax
  if try_worker_verified_noop "$T"; then
    scope_enforce "$T"
    post_commit_verify "$T" "$T"
    log_task END "$T" "already satisfied (O-ESCW) — $(git log --oneline -1 | cut -c1-80)"
    record_rule_outcomes "$T" "escw"
    debt_frozen && return 1
    return 0
  fi
  # O-ESCALCAUSE: classify why MiniMax is taking over (rescue vs redo).
  local esc_cause="worker-failed"
  if [ -f "/tmp/oc-${T}.err" ] && grep -qiE '429|rate.?limit|quota|Too Many Requests' "/tmp/oc-${T}.err" 2>/dev/null; then
    esc_cause="quota"
  elif tail -n 80 "$LOG" 2>/dev/null | grep -qE "${T}: O-T6d|unexpected-paths"; then
    esc_cause="guard-refused"
  elif [ -f "/tmp/oc-${T}.err" ] && grep -qiE 'unexpected-paths|staged paths mismatch|O-T6d' "/tmp/oc-${T}.err" 2>/dev/null; then
    esc_cause="guard-refused"
  fi
  # F-20 P3: cause file carries guard id + reason when known (self-contained).
  local esc_detail=""
  esc_detail=$(tail -n 80 "$LOG" 2>/dev/null | grep -E "${T}: O-T6d" | tail -1 | sed 's/^.*O-T6d /O-T6d /' || true)
  {
    echo "$esc_cause"
    [ -n "$esc_detail" ] && echo "$esc_detail"
    echo "worker_rc=${WORKER_LAST_RC:-unset}"
  } > "/tmp/escalation-cause-${T}.txt"
  event "$T" 0 escalation_cause "$esc_cause"
  log "$T: O-ESCALCAUSE ${esc_cause}${esc_detail:+ — ${esc_detail}} (rc=${WORKER_LAST_RC:-unset}) → /tmp/escalation-cause-${T}.txt"
  log_task START "$T" "Actor: $(orch_label) escalation — ${esc_cause}"
  # K2: same Analysis evidence the worker packet carries (bounded) — MiniMax
  # must see MTA remediation text, not bare Findings ids.
  local esc_packet=""
  if [ -f .hermes/harness/task-packet.py ]; then
    esc_packet=$(python3 .hermes/harness/task-packet.py "$TASKS_FILE" "$T" "$WORKER_MODEL" 2>/dev/null || true)
  fi
  local esc_evidence=""
  if [ -n "$esc_packet" ]; then
    esc_evidence=$(printf '%s\n' "$esc_packet" | sed -n '/^Analysis evidence/,/^Target Design:/p' | sed '$d')
  fi
  # O-ESCALORACLE: surface Shape/Oracle from the worker packet on the
  # escalation prompt so MiniMax cannot invent deletion targets (F-23).
  local esc_shape esc_oracle
  esc_shape=$(printf '%s\n' "$esc_packet" | sed -n 's/^Shape:[[:space:]]*//p' | head -1)
  esc_oracle=$(printf '%s\n' "$esc_packet" | sed -n 's/^Oracle:[[:space:]]*//p' | head -1)
  # O-ESCREOPENCODE: after wedge/thrash/INFERABSENT, MiniMax owns edits — do not
  # re-dispatch the same wedged OpenCode class (S03 T-007/T-012).
  local esc_routing
  if [ -f "/tmp/escalation-no-opencode-${T}" ] \
    || { [ -f "/tmp/oc-${T}.err" ] && grep -qiE 'O-INFERABSENT|JSON_STALE|READ_THRASH|TRUNCATION|O-WORKERREAD|O-WORKERWEDGE' "/tmp/oc-${T}.err" 2>/dev/null; } \
    || { [ -f /tmp/worker-wedge-skip ] && grep -qxF "$(echo "${STORY_SPEC_PREFIX:-run}" | awk '{print $1}')" /tmp/worker-wedge-skip 2>/dev/null; }; then
    esc_routing="MODEL ROUTING (O-ESCREOPENCODE): You are MiniMax on ESCALATION after a wedged/skipped worker. YOU OWN all file-changing work with your own tools. Do NOT dispatch opencode (-m ${WORKER_MODEL}) — re-invoking the wedged worker class burns another seat."
  else
    esc_routing="MODEL ROUTING (V7): You are MiniMax orchestrator on ESCALATION. Prefer dispatching opencode (-m ${WORKER_MODEL}) for all file-changing work. Do NOT apply mechanical rewrite/harvest edits with your own tools unless the worker already failed — Qwen has unlimited tokens; MiniMax is rate-limited."
  fi
  if run_stage "$T" "$T" \
"Use the migration-harness skill and read EXECUTION.md in its directory. Execute M4 for task ${T} from ${TASKS_FILE} ONLY.
${esc_routing}
O-ESCWSCOPE: edit ONLY this task's Owns/Target paths from ${TASKS_FILE}. Do NOT create or mutate later-story classes (${LATER_CLASSES:-none}) or unrelated services.
O-ESCALORACLE: Shape=${esc_shape:-unknown} Oracle=${esc_oracle:-unknown}. If Oracle=absent or Shape=remove: prove named targets are ABSENT — never create a file solely to delete it; never invent unlisted deletion targets.
Worker discipline (V6 P2.1/P2.2): if you do launch opencode, run it in the FOREGROUND with a terminal timeout ≥1800s; WAIT for exit; NEVER background it; NEVER use python3 <<heredoc, python3 -c multi-line, or scratch OpenRewrite — bundled scripts only.
${esc_evidence:+$esc_evidence
}Worker packet (authoritative goal + constraints):
${esc_packet:-'(task-packet unavailable — read ${TASKS_FILE} for ${T})'}
${RUN_CONTRACT}
Finish with ONE commit whose message STARTS with '${T}:'. Stop after ${T}." \
"Use the migration-harness skill and read EXECUTION.md in its directory. Continue M4 for task ${T} from ${TASKS_FILE} ONLY. Inspect git status first. If a previous worker left complete work and sensors are GREEN, commit ONE commit starting '${T}:' WITHOUT launching opencode. ${esc_routing} Foreground only; bundled scripts only — no heredocs / python3 -c.
${esc_evidence:+$esc_evidence
}${RUN_CONTRACT}"; then
    # O-T1FINDESC: scrub before amend so the attributed tip stays clean.
    scrub_findings_from_tip
    scrub_frozen_specs_from_tip
    # O-DRV7DET: stamp subject so commit-grep detectors also fire (log remains primary).
    if git log -1 --format=%s | grep -qE "^${T}:" \
      && ! git log -1 --format=%s | grep -qiE 'via MiniMax escalation'; then
      git commit --amend -m "$(git log -1 --format=%s) [via MiniMax escalation]" \
        --no-verify >>"$LOG" 2>&1 || true
    fi
    log_task END "$T" "committed via MiniMax escalation — $(git log --oneline -1 | cut -c1-80)"
    record_rule_outcomes "$T" "escalation"
    clear_worker_wedge_skip
    # K12: refute MiniMax escalation tip before accepting it.
    if ! refute_high_stakes HEAD "$T-k12"; then
      log "$T: K12 refused escalation commit — resetting tip + debt freeze"
      git reset --hard HEAD~1 >>"$LOG" 2>&1 || true
      record_debt "$T" k12 "escalation commit REFUTED (see migration/refute-log.md)"
      touch /tmp/debt-freeze
      touch /tmp/supervisor-pause
      debt_frozen && return 1
      return 1
    fi
  else
    log_task SKIP "$T" "exhausted — recorded in debt; O-DEBTFRZ freeze (not moving on)"
    log "$T: exhausted — recorded; freezing (O-DEBTFRZ)"
    record_rule_outcomes "$T" "exhausted"
    touch /tmp/debt-freeze
    touch /tmp/supervisor-pause
  fi
  debt_frozen && return 1
  return 0
}

BATCH_MAX="${BATCH_MAX:-3}"
flush_batch() { # $1=space-separated rewrite task ids
  # V7: do NOT send rewrite batches to MiniMax "apply directly" — that burned
  # the rate-limited orchestrator on mechanical harvest/POM work. Each rewrite
  # goes worker-first (OpenCode/Qwen), same as infer.
  local ids="${1# }"; [ -n "$ids" ] || return 0
  local n T desc
  n=$(echo $ids | wc -w | tr -d ' ')
  desc=""
  for T in $ids; do
    desc="${desc}${desc:+; }${T}: $(task_title "$T")"
  done
  log "batch: worker-first rewrite path ($n tasks, no MiniMax apply-directly): $ids"
  log_task BATCH "$ids" "Actor: $(worker_label) each — $desc"
  for T in $ids; do
    debt_frozen && { log "batch: O-DEBTFRZ — aborting remaining rewrite batch"; return 1; }
    committed "$T" && { log_task SKIP "$T" "already committed"; continue; }
    run_task "$T" || true
  done
  debt_frozen && return 1
  [ "$n" -ge 2 ] && post_commit_verify "$(echo $ids | awk '{print $NF}') batch" "batch-verify"
  debt_frozen && return 1
  return 0
}

# Publish the full task list into the demo narrative before M4 work.
{
  outer_log "         M4 task list ($(echo $TASK_IDS | wc -w | tr -d ' ') tasks) from ${TASKS_FILE}:"
  for T in $TASK_IDS; do
    outer_log "         • ${T} — $(task_title "$T") [class=$(task_class "$T")]"
  done
} 2>/dev/null || true

ensure_discovered

# O-FGRETRO: after mid-run probe harden (/tmp/probe-reeval-needed), re-check
# ALREADY COMPLETE / Already satisfied skips — reopen tasks the new probe refuses.
if [ -f /tmp/probe-reeval-needed ] && [ -f .hermes/harness/fgretro-reeval.py ]; then
  FGRETO_ROOT="$PWD" python3 .hermes/harness/fgretro-reeval.py \
    "$TASKS_FILE" "$RUN_BASE" > /tmp/fgretro-reopen.txt 2>/tmp/fgretro-reeval.err || true
  if [ -s /tmp/fgretro-reopen.txt ]; then
    log "O-FGRETRO: re-opening $(tr '\n' ' ' </tmp/fgretro-reopen.txt | head -c 200)"
    outer_log "         O-FGRETRO: re-dispatch $(tr '\n' ' ' </tmp/fgretro-reopen.txt)"
  else
    rm -f /tmp/fgretro-reopen.txt
    log "O-FGRETRO: probe re-eval — no false skips to reopen"
  fi
  rm -f /tmp/probe-reeval-needed
fi

BATCH=""
for T in $TASK_IDS; do
  if debt_frozen; then
    log "O-DEBTFRZ: stopping M4 task loop — unresolved debt RED (no silent advance)"
    echo "debt-freeze" > /tmp/supervisor-done
    exit 78
  fi
  if committed "$T"; then
    log "$T: already committed"
    log_task SKIP "$T" "already committed — skipping"
    continue
  fi
  if [ "$(task_class "$T")" = "rewrite" ]; then
    BATCH="$BATCH $T"
    [ "$(echo $BATCH | wc -w | tr -d ' ')" -ge "$BATCH_MAX" ] && { flush_batch "$BATCH"; BATCH=""; }
    continue
  fi
  flush_batch "$BATCH"; BATCH=""
  run_task "$T" || true
done
flush_batch "$BATCH"; BATCH=""
if debt_frozen; then
  log "O-DEBTFRZ: M4 ended under debt freeze — not entering M5"
  echo "debt-freeze" > /tmp/supervisor-done
  exit 78
fi

# ---------------------------------------------------------------- M5 evaluate
if ! committed "M5 evaluate"; then
  # Harness owns BOTH ends of the analysis (S01 lesson: sessions lack the
  # Java 21 export and wedge on kantra) — the after-analysis is a script
  # step; the session interprets the delta, it never runs analysis tools.
  A_TARGETS=$(grep -A12 "^analysis:" migration.yaml 2>/dev/null | grep -m1 "targets:" | sed 's/.*\[\(.*\)\].*/\1/; s/,/ /g')
  [ -n "$A_TARGETS" ] || A_TARGETS="quarkus jakarta-ee9 cloud-readiness"
  K_ARGS=""; for t in $A_TARGETS; do K_ARGS="$K_ARGS --target $t"; done
  [ -d .hermes/rules ] && K_ARGS="$K_ARGS --rules /projects/modernized/.hermes/rules"
  # O-DELTASTAGING: staging is legacy-by-design; .hermes is harness — exclude
  # both from the after-scan so phantom residuals do not inflate the delta.
  AFTER_SRC=/tmp/kantra-after-src
  rm -rf "$AFTER_SRC"
  mkdir -p "$AFTER_SRC"
  if command -v rsync >/dev/null 2>&1; then
    rsync -a --delete \
      --exclude 'migration/staging/' --exclude '.hermes/' --exclude 'target/' \
      --exclude '.git/' \
      /projects/modernized/ "$AFTER_SRC/" >> "$LOG" 2>&1 \
      || cp -a /projects/modernized/. "$AFTER_SRC/" 2>/dev/null || true
  else
    cp -a /projects/modernized/. "$AFTER_SRC/" 2>/dev/null || true
    rm -rf "$AFTER_SRC/migration/staging" "$AFTER_SRC/.hermes" "$AFTER_SRC/target" \
      "$AFTER_SRC/.git" 2>/dev/null || true
  fi
  (cd /tmp && JAVA_HOME="${JAVA_HOME_21:-$JAVA_HOME}" PATH="${JAVA_HOME_21:-$JAVA_HOME}/bin:$PATH" \
    /tmp/kantra/kantra analyze -i "$AFTER_SRC" -o /tmp/kantra-after \
    $K_ARGS --mode source-only --json-output --overwrite) >> "$LOG" 2>&1 \
    && cp /tmp/kantra-after/output.json migration/mta-findings-after.json 2>/dev/null \
    && log "M5 evaluate: after-analysis complete (script step; O-DELTASTAGING excluded staging/.hermes)" \
    || log "WARN: after-analysis failed — M5 evaluate proceeds without the delta"
  # O-DELTABASE: mechanical absence-vs-conversion split (do not credit empty trees).
  if [ -f migration/mta-findings-after.json ] && [ -f .hermes/harness/findings-delta.py ]; then
    FINDINGS_DELTA_ROOT="$PWD" python3 .hermes/harness/findings-delta.py \
      > migration/findings-delta.txt 2>/tmp/findings-delta.err \
      || log "WARN: findings-delta.py failed — see /tmp/findings-delta.err"
    cp migration/findings-delta.txt /tmp/findings-delta.txt 2>/dev/null || true
    log "M5 evaluate: O-DELTABASE summary — $(grep -m1 '^SUMMARY' migration/findings-delta.txt 2>/dev/null || echo n/a)"
  fi
  run_stage "M5 evaluate" "m5-evaluate" \
"Use the migration-harness skill and read SHIPPING.md in its directory. All tasks are executed (see migration/run-log.md and migration/debt.md). Execute M5 evaluate per SHIPPING.md. The harness ALREADY RAN the after-analysis: migration/mta-findings-after.json AND migration/findings-delta.txt (O-DELTABASE). Use findings-delta.txt as the authoritative delta — ABSENT-NOT-LANDED and SCAFFOLD-PRESATISFIED must NOT be counted as resolved; only the RESOLVED section is story credit. Also cite METRIC src_main_java / residual_incidents. Optionally use extract_findings.py for remaining rule detail. Append the findings delta to the run-log with every remaining finding individually explained (resolved here / absent-not-landed / owned by a later story / genuine debt). Run .hermes/harness/sensors.sh preflight and record the result honestly — do NOT claim factory/preflight green unless that command exits 0 (L-M5e; mvn verify alone is not enough).
${RUN_CONTRACT}
Commit prefix: 'M5 evaluate:'. DO NOT PUSH." \
"Use the migration-harness skill and read SHIPPING.md in its directory. Continue M5 evaluate; verify migration/mta-findings-after.json and migration/findings-delta.txt exist, run .hermes/harness/sensors.sh preflight, state GREEN or RED honestly in the commit message (L-M5e), then commit starting 'M5 evaluate:'. ${RUN_CONTRACT}" \
    || log "M5 evaluate: exhausted — shipping without final re-analysis commit"
  # L-M5e: mechanical honesty check — evaluate commit must not be treated as
  # ship-ready when preflight is RED (V8 S02 overstated evaluate).
  if committed "M5 evaluate"; then
    if .hermes/harness/sensors.sh preflight > /tmp/m5-evaluate-preflight.txt 2>&1; then
      log "M5 evaluate: preflight GREEN (L-M5e bar)"
    else
      log "M5 evaluate: preflight RED after evaluate commit (L-M5e) — not ship-ready; ship loop will correct — $(grep -E 'SENSOR RED|COVERAGE' /tmp/m5-evaluate-preflight.txt | head -3 | tr '\n' ' ')"
    fi
  fi
fi

fi # SHIP_ONLY else (M1–M5 evaluate)

# ---------------------------------------------------------------- M5 ship
NS=$(grep -rhoE '^\s*namespace:\s*\S+' k8s/*.y*ml 2>/dev/null | head -1 | awk '{print $2}')
[ -n "$NS" ] || NS="$(basename $(git remote get-url origin) .git)-dev"
SONAR_URL="${SONAR_URL:-http://sonarqube.sonarqube.svc:9000}"
SONAR_KEY="$(basename $(git remote get-url origin) .git)"

# Workspace oc is not logged in by default — authenticate with the pod's
# service account (harness-pipeline-observer RBAC grants the reads).
SA=/var/run/secrets/kubernetes.io/serviceaccount
OC() { oc --server=https://kubernetes.default.svc --token="$(cat $SA/token)" --certificate-authority=$SA/ca.crt "$@"; }

newest_pipelinerun() { OC get pipelinerun -n "$NS" --sort-by=.metadata.creationTimestamp -o jsonpath='{.items[-1:].metadata.name}' 2>/dev/null; }
pipeline_status()   { OC get pipelinerun "$1" -n "$NS" -o jsonpath='{.status.conditions[0].status} {.status.conditions[0].reason}' 2>/dev/null; }

wait_pipeline() { # $1=previous newest run; $2=1 if git push was up-to-date
  # O-SHIPNOPR / O-NOPUSHPR: when push is Truly "Everything up-to-date"
  # (SHIP_ONLY re-earn), fall back to the newest existing run. When push
  # advanced remote commits, a NEW PipelineRun is required — do NOT judge a
  # stale prior Succeeded run (S06 empty-delta false ship on …-push-7k7vn).
  # Decision core: nopushpr-decide.py (instrumented).
  local prev="$1" push_uptodate="${2:-0}" name="" i decision
  local max_new=12
  [ "$push_uptodate" = "1" ] || max_new=36  # ~6m for webhook/PR to appear
  for i in $(seq 1 "$max_new"); do
    name=$(newest_pipelinerun)
    [ -n "$name" ] && [ "$name" != "$prev" ] && break
    sleep 10
  done
  decision=$(python3 .hermes/harness/nopushpr-decide.py \
    "$push_uptodate" "${prev:-}" "${name:-}" 2>/dev/null || true)
  if [ "$decision" = "no-trigger" ]; then
    log "M5 ship: O-NOPUSHPR — commits pushed but no new PipelineRun within $((max_new * 10))s — refusing stale ${prev:-none}"
    echo "none no-trigger"
    return
  fi
  if [ "$decision" = "judge-existing" ]; then
    name=$(newest_pipelinerun)
    [ -n "$name" ] || name="$prev"
    if [ -z "$name" ]; then
      echo "none no-trigger"
      return
    fi
    log "M5 ship: no new PipelineRun (up-to-date push) — judging existing $name (O-SHIPNOPR)"
  fi
  for i in $(seq 1 120); do
    local st; st=$(pipeline_status "$name")
    case "$st" in
      True*)  echo "$name succeeded"; return;;
      False*) echo "$name failed"; return;;
    esac
    sleep 30
  done
  echo "$name timeout"
}

gate_violations() { # writes /tmp/gate-violations.txt; echoes count
  # Single evidence source (audit consolidation): violations + duplication
  # + coverage (the gate can fail on coverage alone — cart run #2).
  python3 .hermes/harness/sonar-report.py "$SONAR_URL" "$SONAR_KEY" \
    --out /tmp/gate-violations.txt --coverage 2>/dev/null || echo 0
}

log "M5 ship: shipping (namespace=$NS, sonar key=$SONAR_KEY)"
BUILD_R=0; GATE_R=0; DEPLOY_R=0; PREF_R=0
MAX_PER_CLASS=2
LAST_PUSHED=""
# O-PREFLIGHTDIM: fresh ship session gets a clean full-preflight budget.
rm -f /tmp/preflight-count
# Cart run #2: a gate round "exhausted" while the fix (96.7% coverage)
# sat committed as a checkpoint — and the old loop broke straight to
# factory-failed. An exhausted round only ends the run when it produced
# NOTHING new to ship; any new commit re-enters the loop, where the
# pre-push preflight gates it and the factory arbitrates.
round_exhausted() { # $1=class; 0 = continue the ship loop, 1 = stop
  if [ "$(git rev-parse HEAD)" != "$LAST_PUSHED" ]; then
    log "M5 ship: ${1}-fix round exhausted but new commits exist — re-entering the ship loop"
    return 0
  fi
  log "M5 ship: ${1}-fix round exhausted with nothing new to ship"
  return 1
}
while :; do
  # V5 run-4: `sensors.sh preflight` scans the WORKING tree. A prior
  # preflight-fix session can leave UNTRACKED fabrications (S04/S05 classes it
  # created chasing the coverage gate but never committed) — and those
  # uncommitted, untested files POLLUTE the coverage scan, dropping it below
  # the gate and triggering yet more fabrication (a self-defeating loop that
  # the post-commit stray-sweep/scope_enforce never catch because nothing was
  # committed). All legitimate work is committed by ship time, so archive any
  # untracked src/ strays before the scan: preflight must judge the committed
  # tree, not the pollution.
  STRAYS=$(git ls-files --others --exclude-standard -- src/ | head)
  if [ -n "$STRAYS" ]; then
    log "M5 ship: archiving untracked src/ strays before preflight (fabrication-pollution guard): $(echo $STRAYS | tr '\n' ' ')"
    mkdir -p /tmp/strays/preflight
    git ls-files --others --exclude-standard -- src/ | while read -r f; do
      mkdir -p "/tmp/strays/preflight/$(dirname "$f")"
      mv "$f" "/tmp/strays/preflight/$f" 2>/dev/null || rm -f "$f"
    done
  fi
  # Pre-push preflight (cart run #2): the factory failed maven-build on a
  # defect (unpinned compiler plugin) the local full check catches — never
  # burn a pipeline round on a locally-detectable failure. Bounded like
  # every fix class; when the budget is spent, push and let the factory
  # arbitrate.
  if ! .hermes/harness/sensors.sh preflight > /tmp/preflight-failure.txt 2>&1; then
    PREF_R=$((PREF_R+1))
    # O-GATEACHIEVE / N14 / D2 durable: coverage-gap decision-class REDs page
    # the operator — do not burn MiniMax ship-fix seats on unachievable bars.
    if [ -f .hermes/harness/gate-achievability.py ]; then
      _ga_rc=0
      python3 .hermes/harness/gate-achievability.py /tmp/preflight-failure.txt \
        > /tmp/gate-achievability.out 2>&1 || _ga_rc=$?
      if [ "$_ga_rc" = "10" ]; then
        event "m5-ship" 0 ship_blocked gate_decision_needed
        record_debt "M5 ship" coverage \
          "O-GATEACHIEVE decision-needed — see /tmp/gate-decision-needed.txt"
        log "M5 ship: BLOCKED — N14 decision-needed RED (coverage policy). Not burning fix seats."
        outer_log "         M5 ship: BLOCKED — coverage gap needs operator decision (N14/D2)"
        write_run_report "ship-blocked-coverage-decision"
        echo "ship-blocked-coverage-decision" > /tmp/supervisor-done
        exit 3
      fi
    fi
    if [ "$PREF_R" -le "$MAX_PER_CLASS" ]; then
      log "M5 ship: pre-push preflight RED (round $PREF_R) — fixing before push"
      outer_log "         M5 ship: preflight RED — fix round ${PREF_R}/${MAX_PER_CLASS} starting"
      event "m5-ship" 0 "preflight_red" "round=$PREF_R"
      run_stage "Preflight fix r${PREF_R}" "preflightfix-r${PREF_R}" \
"Use the migration-harness skill and read SHIPPING.md in its directory. The pre-push preflight is RED - the failure evidence is in /tmp/preflight-failure.txt, read it with your file tools. Fix the root cause (build wiring against the WORKING scaffold pom conventions; coverage gaps need real tests for the uncovered classes - never weaken assertions). Finish with .hermes/harness/sensors.sh preflight GREEN, then commit ONE commit. DO NOT PUSH.
${RUN_CONTRACT}
Commit prefix: 'Preflight fix r${PREF_R}:'." \
"Use the migration-harness skill and read SHIPPING.md in its directory. Continue preflight-correction round ${PREF_R}; inspect git status and /tmp/preflight-failure.txt, finish the root-cause fix, run .hermes/harness/sensors.sh preflight until GREEN, and commit ONE commit starting 'Preflight fix r${PREF_R}:'. DO NOT PUSH.
${RUN_CONTRACT}" \
        || log "M5 ship: preflight-fix round $PREF_R did not converge"
      continue
    fi
    # V5 finding #4: build/coverage/boot preflight failures may push — the
    # factory re-checks them. But fidelity drift and a legacy-package
    # inversion are NOT arbitrated by the factory (legacy-package code
    # compiles and passes sonar), so "push anyway" would ship the defect.
    # Block the ship on those two dimensions and stop the run with a durable
    # record (the outer loop treats a non-success marker as a failed story).
    if ! .hermes/harness/sensors.sh fidelity > /tmp/ship-fidelity.txt 2>&1; then
      event "m5-ship" 0 ship_blocked fidelity_red
      record_debt "M5 ship" fidelity "harvest fidelity RED at ship — factory cannot arbitrate (see /tmp/ship-fidelity.txt)"
      log "M5 ship: BLOCKED — harvest fidelity RED cannot be arbitrated by the factory. Story NOT shipped."
      write_run_report "ship-blocked-fidelity"; echo "ship-blocked-fidelity" > /tmp/supervisor-done; exit 3
    fi
    if ! .hermes/harness/sensors.sh package > /tmp/ship-package.txt 2>&1; then
      event "m5-ship" 0 ship_blocked package_red
      record_debt "M5 ship" package "legacy package under src/main at ship — factory cannot arbitrate (see /tmp/ship-package.txt)"
      log "M5 ship: BLOCKED — legacy-package inversion cannot be arbitrated by the factory. Story NOT shipped."
      write_run_report "ship-blocked-package"; echo "ship-blocked-package" > /tmp/supervisor-done; exit 3
    fi
    log "M5 ship: preflight budget exhausted — pushing anyway (factory as arbiter)"
  fi
  # K12: adversarial refute of tip before push (escalation+ship high-stakes).
  if ! refute_high_stakes HEAD "m5-ship-k12"; then
    event "m5-ship" 0 ship_blocked k12_refuted
    record_debt "M5 ship" k12 "pre-push REFUTED (see migration/refute-log.md)"
    log "M5 ship: BLOCKED — K12 refute refused the tip. Story NOT shipped."
    write_run_report "ship-blocked-k12"; echo "ship-blocked-k12" > /tmp/supervisor-done; exit 3
  fi
  PREV=$(newest_pipelinerun)
  PUSH_OUT=$(git push origin main 2>&1) || { log "FATAL: git push failed"; echo "$PUSH_OUT" >> "$LOG"; write_run_report "push-failed"; echo push-failed > /tmp/supervisor-done; exit 1; }
  echo "$PUSH_OUT" >> "$LOG"
  LAST_PUSHED=$(git rev-parse HEAD)
  PUSH_UPTODATE=0
  if echo "$PUSH_OUT" | grep -qiE 'up-to-date|Everything up-to-date|already up to date'; then
    PUSH_UPTODATE=1
  fi
  log "M5 ship: pushed $(git rev-parse --short HEAD), waiting for pipeline (uptodate=$PUSH_UPTODATE)"
  # O-UXLOG-SHIP (Poll 77 U2): climax visible on the demo outer-loop log.
  outer_log "         M5 ship: pushed $(git rev-parse --short HEAD) — waiting for factory pipeline"
  RESULT=$(wait_pipeline "$PREV" "$PUSH_UPTODATE"); PR_NAME=${RESULT% *}; PR_ST=${RESULT#* }
  # O-SHIPNOPR: up-to-date push with no new PR → acceptance-only recheck.
  # O-NOPUSHPR: commits were pushed but no new PR → do NOT pretend success.
  if [ -z "$PR_NAME" ] || [ "$PR_NAME" = "none" ] || [ "$PR_ST" = "no-trigger" ]; then
    if [ "$PUSH_UPTODATE" = "1" ]; then
      log "M5 ship: no PipelineRun to judge (up-to-date push) — acceptance-only recheck (O-SHIPNOPR)"
      PR_ST=succeeded
      PR_NAME="${PREV:-none}"
    else
      log "M5 ship: O-NOPUSHPR — pushed new commits but no PipelineRun triggered — ship FAIL (stale pipeline not judged)"
      PR_ST=failed
      PR_NAME="${PREV:-none}"
    fi
  fi
  event "m5-ship" 0 "pipeline_$PR_ST" "$PR_NAME"
  log "M5 ship: pipeline $PR_NAME -> $PR_ST"
  outer_log "         M5 ship: pipeline ${PR_NAME} → ${PR_ST}"
  if [ "$PR_ST" = "succeeded" ]; then
    # Non-deploy story (M5 hybrid shipping): the factory quality gate IS
    # the story's finish line — no acceptance surface expected yet.
    if [ "$STORY_DEPLOY" != "true" ]; then
      event "m5-ship" 0 "story_gate_pass" "non-deploy story"
      clear_debt
      write_run_report "story gate passed (non-deploy story): pipeline + quality gate green"
      phase_f_retro
      git push origin main >> "$LOG" 2>&1 || true
      echo "story-gate-passed" > /tmp/supervisor-done
      log "SUPERVISOR COMPLETE: story gate passed (non-deploy story)"
      if [ "${SHIP_ONLY:-}" = "1" ]; then
        outer_log "OK END    SHIP_ONLY — story-gate-passed; outer-loop still idle"
      fi
      exit 0
    fi
    # E2: success = demo acceptance, not HTTP liveness — index page serves
    # AND acceptance.path returns a non-empty **collection array** (V6 R2/R4 /
    # O-ACCEPTGEN). Bare JSON objects must not count as 1 item (run-4 false green).
    ACC_COLLECTION=$(python3 -c "
import sys
sys.path.insert(0, '.hermes/harness')
from acceptance_config import load
print(load('migration.yaml').get('collection') or 'products')
" 2>/dev/null || echo products)
    ROUTE=$(OC get route -n "$NS" -o jsonpath='{.items[0].spec.host}' 2>/dev/null)
    # Prefer rollout readiness over a fixed sleep (V6 P4.2).
    DEP=$(OC get deploy -n "$NS" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
    if [ -n "$DEP" ]; then
      OC rollout status "deploy/$DEP" -n "$NS" --timeout=180s >> "$LOG" 2>&1 || true
      outer_log "         M5 ship: rollout ready (deploy/${DEP})"
    else
      sleep 10
    fi
    # Acceptance path: comment-tolerant parse (same class as plan-lint V6 R7).
    ACC_PATH=$(python3 -c "
import re,sys
try: my=open('migration.yaml').read()
except FileNotFoundError: sys.exit(0)
m=re.search(r'^acceptance:\s*\n(?:[ \t]*#.*\n|[ \t]*\n)*[ \t]*path:\s*(\S+)', my, re.M)
print(m.group(1) if m else '')
" 2>/dev/null)
    ACC_PATH="${ACC_PATH:-/api/products}"
    # R1: stamp on first ship attempt; later rewrites of acceptance.path are forbidden.
    if [ -z "${ACC_PATH_STAMP:-}" ]; then
      ACC_PATH_STAMP="$ACC_PATH"
      export ACC_PATH_STAMP
    fi
    CODE=$(curl -sk -o /dev/null -w "%{http_code}" "https://${ROUTE}/" 2>/dev/null || echo 000)
    # O-ACCEPTROOT: preserved servlet context-path via quarkus.http.root-path
    # serves META-INF/resources/index.html under that prefix, not at /. Prefer
    # / when it is already 200; otherwise accept ${root-path}/ as the index.
    if [ "$CODE" != "200" ]; then
      ROOT_PATH=$(python3 -c "
import re, sys
try:
    t = open('src/main/resources/application.properties').read()
except FileNotFoundError:
    sys.exit(0)
m = re.search(r'(?m)^quarkus\\.http\\.root-path=(/\\S*)', t)
print((m.group(1).rstrip('/') if m else ''), end='')
" 2>/dev/null || true)
      if [ -n "${ROOT_PATH:-}" ]; then
        CODE_ROOT=$(curl -sk -o /dev/null -w "%{http_code}" "https://${ROUTE}${ROOT_PATH}/" 2>/dev/null || echo 000)
        log "M5 ship: O-ACCEPTROOT index fallback ${ROOT_PATH}/ -> ${CODE_ROOT} (bare / was ${CODE})"
        if [ "$CODE_ROOT" = "200" ]; then
          CODE="$CODE_ROOT"
          ACC_INDEX_URL="${ROOT_PATH}/"
        fi
      fi
    fi
    ACC_INDEX_URL="${ACC_INDEX_URL:-/}"
    ACC=$(curl -sk -o /tmp/acceptance-body.json -w "%{http_code}" "https://${ROUTE}${ACC_PATH}" 2>/dev/null || echo 000)
    PRODUCTS=$(python3 .hermes/harness/acceptance-products.py < /tmp/acceptance-body.json 2>/dev/null || echo 0)
    # O-ACCEPTPROBE: log the URL that actually scored index 200 (may be
    # ${root-path}/ via O-ACCEPTROOT — external / can still be 404).
    log "M5 ship: route ${ACC_INDEX_URL} -> ${CODE}; ${ACC_PATH} -> HTTP ${ACC} (${PRODUCTS} ${ACC_COLLECTION})"
    outer_log "         M5 ship: acceptance probe: ${ACC_INDEX_URL} → ${CODE}, ${ACC_PATH} → ${ACC}, ${ACC_COLLECTION}=${PRODUCTS}"
    if [ "$ACC_PATH" != "$ACC_PATH_STAMP" ]; then
      log "M5 ship: ACCEPTANCE PATH CHANGED ('$ACC_PATH_STAMP' -> '$ACC_PATH') — V6 R1 forbidden goalpost move"
      {
        echo "Acceptance failure: migration.yaml acceptance.path was rewritten during ship/correction."
        echo "Stamped path: $ACC_PATH_STAMP"
        echo "Current path: $ACC_PATH"
        echo "Restore acceptance.path to the stamped value. Do not edit migration.yaml to match a weaker endpoint."
        echo "See SHIPPING.md acceptance-correction (V6 R1)."
      } > /tmp/deploy-failure.txt
      FAILED_TASK="acceptance-deploy"
    elif [ "$CODE" = "200" ] && [ "$ACC" = "200" ] && [ "${PRODUCTS:-0}" -gt 0 ]; then
      event "m5-ship" 0 "acceptance_pass" "route=${CODE},${ACC_COLLECTION}=${PRODUCTS}"
      clear_debt
      write_run_report "success: shipped, route 200, ${PRODUCTS} ${ACC_COLLECTION}"
      phase_f_retro
      git push origin main >> "$LOG" 2>&1 || true
      echo "success route=${ROUTE} http=${CODE} ${ACC_COLLECTION}=${PRODUCTS}" > /tmp/supervisor-done
      log "SUPERVISOR COMPLETE: migration shipped and accepted"
      if [ "${SHIP_ONLY:-}" = "1" ]; then
        outer_log "OK END    SHIP_ONLY — success http=${CODE} ${ACC_COLLECTION}=${PRODUCTS}; outer-loop still idle"
      fi
      exit 0
    else
      log "M5 ship: pipeline green but ACCEPTANCE failed (/ ${CODE}, ${ACC_COLLECTION} ${PRODUCTS}) — deploy-correction round"
      {
        echo "Acceptance failure: pipeline green but the demo acceptance is unmet."
        echo "Route / returned HTTP ${CODE} (need 200 — an index page must exist)."
        echo "${ACC_PATH} returned HTTP ${ACC} with ${PRODUCTS} ${ACC_COLLECTION} (need 200 and a non-empty JSON array, or {\"${ACC_COLLECTION}\":[...]} — not a bare status object)."
        echo "Mandatory correction checklist (V6/O-ACCEPTGEN): keep acceptance.path unchanged; collection-backed body per migration.yaml acceptance.collection; k8s endpoint env; narrow ExceptionMapper away from Exception; no fail-open catch→200."
        echo "See SHIPPING.md acceptance-correction for the contract and decided fixes."
      } > /tmp/deploy-failure.txt
      FAILED_TASK="acceptance-deploy"
    fi
  else
    FAILED_TASK=$(OC get taskrun -n "$NS" -l tekton.dev/pipelineRun="$PR_NAME"       -o jsonpath='{range .items[?(@.status.conditions[0].status=="False")]}{.metadata.name}{"\n"}{end}' 2>/dev/null | head -1)
    log "M5 ship: failed pipeline task: ${FAILED_TASK:-unknown}"
  fi
  if [[ "$FAILED_TASK" == *maven-build* || "$FAILED_TASK" == *build-and-push* ]]; then
    CLASS=build; BUILD_R=$((BUILD_R+1)); ROUND=$BUILD_R
    [ $BUILD_R -gt $MAX_PER_CLASS ] && { log "M5 ship: build round budget exhausted"; break; }
    {
      echo "Build-stage failure for pipeline $PR_NAME (task: $FAILED_TASK)."
      echo "--- maven/build errors ---"
      OC logs -n "$NS" -l tekton.dev/taskRun="$FAILED_TASK" --tail=80 2>/dev/null | grep -iE "ERROR|BUILD|Caused|Could not" | head -30
    } > /tmp/build-failure.txt
    run_stage "Build fix r${ROUND}" "buildfix-r${ROUND}" \
"Use the migration-harness skill and read SHIPPING.md in its directory. Execute the M5 ship BUILD-correction procedure for round ${ROUND}: the failure evidence is in /tmp/build-failure.txt - read it with your file tools and follow SHIPPING.md for this correction class. Finish with .hermes/harness/sensors.sh preflight GREEN before committing.
${RUN_CONTRACT}
Commit prefix: 'Build fix r${ROUND}:'." \
"Use the migration-harness skill and read SHIPPING.md in its directory. Continue M5 ship build-correction round ${ROUND}; inspect git status and /tmp/build-failure.txt, finish the root-cause fix, run .hermes/harness/sensors.sh preflight, and commit ONE commit starting 'Build fix r${ROUND}:'. DO NOT PUSH.
${RUN_CONTRACT}" \
      || { round_exhausted build || break; continue; }
  elif [[ "$FAILED_TASK" == *deploy* ]]; then
    CLASS=deploy; DEPLOY_R=$((DEPLOY_R+1)); ROUND=$DEPLOY_R
    [ $DEPLOY_R -gt $MAX_PER_CLASS ] && { log "M5 ship: deploy round budget exhausted"; break; }
    if [ "$FAILED_TASK" != "acceptance-deploy" ]; then
      APP=$(OC get pods -n "$NS" -o jsonpath='{range .items[*]}{.metadata.name} {.status.phase} {.status.containerStatuses[0].state.waiting.reason}{"\n"}{end}' 2>/dev/null \
        | grep -E "CrashLoopBackOff|Error" | head -1 | awk '{print $1}')
      {
        echo "Deploy-stage failure for pipeline $PR_NAME."
        echo "Failed task: $FAILED_TASK"
        echo "Crash-looping pod: ${APP:-none found}"
        echo "--- last 60 log lines of the failing pod ---"
        [ -n "$APP" ] && OC logs -n "$NS" "$APP" --tail=60 2>/dev/null
      } > /tmp/deploy-failure.txt
    fi
    run_stage "Deploy fix r${ROUND}" "deployfix-r${ROUND}" \
"Use the migration-harness skill and read SHIPPING.md in its directory. Execute the M5 ship DEPLOY-correction procedure for round ${ROUND}: the failure evidence is in /tmp/deploy-failure.txt - read it with your file tools and follow SHIPPING.md for this correction class. Finish with .hermes/harness/sensors.sh preflight GREEN before committing.
${RUN_CONTRACT}
Commit prefix: 'Deploy fix r${ROUND}:'." \
"Use the migration-harness skill and read SHIPPING.md in its directory. Continue M5 ship deploy-correction round ${ROUND}; inspect git status and /tmp/deploy-failure.txt, finish the root-cause fix, run .hermes/harness/sensors.sh preflight, and commit ONE commit starting 'Deploy fix r${ROUND}:'. DO NOT PUSH.
${RUN_CONTRACT}" \
      || { round_exhausted deploy || break; continue; }
  else
    CLASS=gate; GATE_R=$((GATE_R+1)); ROUND=$GATE_R
    [ $GATE_R -gt $MAX_PER_CLASS ] && { log "M5 ship: gate round budget exhausted"; break; }
    N=$(gate_violations)
    log "M5 ship: gate round $ROUND — $N new violations exported to /tmp/gate-violations.txt"
    run_stage "Gate fix r${ROUND}" "gatefix-r${ROUND}" \
"Use the migration-harness skill and read SHIPPING.md in its directory. Execute the M5 ship GATE-correction procedure for round ${ROUND}: the failure evidence is in /tmp/gate-violations.txt - read it with your file tools and follow SHIPPING.md for this correction class. Finish with .hermes/harness/sensors.sh milestone GREEN before committing (it runs the factory's own sonar gate locally - iterate until it passes).
${RUN_CONTRACT}
Commit prefix: 'Gate fix r${ROUND}:'." \
"Use the migration-harness skill and read SHIPPING.md in its directory. Continue M5 ship gate-correction round ${ROUND}; inspect git status, finish the remaining violations from /tmp/gate-violations.txt, run .hermes/harness/sensors.sh milestone until GREEN, and commit ONE commit starting 'Gate fix r${ROUND}:'. DO NOT PUSH.
${RUN_CONTRACT}" \
      || { round_exhausted gate || break; continue; }
  fi
done
write_run_report "factory not passed (build=${BUILD_R} gate=${GATE_R} deploy=${DEPLOY_R} rounds)"
phase_f_retro
git push origin main >> "$LOG" 2>&1 || true
echo "factory-failed build=${BUILD_R} gate=${GATE_R} deploy=${DEPLOY_R}" > /tmp/supervisor-done
log "SUPERVISOR COMPLETE: factory not passed — evidence preserved for the retro"
if [ "${SHIP_ONLY:-}" = "1" ]; then
  outer_log "X FAIL   SHIP_ONLY — factory not passed (build=${BUILD_R} gate=${GATE_R} deploy=${DEPLOY_R}); see ${LOG}"
fi
exit 1
