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
      findings_n=$(grep -ciE '\*\*Findings\*\*:' "$tasks" 2>/dev/null || true); findings_n=${findings_n:-0}
    fi
    if [ -f "$EVENTS" ]; then
      evid_n=$(grep -cE ',k2:evidence,' "$EVENTS" 2>/dev/null || true); evid_n=${evid_n:-0}
    fi
    if [ "${evid_n:-0}" -gt 0 ] 2>/dev/null; then
      record "$story" K2 "$evid_n" "k2:evidence events"
    elif [ "${findings_n:-0}" -eq 0 ] 2>/dev/null; then
      record "$story" K2 1 "none-applicable (no Findings tasks)"
    fi
    # If Findings exist but no k2 events → leave silent for check RED
  fi

  # ---- K3: adopt/defer decisions in roadmap ----
  if [ "$(row_count "$story" K3 | tr -d '[:space:]')" = "0" ]; then
    if [ -f "$roadmap" ]; then
      local k3n
      # Decision forms only — not prose that merely mentions adopt/defer.
      k3n=$(grep -cE '(: defer|: adopt|defer \([^\)]+\)|: *defer|: *adopt)' "$roadmap" 2>/dev/null || true); k3n=${k3n:-0}
      if [ "${k3n:-0}" -gt 0 ] 2>/dev/null; then
        record "$story" K3 "$k3n" "roadmap adopt/defer present"
      else
        # Roadmap exists but no decisions — still record that K3 ran empty?
        # Charter: ≥1 row OR RED. Empty decisions on a roadmap that claims
        # inventory is a real defect → leave silent → RED.
        :
      fi
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
