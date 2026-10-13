#!/usr/bin/env bash
# Build shared Git/Python/oc tooling; project application images use Tekton instead.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
[[ $# -ge 1 && $# -le 2 && "$1" =~ ^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$ ]] || { echo 'Usage: build-stage070-platform-tools.sh <tag> [--push]' >&2; exit 2; }
[[ "${2:-}" == '' || "${2:-}" == --push ]] || exit 2
image="quay.io/rhoai3-coding-demo/rhoai3-ws-080:platform-tools-$1"
connection="${STAGE070_PODMAN_CONNECTION:-podman-machine-default}"
context="$REPO_ROOT/stages/070-advanced-app-platform/tools-image"
auth=()
[[ -z "${REGISTRY_AUTH_FILE:-}" ]] || auth=(--authfile "$REGISTRY_AUTH_FILE")
podman --connection "$connection" info >/dev/null
podman --connection "$connection" build "${auth[@]}" --platform linux/amd64 -t "$image" -f "$context/Dockerfile" "$context"
podman --connection "$connection" run --rm --platform linux/amd64 --entrypoint /bin/sh "$image" -c 'set -e; git --version; python3 --version; oc version --client'
if [[ "${2:-}" == --push ]]; then
  digest_file=$(mktemp)
  trap 'rm -f "$digest_file"' EXIT
  podman --connection "$connection" push "${auth[@]}" --digestfile "$digest_file" "$image"
  printf 'Published: %s@%s\n' "${image%:*}" "$(cat "$digest_file")"
fi
