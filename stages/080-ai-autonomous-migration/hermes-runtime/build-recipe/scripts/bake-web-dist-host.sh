#!/usr/bin/env bash
# Bake Hermes dashboard web_dist on the *build host* (arch-independent JS).
# Do not run `vite`/`tsc` inside `podman build --arch amd64` on Apple Silicon:
# qemu user emulation segfaults (signal 11, exit 139) — same class as uv.
# Pin: Hermes tag v2026.8.19 / commit fcbd1076a93841fa88855acce810e342a5b78101
# (Operator 195540Zop) / Node 22.23.1 (UDI 3.29.1 ships that Node).
set -euo pipefail

CONTEXT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${CONTEXT}/out"
HERMES_GIT_REF="${HERMES_GIT_REF:-v2026.8.19}"
HERMES_GIT_SHA="${HERMES_GIT_SHA:-fcbd1076a93841fa88855acce810e342a5b78101}"
NODE_VER="${NODE_VER:-22.23.1}"
SRC="${OUT}/hermes-agent-${HERMES_GIT_REF}"
DST="${OUT}/web_dist"

# Node tarball sha256 from https://nodejs.org/dist/v22.23.1/SHASUMS256.txt
# measured 2026-08-25. Do not invent.
NODE_SHA_DARWIN_ARM64="ef28d8fab2c0e4314522d4bb1b7173270aa3937e93b92cb7de79c112ac1fa953"
NODE_SHA_LINUX_X64="7a8cb04b4a1df4eaf432125324b81b29a088e73570a23259a8de1c65d07fc129"

mkdir -p "${OUT}"
case "$(uname -s)-$(uname -m)" in
  Darwin-arm64)
    NODE_DIST="node-v${NODE_VER}-darwin-arm64"
    NODE_SHA="${NODE_SHA_DARWIN_ARM64}"
    ;;
  Linux-x86_64)
    NODE_DIST="node-v${NODE_VER}-linux-x64"
    NODE_SHA="${NODE_SHA_LINUX_X64}"
    ;;
  *)
    echo "ERROR: bake-web-dist-host.sh has no Node tarball for $(uname -s)-$(uname -m)" >&2
    exit 1
    ;;
esac
NODEDIR="${OUT}/${NODE_DIST}"
TARBALL="${OUT}/${NODE_DIST}.tar.gz"
if [[ ! -x "${NODEDIR}/bin/node" ]]; then
  curl -fsSL --retry 3 -o "${TARBALL}" \
    "https://nodejs.org/dist/v${NODE_VER}/${NODE_DIST}.tar.gz"
  python3 -c '
import hashlib, sys
want, path = sys.argv[1], sys.argv[2]
got = hashlib.sha256(open(path, "rb").read()).hexdigest()
if got != want:
    raise SystemExit(f"bake-web-dist-host: node tarball sha256 {got} != {want}")
' "${NODE_SHA}" "${TARBALL}"
  tar -xzf "${TARBALL}" -C "${OUT}"
fi
export PATH="${NODEDIR}/bin:${PATH}"
test "$(node -v)" = "v${NODE_VER}"

clone_ok=0
if [[ -d "${SRC}/.git" ]]; then
  if [[ "$(git -C "${SRC}" rev-parse HEAD)" == "${HERMES_GIT_SHA}" ]] \
     && [[ "$(git -C "${SRC}" describe --tags --exact-match HEAD 2>/dev/null || true)" == "${HERMES_GIT_REF}" ]] \
     && [[ -z "$(git -C "${SRC}" status --porcelain)" ]]; then
    clone_ok=1
  fi
fi
if [[ "${clone_ok}" -ne 1 ]]; then
  rm -rf "${SRC}"
  git clone --depth 1 --branch "${HERMES_GIT_REF}" \
    https://github.com/NousResearch/hermes-agent.git "${SRC}"
fi
test "$(git -C "${SRC}" rev-parse HEAD)" = "${HERMES_GIT_SHA}"
test "$(git -C "${SRC}" describe --tags --exact-match HEAD)" = "${HERMES_GIT_REF}"
test -z "$(git -C "${SRC}" status --porcelain)"

cd "${SRC}"
npm install --workspace web --no-audit --no-fund
npm run build --workspace web
test -s "${SRC}/hermes_cli/web_dist/index.html"
rm -rf "${DST}"
mkdir -p "${DST}"
cp -a "${SRC}/hermes_cli/web_dist/." "${DST}/"
test -s "${DST}/index.html"
echo "baked ${DST} files=$(find "${DST}" -type f | wc -l | tr -d ' ')"
