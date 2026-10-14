#!/usr/bin/env bash
# Read-only check of the maas-gateway-boundary AdminNetworkPolicy: from each MaaS gateway pod, open a TCP
# connection (no HTTP request, no model call) to every destination the gateway needs and to destinations the
# policy must block. Exit 1 if any result differs from the expectation.
#   ./stages/040-governed-models-as-a-service/validate-gateway-boundary.sh
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "$REPO_ROOT/scripts/shared/lib.sh"; load_env >/dev/null; check_oc_logged_in >/dev/null
oc --request-timeout=10s get adminnetworkpolicy maas-gateway-boundary >/dev/null || { echo "FAIL AdminNetworkPolicy maas-gateway-boundary is missing"; exit 1; }
kapi_node=$(oc --request-timeout=10s get nodes -l node-role.kubernetes.io/control-plane -o jsonpath='{.items[0].status.addresses[?(@.type=="InternalIP")].address}')
# expect|label|host|port
TARGETS="open|dns (openshift-dns)|dns-default.openshift-dns.svc.cluster.local|53
open|istiod xDS|istiod-openshift-gateway.openshift-ingress.svc.cluster.local|15012
open|authorino|authorino-authorino-authorization.kuadrant-system.svc.cluster.local|50051
open|limitador|limitador-limitador.kuadrant-system.svc.cluster.local|8081
open|kuadrant wasm module|kuadrant-operator-wasm.openshift-operators.svc.cluster.local|8082
open|payload-processing|payload-processing.openshift-ingress.svc.cluster.local|9004
open|payload-pre-processing|payload-pre-processing.openshift-ingress.svc.cluster.local|9004
open|maas-api|maas-api.redhat-ai-gateway-infra.svc.cluster.local|8443
open|public https (api.openai.com)|api.openai.com|443
open|public https (api.anthropic.com)|api.anthropic.com|443
blocked|kube-apiserver on node|$kapi_node|6443
blocked|kubelet on node|$kapi_node|10250
blocked|limitador http port (only grpc 8081 needed)|limitador-limitador.kuadrant-system.svc.cluster.local|8080
blocked|authorino oidc port (only 50051 needed)|authorino-authorino-authorization.kuadrant-system.svc.cluster.local|5001
blocked|public http (example.com:80)|example.com|80"
rc=0
for pod in $(oc --request-timeout=10s get pods -n openshift-ingress -l gateway.networking.k8s.io/gateway-name=maas-default-gateway -o jsonpath='{.items[*].metadata.name}'); do
  echo "== $pod"
  printf '%-8s %-8s %s\n' EXPECT RESULT TARGET
  while IFS='|' read -r expect label host port; do
    if oc exec -n openshift-ingress "$pod" -c istio-proxy -- timeout 4 bash -c "</dev/tcp/$host/$port" >/dev/null 2>&1; then r=open; else r=blocked; fi
    flag=""; [[ "$r" == "$expect" ]] || { flag="  <-- differs"; rc=1; }
    printf '%-8s %-8s %s (%s)%s\n' "$expect" "$r" "$label" "$port" "$flag"
  done <<<"$TARGETS"
done
[[ $rc == 0 ]] && echo "PASS MaaS gateway boundary: every needed destination open, every probed other destination blocked" || echo "FAIL MaaS gateway boundary differs from the policy (see rows marked differs)"
exit $rc
