#!/usr/bin/env bash
# Stage 040: Governed Models-as-a-Service — Validation Script
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/validate-lib.sh"
load_env

echo "Stage 040: Governed Models-as-a-Service — Validation"
echo ""

log_step "Argo CD Application"
check_argocd_app "040-governed-models-as-a-service"

log_step "Operators"
check_csv_succeeded "rhcl-operator" "Connectivity Link"
check_csv_succeeded "openshift-operators" "cloudnative-pg"

log_step "MaaS CRDs"
check_crd_exists "maasmodelrefs.maas.opendatahub.io"
check_crd_exists "maasauthpolicies.maas.opendatahub.io"
check_crd_exists "maassubscriptions.maas.opendatahub.io"
check_crd_exists "externalmodels.maas.opendatahub.io"

log_step "Gateway and policy"
check "MaaS GatewayClass accepted" \
  "oc get gatewayclass openshift-default -o jsonpath='{.status.conditions[?(@.type==\"Accepted\")].status}'" \
  "True"
check "MaaS Gateway exists" \
  "oc get gateway maas-default-gateway -n openshift-ingress -o jsonpath='{.status.conditions[?(@.type==\"Accepted\")].status}'" \
  "True"
check "MaaS Gateway programmed" \
  "oc get gateway maas-default-gateway -n openshift-ingress -o jsonpath='{.status.conditions[?(@.type==\"Programmed\")].status}'" \
  "True"
check "MaaS Gateway hostname assigned" \
  "oc get gateway maas-default-gateway -n openshift-ingress -o jsonpath='{.spec.listeners[0].hostname}'" \
  "maas."
check "Kuadrant ready" \
  "oc get kuadrant kuadrant -n kuadrant-system -o jsonpath='{.status.conditions[?(@.type==\"Ready\")].status}'" \
  "True"
check "Authorino deployment ready" \
  "oc get deployment authorino -n kuadrant-system -o jsonpath='{.status.readyReplicas}'" \
  "1"
check "Limitador deployment ready" \
  "oc get deployment limitador-limitador -n kuadrant-system -o jsonpath='{.status.readyReplicas}'" \
  "1"

log_step "MaaS API"
check "Tenant-managed maas-api deployment ready" \
  "oc get deployment maas-api -n redhat-ods-applications -o jsonpath='{.status.readyReplicas}'" \
  "1"
check "MaaS API route accepted" \
  "oc get httproute maas-api-route -n redhat-ods-applications -o jsonpath='{.status.parents[*].conditions[?(@.type==\"Accepted\")].status}'" \
  "True"
check "maas-api owned by upstream tenant reconciler" \
  "oc get deployment maas-api -n redhat-ods-applications -o jsonpath='{.metadata.labels.maas\\.opendatahub\\.io/tenant-name}'" \
  "default-tenant"
check "maas-api uses models-as-a-service policy namespace" \
  "oc get deployment maas-api -n redhat-ods-applications -o jsonpath='{.spec.template.spec.containers[0].env[?(@.name==\"MAAS_SUBSCRIPTION_NAMESPACE\")].value}'" \
  "models-as-a-service"
check "maas-api uses upstream image with ExternalModel discovery" \
  "oc get deployment maas-api -n redhat-ods-applications -o jsonpath='{.spec.template.spec.containers[0].image}'" \
  "quay.io/opendatahub/maas-api:latest"

log_step "Local MaaS resources"
check "MaaSModelRef gpt-oss-20b ready" \
  "oc get maasmodelref gpt-oss-20b -n maas -o jsonpath='{.status.phase}'" \
  "Ready"
check "MaaSModelRef nemotron-3-nano-30b-a3b ready" \
  "oc get maasmodelref nemotron-3-nano-30b-a3b -n maas -o jsonpath='{.status.phase}'" \
  "Ready"
check "MaaSAuthPolicy local-models-access active" \
  "oc get maasauthpolicy local-models-access -n models-as-a-service -o jsonpath='{.status.phase}'" \
  "Active"
check "MaaSSubscription local-models-subscription active" \
  "oc get maassubscription local-models-subscription -n models-as-a-service -o jsonpath='{.status.phase}'" \
  "Active"
check "local-models-subscription token limits ready" \
  "oc get maassubscription local-models-subscription -n models-as-a-service -o jsonpath='{.status.tokenRateLimitStatuses[*].ready}'" \
  "true"

log_step "Local model routing"
check "Per-route AuthPolicy for gpt-oss-20b" \
  "oc get authpolicy maas-auth-gpt-oss-20b -n maas -o jsonpath='{.metadata.name}'" \
  "maas-auth-gpt-oss-20b"
check "AuthPolicy for gpt-oss-20b enforced" \
  "oc get authpolicy maas-auth-gpt-oss-20b -n maas -o jsonpath='{.status.conditions[?(@.type==\"Enforced\")].status}'" \
  "True"
check "Per-route AuthPolicy for nemotron-3-nano-30b-a3b" \
  "oc get authpolicy maas-auth-nemotron-3-nano-30b-a3b -n maas -o jsonpath='{.metadata.name}'" \
  "maas-auth-nemotron-3-nano-30b-a3b"
check "AuthPolicy for nemotron-3-nano-30b-a3b enforced" \
  "oc get authpolicy maas-auth-nemotron-3-nano-30b-a3b -n maas -o jsonpath='{.status.conditions[?(@.type==\"Enforced\")].status}'" \
  "True"
check "HTTPRoute for gpt-oss-20b accepted" \
  "oc get httproute gpt-oss-20b-kserve-route -n maas -o jsonpath='{.status.parents[*].conditions[?(@.type==\"Accepted\")].status}'" \
  "True"
check "HTTPRoute for nemotron-3-nano-30b-a3b accepted" \
  "oc get httproute nemotron-3-nano-30b-a3b-kserve-route -n maas -o jsonpath='{.status.parents[*].conditions[?(@.type==\"Accepted\")].status}'" \
  "True"
check "TokenRateLimitPolicy for gpt-oss-20b accepted" \
  "oc get tokenratelimitpolicy maas-trlp-gpt-oss-20b -n maas -o jsonpath='{.status.conditions[?(@.type==\"Accepted\")].status}'" \
  "True"
check "TokenRateLimitPolicy for nemotron-3-nano-30b-a3b accepted" \
  "oc get tokenratelimitpolicy maas-trlp-nemotron-3-nano-30b-a3b -n maas -o jsonpath='{.status.conditions[?(@.type==\"Accepted\")].status}'" \
  "True"

log_step "Observability Policies"
check "Gateway RateLimitPolicy enforced" \
  "oc get ratelimitpolicy gateway-rate-limits -n openshift-ingress -o jsonpath='{.status.conditions[?(@.type==\"Enforced\")].status}'" \
  "True"
check "MaaS telemetry policy enforced" \
  "oc get telemetrypolicy maas-telemetry -n openshift-ingress -o jsonpath='{.status.conditions[?(@.type==\"Enforced\")].status}'" \
  "True"

log_step "Grafana"
check_pods_ready "grafana" "app=grafana" 1
GRAFANA_POD_CONTAINERS=$(oc get pod -n grafana -l app=grafana \
  -o jsonpath='{.items[0].spec.containers[*].name}' 2>/dev/null || true)
if [[ "$GRAFANA_POD_CONTAINERS" == *"oauth-proxy"* ]]; then
  echo -e "${GREEN}[PASS]${NC} Grafana OAuth proxy sidecar present"
  VALIDATE_PASS=$((VALIDATE_PASS + 1))
else
  echo -e "${RED}[FAIL]${NC} Grafana OAuth proxy sidecar present"
  VALIDATE_FAIL=$((VALIDATE_FAIL + 1))
fi
check "Grafana route exists" \
  "oc get route grafana-route -n grafana -o jsonpath='{.spec.host}'" \
  "grafana"
check "Grafana route uses OAuth proxy target port" \
  "oc get route grafana-route -n grafana -o jsonpath='{.spec.port.targetPort}'" \
  "oauth-proxy"
check "Grafana route uses reencrypt TLS termination" \
  "oc get route grafana-route -n grafana -o jsonpath='{.spec.tls.termination}'" \
  "reencrypt"
check "Grafana OAuth redirect reference configured" \
  "oc get serviceaccount grafana-sa -n grafana -o jsonpath='{.metadata.annotations.serviceaccounts\\.openshift\\.io/oauth-redirectreference\\.grafana}'" \
  "grafana-route"
check "Grafana OAuth proxy restricts access to RHOAI users" \
  "oc get grafana grafana -n grafana -o jsonpath='{.spec.deployment.spec.template.spec.containers[?(@.name==\"oauth-proxy\")].args}'" \
  "rhoai-users"
check "Grafana OAuth proxy can delegate token authentication" \
  "oc get clusterrolebinding grafana-oauth-proxy-auth-delegator -o jsonpath='{.roleRef.name}{\" \"}{.subjects[0].name}'" \
  "system:auth-delegator grafana-sa"
check "Grafana datasource exists" \
  "oc get grafanadatasource prometheus -n grafana -o jsonpath='{.metadata.name}'" \
  "prometheus"
check "Grafana datasource synchronized" \
  "oc get grafanadatasource prometheus -n grafana -o jsonpath='{.status.conditions[?(@.type==\"DatasourceSynchronized\")].status}'" \
  "True"
GRAFANA_DATASOURCE_TOKEN=$(oc get grafanadatasource prometheus -n grafana -o jsonpath='{.spec.datasource.secureJsonData.httpHeaderValue1}' 2>/dev/null || true)
if [[ "$GRAFANA_DATASOURCE_TOKEN" == Bearer\ ey* ]]; then
  echo -e "${GREEN}[PASS]${NC} Grafana datasource has runtime service account token"
  VALIDATE_PASS=$((VALIDATE_PASS + 1))
elif [[ "$GRAFANA_DATASOURCE_TOKEN" == *'${GRAFANA_SA_TOKEN}'* || -z "$GRAFANA_DATASOURCE_TOKEN" ]]; then
  echo -e "${RED}[FAIL]${NC} Grafana datasource has runtime service account token (placeholder or empty token)"
  VALIDATE_FAIL=$((VALIDATE_FAIL + 1))
else
  echo -e "${YELLOW}[WARN]${NC} Grafana datasource token is present but has an unexpected shape"
  VALIDATE_WARN=$((VALIDATE_WARN + 1))
fi
check "Grafana MaaS dashboard exists" \
  "oc get grafanadashboard maas-usage -n grafana -o jsonpath='{.metadata.name}'" \
  "maas-usage"
check "Grafana MaaS dashboard synchronized" \
  "oc get grafanadashboard maas-usage -n grafana -o jsonpath='{.status.conditions[?(@.type==\"DashboardSynchronized\")].status}'" \
  "True"
check "MaaS Gateway metrics PodMonitor exists" \
  "oc get podmonitor maas-gateway-metrics -n openshift-ingress -o jsonpath='{.metadata.name}'" \
  "maas-gateway-metrics"
check "MaaS dashboard recording rule exists" \
  "oc get prometheusrule maas-dashboard-usage-metrics -n openshift-ingress -o jsonpath='{.metadata.name}'" \
  "maas-dashboard-usage-metrics"
check "Grafana ConsoleLink exists" \
  "oc get consolelink grafana-maas -o jsonpath='{.spec.location}{\" \"}{.spec.text}'" \
  "ApplicationMenu MaaS Grafana"
GRAFANA_CONSOLELINK_HREF=$(oc get consolelink grafana-maas -o jsonpath='{.spec.href}' 2>/dev/null || true)
if [[ "$GRAFANA_CONSOLELINK_HREF" == https://grafana* && "$GRAFANA_CONSOLELINK_HREF" != *placeholder* ]]; then
  echo -e "${GREEN}[PASS]${NC} Grafana ConsoleLink patched with route"
  VALIDATE_PASS=$((VALIDATE_PASS + 1))
else
  echo -e "${RED}[FAIL]${NC} Grafana ConsoleLink patched with route (got: ${GRAFANA_CONSOLELINK_HREF:-ERROR})"
  VALIDATE_FAIL=$((VALIDATE_FAIL + 1))
fi

GRAFANA_HOST=$(oc get route grafana-route -n grafana -o jsonpath='{.spec.host}' 2>/dev/null || true)
if command -v curl >/dev/null 2>&1 && [[ -n "$GRAFANA_HOST" ]]; then
  GRAFANA_LOGIN_CODE=$(curl -k -s -o /dev/null -w '%{http_code}' "https://${GRAFANA_HOST}/" || true)
  if [[ "$GRAFANA_LOGIN_CODE" == "302" ]]; then
    echo -e "${GREEN}[PASS]${NC} Grafana OAuth route redirects unauthenticated users"
    VALIDATE_PASS=$((VALIDATE_PASS + 1))
  else
    echo -e "${RED}[FAIL]${NC} Grafana OAuth route redirects unauthenticated users (expected: 302, got: ${GRAFANA_LOGIN_CODE:-ERROR})"
    VALIDATE_FAIL=$((VALIDATE_FAIL + 1))
  fi

  GRAFANA_INTERNAL_HEALTH=$(oc exec deployment/grafana-deployment -n grafana -c grafana -- \
    curl -s -H "X-Forwarded-User: ai-admin" "http://localhost:3000/api/health" 2>/dev/null || true)
  if [[ "$GRAFANA_INTERNAL_HEALTH" == *'"database":"ok"'* ]]; then
    echo -e "${GREEN}[PASS]${NC} Grafana accepts trusted OpenShift proxy user header internally"
    VALIDATE_PASS=$((VALIDATE_PASS + 1))
  else
    echo -e "${RED}[FAIL]${NC} Grafana accepts trusted OpenShift proxy user header internally"
    VALIDATE_FAIL=$((VALIDATE_FAIL + 1))
  fi

  GRAFANA_SEARCH=$(oc exec deployment/grafana-deployment -n grafana -c grafana -- \
    curl -s -H "X-Forwarded-User: ai-admin" "http://localhost:3000/api/search?query=maas" 2>/dev/null || true)
  if [[ "$GRAFANA_SEARCH" == *"MaaS"* || "$GRAFANA_SEARCH" == *"maas"* ]]; then
    echo -e "${GREEN}[PASS]${NC} Grafana API can find MaaS dashboard"
    VALIDATE_PASS=$((VALIDATE_PASS + 1))
  else
    echo -e "${YELLOW}[WARN]${NC} Grafana API did not return MaaS dashboard search results"
    VALIDATE_WARN=$((VALIDATE_WARN + 1))
  fi

  GRAFANA_DATASOURCE_UID=$(oc get grafanadatasource prometheus -n grafana -o jsonpath='{.status.uid}' 2>/dev/null || true)
  if [[ -n "$GRAFANA_DATASOURCE_UID" ]]; then
    GRAFANA_PROM_QUERY=$(oc exec deployment/grafana-deployment -n grafana -c grafana -- \
      curl -s -H "X-Forwarded-User: ai-admin" \
      "http://localhost:3000/api/datasources/uid/${GRAFANA_DATASOURCE_UID}/resources/api/v1/query?query=up" 2>/dev/null || true)
    if [[ "$GRAFANA_PROM_QUERY" == *'"status":"success"'* ]]; then
      echo -e "${GREEN}[PASS]${NC} Grafana datasource can query OpenShift monitoring"
      VALIDATE_PASS=$((VALIDATE_PASS + 1))
    else
      echo -e "${RED}[FAIL]${NC} Grafana datasource can query OpenShift monitoring"
      VALIDATE_FAIL=$((VALIDATE_FAIL + 1))
    fi

    GRAFANA_USAGE_QUERY=$(oc exec deployment/grafana-deployment -n grafana -c grafana -- \
      curl -s -H "X-Forwarded-User: ai-admin" \
      "http://localhost:3000/api/datasources/uid/${GRAFANA_DATASOURCE_UID}/resources/api/v1/query?query=sum%28authorized_hits%29" 2>/dev/null || true)
    if [[ "$GRAFANA_USAGE_QUERY" == *'"status":"success"'* && "$GRAFANA_USAGE_QUERY" != *'"result":[]'* ]]; then
      echo -e "${GREEN}[PASS]${NC} Grafana MaaS usage metric query returns data"
      VALIDATE_PASS=$((VALIDATE_PASS + 1))
    else
      echo -e "${YELLOW}[WARN]${NC} Grafana MaaS usage metric has no data yet; generate governed MaaS traffic and wait for scrape"
      VALIDATE_WARN=$((VALIDATE_WARN + 1))
    fi
  else
    echo -e "${RED}[FAIL]${NC} Grafana datasource UID available for API validation"
    VALIDATE_FAIL=$((VALIDATE_FAIL + 1))
  fi
else
  echo -e "${YELLOW}[WARN]${NC} curl not available or Grafana route missing; skipping route reachability check"
  VALIDATE_WARN=$((VALIDATE_WARN + 1))
fi

log_step "GuideLLM load test"
if [[ "${GUIDELLM_SKIP_LOAD_TEST:-false}" == "true" ]]; then
  echo -e "${YELLOW}[WARN]${NC} GuideLLM load test skipped by GUIDELLM_SKIP_LOAD_TEST=true"
  VALIDATE_WARN=$((VALIDATE_WARN + 1))
elif "$SCRIPT_DIR/run-guidellm-load-test.sh"; then
  echo -e "${GREEN}[PASS]${NC} GuideLLM short MaaS load test completed"
  VALIDATE_PASS=$((VALIDATE_PASS + 1))
else
  GUIDELLM_RC=$?
  if [[ "$GUIDELLM_RC" -eq 2 ]]; then
    echo -e "${YELLOW}[WARN]${NC} GuideLLM load test skipped because prerequisites are unavailable"
    VALIDATE_WARN=$((VALIDATE_WARN + 1))
  else
    echo -e "${RED}[FAIL]${NC} GuideLLM short MaaS load test failed"
    VALIDATE_FAIL=$((VALIDATE_FAIL + 1))
  fi
fi

echo ""
validation_summary
