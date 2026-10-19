#!/usr/bin/env bash
# Register the OpenShell gateway Route in a private CLI profile and sign a persona in through Keycloak. The login URL
# is printed rather than opened in the default browser: paste it into a private window and sign in as the persona.
# The profile is the persona's XDG_CONFIG_HOME: its own openshell commands use it, and so does create.sh
# (--persona-home, or RHOAI_STAGE060_ADMIN_CLI_HOME / RHOAI_STAGE060_PERSONA_CLI_HOME). The gateway certificate does not
# name the Route host, so the profile's commands skip TLS verification (OPENSHELL_GATEWAY_INSECURE=true; demo posture);
# RUST_LOG=error keeps the CLI's TLS warning off stdout, where it would break -o json.
# Reads the Route host and issuer with the current kubeconfig; changes nothing on the cluster.
# Usage: stages/060-agent-runtime-and-agentops/sandboxes/login.sh PROFILE_DIR
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"
PROFILE=${1:-}
[[ -n "$PROFILE" && $# -eq 1 ]] || { sed -n 's/^# Usage: //p' "$0" >&2; exit 1; }
load_env
check_oc_logged_in >/dev/null
source "$SCRIPT_DIR/native.sh"
trap native_cleanup EXIT
resolve_cli
host=$(oc --request-timeout=15s get route openshell -n openshell -o jsonpath='{.spec.host}')
issuer=$(oc --request-timeout=15s get configmap openshell-identity -n openshell -o jsonpath='{.data.issuer}')
[[ -n "$host" ]] || fail "Route openshell/openshell is missing; deploy 060-openshell-runtime first"
[[ "$issuer" == https://*/realms/openshell ]] || fail "Unexpected native issuer"
(umask 077; mkdir -p "$PROFILE")
private_path "$PROFILE" || fail "Use an owner-only profile directory"
# A stand-in browser that prints the URL the CLI would open.
printf '#!/bin/sh\nprintf "\\n  Sign in (private window, as the persona):\\n  %%s\\n\\n" "$*" >&2\n' >"$WORK/open"
cp "$WORK/open" "$WORK/xdg-open"
chmod 700 "$WORK/open" "$WORK/xdg-open"
export XDG_CONFIG_HOME="$PROFILE" OPENSHELL_GATEWAY_INSECURE=true RUST_LOG=error PATH="$WORK:$PATH"
if [[ ! -f "$PROFILE/openshell/gateways/openshell/metadata.json" ]]; then
  "$CLI" gateway add "https://$host" --name openshell --oidc-issuer "$issuer"
fi
"$CLI" gateway login openshell
"$CLI" --gateway openshell whoami
log_success "Profile $PROFILE: gateway https://$host. Use it with XDG_CONFIG_HOME=$PROFILE OPENSHELL_GATEWAY_INSECURE=true RUST_LOG=error"
