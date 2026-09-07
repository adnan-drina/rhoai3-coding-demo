#!/usr/bin/env bash
# Validate the demo stage layout from the repository tree.
#
#   ./scripts/validate-stage-flow.sh
#       Static: stages/*/ + matching Argo CD apps + kustomize build. No cluster.
#   ./scripts/validate-stage-flow.sh --live
#       Static, then each stage validate.sh in directory order (needs oc + .env).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"

LIVE=0
while [[ $# -gt 0 ]]; do
    case "$1" in
        --live) LIVE=1; shift ;;
        -h|--help)
            cat <<'EOF'
Usage:
  ./scripts/validate-stage-flow.sh
      Static: stages/*/ + matching Argo CD apps + kustomize build. No cluster.
  ./scripts/validate-stage-flow.sh --live
      Static, then each stage validate.sh in directory order (needs oc + .env).
EOF
            exit 0
            ;;
        -*)
            log_error "Unknown flag: $1 (try --live)"
            exit 1
            ;;
        *)
            log_error "Unexpected argument: $1"
            exit 1
            ;;
    esac
done

TMP_PATHS="$(mktemp)"
trap 'rm -f "$TMP_PATHS"' EXIT

command -v python3 >/dev/null || { log_error "python3 is required"; exit 1; }
command -v kustomize >/dev/null || { log_error "kustomize is required"; exit 1; }

log_step "Validating stage layout"

python3 - "$REPO_ROOT" >"$TMP_PATHS" <<'PY'
from pathlib import Path
import re
import sys

repo = Path(sys.argv[1])
stages_root = repo / "stages"
app_root = repo / "gitops" / "argocd" / "app-of-apps"
gitops_stages_root = repo / "gitops" / "stages"

errors = []

def fail(message):
    errors.append(message)

def unquote(value):
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value

def load_mapping(path):
    """Parse nested mappings from simple Kubernetes YAML. Lists are skipped."""
    try:
        lines = path.read_text().splitlines()
    except Exception as exc:
        fail(f"{path.relative_to(repo)} could not be read: {exc}")
        return {}

    root = {}
    stack = [root]
    indents = [-1]
    for raw in lines:
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        if stripped.startswith("- "):
            continue
        while indent <= indents[-1]:
            stack.pop()
            indents.pop()
        if ":" not in stripped:
            continue
        key, _, rest = stripped.partition(":")
        key = key.strip()
        rest = rest.strip()
        if rest.startswith("#"):
            rest = ""
        elif " #" in rest:
            rest = rest.split(" #", 1)[0].rstrip()
        if rest:
            stack[-1][key] = unquote(rest)
            continue
        child = {}
        stack[-1][key] = child
        stack.append(child)
        indents.append(indent)
    return root

if not stages_root.is_dir():
    print("stages/ does not exist", file=sys.stderr)
    sys.exit(1)

stage_dirs = sorted(
    (path for path in stages_root.iterdir() if path.is_dir()),
    key=lambda path: path.name,
)

if not stage_dirs:
    fail("stages/ has no stage directories")

stage_name_re = re.compile(r"^(\d{3})-.+")
seen_ids = []
gitops_stage_names = set()
gitops_paths = []

for stage_dir in stage_dirs:
    name = stage_dir.name
    match = stage_name_re.fullmatch(name)
    if not match:
        fail(f"stage directory must be NNN-slug: stages/{name}")
        continue

    stage_id = match.group(1)
    if stage_id in seen_ids:
        fail(f"duplicate stage id: {stage_id}")
    seen_ids.append(stage_id)

    readme_path = stage_dir / "README.md"
    validate_path = stage_dir / "validate.sh"
    deploy_path = stage_dir / "deploy.sh"

    if not readme_path.exists():
        fail(f"stage {stage_id} README does not exist: {readme_path.relative_to(repo)}")
    if not validate_path.exists():
        fail(f"stage {stage_id} validate.sh does not exist: {validate_path.relative_to(repo)}")
    elif not validate_path.stat().st_mode & 0o111:
        fail(f"stage {stage_id} validate.sh is not executable: {validate_path.relative_to(repo)}")

    app_path = app_root / f"{name}.yaml"
    gitops_path = gitops_stages_root / name / "base"

    if not deploy_path.exists():
        continue

    gitops_stage_names.add(name)

    if not deploy_path.stat().st_mode & 0o111:
        fail(f"stage {stage_id} deploy.sh is not executable: {deploy_path.relative_to(repo)}")

    if not app_path.exists():
        fail(f"stage {stage_id} Argo CD app does not exist: {app_path.relative_to(repo)}")
    if not (gitops_path / "kustomization.yaml").exists():
        fail(
            f"stage {stage_id} gitops path has no kustomization.yaml: "
            f"{gitops_path.relative_to(repo)}"
        )
    else:
        gitops_paths.append(str(gitops_path.relative_to(repo)))

    if not app_path.exists():
        continue

    app = load_mapping(app_path)
    metadata = app.get("metadata") or {}
    spec = app.get("spec") or {}
    source = spec.get("source") or {}
    labels = metadata.get("labels") or {}
    annotations = metadata.get("annotations") or {}
    expected_path = f"gitops/stages/{name}/base"

    if metadata.get("name") != name:
        fail(f"stage {stage_id} Argo CD app metadata.name must match {name}")
    if spec.get("project") != "rhoai-demo":
        fail(f"stage {stage_id} Argo CD app project must be rhoai-demo")
    if source.get("path") != expected_path:
        fail(f"stage {stage_id} Argo CD app source.path must be {expected_path}")
    if labels.get("demo.rhoai.io/stage") != stage_id:
        fail(f"stage {stage_id} Argo CD app missing demo.rhoai.io/stage label")
    if not annotations.get("argocd.argoproj.io/manifest-generate-paths", "").startswith(
        "gitops/stages/"
    ):
        fail(f"stage {stage_id} Argo CD app manifest-generate-paths should point at gitops/stages")

if seen_ids != sorted(seen_ids):
    fail(f"stage ids must be in ascending directory order: {seen_ids}")

if stage_dirs and not gitops_stage_names:
    fail("no GitOps stages found: every workshop needs at least one stages/*/deploy.sh")

if app_root.is_dir():
    for app_path in sorted(app_root.glob("*.yaml")):
        name = app_path.stem
        if not stage_name_re.fullmatch(name):
            fail(f"Argo CD app filename should be NNN-slug.yaml: {app_path.relative_to(repo)}")
            continue
        if name not in gitops_stage_names:
            fail(
                f"Argo CD app {app_path.relative_to(repo)} has no matching "
                f"stages/{name}/deploy.sh"
            )

if gitops_stages_root.is_dir():
    for gitops_dir in sorted(path for path in gitops_stages_root.iterdir() if path.is_dir()):
        name = gitops_dir.name
        if name not in gitops_stage_names:
            fail(
                f"gitops/stages/{name} has no matching stages/{name}/deploy.sh "
                "(workflow-only stages omit GitOps)"
            )

if errors:
    for error in errors:
        print(f"[FAIL] {error}", file=sys.stderr)
    sys.exit(1)

for path in gitops_paths:
    print(path)
PY

log_success "Stage layout is consistent"

log_step "Rendering stage Kustomize bases"
while IFS= read -r gitops_path; do
    [[ -n "$gitops_path" ]] || continue
    log_info "kustomize build $gitops_path"
    kustomize build "$REPO_ROOT/$gitops_path" >/dev/null
done <"$TMP_PATHS"

log_success "Stage layout static validation passed"

if [[ "$LIVE" -eq 0 ]]; then
    exit 0
fi

load_env
check_oc_logged_in

log_step "Live stage validation"

# while-read instead of mapfile: macOS ships bash 3.2
stages=()
while IFS= read -r stage; do
    stages+=("$stage")
done < <(
    python3 - "$REPO_ROOT" <<'PY'
from pathlib import Path
import sys

root = Path(sys.argv[1]) / "stages"
for path in sorted((item for item in root.iterdir() if item.is_dir()), key=lambda item: item.name):
    print(path.name)
PY
)

set +e
max_rc=0
for stage in "${stages[@]}"; do
    log_step "Validating ${stage}"
    "$REPO_ROOT/stages/${stage}/validate.sh"
    rc=$?
    if [[ $rc -eq 1 ]]; then
        max_rc=1
    elif [[ $rc -eq 2 && $max_rc -eq 0 ]]; then
        max_rc=2
    fi
done

exit "$max_rc"
