# Stage 150: Governed Pipeline And Deployment

## Status

This is a planned developer workflow stage. It is not part of [`../../flows/default.yaml`](../../flows/default.yaml) and does not include deploy scripts, validate scripts, GitOps manifests, or an Argo CD Application.

## Why This Matters

Agentic engineering must not turn deployment into an improvised cluster session. Enterprise delivery needs a controlled path for tests, builds, image creation, security checks, deployment, ownership metadata, and rollback.

Stage 150 shows how an agent can help create pipeline and deployment artifacts from an approved golden-path contract while the platform keeps delivery controls intact.

## What This Stage Adds

This planned stage adds the delivery workflow for `coolstore-inventory-service`.

- Pipelines-as-Code assets under `.tekton/`.
- Tests before image build.
- Buildah image build from an app-local `Containerfile`.
- Image push to the OpenShift internal registry.
- App-local Kustomize state under `gitops/base` and `gitops/overlays/dev`.
- Rollout, promotion, and rollback evidence in repository documentation.
- No direct service deployment from the first pipeline slice.

OpenShift Pipelines and Pipelines-as-Code are prerequisites for this extension. They are not installed by the current `010-090` platform flow.

## Platform Capabilities Consumed

- Stage 090 provides Developer Hub as the future catalog and documentation surface.
- Stage 130 provides OpenCode agents and skills.
- Stage 140 provides the `coolstore-inventory-service` target.
- Stages 010-090 provide the GitOps operating model to preserve.

## Developer Workflow

The developer has a reviewed service implementation or reference output from Stage 140. OpenCode uses a pipeline engineer role or pipeline creation skill to produce reviewable delivery artifacts.

The selected first delivery slice is:

- `.tekton/pull-request.yaml` triggers on pull requests to `main`;
- `./mvnw -B test package` runs before image build;
- Buildah builds the app-local `Containerfile`;
- the image is pushed to `image-registry.openshift-image-registry.svc:5000/coolstore-inventory-dev/coolstore-inventory-service:<revision>`;
- namespace, app, service, route, service account, and image repository names use `coolstore-inventory-dev` and `coolstore-inventory-service`;
- the first pipeline does not deploy the service.

## Starter Prompts

```text
Plan a Tekton pipeline for this Quarkus service using only approved repository patterns. Include test, build, image, scan, and GitOps handoff steps. Do not create resources until the plan identifies templates, parameters, secrets, and validation.
```

```text
Use the approved golden-path delivery packet. Identify where this repository owns application source, app-local desired state, image metadata updates, and rollback evidence before generating YAML.
```

```text
Review the generated pipeline for hard-coded secrets, direct cluster mutation outside the approved path, missing tests, and missing rollback evidence.
```

## What To Notice And Why It Matters

The proof point is that agentic work stops at the right boundary. The assistant may draft pipeline and deployment assets, but the platform controls how software moves from source to runtime.

This matters because delivery shortcuts are one of the easiest ways for AI-assisted work to weaken enterprise controls. A governed pipeline makes acceleration compatible with traceability and rollback.

## How Red Hat And Open Source Make It Work

Red Hat OpenShift provides the application platform. Red Hat OpenShift Pipelines, based on Tekton, can provide Kubernetes-native CI/CD. Red Hat OpenShift GitOps can reconcile approved desired state from the app-local `gitops/` path. Red Hat Developer Hub can expose ownership, documentation, pipeline links, and service metadata.

OpenCode can help generate or review delivery assets, but it should not become an uncontrolled deployment mechanism.

## Red Hat Products Used

- **[Red Hat OpenShift Pipelines](https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/)** provides the Tekton-based pipeline path when enabled.
- **[Red Hat OpenShift GitOps](https://www.redhat.com/en/technologies/cloud-computing/openshift/gitops)** provides the desired-state deployment model.
- **[Red Hat Developer Hub](https://www.redhat.com/en/technologies/cloud-computing/developer-hub)** provides the future catalog and documentation surface.
- **[Red Hat OpenShift](https://www.redhat.com/en/technologies/cloud-computing/openshift)** provides the target application platform.

## Open Source Projects To Know

- [Tekton](https://tekton.dev/) provides cloud-native pipeline primitives.
- [Argo CD](https://argo-cd.readthedocs.io/) provides GitOps reconciliation patterns.
- [Backstage Software Templates](https://backstage.io/docs/features/software-templates/) provide the upstream scaffolding mechanism used by Developer Hub.
- [OpenCode](https://opencode.ai/) provides the agent workflow used to create and review delivery artifacts.

## TODOs

- TODO: Add static validation for the selected `.tekton/`, `Containerfile`, and app-local GitOps files.
- TODO: Add live PipelineRun validation only after the first application repository slice exists.
- TODO: Decide whether Developer Hub software templates or an authenticated MCP Gateway service become the source for pipeline templates.
- TODO: Add catalog and TechDocs links only after real resources exist.

## Deploy And Validate

This planned stage has no deploy or validate scripts. Static validation is documentation review only. Shared quality gates and evidence expectations live in [Developer Workflow Validation](../../docs/DEVELOPER_WORKFLOW_VALIDATION.md).

## References

- [Red Hat OpenShift Pipelines documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/)
- [Red Hat OpenShift GitOps documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_gitops/)
- [Designing Golden Paths](https://www.redhat.com/en/blog/designing-golden-paths)
- [How golden paths improve developer productivity](https://developers.redhat.com/articles/2025/01/29/how-golden-paths-improve-developer-productivity)
- [How to template AI software in Red Hat Developer Hub](https://developers.redhat.com/articles/2024/11/12/template-ai-software-red-hat-developer-hub)
- [Red Hat Developer Hub Software Templates Library](https://github.com/redhat-developer/red-hat-developer-hub-software-templates)
- [Quarkus target service options](../140-golden-path-quarkus-service/quarkus-target-service-options.md)
- [coolstore-inventory-service application repository plan](../140-golden-path-quarkus-service/coolstore-inventory-service-app-repo-plan.md)
- [Advanced authentication and authorization for MCP Gateway](https://developers.redhat.com/articles/2025/12/12/advanced-authentication-authorization-mcp-gateway)
- [Tekton](https://tekton.dev/)
- [Red Hat Developer Hub documentation](https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.9)

## Next Stage

[Stage 155: Red Hat Trusted Software Supply Chain](../155-red-hat-trusted-software-supply-chain/README.md) adds supply-chain evidence before the workflow shifts to modernization at scale.
