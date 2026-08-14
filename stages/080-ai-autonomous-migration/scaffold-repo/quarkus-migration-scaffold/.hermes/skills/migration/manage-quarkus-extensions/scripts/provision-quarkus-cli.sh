#!/usr/bin/env bash
# W1 — user-space Quarkus CLI + RH registry-first config (no root / no custom image).
#
# Install method: official Quarkus CLI tooling via JBang
#   https://quarkus.io/guides/cli-tooling
# RH docs point at that guide from "Preparing your environment"
#   (Red Hat build of Quarkus Getting started).
# Registry client shape: RH docs — ~/.quarkus/config.yaml with
#   registry.quarkus.redhat.com first (+ offering: redhat).
#
# Idempotent: skips jbang/CLI download when `quarkus` is already on PATH;
# always re-asserts RH-first config.yaml (cheap, fail-closed for community-first).
set -euo pipefail

case "${1:-}" in
  -h|--help)
    cat <<'USAGE'
provision-quarkus-cli.sh — install Quarkus CLI (JBang) + RH-first registry config.

Usage:
  bash provision-quarkus-cli.sh

Exit: 0 on success or soft Maven-fallback WARN; 1 if RH registry config fails
lint while being written. Does not create Quarkus apps (DD1 create path retired).
USAGE
    exit 0
    ;;
esac

export PATH="${HOME}/.local/bin:${HOME}/.jbang/bin:${PATH}"

mkdir -p "${HOME}/.local/bin" "${HOME}/.quarkus"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHECK_RH="${SCRIPT_DIR}/../../bootstrap-quarkus-project/scripts/check-rh-registry-first.py"

write_rh_registry_config() {
  printf '%s\n' \
    'registries:' \
    '  - registry.quarkus.redhat.com:' \
    '      offering: redhat' \
    '  - registry.quarkus.io' \
    > "${HOME}/.quarkus/config.yaml"
}

ensure_path_rc() {
  local marker="# quarkus-migration-scaffold: quarkus-cli path"
  local line='export PATH="${HOME}/.local/bin:${HOME}/.jbang/bin:${PATH}"'
  local rc
  for rc in "${HOME}/.bashrc" "${HOME}/.zshrc"; do
    touch "${rc}"
    if ! grep -qF "${marker}" "${rc}" 2>/dev/null; then
      printf '\n%s\n%s\n' "${marker}" "${line}" >> "${rc}"
    fi
  done
}

write_rh_registry_config
ensure_path_rc

if [ -f "${CHECK_RH}" ]; then
  python3 "${CHECK_RH}" "${HOME}/.quarkus/config.yaml" \
    || { echo "FAIL: RH registry not first in ${HOME}/.quarkus/config.yaml" >&2; exit 1; }
  echo "OK: ~/.quarkus/config.yaml has registry.quarkus.redhat.com first"
else
  echo "WARN: check-rh-registry-first.py missing — config written but not linted" >&2
fi

if command -v quarkus >/dev/null 2>&1; then
  echo "OK: Quarkus CLI already on PATH ($(command -v quarkus))"
  quarkus version 2>/dev/null || true
  exit 0
fi

echo "Provisioning Quarkus CLI via JBang (official CLI tooling path)…"
if ! command -v jbang >/dev/null 2>&1; then
  curl -fsSL --retry 3 --retry-delay 5 --retry-all-errors --max-time 120 \
    https://sh.jbang.dev | bash -s - \
    || { echo "WARN: jbang install failed — Maven quarkus:* fallback remains (W3)" >&2; exit 0; }
  export PATH="${HOME}/.local/bin:${HOME}/.jbang/bin:${PATH}"
fi

if ! command -v jbang >/dev/null 2>&1; then
  # Some installs only drop ~/.jbang/bin/jbang without updating PATH yet.
  if [ -x "${HOME}/.jbang/bin/jbang" ]; then
    export PATH="${HOME}/.jbang/bin:${PATH}"
  else
    echo "WARN: jbang still absent after setup — skip Quarkus CLI (Maven fallback)" >&2
    exit 0
  fi
fi

# RH GA needed when resolving RH-platform-adjacent CLI bits.
jbang config set run.repos "central,https://maven.repository.redhat.com/ga/" >/dev/null 2>&1 || true

curl -fsSL --retry 3 --retry-delay 5 --retry-all-errors --max-time 120 \
  https://sh.jbang.dev | bash -s - trust add https://repo1.maven.org/maven2/io/quarkus/quarkus-cli/ \
  || true

jbang app install --fresh --force quarkus@quarkusio \
  || { echo "WARN: quarkus@quarkusio install failed — Maven fallback remains (W3)" >&2; exit 0; }

export PATH="${HOME}/.local/bin:${HOME}/.jbang/bin:${PATH}"
if command -v quarkus >/dev/null 2>&1; then
  echo "OK: Quarkus CLI installed at $(command -v quarkus)"
  quarkus version 2>/dev/null || true
else
  echo "WARN: quarkus binary not on PATH after install — Maven fallback remains (W3)" >&2
fi
exit 0
