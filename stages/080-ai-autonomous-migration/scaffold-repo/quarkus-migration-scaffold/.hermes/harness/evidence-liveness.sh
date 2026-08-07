#!/usr/bin/env bash
# O-EVIDLIVE — evidence liveness (Wave4 R-A6 / retrospective §3.3).
#
# Each *active* K-system must emit ≥1 ledger row per story, or story-gate RED.
# Silent-and-presumed-watching is forbidden. Channels that may legitimately
# have nothing to report still emit an explicit none/checked row (heartbeat).
#
# Active (must live): K1 K2 K3 K9 K11
# Retired from liveness (bank note): K10 — optional ADVANCE-gated hints;
#   silence until first accepted tip is expected, not a dead watch.
#
# Usage (from workspace root /projects/modernized):
#   bash .hermes/harness/evidence-liveness.sh init
#   bash .hermes/harness/evidence-liveness.sh record <story> <K#> <rows> [note…]
#   bash .hermes/harness/evidence-liveness.sh heartbeat <story>   # fill gaps
#   bash .hermes/harness/evidence-liveness.sh check <story>       # exit 1 if silent
set -euo pipefail

ROOT="${ORACLE_ROOT:-.}"
LEDGER="${EVIDENCE_LIVENESS_LEDGER:-$ROOT/migration/evidence-liveness.md}"
EVENTS="${SUPERVISOR_EVENTS:-/tmp/supervisor-events.csv}"
ACTIVE_K="K1 K2 K3 K9 K11"

HEADER='# Evidence liveness (O-EVIDLIVE)

Each active K-system emits ≥1 row per story or story-gate RED.
K10 retired from this gate (optional hints — see bank).

| when (UTC) | story | system | rows | note |
|---|---|---|---|---|
'

cmd="${1:-}"
shift || true

init_ledger() {
  mkdir -p "$(dirname "$LEDGER")"
  if [ ! -f "$LEDGER" ]; then
    printf '%s' "$HEADER" > "$LEDGER"
  fi
}

row_count() { # $1=story $2=system → single integer (never "00")
  local story="$1" sys="$2" n
  [ -f "$LEDGER" ] || { echo 0; return; }
  # grep -c exits 1 when count is 0 — do not pair with `|| echo 0` (→ "00").
  n=$(grep -cE "^\| 20[^|]*\| ${story} \| ${sys} \|" "$LEDGER" 2>/dev/null || true)
  echo "${n:-0}"
}

record() { # story system rows note…
  local story="$1" sys="$2" rows="$3"
  shift 3 || true
  local note="$*"
  note=${note//|/\/}
  note=${note//$'\n'/ }
  init_ledger
  local ts
  ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  printf '| %s | %s | %s | %s | %s |\n' "$ts" "$story" "$sys" "$rows" "${note:-recorded}" >> "$LEDGER"
  echo "evidlive:${story}:${sys}:${rows}"
}

# Natural signals → ledger rows for systems still at 0.
heartbeat() { # story
  local story="$1"
  local tasks="${STORY_TASKS:-}"
  local roadmap="${ROADMAP_FILE:-$ROOT/migration/roadmap.md}"
  local discovered="$ROOT/migration/discovered.md"
  init_ledger

  # ---- K1: plan-lint ownership exercised this supervisor (PASS logged) ----
  if [ "$(row_count "$story" K1 | tr -d '[:space:]')" = "0" ]; then
    if grep -qE 'plan lint: PASS|PLAN OK|m3-all.*PASS|LINT:incident-' \
      /tmp/supervisor.log /tmp/plan-lint.txt /tmp/m3-all-lint.txt 2>/dev/null; then
      record "$story" K1 1 "plan-lint/m3-all exercised"
    elif [ -n "$tasks" ] && [ -f "$tasks" ]; then
      # Plan exists with Owns/Target — ownership surface was authored.
      if grep -qE '\*\*Owns\*\*|\*\*Target\*\*|Findings' "$tasks" 2>/dev/null; then
        record "$story" K1 1 "tasks.md ownership surface present"
      fi
    fi
  fi

  # ---- K2: Analysis evidence (Findings-bearing tasks) ----
  if [ "$(row_count "$story" K2 | tr -d '[:space:]')" = "0" ]; then
    local findings_n=0 evid_n=0
    if [ -n "$tasks" ] && [ -f "$tasks" ]; then
      # O-EVIDLIVEK2NONE (W4-664): **Findings**: (none) is not a Findings-bearing
      # task — counting every Findings header false-silenced S01 (9 headers, 1 real).
      findings_n=$(
        grep -E '\*\*Findings\*\*:' "$tasks" 2>/dev/null \
          | grep -civE '\*\*Findings\*\*:[[:space:]]*(\(none\)|-)?[[:space:]]*$' \
          || true
      )
      findings_n=${findings_n:-0}
    fi
    if [ -f "$EVENTS" ]; then
      evid_n=$(grep -cE ',k2:evidence,' "$EVENTS" 2>/dev/null || true); evid_n=${evid_n:-0}
    fi
    # Reconstruct from live task-packet Analysis evidence when the events CSV
    # was rotated/lost after M4 (ship gate must not RED on missing CSV alone).
    if [ "${evid_n:-0}" -eq 0 ] 2>/dev/null \
      && [ "${findings_n:-0}" -gt 0 ] 2>/dev/null \
      && [ -n "$tasks" ] && [ -f "$tasks" ] \
      && [ -f "$ROOT/.hermes/harness/task-packet.py" ]; then
      local tid pkt
      while IFS= read -r tid; do
        [ -n "$tid" ] || continue
        pkt=$(python3 "$ROOT/.hermes/harness/task-packet.py" "$tasks" "$tid" worker 2>/dev/null || true)
        if printf '%s\n' "$pkt" | grep -q '^Analysis evidence'; then
          evid_n=$((evid_n + 1))
        fi
      done < <(
        # Task ids whose Findings line names at least one rule id.
        # Headings are #### T-ID: title (O-M3TYPED); tolerate ### too.
        awk '
          /^#{3,4} / {
            tid=$0
            sub(/^#{3,4}[[:space:]]*/, "", tid)
            sub(/:.*$/, "", tid)
            sub(/[[:space:]].*/, "", tid)
          }
          /\*\*Findings\*\*:/ && $0 !~ /\(none\)/ && $0 !~ /\*\*Findings\*\*:[[:space:]]*$/ {
            if (tid != "") print tid
          }
        ' "$tasks"
      )
    fi
    if [ "${evid_n:-0}" -gt 0 ] 2>/dev/null; then
      record "$story" K2 "$evid_n" "k2:evidence events"
    elif [ "${findings_n:-0}" -eq 0 ] 2>/dev/null; then
      record "$story" K2 1 "none-applicable (no Findings tasks)"
    fi
    # If Findings exist but no k2 events/packets → leave silent for check RED
  fi

  # ---- K3: adopt/defer — typed per-story (O-K3TYPED / F-k3-typed / W4-623) ----
  # Never grep -c roadmap prose. Counts = model.nm_decisions ∩ story findings.
  if [ "$(row_count "$story" K3 | tr -d '[:space:]')" = "0" ]; then
    local _k3py="${ROOT}/.hermes/harness/k3_evidence.py"
    [ -f "$_k3py" ] || _k3py="$(dirname "$0")/k3_evidence.py"
    if [ -f "$_k3py" ]; then
      local _k3line _k3n _k3note
      _k3line=$(python3 "$_k3py" --root "$ROOT" count --sid "$story" 2>/dev/null || true)
      _k3n=$(printf '%s\n' "$_k3line" | awk -F'\t' '{print $2}')
      _k3note=$(printf '%s\n' "$_k3line" | awk -F'\t' '{print $3}')
      _k3n=${_k3n:-0}
      if [ "${_k3n:-0}" -gt 0 ] 2>/dev/null; then
        record "$story" K3 "$_k3n" "${_k3note:-typed nm_decisions}"
      elif printf '%s\n' "$_k3note" | grep -q 'none-applicable'; then
        record "$story" K3 1 "none-applicable (no story-owned findings)"
      else
        # Findings owned but undecided — leave silent → check RED.
        :
      fi
    elif [ -f "$roadmap" ]; then
      # Pre-O-K3TYPED harness without k3_evidence.py — refuse false greens.
      echo "O-K3TYPED: missing k3_evidence.py — K3 heartbeat skipped (no roadmap grep)" >&2
    fi
  fi

  # ---- K9: discovered.md data row (heartbeat none if empty) ----
  if [ "$(row_count "$story" K9 | tr -d '[:space:]')" = "0" ]; then
    local disc_n=0
    if [ -f "$discovered" ]; then
      disc_n=$(grep -cE '^\| 20' "$discovered" 2>/dev/null || true); disc_n=${disc_n:-0}
    fi
    if [ "${disc_n:-0}" -gt 0 ] 2>/dev/null; then
      record "$story" K9 "$disc_n" "discovered.md data rows"
    else
      # Explicit none — channel watched, nothing found this story.
      if [ -f "$ROOT/.hermes/harness/append-discovered.py" ]; then
        ORACLE_ROOT="$ROOT" python3 "$ROOT/.hermes/harness/append-discovered.py" \
          "$story" "—" "(none this story)" >/dev/null 2>&1 || true
      else
        mkdir -p "$ROOT/migration"
        if [ ! -f "$discovered" ]; then
          cat > "$discovered" <<'EOF'
# Discovered work (K9)

Forward-looking scope intelligence — **not** sensor debt (`migration/debt.md`).
Workers append out-of-scope needs here instead of acting on them.

| when (UTC) | task | file/area | need |
|---|---|---|---|
EOF
        fi
        printf '| %s | %s | `—` | (none this story) |\n' \
          "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$story" >> "$discovered"
      fi
      record "$story" K9 1 "heartbeat none this story"
    fi
  fi

  # ---- K11: per-rule outcomes ----
  if [ "$(row_count "$story" K11 | tr -d '[:space:]')" = "0" ]; then
    local rule_n=0
    if [ -f "$EVENTS" ]; then
      rule_n=$(awk -F, '$4 ~ /^rule:/ {n++} END{print n+0}' "$EVENTS" 2>/dev/null || echo 0)
    fi
    if [ "${rule_n:-0}" -gt 0 ] 2>/dev/null; then
      record "$story" K11 "$rule_n" "rule: events in supervisor-events"
    else
      local findings_n=0
      if [ -n "$tasks" ] && [ -f "$tasks" ]; then
        findings_n=$(grep -ciE '\*\*Findings\*\*:' "$tasks" 2>/dev/null || true); findings_n=${findings_n:-0}
      fi
      if [ "${findings_n:-0}" -eq 0 ] 2>/dev/null; then
        # No Findings → emit explicit none so the ledger is walkable.
        if [ -f "$EVENTS" ] || mkdir -p "$(dirname "$EVENTS")" 2>/dev/null; then
          echo "$(date -u +%s),${story},0,rule:_none,story_complete" >> "$EVENTS" 2>/dev/null || true
        fi
        record "$story" K11 1 "none-no-findings (rule:_none)"
      fi
      # Findings present but zero rule: events → leave silent → RED
      # (record_rule_outcomes failed to fire — that is the defect).
    fi
  fi
}

check() { # story
  local story="$1"
  local sys missing=0
  init_ledger
  echo "O-EVIDLIVE check story=${story}"
  for sys in $ACTIVE_K; do
    local n
    n=$(row_count "$story" "$sys" | tr -d '[:space:]')
    n=${n:-0}
    if [ "$n" -lt 1 ] 2>/dev/null; then
      echo "RED:O-EVIDLIVE:silent ${sys} (0 rows for ${story})" >&2
      missing=$((missing + 1))
    else
      echo "OK ${sys} rows=${n}"
    fi
  done
  if [ "$missing" -gt 0 ]; then
    echo "RED:O-EVIDLIVE: ${missing} silent K-system(s) — story-gate refuse" >&2
    return 1
  fi
  echo "O-EVIDLIVE PASS (${story})"
  return 0
}

case "$cmd" in
  init) init_ledger; echo "ok:$LEDGER" ;;
  record)
    [ $# -ge 3 ] || { echo "usage: record <story> <K#> <rows> [note]" >&2; exit 2; }
    record "$@"
    ;;
  heartbeat)
    [ $# -ge 1 ] || { echo "usage: heartbeat <story>" >&2; exit 2; }
    heartbeat "$1"
    ;;
  check)
    [ $# -ge 1 ] || { echo "usage: check <story>" >&2; exit 2; }
    check "$1"
    ;;
  active)
    echo "$ACTIVE_K"
    ;;
  *)
    echo "usage: evidence-liveness.sh init|record|heartbeat|check|active" >&2
    exit 2
    ;;
esac
