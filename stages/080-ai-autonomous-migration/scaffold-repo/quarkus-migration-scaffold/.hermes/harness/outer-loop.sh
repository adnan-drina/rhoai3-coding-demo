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
# O-M3ROUTE: M3 SPECIFY — MiniMax-first default (W4R7 operator 2026-08-05:
# "keep running minimax"). Qwen fix-seat remains via O-M3WORKERREENTRY after
# MiniMax RED/429 on populated tasks.md (ungated; does not require
# WORKER_M3_FIRST=true). Set WORKER_M3_FIRST=true only for explicit Qwen-draft A/B.
# Inline ${WORKER_M3_FIRST:-…} defaults below MUST match this line.
WORKER_M3_FIRST="${WORKER_M3_FIRST:-false}"
# ADR-35/40 — typed model.tasks[] + write-inversion Qwen loop (default ON).
# Set M3_TYPED_LOOP=0 to force legacy MiniMax edit-tasks.md path.
M3_TYPED_LOOP="${M3_TYPED_LOOP:-1}"
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

# O-LOGSTORY / O-LOGFULLSTORY: in-story log() prefix is full slug (S01-platform-…) ▸.
# STORY_TAG is empty for M1/M2 and between stories — do not set at call sites.
STORY_TAG="${STORY_TAG:-}"
log() { echo "[$(date -u +%F' '%T)]${STORY_TAG:+ $STORY_TAG}$([ -n "${STORY_TAG:-}" ] && echo ' ▸') $*" >> "$LOG"; }
phase_start() { # $1=code+title  [$2=extra]
  # O-PHASESTARTRC: must return 0 — `[ -n '' ] && log` returns 1 under set -e
  # and aborted outer at one-arg phase_start (M3 worker START → TMPARCHIVE only).
  log "$(_sym '▶' '>') START  $1"
  if [ -n "${2:-}" ]; then
    log "         $2"
  fi
  return 0
}
phase_ok() { log "$(_sym '✓' 'OK') END    $1"; }
phase_fail() { log "$(_sym '✗' 'X') FAIL   $1"; }
phase_gate() { # $1=name $2=RED|GREEN $3=detail
  if [ "$2" = "GREEN" ]; then log "$(_sym '✓' 'OK') GATE   $1 — GREEN${3:+ — $3}"
  else log "$(_sym '✗' 'X') GATE   $1 — RED${3:+ — $3}"; fi
}
phase_retry() { log "$(_sym '↻' 'R') RETRY  $1"; }

# O-GROUNDLOG: demo-facing G1–G10 lines in outer-loop.log (question + result only).
# No ADR identifiers in user-visible log text. Honest NOT-LANDED for open guards.
_count_re() { # $1=file $2=regex → count (0 if missing)
  local f="$1" re="$2" n
  [ -f "$f" ] || { echo 0; return 0; }
  n=$(grep -cE "$re" "$f" 2>/dev/null || true)
  echo "${n:-0}"
}
# $1=Gid $2=PASS|FAIL|SKIP|NOT-LANDED $3=question $4=evidence detail
log_ground() {
  log "GROUND  $1 — $2"
  log "         Q: $3"
  log "         $4"
}
log_gchain_banner() {
  log "GROUND  G1–G10 — grounding checks"
  log "         Each step sits at one pipeline handoff and answers: is what this"
  log "         stage produced actually derived from what the previous stage gave it?"
  log "         M1: G1/G2 · M2: G3/G6/G7/G8 · M3: G4 (inline) · M3 authoring: G5/G9 · M4: G10"
}
# M1 PROFILE gate → G1 + G2 (problem lists from live rubric) + coverage from
# evaluate_roles SoT (O-PROFCOVSTALE — never grep stale COVERAGE: from rubric).
log_gchain_m1_profile() { # $1=GREEN|RED (overall rubric; narrated separately)
  local gate="${1:-}" ct pv cov named total authored emiss fields
  ct=$(_count_re /tmp/profile-rubric.txt 'RUBRIC:claimtruth')
  pv=$(_count_re /tmp/profile-rubric.txt 'RUBRIC:profvocab')
  fields=$(_profile_cov_fields || true)
  named=$(echo "$fields" | awk '{print $1}')
  total=$(echo "$fields" | awk '{print $2}')
  authored=$(echo "$fields" | awk '{print $3}')
  emiss=$(echo "$fields" | awk '{print $4}')
  if [ -n "${named:-}" ] && [ -n "${total:-}" ]; then
    cov="${named}/${total} named (authored=${authored:-?} evidence_miss=${emiss:-?} · evaluate_roles SoT)"
  else
    cov="(evaluate_roles unavailable)"
  fi
  if [ "${ct:-0}" -eq 0 ]; then
    log_ground "G1" "PASS" \
      "Does the architecture profile only claim things that exist in the legacy source?" \
      "0 claimtruth findings — every §7 (Class Roles & Target Contract) cited token resolves in the cited legacy file (rubric ${gate})"
  else
    log_ground "G1" "FAIL" \
      "Does the architecture profile only claim things that exist in the legacy source?" \
      "${ct} claimtruth findings — see /tmp/profile-rubric.txt (rubric ${gate})"
  fi
  if [ "${pv:-0}" -eq 0 ]; then
    log_ground "G2" "PASS" \
      "Is every architecture word in the profile native to this specimen (not leftover from a prior demo app)?" \
      "0 vocab findings — no prior-specimen residue (rubric ${gate})"
  else
    log_ground "G2" "FAIL" \
      "Is every architecture word in the profile native to this specimen (not leftover from a prior demo app)?" \
      "${pv} vocab findings — see /tmp/profile-rubric.txt (rubric ${gate})"
  fi
  log "         coverage ${cov} · G3/G5/G6/G9 checked at later stages"
}
# O-PROFSECTIONS — after PROFILE GREEN, keep a full §§1–7 dump in a side file
# and put only a compact summary in outer-loop.log (O-PROFSECTIONNOISE / W5-093:
# reprinting every §7 role bullet polluted the live progress log).
log_architecture_profile_sections() {
  local p="${1:-migration/architecture-profile.md}"
  if [ ! -f "$p" ]; then
    log "         O-PROFSECTIONS: $p missing — cannot log §§1–7"
    return 0
  fi
  log "PROFILE  architecture-profile.md — sections 1–7"
  # Full forensic dump (not mirrored line-by-line into outer-loop.log).
  python3 "$HARNESS/profile_sections_log.py" "$p" \
    > /tmp/outer-m1-profile-sections.log 2>&1 || true
  # Compact summary for the live progress sink.
  python3 "$HARNESS/profile_sections_log.py" --summary "$p" \
    > /tmp/outer-m1-profile-sections-summary.log 2>&1 || true
  while IFS= read -r _ps; do
    log "         ${_ps}"
  done < /tmp/outer-m1-profile-sections-summary.log
  return 0
}
# M2 roadmap-lint gate → G7 + G8; G3/G6 honesty
log_gchain_m2_roadmap() { # $1=GREEN|RED
  local gate="${1:-}" consist fresh fab lintf
  lintf=/tmp/roadmap-lint.txt
  [ -f /tmp/roadmap-lint-m2exit.txt ] && lintf=/tmp/roadmap-lint-m2exit.txt
  [ -f /tmp/roadmap-lint.txt ] && lintf=/tmp/roadmap-lint.txt
  consist=$(_count_re "$lintf" 'O-BRIEFCONSIST')
  fresh=$(_count_re "$lintf" 'O-BRIEFFRESH')
  fab=$(_count_re "$lintf" 'LINT:fabrication')
  log_ground "G3" "NOT-LANDED" \
    "Do fenced config quotes in the briefs match the legacy files byte-for-byte?" \
    "not enforced yet — would catch invented jdbc/config literals attributed to legacy files"
  if [ "${fab:-0}" -gt 0 ]; then
    log_ground "G6" "FAIL" \
      "Do brief claims about real symbols tell the truth (same bar as G1, at the M2 handoff)?" \
      "${fab} fabrication findings on presence-only half-check — full brief claimtruth still NOT-LANDED"
  else
    log_ground "G6" "NOT-LANDED" \
      "Do brief claims about real symbols tell the truth (same bar as G1, at the M2 handoff)?" \
      "0 fabrication findings on presence-only half-check; full brief claimtruth still open"
  fi
  if [ "${consist:-0}" -eq 0 ]; then
    log_ground "G7" "PASS" \
      "Are the story briefs self-consistent (no preserve-X while forbidding X's only enabler)?" \
      "0 consistency findings (roadmap ${gate})"
  else
    log_ground "G7" "FAIL" \
      "Are the story briefs self-consistent (no preserve-X while forbidding X's only enabler)?" \
      "${consist} consistency findings — ${lintf} (roadmap ${gate})"
  fi
  if [ "${fresh:-0}" -eq 0 ]; then
    log_ground "G8" "PASS" \
      "Are the briefs still derived from the current profile §7 (Class Roles & Target Contract) (not a stale paste after M1 corrected)?" \
      "0 freshness findings — brief hashes include profile §7 (Class Roles & Target Contract) digest (roadmap ${gate})"
  else
    log_ground "G8" "FAIL" \
      "Are the briefs still derived from the current profile §7 (Class Roles & Target Contract) (not a stale paste after M1 corrected)?" \
      "${fresh} freshness findings — ${lintf} (roadmap ${gate})"
  fi
}
# M3 derived-facts inline → G4 (population from evidence_kinds_for_acceptance)
log_gchain_m3_g4() { # $1=derived-facts text  $2=story id
  local block="${1:-}" sid="${2:-}" status detail
  status="FAIL"; detail="${sid}: ground_chain unavailable"
  if [ -f "${HARNESS:-.hermes/harness}/ground_chain.py" ]; then
    # stdin = block; kinds derived from typed acceptance when model present
    out=$(printf '%s\n' "$block" | python3 "${HARNESS:-.hermes/harness}/ground_chain.py" g4 \
      --root . --sid "${sid}" 2>/dev/null || true)
    status=$(printf '%s\n' "$out" | awk -F'\t' 'NR==1{print $1}')
    detail=$(printf '%s\n' "$out" | awk -F'\t' 'NR==1{print $2}')
    [ -n "$status" ] || status="FAIL"
    [ -n "$detail" ] || detail="${sid}: empty g4 verdict"
  elif printf '%s\n' "$block" | grep -q 'BEGIN DERIVED FACTS'; then
    status="PASS"; detail="${sid}: header present (legacy fallback — ground_chain.py missing)"
  fi
  log_ground "G4" "$status" \
    "Are acceptance-declared evidence facts inlined so the planner cannot invent them?" \
    "${detail}"
}
# M3 plan-lint → G5 + G9 (after SPECIFIED only; real verdicts via ground_chain)
log_gchain_m3_plan() { # $1=GREEN|RED|UNSPECIFIED $2=story id
  # ADR-42 Move 4: G5/G9 only meaningful after SPECIFIED (authored goals exist).
  local gate="${1:-}" sid="${2:-}" g5s g5d g9s g9d out
  if [ "${_GCHAIN_M3PLAN_LOGGED:-}" = "$sid:$gate" ]; then
    return 0
  fi
  _GCHAIN_M3PLAN_LOGGED="$sid:$gate"
  if [ "$gate" = "UNSPECIFIED" ]; then
    # O-GROUNDLOG / O-LOGNOADR: no ADR-* tokens in demo-facing GROUND lines.
    log "GROUND  ${sid} — UNSPECIFIED (expected; running M3) — G5/G9 deferred until SPECIFIED"
    return 0
  fi
  g5s="NOT-LANDED"; g5d="${sid}: ground_chain unavailable"
  g9s="NOT-LANDED"; g9d="${sid}: ground_chain unavailable"
  if [ -f "${HARNESS:-.hermes/harness}/ground_chain.py" ]; then
    out=$(python3 "${HARNESS:-.hermes/harness}/ground_chain.py" g5 --root . --sid "$sid" 2>/dev/null || true)
    g5s=$(printf '%s\n' "$out" | awk -F'\t' 'NR==1{print $1}')
    g5d=$(printf '%s\n' "$out" | awk -F'\t' 'NR==1{print $2}')
    out=$(python3 "${HARNESS:-.hermes/harness}/ground_chain.py" g9 --root . --sid "$sid" 2>/dev/null || true)
    g9s=$(printf '%s\n' "$out" | awk -F'\t' 'NR==1{print $1}')
    g9d=$(printf '%s\n' "$out" | awk -F'\t' 'NR==1{print $2}')
    [ -n "$g5s" ] || g5s="NOT-LANDED"
    [ -n "$g9s" ] || g9s="NOT-LANDED"
  fi
  log_ground "G5" "$g5s" \
    "Do harness-derived Shape/Acceptance/owns hold, and do goal/plan type tokens resolve in story scope?" \
    "${g5d}"
  log_ground "G9" "$g9s" \
    "Can this task's Acceptance be satisfied without doing what its Goal requires?" \
    "${g9d}"
  if [ "$gate" = "GREEN" ]; then
    log "GROUND  ${sid} plan-lint GREEN — form complete; G5=${g5s} G9=${g9s}"
  else
    log "GROUND  ${sid} plan-lint RED — see /tmp/plan-lint.txt; G5=${g5s} G9=${g9s}"
  fi
}
# M4 handoff → G10 (code derived from typed M3 acceptance)
log_gchain_m4_g10() { # $1=story id
  local sid="${1:-}" status detail out
  if [ "${_GCHAIN_G10_LOGGED:-}" = "$sid" ]; then
    return 0
  fi
  _GCHAIN_G10_LOGGED="$sid"
  status="NOT-LANDED"; detail="${sid}: ground_chain unavailable"
  if [ -f "${HARNESS:-.hermes/harness}/ground_chain.py" ]; then
    out=$(python3 "${HARNESS:-.hermes/harness}/ground_chain.py" g10 --root . --sid "$sid" 2>/dev/null || true)
    status=$(printf '%s\n' "$out" | awk -F'\t' 'NR==1{print $1}')
    detail=$(printf '%s\n' "$out" | awk -F'\t' 'NR==1{print $2}')
    [ -n "$status" ] || status="NOT-LANDED"
    [ -n "$detail" ] || detail="${sid}: empty g10 verdict"
  fi
  log_ground "G10" "$status" \
    "Is the code this story produced actually derived from the task specs M3 authored?" \
    "${detail}"
}
# Wrap M3 plan-lint gates so GROUND lines always accompany GATE lines.
m3_phase_gate() { # same args as phase_gate
  phase_gate "$@"
  case "${2:-}" in
    GREEN|RED) log_gchain_m3_plan "$2" "${SID:-}" ;;
  esac
}

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
    total=$(grep -cE '^#### T-[0-9]+[A-Za-z]*' "$SPEC_TASKS" 2>/dev/null || echo 0)
  fi
  if [ -n "$base" ]; then
    shipped=$(git log --oneline "${base}..HEAD" 2>/dev/null \
      | grep -cE '^[0-9a-f]+ T-[0-9]+[A-Za-z]*:' || true)
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
    debt_note=$(grep -oE 'T-[0-9]+[A-Za-z]*' migration/debt.md 2>/dev/null | head -1 || true)
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
  # O-M3LINTLOG (W4R7 W-2): per-seat lint deltas from /tmp/m3-lint-seats-${SID}.tsv
  local lint_seats="" lint_summary=""
  if [ -f "/tmp/m3-lint-seats-${SID}.tsv" ]; then
    lint_seats=$(wc -l <"/tmp/m3-lint-seats-${SID}.tsv" | tr -d ' ')
    lint_summary=$(awk -F'\t' '{
      if (NF>=4) printf "%s:%s→%s ", $1, $2, $3
    }' "/tmp/m3-lint-seats-${SID}.tsv" | sed 's/ $//')
  fi
  log "${SID} COST    ${seats} seats (${seats_w} worker · ${seats_e} escalation) · ${sensor_red} sensor RED · ${sfix_n} sfix · ${m3_rev} M3 revisions${lint_seats:+ · lint-seats ${lint_seats}${lint_summary:+ (${lint_summary})}}"
  log "${SID} HEAD    ${head_s}"
}

emit_m3_deliverables() {
  # O-M3DELIVERLOG: demo-visible M3 author artifacts after plan-lint GREEN.
  # Emission-only — no control-flow. Lists specs/<slug>/{tasks,plan,spec}.md,
  # brief path, HEAD, and a short task-id roster (truncate when long).
  local sid="${SID:-}" slug="${SLUG:-}" head_s="" tasks_f="" brief_f=""
  local plan_st="absent" spec_st="absent" n_tasks=0 task_ids="" more=0
  local deliver_extra=""
  [ -n "$sid" ] && [ -n "$slug" ] || return 0
  head_s=$(git rev-parse --short HEAD 2>/dev/null || echo unknown)
  tasks_f="specs/${slug}/tasks.md"
  brief_f="${BRIEF:-}"
  [ -n "$brief_f" ] || brief_f=$(ls migration/briefs/${sid}-*.md 2>/dev/null | head -1 || true)
  [ -f "specs/${slug}/plan.md" ] && plan_st="present"
  [ -f "specs/${slug}/spec.md" ] && spec_st="present"
  if [ -f "$tasks_f" ]; then
    eval "$(python3 - "$tasks_f" <<'PY'
import re, sys
from pathlib import Path
text = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace")
heads = re.findall(r"(?m)^####\s+(\S+):\s*(.+)$", text)
ids = []
for hid, title in heads:
    ids.append(hid)
print(f"n_tasks={len(ids)}")
# Cap roster length for outer-loop readability (S02 can be 40+).
cap = 12
shown = ids[:cap]
more = max(0, len(ids) - cap)
print(f"task_ids={repr(' · '.join(shown))}")
print(f"more={more}")
PY
)"
  else
    n_tasks=0
    task_ids=""
    more=0
  fi
  # Optional extras in the story specs dir (beyond the three named files).
  if [ -d "specs/${slug}" ]; then
    deliver_extra=$(find "specs/${slug}" -maxdepth 1 -type f ! -name 'tasks.md' \
      ! -name 'plan.md' ! -name 'spec.md' -exec basename {} \; 2>/dev/null \
      | sort | tr '\n' ' ' | sed 's/[[:space:]]*$//')
  fi
  _log_rule "══ ${sid} M3 deliverables "
  if [ -f "$tasks_f" ]; then
    log "${sid} DELIVER  ${tasks_f} (${n_tasks} tasks) · plan.md ${plan_st} · spec.md ${spec_st} · brief=${brief_f:-missing} · HEAD ${head_s}"
  else
    log "${sid} DELIVER  tasks.md missing · plan.md ${plan_st} · spec.md ${spec_st} · brief=${brief_f:-missing} · HEAD ${head_s}"
  fi
  if [ -n "${task_ids:-}" ]; then
    if [ "${more:-0}" -gt 0 ]; then
      log "${sid} TASKS    ${task_ids} · +${more} more"
    else
      log "${sid} TASKS    ${task_ids}"
    fi
  else
    log "${sid} TASKS    (none parsed)"
  fi
  if [ -n "$deliver_extra" ]; then
    log "${sid} EXTRA    specs/${slug}/: ${deliver_extra}"
  fi
  return 0
}

# Bounded session runner for the M1/M2/M3 authoring gates. Simpler than
# the supervisor's classifier on purpose: these are single-artifact
# sessions with deterministic lints behind them — one attempt plus one
# retry, then the loop stops and reports (a defective plan must never
# reach execution ungated).
# Logs Actor + sparse heartbeats; session rc ≠ gate success (V6 notes).
_outer_heartbeat_start() { # $1=title $2=t0 $3=slog $4=kind → sets hb_pid
  local title="$1" t0="$2" slog="$3" kind="${4:-orchestrator}" parent=$$
  cat > /tmp/outer-loop-heartbeat.sh <<'HBEOF'
#!/usr/bin/env bash
# outer-loop-heartbeat — not the outer loop itself
# O-HBORPHAN: exit when parent outer-loop dies (ppid=1 survivors polluted the log).
# O-PROFDECIDEHB: optional /tmp/outer-heartbeat-progress.txt (one line) is appended
# so long harness loops (ADR-32 Qwen classify) show typed=N/M like MiniMax seats.
SECS="${1:-60}"; TITLE="${2:-session}"; T0="${3:-0}"; SLOG="${4:-/tmp/outer.log}"
LOG="${5:-/tmp/outer-loop.log}"; KIND="${6:-orchestrator}"; PARENT="${7:-}"
PROG="${8:-/tmp/outer-heartbeat-progress.txt}"
while true; do
  if [ -n "$PARENT" ] && ! kill -0 "$PARENT" 2>/dev/null; then
    exit 0
  fi
  sleep "$SECS"
  if [ -n "$PARENT" ] && ! kill -0 "$PARENT" 2>/dev/null; then
    exit 0
  fi
  now=$(date +%s); elapsed=$((now - T0))
  extra=""
  if [ -f "$PROG" ]; then
    extra=" — $(tr -d '\n' <"$PROG" | head -c 200)"
  fi
  if [ "$KIND" = "orchestrator" ] && grep -qE "429|Too Many Requests|Rate limit|rate.?limit" "$SLOG" 2>/dev/null; then
    echo "[$(date -u +%F' '%T)] …        ${TITLE} waiting on MiniMax rate limit (${elapsed}s)${extra} — details ${SLOG}" >> "$LOG"
  else
    echo "[$(date -u +%F' '%T)] …        ${TITLE} still working on ${KIND} (${elapsed}s)${extra} — details ${SLOG}" >> "$LOG"
  fi
done
HBEOF
  chmod +x /tmp/outer-loop-heartbeat.sh
  /tmp/outer-loop-heartbeat.sh "$HEARTBEAT_SECS" "$title" "$t0" "$slog" "$LOG" "$kind" "$parent" \
    /tmp/outer-heartbeat-progress.txt &
  hb_pid=$!
}

# O-HERMSCOOPPATH / O-M2-FREEZE-JUNK: MiniMax often git-adds golden .hermes/
# into M2/M3 tips (543–547 paths). Untrack; keep WT. Stage-agnostic.
scrub_hermes_scoop() {
  local label="${1:-hygiene}"
  if git ls-files .hermes 2>/dev/null | grep -q .; then
    local n
    n=$(git ls-files .hermes 2>/dev/null | wc -l | tr -d ' ')
    log "         O-HERMSCOOPPATH: untracking ${n} .hermes paths from git index (${label}; keep WT)"
    git rm -r --cached -q .hermes 2>/dev/null || true
    if ! git diff --cached --quiet 2>/dev/null; then
      git commit -q -m "${label}: drop harness scoop (O-HERMSCOOPPATH/O-M2-FREEZE-JUNK)" 2>/dev/null \
        || log "         O-HERMSCOOPPATH: commit failed — review index before next gate"
    fi
  fi
}

# O-M3COMMITHYGIENE / Criterion 10: after an M3 seat, refuse agent tips that
# scoop .hermes/ or *.pyc (commit-hygiene O-HERMSCOOP). Reset to pre-seat SHA
# while keeping specs/${slug}/tasks.md in the working tree for plan-lint.
_m3_refuse_bad_tip() {
  local pre_sha="$1" slug="$2"
  local head cur hyg tasks_save
  head=$(git rev-parse HEAD 2>/dev/null) || return 0
  [ -n "$pre_sha" ] || return 0
  [ "$head" = "$pre_sha" ] && return 0
  hyg=$(mktemp)
  if python3 "$HARNESS/commit-hygiene.py" HEAD >"$hyg" 2>&1; then
    rm -f "$hyg"
    return 0
  fi
  log "         O-M3COMMITHYGIENE: refuse tip $(git rev-parse --short HEAD) — $(tr '\n' ' ' <"$hyg")"
  tasks_save=$(mktemp)
  if [ -f "specs/${slug}/tasks.md" ]; then
    cp "specs/${slug}/tasks.md" "$tasks_save"
  else
    rm -f "$tasks_save"
    tasks_save=""
  fi
  git reset --hard "$pre_sha" >/dev/null 2>&1 || true
  # drop any re-tracked harness from the refused tip's index residue
  scrub_hermes_scoop "M3-hygiene-refuse"
  if [ -n "$tasks_save" ] && [ -f "$tasks_save" ]; then
    mkdir -p "specs/${slug}"
    cp "$tasks_save" "specs/${slug}/tasks.md"
    rm -f "$tasks_save"
  fi
  rm -f "$hyg"
  return 1
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
  rm -f /tmp/outer-last-mchat-ratelimit
  if grep -qE "429|Too Many Requests|Rate limit|rate.?limit" "$slog" 2>/dev/null; then
    # O-ORCH429BACKOFF / O-M2-429 / O-PROF1OF79STOP: do not claim a backoff
    # here — callers must NOT-spend + sleep / stop themselves (session≠gate).
    echo 1 > /tmp/outer-last-mchat-ratelimit
    log "         ${title}: MiniMax rate limit seen in session log (hermes_rc=${rc}) — caller must NOT-spend + backoff"
  fi
  log "·        ${title} session finished ($((now - t0))s, hermes_rc=${rc}) — checking gate next (session≠gate)"
  # O-HERMSCOOPPATH: scrub after every MiniMax seat (M2/M3/M1-profile), not
  # only the M2 call site — ff2664b proved M3 scoops too.
  scrub_hermes_scoop "M-hygiene"
  return $rc
}

# O-PROFCOVSTALE / O-PROF1OF79STOP — coverage for gates comes from evaluate_roles
# SoT (model.units[].decision), never from a stale /tmp/profile-rubric.txt parse.
# Rubric text remains a human-facing side effect only.
# Prints: named total authored evidence_miss  (space-separated); empty on fail.
_profile_cov_fields() {
  local _legacy="${PROFILE_LEGACY_ROOT:-/projects/legacy}"
  python3 - "$_legacy" <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, str(Path(".hermes/harness").resolve()))
try:
    from profile_roles import evaluate_roles
except Exception:
    sys.exit(0)
root = Path(".").resolve()
if not (root / "migration" / "model.json").is_file():
    sys.exit(0)
ev = evaluate_roles(root, legacy=sys.argv[1] if len(sys.argv) > 1 else "/projects/legacy")
print(
    f"{int(ev.get('named') or 0)} {int(ev.get('total') or 0)} "
    f"{int(ev.get('authored') or 0)} {int(ev.get('evidence_miss') or 0)}"
)
PY
}

# O-M3QWENSTALL: OpenCode JSON log has write/edit tools (not bash/read-only).
_m3_log_has_write() {
  local slog="$1"
  [ -f "$slog" ] || return 1
  grep -qE '"tool"\s*:\s*"(edit|write|Write|Edit)"' "$slog" 2>/dev/null \
    || grep -qE '"name"\s*:\s*"(edit|write|Write|Edit)"' "$slog" 2>/dev/null
}

# O-M3TOOLHIST: one-line tool histogram at seat exit (no JSONL dig required).
_m3_tool_hist_line() {
  local slog="$1"
  [ -f "$slog" ] || { echo "tools:none writes=0"; return; }
  python3 - "$slog" <<'PY' 2>/dev/null || echo "tools:parse-fail writes=?"
import json, collections, sys
from pathlib import Path
t = collections.Counter()
for line in Path(sys.argv[1]).read_text(errors="replace").splitlines():
    try:
        o = json.loads(line)
    except Exception:
        continue
    if o.get("type") != "tool_use":
        continue
    name = (o.get("part") or {}).get("tool") or (o.get("part") or {}).get("name") or "?"
    t[str(name)] += 1
writes = sum(t[k] for k in t if k.lower() in ("write", "edit"))
parts = ",".join(f"{k}={t[k]}" for k in sorted(t)) or "none"
print(f"tools:{parts} writes={writes}")
PY
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
    # O-M3ALLSTALL / W4-186: M3-ALL compose writes a full tasks.md *before* the
    # worker seat (<!-- O-M3ALL-SKELETON -->). Existence without the QwenSTALL
    # preseed marker must NOT count as worker progress — capture pre-seat
    # cksum so both stall (120s) and empty (360s) watchers require a mutate
    # or a write/edit tool in the session log.
    _m3_tasks_baseline=""
    if [ -f "$M3_EXPECT_TASKS" ]; then
      _m3_tasks_baseline=$(cksum < "$M3_EXPECT_TASKS" | awk '{print $1" "$2}')
    fi
    (
      # O-M3QWENSTALL: read-thrash with zero writes — abort at 120s default.
      # Preseed / M3-ALL skeleton / unchanged pre-seat cksum all count as
      # stalled until worker writes/edits (or mutates tasks.md).
      stall_s="${M3_STALL_ABORT_SECS:-120}"
      step=15
      elapsed=0
      _m3_tasks_real() {
        [ -f "$M3_EXPECT_TASKS" ] || return 1
        if grep -qE 'O-M3QWENSTALL preseed|O-M3ALL-SKELETON' "$M3_EXPECT_TASKS" 2>/dev/null; then
          return 1
        fi
        if [ -n "${_m3_tasks_baseline}" ]; then
          local cur
          cur=$(cksum < "$M3_EXPECT_TASKS" | awk '{print $1" "$2}')
          [ "$cur" != "${_m3_tasks_baseline}" ]
        else
          return 0
        fi
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
      # O-M3EMPTY: final backstop when tasks.md never lands, stays preseed /
      # M3-ALL skeleton, or is unchanged from the pre-seat baseline with
      # zero write/edit tools (O-M3ALLSTALL).
      abort_s="${M3_EMPTY_ABORT_SECS:-360}"
      sleep "$abort_s"
      _empty_stale=0
      if [ ! -f "$M3_EXPECT_TASKS" ] \
        || grep -qE 'O-M3QWENSTALL preseed|O-M3ALL-SKELETON' "$M3_EXPECT_TASKS" 2>/dev/null; then
        _empty_stale=1
      elif [ -n "${_m3_tasks_baseline}" ]; then
        _cur=$(cksum < "$M3_EXPECT_TASKS" | awk '{print $1" "$2}')
        [ "$_cur" = "${_m3_tasks_baseline}" ] && _empty_stale=1
      fi
      if [ "$_empty_stale" -eq 1 ] && ! _m3_log_has_write "$slog"; then
        echo "[$(date -u +%F' '%T)]          O-M3EMPTY: abort — ${M3_EXPECT_TASKS} missing/preseed/unchanged after ${abort_s}s" >> "$LOG"
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
  # O-M3TOOLHIST: surface read/bash/write counts without digging JSONL.
  log "         O-M3TOOLHIST: $(_m3_tool_hist_line "$slog")"
  log "·        ${title} session finished ($((now - t0))s, worker_rc=${rc}) — checking gate next (session≠gate)"
  return $rc
}

# O-TMPARCHIVE: PVC-side copy of forensic /tmp (success AND fail — W4-029b).
# EXIT trap so debt-freeze / X FAIL / signal paths archive before /tmp recycle.
_TMPARCHIVE_DONE=0
archive_tmp_forensics() {
  [ "${_TMPARCHIVE_DONE:-0}" = "1" ] && return 0
  _TMPARCHIVE_DONE=1
  local _arch_root _arch _jn
  _arch_root="${RUN_ARCHIVE_ROOT:-/projects/modernized/migration/run-archives}"
  _arch="${_arch_root}/$(date -u +%Y%m%dT%H%M%SZ)-$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
  mkdir -p "$_arch" 2>/dev/null || true
  if [ -d "$_arch" ]; then
    # ADR-43: run journal is copied wholesale (no M3-missing glob list).
    _jn=0
    if [ -f "${HARNESS:-.hermes/harness}/run_journal.py" ]; then
      _jn=$(python3 "${HARNESS:-.hermes/harness}/run_journal.py" archive-to "$_arch" 2>/dev/null \
        | sed -n 's/^archived_journal_files=//p' | tail -1)
      _jn=${_jn:-0}
    fi
    shopt -s nullglob
    # W4-526 PART C — M1 PROFILE forensics (profile-rubric + prose/decide logs).
    # O-M2SEATARCH / W4-543 P2 — M2 SEQUENCE seat + projection forensics.
    # Phase-2 backlog: supervisor/sensors still write fixed /tmp paths until
    # migrated into run_journal. Keep those globs; journal covers m3 seats.
    for p in \
      /tmp/supervisor.log /tmp/outer-loop.log /tmp/kill-ledger.log \
      /tmp/findings-delta.txt /tmp/outer-git-push.log \
      /tmp/escalation-cause-*.txt /tmp/oc-*.json /tmp/oc-*.err \
      /tmp/sensor-*.log /tmp/sonar-violations.txt \
      /tmp/profile-rubric.txt \
      /tmp/outer-m1-profile-*.log \
      /tmp/profile-prose-s*.log \
      /tmp/profile-classify-*.log \
      /tmp/outer-m2-sequence-*.log \
      /tmp/m2-projected-facts.txt \
      /tmp/m2-compose.txt \
      /tmp/roadmap-lint.txt \
      /tmp/roadmap-lint-m2exit.txt \
      /tmp/plan-lint.txt \
      /tmp/plan-lint-*-entry.txt
    do
      cp -a "$p" "$_arch/" 2>/dev/null || true
    done
    shopt -u nullglob
    printf 'head=%s\narchived_at=%s\nrun_id=%s\njournal_files=%s\n' \
      "$(git rev-parse HEAD 2>/dev/null || true)" \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
      "${HARNESS_RUN_ID:-}" \
      "${_jn}" > "$_arch/ARCHIVE.txt" 2>/dev/null || true
    if declare -F log >/dev/null 2>&1; then
      log "O-TMPARCHIVE — forensic /tmp + journal(${_jn}) → ${_arch}"
    else
      echo "[$(date -u +%F' '%T)] O-TMPARCHIVE — forensic /tmp + journal(${_jn}) → ${_arch}" >> /tmp/outer-loop.log 2>/dev/null || true
    fi
  elif declare -F log >/dev/null 2>&1; then
    log "WARN: O-TMPARCHIVE — could not create ${_arch}"
  fi
}
# O-HBORPHAN: kill stray heartbeats on EXIT (SIGTERM path used to leave ppid=1 ghosts).
_kill_outer_heartbeats() {
  pkill -TERM -f '/tmp/outer-loop-heartbeat\.sh' 2>/dev/null || true
}
trap '_kill_outer_heartbeats; archive_tmp_forensics' EXIT

fail_run() {
  phase_fail "$1"
  echo "outer-failed: $1" > /tmp/outer-loop-done
  # O-STOPMARKER: durable terminal record (not only /tmp/outer-loop-done).
  if [ -x "$HARNESS/write-stopped.sh" ] || [ -f "$HARNESS/write-stopped.sh" ]; then
    bash "$HARNESS/write-stopped.sh" \
      --kind "outer-failed" \
      --authorizing "outer-loop fail_run" \
      --reason "$1" \
      --expected-next "fix root cause; durableize; clear migration/.stopped; restart outer" \
      >>"$LOG" 2>&1 || true
  fi
  exit 1
}

# O-UXLOG-TRUNC (Poll 77 U1): never wipe the demo narrative on relaunch.
# Append; rotate only when the file is huge (~5 MiB).
# O-LOGSTART: banner says RESUME only when story-state has progress; otherwise
# START (appending log) — wipe/fresh relaunch must not look like a story resume.
_log_tee_lines() { # stdin → timestamped indented narrative lines
  while IFS= read -r _line || [ -n "${_line:-}" ]; do
    [ -z "${_line}" ] && continue
    log "         ${_line}"
  done
}
if [ -s "$LOG" ]; then
  _log_sz=$(wc -c <"$LOG" 2>/dev/null | tr -d ' ' || echo 0)
  if [ "${_log_sz:-0}" -gt 5000000 ]; then
    mv "$LOG" "${LOG}.prev.$(date -u +%Y%m%dT%H%M%SZ)" 2>/dev/null || true
  fi
  {
    echo ""
    if [ -s "$STATE" ] && grep -qE ',(complete|running|in.progress|debt-freeze),' "$STATE" 2>/dev/null; then
      echo "[$(date -u +%F' '%T)] ——— RESUME outer-loop (append; prior narrative preserved) ———"
    else
      echo "[$(date -u +%F' '%T)] ——— START outer-loop (appending log; prior narrative preserved) ———"
    fi
  } >> "$LOG"
else
  : > "$LOG"
  echo "[$(date -u +%F' '%T)] ——— START outer-loop (fresh log) ———" >> "$LOG"
fi
# ADR-43: run journal namespaced by HARNESS_RUN_ID — no O-M3LOGSTALE wipe.
# Stale mixing is impossible across runs (different journal directories).
if [ -z "${HARNESS_RUN_ID:-}" ]; then
  export HARNESS_RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
fi
if [ -f "$HARNESS/run_journal.py" ]; then
  python3 "$HARNESS/run_journal.py" ensure >>"$LOG" 2>&1 || true
fi
echo "[$(date -u +%F' '%T)] run-journal: HARNESS_RUN_ID=${HARNESS_RUN_ID}" >> "$LOG"
# O-STOPMARKER: refuse start on deliberate/stale stop unless cleared.
# tip may lag HEAD by the commit that *added* .stopped — treat as current when
# tip..HEAD only touches migration/.stopped (not other work).
if [ -f migration/.stopped ]; then
  _stop_tip=$(grep -E '^tip:' migration/.stopped | head -1 | sed 's/^tip:[[:space:]]*//' | tr -d '[:space:]')
  _head=$(git rev-parse HEAD 2>/dev/null || echo "")
  _stop_stale=0
  if [ -n "$_stop_tip" ] && [ -n "$_head" ] && [ "$_stop_tip" != "$_head" ]; then
    _stop_delta=$(git diff --name-only "${_stop_tip}..${_head}" 2>/dev/null | grep -v '^migration/\.stopped$' || true)
    if [ -n "$_stop_delta" ]; then
      _stop_stale=1
    fi
  fi
  if [ "$_stop_stale" = "1" ]; then
    # O-STOPREFUSELOG: refuse must hit the outer log (not only stderr).
    {
      echo "[$(date -u +%F' '%T)] O-STOPMARKER: REFUSE start — stale marker tip=${_stop_tip} != HEAD=${_head} (tip..HEAD has non-marker changes)"
      echo "[$(date -u +%F' '%T)] O-STOPMARKER: investigate before clearing; do not blind CLEAR_STOPPED"
    } | tee -a "$LOG" >&2
    exit 1
  fi
  if [ "${CLEAR_STOPPED:-0}" = "1" ] || [ "${OPERATOR_CONFIRM_START:-0}" = "1" ]; then
    echo "[$(date -u +%F' '%T)] O-STOPMARKER: clearing migration/.stopped (CLEAR_STOPPED/OPERATOR_CONFIRM_START)" >> "$LOG"
    rm -f migration/.stopped
  else
    _exp=$(grep -E '^expected_next:' migration/.stopped | head -1 | sed 's/^expected_next:[[:space:]]*//' || true)
    {
      echo "[$(date -u +%F' '%T)] O-STOPMARKER: REFUSE start — deliberate stop present (expected_next=${_exp:-unknown})"
      echo "[$(date -u +%F' '%T)] O-STOPMARKER: to proceed: OPERATOR_CONFIRM_START=1 (or CLEAR_STOPPED=1) .hermes/harness/outer-loop.sh"
    } | tee -a "$LOG" >&2
    exit 1
  fi
fi

phase_start "Outer loop — autonomous migration" \
  "Models: $(orch_label) · $(worker_label) | progress: $LOG | resume: $STATE"
log_gchain_banner

# O-STAMP-AUTO: derive migration.yaml from legacy tree before M1 ground truth.
LEGACY_ROOT="${LEGACY_ROOT:-/projects/legacy}"
if [ -d "$LEGACY_ROOT" ]; then
  phase_start "M1 contract stamp — auto-derived specimen contract (O-STAMP-AUTO)"
  _stamp_out=$(mktemp)
  if python3 "$HARNESS/contract-stamp.py" stamp --legacy "$LEGACY_ROOT" --yaml migration.yaml --write \
      >"$_stamp_out" 2>&1; then
    _log_tee_lines < "$_stamp_out"
    rm -f "$_stamp_out"
    if git diff --quiet migration.yaml 2>/dev/null; then
      : # status already narrated by contract-stamp stdout via _log_tee_lines
    else
      git add migration.yaml
      # O-M1SENSORGATE: stamp commit must not run sensors.sh task (fresh tree RED).
      log "         O-M1SENSORGATE: SKIP_SENSOR_GATE=1 for M1 contract stamp commit"
      if SKIP_SENSOR_GATE=1 git commit -m "M1 contract: auto-derived specimen stamp" >> "$LOG" 2>&1; then
        log "         contract-stamp: committed migration.yaml"
      else
        log "         contract-stamp: migration.yaml updated (commit skipped — review tree)"
      fi
    fi
  else
    _log_tee_lines < "$_stamp_out"
    rm -f "$_stamp_out"
    fail_run "M1 contract stamp — contract-stamp.py failed (see $LOG)"
  fi
  _stamp_out=$(mktemp)
  if ! python3 "$HARNESS/contract-stamp-gate.py" --legacy "$LEGACY_ROOT" --yaml migration.yaml \
      >"$_stamp_out" 2>&1; then
    _log_tee_lines < "$_stamp_out"
    rm -f "$_stamp_out"
    fail_run "M1 contract stamp gate — O-STAMP-GATE RED (see $LOG)"
  fi
  _log_tee_lines < "$_stamp_out"
  rm -f "$_stamp_out"
  phase_ok "M1 contract stamp — O-STAMP-GATE GREEN"
else
  log "         WARN: LEGACY_ROOT $LEGACY_ROOT missing — skipping O-STAMP-AUTO"
fi

# ------------------------------------------------------------- M1 ANALYZE
# O-M1SKIPPROV: skip only when artifacts + provenance stamp match current
# legacy HEAD (existence alone is not enough after keep-M1 abort wipes).
m1_analyze_green() {
  python3 "$HARNESS/m1-provenance.py" check-analyze --root . --legacy /projects/legacy \
    > /tmp/m1-analyze-provenance.txt 2>&1
}
m1_profile_green() {
  # O-RUBRICGENSRC: grade source tree only — never /projects/legacy (includes
  # target/generated-sources MapStruct *MapperImpl false classroles).
  local _legacy_src="/projects/legacy/src"
  [ -d "$_legacy_src" ] || _legacy_src="/projects/legacy"
  [ -f migration/architecture-profile.md ] || return 1
  python3 "$HARNESS/profile-rubric.py" migration/architecture-profile.md "$_legacy_src" \
    > /tmp/profile-rubric.txt 2>&1 || return 1
  python3 "$HARNESS/m1-provenance.py" check-profile --root . --legacy /projects/legacy \
    > /tmp/m1-profile-provenance.txt 2>&1
}
phase_start "M1 ANALYZE — establish migration ground truth (MTA + recipes)" \
  "Actor: harness scripts (no LLM)"
if m1_analyze_green; then
  phase_ok "M1 ANALYZE — ground truth present + provenance-matched (O-M1SKIPPROV)"
else
  if [ -f migration/mta-findings.json ]; then
    log "         O-M1SKIPPROV: artifacts present but provenance RED — re-running ANALYZE ($(head -1 /tmp/m1-analyze-provenance.txt 2>/dev/null || echo no-detail))"
  fi
  "$HARNESS/analyze.sh" > /tmp/outer-m1-analyze.log 2>&1 \
    || fail_run "M1 ANALYZE — ground truth unavailable (see /tmp/outer-m1-analyze.log)"
  # O-RULESETLOG: surface coverage in the outer log (also written to file by analyze.sh)
  if [ -f migration/ruleset-coverage.md ]; then
    while IFS= read -r _rsl; do
      [ -n "$_rsl" ] && log "         $_rsl"
    done < <(grep '^O-RULESETLOG' /tmp/outer-m1-analyze.log 2>/dev/null || true)
  fi
  python3 "$HARNESS/m1-provenance.py" write-analyze --root . --legacy /projects/legacy \
    > /tmp/m1-analyze-stamp-write.txt 2>&1 \
    || fail_run "M1 ANALYZE — provenance stamp write failed (see /tmp/m1-analyze-stamp-write.txt)"
  if [ -n "$(git status --porcelain migration/.m1-analyze.stamp.json migration/ 2>/dev/null || true)" ]; then
    git add migration/.m1-analyze.stamp.json \
      migration/mta-findings.json migration/findings-inventory.md \
      migration/dependency-order.md migration/recipe-log.md \
      migration/ruleset-coverage.md migration/staging \
      2>/dev/null || true
    SKIP_SENSOR_GATE=1 git commit -q -m "M1 analyze: provenance stamp (O-M1SKIPPROV)" 2>/dev/null || true
  fi
  # L-D1: enumerate key M1 deliverables
  log "         • migration/mta-findings.json (+ findings-inventory.md, dependency-order.md, recipe-log.md, ruleset-coverage.md)"
  [ -d migration/staging ] && log "         • migration/staging/ ($(find migration/staging -type f 2>/dev/null | wc -l | tr -d ' ') files)"
  log "         • migration/.m1-analyze.stamp.json (O-M1SKIPPROV)"
  phase_ok "M1 ANALYZE — ground truth ready (details /tmp/outer-m1-analyze.log; HEAD $(git rev-parse --short HEAD 2>/dev/null || echo ?))"
fi

if m1_profile_green; then
  phase_ok "M1 PROFILE — architecture-profile.md rubric-green + provenance-matched (O-M1SKIPPROV)"
  log_gchain_m1_profile GREEN
  log_architecture_profile_sections migration/architecture-profile.md
else
  if [ -f migration/architecture-profile.md ]; then
    log "         O-M1SKIPPROV: profile present but rubric/provenance RED — re-running PROFILE"
  fi
  # O-PROFRUBRICWIPE / W4-495 / W4-496 — drop stale rubric text before PROFILE.
  # Otherwise log_gchain_m1_profile greps claimtruth/profvocab from a prior run's
  # /tmp/profile-rubric.txt (live cold wipe left COVERAGE 79/79 with decided=0).
  rm -f /tmp/profile-rubric.txt
  # ADR-27: model-projected §7 skeleton BEFORE any MiniMax seat (checklist, not blank page).
  if [ -f migration/model.json ]; then
    python3 "$HARNESS/model.py" emit-profile-skeleton --root . \
      > /tmp/outer-m1-profile-skeleton.log 2>&1 \
      || log "         WARN: profile skeleton emit failed (see /tmp/outer-m1-profile-skeleton.log)"
    while IFS= read -r _sk; do
      [ -n "$_sk" ] && log "         $_sk"
    done < <(grep '^O-ADR27' /tmp/outer-m1-profile-skeleton.log 2>/dev/null || true)
  fi
  # ADR-27: NEVER git checkout -- migration/ on PROFILE bounce (keep dirty profile).
  # ADR-32 / O-PROFSEATARCH — harness decide loop (default). Legacy MiniMax
  # N=20 mchat batches: PROFILE_DECIDE_ENGINE=batch-mchat (containment only).
  # Hourly MiniMax quota is NOT helped by more seats — prefer Qwen classify.
  PROFILE_DECIDE_ENGINE="${PROFILE_DECIDE_ENGINE:-harness-loop}"
  PROFILE_CLASSIFY_BACKEND="${PROFILE_CLASSIFY_BACKEND:-opencode-qwen}"
  PROFILE_PROSE_BACKEND="${PROFILE_PROSE_BACKEND:-opencode-qwen}"
  PROFILE_DECISION_BATCH="${PROFILE_DECISION_BATCH:-20}"
  PROFILE_A2_MIN_RATIO="${PROFILE_A2_MIN_RATIO:-0.50}"
  PROFILE_MAX_DECISION_BATCHES="${PROFILE_MAX_DECISION_BATCHES:-6}"
  PROFILE_CLASSIFY_TIMEOUT="${PROFILE_CLASSIFY_TIMEOUT:-180}"
  PROFILE_DECIDE_PASSES="${PROFILE_DECIDE_PASSES:-2}"
  rm -f migration/.profile-coverage-best

  _profile_close_and_grade() {
    python3 "$HARNESS/profile_close.py" migration/architecture-profile.md --root . \
      > /tmp/outer-m1-profile-close.log 2>&1 || true
    while IFS= read -r _cl; do
      [ -n "$_cl" ] && log "         $_cl"
    done < <(grep '^CLOSE:' /tmp/outer-m1-profile-close.log 2>/dev/null || true)
    if [ -f migration/architecture-profile.md ] && \
       python3 "$HARNESS/profile-rubric.py" migration/architecture-profile.md /projects/legacy/src \
         > /tmp/profile-rubric.txt 2>&1; then
      return 0
    fi
    return 1
  }
  _profile_commit_green() {
    local msg="$1"
    python3 "$HARNESS/m1-provenance.py" write-profile --root . --legacy /projects/legacy \
      > /tmp/m1-profile-stamp-write.txt 2>&1 || true
    [ -n "$(git status --porcelain migration/)" ] && git add migration/ && \
      git commit -q -m "$msg" 2>/dev/null || true
    phase_gate "M1 PROFILE rubric" GREEN "architecture-profile.md; commit $(git rev-parse --short HEAD)"
    log_gchain_m1_profile GREEN
    log "         • migration/architecture-profile.md (§7 Class Roles & Target Contract — rendered from model decisions)"
    log "         • migration/.m1-profile.stamp.json (O-M1SKIPPROV)"
    log_architecture_profile_sections migration/architecture-profile.md
    phase_ok "M1 PROFILE — architecture-profile.md rubric-green; commit $(git rev-parse --short HEAD)"
  }
  _profile_batch_derived() {
    if [ ! -f migration/model.json ]; then
      echo ""
      return 0
    fi
    python3 "$HARNESS/model.py" context-for-profile --root . \
      --undecided-only --limit "$PROFILE_DECISION_BATCH" \
      --legacy /projects/legacy 2>/dev/null | head -c 32000 || true
  }
  _profile_harness_decide() {
    # O-PROFDECIDEHB — same 60s outer-loop cadence as mchat/wchat. The decide
    # loop is a long synchronous python process (not a wchat seat), so without
    # an explicit heartbeat the log goes silent for tens of minutes while Qwen
    # classifies units — looks stuck to operators/demo viewers.
    local pass_i="$1" t0 hb_pid slog _dl _rc
    t0=$(date +%s)
    slog="/tmp/outer-m1-profile-decide-${pass_i}.log"
    phase_start "M1 PROFILE — class-role decide loop [${pass_i}/${PROFILE_DECIDE_PASSES}] (${PROFILE_CLASSIFY_BACKEND})"
    log "         Actor: harness profile_decide_loop + $(worker_label) classify — session decide-${pass_i} → ${slog}"
    : > /tmp/outer-heartbeat-progress.txt
    printf 'typed=0/? active=starting pass=%s\n' "$pass_i" > /tmp/outer-heartbeat-progress.txt
    _outer_heartbeat_start "M1 PROFILE decide" "$t0" "$slog" worker
    # PYTHONUNBUFFERED: OK/FAIL lines must hit slog in real time (else heartbeat
    # and operators only see retries after the whole pass ends).
    # O-PROFLOOPRC (W4-478): never `cmd || true; _rc=$?` — that captures `true`'s
    # rc and fabricates loop_rc=0. Match mchat: run, then read the real status.
    set +e
    PYTHONUNBUFFERED=1 python3 "$HARNESS/profile_decide_loop.py" run --root . --legacy /projects/legacy \
      --backend "$PROFILE_CLASSIFY_BACKEND" \
      --worker-model "$WORKER_MODEL" \
      --unit-timeout "$PROFILE_CLASSIFY_TIMEOUT" \
      > "$slog" 2>&1
    _rc=$?
    set -e
    kill "$hb_pid" 2>/dev/null || true
    wait "$hb_pid" 2>/dev/null || true
    rm -f /tmp/outer-heartbeat-progress.txt
    log "·        M1 PROFILE decide pass ${pass_i} finished ($(( $(date +%s) - t0 ))s, loop_rc=${_rc}) — checking gate next (session≠gate)"
    # O-PROFSEATNOISE / W5-105: per-unit OK FQNs stay in ${slog}; outer-loop.log
    # only mirrors the done summary + FAIL/RETRY/SKIP/escalate (demo-facing).
    _ok_n=$(grep -cE '^O-PROFSEATARCH: OK ' "$slog" 2>/dev/null || true)
    log "         O-PROFSEATARCH: ${_ok_n:-0} unit OK lines → ${slog} (not reprinted here)"
    while IFS= read -r _dl; do
      [ -n "$_dl" ] && log "         $_dl"
    done < <(
      grep -E '^O-PROFSEATARCH: (done|FAIL|RETRY|SKIP|escalate|backend=)' "$slog" 2>/dev/null \
        | tail -n 40 || true
    )
  }

  # O-PROFPROSENOOP — §§1–6 prose must leave witnessed substance, not ADR-27
  # skeleton + noop. Gate before burning the decide loop.
  # O-PROFPROSEDECOMP: harness writes the file; witness = no skeleton leftovers
  # + at least one O-PROFPROSEDECOMP: OK (or legacy wchat edit tools).
  _profile_prose_witnessed() {
    local slog="${1:-/tmp/outer-m1-profile-prose.log}"
    local profile="${2:-migration/architecture-profile.md}"
    if [ ! -f "$profile" ]; then
      log "         O-PROFPROSENOOP: $profile missing"
      return 1
    fi
    if grep -qE 'LLM fills|^\(LLM fills' "$profile" 2>/dev/null; then
      log "         O-PROFPROSENOOP: skeleton leftovers still in §§1–6 (Purpose & Domain … Domain Boundaries)"
      return 1
    fi
    if grep -q 'O-PROFPROSEDECOMP' "$slog" 2>/dev/null; then
      if ! grep -qE 'O-PROFPROSEDECOMP: OK' "$slog" 2>/dev/null; then
        log "         O-PROFPROSENOOP: harness prose wrote 0 sections (see $slog)"
        return 1
      fi
      return 0
    fi
    # Legacy containment: monolithic wchat must show edit/write tools.
    if ! _m3_log_has_write "$slog"; then
      log "         O-PROFPROSENOOP: prose seat writes=0 (see $slog)"
      return 1
    fi
    return 0
  }

  # O-PROFPROSEDECOMP — per-section §§1–6 loop (same shape as ADR-32 decide).
  _profile_harness_prose() {
    local t0 hb_pid slog _rc _dl
    t0=$(date +%s)
    slog="/tmp/outer-m1-profile-prose.log"
    phase_start "M1 PROFILE — architecture prose §§1–6 ($(worker_label))"
    # O-PROFPROSECTX: never inject the decide-projection / ADR-26|31 anchor
    # packet into the §§1–6 prose path. Harness asks per-section JSON only;
    # model does not edit files (harness writes).
    log "         Actor: harness profile_prose_loop + $(worker_label) — session prose → ${slog}"
    log "         Profile prose: per-section projected facts (not decide anchors); model returns JSON; harness writes"
    # Demo-facing catalog — bare §N alone is opaque to workshop viewers.
    log "         Sections: §1 (Purpose & Domain) · §2 (Components & Relationships) · §3 (Integration Surfaces) · §4 (Behavioral Contract Sources) · §5 (Modernization Surface) · §6 (Domain Boundaries)"
    rm -f /tmp/outer-heartbeat-progress.txt
    printf 'prose_ok=0/6 fail=0 active=starting\n' > /tmp/outer-heartbeat-progress.txt
    _outer_heartbeat_start "M1 PROFILE prose" "$t0" "$slog" worker
    set +e
    PYTHONUNBUFFERED=1 python3 "$HARNESS/profile_prose_loop.py" run --root . --legacy /projects/legacy \
      --backend "$PROFILE_PROSE_BACKEND" \
      --worker-model "$WORKER_MODEL" \
      --section-timeout "${PROFILE_PROSE_TIMEOUT:-180}" \
      > "$slog" 2>&1
    _rc=$?
    set -e
    kill "$hb_pid" 2>/dev/null || true
    wait "$hb_pid" 2>/dev/null || true
    rm -f /tmp/outer-heartbeat-progress.txt
    log "·        M1 PROFILE prose finished ($(( $(date +%s) - t0 ))s, loop_rc=${_rc}) — checking O-PROFPROSENOOP next"
    while IFS= read -r _dl; do
      [ -n "$_dl" ] && log "         $_dl"
    done < <(grep '^O-PROFPROSEDECOMP' "$slog" 2>/dev/null | tail -n 40 || true)
    return "${_rc}"
  }

  if [ "$PROFILE_DECIDE_ENGINE" = "harness-loop" ]; then
    # --- ADR-32 happy path: harness prose §§1–6, then harness+Qwen classify ---
    set +e
    _profile_harness_prose
    _prose_rc=$?
    set -e
    if [ "${_prose_rc:-1}" -ne 0 ] || ! _profile_prose_witnessed /tmp/outer-m1-profile-prose.log; then
      phase_gate "M1 PROFILE prose" RED "O-PROFPROSENOOP worker_rc=${_prose_rc:-?} — skeleton or writes=0"
      fail_run "M1 PROFILE prose noop (O-PROFPROSENOOP) — refuse decide loop on thin skeleton; do not MiniMax a2"
    fi
    # Decide loop (may take multiple passes over remaining undecided)
    _prof_pass=0
    while [ "$_prof_pass" -lt "$PROFILE_DECIDE_PASSES" ]; do
      _prof_pass=$((_prof_pass + 1))
      _profile_harness_decide "$_prof_pass"
      if _profile_close_and_grade; then
        _profile_commit_green "M1 profile: harness decide-loop rubric-green (Qwen classify)"
        break
      fi
      phase_gate "M1 PROFILE rubric" RED "decide pass ${_prof_pass} — see /tmp/profile-rubric.txt"
      log_gchain_m1_profile RED
    done
    if ! m1_profile_green; then
      phase_start "M1 PROFILE — mechanical close after harness-loop"
      if _profile_close_and_grade; then
        _profile_commit_green "M1 profile: mechanical close after harness-loop"
      else
        phase_gate "M1 PROFILE rubric" RED "see /tmp/profile-rubric.txt"
        log_gchain_m1_profile RED
        fail_run "M1 PROFILE harness decide-loop did not reach rubric GREEN (backend=${PROFILE_CLASSIFY_BACKEND}) — refuse MiniMax a2"
      fi
    fi
  else
    # --- legacy containment: MiniMax N=20 mchat batches (PROFILE_DECIDE_ENGINE=batch-mchat) ---
    log "         WARN: PROFILE_DECIDE_ENGINE=batch-mchat — MiniMax hourly quota containment path"
    phase_start "M1 PROFILE — architecture profile (class roles & target contract) [attempt 1/2]"
    # O-DECISIONWRITEDROP — seats use profile_roles.py upsert (≤3 rows); never
    # wholesale rewrite migration/profile-decisions.json.
    _prof_derived=$(_profile_batch_derived)
    mchat "m1-profile-a1" \
"Use the migration-harness skill and read ANALYSIS.md in its directory. The analysis bundle is committed (migration/mta-findings.json, findings-inventory.md, dependency-order.md, recipe-log.md, migration/model.json). Execute the M1 profile step ONLY (typed decisions; one-unit upsert; no wholesale rewrite): fill sections 1–6 in architecture-profile.md; for EVERY unit listed in DERIVED FACTS below persist a typed decision via harness upsert ONE UNIT AT A TIME — python3 ${HARNESS}/profile_roles.py upsert --root . --legacy /projects/legacy --fqn <FQN> --role HARVEST|REDESIGN --rationale '…' --path <path> --line <N> --token <token> (evidence SELECTED from that unit's projected anchors — do NOT invent path:line:token). Do NOT rewrite migration/profile-decisions.json wholesale (Hermes drops large patches). Optional: upsert --json-file with ≤3 rows. Do NOT author §7 role bullets — the harness renders §7 from model.units[].decision. This seat is a BATCH — do not attempt all profile-units; only the listed undecided batch. No deferral/scaffold roles. Read legacy under /projects/legacy. Source *Mapper.java = classify; *MapperImpl/generated-sources = never class-role (O-RUBRICGENASSERT). Verify: python3 ${HARNESS}/profile_close.py migration/architecture-profile.md --root . && python3 ${HARNESS}/profile-rubric.py migration/architecture-profile.md /projects/legacy/src (exit 0). Commit message STARTS with 'M1 profile:'. DO NOT PUSH. O-CTX: keep packet tight.
${_prof_derived}" \
      "M1 PROFILE"
    if [ -f /tmp/outer-last-mchat-ratelimit ]; then
      phase_gate "M1 PROFILE rubric" RED "a1 rate-limited — see /tmp/outer-m1-profile-a1.log"
      log_gchain_m1_profile RED
      fail_run "M1 PROFILE a1 MiniMax rate-limited (O-PROF1OF79STOP) — NOT-spend; refusing a2; backoff before restart"
    fi
    if _profile_close_and_grade; then
      _profile_commit_green "M1 profile: outer-loop mechanical commit of rubric-green profile"
    else
      phase_gate "M1 PROFILE rubric" RED "see /tmp/profile-rubric.txt"
      log_gchain_m1_profile RED
      _prof_batch_i=0
      while [ "$_prof_batch_i" -lt "$PROFILE_MAX_DECISION_BATCHES" ]; do
        _prof_batch_i=$((_prof_batch_i + 1))
        _prof_derived=$(_profile_batch_derived)
        if echo "$_prof_derived" | grep -qE 'profile-units \(0 java' \
          || ! echo "$_prof_derived" | grep -q 'decision=null'; then
          log "         O-PROF1OF79STOP: no undecided batch projected — stopping decision seats"
          break
        fi
        phase_start "M1 PROFILE — typed-decision batch ${_prof_batch_i}/${PROFILE_MAX_DECISION_BATCHES}"
        mchat "m1-profile-batch-${_prof_batch_i}" \
"Use the migration-harness skill. Typed decision BATCH ONLY: for EVERY unit in DERIVED FACTS below, persist via python3 ${HARNESS}/profile_roles.py upsert --root . --legacy /projects/legacy --fqn … --role … --rationale … --path … --line … --token … (ONE unit per call, or --json-file ≤3 rows). Evidence SELECTED from projected anchors — do NOT invent path:line:token. Do NOT rewrite migration/profile-decisions.json wholesale. Do NOT rewrite sections 1–6 unless broken. Do NOT author §7 role bullets — harness renders §7. Fix evidence_miss / non-member anchors as well as null roles. Verify: python3 ${HARNESS}/profile_close.py migration/architecture-profile.md --root . && python3 ${HARNESS}/profile-rubric.py migration/architecture-profile.md /projects/legacy/src (exit 0). Commit message STARTS with 'M1 profile:'. DO NOT PUSH.
${_prof_derived}" \
          "M1 PROFILE"
        if [ -f /tmp/outer-last-mchat-ratelimit ]; then
          phase_gate "M1 PROFILE rubric" RED "batch ${_prof_batch_i} rate-limited"
          log_gchain_m1_profile RED
          fail_run "M1 PROFILE decision-batch MiniMax rate-limited (O-PROF1OF79STOP) — NOT-spend; refusing a2"
        fi
        if _profile_close_and_grade; then
          _profile_commit_green "M1 profile: decision batch ${_prof_batch_i} rubric-green"
          break
        fi
        phase_gate "M1 PROFILE rubric" RED "batch ${_prof_batch_i} — see /tmp/profile-rubric.txt"
        log_gchain_m1_profile RED
      done
    fi
    if ! m1_profile_green; then
      phase_start "M1 PROFILE — architecture profile (class roles & target contract) [attempt 2/2]"
      phase_retry "M1 PROFILE — bouncing once (keep dirty profile; no git checkout wipe)"
      if _profile_close_and_grade; then
        _profile_commit_green "M1 profile: mechanical close (no LLM a2)"
      else
        _pc_fields=$(_profile_cov_fields /tmp/profile-rubric.txt || true)
        _pc_named=$(echo "$_pc_fields" | awk '{print $1}')
        _pc_total=$(echo "$_pc_fields" | awk '{print $2}')
        _pc_authored=$(echo "$_pc_fields" | awk '{print $3}')
        _pc_emiss=$(echo "$_pc_fields" | awk '{print $4}')
        _pc_ratio="0"
        if [ -n "${_pc_total:-}" ] && [ "${_pc_total:-0}" -gt 0 ] 2>/dev/null; then
          _pc_ratio=$(python3 -c "print(float(${_pc_named:-0})/float(${_pc_total}))")
        fi
        log "         O-PROF1OF79STOP: pre-a2 coverage credited=${_pc_named:-?}/${_pc_total:-?} authored=${_pc_authored:-?} evidence_miss=${_pc_emiss:-?} ratio=${_pc_ratio}"
        phase_gate "M1 PROFILE rubric" RED "refuse MiniMax a2 — harness-loop is default; batch-mchat will not burn a2"
        log_gchain_m1_profile RED
        fail_run "M1 PROFILE batch-mchat incomplete (ratio=${_pc_ratio}); use PROFILE_DECIDE_ENGINE=harness-loop — refuse MiniMax a2"
      fi
    fi
  fi
fi

# O-STOPAFTERM1 — validation runs: exit after M1 ANALYZE+PROFILE GREEN (no M2/M3).
# Used to prove ruleset coverage / openjdk21 / provenance before spending M2 seats.
if [ "${STOP_AFTER_M1:-0}" = "1" ] || [ "${STOP_AFTER_M1:-}" = "true" ]; then
  if m1_analyze_green && m1_profile_green; then
    phase_gate "M1 stop-after" GREEN \
      "STOP_AFTER_M1 — analyze+profile provenance-green; refusing M2 SEQUENCE"
    log "         O-STOPAFTERM1: M1 validation complete — not starting M2"
    if [ -x "$HARNESS/write-stopped.sh" ] || [ -f "$HARNESS/write-stopped.sh" ]; then
      bash "$HARNESS/write-stopped.sh" \
        --kind deliberate-stop \
        --authorizing "STOP_AFTER_M1=1" \
        --reason "M1 ANALYZE+PROFILE complete; validation hold before M2" \
        --expected-next "review M1 artifacts (ruleset-coverage, openjdk21); clear STOP_AFTER_M1 + migration/.stopped; resume" \
        || true
      if [ -n "$(git status --porcelain migration/.stopped 2>/dev/null || true)" ]; then
        git add migration/.stopped
        SKIP_SENSOR_GATE=1 git commit -q -m "chore: STOP_AFTER_M1 hold (.stopped)" 2>/dev/null || true
      fi
    fi
    echo "outer-complete: STOP_AFTER_M1 $(date -u +%Y-%m-%dT%H:%MZ)" > /tmp/outer-loop-done
    exit 0
  fi
  fail_run "O-STOPAFTERM1 set but M1 ANALYZE/PROFILE not provenance-green"
fi

# ------------------------------------------------------------ M2 SEQUENCE
# O-M2-429 / O-ORCH429BACKOFF: real backoff when MiniMax 429s mid-seat
# (default 900s). Override M2_429_BACKOFF_SECS for instruments.
# O-M2429CAP: NOT-spent 429 retries are capped (default 3 ≈ 45m) then
# fail_run with a distinct quota cause — never silent livelock.
M2_429_BACKOFF_SECS="${M2_429_BACKOFF_SECS:-900}"
M2_429_MAX="${M2_429_MAX:-3}"
M2_429_COUNT=0
M2_COMPOSE="${M2_COMPOSE:-1}"
roadmap_lint_residual() {
  # O-LOGLINTRES: count findings lines in /tmp/roadmap-lint.txt (0 if missing/OK)
  if [ ! -f /tmp/roadmap-lint.txt ]; then
    echo 0
    return 0
  fi
  if grep -qE '^ROADMAP OK' /tmp/roadmap-lint.txt 2>/dev/null; then
    echo 0
    return 0
  fi
  # Prefer LINT: lines; fall back to non-empty non-OK lines
  local n
  n=$(grep -cE '^LINT:' /tmp/roadmap-lint.txt 2>/dev/null || true)
  n=${n:-0}
  if [ "$n" -eq 0 ]; then
    n=$(grep -cE '.' /tmp/roadmap-lint.txt 2>/dev/null || true)
    n=${n:-0}
  fi
  echo "$n"
}
roadmap_green() {
  # O-PORTDERIVE: pass architecture-profile.md so §7 REDESIGN ↔ brief contract is gated
  [ -f migration/roadmap.md ] && python3 "$HARNESS/roadmap-lint.py" migration/roadmap.md migration/findings-inventory.md /projects/legacy migration/architecture-profile.md > /tmp/roadmap-lint.txt 2>&1
}
m2_compose_bookkeeping() {
  # O-M2COMPOSE: deterministic partition + kind/S-FND/seat-budget + brief stubs + K3
  [ "${M2_COMPOSE}" = "1" ] || return 0
  [ -f "$HARNESS/m2-compose.py" ] || return 0
  local mode="${1:-fill}"
  local before after detail
  before=$(roadmap_lint_residual)
  if python3 "$HARNESS/m2-compose.py" --root . --mode "$mode" \
      > /tmp/m2-compose.txt 2>&1; then
    # Re-run lint so residual reflects post-compose bookkeeping (O-LOGLINTRES)
    roadmap_green || true
    after=$(roadmap_lint_residual)
    detail="$(tail -1 /tmp/m2-compose.txt 2>/dev/null || true)"
    log "         O-M2COMPOSE ${mode}: ${detail} · lint ${before} → ${after}"
    return 0
  fi
  log "         O-M2COMPOSE ${mode} RED — see /tmp/m2-compose.txt · lint residual $(roadmap_lint_residual)"
  return 1
}
m2_brief_quality_exit() {
  # O-BRIEFQUALITY — floor at M2 exit (not only --story / O-M3PREFLIGHT).
  BRIEF_QUALITY_ENFORCE=1 python3 "$HARNESS/roadmap-lint.py" \
      migration/roadmap.md migration/findings-inventory.md /projects/legacy \
      migration/architecture-profile.md \
      > /tmp/roadmap-lint-m2exit.txt 2>&1
}
if roadmap_green; then
  phase_ok "M2 SEQUENCE — roadmap already present and lint-green"
  log_gchain_m2_roadmap GREEN
  if ! m2_brief_quality_exit; then
    cp -f /tmp/roadmap-lint-m2exit.txt /tmp/roadmap-lint.txt 2>/dev/null || true
    phase_gate "M2 SEQUENCE brief-quality" RED \
      "already-green path below floor — /tmp/roadmap-lint-m2exit.txt"
    fail_run "O-BRIEFQUALITY M2 exit floor (already-green path; see /tmp/roadmap-lint-m2exit.txt)"
  fi
else
  # O-M2COMPOSE skeleton-first: unique-owner partition + brief stubs before seat
  if [ "${M2_COMPOSE}" = "1" ] && [ ! -f migration/roadmap.md ]; then
    phase_start "M2 SEQUENCE — skeleton-first compose (O-M2COMPOSE)"
    if m2_compose_bookkeeping skeleton; then
      # O-LOGSTART: residual after skeleton is expected — MiniMax seat closes it.
      phase_gate "M2 SEQUENCE compose" GREEN \
        "skeleton seeded; lint residual $(roadmap_lint_residual) left for MiniMax — $(tail -1 /tmp/m2-compose.txt 2>/dev/null || true)"
    else
      phase_gate "M2 SEQUENCE compose" RED "lint residual $(roadmap_lint_residual) — see /tmp/m2-compose.txt"
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
    # ADR-34 / ADR-38 / O-M2PROJ / F-no-discovery: projected facts + SNIPPET text
    # (not cite= pointers alone). Cap raised for anchored snippets (was 48K).
    python3 "$HARNESS/model.py" context-for-m2 --root . \
      > /tmp/m2-projected-facts.txt 2>/tmp/m2-projected-facts.err || true
    _m2_proj="$(head -c "${M2_PROJ_BYTES:-120000}" /tmp/m2-projected-facts.txt 2>/dev/null || true)"
    [ -n "${_m2_proj}" ] || _m2_proj="(m2 projection empty — run model.py context-for-m2)"
    P="Use the migration-harness skill and read SEQUENCING.md and BRIEF-TEMPLATE.md in its directory. M1 is committed. Execute M2 ONLY: fill JUDGMENT on the harness-seeded roadmap + briefs (titles, rationale, adopt/defer, cite snippets). ADR-34: story membership/scope/deploy are harness SoT from typed model.order+SCC+decision.role — do NOT rewrite unit ownership or rediscover via /projects/legacy tree reads (F-no-discovery). PROJECTED FACTS below are complete (ADR-38: every cite= includes SNIPPET source lines — copy quotes from SNIPPET only). A deterministic m2-compose.py pass already seeded partition, brief stubs, non-mandatory rows, last-story deploy, seat-budget when kind is set (O-M2COMPOSE) — do NOT re-arithmetic seat-budget and do NOT dual-own findings. Each brief carries classes' roles and, for REDESIGN, per-unit target_contract from typed decisions / §7 (Class Roles & Target Contract). Declare story kind: rename|reimplement|mixed when OPEN DESIGN or REDESIGN scope (O-STORYKIND). Quotes must copy SNIPPET lines from PROJECTED FACTS verbatim; never invent methods; never read /projects/legacy. O-M2-FREEZE-JUNK / O-HERMSCOOP: stage ONLY migration/roadmap.md and migration/briefs/ — NEVER git add .hermes/. Verify: python3 ${HARNESS}/roadmap-lint.py migration/roadmap.md migration/findings-inventory.md /projects/legacy migration/architecture-profile.md (exit 0) BEFORE committing. ONE commit starting with 'M2 sequence:'. DO NOT PUSH. ${PKG_RENAME_HINT}

---BEGIN M2 PROJECTED FACTS---
${_m2_proj}
---END M2 PROJECTED FACTS---"
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
    # O-M2-FREEZE-JUNK / O-HERMSCOOPPATH: scrub now lives in mchat() (stage-
    # agnostic). Keep a no-op call here so older call-site greps still find the
    # label; scrub_hermes_scoop is idempotent when index is clean.
    scrub_hermes_scoop "M2 hygiene"
    # O-M2COMPOSE fill after seat — kill coverage/briefs/deploy/seat-budget bookkeeping
    m2_compose_bookkeeping fill || true
    if roadmap_green; then
      M2_429_COUNT=0  # O-M2429CAP: non-429 success resets quota counter
      # O-BRIEFQUALITY — enforce floor at M2 exit (cheaper than M3 preflight).
      if ! m2_brief_quality_exit; then
        cp -f /tmp/roadmap-lint-m2exit.txt /tmp/roadmap-lint.txt 2>/dev/null || true
        phase_gate "M2 SEQUENCE brief-quality" RED \
          "$(grep -cE '^LINT:O-BRIEFQUALITY' /tmp/roadmap-lint-m2exit.txt 2>/dev/null || echo 0) below floor — /tmp/roadmap-lint-m2exit.txt"
        [ "$ATTEMPT" -ge "$M2_MAX_ATTEMPTS" ] \
          && fail_run "O-BRIEFQUALITY M2 exit floor (see /tmp/roadmap-lint-m2exit.txt)"
        ATTEMPT=$((ATTEMPT + 1))
        phase_retry "M2 SEQUENCE — brief quality below floor; bouncing"
        continue
      fi
      [ -n "$(git status --porcelain migration/)" ] && git add migration/ && git commit -q -m "M2 sequence: outer-loop mechanical commit of lint-green roadmap" 2>/dev/null
      # O-LOGLINTRES: narrate residual (0) on GREEN so convergence is visible
      phase_gate "M2 SEQUENCE roadmap-lint" GREEN "0 findings; commit $(git rev-parse --short HEAD)"
      log_gchain_m2_roadmap GREEN
      # O-EVIDLIVE / K3: roadmap adopt/defer exercised — seed per-story ledger rows.
      # Ledger writes stay; do not dump bare `evidlive:S0N:K3:N` into the demo
      # outer-loop log (O-EVIDLIVELOG — align with timestamped `log` lines).
      if [ -f "$HARNESS/evidence-liveness.sh" ] && [ -f migration/roadmap.md ]; then
        # O-EVIDLIVEK3TABLE: also count markdown table `| id | adopt|defer | reason |`
        _k3n=$(grep -cE '(: defer|: adopt|defer \([^\)]+\)|: *defer|: *adopt|[[:space:]]\|[[:space:]]*(adopt|defer)[[:space:]]\|)' migration/roadmap.md 2>/dev/null || true)
        _k3n=${_k3n:-0}
        if [ "${_k3n:-0}" -gt 0 ] 2>/dev/null; then
          _k3_sids=()
          for _sid in $(grep -E '^## S[0-9]+' migration/roadmap.md | sed -E 's/^## (S[0-9]+).*/\1/'); do
            _k3_sids+=("$_sid")
            # stdout is machine-token for instruments/supervisor — not demo narration
            bash "$HARNESS/evidence-liveness.sh" record "$_sid" K3 "$_k3n" "roadmap-lint GREEN adopt/defer" \
              >/dev/null 2>&1 || true
          done
          log "         O-EVIDLIVE: K3 seeded · stories=${#_k3_sids[@]} · adopt/defer-marks=${_k3n}"
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
    # O-M2429CAP: cap consecutive NOT-spent 429s then fail_run with distinct cause
    if grep -qE "429|Too Many Requests|Rate limit|rate.?limit" \
        "/tmp/outer-m2-sequence-a${ATTEMPT}.log" 2>/dev/null; then
      M2_429_COUNT=$((M2_429_COUNT + 1))
      if [ "$M2_429_COUNT" -ge "$M2_429_MAX" ]; then
        log "         O-M2429CAP: ${M2_429_COUNT} consecutive rate-limited seats (max ${M2_429_MAX}) — failing run"
        fail_run "quota exhausted after ${M2_429_COUNT} rate-limited seats (O-M2-429CAP)"
      fi
      log "         O-M2-429: MiniMax rate-limited — attempt ${ATTEMPT} NOT spent; backoff ${M2_429_BACKOFF_SECS}s (${M2_429_COUNT}/${M2_429_MAX})"
      phase_retry "M2 SEQUENCE — quota; sleeping ${M2_429_BACKOFF_SECS}s (O-M2-429 ${M2_429_COUNT}/${M2_429_MAX})"
      sleep "${M2_429_BACKOFF_SECS}"
      continue
    fi
    M2_429_COUNT=0  # O-M2429CAP: non-429 seat resets counter (lint RED burns attempt below)
    # O-LOGLINTRES: residual count on RED — the number that shows M2 convergence
    phase_gate "M2 SEQUENCE roadmap-lint" RED "$(roadmap_lint_residual) findings — /tmp/roadmap-lint.txt"
    log_gchain_m2_roadmap RED
    [ "$ATTEMPT" -ge "$M2_MAX_ATTEMPTS" ] && fail_run "M2 SEQUENCE failed its lint twice"
    ATTEMPT=$((ATTEMPT + 1))
    phase_retry "M2 SEQUENCE — bouncing once"
  done
fi

# O-STOPAFTERM2 — validation runs: exit after M2 GREEN (no M3/M4/M5).
# Used to prove brief-quality / PREFLIGHT / compose before spending M3 seats.
if [ "${STOP_AFTER_M2:-0}" = "1" ] || [ "${STOP_AFTER_M2:-}" = "true" ]; then
  if [ -f migration/roadmap.md ] && roadmap_green; then
    if m2_brief_quality_exit; then
      phase_gate "M2 SEQUENCE stop-after" GREEN \
        "STOP_AFTER_M2 — brief-quality floor cleared; refusing story loop"
      log "         O-STOPAFTERM2: M2 validation complete — not starting M3"
      if [ -x "$HARNESS/write-stopped.sh" ] || [ -f "$HARNESS/write-stopped.sh" ]; then
        bash "$HARNESS/write-stopped.sh" \
          --kind deliberate-stop \
          --authorizing "STOP_AFTER_M2=1" \
          --reason "M2 SEQUENCE complete; validation hold before M3" \
          --expected-next "review M2 roadmap/briefs; clear STOP_AFTER_M2 + migration/.stopped; resume M3" \
          || true
        if [ -n "$(git status --porcelain migration/.stopped 2>/dev/null || true)" ]; then
          git add migration/.stopped
          SKIP_SENSOR_GATE=1 git commit -q -m "chore: STOP_AFTER_M2 hold (.stopped)" 2>/dev/null || true
        fi
      fi
      echo "outer-complete: STOP_AFTER_M2 $(date -u +%Y-%m-%dT%H:%MZ)" > /tmp/outer-loop-done
      exit 0
    fi
    phase_gate "M2 SEQUENCE stop-after" RED \
      "STOP_AFTER_M2 but brief-quality floor RED — /tmp/roadmap-lint-m2exit.txt"
    fail_run "O-STOPAFTERM2: M2 present but O-BRIEFQUALITY floor RED"
  fi
  fail_run "O-STOPAFTERM2 set but M2 roadmap missing or lint-RED"
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
# O-M3PREFLIGHT: SIDs refused this pass (brief-quality RED); fail after loop
# so other stories still get their preflight/seats attempted first.
M3_PREFLIGHT_HELD=""

for M3_ALL_PASS in $M3_ALL_PASSES; do
M3_PREFLIGHT_HELD=""
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
  SLUG_HINT=$(ls migration/briefs/${SID}-*.md 2>/dev/null | head -1 | xargs -n1 basename 2>/dev/null | sed 's/\.md$//' || echo "$SID")
  # O-LOGFULLSTORY: STORY_TAG is full slug when brief exists; else SID
  STORY_TAG="${SLUG_HINT:-$SID}"
  story_done "$SID" && { phase_ok "${SID} (${SLUG_HINT}) — already complete; skipping"; STORY_TAG=""; continue; }

  # O-EXECUTEONLY — validation runs: execute-pass only for one story
  # (e.g. EXECUTE_ONLY_STORY=S02 + M3_ALL=0 + STOP_AFTER_EXECUTE=S02 for
  # first-M4 probe without burning S01 or later-story MiniMax author).
  if [ "$M3_ALL_PASS" = "execute" ] \
    && [ -n "${EXECUTE_ONLY_STORY:-}" ] \
    && [ "${EXECUTE_ONLY_STORY}" != "$SID" ]; then
    log "         O-EXECUTEONLY: skip ${SID} (EXECUTE_ONLY_STORY=${EXECUTE_ONLY_STORY})"
    STORY_TAG=""
    continue
  fi

  # -------------------------------------------------------- M3 SPECIFY
  # O-M3SKIP: never treat "tasks.md exists" as GREEN. Untracked/half-written
  # specs after a failed M3 (or auto-restart) must re-lint; only skip mchat
  # when plan-lint is already green.
  SPEC_TASKS=$(ls specs/${SID}-*/tasks.md 2>/dev/null | head -1)
  BRIEF=$(ls migration/briefs/${SID}-*.md 2>/dev/null | head -1)
  [ -n "$BRIEF" ] || fail_run "$SID has no brief under migration/briefs/"
  SLUG=$(basename "$BRIEF" .md)
  # O-LOGFULLSTORY: prefix + phase titles use full slug (S01-platform-...), not bare S01
  STORY_TAG="$SLUG"
  M3_DONE=0

  # O-M3PREFLIGHT — brief-quality vs *current* roadmap before any M3 seat.
  # M2-time GREEN is not enough: recompose can stale briefs between M2 and
  # M3. Per-story --story so a deficient S03 holds S03 while S01 proceeds.
  # Distinct cause; do not spend MiniMax/Qwen on a bad input.
  _m3pf="/tmp/m3-preflight-${SID}.txt"
  set +e
  python3 "$HARNESS/roadmap-lint.py" migration/roadmap.md \
    migration/findings-inventory.md /projects/legacy \
    migration/architecture-profile.md --story "$SID" \
    > "$_m3pf" 2>&1
  _m3pf_rc=$?
  set -e
  if [ "$_m3pf_rc" != "0" ]; then
    phase_gate "M3 PREFLIGHT ${SLUG} brief-quality" RED \
      "O-M3PREFLIGHT — see ${_m3pf}"
    log "         O-M3PREFLIGHT: ${SID} brief-quality RED vs current roadmap — refusing M3 seats (other stories proceed)"
    M3_PREFLIGHT_HELD="${M3_PREFLIGHT_HELD:-}${M3_PREFLIGHT_HELD:+ }${SID}"
    STORY_TAG=""
    continue
  fi
  phase_gate "M3 PREFLIGHT ${SLUG} brief-quality" GREEN "O-M3PREFLIGHT"

  # O-M3ACCEPT / O-M3DTOSCOPE — lint args (quality gate only; see ADR-42).
  M3_LINT_CMD="python3 ${HARNESS}/plan-lint.py specs/${SLUG}/tasks.md migration/mta-findings.json --findings-scope ${FINDINGS} --profile migration/architecture-profile.md --story-deploy ${DEPLOY} --story-scope '${SCOPE}'"
  # ADR-42: readiness from typed store — never discover work by plan-lint RED.
  # assign/render first so story_state sees current tasks[]; plan-lint runs
  # only when SPECIFIED (all filled).
  if [ "${M3_TYPED_LOOP:-1}" = "1" ] && [ -f "$HARNESS/model.py" ]; then
    python3 "$HARNESS/model.py" assign-tasks --root . >/tmp/m3-assign-tasks.txt 2>&1 || true
    python3 "$HARNESS/model.py" render-tasks --root . --sid "$SID" \
      >/tmp/m3-render-tasks-${SID}.txt 2>&1 || true
    _story_state=$(python3 "$HARNESS/model.py" story-state --root . --sid "$SID" 2>/dev/null || echo UNSPECIFIED)
  else
    _story_state="UNSPECIFIED"
  fi
  if [ "$_story_state" = "SPECIFIED" ] && [ -n "$SPEC_TASKS" ]; then
    # Quality gate — story is specified; RED means incorrect, not "not done".
    if python3 "$HARNESS/plan-lint.py" "$SPEC_TASKS" migration/mta-findings.json \
         --findings-scope "$FINDINGS" --profile migration/architecture-profile.md \
         --story-deploy "$DEPLOY" --story-scope "$SCOPE" \
         > /tmp/plan-lint.txt 2>&1; then
      [ -n "$(git status --porcelain "specs/${SLUG}/")" ] \
        && git add "specs/${SLUG}/" \
        && git commit -q -m "${SID} spec: outer-loop mechanical commit of lint-green spec" 2>/dev/null
      m3_phase_gate "M3 SPECIFY ${SLUG} plan-lint" GREEN "commit $(git rev-parse --short HEAD)"
      phase_ok "M3 SPECIFY — ${SLUG} SPECIFIED + plan-lint GREEN ($SPEC_TASKS); commit $(git rev-parse --short HEAD)"
      M3_DONE=1
    else
      m3_phase_gate "M3 SPECIFY ${SLUG} plan-lint" RED "SPECIFIED story failed quality lint — /tmp/plan-lint.txt"
      log "         story_state=SPECIFIED but plan-lint RED — quality defect (not scheduler)"
      # Fall through to typed re-seat / legacy path when M3_DONE still 0.
    fi
  elif [ "$_story_state" = "UNSPECIFIED" ]; then
    log "·        M3 SPECIFY ${SLUG} — story_state=UNSPECIFIED (expected; running M3)"
    log_gchain_m3_plan UNSPECIFIED "${SID}"
  fi
  if [ "$M3_DONE" != "1" ]; then
    # ADR-35/40 typed path — harness SoT + Qwen write-inversion (default ON).
    # W4-556: M3_TYPED_LOOP=1 failure is terminal (O-M3TYPEDSTOP).
    if [ "${M3_TYPED_LOOP:-1}" = "1" ]; then
      if [ ! -f "$HARNESS/m3_task_loop.py" ]; then
        fail_run "M3 SPECIFY ${SLUG}: M3_TYPED_LOOP=1 but m3_task_loop.py missing (O-M3TYPEDSTOP)"
      fi
      phase_start "M3 SPECIFY — typed write-inversion ${SLUG} (${STORY_IDX}/${STORY_COUNT}) [typed/Qwen]"
      _m3_journal_hint="/tmp/hj/${HARNESS_RUN_ID:-run}/m3/"
      log "         Actor: m3_task_loop + $(worker_label) — journal → ${_m3_journal_hint}"
      # O-M3TYPEDHB: typed loop heartbeat (same class as O-PROFDECIDEHB).
      _m3tl_t0=$(date +%s)
      _m3tl_slog=$(python3 "$HARNESS/run_journal.py" seat-log m3 "loop-${SID}" --attempt 1 2>/dev/null \
        || echo "/tmp/m3-task-loop-${SID}.log")
      : > /tmp/outer-heartbeat-progress.txt
      printf 'm3=%s seats=0/? active=starting\n' "$SID" > /tmp/outer-heartbeat-progress.txt
      _outer_heartbeat_start "M3 SPECIFY ${SLUG}" "$_m3tl_t0" "$_m3tl_slog" worker
      set +e
      PYTHONUNBUFFERED=1 python3 "$HARNESS/m3_task_loop.py" run --root . --sid "$SID" \
        --backend opencode-qwen \
        --worker-model "${WORKER_MODEL}" \
        --legacy /projects/legacy \
        >"$_m3tl_slog" 2>&1
      _m3tl_rc=$?
      set -e
      kill "$hb_pid" 2>/dev/null || true
      wait "$hb_pid" 2>/dev/null || true
      rm -f /tmp/outer-heartbeat-progress.txt
      log "·        M3 SPECIFY ${SLUG} typed-loop finished ($(( $(date +%s) - _m3tl_t0 ))s, loop_rc=${_m3tl_rc}) — checking plan-lint next"
      # ADR-42 Move 3: plan-lint once when seats claim SPECIFIED (or after fill).
      _m3_lint_rc=1
      if [ "$_m3tl_rc" = "0" ]; then
        set +e
        python3 "$HARNESS/plan-lint.py" "specs/${SLUG}/tasks.md" migration/mta-findings.json \
             --findings-scope "$FINDINGS" --profile migration/architecture-profile.md \
             --story-deploy "$DEPLOY" --story-scope "$SCOPE" \
             > /tmp/plan-lint.txt 2>&1
        _m3_lint_rc=$?
        set -e
      fi
      if [ "$_m3tl_rc" = "0" ] && [ "${_m3_lint_rc}" = "0" ]; then
        [ -n "$(git status --porcelain "specs/${SLUG}/" migration/model.json)" ] \
          && git add "specs/${SLUG}/" migration/model.json \
          && git commit -q -m "${SID} spec: typed M3 write-inversion (typed/Qwen)" 2>/dev/null
        m3_phase_gate "M3 SPECIFY ${SLUG} plan-lint" GREEN \
          "typed-loop commit $(git rev-parse --short HEAD)"
        phase_ok "M3 SPECIFY — ${SLUG} typed write-inversion GREEN; commit $(git rev-parse --short HEAD)"
        M3_DONE=1
      elif [ "$_m3tl_rc" != "0" ]; then
        _m3_fail_n=$(grep -c "^  FAIL " "$_m3tl_slog" 2>/dev/null || echo 0)
        m3_phase_gate "M3 SPECIFY ${SLUG} typed-loop" RED \
          "SEAT-FAILED rc=${_m3tl_rc:-?} fail=${_m3_fail_n} — see ${_m3tl_slog} (O-M3TYPEDSTOP)"
        fail_run "M3 SPECIFY ${SLUG} SEAT-FAILED (rc=${_m3tl_rc:-?}, fail=${_m3_fail_n}) (O-M3TYPEDSTOP; no legacy fallback). See ${_m3tl_slog}"
      else
        _m3_lint_n=$(grep -c '^LINT:' /tmp/plan-lint.txt 2>/dev/null || echo 0)
        _m3_lint_first=$(grep '^LINT:' /tmp/plan-lint.txt 2>/dev/null | head -1 | cut -c1-120 || echo "(no LINT lines)")
        m3_phase_gate "M3 SPECIFY ${SLUG} plan-lint" RED \
          "LINT-RED n=${_m3_lint_n} first: ${_m3_lint_first} (O-M3TYPEDSTOP; seats ok rc=0)"
        fail_run "M3 SPECIFY ${SLUG} LINT-RED (n=${_m3_lint_n} lints, first: ${_m3_lint_first}) (O-M3TYPEDSTOP; no legacy fallback). Seats ok — see /tmp/plan-lint.txt"
      fi
    fi
  fi
  if [ "$M3_DONE" != "1" ] && [ "${M3_TYPED_LOOP:-1}" != "1" ]; then
    # Legacy MiniMax/Qwen edit path — only when operator set M3_TYPED_LOOP=0.
    # O-M3WORKER: Qwen drafts (≤M3_WORKER_ATTEMPTS), then MiniMax backstop
    # (≤M3_ORCH_BACKSTOP). plan-lint remains the gate — session≠success.
    # O-M3KILL: SIGKILL must NOT spend an attempt.
    # O-M3DERIVEDCTX (ADR-21 G4): inline derived facts beside the brief at zero
    # tool cost. Keep O-M3FIRSTWRITE read ban; on conflict DERIVED FACTS win.
    m3_derived_facts() {
      # ADR-24: prefer model.py projection (no basename scrape / silent cap).
      if [ -f migration/model.json ] && [ -f "${HARNESS:-.hermes/harness}/model.py" ]; then
        local _ctx=""
        if [ -n "${SID:-}" ]; then
          _ctx="$(python3 "${HARNESS:-.hermes/harness}/model.py" context-for "${SID}" --root . 2>/dev/null || true)"
        fi
        if [ -z "${_ctx}" ] || ! printf '%s' "$_ctx" | grep -q 'convert-together\|units ('; then
          _ctx="$(python3 "${HARNESS:-.hermes/harness}/model.py" context-for --scope "${SCOPE}" --root . 2>/dev/null || true)"
        fi
        if [ -n "${_ctx}" ]; then
          # Keep preserve tokens + symbol-index after the model block.
          local _pres
          _ctx="$(printf '%s\n' "$_ctx" | sed '/^===== END DERIVED FACTS =====$/d')"
          _pres="$(python3 - <<'PY' 2>/dev/null || true
import re
from pathlib import Path
y = Path("migration.yaml").read_text(encoding="utf-8", errors="replace") if Path("migration.yaml").is_file() else ""
pres = re.findall(r"^\s*-\s+(\S+)\s*$", y.split("preserve:", 1)[-1].split("\nforbidden", 1)[0] if "preserve:" in y else "", re.M)
if not pres:
    m = re.search(r"^preserve:\s*\[(.*?)\]", y, re.M | re.S)
    if m:
        pres = [p.strip().strip("'\"") for p in m.group(1).split(",") if p.strip()]
print("preserve: " + (", ".join(pres) if pres else "(none)"))
PY
)"
          printf '%s\n%s\n' "$_ctx" "${_pres:-preserve: (none)}"
          # symbol-index still from scope files (legacy paths)
          python3 - "$SCOPE" <<'PY' 2>/dev/null || true
import re, sys
from pathlib import Path
scope = [s.strip() for s in (sys.argv[1] or "").replace(",", " ").split() if s.strip()]
SYM_CAP = 80
print("symbol-index (from scope files — do not preserve types absent here):")
roots = [Path("/projects/legacy"), Path("legacy"), Path(".")]
shown = 0
for sp in scope[:SYM_CAP]:
    path = None
    for root in roots:
        for cand in (root / sp, root / "src/main/java" / sp, root / sp.lstrip("/")):
            if cand.is_file():
                path = cand
                break
        if path:
            break
    if not path:
        continue
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        continue
    annos = sorted(set(re.findall(r"@([A-Z][A-Za-z0-9]+)", text)))[:12]
    types = sorted(set(re.findall(r"\b([A-Z][A-Za-z0-9]{2,})\b", text)))[:12]
    print(f"  - {sp}: @{','.join(annos) or '-'} types={','.join(types) or '-'}")
    shown += 1
if not shown:
    print("  - (no scope files readable)")
print("===== END DERIVED FACTS =====")
PY
          return 0
        fi
      fi
      python3 - "$SCOPE" <<'PY' 2>/dev/null || true
import re, sys
from pathlib import Path

scope = [s.strip() for s in (sys.argv[1] or "").replace(",", " ").split() if s.strip()]
lines = [
    "===== BEGIN DERIVED FACTS (authoritative over BRIEF on conflict) =====",
    "O-M3DERIVEDCTX: where BRIEF and DERIVED FACTS disagree, DERIVED FACTS win;",
    "record the conflict in the task Goal/notes. Do not invent types absent below.",
]

# preserve tokens from migration.yaml
try:
    y = Path("migration.yaml").read_text(encoding="utf-8", errors="replace")
except OSError:
    y = ""
pres = re.findall(r"^\s*-\s+(\S+)\s*$", y.split("preserve:", 1)[-1].split("\nforbidden", 1)[0] if "preserve:" in y else "", re.M)
if not pres:
    # also accept inline list form
    m = re.search(r"^preserve:\s*\[(.*?)\]", y, re.M | re.S)
    if m:
        pres = [p.strip().strip("'\"") for p in m.group(1).split(",") if p.strip()]
lines.append("preserve: " + (", ".join(pres) if pres else "(none)"))

# findings rows for this story's scope (id + description).
# O-M3DERIVEDCAP (W4-360 P2): never silent-truncate — raise notice if capped.
FIND_SCOPE_CAP = 80
FIND_ROW_CAP = 40
fin_path = Path("migration/findings-inventory.md")
find_bits = []
scope_for_find = scope[:FIND_SCOPE_CAP]
if fin_path.is_file() and scope:
    body = fin_path.read_text(encoding="utf-8", errors="replace")
    for sp in scope_for_find:
        base = Path(sp).name
        for ln in body.splitlines():
            if base in ln or sp in ln:
                find_bits.append(ln.strip()[:200])
                if len(find_bits) >= FIND_ROW_CAP:
                    break
        if len(find_bits) >= FIND_ROW_CAP:
            break
lines.append("findings:")
if len(scope) > FIND_SCOPE_CAP or len(find_bits) >= FIND_ROW_CAP:
    lines.append(
        f"  - (findings: scanned {min(len(scope), FIND_SCOPE_CAP)} of "
        f"{len(scope)} scope paths; rows={len(find_bits)} — truncated; "
        f"do not treat absence as proof)"
    )
if find_bits:
    lines.extend("  - " + b for b in find_bits)
else:
    lines.append("  - (none matched for scope)")

# ADR-24 fallback only: full-path join (never basename) when model missing
dep_path = Path("migration/dependency-order.md")
dep_bits = []
if dep_path.is_file() and scope:
    body = dep_path.read_text(encoding="utf-8", errors="replace")
    for ln in body.splitlines():
        if any(sp in ln for sp in scope):
            dep_bits.append(ln.strip()[:200])
            if len(dep_bits) >= 40:
                break
lines.append("dependency-order:")
if dep_bits:
    lines.extend("  - " + b for b in dep_bits)
else:
    lines.append("  - (none matched for scope)")

# symbol-index: annotations/types actually present in scoped legacy files
# O-M3DERIVEDCAP: cap raised; always declare N of M when truncated (W4-360 P2).
SYM_CAP = 80
lines.append("symbol-index (from scope files — do not preserve types absent here):")
roots = [Path("/projects/legacy"), Path("legacy"), Path(".")]
shown = 0
skipped = max(0, len(scope) - SYM_CAP)
for sp in scope[:SYM_CAP]:
    path = None
    for root in roots:
        for cand in (root / sp, root / "src/main/java" / sp, root / sp.lstrip("/")):
            if cand.is_file():
                path = cand
                break
        if path:
            break
        # basename search under legacy/src
        base = Path(sp).name
        for root in roots:
            src = root / "src/main/java"
            if not src.is_dir():
                continue
            hits = list(src.rglob(base))
            if hits:
                path = hits[0]
                break
        if path:
            break
    if path is None:
        continue
    try:
        src = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        continue
    annos = sorted(set(re.findall(r"@([A-Z][A-Za-z0-9]+)", src)))[:12]
    types = sorted(set(re.findall(r"\b([A-Z][a-zA-Z0-9]{6,})\b", src)))[:16]
    # Drop the file's own simple name from noise
    own = path.stem
    types = [t for t in types if t != own][:12]
    lines.append(f"  - {path.name}: annos=[{', '.join(annos) or '—'}] types=[{', '.join(types) or '—'}]")
    shown += 1
if shown == 0:
    lines.append("  - (no scope files resolved under /projects/legacy)")
elif skipped > 0:
    lines.append(
        f"  - (symbol-index: {shown} of {len(scope)} scope files — truncated; "
        f"do not treat absence as proof for the {skipped} omitted paths)"
    )

lines.append("===== END DERIVED FACTS =====")
text = "\n".join(lines)
# Cap so prompt stays within seat budget; never silent (O-M3DERIVEDCAP).
CHAR_CAP = 12000
if len(text) > CHAR_CAP:
    text = (
        text[: CHAR_CAP - 120]
        + "\n… (O-M3DERIVEDCAP: DERIVED FACTS truncated at "
        + f"{CHAR_CAP} chars — do not treat omitted rows as absent from code)\n"
        + "===== END DERIVED FACTS =====\n"
    )
print(text)
PY
    }
    m3_build_prompt() { # $1=fresh|fix — sets P from brief or plan-lint RED fix
      local mode="${1:-fresh}"
      local BRIEF_INLINE=""
      local DERIVED_INLINE=""
      # O-M3EMPTY: if tasks.md never landed, always use fresh create prompt —
      # "fix specs/<slug>/" misleads when the directory does not exist.
      if [ "$mode" = "fix" ] && [ ! -f "specs/${SLUG}/tasks.md" ]; then
        mode=fresh
      fi
      # O-M3BRIEFINLINE (R-Q3′): paste brief into the seat prompt — path/-f alone
      # did not stop Qwen from reading M1 artifacts instead (S02 w1). Cap ~24k
      # chars so large briefs still fit; S02 ~3k tokens.
      if [ -n "${BRIEF:-}" ] && [ -f "$BRIEF" ]; then
        BRIEF_INLINE="$(head -c 24000 "$BRIEF" 2>/dev/null || true)"
      fi
      # O-M3DERIVEDCTX (ADR-21 G4): derived facts beside brief; zero tool cost.
      DERIVED_INLINE="$(m3_derived_facts)"
      # O-GROUNDLOG: emit G4 once per story (first prompt build) for demo chain visibility.
      if [ "${_GCHAIN_G4_LOGGED:-}" != "${SID:-}" ]; then
        _GCHAIN_G4_LOGGED="${SID:-}"
        log_gchain_m3_g4 "$DERIVED_INLINE" "${SID:-}"
      fi
      # O-M3FIRSTWRITE / O-M3SKILLNAV / O-M3BRIEFINLINE: lead with first-tool EDIT;
      # forbid M1 explore before mutate; brief is inlined below (not a path to chase).
      P="M3 ONLY for ${SID} (${SLUG}). O-M3FIRSTWRITE: your FIRST tool MUST be edit/write on specs/${SLUG}/tasks.md (fill Goal/Target/Class·Shape; remove O-M3ALL-SKELETON/preseed markers). Do NOT read migration.yaml, findings-inventory.md, dependency-order.md, specs/${SLUG}/spec.md, or plan.md before that first edit — those burn the ${M3_STALL_ABORT_SECS:-120}s stall budget. Brief + DERIVED FACTS are INLINED below; on conflict DERIVED FACTS win (O-M3DERIVEDCTX). After the first tasks.md mutate: fix plan-lint, optionally write plan.md/spec.md stubs, verify: ${M3_LINT_CMD} (exit 0). If you commit, ONE commit starting with '${SID} spec:' staging ONLY specs/${SLUG}/ (never git add -A / .hermes / __pycache__); prefer leaving uncommitted for outer-loop mechanical commit (O-M3COMMITHYGIENE/O-M3MECHSCOPE). DO NOT PUSH. Scope=${SCOPE}. ${PKG_RENAME_HINT} ACCEPTANCE deploy=${DEPLOY} (if false: no acceptance.path endpoint tasks). Every task needs **Class**: rewrite|infer and **Shape**: create|modify|remove|structure|verify. O-SPECREIMPL: REDESIGN classes in spec.md need **Port**: reimplement.

===== BEGIN BRIEF ${BRIEF} =====
${BRIEF_INLINE}
===== END BRIEF =====

${DERIVED_INLINE}"
      if [ "$mode" = "fix" ]; then
        ORDER_HINT=""
        if grep -q "LINT:order" /tmp/plan-lint.txt 2>/dev/null; then
          ORDER_HINT=" O-M3ORDER: LINT:order means EVERY Class=rewrite task MUST appear before ANY Class=infer — reorder #### headings (do not leave characterization/verify infer before migration rewrite)."
        fi
        P="M3 FIX for ${SID} (${SLUG}) — plan-lint RED (see /tmp/plan-lint.txt).${ORDER_HINT} O-M3FIRSTWRITE: your FIRST tool MUST be edit on specs/${SLUG}/tasks.md (fill Goal/Target; put verbatim migration.yaml preserve: tokens in a covering task; remove skeleton/preseed markers). Do NOT read migration.yaml, findings-inventory.md, dependency-order.md, spec.md, or plan.md before that first edit. Brief + DERIVED FACTS are INLINED below; on conflict DERIVED FACTS win (O-M3DERIVEDCTX). Then clear every lint finding. Verify ${M3_LINT_CMD} exits 0. If you commit, stage ONLY specs/${SLUG}/ (never git add -A / .hermes / __pycache__); prefer leaving uncommitted for outer-loop mechanical commit. DO NOT PUSH. Scope=${SCOPE}. ${PKG_RENAME_HINT} ACCEPTANCE deploy=${DEPLOY}.

===== BEGIN BRIEF ${BRIEF} =====
${BRIEF_INLINE}
===== END BRIEF =====

${DERIVED_INLINE}"
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
    # O-M3LINTLOG (W4R7 W-2): attributable per-seat lint counts on every gate line.
    _m3_lint_count() {
      local c=0
      if [ -f /tmp/plan-lint.txt ]; then
        c=$(grep -cE '^LINT:' /tmp/plan-lint.txt 2>/dev/null || true)
      fi
      echo "${c:-0}"
    }
    _m3_seat_lint_prev=-1
    : >"/tmp/m3-lint-seats-${SID}.tsv"
    _m3_mark_lint_before_seat() {
      _m3_seat_lint_prev="$(_m3_lint_count)"
    }
    _m3_record_lint_seat() { # $1=seat-tag  (after lint evidence refreshed)
      local seat="$1" cur prev ts
      cur="$(_m3_lint_count)"
      prev="${_m3_seat_lint_prev:--1}"
      ts=$(date -u +%Y-%m-%dT%H:%MZ)
      printf '%s\t%s\t%s\t%s\n' "$seat" "$prev" "$cur" "$ts" \
        >>"/tmp/m3-lint-seats-${SID}.tsv"
      _m3_seat_lint_prev="$cur"
    }
    _m3_gate_lint_detail() { # $1=base label → "label — lint 18→14"
      local base="$1" cur prev
      cur="$(_m3_lint_count)"
      prev="${_m3_seat_lint_prev:--1}"
      # Prefer last recorded seat row when available (post-_m3_record_lint_seat).
      if [ -f "/tmp/m3-lint-seats-${SID}.tsv" ]; then
        local last
        last=$(tail -1 "/tmp/m3-lint-seats-${SID}.tsv" 2>/dev/null || true)
        if [ -n "$last" ]; then
          prev=$(printf '%s' "$last" | cut -f2)
          cur=$(printf '%s' "$last" | cut -f3)
        fi
      fi
      if [ "$prev" -ge 0 ] 2>/dev/null; then
        echo "${base} — lint ${prev}→${cur}"
      else
        echo "${base} — lint ${cur}"
      fi
    }

    # --- Phase A: Qwen worker attempts (default 2) ---
    # O-M3QUOTA-GATE: if a prior session left lint-green, advance before any seat.
    if [ "${WORKER_M3_FIRST:-false}" = "true" ]; then
      ATTEMPT=1
      while [ "$ATTEMPT" -le "${M3_WORKER_ATTEMPTS:-2}" ]; do
        if m3_lint_green; then
          [ -n "$(git status --porcelain "specs/${SLUG}/")" ] && git add "specs/${SLUG}/" && git commit -q -m "${SID} spec: outer-loop mechanical commit of lint-green spec" 2>/dev/null
          m3_phase_gate "M3 SPECIFY ${SLUG} plan-lint" GREEN "commit $(git rev-parse --short HEAD)"
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
        _m3_mark_lint_before_seat
        # O-M3WCHATSETE: bare wchat under set -e aborts outer when worker_rc≠0
        # (lost S01 A/B at first tool-round exit — no fail_run, only TMPARCHIVE).
        set +e
        wchat "m3-${SID}-w${ATTEMPT}" "$P" "M3 SPECIFY ${SLUG} (worker)" \
          -f "$BRIEF" -f migration/architecture-profile.md
        mchat_rc=$?
        set -e
        unset M3_EXPECT_TASKS
        if [ -f "/tmp/m3-empty-abort-m3-${SID}-w${ATTEMPT}" ]; then
          log "         O-M3EMPTY/O-M3QWENSTALL: worker produced no tasks.md — attempt ${ATTEMPT} spent (early abort)"
          m3_write_lint_evidence
          _m3_record_lint_seat "w${ATTEMPT}"
          m3_phase_gate "M3 SPECIFY ${SLUG} plan-lint" RED \
            "$(_m3_gate_lint_detail "O-M3EMPTY early abort")"
          phase_retry "M3 SPECIFY ${SLUG} — empty write; advancing"
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
            [ -n "$(git status --porcelain "specs/${SLUG}/")" ] && git add "specs/${SLUG}/" && git commit -q -m "${SID} spec: outer-loop mechanical commit of lint-green spec" 2>/dev/null
            _m3_record_lint_seat "w${ATTEMPT}"
            m3_phase_gate "M3 SPECIFY ${SLUG} plan-lint" GREEN \
              "$(_m3_gate_lint_detail "commit $(git rev-parse --short HEAD)")"
            phase_ok "M3 SPECIFY — ${SLUG} plan-lint-green after O-M3KILL (tip already green); commit $(git rev-parse --short HEAD)"
            M3_DONE=1
            break
          fi
          log "         O-M3KILL: worker M3 killed (rc=${mchat_rc}) — attempt ${ATTEMPT} NOT spent"
          phase_retry "M3 SPECIFY ${SLUG} — worker session killed; not counting as lint fail"
          continue
        fi
        if m3_lint_green; then
          [ -n "$(git status --porcelain "specs/${SLUG}/")" ] && git add "specs/${SLUG}/" && git commit -q -m "${SID} spec: outer-loop mechanical commit of lint-green spec" 2>/dev/null
          _m3_record_lint_seat "w${ATTEMPT}"
          m3_phase_gate "M3 SPECIFY ${SLUG} plan-lint" GREEN \
            "$(_m3_gate_lint_detail "commit $(git rev-parse --short HEAD)")"
          phase_ok "M3 SPECIFY — ${SLUG} plan-lint-green after Qwen; commit $(git rev-parse --short HEAD)"
          M3_DONE=1
          break
        fi
        m3_write_lint_evidence
        _m3_record_lint_seat "w${ATTEMPT}"
        m3_phase_gate "M3 SPECIFY ${SLUG} plan-lint" RED \
          "$(_m3_gate_lint_detail "worker attempt ${ATTEMPT}")"
        phase_retry "M3 SPECIFY ${SLUG} — Qwen plan still RED"
        ATTEMPT=$((ATTEMPT + 1))
      done
    fi

    # --- Phase B: MiniMax backstop (default 1) when worker path did not green ---
    if [ "$M3_DONE" != "1" ] && [ "${M3_ORCH_BACKSTOP:-1}" -ge 1 ]; then
      ATTEMPT=1
      # O-M2429CAP / O-M3QUOTA: cap consecutive NOT-spent 429s (default 3)
      M3_429_BACKOFF_SECS="${M3_429_BACKOFF_SECS:-${M2_429_BACKOFF_SECS:-900}}"
      M3_429_MAX="${M3_429_MAX:-${M2_429_MAX:-3}}"
      M3_429_COUNT=0
      # O-M3CONVERGEBUDGET (W4-273): flat M3_ORCH_BACKSTOP starved converging
      # S02 (34→2). While lint count strictly decreases after a spent seat,
      # grant +1 effective attempt (default max 1 bonus), still capped by 429.
      M3_CONVERGE_BONUS_MAX="${M3_CONVERGE_BONUS_MAX:-1}"
      _m3_effective_backstop="${M3_ORCH_BACKSTOP:-1}"
      _m3_converge_bonus_used=0
      _m3_prev_lint=-1
      # O-M3WORKERREENTRY: at most one Qwen edit seat after MiniMax partial
      # write / 429 when tasks.md is already authored (not skeleton).
      _m3_reentry_done=0
      _m3_tasks_populated() {
        local f="specs/${SLUG}/tasks.md"
        [ -f "$f" ] || return 1
        grep -qE 'O-M3QWENSTALL preseed|O-M3ALL-SKELETON' "$f" 2>/dev/null && return 1
        grep -qE '^#### T-[0-9]+[A-Za-z]*' "$f" 2>/dev/null
      }
      # Seed prev lint from current RED evidence (pre-loop) when present.
      if [ -f /tmp/plan-lint.txt ]; then
        _m3_prev_lint="$(_m3_lint_count)"
      fi
      while [ "$ATTEMPT" -le "${_m3_effective_backstop}" ]; do
        if m3_lint_green; then
          M3_429_COUNT=0
          [ -n "$(git status --porcelain "specs/${SLUG}/")" ] && git add "specs/${SLUG}/" && git commit -q -m "${SID} spec: outer-loop mechanical commit of lint-green spec" 2>/dev/null
          m3_phase_gate "M3 SPECIFY ${SLUG} plan-lint" GREEN \
            "$(_m3_gate_lint_detail "commit $(git rev-parse --short HEAD)")"
          phase_ok "M3 SPECIFY — ${SLUG} plan-lint-green; commit $(git rev-parse --short HEAD)"
          M3_DONE=1
          break
        fi
        if [ "${WORKER_M3_FIRST:-false}" = "true" ]; then
          phase_start "M3 SPECIFY — plan story ${SLUG} (${STORY_IDX}/${STORY_COUNT}) [MiniMax backstop ${ATTEMPT}/${M3_ORCH_BACKSTOP}]"
          log "         O-M3WORKER: MiniMax backstop after Qwen plan-lint RED"
          seat_tag="orch${ATTEMPT}"
          seat_label="M3 SPECIFY ${SLUG} (orch backstop)"
        else
          # O-M3ROUTE: MiniMax drafts first (W4R7 operator MiniMax-first).
          phase_start "M3 SPECIFY — plan story ${SLUG} (${STORY_IDX}/${STORY_COUNT}) [MiniMax draft ${ATTEMPT}/${M3_ORCH_BACKSTOP}]"
          log "         O-M3ROUTE: MiniMax draft (WORKER_M3_FIRST=false)"
          seat_tag="a${ATTEMPT}"
          seat_label="M3 SPECIFY ${SLUG}"
        fi
        SPEC_TASKS=$(ls specs/${SID}-*/tasks.md 2>/dev/null | head -1)
        if [ -n "$SPEC_TASKS" ]; then m3_build_prompt fix; else m3_build_prompt fresh; fi
        # O-M3COMMITHYGIENE: capture tip before seat so scooped agent commits can be refused.
        _m3_pre_sha=$(git rev-parse HEAD)
        _m3_mark_lint_before_seat
        # O-M3WCHATSETE: same set -e trap as wchat — capture orch rc.
        set +e
        mchat "m3-${SID}-${seat_tag}" "$P" "$seat_label"
        mchat_rc=$?
        set -e
        # Criterion 10 refuse branch on M3 path (not M4-only commit-hygiene).
        _m3_refuse_bad_tip "$_m3_pre_sha" "$SLUG" || true
        if [ "$mchat_rc" -eq 137 ] || [ "$mchat_rc" -eq 143 ]; then
          log "         O-M3KILL: orch M3 killed (rc=${mchat_rc}) — backstop NOT spent"
          phase_retry "M3 SPECIFY ${SLUG} — orch session killed; not counting"
          continue
        fi
        if m3_lint_green; then
          M3_429_COUNT=0
          [ -n "$(git status --porcelain "specs/${SLUG}/")" ] && git add "specs/${SLUG}/" && git commit -q -m "${SID} spec: outer-loop mechanical commit of lint-green spec" 2>/dev/null
          # Refuse mechanical tip too if somehow polluted (defense in depth).
          if ! python3 "$HARNESS/commit-hygiene.py" HEAD >/tmp/m3-hygiene.out 2>&1; then
            log "         O-M3COMMITHYGIENE: refuse tip $(git rev-parse --short HEAD) — $(tr '\n' ' ' </tmp/m3-hygiene.out)"
            git reset --hard "$_m3_pre_sha" >/dev/null 2>&1 || true
          else
            _m3_record_lint_seat "${seat_tag}"
            m3_phase_gate "M3 SPECIFY ${SLUG} plan-lint" GREEN \
              "$(_m3_gate_lint_detail "commit $(git rev-parse --short HEAD)")"
            phase_ok "M3 SPECIFY — ${SLUG} plan-lint-green after MiniMax; commit $(git rev-parse --short HEAD)"
            M3_DONE=1
            break
          fi
        fi
        if grep -qE "429|Too Many Requests|Rate limit|rate.?limit" "/tmp/outer-m3-${SID}-${seat_tag}.log" 2>/dev/null; then
          M3_429_COUNT=$((M3_429_COUNT + 1))
          if [ "$M3_429_COUNT" -ge "$M3_429_MAX" ]; then
            log "         O-M2429CAP: M3 ${SID} ${M3_429_COUNT} consecutive rate-limited seats (max ${M3_429_MAX}) — failing run"
            fail_run "quota exhausted after ${M3_429_COUNT} rate-limited seats (O-M2-429CAP)"
          fi
          m3_write_lint_evidence
          _m3_record_lint_seat "${seat_tag}"
          m3_phase_gate "M3 SPECIFY ${SLUG} plan-lint" RED \
            "$(_m3_gate_lint_detail "MiniMax ${seat_tag} 429")"
          # O-M3WORKERREENTRY: MiniMax often lands a populated plan then 429s.
          # Qwen edit-only (Acceptance / remaining lints) before burning more
          # scarce orch seats — stall aborts read-only in ~120s if it fails.
          # W4-366/P-2: must fire under MiniMax-first (WORKER_M3_FIRST=false) too;
          # prior gate on =true left the happy-path route unable to reenter.
          if [ "${M3_WORKER_REENTRY:-true}" = "true" ] \
            && [ "${_m3_reentry_done}" != "1" ] \
            && _m3_tasks_populated; then
            _m3_reentry_done=1
            log "         O-M3WORKERREENTRY: populated tasks.md after MiniMax 429 — Qwen edit seat before backoff"
            phase_start "M3 SPECIFY — plan story ${SLUG} (${STORY_IDX}/${STORY_COUNT}) [worker reentry 1/1]"
            m3_build_prompt fix
            M3_EXPECT_TASKS="specs/${SLUG}/tasks.md"
            export M3_EXPECT_TASKS
            _m3_mark_lint_before_seat
            wchat "m3-${SID}-re1" "$P" "M3 SPECIFY ${SLUG} (worker reentry)" \
              -f "$BRIEF" -f migration/architecture-profile.md || true
            unset M3_EXPECT_TASKS
            if m3_lint_green; then
              M3_429_COUNT=0
              [ -n "$(git status --porcelain "specs/${SLUG}/")" ] && git add "specs/${SLUG}/" && git commit -q -m "${SID} spec: outer-loop mechanical commit of lint-green spec" 2>/dev/null
              _m3_record_lint_seat "re1"
              m3_phase_gate "M3 SPECIFY ${SLUG} plan-lint" GREEN \
                "$(_m3_gate_lint_detail "worker reentry GREEN")"
              phase_ok "M3 SPECIFY — ${SLUG} plan-lint-green via O-M3WORKERREENTRY; commit $(git rev-parse --short HEAD)"
              M3_DONE=1
              break
            fi
            m3_write_lint_evidence
            _m3_record_lint_seat "re1"
            m3_phase_gate "M3 SPECIFY ${SLUG} plan-lint" RED \
              "$(_m3_gate_lint_detail "worker reentry")"
          fi
          log "         O-M3QUOTA: MiniMax rate-limited — NOT spent; backoff ${M3_429_BACKOFF_SECS}s (${M3_429_COUNT}/${M3_429_MAX})"
          phase_retry "M3 SPECIFY ${SLUG} — quota; sleeping ${M3_429_BACKOFF_SECS}s (O-M3QUOTA ${M3_429_COUNT}/${M3_429_MAX})"
          sleep "${M3_429_BACKOFF_SECS}"
          continue
        fi
        M3_429_COUNT=0  # O-M2429CAP: non-429 seat resets counter
        # O-M3WORKERREENTRY: MiniMax wrote but lint still RED (no 429) — try
        # Qwen edit once before another orch seat. (Same W4-366 ungating as 429 path.)
        if [ "${M3_WORKER_REENTRY:-true}" = "true" ] \
          && [ "${_m3_reentry_done}" != "1" ] \
          && _m3_tasks_populated; then
          # Record MiniMax RED delta before reentry so seats are attributable.
          m3_write_lint_evidence
          _m3_record_lint_seat "${seat_tag}"
          m3_phase_gate "M3 SPECIFY ${SLUG} plan-lint" RED \
            "$(_m3_gate_lint_detail "MiniMax attempt ${ATTEMPT}")"
          _m3_reentry_done=1
          log "         O-M3WORKERREENTRY: populated tasks.md after MiniMax RED — Qwen edit seat"
          phase_start "M3 SPECIFY — plan story ${SLUG} (${STORY_IDX}/${STORY_COUNT}) [worker reentry 1/1]"
          m3_build_prompt fix
          M3_EXPECT_TASKS="specs/${SLUG}/tasks.md"
          export M3_EXPECT_TASKS
          _m3_mark_lint_before_seat
          wchat "m3-${SID}-re1" "$P" "M3 SPECIFY ${SLUG} (worker reentry)" \
            -f "$BRIEF" -f migration/architecture-profile.md || true
          unset M3_EXPECT_TASKS
          if m3_lint_green; then
            [ -n "$(git status --porcelain "specs/${SLUG}/")" ] && git add "specs/${SLUG}/" && git commit -q -m "${SID} spec: outer-loop mechanical commit of lint-green spec" 2>/dev/null
            _m3_record_lint_seat "re1"
            m3_phase_gate "M3 SPECIFY ${SLUG} plan-lint" GREEN \
              "$(_m3_gate_lint_detail "worker reentry GREEN")"
            phase_ok "M3 SPECIFY — ${SLUG} plan-lint-green via O-M3WORKERREENTRY; commit $(git rev-parse --short HEAD)"
            M3_DONE=1
            break
          fi
          m3_write_lint_evidence
          _m3_record_lint_seat "re1"
          m3_phase_gate "M3 SPECIFY ${SLUG} plan-lint" RED \
            "$(_m3_gate_lint_detail "worker reentry")"
        else
          m3_write_lint_evidence
          _m3_record_lint_seat "${seat_tag}"
          m3_phase_gate "M3 SPECIFY ${SLUG} plan-lint" RED \
            "$(_m3_gate_lint_detail "MiniMax attempt ${ATTEMPT}")"
        fi
        # O-M3CONVERGEBUDGET: spent RED seat with strictly fewer LINT: lines
        # → extend effective backstop once (default).
        _m3_cur_lint="$(_m3_lint_count)"
        if [ "${_m3_prev_lint}" -ge 0 ] \
          && [ "${_m3_cur_lint}" -lt "${_m3_prev_lint}" ] \
          && [ "${_m3_converge_bonus_used}" -lt "${M3_CONVERGE_BONUS_MAX}" ]; then
          _m3_converge_bonus_used=$((_m3_converge_bonus_used + 1))
          _m3_effective_backstop=$((_m3_effective_backstop + 1))
          log "         O-M3CONVERGEBUDGET: lint ${_m3_prev_lint}→${_m3_cur_lint} — +1 MiniMax attempt (bonus ${_m3_converge_bonus_used}/${M3_CONVERGE_BONUS_MAX}; effective=${_m3_effective_backstop})"
        fi
        _m3_prev_lint="${_m3_cur_lint}"
        ATTEMPT=$((ATTEMPT + 1))
      done
    fi

    if [ "$M3_DONE" != "1" ]; then
      fail_run "M3 SPECIFY ${SLUG} failed plan-lint after M3 attempts (WORKER_M3_FIRST=${WORKER_M3_FIRST:-false})"
    fi
  fi

  # O-M3DELIVERLOG: list demo-visible M3 artifacts now that this story is GREEN.
  emit_m3_deliverables

  # O-M3ALL author pass: no M4 until every story plan exists + whole-set GREEN.
  if [ "$M3_ALL_PASS" = "author" ]; then
    phase_ok "M3-ALL author — ${SLUG} plan ready (defer M4 until whole-set lint)"
    # O-STOPAFTERSTORY — validation runs: exit after this story's M3 author
    # (e.g. STOP_AFTER_STORY=S01 for a clean A/B before burning S02…).
    if [ -n "${STOP_AFTER_STORY:-}" ] && [ "${STOP_AFTER_STORY}" = "$SID" ]; then
      phase_gate "M3 SPECIFY stop-after-story" GREEN \
        "STOP_AFTER_STORY=${SID} — refusing further stories / M4"
      log "         O-STOPAFTERSTORY: ${SID} M3 author complete — not continuing"
      echo "outer-complete: STOP_AFTER_STORY=${SID} $(date -u +%Y-%m-%dT%H:%MZ)" \
        > /tmp/outer-loop-done
      exit 0
    fi
    STORY_TAG=""
    continue
  fi

  # ----------------------------------------------------- M3-ALL JIT (waterfall)
  # Mandatory antidotes: JIT re-lint; Owns/Port/Shape amend → whole-set re-lint;
  # plan-vs-reality delta is first-class (never suppress).
  phase_start "M3-ALL JIT — re-lint ${SLUG} before M4 (waterfall antidote)"
  set +e
  bash "$HARNESS/m3-all-lint.sh" --mode=jit --story "$SID" --root . \
    > /tmp/m3-all-jit.txt 2>&1
  _m3all_rc=$?
  set -e
  if [ "$_m3all_rc" = "3" ]; then
    # O-M3ALLAMENDJIT: EXECUTE_ONLY / M3_ALL=0 cannot satisfy whole-set
    # (sibling skeletons → MISSING + Oracle/Assumes noise). Restamp focus
    # story + re-JIT; full whole-set stays mandatory when M3_ALL authors all.
    if [ -n "${EXECUTE_ONLY_STORY:-}" ] || [ "${M3_ALL:-1}" = "0" ]; then
      log "         O-M3ALL-AMEND: restamp ${SID} + re-JIT (skip whole-set; O-M3ALLAMENDJIT)"
      bash "$HARNESS/m3-all-lint.sh" --mode=restamp --story "$SID" --root . \
        > /tmp/m3-all-restamp.txt 2>&1 \
        || fail_run "O-M3ALL restamp failed for ${SID} (see /tmp/m3-all-restamp.txt)"
      set +e
      bash "$HARNESS/m3-all-lint.sh" --mode=jit --story "$SID" --root . \
        > /tmp/m3-all-jit.txt 2>&1
      _m3all_rc=$?
      set -e
      if [ "$_m3all_rc" != "0" ]; then
        phase_gate "M3-ALL JIT ${SLUG}" RED "post-restamp see /tmp/m3-all-jit.txt"
        fail_run "O-M3ALL JIT RED after restamp for ${SID} (see /tmp/m3-all-jit.txt)"
      fi
      phase_gate "M3-ALL JIT ${SLUG}" GREEN "amend restamped (O-M3ALLAMENDJIT)"
    else
      log "         O-M3ALL-AMEND: Owns/Port/Shape changed — whole-set re-lint"
      bash "$HARNESS/m3-all-lint.sh" --mode=whole-set --root . \
        > /tmp/m3-all-whole.txt 2>&1 \
        || fail_run "O-M3ALL whole-set RED after ${SID} amend (see /tmp/m3-all-whole.txt)"
      phase_gate "M3-ALL whole-set (post-amend)" GREEN "amend re-lint OK"
    fi
  elif [ "$_m3all_rc" != "0" ]; then
    phase_gate "M3-ALL JIT ${SLUG}" RED "see /tmp/m3-all-jit.txt"
    fail_run "O-M3ALL JIT RED for ${SID} (see /tmp/m3-all-jit.txt)"
  else
    phase_gate "M3-ALL JIT ${SLUG}" GREEN "waterfall antidote"
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
      done < <(grep -oE 'T-[0-9]+[A-Za-z]*' "$SPEC_TASKS" 2>/dev/null | sort -u)
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
      && git log --oneline "${SPEC_SHA}..HEAD" 2>/dev/null | grep -qE '^[0-9a-f]+ T-[0-9]+[A-Za-z]*:'; then
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
        | grep -E '^[0-9a-f]+ T-[0-9]+[A-Za-z]*:' | grep -oE 'T-[0-9]+[A-Za-z]*' | sort -u)
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
      done < <(grep -oE 'T-[0-9]+[A-Za-z]*' "$SPEC_TASKS" 2>/dev/null | sort -u)
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
      if [ -n "$_t1" ] && git log --oneline "${_floor}..HEAD" 2>/dev/null | grep -qE "^[0-9a-f]+ T-[0-9]+[A-Za-z]*:"; then
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
      # W4-609 #3 — G10 at M3→M4 handoff (code vs typed acceptance)
      log_gchain_m4_g10 "${SID}"
      emit_story_epilog "complete"
      echo "${SID},complete,$(date -u +%s)" >> "$STATE"
      git add "$STATE" && git commit -q -m "${SID} story complete: ${OUTCOME}" 2>/dev/null || true
      # O-STOPAFTEREXEC — validation runs: exit after this story's M4/M5 ship
      # (e.g. STOP_AFTER_EXECUTE=S02 + M3_ALL=0 for first-M4 probe before
      # spending MiniMax on later-story M3 author). Distinct from
      # STOP_AFTER_STORY (author-pass only; refuses M4).
      if [ -n "${STOP_AFTER_EXECUTE:-}" ] && [ "${STOP_AFTER_EXECUTE}" = "$SID" ]; then
        phase_gate "M4/M5 stop-after-execute" GREEN \
          "STOP_AFTER_EXECUTE=${SID} — refusing further stories"
        log "         O-STOPAFTEREXEC: ${SID} M4/M5 complete — not continuing"
        echo "outer-complete: STOP_AFTER_EXECUTE=${SID} $(date -u +%Y-%m-%dT%H:%MZ)" \
          > /tmp/outer-loop-done
        exit 0
      fi
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

# O-M3PREFLIGHT: after attempting every story, refuse the pass if any brief
# failed vs current roadmap (distinct cause; seats were not spent on them).
if [ -n "${M3_PREFLIGHT_HELD:-}" ]; then
  phase_gate "M3 PREFLIGHT held stories" RED "${M3_PREFLIGHT_HELD}"
  fail_run "O-M3PREFLIGHT: brief-quality RED for ${M3_PREFLIGHT_HELD} vs current roadmap (see /tmp/m3-preflight-*.txt) — fix/regen briefs before M3 seats"
fi

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
