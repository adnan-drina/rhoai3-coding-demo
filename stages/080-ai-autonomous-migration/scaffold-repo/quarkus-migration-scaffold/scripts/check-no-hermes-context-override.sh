#!/usr/bin/env bash
# AD-001 invariant: Hermes project-context precedence is first-match-wins
# (.hermes.md → AGENTS.md → …). Either override file silently shadows AGENTS.md.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
bad=0
for f in .hermes.md HERMES.md; do
  if [ -e "${root}/${f}" ]; then
    echo "FAIL: ${f} present at repo root — removes AGENTS.md from Hermes load order (AD-001)." >&2
    bad=1
  fi
done
if [ "${bad}" -ne 0 ]; then
  exit 1
fi
echo "OK: no .hermes.md / HERMES.md at scaffold root (AGENTS.md remains loadable)."
