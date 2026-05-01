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

log_step "Gateway and policy"
check "MaaS Gateway exists" \
  "oc get gateway maas-default-gateway -n openshift-ingress -o jsonpath='{.status.conditions[?(@.type==\"Accepted\")].status}'" \
  "True"
check "Kuadrant ready" \
  "oc get kuadrant kuadrant -n kuadrant-system -o jsonpath='{.status.conditions[?(@.type==\"Ready\")].status}'" \
  "True"

log_step "MaaS API"
check "Tenant-managed maas-api deployment ready" \
  "oc get deployment maas-api -n redhat-ods-applications -o jsonpath='{.status.readyReplicas}'" \
  "1"
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

log_step "Local model routing"
check "Per-route AuthPolicy for gpt-oss-20b" \
  "oc get authpolicy maas-auth-gpt-oss-20b -n maas -o jsonpath='{.metadata.name}'" \
  "maas-auth-gpt-oss-20b"
check "Per-route AuthPolicy for nemotron-3-nano-30b-a3b" \
  "oc get authpolicy maas-auth-nemotron-3-nano-30b-a3b -n maas -o jsonpath='{.metadata.name}'" \
  "maas-auth-nemotron-3-nano-30b-a3b"

log_step "Grafana"
check_pods_ready "grafana" "app=grafana" 1

echo ""
validation_summary
