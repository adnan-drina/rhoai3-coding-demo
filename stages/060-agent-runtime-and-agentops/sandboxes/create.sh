#!/usr/bin/env bash
# Provision, or check, the persistent OpenCode or Hermes sandbox that ai-admin owns in the ai-agents workspace, through
# the native OpenShell API and the pinned CLI only (never generated Pod edits). It needs the 060-openshell-runtime
# Application Synced and Healthy at --revision (whose published content must equal these scripts and inputs), the
# dedicated MaaS subscription Ready, the runtime image built (images/), and the genuine ai-admin sessions: a private
# `oc login` kubeconfig and the persona's `openshell gateway login` profile (XDG_CONFIG_HOME of that login).
# Without --apply it is read-only and checks an earlier setup against its journal. With --apply it imports the
# provider profile, mints a 30-day MaaS key on the agent's subscription (held only by the native encrypted provider),
# creates the provider, the sandbox template and (once, on an empty fleet with --expected-policy-hash) the complete
# gateway-global policy, then creates the sandbox and uploads its start script, config and listener secret.
# Safe to rerun: every step adopts only what its owner-only journal recorded and refuses anything else; an unknown
# create outcome stops for review instead of creating again. Prints a JSON receipt without credentials.
# Usage: stages/060-agent-runtime-and-agentops/sandboxes/create.sh opencode|hermes --revision SHA [--apply] [--expected-policy-hash HASH] [--state-dir DIR] [--persona-home DIR] [--persona-kubeconfig FILE]
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"
usage() { sed -n 's/^# Usage: //p' "$0" >&2; exit 1; }
RUNTIME=${1:-}
[[ "$RUNTIME" == opencode || "$RUNTIME" == hermes ]] || usage
shift
REVISION="" APPLY=false EXPECTED_POLICY_HASH="" STATE_DIR=""
PERSONA_HOME=${RHOAI_STAGE060_ADMIN_CLI_HOME:-} PERSONA_KUBECONFIG=${RHOAI_STAGE060_ADMIN_KUBECONFIG:-}
while [[ $# -gt 0 ]]; do
  case "$1" in
    --revision) REVISION=${2:-}; shift 2 ;;
    --apply) APPLY=true; shift ;;
    --expected-policy-hash) EXPECTED_POLICY_HASH=${2:-}; shift 2 ;;
    --state-dir) STATE_DIR=${2:-}; shift 2 ;;
    --persona-home) PERSONA_HOME=${2:-}; shift 2 ;;
    --persona-kubeconfig) PERSONA_KUBECONFIG=${2:-}; shift 2 ;;
    *) usage ;;
  esac
done
[[ -n "$REVISION" && -n "$PERSONA_HOME" && -n "$PERSONA_KUBECONFIG" ]] || usage
load_env
check_oc_logged_in >/dev/null
source "$SCRIPT_DIR/native.sh"
trap native_cleanup EXIT
STATE_DIR=${STATE_DIR:-$STATE_ROOT/$RUNTIME}
[[ -n "${KUBECONFIG:-}" ]] || fail "Set KUBECONFIG to the private bootstrap (cluster-admin) kubeconfig"
BOOTSTRAP_KUBECONFIG=$KUBECONFIG

setup_init
setup_preflight "$REVISION" "$SCRIPT_DIR/create.sh" "$SCRIPT_DIR/native.sh"
session_open admin
session_open owner "$PERSONA_HOME"
setup_inventory
setup_policy_input
if [[ "$APPLY" == true ]]; then
  setup_provision
fi
setup_check
printf '%s\n' "$RECEIPT"
