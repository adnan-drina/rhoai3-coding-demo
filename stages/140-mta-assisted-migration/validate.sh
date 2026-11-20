#!/usr/bin/env bash
# Stage 140 validation: the Models-as-a-Service credentials Developer Lightspeed for MTA uses, the migrate-with-mta
# golden-path template in Developer Hub, its legacy source mirror, and the Stage 140 workspace (image, extensions,
# settings). With --project NAME it also checks a project created from the template: its DevWorkspace, the installed
# MTA extensions, the model provider settings, the Java language server mode and the registered Java analysis
# provider. Read-only.
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

log_step "Developer Lightspeed for MTA model access (Models-as-a-Service, no MTA Hub sign-in)"
# Stage 070 mounts the developer's MaaS key into every workspace as environment variables; the Stage 140 devfile
# passes MAAS_API_KEY to the extension as OPENAI_API_KEY and writes provider-settings.yaml from the other two.
check "workspace-maas-credentials mounted as environment variables in $NS" \
  "oc get secret workspace-maas-credentials -n $NS -o jsonpath='{.metadata.annotations.controller\\.devfile\\.io/mount-as}'" \
  "env"
check "workspace-maas-credentials carries the key, endpoint and model" \
  "oc get secret workspace-maas-credentials -n $NS -o json | jq -r '.data | [has(\"MAAS_API_KEY\"), has(\"MAAS_API_BASE_URL\"), has(\"MAAS_MODEL_NAME\")] | all'" \
  "true"

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
# The template's migration-target picker and the profile's lookup tables must agree: every target the picker offers
# needs a title and a label selector in profile.yaml, or the rendered profile is empty.
PROFILE="$TEMPLATE_DIR/skeleton/.konveyor/profiles/migration-target/profile.yaml"
TARGET_VALUES=$(sed -n '/^      target:/,/^  steps:/p' "$TEMPLATE_DIR/template.yaml" | sed -n '/^        enum:/,/^        enumNames:/p' \
  | sed -n 's/^        - //p')
missing=""
for t in $TARGET_VALUES; do
  [[ $(grep -c "^  \"$t\": " "$PROFILE" 2>/dev/null) -eq 2 ]] && grep -q "^  \"$t\": \"konveyor\.io/target=" "$PROFILE" \
    || missing+=" $t"
done
record "skeleton profile covers every migration target the template offers" \
  "$( [[ -n "$TARGET_VALUES" && -z "$missing" ]] && echo pass || echo "missing:${missing:- no targets}")"
record "Spring Boot 3 picker uses the MTA default-rule selector" \
  "$(grep -q '^        - spring-boot3$' "$TEMPLATE_DIR/template.yaml" \
      && grep -q '^        - Spring Boot 3$' "$TEMPLATE_DIR/template.yaml" \
      && grep -qx '  "spring-boot3": "Spring Boot 3",' "$PROFILE" \
      && grep -qx '  "spring-boot3": "konveyor.io/target=spring-boot3",' "$PROFILE" \
      && ! grep -qE 'spring-boot2-to-spring-boot3|spring6' "$TEMPLATE_DIR/template.yaml" "$PROFILE" \
      && echo pass || echo "Spring Boot 3 target differs")"
record "template takes a Git repository URL, a project name and a migration target" \
  "$(sed -n '/^    required:/,/^    properties:/p' "$TEMPLATE_DIR/template.yaml" | grep -E '^    - ' | tr -d ' -' | paste -sd, - | grep -qx 'repoUrl,name,target' && echo pass || echo "parameters differ")"
record "workspace settings: Standard Java server, baked analyzer, GenAI agent mode, no Hub" \
  "$(jq -e '.settings["java.server.launchMode"] == "Standard"
        and .settings["mta-core.analyzerPath"] == "/opt/mta-analyzer-rpc/mta-analyzer-rpc"
        and .settings["mta-core.genai.enabled"] == true and .settings["mta-core.genai.agentMode"] == true
        and (.settings | has("mta-core.hub.auth.method") | not)
        and (.folders | length) == 1 and .folders[0].path == "."' "$WORKSPACE_FILE" >/dev/null && echo pass || echo "settings differ")"
record "devfile passes the MaaS key as OPENAI_API_KEY and connects no MTA Hub" \
  "$(grep -qF 'value: "$(MAAS_API_KEY)"' "$DEVFILE" && grep -q 'name: OPENAI_API_KEY' "$DEVFILE" \
      && ! grep -qE 'name: (HUB_|FORCE_HUB)' "$DEVFILE" && echo pass || echo "env differs")"
record "devfile writes provider-settings.yaml at every start" \
  "$(sed -n '/^  postStart:/,$p' "$DEVFILE" | grep -q 'mta-provider-settings' && grep -q 'provider: ChatOpenAI' "$DEVFILE" \
      && echo pass || echo "postStart differs")"
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
[ -x /opt/mta-analyzer-rpc/mta-analyzer-rpc ] && echo "analyzer present"
[ -n "$OPENAI_API_KEY" ] && [ "$OPENAI_API_KEY" = "$MAAS_API_KEY" ] && echo "maas key"
env | grep -q "^HUB_" && echo "hub env"
grep -qF "baseURL: \"$MAAS_API_BASE_URL\"" \
  /checode/remote/data/User/globalStorage/redhat.mta-core/settings/provider-settings.yaml 2>/dev/null \
  && echo "provider settings"
grep -h "Model provider set from local config" /checode/remote/data/logs/*/exthost*/redhat.mta-core/extension.log \
  2>/dev/null | tail -1 | grep -q . && echo "model provider"' 2>/dev/null || true)
    record "MTA Core 8.3.3 installed" "$(grep -qx 'ext redhat.mta-core 8.3.3' <<<"$STATE" && echo pass || echo missing)"
    record "MTA Java 8.3.3 installed" "$(grep -qx 'ext redhat.mta-java 8.3.3' <<<"$STATE" && echo pass || echo missing)"
    record "Language Support for Java 1.58.0 installed" "$(grep -qx 'ext redhat.java 1.58.0' <<<"$STATE" && echo pass || echo "other version")"
    record "no MTA extension pack or other language extensions" \
      "$(grep -Eq '^ext redhat\.(mta-vscode-extension|mta-csharp|mta-go|mta-javascript) ' <<<"$STATE" && echo present || echo pass)"
    record "baked MTA analyzer present" "$(grep -qx 'analyzer present' <<<"$STATE" && echo pass || echo missing)"
record "workspace OPENAI_API_KEY is the MaaS key" "$(grep -qx 'maas key' <<<"$STATE" && echo pass || echo missing)"
record "no MTA Hub connection variables" "$(grep -qx 'hub env' <<<"$STATE" && echo present || echo pass)"
record "provider-settings.yaml points at the MaaS endpoint" \
  "$(grep -qx 'provider settings' <<<"$STATE" && echo pass || echo missing)"
record_warn "Java language server in Standard mode (after the editor opened)" \
      "$(grep -qx 'jdt standard' <<<"$STATE" && echo pass || echo "not started yet")"
    record_warn "MTA Java analysis provider registered (after the MTA view opened)" \
  "$(grep -qx 'provider java' <<<"$STATE" && echo pass || echo "not registered yet")"
record_warn "Developer Lightspeed model provider loaded (after the MTA view opened)" \
  "$(grep -qx 'model provider' <<<"$STATE" && echo pass || echo "not loaded yet")"
  else
    record "workspace pod for $PROJECT" "no pod"
  fi
  check_warn "project namespace $PROJECT-dev exists (enrollment)" \
    "oc get namespace '$PROJECT-dev' -o jsonpath='{.metadata.name}'" \
    "$PROJECT-dev"
fi

validation_summary
