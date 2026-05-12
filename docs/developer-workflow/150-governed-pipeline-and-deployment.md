# Stage 150: Governed Pipeline And Deployment

## Why This Matters

Agentic engineering should not mean that an assistant deploys by improvising against a cluster. Enterprise delivery needs a controlled path for tests, builds, image creation, security checks, deployment, ownership metadata, and rollback.

This planned stage shows how an agent can help create pipeline and deployment artifacts from a golden-path contract while the platform keeps delivery controls intact.

## Story Goal

Show that OpenCode can use an approved skill, software-template reference, or MCP service to create a Tekton or OpenShift Pipelines path for the Quarkus service, then hand deployment to an approved app-local GitOps route. The agent accelerates the work, but does not own the release process.

## Platform Capabilities Consumed

- Stage 090 provides Developer Hub as the future catalog and documentation surface.
- Stage 130 provides OpenCode agents and skills.
- Stage 140 provides the demo-owned Coolstore Inventory Quarkus service target described in the [`Quarkus target service options`](quarkus-target-service-options.md) assessment.
- The implemented GitOps pattern in stages `010-090` provides the delivery model to preserve.

## What This Stage Adds

This planned stage adds the governed delivery exercise.

- A pipeline generation skill or MCP-backed workflow.
- A first project-local golden-path packet using `.tekton/` Pipelines-as-Code.
- Build, test, image, and static deployment handoff stages.
- App-local GitOps deployment base for the generated service.
- Developer Hub links for repository, docs, pipeline, and deployed route.
- TechDocs guidance for how developers inspect the pipeline, GitOps state, and rollback path.
- MCP Gateway and template-access guidance for authenticated, authorized access to pipeline-generation tools.
- A handoff to Stage 155 for SBOM, signing, provenance, VEX, image scanning, and promotion evidence.

## Developer Workflow

### Starting Point

The developer has a reviewed `coolstore-inventory-service` implementation or reference output from Stage 140. OpenCode is available with the pipeline engineer role or pipeline creation skill.

The pipeline should be treated as part of the golden path, not a one-off YAML generation exercise. The input packet should identify the approved template, parameters, required secrets, image registry pattern, app-local GitOps path, validation commands, and rollback evidence.

### AI-Assisted Task

Ask the agent to generate pipeline and deployment artifacts for the Coolstore Inventory Quarkus service from approved templates. The initial implementation should focus on structure and validation before attempting live cluster execution.

The target pipeline should eventually:

- run tests;
- build the application;
- build or assemble an image;
- perform the selected checks;
- update or hand off to the app-local GitOps path;
- expose evidence through Developer Hub or repository documentation.

Developer Hub software-template examples show several useful target patterns. For this first demo, the accepted pattern is a single renamed `coolstore-inventory-service` repository: Quarkus source at the root, Pipelines-as-Code assets under `.tekton/`, app-local GitOps desired state under `gitops/`, and rollout, promotion, and rollback evidence in repository documentation. A later multi-repository promotion model can still be evaluated after the first live workflow is stable.

The first delivery slice is now selected for the application repository:

- `.tekton/pull-request.yaml` triggers on pull requests to `main`;
- `./mvnw -B test package` runs before image build;
- Buildah builds the app-local `Containerfile`;
- the image is pushed to the OpenShift internal registry path `image-registry.openshift-image-registry.svc:5000/coolstore-inventory-dev/coolstore-inventory-service:<revision>`;
- app-local Kustomize state lives under `gitops/base` and `gitops/overlays/dev`;
- namespace, app, service, route, runtime service account, and image repository names are fixed as `coolstore-inventory-dev` and `coolstore-inventory-service`;
- the pipeline does not deploy the service in this first slice;
- OpenShift Pipelines and Pipelines-as-Code remain prerequisites, not new platform stage installs.

### Prompts Or Agent Instructions

Recommended planning instruction:

```text
Plan a Tekton pipeline for this Quarkus service using only approved repository patterns. Include test, build, image, scan, and GitOps handoff steps. Do not create resources until the plan identifies templates, parameters, secrets, and validation.
```

Recommended golden-path instruction:

```text
Use the approved golden-path delivery packet. Identify where this repository owns application source, app-local desired state, image metadata updates, and rollback evidence before generating YAML.
```

Recommended review instruction:

```text
Review the generated pipeline for hard-coded secrets, direct cluster mutation outside the approved path, missing tests, and missing rollback evidence.
```

### Expected Developer Actions

- Confirm whether OpenShift Pipelines and Pipelines-as-Code are enabled for the implementation environment.
- Confirm that the project-local golden-path packet remains the selected template source for the first demo.
- Review the pipeline plan before generation.
- Confirm secret references are placeholders or approved platform references.
- Run static YAML and Kustomize validation once resources exist.
- Connect Developer Hub metadata only to real resources.

### Review And Quality Gates

- Pipeline YAML parses cleanly.
- No credentials are committed.
- Deployment does not bypass the approved app-local GitOps or platform route.
- Test execution is part of the pipeline.
- Image and deployment metadata are traceable.
- Pipeline, application, and app-local GitOps ownership are visible through Developer Hub metadata when implemented.
- Rollback notes are documented.
- MCP-backed pipeline or template tools use identity-based access, least privilege, and auditable approval points.
- Supply-chain evidence gaps are carried forward to Stage 155 instead of being hidden inside deployment YAML.

### Evidence To Capture

- Pipeline plan and template source.
- Generated `.tekton/` PipelineRun, `Containerfile`, and app-local GitOps files.
- Static validation output.
- PipelineRun result once a live environment exists.
- App-local GitOps application or deployment handoff evidence.
- Developer Hub links once implemented.

## What To Notice And Why It Matters

The proof point is that agentic work stops at the right boundary. The assistant can create reviewable artifacts, but the platform still controls the path from source to running service.

This matters because delivery shortcuts are one of the easiest ways for AI-assisted work to undermine enterprise controls. A governed pipeline makes the acceleration compatible with traceability and rollback.

## How Red Hat And Open Source Make It Work

Red Hat OpenShift provides the application platform. Red Hat OpenShift Pipelines, based on Tekton, can provide Kubernetes-native CI/CD. Red Hat OpenShift GitOps can reconcile approved desired state from the app-local `gitops/` path. Red Hat Developer Hub can expose ownership, documentation, pipeline links, and service metadata.

The Red Hat golden-path guidance strengthens this stage. It describes a supported path that includes a repository template, a pipeline, deployment manifests, observability defaults, GitOps, and Tekton. The Red Hat Developer Hub software-template sources also show how templates can create application repositories, pipeline definitions, desired-state manifests, TechDocs, and catalog links.

OpenCode and MCP can help generate or retrieve approved templates, but they should not become an uncontrolled deployment mechanism.

The MCP security pattern matters here because pipeline generation is a privileged workflow. A future implementation should expose template lookup and pipeline creation through authenticated and authorized services, with identity-based tool filtering, explicit approval points, and network boundaries around any tool that can affect delivery resources.

## Trust Boundaries

Pipeline credentials, image registry access, template trust, MCP tool access, and deployment authority are sensitive boundaries. The agent should reference approved secret names and templates, not create real credentials or deploy directly outside the documented platform path.

## Red Hat Products Used

- **[Red Hat OpenShift Pipelines](https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/)** provides the Tekton-based pipeline path when enabled.
- **[Red Hat OpenShift GitOps](https://www.redhat.com/en/technologies/cloud-computing/openshift/gitops)** provides the desired-state deployment model.
- **[Red Hat Developer Hub](https://www.redhat.com/en/technologies/cloud-computing/developer-hub)** provides the future catalog and documentation surface.
- **[Red Hat OpenShift](https://www.redhat.com/en/technologies/cloud-computing/openshift)** provides the target application platform.

## Open Source Projects To Know

- [Tekton](https://tekton.dev/) provides the cloud-native pipeline primitives.
- [Argo CD](https://argo-cd.readthedocs.io/) provides GitOps reconciliation patterns.
- [Backstage Software Templates](https://backstage.io/docs/features/software-templates/) provide the upstream scaffolding mechanism used by Developer Hub.
- [OpenCode](https://opencode.ai/) provides the agent workflow used to create and review delivery artifacts.

## Future Implementation Notes

- Treat OpenShift Pipelines and Pipelines-as-Code as prerequisites for this extension, not installs owned by the current platform flow.
- Use the [`Quarkus target service options`](quarkus-target-service-options.md) assessment as the application baseline for the first pipeline exercise.
- Use the [`coding-exercises` application repository plan](coding-exercises-app-repo-plan.md) as the repository baseline for the renamed `coolstore-inventory-service` repo.
- Use local `coolstore-demo/inventory-gitops` only as a historical reference. Update any adopted pattern for current OpenShift, current Tekton API versions, tests-before-image behavior, and GitOps handoff expectations.
- Use the application repository's project-local golden-path packet as the first template source.
- Put first-demo GitOps desired state under `gitops/` in the renamed service repository.
- Use `.tekton/` for the first Pipelines-as-Code PipelineRun and keep image update, promotion, and rollback evidence in repository documentation until live validation exists.
- Revisit Developer Hub software templates or an authenticated MCP Gateway service after the project-local packet is validated.
- Add static validation and later live PipelineRun validation.
- Add Developer Hub catalog and TechDocs links only after real resources exist.

## Deploy And Validate

This planned workflow stage does not yet include deploy or validate scripts. Static validation for this iteration is documentation review only.

## References

- [Red Hat OpenShift Pipelines documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/)
- [Red Hat OpenShift GitOps documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_gitops/)
- [Designing Golden Paths](https://www.redhat.com/en/blog/designing-golden-paths)
- [How golden paths improve developer productivity](https://developers.redhat.com/articles/2025/01/29/how-golden-paths-improve-developer-productivity)
- [How to template AI software in Red Hat Developer Hub](https://developers.redhat.com/articles/2024/11/12/template-ai-software-red-hat-developer-hub)
- [Red Hat Developer Hub Software Templates Library](https://github.com/redhat-developer/red-hat-developer-hub-software-templates)
- [Quarkus target service options](quarkus-target-service-options.md)
- [coding-exercises application repository plan](coding-exercises-app-repo-plan.md)
- [Advanced authentication and authorization for MCP Gateway](https://developers.redhat.com/articles/2025/12/12/advanced-authentication-authorization-mcp-gateway)
- [MCP security: Implementing robust authentication and authorization](https://www.redhat.com/en/blog/mcp-security-implementing-robust-authentication-and-authorization)
- [Tekton](https://tekton.dev/)
- [Red Hat Developer Hub documentation](https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.9)

## Next Stage

[Stage 155: Red Hat Trusted Software Supply Chain](155-red-hat-trusted-software-supply-chain.md) adds supply-chain evidence before the workflow shifts to modernization at scale.
