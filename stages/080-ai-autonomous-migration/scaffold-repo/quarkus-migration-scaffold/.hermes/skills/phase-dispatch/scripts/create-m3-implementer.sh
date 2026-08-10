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

# Validate typed body before create
python3 "${ROOT}/.hermes/skills/sdd-readiness/scripts/check-kanban-body.py" "${ROOT}" \
  || die "check-kanban-body failed — fix typed body first"
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
  echo "Record pre/post write-set digests under \`migration/runs/\` (schema \`rhoai3.run-journal/v1\`)."
  echo "Do NOT bulk-read all files_in_scope in one turn — migrate file-by-file."
  echo "Satisfy every \`exit_criteria\` item before \`kanban_complete\` (endpoint/semantic exits required — AR-4.4)."
  echo "**In-loop testCompile (S-010 Class A):** if writing \`src/test/**\`, run \`mvn -q test-compile\` after each batch of test writes; red compile is a typed terminal/fix — do **not** proceed to \`kanban_complete\` with a corpus that does not compile. Scaffold ships assertj-core + rest-assured (\`migration/contracts/test-toolchain.md\`)."
  echo "**AD-002E/F/G:** preloaded skills are \`sdd-readiness\` + \`spring-to-quarkus-patterns\` only. Each → \`skill_view\` consult **or** typed \`skills_unused:<skill>:<reason>\` before \`kanban_complete\`. Silence invalid; no false \"skills consulted\" claim."
  echo "**Hard invoke (AD-002G P0.3):** run \`/spring-to-quarkus-patterns\` (or equivalent \`skill_view\` on that skill) before first destination edit; then open needed \`references/*\` (rest / di-config / persistence / testing / security-config)."
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

CREATE_ARGS=(
  --json
  --assignee default
  --workspace "dir:${WORKSPACE_DIR}"
  --max-runtime "${MAX_RUNTIME}"
  --created-by create-m3-implementer
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
