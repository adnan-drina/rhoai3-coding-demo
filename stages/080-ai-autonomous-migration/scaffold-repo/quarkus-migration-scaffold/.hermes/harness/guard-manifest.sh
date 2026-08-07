#!/usr/bin/env bash
# O-GUARDMANIFEST (ARCH-B2) — generated harness guard coverage manifest.
#
# Declares which guard is enforced at which stage by which mechanism, and
# which verification tier proves it (L1 fixture / L2 corpus / L3 live).
# Same shape as defaults-inventory: generate artefact + --check seed rows.
# Bank retest-owed rows should cite this file (not prose-only greps).
#
# Usage:
#   bash .hermes/harness/guard-manifest.sh
#   bash .hermes/harness/guard-manifest.sh --check
set -euo pipefail

HARNESS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="${HARNESS_DIR}/guard-manifest.md"
LINT="${HARNESS_DIR}/plan-lint.py"
SUP="${HARNESS_DIR}/supervisor.sh"
OUTER="${HARNESS_DIR}/outer-loop.sh"
CHECK=0
[ "${1:-}" = "--check" ] && CHECK=1

_grepn() {
  grep -nE "$1" "$2" 2>/dev/null || true
}

# Seed table rows that must remain in the artefact (coverage contract).
# W4-254: SEED_IDS is the coverage contract — new load-bearing guards must
# be added here *and* in the seed table below, or --check / row counts lie.
SEED_IDS=(
  'O-INFERABSENT'
  'O-ORACLEDERIVE'
  'roadmap-lint'
  'O-PORTDERIVE'
  'O-STORYKIND'
  'O-SEATBUDGET'
  'O-SPECREIMPL'
  'O-PLANCORPUS'
  'O-EXECCORPUS'
  'O-EVIDLIVE'
  'O-SFIXNODELTA'
  'O-HERMESPREFLIGHT'
  'O-DEFAULTAUDIT'
  'O-M3SHAPEHARD'
  'O-DEBTFRZ'
  'O-GUARDMANIFEST'
  'O-M3PREFLIGHT'
  'O-BRIEFCONTRACT'
  'O-BRIEFQCONT'
  'O-BRIEFQUALITY'
  'O-M1SCC'
  'O-DEPCHAIN'
  'O-M3PIPEFIELD'
  'O-STOPAFTERM2'
  'O-STOPAFTERM1'
  # W4 continue-residuals / R3 discovery — restart-critical M4 guards
  'O-EXECSCOPE'
  'O-RUNLOGTERM'
  'O-CHARPROTECT'
  'O-T6DM4STRUCT'
  'O-CHARSONAR'
  'O-OWNSTAGEALL'
  'O-ATTRSWEEP'
  'O-PARTIALADV'
  'O-VERIFYCREATE'
  'O-SYNTHROUTE'
  'O-DEBTFRZLEDGER'
  'O-PROFILE7GAP'
  'O-NOSPECIMEN'
  'O-STAMPGITIGN'
  'O-HERMNESTTIP'
)

# O-GUARDDISC / R3 (W4-292): harvest instrumented O-* from core files and
# append any missing rows so SEED_IDS lag cannot hide live guards.
# Canary: O-PROFILE7GAP must appear after discovery (was missing until named).
discover_instrumented_ids() {
  local inst="${HARNESS_DIR}/tests/instruments.sh" src
  [ -f "$inst" ] || return 0
  local -a cores=(
    "$SUP" "$LINT" "$OUTER"
    "${HARNESS_DIR}/profile-rubric.py"
    "${HARNESS_DIR}/m2-compose.py"
    "${HARNESS_DIR}/mechan-match.py"
    "${HARNESS_DIR}/char-protect.py"
    "${HARNESS_DIR}/exec-scope.py"
    "${HARNESS_DIR}/roadmap-lint.py"
  )
  for src in "${cores[@]}"; do
    [ -f "$src" ] || continue
    # Min length 5 after O- avoids O-AC / O-T6 fragments.
    grep -ohE 'O-[A-Z][A-Z0-9]{4,}' "$src" 2>/dev/null || true
  done | sort -u | while IFS= read -r id; do
    [ -n "$id" ] || continue
    grep -q "$id" "$inst" 2>/dev/null || continue
    printf '%s\n' "$id"
  done
}

append_discovered_rows() {
  local f="$1" id n=0
  {
    echo
    echo "### Auto-discovered instrumented guards (O-GUARDDISC / R3)"
    echo
    echo "| Guard ID | Stage | Mechanism | Verification | Site / proof |"
    echo "|----------|-------|-----------|--------------|--------------|"
    while IFS= read -r id; do
      [ -n "$id" ] || continue
      grep -qE "\\| *${id} *\\|" "$f" && continue
      echo "| ${id} | auto | discovered | L1 | auto-row core+instruments (O-GUARDDISC) |"
      n=$((n + 1))
    done < <(discover_instrumented_ids)
    echo
    echo "_O-GUARDDISC auto-rows appended: ${n}_"
  } >> "$f"
}

assert_seed_rows() {
  local f="$1" needle
  for needle in "${SEED_IDS[@]}"; do
    grep -q "$needle" "$f" || {
      echo "O-GUARDMANIFEST: artefact missing seed row: $needle" >&2
      return 1
    }
  done
  # Require stage × mechanism × verification columns present
  grep -qE '\| *Stage *\|' "$f" || {
    echo "O-GUARDMANIFEST: missing Stage column header" >&2
    return 1
  }
  grep -qE '\| *Mechanism *\|' "$f" || {
    echo "O-GUARDMANIFEST: missing Mechanism column header" >&2
    return 1
  }
  grep -qE '\| *Verification *\|' "$f" || {
    echo "O-GUARDMANIFEST: missing Verification column header" >&2
    return 1
  }
  # At least one L1 / L2 / L3 marker in the seed table body
  local l1 l2 l3
  l1=$(grep -cE '\| L1' "$f" || true)
  l2=$(grep -cE '\| L2' "$f" || true)
  l3=$(grep -cE '\| L3' "$f" || true)
  if [ "${l1:-0}" -lt 1 ] || [ "${l2:-0}" -lt 1 ] || [ "${l3:-0}" -lt 1 ]; then
    echo "O-GUARDMANIFEST: need ≥1 L1, L2, and L3 verification rows (L1=$l1 L2=$l2 L3=$l3)" >&2
    return 1
  fi
  # R3 canary — PROFILE7GAP must be present (seed or auto-discovered).
  grep -qE '\| *O-PROFILE7GAP *\|' "$f" || {
    echo "O-GUARDMANIFEST: R3 canary O-PROFILE7GAP missing from artefact" >&2
    return 1
  }
  grep -q 'O-GUARDDISC' "$f" || {
    echo "O-GUARDMANIFEST: missing O-GUARDDISC auto-discovery section" >&2
    return 1
  }
  return 0
}

assert_fence_harvest() {
  local f="$1"
  local n
  n=$(awk '
    /^### harness O-\* \/ guard markers/ { sec=1; next }
    sec && /^```$/ { if (in_fence) { exit } in_fence=1; next }
    sec && in_fence { print }
  ' "$f" | grep -cE '^[0-9]+:' || true)
  if [ "${n:-0}" -lt 1 ]; then
    echo "O-GUARDMANIFEST: empty fence harvest (hits=${n:-0}) — refuse GREEN" >&2
    return 1
  fi
  return 0
}

tmp="$(mktemp)"
{
  cat <<'EOF'
# Harness guard manifest (O-GUARDMANIFEST / ARCH-B2)

**Purpose:** make guard coverage **computable** — each guard declares
`stage` × `mechanism` × `verification` so "is this guard live?" and
"how much of the set is verified?" are not answered by ad-hoc regex
greps of the bank.

Generated by `guard-manifest.sh`. Re-run after adding/removing guards.
Bank **retest-owed** rows should point here (column `Verification` +
instrument / corpus id) instead of prose-only claims.

| Verification | Meaning |
|--------------|---------|
| L1 | Fixture / instrument in `tests/instruments.sh` (or host gate instruments) |
| L2 | Corpus replay (`plan-corpus-lint` / `exec-corpus-lint` / similar) |
| L3 | Live run evidence (pod outer/supervisor / archived run) |

| Guard ID | Stage | Mechanism | Verification | Site / proof |
|----------|-------|-----------|--------------|--------------|
| roadmap-lint (O-M2*) | M2 | lint | L1 | `roadmap-lint.py` + instruments roadmap-lint\* |
| O-PORTDERIVE | M2/M3 | lint | L1 | roadmap-lint REDESIGN brief contract + plan-lint §7→Port; instruments portderive\* |
| O-STORYKIND | M2 | lint | L1 | roadmap-lint `kind:` rename\|reimplement\|mixed; instruments storykind\* |
| O-SEATBUDGET | M2/M4 | lint+supervisor | L1 | kind×incidents seat-budget in roadmap/brief/banner; overrun debt-freeze; instruments seatbudget\* |
| O-SPECREIMPL | M3 | lint | L1 | plan-lint sibling spec.md→Port: reimplement; instruments specreimpl\* |
| O-PLANCORPUS | M3 | lint | L1+L2 | `plan-corpus-lint.sh` + fixtures; host `v10-plan-corpus-gate.sh` |
| O-M3SHAPEHARD | M3 | lint | L1 | `PLAN_LINT_REQUIRE_SHAPE` hard default in `plan-lint.py` |
| O-INFERABSENT | M3/M4 | lint+supervisor | L1 | plan-lint LINT tier + supervisor skip-worker; instruments inferabsent\* |
| O-ORACLEDERIVE | M4 | packet+supervisor | L1 | `oracle_derive.py` + task-packet Oracle; instruments oraclederive\* |
| O-SFIXNODELTA | M4 | supervisor | L1+L2 | `sfix_nodelta_skip` in supervisor; exec-corpus `s03-t004-sfixnodelta` |
| O-EXECCORPUS | M4 | lint | L2 | `exec-corpus-lint.sh` + fixtures; host `v10-exec-corpus-gate.sh` |
| O-DEBTFRZ | M4/M5 | supervisor | L3 | `record_debt` → debt-freeze / story stop (live) |
| O-EVIDLIVE | M5 | sensor/gate | L1 | `evidence-liveness.sh` + story-gate hook; instruments evidlive\* |
| O-HERMESPREFLIGHT | preflight | host-gate | L1 | `v10-hermes-parity.sh` in `v9-preflight-outer-start.sh` |
| O-GOLDENFRESH | preflight | host-gate | L1 | `v10-golden-fresh.sh` publish-fp + 3-way; instruments goldenfresh\* |
| O-DEFAULTAUDIT | meta | inventory | L1 | `defaults-inventory.sh --check`; instruments defaultaudit/defaultrg |
| O-GUARDMANIFEST | meta | inventory | L1 | this file + `guard-manifest.sh --check`; instrument guardmanifest-ok |
| O-M3PREFLIGHT | M3 | outer-loop | L1 | `roadmap-lint --story` before M3 seats; instruments m3preflight\* |
| O-BRIEFCONTRACT | M2 | lint+compose | L1 | per-class §7 paste; instruments briefcontract\* |
| O-BRIEFQCONT | M2 | lint | L1 | contracts dim = dedicated/required; instrument briefqcont-family-ok |
| O-BRIEFQUALITY | M2/M3 | lint+outer | L1 | composite score + M2-exit / --story floor; instruments briefquality\* |
| O-M1SCC | M1 | analyze | L1 | Tarjan SCCs in `dependency-order.py`; instrument m1scc-ok |
| O-DEPCHAIN | M2 | compose | L1 | `derive_story_depends` real earlier-story edges; instrument depchain-wire-ok |
| O-M3PIPEFIELD | M3 | lint | L1+L2 | `normalize_m3_pipe_fields`; plan-corpus `s02-pipefield-synth` |
| O-STOPAFTERM2 | M2 | outer-loop | L1 | `STOP_AFTER_M2=1` exits after M2 GREEN (validation runs) |
| O-STOPAFTERM1 | M1 | outer-loop | L1 | `STOP_AFTER_M1=1` exits after M1 ANALYZE+PROFILE GREEN (validation before M2) |
| O-EXECSCOPE | M4 | supervisor | L1 | `exec-scope.py` + scope_enforce (C); instrument execscope-wire-ok |
| O-RUNLOGTERM | M4 | supervisor | L1 | `append_harness_runlog` / `task_tip_landed`; instrument runlogterm-wire-ok |
| O-CHARPROTECT | M3/M4 | lint+supervisor | L1 | plan-lint + `char-protect.py`; instrument charprotect-red-ok |
| O-T6DM4STRUCT | M4 | mechan-match | L1 | Shape=structure skip need-src-test; instrument t6dm4struct-ok |
| O-CHARSONAR | M4 | supervisor | L1 | force milestone sensor for char tips; instrument charsonar-wire-ok |
| O-OWNSTAGEALL | M4 | supervisor | L1 | multi-line Target stage + refuse partial; instrument ownstageall-wire-ok |
| O-ATTRSWEEP | M4 | supervisor | L1 | Shape=verify empty allowlist no git add -A; with ownstageall |
| O-PARTIALADV | M4/M5 | supervisor | L1 | `partial_adv_blockers` debt-freeze; with ownstageall |
| O-VERIFYCREATE | M3 | lint | L1 | plan-lint Shape=verify create Target; with ownstageall |
| O-SYNTHROUTE | M4 | supervisor | L1 | undetermined → MiniMax-first; with ownstageall |
| O-DEBTFRZLEDGER | M5 | supervisor | L1 | M5 residuals → debt.md; with ownstageall |
| O-PROFILE7GAP | M2 | lint | L1 | `profile-rubric.py` sec7-cover; instrument profile7gap-red-ok (R3 canary) |
| O-NOSPECIMEN | meta | lint | L1 | no specimen fail-open defaults in harness .py; instruments nospecimen* |
| O-STAMPGITIGN | M4 | supervisor | L1 | stage reset + scaffold gitignore; instrument stampgitign-wire-ok |
| O-HERMNESTTIP | M4 | supervisor | L1 | ESCNOCOMMIT HERMNEST ancestor; instrument hermnesttip-wire-ok |

## Retest-owed pointer

When a bank row is ✅ with **retest-owed**, cite:
`guard-manifest.md` → Guard ID → Verification tier still owed (usually L2
or L3). Do not treat L1-only as full discharge for corpus/live classes.

## Grep harvest (review)

EOF

  echo "### harness O-* / guard markers (plan-lint + supervisor + outer sample)"
  echo '```'
  {
    _grepn 'O-INFERABSENT|O-ORACLEDERIVE|O-SFIXNODELTA|O-EVIDLIVE|O-DEBTFRZ|O-M3PIPEFIELD|PLAN_LINT_REQUIRE_SHAPE|sfix_nodelta_skip|evidence_liveness' "$LINT"
    _grepn 'O-INFERABSENT|O-ORACLEDERIVE|O-SFIXNODELTA|O-EVIDLIVE|O-DEBTFRZ|sfix_nodelta_skip|evidence_liveness|record_debt|O-EXECSCOPE|O-RUNLOGTERM|O-CHARPROTECT|O-T6DM4STRUCT|O-CHARSONAR|O-OWNSTAGEALL' "$SUP"
    if [ -f "$OUTER" ]; then
      _grepn 'O-M3PREFLIGHT|O-STOPAFTERM2|O-STOPAFTERM1|m2_brief_quality_exit|O-BRIEFQUALITY|roadmap-lint|O-EVIDLIVE|record_debt' "$OUTER"
    fi
    RL="${HARNESS_DIR}/roadmap-lint.py"
    DO="${HARNESS_DIR}/dependency-order.py"
    M2C="${HARNESS_DIR}/m2-compose.py"
    [ -f "$RL" ] && _grepn 'O-BRIEFQCONT|O-BRIEFCONTRACT|O-BRIEFQUALITY|O-M3PREFLIGHT' "$RL"
    [ -f "$DO" ] && _grepn 'O-M1SCC|Tarjan|strongly_connected' "$DO"
    [ -f "$M2C" ] && _grepn 'O-DEPCHAIN|derive_story_depends|O-BRIEFQCONT' "$M2C"
  } | head -120
  echo '```'
  echo
  cat <<'EOF'
## Classification guide

- **Stage:** M2 sequence / M3 specify / M4 task-batch / M5 evaluate-ship /
  preflight / meta (inventory of the harness itself).
- **Mechanism:** lint · sensor · packet · skill-doc · supervisor ·
  host-gate · inventory.
- **Verification:** L1 fixture · L2 corpus · L3 live (stack with `+`).

Coverage math (rough): count seed rows with L2 or L3 vs L1-only. Gaps
are the Wave4 ARCH verification asymmetry — not greppable from the bank
alone.

EOF
  echo "_Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)_"
} > "$tmp"

# O-GUARDDISC: append instrumented guards not already named in SEED table.
append_discovered_rows "$tmp"

assert_seed_rows "$tmp" || {
  rm -f "$tmp"
  exit 1
}
assert_fence_harvest "$tmp" || {
  rm -f "$tmp"
  exit 1
}

if [ "$CHECK" = "1" ]; then
  if [ ! -f "$OUT" ]; then
    echo "O-GUARDMANIFEST: missing $OUT — run without --check to generate" >&2
    rm -f "$tmp"
    exit 1
  fi
  assert_seed_rows "$OUT" || {
    rm -f "$tmp"
    exit 1
  }
  assert_fence_harvest "$OUT" || {
    rm -f "$tmp"
    exit 1
  }
  echo "O-GUARDMANIFEST: artefact seed rows OK ($OUT)"
  rm -f "$tmp"
  exit 0
fi

mv "$tmp" "$OUT"
echo "O-GUARDMANIFEST: wrote $OUT"
l1=$(grep -cE '\| L1' "$OUT" || true)
l2=$(grep -cE '\| L2' "$OUT" || true)
l3=$(grep -cE '\| L3' "$OUT" || true)
echo "O-GUARDMANIFEST: verification markers L1≈$l1 L2≈$l2 L3≈$l3"
exit 0
