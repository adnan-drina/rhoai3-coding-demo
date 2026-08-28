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

# Hermes worker HOME is the profile home. specify/uv and speckit skills
# land under the human account (UDI /home/user) or Path.home() at init.
human_home() {
  local h
  h="$(getent passwd "$(id -u)" | cut -d: -f6 || true)"
  if [ -n "${h}" ] && [ -d "${h}" ]; then
    printf '%s\n' "${h}"
    return 0
  fi
  printf '%s\n' "/home/user"
}
HUMAN_HOME="$(human_home)"

# --dry-run as first arg or DRY_RUN=1: print plan and exit 0 before installs.
if [[ "${1:-}" == "--dry-run" ]]; then
  shift
  DRY_RUN=1
fi
DRY_RUN="${DRY_RUN:-0}"

ROOT="$(cd "${1:-.}" && pwd)"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# Golden/source tree: `.specify/` must stay absent (TR-4 restored assert).
case "${ROOT}" in
  /projects/*) ;;
  *)
    python3 "${SCRIPT_DIR}/check-specify-absent.py" "${ROOT}"
    ;;
esac
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
  mkdir -p "${ROOT}/.specify/templates"
  cp "${ASSET_TASKS}" "${ROOT}/.specify/templates/tasks-template.md"
  log "replaced stock Spec Kit tasks-template.md (directory tasks are K4_PLANNING_DEFECT)"

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

After `/speckit-tasks` (optional `/speckit-analyze`), mint Hermes Kanban
cards from the typed partition via `.hermes/kernel/k4_mint.py`
(`hermes kanban create` inline `--body`). Do not grep `tasks.md` for
write-set paths. Do not `kanban decompose`. Do not `kanban swarm`.

**Never run `/speckit-implement`.** Kanban is the only executor (AD-006 / AD-H).

Project overlay (stock `speckit` minus `implement` and the `type: gate`
steps `review-spec` / `review-plan`, plus `clarify`, M1 paths in specify
args):

  specify workflow run speckit   # NOT installed: hermes.manifest files:{}
  # M2 follows .hermes/skills/speckit-specify|plan|tasks SKILL.md instead.
  specify workflow resolve speckit
  # dest PATH shim sets HOME=project for the specify child (profile HOME stays).
  # Do not rely on workers prefixing HOME= — that is the dest-6/dest-7 miss.

Gates are removed from the graph (163200Z unattended). Do not wait on a
human gate click. Do not restore those steps on a live dest — stop, fix
golden, publish, wipe, restart.
EOF

  if [ -d "${ROOT}/.git/hooks" ]; then
    # K5 authoring CI lives on harness-v2, not a dest pre-commit suite.
    rm -f "${ROOT}/.git/hooks/pre-commit"
    log "Phase N: skipped dest pre-commit hook (validate-contracts out of day-one)"
  fi
}

if [[ "${DRY_RUN}" == "1" ]]; then
  log "DRY-RUN: ROOT=${ROOT}"
  log "DRY-RUN: MARKER=${MARKER}"
  log "DRY-RUN: ASSET_OVERRIDE=${ASSET_OVERRIDE}"
  log "DRY-RUN: ASSET_TASKS=${ASSET_TASKS}"
  log "DRY-RUN: ASSET_CONSTITUTION=${ASSET_CONSTITUTION}"
  log "DRY-RUN: ASSET_OVERLAY=${ASSET_OVERLAY}"
  log "DRY-RUN: would run: HOME=${ROOT} specify init --here --integration hermes --force --ignore-agent-tools"
  log "DRY-RUN: would copy override → .specify/templates/overrides/spec-template.md"
  log "DRY-RUN: would copy unique-owner tasks override → .specify/templates/overrides/tasks-template.md"
  log "DRY-RUN: would replace stock .specify/templates/tasks-template.md"
  log "DRY-RUN: would copy constitution → .specify/memory/constitution.md"
  log "DRY-RUN: would copy overlay → .specify/workflows/overlays/speckit/stop-before-implement.yml"
    log "DRY-RUN: would seed speckit-specify into ${ROOT}/.hermes/skills/<name> only (not sdd/; not user-root external_dirs)"
  log "DRY-RUN: would install PATH shim ${ROOT}/.hermes/bin/specify (worker specify, not HOME= prefix)"
  emit_ok "[${LOG_PREFIX}] DRY-RUN complete" "$(python3 -c 'import json,sys; print(json.dumps({"script":"init-workspace","ok":True,"dry_run":True,"root":sys.argv[1]}))' "${ROOT}")"
  exit 0
fi

# dest PATH may already have the project/managed specify shim. That is not
# specify-cli. Probe for a real binary or uv-install one.
# Sets REAL_SPECIFY_PATH to the absolute path of the genuine specify-cli.
# That value is baked into the shim as SPECIFY_REAL so the run-time helper
# never PATH-searches (Architect 153721ZA). A wrapper is rejected
# by CONTENT, not by location: every shim we write execs
# specify-from-project.sh, so grepping for that name catches all of them
# wherever they are installed, which path lists cannot.
REAL_SPECIFY_PATH=""
_real_specify() {
  local p
  p="$(command -v specify 2>/dev/null || true)"
  [[ -n "${p}" && -x "${p}" ]] || return 1
  if grep -qF "specify-from-project.sh" "${p}" 2>/dev/null; then
    return 1
  fi
  REAL_SPECIFY_PATH="${p}"
  return 0
}

ensure_specify() {
  export PATH="${HUMAN_HOME}/.local/bin:/usr/local/bin:${PATH}"
  if _real_specify; then
    return 0
  fi
  export PATH="${HOME}/.local/bin:${PATH}"
  if _real_specify; then
    return 0
  fi
  if ! command -v uv >/dev/null 2>&1; then
    log "installing uv…"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="${HUMAN_HOME}/.local/bin:${HOME}/.local/bin:${PATH}"
  fi
  command -v uv >/dev/null 2>&1 || die "uv not available after install"
  # R-HX.1 — pin Spec Kit (see .hermes/pins.json)
  local SPECIFY_PIN="${SPECIFY_CLI_VERSION:-0.16.1}"
  log "installing specify-cli==${SPECIFY_PIN} via uv tool…"
  uv tool install "specify-cli==${SPECIFY_PIN}"
  export PATH="${HUMAN_HOME}/.local/bin:${HOME}/.local/bin:${PATH}"
  _real_specify || die "specify-cli not on PATH after uv tool install"
}

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
  python3 "${SCRIPT_DIR}/seed-speckit-skills.py" "${ROOT}" "${HUMAN_HOME}" \
    || die "seed-speckit-skills failed (implementer must see speckit-specify)"
  python3 "${SCRIPT_DIR}/assert-specify-skills-root.py" "${ROOT}" \
    || die "specify CLI skills-root missing speckit-specify"
  ensure_specify
  bash "${SCRIPT_DIR}/install-specify-shim.sh" "${ROOT}" "${REAL_SPECIFY_PATH}" \
    || die "install-specify-shim failed"
  python3 "${SCRIPT_DIR}/assert-specify-run-from-worker-home.py" \
    || die "specify worker-shell control failed (profile HOME still hides speckit-specify)"
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

ensure_specify

cd "${ROOT}"
# spec-kit 0.16.1 Hermes integration writes to Path.home()/.hermes/skills
# (spec-kit#3334 unmerged). Init still sets HOME=<project> for `specify init`.
# Run-time `specify workflow run` uses the PATH shim (install-specify-shim.sh /
# dest-init managed bin) so a worker shell without HOME= still resolves
# speckit-specify. Do not add user-root external_dirs.
log "running: HOME=${ROOT} specify init --here --integration hermes --force --ignore-agent-tools"
HOME="${ROOT}" specify init --here --integration hermes --force --ignore-agent-tools

[ -d "${ROOT}/.specify" ] || die "specify init did not create .specify/"

install_ads_overlays
python3 "${SCRIPT_DIR}/seed-speckit-skills.py" "${ROOT}" "${HUMAN_HOME}" \
  || die "seed-speckit-skills failed (implementer must see speckit-specify)"
python3 "${SCRIPT_DIR}/assert-specify-skills-root.py" "${ROOT}" \
  || die "specify CLI skills-root missing speckit-specify"
bash "${SCRIPT_DIR}/install-specify-shim.sh" "${ROOT}" "${REAL_SPECIFY_PATH}" \
  || die "install-specify-shim failed"
python3 "${SCRIPT_DIR}/assert-specify-run-from-worker-home.py" \
  || die "specify worker-shell control failed (profile HOME still hides speckit-specify)"

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
ensure the Hermes *managed* config lists BOTH:
  - <modernized>/.hermes/skills
  - $HOME/.hermes/skills

Do **not** add `/home/user/.hermes/skills` to the implementer profile
(Architect 125450Z / Operator 125618Z). `init-spec-workspace` copies
`speckit-specify` (and plan/tasks/analyze, never implement) into
`<modernized>/.hermes/skills/sdd/` so implementer `skills list` names it.
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
if cfg_path.is_file() and all(n in existing for n in need):
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
    # v2: do not disable deleted v1 harness skill names.
    skills.pop("disabled", None)
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
else:
    block = (
        "# AD-S ensure_external_dirs (postStart provision)\n"
        "skills:\n"
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
log "Stop rule: /speckit-tasks → k4_mint.py hermes kanban create; NEVER /speckit-implement; M2 follows Hermes speckit-specify/plan/tasks (hermes.manifest files:{})"
