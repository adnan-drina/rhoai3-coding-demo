#!/usr/bin/env bash
# Stage 040: MaaS operators, database, Gateway and policies, MaaS, models, access and Gen AI Studio.
#   deploy.sh [--revision REF]     REF defaults to GIT_REPO_BRANCH, then HEAD; it must be published and match the checkout.
# Runtime credentials (provider keys, database password) are created in the cluster, never in Git.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/shared/lib.sh"
load_env
check_oc_logged_in
require_env GIT_REPO_URL "reviewed Stage 040 source repository"
assert_required_env
ref="${GIT_REPO_BRANCH:-HEAD}"
if [[ "${1:-}" == --revision && $# -eq 2 ]]; then ref="$2"; elif [[ $# -ne 0 ]]; then echo "Usage: $0 [--revision REF]" >&2; exit 1; fi
STAGE_APPS="$REPO_ROOT/scripts/shared/stage_apps.py"

revision=$(python3 "$STAGE_APPS" select 040 --ref "$ref" --repo-url "$GIT_REPO_URL" \
  --extra scripts/platform/validate-serving-update.py --extra scripts/platform/check-operator-policy.py)
export RHOAI_STAGE040_EXPECTED_REVISION="$revision"

# Read-only: operator channels, prerequisites and ownership, serving state, node sizing.
python3 "$REPO_ROOT/scripts/platform/check-operator-policy.py" "$REPO_ROOT/gitops/stages/040-governed-models-as-a-service"
state=$("$SCRIPT_DIR/preflight.sh")
if [[ -n "$(python3 "$STAGE_APPS" names 040 | xargs oc --request-timeout=10s get applications.argoproj.io -n openshift-gitops --ignore-not-found -o name)" ]]; then
  python3 "$REPO_ROOT/scripts/platform/validate-serving-update.py" 040
else
  "$REPO_ROOT/stages/020-gpu-infrastructure-private-ai/validate.sh" --readiness
fi
"$REPO_ROOT/scripts/platform/require-node-sizing.sh"

# The Gateway listener hostnames depend on this cluster's ingress domain; they reach the Gateway component as a
# Kustomize patch on its Application, so Git stays cluster-neutral.
work=$(mktemp -d); trap 'rm -rf "$work"' EXIT
oc --request-timeout=10s get ingresscontroller default -n openshift-ingress-operator -o json |
  python3 -c '
import json, re, sys
domain = json.load(sys.stdin).get("status", {}).get("domain", "")
if not re.fullmatch(r"[a-z0-9.-]+", domain):
    sys.exit("ERROR: the default ingress domain is unavailable")
ops = [{"op": "replace", "path": "/spec/listeners/%d/hostname" % i, "value": host + "." + domain}
       for i, host in enumerate(["maas", "qwen3-8-maas"])]
target = {"group": "gateway.networking.k8s.io", "version": "v1", "kind": "Gateway",
          "name": "maas-default-gateway", "namespace": "openshift-ingress"}
print(json.dumps({"040-gateway-governance": [{"target": target, "patch": json.dumps(ops)}]}))' > "$work/patches.json"

# First change: the component Applications at the reviewed commit. Their hooks wait for the credentials below
# (040-maas-database's wait-db-credentials Job), so set those up before waiting.
python3 "$STAGE_APPS" deploy 040 --revision "$revision" --repo-url "$GIT_REPO_URL" --kustomize-patches "$work/patches.json" --no-wait
for secret in openai-provider-api-key anthropic-provider-api-key nvidia-provider-api-key; do
  RHOAI_STAGE040_PROVIDER_SECRET="$secret" "$SCRIPT_DIR/setup-provider-secret.sh"
done
# Read-only: Automatic InstallPlans resolve to the reviewed channel and minimum versions.
python3 "$REPO_ROOT/scripts/platform/check-operator-policy.py" "$REPO_ROOT/gitops/stages/040-governed-models-as-a-service" --wait 900
if [[ "$state" == fresh ]]; then "$SCRIPT_DIR/setup-database.sh" --fresh-database; else "$SCRIPT_DIR/setup-database.sh"; fi
python3 "$STAGE_APPS" wait 040 --revision "$revision" --repo-url "$GIT_REPO_URL" --timeout 2400

# The enable-maas hook turns on Gen AI tracing; re-run the maas-platform hooks once if it is still off.
if [[ "$(oc --request-timeout=10s get odhdashboardconfig odh-dashboard-config -n redhat-ods-applications -o jsonpath='{.spec.dashboardConfig.genAiTracing}')" != true ]]; then
  python3 "$STAGE_APPS" sync 040 --app 040-maas-platform --resync
  python3 "$STAGE_APPS" wait 040 --app 040-maas-platform --revision "$revision" --repo-url "$GIT_REPO_URL" --timeout 900
fi

# Publish the OpenShift MCP servers to the AI asset catalog (deferred while Stage 060 has not deployed them).
python3 "$SCRIPT_DIR/publish-catalog-mcp.py" --defer-if-absent
python3 "$SCRIPT_DIR/publish-catalog-mcp.py" --key OpenShift-MCP-ReadWrite --defer-if-absent

deadline=$((SECONDS + 900))
until "$SCRIPT_DIR/validate.sh" --readiness; do
  (( SECONDS < deadline )) || { log_error "Stage 040 readiness timed out; inspect the operator and component conditions."; exit 1; }
  sleep 10
done
log_success "Stage 040 reconciled at ${revision:0:12}; authenticated inference and Studio acceptance are separate (validate.sh --functional)."
