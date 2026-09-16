#!/usr/bin/env bash
# Runtime proof for restore-source-response-shape (ADR-019): the adapters reach
# the platform's EARLY preflight answer, keep enforcement in both security
# modes, never widen a restrictive policy, and leave no-Origin / same-origin
# requests alone. Real platform HTTP layer, not an argument.
#
#   runtime-check.sh [--workdir DIR] [--online] [--keep]
#
# Copies fixtures/runtime to a scratch directory, installs BOTH adapters through
# the capability's own installer (templates + rows rendered from the fixture's
# source model), then runs the fixture's @QuarkusTest suite with Maven
# (offline by default: the pinned platform BOM must already be in the local
# repository). Prints the surefire totals; exit 0 only when every test passed.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL="$(dirname "$HERE")"
WORK=""
OFFLINE="-o"
KEEP=0
while [ $# -gt 0 ]; do
  case "$1" in
    --workdir) WORK="$2"; shift 2 ;;
    --online) OFFLINE=""; shift ;;
    --keep) KEEP=1; shift ;;
    *) echo "REFUSE: unknown argument $1" >&2; exit 2 ;;
  esac
done
if [ -z "$WORK" ]; then
  WORK="$(mktemp -d "${TMPDIR:-/tmp}/response-adapter-runtime.XXXXXX")"
  [ "$KEEP" = 1 ] || trap 'rm -rf "$WORK"' EXIT
fi
APP="$WORK/app"
rm -rf "$APP"
mkdir -p "$APP"
cp -R "$SKILL/fixtures/runtime/." "$APP/"

python3 "$HERE/install-response-adapter.py" --root "$APP" --adapter cors \
  --operator-step ADR-019 --reason "runtime fixture: prove the adapter on the real HTTP layer"
python3 "$HERE/install-response-adapter.py" --root "$APP" --adapter media-type \
  --operator-step ADR-019 --reason "runtime fixture: prove the media-type adapter on the real HTTP layer" \
  --parameter charset=UTF-8 --media-type application/json
# idempotent: a second run changes nothing
before="$(cat "$APP/src/main/resources/application.properties" | shasum -a 256)"
python3 "$HERE/install-response-adapter.py" --root "$APP" --adapter cors \
  --operator-step ADR-019 --reason "runtime fixture: re-run must change nothing" >/dev/null
after="$(cat "$APP/src/main/resources/application.properties" | shasum -a 256)"
[ "$before" = "$after" ] || { echo "REFUSE: RERUN_CHANGED_CONFIG" >&2; exit 1; }
python3 "$HERE/install-response-adapter.py" --root "$APP" --adapter cors --check

MVN="${MVN:-mvn}"
set +e
( cd "$APP" && "$MVN" $OFFLINE -B -q test ) > "$WORK/mvn.log" 2>&1
rc=$?
set +e
python3 - "$APP/target/surefire-reports" "$rc" <<'PY'
import sys, xml.etree.ElementTree as ET
from pathlib import Path
d, rc = Path(sys.argv[1]), int(sys.argv[2])
tests = fails = errors = skipped = 0
for f in sorted(d.glob("TEST-*.xml")) if d.is_dir() else []:
    r = ET.parse(f).getroot()
    tests += int(r.get("tests", 0)); fails += int(r.get("failures", 0))
    errors += int(r.get("errors", 0)); skipped += int(r.get("skipped", 0))
    print("  %s: %s tests, %s failures, %s errors" % (r.get("name"), r.get("tests"), r.get("failures"), r.get("errors")))
print("RUNTIME tests=%d failures=%d errors=%d skipped=%d mvn_rc=%d" % (tests, fails, errors, skipped, rc))
sys.exit(0 if rc == 0 and tests > 0 and not (fails or errors) else 1)
PY
status=$?
set -e
if [ $status -ne 0 ]; then
  tail -80 "$WORK/mvn.log" >&2
  exit $status
fi

# CONTROL (mutation): the same adapter registered BELOW the platform's CORS
# filter -- where a response filter behind the platform would sit -- must NOT
# reproduce the source's preflight. If it still passes, the suite above proves
# nothing about reaching the early answer.
MUT="$WORK/mutant"
rm -rf "$MUT"
cp -R "$APP" "$MUT"
rm -rf "$MUT/target"
python3 - "$MUT/src/main/java/io/rhoai3/migration/response/SourceCorsResponseAdapter.java" <<'PY'
import sys
p = sys.argv[1]
s = open(p, encoding="utf-8").read()
old = "EARLY_PRIORITY = SecurityHandlerPriorities.CORS + 100;"
if old not in s:
    sys.exit("REFUSE: MUTATION_ANCHOR_MISSING")
open(p, "w", encoding="utf-8").write(s.replace(old, "EARLY_PRIORITY = SecurityHandlerPriorities.CORS - 50;"))
PY
set +e
( cd "$MUT" && "$MVN" $OFFLINE -B -q test -Dtest='DisabledModeTest#preflightIsAnsweredInTheSourceShape' ) > "$WORK/mutant.log" 2>&1
mrc=$?
set -e
if [ $mrc -eq 0 ]; then
  echo "REFUSE: MUTATION_SURVIVED the adapter below the platform CORS filter still reproduced the source preflight" >&2
  exit 1
fi
if ! grep -q "preflightIsAnsweredInTheSourceShape" "$WORK/mutant.log"; then
  echo "REFUSE: MUTATION_NOT_MEASURED the mutant build failed before the preflight test ran" >&2
  tail -40 "$WORK/mutant.log" >&2
  exit 1
fi
echo "CONTROL mutation below the platform CORS filter: preflight test FAILS as required (early answer not reached)"
exit 0
