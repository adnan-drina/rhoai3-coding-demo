#!/usr/bin/env bash
# Configure identity, then prepare the separately owned runtime component.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/shared/lib.sh"
load_env
check_oc_logged_in
# Core-mode Argo CD reads its settings from the kube-context namespace; refuse before any write.
argocd app sync --help 2>&1 | grep -q -- '--core' || { echo 'An argocd client with --core support is required' >&2; exit 1; }
[[ "$(oc config view --minify -o jsonpath='{.contexts[0].context.namespace}')" == openshift-gitops ]] || { echo 'Set the kube-context namespace to openshift-gitops for argocd --core' >&2; exit 1; }
REVISION="${RHOAI_STAGE060_EXPECTED_REVISION:-$(git -C "$REPO_ROOT" rev-parse HEAD)}"
[[ "$REVISION" =~ ^[0-9a-f]{40}$ ]] || { echo 'Immutable revision required' >&2; exit 1; }
# Bind immutable remote source and the exact task-owned local content before writing.
PUBLISHED="$(git -C "$REPO_ROOT" ls-remote origin refs/heads/codex/stage-010-foundation-35 | awk '{print $1}')"
[[ "$PUBLISHED" == "$REVISION" ]] || { echo 'Revision is not the published task branch' >&2; exit 1; }
git -C "$REPO_ROOT" diff --exit-code "$REVISION" -- gitops/stages/060-agent-runtime-and-agentops gitops/argocd/app-of-apps/060-agent-runtime-and-agentops.yaml stages/060-agent-runtime-and-agentops/deploy.sh stages/060-agent-runtime-and-agentops/setup-identity.py >/dev/null || { echo 'Scoped source differs from selected revision' >&2; exit 1; }
# Preflight is read-only; own App is the first write. Refuse foreign/active ownership.
python3 - "$REVISION" <<'PY'
import json,subprocess,sys
r=subprocess.run(['oc','--request-timeout=15s','get','application','openshell-identity','-n','openshift-gitops','--ignore-not-found','-o','json'],capture_output=True,text=True)
assert r.returncode==0,'Application read failed'
if r.stdout.strip():
 a=json.loads(r.stdout);m=a['metadata'];s=a['spec'];assert not m.get('ownerReferences') and not m.get('deletionTimestamp') and 'sources' not in s and not a.get('operation')
 assert s['project']=='rhoai-demo' and s['source']['repoURL']=='https://github.com/adnan-drina/rhoai3-coding-demo.git' and s['source']['path']=='gitops/stages/060-agent-runtime-and-agentops/base'
 assert s['destination']=={'server':'https://kubernetes.default.svc','namespace':'openshift-gitops'}
 assert a.get('status',{}).get('operationState',{}).get('phase') not in ('Running','Terminating'),'Active operation'
PY
python3 "$SCRIPT_DIR/setup-identity.py" --revision "$REVISION" --preflight
# Pin the authored Application template without duplicating its spec.
APP_TEMPLATE="$REPO_ROOT/gitops/argocd/app-of-apps/060-agent-runtime-and-agentops.yaml"
[[ "$(grep -c 'targetRevision: main' "$APP_TEMPLATE")" == 1 ]] || { echo 'Unexpected App template' >&2; exit 1; }
sed "s/targetRevision: main/targetRevision: $REVISION/" "$APP_TEMPLATE" > "${TMPDIR:-/tmp}/stage060-app-$$.json"
trap 'rm -f "${TMPDIR:-/tmp}/stage060-app-$$.json"' EXIT
oc --request-timeout=15s apply -f "${TMPDIR:-/tmp}/stage060-app-$$.json"
# Native core-mode CLI submits a full exact-revision operation, including native hooks.
ARGOCD_NAMESPACE=openshift-gitops argocd --core app sync openshell-identity --app-namespace openshift-gitops --strategy hook --revision "$REVISION" --timeout 300
ARGOCD_NAMESPACE=openshift-gitops argocd --core app wait openshell-identity --app-namespace openshift-gitops --sync --operation --timeout 300
oc --request-timeout=15s wait keycloakrealmimport/openshell-realm -n keycloak --for=condition=Done --timeout=300s
python3 "$SCRIPT_DIR/setup-identity.py" --revision "$REVISION"
"$SCRIPT_DIR/deploy-runtime.sh"
echo 'Identity configured; runtime controller permission approval and persona handshake remain explicit gates.'
