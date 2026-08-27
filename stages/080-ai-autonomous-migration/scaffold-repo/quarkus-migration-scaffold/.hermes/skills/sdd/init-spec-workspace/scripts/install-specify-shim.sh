#!/usr/bin/env bash
# Install PATH name `specify` that points at specify-from-project.sh.
# dest-init also installs a copy under HERMES_MANAGED_DIR/bin / platform
# hermes/bin. dest-9 measured `/home/user/.local/bin` **first** on PATH, so
# that copy is shadowed. M2 must call specify-from-project.sh by path.
# Do not prepend HERMES_HOME/bin (Tirith retired).
set -euo pipefail
ROOT="$(cd "${1:-.}" && pwd)"
# Absolute path of the REAL specify-cli, resolved by the caller. Baked into
# the shim as SPECIFY_REAL so the helper never PATH-searches — a search that
# can rediscover this very shim is what produced 1744 recursive helpers
# (Architect E-20260827T131720ZA). Optional: omitted, the helper falls back
# to its own wrapper-filtered PATH scan.
REAL_SPECIFY="${2:-${REAL_SPECIFY:-}}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HELPER="${SCRIPT_DIR}/specify-from-project.sh"
[[ -f "${HELPER}" ]] || {
  echo "install-specify-shim: missing ${HELPER}" >&2
  exit 1
}
if [[ -n "${REAL_SPECIFY}" ]]; then
  [[ -x "${REAL_SPECIFY}" ]] || {
    echo "install-specify-shim: REAL_SPECIFY not executable: ${REAL_SPECIFY}" >&2
    exit 1
  }
  # A wrapper baked in as SPECIFY_REAL would be a self-exec loop with no
  # PATH scan to filter it. Refuse it here, where it is cheap to catch.
  if grep -qF "specify-from-project.sh" "${REAL_SPECIFY}" 2>/dev/null; then
    echo "install-specify-shim: REAL_SPECIFY is a wrapper, not specify-cli: ${REAL_SPECIFY}" >&2
    exit 1
  fi
fi
BIN="${ROOT}/.hermes/bin"
mkdir -p "${BIN}"
# python for shell-safe paths (no eval)
ROOT="${ROOT}" HELPER="${HELPER}" BIN="${BIN}" REAL_SPECIFY="${REAL_SPECIFY}" python3 - <<'PY'
import os
from pathlib import Path

root = os.environ["ROOT"]
helper = os.environ["HELPER"]
real = os.environ.get("REAL_SPECIFY") or ""
dest = Path(os.environ["BIN"]) / "specify"
lines = ["#!/usr/bin/env bash\n"]
if real:
    lines.append("export SPECIFY_REAL=%r\n" % real)
lines.append("exec bash %r --root %r \"$@\"\n" % (helper, root))
dest.write_text("".join(lines), encoding="utf-8")
dest.chmod(0o755)
suffix = f" SPECIFY_REAL={real}" if real else " (no SPECIFY_REAL — helper will scan PATH)"
print(f"OK: specify shim {dest} -> {helper} --root {root}{suffix}")
PY
