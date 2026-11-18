#!/usr/bin/env bash
# Stage 140 validation: the MTA 8.3 Hub and LLM proxy the developer signs in to, the migrate-with-mta golden-path
# template in Developer Hub, its legacy source mirror, and the Stage 140 workspace (image, extensions, settings).
# With --project NAME it also checks a project created from the template: its DevWorkspace, the installed MTA
# extensions, the Java language server mode and the registered Java analysis provider. Read-only.
# Usage: stages/140-mta-assisted-migration/validate.sh [--project NAME]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"
usage() { sed -n 's/^# Usage: //p' "$0" >&2; exit 1; }
PROJECT=""
case "${1:-}" in
  "") [[ $# -eq 0 ]] || usage ;;
  --project) [[ $# -eq 2 && "$2" =~ ^[a-z][a-z0-9-]{2,40}$ ]] || usage; PROJECT=$2 ;;
  *) usage ;;
esac
load_env
check_oc_logged_in

TEMPLATE_DIR="$REPO_ROOT/gitops/stages/070-advanced-app-platform/070-rhdh/templates/migrate-with-mta"
DEVFILE="$TEMPLATE_DIR/skeleton/devfile.yaml"
WORKSPACE_FILE="$TEMPLATE_DIR/skeleton/.code-workspace"
LOCK="$SCRIPT_DIR/workspace-image/artifacts.lock.json"
EXTENSIONS="/opt/rhoai3/extensions/mta-core.vsix;/opt/rhoai3/extensions/java.vsix;/opt/rhoai3/extensions/mta-java.vsix"
NS=wksp-ai-developer

echo ""
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║  Stage 140: Application Migration with MTA                       ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""

log_step "Argo CD Application (platform stage owns the resources)"
check_stage_applications 070

log_step "MTA Hub and Developer Lightspeed"
check_csv_succeeded "openshift-mta" "mta-operator"
check "MTA operator is 8.3.3" \
  "oc get csv -n openshift-mta -o jsonpath='{range .items[*]}{.metadata.name}{\"\\n\"}{end}' | grep -x 'mta-operator.v8.3.3'" \
  "mta-operator.v8.3.3"
check "Tackle LLM proxy enabled" \
  "oc get tackle mta -n openshift-mta -o jsonpath='{.spec.kai_llm_proxy_enabled}'" \
  "true"
check "Tackle Solution Server disabled (agent mode only)" \
  "oc get tackle mta -n openshift-mta -o jsonpath='{.spec.kai_solution_server_enabled}'" \
  "false"
check "Tackle hub auth enabled (OIDC sign-in)" \
  "oc get tackle mta -n openshift-mta -o jsonpath='{.spec.feature_auth_required}'" \
  "true"
check "LLM proxy model credential present" \
  "oc get secret kai-api-keys -n openshift-mta -o jsonpath='{.data.OPENAI_API_KEY}' | grep -c . || echo 0" \
  "1"
MTA_ROUTE_HOST=$(oc get route mta -n openshift-mta -o jsonpath='{.spec.host}' 2>/dev/null || echo "")
if [[ -n "$MTA_ROUTE_HOST" ]]; then
  check_http_code "Hub OIDC discovery" "https://${MTA_ROUTE_HOST}/oidc/.well-known/openid-configuration" "200"
else
  record "MTA Route exists" "no route mta in openshift-mta"
fi

log_step "Developer Hub template"
# Location targets only: the catalog's comments name template paths too.
TARGETS=$(oc get configmap catalog-runtime-rhdh -n rhdh -o jsonpath='{.data.all\.yaml}' 2>/dev/null | grep -E '^ *target: ' || true)
record "migrate-with-mta template Location in the runtime catalog" \
  "$(grep -q '/templates/migrate-with-mta/template\.yaml' <<<"$TARGETS" && echo pass || echo "Location missing")"
record_warn "Stage 130 app-migration template parked" \
  "$(grep -q '/templates/app-migration/template\.yaml' <<<"$TARGETS" && echo "still listed" || echo pass)"
check "demo source rhoai-workloads/coolstore-cart-legacy listed by the GitLab mirror bootstrap" \
  "grep -c \"'coolstore-cart-legacy'\" '$REPO_ROOT/gitops/stages/070-advanced-app-platform/070-gitlab/bootstrap-scm.py'" \
  "1"

log_step "Stage 140 workspace (template skeleton)"
PUBLISHED=$(jq -r '.published_image // ""' "$LOCK")
record "workspace image digest recorded in the lock file" \
  "$( [[ "$PUBLISHED" =~ ^quay\.io/rhoai3-coding-demo/rhoai3-ws-140@sha256:[0-9a-f]{64}$ ]] && echo pass || echo "published_image unset")"
record "skeleton devfile uses the published workspace image" \
  "$( [[ -n "$PUBLISHED" ]] && grep -qF "image: $PUBLISHED" "$DEVFILE" && echo pass || echo "digest differs")"
if [[ -n "$PUBLISHED" ]]; then
  check "workspace image resolves in the registry" \
    "oc image info --filter-by-os=linux/amd64 '$PUBLISHED' -o json | jq -r '.config.config.Labels[\"rhoai3.io.mta.version\"]'" \
    "8.3.3"
fi
record "DEFAULT_EXTENSIONS installs MTA Core and the Java language extension only" \
  "$(grep -qF "value: \"$EXTENSIONS\"" "$DEVFILE" && ! grep -q 'mta-vscode-extension' "$DEVFILE" && echo pass || echo "extension list differs")"
record "skeleton adds the quarkus-profile analysis profile" \
  "$(grep -q 'konveyor.io/target=quarkus' "$TEMPLATE_DIR/skeleton/.konveyor/profiles/quarkus-profile/profile.yaml" 2>/dev/null && echo pass || echo missing)"
record "template takes a Git repository URL and a project name" \
  "$(sed -n '/^    required:/,/^    properties:/p' "$TEMPLATE_DIR/template.yaml" | grep -E '^    - ' | tr -d ' -' | paste -sd, - | grep -qx 'repoUrl,name' && echo pass || echo "parameters differ")"
record "workspace settings: Standard Java server, baked analyzer, GenAI, Hub OIDC" \
  "$(jq -e '.settings["java.server.launchMode"] == "Standard"
        and .settings["mta-core.analyzerPath"] == "/opt/mta-analyzer-rpc/mta-analyzer-rpc"
        and .settings["mta-core.genai.enabled"] == true and .settings["mta-core.hub.auth.method"] == "oidc"
        and (.folders | length) == 1 and .folders[0].path == "."' "$WORKSPACE_FILE" >/dev/null && echo pass || echo "settings differ")"
record "skeleton workspace file is tracked in Git" \
  "$(git -C "$REPO_ROOT" ls-files --error-unmatch "$WORKSPACE_FILE" >/dev/null 2>&1 && echo pass || echo "not tracked")"

if [[ -n "$PROJECT" ]]; then
  log_step "Project $PROJECT"
  check "DevWorkspace $PROJECT is Running" \
    "oc get devworkspace '$PROJECT' -n $NS -o jsonpath='{.status.phase}'" \
    "Running"
  POD=$(oc get pod -n "$NS" -l "controller.devfile.io/devworkspace_name=$PROJECT" -o name 2>/dev/null | head -1)
  if [[ -n "$POD" ]]; then
    # One read of the workspace state; the checks below match its lines.
    STATE=$(oc exec -n "$NS" "$POD" -c development-tooling -- bash -c '
      jq -r ".[] | \"ext \(.identifier.id) \(.version)\"" /checode/remote/extensions/extensions.json 2>/dev/null
      ps -eo args | grep -q "[r]edhat.java/jdt_ws" && echo "jdt standard"
      grep -h "Registering provider: java" /checode/remote/data/logs/*/exthost*/redhat.mta-core/extension.log 2>/dev/null \
        | tail -1 | grep -q . && echo "provider java"
      [ -x /opt/mta-analyzer-rpc/mta-analyzer-rpc ] && echo "analyzer present"' 2>/dev/null || true)
    record "MTA Core 8.3.3 installed" "$(grep -qx 'ext redhat.mta-core 8.3.3' <<<"$STATE" && echo pass || echo missing)"
    record "MTA Java 8.3.3 installed" "$(grep -qx 'ext redhat.mta-java 8.3.3' <<<"$STATE" && echo pass || echo missing)"
    record "no MTA extension pack or other language extensions" \
      "$(grep -Eq '^ext redhat\.(mta-vscode-extension|mta-csharp|mta-go|mta-javascript) ' <<<"$STATE" && echo present || echo pass)"
    record "baked MTA analyzer present" "$(grep -qx 'analyzer present' <<<"$STATE" && echo pass || echo missing)"
    record_warn "Java language server in Standard mode (after the editor opened)" \
      "$(grep -qx 'jdt standard' <<<"$STATE" && echo pass || echo "not started yet")"
    record_warn "MTA Java analysis provider registered (after the MTA view opened)" \
      "$(grep -qx 'provider java' <<<"$STATE" && echo pass || echo "not registered yet")"
  else
    record "workspace pod for $PROJECT" "no pod"
  fi
  check_warn "project namespace $PROJECT-dev exists (enrollment)" \
    "oc get namespace '$PROJECT-dev' -o jsonpath='{.metadata.name}'" \
    "$PROJECT-dev"
fi

validation_summary
