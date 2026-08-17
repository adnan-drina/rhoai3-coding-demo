#!/usr/bin/env bash
# Create an M3 implementer Kanban task with skills from phase-dispatch.yaml
# and a W2 §6 typed body (not a pointer to tasks.md).
#
# Usage:
#   bash .hermes/skills/harness/dispatch-phase/scripts/create-m3-implementer.sh \
#     --title "M3 IMPLEMENT: Owner Management" \
#     --body-json evidence/bodies/m3-001-owner.json \
#     --parent t_xxx [--idempotency-key KEY]
#
# --parent is REQUIRED (Operator E-20260811T133000Z #5 created_cards attribution).
#
# Body JSON must satisfy check-kanban-body.py (phase=M3, refs[], files_in_scope,
# exit_criteria[] — Deputy E-20260809T190500Z completion half).
# Do NOT use bare `hermes kanban create` for M3 — that path omits skills
# (Review grounding study 20260809: M3 workers loaded zero skills).
#
# Cite: platform/known-hermes-behaviours (B5/B6 — single dispatcher;
# park-at-birth nursing until AD-016). This script implements create/park half.
#
# Architect E-20260811T155332Z Class A (tip FREEZE exception): after create,
# emit unsigned evidence/acks/ack-request-<story>.yaml with task_id + body +
# partition digests so Operator/Deputy can sign without hand-copy races.
set -euo pipefail

# SR-2: walk up to migration.yaml — never a parent-count.
resolve_migration_root() {
  local d
  d="$(cd "$(dirname "$0")" && pwd)"
  while [ "$d" != "/" ]; do
    if [ -f "$d/migration.yaml" ]; then
      printf '%s\n' "$d"
      return 0
    fi
    d="$(dirname "$d")"
  done
  echo "cannot find project root (migration.yaml) walking up from $(dirname "$0") (SR-2)" >&2
  return 1
}
ROOT="$(resolve_migration_root)" || exit 1
LINK_GRAPH="${ROOT}/.hermes/skills/harness/dispatch-phase/scripts/read-link-graph.py"
DISPATCH_YAML="${ROOT}/.hermes/phase-dispatch.yaml"
export HERMES_HOME="${HERMES_HOME:-${ROOT}/.hermes/home}"
export HERMES_MANAGED_DIR="${HERMES_MANAGED_DIR:-/projects/.platform/hermes}"
export HERMES_WRITE_SAFE_ROOT="${HERMES_WRITE_SAFE_ROOT:-${ROOT}}"
WORKSPACE_DIR="${WORKSPACE_DIR:-/projects/modernized}"

TITLE=""
BODY_JSON=""
PARENTS=()
IDEM_KEY=""
DRY_RUN=0

die() { echo "create-m3-implementer: $*" >&2; exit 1; }
[[ -f "${LINK_GRAPH}" ]] || die "missing ${LINK_GRAPH} (BV19-3)"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --title) TITLE="$2"; shift 2 ;;
    --body-json) BODY_JSON="$2"; shift 2 ;;
    --parent) PARENTS+=("$2"); shift 2 ;;
    --idempotency-key) IDEM_KEY="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    *) die "unknown arg: $1" ;;
  esac
done

[[ -n "${TITLE}" ]] || die "--title required"
[[ -n "${BODY_JSON}" ]] || die "--body-json required"
[[ -f "${BODY_JSON}" ]] || die "body json not found: ${BODY_JSON}"
[[ -f "${DISPATCH_YAML}" ]] || die "missing ${DISPATCH_YAML}"
# Operator E-20260811T133000Z #5 — parent link + created_by=parent so
# Hermes created_cards verification accepts CLI creates (not tool-only).
[[ ${#PARENTS[@]} -gt 0 ]] || die "--parent REQUIRED (M2/planner task id) for created_cards attribution"
PARENT_PRIMARY="${PARENTS[0]}"

# Architect E-20260814T190216Z — create-time blocked is not durable if any
# parent is already done (HKN-2 auto-promote). Same PARENT_DONE gate as
# mint-m3-wave.sh so one-shot creates cannot bypass the wave wrapper.
_read_parent_status() {
  hermes kanban show "$1" --json 2>/dev/null \
    | python3 "${LINK_GRAPH}" --print status 2>/dev/null || true
}
if command -v hermes >/dev/null 2>&1; then
  for _p in "${PARENTS[@]}"; do
    [[ -n "${_p}" ]] || continue
    _ps="$(_read_parent_status "${_p}")"
    if [[ "${_ps}" == "done" || "${_ps}" == "archived" ]]; then
      die "PARENT_DONE: ${_p} status=${_ps} — PARK_AT_BIRTH children auto-promote (HKN-2). Do not --parent a done card; mint under a still-open wave holder."
    fi
    if [[ -z "${_ps}" ]]; then
      die "PARENT_DONE: ${_p} status unreadable — fail-closed (cannot prove parent is not done)"
    fi
  done
elif [[ "${DRY_RUN}" -eq 1 ]]; then
  echo "create-m3-implementer: PARENT_DONE guard skipped (no hermes on PATH)" >&2
fi

# D3 / Operator E-20260813T180236Z — persist partition story id on the card so
# "N/N done" is arithmetic (partition ids ⊆ completed titles), not assertion.
STORY_ID="$(python3 -c 'import json,sys
d=json.load(open(sys.argv[1], encoding="utf-8"))
ident=d.get("identity") if isinstance(d.get("identity"), dict) else {}
sid=(ident.get("story_id") or d.get("story_id") or "").strip()
print(sid)' "${BODY_JSON}")"
[[ -n "${STORY_ID}" ]] || die "identity.story_id required in body (Operator E-180236Z — persist story id on card)"
# Prefix title once: "S-003: REST controllers" (refuse if a different S-NNN already leads)
if [[ "${TITLE}" != "${STORY_ID}:"* && "${TITLE}" != "${STORY_ID} "* ]]; then
  if [[ "${TITLE}" =~ ^S-[0-9A-Za-z_-]+: ]]; then
    die "title already has story prefix but body identity.story_id=${STORY_ID}: ${TITLE}"
  fi
  TITLE="${STORY_ID}: ${TITLE}"
fi
echo "create-m3-implementer: story_id=${STORY_ID} title=${TITLE}" >&2

# Pre-v12 R0/R3 — tip sync proof before M3 create
python3 "${ROOT}/.hermes/skills/harness/dispatch-phase/scripts/check-create-path-tip-sync.py" "${ROOT}" \
  || die "create-path tip sync failed (R0/R3)"
python3 "${ROOT}/.hermes/skills/harness/dispatch-phase/scripts/check-phase-body-script-refs.py" "${ROOT}" \
  || die "phase body script refs failed (R0)"

# R-M3.32: materialize AD-011 overlays into Hermes skill tree before create
# CS-2: sync retired — overlays modify-in-place under skill references/ (W3)
# CS-2: sync retired — overlays modify-in-place under skill references/ (W3)

# Operator E-20260811T144200Z — dependencies + destination-inventory at create
python3 "${ROOT}/.hermes/skills/sdd/check-spec-readiness/scripts/stamp-body-dependencies.py" "${ROOT}" \
  --body "${BODY_JSON}" --write \
  || die "stamp-body-dependencies failed (assign orphan model/interface owners first)"
# Architect E-20260811T181749Z Class A — interface-closure before create
python3 "${ROOT}/.hermes/skills/sdd/check-spec-readiness/scripts/check-interface-closure.py" "${ROOT}" \
  --body "${BODY_JSON}" \
  || die "INTERFACE_CLOSURE: add missing interfaces to scope/deps/dest before create"
python3 "${ROOT}/.hermes/skills/sdd/check-spec-readiness/scripts/stamp-destination-inventory.py" "${ROOT}" \
  --body "${BODY_JSON}" --write \
  || die "stamp-destination-inventory failed"
# Partition coverage fail-closed before create (gate already tip-loaded)
python3 "${ROOT}/.hermes/skills/sdd/check-spec-readiness/scripts/check-partition-coverage.py" "${ROOT}" \
  --write-receipt evidence/receipts/partition-coverage/latest.json \
  || die "PARTITION_COVERAGE not VALID — remediate partition/bodies before create"

# Architect E-20260811T170706Z Class A — quarantine tombstones must survive create/dispatch
python3 "${ROOT}/.hermes/skills/sdd/check-spec-readiness/scripts/assert-quarantine-tombstones.py" "${ROOT}" \
  || die "quarantine tombstones resurrected — wipe + purge restorer before create (write-fence / quarantine tombstones)"

# EX-2: S-008 resurrection-order scar retired (not in golden scaffold)

# Architect E-20260811T200911Z Class A — mint-completeness (inject standard constraints
# when absent/empty; distinct from preservation). Refuse later if still empty.
python3 "${ROOT}/.hermes/skills/sdd/check-spec-readiness/scripts/assert-mint-constraints-complete.py" "${ROOT}" \
  --body "${BODY_JSON}" --inject \
  || die "MINT_COMPLETENESS inject failed for ${BODY_JSON}"
python3 "${ROOT}/.hermes/skills/sdd/check-spec-readiness/scripts/assert-mint-constraints-complete.py" "${ROOT}" \
  --body "${BODY_JSON}" \
  || die "MINT_COMPLETENESS: constraints still absent/empty (tag constraint_free if intentional)"
# F9 — wire constraints-preservation: snapshot after mint inject so later
# pre-dispatch amends cannot silently drop constraints (was callerless).
python3 "${ROOT}/.hermes/skills/sdd/check-spec-readiness/scripts/assert-constraints-preserved.py" "${ROOT}" \
  --body "${BODY_JSON}" --snapshot-before \
  || die "CONSTRAINTS_PRESERVATION snapshot-before failed for ${BODY_JSON}"

# Architect E-20260811T203657Z Class A — dependency/pre-exists closure
python3 "${ROOT}/.hermes/skills/sdd/check-spec-readiness/scripts/assert-dependency-closure.py" "${ROOT}" \
  --body "${BODY_JSON}" \
  || die "DEPENDENCY_CLOSURE: fix false pre-exists or absorb missing types into scope (.hermes/skills/sdd/check-spec-readiness/references/story-scope-and-exit.md)"

# Validate THE body being created (Operator E-20260811T124000Z) — not whole
# evidence/bodies/ (incomplete siblings must not block a single create).
# Whole-corpus lint remains available as: check-kanban-body.py "${ROOT}"
python3 "${ROOT}/.hermes/skills/sdd/check-spec-readiness/scripts/check-kanban-body.py" "${ROOT}" \
  --body "${BODY_JSON}" \
  || die "check-kanban-body failed for ${BODY_JSON} — fix typed body first"
# AD-002G P0.2 — refuse create if phase attach matrix drifts
python3 "${ROOT}/.hermes/skills/harness/dispatch-phase/scripts/check-phase-attach-matrix.py" "${ROOT}" \
  || die "phase attach matrix failed — fix .hermes/phase-dispatch.yaml skills[]"
# CS-7 / RW-3 — fail-closed if m3-implementer bundle lists unresolved skills
python3 "${ROOT}/.hermes/skills/harness/dispatch-phase/scripts/assert-bundle-skills-exist.py" "${ROOT}" \
  --bundle m3-implementer \
  || die "CS-7 bundle exists-assert failed — fix .hermes/home/skill-bundles/m3-implementer.yaml"

# Parse M3 max_runtime from yaml (LG7). skills[] is the allow-list pool, not
# attach-all-five — B-16 attaches check-spec-readiness + identity.operand_skills.
PHASE_READER="${ROOT}/.hermes/skills/harness/dispatch-phase/scripts/read-phase-dispatch.py"
MAX_RUNTIME="$(python3 "${PHASE_READER}" --yaml "${DISPATCH_YAML}" --phase M3 --print max_runtime_seconds)" \
  || die "phase-dispatch parse failed for M3"
mapfile -t SKILLS < <(python3 "${ROOT}/.hermes/skills/harness/dispatch-phase/scripts/m3-attach-skills.py" "${BODY_JSON}") \
  || die "B-16 attach skills failed for ${BODY_JSON}"

[[ ${#SKILLS[@]} -gt 0 ]] || die "B-16 attach set empty for ${BODY_JSON}"
[[ -n "${MAX_RUNTIME}" ]] || die "no M3 max_runtime_seconds"

# AD-010 §3b — optional per-story override when body stamps effort-high.
BODY_BUDGET="$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d.get("runtime_budget_sec") or "")' "${BODY_JSON}")"
if [[ -n "${BODY_BUDGET}" ]]; then
  MAX_RUNTIME="${BODY_BUDGET}"
  echo "create-m3-implementer: §3b runtime_budget_sec=${MAX_RUNTIME} from body" >&2
fi

# AR-4.3 — persist exact body digest before create (immutable input stamp)
BODY_DIGEST="$(python3 "${ROOT}/.hermes/skills/harness/record-run-evidence/scripts/stamp-body-digest.py" \
  "${BODY_JSON}" | tail -1)"
[[ -n "${BODY_DIGEST}" && "${#BODY_DIGEST}" -eq 64 ]] \
  || die "AR-4.3 stamp-body-digest failed for ${BODY_JSON}"

# AR-4.4 / AR-2.3–2.7 — lint the body being created (not the whole board)
python3 "${ROOT}/.hermes/skills/sdd/check-spec-readiness/scripts/check-surgical-scopes.py" "${ROOT}" "${BODY_JSON}" \
  || die "AR-4.4 surgical scopes failed for ${BODY_JSON}"
python3 "${ROOT}/.hermes/skills/sdd/check-spec-readiness/scripts/check-semantic-exits.py" "${ROOT}" "${BODY_JSON}" \
  || die "AR-2.3–2.7 semantic exits failed for ${BODY_JSON}"
# Architect E-104925Z / E-110403Z / E-111450Z — operand_count + wall-fit refuse
python3 "${ROOT}/.hermes/skills/sdd/check-spec-readiness/scripts/check-operand-count.py" "${ROOT}" "${BODY_JSON}" \
  --wall-fit \
  || die "BODY_SIZE operand-count/wall-fit failed for ${BODY_JSON}"
# L2 / SR-13 — refs + discriminating exit before create (task_id still story_id)
python3 "${ROOT}/.hermes/skills/sdd/check-spec-readiness/scripts/assert-mint-oracles.py" "${ROOT}" \
  --body "${BODY_JSON}" --skip-task-id \
  || die "MINT_ORACLES: refs/discriminating-exit refused ${BODY_JSON} (SR-13 / L2)"

# Human-readable markdown wrapper + attach typed JSON path as obligation.
# F6 — card ≤1500 chars; standing procedure lives in
# .hermes/skills/harness/dispatch-phase/references/m3-implementer-standing.md (not pasted ×N).
BODY_MD="$(mktemp)"
trap 'rm -f "${BODY_MD}"' EXIT
{
  echo "# ${TITLE}"
  echo
  echo "Phase: M3 per \`.hermes/phase-dispatch.yaml\` · Task-type: implementing"
  echo "Story id (partition): \`${STORY_ID}\`"
  echo "Typed body (W2 §6): \`${BODY_JSON}\`"
  echo "Body digest (AR-4.3): \`${BODY_DIGEST}\`"
  echo
  echo "## Job"
  echo "1. Read the typed body JSON first (\`exit_criteria\`, write-set, \`dependencies\`, \`refs\`)."
  echo "2. Verify digest: \`python3 .hermes/skills/harness/record-run-evidence/scripts/check-body-digest-match.py . --body ${BODY_JSON} --expect ${BODY_DIGEST}\` — mismatch ⇒ REFUSE."
  echo "3. Follow standing procedure (binding): \`.hermes/skills/harness/dispatch-phase/references/m3-implementer-standing.md\` — includes BANK-DEST-INV-HARDINVOKE-1 / \`refs.destination_inventory\`, Pre-v12 R5 hard-invoke traps, checkpoint/complete-cmd, DD3, wall/crash, AD-002 skills."
  echo "4. Write only \`files_writable\`. Satisfy every \`exit_criteria\` before complete."
  echo "5. Before \`kanban_complete\`: \`python3 .hermes/skills/gates/check-release-readiness/scripts/assert-complete-exit-criteria.py . --task-id <this-task-id> --body ${BODY_JSON}\`."
  echo
  echo "## Constraints"
  echo "- workspace: dir:${WORKSPACE_DIR}"
  echo "- Do not rewrite typed body or re-plan scope. Typed BLOCK if inputs wrong."
  echo "- max-runtime=${MAX_RUNTIME}s · no MiniMax (AD-008) · skills preload ≠ consultation (AD-002E)"
} >"${BODY_MD}"
CARD_CHARS="$(wc -c <"${BODY_MD}" | tr -d ' ')"
[[ "${CARD_CHARS}" -le 1500 ]] \
  || die "F6 card budget exceeded: ${CARD_CHARS} chars > 1500 (slim standing procedure; see m3-implementer-standing.md)"
echo "create-m3-implementer: F6 card_chars=${CARD_CHARS}/1500" >&2

# C-2(a) — single-persona. Product default is the worker identity (R-V14.10).
ASSIGNEE="$(
  python3 "${ROOT}/.hermes/skills/harness/dispatch-phase/scripts/resolve-seat-assignee.py" M3
)"
[[ -n "${ASSIGNEE}" ]] \
  || die "C-2(a): M3 assignee resolve failed"

# Deputy E-20260811T131900Z — M3 cards MUST be born parked. v12 lost v11
# born-parked behavior; create+dispatch let the daemon race M2 (serial breach).
# --initial-status blocked = human/gate unpark only (not todo/dispatchable).
# Operator E-20260811T133000Z #5 — created_by=parent task id (not the script
# name) so completing parent may list these ids in created_cards and pass
# Hermes _verify_created_cards (assignee/parent-id/link trust).
CREATE_ARGS=(
  --json
  --assignee "${ASSIGNEE}"
  --workspace "dir:${WORKSPACE_DIR}"
  --max-runtime "${MAX_RUNTIME}"
  --created-by "${PARENT_PRIMARY}"
  --initial-status blocked
  --body "$(cat "${BODY_MD}")"
)
[[ -n "${IDEM_KEY}" ]] && CREATE_ARGS+=(--idempotency-key "${IDEM_KEY}")
for s in "${SKILLS[@]}"; do
  CREATE_ARGS+=(--skill "${s}")
done
for p in "${PARENTS[@]:-}"; do
  [[ -n "${p}" ]] && CREATE_ARGS+=(--parent "${p}")
done

echo "create-m3-implementer: assignee=${ASSIGNEE} skills=${SKILLS[*]} max_runtime=${MAX_RUNTIME}s body=${BODY_JSON}"
if [[ "${DRY_RUN}" -eq 1 ]]; then
  printf '  %q' hermes kanban create "${CREATE_ARGS[@]}" "${TITLE}"
  echo
  exit 0
fi

command -v hermes >/dev/null 2>&1 || die "hermes not on PATH"
hermes profile show "${ASSIGNEE}" >/dev/null 2>&1 \
  || die "C-2(a): assignee profile '${ASSIGNEE}' missing (dispatcher would silent-fail)"
cd "${WORKSPACE_DIR}"
OUT="$(hermes kanban create "${CREATE_ARGS[@]}" "${TITLE}")"
echo "${OUT}"
TASK_ID="$(python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("id") or "")' <<<"${OUT}")"
[[ -n "${TASK_ID}" ]] || die "kanban create returned no id"
for p in "${PARENTS[@]:-}"; do
  [[ -n "${p}" ]] || continue
  hermes kanban show "${TASK_ID}" --json \
    | python3 "${LINK_GRAPH}" --expect-parent "${p}" \
    || die "BV19-3: ${TASK_ID} missing parent link ${p}"
done
mkdir -p "${ROOT}/evidence/derived"
echo "${TASK_ID}" >"${ROOT}/evidence/derived/phase-M3-task-id.txt"
# Operator E-20260813T180236Z — story↔card map for completion arithmetic
python3 - "${ROOT}/evidence/derived/created-story-cards.json" "${STORY_ID}" "${TASK_ID}" "${TITLE}" "${BODY_JSON}" <<'PY'
import json, sys
from pathlib import Path
path, story, task, title, body = Path(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5]
data = {"schema": "rhoai3.created-story-cards/v1", "cards": []}
if path.is_file():
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pass
cards = data.setdefault("cards", [])
cards = [c for c in cards if not (isinstance(c, dict) and c.get("task_id") == task)]
cards.append({"story_id": story, "task_id": task, "title": title, "body": body})
data["cards"] = cards
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
print(f"OK: story-card map {story} -> {task}")
PY
# Architect E-20260811T200911Z Class A — park-at-birth fail-closed.
# Parent may already be done → Hermes auto-promotes dependency children to ready.
# Force harness park with kind=dependency (B-6: must not spend needs_input
# recurrence). Verify; never emit ack-request for dispatchable mint.
# Architect E-20260811T200911Z Class A — park-at-birth fail-closed.
# Parent may already be done → Hermes auto-promotes dependency children to ready.
# Force dependency park (CLI + sqlite fallback) and verify; never emit ack for ready.
_read_status() {
  hermes kanban show "$1" --json 2>/dev/null | python3 -c 'import json,sys
try:
  d=json.load(sys.stdin)
  t=d.get("task") if isinstance(d.get("task"), dict) else d
  print((t.get("status") or "").lower())
except Exception:
  print("")' || true
}
_park_status="$(_read_status "${TASK_ID}")"
if [[ "${_park_status}" != "blocked" && "${_park_status}" != "triage" ]]; then
  # Prefer CLI; --kind before task_id (Hermes argparse). Fallback: sqlite.
  # B-6: harness park uses kind=dependency so it does not spend the worker
  # needs_input recurrence budget (v19 S-005 serial_park consumed recurrence 1).
  hermes kanban block --kind dependency "${TASK_ID}" park-at-birth >/dev/null 2>&1 || true
  _park_status="$(_read_status "${TASK_ID}")"
fi
if [[ "${_park_status}" != "blocked" && "${_park_status}" != "triage" ]]; then
  python3 - "${HERMES_HOME}/kanban.db" "${TASK_ID}" <<'PY' || true
import sqlite3, sys
db, tid = sys.argv[1], sys.argv[2]
conn = sqlite3.connect(db)
conn.execute("UPDATE tasks SET status=? WHERE id=?", ("blocked", tid))
conn.commit()
conn.close()
print(f"OK: sqlite park-at-birth {tid} -> blocked")
PY
  _park_status="$(_read_status "${TASK_ID}")"
fi
if [[ "${_park_status}" == "ready" || "${_park_status}" == "todo" || "${_park_status}" == "running" || -z "${_park_status}" ]]; then
  die "PARK_AT_BIRTH: ${TASK_ID} status=${_park_status:-unknown} still dispatchable after create — refuse mint (park-at-birth)"
fi
echo "PARK_AT_BIRTH=${TASK_ID} status=${_park_status}"
# Phase 5 run-audit — create is not a Hermes kanban hook. Fail-open.
bash "${ROOT}/.hermes/skills/harness/record-run-evidence/scripts/snapshot-card-boundary.sh" create || true
# SR-9 / Deputy E-20260814T214613Z — body.task_id := Hermes card id (not story-001).
# Digest restamp after the write; replace AR-4.3 hex in the card markdown.
BODY_DIGEST="$(python3 - "${BODY_JSON}" "${TASK_ID}" "${HERMES_HOME}/kanban.db" "${BODY_DIGEST}" <<'PY'
import hashlib, json, sqlite3, sys
from pathlib import Path
body_path, tid, db, old = Path(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4]
doc = json.loads(body_path.read_text(encoding="utf-8"))
doc["task_id"] = tid
body_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
new = hashlib.sha256(body_path.read_bytes()).hexdigest()
dbp = Path(db)
if old and new != old and dbp.is_file():
    conn = sqlite3.connect(str(dbp))
    row = conn.execute("select body from tasks where id=?", (tid,)).fetchone()
    if row and isinstance(row[0], str) and old in row[0]:
        conn.execute("UPDATE tasks SET body=? WHERE id=?", (row[0].replace(old, new), tid))
        conn.commit()
    conn.close()
print(new)
PY
)"
[[ -n "${BODY_DIGEST}" && "${#BODY_DIGEST}" -eq 64 ]] \
  || die "SR-9 bind body.task_id=${TASK_ID} failed to restamp digest"
python3 "${ROOT}/.hermes/skills/harness/record-run-evidence/scripts/stamp-body-digest.py" \
  "${BODY_JSON}" >/dev/null \
  || die "AR-4.3 restamp after task_id bind failed for ${BODY_JSON}"
echo "BODY_TASK_ID_BOUND=${TASK_ID} digest=${BODY_DIGEST}"
python3 "${ROOT}/.hermes/skills/sdd/check-spec-readiness/scripts/assert-mint-oracles.py" "${ROOT}" \
  --body "${BODY_JSON}" --expect-task-id "${TASK_ID}" \
  || die "MINT_ORACLES: post-bind task_id/refs/exit refused ${BODY_JSON} (SR-13 / L2)"
# Operator E-20260811T114300Z — Review live adherence observation on every dispatch
{
  echo "schema: rhoai3.review-adhere-observe-need/v1"
  echo "task_id: ${TASK_ID}"
  echo "phase: M3"
  echo "need: Review:adhere-observe-${TASK_ID}"
  echo "operator_event: E-20260811T114300Z"
  date -u +'ts: %Y-%m-%dT%H:%M:%SZ'
} >"${ROOT}/evidence/derived/review-adhere-observe-needed.yaml"
echo "REVIEW_ADHERE_OBSERVE=${TASK_ID}"
# Do NOT dispatch here — cards are born blocked; unpark is gate-driven
# (M2 ledger PASS + brief-identity ack + serial order). Deputy E-131900Z.
hermes kanban comment "${TASK_ID}" \
  "born-parked: initial-status=blocked + park-at-birth verify; unpark only after M2 PASS + brief-identity ack + serial GO (Deputy E-20260811T131900Z / Architect E-20260811T200911Z)" \
  >/dev/null 2>&1 || true
# Stamp derived claim list for parent completion (Operator E-133000Z #5)
# F8a: stamp carries story_id so claim can compare to partition (not self).
STORY_ID="$(python3 -c 'import json,sys,pathlib
p=pathlib.Path(sys.argv[1])
d=json.load(open(p))
sid=(d.get("identity") or {}).get("story_id") or d.get("story_id") or ""
print(sid)' "${BODY_JSON}")"
[[ -n "${STORY_ID}" ]] || die "missing identity.story_id in ${BODY_JSON} (SR-9 — no filename fallback)"
DERIVED_DIR="${ROOT}/evidence/derived"
mkdir -p "${DERIVED_DIR}"
CLAIM_FILE="${DERIVED_DIR}/created-cards-${PARENT_PRIMARY}.json"
python3 - "${CLAIM_FILE}" "${PARENT_PRIMARY}" "${TASK_ID}" "${BODY_DIGEST}" "${STORY_ID}" <<'PY'
import json, sys, pathlib, datetime
path, parent, tid, digest, story = sys.argv[1:6]
p = pathlib.Path(path)
cards = []
if p.is_file():
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        cards = list(data.get("cards") or [])
    except Exception:
        cards = []
ids = {c.get("id") for c in cards if isinstance(c, dict)}
if tid not in ids:
    cards.append({
        "id": tid,
        "story_id": story,
        "body_sha256": digest,
        "created_by": parent,
    })
else:
    for c in cards:
        if isinstance(c, dict) and c.get("id") == tid:
            c.setdefault("story_id", story)
            c["body_sha256"] = digest
out = {
    "schema": "rhoai3.created-cards-claim/v1",
    "parent": parent,
    "cards": cards,
    "updated_at": datetime.datetime.now(datetime.timezone.utc)
    .strftime("%Y-%m-%dT%H:%M:%SZ"),
}
p.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
print(path)
PY
echo "CREATED_CARDS_CLAIM=${CLAIM_FILE}"

# F8a (Deputy E-20260813T221456Z): claim vs partition (subset during incremental mint).
# Full set equality is enforced at M2 parent complete (assert-m2b + enforce).
python3 "${ROOT}/.hermes/skills/harness/dispatch-phase/scripts/check-created-cards-claim.py" \
  --root "${ROOT}" --parent "${PARENT_PRIMARY}" --mode subset \
  || die "CREATED_CARDS_CLAIM partition-subset failed after stamp (E-20260813T221456Z F8a)"

# Architect E-20260811T155332Z Class A — atomic create→digest→ack-request
# (freeze exception). Emit unsigned ack-request so Operator/Deputy signs
# without hand-copying digests; dispatch still verifies ack↔card↔live (AR-4.3).
# Body digests are finalized above (stamps + stamp-body-digest) before create.
PARTITION_JSON="${ROOT}/evidence/briefs/partition.json"
[[ -f "${PARTITION_JSON}" ]] || die "missing ${PARTITION_JSON} for ack-request"
PARTITION_DIGEST="$(python3 -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "${PARTITION_JSON}")"
ACK_DIR="${ROOT}/evidence/acks"
mkdir -p "${ACK_DIR}"
# sanitize story id for filename (S-002a → S-002a)
ACK_REQ="${ACK_DIR}/ack-request-${STORY_ID}.yaml"
{
  echo "kind: migration-ack-request"
  echo "ack_type: brief-identity"
  echo "status: unsigned"
  echo "schema: rhoai3.ack-request/v1"
  echo "story_id: ${STORY_ID}"
  echo "task_id: ${TASK_ID}"
  echo "created_at: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "artifact_refs:"
  echo "  - story_id: ${STORY_ID}"
  echo "  - path: ${BODY_JSON}"
  echo "    sha256: ${BODY_DIGEST}"
  echo "  - path: evidence/briefs/partition.json"
  echo "    sha256: ${PARTITION_DIGEST}"
  echo "notes: \"Architect E-20260811T155332Z Class A atomic create→ack-request; Operator/Deputy signs by completing into brief-identity ack (no hand-copied digests)\""
} >"${ACK_REQ}"
echo "ACK_REQUEST=${ACK_REQ}"
echo "ACK_REQUEST_DIGESTS body=${BODY_DIGEST} partition=${PARTITION_DIGEST} task_id=${TASK_ID} story_id=${STORY_ID}"

# Operator E-20260812T061639Z / Architect E-20260812T061718Z Class A —
# card↔sidecar digest cross-assert at ack-regen choke point (refuse dead digests).
python3 "${ROOT}/.hermes/skills/harness/record-run-evidence/scripts/assert-card-body-digest-match.py" \
  "${ROOT}" --task-id "${TASK_ID}" --body "${BODY_JSON}" \
  || die "card↔sidecar digest cross-assert REFUSE for ${TASK_ID} (.hermes/skills/sdd/check-spec-readiness/references/body-integrity.md)"

echo "OK: M3 → ${TASK_ID} (blocked/parked; parent=${PARENT_PRIMARY}). File ledger Need Review:adhere-observe-${TASK_ID}"
echo "NOTE: parent must kanban_complete with created_cards including ${TASK_ID} (empty list REJECT)"
echo "NOTE: Operator ack-after-create via ${ACK_REQ} (unsigned → brief-identity ack); then Lead reverify + Architect §3a before dispatch"
