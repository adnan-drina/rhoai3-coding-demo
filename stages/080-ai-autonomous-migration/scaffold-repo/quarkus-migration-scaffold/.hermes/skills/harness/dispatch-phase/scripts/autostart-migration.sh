#!/usr/bin/env bash
# dest-init consumer: mint M1 ANALYZE (always) and, only when the planner
# activation gate has been passed (.hermes/pins.json pins.planner.activation
# == "activated"), M2 PLAN as a child of M1 with the fixed key m2-plan.
# Never M3. Never M4 (K4 mints those from an ADMITTED receipt). Never
# triage, specify, decompose, swarm, or kanban daemon --force.
set -euo pipefail

ROOT=""
AFTER_M1=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --root)
      ROOT="${2:-}"
      shift 2
      ;;
    --after-m1)
      AFTER_M1="${2:?--after-m1 requires the existing M1 task id}"
      shift 2
      ;;
    -h|--help)
      echo "usage: autostart-migration.sh --root <project> [--after-m1 <task-id>]" >&2
      exit 2
      ;;
    *)
      echo "usage: autostart-migration.sh --root <project> [--after-m1 <task-id>]" >&2
      exit 2
      ;;
  esac
done

if [[ -z "${ROOT}" || ! -d "${ROOT}" ]]; then
  echo "FAIL: --root must be an existing directory" >&2
  exit 2
fi

ROOT="$(cd "${ROOT}" && pwd)"
STATUS="${ROOT}/.hermes/AUTOSTART-STATUS"
mkdir -p "${ROOT}/.hermes"
export HERMES_HOME="${HERMES_HOME:-${ROOT}/.hermes/home}"
# Do not prepend HERMES_HOME/bin. hermes is /usr/local/bin/hermes on dest.
HERMES="$(command -v hermes || true)"

write_status() {
  python3 - "$STATUS" <<'PY'
import json, os, sys
path = sys.argv[1]
payload = json.loads(os.environ.get("AUTOSTART_JSON") or "{}")
os.makedirs(os.path.dirname(path), exist_ok=True)
with open(path, "w", encoding="utf-8") as fh:
    json.dump(payload, fh, indent=2)
    fh.write("\n")
PY
}

fail_status() {
  local reason="$1"
  export AUTOSTART_JSON
  AUTOSTART_JSON="$(python3 -c 'import json,sys; print(json.dumps({"state":"failed","reason":sys.argv[1]}))' "${reason}")"
  write_status
  echo "FAIL: autostart-migration: ${reason}" >&2
  exit 1
}

# The startup preference controls starting a run, not continuing a native M1
# already started by the Operator. Continuation validates that task below;
# it does not grant planner activation or release M2 before M1 review.
if [[ -z "${AFTER_M1}" ]]; then
case "${AUTO_START_MIGRATION:-true}" in
  false|False|FALSE|0|off|OFF|no|NO)
    export AUTOSTART_JSON
    AUTOSTART_JSON="$(python3 -c 'import json; print(json.dumps({"state":"skipped","reason":"AUTO_START_MIGRATION off"}))')"
    write_status
    echo "OK: autostart skipped (AUTO_START_MIGRATION off)"
    exit 0
    ;;
esac
fi

# Run declaration: this run's name and budget, as the factory declared them in
# the destination's initial commit (planner/run_declaration.py). Checked on
# every start and on continuation, never renewed: a restart re-reads the same
# committed bytes. A refusal stops the run before any card exists -- a missing,
# foreign, stale or rewritten declaration means this repository would run on
# a budget that is not its own. The explicit off switch above still wins.
if ! DECLARATION_OUT="$(PYTHONPATH="${ROOT}/.hermes/lib" python3 -m planner.run_declaration --root "${ROOT}" 2>&1)"; then
  fail_status "${DECLARATION_OUT#REFUSE: }"
fi

# B1: the in-cluster MaaS route is a prerequisite of every dispatch, start and
# continuation alike (v12 was created without its hostAlias and its model
# traffic took the public load balancer). The one shared check
# (planner.maas_route, also used by the Operator preflight): the platform's
# expected gateway host and Service address are set, the worker endpoint is
# that host, it resolves here to that address, and TLS verifies through it.
# A refusal mints nothing. The explicit off switch above still wins.
if [[ -f "${ROOT}/.hermes/lib/planner/maas_route.py" ]]; then
  if ! ROUTE_OUT="$(PYTHONPATH="${ROOT}/.hermes/lib" python3 -m planner.maas_route --root "${ROOT}" 2>&1)"; then
    fail_status "${ROUTE_OUT#REFUSE }"
  fi
  echo "${ROUTE_OUT}"
fi

# R1/R3: a run the factory declared under run control starts only with the
# platform's record present and intact: the contract, the pinned release and
# the pinned model profile (planner.run_control.run_gaps). A legacy run has no
# such declaration and passes through unchanged.
if ! RUNCTL_OUT="$(PYTHONPATH="${ROOT}/.hermes/lib" python3 -c 'import sys; from planner.run_control import run_gaps; g = run_gaps(sys.argv[1]); print(g[0] if g else "run control: ok or not declared"); raise SystemExit(1 if g else 0)' "${ROOT}" 2>&1)"; then
  fail_status "${RUNCTL_OUT}"
fi
# ... and on the Hermes runtime the harness was qualified on: the image stamp
# names the pinned patched tree (loop halt, truncation/quota stops, pacer).
if ! RUNTIME_OUT="$(PYTHONPATH="${ROOT}/.hermes/lib" python3 -c 'import sys; from planner.run_control import runtime_gaps; g = runtime_gaps(sys.argv[1]); print(g[0] if g else "hermes runtime: ok or not declared"); raise SystemExit(1 if g else 0)' "${ROOT}" 2>&1)"; then
  fail_status "${RUNTIME_OUT}"
fi
# The board protocol (planner.outcome_protocol.launch_gaps): a run that
# requested the outcome board starts only when its initial-commit request and
# the read-only run control agree and its execution gate is open. A missing,
# inconsistent or downgraded selection refuses here; the serial loop is never
# started instead. A run that requested nothing (v12-v17) or the serial loop
# passes unchanged.
if ! PROTOCOL_OUT="$(PYTHONPATH="${ROOT}/.hermes/lib" python3 -m planner.outcome_protocol --root "${ROOT}" launch-check 2>&1)"; then
  fail_status "$(printf '%s\n' "${PROTOCOL_OUT}" | grep -m1 '^REFUSE' || printf '%s' "${PROTOCOL_OUT}" | tail -1)"
fi

if [[ -z "${HERMES}" ]]; then
  fail_status "hermes not on PATH"
fi

if [[ -n "${AFTER_M1}" ]]; then
  python3 - "${ROOT}" "${AFTER_M1}" <<'PYCONTINUE' || fail_status "M1 continuation task mismatch"
import sys
from pathlib import Path
root = Path(sys.argv[1])
sys.path.insert(0, str(root / ".hermes/lib"))
from paved_road import phase_card_gaps
gaps = phase_card_gaps(root, sys.argv[2], "M1 ANALYZE")
if gaps:
    print("FAIL: " + "; ".join(gaps), file=sys.stderr)
    raise SystemExit(1)
PYCONTINUE
fi

# Bind a platform-authorized pilot seal to the bundle on disk (SAD section 12).
#
# The decision "this run may plan" is the named human act of creating the
# workspace: dest-init records it in pins.planner.pilot as
# {run_id: <DevWorkspace>, authorized_by: <creator>, authorization: {source:
# devworkspace, ...}} with no digest. Binding that authorization to the
# evidence bundle is a derivation, not a decision -- the only value written is
# the canonical digest of the bundle that exists -- so the harness may do it
# once M1 has produced one. planner.pins.pilot_bind_gaps refuses a seal that is
# already bound, has no named authorizer, or was not recorded by the platform;
# bundle_fitness_gaps refuses to bind an unfit bundle (a producer that did not
# run, no canary, no entry point, no obligation), which is what a human was
# nominally checking before signing. Admission re-checks all of it and is
# still the gate on the plan.
python3 - "${ROOT}" <<'PYBIND' || true
import datetime, sys
from pathlib import Path
root = Path(sys.argv[1])
sys.path.insert(0, str(root / ".hermes" / "lib"))
try:
    from planner.canonical import digest, load_json, write_canonical
    from planner.pins import bundle_fitness_gaps, pilot_bind_gaps
except Exception as exc:
    print("bind: planner lib unavailable (%s); nothing bound" % exc)
    raise SystemExit(0)
pins_path = root / ".hermes" / "pins.json"
bundle_path = root / "evidence" / "planning" / "evidence-bundle.json"
# B8/R3: a run governed by run control (its initial-commit declaration says so)
# is authorized by the PLATFORM's read-only record; the harness's one narrow
# operation is the write-once binding of this bundle's digest. A legacy run
# binds in pins.json exactly as before v13.
from planner import run_control
if run_control.in_use(root):
    if not bundle_path.is_file():
        print("bind: no evidence bundle yet; M1 has not produced one")
        raise SystemExit(0)
    bundle = load_json(bundle_path)
    unfit = bundle_fitness_gaps(bundle)
    if unfit:
        print("REFUSE: BIND_UNFIT_BUNDLE %s" % "; ".join(unfit[:3]))
        raise SystemExit(0)
    ok, msg = run_control.bind(root, digest(bundle), "M1 evidence bundle")
    print(("bind: %s (run control)" if ok else "REFUSE: %s") % msg)
    raise SystemExit(0)
try:
    doc = load_json(pins_path)
except Exception as exc:
    print("bind: pins unreadable (%s); nothing bound" % exc)
    raise SystemExit(0)
gaps = pilot_bind_gaps(doc.get("pins") or {})
if gaps:
    print("bind: not bindable (%s)" % gaps[0])
    raise SystemExit(0)
if not bundle_path.is_file():
    print("bind: no evidence bundle yet; M1 has not produced one")
    raise SystemExit(0)
bundle = load_json(bundle_path)
unfit = bundle_fitness_gaps(bundle)
if unfit:
    print("REFUSE: BIND_UNFIT_BUNDLE %s" % "; ".join(unfit[:3]))
    raise SystemExit(0)
d = digest(bundle)
seal = doc["pins"]["planner"]["pilot"]
seal["evidence_bundle_sha256"] = d
seal["bound_at"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
write_canonical(pins_path, doc)
print("bind: pilot seal for run %s (authorized by %s) bound to bundle %s" % (seal.get("run_id"), seal.get("authorized_by"), d[:16]))
PYBIND

# Planner activation (SAD §9/§12). Read, never decided here. "activated" mints
# M2 at dest-init. "pilot" mints M2 only once the Operator's seal names the
# evidence bundle that is on disk (so at dest-init, before M1, a pilot mints
# M1 only; the last M1 step re-runs this script, which binds the platform
# authorization and mints M2 - M1 is idempotent).
# The same check (planner.pins.activation_gaps) gates the first M2 step, admission and K4.
PLANNER_ACTIVATION="$(python3 - "${ROOT}" <<'PY'
import json, sys
from pathlib import Path
root = Path(sys.argv[1])
sys.path.insert(0, str(root / ".hermes" / "lib"))
try:
    # load_pins takes the activation from run control when it governs this run (B8)
    from planner.pins import load_pins
    pins = {"pins": load_pins(root)}
except Exception:
    pins = {}
mode = str(((pins.get("pins") or {}).get("planner") or {}).get("activation") or "").strip().lower()
if mode == "activated":
    print("activated")
elif mode == "pilot":
    try:
        from planner.canonical import digest, load_json
        from planner.pins import activation_gaps
        bundle = root / "evidence" / "planning" / "evidence-bundle.json"
        gaps = activation_gaps(pins.get("pins") or {}, digest(load_json(bundle)) if bundle.is_file() else "")
    except Exception as exc:  # no lib, unreadable bundle: fail closed
        gaps = ["PLANNER_PILOT_SEAL: %s" % exc]
    print("pilot" if not gaps else "not-activated")
else:
    print("not-activated")
PY
)"

# The card bodies say what each phase delivers and how it is done, for the
# person reading the board. The ordered commands, pins, exceptions and audit
# mechanics live in the pinned skill (paved-road-m1 / paved-road-m2), never
# here. M2 names the procedure of the protocol this run selected
# (planner.outcome_protocol, checked above); it never changes a selection.
BOARD_PROTOCOL="$(printf '%s\n' "${PROTOCOL_OUT:-}" | python3 -c 'import json,sys
for line in sys.stdin:
    line = line.strip()
    if line.startswith("{"):
        try:
            print(json.loads(line).get("protocol") or "serial-loop/v1")
            raise SystemExit(0)
        except ValueError:
            pass
print("serial-loop/v1")' 2>/dev/null || echo serial-loop/v1)"

M1_BODY="Establish the legacy application's baseline for migration planning.

Produce the frozen source reference, build evidence, MTA findings, the application inventories and the source's recorded behavior (baseline captures). Attach the evidence set to this card and record any coverage gaps.

Done when: the evidence bundle and the captures exist for this run, M2 PLAN exists as this card's child, and the reviewer approves the audit.

Procedure: paved-road-m1."

case "${BOARD_PROTOCOL}" in
  outcome-board/v2|outcome-board/v1)
    M2_BODY="Publish the migration plan from the reviewed M1 evidence.

Make every known repair outcome and the M4/M5 milestones visible on the board as their own cards, with their dependencies and attached contracts; the plan itself is attached to this card. Record unresolved responsibilities.

Done when: the plan is ADMITTED, the published board reads back equal to the admitted plan, and the reviewer approves.

Procedure: paved-road-m2 (${BOARD_PROTOCOL})."
    ;;
  *)
    M2_BODY="Admit the migration plan from the reviewed M1 evidence and start the fix-until-green loop.

Compute the work list, admit it, and create the first loop card for the head of the list.

Done when: the plan is ADMITTED, the live board equals the loop's expected cards, and the reviewer approves.

Procedure: paved-road-m2 (serial-loop/v1)."
    ;;
esac

create_card() {
  local title="$1"
  shift
  "${HERMES}" kanban create --json "${title}" "$@"
}

parse_id() {
  python3 -c 'import json,sys
raw=sys.stdin.read()
blob=json.loads(raw[raw.find("{"):raw.rfind("}")+1] if "{" in raw else raw)
tid=blob.get("task_id") or blob.get("id") or (blob.get("task") or {}).get("id")
if not tid:
    raise SystemExit("missing id")
print(tid)
'
}

if [[ -n "${AFTER_M1}" ]]; then
  M1_ID="${AFTER_M1}"
else
M1_JSON="$(
  create_card "M1 ANALYZE" \
    --assignee implementer \
    --workspace "dir:${ROOT}" \
    --max-retries 1 \
    --max-runtime 2h \
    --skill paved-road-m1 \
    --idempotency-key m1-analyze \
    --body "${M1_BODY}"
)" || fail_status "M1 create failed"
M1_ID="$(parse_id <<<"${M1_JSON}")" || fail_status "M1 create JSON missing t_* id"
fi

M2_ID=""
if [[ "${PLANNER_ACTIVATION}" == "activated" || "${PLANNER_ACTIVATION}" == "pilot" ]]; then
  M2_JSON="$(
    create_card "M2 PLAN" \
      --assignee implementer \
      --workspace "dir:${ROOT}" \
      --parent "${M1_ID}" \
      --max-retries 1 \
      --max-runtime 2h \
      --skill paved-road-m2 \
      --idempotency-key m2-plan \
      --body "${M2_BODY}"
  )" || fail_status "M2 create failed"
  M2_ID="$(parse_id <<<"${M2_JSON}")" || fail_status "M2 create JSON missing t_* id"
fi

PREV_M1=""
PREV_M2=""
if [[ -f "${STATUS}" ]]; then
  PREV_M1="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("m1_id") or "")' "${STATUS}" 2>/dev/null || true)"
  PREV_M2="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("m2_id") or "")' "${STATUS}" 2>/dev/null || true)"
fi
REUSED=0
if [[ -n "${PREV_M1}" && "${PREV_M1}" == "${M1_ID}" && "${PREV_M2}" == "${M2_ID}" ]]; then
  REUSED=1
fi

export AUTOSTART_JSON
AUTOSTART_JSON="$(python3 -c '
import json, sys
m1, m2, planner, reused = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4] == "1"
after_m1 = sys.argv[5]
if after_m1:
    reason = "Existing M1 continued; %s (planner %s)" % ("M2 ensured as child" if m2 else "M2 not minted", planner)
elif reused and m2:
    reason = "M1 reused; M2 reused as child (planner %s)" % planner
elif reused:
    reason = "M1 reused; M2 not minted (planner %s)" % planner
elif m2:
    reason = "M1 minted; M2 minted as child (planner %s)" % planner
else:
    reason = "M1 minted; M2 not minted (planner activation gate not passed; SOLUTION-ARCHITECTURE section 12)"
print(json.dumps({
  "state": "minted",
  "reason": reason,
  "planner_activation": planner,
  "m1_id": m1,
  "m2_id": m2,
  "after_m1": after_m1,
  "reused": reused,
  "argv_m1": ([] if after_m1 else ["hermes","kanban","create","--json","M1 ANALYZE","--idempotency-key","m1-analyze"]),
  "argv_m2": (["hermes","kanban","create","--json","M2 PLAN","--parent",m1,"--idempotency-key","m2-plan"] if m2 else []),
}))
' "${M1_ID}" "${M2_ID}" "${PLANNER_ACTIVATION}" "${REUSED}" "${AFTER_M1}")"
write_status
if [[ -n "${AFTER_M1}" ]]; then
  echo "OK: autostart continued M1=${M1_ID} M2=${M2_ID:-not-minted} (planner ${PLANNER_ACTIVATION})"
elif [[ "${REUSED}" == "1" && -n "${M2_ID}" ]]; then
  echo "OK: autostart reused M1=${M1_ID} M2=${M2_ID} (planner ${PLANNER_ACTIVATION}; dest-init idempotent, not a new mint)"
elif [[ "${REUSED}" == "1" ]]; then
  echo "OK: autostart reused M1=${M1_ID} (planner ${PLANNER_ACTIVATION}; dest-init idempotent, not a new mint)"
elif [[ -n "${M2_ID}" ]]; then
  echo "OK: autostart minted M1=${M1_ID} M2=${M2_ID} (planner ${PLANNER_ACTIVATION})"
else
  echo "OK: autostart minted M1=${M1_ID} (M2 not minted: planner ${PLANNER_ACTIVATION})"
fi
