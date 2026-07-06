---
name: rhoai-certificate-management
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "RHOAI Platform"
description: >
  Use when installing, documenting, reviewing, or rebuilding Red Hat OpenShift
  AI certificate handling: DSCI trustedCABundle managementState, cluster-wide
  and custom CA bundles, odh-trusted-ca-bundle ConfigMaps, self-signed
  certificate handling for S3-compatible object storage, AI pipelines,
  workbenches, model serving, and Llama Stack, CA bundle removal, namespace
  opt-out, and GitOps review of certificate-related manifests. Do NOT use for
  production PKI design, certificate issuance, cert-manager installation,
  unrelated OpenShift ingress certificate work, or live troubleshooting; use
  env-* skills for live diagnosis.
---

# RHOAI Certificate Management

Use this skill to configure and review OpenShift AI certificate behavior for
the active baseline in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product configuration details.
Official Red Hat documentation is product authority. This skill adapts the
official certificate guidance to this repo's GitOps operating model and demo
security posture.

## Demo Policy

For this demo:

- Keep `spec.trustedCABundle.managementState: Managed` unless there is an
  explicit architecture reason to delegate CA bundle management elsewhere.
- Prefer a custom RHOAI CA bundle for demo-specific external endpoints that use
  self-signed or private CA certificates.
- Use the cluster-wide CA bundle only when the certificate must be trusted
  across the OpenShift cluster.
- Do not commit private keys. Treat CA PEM content as environment-specific
  unless it is intentionally public demo material.
- Use `--insecure-skip-tls-verify=true` and `curl -k` only for local validation
  and demo convenience; do not convert that shortcut into product guidance.

## Certificate Model

OpenShift AI uses the `DSCInitialization` trusted CA bundle settings to control
the `odh-trusted-ca-bundle` ConfigMap in non-reserved namespaces.

Management states:

- `Managed`: the OpenShift AI Operator manages and updates the trusted CA
  bundle ConfigMap.
- `Unmanaged`: the ConfigMap remains, but the Operator no longer updates it
  from `customCABundle`.
- `Removed`: the Operator removes `odh-trusted-ca-bundle` from existing
  non-reserved namespaces and prevents new ones from being created.

The managed ConfigMap can contain:

- `ca-bundle.crt`: cluster-wide CA bundle injected by the Cluster Network
  Operator.
- `odh-ca-bundle.crt`: custom CA certificates added through the DSCI
  `customCABundle` field.

## Workflow

1. Confirm the active baseline in `docs/PLATFORM_BASELINE.md`.
2. Decide whether the certificate belongs in the cluster-wide CA bundle, RHOAI
   custom CA bundle, or a component-specific bundle.
3. Read `references/official-doc-extraction.md` for the affected component.
4. Verify the target CRD fields before writing GitOps:
   - `oc explain dscinitialization.spec.trustedCABundle`
   - `oc explain datasciencepipelinesapplication.spec`
   - `oc explain llamastackdistribution.spec.server.tlsConfig`
   - `oc explain datasciencecluster.spec.components.kserve`
5. Encode only verified fields in GitOps manifests.
6. Validate with `references/validation-checklist.md`.
7. Update README or operations notes only with claims backed by implemented
   manifests and official documentation.

## Component Routing

Use these patterns:

- Cluster-wide trust: update OpenShift proxy trusted CA, then verify
  `odh-trusted-ca-bundle` appears in non-reserved namespaces.
- RHOAI-specific custom trust: set DSCI `trustedCABundle.customCABundle` with
  `managementState: Managed`.
- S3-compatible object storage or in-cluster databases: add the relevant CA to
  the RHOAI custom CA bundle.
- Workbench S3-compatible object storage data workflows: use
  `rhoai-s3-object-storage-data` for endpoint and Boto3 behavior, then return
  here for trusted CA bundle changes.
- AI pipelines: use cluster-wide/custom trust or a DSPA-specific CA bundle.
- Workbenches: restart existing workbenches after CA bundle changes; new
  workbenches pick up the configured bundle.
- Model serving: use a provided ingress gateway certificate through the KServe
  serving configuration only after verifying the active `DataScienceCluster`
  schema.
- Llama Stack: prefer referencing `odh-trusted-ca-bundle` from
  `spec.server.tlsConfig.caBundle`.
- Namespace opt-out: annotate a namespace only when the project should not get
  `odh-trusted-ca-bundle`.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
- `examples/demo-certificate-patterns.md`
