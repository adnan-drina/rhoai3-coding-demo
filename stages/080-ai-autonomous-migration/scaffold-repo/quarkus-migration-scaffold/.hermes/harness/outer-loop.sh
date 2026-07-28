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
"Use the migration-harness skill and read ANALYSIS.md in its directory. The analysis bundle is committed (migration/mta-findings.json, findings-inventory.md, dependency-order.md, recipe-log.md). Execute the M1 profile step ONLY: read the legacy code under /projects/legacy and write migration/architecture-profile.md per ANALYSIS.md. A deterministic rubric gates it — verify yourself with: python3 ${HARNESS}/profile-rubric.py migration/architecture-profile.md /projects/legacy (must exit 0 — it cross-checks that every CDI/JAX-RS class is classified REDESIGN in section 7) BEFORE committing. Finish with ONE commit whose message STARTS with 'M1 profile:'. DO NOT PUSH."
    if [ -f migration/architecture-profile.md ] && python3 "$HARNESS/profile-rubric.py" migration/architecture-profile.md /projects/legacy >> "$LOG" 2>&1; then
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
  [ -f migration/roadmap.md ] && python3 "$HARNESS/roadmap-lint.py" migration/roadmap.md migration/findings-inventory.md /projects/legacy >> "$LOG" 2>&1
}
if roadmap_green; then
  log "M2: roadmap already present and lint-green"
else
  for ATTEMPT in 1 2; do
    P="Use the migration-harness skill and read SEQUENCING.md and BRIEF-TEMPLATE.md in its directory. M1 is committed. Execute M2 ONLY: read migration/architecture-profile.md, migration/dependency-order.md, migration/findings-inventory.md and migration.yaml, then write migration/roadmap.md plus one brief per story under migration/briefs/ exactly per SEQUENCING.md. Each brief carries its classes' roles and, for REDESIGN classes, their target contract from architecture-profile section 7 (SEQUENCING.md 'One quality model'). Every 'In scope' code quote is the REAL legacy code — quote it from /projects/legacy, never invent methods or annotations the class does not have (the lint cross-checks each quoted method/annotation against the legacy source). A deterministic lint gates the result — verify yourself with: python3 ${HARNESS}/roadmap-lint.py migration/roadmap.md migration/findings-inventory.md /projects/legacy (must exit 0) BEFORE committing. Finish with ONE commit whose message STARTS with 'M2 sequence:'. DO NOT PUSH."
    [ "$ATTEMPT" = "2" ] && P="Use the migration-harness skill and read SEQUENCING.md in its directory. A previous M2 attempt failed its lint — the findings are in /tmp/roadmap-lint.txt (read it with your file tools). LINT:fabrication findings mean the brief quoted a method/annotation that is NOT in the legacy source — read the real class under /projects/legacy and quote what is actually there. Fix every lint finding in migration/roadmap.md and the briefs, verify python3 ${HARNESS}/roadmap-lint.py migration/roadmap.md migration/findings-inventory.md /projects/legacy exits 0, and commit with prefix 'M2 sequence:'. DO NOT PUSH."
    mchat "m2-sequence-a${ATTEMPT}" "$P"
    if roadmap_green; then
      [ -n "$(git status --porcelain migration/)" ] && git add migration/ && git commit -q -m "M2 sequence: outer-loop mechanical commit of lint-green roadmap" 2>/dev/null
      log "M2: roadmap committed and lint-green"; break
    fi
    python3 "$HARNESS/roadmap-lint.py" migration/roadmap.md migration/findings-inventory.md /projects/legacy > /tmp/roadmap-lint.txt 2>&1 || true
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
      P="Use the migration-harness skill and read PLANNING.md in its directory. Execute M3 ONLY for story ${SID}: read the brief ${BRIEF} (it is authoritative — the decided shapes and contracts are IN it), migration/architecture-profile.md for context, and the legacy code it cites under /projects/legacy. Write specs/${SLUG}/spec.md, plan.md and tasks.md per PLANNING.md, scoped STRICTLY to this story. A deterministic lint gates the plan — verify yourself with: python3 ${HARNESS}/plan-lint.py specs/${SLUG}/tasks.md migration/mta-findings.json --findings-scope ${FINDINGS} --profile migration/architecture-profile.md (must exit 0) BEFORE committing. Finish with ONE commit whose message STARTS with '${SID} spec:'. DO NOT PUSH."
      [ "$ATTEMPT" = "2" ] && P="Use the migration-harness skill and read PLANNING.md in its directory. A previous M3 attempt for ${SID} failed its plan lint — the findings are in /tmp/plan-lint.txt (read it with your file tools). Fix every finding in specs/${SLUG}/, verify the lint command from the findings file exits 0, and commit with prefix '${SID} spec:'. DO NOT PUSH."
      mchat "m3-${SID}-a${ATTEMPT}" "$P"
      SPEC_TASKS=$(ls specs/${SID}-*/tasks.md 2>/dev/null | head -1)
      if [ -n "$SPEC_TASKS" ] && python3 "$HARNESS/plan-lint.py" "$SPEC_TASKS" migration/mta-findings.json --findings-scope "$FINDINGS" --profile migration/architecture-profile.md >> "$LOG" 2>&1; then
        [ -n "$(git status --porcelain specs/)" ] && git add specs/ && git commit -q -m "${SID} spec: outer-loop mechanical commit of lint-green spec" 2>/dev/null
        log "$SID: spec committed and plan-lint green"; break
      fi
      { echo "Lint command: python3 ${HARNESS}/plan-lint.py specs/${SLUG}/tasks.md migration/mta-findings.json --findings-scope ${FINDINGS} --profile migration/architecture-profile.md"
        [ -n "$SPEC_TASKS" ] && python3 "$HARNESS/plan-lint.py" "$SPEC_TASKS" migration/mta-findings.json --findings-scope "$FINDINGS" --profile migration/architecture-profile.md 2>&1 || echo "tasks.md missing entirely"; } > /tmp/plan-lint.txt
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
  # surfaces are enforced where they ship. Fidelity is ALWAYS on under the
  # single quality model — harvest classes need it; redesign classes are
  # exempt by the harvest-fidelity discriminator (no story-class waiver).
  PC=on; [ "$DEPLOY" = "true" ] || PC=off
  # Later-story class guard (V5 T-004): simple class names owned by stories
  # AFTER this one — the supervisor's scope sensor reverts any of these that
  # a task in THIS story creates in src/main (fabrication of a later-story
  # REDESIGN class). Derived from the roadmap scope of subsequent stories.
  LATER_CLASSES=$(echo "$STORIES" | awk -F'|' -v cur="$SID" 'seen{print $4} $1==cur{seen=1}' \
    | tr ', ' '\n' | sed -E 's/\.java$//; s#.*[./]##' | grep -E '^[A-Z][A-Za-z0-9]*$' | sort -u | tr '\n' ' ')
  rm -f /tmp/supervisor-done
  log "$SID: launching supervisor (deploy=${DEPLOY}, findings=${FINDINGS}, preserve=${PC}, later-classes=$(echo $LATER_CLASSES | wc -w))"
  env RUN_BASE="$(git rev-parse HEAD)" \
      STORY_SPEC_PREFIX="${SID} spec" \
      PLAN_SCOPE="$FINDINGS" \
      STORY_DEPLOY="$DEPLOY" \
      STORY_TASKS="$SPEC_TASKS" \
      STORY_SCOPE="$SCOPE" \
      LATER_CLASSES="$LATER_CLASSES" \
      PRESERVE_CHECK="$PC" \
      "$HARNESS/supervisor.sh" < /dev/null >> /tmp/supervisor-nohup.log 2>&1
  OUTCOME=$(cat /tmp/supervisor-done 2>/dev/null || echo "no-done-marker")
  log "$SID: supervisor finished — ${OUTCOME}"
  case "$OUTCOME" in
    success*|story-gate-passed*)
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
        log "$SID: brief refresh for remaining stories"
        mchat "brief-refresh-${SID}" \
"Use the migration-harness skill. Read migration/retro-proposals.md and apply ONLY the section titled '## Brief updates (auto-applicable)' to these remaining briefs:${REMAINING_BRIEFS}. Do not edit completed-story briefs, specs, skills, or harness scripts. If that section is empty or has no actionable edits, make no file changes. If you change briefs, finish with ONE commit whose message STARTS with 'Brief refresh:'. DO NOT PUSH." \
          || log "$SID: brief refresh session failed — continuing (non-blocking)"
        [ -n "$(git status --porcelain migration/briefs/)" ] \
          && git add migration/briefs/ && git commit -q -m "Brief refresh: outer-loop mechanical commit after ${SID}" 2>/dev/null || true
      else
        log "$SID: no remaining briefs or no retro-proposals — skipping brief refresh"
      fi
      ;;
    *)
      # A failed story blocks its dependents by construction (dependency
      # order) — stop the run with the evidence preserved rather than
      # building on a red foundation. Resume later: story-state.csv keeps
      # completed stories; relaunch outer-loop.sh to continue.
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
