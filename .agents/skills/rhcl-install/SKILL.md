---
name: rhcl-install
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "rhcl"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "OpenShift Platform"
description: >
  Use when installing Red Hat Connectivity Link on single or multiple clusters,
  including operator installation, prerequisites, and Istio/Envoy gateway setup.
  Do NOT use for deploying policies (AuthPolicy, RateLimitPolicy, DNSPolicy,
  TLSPolicy); use rhcl-configure. Do NOT use for MCP gateway installation; use
  rhcl-install-mcp.
---

# RHCL Install

Use this skill to ground Red Hat Connectivity Link installation decisions in
official RHCL 1.4 documentation for the active baseline in
`docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority.

## Demo Posture

The demo pins RHCL at `rhcl-operator.v1.3.4` for MaaS Gateway stability. RHCL
1.4.0 is deprecated in official release notes. Skills document the 1.4
documentation as the canonical reference but Stage 040 GitOps-manages the
Subscription at 1.3.x. Do not approve RHCL 1.4.x InstallPlans until Red Hat
publishes a supported replacement path.

## Key Concepts

- Connectivity Link installs via OLM (`rhcl-operator`) from `redhat-operators`
  on the `stable` channel.
- Component operators: Authorino Operator, DNS Operator, Limitador Operator.
- The `Kuadrant` CR (apiVersion `kuadrant.io/v1beta1`) activates the platform.
- Default gateway controller: OpenShift Container Platform Cluster Ingress
  Operator (`gatewayClassName: openshift-default`).
- Alternative: Istio via OpenShift Service Mesh (set
  `ISTIO_GATEWAY_CONTROLLER_NAMES=istio.io/gateway-controller` on
  Subscription).
- Supported OCP versions: 4.18–4.21.
- Required: cert-manager Operator for Red Hat OpenShift 1.18.
- Optional: Redis for RateLimitPolicy, Keycloak for AuthPolicy, cloud DNS.

## Workflow

1. Confirm the active RHCL baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/official-doc-extraction.md`.
3. Identify whether the task is:
   - new install via web console or CLI
   - install with Istio as gateway controller
   - DNS provider credentials configuration
   - multicluster install
   - disconnected install
4. For manifests, verify API versions against official docs and cluster schema.
5. Validate with verification commands from the extraction.

## Validation Signals

- `oc wait kuadrant/kuadrant --for="condition=Ready=true" -n <ns> --timeout=300s`
- All component operator pods Running in the install namespace.
- No image pull failures: `oc get events -n <ns> --field-selector reason=Failed`

## Related Skills

- `rhcl-install-mcp` for MCP gateway operator installation.
- `rhcl-configure` for deploying gateway policies.
- `rhoai-maas-governance` for RHOAI MaaS integration with Connectivity Link.
- `ocp-ingress-gateway-routes` for OCP Gateway API primitives.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
