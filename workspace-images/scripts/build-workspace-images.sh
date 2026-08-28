#!/usr/bin/env bash
# Build rhoai3 workspace overlay targets. Does not push.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CONTEXT="${ROOT}/workspace-images"
DOCKERFILE="${CONTEXT}/Dockerfile"
PREFIX="${IMAGE_PREFIX:-localhost/rhoai3}"
TAG="${IMAGE_TAG:-unreleased}"
ARCH="${BUILD_ARCH:-amd64}"
OUT_DIR="${ROOT}/workspace-images/out"
mkdir -p "${OUT_DIR}"

build_target() {
  local target="$1"
  local name="$2"
  echo "=== building ${name} (target ${target}) arch=${ARCH} ==="
  podman build \
    --pull \
    --arch "${ARCH}" \
    -f "${DOCKERFILE}" \
    --target "${target}" \
    -t "${PREFIX}-${name}:${TAG}" \
    "${CONTEXT}"
}

inspect_ids() {
  local ref="$1"
  python3 -c '
import json, subprocess, sys
ref = sys.argv[1]
out = subprocess.check_output(["podman", "inspect", ref], text=True)
data = json.loads(out)[0]
digest = data.get("Digest") or ""
image_id = data.get("Id") or ""
repodigests = data.get("RepoDigests") or []
print("ref=" + ref)
print("Id=" + image_id)
print("Digest=" + (digest or "(none — local build; no registry digest)"))
print("RepoDigests=" + (",".join(repodigests) or "(none)"))
' "$ref"
}

build_target rhoai3-udi-foundation udi-foundation
build_target rhoai3-ws-060 ws-060
build_target rhoai3-ws-070 ws-070
# Vite cannot run under qemu-amd64 on Apple Silicon (segfault). Bake first.
bash "${CONTEXT}/scripts/bake-web-dist-host.sh"
build_target rhoai3-ws-080-unsigned ws-080-unsigned

UNSIGNED_REF="${PREFIX}-ws-080-unsigned:${TAG}"
UNSIGNED_DIGEST="$(podman inspect -f '{{.Digest}}' "${UNSIGNED_REF}" || true)"
UNSIGNED_ID="$(podman inspect -f '{{.Id}}' "${UNSIGNED_REF}")"
STAMP="${UNSIGNED_DIGEST:-${UNSIGNED_ID}}"
echo "=== stamping 080 IMAGE_DIGEST=${STAMP} ==="
podman build \
  --pull \
  --arch "${ARCH}" \
  -f "${DOCKERFILE}" \
  --target rhoai3-ws-080 \
  --build-arg "IMAGE_DIGEST=${STAMP}" \
  -t "${PREFIX}-ws-080:${TAG}" \
  "${CONTEXT}"

{
  echo "# rhoai3 workspace overlay build record (local; not a registry digest unless Digest is set)"
  echo "# arch=${ARCH} tag=${TAG}"
  inspect_ids "${PREFIX}-udi-foundation:${TAG}"
  echo
  inspect_ids "${PREFIX}-ws-060:${TAG}"
  echo
  inspect_ids "${PREFIX}-ws-070:${TAG}"
  echo
  inspect_ids "${UNSIGNED_REF}"
  echo
  inspect_ids "${PREFIX}-ws-080:${TAG}"
} | tee "${OUT_DIR}/digests.txt"
echo "Wrote ${OUT_DIR}/digests.txt"
