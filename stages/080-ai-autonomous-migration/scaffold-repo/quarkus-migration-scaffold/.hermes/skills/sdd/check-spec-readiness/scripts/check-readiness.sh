#!/usr/bin/env bash
# check-spec-readiness skill — P0 pattern-steals + AD-S §S.6 (Architect E-20260808T061327Z): fail closed on
# unresolved Q-*, missing Non-Goals, incomplete task packets, waivers
# without re_open_trigger. Skips cleanly when no SDD artifacts exist yet.

usage() {
  cat <<'USAGE'
check-readiness.sh — check-spec-readiness gate (P0 pattern-steals + AD-S S.6).

Fails closed on: specs/briefs missing "## Non-Goals" or carrying unresolved
Q-* open questions; task packets missing ac_ids / files_in_scope / deps;
waivers without a checkable re_open_trigger. Then delegates to
check-ordering.py (AD-S S.6 identity / refuse worker re-plan / plan_revision)
and check-kanban-body.py (W2 S6.1 Kanban body vocabulary).

Arguments:
  none. The scaffold root is found by walking up to migration.yaml (SR-2).
  Scanned under that root:
    .specify/specs, specs, evidence/briefs, migration/specs (*.md)
    evidence/tasks, evidence/kanban (*.json)
    migration/waivers, migration/mta-exceptions (*.yaml|*.yml|*.json)

  -h, --help   print this usage and exit 0

Examples:
  bash .hermes/skills/sdd/check-spec-readiness/scripts/check-readiness.sh
  bash .hermes/skills/sdd/check-spec-readiness/scripts/check-readiness.sh --help

Exit codes:
  0  pass — readiness passed, or lint idle (no SDD specs/tasks/waivers yet)
  1  BLOCK — at least one FAIL: line on stderr, or a delegated check refused
  2  usage error (unexpected argument)
USAGE
}

case "${1:-}" in
  -h|--help)
    usage
    exit 0
    ;;
  "")
    ;;
  *)
    printf 'Error: this script takes no arguments. Received: "%s". Usage: %s [--help]\n' \
      "$1" "$(basename "$0")" >&2
    usage >&2
    exit 2
    ;;
esac

set -euo pipefail

# SR-2: walk up to migration.yaml — never a parent-count.
resolve_migration_root() {
  local d
  d="$(cd "$(dirname "$0")" && pwd)"
  while [ "$d" != "/" ]; do
    if [ -f "$d/migration.yaml" ]; then
      printf '%s\n' "$d"
      return 0
    fi
    d="$(dirname "$d")"
  done
  echo "cannot find project root (migration.yaml) walking up from $(dirname "$0") (SR-2)" >&2
  return 1
}
root="$(resolve_migration_root)" || exit 1
bad=0
checked=0

note() { echo "$*"; }
fail() { echo "FAIL: $*" >&2; bad=1; }

# --- specs / briefs: Non-Goals + open questions ---
spec_roots=()
for d in \
  "${root}/.specify/specs" \
  "${root}/specs" \
  "${root}/evidence/briefs" \
  "${root}/migration/specs"; do
  [ -d "${d}" ] && spec_roots+=("${d}")
done

shopt -s nullglob
spec_files=()
for d in "${spec_roots[@]+"${spec_roots[@]}"}"; do
  while IFS= read -r -d '' f; do
    spec_files+=("${f}")
  done < <(find "${d}" -type f \( -name '*.md' -o -name '*.markdown' \) -print0 2>/dev/null)
done

for f in "${spec_files[@]+"${spec_files[@]}"}"; do
  checked=$((checked + 1))
  rel="${f#"${root}"/}"
  if ! grep -Eqi '^#{1,3}[[:space:]]*Non-Goals' "${f}"; then
    fail "${rel}: missing ## Non-Goals (AD-S / P0)"
  fi
  # Unresolved checkbox questions: "- [ ] Q-123" or "- [ ] **Q-123**"
  if grep -Eqi '^[[:space:]]*-[[:space:]]*\[[[:space:]]\][[:space:]]*.*\bQ-[0-9]+' "${f}"; then
    fail "${rel}: unresolved open question checkbox (Q-*) blocks readiness"
  fi
  # Explicit status: open on a Q- line
  if grep -Eqi '\bQ-[0-9]+[^\n]*status:[[:space:]]*open|\bstatus:[[:space:]]*open[^\n]*\bQ-[0-9]+' "${f}"; then
    fail "${rel}: Q-* with status: open blocks readiness"
  fi
done

# --- task packets ---
task_files=()
for d in "${root}/evidence/tasks" "${root}/evidence/kanban"; do
  [ -d "${d}" ] || continue
  for f in "${d}"/*.json; do
    [ -f "${f}" ] && task_files+=("${f}")
  done
done

for f in "${task_files[@]+"${task_files[@]}"}"; do
  checked=$((checked + 1))
  rel="${f#"${root}"/}"
  if ! python3 - "${f}" <<'PY'
import json, sys
path = sys.argv[1]
try:
    data = json.load(open(path))
except Exception as e:
    print(f"unreadable JSON: {e}")
    sys.exit(2)
items = data if isinstance(data, list) else [data]
missing = []
for i, obj in enumerate(items):
    if not isinstance(obj, dict):
        missing.append(f"item[{i}] not object")
        continue
    def present(*keys):
        # Key must exist; empty list OK for deps / files_in_scope.
        return any(k in obj and obj[k] is not None and obj[k] != "" for k in keys)
    if not present("ac_ids", "acIds", "ac_id", "acId"):
        missing.append("ac_ids")
    if not present("files_in_scope", "filesInScope"):
        missing.append("files_in_scope")
    if not present("deps", "dependencies", "depends_on", "dependsOn"):
        missing.append("deps")
if missing:
    print(",".join(missing))
    sys.exit(1)
sys.exit(0)
PY
  then
    fail "${rel}: task packet missing required fields (ac_ids, files_in_scope, deps)"
  fi
done

# --- waivers / mta-exceptions ---
waiver_files=()
for d in "${root}/migration/waivers" "${root}/migration/mta-exceptions"; do
  [ -d "${d}" ] || continue
  for f in "${d}"/*; do
    [ -f "${f}" ] || continue
    case "${f}" in
      *.yaml|*.yml|*.json) waiver_files+=("${f}") ;;
    esac
  done
done

for f in "${waiver_files[@]+"${waiver_files[@]}"}"; do
  checked=$((checked + 1))
  rel="${f#"${root}"/}"
  if ! python3 - "${f}" <<'PY'
import json, sys, re
path = sys.argv[1]
raw = open(path).read()
if path.endswith(".json"):
    data = json.loads(raw)
    items = data if isinstance(data, list) else [data]
    for obj in items:
        trig = obj.get("re_open_trigger") or obj.get("reOpenTrigger") or ""
        if not str(trig).strip() or str(trig).strip().lower() == "skipped":
            sys.exit(1)
    sys.exit(0)
# minimal YAML: require a non-empty re_open_trigger: line that is not skipped
if not re.search(r'(?im)^re_open_trigger:\s*\S+', raw):
    sys.exit(1)
if re.search(r'(?im)^re_open_trigger:\s*["\']?skipped["\']?\s*$', raw):
    sys.exit(1)
sys.exit(0)
PY
  then
    fail "${rel}: waiver missing checkable re_open_trigger (not 'skipped')"
  fi
done

# --- AD-S §S.6 ordering (identity / refuse worker re-plan / plan_revision) ---
if ! python3 "$(cd "$(dirname "$0")" && pwd)/check-ordering.py" "${root}"; then
  bad=1
fi
# Count §S.6 toward "checked" only when it examined artifacts (script always runs).
checked=$((checked + 1))

# --- W2 §6.1 Kanban body vocabulary ---
if ! python3 "$(cd "$(dirname "$0")" && pwd)/check-kanban-body.py" "${root}"; then
  bad=1
fi
checked=$((checked + 1))

if [ "${checked}" -eq 0 ]; then
  note "OK: no SDD specs/tasks/waivers yet — readiness lint idle (P0 shapes documented under governance/contracts/)."
  exit 0
fi

if [ "${bad}" -ne 0 ]; then
  echo "SDD readiness FAILED (${checked} artifact(s) checked)." >&2
  exit 1
fi
note "OK: SDD readiness passed (${checked} artifact(s) checked)."
