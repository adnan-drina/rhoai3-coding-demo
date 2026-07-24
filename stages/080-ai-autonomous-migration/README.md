# Stage 080: AI-Autonomous Migration with an Agent Harness

The previous stages built the AI maturity ladder one rung at a time, and both stages end with a human driving every cycle. This stage asks the next question: what has to be true for an agent to carry a whole-application migration largely on its own?

Legacy applications are not just expensive to maintain. They are an expanding attack surface. AI-powered exploit tools lower the cost of finding and weaponizing vulnerabilities in outdated frameworks, and regulations are catching up: the EU Cyber Resilience Act makes vendors accountable for the security posture of every product they ship, including the libraries and runtimes underneath it. The migration backlog is no longer a cost problem alone; it is a compliance and security deadline that most teams cannot meet with manual effort.

This demo stage answers with two complementary paths on the same governed platform: assisted modernization through Migration Toolkit for Applications turning a legacy codebase into an inventory of concrete, prioritized migration issues, and autonomous migration where an agent harness takes a legacy service end-to-end to Quarkus with analysis-grounded planning, spec generation, self-evaluation loops, and a trusted software supply chain pipeline that enforces quality and security before anything merges.

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
3. Create, and watch the template run: fetch the migration scaffold → stamp the legacy URL into the workspace definition and `migration.yaml` (provenance) → publish the **destination** repository → register it in the catalog (its first push bootstraps the namespace and pipeline through the platform dispatcher). The legacy code itself is **not** copied anywhere: the workspace clones it read-only at start, side by side with the destination — `/projects/legacy` next to `/projects/modernized`.

**What you should see:** a new catalog component for the migration **destination** (the legacy app never appears in the catalog), with links to the destination repository, Dev Spaces, and SonarQube — the same self-service pattern as stage 070, now wrapped around code that already exists.

> **Why this matters:** migration is where self-service pays off most. Nobody hand-wires analysis tooling, workspaces, and pipelines for every one of hundreds of legacy services. The template makes "start migrating this repo" a ten-second operation with every tool pre-approved by the platform team.

---

## Step 3: Analyze the legacy code with MTA

Before any agent writes a line, the supported product establishes the facts.

1. Open the workspace from the component page's **Dev Spaces** link. Both projects clone automatically — `legacy/` (the application you're migrating, read-only) next to `modernized/` (your destination repository) — and the MTA extension pack installs on first start (1–2 minutes).
2. Click the **MTA icon** in the left Activity Bar (the Konveyor logo), then **Open Analysis Panel**. Give the panel a moment on first open: the Java language server initializes in the background (the workspace pre-configures Standard mode so the analysis provider registers without opening a `.java` file first).
3. Click **Start** (top right of the Analysis View). **Server Status** flips from `Stopped` to `Running` — this boots the analyzer engine inside the workspace. Leave **Agent Mode** off; the platform runs MTA analysis-only.
4. Click **Manage Profiles**. The legacy repository ships its own analysis profiles in `.konveyor/profiles/` — select **`quarkus-profile`** (Quarkus migration targets; the `audit-logging` profile adds custom organization rules).
5. Back in the Analysis View, click **Run Analysis**. The first run downloads rulesets and scans the whole legacy tree — several minutes for a monolith; later runs are much faster (everything caches in the workspace).
6. Review the findings: the issue tree in the MTA panel, plus inline diagnostics directly in `legacy/` source files — every finding anchored to a rule, file, and line, with mandatory issues and effort estimates. Each run is also saved as machine-readable JSON at `legacy/.vscode/mta-core/analysis_<timestamp>.json` — this file is what the agent consumes in the spec step.
7. Keep the findings open. From this point on, the analysis is the **checklist the agentic result must satisfy** — the migration is done when the findings are resolved, not when the agent says so.

> **Expected panel state:** two informational cards are normal — *"GenAI
> functionality is disabled"* and *"Hub Configuration — No features
> enabled"*. They gate the Developer Lightspeed surface (the hub's
> Solution Server for AI remediation suggestions, and centralized Profile
> Sync), which this platform intentionally leaves off: the agent harness
> in `modernized/` is this exercise's remediation engine, and analysis
> profiles are versioned in the legacy repository (`.konveyor/profiles/`)
> instead of synced from the hub. Analysis itself needs neither.

**What you should see:** the analysis panel enumerating concrete migration issues in the legacy code, and squiggles in the legacy sources where each issue lives.

> **Console alternative:** the same analysis runs server-side in the MTA
> console (application launcher → MTA — it auto-redirects through
> **platform SSO**, the same OpenShift login as Developer Hub, with your
> MTA role resolved from the platform realm). Add the legacy repository
> to the Application Inventory, run the analysis, and open the report
> under the application's Reports tab. The in-workspace path above is the
> demo default: the findings land exactly where the agent will work.

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

### The harness implementation: Hermes Agent

Concepts need a runner. This stage uses **[Hermes Agent](https://hermes-agent.nousresearch.com/docs)** (Nous Research) as the harness implementation that owns the autonomous loop: a CLI-first agent that consumes the project's guides, runs the sensors as tools (build, tests, OpenRewrite, analysis), and iterates until the checks pass or the budget expires. The properties that matter here:

- **CLI-native, headless-capable**: `hermes chat -q "..."` runs a one-shot turn (including in non-TTY workers), and `hermes -w -z "..."` runs one in an isolated git worktree — the loop is drivable from a terminal and from automation alike.
- **Governed models, first-class**: `~/.hermes/config.yaml` points at any OpenAI-compatible endpoint — our MaaS gateway with a platform-issued key, so every loop iteration is metered like everything else on this platform.
- **Continuity with what you already built**: Hermes speaks the AGENTS.md and [agentskills.io](https://agentskills.io/home) mental model this project has used since stage 070 — the guides in this repository are its guides — and its built-in learning loop (skills created and improved from experience) is the "skills retro" practice running inside the agent itself.
- **A real task system for real migrations**: the Kanban board (`~/.hermes/kanban.db`) is a durable, multi-agent task graph — a dispatcher decomposes work into child tasks, routes them to specialist worker profiles, and each worker is a full OS process reporting back to the board. That is the ~100-task shape a whole-application migration actually has.

**Why not OpenClaw?** [OpenClaw](https://docs.openclaw.ai/) is the other agent harness you will hear named, and it is a strong product — but its center of gravity is different: a personal agent-ops **platform** built around a gateway daemon, chat channels, and session management, which *can* wrap coding CLIs (Codex, Copilot, even OpenCode via ACP) as embedded runtimes. Two mismatches for this stage:

| Need for stage 080 | Hermes | OpenClaw |
|---|---|---|
| Drive the loop from a CLI, not a UI | First-class: `hermes chat -q` headless/one-shot | Possible, but the CLI is a side door into a gateway/session model |
| Point at governed MaaS (`/v1` + platform key) | First-class OpenAI-compatible endpoint in `config.yaml` | Supported, with more allowlist/runtime/plugin ceremony |
| Continuity with 070 (AGENTS.md, skills) | Native AGENTS.md + agentskills.io mental model | Has skills/bootstrap, but less aligned with the `.opencode/skills` + spec-kit path |
| Self-correcting task loop (sensors → retry) | Kanban/DAG workers and one-shot runs are the product center | The agent loop exists, but product gravity is channels, gateway, sessions |
| Fit the *teaching* word "harness" | Matches Böckeler: everything around the model (tools, skills, memory, approvals, execution) | Uses "harness" for a *different* thing — its low-level runtime executors (`codex`, `copilot` plugins) — which collides with the stage narrative |
| Dev Spaces migration exercise | Heavier than OpenCode alone, but CLI-shaped | Heavier still: gateway daemon and channel/session semantics are the main design |

**Verdict: Hermes fits stage 080's CLI-driven autonomous migration loop more natively than OpenClaw.** The demo should look like *watching the migration converge in the terminal* — Hermes' center of gravity is exactly that loop, with messaging surfaces optional; OpenClaw would have you operating a gateway platform to tell the same story. Division of labor with what you already know: **OpenCode remains the interactive spec-authoring agent** (the 070 muscle memory, used in Step 5); **Hermes owns the autonomous execution loop** (Step 6).

---

## Step 5: Generate the migration spec

The MTA findings say what must change; the spec says what the migrated service must be.

1. Run the spec-kit cycle (`/speckit.specify` → `/speckit.plan` → `/speckit.tasks`) with the MTA analysis and the legacy code as input: the spec captures the service's observed behavior and API contract, the plan maps findings to Quarkus-native equivalents, and the tasks order the work.
2. Where findings are mechanical (dependency swaps, annotation replacement, import rewrites), the plan delegates to **OpenRewrite** recipes rather than model inference — deterministic transforms are cheaper, faster, and always correct, so the agent's inference budget is spent only where judgment is needed.
3. **Review each artifact before the next step amplifies it**, exactly as in stage 070. The spec is the contract the harness will hold the agent to.

**What you should see:** spec, plan, and tasks in the repository, traceable line-by-line to MTA findings and observed behavior.

---

## Step 6: Migrate under the harness

1. Start the implementation run: Hermes takes the task list — one-shot turns for a scoped demo (`hermes chat -q`), or the Kanban board for the full decomposed migration — and works through it: applying OpenRewrite recipes for the mechanical transforms, generating Quarkus-native code and tests for the rest.
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

> **Token governance beat (MTA 8.2):** interactive sessions run on
> five-minute access tokens; automation runs on **API keys** you create in
> the MTA console (your username menu → Tokens → Create API Key) — scoped
> to your role, usable by CI jobs and automation, and
> revocable instantly from the same page. Create one, show a scripted hub
> API call with it, then revoke it: governed automation credentials with a
> visible lifecycle, the same story the platform tells for model keys.

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
- **[Red Hat Developer Hub](https://developers.redhat.com/rhdh)** provides the developer portal and the migration golden-path template.
- **[Red Hat OpenShift Dev Spaces](https://www.redhat.com/en/technologies/cloud-computing/openshift/dev-spaces)** hosts the migration workspace.
- **[Red Hat OpenShift AI](https://www.redhat.com/en/technologies/cloud-computing/openshift/openshift-ai)** provides the governed MaaS endpoints the analysis tooling and the agent consume.
- **[Red Hat OpenShift Pipelines](https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/)** runs the exit pipeline with the SonarQube quality gate.
- **[Red Hat build of Keycloak](https://access.redhat.com/products/red-hat-build-of-keycloak)** provides the platform identity broker (stage 050 `identity` component); MTA 8.2's built-in Hub OIDC provider federates to it, so MTA, RHDH, and the cluster share one OpenShift-backed sign-in.
- **[Red Hat OpenShift](https://www.redhat.com/en/technologies/cloud-computing/openshift)** provides runtime, identity integration, routes, storage, and operations.

## Open Source Projects To Know

- [Konveyor](https://www.konveyor.io/) is the upstream modernization community behind MTA.
- [Kantra](https://github.com/konveyor/kantra) provides CLI-based application analysis.
- [OpenRewrite](https://github.com/openrewrite/rewrite) provides deterministic, recipe-driven code transformation.
- [spec-kit](https://github.com/github/spec-kit) is the spec-driven development toolkit carried over from stage 070.
- [Hermes Agent](https://hermes-agent.nousresearch.com/docs) is the CLI-first agent harness that owns the autonomous migration loop.
- [OpenCode](https://opencode.ai/) is the interactive AI coding agent used for spec authoring, carried over from stage 070.
- [Coolstore](https://github.com/konveyor-ecosystem/coolstore) is the legacy sample application used as the migration target.

## References

| Resource | Link |
|----------|------|
| Harness Engineering for Coding Agents | https://martinfowler.com/articles/harness-engineering.html |
| Hermes Agent documentation | https://hermes-agent.nousresearch.com/docs |
| OpenClaw documentation (compared alternative) | https://docs.openclaw.ai/ |
| MTA 8.2 documentation | https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.2/ |
| OpenRewrite documentation | https://docs.openrewrite.org/ |
| spec-kit — spec-driven.md | https://github.com/github/spec-kit/blob/main/spec-driven.md |
| MaaS code assistant quickstart | https://docs.redhat.com/en/learn/ai-quickstarts/rh-maas-code-assistant |
