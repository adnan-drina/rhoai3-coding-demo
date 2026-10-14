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
#   ./scripts/platform/refresh-persona-logins.sh --persona developer --private-window
#     prints the login URL instead of opening the browser; paste it into a private window so an existing
#     ai-admin browser session is not reused.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/shared/lib.sh"
load_env
check_oc_logged_in

personas="admin developer"; open_browser=true
while [[ $# -gt 0 ]]; do
  case "$1" in
    --persona) [[ "${2:-}" == admin || "${2:-}" == developer ]] || { echo "ERROR: --persona admin|developer" >&2; exit 2; }
               personas="$2"; shift 2 ;;
    --private-window) open_browser=false; shift ;;
    *) echo "Usage: $0 [--persona admin|developer] [--private-window]" >&2; exit 2 ;;
  esac
done

server="$(oc --request-timeout=10s whoami --show-server)"
rc=0
for persona in $personas; do
  if [[ "$persona" == admin ]]; then var=ADMIN; kubeconfig="${RHOAI_ADMIN_KUBECONFIG:-}"; user="${RHOAI_ADMIN_USER:-}"
  else var=DEVELOPER; kubeconfig="${RHOAI_DEVELOPER_KUBECONFIG:-}"; user="${RHOAI_DEVELOPER_USER:-}"; fi
  kubeconfig="${kubeconfig/#\~/$HOME}"
  [[ -n "$kubeconfig" && -n "$user" ]] || { echo "ERROR: set RHOAI_${var}_KUBECONFIG and RHOAI_${var}_USER in .env" >&2; rc=1; continue; }
  mkdir -p "$(dirname "$kubeconfig")"
  if [[ ! -s "$kubeconfig" ]]; then
    # Start a new persona kubeconfig with the guarded context's cluster trust (server plus CA data or its TLS setting),
    # never its user credentials, so the browser login can reach the same API server.
    oc config view --minify --raw -o json | python3 -c '
import json, sys
src = json.load(sys.stdin)
cluster = {"name": "persona-cluster", "cluster": src["clusters"][0]["cluster"]}
print(json.dumps({"apiVersion": "v1", "kind": "Config", "clusters": [cluster], "users": [],
                  "contexts": [{"name": "persona", "context": {"cluster": "persona-cluster"}}], "current-context": "persona"}))
' > "$kubeconfig"
    chmod 600 "$kubeconfig"
  fi
  if [[ "$open_browser" == true ]]; then
    echo "── Sign in as ${user} in the browser window that opens (session saved to ${kubeconfig})"
    oc login --web --kubeconfig "$kubeconfig" "$server" >/dev/null
  else
    echo "── Open the URL below in a private browser window and sign in as ${user} (session saved to ${kubeconfig})"
    oc login --web --auto-open-browser=false --kubeconfig "$kubeconfig" "$server"
  fi
  chmod 600 "$kubeconfig"
  actual="$(oc --kubeconfig "$kubeconfig" --request-timeout=10s whoami 2>/dev/null || true)"
  if [[ "$actual" == "$user" ]]; then
    echo "✓ ${persona}: logged in as ${actual}"
  else
    rm -f "$kubeconfig"  # never leave another user's session in this persona's kubeconfig
    echo "✗ ${persona}: logged in as '${actual:-nobody}', expected ${user}; run again with --private-window" >&2
    rc=1
  fi
done
exit "$rc"
