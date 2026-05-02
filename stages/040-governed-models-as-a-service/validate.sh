#!/usr/bin/env bash
# Stage 040: Governed Models-as-a-Service — Validation Script
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/validate-lib.sh"

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
check "Grafana route exists" \
  "oc get route grafana-route -n grafana -o jsonpath='{.spec.host}'" \
  "grafana"
check "Grafana route uses edge TLS termination" \
  "oc get route grafana-route -n grafana -o jsonpath='{.spec.tls.termination}'" \
  "edge"
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
  GRAFANA_LOGIN_CODE=$(curl -k -s -o /dev/null -w '%{http_code}' "https://${GRAFANA_HOST}/login" || true)
  if [[ "$GRAFANA_LOGIN_CODE" == "200" || "$GRAFANA_LOGIN_CODE" == "302" ]]; then
    echo -e "${GREEN}[PASS]${NC} Grafana route reachable: HTTP ${GRAFANA_LOGIN_CODE}"
    VALIDATE_PASS=$((VALIDATE_PASS + 1))
  else
    echo -e "${RED}[FAIL]${NC} Grafana route reachable (expected: 200 or 302, got: ${GRAFANA_LOGIN_CODE:-ERROR})"
    VALIDATE_FAIL=$((VALIDATE_FAIL + 1))
  fi

  GRAFANA_SEARCH=$(curl -k -s -u admin:redhat123 "https://${GRAFANA_HOST}/api/search?query=maas" || true)
  if [[ "$GRAFANA_SEARCH" == *"MaaS"* || "$GRAFANA_SEARCH" == *"maas"* ]]; then
    echo -e "${GREEN}[PASS]${NC} Grafana API can find MaaS dashboard"
    VALIDATE_PASS=$((VALIDATE_PASS + 1))
  else
    echo -e "${YELLOW}[WARN]${NC} Grafana API did not return MaaS dashboard search results"
    VALIDATE_WARN=$((VALIDATE_WARN + 1))
  fi

  GRAFANA_DATASOURCE_UID=$(oc get grafanadatasource prometheus -n grafana -o jsonpath='{.status.uid}' 2>/dev/null || true)
  if [[ -n "$GRAFANA_DATASOURCE_UID" ]]; then
    GRAFANA_PROM_QUERY=$(curl -k -s -u admin:redhat123 \
      "https://${GRAFANA_HOST}/api/datasources/uid/${GRAFANA_DATASOURCE_UID}/resources/api/v1/query?query=up" || true)
    if [[ "$GRAFANA_PROM_QUERY" == *'"status":"success"'* ]]; then
      echo -e "${GREEN}[PASS]${NC} Grafana datasource can query OpenShift monitoring"
      VALIDATE_PASS=$((VALIDATE_PASS + 1))
    else
      echo -e "${RED}[FAIL]${NC} Grafana datasource can query OpenShift monitoring"
      VALIDATE_FAIL=$((VALIDATE_FAIL + 1))
    fi

    GRAFANA_USAGE_QUERY=$(curl -k -s -u admin:redhat123 \
      "https://${GRAFANA_HOST}/api/datasources/uid/${GRAFANA_DATASOURCE_UID}/resources/api/v1/query?query=sum%28authorized_hits%29" || true)
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

echo ""
validation_summary
