#!/usr/bin/env bash
# Bake Hermes dashboard web_dist on the *build host* (arch-independent JS).
# Do not run `vite`/`tsc` inside `podman build --arch amd64` on Apple Silicon:
# qemu user emulation segfaults (signal 11, exit 139) — same class as uv.
# Pin: Hermes tag v2026.8.19 / Node 22.23.1 (UDI 3.29.1 ships that Node).
set -euo pipefail

CONTEXT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${CONTEXT}/out"
HERMES_GIT_REF="${HERMES_GIT_REF:-v2026.8.19}"
NODE_VER="${NODE_VER:-22.23.1}"
SRC="${OUT}/hermes-agent-${HERMES_GIT_REF}"
DST="${OUT}/web_dist"

mkdir -p "${OUT}"
case "$(uname -s)-$(uname -m)" in
  Darwin-arm64)
    NODE_DIST="node-v${NODE_VER}-darwin-arm64"
    ;;
  Linux-x86_64)
    NODE_DIST="node-v${NODE_VER}-linux-x64"
    ;;
  *)
    echo "ERROR: bake-web-dist-host.sh has no Node tarball for $(uname -s)-$(uname -m)" >&2
    exit 1
    ;;
esac
NODEDIR="${OUT}/${NODE_DIST}"
if [[ ! -x "${NODEDIR}/bin/node" ]]; then
  curl -fsSL --retry 3 -o "${OUT}/${NODE_DIST}.tar.gz" \
    "https://nodejs.org/dist/v${NODE_VER}/${NODE_DIST}.tar.gz"
  tar -xzf "${OUT}/${NODE_DIST}.tar.gz" -C "${OUT}"
fi
export PATH="${NODEDIR}/bin:${PATH}"
test "$(node -v)" = "v${NODE_VER}"

if [[ ! -d "${SRC}/.git" ]]; then
  git clone --depth 1 --branch "${HERMES_GIT_REF}" \
    https://github.com/NousResearch/hermes-agent.git "${SRC}"
fi
cd "${SRC}"
npm install --workspace web --no-audit --no-fund
npm run build --workspace web
test -s "${SRC}/hermes_cli/web_dist/index.html"
rm -rf "${DST}"
mkdir -p "${DST}"
cp -a "${SRC}/hermes_cli/web_dist/." "${DST}/"
test -s "${DST}/index.html"
echo "baked ${DST} files=$(find "${DST}" -type f | wc -l | tr -d ' ')"
