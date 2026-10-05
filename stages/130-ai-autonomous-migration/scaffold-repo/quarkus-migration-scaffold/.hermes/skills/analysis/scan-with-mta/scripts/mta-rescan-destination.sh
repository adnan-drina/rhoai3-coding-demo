#!/usr/bin/env bash
# Destination MTA rescan for M3/M4 obligation closure (same targets, same
# custom rules, no --source). Writes verification/mta-rescan/findings.json
# (append-only execution evidence; never touches evidence/ planning files).
set -euo pipefail

ROOT="${1:-/projects/modernized}"
[[ -d "${ROOT}" ]] || { echo "usage: mta-rescan-destination.sh <dest-root>" >&2; exit 2; }
ROOT="$(cd "${ROOT}" && pwd)"
SCRIPTS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export ENSURE_CLI_LIB=1
# shellcheck source=mta-analyze-legacy.sh
source "${SCRIPTS}/mta-analyze-legacy.sh"
unset ENSURE_CLI_LIB
CLI="$(ensure_cli)" || { echo "FAIL: MTA CLI unusable" >&2; exit 1; }
OUT="${ROOT}/verification/mta-rescan"
rm -rf "${OUT}"; mkdir -p "${OUT}/report"
TARGETS=()
while IFS= read -r t; do [[ -n "${t}" ]] && TARGETS+=(--target "${t}"); done < <(python3 - "${ROOT}/migration.yaml" <<'PY'
import sys
sys.path.insert(0, sys.argv[1].rsplit("/", 1)[0] + "/.hermes/lib")
from planner.evidence import load_migration
from pathlib import Path
for t in load_migration(Path(sys.argv[1]).parent)["targets"]:
    print(t)
PY
)
RULES="$(python3 - "${ROOT}" <<'PY'
import sys
sys.path.insert(0, sys.argv[1] + "/.hermes/lib")
from planner.evidence import load_migration
from pathlib import Path
print(load_migration(Path(sys.argv[1]))["custom_rules"])
PY
)"
RULES_FLAGS=()
[[ -n "${RULES}" && -d "${ROOT}/${RULES#/}" ]] && RULES_FLAGS=(--rules "${ROOT}/${RULES#/}")
CANARY_ID="$(python3 - "${ROOT}" <<'PY'
import sys
sys.path.insert(0, sys.argv[1] + "/.hermes/lib")
from planner.evidence import load_migration
from pathlib import Path
print(load_migration(Path(sys.argv[1]))["canary_rule_id"])
PY
)"
# the measured product version, as mta-analyze-legacy.sh measures it: the analyzer-exit
# judgement binds its one compatibility exception to the version it was identified on
CLI_VERSION="$("${CLI}" version 2>/dev/null | grep -m1 -E '[0-9]+\.[0-9]+' || true)"
# The tree this scan is of, recorded BEFORE the analyzer runs and as the loop
# identifies trees (planner.canonical.product_tree_sha256, the accepted step's
# candidate_sha256): the M4 rescan floor (assert-mta-rescan.py) compares this
# digest with the tree it judges, so a rescan of an older tree cannot stand in
# for one of this tree. The git HEAD is recorded beside it for the audit.
TREE_SHA256="$(python3 - "${ROOT}" <<'PY'
import sys
sys.path.insert(0, sys.argv[1] + "/.hermes/lib")
from pathlib import Path
from planner.canonical import product_tree_sha256
print(product_tree_sha256(Path(sys.argv[1])))
PY
)"
DEST_DIGEST="$(git -C "${ROOT}" rev-parse HEAD 2>/dev/null || echo worktree)"
export JAVA_HOME="${JAVA_HOME_21:-${JAVA_HOME:-}}"; export PATH="${JAVA_HOME}/bin:${PATH}"
MTA_RUN_CWD="${MTA_RUN_CWD:-/projects/.tools/mta-run}"; mkdir -p "${MTA_RUN_CWD}"
# The analyzer never runs on the candidate itself: its Java provider (JDT/m2e)
# writes .project, .settings/ and .classpath into the tree it analyzes. They are
# git-ignored but product bytes, so an in-place scan moved the candidate's
# product digest off HEAD and the next issue refused ISSUE_BASELINE_DRIFT
# (2026-09-28 qualification, pinned ws-080 image). It analyzes a disposable
# snapshot of the CURRENT candidate -- the working tree, uncommitted repair
# included, in harness-owned scratch, with the same relative layout -- then maps
# the findings back to destination-relative paths before normalization and
# binds them to the candidate's pre-scan digest. The candidate is re-hashed after
# the analyzer: a candidate that moved during the scan is a stale input, refused.
SNAP_BASE="$(mktemp -d "${MTA_RUN_CWD%/}/destination-input.XXXXXX")"
SNAP="${SNAP_BASE}/$(basename "${ROOT}")"
# the copy keeps the candidate's modes (evidence/mta is read-only), and cleanup never decides the
# scan's exit status: bash would otherwise report a failed rm as the rescan's own failure
cleanup() { chmod -R u+w "${SNAP_BASE}" 2>/dev/null; rm -rf "${SNAP_BASE}" 2>/dev/null || true; }
trap 'rc_=$?; cleanup; exit ${rc_}' EXIT
python3 - "${ROOT}" "${SNAP}" "${TREE_SHA256}" <<'PY'
import os, shutil, sys
from pathlib import Path
root, snap, want = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
sys.path.insert(0, str(root / ".hermes/lib"))
from planner.canonical import product_tree_sha256
# everything the in-place scan saw, except git's object store and this scan's own output
skip = {".git", "verification/mta-rescan"}
def ignore(d, names):
    rel = os.path.relpath(d, root)
    rel = "" if rel == "." else rel + "/"
    return [n for n in names if (rel + n) in skip]
shutil.copytree(root, snap, symlinks=True, ignore=ignore)
got = product_tree_sha256(snap)
if got != want:
    raise SystemExit("FAIL: MTA_RESCAN_SNAPSHOT the analysis copy is not the candidate (%s != %s)" % (got[:12], want[:12]))
PY
# --json-output is a boolean on the pinned MTA CLI 8.2.1 ("create analysis and dependency output
# as json"); the findings are <output>/output.json. The analyzer's console is kept beside the
# report because the exit judgement reads it. The exit status is judged, never ignored
# (judge-analyzer-exit.py): a clean exit, or the one documented 8.2.1 dependency-JSON marshal
# defect after a completed, consistent analysis, recorded with its nonzero exit status. Anything
# else means incidents are UNKNOWN: the rescan fails and writes no findings.
OUTPUT_EXISTED=()
[[ -e "${OUT}/report/output.json" ]] && OUTPUT_EXISTED=(--output-existed)
touch "${OUT}/.analyze-started"
set +e
( cd "${MTA_RUN_CWD}" && "${CLI}" analyze --input "${SNAP}" --output "${OUT}/report" ${TARGETS[@]+"${TARGETS[@]}"} ${RULES_FLAGS[@]+"${RULES_FLAGS[@]}"} --json-output --overwrite ) 2>&1 | tee "${OUT}/analyze.console.log" >&2
rc=${PIPESTATUS[0]}
python3 "${SCRIPTS}/judge-analyzer-exit.py" --rc "${rc}" --report-dir "${OUT}/report" --console "${OUT}/analyze.console.log" \
  --started "${OUT}/.analyze-started" --cli-version "${CLI_VERSION}" --input-root "${SNAP}" --canary-id "${CANARY_ID}" \
  ${OUTPUT_EXISTED[@]+"${OUTPUT_EXISTED[@]}"} > "${OUT}/analyzer-verdict.json"
judged=$?
set -e
[[ "${judged}" -eq 0 ]] || { echo "FAIL: destination rescan produced no usable findings (analyzer rc=${rc}; verdict ${OUT}/analyzer-verdict.json)" >&2; exit 1; }
cp -f "${OUT}/report/output.json" "${OUT}/findings.json"
# the candidate the findings describe must still be the candidate on disk, and
# findings name destination-relative files, never the scratch copy
python3 - "${ROOT}" "${SNAP}" "${TREE_SHA256}" "${OUT}/findings.json" "${OUT}/report/output.json" <<'PY'
import sys
from pathlib import Path
root, snap, want = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
sys.path.insert(0, str(root / ".hermes/lib"))
from planner.canonical import product_tree_sha256
now = product_tree_sha256(root)
if now != want:
    for f in sys.argv[4:]:
        p = Path(f)
        if p.is_file():
            p.rename(p.with_name(p.name + ".stale"))
    raise SystemExit("FAIL: MTA_RESCAN_STALE_INPUT the destination changed while it was analyzed (%s before, %s after); the "
                     "findings describe neither tree and are kept only as %s.stale for diagnosis" % (want[:12], now[:12], sys.argv[4]))
for f in sys.argv[4:]:
    p = Path(f)
    if p.is_file():
        text = p.read_text(encoding="utf-8", errors="surrogateescape")
        if snap in text:
            p.write_text(text.replace(snap, str(root)), encoding="utf-8", errors="surrogateescape")
PY
python3 "${SCRIPTS}/normalize-findings.py" "${OUT}/findings.json" "${CLI}" "$(printf '%s,' ${TARGETS[@]+"${TARGETS[@]}"} | tr -d '-' | sed 's/target,//g; s/,$//')" "destination:${DEST_DIGEST}" "${OUT}/rules-coverage.json" "${OUT}/report/static-report/index.html" "${TREE_SHA256}" "${DEST_DIGEST}" "${OUT}/analyzer-verdict.json"
echo "OK: destination rescan → ${OUT}/findings.json (analyzer rc=${rc}, $(python3 -c 'import json, sys; v = json.load(open(sys.argv[1])); print((v.get("compatibility_exception") or {}).get("id") or v.get("basis"))' "${OUT}/analyzer-verdict.json"); analyzed a copy of candidate ${TREE_SHA256:0:12})"
