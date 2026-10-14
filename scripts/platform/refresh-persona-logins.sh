#!/usr/bin/env bash
# refresh-persona-logins.sh - log the demo personas in again for persona acceptance checks.
#
# The cluster's login provider is OpenID (environment Keycloak, provider `rhbk`), so each persona signs in through the
# browser. The session is written to the persona's own kubeconfig from .env (RHOAI_ADMIN_KUBECONFIG,
# RHOAI_DEVELOPER_KUBECONFIG), never to your default kubeconfig. OAuth access tokens expire, so run this again when
# Stage 010 validate.sh warns that a persona session is missing or expired.
#
#   ./scripts/platform/refresh-persona-logins.sh              # both personas
#   ./scripts/platform/refresh-persona-logins.sh --persona developer
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/shared/lib.sh"
load_env
check_oc_logged_in

personas="admin developer"
if [[ "${1:-}" == --persona && -n "${2:-}" ]]; then
  [[ "$2" == admin || "$2" == developer ]] || { echo "ERROR: --persona admin|developer" >&2; exit 2; }
  personas="$2"
elif [[ $# -ne 0 ]]; then
  echo "Usage: $0 [--persona admin|developer]" >&2; exit 2
fi

server="$(oc --request-timeout=10s whoami --show-server)"
rc=0
for persona in $personas; do
  if [[ "$persona" == admin ]]; then var=ADMIN; kubeconfig="${RHOAI_ADMIN_KUBECONFIG:-}"; user="${RHOAI_ADMIN_USER:-}"
  else var=DEVELOPER; kubeconfig="${RHOAI_DEVELOPER_KUBECONFIG:-}"; user="${RHOAI_DEVELOPER_USER:-}"; fi
  kubeconfig="${kubeconfig/#\~/$HOME}"
  [[ -n "$kubeconfig" && -n "$user" ]] || { echo "ERROR: set RHOAI_${var}_KUBECONFIG and RHOAI_${var}_USER in .env" >&2; rc=1; continue; }
  mkdir -p "$(dirname "$kubeconfig")"
  echo "── Sign in as ${user} in the browser window that opens (session saved to ${kubeconfig})"
  oc login --web --kubeconfig "$kubeconfig" "$server" >/dev/null
  chmod 600 "$kubeconfig"
  actual="$(oc --kubeconfig "$kubeconfig" --request-timeout=10s whoami 2>/dev/null || true)"
  if [[ "$actual" == "$user" ]]; then
    echo "✓ ${persona}: logged in as ${actual}"
  else
    echo "✗ ${persona}: logged in as '${actual:-nobody}', expected ${user}; sign out of the browser session and run again" >&2
    rc=1
  fi
done
exit "$rc"
