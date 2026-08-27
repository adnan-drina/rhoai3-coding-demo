#!/usr/bin/env bash
# Install PATH name `specify` that points at specify-from-project.sh.
# dest-init also installs a copy under HERMES_MANAGED_DIR/bin / platform
# hermes/bin. dest-9 measured `/home/user/.local/bin` **first** on PATH, so
# that copy is shadowed. M2 must call specify-from-project.sh by path.
# Do not prepend HERMES_HOME/bin (Tirith retired).
#
# $2 / SPECIFY_REAL is required: the absolute uv specify-cli path. Baked
# into the shim so the helper never PATH-searches (Architect 153721ZA).
# A PATH search that rediscovers this shim is the dest-11 fork bomb.
set -euo pipefail
ROOT="$(cd "${1:-.}" && pwd)"
REAL_SPECIFY="${2:-${SPECIFY_REAL:-}}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HELPER="${SCRIPT_DIR}/specify-from-project.sh"
[[ -f "${HELPER}" ]] || {
  echo "install-specify-shim: missing ${HELPER}" >&2
  exit 1
}
[[ -n "${REAL_SPECIFY}" && -x "${REAL_SPECIFY}" ]] || {
  echo "install-specify-shim: SPECIFY_REAL must be an executable (got: ${REAL_SPECIFY:-unset})" >&2
  exit 1
}
if grep -qF "specify-from-project.sh" "${REAL_SPECIFY}" 2>/dev/null; then
  echo "install-specify-shim: SPECIFY_REAL is a wrapper, not specify-cli: ${REAL_SPECIFY}" >&2
  exit 1
fi
BIN="${ROOT}/.hermes/bin"
mkdir -p "${BIN}"
ROOT="${ROOT}" HELPER="${HELPER}" BIN="${BIN}" REAL_SPECIFY="${REAL_SPECIFY}" python3 - <<'PY'
import os
from pathlib import Path

root = os.environ["ROOT"]
helper = os.environ["HELPER"]
real = os.environ["REAL_SPECIFY"]
dest = Path(os.environ["BIN"]) / "specify"
dest.write_text(
    "#!/usr/bin/env bash\n"
    "export SPECIFY_REAL=%r\n"
    "exec bash %r --root %r \"$@\"\n" % (real, helper, root),
    encoding="utf-8",
)
dest.chmod(0o755)
print(f"OK: specify shim {dest} -> {helper} --root {root} SPECIFY_REAL={real}")
PY
