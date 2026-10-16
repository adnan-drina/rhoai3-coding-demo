#!/usr/bin/env bash
# Build the shared platform tools image (Git, Python and the OpenShift oc client;
# quay.io/rhoai3-coding-demo/rhoai3-ws-080:platform-tools-TAG, linux/amd64) from the Dockerfile in this folder and
# check the three tools run inside it. Project application images are built by Tekton instead. Changes: the local
# Podman image store; with --push, the Quay tag (prints the pushed digest). Safe to rerun. No cluster access.
# STAGE070_PODMAN_CONNECTION selects the Podman connection (default podman-machine-default); REGISTRY_AUTH_FILE, when
# set, is passed to build and push.
# Usage: stages/070-advanced-app-platform/tools-image/build.sh TAG [--push]
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"
usage() { sed -n 's/^# Usage: //p' "$0" >&2; exit 2; }
[[ $# -ge 1 && $# -le 2 && "$1" =~ ^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$ ]] || usage
[[ -z "${2:-}" || "${2:-}" == --push ]] || usage
IMAGE="quay.io/rhoai3-coding-demo/rhoai3-ws-080:platform-tools-$1"
CONNECTION="${STAGE070_PODMAN_CONNECTION:-podman-machine-default}"
AUTH=()
[[ -z "${REGISTRY_AUTH_FILE:-}" ]] || AUTH=(--authfile "$REGISTRY_AUTH_FILE")

podman --connection "$CONNECTION" info >/dev/null || { log_error "Start the selected Podman machine before running this script"; exit 1; }
podman --connection "$CONNECTION" build ${AUTH[@]+"${AUTH[@]}"} --platform linux/amd64 -t "$IMAGE" -f "$SCRIPT_DIR/Dockerfile" "$SCRIPT_DIR"
podman --connection "$CONNECTION" run --rm --platform linux/amd64 --entrypoint /bin/sh "$IMAGE" -c 'set -e; git --version; python3 --version; oc version --client'
if [[ "${2:-}" == --push ]]; then
  DIGEST_FILE=$(mktemp)
  trap 'rm -f "$DIGEST_FILE"' EXIT
  podman --connection "$CONNECTION" push ${AUTH[@]+"${AUTH[@]}"} --digestfile "$DIGEST_FILE" "$IMAGE"
  printf 'Published: %s@%s\n' "${IMAGE%:*}" "$(cat "$DIGEST_FILE")"
fi
