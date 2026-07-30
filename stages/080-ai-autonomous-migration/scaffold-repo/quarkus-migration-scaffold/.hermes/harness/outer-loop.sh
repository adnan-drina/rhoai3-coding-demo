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

# Same two-writer protection as the supervisor: refuse to start if either
# an outer loop or a bare supervisor is already running.
# L-H1: ignore heartbeat helper processes (cmd contains outer-loop-heartbeat).
if pgrep -af "harness/outer-loo[p]\.sh" 2>/dev/null \
    | grep -v "outer-loop-heartbeat" \
    | awk -v self="$$" -v pp="$PPID" '$1 != self && $1 != pp { found=1 } END { exit found?0:1 }'; then
  echo "FATAL: another outer loop is already running — refusing to start" >&2; exit 1
fi
if pgrep -f "harness/superviso[r]\.sh" >/dev/null 2>&1; then
  echo "FATAL: a supervisor is already running — refusing to start" >&2; exit 1
fi

ORCH_PROVIDER="${ORCH_PROVIDER:-custom:maas-m2}"
ORCH_MODEL="${ORCH_MODEL:-minimax-m2}"
WORKER_MODEL="${WORKER_MODEL:-qwen27b/qwen3-6-27b}"
SESSION_TIMEOUT="${SESSION_TIMEOUT:-2700}"
HEARTBEAT_SECS="${OUTER_LOOP_HEARTBEAT_SECS:-60}"
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
mchat() { # $1=tag $2=prompt [$3=phase title for heartbeats]
  local tag="$1" prompt="$2" title="${3:-$1}" t0 now elapsed rc hb_pid slog
  t0=$(date +%s)
  slog="/tmp/outer-${tag}.log"
  log "         Actor: $(orch_label) — session ${tag} → ${slog}"
  # L-H1: distinct process name so single-instance guard ignores heartbeats
  cat > /tmp/outer-loop-heartbeat.sh <<'HBEOF'
#!/usr/bin/env bash
# outer-loop-heartbeat — not the outer loop itself
SECS="${1:-60}"; TITLE="${2:-session}"; T0="${3:-0}"; SLOG="${4:-/tmp/outer.log}"; LOG="${5:-/tmp/outer-loop.log}"
while true; do
  sleep "$SECS"
  now=$(date +%s); elapsed=$((now - T0))
  # L-R1: surface MiniMax rate limits while the session is still open
  if grep -qE "429|Too Many Requests|Rate limit|rate.?limit" "$SLOG" 2>/dev/null; then
    echo "[$(date -u +%F' '%T)] …        ${TITLE} waiting on MiniMax rate limit (${elapsed}s) — details ${SLOG}" >> "$LOG"
  else
    echo "[$(date -u +%F' '%T)] …        ${TITLE} still working on orchestrator (${elapsed}s) — details ${SLOG}" >> "$LOG"
  fi
done
HBEOF
  chmod +x /tmp/outer-loop-heartbeat.sh
  /tmp/outer-loop-heartbeat.sh "$HEARTBEAT_SECS" "$title" "$t0" "$slog" "$LOG" &
  hb_pid=$!
  timeout "$SESSION_TIMEOUT" hermes chat --provider "$ORCH_PROVIDER" --model "$ORCH_MODEL" -q "$prompt" \
    < /dev/null > "$slog" 2>&1
  rc=$?
  kill "$hb_pid" 2>/dev/null || true
  wait "$hb_pid" 2>/dev/null || true
  now=$(date +%s)
  # L-R1: one summary line if the finished session hit quota
  if grep -qE "429|Too Many Requests|Rate limit|rate.?limit" "$slog" 2>/dev/null; then
    log "         ${title}: MiniMax rate limit seen in session log (hermes_rc=${rc}) — supervisor backs off 15m on orch 429s"
  fi
  log "·        ${title} session finished ($((now - t0))s, hermes_rc=${rc}) — checking gate next (session≠gate)"
  return $rc
}

fail_run() { phase_fail "$1"; echo "outer-failed: $1" > /tmp/outer-loop-done; exit 1; }

: > "$LOG"
phase_start "Outer loop — autonomous migration" \
  "Models: $(orch_label) · $(worker_label) | progress: $LOG | resume: $STATE"

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
phase_start "Story loop — ${STORY_COUNT} stories (${STORY_IDS})"

STORY_IDX=0
while IFS='|' read -r SID DEPLOY FINDINGS SCOPE; do
  [ -n "$SID" ] || continue
  STORY_IDX=$((STORY_IDX + 1))
  SLUG_HINT=$(ls migration/briefs/${SID}-*.md 2>/dev/null | head -1 | xargs -n1 basename 2>/dev/null | sed 's/\.md$//' || echo "$SID")
  story_done "$SID" && { phase_ok "${SID} (${SLUG_HINT}) — already complete; skipping"; continue; }

  # -------------------------------------------------------- M3 SPECIFY
  SPEC_TASKS=$(ls specs/${SID}-*/tasks.md 2>/dev/null | head -1)
  if [ -z "$SPEC_TASKS" ]; then
    BRIEF=$(ls migration/briefs/${SID}-*.md 2>/dev/null | head -1)
    [ -n "$BRIEF" ] || fail_run "$SID has no brief under migration/briefs/"
    SLUG=$(basename "$BRIEF" .md)
    # O-M3KILL: hermes SIGKILL (rc=137/143) from operator freeze must NOT spend
    # a plan-lint attempt — otherwise two freezes look like "failed lint twice".
    ATTEMPT=1
    while [ "$ATTEMPT" -le 2 ]; do
      phase_start "M3 SPECIFY — plan story ${SLUG} (${STORY_IDX}/${STORY_COUNT}) [attempt ${ATTEMPT}/2]"
      P="Use the migration-harness skill and read PLANNING.md in its directory. Execute M3 ONLY for story ${SID}: read the brief ${BRIEF} (it is authoritative — the decided shapes and contracts are IN it), migration/architecture-profile.md for context, and the legacy code it cites under /projects/legacy. Write specs/${SLUG}/spec.md, plan.md and tasks.md per PLANNING.md, scoped STRICTLY to this story. A deterministic lint gates the plan — verify yourself with: python3 ${HARNESS}/plan-lint.py specs/${SLUG}/tasks.md migration/mta-findings.json --findings-scope ${FINDINGS} --profile migration/architecture-profile.md (must exit 0) BEFORE committing. Finish with ONE commit whose message STARTS with '${SID} spec:'. DO NOT PUSH. PACKAGE RENAME: full prefix legacyPackage→targetPackage only (never targetPackage.coolstore when targetPackage is com.demo)."
      [ "$ATTEMPT" = "2" ] && P="Use the migration-harness skill and read PLANNING.md in its directory. A previous M3 attempt for ${SID} failed its plan lint — the findings are in /tmp/plan-lint.txt (read it with your file tools). Fix every finding in specs/${SLUG}/, verify the lint command from the findings file exits 0, and commit with prefix '${SID} spec:'. DO NOT PUSH."
      mchat "m3-${SID}-a${ATTEMPT}" "$P" "M3 SPECIFY ${SID}"
      mchat_rc=$?
      if [ "$mchat_rc" -eq 137 ] || [ "$mchat_rc" -eq 143 ]; then
        log "         O-M3KILL: M3 session killed (hermes_rc=${mchat_rc}) — attempt ${ATTEMPT} NOT spent; retrying same attempt"
        phase_retry "M3 SPECIFY ${SID} — session killed (rc=${mchat_rc}); not counting as lint fail"
        continue
      fi
      SPEC_TASKS=$(ls specs/${SID}-*/tasks.md 2>/dev/null | head -1)
      if [ -n "$SPEC_TASKS" ] && python3 "$HARNESS/plan-lint.py" "$SPEC_TASKS" migration/mta-findings.json --findings-scope "$FINDINGS" --profile migration/architecture-profile.md > /tmp/plan-lint.txt 2>&1; then
        [ -n "$(git status --porcelain specs/)" ] && git add specs/ && git commit -q -m "${SID} spec: outer-loop mechanical commit of lint-green spec" 2>/dev/null
        phase_gate "M3 SPECIFY ${SID} plan-lint" GREEN "commit $(git rev-parse --short HEAD)"
        phase_ok "M3 SPECIFY — ${SLUG} spec/plan/tasks plan-lint-green; commit $(git rev-parse --short HEAD)"
        break
      fi
      { echo "Lint command: python3 ${HARNESS}/plan-lint.py specs/${SLUG}/tasks.md migration/mta-findings.json --findings-scope ${FINDINGS} --profile migration/architecture-profile.md"
        [ -n "$SPEC_TASKS" ] && python3 "$HARNESS/plan-lint.py" "$SPEC_TASKS" migration/mta-findings.json --findings-scope "$FINDINGS" --profile migration/architecture-profile.md 2>&1 || echo "tasks.md missing entirely"; } > /tmp/plan-lint.txt
      phase_gate "M3 SPECIFY ${SID} plan-lint" RED "full findings /tmp/plan-lint.txt"
      [ "$ATTEMPT" = "2" ] && fail_run "M3 SPECIFY ${SID} failed its plan lint twice"
      phase_retry "M3 SPECIFY ${SID} — bouncing once"
      ATTEMPT=$((ATTEMPT + 1))
    done
  else
    phase_ok "M3 SPECIFY — ${SID} spec already present ($SPEC_TASKS)"
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
  rm -f /tmp/supervisor-done
  if [ -n "${RESUME_RUN_BASE:-}" ] && [ "${RESUME_STORY:-}" = "$SID" ]; then
    STORY_RUN_BASE="$RESUME_RUN_BASE"
    log "         O-RESUME: using RESUME_RUN_BASE=$(git rev-parse --short "$STORY_RUN_BASE") for $SID only"
  else
    STORY_RUN_BASE="$(git rev-parse HEAD)"
  fi
  phase_start "M4/M5 EXECUTE — implement & ship ${SLUG_HINT} (${STORY_IDX}/${STORY_COUNT})" \
    "Models: $(orch_label) · $(worker_label) | deploy=${DEPLOY} findings=${FINDINGS} preserve=${PC} later-classes=$(echo $LATER_CLASSES | wc -w | tr -d ' ') | supervisor: /tmp/supervisor.log | run_base=$(git rev-parse --short "$STORY_RUN_BASE")"
  log "         Note: M4 rewrite+infer coding → $(worker_label) first; MiniMax only for orch/escalation (WORKER_FIRST) — supervisor.log records actor"
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
"Use the migration-harness skill. Read migration/retro-proposals.md and apply ONLY the section titled '## Brief updates (auto-applicable)' to these remaining briefs:${REMAINING_BRIEFS}. Do not edit completed-story briefs, specs, skills, or harness scripts. If that section is empty or has no actionable edits, make no file changes. If you change briefs, finish with ONE commit whose message STARTS with 'Brief refresh:'. DO NOT PUSH." \
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
