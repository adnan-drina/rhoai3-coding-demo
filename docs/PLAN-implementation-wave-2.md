# Plan: Implementation Wave 2 — 070 Agentic Migration, 080 Pipeline, 090 Templates, AI-Enhanced App

Status: PLANNED. Prereq state: all nine stages deployed and validated on a
fresh environment; showroom mapping in docs/PLAN-showroom-concept-mapping.md.

## Workstream A — Stage 070 agentic migration (MigIQ pattern)

Verified mechanics: `npx @sshaaf/migiq@0.2.2` installs the orchestrator +
`mig-*` skills into the project's `.claude/` directory; OpenCode discovers
`.claude/skills/<name>/SKILL.md` natively (documented search path), so the
Claude-Code-first layout works for our OpenCode workspaces. The repo ships a
complete Spring Boot sample (`examples/spring-boot-to-quarkus`: pom.xml,
src, Dockerfile, compose).

### A1. Sample application repository (needs user approval — new repo)
- Extract `examples/spring-boot-to-quarkus` into
  `github.com/adnan-drina/migiq-spring-boot-sample` (attribution note to
  sshaaf/migIQ in the README; Apache-2.0 both sides).
- Adapt its AGENT.md for OpenCode terminology (subagent invocation differs
  from Claude Code's Task tool — keep phases, replace tool references).
- Pin note: sample tracked at the commit matching migiq 0.2.2.

### A2. Migration workspace (gitops, stage 070)
- New DevWorkspace `agentic-migration` in `wksp-ai-developer`
  (pattern: stage 060 agentic-coolstore): clones the sample repo,
  6Gi memory, postStart runs `npx @sshaaf/migiq@0.2.2` (idempotent,
  project-local .claude install; verify node availability in the
  cli-ai-tools image — fallback: vendor the skills into the sample repo).
- Elevated-key provisioning: a 070-owned hook job (copy of the 050
  provisioner scoped to subscription `enterprise-rag-autorag`) writing
  `maas-agentic-migration-key` Secret; requires adding the job SA to that
  subscription's owner/subjects (the lesson from today, applied up front).
- OpenCode config drop: qwen executor + nemotron planner entries with the
  elevated key.

### A3. Proving run (manual, gated checkpoints — do NOT script until it passes)
1. Workspace starts; `.claude/skills/` populated; OpenCode `skill` tool
   lists mig-* skills.
2. `/migiq` graphify phase completes on the sample (small repo, minutes).
3. Plan phase produces dependency-ordered tasks.
4. ONE execute task with qwen; verify tool-calls parse (qwen3_coder parser).
5. Parallel execution: if OpenCode subagent semantics diverge from MigIQ's
   assumptions, fall back to sequential execution (documented, still a win).
6. Capture Usage-dashboard evidence during the run.

### A4. Productize
- Update agentic-migration-exercise.md from proving results (replace the
  open-items checklist with verified steps + timings).
- validate.sh additions: workspace exists, sample repo revision, skills
  present (exec ls .claude/skills via workspace pod when running),
  elevated key Secret exists.
- TROUBLESHOOTING entry for the failure modes met during proving.

Exit criteria: exercise runs end-to-end to the review gate; migrated app
builds and its tests pass; token burst visible on the Usage dashboard.

## Workstream B — Stage 080 pipeline recipe (showroom M5/M6)

### B1. Securesign instance
- `Securesign` CR in gitops (namespace trusted-artifact-signer): Fulcio
  keyless OIDC against the Stage 070 Keycloak (new `trusted-artifact-signer`
  client in the mta realm — added to the 070 Keycloak config job), Rekor +
  CTLog with PVC storage.
- Cluster-specific issuer URL via patch job (070 job pattern).
- Validation: fulcio/rekor pods ready; `cosign initialize` against the
  cluster TUF root succeeds.

### B2. Signed pipeline for coolstore-inventory-service
- Enable Tekton Chains in TektonConfig (artifacts.taskrun/pipelinerun
  format in-toto, transparency → in-cluster Rekor, signing → Fulcio
  keyless with the pipeline SA identity).
- Extend the repo's existing `.tekton/` PipelineRun: build (buildah) →
  unit tests → SBOM (syft task, CycloneDX) → push (internal registry) —
  Chains signs and attests automatically post-run.
- Validation: pipelinerun Succeeded; `cosign verify` + attestation
  present in Rekor; SBOM artifact attached.

### B3. TPA (bounded evaluation)
- Time-boxed spike: RHTPA operator deployability on the sandbox. If heavy,
  SBOM evidence stays as signed artifacts and TPA remains a documented
  next step — the demo story survives without it.

Exit criteria: one green signed+attested run for the inventory service;
stage 080 validation covers chains config, securesign readiness, and the
latest run's signature; README Show beats updated from talk-track to live.

## Workstream C — Stage 090 software templates + Lightspeed (showroom M4)

### C1. Scaffolder template `governed-ai-workspace`
- Template YAML in gitops (registered via app-config catalog locations):
  parameters (component name, owner, repo URL, model tier) → actions:
  publish catalog-info (register component), emit Dev Spaces workspace
  link, output the "next steps" card. First iteration does NOT create git
  repos (avoids GitHub app credentials); iteration two adds repo
  scaffolding from a skeleton if credentials are approved.
- Validation: template renders in Create…, dry-run produces a catalog
  entity linked to a governed workspace URL.

### C2. Developer Lightspeed for RHDH
- Enable the Lightspeed dynamic plugin (RHDH 1.9) pointed at a
  MaaS-published model (qwen) with a platform-issued key Secret; requires
  adding the RHDH SA or a dedicated key to the developer subscription
  (same authorization pattern as today's fixes).
- Validation: Lightspeed panel loads and answers a catalog question;
  usage metered on the dashboard.

Exit criteria: a developer can scaffold a component into the catalog and
ask Lightspeed about it, with all AI traffic governed.

## Workstream D — AI-enhanced application (showroom M7 → future stage candidate)

- New Quarkus service `coolstore-support-triage` using quarkus-langchain4j
  with the OpenAI provider pointed at MaaS (qwen; key from a service
  subscription — new MaaSSubscription for workload identities, not
  developer identities: the missing governance persona).
- Delivered through the Workstream B pipeline (ties the arcs together),
  registered in the 090 catalog, one Know/Show exercise: the same golden
  path, now for application AI.
- Lands as stage candidate after 060 numbering-wise conflicts are weighed
  (likely a 060 exercise extension first, standalone stage only when it
  has its own platform resources).

## Sequencing and decision points

1. **A first** (highest demo value; everything else exists). Decision
   needed now: approve creating `migiq-spring-boot-sample` repo.
2. **B second** (Securesign depends on 070 Keycloak, already live).
   Decision: internal registry vs quay.io for signed images.
3. **C third** (small, independent). Decision: iteration-two repo
   scaffolding credentials.
4. **D last** (depends on B pipeline + a service-identity subscription
   design).

Each workstream follows the session's proven loop: skill-guided pre-check →
GitOps change → live validation → fold findings back into skills/docs.
