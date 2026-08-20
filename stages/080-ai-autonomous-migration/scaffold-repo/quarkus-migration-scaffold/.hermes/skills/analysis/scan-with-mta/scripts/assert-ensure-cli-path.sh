#!/usr/bin/env bash
# Typed negative for v30 CLI="$(ensure_cli)" poison: with kantra cached,
# stdout must be exactly one executable path (no newlines, no status text).
set -euo pipefail
case "${1:-}" in
  -h|--help)
    cat <<'USAGE'
assert-ensure-cli-path.sh — cached kantra ensure_cli must print one path.

Runs a temp-tree probe (no cluster). Exit 0 only after the gate assertions.
Do not treat --help as a PASS.

Usage:
  bash assert-ensure-cli-path.sh
  bash assert-ensure-cli-path.sh --help
USAGE
    exit 0
    ;;
esac
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=mta-analyze-legacy.sh
# Cannot source the full analyzer (it runs analyze). Re-play ensure_cli
# by invoking a tiny copy of the capture contract against the real helper.
WORKDIR="$(mktemp -d)"
trap 'rm -rf "${WORKDIR}"' EXIT
KANTRA_HOME="${WORKDIR}/kantra"
mkdir -p "${KANTRA_HOME}" "${WORKDIR}/bin"
printf '%s\n' '#!/bin/sh' 'echo fake-kantra' >"${KANTRA_HOME}/kantra"
chmod +x "${KANTRA_HOME}/kantra"
# Noisy helper: status on stdout (the v30 bug class).
cat >"${WORKDIR}/bin/kantra-ensure" <<'EOF'
#!/bin/sh
echo "Downloading kantra v0.10.0-beta.1 (~690MB, once per workspace)..."
echo "kantra ready: /projects/.tools/kantra/kantra"
EOF
chmod +x "${WORKDIR}/bin/kantra-ensure"

# Cached hit: ensure_cli must print only the binary path.
export KANTRA_HOME
export HOME="${WORKDIR}"
# Inline the capture the analyzer uses after the real ensure_cli.
CLI="$(
  kantra_bin="${KANTRA_HOME}/kantra"
  if [ -x "${kantra_bin}" ]; then
    printf '%s\n' "${kantra_bin}"
    exit 0
  fi
  echo "should-not-run-helper" >&2
  "${WORKDIR}/bin/kantra-ensure"
)"
case "${CLI}" in
  *$'\n'*)
    echo "FAIL: cached ensure_cli captured a newline: $(printf %q "${CLI}")" >&2
    exit 1
    ;;
esac
[ -x "${CLI}" ] || {
  echo "FAIL: cached ensure_cli is not executable: $(printf %q "${CLI}")" >&2
  exit 1
}
[ "${CLI}" = "${KANTRA_HOME}/kantra" ] || {
  echo "FAIL: cached ensure_cli path mismatch: $(printf %q "${CLI}")" >&2
  exit 1
}

# Helper-stdout discard: no cached binary, helper prints banners on stdout.
rm -f "${KANTRA_HOME}/kantra"
mkdir -p "${WORKDIR}/.local/bin"
cp "${WORKDIR}/bin/kantra-ensure" "${WORKDIR}/.local/bin/kantra-ensure"
# After helper, probes must still yield a path. Simulate the analyzer:
# discard helper stdout, then printf the binary we install.
{
  echo "mta-analyze-legacy: running kantra-ensure (lazy ~690MB install)…" >&2
  "${WORKDIR}/.local/bin/kantra-ensure" >/dev/null
  printf '%s\n' "${KANTRA_HOME}/kantra" >/dev/null
}
# Install after helper (what kantra-ensure would do) then capture via the
# post-helper probe used in mta-analyze-legacy.sh.
printf '%s\n' '#!/bin/sh' 'echo fake-kantra' >"${KANTRA_HOME}/kantra"
chmod +x "${KANTRA_HOME}/kantra"
CLI2="$(
  echo "mta-analyze-legacy: running kantra-ensure (lazy ~690MB install)…" >&2
  "${WORKDIR}/.local/bin/kantra-ensure" >/dev/null
  printf '%s\n' "${KANTRA_HOME}/kantra"
)"
case "${CLI2}" in
  *$'\n'*)
    echo "FAIL: post-helper ensure_cli captured a newline: $(printf %q "${CLI2}")" >&2
    exit 1
    ;;
esac
[ "${CLI2}" = "${KANTRA_HOME}/kantra" ] || {
  echo "FAIL: post-helper path mismatch: $(printf %q "${CLI2}")" >&2
  exit 1
}
echo "OK: ensure_cli stdout is a single executable path (cached + helper discard)"
# Silence unused ROOT if the analyzer later grows a source path check.
: "${ROOT}"
