#!/usr/bin/env bash
# Typed negatives for ensure_cli:
#   1) CLI="$(ensure_cli)" must be one executable path (v30 helper-stdout poison).
#   2) A present kantra next to a non-executable runnable sibling is NOT accepted
#      (capability probe; `[ -x kantra ]` is not usability).
set -euo pipefail
case "${1:-}" in
  -h|--help)
    cat <<'USAGE'
assert-ensure-cli-path.sh — cached kantra ensure_cli must print one path,
and a tree with a non-executable runnable sibling must be rejected.

Runs a temp-tree probe (no cluster). Exit 0 only after the gate assertions.
Do not treat --help as a PASS.

Usage:
  bash assert-ensure-cli-path.sh
  bash assert-ensure-cli-path.sh --help
USAGE
    exit 0
    ;;
esac
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKDIR="$(mktemp -d)"
trap 'rm -rf "${WORKDIR}"' EXIT

# Observe-only checker: same ELF/shebang property as dest-init, but never chmod.
# A writable tree would be repaired by the live helper; this proves ensure_cli
# does not accept when the checker fails.
install_observe_checker() {
  local dest="$1"
  cat >"${dest}" <<'PY'
#!/usr/bin/env python3
import os, sys
root = sys.argv[1] if len(sys.argv) > 1 else sys.exit(2)
seen, bad, unwalkable = 0, [], []
for dirpath, _, filenames in os.walk(root, onerror=lambda e: unwalkable.append(
        getattr(e, "filename", None) or str(e))):
    for name in filenames:
        path = os.path.join(dirpath, name)
        if os.path.islink(path):
            continue
        try:
            with open(path, "rb") as fh:
                head = fh.read(4)
        except OSError:
            bad.append(path)
            continue
        if head != b"\x7fELF" and head[:2] != b"#!":
            continue
        seen += 1
        if not os.access(path, os.X_OK):
            bad.append(path)
if unwalkable:
    sys.stderr.write("kantra-assert-exec: unwalkable %s\n" % unwalkable)
    sys.exit(1)
if not seen:
    sys.stderr.write("kantra-assert-exec: no runnable files under %s\n" % root)
    sys.exit(1)
if bad:
    sys.stderr.write("kantra-assert-exec: not executable: %s\n" % bad[:5])
    sys.exit(1)
PY
  chmod +x "${dest}"
}

write_shebang() {
  local path="$1" mode="$2"
  printf '%s\n' '#!/bin/sh' 'echo fake-kantra' >"${path}"
  chmod "${mode}" "${path}"
}

PYDIR="$(dirname "$(command -v python3)")"
HUMAN_HOME="${WORKDIR}/home"
KANTRA_HOME="${WORKDIR}/kantra"
mkdir -p "${HUMAN_HOME}/.local/bin" "${KANTRA_HOME}" "${WORKDIR}/bin"
install_observe_checker "${HUMAN_HOME}/.local/bin/kantra-assert-exec"

# Isolate PATH so a host kantra cannot satisfy the probe.
export HUMAN_HOME KANTRA_HOME ENSURE_CLI_LIB=1
export PATH="${HUMAN_HOME}/.local/bin:${WORKDIR}/bin:${PYDIR}:/usr/bin:/bin"

# shellcheck source=mta-analyze-legacy.sh
source "${ROOT}/mta-analyze-legacy.sh"

# --- (1) cached usable tree: stdout is exactly the binary path ---
write_shebang "${KANTRA_HOME}/kantra" 755
write_shebang "${KANTRA_HOME}/java-external-provider" 755
CLI="$(ensure_cli)"
case "${CLI}" in
  *$'\n'*)
    echo "FAIL: cached ensure_cli captured a newline: $(printf %q "${CLI}")" >&2
    exit 1
    ;;
esac
[ -x "${CLI}" ] || {
  echo "FAIL: cached ensure_cli is not executable: $(printf %q "${CLI}")" >&2
  exit 1
}
[ "${CLI}" = "${KANTRA_HOME}/kantra" ] || {
  echo "FAIL: cached ensure_cli path mismatch: $(printf %q "${CLI}")" >&2
  exit 1
}

# --- (2) present-but-unusable sibling must NOT be accepted ---
chmod 644 "${KANTRA_HOME}/java-external-provider"
if CLI_BAD="$(ensure_cli)" 2>/dev/null; then
  echo "FAIL: unusable sibling was accepted: $(printf %q "${CLI_BAD}")" >&2
  exit 1
fi

# --- (3) helper stdout discard, then a usable tree ---
rm -f "${KANTRA_HOME}/kantra" "${KANTRA_HOME}/java-external-provider"
cat >"${HUMAN_HOME}/.local/bin/kantra-ensure" <<EOF
#!/bin/sh
echo "Downloading kantra v0.10.0-beta.1 (~690MB, once per workspace)..."
echo "kantra ready: ${KANTRA_HOME}/kantra"
mkdir -p "${KANTRA_HOME}"
printf '%s\n' '#!/bin/sh' 'echo fake-kantra' >"${KANTRA_HOME}/kantra"
printf '%s\n' '#!/bin/sh' 'echo fake-provider' >"${KANTRA_HOME}/java-external-provider"
chmod 755 "${KANTRA_HOME}/kantra" "${KANTRA_HOME}/java-external-provider"
EOF
chmod +x "${HUMAN_HOME}/.local/bin/kantra-ensure"
CLI2="$(ensure_cli)"
case "${CLI2}" in
  *$'\n'*)
    echo "FAIL: post-helper ensure_cli captured a newline: $(printf %q "${CLI2}")" >&2
    exit 1
    ;;
esac
[ "${CLI2}" = "${KANTRA_HOME}/kantra" ] || {
  echo "FAIL: post-helper path mismatch: $(printf %q "${CLI2}")" >&2
  exit 1
}

echo "OK: ensure_cli stdout is a single executable path; unusable sibling rejected"
: "${ROOT}"
