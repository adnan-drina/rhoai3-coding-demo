#!/usr/bin/env bash
# Local release qualification of the Stage 080 harness (MIGRATION-IMPROVEMENTS.md
# M-7): runs the golden scaffold's qualification suites and the repeatability
# driver, then writes OUT/verdict.json with the source identity, every suite's
# result, the repeatability cases and the claim boundary. No cluster, no model,
# no network beyond what a suite or producer itself needs.
#
#   qualify-release.sh --out DIR [--python PY] [--suite FILE ...] [--no-suites]
#                      [--suite-timeout SECONDS] [--no-producers]
#                      [--source DIR] [--specimen DIR] [--build-fresh DIR]
#                      [--fresh A B] [--patches A B]
#
# --suite (repeatable) runs only those suites; by default every *.test.py and
# *selftest*.py under the scaffold's .hermes (fixtures excluded) plus this
# stage's run-preflight.test.py. A suite that needs podman where none is on PATH
# is NOT-RUN; a suite whose last status line starts with SKIP is NOT-RUN.
# The repeatability options are passed through to
# .hermes/skills/planning/build-worklist/scripts/qualify-repeatability.py.
#
# verdict.json "verdict" is PASS only when no suite and no repeatability case
# failed. It never widens a claim: claims.* carry the driver's grading
# (MEASURED / PARTIAL / NOT-MEASURED / FAILED) with what each is missing.
# Exit 0 on PASS, 1 on FAIL, 2 on usage errors.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCAFFOLD="${SCRIPT_DIR}/scaffold-repo/quarkus-migration-scaffold"
DRIVER="${SCAFFOLD}/.hermes/skills/planning/build-worklist/scripts/qualify-repeatability.py"

usage() { sed -n '7,11p' "${BASH_SOURCE[0]}" >&2; exit 2; }

OUT=""
PY=""
SUITE_TIMEOUT=1800
NO_SUITES=0
SUITES=()
DRIVER_ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --out) OUT="${2:-}"; shift 2 ;;
    --python) PY="${2:-}"; shift 2 ;;
    --suite) SUITES+=("${2:-}"); shift 2 ;;
    --no-suites) NO_SUITES=1; shift ;;
    --suite-timeout) SUITE_TIMEOUT="${2:-}"; shift 2 ;;
    --no-producers) DRIVER_ARGS+=(--no-producers); shift ;;
    --source|--specimen|--build-fresh) DRIVER_ARGS+=("$1" "${2:-}"); shift 2 ;;
    --fresh|--patches) DRIVER_ARGS+=("$1" "${2:-}" "${3:-}"); shift 3 ;;
    *) usage ;;
  esac
done
[[ -n "${OUT}" ]] || usage
if [[ -z "${PY}" ]]; then
  # the worker interpreter (UDI python3 is 3.9); the host's python3 otherwise
  if command -v python3.9 >/dev/null 2>&1; then PY="python3.9"; else PY="python3"; fi
fi
mkdir -p "${OUT}"
OUT="$(cd "${OUT}" && pwd)"

echo "== repeatability driver" >&2
set +e
"${PY}" "${DRIVER}" --out "${OUT}/repeatability.json" ${DRIVER_ARGS[@]+"${DRIVER_ARGS[@]}"} > "${OUT}/repeatability.log" 2>&1
DRIVER_RC=$?
set -e
tail -n 3 "${OUT}/repeatability.log" >&2 || true

SUITE_LIST="${OUT}/suites.txt"
: > "${SUITE_LIST}"
if [[ "${NO_SUITES}" -eq 0 ]]; then
  if [[ "${#SUITES[@]}" -gt 0 ]]; then
    printf '%s\n' "${SUITES[@]}" > "${SUITE_LIST}"
  else
    find "${SCAFFOLD}/.hermes" -path '*/fixtures' -prune -o -type f \( -name '*.test.py' -o -name '*selftest*.py' \) -print \
      | LC_ALL=C sort > "${SUITE_LIST}"
    printf '%s\n' "${SCRIPT_DIR}/run-preflight.test.py" >> "${SUITE_LIST}"
  fi
fi

echo "== suites ($(wc -l < "${SUITE_LIST}" | tr -d ' ')) and verdict" >&2
"${PY}" - "${OUT}" "${SUITE_LIST}" "${SUITE_TIMEOUT}" "${DRIVER_RC}" "${SCAFFOLD}" "${PY}" <<'PY'
import json, os, platform, shutil, subprocess, sys, time
from pathlib import Path

out, suite_list, timeout, driver_rc, scaffold, py = (Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3]),
                                                      int(sys.argv[4]), Path(sys.argv[5]), sys.argv[6])


def git(*args):
    try:
        return subprocess.run(["git", "-C", str(scaffold)] + list(args), capture_output=True, text=True, timeout=60).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


top = git("rev-parse", "--show-toplevel")
rel = os.path.relpath(str(scaffold), top) if top else ""
identity = {"commit": git("rev-parse", "HEAD"), "scaffold_path": rel,
            "scaffold_tree": git("rev-parse", "HEAD:%s" % rel) if rel else "",
            "scaffold_dirty": bool(git("status", "--porcelain", "--", ".")),
            "python": "%s %s" % (py, platform.python_version()), "platform": platform.platform()}

results = []
for line in suite_list.read_text(encoding="utf-8").splitlines():
    suite = Path(line.strip())
    if not line.strip():
        continue
    rec = {"suite": os.path.relpath(str(suite), str(scaffold.parent.parent)) if suite.is_absolute() else str(suite)}
    if not suite.is_file():
        rec.update(status="FAIL", detail="no such suite")
        results.append(rec)
        continue
    if "podman" in suite.read_text(encoding="utf-8", errors="replace") and not shutil.which("podman"):
        rec.update(status="NOT-RUN", detail="needs podman; none on PATH")
        results.append(rec)
        continue
    t0 = time.time()
    try:
        p = subprocess.run([py, str(suite)], capture_output=True, text=True, timeout=timeout,
                           env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
        lines = [ln for ln in (p.stdout + p.stderr).splitlines() if ln.startswith(("OK", "FAIL", "SKIP", "PASS"))]
        last = lines[-1] if lines else ((p.stdout + p.stderr).strip().splitlines() or ["rc %d" % p.returncode])[-1]
        status = "FAIL" if p.returncode != 0 else "NOT-RUN" if last.startswith("SKIP") else "PASS"
        rec.update(status=status, rc=p.returncode, detail=last[:300])
    except subprocess.TimeoutExpired:
        rec.update(status="FAIL", detail="exceeded %d s" % timeout)
    rec["seconds"] = round(time.time() - t0, 1)
    results.append(rec)
    print("%-7s %s" % (rec["status"], rec["suite"]), file=sys.stderr)

rep_path = out / "repeatability.json"
rep = json.loads(rep_path.read_text(encoding="utf-8")) if rep_path.is_file() else {}
cases = rep.get("cases") or []
failed_cases = [c["case"] for c in cases if c.get("status") == "FAIL"]
driver_ok = driver_rc == 0 and bool(rep)
failed_suites = [r["suite"] for r in results if r["status"] == "FAIL"]
boundary = rep.get("claim_boundary") or {}
verdict = {
    "schema": "rhoai3.release-qualification-verdict/v1",
    "verdict": "PASS" if driver_ok and not failed_suites and not failed_cases else "FAIL",
    "meaning": "PASS: no suite and no repeatability case failed. It establishes only what claims.* grade MEASURED; "
               "a NOT-RUN case or suite is listed, never counted as a pass.",
    "identity": identity,
    "suites": {"total": len(results), "pass": sum(r["status"] == "PASS" for r in results),
               "not_run": [r for r in results if r["status"] == "NOT-RUN"], "failed": failed_suites, "results": results},
    "repeatability": {"driver_rc": driver_rc, "report": str(rep_path) if rep else "",
                      "pass": sum(c.get("status") == "PASS" for c in cases),
                      "not_run": [{"case": c["case"], "detail": c.get("detail")} for c in cases if c.get("status") == "NOT-RUN"],
                      "failed": failed_cases},
    "claims": boundary.get("claims") or {
        k: {"status": "NOT-MEASURED", "missing": ["the repeatability driver produced no report (rc %d)" % driver_rc]}
        for k in ("repeatable_planning", "repeatable_transformations", "repeatable_migration")},
    "claim_boundary": {k: boundary.get(k) for k in ("covers", "does_not_cover")},
}
(out / "verdict.json").write_text(json.dumps(verdict, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print("%s: release qualification (suites %d/%d pass, %d not-run; repeatability %d pass, %d not-run, %d fail); claims %s -> %s" % (
    verdict["verdict"], verdict["suites"]["pass"], len(results), len(verdict["suites"]["not_run"]),
    verdict["repeatability"]["pass"], len(verdict["repeatability"]["not_run"]), len(failed_cases),
    ", ".join("%s=%s" % (k, v.get("status")) for k, v in sorted(verdict["claims"].items())), out / "verdict.json"))
sys.exit(0 if verdict["verdict"] == "PASS" else 1)
PY
