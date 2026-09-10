#!/usr/bin/env bash
# Route a migration workspace's MaaS traffic in-cluster (Operator, once per run).
#
# The public MaaS hostname resolves to the AWS load balancer, and that path
# drops a model response that stays silent for ~8 minutes (vLLM buffers a whole
# tool call before emitting; measured 2026-09-10 on pilot v6: the gateway logged
# `DC downstream_remote_disconnect` at 415-485 s while the pod kept an
# established socket). The same stream through the gateway's Service ClusterIP
# completed after 727 s of silence.
#
# This adds a pod hostAlias mapping the MaaS hostname to that ClusterIP, so TLS
# (SNI, certificate) and the HTTPRoute host match are unchanged and only NAT and
# the ELB are gone. Host and IP are read from the cluster and validated here;
# the value is never templated (an invalid hostAlias makes the workspace
# deployment invalid and the workspace fails to start).
#
# Usage: scripts/patch-workspace-maas-route.sh <devworkspace-name> [namespace]
set -euo pipefail
DW="${1:?usage: patch-workspace-maas-route.sh <devworkspace-name> [namespace]}"
NS="${2:-wksp-ai-developer}"
GW_NS="openshift-ingress"
GW="${MAAS_GATEWAY_NAME:-maas-default-gateway}"
SVC="${MAAS_GATEWAY_INTERNAL_SVC:-maas-gateway-internal}"

HOST="$(oc get gateway "$GW" -n "$GW_NS" -o jsonpath='{.spec.listeners[?(@.name=="https")].hostname}')"
IP="$(oc get svc "$SVC" -n "$GW_NS" -o jsonpath='{.spec.clusterIP}')"
[[ -n "$HOST" ]] || { echo "REFUSE: gateway/$GW in $GW_NS has no https listener hostname"; exit 1; }
[[ -n "$IP" ]] || { echo "REFUSE: service/$SVC in $GW_NS has no clusterIP (stage 040 not synced?)"; exit 1; }
# RFC 1123 subdomain, the same validation the Deployment admission applies
[[ "$HOST" =~ ^[a-z0-9]([-a-z0-9]*[a-z0-9])?(\.[a-z0-9]([-a-z0-9]*[a-z0-9])?)*$ ]] \
  || { echo "REFUSE: $HOST is not an RFC 1123 subdomain"; exit 1; }
[[ "$IP" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "REFUSE: $IP is not an IPv4 address"; exit 1; }
oc get dw "$DW" -n "$NS" >/dev/null

CUR="$(oc get dw "$DW" -n "$NS" -o jsonpath='{.spec.template.attributes.pod-overrides}' || true)"
if [[ "$CUR" == *"\"$HOST\""* && "$CUR" == *"$IP"* ]]; then
  echo "OK: $DW already routes $HOST to $IP in-cluster (no change)"
  exit 0
fi
oc patch dw "$DW" -n "$NS" --type merge \
  -p "{\"spec\":{\"template\":{\"attributes\":{\"pod-overrides\":{\"spec\":{\"hostAliases\":[{\"ip\":\"$IP\",\"hostnames\":[\"$HOST\"]}]}}}}}}" >/dev/null
echo "OK: $DW routes $HOST to $IP in-cluster (the pod restarts; dest-init re-runs)"
echo "verify: oc exec -n $NS <pod> -c development-tooling -- getent hosts $HOST"
