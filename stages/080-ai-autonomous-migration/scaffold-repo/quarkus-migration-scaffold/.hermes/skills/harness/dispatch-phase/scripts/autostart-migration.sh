#!/usr/bin/env bash
# dest-init consumer: mint M1 ANALYZE (always) and, only when the planner
# activation gate has been passed (.hermes/pins.json pins.planner.activation
# == "activated"), M2 PLAN as a child of M1 with the fixed key m2-plan.
# Never M3. Never M4 (K4 mints those from an ADMITTED receipt). Never
# triage, specify, decompose, swarm, or kanban daemon --force.
set -euo pipefail

ROOT=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --root)
      ROOT="${2:-}"
      shift 2
      ;;
    -h|--help)
      echo "usage: autostart-migration.sh --root <project>" >&2
      exit 2
      ;;
    *)
      echo "usage: autostart-migration.sh --root <project>" >&2
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

case "${AUTO_START_MIGRATION:-true}" in
  false|False|FALSE|0|off|OFF|no|NO)
    export AUTOSTART_JSON
    AUTOSTART_JSON="$(python3 -c 'import json; print(json.dumps({"state":"skipped","reason":"AUTO_START_MIGRATION off"}))')"
    write_status
    echo "OK: autostart skipped (AUTO_START_MIGRATION off)"
    exit 0
    ;;
esac

if [[ -z "${HERMES}" ]]; then
  fail_status "hermes not on PATH"
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
    pins = json.load(open(root / ".hermes" / "pins.json", encoding="utf-8"))
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

M1_BODY='Follow paved-road-m1. skill_view subskills from steps.json in order: freeze-migration-input, capture-build-evidence, inventory-legacy-surface, scan-with-mta, assemble-evidence-bundle. Attach the KEEP artifacts by running .hermes/kernel/kanban_attach.py via terminal (python3 .hermes/kernel/kanban_attach.py --task "$HERMES_KANBAN_TASK" --exec). That script fixes the file set and the 25 MiB cap, so the set is not your decision. The kanban_attach tool does not satisfy the paved-road audit. The original frozen legacy source is the only baseline; do not derive or upgrade it first. A producer that records status unpinned is evidence, not a defect to repair: kanban_block kind=needs_input naming the pin. Happy-path terminator is kanban_request_review with reviewer set to reviewer (pass the reviewer parameter; without it the task is dispatched back to you and the paved-road audit never runs), not kanban_complete. kanban_block for external/platform (MaaS 500, missing key, GPU). Do not invent HTTP routes.'

M2_BODY='Follow paved-road-m2. First step is the activation gate (python3 .hermes/skills/planning/admit-migration-plan/scripts/assert-planner-activated.py --root /projects/modernized); then skill_view bootstrap-destination, build-worklist and admit-migration-plan in that order, then python3 .hermes/kernel/k4_mint.py --root /projects/modernized --exec --verify-board, then skill_view verify-live-kanban-loop. The plan is the work list the tools compute; you never author it. An INCONCLUSIVE admission is a legal stop: kanban_block kind=needs_input naming the BLOCK classes; do not hand-author anything under evidence/planning or verification/, and never edit decisions.yaml. K4 mints exactly one card (the head cluster) and zero unless the receipt is ADMITTED. Happy-path terminator is kanban_request_review with reviewer set to reviewer and created_cards equal to the native t_* list from mint. Never kanban swarm, decompose, link, triage, or daemon --force.'

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

export AUTOSTART_JSON
AUTOSTART_JSON="$(python3 -c 'import json,sys; print(json.dumps({
  "state": "minted",
  "reason": ("M1 minted; M2 minted as child (planner %s)" % sys.argv[3] if sys.argv[2] else "M1 minted; M2 not minted (planner activation gate not passed; SOLUTION-ARCHITECTURE section 12)"),
  "planner_activation": sys.argv[3],
  "m1_id": sys.argv[1],
  "m2_id": sys.argv[2],
  "argv_m1": ["hermes","kanban","create","--json","M1 ANALYZE","--idempotency-key","m1-analyze"],
  "argv_m2": (["hermes","kanban","create","--json","M2 PLAN","--parent",sys.argv[1],"--idempotency-key","m2-plan"] if sys.argv[2] else []),
}))' "${M1_ID}" "${M2_ID}" "${PLANNER_ACTIVATION}")"
write_status
if [[ -n "${M2_ID}" ]]; then
  echo "OK: autostart minted M1=${M1_ID} M2=${M2_ID} (planner ${PLANNER_ACTIVATION})"
else
  echo "OK: autostart minted M1=${M1_ID} (M2 not minted: planner ${PLANNER_ACTIVATION})"
fi
