# Stage 080: AI-Autonomous Migration with an Agent Harness

The previous stages built the AI maturity ladder one rung at a time, and both stages end with a human driving every cycle. This stage asks the next question: what has to be true for an agent to carry a whole-application migration largely on its own?

Legacy applications are not just expensive to maintain. They are an expanding attack surface. AI-powered exploit tools lower the cost of finding and weaponizing vulnerabilities in outdated frameworks, and regulations are catching up: the EU Cyber Resilience Act makes vendors accountable for the security posture of every product they ship, including the libraries and runtimes underneath it. The migration backlog is no longer a cost problem alone; it is a compliance and security deadline that most teams cannot meet with manual effort.

This demo stage answers with two complementary paths on the same governed platform: assisted modernization through Migration Toolkit for Applications turning a legacy codebase into an inventory of concrete, prioritized migration issues, and autonomous migration where an agent harness takes a legacy service end-to-end to Quarkus with analysis-grounded planning, spec generation, self-evaluation loops, and a trusted software supply chain pipeline that enforces quality and security before anything merges.

Application domain experts remain essential. Agents handle the volume (hundreds of files, thousands of import rewrites, test scaffolding), but domain experts define what correct migration means: which business behaviors must be preserved, which integration contracts matter, where the analysis findings are real issues versus acceptable deviations. The harness encodes their judgment as guides and sensors; they improve those assets after each run rather than reviewing every line the agent writes.

## What You'll Do

**Demo spine (Acts A–E):** provision a governed migration workspace → establish MTA ground truth → plan with Spec Kit (never `/speckit.implement`) → **watch Hermes Kanban before dispatch** → audit with `list` / `show` / `runs` + verdict JSON. That is what you observe in the room.

Implementation architecture (design, M1–M5, governance, v1 dest vs v2 target) lives in [SOLUTION-ARCHITECTURE.md](SOLUTION-ARCHITECTURE.md). This README is the demo walkthrough. Do not copy either file into `scaffold-repo/`. Agents: consume and contribute using the SAD [§10](SOLUTION-ARCHITECTURE.md#10-how-agents-consume-and-contribute). Full M5 factory ship is **not** claimed DEMONSTRATED for the Owner/Pet slice yet.

---

## Step 1: Sign in to Developer Hub

1. Open the Developer Hub URL and sign in as `ai-developer` (OpenShift OIDC).

**What you should see:** the RHDH home screen with the catalog search bar.

---

## Step 2: Create your migration project from the template

Stage 070's template scaffolded a greenfield service from nothing. The migration template inverts the input: you bring an existing codebase.

1. Open **Self-service** and choose the **Application migration** template.
2. Provide the input the template asks for:
  - **Project name**: becomes the per-run destination repository, namespace, and workspace name (e.g. `coolstore-cart-v6`, `petclinic-rest-v2`).
  - **Legacy repository URL**: HTTPS Git URL clonable without credentials. Two demo inputs are maintained: the Coolstore **cart** service ([coolstore-cart-legacy](https://github.com/adnan-drina/coolstore-cart-legacy.git)) — small and stateless, good for a short workshop run — and the **Spring PetClinic REST** service ([spring-petclinic-rest-legacy](https://github.com/adnan-drina/spring-petclinic-rest-legacy), pinned at v2.6.2), the validated showcase: a database-backed REST API with OpenAPI-generated DTOs, three alternative persistence layers, and profile-driven configuration — the shapes a real migration has to decide about. The monolith round used [mca-coolstore](https://github.com/rhpds/mca-coolstore.git).
  - **Needs database**: leave off for cart (stateless); enable for PetClinic and any legacy app that persists to a database.
3. Create, and watch the template run: fetch the migration scaffold → publish the **destination** repository → register it in the catalog (its first push bootstraps the namespace and pipeline through the platform dispatcher). The legacy code itself is **not** copied anywhere: the workspace clones it read-only at start, side by side with the destination, `/projects/legacy` next to `/projects/modernized`. The migration contract in `migration.yaml` — packages, dest↔legacy leaf maps (`intra_package_maps`), acceptance path/shape, preserve/forbidden, `targetContract` — is **stamped by the app-migration template skeleton** from the legacy URL for the two demo freeze-forks (`coolstore-cart-legacy`, `spring-petclinic-rest-legacy`). The golden scaffold stays specimen-free; unknown legacy URLs get `contract.status: undecided` rather than cart defaults. The dependency deriver applies `path_rewrites` and `intra_package_maps`, so a plan may emit a dest leaf that differs from legacy without breaking gate 3. Review the stamped contract after create; override a decided flag only when you intend to.

**What you should see:** a new catalog component for the migration **destination** (the legacy app never appears in the catalog), with links to the destination repository, Dev Spaces, and SonarQube, the same self-service pattern as stage 070, now wrapped around code that already exists.

> **Why this matters:** migration is where self-service pays off most. Nobody hand-wires analysis tooling, workspaces, and pipelines for every one of hundreds of legacy services. The template makes "start migrating this repo" a ten-second operation with every tool pre-approved by the platform team.

---

## Step 3: Analyze the legacy code with MTA

Before any agent writes a line, the supported product establishes the facts.

1. Open the workspace from the component page's **Dev Spaces** link. Both projects clone automatically: `legacy/` (the application you're migrating, read-only) next to `modernized/` (your destination repository). The MTA extension pack installs on first start (1–2 minutes).
2. Click the **MTA icon** in the left Activity Bar (the Konveyor logo), then **Open Analysis Panel**. Give the panel a moment on first open: the Java language server initializes in the background (the workspace pre-configures Standard mode so the analysis provider registers without opening a `.java` file first).
3. Click **Start** (top right of the Analysis View). **Server Status** flips from `Stopped` to `Running`, which boots the analyzer engine inside the workspace. Leave **Agent Mode** off; the platform runs MTA analysis-only.
4. Click **Manage Profiles**. The legacy repository ships its own analysis profiles in `.konveyor/profiles/`; select `quarkus-profile` (Quarkus migration targets).
5. Back in the Analysis View, click **Run Analysis**. The first run downloads rulesets and scans the whole legacy tree (several minutes for a monolith; later runs are much faster as everything caches in the workspace).
6. Review the findings: the issue tree in the MTA panel, plus inline diagnostics directly in `legacy/` source files. Every finding is anchored to a rule, file, and line, with mandatory issues and effort estimates. Each run is also saved as machine-readable JSON at `legacy/.vscode/mta-core/analysis_<timestamp>.json` (the IDE path; the harness uses `migration/mta-findings.json` instead).
7. Keep the findings open. From this point on, the analysis is the **checklist the agentic result must satisfy**: the migration is done when the findings are resolved, not when the agent says so.

> **Expected panel state:** two informational cards are normal: *"GenAI
> functionality is disabled"* and *"Hub Configuration: No features
> enabled"*. They gate the Developer Lightspeed surface (the hub's
> Solution Server for AI remediation suggestions, and centralized Profile
> Sync), which this platform intentionally leaves off: the agent harness
> in `modernized/` is this exercise's remediation engine, and analysis
> profiles are versioned in the legacy repository (`.konveyor/profiles/`)
> instead of synced from the hub. Analysis itself needs neither.

**What you should see:** the analysis panel enumerating concrete migration issues in the legacy code, and squiggles in the legacy sources where each issue lives.

> **Console alternative:** the same analysis runs server-side in the MTA
> console (application launcher → MTA, which auto-redirects through
> **platform SSO**, the same OpenShift login as Developer Hub, with your
> MTA role resolved from the platform realm). Add the legacy repository
> to the Application Inventory, run the analysis, and open the report
> under the application's Reports tab. The in-workspace path above is the
> demo default: the findings land exactly where the agent will work.

> **Harness analysis path:** M1 uses the `mta-analysis` skill / `mta-cli`
> (kantra) and writes `migration/mta-findings.json` (plus session artifacts
> under `migration/`). The IDE panel above is for *human* exploration; the
> harness reads `migration/mta-findings.json` as ground truth. Both paths
> use the same rulesets and targets from `migration.yaml`.

---

## Demo walkthrough (Acts A–E)

**Authority:** Research journey `source-analysis/demo-ux/20260808-e2e-demo-user-journey.md`;
Architect demo-surface decide; Deputy docs-only Stage-1 exception
`E-20260808T153444Z`. **Specimen for the prove path:** PetClinic Owner/Pet
(`petclinic-rest-v7-refac`) — pick one and stick to it.

| Act | Job | What you look at |
|-----|-----|------------------|
| **A** Arrive | Self-service workspace | RHDH → Dev Spaces; `/projects/legacy` (RO) beside `/projects/modernized` |
| **B** Ground truth | MTA checklist | Prefer `migration/mta-findings.json` (harness authority); IDE panel optional *human* exploration |
| **C** Plan without implementing | Spec Kit → Kanban | `/speckit.specify` → plan → tasks → K4 convert → `k4_mint.py` (`hermes kanban create`) — **never** `/speckit.implement` |
| **D** Watch the migration | Hermes Kanban | Pane A: `hermes kanban watch` **before** dispatch · Pane B: `dispatch` |
| **E** Audit close | Snapshots + verdicts | `list` / `show` / `runs <task_id>` + `migration/verdicts/*.json` — not more watching |

**Forbidden:** `outer-loop.sh`, `supervisor.sh`, `tail -f outer-loop.log`, starting
`watch` only after the run, inventing a sixth log surface.

### Act C — Plan (brief → Spec Kit → Kanban)

```bash
cd /projects/modernized
hermes chat -q "Read migration/briefs/<brief>.md. Run /speckit.specify then /speckit.plan then /speckit.tasks. Stop. Never /speckit.implement. Create Kanban cards from tasks.md with workspace dir:/projects/modernized."
```

**What you should see:** `specs/.../{spec,plan,tasks}.md` and ready/todo cards on
`hermes kanban list`.

### Act D — Watch (Track B replacement)

**Critical ordering** (Architect binding — empty watch after the run is not a defect):

```bash
cd /projects/modernized
export HERMES_HOME=/projects/modernized/.hermes/home
# terminal A — start BEFORE any create
hermes kanban watch --interval 1
# terminal B — seed M1 as a native Kanban task (no dispatch-phase wrapper)
hermes kanban create "M1 ANALYZE" \
  --skill paved-road-m1 \
  --workspace dir:/projects/modernized --json
# later phases: hermes kanban create … --parent <task_id>
# gateway-embedded dispatcher ticks; do not `kanban daemon --force`
```

Do **not** start M1 with a detached `mta-analyze-legacy.sh` — Hermes must own
M1–M5 orchestration (role, skills, `max_runtime_seconds`, recovery).

**Dashboard is not part of Acts A–E.** Operator-only Hermes dashboard (optional)
lives in `harness-refactoring/docs/DEMO-SURFACE-RUNBOOK.md` — **not** the demo
spine. Do not use Che Ports / Simple Browser for it.

Drill-down:

```bash
hermes kanban show <task_id>
hermes kanban runs <task_id>   # task_id required
hermes kanban log <task_id>
```

**Honest exit of this act:** M4 **`PROVISIONAL_ACCEPT`** for Owner/Pet
(`ship=false`, kill-ratio `pending_threshold`) — not “migration finished and shipped.”

### Act E — Audit close

```bash
hermes kanban list
hermes kanban runs <task_id>
# open migration/verdicts/… — ship=false honesty
```

Optional: Stage 040 MaaS usage dashboard for the **metering** beat — not the
progress UI. Skip or label as future: factory push / Sonar green / M5 `ACCEPT`
unless observed in *this* environment.

| Surface | Maturity (live `petclinic-rest-v7-refac`, 2026-08-08) |
|---|---|
| `hermes kanban list` / `show` / `runs` / `log` | **DEMONSTRATED** |
| `hermes kanban watch` / `dispatch` | **DEMONSTRATED** (Owner/Pet) |
| `hermes dashboard` public `:9119` (`hermes-dash`) | **DEFINED** (operator appendix / runbook only; postStart best-effort, overlay `HERMES_WEB_DIST`) — **not** demo surface; not required for DEFINED→DEMONSTRATED |
| Dest named profiles `orchestrator` + `implementer` + `reviewer` | **DEFINED** in GitOps (create without `--clone`; `review_dispatch` true with reviewer). Dest-armed measurement **not** this sitting. OBJECT dest-apply dest-14. |
| Owner/Pet → M4 `PROVISIONAL_ACCEPT` | **DEMONSTRATED** |
| Owner/Pet → M5 full `ACCEPT` / factory | **Not** DEMONSTRATED |

Evidence: `harness-refactoring/measurements/hermes-native-tracking/VERIFY.md`;
runbook: `harness-refactoring/docs/DEMO-SURFACE-RUNBOOK.md`.

Design (M-process, grounding, Hermes model pin, v1 leftover vs v2 target) lives
in [SOLUTION-ARCHITECTURE.md](SOLUTION-ARCHITECTURE.md). This README is the
walkthrough. Conflict rule: SAD wins for design; README wins for what you click.

---

## Step 7: The factory ships it (future / not demo spine)

> **Maturity:** **Not DEMONSTRATED** for the Owner/Pet slice in the live prove
> path. Label clearly if shown; do not imply the room will see this today.

Nothing merges on agent authority, and no human approval substitutes for the factory either.

1. After M5 (full `ACCEPT` path — **after** kill-ratio pin; a waiver cannot
   author ACCEPT),
   re-analyze migrated code; done is the Step 3 baseline resolved or the
   gate REFUSE with a remediation card.
2. Push from the workspace (Git credentials required). The report ends:
   "pushed; the factory pipeline decides."
3. Watch the project's pipeline: clone → build → SonarQube quality gate → image.
   **Red CI means autonomy failed the regulated exit**; green CI is the proof.
4. Spot-check optional. Gaps → improve guides/sensors (steering), not mid-run
   skill rewrites.

**What you should see:** findings delta recorded, tests green, quality gate
passed — pipeline as merge authority. Do not claim this exit until a slice has
actually shipped.

---

## Step 8: The bill and the retro (optional beat)

1. Open the Stage 040 MaaS usage dashboard: token consumption for Hermes
   sessions / Kanban workers on the developer key, next to earlier stages.
2. After a real slice: skim Kanban run history (`hermes kanban runs`), any
   `migration/retro-proposals.md` / debt notes, and tighten guides/skills as
   versioned repo changes (stage 070 skills-retro practice).

> **Token governance beat (MTA 8.2):** interactive sessions run on
> five-minute access tokens; automation runs on **API keys** you create in
> the MTA console (your username menu → Tokens → Create API Key), scoped
> to your role, usable by CI jobs and automation, and
> revocable instantly from the same page. Create one, show a scripted hub
> API call with it, then revoke it: governed automation credentials with a
> visible lifecycle, the same story the platform tells for model keys.

**What you should see:** the complete, attributed cost of the autonomous run on the platform dashboard, and a written record of where the harness needs to get better.

---

## Wrap-up

### What you proved

- **Analysis grounds autonomy:** MTA's findings, not the agent's self-assessment, defined done.
- **The harness regulates quality:** guides steered generation, sensors caught and fed back failures, and the agent iterated to green before a human ever looked.
- **Determinism where possible, inference where needed:** mechanical transforms ride skills and typed bodies; judgement-heavy work stays on Spec Kit + implementer cards under Hermes Kanban.
- **The factory, not a person, was the merge authority:** the agent could push, but only the pipeline and its quality gate could turn that push into a trusted artifact. Humans moved up a level, from reviewing diffs to improving the harness.
- **Governance held at full autonomy:** same identity, token limits, and telemetry as every previous stage, just more visible, because agents consume more.

## Red Hat Products Used

- **[Migration Toolkit for Applications](https://developers.redhat.com/products/mta)** turns legacy code into a concrete, prioritized inventory of what must change. The agent cannot define "done" on its own; MTA's findings are the ground truth.
- **[Red Hat Developer Hub](https://developers.redhat.com/rhdh)** makes "start migrating this repo" a ten-second self-service operation. No tickets, no hand-wiring of tooling per application.
- **[Red Hat OpenShift Dev Spaces](https://www.redhat.com/en/technologies/cloud-computing/openshift/dev-spaces)** gives each migration a preconfigured workspace with analysis tools, agent runtime, and governed model access ready from first start.
- **[Red Hat OpenShift AI](https://www.redhat.com/en/technologies/cloud-computing/openshift/openshift-ai)** governs every model request through MaaS: identity, API keys, rate limits, token budgets, and usage telemetry, so autonomous workloads stay within organizational boundaries.
- **[Red Hat OpenShift Pipelines](https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/)** is the merge authority. No agent, and no human, bypasses the quality gate. Green CI is the platform's proof, not anyone's claim.
- **[Red Hat build of Keycloak](https://access.redhat.com/products/red-hat-build-of-keycloak)** provides single sign-on across MTA, Developer Hub, and the cluster, so every action is attributed to a real identity.
- **[Red Hat OpenShift](https://www.redhat.com/en/technologies/cloud-computing/openshift)** is the foundation: runtime, identity, networking, storage, and GitOps-managed state that makes the whole platform reproducible.

## Open Source Projects To Know

- [Konveyor](https://www.konveyor.io/) is the upstream modernization community behind MTA.
- [Kantra](https://github.com/konveyor/kantra) provides CLI-based application analysis.
- [OpenRewrite](https://github.com/openrewrite/rewrite) provides deterministic, recipe-driven code transformation.
- [spec-kit](https://github.com/github/spec-kit) is the spec-driven development toolkit. Stage 080 provisions it **in the migration workspace only** (AD-S) via Hermes skill `specify-workspace-init` (`specify init --integration hermes`), installs the Non-Goals override, and stops at `/speckit.tasks` → K4 convert → `.hermes/kernel/k4_mint.py` (`hermes kanban create`) — never `/speckit.implement`. Scaffold taxonomy: `.hermes/LAYOUT.md`.
- [Hermes Agent](https://hermes-agent.nousresearch.com/docs) is the CLI-first agent harness that owns the autonomous migration loop.
- [OpenCode](https://opencode.ai/) is the coding worker inside the harness, dispatched by Hermes one bounded task at a time, and remains available interactively, carried over from stage 070.
- [Coolstore cart (legacy demo input)](https://github.com/adnan-drina/coolstore-cart-legacy) is the small, stateless Spring Boot migration target — the first specimen the harness shipped; [Spring PetClinic REST (legacy demo input)](https://github.com/adnan-drina/spring-petclinic-rest-legacy) is the database-backed validated showcase, pinned at v2.6.2 so every run migrates the same code; the [Coolstore monolith](https://github.com/rhpds/mca-coolstore) remains available for longer runs.

## References

| Resource                                      | Link                                                                                                                                                                 |
| --------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Harness Engineering for Coding Agents         | [https://martinfowler.com/articles/harness-engineering.html](https://martinfowler.com/articles/harness-engineering.html)                                             |
| Maintainability sensors for coding agents     | [https://martinfowler.com/articles/sensors-for-coding-agents.html](https://martinfowler.com/articles/sensors-for-coding-agents.html)                                 |
| Open blueprint for cloud-native AI agents     | [https://developers.redhat.com/articles/2026/07/20/architect-open-blueprint-cloud-native-ai-agents](https://developers.redhat.com/articles/2026/07/20/architect-open-blueprint-cloud-native-ai-agents) |
| Hermes Agent documentation                    | [https://hermes-agent.nousresearch.com/docs](https://hermes-agent.nousresearch.com/docs)                                                                             |
| Hermes Agent — configuring models             | [https://hermes-agent.nousresearch.com/docs/user-guide/configuring-models](https://hermes-agent.nousresearch.com/docs/user-guide/configuring-models)                 |
| OpenClaw documentation (compared alternative) | [https://docs.openclaw.ai/](https://docs.openclaw.ai/)                                                                                                               |
| MTA 8.2 documentation                         | [https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.2/](https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.2/) |
| OpenRewrite documentation                     | [https://docs.openrewrite.org/](https://docs.openrewrite.org/)                                                                                                       |
| spec-kit: spec-driven.md                      | [https://github.com/github/spec-kit/blob/main/spec-driven.md](https://github.com/github/spec-kit/blob/main/spec-driven.md)                                           |
| MaaS code assistant quickstart                | [https://docs.redhat.com/en/learn/ai-quickstarts/rh-maas-code-assistant](https://docs.redhat.com/en/learn/ai-quickstarts/rh-maas-code-assistant)                     |


