# Stage 060 agent runtime and AgentOps design proposal

**Status: researched proposal for review. No deployment or implementation is authorized by this document.** Stage 060 would host agent runtimes and AgentOps; Stage 070 supplies developer services, SCM and templates. Stages 110/120/130 consume these separate platform layers. Existing Stage 030 catalogs, Stage 040 MaaS and Stage 050 EvalHub/MLflow keep their ownership and data. Current model/GPU state is unchanged.

## Recommendation

Start with **one persistent logical agent instance per provisioned workspace/project working set**, outside the Dev Spaces Pod. Its identity, session/board state, repository association and result history survive workspace stop/start. A sandbox process may restart or suspend; this must not recreate its logical identity or reset its board on every workspace start. Use one shared OpenShell gateway/control plane with separate agent Sandbox resources, not one gateway per workspace.

A workspace-associated Hermes instance gives each project isolated state and scoped credentials, lets bounded work continue while the IDE is stopped, and preserves sessions for later resumption. A reproducible image/toolchain makes results easier to compare, while project-bound MaaS usage and MLflow evidence connect consumption to actual task outcomes.

Developer Hub provisions the working set and links its IDE, agent and repository. Dev Spaces remains the editor/client. First qualify standalone OpenCode, for which a Red Hat starter kit exists; then qualify Hermes as a custom integration using the same project isolation and Git contract. Keep the existing Hermes verifier and task evidence rather than rebuilding a generic agent framework.

Use **separate Git checkouts and explicit commit/patch exchange**. Freeze a start commit, allow the agent to write only its task branch/checkout, and review its patch before merging. Do not share one writable working copy between IDE and agent: concurrent edits, Git locks, RWO scheduling and per-user workspace storage make that unsafe. Unsaved IDE edits require an explicit upload/commit workflow; HTTP prompting does not synchronize them.

## Current → target and ownership

| Component | Current concrete source | Proposed change |
|---|---|---|
| Stage 070 Dev Spaces | CheCluster per-user PVC; workspace-local tooling and `/projects` | retain IDE/storage; add authenticated client links, no embedded long-lived agent process |
| Stage 070 RHDH migration template | `templates/app-migration/template.yaml` fetches golden source, publishes GitHub destination, registers catalog entity and creates workspace link | provision a persistent agent association separately; keep explicit task/repo pins and lifecycle ownership |
| Stage 120 OpenCode | scaffold instructions/skills and workspace-managed config | standalone scoped OpenCode server/sandbox; qualify pinned client/server protocol and credentials |
| Stage 130 Hermes | local Kanban dispatcher/worker launcher, state at `/projects/modernized/.hermes/home`, legacy readonly and destination writable | preserve workflow/independent verifier; relocate into standalone sandbox after path/process/security qualification |
| Stage 070 SCM | GitHub-specific publisher, catalog URLs, webhook interceptor/provisioner and scripts | requested Gitea for workload repositories; keep platform GitHub Argo sources unchanged to avoid circular bootstrap |
| Stage 030/040/050 | catalog discovery / governed inference / evidence services | reuse; no catalog hosting assumption, universal trace sink or ownership move |

## OpenShell 0.1 target and support gates

Agent Catalog is discovery (Developer Preview); it is not a provisioning controller. The native running-agent view can list manually deployed Sandbox resources. [RHOAI 3.5 feature notes](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/release_notes/developer-preview-features_relnotes).

**Selected upstream release target: [NVIDIA OpenShell v0.1.2](https://github.com/NVIDIA/OpenShell/releases/tag/v0.1.2)**, a stable release (not prerelease), source commit `6648bd0c290efbc41ba131ee9831ee45cd431f94`. Pin gateway/CLI/chart to this release and verify corresponding image digests before implementation. The older Red Hat-linked examples below are compatibility history, not the selected deployment default. Neither a mutable development page nor a floating `0.1` range is a reproducible release pin. This is the requested upstream integration target, not an assertion of an installed Red Hat 3.5-supported 0.1 operator. The requested RHOAI 3.6 Technology Preview/module-operator direction is recorded as roadmap, not a released 3.5 capability or verified support commitment.

Pinned v0.1.2 source provides gRPC fleet lifecycle/policy/watch/log APIs, relay execution/file synchronization/service forwarding and gateway database state. These are usable integration building blocks, not automatic workspace association, Git conflict handling, agent board persistence or MLflow instrumentation. Preserve the tagged `allowUnauthenticatedUsers: false` default and configure the reviewed OIDC issuer/audience; older guide anonymous defaults must not be carried forward. Optional SPIFFE provider-token grants are disabled by default and are not the default sandbox identity; supervisors use gateway JWT and Kubernetes ServiceAccount bootstrap. Do not present SPIFFE or tenant isolation as automatic merely by choosing 0.1. Version 0.1 removed the older managed inference routing path: integrate the existing MaaS OpenAI-compatible endpoint through an approved provider proxy and scoped MaaS key, rather than copying legacy inference-routing fields.

The pinned [agent-ops guide](https://github.com/opendatahub-io/agent-ops/blob/7230605c8c0a4cec41c3e39e52e521db5c941355/guides/getting-started-openshell-openshift.md) uses Agent Sandbox 0.9.0 and OpenShell 0.0.116. The [OpenCode starter kit](https://github.com/red-hat-data-services/agentic-starter-kits/blob/b6b69cc0fc7b36c8415f7756f0d6ecb3a19cbd1d/agents/opencode/README.md) describes a different tested gateway/CLI/OpenCode tuple (0.0.86/0.0.58/1.17.1). Examples include privileged SCC and unauthenticated access and explicitly are not safe shared-cluster defaults. Do not copy them unchanged.

NVIDIA's newer [OpenShift development guide](https://docs.nvidia.com/openshell/dev/kubernetes/openshift) documents nonroot namespace-allocated UIDs without privileged SCC, but requires actual seccomp/Landlock startup probes and enforcing ingress/egress NetworkPolicy. This development contract must be checked against the chosen 0.1 release; it is not proof for the older Red Hat-pinned tuple. Select and pin one combination, verify its kernel/runtime/controller compatibility, and surface any required security expansion before implementation.

Hermes source is a local fork: base `fcbd1076a93841fa88855acce810e342a5b78101` (0.20.5), 21 patches, patched tree `9e5b79b9583d7aef515e8866eba993eb96679f4b`. RELEASE records published image `sha256:5aab5558481fcbb69483122543b7bcb96b9c34daf44466eea6d375fd37c92029`; runtime README has stale not-built wording. Image stamps must settle the actual selected runtime. Current upstream [Hermes HTTP API](https://hermes-agent.nousresearch.com/docs/user-guide/features/api-server) documents Runs/status/events/stop/approval and agent execution, but these are **not established capabilities of this pinned fork**. Perform a bounded upgrade/patch-retirement assessment before relying on them. No A2A capability is assumed.

Current [OpenCode HTTP server](https://opencode.ai/docs/server/) documents sessions, file/VCS access, SSE and basic authentication. It executes against the server's checkout; identity federation and tenant isolation still need deployment design. The repository image pins OpenCode 1.18.16; qualify that version rather than assuming current docs apply unchanged.

## Developer platform integration

Stage 070 owns Gitea, Dev Spaces, RHDH templates and developer delivery. Qualify its SCM before final template integration; Stage 060 runtime does not require a particular IDE or portal. See the [Stage 070 developer platform and SCM proposal](070-developer-platform-and-scm-plan.md).

## Kubernetes versus per-user VM runtime

The requested [Secure Agent Workspace pattern](https://github.com/validatedpatterns-sandbox/secure-agent-workspace/tree/3f02cba94cf7681ec232d105f9e4c5c9e5553717), pinned at `3f02cba94cf7681ec232d105f9e4c5c9e5553717`, is an alternative isolation topology: a dedicated OpenShift Virtualization VM per user, with an OpenShell gateway and agent inside each VM. Its bootc/CDI image and Vault/External Secrets/Keycloak wiring are not the same as Kubernetes Sandboxes under one shared gateway. Its default VM is 4 CPU/8 GiB/40 GiB, with rootless Podman inside Fedora 44. Its BOM selects OpenShell `0.1.2-rhaiv.0` ODH image digests, a custom interceptor patch and a 3.6 early-access package index; that is not identical to unmodified upstream v0.1.2. It also installs RHOAI and RHDH fast channels wholesale, so it must not be overlaid on this existing 3.5 environment. OIDC/mTLS are documented, but the pattern defaults Landlock to `best_effort` and image verification to `warn`; its custom interceptor uses insecure HTTP, and no general per-user VM default-deny egress or unified trace pipeline was established. The reference therefore does not itself prove fail-closed enforcement of every control. No SPIRE deployment was found. Hermes/OpenCode remain separate qualification work rather than supplied specific adapters. A per-VM gateway follows that pattern; it does not imply one gateway per Dev Spaces workspace in the recommended Kubernetes topology.

| Topology | Benefit | Prerequisites and cost/lifecycle implications |
|---|---|---|
| Shared Kubernetes OpenShell control plane, separate agent Sandboxes — proposed first proof | fits project-scoped runtime ownership and avoids a guest OS per agent | exact v0.1.2 driver/SandboxCRD tuple, real seccomp/Landlock and CNI enforcement, scoped identities/persistence; controller and sandbox CPU/storage costs still apply |
| Secure Agent Workspace per-user VM | guest-kernel boundary, user-owned runtime independent of IDE, image-based reprovisioning | OpenShift Virtualization and virtualization-capable CPU capacity (including qualification of supported AWS bare-metal substrate if used), guest image/CDI storage, bootc pipeline and reviewed secrets/OIDC services; per-user VM CPU/RAM plus gateway/agent idle cost; suspend/stop and durable disks need explicit policy |

Reuse its image/policy/identity/lifecycle ideas where they fit, not its full deployment tree or assumptions. Keep Gitea and Git exchange in either topology. Do not add Vault/ESO or a second identity realm merely because the reference includes them; map existing approved services first. No additional host provisioning is authorized by this proposal. VM isolation complements, rather than replaces, least-privilege tool/egress/credential controls. No live cost, throughput or compatibility claim is made here.

## Lifecycle alternatives

| Unit | Advantages | Costs and risks |
|---|---|---|
| Workspace/project-associated logical instance — first choice | clear repo/task scope, independent IDE lifecycle, direct attribution | explicit stable association/owner, pause/cancel semantics and retained state required |
| Per-user persistent instance | cross-workspace memory/session continuity, fewer idle servers | secrets/context crossover and concurrency; isolated per-task sandboxes still needed |
| Shared project/team instance | durable team queue, less controller overhead | attribution, approvals and concurrent checkout ownership; never one broad shared credential |

Workspace stop must preserve the logical agent instance. An explicit project policy chooses pause/cancel or continued background execution; continued work retains an enforced deadline, tool/token budget, credential expiry and visible cancellation control. Stopping the IDE alone must not silently cancel an approved background task or create an unlimited autonomous job. Deleting a workspace must not silently delete retained agent state/results: archive results and revoke owned credentials, then apply the reviewed retention policy. Agent control state and disposable execution are distinct. No additional GPU is required in the agent; CPU/storage/idle runtime cost and MaaS inference usage are separate.

## Trace and acceptance boundaries

MaaS supplies governed model access and aggregate attribution, not internal shell/planning/file trajectories. OpenShell identity, policy and tool-access records do not automatically instrument Hermes internal planning, memory, Kanban semantics or every delegated tool trajectory. Hermes/OpenCode tracing requires explicit instrumentation and redaction; existing MLflow may record bounded pilot evidence through its established tenant contract. Catalog metadata and Studio's embedded trace viewer do not prove universal trace persistence. The independent verifier remains outside the agent's writable scope. Compile, actual tests, API parity, workflow completion and autonomous-agent success are separate results.

## Minimum proof and implementation phases

1. **Resolve pins/security first:** selected Sandbox/OpenShell/chart/runtime tuple, nonroot enforcement, filesystem and network denies, TLS/authenticated ownership and no anonymous tool API.
2. **One standalone OpenCode slice:** one owner/project/repo, frozen commit and separate checkout, existing governed Qwen3.8; prove foreign identity denial, scoped credentials, one bounded edit, actual cancellation, restart continuity and independent verifier results.
3. **Hermes continuity:** qualify image/patch obligations (loop/output controls, pacing/budgets, lifecycle, preload receipts, escalation, context ceiling); prove native Kanban review/change semantics inside the sandbox before remote protocol integration. Keep planner activation gated until the real task oracle is ready.
4. **Gitea qualification and transition:** qualify chart/module/webhook/bootstrap/backup before final template integration, then migrate workload-repo consumers coherently; never repoint platform Argo sources or overwrite existing repos. The early OpenCode proof may use an existing read-only source repository and a separate disposable checkout, avoiding an initial template rewrite.
5. **RHDH/lifecycle integration:** integrate the qualified Gitea publisher and reviewed agent provisioner/association once, add catalog description and template links, and test workspace stop/start/delete with no orphan jobs/keys or lost results. No blind recreate-on-start.

**Catalog publication gate:** confirm the installed Agent Catalog custom-source/entry contract before authoring Hermes or OpenCode metadata. Link a versioned starter-kit/runtime source and state its actual support boundary; Hermes remains a project custom integration. Catalog registration describes the qualified runtime and launch instructions, and does not install or host it. An RHDH catalog entity/link is distinct from a RHOAI Agent Catalog entry and does not satisfy that prerequisite. The installed custom-source mechanism and served schema remain unresolved; no catalog CR fields are proposed here.

Required review decisions: selected support/security tuple; retained instance/state lifecycle; Git exchange and merge authority; Gitea module/chart qualification. No deployment follows from this proposal. Detailed read-only audit: `/private/tmp/agent-platform-research/repository-runtime-lifecycle.md`.
