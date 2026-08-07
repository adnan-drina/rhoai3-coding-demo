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

# O-PIDREG / O-OCGROUP / O-KILLLEDGER (F-74)
# shellcheck source=session-registry.sh
. "$(cd "$(dirname "$0")" && pwd)/session-registry.sh"
SUPERVISOR_LOG=/tmp/supervisor.log

# Single-instance guard (V3 incident: a failed-pull launch script started
# one supervisor, its retry started another — two writers on one tree).
# O-SUPCMDLINE / O-SUPFLOCK: never use bare pgrep -f (oc-exec -lc text and
# even argv-shaped matches false-positive → refuse start → no-done → false
# S0N,failed). Hold an exclusive flock for the life of this process.
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
SUPERVISOR_LOCK="${SUPERVISOR_LOCK:-/tmp/supervisor.lock}"
clear_stale_pid_lock "$SUPERVISOR_LOCK"
exec 9>"$SUPERVISOR_LOCK"
if ! flock -n 9; then
  clear_stale_pid_lock "$SUPERVISOR_LOCK"
  exec 9>"$SUPERVISOR_LOCK"
  if ! flock -n 9; then
    echo "FATAL: another supervisor holds $SUPERVISOR_LOCK — refusing to start" >&2
    exit 1
  fi
fi
printf '%s\n' "$$" >&9
# Keep FD 9 open (flock) until process exit.

# O-LOGCOLLIDE: key OpenCode seat logs by story so S0N T-001 does not clobber
# prior-story /tmp/oc-T-001.{json,err}. Falls back to unprefixed when STORY_ID
# cannot be derived (adhoc/SHIP_ONLY).
# O-M4COMPOSITE: typed tags are already S0N-T-NNN-Name — do not double-prefix
# (was /tmp/oc-S01-S01-T-002-SCC3.json).
oc_seat_base() { # $1=tag → /tmp/oc-<story>-<tag> or /tmp/oc-<tag>
  local tag="$1" sid="${STORY_ID:-}"
  if [ -z "$sid" ]; then
    sid=$(printf '%s' "${STORY_SPEC_PREFIX:-}" | awk '{print $1}')
  fi
  if [[ "$tag" =~ ^S[0-9]+-T- ]]; then
    printf '/tmp/oc-%s' "$tag"
  elif [[ "$sid" =~ ^S[0-9]+$ ]]; then
    printf '/tmp/oc-%s-%s' "$sid" "$tag"
  else
    printf '/tmp/oc-%s' "$tag"
  fi
}


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
# O-DEBTSHIPRACE: if the debt ledger still has unresolved *freeze-worthy sensor*
# RED headers from record_debt (task|milestone|sonar|seat-budget), KEEP freeze
# across hotswap — do not wipe and race into M5 ship.
# O-DEBTFRZM5STICKY: O-DEBTFRZLEDGER writes `## M5 residuals — S0N (…)`, which
# is inventory for later stories — NOT freeze-worthy.
# O-DEBTSHIPPROCESS: `## M5 ship — pipeline RED` / coverage RED are ship-process
# outcomes that SHIP_ONLY re-earns — matching bare `^## .+ — .+ RED` deadlocks
# the next ship on the previous attempt's failure (W4-676).
if [ "${V9_KEEP_DEBT_FREEZE:-0}" = "1" ]; then
  :
elif [ -f migration/debt.md ] \
  && grep -qE '^## .+ — (task|milestone|sonar|seat-budget) RED[[:space:]]*$' migration/debt.md 2>/dev/null; then
  touch /tmp/debt-freeze /tmp/supervisor-pause
  # log not yet open — outer/stderr only
  echo "[supervisor] O-DEBTFRZ: keeping freeze — unresolved freeze-worthy ## … RED in migration/debt.md" >&2
else
  rm -f /tmp/debt-freeze /tmp/supervisor-pause
fi

orch_label() {
  case "${ORCH_MODEL}" in
    *minimax*) echo "orchestrator MiniMax M2 (Hermes)" ;;
    *) echo "orchestrator ${ORCH_MODEL} (Hermes)" ;;
  esac
}
# O-SFIXATTR: after post_commit_verify, append honest sfix actor to END lines.
sfix_attr_end_note() {
  local actor note=""
  [ -f /tmp/sfix-last-actor ] || { echo ""; return 0; }
  actor=$(tr -d '[:space:]' </tmp/sfix-last-actor)
  rm -f /tmp/sfix-last-actor
  case "$actor" in
    minimax) note="; sensor-fix via $(orch_label) (O-SFIXATTR)" ;;
    qwen)    note="; sensor-fix via $(worker_label) (O-SFIXATTR)" ;;
    mechan)  note="; sensor-fix via mechanical (O-SFIXATTR)" ;;
  esac
  printf '%s' "$note"
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

# O-TASKHB: same demo cadence as outer-loop M3 heartbeats — long M4 worker /
# MiniMax / sensor seats must not leave /tmp/outer-loop.log stationary.
# Demo lines include full task title (not only T-NNN), matching log_task.
TASK_HEARTBEAT_SECS="${TASK_HEARTBEAT_SECS:-${OUTER_LOOP_HEARTBEAT_SECS:-60}}"
# O-M4COMPOSITE / O-M4TCHEADING — must match task_contract.HEADING_TASK_ID_ATOM
# (typed S0N-TC-Name | S0N-T-NNN-Name | legacy T-*). Bash ERE (no \d); Python
# uses the task_contract export. TC alternation MUST precede T- (prefix).
HEADING_TASK_ID_ATOM='(?:S[0-9]+-TC-[A-Za-z0-9]+|S[0-9]+-T-[0-9]{3}(?:-[A-Za-z0-9]+)?|T[-A-Za-z0-9]*[0-9]+[A-Za-z]*)'
# O-LOGPROG / O-M4EXECHB: one-line progress for outer-loop M4 heartbeat append.
# O-HBPROGSTALE (W4-669 CHANGE): stamp ts=<epoch> on every write so the
# heartbeat can refuse stale progress instead of confidently naming a dead phase.
m4_progress() { # $1=phase [$2=active-task]
  local phase="$1" active="${2:-}" sid="${STORY_ID:-story}" n="" tot="" ts
  ts=$(date +%s)
  if [ -n "${TASK_IDS:-}" ]; then
    tot=$(printf '%s\n' $TASK_IDS | grep -c . || true)
  fi
  if [ -n "$active" ] && [ -n "${TASK_IDS:-}" ]; then
    n=$(printf '%s\n' $TASK_IDS | grep -nFx "$active" | head -1 | cut -d: -f1 || true)
  fi
  if [ -n "$n" ] && [ -n "$tot" ]; then
    printf 'ts=%s m4=%s phase=%s task=%s %s/%s\n' "$ts" "$sid" "$phase" "$active" "$n" "$tot" \
      > /tmp/outer-heartbeat-progress.txt
  else
    printf 'ts=%s m4=%s phase=%s%s\n' "$ts" "$sid" "$phase" "${active:+ task=$active}" \
      > /tmp/outer-heartbeat-progress.txt
  fi
}
task_hb_pretty() { # $1=label-or-tag → "T-003 — <title>" when resolvable
  local label="$1" tid="" title=""
  # Typed composite first (S01-T-001-BaseEntity), then legacy T-001 / T-001A.
  if [[ "$label" =~ ^(S[0-9]+-T-[0-9]{3}(-[A-Za-z0-9]+)?) ]] \
    || [[ "$label" =~ ^(T-[0-9]+[A-Za-z]*) ]]; then
    tid="${BASH_REMATCH[1]}"
    if declare -F task_title >/dev/null 2>&1; then
      title=$(task_title "$tid" 2>/dev/null || true)
    fi
    if [ -n "$title" ] && [ "$title" != "$tid" ]; then
      printf '%s — %s' "$tid" "$title"
      return 0
    fi
    printf '%s' "$tid"
    return 0
  fi
  printf '%s' "$label"
}
task_hb() { # $1=label $2=kind(worker|orchestrator|sensor:…) $3=elapsed_s [$4=detail]
  local label="$1" kind="$2" elapsed="$3" detail="${4:-}" pretty
  pretty=$(task_hb_pretty "$label")
  if [ -n "$detail" ]; then
    outer_log "         … ${pretty} still working on ${kind} (${elapsed}s) — ${detail}"
  else
    outer_log "         … ${pretty} still working on ${kind} (${elapsed}s)"
  fi
}

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
# C1: per-run isolated Maven repo — factory-parity resolution for every sensor.
# O-M4EXECHB: pulse /tmp/outer-loop.log during seed (can be minutes; demo looked stuck).
m4_progress "maven-seed"
outer_log "         … M4 bootstrap: seeding isolated Maven repo (one-time, ~5 min) — details ${LOG}"
_seed_t0=$(date +%s)
rm -f /tmp/m4-seed-done
(
  while [ ! -f /tmp/m4-seed-done ]; do
    sleep "$TASK_HEARTBEAT_SECS"
    [ -f /tmp/m4-seed-done ] && break
    outer_log "         … M4 bootstrap still working on maven-seed ($(( $(date +%s) - _seed_t0 ))s) — details ${LOG}"
  done
) &
_seed_hb=$!
.hermes/harness/sensors.sh seed >> "$LOG" 2>&1 || log "WARN: isolated repo seed failed — sensors fall back to red-on-use"
touch /tmp/m4-seed-done
kill "$_seed_hb" 2>/dev/null || true
wait "$_seed_hb" 2>/dev/null || true
outer_log "         … M4 bootstrap: maven-seed done (elapsed $(( $(date +%s) - _seed_t0 ))s) — details ${LOG}"
m4_progress "plan-lint"
event() { echo "$(date -u +%s),$1,$2,$3,$4" >> "$EVENTS"; }

# K11: per-Findings-rule outcome for O-DRV5 / run-report aggregation.
record_rule_outcomes() { # $1=tid $2=outcome-token
  local tid="$1" outcome="$2" ids
  [ -n "${TASKS_FILE:-}" ] && [ -f "$TASKS_FILE" ] || return 0
  ids=$(python3 - "$TASKS_FILE" "$tid" <<'PY' 2>/dev/null || true
import re, sys
text = open(sys.argv[1], encoding="utf-8", errors="replace").read()
tid = sys.argv[2]
heads = list(re.finditer(r"^#{2,6}\s+((?:S\d+-TC-[A-Za-z0-9]+|S\d+-T-\d{3}(?:-[A-Za-z0-9]+)?|T[-A-Za-z0-9]*\d+[A-Za-z]*))\s*:", text, re.M))
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

# O-SCOPEBACKFILL: structure deliverable paths for a task (space-separated).
# Emits Target/Owns `.gitkeep` and/or `package-info.java` — never Source/Absorbs
# legacy paths. Empty when Shape≠structure and no structure Owns/Target.
# Migration-general (any package path from tasks.md).
structure_gitkeep_targets() { # $1=task-id
  local tid="$1"
  [ -n "${TASKS_FILE:-}" ] && [ -f "$TASKS_FILE" ] || return 0
  python3 - "$TASKS_FILE" "$tid" <<'PY' 2>/dev/null || true
import re, sys
from pathlib import Path as _P
path, tid = sys.argv[1], sys.argv[2]
text = open(path, encoding="utf-8", errors="replace").read()
heads = list(re.finditer(r"^#{2,6}\s+((?:S\d+-TC-[A-Za-z0-9]+|S\d+-T-\d{3}(?:-[A-Za-z0-9]+)?|T[-A-Za-z0-9]*\d+[A-Za-z]*))\s*:", text, re.M))
body = ""
for i, m in enumerate(heads):
    if m.group(1) != tid:
        continue
    end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
    body = text[m.end():end]
    break
if not body:
    sys.exit(0)
shape_m = re.search(r"^\*\*Shape\s*:\s*(.+?)\*\*\s*$", body, re.M | re.I)
if not shape_m:
    shape_m = re.search(r"^\*\*Shape\*\*\s*:?\s*(.+)$", body, re.M | re.I)
shape = (shape_m.group(1).strip().lower() if shape_m else "")

# O-STRUCTPKGINFO: strip Source/Absorbs legacy lines before path scrape —
# never invent structure Targets under legacyPackage (pair O-ESCW3LEGACYPKG).
body_tgt = "\n".join(
    ln for ln in body.splitlines()
    if not re.search(r"(?i)^\s*[-*]?\s*\*\*(?:Source|Absorbs)\*\*", ln)
    and not re.search(r"(?i)/projects/legacy/|legacyPackage", ln)
)

# Explicit deliverables first (hyphen-safe: package-info.java).
paths = sorted(set(re.findall(
    r"src/(?:main|test)/[A-Za-z0-9_./-]+/\.gitkeep", body_tgt
)))
pkginfo = sorted(set(re.findall(
    r"src/(?:main|test)/java/[A-Za-z0-9_./-]+/package-info\.java", body_tgt
)))
# O-ACSTRUCT / O-STRUCTSHAPE: synthesize `.gitkeep` ONLY when Shape=structure.
# Plan prose like "write to src/main/java/com/demo/model/" on rewrite/batch
# tasks must NOT invent a structure Target — that made committed() log
# O-SCOPEBACKFILL and re-dispatch Qwen (then MiniMax) after an honest O-T6 tip
# (S01-T-002 Role/User).
if shape == "structure" and not paths and not pkginfo:
    for m in re.finditer(r"src/(?:main|test)/java/[A-Za-z0-9_./-]+", body_tgt):
        d = m.group(0).rstrip("/")
        if d.endswith(".java") or d.endswith(".gitkeep"):
            continue
        # Reject truncated "…/package" from package-info hyphen split (legacy).
        if d.endswith("/package") or d.endswith(".package"):
            continue
        if not _P(d).suffix:
            paths.append(f"{d}/.gitkeep")
    paths = sorted(set(paths))
# Prefer package-info as the structure file when Owns declares it; keep
# sibling .gitkeep only when explicitly listed (not synthesized alongside).
deliverables = list(pkginfo) if pkginfo else list(paths)
if pkginfo and paths:
    # Explicit .gitkeep in Owns/Target still required; synthesized dirs alone
    # are dropped when package-info is the declared Owns file.
    explicit_gk = sorted(set(re.findall(
        r"(?:Owns|Target|→|->)[^\n]*?(src/(?:main|test)/[A-Za-z0-9_./-]+/\.gitkeep)",
        body_tgt,
    )))
    deliverables = sorted(set(pkginfo + explicit_gk))
# Structure ledger: Shape=structure, or explicit .gitkeep/package-info Owns.
# Do not treat bare "package-info" prose on rewrite tasks as structure.
structish = shape == "structure" or bool(paths) or bool(pkginfo)
if not structish:
    sys.exit(0)
for p in deliverables:
    print(p)
PY
}

# O-SCOPEBACKFILL: True (exit 0) when a structure Target is still missing.
# Accepts .gitkeep OR package-info.java deliverables from structure_gitkeep_targets.
structure_targets_missing() { # $1=task-id
  local tid="$1" t missing=0
  for t in $(structure_gitkeep_targets "$tid"); do
    if [ ! -f "$t" ]; then
      missing=1
      break
    fi
  done
  [ "$missing" -eq 1 ]
}

# O-SCOPEBACKFILL: after scope revert, mechanically restore missing structure
# Targets (.gitkeep) and commit a clear ${T}: tip — never leave the ledger ✓
# against a tip that is only "scope revert" while the deliverable is absent.
scope_structure_backfill() { # $1=commit-prefix (T-NNN)
  local prefix="$1" missing="" t title
  case "$prefix" in T-*) ;; *) return 0 ;; esac
  [ -n "${TASKS_FILE:-}" ] && [ -f "$TASKS_FILE" ] || return 0
  for t in $(structure_gitkeep_targets "$prefix"); do
    # Only auto-create `.gitkeep` placeholders — never empty package-info.java
    # (O-STRUCTPKGINFO: Owns may be package-info; worker must copy real content).
    case "$t" in
      *.gitkeep) ;;
      *) continue ;;
    esac
    if [ ! -f "$t" ]; then
      mkdir -p "$(dirname "$t")"
      touch "$t"
      missing="$missing $t"
    fi
  done
  [ -n "$missing" ] || return 0
  log "scope sensor: O-SCOPEBACKFILL — restoring structure deliverable(s):${missing}"
  outer_log "         O-SCOPEBACKFILL: created${missing} after scope revert (structure Target was absent)"
  event "$prefix" 0 scope_backfill "${missing# }"
  for t in $missing; do
    git add -- "$t" 2>/dev/null || true
  done
  title=$(task_title "$prefix" 2>/dev/null || true)
  [ -n "$title" ] || title="Restore structure package deliverable"
  # Prefer a real ${T}: subject (not "scope revert") so committed()/ledger
  # cite a deliverable tip. Leave dirty only if commit fails.
  if ! git diff --cached --quiet 2>/dev/null; then
    # Subject must stay `${T}: …` (not "… scope revert …") so committed()
    # and ledger tips cite a deliverable tip distinct from the wipe commit.
    git commit -q -m "${prefix}: ${title} (O-SCOPEBACKFILL)" 2>/dev/null \
      || git commit -q -m "${prefix}: structure deliverable .gitkeep (O-SCOPEBACKFILL)" 2>/dev/null \
      || log "scope sensor: O-SCOPEBACKFILL — staged${missing} but commit failed (left dirty for mechan)"
  fi
}

# O-SFIXNODELTA: True (exit 0) when HEAD tip has no meaningful content —
# empty churn, or only structure scaffold (.gitkeep / package-info.java).
# Migration-general: any Spring Boot → Quarkus structure tip must not own
# a sensor-fix that edits pom/src under the task's name.
sfix_tip_content_empty() {
  local files numstat add del
  files=$(git diff-tree --no-commit-id --name-only -r HEAD 2>/dev/null || true)
  [ -z "$files" ] && return 0
  # Structure-only tip
  if ! printf '%s\n' "$files" | grep -qvE '(^|/)\.gitkeep$|(^|/)package-info\.java$'; then
    return 0
  fi
  # Zero insertions+deletions (incl. mode-only / empty blob adds)
  numstat=$(git diff-tree --no-commit-id --numstat -r HEAD 2>/dev/null || true)
  [ -z "$numstat" ] && return 0
  add=$(printf '%s\n' "$numstat" | awk '{ if ($1 ~ /^[0-9]+$/) s+=$1 } END { print s+0 }')
  del=$(printf '%s\n' "$numstat" | awk '{ if ($2 ~ /^[0-9]+$/) s+=$2 } END { print s+0 }')
  [ "${add:-0}" -eq 0 ] && [ "${del:-0}" -eq 0 ] && return 0
  return 1
}

# O-REVERTPURE: stage only the reverted paths for a scope-revert commit —
# never `git add -A` (that sweeps regenerated mta-findings-current.json).
stage_scope_revert_paths() {
  local f
  for f in "$@"; do
    [ -n "$f" ] || continue
    if [ -e "$f" ]; then
      git add -- "$f" 2>/dev/null || true
    else
      # Deletion already staged by `git rm`, or needs -u after plain rm.
      git add -u -- "$f" 2>/dev/null || true
    fi
  done
  git reset -q HEAD -- migration/mta-findings-current.json \
    migration/scaffold-presatisfied.generated.txt \
    migration/scaffold-presatisfied.txt \
    .hermes migration/staging 2>/dev/null || true
}

committed() {
  # O-FGRETRO: probe harden may invalidate prior ALREADY COMPLETE skips.
  if [ -f /tmp/fgretro-reopen.txt ] && grep -qx "$1" /tmp/fgretro-reopen.txt 2>/dev/null; then
    return 1
  fi
  # Subject must START with T-NNN: — do not match plan messages like
  # "… DTOs (T-005) before …" or cross-story noise inside the body (O-COMMITID).
  # O-RESUMEBASEEXCL: RUN_BASE..HEAD is exclusive of RUN_BASE — include the
  # tip at RUN_BASE itself so RESUME_RUN_BASE=<tipsha> counts that tip.
  # O-SHIPROUNDBASE: Preflight/Gate/Build fix round satisfaction uses
  # /tmp/ship-session-base (exclusive) when present — prior-session tips and
  # abandoned origin tips are not authority for a fresh ship round budget.
  local _hit _range_log="" _base="${RUN_BASE:-}" _include_base=1 _ssb="" _story_floor=""
  case "$1" in
    "Preflight fix"*|"Gate fix"*|"Build fix"*)
      if [ -f /tmp/ship-session-base ]; then
        _ssb=$(tr -d '[:space:]' </tmp/ship-session-base 2>/dev/null || true)
        if [ -n "$_ssb" ] && git rev-parse --verify "${_ssb}^{commit}" >/dev/null 2>&1; then
          _base="$_ssb"
          _include_base=0
        fi
      fi
      ;;
    T-*|TC-*|S[0-9]*)
      # O-COMMITSTORYFLOOR: T-NNN: ids restart every story. RUN_BASE for S02 is
      # often the M3 spec tip *before* S01 execute, so S01's T-001:…T-011: sit
      # inside RUN_BASE..HEAD and falsely skip S02's same ids (W4R7 S02: only
      # Specialty untracked; NamedEntity "already committed" was S01 T-004).
      # Floor at latest subject-leading "… story complete" tip when it is a
      # descendant of RUN_BASE (or when RUN_BASE is unset).
      _story_floor=$(git log -1 --format=%H --grep='story complete' HEAD 2>/dev/null || true)
      if [ -n "$_story_floor" ] && git rev-parse --verify "${_story_floor}^{commit}" >/dev/null 2>&1; then
        if [ -z "$_base" ] || git merge-base --is-ancestor "${_base}" "${_story_floor}" 2>/dev/null; then
          _base="$_story_floor"
          _include_base=0
        fi
      fi
      ;;
  esac
  if [ -n "$_base" ] && git rev-parse --verify "${_base}^{commit}" >/dev/null 2>&1; then
    _range_log=$(git log --oneline "${_base}..HEAD" 2>/dev/null || true)
    if [ "$_include_base" = "1" ]; then
      _range_log=$(
        printf '%s\n' "$_range_log"
        git log --oneline -1 "${_base}" 2>/dev/null || true
      )
    fi
  else
    _range_log=$(git log --oneline 2>/dev/null || true)
  fi
  _hit=$(printf '%s\n' "$_range_log" | grep -E "^[0-9a-f]+ ${1}:" | head -1 || true)
  [ -n "$_hit" ] || return 1
  # O-ACCOMMITSKIP: a false/empty ALREADY COMPLETE must not skip when
  # already-complete.py still says must-run (e.g. JDBC task skipped via
  # JpaRepositoryImpl-cdi while staging jdbc remains — v2 S04 T-004).
  if echo "$_hit" | grep -q "ALREADY COMPLETE"; then
    if [ -f .hermes/harness/already-complete.py ] && [ -n "${TASKS_FILE:-}" ]; then
      if ! python3 .hermes/harness/already-complete.py "$TASKS_FILE" "$1" >/dev/null 2>&1; then
        return 1
      fi
    fi
    # O-ACSTRUCTCOMMIT: allow-empty ALREADY COMPLETE never satisfies
    # Shape=structure — the tip must contain the Target .gitkeep (W4 T-003:
    # a419d88 empty tip + dirty gitkeep → skip → ship archived the deliverable).
    if [ -n "$(structure_gitkeep_targets "$1")" ]; then
      local _acsha _acfiles=""
      _acsha=$(echo "$_hit" | awk '{print $1}')
      _acfiles=$(git diff-tree --no-commit-id --name-only -r "$_acsha" 2>/dev/null || true)
      if [ -z "$_acfiles" ]; then
        log "$1: O-ACSTRUCTCOMMIT — allow-empty ALREADY COMPLETE does not satisfy structure Target"
        return 1
      fi
      local _tgt
      for _tgt in $(structure_gitkeep_targets "$1"); do
        if ! git cat-file -e "${_acsha}:${_tgt}" 2>/dev/null; then
          log "$1: O-ACSTRUCTCOMMIT — ALREADY COMPLETE tip lacks ${_tgt}"
          return 1
        fi
      done
    fi
  fi
  # O-SCOPEBACKFILL: never mark ✓ when structure/.gitkeep Target is still
  # absent — a prior T-NNN: tip + scope-revert tip must not satisfy the ledger
  # while the declared deliverable is missing (v3 S01 T-003).
  if structure_targets_missing "$1"; then
    log "$1: O-SCOPEBACKFILL — not committed (structure Target still absent)"
    return 1
  fi
  # Belt: tip that is only a scope-revert subject cannot satisfy completion
  # when a structure Target was declared (scope revert never matches T-NNN:
  # above; this guards HEAD-only callers that pass the tip subject).
  local _subj
  _subj=$(git log -1 --format=%s 2>/dev/null || true)
  if echo "$_subj" | grep -qE "^${1}[[:space:]]+scope[[:space:]]+revert"; then
    if [ -n "$(structure_gitkeep_targets "$1")" ] && structure_targets_missing "$1"; then
      log "$1: O-SCOPEBACKFILL — HEAD is scope-revert and Target still missing"
      return 1
    fi
  fi
  return 0
}

# O-LIFECYCLESM (step 3 / B) — typed READY→…→ADVANCE|BLOCKED|DEBT + tip SHA.
# W4-742: happy-path sites must not bypass the matrix. Failures are logged
# (not silent). Emergency bypass remains CLI force flag + O-LIFECYCLEFORCE.
lifecycle_running() { # $1=tid
  [ -f .hermes/harness/task_lifecycle.py ] || return 0
  if ! python3 .hermes/harness/task_lifecycle.py transition --task "$1" --to RUNNING \
    --reason "dispatch" >/dev/null 2>/tmp/lifecycle.err; then
    log "WARN:O-LIFECYCLESM: RUNNING failed for $1 — $(tr '\n' ' ' </tmp/lifecycle.err | head -c 200)"
  fi
}
lifecycle_on_committed() { # $1=tid
  [ -f .hermes/harness/task_lifecycle.py ] || return 0
  local _wave=B _cls _tip=""
  _cls=$(task_class "$1" 2>/dev/null || echo rewrite)
  case "$_cls" in
    infer) if is_characterization_task "$1" 2>/dev/null; then _wave=A; fi ;;
  esac
  if is_characterization_task "$1" 2>/dev/null; then _wave=A; _cls=infer; fi
  # O-ADVANCETIPSHA: bind observation to newest ${tid}: tip (not a stale ledger sha).
  _tip=$(git log -1 --format=%H -E --grep="^${1}:" 2>/dev/null || true)
  if python3 .hermes/harness/task_lifecycle.py on-committed --task "$1" \
    ${_tip:+--tip "$_tip"} \
    --wave "$_wave" --class "$_cls" >/tmp/lifecycle-on-committed.txt 2>/tmp/lifecycle.err; then
    log "O-LIFECYCLESM: $(tr '\n' ' ' </tmp/lifecycle-on-committed.txt | head -c 160)"
    if grep -q 'O-ADVANCETIPSHA' /tmp/lifecycle.err 2>/dev/null; then
      log "O-ADVANCETIPSHA: $(tr '\n' ' ' </tmp/lifecycle.err | head -c 160)"
    fi
  else
    log "WARN:O-LIFECYCLESM: on-committed failed for $1 — $(tr '\n' ' ' </tmp/lifecycle.err | head -c 200)"
  fi
}
lifecycle_blocked() { # $1=tid $2=reason [$3=blocked_on unit/task]
  [ -f .hermes/harness/task_lifecycle.py ] || return 0
  local _on="${3:-}"
  # Default blocked_on = first token of reason when it looks like a task/unit id
  if [ -z "$_on" ]; then
    _on=$(printf '%s' "${2:-}" | awk '{print $NF}' | tr -d ',;')
  fi
  if ! python3 .hermes/harness/task_lifecycle.py transition --task "$1" --to BLOCKED \
    --reason "${2:-blocked}" --blocked-on "${_on:-unknown}" \
    >/dev/null 2>/tmp/lifecycle.err; then
    log "WARN:O-LIFECYCLESM: BLOCKED failed for $1 — $(tr '\n' ' ' </tmp/lifecycle.err | head -c 200)"
  fi
}
lifecycle_debt() { # $1=tid $2=reason
  [ -f .hermes/harness/task_lifecycle.py ] || return 0
  if ! python3 .hermes/harness/task_lifecycle.py transition --task "$1" --to DEBT \
    --reason "${2:-debt}" >/dev/null 2>/tmp/lifecycle.err; then
    log "WARN:O-LIFECYCLESM: DEBT failed for $1 — $(tr '\n' ' ' </tmp/lifecycle.err | head -c 200)"
  fi
}
# ADR-48 (b) — typed REOPEN (never --force). $2=reason ∈ REOPEN_REASONS.
lifecycle_reopen() { # $1=tid $2=reason
  [ -f .hermes/harness/task_lifecycle.py ] || return 0
  if ! python3 .hermes/harness/task_lifecycle.py reopen --task "$1" \
    --reason "${2:-operator}" >/tmp/lifecycle-reopen.txt 2>/tmp/lifecycle.err; then
    log "WARN:O-LIFECYCLEREOPEN: reopen failed for $1 — $(tr '\n' ' ' </tmp/lifecycle.err | head -c 200)"
    return 1
  fi
  log "O-LIFECYCLEREOPEN: $(tr '\n' ' ' </tmp/lifecycle-reopen.txt | head -c 160)"
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

# O-OWNSTAGEALL / O-PARTIALADV — declared Target paths present on disk but
# missing from the index → refuse silent partial tip (W4-346/W4-288).
ownstage_missing_declared() { # $1=tid → prints missing paths, rc=1 if any
  local tid="${1:-}"
  local _tf="${TASKS_FILE:-${STORY_TASKS:-}}"
  local p
  [ -n "$tid" ] && [ -f "$_tf" ] && [ -f .hermes/harness/task-stage-paths.py ] || return 0
  while IFS= read -r p; do
    [ -n "$p" ] || continue
    # O-OWNSTAGEDIR: directories are never tip entries — ignore (pair task-stage-paths).
    [ -d "$p" ] && [ ! -L "$p" ] && continue
    # Only care about files that exist (worker produced them).
    if [ -e "$p" ] || [ -L "$p" ]; then
      if ! git diff --cached --name-only 2>/dev/null | grep -Fxq -- "$p"; then
        # Also treat untracked/modified working tree as missing if not staged.
        if git status --porcelain -- "$p" 2>/dev/null | grep -q .; then
          echo "$p"
        elif ! git ls-files --error-unmatch -- "$p" >/dev/null 2>&1; then
          echo "$p"
        fi
      fi
    fi
  done < <(python3 .hermes/harness/task-stage-paths.py "$_tf" "$tid" 2>/dev/null || true)
}

# O-PARTIALADV — claimed-complete tasks whose declared Targets are still
# dirty/?? → refuse silent skip/advance (partial tip).
# O-PARTIALADVCOLLAB: uncommitted later-task dirt (Pet/Owner co-harvest, or
# T-008 still in BATCH while iterating T-009) must NOT HOLD — only flag when
# committed(T) is true and Target dirt remains.
partial_adv_blockers() { # optional $1=current tid; prints "T-NNN\tpath"; rc=1 if any
  local cur="${1:-}"
  local _tf="${TASKS_FILE:-${STORY_TASKS:-}}"
  local t p
  [ -f "$_tf" ] && [ -f .hermes/harness/task-stage-paths.py ] || return 0
  for t in ${TASK_IDS:-}; do
    if [ -n "$cur" ]; then
      [ "$t" = "$cur" ] && break
    fi
    # Only claimed-complete + leftover dirt (false skip / partial tip).
    committed "$t" 2>/dev/null || continue
    while IFS= read -r p; do
      [ -n "$p" ] || continue
      if [ -e "$p" ] || [ -L "$p" ]; then
        if git status --porcelain -- "$p" 2>/dev/null | grep -qE '^\?\?|^ M|^M |^A |^AM|^MM'; then
          printf '%s\t%s\n' "$t" "$p"
        fi
      fi
    done < <(python3 .hermes/harness/task-stage-paths.py "$_tf" "$t" 2>/dev/null || true)
  done
}

stage_for_task_commit() {
  # Optional $1 = T-NNN (else CURRENT_TASK). O-OWNSTAGE: when the task
  # declares Owns/Target paths, stage only those — never git add -A scoop of
  # sibling entities (S02 T-009 Owner tip bundled Pet+Visit).
  # O-OWNSTAGEALL: task-stage-paths.py must emit *all* multi-line Target src
  # paths; we then refuse tip if any on-disk declared Target stays unstaged.
  restore_frozen_specs
  # O-POMDISCARD: refuse to stage pom-only orphan panache/spring-data deps
  # when src/ has no matching usage (burned-seat leftover).
  discard_orphan_pom "stage"
  local tid="${1:-${CURRENT_TASK:-}}"
  local allow_n=0
  local p
  local _ownstage_paths=""
  if [ -n "$tid" ] && [ -n "${TASKS_FILE:-${STORY_TASKS:-}}" ] \
    && [ -f "${TASKS_FILE:-${STORY_TASKS}}" ] \
    && [ -f .hermes/harness/task-stage-paths.py ]; then
    local _tf="${TASKS_FILE:-${STORY_TASKS}}"
    local _paths
    _paths=$(python3 .hermes/harness/task-stage-paths.py "$_tf" "$tid" 2>/dev/null || true)
    _ownstage_paths="$_paths"
    if [ -n "$_paths" ]; then
      # Drop prior index so siblings staged earlier cannot ride along.
      git reset -q 2>/dev/null || true
      while IFS= read -r p; do
        [ -n "$p" ] || continue
        if [ -e "$p" ] || [ -L "$p" ]; then
          git add -- "$p" 2>/dev/null || true
          allow_n=$((allow_n + 1))
        else
          # Owned path deleted in the working tree — stage the deletion.
          git add -u -- "$p" 2>/dev/null || true
          allow_n=$((allow_n + 1))
        fi
      done <<EOF
$_paths
EOF
      if [ "$allow_n" -gt 0 ]; then
        log "stage: O-OWNSTAGE allowlist ${tid%% *} (${allow_n} path-ops)"
      fi
    fi
  fi
  if [ "$allow_n" -eq 0 ]; then
    # O-ATTRSWEEP / O-VERIFYCREATE: empty allowlist for Shape=verify means
    # do NOT fall back to git add -A (that scoops prior-task leftovers into
    # the wrong tip). Leave index empty → caller must escalate/honest-fail.
    if [ -n "$tid" ] && [ -n "${_ownstage_paths+x}" ] \
      && [ -f .hermes/harness/task-stage-paths.py ]; then
      # Distinguisher: python ran and returned empty vs paths missing entirely.
      if python3 .hermes/harness/task-stage-paths.py \
           "${TASKS_FILE:-${STORY_TASKS}}" "$tid" >/dev/null 2>&1 \
        && [ -z "$_ownstage_paths" ]; then
        log "stage: O-ATTRSWEEP — empty Ownstage allowlist for ${tid%% *} (no create Targets); refusing git add -A scoop"
        git reset -q 2>/dev/null || true
      else
        git add -A
      fi
    else
      # No declared Owns/Target (or no task context) — legacy full stage + reset.
      git add -A
    fi
  fi
  # O-STRUCTPRESAT: never sweep O-DESTBASE inventory into T-NNN tips
  # (false structure-non-gitkeep after valid .gitkeep — W4 T-003).
  # O-ARCHIVESTAGE: never scoop O-TMPARCHIVE forensic trees into T-NNN tips
  # (S03 T-001 d7bde2a bundled 47 run-archives files with spring-tx harvest).
  # O-STAMPGITIGN: never scoop m3-all stamps / run-log / evidence bookkeeping.
  git reset -q -- .hermes migration/staging \
    migration/mta-findings-current.json \
    migration/scaffold-presatisfied.generated.txt \
    migration/scaffold-presatisfied.txt \
    migration/run-archives run-archives \
    migration/.m3-all-stamps migration/run-log.md \
    migration/evidence-liveness.md migration/discovered.md \
    migration/mta-findings-after.json 2>/dev/null || true
  # Belt: never stage frozen complete-story specs even if restore raced.
  for d in $(frozen_spec_paths); do
    git reset -q HEAD -- "$d" 2>/dev/null || true
    git checkout -q HEAD -- "$d" 2>/dev/null || true
  done
  # O-POMDISCARD belt: if pom still staged with panache/spring-data but src
  # has no usage, unstage + revert pom so tip cannot scoop orphan deps.
  if git diff --cached --name-only 2>/dev/null | grep -qx 'pom.xml'; then
    if ! { [ -d src/main/java ] && grep -RqlE \
        'io\.quarkus\.hibernate\.orm\.panache|PanacheRepository|org\.springframework\.data' \
        src/main/java --include='*.java' 2>/dev/null; }; then
      if git show ":pom.xml" 2>/dev/null | grep -Eqi \
          'quarkus-hibernate-orm-panache|hibernate-orm-panache|spring-data'; then
        log "stage: O-POMDISCARD — unstaging/reverting orphan pom.xml from tip"
        git reset -q HEAD -- pom.xml 2>/dev/null || true
        git checkout -q HEAD -- pom.xml 2>/dev/null || true
      fi
    fi
  fi
  # O-OWNSTAGEALL: refuse partial stage — produced∩declared must be staged.
  if [ -n "$tid" ] && [ -n "$_ownstage_paths" ]; then
    local _miss
    _miss=$(ownstage_missing_declared "$tid" | tr '\n' ' ')
    if [ -n "${_miss// /}" ]; then
      log "stage: O-OWNSTAGEALL REFUSE — declared Targets on disk but unstaged: ${_miss}"
      git reset -q 2>/dev/null || true
    fi
  fi
}

# O-HOTSWAPRELOAD (R-227 / T-011): pause for /tmp/harness-update, then EXIT
# so outer-loop re-execs a fresh supervisor. In-process resume keeps stale
# function bodies — O-T1FINDESC was on disk but never ran live (T-011 tip
# still swept findings; zero O-T1FINDESC log lines in supervisor.log).
# Leaves harness-update-ack + hotswap-inflight; does NOT write supervisor-done.
#
# O-HOTSWAPSTALE: a zero-byte /tmp/harness-update with on-disk supervisor
# md5 matching this process's SUPERVISOR_VERSION means deploy already
# applied (or never needed) — auto-clear instead of parking the run.
# Arm harness-update *after* syncing new harness bytes so md5 differs.
hotswap_pause_gate() {
  local tag="${1:-}"
  local saw_update=0
  local cur_md5
  while [ -f /tmp/supervisor-pause ] || [ -f /tmp/harness-update ]; do
    # O-HOTSWAPSTALE — empty marker + md5 parity → clear and continue
    if [ -f /tmp/harness-update ] && [ ! -s /tmp/harness-update ]; then
      cur_md5=$(md5sum "$0" 2>/dev/null | cut -c1-8)
      if [ -n "$cur_md5" ] && [ "$cur_md5" = "$SUPERVISOR_VERSION" ]; then
        if [ -n "$tag" ]; then
          log "$tag: O-HOTSWAPSTALE zero-byte harness-update + md5 parity ($cur_md5) — auto-clear"
        else
          log "O-HOTSWAPSTALE: zero-byte harness-update + supervisor md5 parity ($cur_md5) — auto-clear"
          outer_log "         O-HOTSWAPSTALE: cleared stale zero-byte harness-update (md5 parity)"
        fi
        rm -f /tmp/harness-update
        if [ -f /tmp/harness-update-ack ]; then
          rm -f /tmp/supervisor-pause /tmp/harness-update-ack /tmp/hotswap-inflight
        fi
        continue
      fi
    fi
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

# O-T1FINDESC (R-223) / O-SHIPFIXFINDINGS / O-SFIXFINDINGS: MiniMax/Hermes may
# `git commit` directly and bypass stage_for_task_commit, sweeping
# mta-findings*.json into a T-NNN, sensor-fix, or Preflight/Gate/Build tip
# (S03 T-007; S02 T-004-sfix findings-only while fidelity RED). If HEAD
# includes those paths, rewrite without them — or drop findings-only tips.
_findings_inventory_path() { # stdin paths → 0 if line is findings inventory
  grep -qE '^migration/(mta-findings[^/]*\.json|findings-delta\.txt)$'
}
scrub_findings_from_tip() {
  local msg files nonfind p
  files=$(git diff-tree --no-commit-id --name-only -r HEAD 2>/dev/null || true)
  [ -n "$files" ] || return 0
  echo "$files" | grep -qE '^migration/(mta-findings[^/]*\.json|findings-delta\.txt)$' || return 0
  # Rewrite task + sensor-fix + ship-correction tips — never chore/debt/run-report.
  # Note: ids are T-007 (hyphen), not T007 — do not use ^(T|S)[0-9]+.
  git log -1 --format=%s | grep -qE \
    '^(T-[0-9]+[A-Za-z]*|S[0-9]+(-TC-[A-Za-z0-9]+)?|Preflight fix|Gate fix|Build fix|Deploy fix)(:| sensor fix:| sensor autofix:)' \
    || return 0
  nonfind=""
  while IFS= read -r p; do
    [ -n "$p" ] || continue
    echo "$p" | _findings_inventory_path && continue
    nonfind="${nonfind}${nonfind:+ }$p"
  done <<< "$files"
  msg=$(git log -1 --format=%B)
  if [ -z "$nonfind" ]; then
    # O-SFIXFINDINGS: findings-JSON-only tip cannot clear fidelity/package/compile
    log "O-SFIXFINDINGS: tip is findings-inventory-only — dropping tip (not a code fix)"
    git reset --hard HEAD~1 >>"$LOG" 2>&1 || git reset --soft HEAD~1 >>"$LOG" 2>&1 || true
    return 0
  fi
  log "O-T1FINDESC/O-SHIPFIXFINDINGS/O-SFIXFINDINGS: tip includes findings inventory — rewriting without it"
  # Soft-reset then rebuild the index from non-findings paths only (unstage+
  # recommit was still sweeping findings on some git versions).
  git reset --soft HEAD~1 >>"$LOG" 2>&1 || return 0
  git reset -q HEAD >>"$LOG" 2>&1 || true
  while IFS= read -r p; do
    [ -n "$p" ] || continue
    echo "$p" | _findings_inventory_path && continue
    git add -- "$p" 2>/dev/null || true
  done <<< "$files"
  # Restore findings inventory bytes to parent tip (not staged).
  while IFS= read -r p; do
    [ -n "$p" ] || continue
    echo "$p" | _findings_inventory_path || continue
    git checkout -q HEAD -- "$p" 2>/dev/null || true
  done <<< "$files"
  if git diff --cached --quiet 2>/dev/null; then
    log "O-SFIXFINDINGS: WARN — tip empty after findings unstage; tip dropped"
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
  git log -1 --format=%s | grep -qE '^(T-[0-9]+[A-Za-z]*|S[0-9]+|M3 revision):' || return 0
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
  # O-ESCWFINDINGS / O-T1FINDINGS: mta-findings-current is harness inventory —
  # never a T-NNN deliverable. Counting it as app dirt blocks O-ESCW and forces
  # MiniMax to tip a findings-only commit (then O-T1FINDESC undoes it → false
  # advance on prior HEAD). Exclude alongside .hermes/ and migration/staging/.
  # O-ESCWVERIFYABS / O-ARCHIVESTAGE: migration/run-archives is forensic scoop —
  # never a task deliverable; untracked archives must not block ESCW allow-empty
  # (Wave4 S03 T-000: Qwen verify-absent rc=0 → MiniMax because ?? run-archives).
  git status --porcelain --untracked-files=all 2>/dev/null | awk '{
    p=$2
    if ($1 ~ /^R/ || $1 ~ /^C/) {
      for (i=1;i<=NF;i++) if ($i=="->") { p=$(i+1); break }
    }
    if (p !~ /^\.hermes\// && p !~ /^migration\/staging\// \
        && p !~ /^migration\/run-archives(\/|$)/ && p !~ /^run-archives(\/|$)/ \
        && p != "migration/mta-findings-current.json") print p
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

# O-STYLEFIDELITY: stage only post-autofix diffs under src/ — never git add -A
# (W4-054a: stage_for_task_commit scooped dirty evaluate leftovers like
# Set.copyOf / role.setUser into a "deterministic style-autofix" tip).
style_autofix_stage() {
  # Optional $1 = tip prefix (T-NNN / M5 evaluate) for O-CHARPIN / O-SFIXPATHS.
  local prefix="${1:-${CURRENT_TASK:-}}"
  discard_staging_autofix
  restore_frozen_specs
  git reset -q 2>/dev/null || true
  # O-AUTOFIXJSON / O-T1FINDINGS: never leave findings inventory staged for autofix.
  git reset -q HEAD -- migration/mta-findings-current.json \
    migration/mta-findings-after.json migration/findings-delta.txt 2>/dev/null || true
  local f
  while IFS= read -r f; do
    [ -n "$f" ] || continue
    case "$f" in
      migration/staging/*|.hermes/*|migration/mta-findings*|migration/findings-delta.txt) continue ;;
      # O-CHARPIN / O-SFIXPATHS: characterization pins are style-exempt unless
      # this tip owns the char task (prefix matches T-NNN that Targets the file).
      *CharacterizationTest.java|*CharacterizationTests.java)
        if ! echo "$prefix" | grep -qE '^T-[0-9]+'; then
          log "style-autofix: O-CHARPIN — reverting ${f} (non-task autofix must not mutate char pins)"
          git checkout -q -- "$f" 2>/dev/null || true
          continue
        fi
        # Task tip: only stage if this task's Ownstage list includes the file.
        if [ -f .hermes/harness/task-stage-paths.py ] \
          && [ -n "${TASKS_FILE:-${STORY_TASKS:-}}" ]; then
          if ! python3 .hermes/harness/task-stage-paths.py \
               "${TASKS_FILE:-${STORY_TASKS}}" "$prefix" 2>/dev/null \
               | grep -Fxq -- "$f"; then
            log "style-autofix: O-SFIXPATHS — reverting ${f} (not in ${prefix} Targets)"
            git checkout -q -- "$f" 2>/dev/null || true
            continue
          fi
        fi
        git add -- "$f" 2>/dev/null || true
        ;;
      src/*) git add -- "$f" 2>/dev/null || true ;;
    esac
  done < <(git diff --name-only -- src/ 2>/dev/null; git ls-files --others --exclude-standard -- src/ 2>/dev/null)
}

# O-AUTOFIXJSON: autofix tip must stage ≥1 src/ path — never findings-JSON-only.
autofix_commit_or_refuse() { # $1=commit-message → 0 committed / 1 refused
  local msg="$1" staged
  staged=$(git diff --cached --name-only 2>/dev/null || true)
  if [ -z "$staged" ]; then
    return 1
  fi
  if ! echo "$staged" | grep -qE '^src/'; then
    log "O-AUTOFIXJSON: refuse sensor-autofix tip without src/ (staged=$(echo "$staged" | tr '\n' ','))"
    git reset -q 2>/dev/null || true
    return 1
  fi
  # Belt: drop any findings inventory that snuck into the index.
  while IFS= read -r p; do
    [ -n "$p" ] || continue
    echo "$p" | _findings_inventory_path || continue
    git reset -q HEAD -- "$p" 2>/dev/null || true
  done <<< "$staged"
  if ! git diff --cached --name-only 2>/dev/null | grep -qE '^src/'; then
    log "O-AUTOFIXJSON: refuse — nothing but findings inventory after scrub"
    git reset -q 2>/dev/null || true
    return 1
  fi
  git commit -q -m "$msg" 2>/dev/null || return 1
  scrub_findings_from_tip
  return 0
}

# O-STYLEFIDELITY: park pre-existing src/ dirt so OpenRewrite cannot commit
# evaluate leftovers; archive under /tmp/strays (not restored — sfix starts clean).
park_src_dirt_for_autofix() { # $1=tag
  local tag="$1" arch dirt
  dirt=$(git status --porcelain -- src/ 2>/dev/null || true)
  [ -n "$dirt" ] || return 0
  arch="/tmp/strays/${tag}-pre-autofix-dirt-$(date -u +%Y%m%dT%H%M%SZ)"
  mkdir -p "$arch"
  printf '%s\n' "$dirt" >"$arch/status.txt"
  git diff -- src/ >"$arch/dirty.diff" 2>/dev/null || true
  git diff --cached -- src/ >"$arch/cached.diff" 2>/dev/null || true
  # Copy untracked src files into archive before clean.
  git ls-files --others --exclude-standard -- src/ 2>/dev/null \
    | while IFS= read -r f; do
        [ -n "$f" ] || continue
        mkdir -p "$arch/$(dirname "$f")"
        cp -a "$f" "$arch/$f" 2>/dev/null || true
      done
  log "$tag: O-STYLEFIDELITY — parking pre-autofix src/ dirt → $arch (not scooped into autofix tip)"
  event "$tag" 0 style_autofix_park_dirt "$arch"
  git checkout -q -- src/ 2>/dev/null || true
  git clean -fdq -- src/ 2>/dev/null || true
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
# O-PIDREG: wait/reap REGISTERED sessions only — never pkill -x opencode.
wait_for_worker() {
  session_wait_registered "$WORKER_WAIT_CAP" log
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

# O-ESCREOPENCODE / O-ESCREOPENCODE-ENFORCE / O-ESCREOPENCODE-SENSORRED:
# after wedge/thrash/INFERABSENT/CHARORACLE OR sensor-red / O-STEPFINISHRED
# (false-complete under SENSOR RED), MiniMax owns file edits — do not
# re-dispatch OpenCode/Qwen (Wave4 W4-100a: V7 "Prefer opencode" nursed
# hollow Panache after harvest-only → O-STEPFINISHRED).
escreopencode_should() { # $1=task id (T-NNN)
  local T="$1" cause_file
  [ -n "$T" ] || return 1
  [ -f "/tmp/escalation-no-opencode-${T}" ] && return 0
  if [ -f "$(oc_seat_base "$T").err" ] \
    && grep -qiE 'O-INFERABSENT|JSON_STALE|READ_THRASH|TRUNCATION|O-WORKERREAD|O-WORKERWEDGE|O-CHARORACLE|O-STEPFINISHRED' \
      "$(oc_seat_base "$T").err" 2>/dev/null; then
    return 0
  fi
  # O-ESCREOPENCODE-SENSORRED: cause file / sensor log after false-complete.
  cause_file="/tmp/escalation-cause-${T}.txt"
  if [ -f "$cause_file" ] \
    && head -1 "$cause_file" 2>/dev/null | grep -qiE '^sensor-red$'; then
    return 0
  fi
  if [ -f "$(oc_seat_base "$T").err" ] \
    && grep -qiE 'SENSOR RED|task sensor RED' \
      "$(oc_seat_base "$T").err" 2>/dev/null; then
    return 0
  fi
  if [ -f /tmp/worker-wedge-skip ] \
    && grep -qxF "$(echo "${STORY_SPEC_PREFIX:-run}" | awk '{print $1}')" \
      /tmp/worker-wedge-skip 2>/dev/null; then
    return 0
  fi
  return 1
}

# Arm deny-shim + marker so orch() refuses/kills a second opencode seat.
arm_escreopencode() { # $1=task id
  local T="$1"
  [ -n "$T" ] || return 0
  printf '%s\n' "$T" > "/tmp/escalation-no-opencode-${T}"
  printf '%s\n' "$T" > /tmp/escalation-no-opencode-active
  mkdir -p /tmp/escreopencode-deny
  cat > /tmp/escreopencode-deny/opencode <<'SH'
#!/usr/bin/env bash
# O-ESCREOPENCODE-ENFORCE — PATH refuse during MiniMax-owned escalation.
echo "O-ESCREOPENCODE-ENFORCE: refused opencode during MiniMax-owned escalation (do not re-dispatch wedged worker). Own edits with MiniMax tools, or O-NULLACTION via /tmp/escalation-noaction-<tid>.txt" >&2
exit 75
SH
  chmod +x /tmp/escreopencode-deny/opencode
}

# Kill MiniMax-spawned opencode during O-ESCREOPENCODE escalation.
# Intentional exception to O-PIDREG "finding, not killing" — prompt-only
# forbid was insufficient (Wave4 S03 T-002 reopened Qwen invent path).
escreopencode_kill_spawned() { # $1=task id $2=hermes wpid
  local T="$1" hermes_pid="$2" opid pgid hpgid
  command -v pgrep >/dev/null 2>&1 || return 0
  for opid in $(pgrep -x opencode 2>/dev/null || true); do
    [[ "$opid" =~ ^[0-9]+$ ]] || continue
    # Never kill the hermes session pid itself (not named opencode anyway).
    [ "$opid" = "$hermes_pid" ] && continue
    # Prefer group kill when opencode shares hermes pgid (tool child).
    pgid=$(ps -o pgid= -p "$opid" 2>/dev/null | tr -d ' ')
    hpgid=$(ps -o pgid= -p "$hermes_pid" 2>/dev/null | tr -d ' ')
    log "$T: O-ESCREOPENCODE-ENFORCE — killing MiniMax-spawned opencode pid=${opid} (pgid=${pgid:-?})"
    event "$T" 0 escreopencode_enforce "pid=${opid}"
    printf '%s tag=%s pid=%s sig=TERM cause=escreopencode-enforce\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "escre-${T}" "$opid" \
      >>"${KILL_LEDGER:-/tmp/kill-ledger.log}" 2>/dev/null || true
    if [[ -n "$pgid" && -n "$hpgid" && "$pgid" == "$hpgid" ]]; then
      kill -TERM "$opid" 2>/dev/null || true
      sleep 1
      kill -KILL "$opid" 2>/dev/null || true
    else
      kill -TERM -- "-$opid" 2>/dev/null || kill -TERM "$opid" 2>/dev/null || true
      sleep 1
      kill -KILL -- "-$opid" 2>/dev/null || kill -KILL "$opid" 2>/dev/null || true
    fi
    printf '%s tag=%s pid=%s sig=KILL cause=escreopencode-enforce-kill\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "escre-${T}" "$opid" \
      >>"${KILL_LEDGER:-/tmp/kill-ledger.log}" 2>/dev/null || true
  done
}

orch() { # $1=tag $2=prompt ; logs to /tmp/sup-<tag>.log ; returns rc
  local tag="$1" prompt="$2" t0 t1 rc wpid
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
  # O-ESCREOPENCODE-ENFORCE: when marker armed for this T-NNN, PATH-deny
  # opencode for the Hermes child and kill any absolute-path spawn.
  local esc_enforce=0 enforce_tid="" watch_pid="" save_path="$PATH"
  if [[ "$tag" =~ ^(T-[0-9]+[A-Za-z]*) ]]; then
    enforce_tid="${BASH_REMATCH[1]}"
    if [ -f "/tmp/escalation-no-opencode-${enforce_tid}" ]; then
      esc_enforce=1
      arm_escreopencode "$enforce_tid"
      export PATH="/tmp/escreopencode-deny:${PATH}"
      log "$tag: O-ESCREOPENCODE-ENFORCE armed — opencode spawn denied/killed this escalation"
    fi
  fi
  # O-PIDREG/O-OCGROUP: setsid + register + group-TERM at end.
  setsid timeout "$budget" hermes chat --provider "$ORCH_PROVIDER" --model "$ORCH_MODEL" -q "$prompt" \
    > "/tmp/sup-${tag}.log" 2>&1 &
  wpid=$!
  # Restore supervisor PATH immediately — only the Hermes child inherits deny.
  PATH="$save_path"
  export PATH
  session_register "$tag" "$wpid"
  if [ "$esc_enforce" -eq 1 ]; then
    (
      while kill -0 "$wpid" 2>/dev/null; do
        escreopencode_kill_spawned "$enforce_tid" "$wpid"
        sleep 3
      done
    ) &
    watch_pid=$!
  fi
  # O-TASKHB: pulse OUTER_LOG while MiniMax/Hermes seat runs (was silent for
  # multi-minute escalations — demo looked stuck on ▶ TASK).
  local _hb_elapsed=0 _hb_detail=""
  while kill -0 "$wpid" 2>/dev/null; do
    sleep "$TASK_HEARTBEAT_SECS"
    if ! kill -0 "$wpid" 2>/dev/null; then
      break
    fi
    _hb_elapsed=$(( $(date +%s) - t0 ))
    _hb_detail="details /tmp/sup-${tag}.log"
    if grep -qE "429|Too Many Requests|Rate limit|rate.?limit" \
         "/tmp/sup-${tag}.log" 2>/dev/null; then
      task_hb "$tag" "orchestrator" "$_hb_elapsed" \
        "waiting on MiniMax rate limit — ${_hb_detail}"
    else
      task_hb "$tag" "orchestrator" "$_hb_elapsed" "$_hb_detail"
    fi
  done
  wait "$wpid"
  rc=$?
  if [ -n "$watch_pid" ]; then
    kill "$watch_pid" 2>/dev/null || true
    wait "$watch_pid" 2>/dev/null || true
    # Final sweep after Hermes exit (race: spawn just before exit).
    escreopencode_kill_spawned "$enforce_tid" "$wpid"
  fi
  session_reap_group "$tag" "$wpid" "session-end"
  t1=$(date +%s)
  echo "${tag},${t0},${t1},$((t1-t0)),rc=${rc}" >> "$METRICS"
  [ $((t1-t0)) -gt 1800 ] && { event "$tag" 0 slow_session "$((t1-t0))s"; log "$tag: SLOW session ($((t1-t0))s) — wedge candidate"; }
  return $rc
}

# O-SFIXWORKER: freeform OpenCode seat for sensor-fix. Same FIX_TIMEOUT as
# MiniMax sfix. Caller re-runs the triggering sensor to decide rescue.
# O-SFIXMUTATE: for *sfix* tags, poll oc-json and early-kill diagnose-freeze
# (0 edit/write past SFIX_MUTATE_DEADLINE_SECS, default 120) so MiniMax rescue
# is not blocked by a full FIX_TIMEOUT burn.
run_worker_prompt() { # $1=tag $2=prompt ; logs $(oc_seat_base <tag>).{json,err}
  local tag="$1" prompt="$2" t0 t1 rc budget wpid
  wait_for_worker
  t0=$(date +%s)
  budget="${FIX_TIMEOUT:-900}"
  : > "$(oc_seat_base "$tag").json"
  : > "$(oc_seat_base "$tag").err"
  log "$tag: Actor: $(worker_label) — OpenCode session → $(oc_seat_base "$tag").json"
  setsid timeout "$budget" opencode run "$prompt" \
    -m "$WORKER_MODEL" --auto --format json \
    -f AGENTS.md \
    > "$(oc_seat_base "$tag").json" 2>"$(oc_seat_base "$tag").err" &
  wpid=$!
  session_register "$tag" "$wpid"
  case "$tag" in
    *sfix*)
      local elapsed=0 last_sz=-1 stale=0 sz thrash
      local mutate_deadline="${SFIX_MUTATE_DEADLINE_SECS:-120}"
      local stale_limit="${SFIX_JSON_STALE_SECS:-180}"
      while kill -0 "$wpid" 2>/dev/null; do
        sleep 30
        elapsed=$((elapsed + 30))
        sz=$(stat -c%s "$(oc_seat_base "$tag").json" 2>/dev/null || echo 0)
        if [ "$sz" -eq "$last_sz" ]; then
          stale=$((stale + 30))
        else
          stale=0
          last_sz=$sz
        fi
        # O-TASKHB: every ~60s on the 30s sfix poll cadence.
        if [ $((elapsed % 60)) -eq 0 ]; then
          task_hb "$tag" "worker" "$elapsed" \
            "sfix json=${sz}B — details $(oc_seat_base "$tag").json"
        fi
        # Tighter read-thrash + mutate deadline for sfix (O-SFIXMUTATE).
        if [ -f .hermes/harness/worker-read-watch.py ]; then
          thrash=$(
            WORKER_READ_GLOB_MAX="${SFIX_READ_GLOB_MAX:-8}" \
            WORKER_MUTATE_DEADLINE_SECS="$mutate_deadline" \
            python3 .hermes/harness/worker-read-watch.py \
              "$(oc_seat_base "$tag").json" "$elapsed" 2>/dev/null || true
          )
          if [ -n "$thrash" ]; then
            log "$tag: O-SFIXMUTATE — ${thrash} — killing early for rescue/escalate"
            {
              echo "sfix diagnose-freeze — ${thrash} (O-SFIXMUTATE)"
              echo "abort: 0 edit/write after diagnose budget — escalate to MiniMax rescue"
            } >> "$(oc_seat_base "$tag").err"
            event "$tag" 0 sfix_mutate_kill "$thrash"
            harness_kill_group "$tag" "$wpid" TERM "sfix-mutate"
            sleep 2
            harness_kill_group "$tag" "$wpid" KILL "sfix-mutate-kill"
            break
          fi
        fi
        if [ "$stale" -ge "$stale_limit" ]; then
          log "$tag: O-SFIXMUTATE — oc-json frozen ${stale}s@${sz}B — killing early"
          {
            echo "sfix wedged — no session JSON growth for ${stale}s (O-SFIXMUTATE)"
            echo "session JSON size frozen at ${sz} bytes"
          } >> "$(oc_seat_base "$tag").err"
          event "$tag" 0 sfix_json_stale "${stale}s"
          harness_kill_group "$tag" "$wpid" TERM "sfix-json-stale"
          sleep 2
          harness_kill_group "$tag" "$wpid" KILL "sfix-json-stale-kill"
          break
        fi
        if [ -f /tmp/supervisor-pause ] || [ -f /tmp/debt-freeze ]; then
          local why="supervisor-pause"
          [ -f /tmp/debt-freeze ] && why="debt-freeze"
          harness_kill_group "$tag" "$wpid" TERM "$why"
          sleep 2
          harness_kill_group "$tag" "$wpid" KILL "${why}-kill"
          break
        fi
      done
      wait "$wpid" 2>/dev/null
      rc=$?
      ;;
    *)
      wait "$wpid"
      rc=$?
      ;;
  esac
  session_reap_group "$tag" "$wpid" "session-end"
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
    # O-ESCWSCOPEUTIL: scrub *untracked* later-story classes mid-convert
    # (commit-diff alone missed util/EntityUtils before tip).
    local uviol=""
    while IFS= read -r f; do
      [ -n "$f" ] || continue
      bn=$(basename "$f" .java)
      case " ${LATER_CLASSES} " in *" ${bn} "*)
        uviol="$uviol $f"
        ;;
      esac
    done < <(git ls-files --others --exclude-standard -- 'src/main/java' 2>/dev/null \
      | grep '\.java$' || true)
    if [ -n "$uviol" ]; then
      event "scope" 0 later_story_untracked "${uviol# }"
      log "scope sensor: O-ESCWSCOPEUTIL removing untracked later-story class(es):${uviol}"
      outer_log "         SCOPE SCRUB (O-ESCWSCOPEUTIL): removed untracked later-story class(es):${uviol} — keep them in migration/staging until their story"
      {
        echo "O-ESCWSCOPEUTIL removed untracked later-story class(es):${uviol}"
        echo "Do NOT create/harvest util/* or LATER_CLASSES mid-convert — stay on Owns/Target only."
      } > /tmp/scope-violation.txt
      for f in $uviol; do
        rm -f "$f"
      done
    fi
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
      # O-REVERTPURE: stage only reverted paths — never git add -A
      # (v3 T-003: scope revert swept migration/mta-findings-current.json).
      stage_scope_revert_paths $lviol
      if ! git diff --cached --quiet 2>/dev/null; then
        git commit -q -m "${prefix} scope revert: removed later-story class(es) created early (${lviol# })" 2>/dev/null
      fi
    fi
  fi
  # (B) this-story path-scope check --------------------------------------
  if [ -n "${STORY_SCOPE:-}" ]; then
    # Only path-form scope entries are enforceable (V4 first-run catch: M2
    # wrote class FQNs — enforcing those would mass-revert every edit).
    # Enforcement covers src/main/java only: resources (application
    # .properties) are shared story surface, not class ownership.
    local pathscope="" e
    for e in ${STORY_SCOPE}; do case "$e" in src/*) pathscope="$pathscope $e";; esac; done
    if [ -z "$pathscope" ]; then
      log "scope sensor: no path-form scope entries — enforcement skipped (informational scope)"
    else
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
      if [ -n "$viol" ]; then
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
        # O-REVERTPURE: stage only reverted paths — never git add -A
        stage_scope_revert_paths $viol
        if ! git diff --cached --quiet 2>/dev/null; then
          git commit -q -m "${prefix} scope revert: story-scope sensor reverted out-of-scope src/main edits (${viol# })" 2>/dev/null
        fi
      else
        rm -f /tmp/scope-violation.txt
      fi
    fi
  fi
# (C) O-EXECSCOPE — also revert out-of-scope resources + unowned pom.xml
  # (M4 used to only enforce src/main/java; T-003 edited S01 props + pom).
  if [ -n "${STORY_SCOPE:-}" ] && [ -f .hermes/harness/exec-scope.py ] \
    && [ -n "${TASKS_FILE:-}" ] && [ -f "$TASKS_FILE" ]; then
    case "$prefix" in
      T-*)
        local esc_list="" f
        while IFS= read -r f; do
          [ -n "$f" ] || continue
          esc_list="${esc_list}${f}"$'\n'
        done < <(git diff --name-only HEAD~1..HEAD -- src/main/resources pom.xml 2>/dev/null || true)
        if [ -n "$(echo "$esc_list" | tr -d '[:space:]')" ]; then
          if ! printf '%s' "$esc_list" | STORY_SCOPE="$STORY_SCOPE" \
               python3 .hermes/harness/exec-scope.py "$TASKS_FILE" "$prefix" \
               > /tmp/exec-scope.out 2>&1; then
            local esc_viol _raw _f
            esc_viol=$(tr '\n' ' ' </tmp/exec-scope.out)
            log "scope sensor: O-EXECSCOPE revert ${esc_viol}"
            event "scope" 0 exec_scope "${esc_viol}"
            {
              echo "O-EXECSCOPE: tip touched non-test paths outside story scope / Owns"
              echo "$esc_viol"
              echo "Story scope: ${STORY_SCOPE}"
              echo "Stay on Owns/Target or record debt — do not edit later-story props/pom."
            } > /tmp/scope-violation.txt
            _raw=$(grep -E '^O-EXECSCOPE:' /tmp/exec-scope.out | head -1 | sed 's/^O-EXECSCOPE://')
            local _reverts=""
            IFS=',' read -ra _vs <<< "${_raw}"
            for _f in "${_vs[@]}"; do
              _f="${_f// /}"
              [ -n "$_f" ] || continue
              _reverts="${_reverts} ${_f}"
              if git diff --name-only --diff-filter=A HEAD~1..HEAD -- "$_f" 2>/dev/null | grep -q .; then
                git rm -q "$_f" 2>/dev/null || rm -f "$_f"
              else
                git checkout HEAD~1 -- "$_f" 2>/dev/null || true
              fi
            done
            stage_scope_revert_paths ${_reverts}
            if ! git diff --cached --quiet 2>/dev/null; then
              git commit -q -m "${prefix} scope revert: O-EXECSCOPE out-of-scope resources/pom" 2>/dev/null
            fi
          fi
        fi
        ;;
    esac
  fi
  # O-SCOPEBACKFILL / O-STRUCTREVERT: after any scope revert, restore missing
  # structure/.gitkeep Targets so the task is not marked ✓ with deliverable absent.
  scope_structure_backfill "$prefix"
}

# O-EXECSCOPE — pre-commit refuse for staged non-test paths outside STORY_SCOPE.
exec_scope_refuse_staged() { # $1=tid → 0 ok, 1 reset index
  local tid="$1"
  [ -n "$tid" ] || return 0
  [ -n "${STORY_SCOPE:-}" ] || return 0
  [ -f .hermes/harness/exec-scope.py ] || return 0
  [ -n "${TASKS_FILE:-}" ] && [ -f "$TASKS_FILE" ] || return 0
  case "$tid" in T-*) ;; *) return 0 ;; esac
  if git diff --cached --quiet 2>/dev/null; then
    return 0
  fi
  if git diff --cached --name-only | STORY_SCOPE="$STORY_SCOPE" \
       python3 .hermes/harness/exec-scope.py "$TASKS_FILE" "$tid" \
       > /tmp/exec-scope.out 2>&1; then
    return 0
  fi
  log "$tid: O-EXECSCOPE refuse staged tip — $(tr '\n' ' ' </tmp/exec-scope.out)"
  event "$tid" 0 exec_scope_refuse "$(tr '\n' ' ' </tmp/exec-scope.out)"
  {
    echo "O-EXECSCOPE refused staged non-test paths outside story scope:"
    cat /tmp/exec-scope.out
    echo "Story scope: ${STORY_SCOPE}"
  } > /tmp/scope-violation.txt
  git reset -q
  return 1
}

# O-CHARPROTECT — refuse char tips that only pin /projects/legacy source text.
char_protect_refuse_tip() { # $1=tid → 0 ok, 1 reset HEAD tip
  local tid="$1"
  [ -f .hermes/harness/char-protect.py ] || return 0
  case "$tid" in T-*) ;; *) return 0 ;; esac
  git log -1 --format=%s | grep -qE "^${tid}:" || return 0
  if git show --pretty= --name-only HEAD | python3 .hermes/harness/char-protect.py \
       migration.yaml > /tmp/char-protect.out 2>&1; then
    return 0
  fi
  log "$tid: O-CHARPROTECT — $(tr '\n' ' ' </tmp/char-protect.out) — resetting tip"
  event "$tid" 0 char_protect_reset "$(tr '\n' ' ' </tmp/char-protect.out)"
  git reset --hard HEAD~1 >> "$LOG" 2>&1 || true
  return 1
}

# O-RUNLOGTERM — harness-authored terminal ledger (not model prose).
append_harness_runlog() { # $1=tid $2=status $3=detail
  local tid="$1" status="$2" detail="${3:-}" tip
  mkdir -p migration
  tip=$(git log -1 --oneline 2>/dev/null | head -1 || echo "(no tip)")
  {
    echo
    echo "### Harness terminal — ${tid} — $(date -u +%Y-%m-%dT%H:%MZ)"
    echo "- status: \`${status}\`"
    echo "- tip: \`${tip}\`"
    [ -n "$detail" ] && echo "- detail: ${detail}"
    echo "- note: harness-authored (O-RUNLOGTERM); ignore model 'complete/ready for next' claims"
  } >> migration/run-log.md
  log "$tid: O-RUNLOGTERM append status=${status}"
}

# O-RUNLOGTERM + O-CHARPROTECT after a tip lands (before post_commit_verify).
task_tip_landed() { # $1=tid $2=status $3=detail → 0 ok, 1 char_protect reset
  local tid="$1" status="$2" detail="${3:-}"
  if ! char_protect_refuse_tip "$tid"; then
    append_harness_runlog "$tid" "TIP_RESET_CHARPROTECT" "$detail"
    return 1
  fi
  append_harness_runlog "$tid" "$status" "$detail"
  return 0
}

# O-CHARSONAR — true when task is characterization (force milestone Sonar).
is_characterization_task() { # $1=tid
  local tid="$1" tf="${TASKS_FILE:-${STORY_TASKS:-}}"
  [ -n "$tid" ] && [ -n "$tf" ] && [ -f "$tf" ] || return 1
  python3 - "$tf" "$tid" <<'PY' 2>/dev/null
import re, sys
text = open(sys.argv[1], encoding="utf-8", errors="replace").read()
tid = sys.argv[2]
heads = list(re.finditer(r"^#{2,6}\s+((?:S\d+-TC-[A-Za-z0-9]+|S\d+-T-\d{3}(?:-[A-Za-z0-9]+)?|T[-A-Za-z0-9]*\d+[A-Za-z]*))\s*:\s*(.+)$", text, re.M))
for i, m in enumerate(heads):
    if m.group(1) != tid:
        continue
    title = m.group(2)
    end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
    body = text[m.end():end]
    sys.exit(0 if re.search(r"characteri[sz]", title + "\n" + body, re.I) else 1)
sys.exit(1)
PY
}

# --- Debt ledger (V5 finding #4) --------------------------------------------
# A sensor that stays RED after its fix session is no longer swallowed as a
# bare log line (run-4: a milestone RED "recorded as debt" wrote NO artifact,
# so it reached M5/ship invisibly). Write a durable, reviewable entry to
# migration/debt.md and commit it. This is the record; the M5 ship gate
# INDEPENDENTLY blocks on the factory-uncatchable dimensions (fidelity,
# package) so unresolved debt of those kinds can never ship.
# O-DEBTFRZRACE / O-SFIXDIRTY: orphan untracked or uncommitted poison under
# src/ must not drive debt freeze. Discard src dirt (migration-general —
# no specimen class names).
# O-POMDISCARD (W4-101a): after src/ discard/reset, orphan pom.xml deps
# (e.g. quarkus-hibernate-orm-panache added by a burned seat with no surviving
# Panache src) must not remain dirty for the next git add -A. Migration-
# general — dep artifact names only; no specimen class names.
discard_orphan_pom() { # optional $1=tag
  local tag="${1:-harness}"
  [ -f pom.xml ] || return 0
  git status --porcelain -- pom.xml 2>/dev/null | grep -q . || return 0
  # If src still cites Panache / spring-data convert markers, keep pom dirt.
  if [ -d src/main/java ] && grep -RqlE \
      'io\.quarkus\.hibernate\.orm\.panache|PanacheRepository|org\.springframework\.data' \
      src/main/java --include='*.java' 2>/dev/null; then
    return 0
  fi
  # Orphan dep smell: dirty pom mentions panache (or spring-data) while src
  # has zero matching usage after discard.
  if grep -Eqi 'quarkus-hibernate-orm-panache|hibernate-orm-panache|spring-data' pom.xml 2>/dev/null; then
    log "$tag: O-POMDISCARD — reverting orphan pom.xml (no matching src Panache/Spring Data usage)"
    git checkout -q -- pom.xml 2>/dev/null || true
  fi
}

discard_src_dirt() { # optional $1=tag for log
  local tag="${1:-harness}"
  local had_src=0
  if [ -n "$(git status --porcelain -- src/ 2>/dev/null)" ]; then
    had_src=1
    log "$tag: O-SFIXDIRTY — discarding uncommitted/orphan dirt under src/"
    git checkout -q -- src/ 2>/dev/null || true
    git clean -fdq -- src/ 2>/dev/null || true
  fi
  # Always check orphan pom after any src discard (and when src already clean
  # but pom still dirty from a prior burned seat).
  if [ "$had_src" -eq 1 ] || [ -n "$(git status --porcelain -- pom.xml 2>/dev/null)" ]; then
    discard_orphan_pom "$tag"
  fi
}

# O-SFIXRESCUEDISCARD / O-SFIXSIGINT: when cited sfix dims are GREEN on a
# dirty tree (Qwen or MiniMax rescue), tip that work BEFORE full milestone
# re-verify / O-SFIXDIRTY discard / SIGINT teardown. Full sensors.sh can still
# RED on another dim (or exit 130 mid-findings) — discarding then destroys a
# tip-backed fidelity/sonar win. Uses sfix_loop_recheck (cited dims), not the
# full milestone bundle. Migration-general — no specimen class names.

# O-SFIXTESTPAIR: when fidelity sfix reverts a harvest class to staging, the
# packet must include characterization tests that reference that class — else
# revert ↔ autofix oscillation (fidelity GREEN / tests RED).
sfix_test_pair_note() {
  local classes c tests="" line
  classes=$(
    grep -Eh '^FIDELITY:' /tmp/sensor-fidelity.log /tmp/sensor-milestone.log 2>/dev/null \
      | sed -E 's/^FIDELITY:([^:]+):.*/\1/' \
      | sed -E 's|.*/||; s|\.java$||' \
      | sort -u || true
  )
  [ -n "$classes" ] || return 0
  for c in $classes; do
    while IFS= read -r line; do
      [ -n "$line" ] || continue
      tests="${tests}
  - ${line}"
    done < <(git grep -l --fixed-strings "$c" -- 'src/test/java' 2>/dev/null || true)
  done
  [ -n "$tests" ] || return 0
  cat <<EOF
O-SFIXTESTPAIR: fidelity revert of harvest class(es) [${classes//$'\n'/ }] MUST revise coupled tests in the SAME commit:${tests}
Do not leave characterization asserting autofix-only contracts (e.g. UnsupportedOperationException on Set.copyOf) after reverting to staging return shapes. Verify with: mvn -q test -Dtest=<SimpleNames> then .hermes/harness/sensors.sh fidelity && .hermes/harness/sensors.sh task.
EOF
}

sfix_commit_green_dirt() { # $1=prefix $2=tag $3=SENSOR_KIND → 0 if tip landed
  local prefix="$1" tag="$2" kind="$3"
  [ -n "$(git status --porcelain)" ] || return 1
  if ! sfix_loop_recheck "$kind" >> "$LOG" 2>&1; then
    return 1
  fi
  stage_for_task_commit
  if git diff --cached --quiet 2>/dev/null; then
    return 1
  fi
  if SKIP_SENSOR_GATE=1 git commit -m \
      "${prefix} sensor fix: O-SFIXRESCUEDISCARD tip of ${kind}-green dirty tree" \
      >/dev/null 2>&1; then
    log "$tag: O-SFIXRESCUEDISCARD — mechan-committed ${kind}-GREEN dirty tree $(git log --oneline -1)"
    event "$tag" 0 sfix_rescue_commit "$kind"
    return 0
  fi
  # Commit failed — archive dirt instead of silent wipe (O-SFIXSIGINT safety).
  local _arch="/tmp/strays/${tag}-sfix-green-$(date -u +%Y%m%dT%H%M%SZ)"
  mkdir -p "$_arch"
  git status --porcelain >"$_arch/status.txt" 2>/dev/null || true
  git diff >"$_arch/dirty.diff" 2>/dev/null || true
  git diff --cached >"$_arch/cached.diff" 2>/dev/null || true
  log "$tag: O-SFIXRESCUEDISCARD — commit failed; archived green dirt → $_arch (not discarding yet)"
  event "$tag" 0 sfix_rescue_archive "$kind"
  return 1
}

# O-PREFCONTUT: working-tree @Test count (tracked + untracked). `git grep`
# alone is blind to new untracked *Test.java — the case the floor protects.
count_test_annotations() {
  if [ -d src/test ]; then
    grep -rho --include='*.java' '@Test' src/test 2>/dev/null | wc -l | tr -d ' '
  else
    echo 0
  fi
}

# O-SHIPFIXCOMMIT: preflight/gate/build fix seats often burn the 900s budget on
# sensors.sh sonar AFTER local tests are already GREEN, leaving unpaid
# tests-only dirt for attempt≥2 (which then rewrites — O-PREFCONT). On
# timeout/no_commit, tip task-GREEN dirt when src/main is clean — do not wait
# for full preflight GREEN or attempt exhaustion. Migration-general.
pref_commit_green_dirt() { # $1=prefix $2=tag → 0 if tip landed
  local prefix="$1" tag="$2"
  [ -n "$(git status --porcelain)" ] || return 1
  case "$tag" in
    preflightfix*|gatefix*|buildfix*) ;;
    *) return 1 ;;
  esac
  # Coverage/wiring tips only — refuse if src/main still dirty.
  if [ -n "$(git status --porcelain -- src/main/ 2>/dev/null)" ]; then
    log "$tag: O-SHIPFIXCOMMIT — src/main dirty; defer tip (not tests-only/wiring)"
    return 1
  fi
  # O-SHIPFIXPOM: tip subject claims tests-only — require src/test dirt and
  # stage ONLY src/test/ (never git add -A). Unrelated pom deps (assertj, etc.)
  # must not ride into a "tests-only" mechan tip (W4-066a / fa95d79).
  if [ -z "$(git status --porcelain -- src/test/ 2>/dev/null)" ]; then
    log "$tag: O-SHIPFIXPOM — no src/test dirt; refuse non-test tip (pom/wiring needs agent commit)"
    return 1
  fi
  if git status --porcelain | awk 'NF>=2 {p=$2; if (p !~ /^src\/test\//) found=1} END {exit !found}'; then
    log "$tag: O-SHIPFIXPOM — non-test dirt present (pom/etc); staging src/test only"
  fi
  # Characterization floor (O-PREFCONT / O-PREFCONTUT): refuse tip that shrinks
  # @Test count vs attempt-start snapshot when present (includes untracked).
  if [ -f "/tmp/pref-char-floor-${tag}.txt" ]; then
    local _floor _now
    _floor=$(tr -d '[:space:]' <"/tmp/pref-char-floor-${tag}.txt" 2>/dev/null || echo 0)
    _now=$(count_test_annotations)
    if [ "${_floor:-0}" -gt 0 ] && [ "${_now:-0}" -lt "$_floor" ]; then
      log "$tag: O-PREFCONT — refuse tip; @Test count ${_now} < floor ${_floor}"
      event "$tag" 0 prefcont_floor_refuse "now=${_now};floor=${_floor}"
      return 1
    fi
  fi
  if ! .hermes/harness/sensors.sh task >> "$LOG" 2>&1; then
    log "$tag: O-SHIPFIXCOMMIT — task sensor RED; refuse mid-seat tip (keeps O-SHIPASSERTWEAK etc.)"
    return 1
  fi
  # Stage tests only — do NOT call stage_for_task_commit (git add -A).
  restore_frozen_specs
  git add -- src/test/
  git reset -q -- .hermes migration/staging \
    migration/mta-findings-current.json \
    migration/scaffold-presatisfied.generated.txt \
    migration/scaffold-presatisfied.txt 2>/dev/null || true
  if git diff --cached --quiet 2>/dev/null; then
    return 1
  fi
  if SKIP_SENSOR_GATE=1 git commit -m \
      "${prefix}: O-SHIPFIXCOMMIT tip of task-GREEN tests-only dirt (pre-sonar / seat timeout)" \
      >/dev/null 2>&1; then
    log "$tag: O-SHIPFIXCOMMIT — mechan-committed task-GREEN tests-only dirt $(git log --oneline -1)"
    event "$tag" 0 shipfix_timeout_commit tests_only
    return 0
  fi
  return 1
}

# Snapshot @Test count at attempt start for O-PREFCONT floor checks.
pref_snapshot_char_floor() { # $1=tag
  local tag="$1"
  case "$tag" in
    preflightfix*|gatefix*|buildfix*) ;;
    *) return 0 ;;
  esac
  # O-PREFCONTUT: include untracked new test classes (grep -rho, not git grep).
  count_test_annotations >"/tmp/pref-char-floor-${tag}.txt" 2>/dev/null \
    || echo 0 >"/tmp/pref-char-floor-${tag}.txt"
}

record_debt() { # $1=tag $2=sensor-kind $3=short-reason
  local tag="$1" kind="$2" reason="$3"
  # O-DEBTFRZRACE: before writing debt/freeze for sensor kinds, discard
  # orphan src/ poison and re-run the triggering sensor on a clean tree.
  # False RED from discarded dirt must not freeze (S06 T-001).
  case "$kind" in
    task|milestone|sonar)
      discard_src_dirt "$tag"
      if .hermes/harness/sensors.sh "$kind" >> "$LOG" 2>&1; then
        log "$tag: O-DEBTFRZRACE false-red averted — ${kind} GREEN after clean-tree recheck (not recording debt/freeze)"
        event "$tag" 0 debtfrzrace_averted "$kind"
        return 0
      fi
      ;;
  esac
  [ -f migration/debt.md ] || printf '# Migration debt ledger\n\nUnresolved sensor REDs recorded by the supervisor: each is a defect that\nsurvived its fix session. The M5 ship gate blocks on fidelity/package debt.\n' > migration/debt.md
  # O-DEBTNONE: drop template "(none)" placeholders once a real ## entry exists
  if grep -qE '^\(none\)$|^- \(none\)$|^None\.$' migration/debt.md 2>/dev/null; then
    sed -i.bak -E '/^\(none\)$/d; /^- \(none\)$/d; /^None\.$/d' migration/debt.md 2>/dev/null \
      || sed -i '' -E '/^\(none\)$/d; /^- \(none\)$/d; /^None\.$/d' migration/debt.md
    rm -f migration/debt.md.bak
  fi
  {
    printf '\n## %s — %s RED\n' "$tag" "$kind"
    printf -- '- head: %s\n' "$(git rev-parse --short HEAD 2>/dev/null)"
    printf -- '- reason: %s\n' "$reason"
  } >> migration/debt.md
  # O-DEBTTREE / ADR-48: debt commits are journal-only — never sweep staged src/
  # (f461242 class: bare `git commit` included vacuous UserRepositoryTest restore).
  # --only ignores other staged paths; pathspec limits the tip to debt.md.
  git add -- migration/debt.md 2>/dev/null || true
  if ! git commit -q --only -m "debt: ${tag} ${kind} RED (unresolved)" -- migration/debt.md \
      >>"$LOG" 2>&1; then
    log "$tag: O-DEBTTREE — debt.md commit skipped or empty (path-limited; src/ untouched)"
  elif git log -1 --format=%s 2>/dev/null | grep -qE '^debt:' \
    && git show --name-only --format= HEAD 2>/dev/null | grep -qE '^(src/|pom\.xml$)'; then
    # Soft rewrite: keep working tree, drop polluted tip, recommit journal only.
    log "$tag: O-DEBTTREE — debt tip mutated app tree; soft-rewrite to debt.md only"
    git reset --soft HEAD~1 >>"$LOG" 2>&1 || true
    git restore --staged :/ >>"$LOG" 2>&1 || git reset HEAD >>"$LOG" 2>&1 || true
    git add -- migration/debt.md 2>/dev/null || true
    git commit -q --only -m "debt: ${tag} ${kind} RED (unresolved)" -- migration/debt.md \
      >>"$LOG" 2>&1 || true
  fi
  event "$tag" 0 debt_recorded "$kind"
  # O-DEBTFRZ: unresolved task/milestone debt must FREEZE — not continue to the
  # next task (V9 S04 T-002→T-003 silent advance). Ship-gate fidelity/package
  # debt at M5 still records; freeze applies to in-story task/milestone kinds.
  case "$kind" in
    task|milestone|sonar|seat-budget)
      touch /tmp/debt-freeze
      touch /tmp/supervisor-pause
      # ADR-48 (c) / O-DEBTADVANCE: project freeze-worthy debt into ledger DEBT
      # (ADVANCE→DEBT demotion). Journal append above is the incident trail only.
      lifecycle_debt "$tag" "${kind}: ${reason}"
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

# O-SEATBUDGET / ARCH A5 — escalate when story seats exceed budget × factor.
check_seat_budget_overrun() { # $1=tag (task id or batch label)
  local tag="${1:-seat-budget}" sid="${STORY_ID:-}"
  local sb=".hermes/harness/seat-budget.py"
  [ -n "$sid" ] || return 0
  [ -f "$sb" ] || return 0
  [ -f "/tmp/story-seat-budget-${sid}" ] || return 0
  if python3 "$sb" check-overrun --sid "$sid" >> "$LOG" 2>&1; then
    return 0
  fi
  log "$tag: O-SEATBUDGET OVERRUN — actual seats exceed budget×factor for ${sid} — escalating (debt-freeze)"
  outer_log "         O-SEATBUDGET: OVERRUN ${sid} — debt-freeze (actual > budget×factor)" 2>/dev/null || true
  record_debt "$tag" "seat-budget" \
    "O-SEATBUDGET: actual OpenCode seats exceed kind×incidents budget×factor for ${sid}"
  return 1
}

# O-REVHOLD: review/lead HOLD file blocks story-gate-passed (W4-015d).
# Create migration/HOLD (or /tmp/review-hold) with a reason; remove when cleared.
review_hold_blocks_ship() {
  if [ -f migration/HOLD ] || [ -f /tmp/review-hold ]; then
    local why
    why=$(head -3 migration/HOLD /tmp/review-hold 2>/dev/null | tr '\n' ' ' | head -c 200)
    log "O-REVHOLD: refusing story close — HOLD present (${why:-see migration/HOLD})"
    event "m5-ship" 0 review_hold_block "${why:-HOLD}"
    write_run_report "ship-blocked-review-hold: ${why:-migration/HOLD}"
    echo "review-hold" > /tmp/supervisor-done
    return 0
  fi
  return 1
}

# O-EVIDLIVE: each active K-system ≥1 ledger row per story or story-gate RED.
# Heartbeat fills legitimate-none channels (K9 none, K11 no-Findings); silent
# required channels (Findings+zero K11, Findings+zero K2, empty K3) RED.
evidence_liveness_blocks_ship() {
  local sid="${STORY_ID:-}"
  if [ -z "$sid" ]; then
    sid=$(printf '%s' "${STORY_SPEC_PREFIX:-}" | awk '{print $1}')
  fi
  [[ "$sid" =~ ^S[0-9]+$ ]] || sid="${sid:-story}"
  if [ ! -f .hermes/harness/evidence-liveness.sh ]; then
    log "WARN:O-EVIDLIVE: evidence-liveness.sh missing — refusing silent skip"
    event "m5-ship" 0 evidlive_missing "no-script"
    write_run_report "ship-blocked-evidlive: missing evidence-liveness.sh"
    echo "evidlive-red" > /tmp/supervisor-done
    return 0
  fi
  m4_progress "evidlive"
  STORY_TASKS="${STORY_TASKS:-${TASKS_FILE:-}}" \
    SUPERVISOR_EVENTS="$EVENTS" \
    bash .hermes/harness/evidence-liveness.sh heartbeat "$sid" >> "$LOG" 2>&1 || true
  if ! STORY_TASKS="${STORY_TASKS:-${TASKS_FILE:-}}" \
    SUPERVISOR_EVENTS="$EVENTS" \
    bash .hermes/harness/evidence-liveness.sh check "$sid" >> "$LOG" 2>&1; then
    log "O-EVIDLIVE: refusing story close — silent K-system(s) (see migration/evidence-liveness.md)"
    event "m5-ship" 0 evidlive_red "$sid"
    write_run_report "ship-blocked-evidlive: silent K-system(s) for ${sid}"
    echo "evidlive-red" > /tmp/supervisor-done
    return 0
  fi
  log "O-EVIDLIVE: PASS (${sid})"
  return 1
}

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

# O-SFIXHINTFIDELITY: detect which cheap dimension(s) the milestone RED cited.
# Writes /tmp/sensor-fix-dim (primary) for prompt routing.
sfix_red_dims() {
  local dims="" logblob
  logblob=$(cat /tmp/sensor-fidelity.log /tmp/sensor-milestone.log \
              /tmp/sensor-sonar.log /tmp/sensor-task.log 2>/dev/null || true)
  if [ -f /tmp/sensor-fix-dim ]; then
    dims=$(tr -d '[:space:]' </tmp/sensor-fix-dim)
  fi
  # O-SFIXDIMCHAR / O-CHARMILEORPHAN: when FIDELITY_CHECK=off (char tips), do not
  # cite fidelity from stale log lines — route remaining RED to sonar/task.
  if [ "${FIDELITY_CHECK:-on}" != "off" ]; then
    if echo "$logblob" | grep -qE 'FIDELITY:|HARVEST FIDELITY|SENSOR RED:fidelity|SENSOR RED \(fidelity\)'; then
      dims="${dims:+$dims }fidelity"
    fi
  fi
  if echo "$logblob" | grep -qE 'FINDINGS RED|FINDINGS:'; then
    dims="${dims:+$dims }findings"
  fi
  if echo "$logblob" | grep -qE 'COMPILATION ERROR|BUILD FAILURE|cannot find symbol'; then
    dims="${dims:+$dims }task"
  fi
  # O-SFIXDIMNONE / O-DSKIND: Quarkus config/build failures (missing jdbc,
  # Datasource must be defined, Agroal driver) are wiring/task — never dims=none
  # skip. v3 S02 T-007: empty dims → skipped sfix → HOTSWAP advanced on RED.
  if echo "$logblob" | grep -qiE \
    'ConfigurationException|Datasource must be defined|Unable to find a JDBC driver|quarkus-maven-plugin|Failed to build quarkus|AgroalProcessor|HibernateOrmProcessor'; then
    dims="${dims:+$dims }task"
  fi
  # O-SONAR401 / O-SFIXDIMNONE: auth/bootstrap failures are not a sonar
  # *violation* dimension — leave dims empty so dispatcher can refuse the seat.
  if echo "$logblob" | grep -qE 'SENSOR RED:sonar|SENSOR RED \(sonar\)|in-loop gate:|QUALITYGATE FAIL|new violations'; then
    if ! echo "$logblob" | grep -qE 'O-SONAR401|HTTP 401|401 Unauthorized|scanner bootstrapping has failed'; then
      dims="${dims:+$dims }sonar"
    fi
  fi
  # de-dupe whitespace tokens; strip fidelity if check is off (belt)
  dims=$(echo "$dims" | tr ' ' '\n' | awk 'NF && !seen[$0]++' | tr '\n' ' ' | sed 's/[[:space:]]*$//')
  if [ "${FIDELITY_CHECK:-on}" = "off" ]; then
    dims=$(echo "$dims" | tr ' ' '\n' | grep -v '^fidelity$' | tr '\n' ' ' | sed 's/[[:space:]]*$//')
  fi
  echo "$dims"
}

# O-SFIXLOOP / O-SFIXFALSEGREEN: during sensor-fix, milestone is REFUSED —
# recheck the *cited* cheap dimensions (never sonar-only when fidelity RED).
sfix_loop_recheck() { # $1=SENSOR_KIND
  local kind="$1" dims d rc=0
  if [ "$kind" != "milestone" ]; then
    .hermes/harness/sensors.sh "$kind"
    return $?
  fi
  dims=$(sfix_red_dims)
  if [ -z "$dims" ]; then
    # Unknown milestone RED — require both fidelity and sonar before GREEN
    # (v3 T-003: sonar-only recheck skipped MiniMax while fidelity still RED).
    # O-SFIXDIMCHAR: char tips (FIDELITY_CHECK=off) default sonar-only.
    if [ "${FIDELITY_CHECK:-on}" = "off" ]; then
      dims="sonar"
    else
      dims="fidelity sonar"
    fi
  fi
  primary=$(echo "$dims" | awk '{print $1}')
  printf '%s\n' "$primary" > /tmp/sensor-fix-dim
  for d in $dims; do
    case "$d" in
      fidelity) .hermes/harness/sensors.sh fidelity || rc=1 ;;
      findings) .hermes/harness/sensors.sh findings || rc=1 ;;
      task)     .hermes/harness/sensors.sh task || rc=1 ;;
      sonar)    .hermes/harness/sensors.sh sonar || rc=1 ;;
      package)  .hermes/harness/sensors.sh package || rc=1 ;;
      *)        .hermes/harness/sensors.sh sonar || rc=1 ;;
    esac
  done
  return "$rc"
}

# --- Post-commit verification (extracted so the batch path shares it) -----
# Trust-but-verify (run-4 lesson: a session committed a red tree): the
# supervisor runs the sensors itself after EVERY commit. The milestone
# sensor (verify + the factory's sonar gate) is ENFORCED — not advisory —
# on every pom/config-touching commit and every 3rd task, so style
# violations die in-loop, not at the factory.
post_commit_verify() { # $1=commit-prefix $2=tag ; always returns 0
  local prefix="$1" tag="$2"
  # O-SFIXATTR: fresh seat attribution for this verify (consumed by END note).
  rm -f /tmp/sfix-last-actor
  # O-LIFECYCLESM: tip → VERIFY dims → ADVANCE (typed completion + tip SHA)
  case "$prefix" in
    T-*|S[0-9]*-T-*|S[0-9]*-TC-*) lifecycle_on_committed "$prefix" ;;
  esac
  # O-HERMNEST: strip any .hermes/ that MiniMax/worker just committed
  scrub_hermes_from_git
  TASKS_SINCE_MILESTONE=$((TASKS_SINCE_MILESTONE+1))
  local SENSOR_KIND=task
  # O-CHARSONAR: characterization tips must clear milestone Sonar before
  # convert advances — task-only GREEN left 13 new issues for T-003 (W4-334).
  # O-CHARMILEORPHAN: char Owns are src/test; full milestone fidelity still
  # scans orphan/prior Port=rename mains (e.g. EntityUtils after M4 re-order)
  # → false sfix under the char id + ANTISCOPE conflict. Keep milestone
  # Sonar/findings, but skip harvest fidelity on characterization tips.
  local CHAR_MILE_NOFIDELITY=0
  if is_characterization_task "$prefix"; then
    SENSOR_KIND=milestone; TASKS_SINCE_MILESTONE=0
    CHAR_MILE_NOFIDELITY=1
    log "$tag: O-CHARSONAR — forcing milestone sensor for characterization tip"
    log "$tag: O-CHARMILEORPHAN — FIDELITY_CHECK=off for characterization tip (Sonar stays on)"
  elif git show --stat HEAD | grep -qE "pom.xml|application.properties" || [ $TASKS_SINCE_MILESTONE -ge 3 ]; then
    SENSOR_KIND=milestone; TASKS_SINCE_MILESTONE=0
  fi
  log "$tag: post-commit verification (${SENSOR_KIND} sensor)"
  if [ "$CHAR_MILE_NOFIDELITY" = "1" ]; then
    export FIDELITY_CHECK=off
  fi
  if [ "$SENSOR_KIND" = "milestone" ] && [ -f .hermes/harness/findings-milestone-scope.py ] \
    && [ -n "${TASKS_FILE:-}" ] && [ -f "$TASKS_FILE" ]; then
    _kms=$(FINDINGS_MILESTONE_SCOPE_ROOT="$PWD" PLAN_SCOPE="${PLAN_SCOPE:-}" \
      python3 .hermes/harness/findings-milestone-scope.py "$TASKS_FILE" "${RUN_BASE:-HEAD}" \
      2>/tmp/findings-milestone-scope.err || true)
    if [ -n "$_kms" ]; then
      export FINDINGS_SCOPE="$_kms"
      log "$tag: O-K5MILESCOPE — in-loop K5 rules=$(echo "$_kms" | tr ',' ' ' | wc -w | tr -d ' ') from completed tasks"
    else
      unset FINDINGS_SCOPE
      log "$tag: O-K5MILESCOPE — no Findings on completed tasks; in-loop K5 skip"
    fi
  fi
  # O-DTOCOV: OpenAPI dto harvest without pom exclusions → milestone Sonar RED
  # (+coverage/CPD/S6353). Patch pom before the sensor runs (migration-general).
  if [ -f .hermes/harness/ensure-dtocov-pom.py ]; then
    if python3 .hermes/harness/ensure-dtocov-pom.py "$PWD" > /tmp/dtocov-${tag}.out 2>&1; then
      if grep -q '^ok:pom-updated' /tmp/dtocov-${tag}.out 2>/dev/null; then
        if ! git diff --quiet pom.xml 2>/dev/null; then
          stage_for_task_commit
          git add pom.xml
          git commit -q -m "${prefix} harness: O-DTOCOV sonar exclusions for dto package" \
            >> "$LOG" 2>&1 || true
          log "$tag: O-DTOCOV — $(tr '\n' ' ' </tmp/dtocov-${tag}.out)"
        fi
      fi
    fi
  fi
  # O-DSKIND: hibernate-orm / @Entity without jdbc+db-kind → ConfigurationException
  # milestone RED (v3 S02 T-007). Wire before sensors; migration-general.
  if [ -f .hermes/harness/ensure-dskind.py ]; then
    if python3 .hermes/harness/ensure-dskind.py "$PWD" > /tmp/dskind-${tag}.out 2>&1; then
      if grep -q '^ok:dskind-updated' /tmp/dskind-${tag}.out 2>/dev/null; then
        if ! git diff --quiet -- pom.xml src/main/resources/application.properties 2>/dev/null; then
          stage_for_task_commit
          git add pom.xml src/main/resources/application.properties 2>/dev/null || true
          git commit -q -m "${prefix} harness: O-DSKIND jdbc + profiled db-kind for hibernate" \
            >> "$LOG" 2>&1 || true
          log "$tag: O-DSKIND — $(tr '\n' ' ' </tmp/dskind-${tag}.out)"
        fi
      fi
    fi
  fi
  local _sense_t0 _sense_elapsed _sense_pid _sense_rc=0
  _sense_t0=$(date +%s)
  # O-TASKHB: milestone/sonar can take minutes — pulse OUTER_LOG while sensing.
  outer_log "         … $(task_hb_pretty "$tag") sensing ${SENSOR_KIND} (started) — details ${LOG}"
  .hermes/harness/sensors.sh "$SENSOR_KIND" >> "$LOG" 2>&1 &
  _sense_pid=$!
  while kill -0 "$_sense_pid" 2>/dev/null; do
    sleep "$TASK_HEARTBEAT_SECS"
    if kill -0 "$_sense_pid" 2>/dev/null; then
      task_hb "$tag" "sensor:${SENSOR_KIND}" "$(( $(date +%s) - _sense_t0 ))" \
        "details ${LOG}"
    fi
  done
  wait "$_sense_pid" || _sense_rc=$?
  if [ "$_sense_rc" -ne 0 ]; then
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
    # O-STYLEFIDELITY: park pre-existing src/ dirt so evaluate leftovers
    # (defensive-copy / bidirectional-link harvest drift) are never scooped
    # into a "deterministic style-autofix" tip via stage_for_task_commit.
    park_src_dirt_for_autofix "$tag"
    local _pre_autofix_fid_rc=0
    .hermes/harness/sensors.sh fidelity >/tmp/fidelity-pre-autofix.log 2>&1 \
      || _pre_autofix_fid_rc=$?
    .hermes/harness/style-autofix.sh >> "$LOG" 2>&1 || true
    if [ -n "$(git status --porcelain -- src/)" ]; then
      # The autofix's changes are deterministic OpenRewrite fixes — KEEP them
      # even when the full sensor is still RED. V5 run-4: the old path did
      # `git checkout -- .` here, discarding the autofix (e.g. the ArrayList
      # diamond) whenever OTHER violations it can't fix kept the sensor red —
      # so those fixes oscillated back every cycle (sonar 5->3->4, never
      # converging). Commit them; if they cleared the RED we are done, else
      # the sfix starts from the cleaner tree.
      # O-STY: never commit OpenRewrite edits under migration/staging/
      discard_staging_autofix
      # O-STYLEFIDELITY: refuse src/main behavioural harvest mutations that
      # worsen fidelity (Set.copyOf / null-check / setUser-style drift).
      # Do NOT add defensive-copy to approved transforms — behaviour change.
      local _post_autofix_fid_rc=0
      .hermes/harness/sensors.sh fidelity >/tmp/fidelity-post-autofix.log 2>&1 \
        || _post_autofix_fid_rc=$?
      if [ "$_post_autofix_fid_rc" -ne 0 ] \
        && { [ "$_pre_autofix_fid_rc" -eq 0 ] \
          || [ -n "$(git diff --name-only -- src/main/ 2>/dev/null)" ]; }; then
        if [ -n "$(git diff --name-only -- src/main/ 2>/dev/null)" ] \
          || [ -n "$(git ls-files --others --exclude-standard -- src/main/ 2>/dev/null)" ]; then
          log "$tag: O-STYLEFIDELITY — autofix/dirt broke or worsened fidelity — reverting src/main (keep test-only recipe fixes)"
          event "$tag" 0 style_autofix_fidelity_revert "pre=${_pre_autofix_fid_rc}:post=${_post_autofix_fid_rc}"
          git checkout -q -- src/main/ 2>/dev/null || true
          git clean -fdq -- src/main/ 2>/dev/null || true
        fi
      fi
      if .hermes/harness/sensors.sh "$SENSOR_KIND" >> "$LOG" 2>&1; then
        style_autofix_stage "$prefix"
        # O-SFIXCREDIT: autofix uses distinct prefix so sfix credit cannot
        # match an earlier autofix SHA (S04 T-003 false GREEN).
        # O-AUTOFIXJSON: require src/ tip — never findings-JSON-only "autofix".
        if git diff --cached --quiet 2>/dev/null; then
          event "$tag" 0 style_autofix resolved_no_tip
          log "$tag: style-autofix/sensor GREEN with no src/ tip — done (O-AUTOFIXJSON)"
          return 0
        fi
        if autofix_commit_or_refuse \
          "${prefix} sensor autofix: deterministic style-autofix (OpenRewrite cleanup recipes)"; then
          event "$tag" 0 style_autofix resolved
          log "$tag: style-autofix resolved the red deterministically — no model session needed"
          return 0
        fi
        log "$tag: O-AUTOFIXJSON — autofix tip refused; ${SENSOR_KIND} already GREEN — continue without false tip"
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
        style_autofix_stage "$prefix"
        if ! git diff --cached --quiet; then
          # Final fidelity gate on what we are about to tip.
          if ! .hermes/harness/sensors.sh fidelity >/tmp/fidelity-pre-autofix-commit.log 2>&1 \
            && [ -n "$(git diff --cached --name-only -- src/main/ 2>/dev/null)" ]; then
            log "$tag: O-STYLEFIDELITY — refusing autofix tip with fidelity-RED src/main staged"
            event "$tag" 0 style_autofix_fidelity_refuse
            git reset -q 2>/dev/null || true
            git checkout -q -- src/main/ 2>/dev/null || true
            style_autofix_stage "$prefix"
          fi
          if ! git diff --cached --quiet; then
            if autofix_commit_or_refuse \
              "${prefix} sensor autofix: partial deterministic style-autofix (remaining violations to sfix)"; then
              event "$tag" 0 style_autofix partial
              log "$tag: style-autofix fixed some violations (committed, compiles); remaining go to a sfix session"
            fi
          fi
        fi
      fi
    fi
    # O-SONAR401: auth/bootstrap failure is infra — do not burn Qwen/MiniMax sfix.
    if [ "$SENSOR_KIND" = "milestone" ] || [ "$SENSOR_KIND" = "sonar" ]; then
      if grep -qE 'O-SONAR401|HTTP 401|401 Unauthorized' /tmp/sensor-sonar.log /tmp/sensor-milestone.log 2>/dev/null; then
        log "$tag: O-SONAR401 — Sonar auth failed; skip sensor-fix (refresh SONAR_TOKEN)"
        outer_log "         O-SONAR401: skip ${prefix} sfix — Sonar 401; not a code violation"
        event "$tag" 0 sonar401_skip "$SENSOR_KIND"
        record_debt "$prefix" "O-SONAR401 Sonar auth 401 — refresh SONAR_TOKEN before sfix" || true
        return 0
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
    # O-SFIXNODELTA: after failure-delta, before O-SFIXWORKER — do not dispatch
    # a task-attributed sensor-fix when K7 SUMMARY new=0 gone=0 AND the tip
    # has no content (0-byte / structure .gitkeep only). That RED is pre-existing
    # or signature/sensor disagree; burning Qwen→MiniMax under T-NNN misattributes
    # the repair (v3 T-004: empty .gitkeep tip → sfix edited pom.xml). Prefer
    # skip+continue (story/milestone attribution later) over false MiniMax.
    case "$prefix" in
      T-*)
        if [ -f "$FDELTA" ] \
          && grep -qE '^SUMMARY new=0 gone=0([[:space:]]|$)' "$FDELTA" 2>/dev/null \
          && sfix_tip_content_empty; then
          log "$tag: O-SFIXNODELTA — K7 new=0 gone=0 and tip empty/structure-only — skip task-attributed sfix (no seat burn)"
          outer_log "         O-SFIXNODELTA: skip ${prefix} sfix (K7 delta 0/0 + empty/structure tip); RED not this tip's debt"
          event "$tag" 0 sfix_nodelta_skip "$SENSOR_KIND"
          return 0
        fi
        ;;
    esac
    # O-SFIXOOSREVERT (W4-766 / ADR-47 §8): sonar paths outside OWNSTAGE must
    # become debt — not a sfix seat that writes OOS bytes then gets scope-reverted
    # (EntityUtils S1118 +3/−3 thrash). Do not widen story-scope to admit the fix.
    # Uses NEW:sonar when present; else after-sig sonar set (post scope-revert re-RED).
    if [ -n "${TASKS_FILE:-}" ] && [ -f "$FDELTA" ] \
      && [ -f .hermes/harness/sfix-oos-debt.py ]; then
      local _oos_out
      if _oos_out=$(
           python3 .hermes/harness/sfix-oos-debt.py \
             "$TASKS_FILE" "$prefix" "$FDELTA" "$FSIG_AFTER" \
             2>/tmp/sfix-oos-${tag}.err
         ); then
        log "$tag: O-SFIXOOSREVERT — ${_oos_out}; record debt + skip sfix (no OOS write)"
        outer_log "         O-SFIXOOSREVERT: skip ${prefix} sfix — OOS sonar → debt (not mutate+revert)"
        event "$tag" 0 sfix_oos_debt "$SENSOR_KIND"
        record_debt "$tag" "$SENSOR_KIND" \
          "O-SFIXOOSREVERT: sonar outside Owns (${_oos_out}) — fix under owning task; do not sfix-mutate OOS" \
          || true
        return 0
      fi
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
    local SFIX_VERIFY_HINT="verify with .hermes/harness/sensors.sh sonar|task|fidelity|package|findings as appropriate"
    local SFIX_RED_DESC="post-commit '${SENSOR_KIND}' sensor is RED"
    local SFIX_DIMS SFIX_PRIMARY SFIX_FIDELITY_NOTE=""
    SFIX_DIMS=$(sfix_red_dims)
    SFIX_PRIMARY=$(echo "${SFIX_DIMS:-sonar}" | awk '{print $1}')
    # O-SFIXDIMCHAR: char milestone tips never primary=fidelity (check is off;
    # stale FIDELITY: log lines must not steal the seat from Sonar NEW).
    if [ "$CHAR_MILE_NOFIDELITY" = "1" ] || [ "${FIDELITY_CHECK:-on}" = "off" ]; then
      SFIX_DIMS=$(echo "${SFIX_DIMS}" | tr ' ' '\n' | grep -v '^fidelity$' | tr '\n' ' ' | sed 's/[[:space:]]*$//')
      [ -n "${SFIX_DIMS}" ] || SFIX_DIMS=sonar
      SFIX_PRIMARY=$(echo "${SFIX_DIMS}" | awk '{print $1}')
      log "$tag: O-SFIXDIMCHAR — char tip sfix dims=[${SFIX_DIMS}] primary=${SFIX_PRIMARY} (fidelity suppressed)"
    fi
    printf '%s\n' "$SFIX_PRIMARY" > /tmp/sensor-fix-dim
    if [ "$SENSOR_KIND" = "milestone" ]; then
      # O-SFIXHINTFIDELITY / O-SFIXMILESTONE: name the *triggering* dimension —
      # never default "usually sonar" when FIDELITY lines are present.
      case "$SFIX_PRIMARY" in
        fidelity)
          SFIX_VERIFY_HINT="PRIMARY dimension is fidelity — verify with .hermes/harness/sensors.sh fidelity FIRST (never sensors.sh milestone; O-SFIXLOOP refuses it). Fix FIDELITY: lines in /tmp/sensor-fidelity.log / /tmp/sensor-milestone.log before any sonar chase (O-SFIXFIDELITY)."
          SFIX_RED_DESC="post-commit quality gate RED — HARVEST FIDELITY (not sonar). Fix drifted lines from /tmp/sensor-fidelity.log"
          SFIX_FIDELITY_NOTE="
O-SFIXFIDELITY PRIMARY TARGETS (paste/fix these before sonar):
$(grep -E '^FIDELITY:|HARVEST FIDELITY' /tmp/sensor-fidelity.log /tmp/sensor-milestone.log 2>/dev/null | head -40)
O-FIDELITYSORT: PropertyComparator → keep ArrayList<>(get*Internal()) + list.sort(Comparator); do not stream().sorted().collect; do not re-harvest Spring support.
$(sfix_test_pair_note)
"
          ;;
        findings)
          SFIX_VERIFY_HINT="PRIMARY dimension is findings — verify with .hermes/harness/sensors.sh findings ONLY (never milestone)"
          SFIX_RED_DESC="post-commit quality gate RED — FINDINGS dimension"
          ;;
        task)
          SFIX_VERIFY_HINT="PRIMARY dimension is compile/test — verify with .hermes/harness/sensors.sh task ONLY (never milestone)"
          SFIX_RED_DESC="post-commit quality gate RED — compile/test (task) dimension"
          ;;
        *)
          SFIX_VERIFY_HINT="PRIMARY dimension is sonar — verify with .hermes/harness/sensors.sh sonar ONLY (never sensors.sh milestone; O-SFIXLOOP refuses it)"
          SFIX_RED_DESC="post-commit quality gate RED (milestone bundle failed — fix sonar from /tmp/sensor-sonar.log; NOT a milestone re-run)"
          ;;
      esac
      log "$tag: O-SFIXHINTFIDELITY — sfix dims=[${SFIX_DIMS:-none}] primary=${SFIX_PRIMARY}"
      # O-SFIXDIMNONE (W4-022a): dims=[none] means sensor unavailable / infra —
      # not violations. Refuse the seat (same shape as O-SFIXNODELTA).
      if [ -z "${SFIX_DIMS}" ]; then
        # Re-scan logs once more — milestone stdout may land after first parse.
        SFIX_DIMS=$(sfix_red_dims)
        SFIX_PRIMARY=$(echo "$SFIX_DIMS" | awk '{print $1}')
      fi
      if [ -z "${SFIX_DIMS}" ]; then
        # O-SFIXDIMNONE: only skip for true infra/auth unavailability. Never
        # skip when SENSOR_KIND=milestone on a RED tip — force task dim so
        # Qwen/sfix can wire jdbc/db-kind (v3 S02 T-007 false advance).
        if [ "$SENSOR_KIND" = "milestone" ] \
          && grep -qE 'SENSOR RED \(milestone\)|Failed to build quarkus|ConfigurationException|Datasource must be defined' \
               /tmp/sensor-milestone.log "$LOG" 2>/dev/null; then
          SFIX_DIMS=task
          SFIX_PRIMARY=task
          printf '%s\n' task > /tmp/sensor-fix-dim
          log "$tag: O-SFIXDIMNONE — remapped empty dims → task (milestone build/config RED)"
          outer_log "         O-SFIXDIMNONE: remap dims=none→task for ${prefix} milestone RED"
        else
          log "$tag: O-SFIXDIMNONE — sfix dims empty (sensor unavailable); skip sensor-fix seat"
          outer_log "         O-SFIXDIMNONE: skip ${prefix} sfix (dims=none; see sensor logs / O-SONAR401)"
          event "$tag" 0 sfix_dimnone_skip "$SENSOR_KIND"
          if grep -qE 'O-SONAR401|HTTP 401|401 Unauthorized' /tmp/sensor-sonar.log /tmp/sensor-milestone.log 2>/dev/null; then
            record_debt "$prefix" "O-SONAR401 Sonar auth 401 — refresh SONAR_TOKEN before sfix" || true
          else
            record_debt "$prefix" "O-SFIXDIMNONE sensor unavailable (no violation dims) — inspect sensor logs" || true
          fi
          rm -f /tmp/sensor-fix-mode
          return 0
        fi
      fi
    fi
    SFIX_PROMPT="Use the migration-harness skill and read EXECUTION.md in its directory. The stage '${prefix}' was just committed but the supervisor's ${SFIX_RED_DESC} — read /tmp/sensor-task.log, /tmp/sensor-milestone.log, /tmp/sensor-fidelity.log and /tmp/sensor-sonar.log for the exact errors (sonar violations are listed inline when the gate is red). If those logs show FINDINGS: or FINDINGS RED lines, the RED dimension is findings — fix those file:line incidents (typical: replace quarkus-micrometer* with quarkus-smallrye-metrics) and verify with .hermes/harness/sensors.sh findings; do NOT commit unrelated comment/test polish while FINDINGS is RED (O-SFIXWRONGDIM). If /tmp/scope-violation.txt exists, the story-scope sensor reverted out-of-scope edits — read it and repair WITHIN the story scope only. Diagnose and fix the ROOT CAUSE (typical: files harvested prematurely without their extension/dependency). PACKAGE DIRECTION IS ONE-WAY: this migration RENAMES the legacy package to the target package (migration.yaml legacyPackage -> targetPackage). The target package is ALWAYS correct; a file under the legacy package in src/main is the defect. If a class is in the wrong place, move it INTO the target package and rewrite its 'package'/imports to the target — NEVER move or revert a class into the legacy package, and NEVER rewrite target-package files back to the legacy package to 'match' staged source (migration/staging holds legacy-package source by design; fidelity already accounts for the rename). A 'harvest fidelity RED' is about drifted CONTENT, not the package. O-FIDELITYVALID / O-SFIXNOSPRING: Spring BindingResult/FieldError → Jakarta ConstraintViolation is an approved validation conversion — do NOT re-harvest Spring validation types or add org.springframework.* imports / spring-* pom deps to green-wash fidelity. Re-run .hermes/harness/sensors.sh fidelity after harness updates; if already GREEN, commit nothing for fidelity. add a dependency ONLY if this stage's findings require it. VERIFY HINT: ${SFIX_VERIFY_HINT}. CHEAP FIX LOOP (O-SFIXLOOP — ENFORCED / O-SFIXMILESTONE): fix ALL listed violations in ONE pass, then verify ONCE with the dimension-specific check — sonar violations: .hermes/harness/sensors.sh sonar; FINDINGS:/FINDINGS RED: .hermes/harness/sensors.sh findings; fidelity drift: .hermes/harness/sensors.sh fidelity; a legacy package under src/main: .hermes/harness/sensors.sh package; compile/test failure: .hermes/harness/sensors.sh task. DO NOT run .hermes/harness/sensors.sh milestone — it is REFUSED during this session (exits 2). Commit ONE commit starting '${prefix} sensor fix:' the moment your dimension check is green; do not polish further. O-SONARTIME: NEVER wrap .hermes/harness/sensors.sh in timeout <600s (sonar needs 2–3m; timeout 60 → exit 124). O-SFIXSCOPE: NEVER commit while the dimension check is still RED claiming failures are 'pre-existing' or 'out of scope' — fix them or stop without commit (V9 S04 T-003). For RestAssured RED: fix JSON paths under the collection property, empty-path 400 myths, and test isolation (EXECUTION O-RESTJSON/O-RESTEMPTY/O-TESTISO). S5976: prefer @ParameterizedTest + @CsvSource — never delete characterization cases (O-SFIXCOUNT/O-SFIXDIRTY).
O-SFIXMUTATE: AFTER naming the fidelity/sonar root cause, your NEXT tool MUST be edit/write on the drifted file — do NOT keep reading. Supervisor kills diagnose-freeze (0 mutates ~120s) and escalates. O-STYLEFIDELITY: restore staged harvest return shapes (mutable collection returns when staging returns the field); never add Set.copyOf / unmodifiable defensive copies or bidirectional setUser hooks to green-wash Sonar S2384 — that breaks harvest fidelity and characterization contracts.
${SFIX_FIDELITY_NOTE}${K7_DELTA_NOTE}${RUN_CONTRACT}"
    # O-SFIXWORKER: Qwen first (cheap verifier); MiniMax rescue capped by
    # SFIX_MINIMAX_RESCUE_MAX (default 1 — R-218 enforced integer, not a comment).
    if [ "${WORKER_SFIX_FIRST:-true}" = "true" ]; then
      log "$tag: O-SFIXWORKER — sensor-fix via $(worker_label) first (MiniMax rescue≤${SFIX_MINIMAX_RESCUE_MAX:-1} if ${SENSOR_KIND} still RED)"
      outer_log "         O-SFIXWORKER: sensor-fix → $(worker_label); MiniMax rescue≤${SFIX_MINIMAX_RESCUE_MAX:-1}"
      event "$tag" 0 sfix_worker_first "$SENSOR_KIND"
      run_worker_prompt "${tag}-sfix-w" "$SFIX_PROMPT" || true
      if sfix_loop_recheck "$SENSOR_KIND" >> "$LOG" 2>&1; then
        # O-SFIXFALSEGREEN: log names cited dims — skip MiniMax only when
        # sfix_loop_recheck (all cited cheap dims, incl fidelity) is GREEN.
        log "$tag: O-SFIXWORKER — ${SENSOR_KIND} GREEN after Qwen (skip MiniMax; dims=${SFIX_DIMS:-recheck})"
        event "$tag" 0 sfix_worker_green "$SENSOR_KIND"
        # O-SFIXATTR: seat accounting — Qwen closed sfix (not coding worker alone).
        printf 'qwen\n' >"/tmp/sfix-last-actor"
        # O-SFIXRESCUEDISCARD: tip dirty GREEN before later full-sensor/discard.
        sfix_commit_green_dirt "$prefix" "$tag" "$SENSOR_KIND" || true
      else
        # O-SONAR401 / O-SFIXDIMNONE (W4-022a/W4-023): never MiniMax-rescue an
        # auth/bootstrap failure the worker already diagnosed — seat cannot mint tokens.
        if grep -qE 'O-SONAR401|HTTP 401|401 Unauthorized|scanner bootstrapping has failed' \
             /tmp/sensor-sonar.log /tmp/sensor-milestone.log 2>/dev/null \
          || [ -z "${SFIX_DIMS:-}" ]; then
          log "$tag: O-SONAR401/O-SFIXDIMNONE — skip MiniMax sfix rescue (sensor unavailable)"
          outer_log "         O-SONAR401: skip MiniMax sfix rescue — refresh SONAR_TOKEN"
          event "$tag" 0 sfix_auth_skip_rescue "$SENSOR_KIND"
          record_debt "$prefix" "O-SONAR401 Sonar auth/unavailable — refresh SONAR_TOKEN; sfix/rescue skipped" || true
        else
        local _sfix_rescue=0
        while [ "$_sfix_rescue" -lt "${SFIX_MINIMAX_RESCUE_MAX:-1}" ]; do
          _sfix_rescue=$((_sfix_rescue + 1))
          log "$tag: O-SFIXWORKER — ${SENSOR_KIND} still RED after Qwen — MiniMax rescue ${_sfix_rescue}/${SFIX_MINIMAX_RESCUE_MAX}"
          outer_log "         O-SFIXWORKER: MiniMax rescue ${_sfix_rescue}/${SFIX_MINIMAX_RESCUE_MAX}"
          event "$tag" 0 sfix_minimax_rescue "${SENSOR_KIND}:${_sfix_rescue}"
          # O-SFIXSIGINT: orch may return 124/130 after primary dim already GREEN
          # in the dirty tree — always try tip/archive before next rescue/teardown.
          orch "${tag}-sfix-r${_sfix_rescue}" "$SFIX_PROMPT" || true
          if sfix_loop_recheck "$SENSOR_KIND" >> "$LOG" 2>&1; then
            log "$tag: O-SFIXWORKER — ${SENSOR_KIND} GREEN after MiniMax rescue ${_sfix_rescue}"
            # O-SFIXATTR: MiniMax orch closed sfix — END must not credit coding worker alone.
            printf 'minimax\n' >"/tmp/sfix-last-actor"
            sfix_commit_green_dirt "$prefix" "$tag" "$SENSOR_KIND" || true
            break
          fi
          # Rescue timed out / SIGINT with partial dim win still dirty — tip if
          # cited dims cleared even when the full loop above raced.
          printf 'minimax\n' >"/tmp/sfix-last-actor"
          sfix_commit_green_dirt "$prefix" "$tag" "$SENSOR_KIND" || true
        done
        fi
      fi
    else
      orch "${tag}-sfix" "$SFIX_PROMPT" || true
      printf 'minimax\n' >"/tmp/sfix-last-actor"
      sfix_commit_green_dirt "$prefix" "$tag" "$SENSOR_KIND" || true
    fi
    rm -f /tmp/sensor-fix-mode
    # #6: re-verify the TRIGGERING sensor (${SENSOR_KIND}), not `task` — a
    # milestone-red (fidelity/sonar) is not cleared by a task-sensor green,
    # and a commit with the right prefix is not proof the red went away.
    if [ "$(git rev-parse HEAD)" != "$PRE_SFIX_HEAD" ] && committed "${prefix} sensor fix"; then
      # O-SFIXFINDINGS: drop/rewrite findings-inventory tips before accepting sfix.
      scrub_findings_from_tip
      if [ "$(git rev-parse HEAD)" = "$PRE_SFIX_HEAD" ] \
        || ! committed "${prefix} sensor fix"; then
        log "$tag: O-SFIXFINDINGS — no durable sensor-fix tip after findings scrub (code fix required)"
        outer_log "         O-SFIXFINDINGS: findings-only sfix tip refused — fix dest.java / cited dim"
        event "$tag" 0 sfix_findings_only_refused "$SENSOR_KIND"
      # O-SFIXNOSPRING (F-21): sfix must not reintroduce Spring to green-wash
      # harvest fidelity (type-level inversion — BindingResult restore).
      elif [ -f .hermes/harness/sfix-no-spring.py ] \
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
        # O-SFIXRESCUEDISCARD: if cited dims still GREEN, KEEP the tip (do not
        # O-SFIXSCOPE-reset a real dim win because full milestone/sonar lagged
        # or SIGINT'd). Residual full-sensor RED → debt/freeze, tip stays.
        if sfix_loop_recheck "$SENSOR_KIND" >> "$LOG" 2>&1; then
          log "$tag: O-SFIXRESCUEDISCARD — keep tip; cited dims GREEN while full ${SENSOR_KIND} still RED"
          event "$tag" 0 sfix_keep_tip_cited_green "$SENSOR_KIND"
          record_debt "$tag" "$SENSOR_KIND" "sensor-fix tip kept (cited dims GREEN) but full ${SENSOR_KIND} still RED"
        else
        # O-SFIXSCOPE: never keep a sensor-fix commit that left cited dims RED
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
        # O-DEBTFRZRACE: after O-SFIXSCOPE reset, discard orphan src/ poison and
        # recheck before debt — a prior sfix_loop_recheck GREEN must win over
        # a stale dirty-tree RED.
        # O-SFIXRESCUEDISCARD: try tip-of-green before discard.
        sfix_commit_green_dirt "$prefix" "$tag" "$SENSOR_KIND" || true
        if [ "$(git rev-parse HEAD)" = "$PRE_SFIX_HEAD" ]; then
          discard_src_dirt "$tag"
        fi
        if sfix_loop_recheck "$SENSOR_KIND" >> "$LOG" 2>&1; then
          log "$tag: O-DEBTFRZRACE false-red averted — ${SENSOR_KIND} GREEN after discard+recheck (post sfix reset)"
          event "$tag" 0 debtfrzrace_averted "$SENSOR_KIND"
        else
          record_debt "$tag" "$SENSOR_KIND" "sensor-fix committed but ${SENSOR_KIND} still RED (commit reset)"
        fi
        fi
      fi
    elif [ "$(git rev-parse HEAD)" = "$PRE_SFIX_HEAD" ] && committed "${prefix} sensor fix"; then
      log "$tag: O-SFIXCREDIT — sfix did not move HEAD (stale sensor-fix match ignored)"
      event "$tag" 0 sfix_no_new_commit credit
      # O-SFIXRESCUEDISCARD before O-SFIXDIRTY wipe
      if sfix_commit_green_dirt "$prefix" "$tag" "$SENSOR_KIND"; then
        :
      else
        discard_src_dirt "$tag"
        if sfix_loop_recheck "$SENSOR_KIND" >> "$LOG" 2>&1; then
          log "$tag: O-DEBTFRZRACE false-red averted — ${SENSOR_KIND} GREEN after discard (no new sfix commit)"
          event "$tag" 0 debtfrzrace_averted "$SENSOR_KIND"
        else
          record_debt "$tag" "$SENSOR_KIND" "sensor-fix did not clear ${SENSOR_KIND} (no new commit)"
        fi
      fi
    elif sfix_commit_green_dirt "$prefix" "$tag" "$SENSOR_KIND"; then
      # O-SFIXRESCUEDISCARD primary path: cited-dim GREEN dirty → tip (covers
      # the case where full sensors.sh milestone would still RED/SIGINT).
      log "$tag: O-SFIXRESCUEDISCARD — closed dirty ${SENSOR_KIND}-GREEN via cited-dim tip"
    elif [ -n "$(git status --porcelain)" ] && .hermes/harness/sensors.sh "$SENSOR_KIND" >> "$LOG" 2>&1; then
      # Mechanical closure — verifies the TRIGGERING sensor (#6), not task.
      # O-T6c: exclude .hermes/ (and staging) from escalation/sfix mechan commits.
      stage_for_task_commit
      if ! git diff --cached --quiet; then
        git commit -m "${prefix} sensor fix: supervisor mechanical commit of ${SENSOR_KIND}-green session work" >/dev/null 2>&1
        event "$tag" 0 mechanical_commit sfix_closure
        printf 'mechan\n' >"/tmp/sfix-last-actor"
        log "$tag: sensor-fix work was ${SENSOR_KIND}-GREEN but uncommitted — supervisor completed the commit"
      fi
    else
      # O-SFIXDIRTY + O-DEBTFRZRACE: only discard after commit-green attempt failed
      discard_src_dirt "$tag"
      if sfix_loop_recheck "$SENSOR_KIND" >> "$LOG" 2>&1; then
        log "$tag: O-DEBTFRZRACE false-red averted — ${SENSOR_KIND} GREEN after discard (sfix else-path)"
        event "$tag" 0 debtfrzrace_averted "$SENSOR_KIND"
      else
        record_debt "$tag" "$SENSOR_KIND" "sensor-fix did not clear ${SENSOR_KIND}"
      fi
    fi
  else
    # O-UXLOG-SENSE (Poll 77 U3): GREEN sensors visible on the demo log.
    _sense_elapsed=$(( $(date +%s) - _sense_t0 ))
    case "$SENSOR_KIND" in
      milestone) outer_log "         ✓ SENSE milestone sensor GREEN after ${tag} (verify+sonar, ${_sense_elapsed}s)" ;;
      *)         outer_log "         ✓ SENSE task sensor GREEN after ${tag} (compile+test, ${_sense_elapsed}s)" ;;
    esac
  fi
  if [ "${CHAR_MILE_NOFIDELITY:-0}" = "1" ]; then
    unset FIDELITY_CHECK
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

# O-HYGIENEWORKER: worker/mechan/ESCW success paths used to call
# post_commit_verify without commit-hygiene.py — O-JDBCREGRESS (spring-tx
# re-add) only ran inside run_stage MiniMax path. S03 T-001 d7bde2a landed
# spring-tx + GREEN sensors. Shared refuse for every tip-accept path.
refuse_unhygienic_commit() { # $1=prefix $2=tag -> 0 keep, 1 reset
  local prefix="$1" tag="$2" red_sha arch
  [ -f .hermes/harness/commit-hygiene.py ] || return 0
  # O-TREEFIXSTUB: Tree fix tips must pass hygiene (was bypassing — stub-nuke
  # tip 84632cf landed REMOVED husks with sensors falsely GREEN).
  case "$prefix" in
    T-*|S*|Preflight*|Gate*|Build*|Deploy*|Tree\ fix*|Tree*) ;;
    *) return 0 ;;
  esac
  git log -1 --format=%s | grep -qE "^(${prefix}|T-[0-9]+[A-Za-z]*|S[0-9]+|Tree fix)" || return 0
  if python3 .hermes/harness/commit-hygiene.py HEAD > /tmp/commit-hygiene.out 2>&1; then
    return 0
  fi
  red_sha=$(git rev-parse HEAD)
  arch="/tmp/strays/${tag}-hygiene-$(date -u +%Y%m%dT%H%M%SZ)"
  mkdir -p "$arch"
  git show --stat "$red_sha" >"$arch/stat.txt" 2>&1 || true
  git show "$red_sha" >"$arch/full.diff" 2>&1 || true
  cp /tmp/commit-hygiene.out "$arch/hygiene.txt" 2>/dev/null || true
  printf '%s\n' "$red_sha" >"$arch/sha.txt"
  log "$tag: O-COMMITHYGIENE — $(tr '\n' ' ' </tmp/commit-hygiene.out) — resetting dishonest tip (O-HYGIENEWORKER/O-TREEFIXSTUB)"
  event "$tag" 0 commit_hygiene_reset "$(tr '\n' ' ' </tmp/commit-hygiene.out)"
  git reset --hard HEAD~1 >> "$LOG" 2>&1 || true
  return 1
}

# O-ESCALAFTERRESET: after O-SFIXSCOPE resets a RED tip, do not immediately
# invent via MiniMax. Prefer commit existing GREEN dirt; discard orphan src/
# poison; re-sensor. Return 0 = skip escalation (treat success / tip landed).
post_reset_escalation_gate() { # $1=task-id -> 0 skip esc, 1 continue to esc
  local T="$1"
  case "$T" in
    T-*) ;;
    *) return 1 ;;
  esac
  # Prefer commit existing GREEN dirt before discarding/inventing.
  if [ -n "$(git status --porcelain -- src/ 2>/dev/null)" ]; then
    if .hermes/harness/sensors.sh task > /tmp/sensor-task.log 2>&1; then
      log "$T: O-ESCALAFTERRESET — task GREEN with post-reset dirt; prefer mechan/commit (no invent)"
      event "$T" 0 escal_after_reset green_dirt
      if try_mechan_commit "$T"; then
        return 0
      fi
      # GREEN dirt that mechan could not title-match — leave for CONTINUE
      # commit-gated; do not discard good work and do not invent.
      touch "/tmp/escal-after-reset-${T}"
      return 1
    fi
    # RED with dirt — orphan poison (untracked tests etc.); discard then recheck
    log "$T: O-ESCALAFTERRESET — discarding orphan/uncommitted src/ after O-SFIXSCOPE reset"
    discard_src_dirt "$T"
  fi
  if .hermes/harness/sensors.sh task > /tmp/sensor-task.log 2>&1; then
    log "$T: O-ESCALAFTERRESET — task GREEN on clean tree after reset; skip MiniMax invent"
    event "$T" 0 escal_after_reset clean_green
    if try_mechan_commit "$T"; then
      return 0
    fi
    if try_worker_verified_noop "$T"; then
      return 0
    fi
    # Clean+GREEN but no tip yet — escalate with commit-first guidance only
    touch "/tmp/escal-after-reset-${T}"
    log "$T: O-ESCALAFTERRESET — clean GREEN but no tip; CONTINUE must commit-gated without invent"
    return 1
  fi
  touch "/tmp/escal-after-reset-${T}"
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
      # O-ESCALAFTERRESET: after reset, prefer GREEN commit / skip invent
      if post_reset_escalation_gate "$prefix"; then
        event "$tag" "$attempt" success escal_after_reset
        return 0
      fi
      attempt=$((attempt+1))
      continue
    fi
    local p="$prompt"; [ $attempt -gt 1 ] && p="$rprompt"
    # O-ESCALAFTERRESET: strengthen CONTINUE when prior tip was reset
    if [ $attempt -gt 1 ] && [ -f "/tmp/escal-after-reset-${prefix}" ]; then
      p="O-ESCALAFTERRESET: A prior ${prefix} tip was O-SFIXSCOPE-reset. Inspect git status FIRST. If sensors.sh task is GREEN on a clean or dirty-but-good tree, land ONE commit starting '${prefix}:' via \`.hermes/harness/commit-gated.sh\` WITHOUT inventing new files/tests and WITHOUT rewriting already-GREEN tip content. Do not re-break mappers/tests that sensors already accept.
${p}"
    fi
    # O-PREFCONT: strengthen preflight/gate/build CONTINUE — forbid rewrite of
    # existing dirty/untracked work + characterization floor (W4-062).
    if [ $attempt -gt 1 ]; then
      case "$tag" in
        preflightfix*|gatefix*|buildfix*)
          p="O-PREFCONT: Inspect git status FIRST. Continue from EXISTING dirty/untracked work WITHOUT inventing new files/tests and WITHOUT rewriting already-present dirty tip content. Characterization floor: do not shrink @Test / assertion counts vs attempt start; keep typed assertThrows(UnsupportedOperationException) for unmodifiable collection getters (O-SHIPASSERTWEAK). Prefer commit-gated tip of task-GREEN tests-only dirt BEFORE sensors.sh sonar/preflight when the seat budget is tight (O-SHIPFIXCOMMIT).
${p}"
          ;;
      esac
    fi
    pref_snapshot_char_floor "$tag"
    orch "${tag}-a${attempt}p${pf}" "$p"; local rc=$?
    # O-NULLACTION (N17): honest stop without fabrication is success, not a burn.
    # ADR-48: completion_authority — prose is a request; reject completion claims
    # when ledger state ≠ ADVANCE (typed REOPEN → READY).
    if [ -f "/tmp/escalation-noaction-${tag}.txt" ] || [ -f "/tmp/escalation-noaction-${prefix}.txt" ]; then
      local naf="/tmp/escalation-noaction-${tag}.txt"
      [ -f "$naf" ] || naf="/tmp/escalation-noaction-${prefix}.txt"
      local na_rc=0
      if [ -f .hermes/harness/completion_authority.py ]; then
        python3 .hermes/harness/completion_authority.py \
          --resolve-null-action --task "$tag" --reason-file "$naf" \
          2>/tmp/nullaction-reopen.err || na_rc=$?
      elif [ -f .hermes/harness/nullaction_reopen.py ]; then
        python3 .hermes/harness/nullaction_reopen.py \
          --task "$tag" --reason-file "$naf" 2>/tmp/nullaction-reopen.err || na_rc=$?
      fi
      if [ "$na_rc" = "1" ]; then
        log "$tag: ADR-48/O-NULLACTIONREOPEN — rejected completion claim ($(tr '\n' ' ' </tmp/nullaction-reopen.err 2>/dev/null))"
        event "$tag" "$attempt" null_action_reopen_reject "$(head -1 /tmp/nullaction-reopen.err 2>/dev/null | tr '\n' ' ')"
        rm -f "$naf" /tmp/escalation-noaction-${tag}.txt /tmp/escalation-noaction-${prefix}.txt
        attempt=$((attempt+1))
        continue
      fi
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
        if post_reset_escalation_gate "$prefix"; then
          event "$tag" "$attempt" success escal_after_reset
          return 0
        fi
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
      # O-GITBAK / O-SIMPLEDTO / O-POMUNC / O-JDBCREGRESS via shared refuse
      # (O-HYGIENEWORKER — same gate as worker/mechan tip-accept paths).
      if ! refuse_unhygienic_commit "$prefix" "$tag"; then
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
      # The stage is sealed — reap REGISTERED residual workers only (O-PIDREG).
      shopt -s nullglob
      for _sf in /tmp/sessions/*.pid; do
        _spid=$(tr -d '[:space:]' <"$_sf" || true)
        _stag=$(basename "$_sf" .pid)
        if [[ "$_spid" =~ ^[0-9]+$ ]] && kill -0 "$_spid" 2>/dev/null; then
          log "$tag: reaping residual registered session ${_stag} (stage already committed)"
          session_reap_group "$_stag" "$_spid" "post-commit-residual"
        else
          rm -f "$_sf"
        fi
      done
      shopt -u nullglob
      session_log_unregistered_opencode
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
      # O-STRAYLATERTASK (W4R7 S02): also keep untracked Owns/Target paths of
      # later incomplete story tasks. MiniMax left Role.java untracked to
      # compile User (T-002) → stray sweep archived Role → post-commit sensor
      # RED → sfix thrash. Pair O-BATCHDEPORDER (order) + this (don't erase).
      KEEP_SCAFFOLD=""
      KEEP_LATER=""
      STRAYS=""
      _later_targets=""
      if [ -n "${TASKS_FILE:-}" ] && [ -n "${TASK_IDS:-}" ] && [ -f .hermes/harness/task-stage-paths.py ]; then
        for _lt in $TASK_IDS; do
          [ "$_lt" = "$prefix" ] && continue
          committed "$_lt" && continue
          _later_targets="${_later_targets}$(python3 .hermes/harness/task-stage-paths.py "$TASKS_FILE" "$_lt" 2>/dev/null || true)"$'\n'
        done
      fi
      while IFS= read -r f; do
        [ -n "$f" ] || continue
        if { [[ "$f" == src/main/java/* ]] || [[ "$f" == src/test/java/* ]]; } \
          && { [[ "$f" == *.gitkeep ]] || [[ "$f" == */package-info.java ]]; }; then
          KEEP_SCAFFOLD="${KEEP_SCAFFOLD}${f}"$'\n'
        elif [ -n "$_later_targets" ] && printf '%s\n' "$_later_targets" | grep -qxF "$f"; then
          KEEP_LATER="${KEEP_LATER}${f}"$'\n'
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
      if [ -n "$(echo "$KEEP_LATER" | tr -d '[:space:]')" ]; then
        log "$tag: O-STRAYLATERTASK — keeping untracked later-task Targets: $(echo "$KEEP_LATER" | tr '\n' ' ')"
        mkdir -p "/tmp/strays/${tag}"
        printf '%s' "$KEEP_LATER" > "/tmp/strays/${tag}/KEPT-LATERTASK.txt"
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
      timeout|no_commit)
        if [ "$cls" = "timeout" ]; then
          log "$tag: session hit the ${ORCH_LAST_BUDGET:-$SESSION_TIMEOUT}s budget — attempt $attempt burned, partial work stays for the next attempt"
        else
          log "$tag: session ended without commit — attempt $attempt burned"
        fi
        # O-SHIPFIXCOMMIT: tip unpaid task-GREEN tests-only dirt before a2
        # rewrite / next sonar burn (do not require full preflight GREEN).
        if pref_commit_green_dirt "$prefix" "$tag"; then
          if committed "$prefix"; then
            scrub_findings_from_tip
            scrub_frozen_specs_from_tip
            event "$tag" "$attempt" success shipfix_timeout_commit
            scope_enforce "$prefix"
            post_commit_verify "$prefix" "$tag"
            return 0
          fi
        fi
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
    # O-SHIPFIXCOMMIT: prefer tests-only tip path for ship-fix tags first.
    if pref_commit_green_dirt "$prefix" "$tag"; then
      if committed "$prefix"; then
        scrub_findings_from_tip
        scrub_frozen_specs_from_tip
        event "$tag" "$MAX_ATTEMPTS" mechanical_commit shipfix_closure
        log "$tag: O-SHIPFIXCOMMIT — exhausted-attempts tip of task-GREEN tests-only dirt ($(git log --oneline -1))"
        scope_enforce "$prefix"
        post_commit_verify "$prefix" "$tag"
        return 0
      fi
    fi
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
For each Findings rule that this story solved cleanly, optionally run write-hint.py
(O-RETROBTICK: do NOT wrap the example in shell backticks — this prompt is a
double-quoted bash string and backticks + <rule-id> become command substitution
plus stdin redirect). Example shape (copy, replace RULE_ID and the tip text):
python3 .hermes/harness/write-hint.py RULE_ID 'before→after shape, no specimen names'
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
    # O-RPTAWKESC: awk program must use '$4' in single quotes — '\$4' passes a
    # literal backslash to awk and breaks the KPI line in write_run_report.
    echo "- Escalations (KPI, from supervisor events): $(awk -F, '$4=="escalated"' "$EVENTS" | wc -l | tr -d ' ') (untested: $(awk -F, '$4=="escalated_untested"' "$EVENTS" | wc -l | tr -d ' '))"
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
# Requires STORY_DEPLOY + a tree that already implements the story.
# O-SHIPONLYSTATE: on success, append S0N,complete to migration/story-state.csv
# (committed) so a later outer-loop restart does not replay M4 for that story.
# Never use this to skip unfinished coding work.
# O-SHIPONLYSTATE: persist ledger so outer resume skips the shipped story.
ship_only_record_complete() {
  [ "${SHIP_ONLY:-}" = "1" ] || return 0
  local sid="${STORY_ID:-}"
  [ -z "$sid" ] && sid=$(printf '%s' "${STORY_SPEC_PREFIX:-}" | awk '{print $1}')
  [ -n "$sid" ] || { log "O-SHIPONLYSTATE: no STORY_ID/STORY_SPEC_PREFIX — ledger not updated"; return 0; }
  mkdir -p migration
  [ -f migration/story-state.csv ] || echo "story,outcome,epoch" > migration/story-state.csv
  if grep -q "^${sid},complete," migration/story-state.csv 2>/dev/null; then
    log "O-SHIPONLYSTATE: ${sid} already complete in story-state.csv"
    return 0
  fi
  echo "${sid},complete,$(date -u +%s)" >> migration/story-state.csv
  git add migration/story-state.csv \
    && git commit -q -m "${sid} story complete: story-gate-passed (SHIP_ONLY)" 2>/dev/null \
    || true
  log "O-SHIPONLYSTATE: recorded ${sid},complete in story-state.csv"
}
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
# O-M3DTOSCOPE / O-M3SUPSCOPE: pass roadmap file scope so supervisor re-lint
# matches outer-loop M3 gate — without --story-scope, dto/** incidents on a
# pom/properties story false-RED and burn MiniMax M3 revision (S01 fcc506c).
STORY_SCOPE_ARGS=()
[ -n "${STORY_SCOPE:-}" ] && STORY_SCOPE_ARGS=(--story-scope "$STORY_SCOPE")
# O-SHAPEDECL: live M3 requires **Shape** on every task (instruments stay WARN).
export PLAN_LINT_REQUIRE_SHAPE="${PLAN_LINT_REQUIRE_SHAPE:-1}"
LINT_OUT=$(python3 .hermes/harness/plan-lint.py "$TASKS_FILE" migration/mta-findings.json $SCOPE_ARGS $DEPLOY_ARGS "${STORY_SCOPE_ARGS[@]}" 2>&1)
if [ $? -ne 0 ] && ! committed "M3 revision"; then
  log "plan lint: revision required"; echo "$LINT_OUT" | head -20 >> "$LOG"
  printf '%s\n' "$LINT_OUT" > /tmp/plan-lint.txt
  if ! run_stage "M3 revision" "m3-lint" \
"Use the migration-harness skill and read PLANNING.md and MAPPINGS.md in its directory. The plan lint REJECTED ${TASKS_FILE} — the findings are in /tmp/plan-lint.txt (read it with your file tools). Revise ONLY ${TASKS_FILE} (and sibling files in that same specs/<story>/ directory) to fix every lint finding: infer tasks must carry the decided target design (file mappings, signatures, annotations — cite MAPPINGS.md shapes). Do not renumber or remove completed work.
O-SPECFROZEN: NEVER edit specs/ for a story whose migration/story-state.csv last status is complete (e.g. S01 after S01,complete). Do not delete delivered tasks from finished stories.
${RUN_CONTRACT}
Commit prefix: 'M3 revision:'." \
"Use the migration-harness skill and read PLANNING.md in its directory. Finish revising ONLY ${TASKS_FILE} per /tmp/plan-lint.txt and commit with prefix 'M3 revision:'. O-SPECFROZEN: never mutate complete stories' specs/.
${RUN_CONTRACT}"; then
    # O-M3LINTPROCEED: exhaustion is not permission to M4 — re-lint below.
    log "O-M3LINTPROCEED: revision round exhausted — re-linting; will HOLD if still RED (no M4)"
  fi
fi

# O-M3LINTPROCEED: M4 entry requires plan-lint GREEN. Never "proceed as-is"
# after exhausted m3-lint / still-RED tip (S03 573cc08 false-green → M4 risk).
LINT2=$(python3 .hermes/harness/plan-lint.py "$TASKS_FILE" migration/mta-findings.json $SCOPE_ARGS $DEPLOY_ARGS "${STORY_SCOPE_ARGS[@]}" 2>&1) || {
  log "O-M3LINTPROCEED: plan-lint still RED — refusing M4 (HOLD/re-M3)"
  echo "$LINT2" | head -30 >> "$LOG"
  printf '%s\n' "$LINT2" > /tmp/plan-lint.txt
  printf '%s\n' "O-M3LINTPROCEED: plan-lint RED after m3-lint — HOLD; re-M3 (do not enter M4)" > /tmp/supervisor-pause
  write_run_report "m3-lint-hold"
  echo "m3-lint-hold" > /tmp/supervisor-done
  exit 1
}
log "plan lint: PASS (M4 entry gate)"
# ADR-47 / step 1b — M4←M3 consumer assert (default OBSERVE until refuse flip).
# M4_CONSUMER_ASSERT=observe|refuse|refuse-char|off
# Default refuse-char (W4-768): only characterize char_surface oracle refuses;
# other asserts stay observe until full refuse is earned.
_m4ca_mode="${M4_CONSUMER_ASSERT:-refuse-char}"
if [ "$_m4ca_mode" != "off" ] && [ -f .hermes/harness/m4_consumer_assert.py ]; then
  _m4ca_story="${STORY_ID:-}"
  _m4ca_args=(--mode="$_m4ca_mode" --json=/tmp/m4-consumer-assert.json)
  [ -n "$_m4ca_story" ] && _m4ca_args+=(--story="$_m4ca_story")
  if ! python3 .hermes/harness/m4_consumer_assert.py "${_m4ca_args[@]}" \
      >>"$SUPERVISOR_LOG" 2>&1; then
    log "M4_CONSUMER_ASSERT:REFUSE mode=${_m4ca_mode} — INVALID_INPUT (see /tmp/m4-consumer-assert.json)"
    outer_log "         M4 consumer-assert REFUSE — INVALID_INPUT (ADR-47 / 1b)"
    # O-ADR47-1c: request rewind to owning phase (M3) — not silent repair.
    _rw_rc=0
    if [ -f .hermes/harness/phase_rewind.py ]; then
      python3 .hermes/harness/phase_rewind.py request \
        --from M4 --to M3 --reason M4_CONSUMER_ASSERT \
        --story "${_m4ca_story}" --detail /tmp/m4-consumer-assert.json \
        >>"$SUPERVISOR_LOG" 2>&1 || _rw_rc=$?
    fi
    if [ "$_rw_rc" = "2" ]; then
      log "PHASE_REWIND:EXHAUSTED — livelock cap (ADR-46 §7.3)"
      echo "phase-rewind-exhausted" > /tmp/supervisor-done
      write_run_report "phase-rewind-exhausted" 2>/dev/null || true
      exit 1
    fi
    # O-REWINDAPPLYGAP: apply BEFORE supervisor-done/archive so relaunch never
    # sees status=pending after fail_run (W4-768 live: request then O-TMPARCHIVE
    # left ledger pending twice). Outer apply remains idempotent.
    if [ -f .hermes/harness/phase_rewind.py ]; then
      python3 .hermes/harness/phase_rewind.py apply >>"$SUPERVISOR_LOG" 2>&1 \
        || log "PHASE_REWIND: apply failed (outer will retry)"
    fi
    # ADR-48 (b): typed REOPEN for ADVANCE tasks named in char_surface fires
    # (never --force). tip_sha remains observation; state→READY.
    if [ -f /tmp/m4-consumer-assert.json ] && [ -f .hermes/harness/task_lifecycle.py ]; then
      while IFS= read -r _reopen_tid; do
        [ -n "$_reopen_tid" ] || continue
        lifecycle_reopen "$_reopen_tid" consumer_assert || true
      done < <(python3 - <<'PY'
import json
from pathlib import Path
try:
    data = json.loads(Path("/tmp/m4-consumer-assert.json").read_text(encoding="utf-8"))
except Exception:
    raise SystemExit(0)
seen = set()
for f in data.get("fires") or []:
    if not isinstance(f, dict):
        continue
    if str(f.get("assert") or "") != "char_surface":
        continue
    tid = str(f.get("task") or "").strip()
    if tid and tid not in seen:
        seen.add(tid)
        print(tid)
PY
)
    fi
    echo "phase-rewind" > /tmp/supervisor-done
    write_run_report "phase-rewind" 2>/dev/null || true
    exit 1
  fi
  log "M4_CONSUMER_ASSERT: mode=${_m4ca_mode} — see /tmp/m4-consumer-assert.json"
fi
outer_log "         … M4 bootstrap: plan-lint PASS — entering task loop"
m4_progress "plan-lint-pass"
# O-EVIDLIVE: K1 exercised this story (ownership lint ran green).
if [ -f .hermes/harness/evidence-liveness.sh ]; then
  _evid_sid="${STORY_ID:-}"
  [ -z "$_evid_sid" ] && _evid_sid=$(printf '%s' "${STORY_SPEC_PREFIX:-}" | awk '{print $1}')
  [[ "$_evid_sid" =~ ^S[0-9]+$ ]] || _evid_sid="${_evid_sid:-story}"
  bash .hermes/harness/evidence-liveness.sh record "$_evid_sid" K1 1 "plan-lint PASS" \
    >> "$LOG" 2>&1 || true
fi

# ---------------------------------------------------------------- M4
TASKS_FILE="${STORY_TASKS:-$(ls specs/*/tasks.md 2>/dev/null | head -1)}"
# Accept 3-6 hash heading levels and any T-style id — models format
# tasks.md differently no matter what the prompt mandates (run #3 lesson).
# Depth 2-6, matching plan-lint exactly — a '## T-001:' plan used to pass
# the lint and then FATAL here (audit finding: regex drift between the
# two parsers).
# O-TASKIDSUFFIX / R3: heading order = M4 execution order (not sort -u).
# Letter-suffixed ids (T-001A) must parse — same regex family as plan-lint.
# O-M4COMPOSITE: typed VIEW headings are S0N-T-NNN-Name (ADR-35/40), not bare T-NNN.
TASK_IDS=$(python3 - "$TASKS_FILE" <<'PY'
import re, sys
from pathlib import Path
sys.path.insert(0, str(Path(".hermes/harness").resolve()))
from task_contract import HEADING_TASK_ID_ATOM
text = open(sys.argv[1], encoding="utf-8", errors="replace").read()
for m in re.finditer(rf"^#{{2,6}}\s+({HEADING_TASK_ID_ATOM})\s*:", text, re.M):
    print(m.group(1))
PY
)
[ -n "$TASK_IDS" ] || { log "FATAL: no task ids parsed from $TASKS_FILE"; echo no-tasks > /tmp/supervisor-done; exit 1; }
# O-M4WAVE (step C): partition characterize (wave A) before convert (wave B).
if [ -f .hermes/harness/m4_wave.py ]; then
  _ordered=$(python3 .hermes/harness/m4_wave.py order --ids $TASK_IDS 2>/dev/null || true)
  if [ -n "${_ordered:-}" ]; then
    TASK_IDS="$_ordered"
    log "O-M4WAVE: task list reordered char-wave-A then convert-wave-B"
  fi
fi
# O-ADR46-S3 (step 2b): derive requires-type / characterizes edges — LOG ONLY.
# Does not reorder TASK_IDS. Sizes convert↔convert violations for B.
if [ -f .hermes/harness/m4_edges.py ]; then
  _elog=$(python3 .hermes/harness/m4_edges.py derive --order $TASK_IDS 2>&1 | tee /tmp/m4-edges-derive.txt | tail -1 || true)
  log "O-ADR46-S3: ${_elog:-derive ran} (log-only — no dispatch)"
  outer_log "         O-ADR46-S3: ${_elog:-edges logged} — see migration/m4-edges-log.json"
fi
log "task list (file/M4 order): $(echo $TASK_IDS | tr '\n' ' ')"
outer_log "         … M4 bootstrap: $(echo "$TASK_IDS" | grep -c .) tasks parsed — $(echo $TASK_IDS | tr '\n' ' ' | head -c 160)"
m4_progress "task-loop"

# Resume hygiene: a relaunch may inherit a red tree from work committed
# before post-commit verification existed (or from a failed sensor-fix).
# Verify once at loop entry; RED gets one evidence-driven fix session.
if ! .hermes/harness/sensors.sh task >> "$LOG" 2>&1; then
  event "loop-entry" 0 sensor_red_at_entry verify
  log "loop entry: tree sensor RED — dispatching tree-fix session before tasks"
  orch "treefix" \
"Use the migration-harness skill and read EXECUTION.md in its directory. The working tree is RED before task execution: .hermes/harness/sensors.sh task fails — read /tmp/sensor-task.log for the exact errors. Diagnose and fix the ROOT CAUSE (typical: files harvested prematurely without their extension/dependency, or into the wrong package — fix or revert them; add a dependency ONLY if already-committed task scope requires it). Run .hermes/harness/sensors.sh task until GREEN, then commit ONE commit whose message STARTS with 'Tree fix:'.
O-TREEFIXSTUB: NEVER clear spring residue by rewriting owned Targets to comment-only /* REMOVED */ husks or by deleting type bodies / interface methods. For JDBC convert stacks implement the FULL repository API with Agroal DataSource + java.sql (or EntityManager) — do not stub-delete collaborators. If same-package collaborators required by Targets are absent (O-COLLABOWN), write /tmp/escalation-noaction-treefix.txt with O-NULLACTION reason and STOP — that is success. Sensors + commit-hygiene RED O-TREEFIXSTUB on REMOVED stubs.
${RUN_CONTRACT}"
  if committed "Tree fix"; then
    # O-TREEFIXSTUB / O-HYGIENEWORKER: tree-fix tips used to bypass tip-accept
    # hygiene — refuse REMOVED stubs / spring re-adds immediately.
    if refuse_unhygienic_commit "Tree fix" "treefix"; then
      log "loop entry: tree fix committed $(git log --oneline -1)"
    else
      log "loop entry: O-TREEFIXSTUB — dishonest Tree fix tip reset (REMOVED stubs / hygiene)"
    fi
  else
    log "loop entry: tree-fix did not commit — proceeding on a red tree (recorded)"
  fi
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
blocks = re.split(r"^#{2,6} +((?:S\d+-TC-[A-Za-z0-9]+|S\d+-T-\d{3}(?:-[A-Za-z0-9]+)?|T[-A-Za-z0-9]*\d+[A-Za-z]*)):", text, flags=re.M)
for i in range(1, len(blocks) - 1, 2):
    tid, body = blocks[i], blocks[i + 1]
    cls = field(body, "Class", "Type") or "infer"
    m = re.search(r"\b(rewrite|infer)\b", cls, re.I)
    print(f"{tid}:{(m.group(1).lower() if m else 'infer')}")
PYEOF
)
task_class() { echo "$TASK_CLASSES" | grep -m1 "^$1:" | cut -d: -f2; }

# Oracle derived from filesystem (O-ORACLEDERIVE / O-INFERABSENT) —
# absent|present; NEVER default undeclared → present.
task_oracle() {
  python3 - "$TASKS_FILE" "$1" <<'PY' 2>/dev/null || echo absent
import importlib.util, re, sys
from pathlib import Path
path, tid = sys.argv[1], sys.argv[2]
text = open(path, encoding="utf-8", errors="replace").read()
heads = list(re.finditer(r"^#{2,6}\s+((?:S\d+-TC-[A-Za-z0-9]+|S\d+-T-\d{3}(?:-[A-Za-z0-9]+)?|T[-A-Za-z0-9]*\d+[A-Za-z]*))\s*:", text, re.M))
body = ""
for i, m in enumerate(heads):
    if m.group(1) != tid:
        continue
    end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
    body = text[m.end():end]
    break
odp = Path(".hermes/harness/oracle_derive.py")
spec = importlib.util.spec_from_file_location("oracle_derive", odp)
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(mod)
print(mod.derive_oracle(body, root=Path.cwd()))
PY
}

# Shape from tasks.md (for O-INFERABSENT proceed: create|verify).
task_shape() {
  python3 - "$TASKS_FILE" "$1" <<'PY' 2>/dev/null || echo ""
import importlib.util, re, sys
from pathlib import Path
path, tid = sys.argv[1], sys.argv[2]
text = open(path, encoding="utf-8", errors="replace").read()
heads = list(re.finditer(r"^#{2,6}\s+((?:S\d+-TC-[A-Za-z0-9]+|S\d+-T-\d{3}(?:-[A-Za-z0-9]+)?|T[-A-Za-z0-9]*\d+[A-Za-z]*))\s*:", text, re.M))
body = ""
for i, m in enumerate(heads):
    if m.group(1) != tid:
        continue
    end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
    body = text[m.end():end]
    break
odp = Path(".hermes/harness/oracle_derive.py")
spec = importlib.util.spec_from_file_location("oracle_derive", odp)
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(mod)
print(mod.task_shape(body))
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
      m4_progress "batch" "${tid%% *}"
      ;;
    START)
      title=$(task_title "$tid"); cls=$(task_class "$tid")
      [ -n "$cls" ] || cls="?"
      line="▶ TASK   ${tid} — ${title} [class=${cls}]${detail:+ — ${detail}}"
      m4_progress "running" "$tid"
      ;;
    END)
      title=$(task_title "$tid")
      line="✓ TASK   ${tid} — ${title}${detail:+ — ${detail}}"
      m4_progress "done" "$tid"
      ;;
    SKIP)
      title=$(task_title "$tid")
      line="· TASK   ${tid} — ${title}${detail:+ — ${detail}}"
      m4_progress "skip" "$tid"
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
      # O-ACDIRTY: untracked/modified declared Targets must land in the AC tip —
      # allow-empty while Target dirt remains left Pet/Owner ?? (W4R7 T-008/T-009)
      # and tripped O-PARTIALADVCOLLAB (committed + leftover dirt).
      local _ac_staged=0 _acp
      if [ -f .hermes/harness/task-stage-paths.py ]; then
        while IFS= read -r _acp; do
          [ -n "$_acp" ] || continue
          if [ -e "$_acp" ] || [ -L "$_acp" ]; then
            if git status --porcelain -- "$_acp" 2>/dev/null | grep -q .; then
              git add -- "$_acp" 2>/dev/null || true
              _ac_staged=1
            fi
          fi
        done < <(python3 .hermes/harness/task-stage-paths.py "$TASKS_FILE" "$T" 2>/dev/null || true)
      fi
      case "$detail" in
        *:*/*)
          _acp=${detail#*:}
          if [ -e "$_acp" ] && git status --porcelain -- "$_acp" 2>/dev/null | grep -q .; then
            git add -- "$_acp" 2>/dev/null || true
            _ac_staged=1
          fi
          ;;
      esac
      if [ "$_ac_staged" = "1" ] && ! git diff --cached --quiet 2>/dev/null; then
        git commit -q -m "${T}: ALREADY COMPLETE — ${detail} already present (O-ACDIRTY)" 2>/dev/null \
          || git commit -m "${T}: ALREADY COMPLETE — ${detail} already present (O-ACDIRTY)" >/dev/null 2>&1 \
          || return 1
        event "$T" 0 already_complete "dirty:$detail"
        log "$T: ALREADY COMPLETE — ${detail} present; committed Target dirt (O-ACDIRTY); skipped opencode"
        return 0
      fi
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
      # O-ACSTRUCTCOMMIT: Shape=structure with Target .gitkeep on disk must
      # commit the deliverable — never allow-empty (W4 T-003: 1b1dda7 empty tip
      # while dto/.gitkeep stayed untracked → ship archived it).
      if [ -n "$(structure_gitkeep_targets "$T")" ]; then
        local _sg _staged=0
        for _sg in $(structure_gitkeep_targets "$T"); do
          if [ -f "$_sg" ]; then
            git add -- "$_sg" 2>/dev/null || true
            _staged=1
          fi
        done
        if [ "$_staged" = "1" ] && ! git diff --cached --quiet 2>/dev/null; then
          git commit -q -m "${T}: ALREADY COMPLETE — structure Target present (${detail}) (O-ACSTRUCTCOMMIT)" 2>/dev/null \
            || git commit -m "${T}: ALREADY COMPLETE — structure Target present (${detail}) (O-ACSTRUCTCOMMIT)" >/dev/null 2>&1 \
            || return 1
          event "$T" 0 already_complete "structure:$detail"
          log "$T: ALREADY COMPLETE — structure Target committed (${detail}); skipped opencode"
          return 0
        fi
        log "$T: O-ACSTRUCTCOMMIT — oracle-absent but structure Target not on disk; must-run"
        return 1
      fi
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
  # O-EVIDLIVE / K2: mark Analysis evidence presence for story-gate liveness.
  if printf '%s\n' "$packet" | grep -q '^Analysis evidence'; then
    event "$T" 0 "k2:evidence" "packet"
  fi
  # O-CREATEFIRSTMUT: Shape=create — tighter read-thrash kill + first-write tip
  # so Qwen cannot burn 10–15m exploring before Target exists (S06/S07).
  local shape
  shape=$(printf '%s\n' "$packet" | sed -n 's/^Shape:[[:space:]]*//p' | head -1 | tr '[:upper:]' '[:lower:]')
  if [ "$shape" = "create" ]; then
    export WORKER_READ_GLOB_MAX="${CREATE_READ_GLOB_MAX:-10}"
    packet=$(printf '%s\n\n%s\n' "$packet" \
      "O-CREATEFIRSTMUT: FIRST tool batch MUST write/edit the Target basename (or harvest-from-staging.sh). Do NOT read/glob-tour before the Target file exists — supervisor kills read-thrash early on Shape=create.")
  else
    unset WORKER_READ_GLOB_MAX 2>/dev/null || true
  fi
  # O-CHARFIRSTMUT (W4-311 / O-M4CHARFAIL): characterization must land
  # src/test/*.java — never claim success with a clean tree / empty commit.
  if printf '%s\n' "$packet" | grep -qiE 'characteri[sz]|src/test/.*Test\.java'; then
    packet=$(printf '%s\n\n%s\n' "$packet" \
      "O-CHARFIRSTMUT: FIRST tool MUST edit/write a src/test/**/*Test.java Target (characterization pins). Clean-tree / 'no file modifications' / empty commit-gated is FAILURE — supervisor mutate-deadline kills 0-write seats. Do NOT only update run-log.md.")
  fi
  log_task START "$T" "Actor: $(worker_label) — MiniMax not used for coding"
  lifecycle_running "$T"
  # O-WORKERWEDGE-RCA / O-WEDGESKIP: after a wedge kill, skip further Qwen
  # seats until the next successful story task commit (mechan/worker/escalation)
  # clears /tmp/worker-wedge-skip — do NOT burn MiniMax for the rest of the story.
  local story_key
  story_key=$(echo "${STORY_SPEC_PREFIX:-run}" | awk '{print $1}')
  if [ -f /tmp/worker-wedge-skip ] && grep -qxF "$story_key" /tmp/worker-wedge-skip 2>/dev/null; then
    log "$T: skip worker — prior wedge/thrash this story (O-WORKERWEDGE-RCA; clears on next task commit — O-WEDGESKIP)"
    echo "worker skipped — prior wedge class this story (O-WORKERWEDGE-RCA)" >> "$(oc_seat_base "$T").err"
    WORKER_LAST_RC=143
    return 1
  fi
  # O-WORKERWEDGE / O-OCSTALL: hard timeout alone burns 1800s on a hung OpenCode
  # with a frozen session JSON. Run under timeout in the background and kill early
  # if $(oc_seat_base "$T").json stops growing (default 300s unchanged).
  : > "$(oc_seat_base "$T").json"
  : > "$(oc_seat_base "$T").err"
  # O-PIDREG/O-OCGROUP: setsid so group-TERM reaps opencode serve children.
  setsid timeout 1800 opencode run "$packet" \
    -m "$WORKER_MODEL" --auto --format json \
    -f "$TASKS_FILE" -f AGENTS.md \
    > "$(oc_seat_base "$T").json" 2>"$(oc_seat_base "$T").err" &
  local wpid=$!
  session_register "$T" "$wpid"
  local stale=0 last_sz=-1 sz elapsed=0 thrash
  local stale_limit="${WORKER_JSON_STALE_SECS:-300}"
  # ARCH-C1 / O-TASKMUTATE: same first-write deadline as M3/sfix (default 120s).
  # Productive seats first-write at 0–38s; next cluster ~331s — 120s is well clear.
  local mutate_deadline="${WORKER_MUTATE_DEADLINE_SECS:-120}"
  while kill -0 "$wpid" 2>/dev/null; do
    sleep 60
    elapsed=$((elapsed + 60))
    sz=$(stat -c%s "$(oc_seat_base "$T").json" 2>/dev/null || echo 0)
    if [ "$sz" -eq "$last_sz" ]; then
      stale=$((stale + 60))
    else
      stale=0
      last_sz=$sz
    fi
    # O-TASKHB: demo outer-loop progress during long OpenCode seats.
    task_hb "$T" "worker" "$elapsed" \
      "json=${sz}B stale=${stale}s — details $(oc_seat_base "$T").json"
    # O-WORKERREAD / O-FIRSTMUT / O-FIRSTMUTBASH / O-TASKMUTATE (ARCH-C1):
    # kill early on read/glob thrash OR no first edit/write past mutate
    # deadline. Plain bash does NOT count (R-222 T-007). Successful
    # harvest-from-staging.sh DOES count (O-FIRSTMUTBASH).
    if [ -f .hermes/harness/worker-read-watch.py ] \
      && thrash=$(
           WORKER_MUTATE_DEADLINE_SECS="$mutate_deadline" \
           python3 .hermes/harness/worker-read-watch.py \
             "$(oc_seat_base "$T").json" "$elapsed" 2>/dev/null
         ); then
      if echo "$thrash" | grep -q 'mutate-deadline'; then
        log "$T: worker first-write deadline — ${thrash} — killing early (O-TASKMUTATE/ARCH-C1)"
        {
          echo "worker first-write deadline — ${thrash} (O-TASKMUTATE)"
          echo "abort: 0 edit/write after ${mutate_deadline}s — escalate or replan"
        } >> "$(oc_seat_base "$T").err"
        event "$T" 0 task_mutate_kill "$thrash"
        harness_kill_group "$T" "$wpid" TERM "mutate-deadline"
        sleep 2
        harness_kill_group "$T" "$wpid" KILL "mutate-deadline-kill"
      else
        log "$T: worker read-thrash — ${thrash} — killing early (O-WORKERREAD/O-FIRSTMUT)"
        {
          echo "worker read-thrash — ${thrash} (O-WORKERREAD/O-FIRSTMUT)"
          echo "abort: reads+globs exceeded with no edit/write — escalate or replan"
        } >> "$(oc_seat_base "$T").err"
        harness_kill_group "$T" "$wpid" TERM "read-thrash"
        sleep 2
        harness_kill_group "$T" "$wpid" KILL "read-thrash-kill"
      fi
      break
    fi
    if [ "$stale" -ge "$stale_limit" ]; then
      log "$T: worker wedged — no session JSON growth for ${stale}s — killing early (O-WORKERWEDGE)"
      {
        echo "worker wedged — no session output for ${stale}s (O-WORKERWEDGE)"
        echo "session JSON size frozen at ${sz} bytes"
      } >> "$(oc_seat_base "$T").err"
      harness_kill_group "$T" "$wpid" TERM "worker-wedge"
      sleep 2
      harness_kill_group "$T" "$wpid" KILL "worker-wedge-kill"
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
      } >> "$(oc_seat_base "$T").err"
      harness_kill_group "$T" "$wpid" TERM "$why"
      sleep 2
      harness_kill_group "$T" "$wpid" KILL "${why}-kill"
      break
    fi
  done
  wait "$wpid" 2>/dev/null
  rc=$?
  session_reap_group "$T" "$wpid" "session-end"
  WORKER_LAST_RC=$rc
  wait_for_worker
  # O-KILLREASON: if .err still empty after SIGTERM and freeze markers exist,
  # backfill (covers external pkill before this loop learned to write).
  if [ ! -s "$(oc_seat_base "$T").err" ] && { [ -f /tmp/supervisor-pause ] || [ -f /tmp/debt-freeze ]; }; then
    {
      echo "worker exit rc=${rc} with empty .err during freeze (O-KILLREASON backfill)"
      [ -f /tmp/supervisor-pause ] && { echo "--- /tmp/supervisor-pause ---"; head -n 20 /tmp/supervisor-pause; }
    } >> "$(oc_seat_base "$T").err"
  fi
  # O-WORKERWEDGE-RCA: classify kill/fail cause; skip further worker seats this story.
  if [ -f .hermes/harness/wedge-classify.py ] && [ -f "$(oc_seat_base "$T").err" ]; then
    local wclass
    wclass=$(python3 .hermes/harness/wedge-classify.py \
      "$(oc_seat_base "$T").err" "$(oc_seat_base "$T").json" 2>/dev/null || echo OTHER)
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
  if [ ! -s "$(oc_seat_base "$T").err" ] && [ -s "$(oc_seat_base "$T").json" ]; then
    python3 - "$(oc_seat_base "$T").json" "$(oc_seat_base "$T").err" <<'PY' 2>/dev/null || true
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
  log "$T: worker exit rc=${rc} (details $(oc_seat_base "$T").err)"
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
      if ! exec_scope_refuse_staged "$T"; then
        return 1
      fi
      git commit -q -m "${T}: $(task_title "$T") (worker $(worker_label))" 2>/dev/null \
        || git commit -m "${T}: $(task_title "$T") (worker $(worker_label))" >/dev/null 2>&1
      if committed "$T"; then
        char_protect_refuse_tip "$T" || return 1
        return 0
      fi
      log "$T: O-T6e worker auto-commit failed — commit command did not produce '${T}:' prefix"
    else
      # O-STEPFINISHRED: OpenCode often exits rc=0 with prose "complete / ready
      # for commit" while redesign-sig/task sensors are still RED (e.g.
      # O-AGROALHELPERSIG mapRow drop). Tip-accept correctly refuses; do NOT
      # treat that exit as success — rewrite rc so escalation is honest
      # (sensor-red), not worker-failed/rc=0 false-complete.
      log "$T: O-T6e worker auto-commit skip — task sensor RED after worker (see /tmp/sensor-task.log)"
      if [ "${WORKER_LAST_RC:-1}" = "0" ]; then
        WORKER_LAST_RC=42
        {
          echo "O-STEPFINISHRED: worker exited 0 with uncommitted app dirt but task sensor RED — incomplete (not success)"
          echo "refuse tip-accept / Already-satisfied / step_finish under SENSOR RED; fix signature then commit-gated, or escalate honestly"
          grep -E 'SENSOR RED|REDESIGN SIG RED|O-AGROALHELPERSIG|fail ' /tmp/sensor-task.log 2>/dev/null | head -8 || true
        } >> "$(oc_seat_base "$T").err"
        log "$T: O-STEPFINISHRED — rewriting worker_rc 0→42 (false-complete under sensor RED)"
        event "$T" 0 stepfinish_red "worker_rc=42"
      fi
    fi
  else
    log "$T: O-T6e worker left no app dirt (only .hermes/staging or clean) — no auto-commit"
    # O-STEPFINISHRED: clean-tree rc=0 still false-complete when task sensor RED
    # (worker claimed done without landing dirt that would tip-accept).
    if [ "${WORKER_LAST_RC:-1}" = "0" ] \
      && ! .hermes/harness/sensors.sh task > /tmp/sensor-task.log 2>&1; then
      WORKER_LAST_RC=42
      {
        echo "O-STEPFINISHRED: worker exited 0 on clean tree but task sensor RED — incomplete (not Already-satisfied)"
        grep -E 'SENSOR RED|REDESIGN SIG RED|O-AGROALHELPERSIG|fail ' /tmp/sensor-task.log 2>/dev/null | head -8 || true
      } >> "$(oc_seat_base "$T").err"
      log "$T: O-STEPFINISHRED — rewriting worker_rc 0→42 (clean-tree false-complete under sensor RED)"
      event "$T" 0 stepfinish_red "worker_rc=42;clean"
    fi
  fi
  return 1
}

# O-SFIXGREENNOCOMMIT: force-stage declared Target paths that already exist on
# disk (untracked/?? or missed by ATTRSWEEP empty allowlist). Returns 0 when
# the index has ≥1 staged path afterwards.
force_stage_declared_on_disk() { # $1=tid
  local tid="$1" _tf p n=0
  _tf="${TASKS_FILE:-${STORY_TASKS:-}}"
  [ -n "$tid" ] && [ -f "$_tf" ] && [ -f .hermes/harness/task-stage-paths.py ] || return 1
  git reset -q 2>/dev/null || true
  while IFS= read -r p; do
    [ -n "$p" ] || continue
    if [ -f "$p" ] || [ -L "$p" ]; then
      git add -- "$p" 2>/dev/null || true
      n=$((n + 1))
    elif [ -d "$p" ]; then
      # Structure dirs — stage gitkeep / package-info / java leaves.
      while IFS= read -r -d '' f; do
        git add -- "$f" 2>/dev/null || true
        n=$((n + 1))
      done < <(
        find "$p" -maxdepth 2 \( -name '.gitkeep' -o -name 'package-info.java' \
          -o -name '*.java' \) -print0 2>/dev/null || true
      )
    fi
  done < <(python3 .hermes/harness/task-stage-paths.py "$_tf" "$tid" 2>/dev/null || true)
  # Never scoop harness/findings into a forced tip.
  git reset -q -- .hermes migration/staging \
    migration/mta-findings-current.json migration/findings-delta.txt \
    migration/run-log.md 2>/dev/null || true
  [ "$n" -gt 0 ] || return 1
  git diff --cached --quiet && return 1
  log "${tid%% *}: O-SFIXGREENNOCOMMIT — forced stage of ${n} on-disk Target path-op(s)"
  return 0
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
      # O-SFIXGREENNOCOMMIT: empty Ownstage/ATTRSWEEP with Targets on disk —
      # force-stage declared paths before giving up (W4R7 S02 T-004).
      if force_stage_declared_on_disk "$T"; then
        :
      else
        log "$T: O-T6b skip mechan-commit — only .hermes/staging dirt (or empty stage)"
        return 1
      fi
    fi
    if ! git diff --cached --name-only | python3 .hermes/harness/mechan-match.py "$TASKS_FILE" "$T" \
         > /tmp/mechan-match.out 2>&1; then
      log "$T: O-T6d skip mechan-commit — staged paths mismatch task ($(cat /tmp/mechan-match.out 2>/dev/null | tr '\n' ' '))"
      git reset -q
      return 1
    fi
    # O-EXECSCOPE: refuse out-of-scope props/pom before attaching T-NNN title
    if ! exec_scope_refuse_staged "$T"; then
      return 1
    fi
    git commit -q -m "${T}: $(task_title "$T") (mechanical verify-and-commit; O-T6)" 2>/dev/null \
      || git commit -m "${T}: $(task_title "$T") (mechanical verify-and-commit; O-T6)" >/dev/null 2>&1
    if committed "$T"; then
      if ! char_protect_refuse_tip "$T"; then
        return 1
      fi
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
  # O-ESCWSTRUCTTGT: never allow-empty "Already satisfied" while Shape=structure
  # / Target .gitkeep is still absent — that tip poisons HEAD then still escalates
  # (v3 S02 T-001: 51dad87 empty tip + O-SCOPEBACKFILL refuse + MiniMax).
  if structure_targets_missing "$T"; then
    log "$T: O-ESCWSTRUCTTGT skip allow-empty — structure Target still absent"
    return 1
  fi
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
    # Tip landed but committed() refused (structure/ACSTRUCT) — drop the empty tip
    # so MiniMax/escalation does not inherit a false Already-satisfied HEAD.
    if git log -1 --format=%s 2>/dev/null | grep -qE "^${T}: Already satisfied"; then
      git reset --soft HEAD~1 2>/dev/null \
        || git reset --mixed HEAD~1 2>/dev/null \
        || true
      log "$T: O-ESCWSTRUCTTGT — reset false Already-satisfied tip (Target still absent)"
    fi
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
    task_tip_landed "$T" "ALREADY_COMPLETE" "fast path" || return 1
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
  # O-HARVESTREADY: single pre-mechan / pre-worker compile-readiness pipeline.
  # Derives validation|mapstruct|jpa|spring signals from on-disk Java and runs
  # registered ensurers. Do NOT add a parallel one-off ensure wire here —
  # register in ensure-harvest-ready.py ENSURERS (see harvest_ready.py).
  if [ "$(task_class "$T")" = "rewrite" ] \
    && [ -f .hermes/harness/ensure-harvest-ready.py ]; then
    if python3 .hermes/harness/ensure-harvest-ready.py "$PWD" \
         > /tmp/harvest-ready-${T}.out 2>/tmp/harvest-ready-${T}.err; then
      log "$T: O-HARVESTREADY — $(tr '\n' ' ' </tmp/harvest-ready-${T}.out)"
    fi
  fi
  # O-SCAFFOLDREADY / O-PKGINFOAC: peer of O-HARVESTREADY for create/structure.
  # package-info.java / .gitkeep are mechanical (Oracle:absent, often no
  # staging). Register plugins in ensure-scaffold-ready.py CREATE_ENSURERS —
  # do not add a parallel one-off ensure wire here (Wave5 S01-T-008 MiniMax).
  if [ -f .hermes/harness/ensure-scaffold-ready.py ]; then
    if python3 .hermes/harness/ensure-scaffold-ready.py \
         "$TASKS_FILE" "$T" "$PWD" \
         > /tmp/scaffold-ready-${T}.out 2>/tmp/scaffold-ready-${T}.err; then
      if grep -qE 'ok:|scaffold-create:ok' /tmp/scaffold-ready-${T}.out 2>/dev/null; then
        log "$T: O-SCAFFOLDREADY — $(tr '\n' ' ' </tmp/scaffold-ready-${T}.out)"
      fi
    fi
  fi
  # O-PKGDIR before mechan: empty dirs → .gitkeep so mkdir work can commit
  ensure_trackable_packages
  # O-T6: untracked/dirty target tree already green — don't burn a model seat
  if try_mechan_commit "$T"; then
    if refuse_unhygienic_commit "$T" "$T"; then
      task_tip_landed "$T" "MECHAN_GREEN" "O-T6" || {
        record_rule_outcomes "$T" "char_protect_reset"; return 1
      }
      log_task END "$T" "mechanical commit (O-T6) — $(git log --oneline -1 | cut -c1-80)"
      record_rule_outcomes "$T" "mechan"
      scope_enforce "$T"
      post_commit_verify "$T" "$T"
      debt_frozen && return 1
      return 0
    fi
    log "$T: O-HYGIENEWORKER reset mechan tip — continuing"
    record_rule_outcomes "$T" "hygiene_reset"
  fi
  # O-INFERABSENT (R-231 / Wave4 §2.2): infer + *derived* Oracle:absent is
  # the S03 T-007/T-012 wedge (high-read/0-write → JSON_STALE). Skip Qwen
  # unless a proceed path applies (Shape=create|verify or Proceed:
  # O-NULLACTION). Escalate with MiniMax-owned edits (O-ESCREOPENCODE).
  local skip_worker=0
  if python3 - "$TASKS_FILE" "$T" <<'PY' 2>/dev/null
import importlib.util, re, sys
from pathlib import Path
path, tid = sys.argv[1], sys.argv[2]
text = open(path, encoding="utf-8", errors="replace").read()
heads = list(re.finditer(r"^#{2,6}\s+((?:S\d+-TC-[A-Za-z0-9]+|S\d+-T-\d{3}(?:-[A-Za-z0-9]+)?|T[-A-Za-z0-9]*\d+[A-Za-z]*))\s*:", text, re.M))
body = ""
for i, m in enumerate(heads):
    if m.group(1) != tid:
        continue
    end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
    body = text[m.end():end]
    break
odp = Path(".hermes/harness/oracle_derive.py")
spec = importlib.util.spec_from_file_location("oracle_derive", odp)
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(mod)
cls_m = re.search(r"^[^\n]*(?:Class|Type)[^\n]*?\b(rewrite|infer)\b", body, re.M | re.I)
cls = cls_m.group(1).lower() if cls_m else "infer"
oracle = mod.derive_oracle(body, root=Path.cwd())
shape = mod.task_shape(body)
sys.exit(0 if mod.inferabsent_blocks(cls=cls, oracle=oracle, shape=shape, body=body) else 1)
PY
  then
    skip_worker=1
    log "$T: O-INFERABSENT — skip worker (infer + derived-Oracle:absent wedge)"
    {
      echo "O-INFERABSENT — worker skipped (infer + derived Oracle:absent)"
      echo "reshape Shape=create|verify or Proceed: O-NULLACTION; do not re-dispatch opencode"
    } > "$(oc_seat_base "$T").err"
    WORKER_LAST_RC=143
    arm_escreopencode "$T"
  fi
  # O-SYNTHROUTE (W4-287): skip Qwen when output is undetermined — MiniMax-first.
  # Determined = Shape=create|modify|structure with concrete src/ Target paths.
  # Undetermined = Shape=verify, characterization synthesis, or doc/prose Goals
  # with no create Target (T-000/T-002/T-005 class failures).
  if [ "$skip_worker" -eq 0 ] && python3 - "$TASKS_FILE" "$T" <<'PY' 2>/dev/null
import re, sys
path, tid = sys.argv[1], sys.argv[2]
text = open(path, encoding="utf-8", errors="replace").read()
heads = list(re.finditer(r"^#{2,6}\s+((?:S\d+-TC-[A-Za-z0-9]+|S\d+-T-\d{3}(?:-[A-Za-z0-9]+)?|T[-A-Za-z0-9]*\d+[A-Za-z]*))\s*:\s*(.+)$", text, re.M))
body = title = ""
for i, m in enumerate(heads):
    if m.group(1) != tid:
        continue
    title = m.group(2)
    end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
    body = text[m.end():end]
    break
sm = re.search(r"(?im)^\*?\*?Shape\*?\*?\s*:?\s*(\w+)", body)
shape = (sm.group(1).lower() if sm else "")
if shape in {"verify", "absent"}:
    sys.exit(0)  # undetermined → skip worker
if re.search(r"characteri[sz]", title + "\n" + body, re.I) and shape != "create":
    sys.exit(0)
# Doc / prose goals without a create .java/.gitkeep Target
noc = "\n".join(ln for ln in body.splitlines() if not re.search(r"(?i)Verification\s+of\s*:", ln))
create = re.findall(r"src/(?:main|test)/[\w./-]+(?:\.java|/\.gitkeep)", noc)
if re.search(r"(?i)\b(documentation|document|README|verify all|validation and compilation)\b", title) and not create:
    sys.exit(0)
sys.exit(1)  # determined — keep worker-first
PY
  then
    skip_worker=1
    log "$T: O-SYNTHROUTE — skip Qwen (undetermined output); MiniMax-first"
    {
      echo "O-SYNTHROUTE — worker skipped (undetermined output; route MiniMax-first)"
      echo "Qwen writes only when artifact+content are fully specified"
    } > "$(oc_seat_base "$T").err"
    WORKER_LAST_RC=143
  fi
  if [ "$skip_worker" -eq 0 ] && [ "${WORKER_FIRST}" = "true" ] && run_worker_task "$T"; then
    # O-SFIXSCOPE: worker may commit then leave task RED — reset and escalate
    if refuse_red_task_commit "$T" "$T"; then
      # O-HYGIENEWORKER: refuse spring-tx/jdbc/orm re-add etc. before GREEN advance
      if refuse_unhygienic_commit "$T" "$T"; then
        task_tip_landed "$T" "WORKER_GREEN" "$(worker_label)" || {
          record_rule_outcomes "$T" "char_protect_reset"; return 1
        }
        orphan_oc_reap_after_tip "$T" "worker-tip-seal"
        scope_enforce "$T"
        post_commit_verify "$T" "$T"
        log_task END "$T" "committed via $(worker_label)$(sfix_attr_end_note) — $(git log --oneline -1 | cut -c1-80)"
        record_rule_outcomes "$T" "worker_green"
        clear_worker_wedge_skip
        debt_frozen && return 1
        return 0
      fi
      log "$T: O-HYGIENEWORKER reset worker tip — continuing to escalation path"
      record_rule_outcomes "$T" "hygiene_reset"
    else
      log "$T: O-SFIXSCOPE reset worker RED commit — continuing to escalation path"
      record_rule_outcomes "$T" "worker_reset"
    fi
    # O-ESCALAFTERRESET: clean orphan poison + re-sensor; prefer commit GREEN
    # dirt / ESCW over MiniMax invent on a freshly reset tip.
    if post_reset_escalation_gate "$T"; then
      if refuse_unhygienic_commit "$T" "$T"; then
        task_tip_landed "$T" "ESCAL_AFTER_RESET" "no MiniMax invent" || {
          record_rule_outcomes "$T" "char_protect_reset"; return 1
        }
        scope_enforce "$T"
        post_commit_verify "$T" "$T"
        log_task END "$T" "O-ESCALAFTERRESET — GREEN after reset (no MiniMax invent) — $(git log --oneline -1 | cut -c1-80)"
        record_rule_outcomes "$T" "escal_after_reset"
        clear_worker_wedge_skip
        debt_frozen && return 1
        return 0
      fi
      log "$T: O-HYGIENEWORKER reset after O-ESCALAFTERRESET — continuing"
      record_rule_outcomes "$T" "hygiene_reset"
    fi
  fi
  # O-T6e: second mechan pass after worker (gitkeep / late writes / ESCW2 dirt)
  ensure_trackable_packages
  if try_mechan_commit "$T"; then
    if refuse_unhygienic_commit "$T" "$T"; then
      task_tip_landed "$T" "MECHAN_GREEN" "O-T6e after worker" || {
        record_rule_outcomes "$T" "char_protect_reset"; return 1
      }
      orphan_oc_reap_after_tip "$T" "mechan-tip-seal"
      scope_enforce "$T"
      post_commit_verify "$T" "$T"
      log_task END "$T" "mechanical commit after worker (O-T6e)$(sfix_attr_end_note) — $(git log --oneline -1 | cut -c1-80)"
      record_rule_outcomes "$T" "mechan"
      debt_frozen && return 1
      return 0
    fi
    log "$T: O-HYGIENEWORKER reset mechan tip after worker — continuing"
    record_rule_outcomes "$T" "hygiene_reset"
  fi
  # O-ESCW: worker verified, nothing to change — close without MiniMax
  if try_worker_verified_noop "$T"; then
    if refuse_unhygienic_commit "$T" "$T"; then
      task_tip_landed "$T" "ESCW" "worker verified clean tree" || {
        record_rule_outcomes "$T" "char_protect_reset"; return 1
      }
      # O-ORPHANOC: ESCW used to return without reaping — orphan opencode kept writing.
      orphan_oc_reap_after_tip "$T" "escw-tip-seal"
      scope_enforce "$T"
      post_commit_verify "$T" "$T"
      log_task END "$T" "already satisfied (O-ESCW)$(sfix_attr_end_note) — $(git log --oneline -1 | cut -c1-80)"
      record_rule_outcomes "$T" "escw"
      debt_frozen && return 1
      return 0
    fi
    log "$T: O-HYGIENEWORKER reset ESCW tip — continuing"
    record_rule_outcomes "$T" "hygiene_reset"
  fi
  # O-SFIXGREENNOCOMMIT: last chance — try_mechan_commit (with forced Target
  # stage on empty Ownstage). If still GREEN + Targets on disk but uncommitted,
  # refuse MiniMax — commit-staging failure alone is not an escalation cause.
  if ! committed "$T" \
    && .hermes/harness/sensors.sh task > /tmp/sensor-task.log 2>&1; then
    if try_mechan_commit "$T"; then
      if refuse_unhygienic_commit "$T" "$T"; then
        task_tip_landed "$T" "MECHAN_GREEN" "O-SFIXGREENNOCOMMIT" || {
          record_rule_outcomes "$T" "char_protect_reset"; return 1
        }
        orphan_oc_reap_after_tip "$T" "sfixgreen-tip-seal"
        scope_enforce "$T"
        post_commit_verify "$T" "$T"
        log_task END "$T" "O-SFIXGREENNOCOMMIT mechanical tip (no MiniMax)$(sfix_attr_end_note) — $(git log --oneline -1 | cut -c1-80)"
        record_rule_outcomes "$T" "sfixgreen_nocommit_mechan"
        debt_frozen && return 1
        return 0
      fi
    fi
    local _miss_tgt
    _miss_tgt=$(ownstage_missing_declared "$T" | head -5 | tr '\n' ' ')
    if [ -n "${_miss_tgt// /}" ]; then
      orphan_oc_reap_after_tip "$T" "sfixgreen-refuse-minimax"
      log "$T: O-SFIXGREENNOCOMMIT — task GREEN + Targets on disk (${_miss_tgt}) but tip staging failed — refusing MiniMax"
      {
        echo "O-SFIXGREENNOCOMMIT: task sensor GREEN with on-disk Targets unstaged/uncommitted — not a MiniMax seat"
        echo "targets: ${_miss_tgt}"
      } >> "$(oc_seat_base "$T").err"
      event "$T" 0 sfixgreen_nocommit_refuse_minimax "${_miss_tgt}"
      record_debt "$T" "O-SFIXGREENNOCOMMIT Targets present + GREEN but tip staging failed — fix Ownstage/paths (no MiniMax)" || true
      record_rule_outcomes "$T" "sfixgreen_nocommit_refuse"
      return 1
    fi
  fi
  # O-ESCALCAUSE: classify why MiniMax is taking over (rescue vs redo).
  # Prefer O-KILLREASON / wedge text already written to .err (W3-143) — never
  # collapse pause-kills into the constant worker-failed.
  local esc_cause="worker-failed"
  local esc_detail=""
  if [ -f "$(oc_seat_base "$T").err" ] && grep -qiE 'supervisor-pause' "$(oc_seat_base "$T").err" 2>/dev/null; then
    esc_cause="supervisor-pause"
    esc_detail=$(grep -m1 'worker killed —' "$(oc_seat_base "$T").err" 2>/dev/null || echo "O-KILLREASON supervisor-pause")
  elif [ -f "$(oc_seat_base "$T").err" ] && grep -qiE 'debt-freeze' "$(oc_seat_base "$T").err" 2>/dev/null; then
    esc_cause="debt-freeze"
    esc_detail=$(grep -m1 'worker killed —' "$(oc_seat_base "$T").err" 2>/dev/null || echo "O-KILLREASON debt-freeze")
  elif [ -f "$(oc_seat_base "$T").err" ] && grep -qiE 'O-WORKERREAD|read-thrash|O-FIRSTMUT' "$(oc_seat_base "$T").err" 2>/dev/null; then
    esc_cause="read-thrash"
    esc_detail=$(grep -m1 'read-thrash\|O-WORKERREAD\|O-FIRSTMUT' "$(oc_seat_base "$T").err" 2>/dev/null | head -1 || true)
  elif [ -f "$(oc_seat_base "$T").err" ] && grep -qiE 'O-WORKERWEDGE|worker wedged' "$(oc_seat_base "$T").err" 2>/dev/null; then
    esc_cause="worker-wedge"
    esc_detail=$(grep -m1 'wedged\|O-WORKERWEDGE' "$(oc_seat_base "$T").err" 2>/dev/null | head -1 || true)
  elif [ -f "$(oc_seat_base "$T").err" ] && grep -qiE '429|rate.?limit|quota|Too Many Requests' "$(oc_seat_base "$T").err" 2>/dev/null; then
    esc_cause="quota"
  elif [ "${WORKER_LAST_RC:-}" = "130" ]; then
    # O-SIGINT: harness kills use TERM/KILL (143/137); rc=130 is external INT.
    esc_cause="sigint"
    esc_detail="worker_rc=130 (SIGINT — not harness TERM/KILL; see kill-ledger)"
  # O-STEPFINISHRED / O-ESCALCAUSE-STALE: prefer latest post-worker sensor RED
  # over an earlier pre-worker O-T6d empty-stage / guard-refused (v3 S01 T-001:
  # cause stayed guard-refused while real reason was task sensor RED /
  # O-HTTPPORT). Also match O-T6e "task sensor RED after worker" and
  # O-STEPFINISHRED .err — wake#293 labeled worker-failed/rc=0 dishonestly.
  elif [ -f "$(oc_seat_base "$T").err" ] \
    && grep -qiE 'O-STEPFINISHRED' "$(oc_seat_base "$T").err" 2>/dev/null; then
    esc_cause="sensor-red"
    esc_detail=$(grep -E 'O-STEPFINISHRED|SENSOR RED|REDESIGN SIG RED|O-AGROALHELPERSIG|fail ' \
      "$(oc_seat_base "$T").err" /tmp/sensor-task.log 2>/dev/null \
      | tail -5 | tr '\n' ';' | cut -c1-240)
  elif grep -qE 'SENSOR RED|O-HTTPPORT|REDESIGN SIG RED|O-AGROALHELPERSIG' \
         /tmp/sensor-task.log /tmp/sensor-milestone.log /tmp/sensor-sonar.log 2>/dev/null \
    && tail -n 160 "$LOG" 2>/dev/null \
         | grep -qE "${T}:.*(committed but the|sensor is RED|task sensor RED|O-STEPFINISHRED|O-T6e.*sensor RED|post_commit|O-SFIX|Actor:|mechanical commit|already satisfied)"; then
    esc_cause="sensor-red"
    esc_detail=$(grep -E 'SENSOR RED|O-HTTPPORT|REDESIGN SIG RED|O-AGROALHELPERSIG|fail ' \
      /tmp/sensor-task.log /tmp/sensor-milestone.log /tmp/sensor-sonar.log 2>/dev/null \
      | tail -5 | tr '\n' ';' | cut -c1-240)
  elif _esc_last=$(tail -n 200 "$LOG" 2>/dev/null | grep -E "${T}:" | tail -1) \
    && [ -n "$_esc_last" ]; then
    # Only classify guard-refused when the *latest* log line for this task is
    # still the mechan/path guard — not a stale earlier O-T6d after worker ran.
    if echo "$_esc_last" | grep -qE 'O-T6d|unexpected-paths|staged paths mismatch'; then
      esc_cause="guard-refused"
      esc_detail=$(echo "$_esc_last" | sed 's/^.*O-T6d /O-T6d /')
    elif [ -f "$(oc_seat_base "$T").err" ] \
      && grep -qiE 'unexpected-paths|staged paths mismatch|O-T6d' "$(oc_seat_base "$T").err" 2>/dev/null \
      && ! echo "$_esc_last" | grep -qE 'Actor:|committed|sensor|O-SFIX|post_commit'; then
      esc_cause="guard-refused"
    fi
    unset _esc_last
  elif [ -f "$(oc_seat_base "$T").err" ] && grep -qiE 'unexpected-paths|staged paths mismatch|O-T6d' "$(oc_seat_base "$T").err" 2>/dev/null; then
    esc_cause="guard-refused"
  fi
  # F-20 P3: cause file carries guard id + reason when known (self-contained).
  if [ -z "$esc_detail" ] && [ "$esc_cause" = "guard-refused" ]; then
    esc_detail=$(tail -n 80 "$LOG" 2>/dev/null | grep -E "${T}: O-T6d" | tail -1 | sed 's/^.*O-T6d /O-T6d /' || true)
  fi
  {
    echo "$esc_cause"
    [ -n "$esc_detail" ] && echo "$esc_detail"
    echo "worker_rc=${WORKER_LAST_RC:-unset}"
  } > "/tmp/escalation-cause-${T}.txt"
  event "$T" 0 escalation_cause "$esc_cause"
  log "$T: O-ESCALCAUSE ${esc_cause}${esc_detail:+ — ${esc_detail}} (rc=${WORKER_LAST_RC:-unset}) → /tmp/escalation-cause-${T}.txt"
  # O-ESCALPAUSE: pause/debt kills are not coding failures — do not burn MiniMax.
  if [ "$esc_cause" = "supervisor-pause" ] || [ "$esc_cause" = "debt-freeze" ]; then
    log "$T: O-ESCALPAUSE — suppress MiniMax escalation (${esc_cause}); waiting at pause gate"
    log_task SKIP "$T" "pause-kill (${esc_cause}) — no escalation"
    hotswap_pause_gate "$T"
    debt_frozen && return 1
    return 1
  fi
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
  # O-ESCREOPENCODE (+ ENFORCE / SENSORRED): after wedge/thrash/INFERABSENT/
  # CHARORACLE/sensor-red/O-STEPFINISHRED, MiniMax owns edits — do not
  # re-dispatch the incomplete OpenCode class. Prompt forbid alone failed
  # (Wave4 S03 T-002 invent; W4-100a sensor-red nested Qwen hollow).
  local esc_routing esc_worker_disc
  if escreopencode_should "$T"; then
    arm_escreopencode "$T"
    esc_routing="MODEL ROUTING (O-ESCREOPENCODE): You are MiniMax on ESCALATION after a wedged/skipped/sensor-red worker. YOU OWN all file-changing work with your own tools. Do NOT dispatch opencode (-m ${WORKER_MODEL}) — re-invoking the incomplete worker class burns another seat (incl. O-STEPFINISHRED / sensor-red). O-ESCREOPENCODE-ENFORCE: supervisor DENIES/KILLS any opencode spawn during this escalation."
    esc_worker_disc="O-ESCREOPENCODE-ENFORCE: opencode is refused (exit 75) and killed if spawned. Do NOT attempt opencode. Own file edits with MiniMax tools. If O-CHARORACLE/oracle absent or fabrication would be required: write /tmp/escalation-noaction-${T}.txt with reason and STOP (O-NULLACTION success). NEVER use python3 <<heredoc, python3 -c multi-line, or scratch OpenRewrite — bundled scripts only."
  else
    esc_routing="MODEL ROUTING (V7): You are MiniMax orchestrator on ESCALATION. Prefer dispatching opencode (-m ${WORKER_MODEL}) for all file-changing work. Do NOT apply mechanical rewrite/harvest edits with your own tools unless the worker already failed — Qwen has unlimited tokens; MiniMax is rate-limited."
    esc_worker_disc="Worker discipline (V6 P2.1/P2.2): if you do launch opencode, run it in the FOREGROUND with a terminal timeout ≥1800s; WAIT for exit; NEVER background it; NEVER use python3 <<heredoc, python3 -c multi-line, or scratch OpenRewrite — bundled scripts only."
  fi
  if run_stage "$T" "$T" \
"Use the migration-harness skill and read EXECUTION.md in its directory. Execute M4 for task ${T} from ${TASKS_FILE} ONLY.
${esc_routing}
O-ESCWSCOPE / O-ESCWSCOPEUTIL: edit ONLY this task's Owns/Target paths from ${TASKS_FILE}. Do NOT create or mutate later-story classes (${LATER_CLASSES:-none}), src/main/**/util/* collaborators, or unrelated services. Untracked later-class dirt is removed (O-ESCWSCOPEUTIL) — tip REJECT if util lands with a convert tip.
O-ESCALORACLE: Shape=${esc_shape:-unknown} Oracle=${esc_oracle:-unknown}. If Oracle=absent or Shape=remove: prove named targets are ABSENT — never create a file solely to delete it; never invent unlisted deletion targets.
O-CHARFIRSTMUT: If this task is characterization / names src/test/*Test.java — empty tree + 'no file modifications' + empty commit-gated is FAILURE. Write the src/test Target(s) first, then commit-gated. Do NOT only append run-log.md.
${esc_worker_disc}
O-ESCTERM60: land the tip with \`.hermes/harness/commit-gated.sh '${T}: …'\` (terminal timeout ≥300). Do NOT bare \`git commit\` — commit-msg sensor exceeds short tool timeouts.
${esc_evidence:+$esc_evidence
}Worker packet (authoritative goal + constraints):
${esc_packet:-'(task-packet unavailable — read ${TASKS_FILE} for ${T})'}
${RUN_CONTRACT}
Finish with ONE commit whose message STARTS with '${T}:'. Stop after ${T}." \
"Use the migration-harness skill and read EXECUTION.md in its directory. Continue M4 for task ${T} from ${TASKS_FILE} ONLY. Inspect git status first. O-ESCALAFTERRESET: if a prior tip was O-SFIXSCOPE-reset, do NOT invent new files/tests or rewrite already-GREEN tip content — if sensors.sh task is GREEN on a clean or dirty-but-good tree, land ONE commit starting '${T}:' via \`.hermes/harness/commit-gated.sh '${T}: …'\` only. If a previous worker left complete work and sensors are GREEN, commit ONE commit starting '${T}:' WITHOUT launching opencode via \`.hermes/harness/commit-gated.sh '${T}: …'\` (O-ESCTERM60; terminal timeout ≥300; no bare git commit). ${esc_routing} ${esc_worker_disc} Foreground only; bundled scripts only — no heredocs / python3 -c.
${esc_evidence:+$esc_evidence
}${RUN_CONTRACT}"; then
    # O-T1FINDESC: scrub before amend so the attributed tip stays clean.
    scrub_findings_from_tip
    scrub_frozen_specs_from_tip
    # O-ESCNOCOMMIT: run_stage/Hermes exit 0 is not proof of a ${T}: tip.
    # Wave2 petclinic T-003: MiniMax findings-only tip → O-T1FINDESC undid it →
    # supervisor logged "committed via MiniMax" on prior T-002 SHA (false green).
    # O-HERMNESTTIP: accept ${T}: as an ancestor of HEAD when tip is an
    # O-HERMNEST chore (gitignore/.hermes untrack) immediately after the task tip.
    _esc_ok_tip=0
    if git log -1 --format=%s | grep -qE "^${T}:"; then
      _esc_ok_tip=1
    elif git log -1 --format=%s | grep -qiE 'O-HERMNEST|gitignore \.hermes|untrack \.hermes' \
      && git log -5 --format=%s | grep -qE "^${T}:"; then
      _esc_ok_tip=1
      log "$T: O-HERMNESTTIP — HEAD is HERMNEST chore; ${T}: found in last 5 commits — accept (not ESCNOCOMMIT)"
    fi
    if [ "$_esc_ok_tip" -eq 0 ]; then
      log "$T: O-ESCNOCOMMIT — escalation OK but HEAD is not ${T}: (got: $(git log -1 --format=%s | cut -c1-80))"
      # Shape=remove / already-absent often leaves a clean tree — prefer ESCW
      # allow-empty over MiniMax false credit on a prior task's SHA.
      if try_worker_verified_noop "$T"; then
        log_task END "$T" "already satisfied (O-ESCW after O-ESCNOCOMMIT) — $(git log --oneline -1 | cut -c1-80)"
        record_rule_outcomes "$T" "escw"
        scope_enforce "$T"
        post_commit_verify "$T" "$T"
        clear_worker_wedge_skip
        debt_frozen && return 1
        return 0
      fi
      # ADR-48 (d) / O-BLOCKSCHED: unresolvable tip → BLOCKED; scheduler continues.
      # Sensor RED (task|milestone|sonar) still freezes via record_debt — this path
      # is "cannot land a tip", not "tip is dishonest".
      log "$T: O-ESCNOCOMMIT — BLOCKED (O-BLOCKSCHED/ADR-48d); scheduler continues"
      record_debt "$T" escnocommit "escalation without ${T}: tip (see O-ESCNOCOMMIT)"
      lifecycle_blocked "$T" "escnocommit" "$T"
      append_harness_runlog "$T" "ESCNOCOMMIT_BLOCKED" "O-BLOCKSCHED — not debt-freeze kill"
      return 0
    fi
    unset _esc_ok_tip
    # O-NOAMEND / F-sha-stable (W4-646): never rewrite a tip a sensor may have
    # certified. Attribution belongs in the original commit message (compose
    # before commit) or in the run-log/events — never amend after the fact.
    if git log -1 --format=%s | grep -qE "^${T}:" \
      && ! git log -1 --format=%s | grep -qiE 'via MiniMax escalation'; then
      log "$T: O-NOAMEND — tip lacks [via MiniMax escalation] in subject; recording in run-log (sha stays $(git rev-parse --short HEAD))"
      append_harness_runlog "$T" "ESCALATION_ATTR" "actor=MiniMax cause=${esc_cause:-escalation} sha=$(git rev-parse --short HEAD) (O-NOAMEND no-amend)"
      event "$T" 0 escalation_attr_runlog "sha=$(git rev-parse --short HEAD)"
    fi
    log_task END "$T" "committed via MiniMax escalation — $(git log --oneline -1 | cut -c1-80)"
    record_rule_outcomes "$T" "escalation"
    clear_worker_wedge_skip
    # K12: refute MiniMax escalation tip before accepting it.
    if ! refute_high_stakes HEAD "$T-k12"; then
      log "$T: K12 refused escalation commit — resetting tip + debt freeze"
      git reset --hard HEAD~1 >>"$LOG" 2>&1 || true
      append_harness_runlog "$T" "TIP_RESET_K12" "escalation REFUTED"
      record_debt "$T" k12 "escalation commit REFUTED (see migration/refute-log.md)"
      touch /tmp/debt-freeze
      touch /tmp/supervisor-pause
      debt_frozen && return 1
      return 1
    fi
    task_tip_landed "$T" "ESCALATION_GREEN" "MiniMax ${esc_cause}" || {
      record_rule_outcomes "$T" "char_protect_reset"
      debt_frozen && return 1
      return 1
    }
  else
    # O-ESCRATEZOMBIE: MiniMax may burn attempts on rate-limit while a parallel
    # mechan-commit / other supervisor already landed ${T}: (W4R7 S02 T-004 —
    # NamedEntity tip c1382c2 then false debt-freeze). Accept, do not freeze.
    if committed "$T"; then
      log "$T: O-ESCRATEZOMBIE — escalation exhausted but ${T}: tip already present — accept (no debt-freeze)"
      log_task END "$T" "already committed during escalation wait (O-ESCRATEZOMBIE) — $(git log --oneline --grep="^${T}:" -1 | cut -c1-80)"
      record_rule_outcomes "$T" "escalation_zombie_accept"
      append_harness_runlog "$T" "ESCRATEZOMBIE" "accept existing tip; no debt-freeze"
      clear_worker_wedge_skip
      debt_frozen && return 1
      return 0
    fi
    # ADR-48 (d) / O-BLOCKSCHED: unresolvable seat → BLOCKED; do not kill the loop.
    log_task SKIP "$T" "exhausted — BLOCKED (O-BLOCKSCHED); scheduler continues"
    log "$T: exhausted — O-BLOCKSCHED BLOCKED (ADR-48d; not debt-freeze kill)"
    record_rule_outcomes "$T" "exhausted"
    append_harness_runlog "$T" "EXHAUSTED" "O-BLOCKSCHED BLOCKED — scheduler continues"
    lifecycle_blocked "$T" "exhausted" "$T"
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
  # ADR-48 (d) / O-BLOCKSCHED: already-BLOCKED tasks are observations — skip,
  # keep scheduling remaining work (gate ≠ scheduler).
  if [ -f .hermes/harness/task_lifecycle.py ]; then
    if python3 .hermes/harness/task_lifecycle.py blocked --ids "$T" >/tmp/blocksched-one.txt 2>/dev/null; then
      :
    else
      if grep -q "O-BLOCKSCHED:BLOCKED" /tmp/blocksched-one.txt 2>/dev/null; then
        log "$T: O-BLOCKSCHED — already BLOCKED; skip (scheduler continues)"
        log_task SKIP "$T" "BLOCKED — not re-dispatching (O-BLOCKSCHED/ADR-48d)"
        continue
      fi
    fi
  fi
  # O-SEATBUDGET: tripwire before dispatching more seats
  check_seat_budget_overrun "$T" || {
    echo "debt-freeze" > /tmp/supervisor-done
    exit 78
  }
  # O-PARTIALADV / O-PARTIALADVCOLLAB: only earlier uncommitted dirty Targets
  _padv=$(partial_adv_blockers "$T" 2>/dev/null | head -5 || true)
  if [ -n "${_padv}" ]; then
    log "O-PARTIALADV: refusing advance past unfinished Targets — $(echo "$_padv" | tr '\n' '; ')"
    outer_log "         O-PARTIALADV: unfinished declared Targets still dirty — HOLD (not silent advance)"
    echo "$_padv" > /tmp/partial-adv-blockers.txt
    echo "debt-freeze" > /tmp/supervisor-done
    exit 78
  fi
  if committed "$T"; then
    log "$T: already committed"
    log_task SKIP "$T" "already committed — skipping"
    continue
  fi
  # O-M4WAVE: refuse wave-B dispatch while any wave-A (characterize) is open.
  if [ -f .hermes/harness/m4_wave.py ]; then
    _comm=""
    for _ct in $TASK_IDS; do
      committed "$_ct" && _comm="$_comm $_ct"
    done
    if ! python3 .hermes/harness/m4_wave.py check-dispatch \
        --task "$T" --ids $TASK_IDS --committed $_comm >/tmp/m4-wave-dispatch.txt 2>/tmp/m4-wave-dispatch.err; then
      _blk=$(tr '\n' ' ' </tmp/m4-wave-dispatch.txt 2>/dev/null | sed 's/^BLOCK //')
      log "O-M4WAVE: defer $T — open characterize wave: ${_blk:-(see /tmp/m4-wave-dispatch.err)}"
      outer_log "         O-M4WAVE: HOLD convert until char wave complete — $T blocked by ${_blk}"
      lifecycle_blocked "$T" "m4-wave-hold open_char=${_blk}" "$(echo "$_blk" | awk '{print $1}')"
      # Flush any pending rewrite batch first; stop loop (no silent convert).
      flush_batch "$BATCH"; BATCH=""
      echo "m4-wave-hold" > /tmp/supervisor-done
      exit 78
    fi
  fi
  if [ "$(task_class "$T")" = "rewrite" ]; then
    BATCH="$BATCH $T"
    [ "$(echo $BATCH | wc -w | tr -d ' ')" -ge "$BATCH_MAX" ] && { flush_batch "$BATCH"; BATCH=""; check_seat_budget_overrun "batch" || true; }
    continue
  fi
  flush_batch "$BATCH"; BATCH=""
  run_task "$T" || true
  check_seat_budget_overrun "$T" || {
    echo "debt-freeze" > /tmp/supervisor-done
    exit 78
  }
done
flush_batch "$BATCH"; BATCH=""
check_seat_budget_overrun "M4-end" || true
if debt_frozen; then
  log "O-DEBTFRZ: M4 ended under debt freeze — not entering M5"
  echo "debt-freeze" > /tmp/supervisor-done
  exit 78
fi
# ADR-48 (d) / O-BLOCKSCHED: any BLOCKED task → typed story stop (not M5, not crash).
if [ -f .hermes/harness/task_lifecycle.py ]; then
  if ! python3 .hermes/harness/task_lifecycle.py blocked --ids $TASK_IDS \
      >/tmp/blocksched-m4end.txt 2>/tmp/blocksched-m4end.err; then
    _bn=$(awk '/^O-BLOCKSCHED:BLOCKED/{print $2}' /tmp/blocksched-m4end.txt 2>/dev/null || echo 0)
    log "O-BLOCKSCHED: ${_bn:-?} task(s) BLOCKED after M4 — typed stop (not entering M5)"
    outer_log "         O-BLOCKSCHED: BLOCKED tasks — $(tr '\n' ' ' </tmp/blocksched-m4end.txt | head -c 200)"
    echo "tasks-blocked" > /tmp/supervisor-done
    exit 78
  fi
fi
# O-PARTIALADV belt before M5
if _padv=$(partial_adv_blockers 2>/dev/null | head -5); [ -n "${_padv}" ]; then
  log "O-PARTIALADV: blocking M5 — unfinished Targets: $(echo "$_padv" | tr '\n' '; ')"
  echo "$_padv" > /tmp/partial-adv-blockers.txt
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
  # O-KANTRAMISS / O-KANTRAPATH: lazy-install; prefer PVC home over /tmp.
  # O-M5STALE: substitute/fail → STALE-AFTER (no RESOLVED credit, not "honest").
  # shellcheck source=kantra-path.sh
  . "$(dirname "${BASH_SOURCE[0]}")/kantra-path.sh" 2>/dev/null \
    || . .hermes/harness/kantra-path.sh 2>/dev/null || true
  export KANTRA_HOME="${KANTRA_HOME:-/projects/.tools/kantra}"
  if command -v kantra-ensure >/dev/null 2>&1; then
    kantra-ensure >> "$LOG" 2>&1 || log "WARN: O-KANTRAMISS — kantra-ensure failed"
  fi
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
  AFTER_SCAN_OK=0
  AFTER_SCAN_STALE=0
  KBIN=$(kantra_bin 2>/dev/null || true)
  if [ -n "$KBIN" ]; then
    if (cd /tmp && JAVA_HOME="${JAVA_HOME_21:-$JAVA_HOME}" PATH="${JAVA_HOME_21:-$JAVA_HOME}/bin:$PATH" \
      "$KBIN" analyze -i "$AFTER_SRC" -o /tmp/kantra-after \
      $K_ARGS --mode source-only --json-output --overwrite) >> "$LOG" 2>&1 \
      && cp /tmp/kantra-after/output.json migration/mta-findings-after.json 2>/dev/null; then
      AFTER_SCAN_OK=1
      log "M5 evaluate: after-analysis complete (script step; O-DELTASTAGING excluded staging/.hermes; bin=$KBIN)"
      # O-ANALYZERPIN: stamp after-engine sidecar (same engine as M1 pin).
      _KVER=$("$KBIN" version 2>/dev/null | head -1 || echo unknown)
      python3 .hermes/harness/analysis_engine_pin.py stamp --kind after \
        --bin "$KBIN" --version "$_KVER" --mode source-only \
        >> "$LOG" 2>&1 \
        || log "WARN: O-ANALYZERPIN after stamp failed"
    else
      AFTER_SCAN_STALE=1
      log "WARN: after-analysis failed — O-M5STALE (will not credit RESOLVED)"
    fi
  else
    AFTER_SCAN_STALE=1
    log "WARN: O-KANTRAMISS — kantra binary missing after kantra-ensure; O-M5STALE substitute"
    if [ -f migration/mta-findings-current.json ]; then
      cp migration/mta-findings-current.json migration/mta-findings-after.json 2>/dev/null \
        && log "M5 evaluate: O-KANTRAMISS — after-scan substituted from mta-findings-current.json (STALE)" \
        || true
    elif [ -f migration/mta-findings.json ]; then
      cp migration/mta-findings.json migration/mta-findings-after.json 2>/dev/null \
        && log "M5 evaluate: O-KANTRAMISS — after-scan substituted from mta-findings.json (STALE)" \
        || true
    fi
  fi
  # O-ANALYZERPIN: if after.json exists without pin (STALE substitute), copy
  # before-pin so delta does not false-mismatch; STALE path still unscores.
  if [ -f migration/mta-findings-after.json ] && [ ! -f migration/mta-findings-after.engine ]; then
    if [ -f migration/mta-findings.engine ]; then
      cp migration/mta-findings.engine migration/mta-findings-after.engine 2>/dev/null || true
    else
      python3 .hermes/harness/analysis_engine_pin.py stamp --kind after \
        --mode source-only >> "$LOG" 2>&1 || true
    fi
  fi
  # O-DELTABASE / O-M5STALE: mechanical absence-vs-conversion split.
  if [ -f migration/mta-findings-after.json ] && [ -f .hermes/harness/findings-delta.py ]; then
    if [ "$AFTER_SCAN_STALE" = "1" ] || [ "$AFTER_SCAN_OK" != "1" ]; then
      FINDINGS_DELTA_STALE=1 FINDINGS_DELTA_ROOT="$PWD" \
        python3 .hermes/harness/findings-delta.py \
        > migration/findings-delta.txt 2>/tmp/findings-delta.err \
        || log "WARN: findings-delta.py failed — see /tmp/findings-delta.err"
      echo "STALE-AFTER" > migration/findings-delta.STALE
    else
      rm -f migration/findings-delta.STALE
      FINDINGS_DELTA_ROOT="$PWD" python3 .hermes/harness/findings-delta.py \
        > migration/findings-delta.txt 2>/tmp/findings-delta.err \
        || log "WARN: findings-delta.py failed — see /tmp/findings-delta.err"
    fi
    cp migration/findings-delta.txt /tmp/findings-delta.txt 2>/dev/null || true
    log "M5 evaluate: O-DELTABASE summary — $(grep -m1 '^SUMMARY' migration/findings-delta.txt 2>/dev/null || echo n/a)"
    # O-DEBTFRZLEDGER (W4-289): M5 residual rules must land in debt.md, not
    # only in findings-delta / commit-message prose.
    if [ -f migration/findings-delta.txt ]; then
      _rem=$(grep -m1 '^SUMMARY' migration/findings-delta.txt 2>/dev/null \
        | sed -n 's/.*remaining=\([0-9][0-9]*\).*/\1/p' || true)
      if [ -n "${_rem:-}" ] && [ "$_rem" -gt 0 ] 2>/dev/null; then
        [ -f migration/debt.md ] || printf '# Migration debt\n\n' > migration/debt.md
        if grep -qE '^\(none\)$|^- \(none\)$|^None\.$' migration/debt.md 2>/dev/null; then
          sed -i.bak -E '/^\(none\)$/d; /^- \(none\)$/d; /^None\.$/d' migration/debt.md 2>/dev/null \
            || sed -i '' -E '/^\(none\)$/d; /^- \(none\)$/d; /^None\.$/d' migration/debt.md
          rm -f migration/debt.md.bak
        fi
        if ! grep -qE "^## M5 residuals — ${STORY_ID:-story}" migration/debt.md 2>/dev/null; then
          {
            printf '\n## M5 residuals — %s (%s remaining)\n' "${STORY_ID:-story}" "$_rem"
            printf -- '- head: %s\n' "$(git rev-parse --short HEAD 2>/dev/null)"
            printf -- '- source: migration/findings-delta.txt SUMMARY remaining=%s\n' "$_rem"
            grep -E '^(REMAINING|NEW-AFTER)' migration/findings-delta.txt 2>/dev/null | head -40 \
              | sed 's/^/- /' || true
          } >> migration/debt.md
          log "M5 evaluate: O-DEBTFRZLEDGER — wrote ${_rem} residual rules into migration/debt.md"
          event "m5-evaluate" 0 debt_m5_residuals "remaining=${_rem}"
        fi
      fi
      unset _rem
    fi
  fi
  # O-M5EVALHARVEST: evaluate explains delta + optional in-story pom/props fixes.
  # Never harvest-from-staging / invent later-story packages to clear REMAINING
  # or ABSENT-NOT-LANDED (Wave2 S01: MiniMax dumped model/repo/rest/service trees).
  # O-M5EVALDELETE: never delete landed src/main/java / required pom deps.
  _m5_eval_base=$(git rev-parse HEAD)
  run_stage "M5 evaluate" "m5-evaluate" \
"Use the migration-harness skill and read SHIPPING.md in its directory. All tasks are executed (see migration/run-log.md and migration/debt.md). Execute M5 evaluate per SHIPPING.md. The harness ALREADY RAN the after-analysis: migration/mta-findings-after.json AND migration/findings-delta.txt (O-DELTABASE). Use findings-delta.txt as the authoritative delta — ABSENT-NOT-LANDED and SCAFFOLD-PRESATISFIED must NOT be counted as resolved; only the RESOLVED section is story credit. O-M5STALE: if findings-delta.txt contains STALE-AFTER or stale_resolve_pct=UNSCORED, do NOT invent resolve % or move rules into RESOLVED — report STALE and re-run after-scan when kantra is available. Also cite METRIC src_main_java / residual_incidents. Optionally use extract_findings.py for remaining rule detail. Append the findings delta to the run-log with every remaining finding individually explained (resolved here / absent-not-landed / owned by a later story / genuine debt). Run .hermes/harness/sensors.sh preflight and record the result honestly — do NOT claim factory/preflight green unless that command exits 0 (L-M5e; mvn verify alone is not enough).
O-M5EVALHARVEST: Do NOT run harvest-from-staging or create/copy src/main/java packages for later stories. ABSENT-NOT-LANDED means explain in run-log (owned by later story / not landed yet) — never materialize those classes here. REMAINING pom/plugin rules (e.g. javaee-pom-to-quarkus-00030/00050): edit pom.xml only, or document as residual debt if out of this story's Owns. Story scope paths: ${STORY_SCOPE:-see roadmap}. Later classes (${LATER_CLASSES:-none}) are forbidden.
O-M5EVALDELETE: Do NOT delete or empty already-landed src/main/java under story Owns (including repository/**) and do NOT remove required deps (e.g. quarkus-spring-data-jpa) to clear REMAINING — document RED honestly instead.
${RUN_CONTRACT}
Commit prefix: 'M5 evaluate:'. DO NOT PUSH. O-M5EVALTESTMAIN: do NOT commit characterization tests that require src/main harvest transforms absent from this tip — co-commit approved main+tests or leave tests uncommitted. O-M5EVALBURN: ALWAYS commit findings-delta.txt + run-log append even when preflight is RED (honest L-M5e RED tip beats a no-commit burn)." \
"Use the migration-harness skill and read SHIPPING.md in its directory. Continue M5 evaluate; verify migration/mta-findings-after.json and migration/findings-delta.txt exist, run .hermes/harness/sensors.sh preflight, state GREEN or RED honestly in the commit message (L-M5e), then commit starting 'M5 evaluate:'. O-M5EVALHARVEST: no harvest / no later-story packages — pom/props/run-log only unless already in story scope. O-M5EVALDELETE: do not delete landed src/main/java or required pom deps. O-M5EVALBURN: commit findings-delta/run-log even on preflight RED. ${RUN_CONTRACT}" \
    || log "M5 evaluate: exhausted — shipping without final re-analysis commit"
  # O-M5EVALBURN: if the model seat burned with no tip, mechan-commit harness
  # findings artifacts so the story has an honest evaluate marker (not silence).
  if ! committed "M5 evaluate"; then
    if [ -f migration/findings-delta.txt ] || [ -f migration/mta-findings-after.json ]; then
      git add -f migration/findings-delta.txt migration/findings-delta.STALE \
        migration/mta-findings-after.json migration/mta-findings-after.engine \
        migration/mta-findings.engine migration/run-log.md 2>/dev/null || true
      if ! git diff --cached --quiet 2>/dev/null; then
        if SKIP_SENSOR_GATE=1 git commit -q -m \
          "M5 evaluate: O-M5EVALBURN mechan findings-delta (no model tip; preflight not claimed GREEN)" \
          >>"$LOG" 2>&1; then
          log "M5 evaluate: O-M5EVALBURN — mechan-committed findings artifacts after no-commit burn"
          event "m5-evaluate" 0 m5_eval_burn_mechan
        fi
      fi
    fi
  fi
  # O-M5EVALDELETE: working-tree or tip deletions under src/main/java / pom → restore + FREEZE (v2 S04).
  _m5_del=$(git diff --name-only --diff-filter=D "${_m5_eval_base}" -- src/main/java pom.xml 2>/dev/null || true)
  if committed "M5 evaluate"; then
    _m5_del=$(printf '%s\n%s\n' "${_m5_del}" \
      "$(git diff-tree --no-commit-id --name-only --diff-filter=D -r HEAD 2>/dev/null || true)" \
      | sed '/^$/d' | sort -u || true)
  fi
  if echo "${_m5_del}" | grep -qE '^(src/main/java/|pom\.xml$)'; then
    log "M5 evaluate: O-M5EVALDELETE — deleted tracked sources; restoring ${_m5_eval_base:0:7} and FREEZE"
    printf '%s\n' "${_m5_del}" >> "$LOG"
    git reset --hard "${_m5_eval_base}" >>"$LOG" 2>&1 || true
    git checkout -q "${_m5_eval_base}" -- src/main/java pom.xml 2>/dev/null || true
    touch /tmp/debt-freeze /tmp/supervisor-pause
    record_debt "m5-evaluate" "milestone" "O-M5EVALDELETE: evaluate deleted src/main/java or pom.xml"
    echo "debt-freeze" > /tmp/supervisor-done
    exit 78
  fi
  unset _m5_del _m5_eval_base
  # Refuse evaluate tips that land out-of-story Java packages (O-M5EVALHARVEST).
  if committed "M5 evaluate"; then
    _bad_eval=$(git diff-tree --no-commit-id --name-only -r HEAD 2>/dev/null \
      | grep -E '^src/main/java/.+/(model|repository|rest|service|mapper|dto|security|util)/' \
      | head -20 || true)
    if [ -n "${_bad_eval}" ] \
      && [ "${STORY_DEPLOY:-}" = "false" ] \
      && ! echo "${STORY_SCOPE:-}" | grep -qE 'model/|repository/|rest/|service/'; then
      log "M5 evaluate: O-M5EVALHARVEST — tip introduced out-of-story Java paths; resetting tip"
      printf '%s\n' "${_bad_eval}" >> "$LOG"
      git reset --hard HEAD~1 >>"$LOG" 2>&1 || true
      # Drop untracked later-story package trees (any targetPackage root).
      git status --porcelain --untracked-files=all 2>/dev/null \
        | awk '/^\?\? src\/main\/java\// {print $2}' \
        | grep -E '/(model|repository|rest|service|mapper|dto|security|util)(/|$)' \
        | while read -r d; do rm -rf "$d"; done
      git checkout -q HEAD -- src/main/java 2>/dev/null || true
    fi
    unset _bad_eval
  fi
  # L-M5e: mechanical honesty check — evaluate commit must not be treated as
  # ship-ready when preflight is RED (V8 S02 overstated evaluate).
  if committed "M5 evaluate"; then
    if .hermes/harness/sensors.sh preflight > /tmp/m5-evaluate-preflight.txt 2>&1; then
      log "M5 evaluate: preflight GREEN (L-M5e bar)"
    else
      log "M5 evaluate: preflight RED after evaluate commit (L-M5e) — not ship-ready; ship loop will correct — $(grep -E 'SENSOR RED|COVERAGE' /tmp/m5-evaluate-preflight.txt | head -3 | tr '\n' ' ')"
      # O-M5PRECLAIM + O-NOAMEND: tip subject must not claim preflight=GREEN when
      # proof is RED — record the lie in events/run-log; do **not** amend (sha-stable).
      _m5_subj=$(git log -1 --format=%s)
      if echo "$_m5_subj" | grep -qiE 'preflight[[:space:]]*=[[:space:]]*GREEN'; then
        log "M5 evaluate: O-M5PRECLAIM/O-NOAMEND — tip subject claims preflight=GREEN but proof is RED; sha=$(git rev-parse --short HEAD) left unchanged"
        event "m5-evaluate" 0 m5_preclaim_lie "preflight=RED sha=$(git rev-parse --short HEAD) (no-amend)"
      fi
      unset _m5_subj
    fi
    # O-M5EVALTESTMAIN: refuse evaluate tips that land src/test characterization
    # requiring src/main mutations absent from the tip (tests RED vs tip main).
    # Co-commit approved transforms + tests, or leave tests uncommitted.
    _m5_tests=$(git diff-tree --no-commit-id --name-only -r HEAD 2>/dev/null \
      | grep -E '^src/test/' | head -5 || true)
    _m5_main=$(git diff-tree --no-commit-id --name-only -r HEAD 2>/dev/null \
      | grep -E '^src/main/' | head -5 || true)
    if [ -n "${_m5_tests}" ] && [ -z "${_m5_main}" ]; then
      if ! .hermes/harness/sensors.sh task >/tmp/m5-evaluate-testmain.log 2>&1; then
        log "M5 evaluate: O-M5EVALTESTMAIN — tip landed src/test without src/main and task RED; resetting tip"
        event "m5-evaluate" 0 m5_eval_testmain_reset
        _arch="/tmp/strays/m5-evaluate-testmain-$(date -u +%Y%m%dT%H%M%SZ)"
        mkdir -p "$_arch"
        git show --stat HEAD >"$_arch/stat.txt" 2>&1 || true
        git show HEAD >"$_arch/full.diff" 2>&1 || true
        git reset --hard HEAD~1 >>"$LOG" 2>&1 || true
        record_debt "m5-evaluate" "milestone" \
          "O-M5EVALTESTMAIN: evaluate tests without co-committed src/main (task RED)" || true
      fi
    fi
    unset _m5_tests _m5_main _arch
  fi
fi

fi # SHIP_ONLY else (M1–M5 evaluate)

# ---------------------------------------------------------------- M5 ship
# O-HBPROGSTALE: keep progress fresh through ship/preflight/evidlive (not stuck
# on last M4 phase=done task).
m4_progress "ship"
# O-M5LIFECYCLE (W4-741 §3b): M5←M4 typed completion + tip SHA — not filesystem
# ALREADY COMPLETE. Lifecycle-aware: unstarted tasks are not gaps.
if [ -f .hermes/harness/task_lifecycle.py ] && [ -n "${TASK_IDS:-}" ]; then
  if ! python3 .hermes/harness/task_lifecycle.py m5-check --ids $TASK_IDS \
      > /tmp/m5-lifecycle-check.txt 2>/tmp/m5-lifecycle-check.err; then
    log "O-M5LIFECYCLE: REFUSE ship — typed completion gaps (see /tmp/m5-lifecycle-check.txt)"
    outer_log "         O-M5LIFECYCLE: ship blocked — M5←M4 tip_sha/ADVANCE gaps"
    echo "m5-lifecycle-gap" > /tmp/supervisor-done
    cat /tmp/m5-lifecycle-check.txt >> "$LOG" 2>/dev/null || true
    exit 78
  fi
  log "O-M5LIFECYCLE: m5-check OK (ADVANCE+tip_sha for ran tasks)"
fi
# O-M5OBSERVEFIRE (W4-754 §2): ADVANCE+tip_sha is not acceptance-clean when the
# live consumer-assert mode would refuse (char_surface / full refuse). Re-run at
# ship; reopen fired ADVANCE tasks (ADR-48b) — do not phase-rewind here.
_m5ca_mode="${M4_CONSUMER_ASSERT:-refuse-char}"
if [ "${_m5ca_mode}" != "off" ] && [ -f .hermes/harness/m4_consumer_assert.py ]; then
  _m5ca_args=(--mode="${_m5ca_mode}" --json=/tmp/m5-consumer-assert.json)
  [ -n "${STORY_ID:-}" ] && _m5ca_args+=(--story="${STORY_ID}")
  if ! python3 .hermes/harness/m4_consumer_assert.py "${_m5ca_args[@]}" \
      >>"$LOG" 2>&1; then
    log "O-M5OBSERVEFIRE: REFUSE ship — consumer-assert fires under mode=${_m5ca_mode} (not tip_sha-clean)"
    outer_log "         O-M5OBSERVEFIRE: ship blocked — consumer-assert REFUSE (see /tmp/m5-consumer-assert.json)"
    if [ -f /tmp/m5-consumer-assert.json ] && [ -f .hermes/harness/task_lifecycle.py ]; then
      while IFS= read -r _reopen_tid; do
        [ -n "$_reopen_tid" ] || continue
        lifecycle_reopen "$_reopen_tid" consumer_assert || true
      done < <(python3 - <<'PY'
import json
from pathlib import Path
try:
    data = json.loads(Path("/tmp/m5-consumer-assert.json").read_text(encoding="utf-8"))
except Exception:
    raise SystemExit(0)
mode = str(data.get("mode") or "")
seen = set()
for f in data.get("fires") or []:
    if not isinstance(f, dict):
        continue
    kind = str(f.get("assert") or "")
    if mode == "refuse-char" and kind != "char_surface":
        continue
    tid = str(f.get("task") or "").strip()
    if tid and tid not in seen and tid != "*":
        seen.add(tid)
        print(tid)
PY
)
    fi
    echo "m5-observe-fire" > /tmp/supervisor-done
    exit 78
  fi
  log "O-M5OBSERVEFIRE: consumer-assert OK at ship (mode=${_m5ca_mode})"
fi
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
pipeline_created()  { OC get pipelinerun "$1" -n "$NS" -o jsonpath='{.metadata.creationTimestamp}' 2>/dev/null; }
pipeline_revision() { OC get pipelinerun "$1" -n "$NS" -o jsonpath='{.spec.params[?(@.name=="revision")].value}' 2>/dev/null; }

# O-SHIPNOPRSTALE: uptodate O-SHIPNOPR may only judge a PR created at/after
# this ship session (and matching HEAD revision when known).
pipelinerun_session_fresh() { # $1=pr name → fresh|stale|no-pr
  local name="$1" created rev head sess decision
  [ -n "$name" ] || { echo no-pr; return; }
  created=$(pipeline_created "$name")
  rev=$(pipeline_revision "$name")
  head=$(git rev-parse HEAD 2>/dev/null || true)
  sess=""
  [ -f /tmp/ship-session-started ] && sess=$(tr -d '[:space:]' </tmp/ship-session-started)
  decision=$(python3 .hermes/harness/shipnoprstale-decide.py \
    "${created:-}" "${sess:-}" "${rev:-}" "${head:-}" 2>/dev/null || echo stale)
  echo "$decision"
}

wait_pipeline() { # $1=previous newest run; $2=1 if git push was up-to-date
  # O-SHIPNOPR / O-NOPUSHPR: when push is Truly "Everything up-to-date"
  # (SHIP_ONLY re-earn), fall back to the newest existing run. When push
  # advanced remote commits, a NEW PipelineRun is required — do NOT judge a
  # stale prior Succeeded run (S06 empty-delta false ship on …-push-7k7vn).
  # O-SHIPNOPRSTALE: uptodate judge-existing must still be post-session
  # (creation ≥ /tmp/ship-session-started) and revision-aligned with HEAD —
  # abandoned Failed/Succeeded PRs must not open Deploy-fix seats.
  # Decision core: nopushpr-decide.py + shipnoprstale-decide.py (instrumented).
  local prev="$1" push_uptodate="${2:-0}" name="" i decision freshness
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
    freshness=$(pipelinerun_session_fresh "$name")
    if [ "$freshness" != "fresh" ]; then
      # Give operator a short window to trigger a post-session PR (no Deploy-fix).
      log "M5 ship: O-SHIPNOPRSTALE — existing $name is pre-session/abandoned ($freshness); waiting for post-session PipelineRun"
      outer_log "         M5 ship: O-SHIPNOPRSTALE — refusing stale ${name}; waiting for new PipelineRun"
      local waited_name="" _wait_t0
      _wait_t0=$(date +%s)
      m4_progress "ship-wait-pr"
      for i in $(seq 1 36); do
        # O-SHIPWAITPULSE: outer-loop.log must not sit silent on "waiting for
        # factory pipeline" — pulse every 60s so waiting ≠ stuck.
        if [ $((i % 6)) -eq 1 ]; then
          outer_log "         … M5 ship still waiting for post-session PipelineRun ($(( $(date +%s) - _wait_t0 ))s; newest=${name}) — details ${LOG}"
          m4_progress "ship-wait-pr"
        fi
        waited_name=$(newest_pipelinerun)
        if [ -n "$waited_name" ] && [ "$waited_name" != "$name" ]; then
          if [ "$(pipelinerun_session_fresh "$waited_name")" = "fresh" ]; then
            name="$waited_name"
            freshness=fresh
            log "M5 ship: O-SHIPNOPRSTALE — post-session PipelineRun $name appeared"
            break
          fi
        fi
        # Same name may be replaced after delete; re-check newest.
        if [ -n "$waited_name" ] && [ "$(pipelinerun_session_fresh "$waited_name")" = "fresh" ]; then
          name="$waited_name"
          freshness=fresh
          log "M5 ship: O-SHIPNOPRSTALE — post-session PipelineRun $name appeared"
          break
        fi
        sleep 10
      done
      if [ "$freshness" != "fresh" ]; then
        log "M5 ship: O-SHIPNOPRSTALE — no post-session PipelineRun — ship-blocked-stale-pipeline (no Deploy-fix)"
        echo "none stale-pipeline"
        return
      fi
    fi
    log "M5 ship: no new PipelineRun (up-to-date push) — judging existing $name (O-SHIPNOPR; session-fresh)"
  elif [ "$decision" = "proceed" ] && [ -n "$name" ]; then
    # New PR after push: still refuse if revision≠HEAD (wrong trigger).
    freshness=$(pipelinerun_session_fresh "$name")
    if [ "$freshness" = "stale" ]; then
      log "M5 ship: O-SHIPNOPRSTALE — new PipelineRun $name failed session/revision check — ship-blocked-stale-pipeline"
      echo "none stale-pipeline"
      return
    fi
  fi
  m4_progress "ship-wait-pipeline"
  local _pipe_t0
  _pipe_t0=$(date +%s)
  for i in $(seq 1 120); do
    if [ $((i % 6)) -eq 1 ]; then
      outer_log "         … M5 ship still waiting on pipeline ${name} ($(( $(date +%s) - _pipe_t0 ))s) — details ${LOG}"
      m4_progress "ship-wait-pipeline"
    fi
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

# O-DEBTSHIPRACE: debt-freeze must hard-stop ship/preflight fix rounds.
# record_debt may land in the same second as evaluate→ship fallthrough;
# never start preflight-fix while /tmp/debt-freeze is set.
if debt_frozen; then
  log "M5 ship: O-DEBTSHIPRACE — debt-freeze present; refusing ship/preflight fix rounds"
  outer_log "         M5 ship: O-DEBTSHIPRACE — blocked by debt-freeze (no preflight fix)"
  touch /tmp/supervisor-pause
  echo "debt-freeze" > /tmp/supervisor-done
  exit 78
fi

log "M5 ship: shipping (namespace=$NS, sonar key=$SONAR_KEY)"
BUILD_R=0; GATE_R=0; DEPLOY_R=0; PREF_R=0
MAX_PER_CLASS=2
LAST_PUSHED=""
# O-PREFLIGHTDIM: fresh ship session gets a clean full-preflight budget.
# O-SHIPROUNDBASE: stamp exclusive ship-session base so Preflight/Gate/Build
# fix committed() checks do not auto-satisfy from prior-session tips under
# story RUN_BASE (W4-068a: r1 burned in ~26s after restart). Abandoned
# origin/main tips are not authority — fetch for geometry only; never pull/merge.
rm -f /tmp/preflight-count
git rev-parse HEAD >/tmp/ship-session-base
# O-SHIPNOPRSTALE: wall-clock session start — PipelineRuns created before
# this stamp are abandoned/prior-round and must not drive Deploy-fix.
date -u +%s >/tmp/ship-session-started
log "M5 ship: O-SHIPROUNDBASE — ship-session-base=$(tr -d '[:space:]' </tmp/ship-session-base)"
log "M5 ship: O-SHIPNOPRSTALE — ship-session-started=$(tr -d '[:space:]' </tmp/ship-session-started)"
if git fetch origin --prune >/tmp/ship-fetch.out 2>&1; then
  if ! git merge-base --is-ancestor origin/main HEAD 2>/dev/null \
    && ! git merge-base --is-ancestor HEAD origin/main 2>/dev/null; then
    log "M5 ship: O-SHIPROUNDBASE — origin/main diverged (not ancestor/descendant); abandoned remote tip is NOT authority (no pull/merge; O-SHIPREMOTE blocks non-FF)"
    outer_log "         M5 ship: O-SHIPROUNDBASE — diverged origin/main ignored as authority (reconcile before push)"
  fi
else
  log "M5 ship: O-SHIPROUNDBASE — git fetch origin failed (continuing; push may hit O-SHIPREMOTE)"
fi
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
    # O-SHIPSTRAYSTRUCT: never archive declared structure .gitkeep Targets —
    # they are task deliverables awaiting commit, not fabrication pollution
    # (W4 T-003: ship swept dto/.gitkeep after false already-complete skip).
    _keep_struct=""
    if [ -n "${TASKS_FILE:-}" ]; then
      for _tid in $(grep -oE 'T-[A-Za-z0-9]*[0-9]+' "$TASKS_FILE" 2>/dev/null | sort -u); do
        _keep_struct="$_keep_struct $(structure_gitkeep_targets "$_tid")"
      done
    fi
    _arch_list=""
    while read -r f; do
      [ -n "$f" ] || continue
      _skip=0
      for _k in $_keep_struct; do
        [ "$f" = "$_k" ] && _skip=1 && break
      done
      [ "$_skip" = "1" ] && continue
      _arch_list="$_arch_list $f"
    done <<EOF
$(git ls-files --others --exclude-standard -- src/)
EOF
    if [ -n "$(echo $_arch_list | tr -d ' ')" ]; then
      log "M5 ship: archiving untracked src/ strays before preflight (fabrication-pollution guard): $_arch_list"
      mkdir -p /tmp/strays/preflight
      for f in $_arch_list; do
        mkdir -p "/tmp/strays/preflight/$(dirname "$f")"
        mv "$f" "/tmp/strays/preflight/$f" 2>/dev/null || rm -f "$f"
      done
    else
      log "M5 ship: O-SHIPSTRAYSTRUCT — kept untracked structure Target(s); no strays archived"
    fi
  fi
  # Pre-push preflight (cart run #2): the factory failed maven-build on a
  # defect (unpinned compiler plugin) the local full check catches — never
  # burn a pipeline round on a locally-detectable failure. Bounded like
  # every fix class; when the budget is spent, O-SHIPBUDGET runs one
  # closing preflight then HOLDs if still RED (no push-anyway).
  m4_progress "preflight"
  _pref_ok=0
  if .hermes/harness/sensors.sh preflight > /tmp/preflight-failure.next 2>&1; then
    cp /tmp/preflight-failure.next /tmp/preflight-failure.txt
    _pref_ok=1
  elif grep -qE 'REFUSED \(O-PREFLIGHTDIM\)' /tmp/preflight-failure.next 2>/dev/null; then
    # O-PREFDIMTHRASH / O-PFEVID: REFUSED is a budget signal, not unpaid RED.
    # Do not clobber real QUALITYGATE evidence with refuse; reset count and
    # run ONE closing preflight before burning a fix seat (wake#184 thrash).
    log "M5 ship: O-PREFDIMTHRASH — full-preflight cap refuse; reset count + one closing preflight (no seat on refuse)"
    outer_log "         M5 ship: O-PREFDIMTHRASH — refuse→reset→closing preflight (not a fix seat)"
    event "m5-ship" 0 preflightdim_refuse_reset "cap"
    cat /tmp/preflight-failure.next >> /tmp/preflight-refuse.log 2>/dev/null || true
    # O-PFEVID: keep prior real evidence if present; refuse goes to refuse.log only.
    if ! grep -qE 'QUALITYGATE|new_violations|coverage|java:S' /tmp/preflight-failure.txt 2>/dev/null; then
      if [ -f /tmp/sensor-sonar.log ] && grep -qE 'QUALITYGATE|java:S' /tmp/sensor-sonar.log 2>/dev/null; then
        grep -E 'QUALITYGATE|FAIL|java:S|coverage|ERROR' /tmp/sensor-sonar.log \
          | tail -n 40 > /tmp/preflight-failure.txt 2>/dev/null || true
        echo "(O-PFEVID: restored from sensor-sonar.log after O-PREFLIGHTDIM refuse)" \
          >> /tmp/preflight-failure.txt
      fi
    fi
    rm -f /tmp/preflight-count
    if .hermes/harness/sensors.sh preflight > /tmp/preflight-failure.txt 2>&1; then
      log "M5 ship: closing preflight GREEN after O-PREFLIGHTDIM reset"
      _pref_ok=1
    else
      log "M5 ship: closing preflight still RED after dim reset — proceeding to fix rounds"
    fi
  else
    cp /tmp/preflight-failure.next /tmp/preflight-failure.txt
  fi
  rm -f /tmp/preflight-failure.next
  if [ "$_pref_ok" != "1" ]; then
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
    # O-SONAR401: Sonar auth/bootstrap RED is infra — never burn MiniMax
    # preflight-fix seats (W4 wake43/44: preflight named O-SONAR401 401).
    if grep -qE 'O-SONAR401|HTTP 401|401 Unauthorized|scanner bootstrapping has failed' \
      /tmp/preflight-failure.txt 2>/dev/null; then
      event "m5-ship" 0 ship_blocked sonar_auth
      record_debt "M5 ship" sonar \
        "O-SONAR401 Sonar auth 401 — refresh SONAR_TOKEN; preflight-fix skipped"
      log "M5 ship: BLOCKED — O-SONAR401 Sonar auth failed. Not burning preflight-fix seats."
      outer_log "         M5 ship: BLOCKED — Sonar 401; refresh SONAR_TOKEN (O-SONAR401)"
      write_run_report "ship-blocked-sonar-auth"
      echo "ship-blocked-sonar-auth" > /tmp/supervisor-done
      exit 3
    fi
    if [ "$PREF_R" -le "$MAX_PER_CLASS" ]; then
      # O-SFIXALREADYGREEN / O-SHIPPUSHONRED: never dispatch a fix seat on a
      # stale metric — re-run preflight first. W4-664: ship burned MiniMax on
      # 0.0% coverage evidence after the tree was already GREEN.
      # O-SFIXALREADYGREEN-METRIC (W4-667 CHANGE): skip only when a *fresh*
      # numeric new_coverage is known; never scrape /tmp/preflight-failure.txt
      # on the GREEN path; unknown coverage → do not skip (fall to fix route).
      _ship_fresh_new_coverage() { # $1=fresh preflight out → pct or empty
        local f="$1" pct=""
        [ -f "$f" ] || { printf ''; return 0; }
        pct=$(grep -oE 'new_coverage[=: ]+[0-9]+(\.[0-9]+)?' "$f" 2>/dev/null \
          | head -1 | grep -oE '[0-9]+(\.[0-9]+)?$' || true)
        if [ -z "$pct" ]; then
          local host="${SONAR_HOST:-http://sonarqube.sonarqube.svc:9000}"
          local key
          key=$(basename "$(git remote get-url origin 2>/dev/null || echo fixture)" .git)
          pct=$(curl -sf "${host}/api/measures/component?component=${key}&metricKeys=new_coverage" 2>/dev/null \
            | python3 -c 'import json,sys
try:
  d=json.load(sys.stdin)
  for m in d.get("component",{}).get("measures",[]):
    if m.get("metric")=="new_coverage":
      print(m.get("period",{}).get("value") or m.get("value") or "")
      break
except Exception:
  pass' 2>/dev/null || true)
        fi
        printf '%s' "${pct:-}"
      }
      rm -f /tmp/preflight-count
      if .hermes/harness/sensors.sh preflight > /tmp/preflight-pre-fixcheck.txt 2>&1; then
        _cov=$(_ship_fresh_new_coverage /tmp/preflight-pre-fixcheck.txt)
        if [ -n "${_cov:-}" ]; then
          cp -f /tmp/preflight-pre-fixcheck.txt /tmp/preflight-success.txt
          log "M5 ship: O-SFIXALREADYGREEN — preflight GREEN before fix seat r${PREF_R}; skipping MiniMax — new_coverage=${_cov}% (fresh)"
          outer_log "         M5 ship: O-SFIXALREADYGREEN — new_coverage=${_cov}% fresh GREEN (no fix seat)"
          event "m5-ship" 0 preflight_already_green "round=$PREF_R;new_coverage=${_cov}"
          _pref_ok=1
        else
          # Amendment 1: GREEN without a measurable coverage number ≠ skip.
          log "M5 ship: O-SFIXALREADYGREEN-METRIC — preflight GREEN but no fresh new_coverage — not skipping MiniMax"
          outer_log "         M5 ship: O-SFIXALREADYGREEN-METRIC — unknown coverage; fall through to fix route"
          event "m5-ship" 0 preflight_green_unknown_coverage "round=$PREF_R"
          cp -f /tmp/preflight-pre-fixcheck.txt /tmp/preflight-failure.txt
          # Fall into fix-seat branch below (do not set _pref_ok).
          :
        fi
      fi
      if [ "$_pref_ok" = "1" ]; then
        :
      else
      # Fresh evidence for the fix seat: prefer this iteration's pre-fixcheck
      # (RED or GREEN-without-coverage). Never trust a stale failure file alone.
      if [ -s /tmp/preflight-pre-fixcheck.txt ]; then
        cp -f /tmp/preflight-pre-fixcheck.txt /tmp/preflight-failure.txt
      elif [ ! -s /tmp/preflight-failure.txt ]; then
        .hermes/harness/sensors.sh preflight > /tmp/preflight-failure.txt 2>&1 || true
      fi
      log "M5 ship: pre-push preflight needs fix seat r${PREF_R} (RED or GREEN-without-coverage) — fixing before push"
      outer_log "         M5 ship: preflight fix round ${PREF_R}/${MAX_PER_CLASS} starting"
      event "m5-ship" 0 "preflight_red" "round=$PREF_R"
      # O-PREFDIMTHRASH / O-PFCOUNTRM: each fix round gets a fresh full-preflight
      # budget so seats are not stuck on REFUSED with no real unpaid evidence.
      rm -f /tmp/preflight-count
      if ! run_stage "Preflight fix r${PREF_R}" "preflightfix-r${PREF_R}" \
"Use the migration-harness skill and read SHIPPING.md in its directory. The pre-push preflight is RED - the failure evidence is in /tmp/preflight-failure.txt, read it with your file tools. Fix the root cause (build wiring against the WORKING scaffold pom conventions; coverage gaps need real tests for the uncovered classes - never weaken assertions; keep typed assertThrows(UnsupportedOperationException) for unmodifiable getters — O-SHIPASSERTWEAK). O-SONARFIX/S5778: arrange mutation outside a single-invocation assertThrows — do NOT thrash brace/bind/assertj cosmetics or add unused assertj-core to pom. Prefer .hermes/harness/sensors.sh sonar|task (dim) then ONE closing preflight. O-SHIPFIXCOMMIT: when local mvn test / sensors.sh task is GREEN on tests-only dirt, COMMIT the 'Preflight fix r${PREF_R}:' tip BEFORE running full sensors.sh preflight/sonar — unpaid green tests must not burn the seat timeout. Do not commit unrelated pom deps in a tests-only tip (O-SHIPFIXPOM). Finish with .hermes/harness/sensors.sh preflight GREEN when budget allows, then commit ONE commit. DO NOT PUSH.
O-M5SHIPHARVEST: Do NOT harvest-from-staging or create later-story packages (model/repository/rest/service/…) to clear preflight. If O-QJACOCO / coverage RED and this story has no @QuarkusTest yet (platform/POM story), do not invent app code — fix pom/wiring only or stop with /tmp/escalation-noaction-preflightfix.txt. Story scope: ${STORY_SCOPE:-roadmap}. Later classes forbidden: ${LATER_CLASSES:-none}.
${RUN_CONTRACT}
Commit prefix: 'Preflight fix r${PREF_R}:'." \
"Use the migration-harness skill and read SHIPPING.md in its directory. O-PREFCONT: Inspect git status FIRST. Continue from EXISTING dirty/untracked work WITHOUT inventing new files/tests and WITHOUT rewriting already-present dirty tip content. Characterization floor: do not shrink @Test / assertion counts; keep typed assertThrows(UnsupportedOperationException) (O-SHIPASSERTWEAK). O-SONARFIX/S5778: arrange outside assertThrows — no brace/assertj cosmetic thrash. O-SHIPFIXCOMMIT: tip task-GREEN tests-only dirt before sonar when the seat is tight (src/test only — O-SHIPFIXPOM). Finish the root-cause fix from /tmp/preflight-failure.txt, run dim sensors then ONE closing preflight until GREEN when budget allows, and commit ONE commit starting 'Preflight fix r${PREF_R}:'. DO NOT PUSH. O-M5SHIPHARVEST: no harvest / no later-story packages.
${RUN_CONTRACT}"
      then
        log "M5 ship: preflight-fix round $PREF_R did not converge"
        # O-SHIPPUSHONRED (W4-664): after a failed fix seat, re-measure. Only
        # continue the ship loop when fresh preflight is GREEN; never fall into
        # K12/push on the strength of a stale failure file or a no-op seat.
        rm -f /tmp/preflight-count
        if .hermes/harness/sensors.sh preflight > /tmp/preflight-failure.txt 2>&1; then
          log "M5 ship: O-SHIPPUSHONRED — fresh preflight GREEN after non-converged seat; proceeding"
          event "m5-ship" 0 preflight_green_after_nonconverge "round=$PREF_R"
          _pref_ok=1
        else
          log "M5 ship: O-SHIPPUSHONRED — still RED after non-converged seat; not pushing this iteration"
          event "m5-ship" 0 preflight_still_red_after_nonconverge "round=$PREF_R"
          continue
        fi
      else
        # Seat claimed success — still require a fresh GREEN preflight (no trust).
        rm -f /tmp/preflight-count
        if .hermes/harness/sensors.sh preflight > /tmp/preflight-failure.txt 2>&1; then
          _pref_ok=1
        else
          log "M5 ship: O-SHIPPUSHONRED — fix seat returned but preflight still RED; continuing"
          continue
        fi
      fi
      fi
      # When _pref_ok=1 from this block, skip budget path below and fall to K12.
      if [ "$_pref_ok" != "1" ]; then
        continue
      fi
    fi
    # Budget / fidelity path only when fix rounds are exhausted and still RED.
    if [ "$_pref_ok" != "1" ]; then
    # Fidelity / legacy-package cannot be arbitrated by the factory.
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
    # O-SHIPBUDGET: never "push anyway" on unpaid preflight (esp. boot RED).
    # One untimed closing preflight after the fix-round budget; GREEN → push.
    # Still RED → HOLD + debt (factory cannot invent schema/Flyway/wiring).
    log "M5 ship: O-SHIPBUDGET — fix budget spent; one closing preflight (no push-anyway)"
    outer_log "         M5 ship: O-SHIPBUDGET — closing preflight after budget (refuse push-anyway)"
    rm -f /tmp/preflight-count
    if .hermes/harness/sensors.sh preflight > /tmp/preflight-failure.txt 2>&1; then
      log "M5 ship: O-SHIPBUDGET closing preflight GREEN — proceeding to push"
      _pref_ok=1
    else
      _boot_red=0
      grep -qiE 'SENSOR RED \(boot\)|Schema-validation|SchemaManagementException|missing table' \
        /tmp/preflight-failure.txt 2>/dev/null && _boot_red=1
      event "m5-ship" 0 ship_blocked preflight_budget
      if [ "$_boot_red" = "1" ]; then
        record_debt "M5 ship" boot \
          "O-SHIPBUDGET unpaid boot RED after preflight fix budget (see /tmp/preflight-failure.txt) — not pushing"
        log "M5 ship: BLOCKED — O-SHIPBUDGET unpaid boot RED after fix budget. Story NOT shipped."
        outer_log "         M5 ship: BLOCKED — O-SHIPBUDGET boot RED unpaid (no push-anyway)"
      else
        record_debt "M5 ship" preflight \
          "O-SHIPBUDGET preflight budget exhausted with unpaid RED (see /tmp/preflight-failure.txt) — not pushing"
        log "M5 ship: BLOCKED — O-SHIPBUDGET unpaid preflight after fix budget. Story NOT shipped."
        outer_log "         M5 ship: BLOCKED — O-SHIPBUDGET unpaid preflight (no push-anyway)"
      fi
      write_run_report "ship-blocked-preflight-budget"
      echo "ship-blocked-preflight-budget" > /tmp/supervisor-done
      exit 3
    fi
    fi
  fi
  # O-SHIPPUSHONRED (W4-664): final belt — never K12/push unless _pref_ok and a
  # fresh preflight is GREEN in this iteration (stale failure files cannot ship).
  if [ "$_pref_ok" != "1" ]; then
    event "m5-ship" 0 ship_blocked preflight_not_ok
    record_debt "M5 ship" preflight \
      "O-SHIPPUSHONRED refused push — _pref_ok!=1 (see /tmp/preflight-failure.txt)"
    log "M5 ship: BLOCKED — O-SHIPPUSHONRED preflight not GREEN. Story NOT shipped."
    write_run_report "ship-blocked-preflight-red"
    echo "ship-blocked-preflight-red" > /tmp/supervisor-done
    exit 3
  fi
  rm -f /tmp/preflight-count
  if ! .hermes/harness/sensors.sh preflight > /tmp/preflight-prepush.txt 2>&1; then
    cp /tmp/preflight-prepush.txt /tmp/preflight-failure.txt
    event "m5-ship" 0 ship_blocked preflight_prepush_red
    record_debt "M5 ship" preflight \
      "O-SHIPPUSHONRED final pre-push preflight RED — not pushing (see /tmp/preflight-prepush.txt)"
    log "M5 ship: BLOCKED — O-SHIPPUSHONRED final pre-push preflight RED. Story NOT shipped."
    outer_log "         M5 ship: BLOCKED — O-SHIPPUSHONRED final preflight RED (no push)"
    write_run_report "ship-blocked-preflight-red"
    echo "ship-blocked-preflight-red" > /tmp/supervisor-done
    exit 3
  fi
  cp /tmp/preflight-prepush.txt /tmp/preflight-failure.txt
  log "M5 ship: O-SHIPPUSHONRED final pre-push preflight GREEN — proceeding to K12/push"

  # K12: adversarial refute of tip before push (escalation+ship high-stakes).
  if ! refute_high_stakes HEAD "m5-ship-k12"; then
    event "m5-ship" 0 ship_blocked k12_refuted
    record_debt "M5 ship" k12 "pre-push REFUTED (see migration/refute-log.md)"
    log "M5 ship: BLOCKED — K12 refute refused the tip. Story NOT shipped."
    write_run_report "ship-blocked-k12"; echo "ship-blocked-k12" > /tmp/supervisor-done; exit 3
  fi
  PREV=$(newest_pipelinerun)
  # O-SHIPREMOTE (W4-026a): name non-fast-forward / diverged remotes distinctly —
  # after wipe+restart, origin/main may still carry the aborted run tip.
  # Never force-push from the harness; operator reconciles with full SHA.
  if ! PUSH_OUT=$(git push origin main 2>&1); then
    echo "$PUSH_OUT" >> "$LOG"
    if echo "$PUSH_OUT" | grep -qiE 'non-fast-forward|\[rejected\].*\(non-fast-forward\)|fetch first|tip of your current branch is behind'; then
      event "m5-ship" 0 ship_blocked remote_diverged
      record_debt "M5 ship" remote \
        "O-SHIPREMOTE origin/main diverged (non-fast-forward) — operator force-update with full SHA or ship other branch; harness will not force-push"
      log "M5 ship: BLOCKED — O-SHIPREMOTE remote diverged (non-fast-forward). Not force-pushing."
      outer_log "         M5 ship: BLOCKED — origin/main diverged; reconcile remote before ship (O-SHIPREMOTE)"
      write_run_report "ship-blocked-remote-diverged"
      echo "ship-blocked-remote-diverged" > /tmp/supervisor-done
      exit 3
    fi
    log "FATAL: git push failed"
    write_run_report "push-failed"
    echo push-failed > /tmp/supervisor-done
    exit 1
  fi
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
  # O-SHIPNOPRSTALE: abandoned/prior-round PipelineRun must HOLD — never
  # open Deploy/Build/Gate fix seats on a pre-session Failed/Succeeded run.
  if [ "$PR_ST" = "stale-pipeline" ]; then
    event "m5-ship" 0 ship_blocked stale_pipeline
    record_debt "M5 ship" pipeline \
      "O-SHIPNOPRSTALE: uptodate push with only pre-session PipelineRun(s) — trigger a new run for HEAD or reconcile; no Deploy-fix" || true
    log "M5 ship: BLOCKED — O-SHIPNOPRSTALE stale/abandoned PipelineRun (no Deploy-fix). Story NOT shipped."
    outer_log "         M5 ship: BLOCKED — O-SHIPNOPRSTALE stale pipeline (need post-session PipelineRun)"
    write_run_report "ship-blocked-stale-pipeline"
    echo "ship-blocked-stale-pipeline" > /tmp/supervisor-done
    exit 3
  fi
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
      if review_hold_blocks_ship; then
        exit 3
      fi
      if evidence_liveness_blocks_ship; then
        exit 3
      fi
      event "m5-ship" 0 "story_gate_pass" "non-deploy story"
      clear_debt
      write_run_report "story gate passed (non-deploy story): pipeline + quality gate green"
      phase_f_retro
      ship_only_record_complete
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
      if review_hold_blocks_ship; then
        exit 3
      fi
      if evidence_liveness_blocks_ship; then
        exit 3
      fi
      event "m5-ship" 0 "acceptance_pass" "route=${CODE},${ACC_COLLECTION}=${PRODUCTS}"
      clear_debt
      write_run_report "success: shipped, route 200, ${PRODUCTS} ${ACC_COLLECTION}"
      phase_f_retro
      ship_only_record_complete
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
