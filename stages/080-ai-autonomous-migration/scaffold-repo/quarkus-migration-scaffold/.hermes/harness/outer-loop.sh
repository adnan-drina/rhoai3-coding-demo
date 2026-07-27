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
#   nohup .hermes/harness/outer-loop.sh > /tmp/outer-loop-nohup.log 2>&1 &
# Progress:  tail -f /tmp/outer-loop.log  (and /tmp/supervisor.log per story)
# ---------------------------------------------------------------------------
set -u
export PATH=$HOME/.opencode/bin:$HOME/.local/bin:$PATH
cd /projects/modernized

# Same two-writer protection as the supervisor: refuse to start if either
# an outer loop or a bare supervisor is already running.
if pgrep -f "harness/outer-loo[p]" | grep -v "^$$\$" | grep -qv "^$PPID\$"; then
  echo "FATAL: another outer loop is already running — refusing to start" >&2; exit 1
fi
if pgrep -f "harness/superviso[r]" >/dev/null 2>&1; then
  echo "FATAL: a supervisor is already running — refusing to start" >&2; exit 1
fi

ORCH_PROVIDER="${ORCH_PROVIDER:-custom:maas-m2}"
ORCH_MODEL="${ORCH_MODEL:-minimax-m2}"
SESSION_TIMEOUT="${SESSION_TIMEOUT:-2700}"
LOG=/tmp/outer-loop.log
STATE=migration/story-state.csv
HARNESS=.hermes/harness
SKILLDIR=.hermes/skills/migration-harness

log() { echo "[$(date -u +%F' '%T)] $*" >> "$LOG"; }
log "outer loop start: orch=${ORCH_PROVIDER}/${ORCH_MODEL}"

# Bounded session runner for the M1/M2/M3 authoring gates. Simpler than
# the supervisor's classifier on purpose: these are single-artifact
# sessions with deterministic lints behind them — one attempt plus one
# retry, then the loop stops and reports (a defective plan must never
# reach execution ungated).
mchat() { # $1=tag $2=prompt
  local tag="$1" t0 t1 rc
  t0=$(date +%s)
  timeout "$SESSION_TIMEOUT" hermes chat --provider "$ORCH_PROVIDER" --model "$ORCH_MODEL" -q "$2" \
    < /dev/null > "/tmp/outer-${tag}.log" 2>&1
  rc=$?
  t1=$(date +%s)
  log "session ${tag}: $((t1-t0))s rc=${rc}"
  return $rc
}

fail_run() { log "FATAL: $1"; echo "outer-failed: $1" > /tmp/outer-loop-done; exit 1; }

# ------------------------------------------------------------- M1 ANALYZE
if [ -f migration/mta-findings.json ]; then
  log "M1: ground truth already present"
else
  log "M1: running analyze.sh (kantra + spec input bundle)"
  "$HARNESS/analyze.sh" >> "$LOG" 2>&1 || fail_run "M1 ground truth unavailable"
fi

if [ -f migration/architecture-profile.md ]; then
  log "M1: architecture profile already present"
else
  for ATTEMPT in 1 2; do
    mchat "m1-profile-a${ATTEMPT}" \
"Use the migration-harness skill and read ANALYSIS.md in its directory. The analysis bundle is committed (migration/mta-findings.json, findings-inventory.md, dependency-order.md, recipe-log.md). Execute the M1 profile step ONLY: read the legacy code under /projects/legacy and write migration/architecture-profile.md per ANALYSIS.md. A deterministic rubric gates it — verify yourself with: python3 ${HARNESS}/profile-rubric.py migration/architecture-profile.md (must exit 0) BEFORE committing. Finish with ONE commit whose message STARTS with 'M1 profile:'. DO NOT PUSH."
    if [ -f migration/architecture-profile.md ] && python3 "$HARNESS/profile-rubric.py" migration/architecture-profile.md >> "$LOG" 2>&1; then
      # Mechanical closure: commit if the session forgot.
      [ -n "$(git status --porcelain migration/)" ] && git add migration/ && git commit -q -m "M1 profile: outer-loop mechanical commit of rubric-green profile" 2>/dev/null
      log "M1: profile committed and rubric-green"; break
    fi
    [ "$ATTEMPT" = "2" ] && fail_run "M1 profile failed the rubric twice"
    log "M1: profile missing or rubric-red — retrying"
    git checkout -q -- migration/ 2>/dev/null || true
  done
fi

# ------------------------------------------------------------ M2 SEQUENCE
roadmap_green() {
  [ -f migration/roadmap.md ] && python3 "$HARNESS/roadmap-lint.py" migration/roadmap.md migration/findings-inventory.md >> "$LOG" 2>&1
}
if roadmap_green; then
  log "M2: roadmap already present and lint-green"
else
  for ATTEMPT in 1 2; do
    P="Use the migration-harness skill and read SEQUENCING.md and BRIEF-TEMPLATE.md in its directory. M1 is committed. Execute M2 ONLY: read migration/architecture-profile.md, migration/dependency-order.md, migration/findings-inventory.md and migration.yaml, then write migration/roadmap.md plus one brief per story under migration/briefs/ exactly per SEQUENCING.md. Deploy stories must meet the production-grade bar (SEQUENCING.md 'Production-grade bar'). A deterministic lint gates the result — verify yourself with: python3 ${HARNESS}/roadmap-lint.py migration/roadmap.md migration/findings-inventory.md (must exit 0) BEFORE committing. Finish with ONE commit whose message STARTS with 'M2 sequence:'. DO NOT PUSH."
    [ "$ATTEMPT" = "2" ] && P="Use the migration-harness skill and read SEQUENCING.md in its directory. A previous M2 attempt failed its lint — the findings are in /tmp/roadmap-lint.txt (read it with your file tools). Fix every lint finding in migration/roadmap.md and the briefs, verify python3 ${HARNESS}/roadmap-lint.py migration/roadmap.md migration/findings-inventory.md exits 0, and commit with prefix 'M2 sequence:'. DO NOT PUSH."
    mchat "m2-sequence-a${ATTEMPT}" "$P"
    if roadmap_green; then
      [ -n "$(git status --porcelain migration/)" ] && git add migration/ && git commit -q -m "M2 sequence: outer-loop mechanical commit of lint-green roadmap" 2>/dev/null
      log "M2: roadmap committed and lint-green"; break
    fi
    python3 "$HARNESS/roadmap-lint.py" migration/roadmap.md migration/findings-inventory.md > /tmp/roadmap-lint.txt 2>&1 || true
    [ "$ATTEMPT" = "2" ] && fail_run "M2 roadmap failed its lint twice"
    log "M2: roadmap lint red — bouncing once with the findings"
  done
fi

# ---------------------------------------------------------- story loop
[ -f "$STATE" ] || { echo "story,outcome,epoch" > "$STATE"; git add "$STATE"; git commit -q -m "Outer loop: story state ledger" 2>/dev/null || true; }
story_done() { grep -q "^$1,complete" "$STATE" 2>/dev/null; }

STORIES=$(python3 "$HARNESS/parse-roadmap.py" migration/roadmap.md)
[ -n "$STORIES" ] || fail_run "roadmap parsed to zero stories"
log "stories: $(echo "$STORIES" | cut -d'|' -f1 | tr '\n' ' ')"

while IFS='|' read -r SID DEPLOY FINDINGS SCOPE; do
  [ -n "$SID" ] || continue
  story_done "$SID" && { log "$SID: already complete"; continue; }

  # -------------------------------------------------------- M3 SPECIFY
  SPEC_TASKS=$(ls specs/${SID}-*/tasks.md 2>/dev/null | head -1)
  if [ -z "$SPEC_TASKS" ]; then
    BRIEF=$(ls migration/briefs/${SID}-*.md 2>/dev/null | head -1)
    [ -n "$BRIEF" ] || fail_run "$SID has no brief under migration/briefs/"
    SLUG=$(basename "$BRIEF" .md)
    for ATTEMPT in 1 2; do
      P="Use the migration-harness skill and read PLANNING.md in its directory. Execute M3 ONLY for story ${SID}: read the brief ${BRIEF} (it is authoritative — the decided shapes and contracts are IN it), migration/architecture-profile.md for context, and the legacy code it cites under /projects/legacy. Write specs/${SLUG}/spec.md, plan.md and tasks.md per PLANNING.md, scoped STRICTLY to this story. A deterministic lint gates the plan — verify yourself with: python3 ${HARNESS}/plan-lint.py specs/${SLUG}/tasks.md migration/mta-findings.json --findings-scope ${FINDINGS} (must exit 0) BEFORE committing. Finish with ONE commit whose message STARTS with '${SID} spec:'. DO NOT PUSH."
      [ "$ATTEMPT" = "2" ] && P="Use the migration-harness skill and read PLANNING.md in its directory. A previous M3 attempt for ${SID} failed its plan lint — the findings are in /tmp/plan-lint.txt (read it with your file tools). Fix every finding in specs/${SLUG}/, verify the lint command from the findings file exits 0, and commit with prefix '${SID} spec:'. DO NOT PUSH."
      mchat "m3-${SID}-a${ATTEMPT}" "$P"
      SPEC_TASKS=$(ls specs/${SID}-*/tasks.md 2>/dev/null | head -1)
      if [ -n "$SPEC_TASKS" ] && python3 "$HARNESS/plan-lint.py" "$SPEC_TASKS" migration/mta-findings.json --findings-scope "$FINDINGS" >> "$LOG" 2>&1; then
        [ -n "$(git status --porcelain specs/)" ] && git add specs/ && git commit -q -m "${SID} spec: outer-loop mechanical commit of lint-green spec" 2>/dev/null
        log "$SID: spec committed and plan-lint green"; break
      fi
      { echo "Lint command: python3 ${HARNESS}/plan-lint.py specs/${SLUG}/tasks.md migration/mta-findings.json --findings-scope ${FINDINGS}"
        [ -n "$SPEC_TASKS" ] && python3 "$HARNESS/plan-lint.py" "$SPEC_TASKS" migration/mta-findings.json --findings-scope "$FINDINGS" 2>&1 || echo "tasks.md missing entirely"; } > /tmp/plan-lint.txt
      [ "$ATTEMPT" = "2" ] && fail_run "$SID spec failed its plan lint twice"
      log "$SID: plan lint red — bouncing once with the findings"
    done
  else
    log "$SID: spec already present ($SPEC_TASKS)"
  fi

  # ----------------------------------------------------- M4/M5 EXECUTE
  # One supervisor child per story with computed env. RUN_BASE=HEAD at
  # story start keeps every phase prefix story-scoped (no cross-story
  # commit-range collisions). PRESERVE_CHECK follows deploy: preserve
  # surfaces are enforced where they ship. FIDELITY_CHECK follows story
  # class: hardening stories (findings: -) deliberately depart from the
  # staged legacy, so the harvest-fidelity sensor is waived for them
  # (S03 lesson — the brief is their design authority, not staging).
  PC=on; [ "$DEPLOY" = "true" ] || PC=off
  FC=on; [ "$FINDINGS" = "none" ] && FC=off
  rm -f /tmp/supervisor-done
  log "$SID: launching supervisor (deploy=${DEPLOY}, findings=${FINDINGS}, preserve=${PC}, fidelity=${FC})"
  env RUN_BASE="$(git rev-parse HEAD)" \
      STORY_SPEC_PREFIX="${SID} spec" \
      PLAN_SCOPE="$FINDINGS" \
      STORY_DEPLOY="$DEPLOY" \
      STORY_TASKS="$SPEC_TASKS" \
      STORY_SCOPE="$SCOPE" \
      PRESERVE_CHECK="$PC" \
      FIDELITY_CHECK="$FC" \
      "$HARNESS/supervisor.sh" < /dev/null >> /tmp/supervisor-nohup.log 2>&1
  OUTCOME=$(cat /tmp/supervisor-done 2>/dev/null || echo "no-done-marker")
  log "$SID: supervisor finished — ${OUTCOME}"
  case "$OUTCOME" in
    success*|story-gate-passed*)
      echo "${SID},complete,$(date -u +%s)" >> "$STATE"
      git add "$STATE" && git commit -q -m "${SID} story complete: ${OUTCOME}" 2>/dev/null || true
      ;;
    *)
      # A failed story blocks its dependents by construction (dependency
      # order) — stop the run with the evidence preserved rather than
      # building on a red foundation.
      echo "${SID},failed,$(date -u +%s)" >> "$STATE"
      git add "$STATE" && git commit -q -m "${SID} story FAILED: ${OUTCOME}" 2>/dev/null || true
      git push origin main >> "$LOG" 2>&1 || true
      fail_run "$SID did not ship (${OUTCOME}) — run stopped before dependent stories"
      ;;
  esac
done <<< "$STORIES"

log "OUTER LOOP COMPLETE: all stories shipped"
git push origin main >> "$LOG" 2>&1 || true
echo "outer-complete" > /tmp/outer-loop-done
exit 0
