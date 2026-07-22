# Stage 080: Autonomous Application Migration

## Why This Matters

Most enterprises carry a backlog of legacy applications they cannot afford to migrate by hand — and cannot afford to send to an external AI service either. The question this stage answers is: how far can AI take application migration when it runs on governed, private infrastructure, and where must humans stay in the loop?

Stage 080 answers with two complementary paths on the same platform:

- **Assisted modernization (supported product path):** Migration Toolkit for Applications analyzes the portfolio with rules and static analysis; Red Hat Developer Lightspeed for MTA turns findings into focused, reviewable remediation suggestions through governed model access.
- **Autonomous migration (experimental agentic path):** a multi-agent workflow following the [MigIQ](https://github.com/sshaaf/migIQ) pattern takes a Spring Boot service end-to-end to Quarkus — graph-based code analysis, dependency-ordered planning, parallel execution, test generation, containerization, and OpenShift deployment — with a mandatory human review gate before anything merges, and every agent request metered through MaaS. MigIQ is an experimental community project (Claude-Code-first; OpenCode compatibility is pending a proving run). It is demonstrated as a pattern for multi-agent migration under platform governance, not as a supported product path.

The contrast is the message: analysis-grounded assistance is production-supported today; autonomous agents multiply throughput on well-understood migrations — and both run under the same identity, token limits, and telemetry.

## Architecture

## What This Stage Adds

This stage adds both migration paths on a single governed platform.

- Migration Toolkit for Applications 8.1 with MTA Hub, UI, and a ConsoleLink for the OpenShift launcher.
- Red Hat Developer Lightspeed for MTA (Technology Preview) with `kai_llm_proxy_enabled`, `kai_solution_server_enabled`, and `kai_llm_model: nemotron-3-nano-30b-a3b` configured in the Tackle CR.
- OpenShift OAuth federation through a `mta-keycloak` OAuthClient, RHBK realm `mta`, and pre-created demo users (`ai-admin` mapped to `tackle-admin`, `ai-developer` mapped to `tackle-migrator`) — configured by a PostSync hook Job.
- MaaS-backed LLM proxy credentials provisioned automatically: the `kai-api-keys` Secret uses the `mta-migration-models` subscription (key name `mta-kai-auto`), with the cluster-specific MaaS URL patched by a PostSync Job.
- An `agentic-migration` DevWorkspace that clones `adnan-drina/migiq-spring-boot-sample`, installs `@sshaaf/migiq@0.2.2`, and writes an elevated MaaS key to `~/.agentic-maas.env` — drawn from the `mta-migration-models` subscription (key name `agentic-migration`), sized for parallel-agent token bursts.

## What To Notice And Why It Matters

Stage 080 grounds AI assistance in modernization evidence.

- MTA provides findings from rules, static analysis, and application inventory — the migration starts with evidence, not a prompt.
- Developer Lightspeed for MTA uses that context to produce focused remediation suggestions through the private `nemotron-3-nano-30b-a3b` model on MaaS.
- The LLM proxy centralizes model access: developers do not manage provider credentials in the workspace, and every request flows through MaaS identity and rate-limit policies.
- The assisted path and the agentic path use the `mta-migration-models` MaaS subscription, so platform teams can size MTA token budgets independently from developer workspace and personal interactive subscriptions.
- The Coolstore sample for the assisted path is the external `konveyor-ecosystem/coolstore` repository — it is not imported by Stage 080 GitOps. The MTA VS Code extensions used in Dev Spaces are provisioned by Stage 060 workspace assets (`mca-coolstore` DevWorkspace), not by this stage.
- MaaS usage dashboards showing token consumption depend on Stage 040 observability — they are not configured by Stage 080.

This matters because enterprise modernization is a risk-managed engineering workflow. Generated remediation remains a proposal until application owners review the diff, tests, and evidence.

## How Red Hat And Open Source Make It Work

Migration Toolkit for Applications provides the modernization platform: analysis engine, inventory, rules, UI, and developer workflow integration. Red Hat Developer Lightspeed for MTA adds AI-assisted code resolution based on MTA findings and is documented as Technology Preview in MTA 8.1.

The MTA `Tackle` custom resource enables the LLM proxy and Solution Server. The `kai-api-keys` Secret holds MaaS-backed OpenAI-compatible credentials. Red Hat build of Keycloak provides the identity layer in a `mta` realm, and Red Hat OpenShift AI MaaS publishes the private model endpoint used by the assistant workflow. PostSync hook Jobs handle cluster-specific configuration: patching the MaaS URL, provisioning API keys, configuring the OpenShift identity provider in RHBK, and pre-creating demo users with correct role mappings.

## Trust Boundaries

Modernization context can include source code, static-analysis findings, dependency information, and remediation suggestions. The private MaaS path keeps this context inside OpenShift. Any approved external model path requires separate data-classification, provider, legal, and application-owner review.

The agentic path uses an elevated MaaS key (`mta-migration-models`) stored as a Kubernetes Secret and injected at workspace startup. This key grants higher token throughput than personal-tier keys; platform teams should review the subscription's rate-limit policy before production use.

## Red Hat Products Used

- **[Migration Toolkit for Applications](https://developers.redhat.com/products/mta)** provides modernization analysis, inventory, rules, and developer workflow integration.
- **[Red Hat Developer Lightspeed for MTA](https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.1/html/configuring_and_using_red_hat_developer_lightspeed_for_mta/)** adds AI-assisted code resolution (Technology Preview).
- **[Red Hat OpenShift AI](https://www.redhat.com/en/technologies/cloud-computing/openshift/openshift-ai)** provides the governed MaaS endpoint used by the MTA LLM proxy and the agentic workspace.
- **[Red Hat OpenShift Dev Spaces](https://www.redhat.com/en/technologies/cloud-computing/openshift/dev-spaces)** hosts the agentic migration workspace. The MTA VS Code extensions are provisioned in Stage 060 workspace assets.
- **[Red Hat build of Keycloak](https://access.redhat.com/products/red-hat-build-of-keycloak)** provides the identity layer used by MTA (realm `mta`, OAuthClient `mta-keycloak`).
- **[Red Hat OpenShift](https://www.redhat.com/en/technologies/cloud-computing/openshift)** provides runtime, identity integration, routes, storage, and operations.

## Open Source Projects To Know

- [Konveyor](https://www.konveyor.io/) is the upstream modernization community behind MTA.
- [Kantra](https://github.com/konveyor/kantra) provides CLI-based application analysis.
- [Kai](https://github.com/konveyor/kai) is the upstream AI-assisted modernization effort.
- [MigIQ](https://github.com/sshaaf/migIQ) is the experimental multi-agent migration pattern used in the agentic path.
- [Coolstore](https://github.com/konveyor-ecosystem/coolstore) is the Java EE sample application used in the assisted modernization path.

## Demo Script

### Part 0 — The entry point: MTA

**Know.** For this rung the entry point is MTA itself — the legacy estate
(`migiq-spring-boot-sample`, `konveyor-ecosystem/coolstore`) lives in MTA's
application inventory as source to analyze; it does not need to run on the
cluster. An RHDH golden-path template for self-service migration runs is
deferred until the MigIQ migration flow is settled (see BACKLOG).

### Part 1 — The supported path: analysis-grounded modernization

**Know.** Coolstore carries the classic enterprise backlog: a legacy Java EE application (`konveyor-ecosystem/coolstore`) that is expensive to maintain and impossible to staff. Manual migration quotes came back in engineer-years. The first answer is the supported product path: analysis before generation.

**Show.**
- Open MTA from the console launcher; log in with OpenShift (point out the Keycloak-federated identity — same SSO as everything else).
- Show the application inventory and the analysis report for coolstore: rules-based findings, effort estimates, migration issues by category.
- Open Developer Lightspeed for MTA on one finding: "the suggestion is grounded in this specific finding, and the model behind it is our private Nemotron — reached through the same governed MaaS gateway as every other AI call on this platform. Modernization context never leaves the cluster."

### Part 2 — The agentic path: end-to-end migration under governance

**Know.** Analysis-grounded assistance is production-ready today; the frontier is autonomous execution. The question enterprises actually ask is not "can agents migrate code?" but "what happens to control when they do?" This path is experimental — MigIQ is a community project, Claude-Code-first, with an OpenCode-compatibility proving run still pending.

**Show.**
- Walk the [agentic migration exercise](agentic-migration-exercise.md): MigIQ-pattern phases (graphify, plan, parallel execute, test-gen) on the per-run copy of the Spring Boot sample from Part 0, executed by MaaS-published models.
- While agents run, switch to the RHOAI Usage dashboard: "every one of those parallel agents is metered — this burst is drawing from an elevated subscription the platform team sized for exactly this workload."
- Stop at the human review gate: diff against the MTA findings; approve or reject. "Nothing merges on agent authority. Autonomy multiplied throughput; governance kept the control points."
- **Business value callout:** "The backlog conversation changes from 'engineer-years' to 'agent-hours plus review time' — without a single line of source leaving your platform."
- Push the approved migrated code to the repo's `main`: it exits through the
  same per-project pipeline pattern and SonarQube gate as every other rung.
  *Self-service in, trusted delivery out — even for agent-migrated legacy
  code.*

### Part 3 — Wrap-up: the whole arc, one platform

**Know.** This is the last rung. Walk the arc backwards so the audience sees
one platform, not a pile of tools.

**Show.**
- Return to Developer Hub: the catalog holds the brownfield entry point
  (`coolstore-inventory-service`, stage 060) plus every component this
  session created — the agentic scaffold and the migrated app — each one
  clicking through to its repo, its own namespace, and its pipeline runs.
- Open the RHOAI MaaS usage dashboard: the assisted developer's Kilo Code
  traffic, the agent bursts, the application's own LLM calls — every AI
  consumer on this platform is identified, metered, and governed by the same
  gateway.
- Close: "Assisted, agentic, autonomous — the maturity ladder changed how
  developers work. What never changed: every rung entered through the portal,
  exited through the pipeline, and reached models only through MaaS. That is
  the difference between adopting AI tools and running an AI development
  platform."

## Deploy And Validate

This is a workflow-only stage: it deploys no cluster resources of its own.
The MigIQ stack (MTA operator, Tackle, Developer Lightspeed/MaaS wiring, migration workspace) is owned by
[Stage 050: Advanced Application Platform](../050-advanced-app-platform/README.md)
(`migiq` component). Deploy stage 050 first, then validate this stage's
prerequisites read-only:

```bash
./stages/080-ai-autonomous-migration/validate.sh
```

Manifests: [`gitops/stages/050-advanced-app-platform/base/migiq/`](../../gitops/stages/050-advanced-app-platform/base/migiq/)

Flow dependency: Stages 040 and 050 (matching `flows/default.yaml` `dependsOn: [040, 050]`).

## References

| Topic | Link |
|-------|------|
| Coolstore sample application | https://github.com/konveyor-ecosystem/coolstore |
| MTA 8.1 documentation | https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.1/ |
| MTA 8.1 installation guide | https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.1/html-single/installing_the_migration_toolkit_for_applications/index |
| Red Hat Developer Lightspeed for MTA 8.1 | https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.1/html-single/configuring_and_using_red_hat_developer_lightspeed_for_mta/index |
| MTA VS Code extension 8.1 | https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.1/html-single/configuring_and_using_the_visual_studio_code_extension_for_mta/index |
| MaaS code assistant quickstart | https://docs.redhat.com/en/learn/ai-quickstarts/rh-maas-code-assistant |
| MigIQ multi-agent migration | https://github.com/sshaaf/migIQ |
| rhpds/mca-devspaces | https://github.com/rhpds/mca-devspaces |

## Next Stage

This is the final rung of the maturity ladder. The delivery proof for what
the agents built — pipelines, quality gates, provenance — lives in
[Stage 050: Advanced Application Platform](../050-advanced-app-platform/README.md),
which every rung of the ladder entered through and exited through.
