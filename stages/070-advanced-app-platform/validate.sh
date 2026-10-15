#!/usr/bin/env bash
# Stage 070: static authoring checks or read-only deployed-state validation.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PYTHON="${PYTHON:-python3}"
if [[ "${1:-}" == --static ]]; then
  export PYTHONPATH="$REPO_ROOT/gitops/stages/070-advanced-app-platform/070-pipelines/gitlab${PYTHONPATH:+:$PYTHONPATH}"
  for test in correction-package.test.py internal-registry.test.py chart-gitops.test.py stage070-upgrade.test.py product-schemas.test.py delivery-integration.test.py security-boundaries.test.py sonarqube-bootstrap.test.py sonarqube-scope.test.py sso-alignment.test.py; do
    "$PYTHON" "$SCRIPT_DIR/tests/$test"
  done
  "$PYTHON" "$REPO_ROOT/gitops/stages/070-advanced-app-platform/070-rhdh/jobs/catalog/render_catalog.test.py"
  "$PYTHON" "$REPO_ROOT/gitops/stages/070-advanced-app-platform/070-rhdh/templates/app-migration/app-migration-template.test.py"
  kustomize build "$REPO_ROOT/gitops/stages/070-advanced-app-platform" >/dev/null
  bash -n "$SCRIPT_DIR/deploy.sh" "$SCRIPT_DIR/validate.sh"
  echo 'PASS: Stage 070 authoring checks. Live deployment and model-dependent checks are separate.'
  exit 0
fi
EXPECTED_REVISION="${RHOAI_STAGE070_EXPECTED_REVISION:-}"
if [[ "${1:-}" == --revision && $# -eq 2 ]]; then
  EXPECTED_REVISION="$2"
elif [[ $# -ne 0 ]]; then
  echo 'Usage: validate.sh [--static | --revision <commit>]' >&2; exit 1
fi
source "$REPO_ROOT/scripts/shared/validate-lib.sh"

log_step 'Stage 070 GitOps and selected operators'
check_stage_applications 070 "$EXPECTED_REVISION"
for row in \
  'openshift-operators devspaces devspacesoperator.v3.30.' \
  'rhdh-operator rhdh rhdh-operator.v1.10.5' \
  'openshift-mta mta-operator mta-operator.v8.3.1' \
  'openshift-operators openshift-pipelines-operator-rh openshift-pipelines-operator-rh.v1.24.' \
  'openshift-operators rhtas-operator rhtas-operator.v1.5.'; do
  read -r ns subscription csv <<< "$row"
  if [[ "$ns" == openshift-operators ]]; then
    # Automatic versioned channels admit patch updates. startingCSV is an
    # installation floor, not an installed-version lock (1.24.1 observed live).
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
GITLAB_HOST=$(oc get route gitlab -n gitlab-system -o jsonpath='{.spec.host}' 2>/dev/null || true)
if [[ -n "$GITLAB_HOST" ]]; then
  check_http_code 'GitLab readiness endpoint' "https://${GITLAB_HOST}/-/readiness" '200'
else
  check 'GitLab Route exists' 'echo missing' 'present'
fi
for pair in 'rhdh gitlab-publisher' 'rhdh gitlab-catalog-reader' 'app-platform-build gitlab-enroller' 'openshift-devspaces gitlab-oauth-config' 'gitlab-system gitlab-oidc'; do
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
  check "$ns standing workspace uses GitLab" "oc get devworkspace agentic-coolstore -n '$ns' -o jsonpath='{.spec.template.projects[0].git.remotes.origin}'" "https://${GITLAB_HOST}/rhoai-workloads/coolstore-inventory-service.git"
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
MTA_MAAS_ORIGIN=$(oc get gateway.gateway.networking.k8s.io maas-default-gateway -n openshift-ingress -o json | "$PYTHON" -c 'import json,sys; hosts=[x.get("hostname", "") for x in json.load(sys.stdin)["spec"]["listeners"] if x.get("hostname", "").startswith("maas.")]; print("https://"+hosts[0] if len(hosts)==1 else "UNRESOLVED")' 2>/dev/null || echo UNRESOLVED)
check 'MTA MaaS origin is unambiguous' "printf '%s' '$MTA_MAAS_ORIGIN' | contains -E '^https://maas[.][^/]+$' && echo GOVERNED" 'GOVERNED'
check 'MTA native Gateway uses MaaS origin' "test \"\$(oc get gateways.konveyor.io maas-qwen -n openshift-mta -o jsonpath='{.spec.endpoint}')\" = '$MTA_MAAS_ORIGIN' && echo EXACT_GATEWAY" 'EXACT_GATEWAY'
check 'MTA Lightspeed uses versioned MaaS API base' "test \"\$(oc get tackle mta -n openshift-mta -o jsonpath='{.spec.kai_llm_baseurl}')\" = '$MTA_MAAS_ORIGIN/v1' && echo EXACT_PROXY" 'EXACT_PROXY'

log_step 'Signing service and portal'
check 'TAS service Ready' "oc get securesign platform -n trusted-artifact-signer -o jsonpath='{.status.conditions[?(@.type==\"Ready\")].status}'" 'True'
KEYCLOAK_HOST=$(oc get route keycloak -n keycloak -o jsonpath='{.spec.host}' 2>/dev/null || true)
check 'TAS uses existing platform realm' "oc get securesign platform -n trusted-artifact-signer -o jsonpath='{.spec.fulcio.config.oidcIssuers[0].issuer}'" "https://${KEYCLOAK_HOST}/realms/platform"
check 'Portal instance exists' "oc get backstage developer-hub -n rhdh -o jsonpath='{.metadata.name}'" 'developer-hub'
check 'Portal catalog bundle stamped' "oc get configmap catalog-runtime-rhdh -n rhdh -o jsonpath='{.metadata.annotations.rhoai3\\.redhat\\.com/catalog-bundle}' | contains -E '^[0-9a-f]{64}$' && echo STAMPED" 'STAMPED'
check 'Portal catalog has no unresolved placeholders' "oc get configmap catalog-runtime-rhdh -n rhdh -o jsonpath='{.data.all\\.yaml}' | '$PYTHON' -c 'import sys; s=sys.stdin.read(); assert s and \"__RHOAI3_\" not in s and \"placeholder.example.com\" not in s; print(\"RESOLVED\")'" 'RESOLVED'
check 'Portal templates use private GitLab mirror' "oc get configmap catalog-runtime-rhdh -n rhdh -o jsonpath='{.data.all\\.yaml}' | contains -E 'target: https://gitlab-gitlab-system\\..*/-/blob/[0-9a-f]{40}/.*template.yaml' && echo GITLAB" 'GITLAB'
RHDH_HOST=$(oc get route -n rhdh -l app.kubernetes.io/name=backstage --no-headers 2>/dev/null | awk 'NR==1 {print $2}' || true)
if [[ -n "$RHDH_HOST" ]]; then check_http_code 'Developer Hub reachable' "https://${RHDH_HOST}" '200,302'; fi

log_step 'Credential, identity and ingress correction checks (no inference)'
if "$PYTHON" "$SCRIPT_DIR/security-status.py"; then
  check 'Stage 070 corrected security boundaries' 'echo PASS' 'PASS'
else
  check 'Stage 070 corrected security boundaries' 'echo FAIL' 'PASS'
fi

# Models are deliberately stopped by the operator. A resource check is not
# proof of inference, browser login, signed delivery or a migration run.
echo "[WARN] Platform resource checks do not qualify browser login, inference, AI migration, signed delivery or restore."
VALIDATE_WARN=$((VALIDATE_WARN + 1))
validation_summary
