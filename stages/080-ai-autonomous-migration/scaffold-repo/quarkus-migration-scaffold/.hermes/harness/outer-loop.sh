#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Stage 080 OUTER LOOP — drives the full M-process end-to-end:
#   M1 ANALYZE (analyze.sh + architecture-profile session, rubric-gated)
#   M2 SEQUENCE (roadmap + briefs session, roadmap-lint-gated)
#   per story: M3 SPECIFY (spec session, plan-lint-gated)
#              M4/M5 (one supervisor.sh child run with computed story env)
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

# Same two-writer protection as the supervisor (O-SUPFLOCK / O-OUTERFLOCK).
# F-18: bare pgrep -f matches oc-exec -lc probe text — observer-induced
# refuse-to-start. Hold outer flock for process life; probe supervisor lock
# without keeping it (child supervisor.sh must be able to acquire).
OUTER_LOCK="${OUTER_LOCK:-/tmp/outer-loop.lock}"
exec 8>"$OUTER_LOCK"
if ! flock -n 8; then
  echo "FATAL: another outer loop holds $OUTER_LOCK — refusing to start" >&2
  exit 1
fi
printf '%s\n' "$$" >&8
SUPERVISOR_LOCK="${SUPERVISOR_LOCK:-/tmp/supervisor.lock}"
exec 9>"$SUPERVISOR_LOCK"
if ! flock -n 9; then
  echo "FATAL: a supervisor holds $SUPERVISOR_LOCK — refusing to start" >&2
  exit 1
fi
# Release supervisor lock so the M4 child can take it.
flock -u 9
exec 9>&-

ORCH_PROVIDER="${ORCH_PROVIDER:-custom:maas-m2}"
ORCH_MODEL="${ORCH_MODEL:-minimax-m2}"
WORKER_MODEL="${WORKER_MODEL:-qwen27b/qwen3-6-27b}"
SESSION_TIMEOUT="${SESSION_TIMEOUT:-2700}"
HEARTBEAT_SECS="${OUTER_LOOP_HEARTBEAT_SECS:-60}"
# O-M3WORKER: M3 SPECIFY drafts on Qwen (plan-lint is the cheap verifier);
# MiniMax is a capped backstop after worker attempts fail lint.
WORKER_M3_FIRST="${WORKER_M3_FIRST:-true}"
M3_WORKER_ATTEMPTS="${M3_WORKER_ATTEMPTS:-2}"
M3_ORCH_BACKSTOP="${M3_ORCH_BACKSTOP:-1}"
LOG=/tmp/outer-loop.log
STATE=migration/story-state.csv
HARNESS=.hermes/harness
SKILLDIR=.hermes/skills/migration-harness
# L-P1: OUTER_LOOP_PLAIN=1 for terminals that mangle unicode markers
PLAIN="${OUTER_LOOP_PLAIN:-0}"

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

log() { echo "[$(date -u +%F' '%T)] $*" >> "$LOG"; }
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
  local tag="$1" prompt="$2" title="${3:-$1}" t0 now rc hb_pid slog
  t0=$(date +%s)
  slog="/tmp/outer-${tag}.log"
  log "         Actor: $(orch_label) — session ${tag} → ${slog}"
  _outer_heartbeat_start "$title" "$t0" "$slog" orchestrator
  timeout "$SESSION_TIMEOUT" hermes chat --provider "$ORCH_PROVIDER" --model "$ORCH_MODEL" -q "$prompt" \
    < /dev/null > "$slog" 2>&1
  rc=$?
  kill "$hb_pid" 2>/dev/null || true
  wait "$hb_pid" 2>/dev/null || true
  now=$(date +%s)
  if grep -qE "429|Too Many Requests|Rate limit|rate.?limit" "$slog" 2>/dev/null; then
    log "         ${title}: MiniMax rate limit seen in session log (hermes_rc=${rc}) — supervisor backs off 15m on orch 429s"
  fi
  log "·        ${title} session finished ($((now - t0))s, hermes_rc=${rc}) — checking gate next (session≠gate)"
  return $rc
}

# O-M3WORKER: OpenCode/Qwen seat for M3 SPECIFY (plan-lint gated).
wchat() { # $1=tag $2=prompt [$3=phase title] [$4=extra -f file ...]
  local tag="$1" prompt="$2" title="${3:-$1}" t0 now rc hb_pid slog
  shift 3 || true
  t0=$(date +%s)
  slog="/tmp/outer-${tag}.log"
  log "         Actor: $(worker_label) — session ${tag} → ${slog}"
  _outer_heartbeat_start "$title" "$t0" "$slog" worker
  # shellcheck disable=SC2086
  timeout "$SESSION_TIMEOUT" opencode run "$prompt" \
    -m "$WORKER_MODEL" --auto --format json \
    -f AGENTS.md \
    -f "${SKILLDIR}/PLANNING.md" \
    "$@" \
    < /dev/null > "$slog" 2>&1
  rc=$?
  kill "$hb_pid" 2>/dev/null || true
  wait "$hb_pid" 2>/dev/null || true
  now=$(date +%s)
  log "·        ${title} session finished ($((now - t0))s, worker_rc=${rc}) — checking gate next (session≠gate)"
  return $rc
}

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
roadmap_green() {
  [ -f migration/roadmap.md ] && python3 "$HARNESS/roadmap-lint.py" migration/roadmap.md migration/findings-inventory.md /projects/legacy > /tmp/roadmap-lint.txt 2>&1
}
if roadmap_green; then
  phase_ok "M2 SEQUENCE — roadmap already present and lint-green"
else
  for ATTEMPT in 1 2; do
    phase_start "M2 SEQUENCE — cut migration into dependency-ordered stories [attempt ${ATTEMPT}/2]"
    P="Use the migration-harness skill and read SEQUENCING.md and BRIEF-TEMPLATE.md in its directory. M1 is committed. Execute M2 ONLY: read migration/architecture-profile.md, migration/dependency-order.md, migration/findings-inventory.md and migration.yaml, then write migration/roadmap.md plus one brief per story under migration/briefs/ exactly per SEQUENCING.md. Each brief carries its classes' roles and, for REDESIGN classes, their target contract from architecture-profile section 7 (SEQUENCING.md 'One quality model'). Every 'In scope' code quote is the REAL legacy code — quote it from /projects/legacy, never invent methods or annotations the class does not have (the lint cross-checks each quoted method/annotation against the legacy source). A deterministic lint gates the result — verify yourself with: python3 ${HARNESS}/roadmap-lint.py migration/roadmap.md migration/findings-inventory.md /projects/legacy (must exit 0) BEFORE committing. Finish with ONE commit whose message STARTS with 'M2 sequence:'. DO NOT PUSH. PACKAGE RENAME: full prefix legacyPackage→targetPackage (com.redhat.coolstore.X → com.demo.X); never invent com.demo.coolstore."
    [ "$ATTEMPT" = "2" ] && P="Use the migration-harness skill and read SEQUENCING.md in its directory. A previous M2 attempt failed its lint — the findings are in /tmp/roadmap-lint.txt (read it with your file tools). LINT:fabrication findings mean the brief quoted a method/annotation that is NOT in the legacy source — read the real class under /projects/legacy and quote what is actually there. Fix every lint finding in migration/roadmap.md and the briefs, verify python3 ${HARNESS}/roadmap-lint.py migration/roadmap.md migration/findings-inventory.md /projects/legacy exits 0, and commit with prefix 'M2 sequence:'. DO NOT PUSH."
    mchat "m2-sequence-a${ATTEMPT}" "$P" "M2 SEQUENCE"
    if roadmap_green; then
      [ -n "$(git status --porcelain migration/)" ] && git add migration/ && git commit -q -m "M2 sequence: outer-loop mechanical commit of lint-green roadmap" 2>/dev/null
      phase_gate "M2 SEQUENCE roadmap-lint" GREEN "commit $(git rev-parse --short HEAD)"
      # Name concrete briefs for the demo log.
      log "         • migration/roadmap.md ($(grep -cE '^## S[0-9]' migration/roadmap.md 2>/dev/null || echo 0) stories)"
      for b in migration/briefs/S*.md; do
        [ -f "$b" ] && log "         • $(basename "$b" .md) brief generated"
      done
      phase_ok "M2 SEQUENCE — roadmap + briefs lint-green; commit $(git rev-parse --short HEAD)"
      break
    fi
    phase_gate "M2 SEQUENCE roadmap-lint" RED "full findings /tmp/roadmap-lint.txt"
    [ "$ATTEMPT" = "2" ] && fail_run "M2 SEQUENCE failed its lint twice"
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
phase_start "Story loop — ${STORY_COUNT} stories (${STORY_IDS})"

STORY_IDX=0
while IFS='|' read -r SID DEPLOY FINDINGS SCOPE; do
  [ -n "$SID" ] || continue
  STORY_IDX=$((STORY_IDX + 1))
  SLUG_HINT=$(ls migration/briefs/${SID}-*.md 2>/dev/null | head -1 | xargs -n1 basename 2>/dev/null | sed 's/\.md$//' || echo "$SID")
  story_done "$SID" && { phase_ok "${SID} (${SLUG_HINT}) — already complete; skipping"; continue; }

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
  M3_LINT_CMD="python3 ${HARNESS}/plan-lint.py specs/${SLUG}/tasks.md migration/mta-findings.json --findings-scope ${FINDINGS} --profile migration/architecture-profile.md --story-deploy ${DEPLOY}"
  if [ -n "$SPEC_TASKS" ] \
    && python3 "$HARNESS/plan-lint.py" "$SPEC_TASKS" migration/mta-findings.json \
         --findings-scope "$FINDINGS" --profile migration/architecture-profile.md \
         --story-deploy "$DEPLOY" \
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
      P="Use the migration-harness skill and read PLANNING.md in its directory. Execute M3 ONLY for story ${SID}: read the brief ${BRIEF} (it is authoritative — the decided shapes and contracts are IN it), migration/architecture-profile.md for context, and the legacy code it cites under /projects/legacy. Write specs/${SLUG}/spec.md, plan.md and tasks.md per PLANNING.md, scoped STRICTLY to this story. A deterministic lint gates the plan — verify yourself with: ${M3_LINT_CMD} (must exit 0) BEFORE committing. Finish with ONE commit whose message STARTS with '${SID} spec:'. DO NOT PUSH. PACKAGE RENAME: full prefix legacyPackage→targetPackage only (never targetPackage.coolstore when targetPackage is com.demo). ACCEPTANCE (O-M3ACCEPT): story deploy=${DEPLOY}. If deploy=false, do NOT task migration.yaml acceptance.path with a Java @Path/endpoint — defer to the deploy story (S-AC1/G-OK); omitting the path from tasks is OK. If deploy=true, task the full literal acceptance.path with real @Path substance (no MinimalAcceptanceEndpoint / status-map placeholders)."
      if [ "$mode" = "fix" ]; then
        P="Use the migration-harness skill and read PLANNING.md in its directory. A previous M3 attempt for ${SID} left a plan that fails plan-lint — the findings are in /tmp/plan-lint.txt (read it with your file tools). Fix every finding in specs/${SLUG}/, verify ${M3_LINT_CMD} exits 0, and commit with prefix '${SID} spec:'. DO NOT PUSH. ACCEPTANCE (O-M3ACCEPT): deploy=${DEPLOY} — if false, do not schedule endpoint substance for acceptance.path; if true, task the full literal path with real @Path (no status-map / MinimalAcceptanceEndpoint)."
      fi
    }
    m3_lint_green() {
      SPEC_TASKS=$(ls specs/${SID}-*/tasks.md 2>/dev/null | head -1)
      [ -n "$SPEC_TASKS" ] || return 1
      python3 "$HARNESS/plan-lint.py" "$SPEC_TASKS" migration/mta-findings.json \
        --findings-scope "$FINDINGS" --profile migration/architecture-profile.md \
        --story-deploy "$DEPLOY" > /tmp/plan-lint.txt 2>&1
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
            --story-deploy "$DEPLOY" 2>&1 || true
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
        if [ "$ATTEMPT" -gt 1 ] || [ -n "$SPEC_TASKS" ]; then m3_build_prompt fix; else m3_build_prompt fresh; fi
        wchat "m3-${SID}-w${ATTEMPT}" "$P" "M3 SPECIFY ${SID} (worker)" \
          -f "$BRIEF" -f migration/architecture-profile.md
        mchat_rc=$?
        if [ "$mchat_rc" -eq 137 ] || [ "$mchat_rc" -eq 143 ]; then
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
        phase_start "M3 SPECIFY — plan story ${SLUG} (${STORY_IDX}/${STORY_COUNT}) [MiniMax backstop ${ATTEMPT}/${M3_ORCH_BACKSTOP}]"
        log "         O-M3WORKER: MiniMax backstop after Qwen plan-lint RED"
        SPEC_TASKS=$(ls specs/${SID}-*/tasks.md 2>/dev/null | head -1)
        m3_build_prompt fix
        mchat "m3-${SID}-orch${ATTEMPT}" "$P" "M3 SPECIFY ${SID} (orch backstop)"
        mchat_rc=$?
        if [ "$mchat_rc" -eq 137 ] || [ "$mchat_rc" -eq 143 ]; then
          log "         O-M3KILL: orch M3 killed (rc=${mchat_rc}) — backstop NOT spent"
          phase_retry "M3 SPECIFY ${SID} — orch session killed; not counting"
          continue
        fi
        if m3_lint_green; then
          [ -n "$(git status --porcelain specs/)" ] && git add specs/ && git commit -q -m "${SID} spec: outer-loop mechanical commit of lint-green spec" 2>/dev/null
          phase_gate "M3 SPECIFY ${SID} plan-lint" GREEN "commit $(git rev-parse --short HEAD)"
          phase_ok "M3 SPECIFY — ${SLUG} plan-lint-green after MiniMax backstop; commit $(git rev-parse --short HEAD)"
          M3_DONE=1
          break
        fi
        if grep -qE "429|Too Many Requests|Rate limit|rate.?limit" "/tmp/outer-m3-${SID}-orch${ATTEMPT}.log" 2>/dev/null; then
          log "         O-M3QUOTA: MiniMax backstop rate-limited — NOT spent; backoff 15m"
          phase_retry "M3 SPECIFY ${SID} — quota; sleeping 900s"
          sleep 900
          continue
        fi
        m3_write_lint_evidence
        phase_gate "M3 SPECIFY ${SID} plan-lint" RED "orch backstop — /tmp/plan-lint.txt"
        ATTEMPT=$((ATTEMPT + 1))
      done
    elif [ "$M3_DONE" != "1" ] && [ "${WORKER_M3_FIRST:-true}" != "true" ]; then
      # Legacy path: WORKER_M3_FIRST=false → two MiniMax attempts (pre-O-M3WORKER).
      ATTEMPT=1
      while [ "$ATTEMPT" -le 2 ]; do
        if m3_lint_green; then
          [ -n "$(git status --porcelain specs/)" ] && git add specs/ && git commit -q -m "${SID} spec: outer-loop mechanical commit of lint-green spec" 2>/dev/null
          phase_gate "M3 SPECIFY ${SID} plan-lint" GREEN "commit $(git rev-parse --short HEAD)"
          phase_ok "M3 SPECIFY — ${SLUG} plan-lint-green; commit $(git rev-parse --short HEAD)"
          M3_DONE=1
          break
        fi
        phase_start "M3 SPECIFY — plan story ${SLUG} (${STORY_IDX}/${STORY_COUNT}) [attempt ${ATTEMPT}/2]"
        SPEC_TASKS=$(ls specs/${SID}-*/tasks.md 2>/dev/null | head -1)
        if [ "$ATTEMPT" -gt 1 ] || [ -n "$SPEC_TASKS" ]; then m3_build_prompt fix; else m3_build_prompt fresh; fi
        mchat "m3-${SID}-a${ATTEMPT}" "$P" "M3 SPECIFY ${SID}"
        mchat_rc=$?
        if [ "$mchat_rc" -eq 137 ] || [ "$mchat_rc" -eq 143 ]; then
          phase_retry "M3 SPECIFY ${SID} — session killed (rc=${mchat_rc}); not counting as lint fail"
          continue
        fi
        if m3_lint_green; then
          [ -n "$(git status --porcelain specs/)" ] && git add specs/ && git commit -q -m "${SID} spec: outer-loop mechanical commit of lint-green spec" 2>/dev/null
          phase_gate "M3 SPECIFY ${SID} plan-lint" GREEN "commit $(git rev-parse --short HEAD)"
          phase_ok "M3 SPECIFY — ${SLUG} plan-lint-green; commit $(git rev-parse --short HEAD)"
          M3_DONE=1
          break
        fi
        if grep -qE "429|Too Many Requests|Rate limit|rate.?limit" "/tmp/outer-m3-${SID}-a${ATTEMPT}.log" 2>/dev/null; then
          phase_retry "M3 SPECIFY ${SID} — quota; sleeping 900s (not counting as lint fail)"
          sleep 900
          continue
        fi
        m3_write_lint_evidence
        phase_gate "M3 SPECIFY ${SID} plan-lint" RED "full findings /tmp/plan-lint.txt"
        [ "$ATTEMPT" = "2" ] && fail_run "M3 SPECIFY ${SID} failed its plan lint twice"
        phase_retry "M3 SPECIFY ${SID} — bouncing once"
        ATTEMPT=$((ATTEMPT + 1))
      done
    fi

    if [ "$M3_DONE" != "1" ]; then
      fail_run "M3 SPECIFY ${SID} failed plan-lint after Qwen attempts + MiniMax backstop"
    fi
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
  else
    # O-M4REPLAY: mid-story restart with RUN_BASE=HEAD re-dispatches already
    # committed T-NNN (empty RUN_BASE..HEAD → committed() always false).
    # If this story's spec exists and T-NNN commits already follow it, resume
    # from the spec's parent so those tasks stay "committed".
    SPEC_SHA=$(git log -1 --format=%H --grep="^${SID} spec:" 2>/dev/null || true)
    if [ -n "$SPEC_SHA" ] && [ -f "$SPEC_TASKS" ] \
      && git log --oneline "${SPEC_SHA}..HEAD" 2>/dev/null | grep -qE ' T-[0-9]+:'; then
      STORY_RUN_BASE=$(git rev-parse "${SPEC_SHA}^" 2>/dev/null || git rev-parse "$SPEC_SHA")
      # O-SPECREBASE: a mid-story `S0N spec:` recommit (e.g. DTO-first plan
      # fix) can sit *after* earlier T-NNN. SPEC^ then hides those commits from
      # committed() → false replay (Wave2 T-002 after T-007 sensor-fix restart).
      # Walk base back to the parent of any task commit that exists in history
      # but is missing from SPEC^..HEAD.
      # O-SPECREBASE: only rewrite tasks already progressed in SPEC..HEAD
      # (max T-NNN). Ignoring higher ids avoids walking into prior stories'
      # reused T-00N subjects (Wave2 false base → old T-007/T-008).
      _maxn=0
      while read -r _ht; do
        _hn=${_ht#T-}; _hn=$((10#${_hn}))
        [ "$_hn" -gt "$_maxn" ] && _maxn=$_hn
      done < <(git log --oneline "${SPEC_SHA}..HEAD" 2>/dev/null | grep -oE 'T-[0-9]+' | sort -u)
      _hidden=""
      while read -r _tid; do
        [ -n "$_tid" ] || continue
        _tn=${_tid#T-}; _tn=$((10#${_tn}))
        [ "$_tn" -le "$_maxn" ] || continue
        _tsha=$(git log -1 --format=%H "$SPEC_SHA" --grep="^${_tid}:" 2>/dev/null || true)
        [ -n "$_tsha" ] || continue
        if ! git log --oneline "${STORY_RUN_BASE}..HEAD" 2>/dev/null | grep -q " ${_tid}:"; then
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
      STORY_RUN_BASE="$(git rev-parse HEAD)"
    fi
  fi
  if [ "$HOTSWAP_TRIES" -eq 0 ]; then
    phase_start "M4/M5 EXECUTE — implement & ship ${SLUG_HINT} (${STORY_IDX}/${STORY_COUNT})" \
      "Models: $(orch_label) · $(worker_label) | deploy=${DEPLOY} findings=${FINDINGS} preserve=${PC} later-classes=$(echo $LATER_CLASSES | wc -w | tr -d ' ') | supervisor: /tmp/supervisor.log | run_base=$(git rev-parse --short "$STORY_RUN_BASE")"
    log "         Note: M4 rewrite+infer coding → $(worker_label) first; MiniMax only for orch/escalation (WORKER_FIRST) — supervisor.log records actor"
  else
    log "         O-HOTSWAP: re-entering M4/M5 for ${SID} (attempt $((HOTSWAP_TRIES+1)); run_base=$(git rev-parse --short "$STORY_RUN_BASE"))"
  fi
  env RUN_BASE="$STORY_RUN_BASE" \
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
      echo "${SID},debt-freeze,$(date -u +%s)" >> "$STATE"
      git add "$STATE" && git commit -q -m "${SID} story HOLD: debt-freeze (O-DEBTFRZ)" 2>/dev/null || true
      fail_run "$SID debt-freeze (O-DEBTFRZ) — fix debt, durableize, re-run; do not advance"
      ;;
    success*|story-gate-passed*)
      phase_ok "M4/M5 EXECUTE — ${SLUG_HINT} complete (${OUTCOME}); HEAD $(git rev-parse --short HEAD)"
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
      echo "${SID},failed,$(date -u +%s)" >> "$STATE"
      git add "$STATE" && git commit -q -m "${SID} story FAILED: ${OUTCOME}" 2>/dev/null || true
      git push origin main >> "$LOG" 2>&1 || true
      fail_run "$SID did not ship (${OUTCOME}) — run stopped before dependent stories"
      ;;
  esac
done <<< "$STORIES"

phase_ok "Outer loop — all stories shipped; HEAD $(git rev-parse --short HEAD)"
# Keep git remote chatter out of the demo narrative (L-SHIPLOG) — one summary line.
if git push origin main >> /tmp/outer-git-push.log 2>&1; then
  log "         git push: origin/main @ $(git rev-parse --short HEAD) (details /tmp/outer-git-push.log)"
else
  log "         git push: failed — see /tmp/outer-git-push.log (non-fatal at run end)"
fi
echo "outer-complete" > /tmp/outer-loop-done
log "========== RUN COMPLETE — outer-loop exited; marker /tmp/outer-loop-done =========="
log "         Further supervisor activity (e.g. SHIP_ONLY) is NOT a new outer-loop run."
exit 0
