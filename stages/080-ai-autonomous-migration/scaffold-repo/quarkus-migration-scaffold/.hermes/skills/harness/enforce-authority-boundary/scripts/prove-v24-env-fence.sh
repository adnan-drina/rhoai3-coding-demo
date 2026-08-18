#!/usr/bin/env bash
# Scratch HERMES_HOME proof for v24 items 1+2. No dest. Minutes.
# Assert: fence resolves from env; DENIES when env unset; dest JSON is
# ignored; spawn-hydrate cache task_id agrees with HERMES_KANBAN_TASK.
set -euo pipefail
if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  cat <<'USAGE'
prove-v24-env-fence.sh — scratch proof that write-set-hook.py takes policy
from HERMES_KANBAN_FILES_WRITABLE only. Dest write-set JSON is ignored.
No dest, no cluster. Prints usage on --help; does not print a gate verdict.
USAGE
  exit 0
fi
HERE="$(cd "$(dirname "$0")" && pwd)"
HOOK="${HERE}/write-set-hook.py"
EMIT="${HERE}/emit-write-set-cache.py"
HYDRATE="${HERE}/hermes-spawn-hydrate.py"
python3 -m py_compile "${HOOK}" "${EMIT}" "${HYDRATE}"
scratch="$(mktemp -d "${TMPDIR:-/tmp}/v24-env-fence.XXXXXX")"
cleanup() { cd /tmp; rm -rf "${scratch}"; }
trap cleanup EXIT
export HERMES_WRITE_SAFE_ROOT="${scratch}"
mkdir -p "${scratch}/src/main/java/com/demo" \
  "${scratch}/evidence/bodies" \
  "${scratch}/evidence/runtime/write-sets"
cd "${scratch}"
printf '%s\n' '{"identity":{"story_id":"setup"},"task_id":"setup","files_writable":["pom.xml","src/main/resources/application.properties"]}' \
  > "${scratch}/evidence/bodies/m3-setup.json"
# Poison dest cache: would allow everything if the fence still trusted dest.
printf '%s\n' '{"task_id":"t_deadbeef","files_writable":["pom.xml","src/hack.java"]}' \
  > "${scratch}/evidence/runtime/write-sets/t_deadbeef.json"

hook() {
  printf '%s\n' "$1" | python3 "${HOOK}" >/dev/null
}

echo "== dest JSON must not be policy =="
export HERMES_KANBAN_TASK=t_deadbeef
unset HERMES_KANBAN_FILES_WRITABLE || true
if hook '{"tool_name":"write_file","tool_input":{"path":"pom.xml"}}'; then
  echo "FAIL: dest cache must not allow pom.xml when env unset" >&2
  exit 1
fi
echo "OK: fence DENIES when TASK set and FILES_WRITABLE unset (ignores dest cache)"

echo "== env resolve =="
export HERMES_KANBAN_FILES_WRITABLE='["src/main/java/com/demo/Ok.java"]'
if hook '{"tool_name":"write_file","tool_input":{"path":"pom.xml"}}'; then
  echo "FAIL: env write-set should refuse pom.xml" >&2
  exit 1
fi
if ! hook '{"tool_name":"write_file","tool_input":{"path":"src/main/java/com/demo/Ok.java"}}'; then
  echo "FAIL: env write-set should allow in-set src" >&2
  exit 1
fi
echo "OK: fence resolves files_writable from spawn env"

echo "== env/body id agree via cache hygiene (not fence logic) =="
python3 "${EMIT}" --root "${scratch}" --task-id t_cafeba --body evidence/bodies/m3-setup.json
python3 - <<PY
import json
from pathlib import Path
root = Path("${scratch}")
cache = json.loads((root / "evidence/runtime/write-sets/t_cafeba.json").read_text())
body = json.loads((root / "evidence/bodies/m3-setup.json").read_text())
assert cache["task_id"] == "t_cafeba", cache
assert cache["authority"] == "cache-not-policy", cache
assert "pom.xml" in cache["files_writable"], cache
# Body story slug stays identity; native id is env/cache t_<hex>.
assert body.get("task_id") == "setup", body
print("OK: cache task_id is Hermes t_<hex>; body story slug unchanged")
PY

echo "== spawn hydrate copies cache into env; fence still never opens dest for a different task =="
export HERMES_KANBAN_TASK=t_cafeba
unset HERMES_KANBAN_FILES_WRITABLE || true
python3 - <<PY
import json, os, sys
from pathlib import Path
import importlib.util
os.environ["HERMES_KANBAN_TASK"] = "t_cafeba"
os.environ.pop("HERMES_KANBAN_FILES_WRITABLE", None)
os.environ["HERMES_WRITE_SAFE_ROOT"] = "${scratch}"
spec = importlib.util.spec_from_file_location("hydrate", "${HYDRATE}")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
mod.hydrate()
fw = json.loads(os.environ["HERMES_KANBAN_FILES_WRITABLE"])
assert fw == ["pom.xml", "src/main/resources/application.properties"], fw
assert os.environ["HERMES_KANBAN_TASK"] == "t_cafeba"
print("OK: env TASK and hydrated cache files_writable agree")
PY
export HERMES_KANBAN_FILES_WRITABLE='["pom.xml","src/main/resources/application.properties"]'
if ! hook '{"tool_name":"write_file","tool_input":{"path":"pom.xml"}}'; then
  echo "FAIL: hydrated env should allow pom.xml" >&2
  exit 1
fi
echo "OK: after hydrate, fence allows env paths"

echo "== terminal argv write-sets (defense-in-depth, not a fix) =="
if hook '{"tool_name":"terminal","tool_input":{"command":"mkdir -p evidence/runtime/write-sets && echo x > evidence/runtime/write-sets/t_cafeba.json"}}'; then
  echo "FAIL: terminal argv targeting write-sets must block" >&2
  exit 1
fi
echo "OK: terminal argv targeting write-set cache is refused (not a sandbox)"

echo "OK: v24 scratch items 1+2 PASS (hole 2 not claimed)"
