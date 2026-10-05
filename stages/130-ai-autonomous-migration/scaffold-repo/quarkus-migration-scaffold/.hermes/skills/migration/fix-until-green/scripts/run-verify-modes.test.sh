#!/usr/bin/env bash
# The per-mode parity execution of run-verify.sh, run for real on a bounded fake comparator
# (architect review of 7d77d14f): the marked region is extracted and executed with a fake
# run-parity.py and a stub verify.py. Each issued mode is compared once, in order, with its own
# scenarios and --security-mode; both receipts survive; a failing first mode is not masked by a
# passing second one; run.json records every mode's rc and the scenarios it was assigned.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="${HERE}/run-verify.sh"
TMP="$(mktemp -d)"
trap 'rm -rf "${TMP}"' EXIT
fail() { echo "FAIL: $*" >&2; exit 1; }

awk '/# >>> parity-execution/{f=1} f{print} /# <<< parity-execution/{exit}' "${SCRIPT}" > "${TMP}/region.sh"
grep -q 'run_one_parity' "${TMP}/region.sh" || fail "could not extract the parity execution region"

# the fake comparator: records its argv and writes the receipt of its mode
cat > "${TMP}/run-parity.py" <<'PY'
import json, os, sys
from pathlib import Path
argv = sys.argv[1:]
root = Path(argv[argv.index("--root") + 1])
mode = argv[argv.index("--security-mode") + 1] if "--security-mode" in argv else "disabled"
sids = [argv[i + 1] for i, a in enumerate(argv) if a == "--scenario"]
with open(os.environ["FAKE_LOG"], "a") as f:
    f.write(json.dumps({"mode": mode, "scenarios": sids}) + "\n")
name = "receipt.json" if mode == "disabled" else "receipt-%s.json" % mode
(root / "verification" / "parity").mkdir(parents=True, exist_ok=True)
(root / "verification" / "parity" / name).write_text(json.dumps({"security_mode": mode, "verdict": "PASS", "scenarios": sids}))
sys.exit(int(os.environ.get("FAKE_RC_%s" % mode.upper()) or 0))
PY
mkdir -p "${TMP}/scripts"
printf 'import sys\nsys.exit(0)\n' > "${TMP}/scripts/verify.py"

run_region() {   # $1 disabled rc, $2 enabled rc
  local root="${TMP}/root-$1-$2"
  mkdir -p "${root}/verification/build" "${root}/verification/loop" "${root}/verification/parity"
  printf '{"schema":"rhoai3.verify-run/v1"}' > "${root}/verification/build/run.json"
  : > "${TMP}/log-$1-$2"
  (
    ROOT="${root}"; WORK="${TMP}/work-$1-$2"; mkdir -p "${WORK}"
    RUN="${root}/verification/build/run.json"; DIAG="${TMP}/diag.json"; SCRIPT_DIR="${TMP}/scripts"
    PARITY_RUN_PY="${TMP}/run-parity.py"
    PARITY_RECEIPT="${root}/verification/parity/receipt.json"; PARITY_BEFORE="${root}/verification/build/parity-before.json"
    PARITY_PENDING_SCOPE=0; PARITY_TRIGGER="issued-card"; PARITY_MODE="disabled"
    SIDS="sc:d1,sc:d2,sc:e1"; PLAN_ORACLES=(); TEST_ARGS=(); FIND_ARGS=()
    PARITY_MODE_RUNS=("disabled:sc:d1,sc:d2" "enabled:sc:e1")
    now_ms() { echo 0; }
    record_parity_pending() { :; }
    export FAKE_LOG="${TMP}/log-$1-$2" FAKE_RC_DISABLED="$1" FAKE_RC_ENABLED="$2"
    # shellcheck disable=SC1090
    source "${TMP}/region.sh"
  ) >"${TMP}/out-$1-$2" 2>&1 || fail "the region did not run: $(tail -5 "${TMP}/out-$1-$2")"
  echo "${root}"
}

root="$(run_region 1 0)"
python3 - "${root}" "${TMP}/log-1-0" <<'PY' || exit 1
import json, sys
from pathlib import Path
root, log = Path(sys.argv[1]), sys.argv[2]
calls = [json.loads(l) for l in open(log) if l.strip()]
want = [{"mode": "disabled", "scenarios": ["sc:d1", "sc:d2"]}, {"mode": "enabled", "scenarios": ["sc:e1"]}]
assert calls == want, "each mode compared once, in order, with its own scenarios: %s" % calls
for name in ("receipt.json", "receipt-enabled.json"):
    assert (root / "verification" / "parity" / name).is_file(), "the %s survives the other mode" % name
par = json.loads((root / "verification" / "build" / "run.json").read_text())["runtime"]["parity"]
assert par["rc"] == 1, "a failing first mode is not masked by a passing second one: %s" % par["rc"]
assert par["modes"]["disabled"]["rc"] == 1 and par["modes"]["enabled"]["rc"] == 0, par["modes"]
assert par["modes"]["disabled"]["scenarios"] == ["sc:d1", "sc:d2"] and par["modes"]["enabled"]["scenarios"] == ["sc:e1"], par["modes"]
assert par["scenarios"] == ["sc:d1", "sc:d2", "sc:e1"], par["scenarios"]
PY
root="$(run_region 0 0)"
python3 -c "import json,sys; p=json.load(open(sys.argv[1]))['runtime']['parity']; assert p['rc']==0, p" "${root}/verification/build/run.json" \
  || fail "two passing modes record rc 0"
echo "OK: run-verify per-mode parity execution (each issued mode once, in order, with its own scenarios; both receipts kept; the worst rc stands; run.json records each mode's rc and assigned scenarios)"
