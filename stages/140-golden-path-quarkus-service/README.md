# Stage 140: Golden Path Quarkus Service

## Status

This is a planned developer workflow stage. It is not part of [`../../flows/default.yaml`](../../flows/default.yaml) and does not include deploy scripts, validate scripts, GitOps manifests, or an Argo CD Application.

## Why This Matters

Enterprise developers need more than isolated code snippets. They need supported versions, service structure, dependency policy, tests, configuration, database access, deployment metadata, and documentation that match organizational standards.

Stage 140 applies the controlled OpenCode workflow from Stage 130 to a realistic Quarkus service. The point is not for an agent to invent an architecture. The point is for the agent to work from a golden-path contract.

## What This Stage Adds

This planned stage adds the first service-building scenario.

- A demo-owned `coolstore-inventory-service` target.
- A golden-path input packet with approved Java, Quarkus, package, dependency, testing, deployment, and documentation expectations.
- A small inventory availability domain aligned to Coolstore item IDs.
- App-local GitOps and Pipelines-as-Code as the intended repository structure.
- Reviewable agent planning before implementation.

The current repository baseline is described in:

- [`quarkus-target-service-options.md`](quarkus-target-service-options.md)
- [`coolstore-inventory-service-app-repo-plan.md`](coolstore-inventory-service-app-repo-plan.md)

## Platform Capabilities Consumed

- Stage 070 provides the Dev Spaces workspace.
- Stage 090 provides the future portal and golden path discovery surface.
- Stage 130 provides OpenCode agents, skills, rules, and review patterns.

## Developer Workflow

The developer uses OpenCode in the `coolstore-inventory-service` workspace. The agent must plan first, then implement only a reviewed slice.

The first service target should include:

- REST endpoints for inventory availability and reservation behavior;
- service and persistence layers;
- PostgreSQL runtime configuration using platform-provided resources;
- tests;
- health checks;
- app-local GitOps desired state;
- documentation for implemented behavior only.

The preferred baseline is Red Hat build of Quarkus `3.27.x` with Java 21. The first live database path should use the OpenShift Developer Catalog / Red Hat PostgreSQL image path; operator-backed database choices are deferred.

## Starter Prompts

```text
Plan an enterprise-grade Quarkus service extension. Use approved versions and existing project conventions. Do not edit files until you identify the package structure, dependencies, tests, configuration, and validation commands.
```

```text
Use the provided golden-path packet as the source of truth. Identify the repository template, pipeline expectation, deployment manifest pattern, observability defaults, and allowed extension points before proposing code changes.
```

```text
Implement the reviewed plan in the smallest useful slice. Keep credentials out of source, add tests for the changed behavior, and update documentation only for implemented behavior.
```

## What To Notice And Why It Matters

The proof point is that an agent can help with a realistic application slice while staying inside enterprise constraints. The value is planning, template-backed standards, scoped edits, validation, and reviewable evidence.

This matters because AI-generated service code can easily drift from supported versions, known patterns, and security boundaries. A golden path gives the assistant less room to improvise.

## How Red Hat And Open Source Make It Work

Red Hat OpenShift Dev Spaces provides the workspace. Red Hat build of Quarkus provides the supported Kubernetes-native Java baseline. Red Hat Developer Hub can later publish the golden path through Software Templates, catalog metadata, and TechDocs. Red Hat OpenShift provides the target runtime.

Quarkus, PostgreSQL, PatternFly, Backstage Software Templates, and OpenCode supply the framework, data, UI, scaffolding, and agent tooling pieces.

## Red Hat Products Used

- **[Red Hat OpenShift Dev Spaces](https://www.redhat.com/en/technologies/cloud-computing/openshift/dev-spaces)** provides the workspace.
- **[Red Hat Developer Hub](https://www.redhat.com/en/technologies/cloud-computing/developer-hub)** can later publish the software template, golden path, TechDocs, and catalog metadata.
- **[Red Hat build of Quarkus](https://developers.redhat.com/products/quarkus)** provides the supported Quarkus product context.
- **[Red Hat OpenShift](https://www.redhat.com/en/technologies/cloud-computing/openshift)** provides the application platform.

## Open Source Projects To Know

- [Quarkus](https://quarkus.io/) provides the Java application framework.
- [PostgreSQL](https://www.postgresql.org/) provides the relational data tier.
- [PatternFly](https://www.patternfly.org/) provides the Red Hat-aligned frontend design system.
- [Backstage Software Templates](https://backstage.io/docs/features/software-templates/) provide the upstream scaffolding model used by Developer Hub.
- [OpenCode](https://opencode.ai/) provides the controlled agent workflow.

## TODOs

- TODO: Finalize the golden-path source packet: template reference, standards doc, deployment pattern, observability expectations, and validation commands.
- TODO: Add a reference implementation after standards are agreed.
- TODO: Decide whether frontend integration is required for the first implementation or deferred.
- TODO: Add live validation only after a real service repository and deployment path exist.

## Deploy And Validate

This planned stage has no deploy or validate scripts. Static validation is documentation review only. Shared quality gates and evidence expectations live in [Developer Workflow Validation](../../docs/DEVELOPER_WORKFLOW_VALIDATION.md).

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
