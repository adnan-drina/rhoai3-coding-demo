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
if pgrep -f "harness/superviso[r]" | grep -v "^$$\$" | grep -qv "^$PPID\$"; then
  OTHER=$(pgrep -f "harness/superviso[r]" | grep -v "^$$\$" | grep -v "^$PPID\$" | head -1)
  if [ -n "$OTHER" ] && [ "$OTHER" != "$$" ]; then
    echo "FATAL: another supervisor is already running (pid $OTHER) — refusing to start" >&2
    exit 1
  fi
fi

ORCH_PROVIDER="${ORCH_PROVIDER:-custom:maas-m2}"
ORCH_MODEL="${ORCH_MODEL:-minimax-m2}"
WORKER_MODEL="${WORKER_MODEL:-qwen27b/qwen3-6-27b}"
# V7: MiniMax is rate-limited; Qwen has unlimited tokens. Mechanical M4
# coding (rewrite + infer) goes to OpenCode/Qwen first. MiniMax/Hermes is
# for orchestration + escalation only (M1–M3, sensor-fix, M5 evaluate).
WORKER_FIRST="${WORKER_FIRST:-true}"
SESSION_TIMEOUT="${SESSION_TIMEOUT:-2700}"
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
if [ "${SHIP_ONLY:-}" = "1" ]; then
  outer_log "> START  SHIP_ONLY — acceptance re-earn (not outer-loop; details ${LOG})"
  outer_log "         Models: $(orch_label) · $(worker_label) | mode=SHIP_ONLY (skip M1–M4 / evaluate)"
else
  outer_log "         Models: $(orch_label) · $(worker_label) | M4 coding → worker first (MiniMax escalation only)"
fi
# C1: per-run isolated Maven repo — factory-parity resolution for every sensor
.hermes/harness/sensors.sh seed >> "$LOG" 2>&1 || log "WARN: isolated repo seed failed — sensors fall back to red-on-use"
event() { echo "$(date -u +%s),$1,$2,$3,$4" >> "$EVENTS"; }

# Process contract only — ALL judgment guidance (packet rules, sensors,
# gate bars, dispatch discipline) lives in the migration-harness skill
# and AGENTS.md. The supervisor injects nothing but run configuration
# and the commit/ship contract.
RUN_CONTRACT="Run contract: the worker model for this run is WORKER_MODEL_PLACEHOLDER. DO NOT PUSH anywhere - the supervisor ships. Finish with ONE commit using the exact message prefix stated below."
RUN_CONTRACT="${RUN_CONTRACT//WORKER_MODEL_PLACEHOLDER/$WORKER_MODEL}"

committed() { git log --oneline "${RUN_BASE}..HEAD" | grep -q " $1:"; }

# O-T6b / O-T6c / O-STY: never sweep harness or staging fidelity trees into T-NNN commits.
stage_for_task_commit() {
  git add -A
  git reset -q -- .hermes migration/staging 2>/dev/null || true
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
  while [ -f /tmp/supervisor-pause ]; do
    log "PAUSED (rm /tmp/supervisor-pause to continue)"; sleep 30
  done
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
    local lviol=""
    for f in $(git diff --name-only --diff-filter=A HEAD~1..HEAD -- src/main/java/ 2>/dev/null); do
      case " ${LATER_CLASSES} " in *" $(basename "$f" .java) "*) lviol="$lviol $f";; esac
    done
    if [ -n "$lviol" ]; then
      event "scope" 0 later_story_class "${lviol# }"
      log "scope sensor: reverted src/main class(es) a LATER story owns:${lviol}"
      # S-LC: demo-visible — later-story fabrication must not hide in supervisor.log only
      outer_log "         SCOPE REVERT (S-LC): removed later-story class(es) created early:${lviol} — keep them in migration/staging until their story"
      {
        echo "The story-scope sensor reverted src/main class(es) owned by a LATER story:${lviol}"
        echo "These REDESIGN classes are converted in a later story — do NOT create them now."
        echo "Prefer migration/staging until the owning story; characterization tests use Mockito / test-local fakes — never the real src/main class."
      } > /tmp/scope-violation.txt
      git rm -q $lviol 2>/dev/null
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
  local viol=""
  for f in $(git diff --name-only --diff-filter=M HEAD~1..HEAD -- src/main/java/ 2>/dev/null); do
    case " ${pathscope} " in *" $f "*) ;; *) viol="$viol $f";; esac
  done
  [ -n "$viol" ] || { rm -f /tmp/scope-violation.txt; return 0; }
  event "scope" 0 scope_violation "${viol# }"
  log "scope sensor: out-of-scope src/main edits reverted:${viol}"
  {
    echo "The story-scope sensor reverted out-of-scope src/main modifications:${viol}"
    echo "This story's src/main scope: ${STORY_SCOPE}"
    echo "Rule: finish the task WITHIN scope; if it genuinely requires an out-of-scope edit, record that need in migration/debt.md instead of making the edit."
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
  if ! .hermes/harness/sensors.sh "$SENSOR_KIND" >> "$LOG" 2>&1; then
    event "$tag" 0 sensor_red_post_commit verify
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
        git diff --cached --quiet || \
          git commit -q -m "${prefix} sensor fix: deterministic style-autofix (OpenRewrite cleanup recipes)" 2>/dev/null
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
          git commit -q -m "${prefix} sensor fix: partial deterministic style-autofix (remaining violations to sfix)" 2>/dev/null
          event "$tag" 0 style_autofix partial
          log "$tag: style-autofix fixed some violations (committed, compiles); remaining go to a sfix session"
        fi
      fi
    fi
    log "$tag: committed but the ${SENSOR_KIND} sensor is RED — dispatching sensor-fix session"
    # Cheap-loop guidance (V4 finding #1: ~5100s of full `mvn clean verify`
    # inside fix sessions). Point the model at the dimension-specific cheap
    # recheck so it stops re-running the whole build per fix.
    # O-SFIXLOOP: hard-refuse milestone inside the session via /tmp/sensor-fix-mode
    # (prompt-only was ignored — V9 S03 T-008 ran milestone 5×).
    touch /tmp/sensor-fix-mode
    orch "${tag}-sfix" \
"Use the migration-harness skill and read EXECUTION.md in its directory. The stage '${prefix}' was just committed but the supervisor's post-commit '${SENSOR_KIND}' sensor is RED — read /tmp/sensor-task.log, /tmp/sensor-milestone.log and /tmp/sensor-sonar.log for the exact errors (sonar violations are listed inline when the gate is red). If /tmp/scope-violation.txt exists, the story-scope sensor reverted out-of-scope edits — read it and repair WITHIN the story scope only. Diagnose and fix the ROOT CAUSE (typical: files harvested prematurely without their extension/dependency). PACKAGE DIRECTION IS ONE-WAY: this migration RENAMES the legacy package to the target package (migration.yaml legacyPackage -> targetPackage). The target package is ALWAYS correct; a file under the legacy package in src/main is the defect. If a class is in the wrong place, move it INTO the target package and rewrite its 'package'/imports to the target — NEVER move or revert a class into the legacy package, and NEVER rewrite target-package files back to the legacy package to 'match' staged source (migration/staging holds legacy-package source by design; fidelity already accounts for the rename). A 'harvest fidelity RED' is about drifted CONTENT, not the package. add a dependency ONLY if this stage's findings require it. CHEAP FIX LOOP (O-SFIXLOOP — ENFORCED): fix ALL listed violations in ONE pass, then verify ONCE with the dimension-specific check — sonar violations: .hermes/harness/sensors.sh sonar; fidelity drift: .hermes/harness/sensors.sh fidelity; a legacy package under src/main: .hermes/harness/sensors.sh package; compile/test failure: .hermes/harness/sensors.sh task. DO NOT run .hermes/harness/sensors.sh milestone — it is REFUSED during this session (exits 2). Commit ONE commit starting '${prefix} sensor fix:' the moment your dimension check is green; do not polish further. O-SONARTIME: NEVER wrap .hermes/harness/sensors.sh in timeout <600s (sonar needs 2–3m; timeout 60 → exit 124). O-SFIXSCOPE: NEVER commit while the dimension check is still RED claiming failures are 'pre-existing' or 'out of scope' — fix them or stop without commit (V9 S04 T-003). For RestAssured RED: fix JSON paths under the collection property, empty-path 400 myths, and test isolation (EXECUTION O-RESTJSON/O-RESTEMPTY/O-TESTISO).
${RUN_CONTRACT}"
    rm -f /tmp/sensor-fix-mode
    # #6: re-verify the TRIGGERING sensor (${SENSOR_KIND}), not `task` — a
    # milestone-red (fidelity/sonar) is not cleared by a task-sensor green,
    # and a commit with the right prefix is not proof the red went away.
    if committed "${prefix} sensor fix"; then
      if .hermes/harness/sensors.sh "$SENSOR_KIND" >> "$LOG" 2>&1; then
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
          log "$tag: O-SFIXSCOPE — archiving RED sensor-fix $_red → $_arch then resetting"
          git reset --hard HEAD~1 >> "$LOG" 2>&1 || true
        fi
        record_debt "$tag" "$SENSOR_KIND" "sensor-fix committed but ${SENSOR_KIND} still RED (commit reset)"
      fi
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
      record_debt "$tag" "$SENSOR_KIND" "sensor-fix did not clear ${SENSOR_KIND}"
    fi
  fi
  debt_frozen && return 1
  return 0
}

# O-SFIXSCOPE: a T-NNN / stage commit that leaves task sensor RED must not stand.
# Reset HEAD and return 1 so the caller does not treat it as success.
# O-REDARCH: archive the red tip to /tmp/strays/<tag>/ before hard-reset so
# escalation RCA still has the worker/MiniMax output.
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
    committed "$prefix" && return 0
    local p="$prompt"; [ $attempt -gt 1 ] && p="$rprompt"
    orch "${tag}-a${attempt}p${pf}" "$p"; local rc=$?
    if committed "$prefix"; then
      event "$tag" "$attempt" success commit; log "$tag: committed $(git log --oneline -1)"
      # O-SFIXSCOPE: refuse red T-NNN commits (do not proceed to post_commit_verify as success)
      if ! refuse_red_task_commit "$prefix" "$tag"; then
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
      STRAYS=$(git ls-files --others --exclude-standard -- src/ | head -5)
      if [ -n "$STRAYS" ]; then
        log "$tag: archiving untracked strays left by the session to /tmp/strays/${tag}/: $(echo $STRAYS | tr '\n' ' ')"
        mkdir -p "/tmp/strays/${tag}"
        git ls-files --others --exclude-standard -- src/ | while read -r f; do
          mkdir -p "/tmp/strays/${tag}/$(dirname "$f")"
          mv "$f" "/tmp/strays/${tag}/$f" 2>/dev/null || rm -f "$f"
        done
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
    log "$tag: attempts exhausted — checkpointing partial work per debt policy"
    stage_for_task_commit
    git diff --cached --quiet || \
      git commit -m "checkpoint of ${prefix} (supervisor: attempts exhausted)" >/dev/null 2>&1 || true
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
  orch "retro" \
"Use the migration-harness skill. The migration run/story is CLOSED — this is Retro. Evidence to read with your file tools: migration/run-report.md, migration/retro-events.csv, migration/retro-metrics.csv, migration/run-log.md, migration/debt.md, remaining briefs under migration/briefs/ (if any), and the skill files PLANNING.md, EXECUTION.md, SHIPPING.md, MAPPINGS.md. Write migration/retro-proposals.md with EXACTLY these markdown sections (both required):

## Brief updates (auto-applicable)
Concrete edits for REMAINING story briefs only (not the story just finished). For each change: name the brief file, quote the paragraph to add or replace. Empty list is fine if nothing should change.

## Skill / harness proposals (human-only)
(1) the three costliest failure patterns of THIS run, citing evidence; (2) for each pattern one CONCRETE proposed change to a specific skill or sensor — quote exact text and name file/section; (3) ARTIFACT review of this run's commits (harvest fidelity, story-scope, fabrication); (4) harness waste. PROPOSE ONLY.

Do NOT modify any skill, harness script, or brief in this session — proposals file only. Finish with ONE commit whose message STARTS with 'Retro:'.
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
LINT_OUT=$(python3 .hermes/harness/plan-lint.py "$TASKS_FILE" migration/mta-findings.json $SCOPE_ARGS 2>&1)
if [ $? -ne 0 ] && ! committed "M3 revision"; then
  log "plan lint: revision required"; echo "$LINT_OUT" | head -20 >> "$LOG"
  printf '%s\n' "$LINT_OUT" > /tmp/plan-lint.txt
  run_stage "M3 revision" "m3-lint" \
"Use the migration-harness skill and read PLANNING.md and MAPPINGS.md in its directory. The plan lint REJECTED specs/*/tasks.md — the findings are in /tmp/plan-lint.txt (read it with your file tools). Revise the plan to fix every lint finding: infer tasks must carry the decided target design (file mappings, signatures, annotations — cite MAPPINGS.md shapes). Do not renumber or remove completed work.
${RUN_CONTRACT}
Commit prefix: 'M3 revision:'." \
"Use the migration-harness skill and read PLANNING.md in its directory. Finish revising the plan per /tmp/plan-lint.txt and commit with prefix 'M3 revision:'.
${RUN_CONTRACT}" \
    || log "plan lint: revision round exhausted — proceeding with the plan as-is (recorded)"
  LINT2=$(python3 .hermes/harness/plan-lint.py "$TASKS_FILE" migration/mta-findings.json $SCOPE_ARGS 2>&1) \
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
TASK_CLASSES=$(python3 - "$TASKS_FILE" <<'PYEOF'
import re, sys
text = open(sys.argv[1], encoding="utf-8").read()
blocks = re.split(r"^#{2,6} +(T[-A-Za-z0-9]*\d+):", text, flags=re.M)
for i in range(1, len(blocks) - 1, 2):
    m = re.search(r"class[:*\s]+([a-z]+)", blocks[i + 1][:400], re.I)
    print(f"{blocks[i]}:{m.group(1).lower() if m else 'infer'}")
PYEOF
)
task_class() { echo "$TASK_CLASSES" | grep -m1 "^$1:" | cut -d: -f2; }

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
    absent)
      git commit --allow-empty -q -m "${T}: ALREADY COMPLETE — ${detail} already absent (V6 P2.4)" 2>/dev/null \
        || git commit --allow-empty -m "${T}: ALREADY COMPLETE — ${detail} already absent (V6 P2.4)" >/dev/null 2>&1
      event "$T" 0 already_complete "absent:$detail"
      log "$T: ALREADY COMPLETE — ${detail} absent; skipped opencode"
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
  timeout 1800 opencode run "$packet" \
    -m "$WORKER_MODEL" --auto --format json \
    -f "$TASKS_FILE" -f AGENTS.md \
    > "/tmp/oc-${T}.json" 2>"/tmp/oc-${T}.err"
  rc=$?
  wait_for_worker
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
    committed "$T" && { log "$T: mechanical verify-and-commit (dirty+GREEN; O-T6)"; return 0; }
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
  if debt_frozen; then
    log "$T: O-DEBTFRZ — skip (debt freeze active)"
    return 1
  fi
  if try_already_complete "$T"; then
    log_task SKIP "$T" "already complete (fast path); skipped worker"
    scope_enforce "$T"
    post_commit_verify "$T" "$T"
    debt_frozen && return 1
    return 0
  fi
  # O-PKGDIR before mechan: empty dirs → .gitkeep so mkdir work can commit
  ensure_trackable_packages
  # O-T6: untracked/dirty target tree already green — don't burn a model seat
  if try_mechan_commit "$T"; then
    log_task END "$T" "mechanical commit (O-T6) — $(git log --oneline -1 | cut -c1-80)"
    scope_enforce "$T"
    post_commit_verify "$T" "$T"
    debt_frozen && return 1
    return 0
  fi
  if [ "${WORKER_FIRST}" = "true" ] && run_worker_task "$T"; then
    # O-SFIXSCOPE: worker may commit then leave task RED — reset and escalate
    if refuse_red_task_commit "$T" "$T"; then
      scope_enforce "$T"
      post_commit_verify "$T" "$T"
      log_task END "$T" "committed via $(worker_label) — $(git log --oneline -1 | cut -c1-80)"
      debt_frozen && return 1
      return 0
    fi
    log "$T: O-SFIXSCOPE reset worker RED commit — continuing to escalation path"
  fi
  # O-T6e: second mechan pass after worker (gitkeep / late writes / ESCW2 dirt)
  ensure_trackable_packages
  if try_mechan_commit "$T"; then
    log_task END "$T" "mechanical commit after worker (O-T6e) — $(git log --oneline -1 | cut -c1-80)"
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
    debt_frozen && return 1
    return 0
  fi
  log_task START "$T" "Actor: $(orch_label) escalation — worker incomplete/failed"
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
  if run_stage "$T" "$T" \
"Use the migration-harness skill and read EXECUTION.md in its directory. Execute M4 for task ${T} from ${TASKS_FILE} ONLY.
MODEL ROUTING (V7): You are MiniMax orchestrator on ESCALATION. Prefer dispatching opencode (-m ${WORKER_MODEL}) for all file-changing work. Do NOT apply mechanical rewrite/harvest edits with your own tools unless the worker already failed — Qwen has unlimited tokens; MiniMax is rate-limited.
Worker discipline (V6 P2.1/P2.2): run opencode in the FOREGROUND with a terminal timeout ≥1800s; WAIT for exit; NEVER background it; NEVER use python3 <<heredoc, python3 -c multi-line, or scratch OpenRewrite — bundled scripts only.
${esc_evidence:+$esc_evidence
}Worker packet (authoritative goal + constraints):
${esc_packet:-'(task-packet unavailable — read ${TASKS_FILE} for ${T})'}
${RUN_CONTRACT}
Finish with ONE commit whose message STARTS with '${T}:'. Stop after ${T}." \
"Use the migration-harness skill and read EXECUTION.md in its directory. Continue M4 for task ${T} from ${TASKS_FILE} ONLY. Inspect git status first. If a previous worker left complete work and sensors are GREEN, commit ONE commit starting '${T}:' WITHOUT launching opencode. Launch opencode only when the tree is incomplete or sensors are RED. Foreground worker only; bundled scripts only — no heredocs / python3 -c.
${esc_evidence:+$esc_evidence
}${RUN_CONTRACT}"; then
    # O-DRV7DET: stamp subject so commit-grep detectors also fire (log remains primary).
    if git log -1 --format=%s | grep -qE "^${T}:" \
      && ! git log -1 --format=%s | grep -qiE 'via MiniMax escalation'; then
      git commit --amend -m "$(git log -1 --format=%s) [via MiniMax escalation]" \
        --no-verify >>"$LOG" 2>&1 || true
    fi
    log_task END "$T" "committed via MiniMax escalation — $(git log --oneline -1 | cut -c1-80)"
  else
    log_task SKIP "$T" "exhausted — recorded in debt; O-DEBTFRZ freeze (not moving on)"
    log "$T: exhausted — recorded; freezing (O-DEBTFRZ)"
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
  (cd /tmp && JAVA_HOME="${JAVA_HOME_21:-$JAVA_HOME}" PATH="${JAVA_HOME_21:-$JAVA_HOME}/bin:$PATH" \
    /tmp/kantra/kantra analyze -i /projects/modernized -o /tmp/kantra-after \
    $K_ARGS --mode source-only --json-output --overwrite) >> "$LOG" 2>&1 \
    && cp /tmp/kantra-after/output.json migration/mta-findings-after.json 2>/dev/null \
    && log "M5 evaluate: after-analysis complete (script step)" \
    || log "WARN: after-analysis failed — M5 evaluate proceeds without the delta"
  run_stage "M5 evaluate" "m5-evaluate" \
"Use the migration-harness skill and read SHIPPING.md in its directory. All tasks are executed (see migration/run-log.md and migration/debt.md). Execute M5 evaluate per SHIPPING.md. The harness ALREADY RAN the after-analysis: migration/mta-findings-after.json (use .hermes/skills/migration-harness/scripts/extract_findings.py to summarize it — do NOT run analysis tools yourself). Append the findings delta to the run-log with every remaining finding individually explained (resolved here / owned by a later story / genuine debt). Run .hermes/harness/sensors.sh preflight and record the result honestly — do NOT claim factory/preflight green unless that command exits 0 (L-M5e; mvn verify alone is not enough).
${RUN_CONTRACT}
Commit prefix: 'M5 evaluate:'. DO NOT PUSH." \
"Use the migration-harness skill and read SHIPPING.md in its directory. Continue M5 evaluate; verify migration/mta-findings-after.json and the delta section exist, run .hermes/harness/sensors.sh preflight, state GREEN or RED honestly in the commit message (L-M5e), then commit starting 'M5 evaluate:'. ${RUN_CONTRACT}" \
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

wait_pipeline() { # $1=previous newest run; waits for a NEW run to reach a terminal state; echoes "name status"
  # O-SHIPNOPR: when git push is "Everything up-to-date" (SHIP_ONLY re-earn),
  # no new PipelineRun is created. Always fall back to the newest existing
  # run — never return an empty name (empty → false "gate" correction burn).
  local prev="$1" name="" i
  for i in $(seq 1 12); do
    name=$(newest_pipelinerun)
    [ -n "$name" ] && [ "$name" != "$prev" ] && break
    sleep 10
  done
  if [ -z "$name" ] || [ "$name" = "$prev" ]; then
    name=$(newest_pipelinerun)
    [ -n "$name" ] || name="$prev"
    if [ -z "$name" ]; then
      echo "none no-trigger"
      return
    fi
    log "M5 ship: no new PipelineRun (push may be up-to-date) — judging existing $name"
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
    if [ "$PREF_R" -le "$MAX_PER_CLASS" ]; then
      log "M5 ship: pre-push preflight RED (round $PREF_R) — fixing before push"
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
  PREV=$(newest_pipelinerun)
  PUSH_OUT=$(git push origin main 2>&1) || { log "FATAL: git push failed"; echo "$PUSH_OUT" >> "$LOG"; write_run_report "push-failed"; echo push-failed > /tmp/supervisor-done; exit 1; }
  echo "$PUSH_OUT" >> "$LOG"
  LAST_PUSHED=$(git rev-parse HEAD)
  log "M5 ship: pushed $(git rev-parse --short HEAD), waiting for pipeline"
  RESULT=$(wait_pipeline "$PREV"); PR_NAME=${RESULT% *}; PR_ST=${RESULT#* }
  # O-SHIPNOPR: empty / no-trigger must not fall into gate-fix (burns MiniMax).
  if [ -z "$PR_NAME" ] || [ "$PR_NAME" = "none" ] || [ "$PR_ST" = "no-trigger" ]; then
    log "M5 ship: no PipelineRun to judge (up-to-date push) — acceptance-only recheck (O-SHIPNOPR)"
    PR_ST=succeeded
    PR_NAME="${PREV:-none}"
  fi
  event "m5-ship" 0 "pipeline_$PR_ST" "$PR_NAME"
  log "M5 ship: pipeline $PR_NAME -> $PR_ST"
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
    # AND acceptance.path returns a non-empty **products array** (V6 R2/R4).
    # Bare JSON objects must not count as 1 item (run-4 false green).
    ROUTE=$(OC get route -n "$NS" -o jsonpath='{.items[0].spec.host}' 2>/dev/null)
    # Prefer rollout readiness over a fixed sleep (V6 P4.2).
    DEP=$(OC get deploy -n "$NS" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
    if [ -n "$DEP" ]; then
      OC rollout status "deploy/$DEP" -n "$NS" --timeout=180s >> "$LOG" 2>&1 || true
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
    ACC=$(curl -sk -o /tmp/acceptance-body.json -w "%{http_code}" "https://${ROUTE}${ACC_PATH}" 2>/dev/null || echo 000)
    PRODUCTS=$(python3 .hermes/harness/acceptance-products.py < /tmp/acceptance-body.json 2>/dev/null || echo 0)
    log "M5 ship: route / -> ${CODE}; ${ACC_PATH} -> HTTP ${ACC} (${PRODUCTS} catalog products)"
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
      event "m5-ship" 0 "acceptance_pass" "route=${CODE},products=${PRODUCTS}"
      clear_debt
      write_run_report "success: shipped, route 200, ${PRODUCTS} products"
      phase_f_retro
      git push origin main >> "$LOG" 2>&1 || true
      echo "success route=${ROUTE} http=${CODE} products=${PRODUCTS}" > /tmp/supervisor-done
      log "SUPERVISOR COMPLETE: migration shipped and accepted"
      if [ "${SHIP_ONLY:-}" = "1" ]; then
        outer_log "OK END    SHIP_ONLY — success http=${CODE} products=${PRODUCTS}; outer-loop still idle"
      fi
      exit 0
    else
      log "M5 ship: pipeline green but ACCEPTANCE failed (/ ${CODE}, products ${PRODUCTS}) — deploy-correction round"
      {
        echo "Acceptance failure: pipeline green but the demo acceptance is unmet."
        echo "Route / returned HTTP ${CODE} (need 200 — an index page must exist)."
        echo "${ACC_PATH} returned HTTP ${ACC} with ${PRODUCTS} catalog products (need 200 and a non-empty JSON array of products, or {\"products\":[...]} — not a bare status object)."
        echo "Mandatory correction checklist (V6): keep acceptance.path unchanged; catalog-backed body; k8s CATALOG_ENDPOINT env; narrow ExceptionMapper away from Exception; no fail-open catch→200."
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
