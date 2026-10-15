# MaaS gateway and governance (`040-gateway-governance`)

This Application creates the governed entry point for every model request: the `maas-default-gateway` Gateway in `openshift-ingress`, its TLS certificate and network policies, and the Kuadrant and Authorino instances that enforce MaaS authentication and token limits on it. Developers, Dev Spaces workspaces, the GenAI playground, Stage 050 evaluations and the Stage 070 migration workers all reach private and external models through this Gateway. The OpenShift AI MaaS controller attaches its generated AuthPolicy and TokenRateLimitPolicy objects to it.

| | |
|---|---|
| Argo CD Application | `040-gateway-governance` ([manifest](../../../applications/040-gateway-governance.yaml)) |
| Deployed by | `stages/040-governed-models-as-a-service/deploy.sh` (deploy-order 3). `deploy.sh` passes the listener hostnames for this cluster's ingress domain as a `source.kustomize` patch (`stage_apps.py deploy --kustomize-patches`) |
| Validated by | `stages/040-governed-models-as-a-service/validate.sh` → `validate-native.sh` (Authorino TLS and CA checks; Gateway, listener, namespace-isolation and route checks); `preflight.sh` (adoption checks) |
| Sync | Automated, `prune: true`, `selfHeal: true`; `CreateNamespace`, `SkipDryRunOnMissingResource`, `ServerSideDiff`, `RespectIgnoreDifferences`; compare-option `ServerSideDiff=true`; `ignoreDifferences` on ConfigMap `authorino-service-ca` `/data/service-ca.crt` |
| Depends on | `040-maas-operators` (Kuadrant and Authorino CRDs); Stage 010 (OpenShift AI `data-science-gateway-class`, cert-manager ingress certificate `cert-manager-ingress-cert`) |
| Used by | The MaaS controller (AuthPolicy `maas-gateway-auth`, TokenRateLimitPolicies), `040-local-models` and `040-external-models` (routes on the listeners), `040-maas-platform` (namespace admission labels), Dev Spaces workspaces and the RHDH catalog generator (read the Gateway hostname and the `maas-gateway-internal` ClusterIP) |

## Why

The MaaS guide requires a Gateway named `maas-default-gateway` in `openshift-ingress`. It must use a GatewayClass for the OpenShift Gateway controller and terminate TLS. It must carry `opendatahub.io/managed: "false"`, so the model controller does not override MaaS authorization, and `security.opendatahub.io/authorino-tls-bootstrap: "true"`, so the MaaS controller encrypts traffic between the Gateway and Authorino [1]. The guide also requires a ready `Kuadrant` resource in `kuadrant-system` [1] and a TLS listener on Authorino that uses an OpenShift service serving certificate [1][3].

Gateway, TLS and governance instances form one Application because MaaS authentication on the Gateway depends on the Authorino TLS setup, so they change together. Models and access policies change often and live in other components, so a model change never re-syncs the Gateway.

## What

### `governance/`: Kuadrant and Authorino

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| Namespace | `kuadrant-system` | (cluster) | Kuadrant instance namespace, Pod Security `restricted` audit/warn (wave 1) |
| Kuadrant | `kuadrant` | `kuadrant-system` | Connectivity Link instance [2] with `spec.observability.enable: true` (wave 9). The operator creates `Limitador` and the Authorino wiring |
| ConfigMap | `authorino-service-ca` | `kuadrant-system` | Empty ConfigMap with `service.beta.openshift.io/inject-cabundle: "true"`; the service CA operator writes `service-ca.crt` (wave 9) |
| Authorino | `authorino` | `kuadrant-system` | Cluster-wide, 1 replica, TLS listener with `certSecretRef: authorino-server-cert`, OIDC server TLS off, service CA mounted at `/etc/pki/tls/certs/openshift-service-ca.crt` (wave 10) |

### `gateway/`: the MaaS Gateway

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| ConfigMap | `maas-gateway-resources` | `openshift-ingress` | Gateway `parametersRef`: proxy requests 100m/1Gi, limits 2 CPU/2Gi, and an Envoy stats matcher (wave 9) |
| AdminNetworkPolicy | `maas-gateway-boundary` | cluster-scoped | Enforced ingress/egress boundary for the gateway pods (wave 9, priority 40; see How) |
| Gateway | `maas-default-gateway` | `openshift-ingress` | Class `data-science-gateway-class`, MaaS annotations, ELB idle timeout 3600 s, listeners `api` and `qwen3-8` (HTTPS 443, TLS Terminate, Secret `cert-manager-ingress-cert`) (wave 10) |
| NetworkPolicy | `payload-processing-maas-gateway` | `openshift-ingress` | Ingress to `app=payload-processing` pods on TCP 9004 from the MaaS gateway pods (wave 11) |
| Service | `maas-gateway-internal` | `openshift-ingress` | ClusterIP pinned to `172.30.250.250`, ports 443 and 80, selects the MaaS gateway pods (wave 11) |

### `jobs/`: TLS bootstrap

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| ServiceAccount, Role, RoleBinding | `authorino-serving-cert` | `kuadrant-system` | `get`/`patch` on Service `authorino-authorino-authorization`; `get` on Authorino `authorino` (wave 10) |
| Job | `authorino-serving-cert` | `kuadrant-system` | `Sync` hook, wave 11, `BeforeHookCreation,HookSucceeded`. Adds the serving-certificate annotation to the Authorino Service |

### Objects not in Git

| Object | Owner |
|---|---|
| Gateway Deployment and LoadBalancer Service `maas-default-gateway-data-science-gateway-class` | OpenShift Gateway controller (Istio) |
| NetworkPolicy `maas-default-gateway-allow` (allows all ingress and egress for the gateway pods) and `openshift-ingress-deny-all` | Ingress Operator |
| NetworkPolicy `payload-processing`, Deployment `payload-processing`, AuthPolicy `maas-gateway-auth`, TokenRateLimitPolicy `gateway-default-deny` and `maas-trlp-<model>`, EnvoyFilters `maas-default-gateway-authn-ssl`, `payload-processing` | OpenShift AI MaaS controller |
| EnvoyFilters `kuadrant-*-maas-default-gateway`, `Limitador limitador` | Kuadrant operator |
| Secret `authorino-server-cert` in `kuadrant-system` | OpenShift service CA operator (from the annotation the Job adds) |
| Authorino Deployment `authorino` and Service `authorino-authorino-authorization` | Authorino operator |
| HTTPRoutes on the listeners | MaaS and KServe controllers (`040-local-models`, `040-external-models` sources) |

## How

- **Cluster-specific hostnames (deploy-time patch).** Git holds placeholder hostnames (`maas.placeholder.example.com`, `qwen3-8-maas.placeholder.example.com`). `deploy.sh` reads the ingress domain from `ingresscontroller/default` `.status.domain` and adds an Argo CD inline Kustomize patch [8] to this Application only:

  ```yaml
  spec:
    source:
      kustomize:
        patches:
        - target: {group: gateway.networking.k8s.io, version: v1, kind: Gateway, name: maas-default-gateway, namespace: openshift-ingress}
          patch: '[{"op":"replace","path":"/spec/listeners/0/hostname","value":"maas.<cluster-domain>"},
                   {"op":"replace","path":"/spec/listeners/1/hostname","value":"qwen3-8-maas.<cluster-domain>"}]'
  ```

  The patch addresses the listeners by index, so `api` must stay first and `qwen3-8` second. The domain is checked against `^[a-z0-9.-]+$`. `validate-native.sh` fails if a listener hostname still contains `placeholder` or a wildcard. Re-running `deploy.sh` re-applies the Applications and the patch.
- **Listeners and admission.** `api` (`maas.<cluster-domain>`) is the shared `/v1` endpoint. Routes may attach from namespaces labelled `maas-gateway-access=true` and named `redhat-ai-gateway-infra`, `external-models`, `internal-models` or `redhat-ods-applications`. `qwen3-8` (`qwen3-8-maas.<cluster-domain>`) is a compatibility listener for `internal-models` only. Both conditions must hold. The label alone does not admit a namespace.
- **Gateway TLS.** The MaaS guide requires TLS but does not prescribe the certificate source [1]. Both listeners reference the cluster's cert-manager wildcard ingress certificate, Secret `cert-manager-ingress-cert` in `openshift-ingress`, the same namespace as the Gateway, so no ReferenceGrant is needed [4]. Istio watches referenced Secrets, so a renewal reaches the gateway without a sync. `preflight.sh` requires that IngressController `default` uses this certificate [3] and that the Secret holds `tls.crt` and `tls.key`. An earlier hook Job copied the Secret into `maas-gateway-tls`; the copy was never refreshed on renewal and was removed.
- **Authorino TLS.** The guide's procedure annotates Service `authorino-authorino-authorization` with `service.beta.openshift.io/serving-cert-secret-name=authorino-server-cert`, enables the TLS listener, sets `SSL_CERT_FILE` and `REQUESTS_CA_BUNDLE` on the Authorino Deployment, and annotates the Gateway [1]. This repository does step 1 with the `authorino-serving-cert` Job, because the Authorino operator owns that Service. The Job checks that the operator owns the Service, then patches it. Step 2 is the declarative `spec.listener.tls` on the Authorino CR. For step 3 it mounts the service CA bundle through the Authorino CR's `spec.volumes` at `/etc/pki/tls/certs/openshift-service-ca.crt` instead of `oc set env` on the operator-managed Deployment. The service CA operator fills `authorino-service-ca` [3], and Argo CD ignores that key. Step 4 is the Gateway annotation in Git.
- **Gateway resources.** `spec.infrastructure.parametersRef` points at `maas-gateway-resources`. Its `deployment` key is a strategic merge patch on the generated Deployment (upstream Istio behavior [9]). The proxy requests 1Gi and is limited to 2Gi because it came close to its earlier 1Gi limit during long migration sessions. The same patch sets `proxy.istio.io/config` `proxyStatsMatcher` to keep the default stats plus bounded endpoint-picker (EPP) and `ext_proc` counters. The EPP expression names `qwen3-(6-27b|8-27b-int4)-epp-service`, while the live EPP Service is `qwen3-8-27b-epp-service`, so that expression matches nothing today.
- **Load balancer idle timeout.** `spec.infrastructure.annotations` sets `service.beta.kubernetes.io/aws-load-balancer-connection-idle-timeout: '3600'`. The AWS default for Classic Load Balancers is 60 s [10][4], which cut tool-call streams that stay silent while the model buffers a call. OpenShift documents `spec.infrastructure.annotations` for gateway load balancer annotations [4]. Live: the generated LoadBalancer Service carries the annotation.
- **In-cluster path (`maas-gateway-internal`).** The workspace devfile maps the public hostname to `172.30.250.250` with a pod `hostAlias`. TLS, SNI and HTTPRoute host matching stay unchanged, and traffic stays inside the cluster. The comment in the manifest records why: streams silent for about eight minutes were dropped on the pod → NAT → ELB path and completed through the ClusterIP. The IP is fixed so the catalog generator and devfile can name it. It is in the service CIDR `172.30.0.0/16`, outside the range the platform normally assigns. The Service maps only port 443.
- **Network boundary.** NetworkPolicies are additive: a pod's allowed traffic is the union of every policy that selects it [7]. The Ingress Operator creates `maas-default-gateway-allow`, which allows all ingress and egress for the gateway pods, so no NetworkPolicy can narrow them. The boundary is therefore the AdminNetworkPolicy `maas-gateway-boundary`. OVN-Kubernetes evaluates AdminNetworkPolicies before NetworkPolicies, and their Allow and Deny actions cannot be overridden by them; rules apply in the order written [11][12]. Egress allows, in order: DNS; istiod xDS 15012; `payload-processing` and `payload-pre-processing` 9004; Authorino 50051; Limitador 8081; the Kuadrant operator's Wasm module server 8082 (each gateway pod downloads the policy shim from it at startup); `maas-api` 8443; `internal-models` 8000 (vLLM) and 9002 (endpoint picker). Then it denies every other cluster pod and every private network, allows public HTTPS 443 for the registered external providers (an IP-based policy cannot name provider hostnames), and denies everything else. Ingress allows 443 and 15021 from any pod and the metrics ports 15020/15090 from the two monitoring namespaces, and denies other ports from pods; traffic from outside the cluster arrives from node addresses, which ingress rules cannot name, and stays governed by the operator's allow-all. The destinations come from the gateway's Envoy clusters and HTTPRoutes, not from documentation; the earlier NetworkPolicy missed the Wasm module server and `payload-pre-processing`. A new upstream (for example another model namespace) needs an allow rule here first. The MaaS controller's `payload-processing` policy admits ingress on 9004 from gateway pods; `payload-processing-maas-gateway` remains as the recorded fix for the incident in TROUBLESHOOTING.
- **Secrets.** The gateway certificate is the cluster's cert-manager ingress certificate; Git holds no TLS Secret. `authorino-server-cert` comes from the service CA.

## Validation

`validate-gateway-boundary.sh` (run by `validate.sh`) opens a TCP connection from each gateway pod, without any HTTP request, to every destination the gateway needs (all must connect) and to the kube-apiserver and kubelet on a node, unneeded Authorino and Limitador ports, and public port 80 (all must be refused).

`validate-native.sh` checks:

- Authorino is `Ready` and has the TLS listener and CA mount.
- `authorino-service-ca` holds a certificate, and `authorino-server-cert` has `tls.crt` and `tls.key`.
- The Authorino Deployment, owned by the operator, mounts the CA.
- The Gateway is `Accepted` and `Programmed`.
- The listener set is exactly `api` and `qwen3-8`, with real hostnames.
- Each listener is HTTPS 443 with Terminate TLS and the reviewed `allowedRoutes`, and has current `Accepted` and `ResolvedRefs` conditions.
- `api` has at least one attached route and `qwen3-8` exactly one.
- Namespace isolation matches, and the MaaS API route is attached.

It does not send requests. `preflight.sh` refuses an existing Gateway or `authorino-service-ca` that another owner tracks.

By hand:

```bash
oc get gateway maas-default-gateway -n openshift-ingress \
  -o jsonpath='{range .status.listeners[*]}{.name} attached={.attachedRoutes}{"\n"}{end}'
oc get kuadrant kuadrant -n kuadrant-system -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}{"\n"}'
```

## Alignment with official guidance

| Topic | Official guidance (link) | This repository | Status |
|---|---|---|---|
| Gateway name, namespace, class | `maas-default-gateway` in `openshift-ingress`, class for `openshift.io/gateway-controller/v1` [1][4] | As required, class `data-science-gateway-class` (controller `openshift.io/gateway-controller/v1`) | Aligned |
| Required Gateway annotations | `opendatahub.io/managed: "false"` and `security.opendatahub.io/authorino-tls-bootstrap: "true"` [1] | Both present (the first is also set as a label) | Aligned |
| Gateway TLS | TLS must be configured [1]; listener Secret in the Gateway namespace [4] | Listeners reference the cluster ingress certificate `cert-manager-ingress-cert` directly | Aligned; renewals propagate without a sync |
| Kuadrant instance | Ready `Kuadrant` in `kuadrant-system` [1]; observability for MaaS usage metrics (section 1.18.2) [1] | `kuadrant` with `observability.enable: true` | Aligned |
| Authorino serving certificate | Annotate `authorino-authorino-authorization` for `authorino-server-cert` [1][3] | Sync-hook Job adds the annotation after checking ownership | Aligned (by Job, because the Service is operator-owned) |
| Authorino TLS listener | Enable `spec.listener.tls` with `authorino-server-cert` [1] | Declared in the CR | Aligned |
| Authorino CA trust | Set `SSL_CERT_FILE` and `REQUESTS_CA_BUNDLE` on the Deployment [1] | Service CA mounted through the Authorino CR `spec.volumes` into `/etc/pki/tls/certs` | Deviation (justified: declarative on the CR instead of editing an operator-owned Deployment; validator checks the mount) |
| Hostname per tenant Gateway | Unique hostname for each tenant Gateway; examples use `maas.<cluster-domain>` [1] | `maas.<cluster-domain>` plus a compatibility `qwen3-8-maas.<cluster-domain>` listener, patched at deploy time | Aligned |
| Load balancer annotations | `spec.infrastructure.annotations` for cloud LB settings [4]; ELB idle timeout default 60 s, range 1–4000 s [10] | 3600 s | Aligned |
| Gateway Deployment customization | `parametersRef` ConfigMap `deployment` key (upstream Istio) [9] | Resources and stats matcher | Aligned (upstream mechanism); the stats matcher selects any `*-epp-service` in `internal-models` |
| Network isolation | NetworkPolicies are additive [7]; AdminNetworkPolicy is evaluated first and cannot be overridden [11] | AdminNetworkPolicy `maas-gateway-boundary` enforces the gateway's ingress and egress over the operator's allow-all | Aligned; external-provider egress is any public 443 because policies cannot match hostnames |

## References

1. Govern LLM access with Models-as-a-Service, sections 1.2, 1.3 "Gateway requirements for Models-as-a-Service", 1.4 "Configure TLS for Models-as-a-Service", 1.15.1 (gateway AuthPolicy) and 1.18.2 (Kuadrant observability), Red Hat OpenShift AI Self-Managed 3.5. https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/govern_llm_access_with_models-as-a-service/index
2. Install Connectivity Link on OpenShift Container Platform, Red Hat Connectivity Link 1.4. https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html/install_connectivity_link/rhcl-install-on-ocp
3. Configuring certificates, 3.1.2 "Replace the default ingress certificate", 3.3.2 "Add a service certificate", 3.3.3 "Add the service CA bundle to a config map", OpenShift Container Platform 4.22. https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html/security_and_compliance/configuring-certificates
4. Configuring Gateway API, 3.2.1, 3.4.4 "Configuring an internal load balancer for a gateway", 3.7.2 "Securing client connections with edge TLS termination", OpenShift Container Platform 4.22. https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html/ingress_and_load_balancing/configuring-gateway-api
5. Sync waves and hooks, "Hook lifecycle and cleanup", Argo CD (upstream). https://argo-cd.readthedocs.io/en/stable/user-guide/sync-waves/
6. Sync options, "Respect ignore differences configs", Argo CD (upstream). https://argo-cd.readthedocs.io/en/stable/user-guide/sync-options/
7. Network Policies (policies are additive), Kubernetes (upstream). https://kubernetes.io/docs/concepts/services-networking/network-policies/
8. Kustomize, "Patches", Argo CD (upstream). https://argo-cd.readthedocs.io/en/stable/user-guide/kustomize/
9. Kubernetes Gateway API, "Automated deployment", Istio (upstream). https://istio.io/latest/docs/tasks/traffic-management/ingress/gateway-api/#automated-deployment
10. Service controller annotations, `aws-load-balancer-connection-idle-timeout`, AWS cloud provider for Kubernetes (upstream). https://cloud-provider-aws.sigs.k8s.io/service_controller/
11. Admin network policy, 2.1 "OVN-Kubernetes AdminNetworkPolicy" and 2.4 "Egress nodes and networks peer for AdminNetworkPolicy", OpenShift Container Platform 4.22. https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html/network_security/admin-network-policy
12. AdminNetworkPolicy API reference (rule order, `networks` peer), Kubernetes Network Policy API (upstream). https://network-policy-api.sigs.k8s.io/reference/spec/
