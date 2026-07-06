# Stage 070: Autonomous Application Migration

## Why This Matters

Most enterprises carry a backlog of legacy applications they cannot afford to migrate by hand — and cannot afford to send to an external AI service either. The question this stage answers is: how far can AI take application migration when it runs on governed, private infrastructure, and where must humans stay in the loop?

Stage 070 answers it with two complementary paths on the same platform:

- **Assisted modernization (supported product path):** Migration Toolkit for Applications (MTA) analyzes the portfolio with rules and static analysis; Red Hat Developer Lightspeed for MTA turns findings into focused, reviewable remediation suggestions through governed model access.
- **Autonomous migration (agentic path):** a multi-agent workflow (following the experimental [MigIQ](https://github.com/sshaaf/migIQ) pattern) takes a Spring Boot service end-to-end to Quarkus: graph-based code analysis, dependency-ordered planning, parallel execution, test generation, containerization, and OpenShift deployment — with a mandatory human review gate before anything merges, and every agent request metered through MaaS.

The contrast is the message: analysis-grounded assistance is production-supported today; autonomous agents multiply throughput on the well-understood migrations — and both run under the same identity, token limits, and telemetry.

## Architecture

![Stage 070 layered capability map](../../docs/assets/architecture/stage-070-capability-map.svg)

## What This Stage Adds

This stage adds both migration paths.

Assisted modernization (deployed by this stage):

- Migration Toolkit for Applications 8.1 with MTA Hub and UI.
- Red Hat Developer Lightspeed for MTA services for AI-assisted remediation suggestions.
- A centrally managed LLM proxy path that sends model requests through MaaS.
- OpenShift OAuth federation through the MTA Keycloak / Red Hat build of Keycloak identity path.
- Red Hat OpenShift Dev Spaces integration through the MTA VS Code extension.

Autonomous migration (workspace workflow, see the
[agentic migration exercise](agentic-migration-exercise.md)):

- The MigIQ skill set (pinned npm package `@sshaaf/migiq@0.2.2`, experimental) installed into the Dev Spaces workspace.
- Multi-agent Spring Boot to Quarkus migration driven by MaaS-published models: `qwen3-6-35b-a3b` as the execution model and `nemotron-3-nano-30b-a3b` for long-context planning.
- A human review gate between planning/execution and merge, consistent with the review discipline from Stages 050 and 060.
- Agent token consumption visible on the Stage 040 MaaS usage dashboards — governance of autonomous workloads is part of the demo, not an afterthought.

The assisted-path sample is [konveyor-ecosystem/coolstore](https://github.com/konveyor-ecosystem/coolstore) (`main` = legacy Java EE starting point, `quarkus` = completed reference). The autonomous-path sample is the Spring Boot service from the MigIQ examples; the exercise document tracks its workspace wiring.

## What To Notice And Why It Matters

Stage 070 grounds AI assistance in modernization evidence.

- MTA provides findings from rules, static analysis, and application inventory.
- Developer Lightspeed for MTA uses that context for focused remediation suggestions.
- The LLM proxy centralizes model access so developers do not manage provider credentials in the workspace.
- The primary path sends modernization context through MaaS to a private model on OpenShift.

This matters because enterprise modernization is a risk-managed engineering workflow. Generated remediation remains a proposal until application owners review the diff, tests, and evidence.

## How Red Hat And Open Source Make It Work

Migration Toolkit for Applications provides the modernization platform: analysis engine, inventory, rules, UI, and developer workflow integration. Red Hat Developer Lightspeed for MTA adds AI-assisted code resolution based on MTA findings and is documented as Technology Preview in MTA 8.1.

The MTA `Tackle` custom resource enables the LLM proxy and Solution Server. The `kai-api-keys` Secret holds MaaS-backed OpenAI-compatible credentials. Red Hat build of Keycloak participates in the MTA identity path, and Red Hat OpenShift AI MaaS publishes the private model endpoint used by the assistant workflow.

## Trust Boundaries

Modernization context can include source code, static-analysis findings, dependency information, and remediation suggestions. The private MaaS path keeps this context inside OpenShift. Any approved external model path requires separate data-classification, provider, legal, and application-owner review.

## Red Hat Products Used

- **[Migration Toolkit for Applications](https://developers.redhat.com/products/mta)** provides modernization analysis, inventory, rules, and developer workflow integration.
- **[Red Hat Developer Lightspeed for MTA](https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.1/html/configuring_and_using_red_hat_developer_lightspeed_for_mta/)** adds AI-assisted code resolution.
- **[Red Hat OpenShift AI](https://www.redhat.com/en/technologies/cloud-computing/openshift/openshift-ai)** provides the governed MaaS endpoint used by the MTA LLM proxy.
- **[Red Hat OpenShift Dev Spaces](https://www.redhat.com/en/technologies/cloud-computing/openshift/dev-spaces)** hosts the developer workspace and MTA VS Code extension.
- **[Red Hat build of Keycloak](https://access.redhat.com/products/red-hat-build-of-keycloak)** provides the identity layer used by MTA.
- **[Red Hat OpenShift](https://www.redhat.com/en/technologies/cloud-computing/openshift)** provides runtime, identity integration, routes, storage, and operations.

## Open Source Projects To Know

- [Konveyor](https://www.konveyor.io/) is the upstream modernization community behind MTA.
- [Kantra](https://github.com/konveyor/kantra) provides CLI-based application analysis.
- [Kai](https://github.com/konveyor/kai) is the upstream AI-assisted modernization effort.
- [Coolstore](https://github.com/konveyor-ecosystem/coolstore) is the Java EE sample application used in this stage.

## Demo Script

### Part 1 — The supported path: analysis-grounded modernization

**Know.** Coolstore carries the classic enterprise backlog: a legacy Java EE
application (`konveyor-ecosystem/coolstore`) that is expensive to maintain
and impossible to staff. Manual migration quotes came back in
engineer-years. The first answer is the supported product path: analysis
before generation.

**Show.**
- Open MTA from the console launcher; log in with OpenShift (point out the
  Keycloak-federated identity — same SSO as everything else).
- Show the application inventory and the analysis report for coolstore:
  rules-based findings, effort estimates, migration issues by category.
- Open Developer Lightspeed for MTA on one finding: "the suggestion is
  grounded in this specific finding, and the model behind it is our private
  Nemotron — reached through the same governed MaaS gateway as every other
  AI call on this platform. Modernization context never leaves the cluster."

### Part 2 — The agentic path: end-to-end migration under governance

**Know.** Analysis-grounded assistance is production-ready today; the
frontier is autonomous execution. The question enterprises actually ask is
not "can agents migrate code?" but "what happens to control when they do?"

**Show.**
- Walk the [agentic migration exercise](agentic-migration-exercise.md):
  MigIQ-pattern phases (graphify → plan → parallel execute → test-gen) on
  the Spring Boot sample, executed by MaaS-published models.
- While agents run, switch to the RHOAI Usage dashboard: "every one of
  those parallel agents is metered — this burst is drawing from an elevated
  subscription the platform team sized for exactly this workload."
- Stop at the human review gate: diff against the MTA findings; approve or
  reject. "Nothing merges on agent authority. Autonomy multiplied
  throughput; governance kept the control points."
- **Business value callout:** "The backlog conversation changes from
  'engineer-years' to 'agent-hours plus review time' — without a single
  line of source leaving your platform."

## Deploy And Validate

```bash
./stages/070-ai-autonomous-migration/deploy.sh
./stages/070-ai-autonomous-migration/validate.sh
```

Manifests: [`gitops/stages/070-ai-autonomous-migration/base/`](../../gitops/stages/070-ai-autonomous-migration/base/)

## References

- [Coolstore sample application](https://github.com/konveyor-ecosystem/coolstore)
- [MTA 8.1 documentation](https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.1/)
- [MTA 8.1 installation guide](https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.1/html-single/installing_the_migration_toolkit_for_applications/index)
- [Red Hat Developer Lightspeed for MTA 8.1](https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.1/html-single/configuring_and_using_red_hat_developer_lightspeed_for_mta/index)
- [MTA VS Code extension 8.1](https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.1/html-single/configuring_and_using_the_visual_studio_code_extension_for_mta/index)
- [MaaS code assistant quickstart](https://docs.redhat.com/en/learn/ai-quickstarts/rh-maas-code-assistant)
- [rhpds/mca-devspaces](https://github.com/rhpds/mca-devspaces)

## Next Stage

[Stage 080: AI in Trusted Delivery](../080-ai-trusted-delivery/README.md) proves what the agents built: provenance, signatures, and SBOMs for AI-generated changes.
