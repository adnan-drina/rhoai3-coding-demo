#!/usr/bin/env bash
# O-KANTRAPATH (W3-99/W3-145): resolve kantra outside /tmp so pod restarts
# do not wipe the ~690MB binary. Prefer workspace PVC; keep /tmp as fallback.
# shellcheck disable=SC2034
KANTRA_HOME="${KANTRA_HOME:-/projects/.tools/kantra}"
KANTRA_OUT_BASE="${KANTRA_OUT_BASE:-/tmp}"

kantra_bin() {
  local c
  for c in \
    "${KANTRA_HOME}/kantra" \
    /projects/.tools/kantra/kantra \
    "${HOME}/.local/share/kantra/kantra" \
    /tmp/kantra/kantra
  do
    if [ -x "$c" ] || [ -f "$c" ]; then
      printf '%s\n' "$c"
      return 0
    fi
  done
  return 1
}
