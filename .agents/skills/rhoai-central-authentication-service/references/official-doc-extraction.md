# Official Doc Extraction

Use this reference when authoring or reviewing centralized authentication
service content.

## Component Purpose

The centralized authentication service provides a common authentication path
for OpenShift AI services when the cluster uses an external OIDC provider with
direct authentication. It addresses direct OIDC configurations where the
internal OpenShift `oauth` service is disabled and application dependencies on
`oauth-proxy` sidecars no longer work.

The service uses:

- `data-science-gateway` for external entry points and routing
- `kube-auth-proxy` for Kubernetes token review and delegated authorization
- Gateway API support in the underlying OpenShift cluster
- a `GatewayConfig` resource for OIDC provider configuration

Authorization to backend services still relies on service or pod-level controls
such as `kube-rbac-proxy`; centralized authentication does not replace RHOAI
user and administrator access policy.

## Supported Authentication Paths

The chapter describes two access patterns:

- browser-based OIDC authentication for dashboard and service UI access
- service account bearer-token authentication for programmatic API calls

Use service account token access only when a workload or automation genuinely
needs programmatic access. Do not commit bearer tokens or generated kubeconfig
material.

## Prerequisites

Before configuring the central authentication service, confirm:

- OpenShift is already configured for direct authentication with the same
  external OIDC provider that the Gateway uses.
- OpenShift AI is installed and deployed.
- `DataScienceCluster` and `DSCInitialization` are deployed.
- The OpenShift AI Operator is deployed in `rhods-operator`.
- Gateway API support is enabled on OpenShift Container Platform 4.19.9 or
  later.
- You have cluster-admin access.
- Provider details are available:
  - issuer URL
  - client ID
  - client secret
  - realm name for Keycloak when that provider is used

OpenShift identity-provider setup is outside this skill. Use the official
OpenShift documentation for that configuration.

## Preflight Checks

The official chapter verifies the OpenShift authentication rollout before
configuring the Gateway:

```bash
oc get authentication.config/cluster -o jsonpath='{.spec.type}'
oc get authentication.config/cluster -o jsonpath='{.spec.oidcProviders[*].name}'
oc get co kube-apiserver
```

Proceed only when cluster authentication reports OIDC, the expected provider is
configured, and the kube-apiserver rollout is complete.

## GatewayConfig OIDC Shape

The official chapter configures OIDC through `GatewayConfig.spec.oidc`.

Captured fields:

| Field | Purpose |
|-------|---------|
| `oidc.issuerURL` | Issuer URL for the external OIDC provider. |
| `oidc.clientID` | OIDC client ID registered with the provider. |
| `oidc.clientSecretRef.name` | Kubernetes Secret containing the client secret. |
| `oidc.clientSecretRef.key` | Secret key that stores the client secret value. |
| `providerCASecretName` | Optional Secret name for a custom provider CA bundle. |

The official examples use more than one `GatewayConfig` object name
(`default-gateway` and `gatewayconfig`). Always verify the active object name
before creating GitOps patches:

```bash
oc get gatewayconfigs
oc explain gatewayconfig.spec
```

## OIDC Client Secret Handling

The official chapter creates a Kubernetes `Secret` in the `openshift-ingress`
namespace for the OIDC client secret and references it from
`GatewayConfig.spec.oidc.clientSecretRef`.

Repo policy:

- Do not commit real `clientSecret` values.
- Do not write live secrets into GitOps examples.
- Use the future project-approved secret flow for active manifests.
- If a placeholder Secret is committed for structure, it must contain dummy
  data only and be clearly unusable.

## Service Account Token API Access

For programmatic access, the chapter shows:

1. Creating a service account in the target namespace.
2. Granting least-privilege RBAC to access services through `kube-rbac-proxy`.
3. Creating a token with `oc create token`.
4. Getting the `data-science-gateway` route from `openshift-ingress`.
5. Calling the service path with an `Authorization: Bearer` header.

Kubernetes requires service account token durations to be at least 10 minutes.
Treat generated service account tokens as credentials. Use them only in local
operations or secure automation storage, never in committed files.

## Custom Provider CA

If the external OIDC provider uses a custom or private certificate authority,
the chapter configures trust through a Secret in `openshift-ingress` and
`GatewayConfig.spec.providerCASecretName`. The Gateway controller mounts this
Secret and configures `kube-auth-proxy` to trust the CA.

Keep broader cluster and component certificate guidance in
`rhoai-certificate-management`; this skill only covers the provider CA bundle
used by the central authentication service.

## Troubleshooting Signals

Use documented failure signals before changing manifests:

| Symptom | Primary signal | Likely direction |
|---------|----------------|------------------|
| Token creation fails with a duration error | API rejects `--duration` below 10 minutes | Use a token duration of at least 10 minutes. |
| Gateway returns `HTTP 401 Unauthorized` | Bearer token is invalid, expired, malformed, or token review is blocked | Generate a new token, check header format, and inspect `kube-auth-proxy` logs in `openshift-ingress`. |
| `GatewayConfig` status is not ready | `Ready: False` or missing OIDC configuration in status | Check `GatewayConfig`, OIDC Secret existence, issuer URL reachability, and client Secret correctness. |
| `kube-auth-proxy` fails to start | Deployment not ready, pods pending, or pods in `CrashLoopBackOff` | Check deployment, logs, pod events, `kube-auth-proxy-creds`, issuer reachability, and client ID. |
| Gateway is inaccessible | 502 or 503 on `data-science-gateway` | Check Gateway, HTTPRoute, EnvoyFilter, and `kube-auth-proxy` Service in `openshift-ingress`. |
| OIDC authentication fails | Redirect loops or explicit auth errors | Check `kube-auth-proxy` logs, `kube-auth-proxy-creds`, OIDC discovery endpoint, redirect URI, client secret, and issuer URL. |
| Dashboard is not accessible after successful authentication | 403 Forbidden | Check dashboard deployment/logs, user permissions, dashboard HTTPRoute, and expected user groups such as `odh-users`. |

If the problem is not covered by the official chapter or release notes, route
the issue to Red Hat Support with collected evidence.

## Verification Commands

These commands are examples for documentation and review. Run live commands
only after applying the OpenShift safety guard in `AGENTS.md`.

```bash
oc get gatewayconfigs
oc get gatewayconfig <gatewayconfig_name> -o yaml
oc describe gatewayconfig <gatewayconfig_name>
oc get secret <oidc_client_secret_name> -n openshift-ingress
oc get deployment kube-auth-proxy -n openshift-ingress
oc logs -l app=kube-auth-proxy -n openshift-ingress
oc get gateway data-science-gateway -n openshift-ingress
oc get httproute -n openshift-ingress
oc get envoyfilter -n openshift-ingress
oc get service kube-auth-proxy -n openshift-ingress
oc explain gatewayconfig.spec
```
