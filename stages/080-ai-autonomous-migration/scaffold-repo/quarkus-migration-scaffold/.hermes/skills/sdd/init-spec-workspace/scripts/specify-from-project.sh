#!/usr/bin/env bash
# spec-kit 0.16.1 Hermes integration resolves skills via Path.home()/.hermes/skills
# (spec-kit#3334 unmerged). Point that lookup at the project skills root so
# `specify workflow run speckit` finds speckit-specify where init-spec-workspace
# seeded it. Do not add user-root external_dirs. Do not widen K2_ALLOW_ROOT.
set -euo pipefail
ROOT="$(pwd)"
if [[ "${1:-}" == "--root" ]]; then
  ROOT="$(cd "${2:?--root needs a directory}" && pwd)"
  shift 2
fi
export HOME="${ROOT}"
command -v specify >/dev/null 2>&1 || {
  echo "specify-from-project: specify not on PATH" >&2
  exit 1
}
exec specify "$@"
