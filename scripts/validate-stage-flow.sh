#!/usr/bin/env bash
# Static validation for the canonical staged demo flow.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"

FLOW_FILE="${1:-$REPO_ROOT/demo/flows/default.yaml}"
TMP_PATHS="$(mktemp)"
trap 'rm -f "$TMP_PATHS"' EXIT

command -v python3 >/dev/null || { log_error "python3 is required"; exit 1; }
command -v kustomize >/dev/null || { log_error "kustomize is required"; exit 1; }

log_step "Validating demo flow metadata"

python3 - "$REPO_ROOT" "$FLOW_FILE" >"$TMP_PATHS" <<'PY'
from pathlib import Path
import re
import sys

try:
    import yaml
except ImportError:
    print("PyYAML is required to parse flow and Argo CD YAML files", file=sys.stderr)
    sys.exit(1)

repo = Path(sys.argv[1])
flow_file = Path(sys.argv[2])

errors = []

def fail(message):
    errors.append(message)

def load_yaml(path):
    try:
        with path.open() as handle:
            return yaml.safe_load(handle)
    except Exception as exc:
        fail(f"{path.relative_to(repo)} could not be parsed: {exc}")
        return {}

if not flow_file.exists():
    print(f"Flow file does not exist: {flow_file}", file=sys.stderr)
    sys.exit(1)

flow = load_yaml(flow_file)
stages = flow.get("stages") or []

if flow.get("apiVersion") != "rhoai.demo/v1alpha1":
    fail("apiVersion must be rhoai.demo/v1alpha1")
if flow.get("kind") != "DemoFlow":
    fail("kind must be DemoFlow")
if not stages:
    fail("stages must be a non-empty list")

required = {
    "id",
    "name",
    "productFocus",
    "deployScript",
    "validateScript",
    "gitopsApplication",
    "gitopsPath",
    "dependsOn",
}

seen_ids = set()
ordered_ids = []
stage_ids_by_index = {}
gitops_paths = []

for index, stage in enumerate(stages):
    stage_id = str(stage.get("id", ""))
    stage_label = stage_id or f"index {index}"
    ordered_ids.append(stage_id)
    stage_ids_by_index[stage_id] = index

    missing = sorted(required - set(stage))
    if missing:
        fail(f"stage {stage_label} missing keys: {', '.join(missing)}")
        continue

    if not re.fullmatch(r"\d{3}", stage_id):
        fail(f"stage id must be three digits: {stage_id}")
    if stage_id in seen_ids:
        fail(f"duplicate stage id: {stage_id}")
    seen_ids.add(stage_id)

    for key in ("productFocus", "dependsOn"):
        if not isinstance(stage.get(key), list):
            fail(f"stage {stage_id} {key} must be a list")

    deploy_path = repo / stage["deployScript"]
    validate_path = repo / stage["validateScript"]
    stage_dir = deploy_path.parent
    readme_path = stage_dir / "README.md"
    gitops_path = repo / stage["gitopsPath"]
    app_path = repo / "gitops" / "argocd" / "app-of-apps" / f"{stage['gitopsApplication']}.yaml"

    if not stage_dir.name.startswith(f"{stage_id}-"):
        fail(f"stage {stage_id} deployScript directory should start with {stage_id}-")
    if validate_path.parent != stage_dir:
        fail(f"stage {stage_id} deployScript and validateScript should be in the same directory")

    for label, path in (
        ("deployScript", deploy_path),
        ("validateScript", validate_path),
        ("README", readme_path),
        ("gitopsPath", gitops_path),
        ("Argo CD app", app_path),
    ):
        if not path.exists():
            fail(f"stage {stage_id} {label} does not exist: {path.relative_to(repo)}")

    for label, path in (("deployScript", deploy_path), ("validateScript", validate_path)):
        if path.exists() and not path.stat().st_mode & 0o111:
            fail(f"stage {stage_id} {label} is not executable: {path.relative_to(repo)}")

    if gitops_path.exists():
        if not (gitops_path / "kustomization.yaml").exists():
            fail(f"stage {stage_id} gitopsPath has no kustomization.yaml: {gitops_path.relative_to(repo)}")
        else:
            gitops_paths.append(stage["gitopsPath"])

    if app_path.exists():
        app = load_yaml(app_path)
        metadata = app.get("metadata") or {}
        spec = app.get("spec") or {}
        source = spec.get("source") or {}
        labels = metadata.get("labels") or {}
        annotations = metadata.get("annotations") or {}

        if metadata.get("name") != stage["gitopsApplication"]:
            fail(f"stage {stage_id} Argo CD app metadata.name does not match gitopsApplication")
        if spec.get("project") != "rhoai-demo":
            fail(f"stage {stage_id} Argo CD app project must be rhoai-demo")
        if source.get("path") != stage["gitopsPath"]:
            fail(f"stage {stage_id} Argo CD app source.path must match gitopsPath")
        if labels.get("demo.rhoai.io/stage") != stage_id:
            fail(f"stage {stage_id} Argo CD app missing demo.rhoai.io/stage label")
        if not annotations.get("argocd.argoproj.io/manifest-generate-paths", "").startswith("gitops/stages/"):
            fail(f"stage {stage_id} Argo CD app manifest-generate-paths should point at gitops/stages")

for index, stage in enumerate(stages):
    stage_id = str(stage.get("id", ""))
    for dependency in stage.get("dependsOn") or []:
        dep = str(dependency)
        if dep not in stage_ids_by_index:
            fail(f"stage {stage_id} dependsOn unknown stage {dep}")
        elif stage_ids_by_index[dep] >= index:
            fail(f"stage {stage_id} dependsOn {dep}, which is not earlier in the flow")

if ordered_ids != sorted(ordered_ids):
    fail(f"stage ids must be listed in ascending order: {ordered_ids}")

if errors:
    for error in errors:
        print(f"[FAIL] {error}", file=sys.stderr)
    sys.exit(1)

for path in gitops_paths:
    print(path)
PY

log_success "Flow metadata is consistent"

log_step "Rendering stage Kustomize bases"
while IFS= read -r gitops_path; do
    [[ -n "$gitops_path" ]] || continue
    log_info "kustomize build $gitops_path"
    kustomize build "$REPO_ROOT/$gitops_path" >/dev/null
done <"$TMP_PATHS"

log_success "Stage flow static validation passed"
