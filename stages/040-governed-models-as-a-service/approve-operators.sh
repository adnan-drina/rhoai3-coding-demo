#!/usr/bin/env bash
# Compatibility entrypoint: read-only Automatic readiness; never approves a plan.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
source "$ROOT/scripts/shared/lib.sh"
REPO_ROOT="${RHOAI_ENV_ROOT:-$ROOT}"
load_env
check_oc_logged_in
python3 "$ROOT/scripts/platform/check-operator-policy.py" "$ROOT/gitops/stages/040-governed-models-as-a-service/base" --wait 900
