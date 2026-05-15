# Stage 140: Golden Path Quarkus Service

## Why This Matters

Enterprise developers rarely need a random code snippet in isolation. They need service structure, approved versions, dependency policy, tests, configuration, database access, frontend conventions, deployment metadata, and documentation that all fit the organization's standards.

This planned stage uses the controlled OpenCode workflow from Stage 130 to scaffold or extend a realistic Quarkus service from a golden-path contract. The task is intentionally larger than vibe coding, but still constrained by standards, software-template guidance, and review.

## Story Goal

Show that an agent can help create a service path without inventing the enterprise architecture. The output should follow approved Java and Quarkus versions, package naming, REST conventions, tests, health checks, configuration patterns, OpenShift deployment guidance, and the selected data/frontend standards.

## Platform Capabilities Consumed

- Stage 070 provides the Dev Spaces workspace.
- Stage 090 provides the future portal and golden path discovery surface.
- Stage 130 provides OpenCode agents, skills, project rules, and review patterns.

## What This Stage Adds

This planned stage adds the golden path application exercise.

- A golden-path contract that identifies the repository template, pipeline expectations, deployment manifests, observability defaults, and extension points.
- Enterprise Quarkus standards for package names, extensions, tests, health endpoints, OpenShift deployment settings, and supported Java versions. The first scaffold uses Red Hat build of Quarkus `3.27.x` with Java 21.
- Approved dependency and version guidance.
- PostgreSQL service integration through the OpenShift Developer Catalog / Red Hat PostgreSQL image path, with no committed credentials.
- Optional frontend standard when it supports the story.
- Reference output for a future hands-on exercise.

## Developer Workflow

### Starting Point

The developer has OpenCode running in Dev Spaces with an approved model path and project instructions loaded. The current target-service recommendation is a demo-owned Coolstore Inventory Quarkus service, captured in the [`Quarkus target service options`](quarkus-target-service-options.md) assessment.

The target service should be small and domain-aligned: inventory availability for Coolstore item IDs, with deterministic tests, health, metrics, PostgreSQL runtime configuration, and a clear OpenShift deployment path.

The service repository is `adnan-drina/coolstore-inventory-service`, documented in the [`coolstore-inventory-service` application repository plan](coolstore-inventory-service-app-repo-plan.md). It is a single service repository with Quarkus source at the root, app-local GitOps state under `gitops/`, Pipelines-as-Code assets under `.tekton/`, and rollout, promotion, and rollback evidence in repository documentation.

The new knowledge-base sources make the preferred direction clearer: this stage should not ask the agent to invent a service from scratch. It should give the agent a golden-path input packet that includes approved template references, Java and Quarkus versions, package naming, dependency policy, deployment style, and validation commands.

### AI-Assisted Task

Ask the agent to plan and then scaffold or extend a service with:

- REST endpoints;
- service and persistence layers;
- PostgreSQL-backed data access through the OpenShift Developer Catalog / Red Hat PostgreSQL image path;
- tests;
- health checks;
- OpenShift deployment configuration through app-local GitOps manifests and the selected Quarkus deployment path;
- documentation;
- optional frontend integration.

### Prompts Or Agent Instructions

Recommended initial instruction:

```text
Plan an enterprise-grade Quarkus service extension. Use approved versions and existing project conventions. Do not edit files until you identify the package structure, dependencies, tests, configuration, and validation commands.
```

Recommended golden-path instruction:

```text
Use the provided golden-path packet as the source of truth. Identify the repository template, pipeline expectation, deployment manifest pattern, observability defaults, and allowed extension points before proposing code changes.
```

Recommended implementation instruction after review:

```text
Implement the reviewed plan in the smallest useful slice. Keep credentials out of source, add tests for the changed behavior, and update documentation only for implemented behavior.
```

### Expected Developer Actions

- Provide the selected service name, package prefix, and business capability.
- Review the agent plan before edits.
- Confirm dependency versions, Quarkus extensions, and the Red Hat build of Quarkus `3.27.x` with Java 21 baseline.
- Confirm the chosen OpenShift deployment path: Developer Hub software template, Quarkus OpenShift extension, S2I, Docker build strategy, or app-local GitOps-managed manifests.
- Confirm PostgreSQL configuration does not commit secrets.
- Run the selected Maven and test commands.
- Review generated frontend code if the frontend path is included.

### Review And Quality Gates

- Maven build passes.
- Tests pass.
- Health endpoints exist where expected.
- Dependencies match approved versions.
- Package names and class names follow project conventions.
- Configuration uses environment, ConfigMap, Secret, or platform-provided resources instead of hard-coded credentials.
- Generated OpenShift resources follow the selected golden-path deployment pattern.
- Documentation matches implemented behavior.

### Evidence To Capture

- Approved standards used by the agent.
- Golden-path source packet or software-template reference.
- Generated plan.
- Files changed.
- Build and test results.
- Dependency review notes.
- Configuration and secret-handling review notes.

## What To Notice And Why It Matters

The proof point is that the agent can help with a realistic application slice while still operating under enterprise constraints. The value is not raw file generation. The value is the combination of planning, template-backed standards, scoped edits, validation, and reviewable evidence.

This matters because the enterprise risk is not that developers use AI. The risk is that AI output drifts away from supported versions, known patterns, and security boundaries. A golden path gives the assistant less room to improvise.

## How Red Hat And Open Source Make It Work

Red Hat OpenShift Dev Spaces provides the workspace where the service is created or extended. Red Hat Developer Hub can later publish the golden path through Software Templates, catalog the resulting component, and expose TechDocs for the service. Red Hat OpenShift provides the runtime and deployment foundation.

Red Hat and Quarkus sources now give this stage a stronger technical foundation. The Red Hat build of Quarkus positions Quarkus as Kubernetes-native Java for microservices and serverless applications, while the Quarkus OpenShift deployment guides provide concrete deployment paths such as one-step OpenShift deployment, Docker build strategy, and S2I.

The Red Hat golden-path sources also clarify how this stage should be framed: a golden path should include a repository template, a pipeline, deployment manifests, and observability defaults, while staying transparent and extensible. Developer Hub software templates are the portal mechanism that can turn those patterns into a developer-facing workflow.

## Trust Boundaries

Database credentials, software-template trust, and deployment configuration are the main trust boundaries in this stage. The agent must not hard-code secrets, invent unmanaged databases, pull from unreviewed templates, or bypass the approved platform path. Generated application code is still a proposal until it passes tests and human review.

## Red Hat Products Used

- **[Red Hat OpenShift Dev Spaces](https://www.redhat.com/en/technologies/cloud-computing/openshift/dev-spaces)** provides the workspace.
- **[Red Hat Developer Hub](https://www.redhat.com/en/technologies/cloud-computing/developer-hub)** can later publish the software template, golden path, TechDocs, and catalog metadata.
- **[Red Hat build of Quarkus](https://developers.redhat.com/products/quarkus)** provides the supported Quarkus product context for Kubernetes-native Java.
- **[Red Hat OpenShift](https://www.redhat.com/en/technologies/cloud-computing/openshift)** provides the target application platform.

## Open Source Projects To Know

- [Quarkus](https://quarkus.io/) provides the Java application framework.
- [PostgreSQL](https://www.postgresql.org/) provides the relational data tier.
- [PatternFly](https://www.patternfly.org/) provides the Red Hat-aligned frontend design system.
- [Backstage Software Templates](https://backstage.io/docs/features/software-templates/) provide the upstream scaffolding model used by Developer Hub.
- [OpenCode](https://opencode.ai/) provides the controlled agent workflow used to scaffold or extend the service.

## Future Implementation Notes

- Choose whether the demo creates a new service from a Developer Hub software template, extends an existing Java/Quarkus app, or uses a small reference service committed to this repo.
- Use the [`Quarkus target service options`](quarkus-target-service-options.md) assessment as the current baseline: create or seed a demo-owned `coolstore-inventory-service` rather than adopting the full Quarkus monolith branch.
- Use the [`coolstore-inventory-service` application repository plan](coolstore-inventory-service-app-repo-plan.md) as the repository baseline: keep Quarkus source, app-local GitOps, `.tekton/` Pipelines-as-Code assets, and deployment evidence in the same repository for the first demo.
- Use Red Hat build of Quarkus `3.27.x` with Java 21 as the approved first scaffold baseline.
- Use the OpenShift Developer Catalog / Red Hat PostgreSQL image path for the first live PostgreSQL demo, with any operator-backed database path deferred.
- Use Continue first for README, API, and test-plan alignment, then use OpenCode for the bounded `POST /api/inventory/{itemId}/reservations` feature task.
- Decide whether the frontend path is required for the first implementation or deferred. The KB still needs a project-specific frontend standard before making this mandatory.
- Choose the golden-path source packet: template reference, standards doc, deployment pattern, observability expectations, and validation commands.
- Add a reference implementation after the standards are agreed.

## Deploy And Validate

This planned workflow stage does not yet include deploy or validate scripts. Static validation for this iteration is documentation review only.

## References

- [Designing Golden Paths](https://www.redhat.com/en/blog/designing-golden-paths)
- [How golden paths improve developer productivity](https://developers.redhat.com/articles/2025/01/29/how-golden-paths-improve-developer-productivity)
- [Red Hat Developer Hub Software Templates Library](https://github.com/redhat-developer/red-hat-developer-hub-software-templates)
- [Red Hat build of Quarkus: Kubernetes-native Java](https://developers.redhat.com/products/quarkus)
- [What is Quarkus?](https://www.redhat.com/en/topics/cloud-native-apps/what-is-quarkus)
- [Deploying Quarkus applications to OpenShift in a single step](https://quarkus.io/guides/deploying-to-openshift-howto)
- [Using S2I to deploy Quarkus applications to OpenShift](https://quarkus.io/guides/deploying-to-openshift-s2i-howto)
- [PatternFly](https://www.patternfly.org/)
- [Red Hat Developer Hub documentation](https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.9)
- [OpenCode: A model-neutral AI coding assistant for OpenShift Dev Spaces](https://developers.redhat.com/articles/2026/04/22/opencode-model-neutral-ai-coding-assistant-openshift-dev-spaces)
- [Quarkus target service options](quarkus-target-service-options.md)
- [coolstore-inventory-service application repository plan](coolstore-inventory-service-app-repo-plan.md)

## Next Stage

[Stage 150: Governed Pipeline And Deployment](../150-governed-pipeline-and-deployment/README.md) moves from application generation to controlled build, test, and deployment flow.
