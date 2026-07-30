# AGENTS.md

## Project identity

This repository is `rhoai3-coding-demo`.

It demonstrates a trusted enterprise AI development platform on Red Hat OpenShift AI. The demo shows how platform teams can provide private and governed AI coding assistance through Red Hat OpenShift AI, Models-as-a-Service, Red Hat OpenShift Dev Spaces, Continue, OpenCode, Migration Toolkit for Applications (MTA), Red Hat Developer Hub, and GitOps-managed platform components.

The main architectural idea is:

- Developers use familiar tools.
- Sensitive code can use private models on OpenShift.
- Approved external models can be exposed through a governed access layer.
- MaaS is the control point for identity, API keys, rate limits, quotas, telemetry, and model access.
- GitOps keeps platform state reproducible.

## Human accountability

AI tools may assist with this repository, but they do not own changes.

For every AI-assisted contribution:

- A human must review the full diff.
- A human must verify the commands, manifests, scripts, and documentation.
- A human must ensure no secrets, tokens, credentials, or private data are committed.
- A human must take responsibility for correctness, security, maintainability, and licensing.
- Material AI assistance must be disclosed in the PR.

AI agents must not add `Signed-off-by` trailers on behalf of humans.

## Repository map

Important paths:

- `README.md` — main workshop overview and architecture narrative.
- `BACKLOG.md` — known workarounds, limitations, planned work, and validated status.
- `env.example` — non-secret environment variable template.
- `scripts/` — bootstrap, shared helper scripts, validation utilities.
- `gitops/` — desired state for Argo CD and OpenShift resources.
- `gitops/argocd/app-of-apps/` — Argo CD application structure.
- `flows/default.yaml` — ordered source of truth for the demo flow.
- `gitops/stages/` — desired state for stage-specific OpenShift resources.
- `stages/` — human-facing deployment walkthroughs and per-stage deploy/validate scripts.
- `docs/` — operations, troubleshooting, architecture, and supporting documentation.
- `.agents/` — shared tool-neutral agent guidance (rules, skills, hooks, references).

## Demo stages

The workshop has two parts:

- Stages 010-070 build the trusted AI development platform for platform engineers.
- Stages 060 and later show enterprise developer workflows that consume that platform.

Current implemented stages:

1. 010 OpenShift AI Platform Foundation
2. 020 GPU Infrastructure for Private AI
3. 030 Private Model Serving
4. 040 Governed Models-as-a-Service
5. 050 Advanced Application Platform (Dev Spaces, RHDH, Pipelines, SonarQube, MTA, Coolstore)
6. 060 AI-Assisted Development (Kilo Code, one-shot coding — workflow stage)
7. 070 AI-Agentic Development (OpenCode, AGENTS.md, skills — workflow stage)
8. 080 AI-Autonomous Migration (MTA + multi-agent migration — workflow stage)

The stages renumbered when stage 040 absorbed the former external-model and MCP stages during the rhoai3-demo foundation import: 070/080/090/100 became 050/060/070/080.

Developer workflow stages after 080 are deferred until each has a concrete implementation plan and validation path.

When changing one stage, check whether related changes are also needed in:

- `README.md`
- the stage README
- `docs/OPERATIONS.md`
- `docs/TROUBLESHOOTING.md`
- `BACKLOG.md`
- GitOps manifests
- deploy or validate scripts

## Detailed Rules

For project structure, coding discipline, change conventions, and shared agent guidance, read `.agents/rules/project.md`.

For live demo environment deployment, secrets, certs, and cluster safety, read `.agents/rules/env.md`.

For GitOps authoring, manifests, labels, and schema validation, read `.agents/rules/gitops.md`.

For documentation standards, README structure, and operations docs, read `.agents/rules/docs.md`.

For RHOAI platform component guidance backed by official Red Hat documentation, read `.agents/rules/rhoai.md`.

For OpenShift Container Platform infrastructure, control plane, networking, authentication, monitoring, GitOps, cluster, and storage integration guidance, read `.agents/rules/ocp.md`.

For OpenShift Data Foundation storage, object storage, NooBaa, and ODF storage classes, read `.agents/rules/odf.md`.

For Stage 080 Track B (autonomous migration drive/monitor/harness), read
`.agents/rules/stage-080-track-b.md` and run
`.agents/skills/stage-080-quality-advance/SKILL.md` before ship or next story.

## OpenShift Safety Guard

- Open this repository as its own project; do not open `/Users/adrina/Sandbox` as the active project for live cluster work.
- Before running live `oc`/`kubectl` commands, call `load_env` and `check_oc_logged_in` from `scripts/lib.sh`.
- Set `RHOAI_EXPECTED_API_SERVER` in the local `.env` to a unique target API-server substring before deploy, validate, bootstrap, or resource-management scripts run.
- Do not bypass the guard with `RHOAI_ALLOW_UNGUARDED_CLUSTER=true` unless the user explicitly confirms the current cluster and the command is low risk.

## Security and privacy

Never commit:

- API keys
- OpenShift tokens
- kubeconfigs
- Hugging Face tokens
- OpenAI or external model provider keys
- private cluster URLs if they are not intended for publication
- real user passwords
- customer data
- internal/private source code from another project

Use placeholders in examples.

Sensitive areas include:

- MaaS auth and API key handling
- Authorino and Kuadrant policies
- Gateway routing
- RBAC
- NetworkPolicy
- OpenShift OAuth and identity configuration
- External model credentials
- Red Hat OpenShift Dev Spaces workspace configuration
- MCP integrations

For these areas, include explicit validation notes in the PR.

## Agent workflow

For non-trivial tasks, follow this workflow:

1. Read the relevant README, stage docs, and manifests before editing.
2. State the intended change and affected files.
3. Make the smallest useful change.
4. Avoid broad refactors unless explicitly requested.
5. Update documentation in the same PR as behavior changes.
6. Run the narrowest validation command available.
7. If cluster validation is required but unavailable, state exactly what could not be validated.
8. Produce a PR summary with risks, rollback notes, and validation evidence.

### Stage 080 Track B — non-negotiable mandate

**End state:** an **autonomous, swift, hardened, durable, fully functional**
migration process. No compromises. No assumptions. No cutting corners. No
pushing through on hope.

**Method:** be methodical, thorough, and thoughtful at every step. Skip
nothing. When an issue appears, **fix it and re-run** — do not wait hours
to discover the process was broken. Prefer **multiple partial runs**, each
building harness honesty and durability, over **one completed run with a
broken service**.

**Temporary manual → durable → re-run (mandatory):**

Manual / operator edits in the live migration tree (or one-off hand fixes)
are allowed **only** to confirm an assumption quickly. They are not the
finish line.

1. **Probe** — temporary fix; note the hypothesis in the quality gate.
2. **Validate** — confirm the probe actually cleared the failure class.
3. **Durableize** — implement the same fix in harness / skills / sensors /
   plan-lint / driver (bank ⬜ → ✅); never leave it as “I fixed the app.”
   Durable fixes must be **migration-general** (any Spring Boot → Quarkus
   app using this harness), not Coolstore cart–specific hardcoding.
4. **Re-run** — abort/resume or restart so the *process* applies the durable
   fix without the hand edit. Only then is the item closed.

Skipping step 3 or 4 is forbidden drift (pushing the run through).

**Generalizable harness (mandatory):**

This demo’s cart service is a **specimen**, not the product. Track B
durableizes a reusable Spring Boot → Quarkus migration method. Every banked
fix, sensor, plan-lint rule, skill tip, and supervisor behavior must be
expressed in terms of **general patterns** (package rename, CDI harvest,
REST client, preserve tokens, characterization, Sonar/style, worker vs
orchestrator routing, etc.) parameterized by `migration.yaml` / briefs /
findings — **not** Coolstore-only class names, item ids, endpoints, or
package literals baked into the harness.

Coolstore-specific content belongs in **story briefs/tasks/roadmap** for
that run, or in fixtures/instruments that explicitly test the general rule
with cart-shaped examples. If a fix only works for Coolstore cart, it is
not durable — redesign until another Spring Boot app would inherit it.

**MiniMax-over-Qwen escalations (mandatory — every time):**

Whenever MiniMax / Hermes **takes over coding work from Qwen / OpenCode**
(worker incomplete/failed → orchestrator escalation, including sfix
escalations that MiniMax owns), treat it as a first-class defect until
closed:

1. **Capture** — note task id, actor path, and commit(s) in
   `docs/V9-QUALITY-GATE.md` (do not bury under “escalation”).
2. **Analyze Qwen** — read `/tmp/oc-T-NNN.err`, `/tmp/oc-T-NNN.json` (or
   equivalent OpenCode logs), supervisor lines for that task, and the
   dirty-tree / commit state **before** MiniMax ran. Identify *why* the
   worker failed to finish (no commit, wrong scope, tool error, false
   already-complete, mechan skip, quota, etc.).
3. **Analyze MiniMax** — what it changed; whether the takeover was
   necessary or a harness false path.
4. **Durableize** — bank ⬜ and implement harness/skill/sensor/worker
   improvements so the same cause does not force MiniMax again.
5. **Retest** — re-run the affected task/story (or a focused probe) and
   confirm Qwen/worker path succeeds without MiniMax takeover when the
   durable fix applies.

Closing an escalation because “MiniMax fixed it and GREEN” without steps
2–5 is forbidden. MiniMax is the expensive escape hatch, not the happy
path.

**Forbidden drift:**

- Advancing on sensor GREEN without substance review
- Asking the human whether to bank, analyze, or HOLD
- Leaving open polish for “after the demo” or “next PR”
- Nursing a compromised run to finish the story count
- Assumptions about what a commit “probably” did — read the diff
- Treating a validated hand fix as done without durableize + re-run proof
- Accepting MiniMax escalation success without Qwen-log root cause +
  durableize + retest
- Baking Coolstore cart–specific names/paths/ids into harness “durable”
  fixes that should apply to any Spring Boot → Quarkus migration

Canonical skill/rule: `.agents/skills/stage-080-quality-advance/SKILL.md`,
`.agents/rules/stage-080-track-b.md`. Live wake loop: `tmp/v8-driver-loop.sh`
(O-DRV2 / O-DRV3 / O-DRV4 / **O-DRV5**). Polish bank: `docs/V7-FUTURE-IMPROVEMENTS.md`.

These gates are **script-enforced**, not memory: O-DRV3 →
`tmp/V9-TASK-ANALYSIS-PENDING.md`; O-DRV5 → `tmp/V9-M-ANALYSIS-PENDING.md`;
O-DRV4 → `tmp/V9-CHAT-PULSE-PENDING.md`.

#### Before each new migration run

Implement **all** open polish / banked items (⬜ → ✅) **before** starting
or restarting Track B — so the new run exercises them. Do not start a run
with known open harness defects. Prefer abort/restart over shipping a
compromised run.

#### Driver goals (must follow on every tick)

1. **O-DRV4 — chat pulse every tick (P0, non-negotiable)** — on every
   driver interval (default 120s), post a **2–5 line update in chat** to
   the user, then acknowledge:
   `printf '<tick-ts>\n' > tmp/V9-CHAT-PULSE.ack` and remove
   `tmp/V9-CHAT-PULSE-PENDING.md`. The driver emits **CRITICAL** every tick
   until you do. If the ack is older than ~2.5× interval, the tick is
   **OVERDUE** — you went idle; recover immediately. Going silent while
   the run is live is a process failure, not a judgment call.
2. **O-DRV2 — harness self-heal** — if outer-loop is DOWN and the story
   ledger is incomplete, auto-restart it (no sticky bare `RUN_BASE`). Treat
   unexpected downtime as P0.
3. **O-DRV3 — detailed post-task analysis (script)** — after every new
   `T-NNN` / `T-NNN sensor fix` commit, driver writes
   `tmp/V9-TASK-ANALYSIS-PENDING.md` and stays CRITICAL until a detailed
   gate entry exists and the pending file is cleared. Chat pulse first,
   then analysis.
4. **O-DRV5 — comprehensive post-M analysis (script)** — after every new
   M1/M2/M3/M4/M5 completion (git subjects and/or outer-loop `OK END M*`),
   driver writes `tmp/V9-M-ANALYSIS-PENDING.md` and stays CRITICAL until a
   comprehensive freeze-and-review gate entry exists; clear via
   `tmp/V9-M-ANALYSIS.sha`. Do not advance to the next story/M on GREEN alone.
5. **Bank every durable gap** into `docs/V7-FUTURE-IMPROVEMENTS.md` (⬜) in
   the same analysis pass — never ask whether to bank.
6. **Implement open bank rows that block honesty** as soon as they are
   found (or HOLD until they are) — do not accumulate a backlog while the
   broken run continues.
7. **Abort / HOLD on false greens** — ceremonial commits, empty harvests,
   placeholder tests, wrong-title mechan commits, dishonest
   already-complete skips. Do not advance on sensor GREEN alone.
8. **Prefer fix + re-run over long compromised runs** — if the harness or
   delivery is dishonest, stop, bank, implement, wipe/resume cleanly.
9. **Keep driving** after ADVANCE; freeze on HOLD until fixes land; on
   ABORT, reset and implement open bank rows before restart.
10. **Temporary manual → durable → re-run** — hand edits may probe a
    hypothesis; after validation, implement in the harness/skills and
    re-run so the process (not the agent) owns the fix.
11. **MiniMax-over-Qwen escalations** — every takeover must get Qwen-log
    root-cause analysis, a durable harness/skill fix, and a retest that
    proves the worker path no longer needs MiniMax for that failure class.
    Do not treat “MiniMax committed GREEN” as closed.
12. **Migration-general durable fixes** — harness/skill/sensor changes must
    apply to any Spring Boot → Quarkus migration using this method. Use
    `migration.yaml` / brief / findings parameters; keep Coolstore specifics
    in story artifacts or named fixtures — not in the harness core.

#### What every gate must judge (crucial — not optional)

Sensors (compile/test/sonar) are necessary but **not sufficient**. Every
O-DRV3 / O-DRV5 review must critically judge:

1. **Quality of AI-generated code** — correctness vs legacy/brief, fidelity
   of harvest/rename, real tests (no placeholders), no ceremonial stubs,
   API/package honesty, maintainability, security-sensitive mistakes.
2. **Quality of AI actions** — did the worker/orchestrator/escalation/
   mechan/autofix path do the *right* work? Wrong-title commits, false
   “Already satisfied”, quota burns, scope violations, staging/harness
   sweeps, skipped characterization, dishonest evaluate/ship claims.
3. **Process performance** — wasted MiniMax seats, repeated sfix loops,
   style-autofix thrash, silent ticks, premature story advance.

Do not clear an O-DRV3/O-DRV5 pending file after a superficial GREEN glance.

#### Mandatory per-task checklist (O-DRV3)

1. `git show --stat` + full diff (bodies, not titles) — **read the code**.
2. Judge **AI-generated code quality** against task goal/acceptance/legacy.
3. Actor path + **AI action quality**: worker / mechan / O-ESCW / MiniMax
   escalation / style-autofix / sfix — was the action appropriate?
4. On RED / partial / sfix / escalation: supervisor + dimension logs
   (`/tmp/sensor-*.log`, `/tmp/sonar-violations.txt`, `/tmp/oc-T-*.err`).
5. Root cause, harness smells, process-performance waste.
6. Bank every durable gap NOW in `docs/V7-FUTURE-IMPROVEMENTS.md` (⬜).
7. Detailed entry in `docs/V9-QUALITY-GATE.md` (code quality / actions /
   why / bank / next).
8. Clear pending only after that write-up (`tmp/V9-TASK-ANALYSIS.sha` +
   delete `tmp/V9-TASK-ANALYSIS-PENDING.md`).

#### Gate cadence (script + docs)

| Gate | Enforced by | Clear by |
|------|-------------|----------|
| Chat pulse every 120s | **O-DRV4** script (`V9-CHAT-PULSE-PENDING`) | `V9-CHAT-PULSE.ack` |
| After each T-NNN | **O-DRV3** script (`V9-TASK-ANALYSIS-PENDING`) | `V9-TASK-ANALYSIS.sha` + gate entry |
| After each M1–M5 | **O-DRV5** script (`V9-M-ANALYSIS-PENDING`) | `V9-M-ANALYSIS.sha` + comprehensive gate entry |
| Before story ship / next story | skill + O-DRV5 story-complete detection | ADVANCE in `V9-QUALITY-GATE.md` |

Agentic (no human GO); default bias is HOLD when unsure. Do not treat
AGENTS prose alone as enforcement — if the script is not nagging, fix the
script.

## Coding and manifest style

General rules:

- Prefer clear, boring, maintainable changes.
- Preserve the stage-based workshop structure.
- Preserve GitOps idempotency.
- Prefer Kustomize overlays and existing patterns over one-off scripts.
- Do not introduce new tools unless the reason is documented.
- Do not rename resources casually; OpenShift and Argo CD resources may depend on names.
- Keep comments where they explain operational intent or known platform quirks.
- Do not remove workaround documentation unless the replacement behavior has been validated.

Shell scripts:

- Use `set -euo pipefail` where practical.
- Quote variables.
- Keep scripts repeatable.
- Prefer explicit error messages.

YAML and Kubernetes manifests:

- Preserve namespaces, labels, annotations, sync waves, and Argo CD ordering unless the task explicitly requires changes.
- Check RBAC, NetworkPolicy, AuthPolicy, RateLimitPolicy, and TokenRateLimitPolicy changes carefully.
- Treat gateway, auth, model access, and credential-related manifests as security-sensitive.
- Do not place real credentials in Git.

## Shared Skills

Canonical skills live in `.agents/skills/`, the shared tool-neutral skill discovery path. Keep skill folders flat and use the prefix plus `metadata.skill-group` taxonomy for skill review:

| Group | Prefix | Skills | Purpose |
|-------|--------|--------|---------|
| Project Structure | `project-*` | `maintain-rules-and-skills`, `prepare-pr-summary`, `project-demo-stage-authoring`, `project-documentation-authoring`, `project-red-hat-doc-skill-authoring`, `project-rhoai-doc-chapter-skill-authoring` | Governance, PR output, stage lifecycle, documentation structure, Red Hat docs-to-skill generation |
| GitOps & Manifests | | `review-gitops-change`, `review-manifest-compliance`, `review-doc-alignment` | Review changes, explain risk, verify compliance and doc alignment |
| Documentation | | `update-demo-docs`, `demo-operations-docs` | Keep docs aligned, author operational docs |
| Demo Environment | | `validate-demo-step`, `rhoai-troubleshoot`, `inspect-cluster`, `manage-devspaces`, `manage-resources`, `resume-gpu-demo`, `run-guidellm-load-test`, `workaround-review` | Deploy, validate, diagnose, scale |
| RHOAI Platform | `rhoai-*` | `rhoai-architecture-overview`, `rhoai-release-and-support-posture`, `rhoai-platform-planning`, `rhoai-api-tiers`, `rhoai-update-channels`, `rhoai-self-managed-installation`, `rhoai-dsci-dsc-configuration`, `rhoai-distributed-workloads`, `rhoai-kueue-workload-management`, `rhoai-distributed-workload-operations`, `rhoai-distributed-workload-workflows`, `rhoai-kubeflow-spark-operator`, `rhoai-nvidia-gpu-accelerators`, `rhoai-hardware-profiles`, `rhoai-certificate-management`, `rhoai-observability`, `rhoai-logs-and-audit-records`, `rhoai-installation-troubleshooting`, `rhoai-uninstallation`, `rhoai-users-groups-access`, `rhoai-access-group-selection`, `rhoai-central-authentication-service`, `rhoai-dashboard-applications`, `rhoai-connected-applications`, `rhoai-dashboard-customization`, `rhoai-cluster-pvc-size`, `rhoai-storage-classes`, `rhoai-connection-types`, `rhoai-s3-object-storage-data`, `rhoai-project-workflows`, `rhoai-data-science-ide-workflows`, `rhoai-project-scoped-resources`, `rhoai-component-resource-customization`, `rhoai-telemetry-admin-settings`, `rhoai-feature-store`, `rhoai-automl`, `rhoai-basic-workbenches`, `rhoai-workbenches-custom-images`, `rhoai-workbench-image-import`, `rhoai-workbench-gateway-api-migration`, `rhoai-model-serving-platform`, `rhoai-model-deployment`, `rhoai-maas-governance`, `rhoai-distributed-inference-llmd`, `rhoai-model-management-monitoring`, `rhoai-monitoring-trustyai`, `rhoai-model-catalog-sources`, `rhoai-model-catalog-workflows`, `rhoai-gen-ai-playground`, `rhoai-autorag`, `rhoai-enterprise-rag`, `rhoai-model-registry`, `rhoai-model-registry-workflows`, `rhoai-llama-stack`, `rhoai-ai-pipelines`, `rhoai-mlflow`, `rhoai-model-customization-training`, `rhoai-evaluation`, `rhoai-guardrails-safety`, `rhoai-chatbot-customization`, `rhoai-model-evaluation`, `rhoai-kfp-pipeline-authoring` | Official-doc-backed RHOAI 3.4 component installation, configuration, and usage |
| OpenShift Platform | `ocp-*` | `ocp-ai-workloads`, `ocp-authentication-identity-providers`, `ocp-cicd-builds`, `ocp-distributed-tracing`, `ocp-etcd`, `ocp-grafana-operator`, `ocp-gitops-operator`, `ocp-image-registry-and-mirroring`, `ocp-ingress-gateway-routes`, `ocp-machine-configuration`, `ocp-machine-management`, `ocp-node-feature-discovery`, `ocp-nodes`, `ocp-observability`, `ocp-opentelemetry`, `ocp-security-rbac-scc`, `ocp-storage`, `ocp-web-console` | Official-doc-backed OCP 4.20 infrastructure, networking, auth, monitoring, GitOps, and storage integration |
| OpenShift Dev Spaces | `ocp-devspaces-*` | `ocp-devspaces-about`, `ocp-devspaces-release-notes`, `ocp-devspaces-install`, `ocp-devspaces-admin`, `ocp-devspaces-user-guide` | Official-doc-backed OpenShift Dev Spaces 3.28 cloud development environments, DevWorkspace operator, CheCluster CR, and workspace management |
| OpenShift Lightspeed | `ocp-lightspeed-*` | `ocp-lightspeed-about`, `ocp-lightspeed-release-notes`, `ocp-lightspeed-install`, `ocp-lightspeed-configure`, `ocp-lightspeed-operate`, `ocp-lightspeed-troubleshoot` | Official-doc-backed OpenShift Lightspeed 1.0 AI assistant, LLM provider configuration, OLSConfig CR, RBAC, and troubleshooting |
| OpenShift Pipelines | `ocp-pipelines-*` | `ocp-pipelines-release-notes`, `ocp-pipelines-about`, `ocp-pipelines-install-config`, `ocp-pipelines-performance`, `ocp-pipelines-security`, `ocp-pipelines-observability`, `ocp-pipelines-as-code`, `ocp-pipelines-cicd`, `ocp-pipelines-tekton-hub`, `ocp-pipelines-cli-reference` | Official-doc-backed OpenShift Pipelines 1.22 CI/CD, Tekton, Pipelines as Code, supply chain security, and observability |
| OpenShift Data Foundation | `odf-*` | `odf-storagecluster`, `odf-storage-classes`, `odf-object-bucket-claims`, `odf-multicloud-gateway` | Official-doc-backed ODF storage, object storage, Ceph, NooBaa, and storage class guidance |
| Advanced Developer Suite SSC | `rhads-*` | `rhads-about`, `rhads-release-notes`, `rhads-getting-started`, `rhads-standalone-clis`, `rhads-install`, `rhads-cicd-azure`, `rhads-cicd-github`, `rhads-cicd-gitlab`, `rhads-cicd-jenkins`, `rhads-cicd-tekton`, `rhads-customize`, `rhads-sbom`, `rhads-compliance` | Official-doc-backed RHADS-SSC 1.9 Trusted Application Pipeline: concepts, installation, CI/CD integrations (Azure/GitHub/GitLab/Jenkins/Tekton), SBOM inspection, and Conforma compliance |
| Connectivity Link | `rhcl-*` | `rhcl-about`, `rhcl-mcp-gateway`, `rhcl-release-notes`, `rhcl-install`, `rhcl-install-mcp`, `rhcl-configure`, `rhcl-mcp-config`, `rhcl-observability`, `rhcl-troubleshoot`, `rhcl-update` | Official-doc-backed RHCL 1.3 (1.4.0 deprecated) Connectivity Link and MCP gateway: concepts, installation, deployment, auth/rate-limit policies, MCP server registration, observability, troubleshooting, and upgrades |
| Trusted Profile Analyzer | `tpa-*` | `tpa-release-notes`, `tpa-quick-start`, `tpa-deployment`, `tpa-admin` | Official-doc-backed RHTPA 2.2 SBOM analysis, vulnerability scanning, deployment (RHEL/OpenShift/Helm), and administration |
| Migration Toolkit for Applications | `mta-*` | `mta-release-notes`, `mta-install`, `mta-lightspeed`, `mta-cli`, `mta-ui`, `mta-vscode`, `mta-intellij`, `mta-rules` | Official-doc-backed MTA 8.1 application modernization: release notes, installation, Developer Lightspeed AI, CLI/UI/VS Code/IntelliJ analysis tools, and custom rule development |
| Developer Hub | `rhdh-*` | `rhdh-about`, `rhdh-release-notes`, `rhdh-preview-features`, `rhdh-getting-started-setup`, `rhdh-getting-started-navigate`, `rhdh-install-ocp`, `rhdh-install-aks`, `rhdh-install-eks`, `rhdh-install-osd-gcp`, `rhdh-install-gke`, `rhdh-install-airgapped`, `rhdh-upgrade`, `rhdh-configure`, `rhdh-customize`, `rhdh-techdocs-config`, `rhdh-authentication`, `rhdh-authorization`, `rhdh-git-integration`, `rhdh-developer-lightspeed`, `rhdh-mcp-tools`, `rhdh-openshift-ai-connector`, `rhdh-develop`, `rhdh-techdocs-manage`, `rhdh-adoption-insights`, `rhdh-audit-logs`, `rhdh-monitoring`, `rhdh-telemetry`, `rhdh-scorecards`, `rhdh-diagnostic-data`, `rhdh-orchestrator`, `rhdh-dynamic-plugins-develop`, `rhdh-dynamic-plugins-install`, `rhdh-dynamic-plugins-usage`, `rhdh-dynamic-plugins-reference`, `rhdh-dynamic-plugins-configure`, `rhdh-helm-reference` | Official-doc-backed RHDH 1.10 developer portal: concepts, installation (OCP/AKS/EKS/GKE/OSD/air-gapped), upgrade, configuration, customization, authentication, authorization, Git/AI/MCP integration, development workflows, observability, dynamic plugins, orchestrator, and Helm reference |
| Assets & Miscellaneous | | `red-hat-quick-deck` | Red Hat-aligned presentations |

Skills are invoked workflows. Rules are always-on behavior constraints.

## Subagents

No shared subagents are currently tracked. Add tool-specific subagents only for genuinely tool-specific context isolation needs; shared workflows belong in `.agents/skills/`.

## Stage deployment skill map

When deploying, validating, or changing a stage, consult the matching doc-grounded skills BEFORE making decisions; their doc-backed procedures are authoritative for Red Hat alignment, while repo-specific defaults live in the stage READMEs:

| Stage | Primary skills |
|-------|----------------|
| 010 foundation | `rhoai-self-managed-installation`, `rhoai-dsci-dsc-configuration`, `rhoai-update-channels`, `rhoai-users-groups-access`, `rhoai-observability`, `ocp-gitops-operator`, `ocp-authentication-identity-providers`, `odf-multicloud-gateway`, `odf-object-bucket-claims` |
| 020 GPU infra | `rhoai-nvidia-gpu-accelerators`, `rhoai-hardware-profiles`, `rhoai-kueue-workload-management`, `rhoai-distributed-workloads`, `ocp-machine-management`, `ocp-node-feature-discovery` |
| 030 serving | `rhoai-model-serving-platform`, `rhoai-model-deployment`, `rhoai-model-registry`, `rhoai-model-registry-workflows`, `ocp-grafana-operator` |
| 040 MaaS | `rhoai-maas-governance`, `rhoai-distributed-inference-llmd`, `rhoai-gen-ai-playground`, `rhoai-model-catalog-sources`, `ocp-ingress-gateway-routes` |
| 050 advanced platform | `rhoai-data-science-ide-workflows`, `rhoai-gen-ai-playground`, `manage-devspaces`, `rhdh-getting-started-setup`, `rhdh-getting-started-navigate`, `rhdh-dynamic-plugins-reference`, `rhdh-dynamic-plugins-configure`, `rhdh-dynamic-plugins-install`, `rhdh-dynamic-plugins-usage`, `rhdh-helm-reference`, `ocp-authentication-identity-providers`, `ocp-web-console` |
| 060 assisted dev | `rhoai-maas-governance` (key consumption), `manage-devspaces` |
| 070 agentic dev | `rhoai-maas-governance`, workspace-repo skills |
| 080 migration | `rhoai-maas-governance`, `ocp-authentication-identity-providers` (Keycloak), MTA product docs, `stage-080-quality-advance` (Track B advance gate) |

Skill project-default sections were authored in rhoai3-demo; where this repo deliberately diverges (no GPU time-slicing, two GPU workers, two private models), the stage README is the source of truth and the skill defaults have been updated to match.

## Validation expectations

Use the most specific validation possible.

Examples:

```bash
bash -n scripts/*.sh
bash -n stages/*/*.sh
./scripts/validate-stage-flow.sh

./stages/010-openshift-ai-platform-foundation/validate.sh
./stages/020-gpu-infrastructure-private-ai/validate.sh
./stages/030-private-model-serving/validate.sh
./stages/040-governed-models-as-a-service/validate.sh
./stages/050-advanced-app-platform/validate.sh
./stages/060-ai-assisted-development/validate.sh
./stages/070-ai-agentic-development/validate.sh
./stages/080-ai-autonomous-migration/validate.sh
```

Stage 070 consumes the Stage 060 Dev Spaces platform and Stage 050 Developer Hub assets; its skills content lives in an external repository, so beyond its validate script use `./scripts/validate-stage-flow.sh` and any specific commands documented in the Stage 070 README when a live workspace and cluster are available.

If validation requires a live OpenShift cluster and one is not available, do not pretend validation passed. Say:

> Not validated against a live cluster. Static review only.

## Pull request output expected from agents

When asked to prepare a PR summary, use this format:

```markdown
## Summary
## Why
## Changed files
## Validation
## Risk
## Rollback
## AI assistance
Tool/model used:
Human review performed:
```
