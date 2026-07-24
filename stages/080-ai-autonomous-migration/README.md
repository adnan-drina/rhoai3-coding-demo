# Stage 080: AI-Autonomous Migration with an Agent Harness

The previous stages built the ladder one rung at a time: stage 060 showed one-shot prompting and let the pipeline gate catch its flaws; stage 070 moved the standards into the project (constitution, AGENTS.md, skills, specs) so the agent built it right the first time. Both stages end with a human driving every cycle. This stage asks the next question: what has to be true for an agent to carry a whole-application migration largely on its own, and still deserve a human's approval at the end?

The answer this stage gives is not a bigger model or a longer prompt. It is an **AI Agent Harness**: the engineered layer of guides and sensors around the agent that steers it before it acts and corrects it after, so that by the time a human reviews the result, the obvious failures have already been caught and fixed by the harness itself. The concept and terminology come from [Harness Engineering for Coding Agents](https://martinfowler.com/articles/harness-engineering.html) on martinfowler.com; the parts of the harness come from the platform you have already built: MTA analysis as ground truth, spec-kit artifacts as steering context, OpenRewrite recipes and tests as deterministic checks, and the SonarQube-gated pipeline as the final sensor before deployment.

The message for platform teams: autonomy is not a property of the agent, it is a property of the system around the agent. Everything this stage assembles into a harness is a governed platform capability you already operate.

## Why This Matters

Most enterprises carry a backlog of legacy applications they cannot afford to migrate by hand — and cannot afford to send to an external AI service either. The question this stage answers is: how far can AI take application migration when it runs on governed, private infrastructure, and where must humans stay in the loop?

Stage 080 answers with two complementary paths on the same platform:

- **Assisted modernization (supported product path):** Migration Toolkit for Applications analyzes the portfolio with rules and static analysis; Red Hat Developer Lightspeed for MTA turns findings into focused, reviewable remediation suggestions through governed model access.
- **Autonomous migration (harness-governed agentic path):** an agent workflow takes a legacy service end-to-end to Quarkus — analysis-grounded planning, spec generation, code generation with self-evaluation loops that iterate until the quality bar is met — with a mandatory human review gate before anything merges, and every agent request metered through MaaS.

The contrast is the message: analysis-grounded assistance is production-supported today; harness-governed agents multiply throughput on well-understood migrations — and both run under the same identity, token limits, and telemetry.

## What You'll Do

You will **provision** a migration workspace through a golden-path template that, unlike stage 070's greenfield scaffold, takes the **Git repository of the legacy application you want to migrate** as input and delivers a Dev Spaces workspace with the MTA tools and migration standards preconfigured, **analyze** the legacy code with MTA so the findings become the migration's ground truth, **understand the harness** that will govern the agent (guides that steer, sensors that catch, humans that judge), **generate the migration spec** with spec-kit from the MTA findings and the code itself, **let the agent migrate** the service under the harness — generating code, running the sensors, and self-correcting until the checks pass — **review** the result against the analysis findings at the mandatory human gate, and **ship it**: CI pipeline, SonarQube quality gate, deployment on OpenShift, with the full token cost of autonomy visible on the platform's usage dashboard.

> **Exercise status:** this README defines the target workflow for the stage. The implementation plan (template, workspace wiring, harness assets) is being drafted step by step; see `BACKLOG.md`.

---

## Step 1: Sign in to Developer Hub

1. Open the Developer Hub URL and sign in as `ai-developer` (OpenShift OIDC).

**What you should see:** the RHDH home screen with the catalog search bar.

---

## Step 2: Create your migration project from the template

Stage 070's template scaffolded a greenfield service from nothing. The migration template inverts the input: you bring an existing codebase.

1. Open **Self-service** and choose the **Application migration** template.
2. Provide the input the template asks for:
   - **Legacy repository URL**: the Git repository of the application to migrate. The demo uses the platform's legacy Coolstore monolith — the same brownfield code MTA has been pointed at since stage 050.
   - **Project name**: becomes the per-run repository, namespace, and workspace name, exactly like stage 070.
3. Create, and watch the template run: copy the legacy source into a per-run repository → register the component in the catalog → provision the namespace and pipeline → prepare the Dev Spaces workspace with the MTA extension, the migration skills, and governed model access preconfigured.

**What you should see:** a new catalog component for the migration project, with links to the source repository, Dev Spaces, and SonarQube — the same self-service pattern as stage 070, now wrapped around code that already exists.

> **Why this matters:** migration is where self-service pays off most. Nobody hand-wires analysis tooling, workspaces, and pipelines for every one of hundreds of legacy services. The template makes "start migrating this repo" a ten-second operation with every tool pre-approved by the platform team.

---

## Step 3: Analyze the legacy code with MTA

Before any agent writes a line, the supported product establishes the facts.

1. Open the workspace from the component page. The legacy source is cloned; the MTA extension is connected to the platform's MTA hub out of the box.
2. Run an MTA analysis against the Quarkus migration target and open the report.
3. Review the findings: mandatory issues, effort estimates, and the specific files and patterns that must change. Where Developer Lightspeed is available, inspect its suggested resolutions for a sample of findings.
4. Keep the report open. From this point on, the analysis is the **checklist the agentic result must satisfy** — the migration is done when the findings are resolved, not when the agent says so.

**What you should see:** an analysis report enumerating concrete migration issues in the legacy code, each anchored to files and rules.

---

## Step 4: The concept — an AI Agent Harness

Stage 070 introduced two kinds of agent context: the memory bank and specs. This stage adds the third idea, from Birgitta Böckeler's [Harness Engineering for Coding Agents](https://martinfowler.com/articles/harness-engineering.html): **Agent = Model + Harness**. The model is fixed; the harness is everything the platform engineers around it, and it comes in two kinds:

- **Guides (feedforward):** steer the agent *before* it acts — standards, rules, specs, architectural constraints.
- **Sensors (feedback):** catch problems *after* it acts and feed them back so the agent can self-correct — builds, tests, linters, analyzers, review agents.

Each kind exists in two execution forms: **computational** (deterministic and fast: compilers, tests, recipes, static analysis) and **inferential** (semantic, model-driven: an agent reviewing another agent's diff). Fast, cheap sensors run early and often inside the loop; expensive ones guard the exit.

Everything this platform already operates maps onto that picture:

| Harness part | Kind | Platform asset |
|--------------|------|----------------|
| Migration standards, AGENTS.md, skills | Guide | Stage 070 memory-bank assets, extended with migration skills |
| Migration spec, plan, tasks | Guide | spec-kit artifacts generated in Step 5 |
| MTA analysis findings | Sensor (computational) | The Step 3 report, re-run to verify findings are resolved |
| OpenRewrite recipes | Guide + Sensor | Deterministic transforms for the mechanical share of the migration |
| Build + tests | Sensor (computational) | Maven build and the test suite in the workspace |
| Self-review / evaluation pass | Sensor (inferential) | The agent's harness-defined reflection step in Step 6 |
| SonarQube quality gate | Sensor (computational) | The same fail-on-new-issue gate as stages 060/070 |
| Human review | Judgment | Step 7 — the part no harness externalizes |

Two things follow. First, the loop inverts: in stage 060 *you* read the SonarQube report and prompted the fix; here the harness feeds sensor output back to the agent, which iterates until the checks pass — quality shifts from inspection to regulation. Second, humans move up a level: instead of reviewing every intermediate step, you review the outcome and **improve the harness** when something slips through — Böckeler calls this the steering loop, and it is the stage 070 "skills retro" practice graduated into a system.

---

## Step 5: Generate the migration spec

The MTA findings say what must change; the spec says what the migrated service must be.

1. Run the spec-kit cycle (`/speckit.specify` → `/speckit.plan` → `/speckit.tasks`) with the MTA analysis and the legacy code as input: the spec captures the service's observed behavior and API contract, the plan maps findings to Quarkus-native equivalents, and the tasks order the work.
2. Where findings are mechanical (dependency swaps, annotation replacement, import rewrites), the plan delegates to **OpenRewrite** recipes rather than model inference — deterministic transforms are cheaper, faster, and always correct, so the agent's inference budget is spent only where judgment is needed.
3. **Review each artifact before the next step amplifies it**, exactly as in stage 070. The spec is the contract the harness will hold the agent to.

**What you should see:** spec, plan, and tasks in the repository, traceable line-by-line to MTA findings and observed behavior.

---

## Step 6: Migrate under the harness

1. Start the implementation run. The agent works through the tasks: applying OpenRewrite recipes for the mechanical transforms, generating Quarkus-native code and tests for the rest.
2. This is where the harness earns its name — after each meaningful change the sensors run, and the loop is part of the workflow, not a favor you ask:
   - build and tests must pass;
   - the evaluation pass reviews the change against the spec and the migration standards;
   - sensor failures go back to the agent, which corrects and re-runs — iterating until the quality bar is met or the iteration budget is exhausted.
3. Watch the loop rather than driving it. Your job in this step is observation: where the agent needed multiple iterations is exactly where the harness (or the spec) needs improving.

**What you should see:** the agent converging on a migrated service with passing checks — and a visible record of what the sensors caught that never reached you.

> **Honesty beat:** autonomy is token-hungry. Every iteration of the loop is metered through the developer's MaaS key; Step 8 shows the bill. That cost profile is why token limits exist and why deterministic transforms carry the mechanical share of the work.

---

## Step 7: The human review gate

Nothing merges on agent authority.

1. Re-run the MTA analysis on the migrated code: the Step 3 findings should be resolved.
2. Review the final diff against the spec and the analysis report; reject or re-run phases where the result falls short.
3. Approve and merge when the evidence — not the agent's summary — says the migration is complete.

**What you should see:** a reviewable, evidence-backed migration: analysis clean, tests green, spec satisfied.

---

## Step 8: Ship it and show the cost

1. Push. The project's pipeline runs clone → build → SonarQube gate → image build/push, the same exit every stage uses.
2. Deploy the migrated service on OpenShift and verify the running endpoints against the spec's behavioral contract.
3. Open the Stage 040 MaaS usage dashboard: the token consumption of the full autonomous run, attributed to the developer's key, per model, next to the interactive stages' usage.

**What you should see:** the migrated service running on OpenShift, a green pipeline, and the complete, attributed cost of autonomy on the platform dashboard.

---

## Wrap-up

### What you proved

- **Analysis grounds autonomy:** MTA's findings, not the agent's self-assessment, defined done.
- **The harness regulates quality:** guides steered generation, sensors caught and fed back failures, and the agent iterated to green before a human ever looked.
- **Determinism where possible, inference where needed:** OpenRewrite carried the mechanical transforms; the model spent its budget on judgment calls.
- **Humans judge outcomes and improve the system:** the review gate stayed mandatory, and every harness gap found becomes the next harness improvement.
- **Governance held at full autonomy:** same identity, token limits, and telemetry as every previous stage — just more visible, because agents consume more.

## Red Hat Products Used

- **[Migration Toolkit for Applications](https://developers.redhat.com/products/mta)** provides modernization analysis, inventory, rules, and developer workflow integration.
- **[Red Hat Developer Lightspeed for MTA](https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.1/html/configuring_and_using_red_hat_developer_lightspeed_for_mta/)** adds AI-assisted code resolution (Technology Preview).
- **[Red Hat Developer Hub](https://developers.redhat.com/rhdh)** provides the developer portal and the migration golden-path template.
- **[Red Hat OpenShift Dev Spaces](https://www.redhat.com/en/technologies/cloud-computing/openshift/dev-spaces)** hosts the migration workspace.
- **[Red Hat OpenShift AI](https://www.redhat.com/en/technologies/cloud-computing/openshift/openshift-ai)** provides the governed MaaS endpoints the analysis tooling and the agent consume.
- **[Red Hat OpenShift Pipelines](https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/)** runs the exit pipeline with the SonarQube quality gate.
- **[Red Hat build of Keycloak](https://access.redhat.com/products/red-hat-build-of-keycloak)** provides the identity layer used by MTA.
- **[Red Hat OpenShift](https://www.redhat.com/en/technologies/cloud-computing/openshift)** provides runtime, identity integration, routes, storage, and operations.

## Open Source Projects To Know

- [Konveyor](https://www.konveyor.io/) is the upstream modernization community behind MTA.
- [Kantra](https://github.com/konveyor/kantra) provides CLI-based application analysis.
- [Kai](https://github.com/konveyor/kai) is the upstream AI-assisted modernization effort behind Developer Lightspeed for MTA.
- [OpenRewrite](https://github.com/openrewrite/rewrite) provides deterministic, recipe-driven code transformation.
- [spec-kit](https://github.com/github/spec-kit) is the spec-driven development toolkit carried over from stage 070.
- [OpenCode](https://opencode.ai/) is the AI coding agent the harness governs.
- [Coolstore](https://github.com/konveyor-ecosystem/coolstore) is the legacy sample application used as the migration target.

## References

| Resource | Link |
|----------|------|
| Harness Engineering for Coding Agents | https://martinfowler.com/articles/harness-engineering.html |
| MTA 8.1 documentation | https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.1/ |
| OpenRewrite documentation | https://docs.openrewrite.org/ |
| spec-kit — spec-driven.md | https://github.com/github/spec-kit/blob/main/spec-driven.md |
| MaaS code assistant quickstart | https://docs.redhat.com/en/learn/ai-quickstarts/rh-maas-code-assistant |
