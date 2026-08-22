#!/usr/bin/env bash
# Copy the pin-stamped dashboard bundle into the installed agent tree.
# Fail closed (exit 1) on pin mismatch or missing artifact — caller is fail-soft.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${PROJECT_DIR:-/projects/modernized}"
: "${HERMES_HOME:=/projects/modernized/.hermes/home}"

PINS="${PROJECT_DIR}/.hermes/pins.json"
STAMP="${HERE}/PIN"
BUNDLE="${HERE}/web_dist/index.html"
ASSERT="${HERE}/assert-web-dist-pin.py"

python3 "${ASSERT}" --pins "${PINS}" --stamp "${STAMP}" --bundle "${BUNDLE}"

DEST="${HERMES_HOME}/hermes-agent/hermes_cli/web_dist"
if [ ! -d "${HERMES_HOME}/hermes-agent" ]; then
  echo "install-web-dist: Hermes agent tree missing at ${HERMES_HOME}/hermes-agent" >&2
  exit 1
fi
rm -rf "${DEST}"
mkdir -p "${DEST}"
cp -a "${HERE}/web_dist/." "${DEST}/"
test -f "${DEST}/index.html"
echo "install-web-dist: copied pin-matched web_dist -> ${DEST}"
