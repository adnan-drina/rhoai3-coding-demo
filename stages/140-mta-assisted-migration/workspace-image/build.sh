#!/usr/bin/env bash
# Build the Stage 140 MTA workspace image (quay.io/rhoai3-coding-demo/rhoai3-ws-140:TAG, linux/amd64). Downloads the
# MTA 8.3.3 analyzer RPC archive and the three editor extensions artifacts.lock.json names, checks every sha256 and
# refuses archive paths that escape the build context. The build context is a temporary directory; nothing is added
# to Git. The finished image is then checked from the inside (files, versions, analyzer start). Changes: the local
# Podman image store; with --push, the Quay tag (prints the pushed digest to record in artifacts.lock.json and the
# migrate-with-mta skeleton devfile). Safe to rerun. No cluster access. STAGE140_PODMAN_CONNECTION selects the Podman
# connection (default podman-machine-default).
# Usage: stages/140-mta-assisted-migration/workspace-image/build.sh TAG [--push]
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"
usage() { sed -n 's/^# Usage: //p' "$0" >&2; exit 2; }
[[ $# -ge 1 && $# -le 2 ]] || usage
TAG=$1
PUSH=${2:-}
[[ "$TAG" =~ ^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}$ ]] || { log_error "Invalid image tag"; exit 2; }
[[ -z "$PUSH" || "$PUSH" == --push ]] || usage
LOCK="$SCRIPT_DIR/artifacts.lock.json"
IMAGE="quay.io/rhoai3-coding-demo/rhoai3-ws-140:$TAG"
CONNECTION="${STAGE140_PODMAN_CONNECTION:-podman-machine-default}"
CONTEXT="$(mktemp -d "${TMPDIR:-/tmp}/stage140-workspace.XXXXXX")"
trap 'rm -rf "$CONTEXT"' EXIT

sha256() { if command -v sha256sum >/dev/null; then sha256sum "$1"; else shasum -a 256 "$1"; fi | cut -d' ' -f1; }
verify() {
  [[ "$(sha256 "$1")" == "$2" ]] || { log_error "Artifact checksum mismatch: $(basename "$1")"; exit 1; }
}

# ── Prepare the build context from verified artifacts ────────────────────────────────────────────────────────────
cp "$SCRIPT_DIR/Dockerfile" "$CONTEXT/Dockerfile"
jq . "$LOCK" >"$CONTEXT/artifacts.lock.json"
curl -fsSL --max-time 300 -o "$CONTEXT/analyzer.zip" "$(jq -r '.analyzer_rpc.url' "$LOCK")"
verify "$CONTEXT/analyzer.zip" "$(jq -r '.analyzer_rpc.archive_sha256' "$LOCK")"
# Every archive path must stay inside the extraction directory before anything is extracted.
unzip -Z1 "$CONTEXT/analyzer.zip" | jq -R -s -e \
  'split("\n") | map(select(. != "")) | all(startswith("/") or (split("/") | index("..")) | not)' >/dev/null \
  || { log_error "Archive path escapes its install prefix"; exit 1; }
mkdir "$CONTEXT/analyzer"
unzip -q "$CONTEXT/analyzer.zip" -d "$CONTEXT/analyzer"
BINARY="$CONTEXT/analyzer/$(jq -r '.analyzer_rpc.binary_path' "$LOCK")"
verify "$BINARY" "$(jq -r '.analyzer_rpc.binary_sha256' "$LOCK")"
mv "$BINARY" "$CONTEXT/mta-analyzer-rpc"
rm -rf "$CONTEXT/analyzer" "$CONTEXT/analyzer.zip"
mkdir "$CONTEXT/extensions"
while IFS=$'\t' read -r name url digest; do
  curl -fsSL --max-time 300 -o "$CONTEXT/extensions/$name.vsix" "$url"
  verify "$CONTEXT/extensions/$name.vsix" "$digest"
done < <(jq -r '.extensions[] | [.name, .url, .sha256] | @tsv' "$LOCK")
log_success "Verified the MTA analyzer RPC and all three editor extensions: $CONTEXT"

# ── Build, check inside the image, optionally push ────────────────────────────────────────────────────────────────
# Select the rootless connection explicitly; never repair or prune a store.
podman --connection "$CONNECTION" info >/dev/null || { log_error "Start the selected Podman machine before running this script"; exit 1; }
podman --connection "$CONNECTION" build --platform linux/amd64 -f "$CONTEXT/Dockerfile" -t "$IMAGE" "$CONTEXT"
EXPECTED="$(jq -r '"/opt/mta-analyzer-rpc/mta-analyzer-rpc \(.analyzer_rpc.binary_sha256)",
  (.extensions[] | "/opt/rhoai3/extensions/\(.name).vsix \(.sha256)")' "$LOCK")"
# The checks run in the image's own shell; any failure exits non-zero and stops the script.
podman --connection "$CONNECTION" run --rm -i --platform linux/amd64 --entrypoint bash -e EXPECTED="$EXPECTED" "$IMAGE" -s <<'CHECKS'
set -euo pipefail
while read -r path digest; do
  [[ "$(sha256sum "$path" | cut -d' ' -f1)" == "$digest" ]] || { echo "checksum mismatch: $path" >&2; exit 1; }
done <<<"$EXPECTED"
[[ "$(ls /opt/rhoai3/extensions | sort | tr '\n' ' ')" == "java.vsix mta-core.vsix mta-java.vsix " ]] \
  || { echo "unexpected extension set" >&2; exit 1; }
[[ "$DEFAULT_EXTENSIONS" == "/opt/rhoai3/extensions/mta-core.vsix;/opt/rhoai3/extensions/java.vsix;/opt/rhoai3/extensions/mta-java.vsix" ]] \
  || { echo "DEFAULT_EXTENSIONS differs" >&2; exit 1; }
/opt/mta-analyzer-rpc/mta-analyzer-rpc --help 2>&1 | grep -q -- '-server-pipe' || { echo "analyzer does not start" >&2; exit 1; }
"$JAVA_HOME_21/bin/java" -version 2>&1 | grep -q 'version "21' || { echo "Java 21 missing" >&2; exit 1; }
mvn -v 2>/dev/null | grep -Eq 'Apache Maven 3\.(9\.(9|[1-9][0-9])|[1-9][0-9])' || { echo "Maven 3.9.9 or later missing" >&2; exit 1; }
node -e 'const [a,b]=process.versions.node.split(".").map(Number); process.exit(a>22||(a==22&&b>=9)?0:1)' \
  || { echo "Node 22.9 or later missing" >&2; exit 1; }
stow --version | grep -q '2\.4' || { echo "GNU Stow 2.4 missing" >&2; exit 1; }
echo "image checks passed"
CHECKS
log_success "Image checks passed: $IMAGE"
if [[ "$PUSH" == --push ]]; then
  podman --connection "$CONNECTION" push --digestfile "$CONTEXT/digest" "$IMAGE"
  DIGEST="$(cat "$CONTEXT/digest")"
  [[ "$DIGEST" =~ ^sha256:[0-9a-f]{64}$ ]] || { log_error "Registry did not return a manifest digest"; exit 1; }
  printf 'Published candidate: %s@%s\n' "${IMAGE%:*}" "$DIGEST"
  log_info "Record the digest in artifacts.lock.json (published_image) and the migrate-with-mta skeleton devfile."
fi
