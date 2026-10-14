#!/usr/bin/env bash
set -euo pipefail
candidate_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
build_dir=$(mktemp -d /private/tmp/stage060-runtime-candidate/postrender.XXXXXX)
trap 'rm -rf "$build_dir"' EXIT
mkdir "$build_dir/native"
cat > "$build_dir/native/native.yaml"
cp "$candidate_dir/gateway-patch.yaml" "$candidate_dir/cluster-rbac-patch.yaml" "$candidate_dir"/certgen-*-patch.yaml "$build_dir/native/"
cp -R "$candidate_dir/workspaces" "$build_dir/workspaces"
cat > "$build_dir/native/kustomization.yaml" <<'KUSTOMIZE'
namespace: openshell
resources:
  - native.yaml
patches:
  - path: gateway-patch.yaml
  - path: cluster-rbac-patch.yaml
  - path: certgen-serviceaccount-patch.yaml
  - path: certgen-role-patch.yaml
  - path: certgen-rolebinding-patch.yaml
  - path: certgen-job-patch.yaml
KUSTOMIZE
cat > "$build_dir/kustomization.yaml" <<'KUSTOMIZE'
resources:
  - native
  - workspaces
KUSTOMIZE
kustomize build "$build_dir"
