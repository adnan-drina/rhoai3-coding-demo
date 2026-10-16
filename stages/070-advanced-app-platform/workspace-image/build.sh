#!/usr/bin/env bash
# Build the shared Stage 070 workspace image (quay.io/rhoai3-coding-demo/rhoai3-ws-080:TAG, linux/amd64) from
# verified product artifacts: the official MTA CLI Linux amd64 ZIP you downloaded (checked against
# artifacts.lock.json) and the four editor extensions the lock file names (downloaded and checked). The build context
# is a temporary directory; nothing is added to Git. verify-image.py then runs inside the image. Changes: the local
# Podman image store; with --push, the Quay tag (prints the pushed digest for the pin review). Safe to rerun.
# No cluster access. STAGE070_PODMAN_CONNECTION selects the Podman connection (default podman-machine-default).
# Usage: stages/070-advanced-app-platform/workspace-image/build.sh MTA_ZIP TAG [--push]
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"
usage() { sed -n 's/^# Usage: //p' "$0" >&2; exit 2; }
[[ $# -ge 2 && $# -le 3 ]] || usage
ARCHIVE=$1
TAG=$2
PUSH=${3:-}
[[ "$TAG" =~ ^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}$ ]] || { log_error "Invalid image tag"; exit 2; }
[[ -z "$PUSH" || "$PUSH" == --push ]] || usage
[[ -f "$ARCHIVE" ]] || { log_error "MTA archive not found: $ARCHIVE"; exit 2; }
LOCK="$SCRIPT_DIR/artifacts.lock.json"
IMAGE="quay.io/rhoai3-coding-demo/rhoai3-ws-080:$TAG"
CONNECTION="${STAGE070_PODMAN_CONNECTION:-podman-machine-default}"
CONTEXT="$(mktemp -d "${TMPDIR:-/tmp}/stage070-workspace.XXXXXX")"
trap 'rm -rf "$CONTEXT"' EXIT

sha256() { if command -v sha256sum >/dev/null; then sha256sum "$1"; else shasum -a 256 "$1"; fi | cut -d' ' -f1; }
verify() {
  [[ "$(sha256 "$1")" == "$2" ]] || { log_error "Artifact checksum mismatch: $(basename "$1")"; exit 1; }
}

# ── Prepare the build context from verified artifacts ────────────────────────────────────────────────────────────
verify "$ARCHIVE" "$(jq -r '.mta_cli.archive_sha256' "$LOCK")"
cp "$SCRIPT_DIR/Dockerfile" "$CONTEXT/Dockerfile"
mkdir "$CONTEXT/mta-cli"
# Every archive path must stay inside its install prefix before anything is extracted.
unzip -Z1 "$ARCHIVE" | jq -R -s -e 'split("\n") | map(select(. != "")) | all(startswith("/") or (split("/") | index("..")) | not)' \
  >/dev/null || { log_error "Archive path escapes its install prefix"; exit 1; }
unzip -q "$ARCHIVE" -d "$CONTEXT/mta-cli"
verify "$CONTEXT/mta-cli/$(jq -r '.mta_cli.binary_path' "$LOCK")" "$(jq -r '.mta_cli.binary_sha256' "$LOCK")"
mkdir "$CONTEXT/extensions"
while IFS=$'\t' read -r name url digest; do
  curl -fsSL --max-time 300 -o "$CONTEXT/extensions/$name.vsix" "$url"
  verify "$CONTEXT/extensions/$name.vsix" "$digest"
done < <(jq -r '.extensions[] | [.name, .url, .sha256] | @tsv' "$LOCK")
jq . "$LOCK" >"$CONTEXT/artifacts.lock.json"
log_success "Verified MTA CLI and all four required editor extensions: $CONTEXT"

# ── Build, check inside the image, optionally push ────────────────────────────────────────────────────────────────
# Select the rootless connection explicitly; never repair or prune a store.
podman --connection "$CONNECTION" info >/dev/null || { log_error "Start the selected Podman machine before running this script"; exit 1; }
podman --connection "$CONNECTION" build --platform linux/amd64 -f "$CONTEXT/Dockerfile" -t "$IMAGE" "$CONTEXT"
podman --connection "$CONNECTION" run --rm -i --platform linux/amd64 --entrypoint python3 "$IMAGE" - <"$SCRIPT_DIR/verify-image.py"
if [[ "$PUSH" == --push ]]; then
  podman --connection "$CONNECTION" push --digestfile "$CONTEXT/digest" "$IMAGE"
  DIGEST="$(cat "$CONTEXT/digest")"
  [[ "$DIGEST" =~ ^sha256:[0-9a-f]{64}$ ]] || { log_error "Registry did not return a manifest digest"; exit 1; }
  printf 'Published candidate: %s@%s\n' "${IMAGE%:*}" "$DIGEST"
  log_info "Review the registry read-back and pin changes before deploying the platform."
fi
