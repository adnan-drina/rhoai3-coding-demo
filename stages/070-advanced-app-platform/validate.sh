#!/usr/bin/env bash
# Stage 070 validation (read-only, no inference): the component Applications and selected operators; GitLab, its
# NooBaa storage and scoped integration Secrets; identity and Dev Spaces; SonarQube and internal-registry delivery;
# MTA native Agents and Developer Lightspeed; the signing service and Developer Hub; and the corrected security
# boundaries (no retained credential annotations, server-side diff, scoped identity clients, ingress policies).
# --static checks only the repository: the stage renders, its components are disjoint, and the scripts parse.
# Usage: stages/070-advanced-app-platform/validate.sh [--static | --revision <commit>]
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
if [[ "${1:-}" == --static ]]; then
  oc kustomize "$REPO_ROOT/gitops/stages/070-advanced-app-platform" >/dev/null
  "$REPO_ROOT/scripts/stage-apps.sh" check-static 070
  bash -n "$SCRIPT_DIR/deploy.sh" "$SCRIPT_DIR/validate.sh"
  echo 'PASS: Stage 070 authoring checks. Live deployment and model-dependent checks are separate.'
  exit 0
fi
EXPECTED_REVISION="${RHOAI_STAGE070_EXPECTED_REVISION:-}"
if [[ "${1:-}" == --revision && $# -eq 2 ]]; then
  EXPECTED_REVISION="$2"
elif [[ $# -ne 0 ]]; then
  sed -n 's/^# Usage: //p' "$0" >&2; exit 1
fi
source "$REPO_ROOT/scripts/lib.sh"
load_env
check_oc_logged_in

# ── Corrected security boundaries ─────────────────────────────────────────────
# Credential values stay inside jq and curl pipes; nothing is printed or passed as an argument.
LAST_APPLIED=kubectl.kubernetes.io/last-applied-configuration
denied() { [[ $(oc --request-timeout=15s auth can-i "$1" "$2" -n "$3" --as="$4" 2>/dev/null || true) == no ]] && echo pass || echo "allowed or unavailable"; }
security_boundaries() {
  local ns name sa apps components selected base secret target token realm status
  for pair in rhdh/rhdh-gitlab openshift-gitops/rhdh-local-user gitlab-system/gitlab-oidc openshift-mta/kai-api-keys \
      app-platform-build/sonarqube-credentials openshift-devspaces/gitlab-oauth-config gitlab-system/stage070-scm-provisioner; do
    record "No client-apply credential annotation on $pair" "$(oc --request-timeout=15s get secret "${pair#*/}" -n "${pair%%/*}" -o json 2>/dev/null |
      jq -r --arg a "$LAST_APPLIED" 'if (.metadata.annotations // {} | has($a)) then "annotation retained" else "pass" end' || echo "unreadable")"
  done
  # The developer platform estate, beyond the named sample: no Secret retains a client-apply annotation.
  for ns in $( { printf '%s\n' gitlab-system rhdh openshift-mta openshift-devspaces openshift-gitops app-platform-build sonarqube \
      trusted-artifact-signer wksp-ai-developer wksp-ai-admin coolstore-dev
      oc --request-timeout=15s get namespaces -l rhoai3.redhat.com/pipeline-project=true -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{end}'; } | sort -u); do
    record "No retained Secret annotation in $ns" "$(oc --request-timeout=15s get secrets -n "$ns" -o json 2>/dev/null |
      jq -r --arg a "$LAST_APPLIED" 'if all(.items[]; .metadata.annotations // {} | has($a) | not) then "pass" else "annotation retained" end' || echo "unreadable")"
  done
  apps=$(oc --request-timeout=15s get applications.argoproj.io -n openshift-gitops -o json)
  # Generated project-*/runtime-* Applications carry the stage label too; components are the rhoai-demo ones.
  record "Server-side diff on Stage 070 and generated Applications" "$(jq -r '[.items[] | select((.metadata.labels["demo.rhoai.io/stage"] == "070"
      and .spec.project == "rhoai-demo") or .spec.project == "platform-projects" or .spec.project == "runtime-projects")]
    | if length > 0 and all(.[]; .metadata.annotations["argocd.argoproj.io/compare-options"] // "" | split(",") | index("ServerSideDiff=true"))
      then "pass" else "missing ServerSideDiff=true" end' <<<"$apps")"
  components='[.items[] | select(.metadata.labels["demo.rhoai.io/stage"] == "070" and .spec.project == "rhoai-demo")]'
  record "No client-apply migration for declarative Secrets" "$(jq -r "$components"' | if length > 0
    and all(.[]; .spec.syncPolicy.syncOptions // [] | index("ClientSideApplyMigration=false")) then "pass" else "missing ClientSideApplyMigration=false" end' <<<"$apps")"
  record "Only named controller PVC fields ignored" "$(jq -r "$components"' | [.[].spec.ignoreDifferences[]? | select(.kind == "PersistentVolumeClaim")]
    | if length > 0 and all(.[]; (.name // "") != "" and (.namespace // "") != "" and .jsonPointers == ["/spec/volumeName"]) then "pass" else "broad PVC exceptions" end' <<<"$apps")"
  sa=system:serviceaccount:gitlab-system:gitlab-integrations-bootstrap
  record "Idle bootstrap cannot exec" "$(denied create pods/exec gitlab-system "$sa")"
  for ns in gitlab-system rhdh app-platform-build openshift-devspaces; do
    record "Idle bootstrap cannot write Secrets in $ns" "$(denied create secrets "$ns" "$sa")"
  done
  for pair in rhdh/job-configure-rhdh openshift-mta/job-configure-mta-sso trusted-artifact-signer/configure-signing; do
    record "No master-realm Secret for ${pair#*/}" "$(denied get secret/keycloak-initial-admin keycloak "system:serviceaccount:${pair%%/*}:${pair#*/}")"
  done
  base="https://$(oc --request-timeout=15s get route keycloak -n keycloak -o jsonpath='{.spec.host}')"
  for row in rhdh/stage070-rhdh-provisioner/rhdh openshift-mta/stage070-mta-provisioner/mta-hub \
      trusted-artifact-signer/stage070-signing-provisioner/trusted-artifact-signer gitlab-system/stage070-scm-provisioner/gitlab; do
    IFS=/ read -r ns secret target <<<"$row"
    token=$(oc --request-timeout=15s get secret "$secret" -n "$ns" -o json |
      jq -j '.data | "grant_type=client_credentials&client_id=\(.client_id | @base64d | @uri)&client_secret=\(.client_secret | @base64d | @uri)"' |
      curl -s --max-time 30 --data-binary @- "$base/realms/platform/protocol/openid-connect/token" | jq -r '.access_token // empty')
    if [[ -z "$token" ]]; then record "Scoped client $secret obtains a token" "token request failed"; continue; fi
    record "Scoped client $secret reads its platform configuration" "$(curl -s --max-time 30 --config <(printf 'header = "Authorization: Bearer %s"\n' "$token") \
      "$base/admin/realms/platform/clients?clientId=$target" | jq -r --arg t "$target" 'if length == 1 and .[0].clientId == $t then "pass" else "unexpected answer" end' || echo "request failed")"
    for realm in sso master; do
      status=$(curl -s --max-time 30 -o /dev/null -w '%{http_code}' --config <(printf 'header = "Authorization: Bearer %s"\n' "$token") \
        "$base/admin/realms/$realm" || echo 000)
      [[ "$status" == 401 || "$status" == 403 ]] && R=pass || R="HTTP $status"
      record "Scoped client $secret cannot administer realm $realm" "$R"
    done
  done
  # Developer Hub reads Argo CD with the operator-managed rhdh local user; its copy must match (compared in jq).
  record "Argo CD reader is the operator local user and Developer Hub holds the same token" "$(jq -n -r \
    --slurpfile reader <(oc --request-timeout=15s get secret rhdh-local-user -n openshift-gitops -o json) \
    --slurpfile copy <(oc --request-timeout=15s get secret rhdh-secrets -n rhdh -o json) '
    ($reader[0].data.apiToken | @base64d) as $t | ($copy[0].data.RHDH_ARGOCD_TOKEN // "" | @base64d) as $c
    | ($t | split(".")[1] | gsub("-"; "+") | gsub("_"; "/") | if length % 4 == 0 then . else . + ("=" * (4 - length % 4)) end | @base64d | fromjson) as $claims
    | if $claims.sub == "rhdh:apiKey" and $c == $t then "pass" else "reader or copy differs" end' 2>/dev/null || echo "unreadable")"
  record "Hub bootstrap cannot read the Argo CD admin password" "$(denied get secret/openshift-gitops-cluster openshift-gitops "$sa")"
  # The pipeline control token belongs to the platform-provisioner technical user, never the SonarQube admin.
  record "SonarQube control token belongs to the provisioner" "$(oc --request-timeout=15s get secret sonarqube-credentials -n app-platform-build \
    -o jsonpath='{.metadata.annotations.rhoai3\.io/control-token-owner}' | grep -qx platform-provisioner && echo pass || echo "other owner")"
  for ns in gitlab-system sonarqube rhdh app-platform-build trusted-artifact-signer; do
    record "Ingress NetworkPolicy installed in $ns" "$(oc --request-timeout=15s get networkpolicy platform-ingress -n "$ns" -o json 2>/dev/null |
      jq -r 'if .spec.policyTypes == ["Ingress"] then "pass" else "policy differs" end' || echo missing)"
  done
}

log_step 'Stage 070 GitOps and selected operators'
check_stage_applications 070 "$EXPECTED_REVISION"
for row in \
  'openshift-operators devspaces devspacesoperator.v3.31.' \
  'rhdh-operator rhdh rhdh-operator.v1.10.6' \
  'openshift-mta mta-operator mta-operator.v8.3.2' \
  'openshift-operators openshift-pipelines-operator-rh openshift-pipelines-operator-rh.v1.24.' \
  'openshift-operators rhtas-operator rhtas-operator.v1.5.'; do
  read -r ns subscription csv <<< "$row"
  if [[ "$ns" == openshift-operators ]]; then
    # Automatic versioned channels admit patch updates. startingCSV is an
    # installation floor, not an installed-version lock; Pipelines sets none (1.24.2 observed live).
    installed=$(oc get subscription "$subscription" -n "$ns" -o jsonpath='{.status.installedCSV}' 2>/dev/null || true)
    pattern="^${csv//./\\.}[0-9]+$"
    check "$subscription stays on selected minor" "printf '%s' '$installed' | contains -E '$pattern' && echo SELECTED" 'SELECTED'
    if [[ -n "$installed" ]]; then
      check "$installed succeeded" "oc get csv '$installed' -n '$ns' -o jsonpath='{.status.phase}'" 'Succeeded'
    fi
  else
    check "$subscription installed revision" \
      "oc get subscription '$subscription' -n '$ns' -o jsonpath='{.status.installedCSV}'" "$csv"
    check "$csv succeeded" "oc get csv '$csv' -n '$ns' -o jsonpath='{.status.phase}'" 'Succeeded'
  fi
done

log_step 'GitLab native deployment and scoped NooBaa storage'
check 'GitLab release recorded after migrations/readiness' \
  "oc get configmap gitlab-gitlab-chart-info -n gitlab-system -o jsonpath='{.data.gitlabVersion}' | sed 's/^v//'" '19.4.2'
check 'GitLab webservice ready' "oc get deployment gitlab-webservice-default -n gitlab-system -o jsonpath='{.status.readyReplicas}'" '1'
check 'GitLab Gitaly ready' "oc get statefulset gitlab-gitaly -n gitlab-system -o jsonpath='{.status.readyReplicas}'" '1'
check 'GitLab sidekiq ready' "oc get deployment gitlab-sidekiq-all-in-1-v2 -n gitlab-system -o jsonpath='{.status.readyReplicas}'" '1'
for bucket in lfs artifacts uploads packages backups backup-tmp; do
  check "GitLab $bucket bucket bound" "oc get obc 'gitlab-$bucket' -n gitlab-system -o jsonpath='{.status.phase}'" 'Bound'
done
# Rails reads its host from the bootstrap-rendered *-runtime ConfigMaps; a chart ConfigMap keeps the placeholder host,
# which Sidekiq would put into webhook payloads (project pipelines then never trigger).
for workload in deployment/gitlab-webservice-default deployment/gitlab-sidekiq-all-in-1-v2 deployment/gitlab-toolbox; do
  check "GitLab $workload uses its runtime config" "oc get $workload -n gitlab-system -o json | jq -r '[.spec.template.spec.volumes[] | .configMap.name, (.projected.sources[]?.configMap.name) | select(. != null and test(\"^gitlab-(webservice|sidekiq|toolbox)(-runtime)?$\"))] | if length > 0 and all(endswith(\"-runtime\")) then \"RUNTIME\" else \"CHART\" end'" 'RUNTIME'
done
GITLAB_HOST=$(oc get route gitlab -n gitlab-system -o jsonpath='{.spec.host}' 2>/dev/null || true)
if [[ -n "$GITLAB_HOST" ]]; then
  check_http_code 'GitLab readiness endpoint' "https://${GITLAB_HOST}/-/readiness" '200'
else
  check 'GitLab Route exists' 'echo missing' 'present'
fi
for pair in 'rhdh gitlab-publisher' 'rhdh gitlab-catalog-reader' 'app-platform-build gitlab-enroller' 'openshift-devspaces gitlab-oauth-config' 'gitlab-system gitlab-oidc' 'gitlab-system gitlab-demo-operator'; do
  read -r ns name <<< "$pair"
  check "Scoped integration Secret $ns/$name exists" "oc get secret '$name' -n '$ns' -o jsonpath='{.metadata.name}'" "$name"
done
check 'GitLab enrollment reconciler installed' "oc get cronjob project-provisioner -n app-platform-build -o jsonpath='{.metadata.name}'" 'project-provisioner'

log_step 'Existing identity and Dev Spaces'
check 'Reused Keycloak Ready' "oc get keycloak keycloak -n keycloak -o jsonpath='{.status.conditions[?(@.type==\"Ready\")].status}'" 'True'
check 'Platform realm imported' "oc get keycloakrealmimport platform-realm -n keycloak -o jsonpath='{.status.conditions[?(@.type==\"Done\")].status}'" 'True'
check 'Dev Spaces Active' "oc get checluster devspaces -n openshift-devspaces -o jsonpath='{.status.chePhase}'" 'Active'
check 'Dev Spaces per-workspace storage' "oc get checluster devspaces -n openshift-devspaces -o jsonpath='{.spec.devEnvironments.storage.pvcStrategy}'" 'per-workspace'
check 'Dev Spaces GitLab OAuth configured' "oc get checluster devspaces -n openshift-devspaces -o jsonpath='{.spec.gitServices.gitlab[0].secretName}'" 'gitlab-oauth-config'
for ns in wksp-ai-developer wksp-ai-admin; do
  check "$ns standing workspace uses GitLab" "oc get devworkspace coolstore-inventory-service -n '$ns' -o jsonpath='{.spec.template.projects[0].git.remotes.origin}'" "https://${GITLAB_HOST}/rhoai-workloads/coolstore-inventory-service.git"
done

log_step 'SonarQube and internal-registry delivery'
check 'SonarQube ready' "oc get statefulset sonarqube -n sonarqube -o jsonpath='{.status.readyReplicas}'" '1'
SONAR_HOST=$(oc get route sonarqube -n sonarqube -o jsonpath='{.spec.host}' 2>/dev/null || true)
if [[ -n "$SONAR_HOST" ]]; then check_http_code 'SonarQube reachable' "https://${SONAR_HOST}/api/system/status" '200'; fi
check 'TektonConfig ready' "oc get tektonconfig config -o jsonpath='{.status.conditions[?(@.type==\"Ready\")].status}'" 'True'
check 'Internal registry available' "oc get clusteroperator image-registry -o jsonpath='{.status.conditions[?(@.type==\"Available\")].status}'" 'True'
check 'Coolstore pipeline installed' "oc get pipelines.tekton.dev app-push -n coolstore-dev -o jsonpath='{.metadata.name}'" 'app-push'
check 'Coolstore initial-build receipt bound' "oc get configmap initial-build-receipt -n coolstore-dev -o jsonpath='{.data.source_commit}' | contains -E '^[0-9a-f]{40}$' && echo BOUND" 'BOUND'
check 'Coolstore uses digest from internal registry' "oc get deployment coolstore-inventory-service -n coolstore-dev -o jsonpath='{.spec.template.spec.containers[0].image}' | contains -E '^image-registry.openshift-image-registry.svc:5000/coolstore-dev/coolstore-inventory-service@sha256:[0-9a-f]{64}$' && echo PINNED" 'PINNED'
check 'Coolstore deployment ready' "oc get deployment coolstore-inventory-service -n coolstore-dev -o jsonpath='{.status.readyReplicas}'" '1'
check 'Runtime is reconciled from delivery Git' "oc get application runtime-coolstore-inventory-service -n openshift-gitops -o jsonpath='{.spec.source.repoURL}'" "https://${GITLAB_HOST}/rhoai-delivery/"
check 'Webhook listener ready' "oc get deployment el-gitlab -n coolstore-dev -o jsonpath='{.status.readyReplicas}'" '1'
check 'Pipeline may push its own images' "oc auth can-i update imagestreams --subresource=layers -n coolstore-dev --as=system:serviceaccount:coolstore-dev:image-builder" 'yes'
# A normal authorization denial exits 1; preserve its real 'no' output. API
# failures have no such stdout and still fail the expected-output check.
check 'Pipeline cannot push another project image' "oc auth can-i update imagestreams --subresource=layers -n app-platform-build --as=system:serviceaccount:coolstore-dev:image-builder || true" 'no'

log_step 'MTA 8.3 native Agents (Developer Preview; no inference request)'
check 'MTA Hub authentication retained' "oc get tackle mta -n openshift-mta -o jsonpath='{.spec.feature_auth_required}'" 'true'
check 'MTA platform IdP retained' "oc get tackle mta -n openshift-mta -o jsonpath='{.spec.idp_primary}'" 'true'
check 'MTA native agentic component enabled' "oc get tackle mta -n openshift-mta -o jsonpath='{.spec.agentic_enabled}'" 'true'
check 'MTA native Gateway credential binding' "oc get gateways.konveyor.io maas-qwen -n openshift-mta -o jsonpath='{.spec.credentialRef.secretName}'" 'kai-api-keys'
check 'MTA Gateway uses MaaS canonical model ID' "oc get gateways.konveyor.io maas-qwen -n openshift-mta -o jsonpath='{.spec.model.name}'" 'publishers/internal-models/models/qwen3-8-27b'
check 'MTA credential provisioned' "oc get secret kai-api-keys -n openshift-mta -o jsonpath='{.metadata.name}'" 'kai-api-keys'
check 'MTA native agentic controller ready' "test \"\$(oc get deployment agentic-controller -n openshift-mta -o jsonpath='{.status.readyReplicas}')\" = 1 && echo READY" 'READY'
check 'MTA memory sizing targets only its controller' "test \"\$(oc get vpa mta-agentic-controller -n openshift-mta -o jsonpath='{.spec.targetRef.kind}/{.spec.targetRef.name}')\" = Deployment/agentic-controller && echo SCOPED" 'SCOPED'
check 'MTA memory recommendation is available' "oc get vpa mta-agentic-controller -n openshift-mta -o jsonpath='{.status.conditions[?(@.type==\"RecommendationProvided\")].status}'" 'True'

log_step 'MTA Developer Lightspeed proxy (Technology Preview; separate from native Agents)'
check 'MTA AI proxy enabled' "oc get tackle mta -n openshift-mta -o jsonpath='{.spec.kai_llm_proxy_enabled}'" 'true'
check 'MTA proxy uses MaaS canonical model ID' "oc get tackle mta -n openshift-mta -o jsonpath='{.spec.kai_llm_model}'" 'publishers/internal-models/models/qwen3-8-27b'
check 'MTA LLM proxy ready without inference' "oc get deployment llm-proxy -n openshift-mta -o jsonpath='{.status.readyReplicas}'" '1'

log_step 'Optional MTA Solution Server (deferred; not qualified)'
check 'MTA Solution Server explicitly deferred' "oc get tackle mta -n openshift-mta -o jsonpath='{.spec.kai_solution_server_enabled}'" 'false'
check 'Deferred Solution Server is not crash-looping' "operand=\$(oc get deployment kai-api -n openshift-mta --ignore-not-found -o name) && test -z \"\$operand\" && echo ABSENT" 'ABSENT'
echo '[INFO] Solution Server is disabled pending its vendor dependency fix; this is not a startup or inference PASS.'
MTA_MAAS_ORIGIN=$(oc get gateway.gateway.networking.k8s.io maas-default-gateway -n openshift-ingress -o json 2>/dev/null |
  jq -r '[.spec.listeners[].hostname // "" | select(startswith("maas."))] | if length == 1 then "https://" + .[0] else "UNRESOLVED" end' || echo UNRESOLVED)
check 'MTA MaaS origin is unambiguous' "printf '%s' '$MTA_MAAS_ORIGIN' | contains -E '^https://maas[.][^/]+$' && echo GOVERNED" 'GOVERNED'
check 'MTA native Gateway uses MaaS origin' "test \"\$(oc get gateways.konveyor.io maas-qwen -n openshift-mta -o jsonpath='{.spec.endpoint}')\" = '$MTA_MAAS_ORIGIN' && echo EXACT_GATEWAY" 'EXACT_GATEWAY'
check 'MTA Lightspeed uses versioned MaaS API base' "test \"\$(oc get tackle mta -n openshift-mta -o jsonpath='{.spec.kai_llm_baseurl}')\" = '$MTA_MAAS_ORIGIN/v1' && echo EXACT_PROXY" 'EXACT_PROXY'

log_step 'Signing service and portal'
check 'TAS service Ready' "oc get securesign platform -n trusted-artifact-signer -o jsonpath='{.status.conditions[?(@.type==\"Ready\")].status}'" 'True'
KEYCLOAK_HOST=$(oc get route keycloak -n keycloak -o jsonpath='{.spec.host}' 2>/dev/null || true)
check 'TAS uses existing platform realm' "oc get securesign platform -n trusted-artifact-signer -o jsonpath='{.spec.fulcio.config.oidcIssuers[0].issuer}'" "https://${KEYCLOAK_HOST}/realms/platform"
check 'Portal instance exists' "oc get backstage developer-hub -n rhdh -o jsonpath='{.metadata.name}'" 'developer-hub'
check 'Portal catalog bundle stamped' "oc get configmap catalog-runtime-rhdh -n rhdh -o jsonpath='{.metadata.annotations.rhoai3\\.redhat\\.com/catalog-bundle}' | contains -E '^[0-9a-f]{64}$' && echo STAMPED" 'STAMPED'
check 'Portal catalog has no unresolved placeholders' "oc get configmap catalog-runtime-rhdh -n rhdh -o json | jq -r '.data[\"all.yaml\"] // \"\" | if . != \"\" and (contains(\"__RHOAI3_\") | not) and (contains(\"placeholder.example.com\") | not) then \"RESOLVED\" else \"UNRESOLVED\" end'" 'RESOLVED'
check 'Portal templates use private GitLab mirror' "oc get configmap catalog-runtime-rhdh -n rhdh -o jsonpath='{.data.all\\.yaml}' | contains -E 'target: https://gitlab-gitlab-system\\..*/-/blob/[0-9a-f]{40}/.*template.yaml' && echo GITLAB" 'GITLAB'
RHDH_HOST=$(oc get route -n rhdh -l app.kubernetes.io/name=backstage --no-headers 2>/dev/null | awk 'NR==1 {print $2}' || true)
if [[ -n "$RHDH_HOST" ]]; then check_http_code 'Developer Hub reachable' "https://${RHDH_HOST}" '200,302'; fi
# A failed realm discovery at startup is kept by the OIDC provider and turns every sign-in into HTTP 500.
check 'Developer Hub sign-in redirects to the platform realm' "curl -sk -o /dev/null -w '%{http_code}' --max-time 20 'https://${RHDH_HOST}/api/auth/oidc/start?env=production'" '302'

log_step 'Credential, identity and ingress correction checks (no inference)'
security_boundaries

# Models are deliberately stopped by the operator. A resource check is not
# proof of inference, browser login, signed delivery or a migration run.
echo "[WARN] Platform resource checks do not qualify browser login, inference, AI migration, signed delivery or restore."
VALIDATE_WARN=$((VALIDATE_WARN + 1))
validation_summary
