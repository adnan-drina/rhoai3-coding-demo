# Stage 070: Advanced Application Platform

> **Release status:** implementation on `codex/stage070-gitlab-upgrade`; Stage 070 has not been deployed. The MTA workspace candidate passed a bounded CLI/Java-provider check on OpenShift. This does not qualify portal login, delivery, signing or AI migration. See the [release plan](../../docs/migration/070-upgrade-and-gitlab-plan-20261013.md#implementation-status).

## Why This Matters

Private models help protect source code, but developers also need a reliable route from an approved project to a tested application. This stage connects self-service, private source control, managed workspaces, modernization and delivery. Platform teams own the shared services and credentials; developers work in their own repositories and project namespaces.

[Red Hat Developer Hub](https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10) provides the software catalog and templates. [OpenShift Dev Spaces](https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30) provides the workspace. OpenShift Pipelines and Argo CD carry an approved change through quality checks into a deployment reconciled from Git.

## Architecture

```text
Existing platform: OpenShift · Keycloak · NooBaa · MaaS · internal registry
                                    |
Stage 070: Developer Hub -> private GitLab project -> Dev Spaces workspace
                                    |
                          per-project Tekton pipeline
                                    |
                  compile/test -> SonarQube gate -> image digest
                                    |
                       platform-owned GitLab delivery repo
                                    |
                         Argo CD -> application namespace

MTA Hub + Developer Lightspeed + Solution Server + Agentic Migration Factory
                         -> governed MaaS access
TAS: persistent signing services; signed delivery remains to be qualified
```

- New in this stage: GitLab CE, developer workspaces, the portal, delivery tooling, SonarQube and MTA with its AI components.
- Reused: the existing Keycloak service, NooBaa, MaaS and internal image registry. Stage 060 remains the owner of the installed Agent Sandbox controller.
- Source, delivery configuration and shared platform configuration have separate permissions. GitLab runs without a second container registry or GitLab runners; Tekton is the build engine.

## What This Stage Adds

- **Private GitLab workflows.** Existing demo users sign in through the platform realm. Templates create private repositories and request platform enrollment of their immutable first commit. Project-bound webhooks trigger only that project's main-branch builds.
- **Managed development.** Dev Spaces 3.30.2 uses one persistent volume per workspace, authenticated GitLab access, explicit source allowlists and retained migration worker identities. The MTA image contains verified 8.3 tools and editor extensions.
- **Developer Hub 1.10.5.** Catalog, templates and TechDocs come from one pinned GitLab platform revision. Kubernetes, Topology, Tekton and Argo integrations make the project's delivery visible in the portal.
- **GitOps delivery.** Pipelines 1.24.0 checks out an exact commit, builds/tests, enforces the SonarQube gate and pushes to the internal registry. Promotion writes the image digest into a platform-owned delivery repository and waits for Argo and the deployment to agree.
- **Modernization with AI.** MTA 8.3.0 enables the LLM proxy, Solution Server and native Agentic Migration Factory. Its credential uses an owner-bound MaaS subscription. Models remain stopped until the operator authorizes validation.
- **Persistent shared services.** GitLab CE 19.4.2 and SonarQube Community Build 26.9 use dedicated PostgreSQL services. TAS 1.5.0 retains signing roots and service data. GitLab object storage uses six scoped NooBaa claims.

The reference [OpenShift Developer Days project](https://github.com/rhpds/ocp-dev-days-rdshw-gitops) informs the integration patterns. Product versions, credential boundaries and deployment checks are reviewed independently. Chart-based services are rendered during authoring into ordinary checked-in resources; deployment uses Kustomize, with no Helm runtime.

The `slim` overlay omits MTA. Application migration requires the full overlay; its template refuses a missing MTA Hub endpoint.

## Trust Boundaries

GitLab publisher, enrollment, catalog, clone and delivery identities have separate credentials. A webhook can request a build, not provision a project. Only the image-build Task receives the build SCC and registry push permission. Runtime workloads receive no API token. Migration workers retain their existing restricted identities and run-control contract; no existing migration run is reset or upgraded by this release.

The ordinary delivery contract requires a passing quality gate and an exact internal image digest. A configured TAS service is not proof of signed delivery. Signature/attestation production, verification and any blocking signed-promotion policy are explicitly pending live qualification. GitLab CE and SonarQube Community Build are upstream components, separate from Red Hat product support.

## Red Hat Products Used

| Product | Role |
|---|---|
| Red Hat Developer Hub | Catalog, TechDocs and project templates |
| Red Hat OpenShift Dev Spaces | Managed IDE and workspace lifecycle |
| Red Hat OpenShift Pipelines | Builds, tests and quality-gated delivery |
| Red Hat Trusted Artifact Signer | Signing services and trust-root lifecycle |
| Migration Toolkit for Applications | Analysis, Developer Lightspeed and migration services |
| Red Hat build of Keycloak | Reused platform identity broker |
| OpenShift / OpenShift Data Foundation | GitOps, registry, storage, RBAC and NooBaa |

## Deploy And Validate

Review the full feature-branch diff and the [release checklist](../../docs/migration/070-upgrade-and-gitlab-plan-20261013.md#implementation-status) before publishing and deploying. Keep the models stopped during platform installation.

```bash
./stages/070-advanced-app-platform/validate.sh --static
./stages/070-advanced-app-platform/deploy.sh
./stages/070-advanced-app-platform/validate.sh
```

Static checks need the [test dependencies](tests/requirements.txt), Kustomize and Git. Live deployment uses the repository's cluster guard. [Operations](../../docs/OPERATIONS.md#stage-070-gitlab-release) contains deployment order, credentials, lifecycle and acceptance. [Troubleshooting](../../docs/TROUBLESHOOTING.md#stage-070-gitlab-project-enrollment-is-pending) covers refusal and recovery.

Source: [Stage 070 Kustomize resources](../../gitops/stages/070-advanced-app-platform/base/). The root platform Application retains its GitHub bootstrap source; project tooling, owned goldens, catalog and delivery use GitLab. A full platform-root cutover is a separate reviewed step.

## References

- [Dev Spaces 3.30 administration](https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30)
- [RHDH 1.10 Tekton configuration](https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html/configuring_dynamic_plugins/enable-the-tekton-plugin_configuring-dynamic-plugins)
- [Pipelines 1.24 security](https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/securing_openshift_pipelines/index)
- [MTA 8.3 documentation](https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3)
- [GitLab OpenShift deployment guidance](https://docs.gitlab.com/charts/installation/cloud/openshift/)

## Next Stage

[Stage 110: AI-Assisted Development](../110-ai-assisted-development/README.md) starts the developer workflow in the governed workspace and delivers through this stage's pipeline.
