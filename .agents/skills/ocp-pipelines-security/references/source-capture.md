# Source Capture

## Official Source

| Field | Value |
|-------|-------|
| Product family | Red Hat OpenShift Pipelines |
| Baseline source | `docs/PLATFORM_BASELINE.md` |
| Documentation category | Security |
| Official guide | Securing OpenShift Pipelines |
| Source URL | https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.22/html-single/securing_openshift_pipelines/index |
| Multi-page URL | https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.22/html/securing_openshift_pipelines/index |
| Capture date | 2026-07-06 |

## Captured Sections

- Chapter 1. Using Tekton Chains for OpenShift Pipelines supply chain security
  - 1.1. Tekton Chains configuration
    - 1.1.1. Supported parameters for Tekton Chains configuration
      - 1.1.1.1. Supported parameters for Key Management Service (KMS) signers
    - 1.1.2. Create and mount the Mongo server URL secret
    - 1.1.3. Create and mount the Key Management Service (KMS) authentication token secret
    - 1.1.4. Enable Tekton Chains to operate only in selected namespaces
- Chapter 2. Secrets for signing data in Tekton Chains
  - 2.1. Generate the cosign key pair by using the TektonConfig CR
  - 2.2. Manually generate signing secrets with the cosign tool
  - 2.3. Manually generate signing secrets with the Skopeo tool
  - 2.4. Resolve the "secret already exists" error
- Chapter 3. Authenticate to an OCI registry
- Chapter 4. Create and verify task run signatures without any additional authentication
- Chapter 5. Use Tekton Chains to sign and verify image and provenance
- Chapter 6. Setting up OpenShift Pipelines in the web console to view Software Supply Chain Security elements
  - 6.1. Setting up OpenShift Pipelines to view project vulnerabilities
  - 6.2. Setting up OpenShift Pipelines to download or view software bills of materials (SBOMs)
    - 6.2.1. Viewing an SBOM in the web UI
    - 6.2.2. Downloading an SBOM in the CLI
    - 6.2.3. Reading the SBOM
- Chapter 7. Configuring the security context for pods
  - 7.1. Configuring the default and maximum SCC for pods that OpenShift Pipelines creates
  - 7.2. Configuring the SCC for pods in a namespace
  - 7.3. Running pipeline run and task run by using a custom security context constraint (SCC) and a custom service account
- Chapter 8. Secure webhooks with event listeners
  - 8.1. Provide secure connection with OpenShift routes
  - 8.2. Configure security context for event listeners
  - 8.3. Create a sample EventListener resource using secure HTTPS connection
- Chapter 9. Authenticating pipelines with repositories using secrets
  - 9.1. Providing secrets using service accounts
    - 9.1.1. Types and annotation of secrets for service accounts
      - 9.1.1.1. Git authentication secrets
      - 9.1.1.2. Container registry authentication secrets
    - 9.1.2. Configuring Basic HTTP authentication for Git using a service account
    - 9.1.3. Configuring SSH authentication for Git using a service account
    - 9.1.4. Configuring container registry authentication by using a service account
    - 9.1.5. Additional considerations for authentication using service accounts
      - 9.1.5.1. SSH Git authentication in tasks
      - 9.1.5.2. Use of secrets as a non-root user
  - 9.2. Providing secrets using workspaces
    - 9.2.1. Configuring SSH authentication for Git using workspaces
    - 9.2.2. Configuring container registry authentication using workspaces
    - 9.2.3. Limiting a secret to particular steps using workspaces
- Chapter 10. Building of container images using Buildah as a non-root user
  - 10.1. Running Buildah as a non-root user by configuring user namespaces
  - 10.2. Running Buildah as a non-root user by defining a custom SA and SCC
    - 10.2.1. Configuring custom service account and security context constraint
    - 10.2.2. Configuring Buildah to use build user
    - 10.2.3. Starting a task run with custom config map, or a pipeline run
  - 10.3. Limitations of unprivileged builds
- Chapter 11. Using buildah-ns Tekton task
  - 11.1. Differences between buildah and buildah-ns tasks
  - 11.2. Security model of the buildah-ns task
  - 11.3. Workspaces, parameters, and results for the buildah-ns task
    - 11.3.1. Workspace
    - 11.3.2. Parameters
    - 11.3.3. Results
  - 11.4. Running the buildah-ns task

## Source Boundaries

This skill covers only the security aspects of Red Hat OpenShift Pipelines 1.22.
It documents Tekton Chains supply chain security, signing secrets, OCI registry
authentication, SLSA provenance, image signing and verification, SBOM viewing,
security context constraints for pods, secure webhooks with event listeners,
pipeline authentication with Git and container repositories, and building
container images as a non-root user.

This skill does NOT cover:

- OpenShift Pipelines installation, configuration, or administration
- Tekton CRD authoring (Pipeline, Task, PipelineRun, TaskRun) beyond security examples
- Pipelines as Code setup, Repository CR configuration, or webhook setup
- General CI/CD pipeline design patterns
- OpenShift Pipelines versions other than 1.22.x
- OpenShift Builds, OpenShift GitOps, or Jenkins
- Release notes, new features, or version compatibility

## Related Official Sources

- OpenShift Pipelines documentation: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.22
- Understanding OpenShift Pipelines: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.22/html/about/understanding-openshift-pipelines
- Sigstore Cosign documentation: https://docs.sigstore.dev/cosign/overview/
- OpenShift Operator Life Cycles: https://access.redhat.com/support/policy/updates/openshift_operators
