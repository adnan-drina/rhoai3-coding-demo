#!/usr/bin/env bash
# AD-001 / AD-002 invariant: Hermes project-context precedence is
# first-match-wins (.hermes.md → AGENTS.md → …). Either override file
# silently shadows AGENTS.md — fail if either name appears anywhere.

usage() {
  cat <<'USAGE'
check-no-hermes-context-override.sh — AD-001 / AD-002 project-context invariant.

Hermes loads project context first-match-wins (.hermes.md -> AGENTS.md -> ...),
so a .hermes.md or HERMES.md file anywhere in the scaffold tree silently
removes AGENTS.md from the load order. This check refuses either name.

Arguments:
  none. The scaffold root is found by walking up to migration.yaml (SR-2);
  target/ subtrees are excluded from the scan.

  -h, --help   print this usage and exit 0

Examples:
  bash .hermes/skills/harness/validate-contracts/scripts/check-no-hermes-context-override.sh
  bash .hermes/skills/harness/validate-contracts/scripts/check-no-hermes-context-override.sh --help

Exit codes:
  0  pass — no .hermes.md / HERMES.md in the scaffold tree
  1  BLOCK — at least one override file found (one FAIL: line per file, stderr)
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
while IFS= read -r -d '' f; do
  echo "FAIL: ${f#"${root}"/} — removes AGENTS.md from Hermes load order (AD-002)." >&2
  bad=1
done < <(find "${root}" \( -name '.hermes.md' -o -name 'HERMES.md' \) \
  -not -path '*/target/*' -print0 2>/dev/null)
if [ "${bad}" -ne 0 ]; then
  exit 1
fi
echo "OK: no .hermes.md / HERMES.md in scaffold tree (AGENTS.md remains loadable)."
