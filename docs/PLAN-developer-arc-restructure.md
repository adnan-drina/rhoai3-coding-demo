# Plan: Developer-Arc Restructure (stages 050–090)

Status: SUPERSEDED by `PLAN-advanced-app-platform-restructure.md` (2026-07-10).
Phase 1 of this plan (renumber/rename/merge) was executed 2026-07-06; the new
plan reorganizes its result (080+090 fold into a new 050-advanced-app-platform;
dev stages shift to 060/070/080).
Decisions (2026-07-06): MTA folds into stage 070; portal takes 090 with 080
reserved for AI-in-CI/CD; stage 060 targets coolstore-inventory-service.

## Target structure

| Stage | Name | Story | Built from |
|---|---|---|---|
| 010–040 | (unchanged platform foundation) | Governed platform | rhoai3-demo import |
| 050 | ai-assisted-development | Dev Spaces + Continue via MaaS; **one-shot prompt vibe coding** — possibilities and limits of the most basic AI-assisted coding | merge: current 050 (infra) + current 080 (vibe-coding exercise) |
| 060 | ai-agentic-development | OpenCode + AGENT.md + Skills: enterprise Quarkus standards as reusable skills that agents follow and improve | new content; infra from 050 |
| 070 | ai-autonomous-migration | MTA + Developer Lightspeed (supported path) + multi-agent Spring Boot→Quarkus end-to-end migration (MigIQ pattern) | current 060 (MTA) + new agentic workflow |
| 080 | *(reserved)* ai-trusted-delivery | AI with Red Hat Trusted Software Supply Chain | BACKLOG topic until concrete |
| 090 | ai-self-service-portal | Developer Hub + Lightspeed for RHDH: the self-service wrap-up of all stages | current 070, moved to capstone |

Narrative arc: assisted (one-shot) → agentic (skills/rules) → autonomous
(multi-agent migration) → delivery (CI/CD, reserved) → self-service (portal).
Each stage motivates the next: one-shot limits motivate skills; skill-guided
agents motivate autonomous workflows; autonomy motivates supply-chain trust;
everything lands in the portal as the end-user experience.

## Stage plans

### 050 ai-assisted-development

- Rename dirs/apps: `050-controlled-developer-workspaces` →
  `050-ai-assisted-development` (stages/, gitops/stages/,
  app-of-apps, flows, labels).
- Keep all current 050 gitops (CheCluster, DevWorkspaces, MaaS key
  provisioning, Continue/OpenCode configs, editor policy).
- Merge current 080 README content as the demo exercise section: one-shot
  prompt vibe coding in Continue against the getting-started repo.
  - Frame explicitly: what one-shot prompting does well (scaffolding,
    boilerplate, explanation) and where it fails (project standards,
    multi-file consistency, hidden requirements) — the hook for 060.
  - Trim portal-dependent parts of old 080 (TechDocs links move to 090).
  - Keep the review-discipline guidance (human review gates) — it applies
    from the first prompt on.
- Retire `stages/080-governed-vibe-coding/` after merge.
- Validation: current 050 validate.sh + documented manual demo path.

### 060 ai-agentic-development

- New stage dirs: `stages/060-ai-agentic-development/` (README, deploy.sh thin or
  none if no new cluster resources; validate.sh for workspace assets).
- In-repo work: OpenCode wiring already exists (MaaS keys, opencode.json);
  add workspace/devfile entries if a dedicated workspace is needed
  (reuse coolstore-inventory-service workspace from 050).
- External-repo work (github.com/adnan-drina/coolstore-inventory-service):
  - `AGENT.md` — project identity, build/test commands, standards pointers.
  - `.opencode/skills/` (or agreed layout): reusable skills such as
    quarkus-rest-endpoint, quarkus-panache-entity, project-test-standards,
    api-docs-consistency; each encodes "how we build Quarkus apps here".
  - Rules: code style, package layout, test naming, OpenAPI annotations.
- Demo script: same task as 050's one-shot attempt, now executed by
  OpenCode with skills — compare outcomes; then a second task where the
  agent improves a skill after review feedback ("guidelines as living
  assets").
- Validation: skills present in workspace, OpenCode config resolves MaaS,
  scripted agent run completes the reference task (documented manual gate).

### 070 ai-autonomous-migration

- Rename current 060 (`ai-assisted-application-modernization`) →
  `070-ai-autonomous-migration`; keep MTA operator, Tackle, Lightspeed,
  Keycloak (portal OIDC depends on it), kai-api-keys MaaS wiring.
- Add the agentic migration workflow:
  - Sample app: Spring Boot service (MigIQ example or a curated fork under
    adnan-drina) added as a workspace project.
  - MigIQ skills installed into the workspace (pin npm version; document
    provenance and experimental status).
  - Models via MaaS: qwen3-6-35b-a3b executor, nemotron for long-context
    planning; agent traffic shows up in MaaS usage dashboards (040).
  - Flow: MTA analysis grounds the migration report → multi-agent
    graphify/plan/execute/test-gen → human review gate → containerize →
    deploy to OpenShift.
- Validation: MTA validate (existing) + migrated app builds/tests/deploys;
  MaaS telemetry captured as evidence.

### 080 (reserved) ai-trusted-delivery — BACKLOG only

- BACKLOG topic: AI with Red Hat Trusted Software Supply Chain (pipeline
  generation/review, artifact signing/attestation with TAS, vulnerability
  triage with TPA, Konflux). No stage dir until concrete plan exists.

### 090 ai-self-service-portal

- Renumber current 070 → 090 (dirs, app, flows, labels, docs).
- Scope addition (small): surface the whole arc as self-service — catalog
  entries and TechDocs for stages 050/060/070 exercises, Lightspeed for
  RHDH as the AI entry point. Absorbs the portal-dependent content trimmed
  from old 080.

## Execution order

1. Renumber/rename pass: 050 rename, 060 MTA→070, 070 portal→090; retire
   080-governed-vibe-coding into 050; flows/app-of-apps/labels/docs/skills
   references; static validation. (repo-only, no cluster needed)
2. 050 README merge + exercise rewrite.
3. 060 stage authoring (repo) + coolstore-inventory-service skills (external
   repo) — can proceed in parallel with foundation redeploy.
4. 070 agentic-migration authoring: sample app selection, MigIQ pinning,
   workspace wiring, README.
5. BACKLOG entries: 080 reserved topic; MigIQ provenance note.
6. Live validation on the fresh environment after foundation 010–040:
   deploy 050, 070 (MTA), 090; run 050/060/070 demo scripts end-to-end.

## Risks / notes

- MigIQ is experimental and Claude-Code-first; OpenCode compatibility in
  Dev Spaces needs a proving run before the stage README promises it.
- Agent runs are token-heavy: set expectations via MaaS token limits and
  show the Usage dashboard — it is part of the story, not a bug.
- External repo changes (coolstore-inventory-service) version the skills;
  workspace clones track a branch — pin refs in the devfile/workspace.
- Old 080's review-discipline content must not be lost in the merge; it
  becomes the common thread across 050→070.
