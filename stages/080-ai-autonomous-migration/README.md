# Stage 080 — Autonomous Spring Boot to Quarkus Migration

## Why This Matters

Most enterprises carry a backlog of legacy applications they cannot afford to migrate by hand — and cannot afford to send to an external AI service either. The question this stage answers is: how far can AI take application migration when it runs on governed, private infrastructure, and where must humans stay in the loop?

Stage 080 answers with two complementary paths on the same platform:

- **Assisted modernization (supported product path):** Migration Toolkit for Applications analyzes the portfolio with rules and static analysis; Red Hat Developer Lightspeed for MTA turns findings into focused, reviewable remediation suggestions through governed model access.
- **Autonomous migration (experimental agentic path):** a multi-agent workflow following the [MigIQ](https://github.com/sshaaf/migIQ) pattern takes a Spring Boot service end-to-end to Quarkus — graph-based code analysis, dependency-ordered planning, parallel execution, test generation, containerization, and OpenShift deployment — with a mandatory human review gate before anything merges, and every agent request metered through MaaS.

The contrast is the message: analysis-grounded assistance is production-supported today; autonomous agents multiply throughput on well-understood migrations — and both run under the same identity, token limits, and telemetry.

> **Status:** design complete, pending the OpenCode-compatibility proving run in Dev Spaces (see BACKLOG "Stage 080 agentic migration provenance"). MigIQ is an experimental community project (`@sshaaf/migiq`, pinned to `0.2.2`), demonstrated here as a pattern for multi-agent migration under platform governance — it is not a supported Red Hat product.

## The Story

Stages 050 and 060 scaled AI assistance from one-shot prompts to skill-guided tasks. This exercise scales it again: a whole-application migration executed by cooperating agents — analysis, planning, parallel execution, test generation, containerization, deployment — while the platform keeps every model call identified, rate-limited, and measured, and a human approves the result before it merges.

## Workflow

1. **Open the migration workspace** (Dev Spaces). The workspace clones the Spring Boot sample service (from the MigIQ examples) and has Kilo Code installed (no `.opencode/` directory). The agentic path uses MigIQ/Claude Code in the terminal with an elevated `maas-agentic-migration-key` from the `mta-migration-models` subscription (not Stage 060 devspace keys).
2. **Install the pinned MigIQ skill set** into the workspace project:

   ```bash
   npx @sshaaf/migiq@0.2.2
   ```

   This lays down the `migiq` orchestrator and the `mig-*` skills (`graphify`, `plan`, `execute`, `test-gen`, `containerize`, `deploy`).
3. **Ground with MTA first (recommended):** run an MTA analysis of the sample app and keep the report open — the supported product's findings are the checklist the agentic result must satisfy.
4. **Run the orchestrated migration** with the agent (`/migiq` interactive mode for demos; approve each phase):
   - graphify: knowledge-graph analysis of entities, dependencies, clusters;
   - plan: dependency-ordered tasks (expect ~100+ subtasks);
   - execute: parallel sub-agents apply Spring→Quarkus transformations;
   - test-gen: unit tests for migrated code.
5. **Human review gate (mandatory):** review the diff against the MTA findings and project standards; reject or re-run phases as needed. Nothing merges on agent authority.
6. **Containerize and deploy** to OpenShift; verify the running service.
7. **Show the governance evidence:** the Stage 040 MaaS usage dashboard during the run — per-model token consumption of an autonomous multi-agent workload, attributable to the developer's MaaS key.

## Model Routing

| Role | Model | Why |
|------|-------|-----|
| Execution agents | `qwen3-6-35b-a3b` | strong coding model, tool calling, 32K context |
| Planning / graph context | `nemotron-3-nano-30b-a3b` | 131K context for repository-scale analysis |

Both are private models on the platform; prompts and source code never leave the OpenShift boundary. Expect a token-heavy run — that is part of the demo's honesty about what autonomy costs and why token limits exist.

## Open Items Before This Exercise Is Demo-Ready

- [ ] Proving run: MigIQ skills under OpenCode (project is Claude-Code-first; `.opencode/skills` compatibility must be verified in Dev Spaces).
- [x] Workspace wiring: DONE — the `agentic-migration` DevWorkspace clones `adnan-drina/migiq-spring-boot-sample`, installs `@sshaaf/migiq@0.2.2` into `.claude/` on postStart, and the init command writes the elevated MaaS key to `~/.agentic-maas.env` (source it before agent runs; key drawn from `mta-migration-models`, model access via the MTA migration MaaSAuthPolicy).
- [ ] Model behavior: confirm the qwen tool-call parser handles MigIQ's structured prompts; fall back to nemotron as executor if needed.
- [ ] Evidence capture: scripted before/after test + MaaS usage screenshots for the stage README.

## Red Hat Products Used

- **[Migration Toolkit for Applications](https://developers.redhat.com/products/mta)** provides modernization analysis, inventory, rules, and developer workflow integration.
- **[Red Hat Developer Lightspeed for MTA](https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.1/html/configuring_and_using_red_hat_developer_lightspeed_for_mta/)** adds AI-assisted code resolution (Technology Preview).
- **[Red Hat OpenShift AI](https://www.redhat.com/en/technologies/cloud-computing/openshift/openshift-ai)** provides the governed MaaS endpoint used by the MTA LLM proxy and the agentic workspace.
- **[Red Hat OpenShift Dev Spaces](https://www.redhat.com/en/technologies/cloud-computing/openshift/dev-spaces)** hosts the agentic migration workspace.
- **[Red Hat build of Keycloak](https://access.redhat.com/products/red-hat-build-of-keycloak)** provides the identity layer used by MTA.
- **[Red Hat OpenShift](https://www.redhat.com/en/technologies/cloud-computing/openshift)** provides runtime, identity integration, routes, storage, and operations.

## Open Source Projects To Know

- [Konveyor](https://www.konveyor.io/) is the upstream modernization community behind MTA.
- [Kantra](https://github.com/konveyor/kantra) provides CLI-based application analysis.
- [Kai](https://github.com/konveyor/kai) is the upstream AI-assisted modernization effort.
- [MigIQ](https://github.com/sshaaf/migIQ) is the experimental multi-agent migration pattern used in the agentic path.
- [Coolstore](https://github.com/konveyor-ecosystem/coolstore) is the Java EE sample application used in the assisted modernization path.

## References

| Resource | Link |
|----------|------|
| MTA 8.1 documentation | https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.1/ |
| MaaS code assistant quickstart | https://docs.redhat.com/en/learn/ai-quickstarts/rh-maas-code-assistant |
