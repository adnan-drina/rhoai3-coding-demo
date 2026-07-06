---
name: ocp-pipelines-security
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "ocp"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "OpenShift Platform"
description: >
  Use when securing OpenShift Pipelines: Tekton Chains supply chain security,
  SLSA provenance, image signing, OCI storage, transparency logs, secret
  management, Git SSH authentication, pipeline authentication with repositories,
  and security contexts for OpenShift Pipelines 1.22. Do NOT use for installing
  pipelines (use ocp-pipelines-install-config), creating CI/CD pipelines (use
  ocp-pipelines-cicd), or Pipelines as Code (use ocp-pipelines-as-code).
---

# OCP Pipelines Security

Use this skill to ground OpenShift Pipelines security guidance in the
official Red Hat OpenShift Pipelines 1.22 securing guide for the active
baseline in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority.

## Tekton Chains Supply Chain Security

Tekton Chains is a CRD controller installed by default with the OpenShift
Pipelines Operator. It observes task run and pipeline run executions, takes
snapshots on completion, converts them to standard payload formats (in-toto /
SLSA), signs the artifacts, and stores them. Configuration is managed via the
`TektonConfig` CR in the `chain:` section.

Key configuration areas:
- Task run, pipeline run, and OCI artifact format, storage, and signer
- KMS signer integration (HashiVault, AWS, GCP, Azure)
- Transparency log uploads (Rekor)
- x509 keyless signing with Fulcio
- Docstore and Grafeas storage backends
- Namespace scoping to limit Chains to specific namespaces

Read `references/official-doc-extraction.md` for full parameter tables.

## Signing Secrets

Tekton Chains requires a `signing-secrets` secret in the `openshift-pipelines`
namespace. Supports `x509` and `cosign` schemes (use only one).

Key pair generation methods:
- **Automated**: Set `generateSigningSecret: true` in `TektonConfig` CR
- **Manual cosign**: `cosign generate-key-pair k8s://openshift-pipelines/signing-secrets`
- **Manual skopeo**: `skopeo generate-sigstore-key` with base64 encoding

## OCI Registry Authentication

Configure a service account with Docker config credentials for Tekton Chains to
push signatures to OCI registries. Best practice: create a dedicated service
account rather than patching the default `pipeline` SA.

## Image and Provenance Signing and Verification

End-to-end workflow for signing images with Tekton Chains and verifying with
cosign. Includes Rekor transparency log integration for provenance discovery.

## Software Supply Chain Security in the Web Console

- **Vulnerability viewing**: PipelineRun details show vulnerabilities by severity
  when tasks produce `SCAN_OUTPUT` results (available from OCP 4.15+)
- **SBOM viewing/downloading**: Tasks produce `LINK_TO_SBOM` results; download
  via `cosign download sbom`
- **Signed badge**: Displayed next to PipelineRun names when Tekton Chains is
  configured

## Security Context for Pods

Configure SCCs for pipeline-created pods:
- **Cluster-wide**: Set `default` and `maxAllowed` SCC in `TektonConfig` CR
  under `spec.platforms.openshift.scc`
- **Per-namespace**: Set `operator.tekton.dev/scc` annotation on namespace
- **Custom SCC**: Create custom SCC with `fsGroup.type: RunAsAny` to avoid pod
  timeouts, associate with a custom service account

## Secure Webhooks with Event Listeners

- Label namespace with `operator.tekton.dev/enable-annotation=enabled` for HTTPS
- Create re-encrypted TLS routes for external access
- Configure pod-level and container-level security context in EventListener CR

## Pipeline Authentication with Repositories

Two approaches for providing credentials:

### Service Account Method
- Git: `kubernetes.io/basic-auth` or `kubernetes.io/ssh-auth` with
  `tekton.dev/git-*` annotations
- Container registry: `kubernetes.io/basic-auth` (with `tekton.dev/docker-*`
  annotations), `kubernetes.io/dockercfg`, or `kubernetes.io/dockerconfigjson`
- Associate secrets with a service account, then reference in TaskRun/PipelineRun

### Workspace Method
- No annotations required
- Bind secrets to named workspaces at runtime
- Can limit secret access to specific steps by defining workspace in both task
  and step specs

## Non-Root Buildah Builds

Two approaches:
- **User namespace method**: Add CRI-O user namespace annotations; simpler but
  some images may not build
- **Custom SA/SCC method**: Create SCC with `allowPrivilegeEscalation: true`
  and `runAsUser.uid: 1000`; more compatible but elevated privileges

The `buildah-ns` task provides user namespace isolation out of the box with
`io.kubernetes.cri-o.userns-mode: "auto"` annotation.

Limitations: `--mount=type=cache` and `--mount=type=secret` may fail in
unprivileged builds.

## Workflow

1. Confirm the active OpenShift baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/official-doc-extraction.md`.
3. Identify whether the question concerns:
   - Tekton Chains configuration and supply chain security
   - Signing secrets and key management
   - OCI registry authentication for Chains
   - Image signing and provenance verification
   - SBOM and vulnerability viewing in the web console
   - Security context constraints for pipeline pods
   - Secure webhook event listeners
   - Git or container registry authentication for pipelines
   - Non-root Buildah image builds
4. Use exact parameter names, API versions, and procedures from the extraction.
5. When advising on security configuration, note the trust boundaries between
   signing keys, storage backends, and transparency logs.

## Related Skills

- Use `ocp-pipelines-release-notes` for OpenShift Pipelines 1.22 release notes,
  version compatibility, and known issues.
- Use `ocp-cicd-builds` for OpenShift build strategies and BuildConfig.
- Use `ocp-gitops-operator` for OpenShift GitOps and Argo CD behavior.
- Use `ocp-security-rbac-scc` for general OpenShift RBAC and SCC guidance.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
