#!/usr/bin/env bash
# Thin launcher for the coolstore catalog stub (see coolstore-catalog-stub.py).
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
exec python3 "${root}/scripts/coolstore-catalog-stub.py" "$@"
