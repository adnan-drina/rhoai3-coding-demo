#!/usr/bin/env bash
# spec-kit 0.16.1 Hermes integration resolves skills via Path.home()/.hermes/skills
# (spec-kit#3334 unmerged). Point that lookup at the project skills root so a
# worker shell `specify workflow run speckit` finds speckit-specify where
# init-spec-workspace seeded it — without the worker prefixing HOME=.
# HOME is set only for this child. Do not collapse profile HOME.
# Do not add user-root external_dirs. Do not widen K2_ALLOW_ROOT.
set -euo pipefail

_here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

_has_speckit() {
  [[ -f "${1}/.hermes/skills/speckit-specify/SKILL.md" ]]
}

ROOT=""
if [[ "${1:-}" == "--root" ]]; then
  ROOT="$(cd "${2:?--root needs a directory}" && pwd)"
  shift 2
fi
SPECIFY_ARGS=("$@")

if [[ -z "${ROOT}" ]]; then
  if [[ -n "${SPECIFY_PROJECT_ROOT:-}" ]]; then
    ROOT="$(cd "${SPECIFY_PROJECT_ROOT}" && pwd)"
  elif _has_speckit "$(pwd)"; then
    ROOT="$(pwd)"
  elif _has_speckit "/projects/modernized"; then
    ROOT="/projects/modernized"
  else
    d="$(pwd)"
    while [[ "${d}" != "/" ]]; do
      if _has_speckit "${d}"; then
        ROOT="${d}"
        break
      fi
      d="$(dirname "${d}")"
    done
  fi
fi

if [[ -z "${ROOT}" ]]; then
  echo "specify-from-project: no project skills root (missing .hermes/skills/speckit-specify)" >&2
  exit 1
fi





# Sole wrapper guard. dest-init bakes SPECIFY_REAL into the shim
# (E-20260827T153721ZA), so this PATH scan is the fallback path only.
# Detection is by CONTENT, not location: every shim we write execs
# specify-from-project.sh, so this catches them wherever they are installed
# — which the deleted path list could not (Architect 131720ZA: preferring
# the .platform copy produced 1744 concurrent helpers).
_is_wrapper() {
  local cand="$1"
  [[ -f "${cand}" ]] || return 1
  grep -qF "specify-from-project.sh" "${cand}" 2>/dev/null
}


_filtered_path=""
IFS=':' read -r -a _path_parts <<< "${PATH}"
for _p in "${_path_parts[@]}"; do
  [[ -z "${_p}" ]] && continue
  if _is_wrapper "${_p}/specify"; then
    continue
  fi
  if [[ -z "${_filtered_path}" ]]; then
    _filtered_path="${_p}"
  else
    _filtered_path="${_filtered_path}:${_p}"
  fi
done

REAL=""
if [[ -n "${SPECIFY_REAL:-}" ]]; then
  REAL="${SPECIFY_REAL}"
else
  REAL="$(PATH="${_filtered_path}" command -v specify || true)"
fi

if [[ -z "${REAL}" || ! -x "${REAL}" ]]; then
  echo "specify-from-project: specify not on PATH (after skipping shims)" >&2
  exit 1
fi
if [[ -z "${SPECIFY_REAL:-}" ]] && _is_wrapper "${REAL}"; then
  echo "specify-from-project: refusing wrapper ${REAL} (re-enters this script)" >&2
  exit 1
fi

export HOME="${ROOT}"
set +e
"${REAL}" "${SPECIFY_ARGS[@]}"
_rc=$?
set -e
python3 "${_here}/stamp-speckit-workflow-receipt.py" "${ROOT}" "${_rc}" \
  "${SPECIFY_ARGS[@]}"
exit "${_rc}"
