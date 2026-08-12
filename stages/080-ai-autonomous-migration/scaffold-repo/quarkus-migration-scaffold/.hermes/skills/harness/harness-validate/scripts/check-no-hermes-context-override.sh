#!/usr/bin/env bash
# AD-001 / AD-002 invariant: Hermes project-context precedence is
# first-match-wins (.hermes.md → AGENTS.md → …). Either override file
# silently shadows AGENTS.md — fail if either name appears anywhere.
set -euo pipefail
root="$(cd "$(dirname "$0")/../../../.." && pwd)"
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
