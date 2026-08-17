#!/usr/bin/env bash
# AD-S — provision-time spec-kit init for the migration workspace (modernized).
#
# Runs in /projects/modernized (or $1). Does NOT commit .specify/ into the
# golden scaffold — it creates .specify/ in the live workspace only.
#
#   specify init --here --integration hermes --force --ignore-agent-tools
#   + Non-Goals override from this skill's assets/spec-template.md
#   + external_dirs reminder when HERMES_HOME is relocated
#
# Idempotent: skips when .specify/.rhoai3-ads-provisioned exists.
set -euo pipefail

# --dry-run as first arg or DRY_RUN=1: print plan and exit 0 before installs.
if [[ "${1:-}" == "--dry-run" ]]; then
  shift
  DRY_RUN=1
fi
DRY_RUN="${DRY_RUN:-0}"

ROOT="$(cd "${1:-.}" && pwd)"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# Skill root = parent of scripts/ (self-contained asset home — Deputy E-172448Z).
SKILL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ASSET_OVERRIDE="${SKILL_DIR}/assets/spec-template.md"
ASSET_TASKS="${SKILL_DIR}/assets/tasks-template.md"
ASSET_CONSTITUTION="${SKILL_DIR}/assets/constitution.md"
ASSET_OVERLAY="${SKILL_DIR}/assets/stop-before-implement.overlay.yml"
# Workspace tip may also carry the skill under ROOT/.hermes/skills/... when
# HERMES_SKILL_DIR is not this SCRIPT_DIR tree (relocated home copy).
  if [ ! -f "${ASSET_OVERRIDE}" ]; then
    ALT="${ROOT}/.hermes/skills/sdd/init-spec-workspace/assets/spec-template.md"
    if [ -f "${ALT}" ]; then
      ASSET_OVERRIDE="${ALT}"
      SKILL_DIR="$(cd "$(dirname "${ALT}")/.." && pwd)"
      ASSET_TASKS="${SKILL_DIR}/assets/tasks-template.md"
      ASSET_CONSTITUTION="${SKILL_DIR}/assets/constitution.md"
      ASSET_OVERLAY="${SKILL_DIR}/assets/stop-before-implement.overlay.yml"
    fi
  fi
MARKER="${ROOT}/.specify/.rhoai3-ads-provisioned"
LOG_PREFIX="init-spec-workspace"

log() { echo "[${LOG_PREFIX}] $*" >&2; }
die() { echo "[${LOG_PREFIX}] ERROR: $*" >&2; exit 1; }

# UPLIFT-2: progress + human lines on stderr; one JSON object on stdout.
emit_ok() {
  local human="$1"
  shift
  python3 -c 'import json,sys; print(json.dumps(json.loads(sys.argv[1]),separators=(",",":")))' "$1"
  printf '%s\n' "${human}" >&2
}

[ -d "${ROOT}" ] || die "missing root ${ROOT}"
[ -f "${ASSET_OVERRIDE}" ] || die "missing Non-Goals override asset at ${ASSET_OVERRIDE} (expected under init-spec-workspace/assets/)"
[ -f "${ASSET_TASKS}" ] || die "missing tasks-template unique-owner asset at ${ASSET_TASKS}"
[ -f "${ASSET_CONSTITUTION}" ] || die "missing constitution asset at ${ASSET_CONSTITUTION}"
[ -f "${ASSET_OVERLAY}" ] || die "missing speckit overlay asset at ${ASSET_OVERLAY}"

install_ads_overlays() {
  mkdir -p "${ROOT}/.specify/templates/overrides" \
    "${ROOT}/.specify/memory" \
    "${ROOT}/.specify/workflows/overlays/speckit"
  cp "${ASSET_OVERRIDE}" "${ROOT}/.specify/templates/overrides/spec-template.md"
  log "installed Non-Goals override → .specify/templates/overrides/spec-template.md"
  cp "${ASSET_TASKS}" "${ROOT}/.specify/templates/overrides/tasks-template.md"
  log "installed unique-owner tasks override → .specify/templates/overrides/tasks-template.md"

  local const_dest="${ROOT}/.specify/memory/constitution.md"
  if [ ! -f "${const_dest}" ] || grep -q '\[PROJECT_NAME\]\|\[PRINCIPLE_1' "${const_dest}" 2>/dev/null; then
    cp "${ASSET_CONSTITUTION}" "${const_dest}"
    log "installed destination constitution → .specify/memory/constitution.md"
  else
    log "constitution present and not placeholder — leave in place"
  fi

  local overlay_dest="${ROOT}/.specify/workflows/overlays/speckit/stop-before-implement.yml"
  cp "${ASSET_OVERLAY}" "${overlay_dest}"
  log "installed speckit overlay → ${overlay_dest}"
  rm -f "${ROOT}/.specify/workflows/sdd-to-tasks.yml"

  cat > "${ROOT}/.specify/AD-S-STOP-RULE.md" <<'EOF'
# AD-S stop rule

After `/speckit-tasks` (optional `/speckit-analyze`), convert `tasks.md`
into Hermes Kanban cards.

**Never run `/speckit-implement`.** Kanban is the only executor (AD-006 / AD-H).

Project overlay (stock `speckit` minus `implement` and the `type: gate`
steps `review-spec` / `review-plan`, plus `clarify`, M1 paths in specify
args):

  specify workflow run speckit
  specify workflow resolve speckit   # no implement; no review-spec/review-plan

Gates are removed from the graph (163200Z unattended). Do not wait on a
human gate click. Do not restore those steps on a live dest — stop, fix
golden, publish, wipe, restart.
EOF

  if [ -d "${ROOT}/.git/hooks" ]; then
    cat > "${ROOT}/.git/hooks/pre-commit" <<'HOOK'
#!/bin/sh
ROOT=$(git rev-parse --show-toplevel)
exec bash "${ROOT}/.hermes/skills/harness/validate-contracts/scripts/pre-commit-index-suite.sh"
HOOK
    chmod +x "${ROOT}/.git/hooks/pre-commit"
    log "installed LG9a pre-commit hook → .git/hooks/pre-commit"
  fi
}

if [[ "${DRY_RUN}" == "1" ]]; then
  log "DRY-RUN: ROOT=${ROOT}"
  log "DRY-RUN: MARKER=${MARKER}"
  log "DRY-RUN: ASSET_OVERRIDE=${ASSET_OVERRIDE}"
  log "DRY-RUN: ASSET_TASKS=${ASSET_TASKS}"
  log "DRY-RUN: ASSET_CONSTITUTION=${ASSET_CONSTITUTION}"
  log "DRY-RUN: ASSET_OVERLAY=${ASSET_OVERLAY}"
  log "DRY-RUN: would run: specify init --here --integration hermes --force --ignore-agent-tools"
  log "DRY-RUN: would copy override → .specify/templates/overrides/spec-template.md"
  log "DRY-RUN: would copy unique-owner tasks override → .specify/templates/overrides/tasks-template.md"
  log "DRY-RUN: would copy constitution → .specify/memory/constitution.md"
  log "DRY-RUN: would copy overlay → .specify/workflows/overlays/speckit/stop-before-implement.yml"
  log "DRY-RUN: would write marker ${MARKER}"
  emit_ok "[${LOG_PREFIX}] DRY-RUN complete" "$(python3 -c 'import json,sys; print(json.dumps({"script":"init-workspace","ok":True,"dry_run":True,"root":sys.argv[1]}))' "${ROOT}")"
  exit 0
fi

if [ -f "${MARKER}" ]; then
  TS="$(cat "${MARKER}")"
  # CS-9: prior tips wrote EXTERNAL_DIRS.note into the skill tree (R-SK.1 stray).
  # Relocate under .specify/ (gitignored) even on skip so tip-pull seats go green.
  legacy_note="${ROOT}/.hermes/skills/sdd/init-spec-workspace/EXTERNAL_DIRS.note"
  dest_note="${ROOT}/.specify/EXTERNAL_DIRS.note"
  if [ -f "${legacy_note}" ]; then
    mkdir -p "${ROOT}/.specify"
    if [ ! -f "${dest_note}" ]; then
      mv "${legacy_note}" "${dest_note}"
      log "relocated legacy EXTERNAL_DIRS.note → ${dest_note}"
    else
      rm -f "${legacy_note}"
      log "removed legacy skill-tree EXTERNAL_DIRS.note (dest already present)"
    fi
  fi
  install_ads_overlays
  HUMAN="[${LOG_PREFIX}] already provisioned (${TS}) — skip specify init; overlays refreshed"
  emit_ok "${HUMAN}" "$(python3 -c 'import json,sys; print(json.dumps({"script":"init-workspace","ok":True,"skipped":True,"overlays_refreshed":True,"root":sys.argv[1],"marker":sys.argv[2],"provisioned_at":sys.argv[3]}))' "${ROOT}" "${MARKER}" "${TS}")"
  exit 0
fi

# Refuse runs that would create .specify/ outside a live workspace (AD-S S.4).
# Mechanical assert (check-specify-absent.py) replaces the retired
# DO_NOT_COMMIT_SPECIFY note. Workspaces live under /projects/*; intentional
# dry-runs set FORCE_AD_S_PROVISION=1.
case "${ROOT}" in
  /projects/*) ;;
  *)
    if [ "${FORCE_AD_S_PROVISION:-}" != "1" ]; then
      die "refusing AD-S init in scaffold/source tree (workspace: /projects/*; dry-run: FORCE_AD_S_PROVISION=1)"
    fi
    ;;
esac

ensure_specify() {
  if command -v specify >/dev/null 2>&1; then
    return 0
  fi
  export PATH="${HOME}/.local/bin:${PATH}"
  if command -v specify >/dev/null 2>&1; then
    return 0
  fi
  if ! command -v uv >/dev/null 2>&1; then
    log "installing uv…"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="${HOME}/.local/bin:${PATH}"
  fi
  command -v uv >/dev/null 2>&1 || die "uv not available after install"
  # R-HX.1 — pin Spec Kit (see .hermes/pins.json)
  local SPECIFY_PIN="${SPECIFY_CLI_VERSION:-0.16.1}"
  log "installing specify-cli==${SPECIFY_PIN} via uv tool…"
  uv tool install "specify-cli==${SPECIFY_PIN}"
  export PATH="${HOME}/.local/bin:${PATH}"
  command -v specify >/dev/null 2>&1 || die "specify not on PATH after uv tool install"
}

ensure_specify

cd "${ROOT}"
log "running: specify init --here --integration hermes --force --ignore-agent-tools"
# --ignore-agent-tools: workspace may not expose a hermes binary on PATH at
# postStart; Hermes skills still install under ~/.hermes/skills (AD-S / §9).
specify init --here --integration hermes --force --ignore-agent-tools

[ -d "${ROOT}/.specify" ] || die "specify init did not create .specify/"

install_ads_overlays

# external_dirs: when HERMES_HOME is relocated away from ~/.hermes, spec-kit
# still writes skills to Path.home()/.hermes/skills — keep both on the list.
note_external_dirs() {
  # Workspace-only under .specify/ (gitignored) — never land in R-SK.1/R-SK.5
  # scanned skill trees (CS-9 / R-SK.1 stray tip file).
  local note="${ROOT}/.specify/EXTERNAL_DIRS.note"
  mkdir -p "$(dirname "${note}")"
  # Drop legacy tip-path note if a prior provision wrote it into the skill tree.
  rm -f "${ROOT}/.hermes/skills/sdd/init-spec-workspace/EXTERNAL_DIRS.note"
  cat > "${note}" <<'EOF'
AD-S / AD-002B — skills.external_dirs after specify init

spec-kit's Hermes integration installs skills under:
  ~/.hermes/skills/   (Path.home() — ignores $HERMES_HOME)

Project skills live under:
  <modernized>/.hermes/skills/

If Managed Scope relocates HERMES_HOME to .hermes/home/ (or /etc/hermes),
ensure the Hermes profile lists BOTH:
  - <modernized>/.hermes/skills
  - $HOME/.hermes/skills

Do not remove the Path.home() entry or /speckit-* skills become invisible.
EOF
  log "wrote ${note}"
}
note_external_dirs

# Provision-owns-tools (Operator E-20260813T191700Z): when HERMES_HOME is
# relocated, init-ai-tools may skip Managed Scope config (Hermes venv absent)
# — leaving no config.yaml. Spec Kit still installs under
# Path.home()/.hermes/skills; ensure both dirs are listed before assert so
# postStart does not fail-closed after a successful specify init.
ensure_external_dirs_config() {
  local project_skills="${ROOT}/.hermes/skills"
  local home_skills="${HOME}/.hermes/skills"
  mkdir -p "${project_skills}" "${home_skills}"
  local cfg=""
  if [ -n "${HERMES_MANAGED_DIR:-}" ]; then
    mkdir -p "${HERMES_MANAGED_DIR}"
    cfg="${HERMES_MANAGED_DIR}/config.yaml"
  elif [ -n "${HERMES_HOME:-}" ]; then
    mkdir -p "${HERMES_HOME}"
    cfg="${HERMES_HOME}/config.yaml"
  else
    cfg="${ROOT}/.hermes/home/config.yaml"
    mkdir -p "$(dirname "${cfg}")"
  fi
  PROJECT_SKILLS="${project_skills}" HOME_SKILLS="${home_skills}" CFG="${cfg}" \
    python3 - <<'PY'
import os
from pathlib import Path

cfg_path = Path(os.environ["CFG"])
project = str(Path(os.environ["PROJECT_SKILLS"]).resolve())
home = str(Path(os.environ["HOME_SKILLS"]).resolve())
text = cfg_path.read_text(encoding="utf-8") if cfg_path.is_file() else ""


def parse_external_dirs(raw: str) -> list[str]:
    dirs: list[str] = []
    in_block = False
    for raw_ln in raw.splitlines():
        ln = raw_ln.split("#", 1)[0].rstrip()
        if "external_dirs" in ln and ":" in ln:
            in_block = True
            rest = ln.split(":", 1)[1].strip()
            if rest.startswith("[") and rest.endswith("]"):
                for part in rest[1:-1].split(","):
                    part = part.strip().strip("\"'")
                    if part:
                        dirs.append(part)
                in_block = False
            continue
        if not in_block:
            continue
        s = ln.strip()
        if s.startswith("- "):
            dirs.append(s[2:].strip().strip("\"'"))
            continue
        if s and not ln.startswith((" ", "\t")):
            in_block = False
    return dirs


def resolve_one(d: str) -> str:
    p = Path(os.path.expandvars(os.path.expanduser(d)))
    return str(p.resolve()) if p.is_absolute() else str((Path.cwd() / p).resolve())


existing = [resolve_one(d) for d in parse_external_dirs(text)]
need = [project, home]
disabled_need = [
    "dispatch-phase",
    "enforce-authority-boundary",
    "ground-in-harvest",
    "record-run-evidence",
    "validate-contracts",
]
if (
    cfg_path.is_file()
    and all(n in existing for n in need)
    and "disabled:" in text
    and all(n in text for n in disabled_need)
):
    print(f"ensure_external_dirs: OK ({cfg_path})")
    raise SystemExit(0)

try:
    import yaml  # type: ignore
except ImportError:
    yaml = None

if yaml is not None:
    data = yaml.safe_load(text) if text.strip() else {}
    if not isinstance(data, dict):
        data = {}
    skills = data.get("skills")
    if not isinstance(skills, dict):
        skills = {}
        data["skills"] = skills
    dirs = list(skills.get("external_dirs") or [])
    resolved = [resolve_one(str(x)) for x in dirs]
    for n in need:
        if n not in resolved:
            dirs.append(n)
            resolved.append(n)
    skills["external_dirs"] = dirs
    disabled = [
        "dispatch-phase",
        "enforce-authority-boundary",
        "ground-in-harvest",
        "record-run-evidence",
        "validate-contracts",
    ]
    cur_dis = [str(x) for x in (skills.get("disabled") or [])]
    for n in disabled:
        if n not in cur_dis:
            cur_dis.append(n)
    skills["disabled"] = cur_dis
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
else:
    block = (
        "# AD-S ensure_external_dirs (postStart provision)\n"
        "skills:\n"
        "  disabled:\n"
        "    - dispatch-phase\n"
        "    - enforce-authority-boundary\n"
        "    - ground-in-harvest\n"
        "    - record-run-evidence\n"
        "    - validate-contracts\n"
        "  external_dirs:\n"
        f"    - {project}\n"
        f"    - {home}\n"
    )
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    if text.strip():
        cfg_path.write_text(text.rstrip() + "\n" + block, encoding="utf-8")
    else:
        cfg_path.write_text(block, encoding="utf-8")
print(f"ensure_external_dirs: wrote {cfg_path}")
PY
  log "ensured skills.external_dirs in ${cfg}"
}

# Enforce (not merely remind) when HERMES_HOME is relocated — Operator
# no-compromise E-20260808T075048Z / AD-S.
if [ -n "${HERMES_HOME:-}" ]; then
  default_hh="${HOME}/.hermes"
  if [ "$(cd "${HERMES_HOME}" 2>/dev/null && pwd -P)" != "$(cd "${default_hh}" 2>/dev/null && pwd -P)" ]; then
    ensure_external_dirs_config
    python3 "$(cd "$(dirname "$0")" && pwd)/check-external-dirs.py" "${ROOT}" \
      || die "external_dirs assert failed (HERMES_HOME relocated)"
  fi
fi

date -u +%Y-%m-%dT%H:%M:%SZ > "${MARKER}"
TS="$(cat "${MARKER}")"
HUMAN="[${LOG_PREFIX}] OK — AD-S provision complete (marker ${MARKER})"
emit_ok "${HUMAN}" "$(python3 -c 'import json,sys; print(json.dumps({"script":"init-workspace","ok":True,"skipped":False,"root":sys.argv[1],"marker":sys.argv[2],"provisioned_at":sys.argv[3]}))' "${ROOT}" "${MARKER}" "${TS}")"
log "Stop rule: /speckit-tasks → kanban mint; NEVER /speckit-implement; specify workflow run speckit"
