#!/usr/bin/env bash
# Compile the qualification pipeline into the Kubernetes Pipeline and PipelineVersion manifests that
# GitOps applies to the evaluated-models pipeline server (RHOAI 3.5 "Working with AI pipelines":
# pipeline definitions stored in Kubernetes). Requires Python 3.11+ and kfp 2.14.3 or later; use kfp 2.16.1:
# every step installs the compiling SDK version, and the RHOAI runtime image's package index offers 2.16.1.
#
# Usage: compile.sh <version>   e.g. compile.sh v1 — a changed pipeline gets a new version name.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
VERSION="${1:?usage: compile.sh <version, e.g. v1>}"
KFP="${KFP:-kfp}"
command -v "$KFP" >/dev/null || { echo "[FAIL] kfp CLI not found (pip install 'kfp==2.16.1' 'kfp-kubernetes==2.16.1')" >&2; exit 1; }
OUT="$REPO_ROOT/gitops/stages/050-model-evaluation/base/model-qualification/pipeline/agentic-coding-model-qualification.yaml"
mkdir -p "$(dirname "$OUT")"
"$KFP" dsl compile --py "$SCRIPT_DIR/pipeline.py" --function qualification --output "$OUT" \
  --kubernetes-manifest-format --include-pipeline-manifest --namespace evaluated-models \
  --pipeline-name agentic-coding-model-qualification \
  --pipeline-display-name "Agentic coding model qualification" \
  --pipeline-version-name "agentic-coding-model-qualification-$VERSION" \
  --pipeline-version-display-name "agentic-coding-model-qualification $VERSION"
echo "[OK] compiled $VERSION -> ${OUT#"$REPO_ROOT/"}"
