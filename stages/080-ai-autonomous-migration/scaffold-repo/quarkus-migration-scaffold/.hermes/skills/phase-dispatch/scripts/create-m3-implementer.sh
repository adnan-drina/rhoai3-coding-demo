#!/usr/bin/env bash
# Create an M3 implementer Kanban task with skills from phase-dispatch.yaml
# and a W2 §6 typed body (not a pointer to tasks.md).
#
# Usage:
#   bash .hermes/skills/phase-dispatch/scripts/create-m3-implementer.sh \
#     --title "M3 IMPLEMENT: Owner Management" \
#     --body-json migration/bodies/m3-001-owner.json \
#     [--parent t_xxx] [--idempotency-key KEY]
#
# Body JSON must satisfy check-kanban-body.py (phase=M3, refs[], files_in_scope,
# exit_criteria[] — Deputy E-20260809T190500Z completion half).
# Do NOT use bare `hermes kanban create` for M3 — that path omits skills
# (Review grounding study 20260809: M3 workers loaded zero skills).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
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

# Pre-v12 R0/R3 — tip sync proof before M3 create
python3 "${ROOT}/.hermes/skills/phase-dispatch/scripts/check-create-path-tip-sync.py" "${ROOT}" \
  || die "create-path tip sync failed (R0/R3)"
python3 "${ROOT}/.hermes/skills/phase-dispatch/scripts/check-phase-body-script-refs.py" "${ROOT}" \
  || die "phase body script refs failed (R0)"

# R-M3.32: materialize AD-011 overlays into Hermes skill tree before create
python3 "${ROOT}/.hermes/skills/phase-dispatch/scripts/sync-extension-overlays-into-skills.py" "${ROOT}" \
  || die "sync-extension-overlays-into-skills failed"
python3 "${ROOT}/.hermes/skills/phase-dispatch/scripts/sync-extension-overlays-into-skills.py" "${ROOT}" --check \
  || die "R-M3.32: extension overlays missing from .hermes/skills/*/references/ (skill_view will fail)"

# Validate THE body being created (Operator E-20260811T124000Z) — not whole
# migration/bodies/ (incomplete siblings must not block a single create).
# Whole-corpus lint remains available as: check-kanban-body.py "${ROOT}"
python3 "${ROOT}/.hermes/skills/sdd-readiness/scripts/check-kanban-body.py" "${ROOT}" \
  --body "${BODY_JSON}" \
  || die "check-kanban-body failed for ${BODY_JSON} — fix typed body first"
# AD-002G P0.2 — refuse create if phase attach matrix drifts
python3 "${ROOT}/.hermes/skills/phase-dispatch/scripts/check-phase-attach-matrix.py" "${ROOT}" \
  || die "phase attach matrix failed — fix .hermes/phase-dispatch.yaml skills[]"

# Parse M3 skills + max_runtime from yaml
eval "$(python3 - "${DISPATCH_YAML}" <<'PY'
import re, sys
text = open(sys.argv[1], encoding="utf-8").read().splitlines()
in_m3 = False
skills = []
max_rt = ""
in_skills = False
for ln in text:
    if re.match(r"^  M3:\s*$", ln):
        in_m3 = True
        continue
    if in_m3 and re.match(r"^  [A-Za-z0-9_]+:\s*$", ln) and not ln.startswith("  M3"):
        break
    if not in_m3:
        continue
    if re.match(r"^    skills:\s*$", ln):
        in_skills = True
        continue
    if in_skills:
        m = re.match(r"^      - (\S+)\s*$", ln)
        if m:
            skills.append(m.group(1))
            continue
        if ln.strip() and not ln.startswith("      "):
            in_skills = False
    m = re.match(r"^    max_runtime_seconds:\s*(\d+)\s*$", ln)
    if m:
        max_rt = m.group(1)
print(f"SKILLS=({' '.join(skills)})")
print(f"MAX_RUNTIME={max_rt or '2700'}")
PY
)"

[[ ${#SKILLS[@]} -gt 0 ]] || die "no M3 skills parsed from phase-dispatch.yaml"
[[ -n "${MAX_RUNTIME}" ]] || die "no M3 max_runtime_seconds"

# AD-010 §3b — optional per-story override when body stamps effort-high.
BODY_BUDGET="$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d.get("runtime_budget_sec") or "")' "${BODY_JSON}")"
if [[ -n "${BODY_BUDGET}" ]]; then
  MAX_RUNTIME="${BODY_BUDGET}"
  echo "create-m3-implementer: §3b runtime_budget_sec=${MAX_RUNTIME} from body" >&2
fi

# AR-4.3 — persist exact body digest before create (immutable input stamp)
BODY_DIGEST="$(python3 "${ROOT}/.hermes/skills/auditability-repeatability/scripts/stamp-body-digest.py" \
  "${BODY_JSON}" | tail -1)"
[[ -n "${BODY_DIGEST}" && "${#BODY_DIGEST}" -eq 64 ]] \
  || die "AR-4.3 stamp-body-digest failed for ${BODY_JSON}"

# AR-4.4 / AR-2.3–2.7 — lint the body being created (not the whole board)
python3 "${ROOT}/.hermes/skills/sdd-readiness/scripts/check-surgical-scopes.py" "${ROOT}" "${BODY_JSON}" \
  || die "AR-4.4 surgical scopes failed for ${BODY_JSON}"
python3 "${ROOT}/.hermes/skills/sdd-readiness/scripts/check-semantic-exits.py" "${ROOT}" "${BODY_JSON}" \
  || die "AR-2.3–2.7 semantic exits failed for ${BODY_JSON}"
# Architect E-104925Z / E-110403Z / E-111450Z — operand_count + wall-fit refuse
python3 "${ROOT}/.hermes/skills/sdd-readiness/scripts/check-operand-count.py" "${ROOT}" "${BODY_JSON}" \
  --wall-fit \
  || die "BODY_SIZE operand-count/wall-fit failed for ${BODY_JSON}"

# Human-readable markdown wrapper + attach typed JSON path as obligation
BODY_MD="$(mktemp)"
trap 'rm -f "${BODY_MD}"' EXIT
{
  echo "# ${TITLE}"
  echo
  echo "Phase: M3 per \`.hermes/phase-dispatch.yaml\`"
  echo "Role: implementer"
  echo "Typed body (W2 §6): \`${BODY_JSON}\`"
  echo "Body digest (AR-4.3): \`${BODY_DIGEST}\`"
  echo
  echo "## Obligation"
  echo "Read the typed body JSON path above first (\`exit_criteria\`, \`files_in_scope\`/\`files_writable\`, \`refs\`)."
  echo "Verify body sha256 matches \`${BODY_DIGEST}\` before first destination edit; retries must reuse this digest."
  echo "**Body immutability (Architect E-111424Z):** do **not** rewrite the typed body after dispatch. Run \`python3 .hermes/skills/auditability-repeatability/scripts/check-body-digest-match.py . --body ${BODY_JSON} --expect ${BODY_DIGEST}\` — mismatch ⇒ REFUSE (\`migration/contracts/body-immutability.md\`)."
  echo "Record pre/post write-set digests under \`migration/runs/\` (schema \`rhoai3.run-journal/v1\`)."
  echo "**Checkpoint/resume (S-010 Class A #3):** before first edit, init or load \`migration/runs/<task_id>/checkpoint.json\` (\`init-implementer-checkpoint.py\` / \`check-implementer-checkpoint.py\`). After each successful dest write, \`stamp-implementer-checkpoint.py --completed <path>\`. On retry/re-dispatch: resume at \`next\` — do **not** cold re-walk completed operands (\`migration/contracts/implementer-checkpoint.md\`)."
  echo "Do NOT bulk-read all files_in_scope in one turn — migrate file-by-file (prefer \`next\` from checkpoint)."
  echo "Satisfy every \`exit_criteria\` item before \`kanban_complete\` (endpoint/semantic exits required — AR-4.4)."
  echo "**In-loop testCompile invariant (S-010 Class A #1b / Deputy E-115113Z):** \`stamp-implementer-checkpoint.py --completed src/test/**\` **REFUSE**s unless \`run-test-compile-gate.py\` (\`mvn -q test-compile\`) is green for that advance — not advisory prose. Red compile ⇒ fix before stamp/next. Scaffold ships assertj-core + rest-assured (\`migration/contracts/test-toolchain.md\`)."
  echo "**Wall / requeue (Architect E-110403Z / E-121300Z):** on \`timed_out\`, run \`apply-wall-requeue-policy.py\` (exit-eval + checkpoint sync; soft K=1 then hard-block). Unbounded silent requeue REJECT (\`migration/contracts/wall-exit-eval.md\`)."
  echo "**Crash / reclaim (Architect E-20260810T142650Z):** on \`crashed\`, run \`apply-crash-requeue-policy.py\` (K_crash=1; does not spend wall soft-K). Hard ceiling → typed \`harness_fault\`/\`environmental_provider\`/\`context_budget\` — never budget/timed_out (\`migration/contracts/crash-requeue.md\`)."
  echo "**R-M3.5/7 POM handoff (Architect E-20260810T172800Z):** before first destination edit on JPA/model stories, run \`python3 .hermes/skills/sdd-readiness/scripts/check-compile-deps-preflight.py .\` — fail ⇒ typed \`dependency_wait\` (no N-file sunk cost). Scaffold/S-001-class must leave \`quarkus-hibernate-orm\` + \`quarkus-hibernate-validator\` (\`migration/contracts/pom-persistence-handoff.md\`)."
  echo "**R-M3.6/8 dependency_wait (Architect E-20260810T172800Z):** on \`dependency_wait\`, do **not** soft-promote or OOS-edit \`pom.xml\`. Stamp/hold via \`apply-dependency-wait-hold.py --stamp --block\`; escalate \`Needs: Lead:fix-upstream-pom\`. After typed wait, **forbid** re-litigating \`files_writable\` in Reasoning — wait or escalate."
  echo "**R-M3.9 wall-fit (Architect E-20260810T184700Z):** create path refuses FIS×90s > budget and dual-stack JPA+JDBC ≥20 — prefer JPA-repos vs JDBC-repos split; do **not** raise wall alone (\`migration/contracts/m3-wallfit-jdbc.md\` / \`story-sizing.md\`)."
  echo "**R-M3.10/12 JDBC (Architect E-20260810T184700Z):** before first \`repository/jdbc/**\` edit — \`skill_view\` persistence (+ jdbc notes); write-first mechanical transforms; **forbid** multi-kB Spring-replacement redesign essays in Reasoning."
  echo "**R-M3.11 JDBC deps:** run \`python3 .hermes/skills/sdd-readiness/scripts/check-jdbc-deps-preflight.py .\` before first JDBC write — require \`spring-jdbc\` + \`spring-data-jdbc-core\` (no OOS pom)."
  echo "**R-M3.13 lean reclaim (FIS≥20):** on soft reclaim, resume from checkpoint \`next\` only — do **not** re-bulk-read all legacy JDBC/JPA sources."
  echo "**AD-011 / R-AD011.2 overlay (Architect E-20260810T185500Z):** author overlays under \`extensions/<skill>/references/*\`; create path syncs them into \`.hermes/skills/<skill>/references/\` (R-M3.32). \`skill_view\` in-skill \`references/<file>\` after sync. Never SOUL. See \`migration/contracts/ad011-skill-extension.md\` + \`m3-security-write-first.md\`."
  echo "**R-M3.29/32/39 security write-first:** before first \`security/**\` edit — hard \`skill_view\` \`references/security-config.md\` **and** \`references/security-anti-essay.md\` (Hermes skill tree; create refuses if sync/--check fails); write-first / anti-essay; stamp after each dest write. **R-M3.39:** javadoc-only shells FAIL — land pom (\`quarkus-security\` + \`quarkus-elytron-security-jdbc\`) + \`application.properties\` auth wiring; \`check-empty-security.py .\` must be rc=0 before complete."
  echo "**R-M3.28/31 wall narrative (Architect E-20260810T230310Z):** exit-eval credits AD-009 freeze/>300s latency; \`overall_ok=false\` when wallish + incomplete checkpoint (compile-only green ≠ product PASS)."
  echo "**Checkpoint lag (Deputy E-121112Z):** after \`src/test/**\` writes — and on every wall — run \`sync-checkpoint-from-test-writes.py\` so stamp/#1b gate is harness-driven, not voluntary."
  echo "**AD-002E/F/G:** preloaded skills are \`sdd-readiness\` + \`spring-to-quarkus-patterns\` only. Each → \`skill_view\` consult **or** typed \`skills_unused:<skill>:<reason>\` before \`kanban_complete\`. Silence invalid; no false \"skills consulted\" claim."
  echo "**Hard invoke (AD-002G P0.3):** run \`/spring-to-quarkus-patterns\` (or equivalent \`skill_view\` on that skill) before first destination edit; then open needed \`references/*\` (rest / di-config / persistence / testing / security-config). For security cards also open the R-M3.29 extension. For S-010/test work open \`references/testing.md\` §Failure/Import/Mock procedures + golden fixture \`migration/fixtures/testing/golden-rest-controller/PetTypeRestControllerTests.java\`."
  echo "**Pre-v12 R5 hard-invoke traps (Architect E-20260811T102405Z):** when story touches REST/DTO/MapStruct — \`skill_view\` \`references/di-config.md\` and set MapStruct \`componentModel = \"cdi\"\` (no default/spring). When story touches \`@IfBuildProfile\` / profile-gated beans — forbid that API; use \`%profile\` config / build-time alternatives per di-config. When story touches QuarkusTest / continuous testing props — \`skill_view\` \`references/testing.md\` continuous-testing enum (boolean props FAIL). Cite the ref path in Reasoning before first related dest write."
  echo "**Pre-flight ceiling (AD-002 §1 / AD-009 §3.5):** before large API turns, refuse emit when \`prompt_tokens + max_tokens > max-model-len\` via \`check-preflight-ceiling.py\` (stamp \`context_budget\` on refuse). Do **not** discover the ceiling via \`VLLMValidationError\`."
  echo "**F3–F6 predictions (when body carries them):** score \`injectmock_reasoning_blocks\` / \`import_hunt\` / reasoning-share gates at terminal — Architect ACCEPT \`E-20260810T131445Z\`; missing scores ⇒ cannot claim skill-guide DEMONSTRATED."
  echo "Progressive disclosure — do not bulk-paste skill bodies. Run: \`python3 .hermes/skills/sdd-readiness/scripts/check-kanban-body.py /projects/modernized\`"
  echo
  # Do NOT inline the typed JSON here — it bloated M3 prompts to ~30k before any
  # tool use (v10 S-001 hang at API#4 in=62473). Path above is authoritative.
  echo "## Constraints"
  echo "- workspace: dir:${WORKSPACE_DIR}"
  echo "- Do not re-plan scope. Typed BLOCK if inputs wrong."
  echo "- Write only \`files_writable\` / destination write-set (AR-4.4); readable deps are not write authority."
  echo "- **AD-009:** max-runtime=${MAX_RUNTIME}s; no MiniMax (AD-008)."
  echo "- Skills preload ≠ consultation (AD-002D/E) — consult or typed unused."
} >"${BODY_MD}"

# Deputy E-20260811T131900Z — M3 cards MUST be born parked. v12 lost v11
# born-parked behavior; create+dispatch let the daemon race M2b (serial breach).
# --initial-status blocked = human/gate unpark only (not todo/dispatchable).
CREATE_ARGS=(
  --json
  --assignee default
  --workspace "dir:${WORKSPACE_DIR}"
  --max-runtime "${MAX_RUNTIME}"
  --created-by create-m3-implementer
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

echo "create-m3-implementer: skills=${SKILLS[*]} max_runtime=${MAX_RUNTIME}s body=${BODY_JSON}"
if [[ "${DRY_RUN}" -eq 1 ]]; then
  printf '  %q' hermes kanban create "${CREATE_ARGS[@]}" "${TITLE}"
  echo
  exit 0
fi

command -v hermes >/dev/null 2>&1 || die "hermes not on PATH"
cd "${WORKSPACE_DIR}"
OUT="$(hermes kanban create "${CREATE_ARGS[@]}" "${TITLE}")"
echo "${OUT}"
TASK_ID="$(python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("id") or "")' <<<"${OUT}")"
[[ -n "${TASK_ID}" ]] || die "kanban create returned no id"
mkdir -p "${ROOT}/migration/derived"
echo "${TASK_ID}" >"${ROOT}/migration/derived/phase-M3-task-id.txt"
# Operator E-20260811T114300Z — Review live adherence observation on every dispatch
{
  echo "schema: rhoai3.review-adhere-observe-need/v1"
  echo "task_id: ${TASK_ID}"
  echo "phase: M3"
  echo "need: Review:adhere-observe-${TASK_ID}"
  echo "operator_event: E-20260811T114300Z"
  date -u +'ts: %Y-%m-%dT%H:%M:%SZ'
} >"${ROOT}/migration/derived/review-adhere-observe-needed.yaml"
echo "REVIEW_ADHERE_OBSERVE=${TASK_ID}"
# Do NOT dispatch here — cards are born blocked; unpark is gate-driven
# (M2b ledger PASS + brief-identity ack + serial order). Deputy E-131900Z.
hermes kanban comment "${TASK_ID}" \
  "born-parked: initial-status=blocked; unpark only after M2b PASS + brief-identity ack + serial GO (Deputy E-20260811T131900Z)" \
  >/dev/null 2>&1 || true
echo "OK: M3 → ${TASK_ID} (blocked/parked). File ledger Need Review:adhere-observe-${TASK_ID}"
