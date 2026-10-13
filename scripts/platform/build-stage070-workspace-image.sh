#!/usr/bin/env bash
# Rebuild the shared workspace tools from verified product artifacts.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
[[ $# -ge 2 && $# -le 3 ]] || { echo 'Usage: build-stage070-workspace-image.sh <MTA Linux amd64 ZIP> <Quay tag> [--push]' >&2; exit 2; }
archive="$1"
tag="$2"
[[ "$tag" =~ ^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}$ ]] || { echo 'Invalid image tag' >&2; exit 2; }
[[ "${3:-}" == '' || "${3:-}" == --push ]] || { echo 'Only --push is accepted as the third argument' >&2; exit 2; }
context="$(mktemp -d "${TMPDIR:-/tmp}/stage070-workspace.XXXXXX")"
trap 'rm -rf "$context"' EXIT
python3 "$REPO_ROOT/scripts/platform/prepare-stage070-workspace-image.py" --mta-archive "$archive" --out "$context"
# Select the rootless connection explicitly; never repair or prune a store.
connection="${STAGE070_PODMAN_CONNECTION:-podman-machine-default}"
podman --connection "$connection" info >/dev/null || { echo 'Start the selected Podman machine before running this script' >&2; exit 1; }
image="quay.io/rhoai3-coding-demo/rhoai3-ws-080:$tag"
podman --connection "$connection" build --platform linux/amd64 -f "$context/Dockerfile" -t "$image" "$context"
podman --connection "$connection" run --rm -i --platform linux/amd64 --entrypoint python3 "$image" - < "$REPO_ROOT/stages/070-advanced-app-platform/workspace-image/verify-image.py"
if [[ "${3:-}" == --push ]]; then
  podman --connection "$connection" push --digestfile "$context/digest" "$image"
  digest="$(cat "$context/digest")"
  [[ "$digest" =~ ^sha256:[0-9a-f]{64}$ ]] || { echo 'Registry did not return a manifest digest' >&2; exit 1; }
  printf 'Published candidate: %s@%s\n' "${image%:*}" "$digest"
  echo 'Review the registry read-back and pin changes before deploying the platform.'
fi
