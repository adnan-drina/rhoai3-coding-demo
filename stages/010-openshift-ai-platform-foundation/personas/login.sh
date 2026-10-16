#!/usr/bin/env bash
# Sign the demo personas in again (browser; OAuth tokens expire) into their own kubeconfigs from .env
# (RHOAI_ADMIN_KUBECONFIG, RHOAI_DEVELOPER_KUBECONFIG), never your default kubeconfig. Changes only those two persona
# kubeconfig files; safe to rerun. --private-window prints the login URL instead of opening the browser, so an existing
# ai-admin browser session is not reused.
# Usage: stages/010-openshift-ai-platform-foundation/personas/login.sh [admin|developer] [--private-window]
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"
LOGIN="admin developer" OPEN_BROWSER=true
while [[ $# -gt 0 ]]; do
  case "$1" in
    admin|developer) LOGIN=$1; shift ;;
    --private-window) OPEN_BROWSER=false; shift ;;
    *) sed -n 's/^# Usage: //p' "$0" >&2; exit 1 ;;
  esac
done
load_env
check_oc_logged_in

login_personas() {
  local server persona var kubeconfig user actual rc=0
  server="$(oc --request-timeout=10s whoami --show-server)"
  for persona in $LOGIN; do
    if [[ "$persona" == admin ]]; then var=ADMIN; kubeconfig="${RHOAI_ADMIN_KUBECONFIG:-}"; user="${RHOAI_ADMIN_USER:-}"
    else var=DEVELOPER; kubeconfig="${RHOAI_DEVELOPER_KUBECONFIG:-}"; user="${RHOAI_DEVELOPER_USER:-}"; fi
    kubeconfig="${kubeconfig/#\~/$HOME}"
    [[ -n "$kubeconfig" && -n "$user" ]] || { log_error "set RHOAI_${var}_KUBECONFIG and RHOAI_${var}_USER in .env"; rc=1; continue; }
    mkdir -p "$(dirname "$kubeconfig")"
    if [[ ! -s "$kubeconfig" ]]; then
      # A new persona kubeconfig carries the guarded context's cluster trust (server plus CA data or its TLS setting),
      # never its user credentials, so the browser login reaches the same API server.
      (umask 077; oc config view --minify --raw -o json | jq '{apiVersion: "v1", kind: "Config",
        clusters: [{name: "persona-cluster", cluster: .clusters[0].cluster}], users: [],
        contexts: [{name: "persona", context: {cluster: "persona-cluster"}}], "current-context": "persona"}' >"$kubeconfig")
    fi
    if [[ "$OPEN_BROWSER" == true ]]; then
      echo "── Sign in as ${user} in the browser window that opens (session saved to ${kubeconfig})"
      oc login --web --kubeconfig "$kubeconfig" "$server" >/dev/null
    else
      echo "── Open the URL below in a private browser window and sign in as ${user} (session saved to ${kubeconfig})"
      oc login --web --auto-open-browser=false --kubeconfig "$kubeconfig" "$server"
    fi
    chmod 600 "$kubeconfig"
    actual="$(oc --kubeconfig "$kubeconfig" --request-timeout=10s whoami 2>/dev/null || true)"
    if [[ "$actual" == "$user" ]]; then
      log_success "${persona}: logged in as ${actual}"
    else
      rm -f "$kubeconfig"  # never leave another user's session in this persona's kubeconfig
      log_error "${persona}: logged in as '${actual:-nobody}', expected ${user}; run again with --private-window"
      rc=1
    fi
  done
  return "$rc"
}
login_personas
