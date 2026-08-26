#!/usr/bin/env bash
# Install PATH name `specify` that points at specify-from-project.sh.
# dest-init also installs a copy under HERMES_MANAGED_DIR/bin / platform
# hermes/bin. dest-9 measured `/home/user/.local/bin` **first** on PATH, so
# that copy is shadowed. M2 must call specify-from-project.sh by path.
# Do not prepend HERMES_HOME/bin (Tirith retired).
set -euo pipefail
ROOT="$(cd "${1:-.}" && pwd)"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HELPER="${SCRIPT_DIR}/specify-from-project.sh"
[[ -f "${HELPER}" ]] || {
  echo "install-specify-shim: missing ${HELPER}" >&2
  exit 1
}
BIN="${ROOT}/.hermes/bin"
mkdir -p "${BIN}"
# python for shell-safe paths (no eval)
ROOT="${ROOT}" HELPER="${HELPER}" BIN="${BIN}" python3 - <<'PY'
import os
from pathlib import Path

root = os.environ["ROOT"]
helper = os.environ["HELPER"]
dest = Path(os.environ["BIN"]) / "specify"
text = (
    "#!/usr/bin/env bash\n"
    "exec bash %r --root %r \"$@\"\n" % (helper, root)
)
dest.write_text(text, encoding="utf-8")
dest.chmod(0o755)
print(f"OK: specify shim {dest} -> {helper} --root {root}")
PY
