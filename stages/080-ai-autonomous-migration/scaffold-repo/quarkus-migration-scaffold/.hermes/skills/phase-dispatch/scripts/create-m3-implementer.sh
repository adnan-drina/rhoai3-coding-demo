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

# Human-readable markdown wrapper + attach typed JSON path as obligation
BODY_MD="$(mktemp)"
trap 'rm -f "${BODY_MD}"' EXIT
{
  echo "# ${TITLE}"
  echo
  echo "Phase: M3 per \`.hermes/phase-dispatch.yaml\`"
  echo "Role: implementer"
  echo "Typed body (W2 §6): \`${BODY_JSON}\`"
  echo
  echo "## Obligation"
  echo "Execute only the files_in_scope and refs in the typed body."
  echo "Satisfy every \`exit_criteria\` item before \`kanban_complete\`."
  echo "Consult grounded-generation + spring-to-quarkus-patterns before edits."
  echo "Run: \`python3 .hermes/skills/sdd-readiness/scripts/check-kanban-body.py /projects/modernized\`"
  echo
  echo "## Typed body (inline copy for worker)"
  echo '```json'
  cat "${BODY_JSON}"
  echo '```'
  echo
  echo "## Constraints"
  echo "- workspace: dir:${WORKSPACE_DIR}"
  echo "- Do not re-plan scope. Typed BLOCK if inputs wrong."
  echo "- **AD-009:** max-runtime=${MAX_RUNTIME}s; no MiniMax (AD-008)."
  echo "- Skills are preloaded via dispatch — use skill_view / skill scripts."
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
