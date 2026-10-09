# Stage 060 AI Agents Continuation Handoff

**Prepared:** 2026-10-09, 13:28 UTC. **Last updated:** 2026-10-09, 15:30 UTC, continuation checkpoint (section 10). **Scope:** the AI Agents portion of Stage 060, including the next owner-client and selected-call MLflow tracing milestone. This is a continuation checkpoint, not a full-stage acceptance report. No cluster commands, model requests or deployments were run while writing it.

The persistent OpenCode and Hermes deployments have passed their bounded runtime qualifications. The human owner has now visually confirmed **both Ready/Sandboxed** under **AI hub → Agents → Deployments → AI Agents**, signed in as `ai-admin`. The next slice is committed, reviewed source: an owner-only client and explicit selected-task MLflow traces in `9851b7aaafe927e8ecf791feadd9e49534816176`. Its source review and offline tests passed. Its isolated live candidate, MLflow permission grant, experiment, client tasks and stored trace readback are **complete** as of the section 10 checkpoint. Stage 060 remains incomplete. Stage 070 developer workspaces and portal integration are separate later work.

## 1. Resume At This Checkpoint

| Item | Last verified or reported state |
|---|---|
| Repository | `rhoai3-coding-demo`; origin `git@github.com:adnan-drina/rhoai3-coding-demo.git` |
| Active checkout | `/Users/adrina/.codex/worktrees/platform-foundation-35/rhoai3-coding-demo` |
| Source branch | `codex/stage-010-foundation-35` |
| Accepted deployed-agent implementation snapshot | `77e1c2a627e31be7754776d7a85cc2d69fef2649` — locally verified initial snapshot |
| Committed client/tracing implementation (before report-only commit) | `9851b7aaafe927e8ecf791feadd9e49534816176`, parent `aa6a578bc6456ad0ea7af51d0a7b997f5daa43f8` (concurrent MCP source/docs). Preserve ancestry; neither changes the live agent runtime |
| Live `openshell-runtime` revision | `07a29a299fd6ed6c8da3aa5ce35a82a1a15dc74f` (two RBAC operands added on `3a65ec3c…`; see section 10) |
| Live Stage 030/catalog revision | `dd08961d64c14c327ecfeeed1ab7683fe868bb6b`; tag `stage030-hermes-qualified-20261009` — operator checkpoint |
| Current client/tracing candidate revision | `07a29a299fd6ed6c8da3aa5ce35a82a1a15dc74f` (tag `stage060-client-traces-k8s-pin-20261009`), parent `ff92a7550e8bdfb96629abc7eab1797d61ec4c47` (tag `stage060-client-traces-20261009`) on the retained runtime `3a65ec3c…`; see section 10 |
| Platform | OpenShift Container Platform 4.22; Red Hat OpenShift AI 3.5.1 |
| Active agents | Native `opencode` and `hermes`, workspace and namespace `ai-agents` |
| Current command sessions | None running at the final operator checkpoint |
| Full-stage validator | `validate.sh` deliberately reports `[PENDING]` and exits 2; individual qualification success does not change that |
| Developer workspaces | Zero current DevWorkspaces and no Stage 070 Application at the parent checkpoint; not independently rechecked for this document |

The primary checkout `/Users/adrina/Sandbox/rhoai3-coding-demo` is used only as the authoritative environment-root input. Do not modify it to resume this task. There are concurrent unrelated edits in the active worktree, including foundation/Lightspeed, GPU probes and migration documentation. Existing changes to `BACKLOG.md`, `docs/OPERATIONS.md`, Stage 060 README/plan and runtime Kustomization also contain work from other owners. Do not reset, clean, bulk stage or bulk restore them. Inspect the complete diff, assign file or hunk ownership, and publish only this slice. A human must review the full contribution and retain responsibility; disclose AI assistance and do not add a human sign-off.

### Prepared public-source recovery archive

Before the implementation commit, the operator saved an owner-only archive of the prepared client milestone. It remains an immutable historical recovery checkpoint:

- Archive: `/private/tmp/060-agent-handoff/prepared-public-source-20261009-v2.tar.gz`
- **Current SHA-256:** `e7cf5e65512b6f29c69e323de703059ed97d133749515f832435f060256c078b`
- Manifest: `/private/tmp/060-agent-handoff/prepared-public-source-v2/MANIFEST.json`
- Receipt: `/private/tmp/060-agent-handoff/archive-receipt-v2.json`

The directory is mode 700 and archive mode 600. Its twelve public files are `owner-client.py`, `client-requirements.txt`, `selected_task_trace.py`, their two focused test files, runtime `kustomization.yaml`, three `client-traces` YAML files, Stage 060 README, the Stage 060 plan and Operations. Operations was reconstructed from HEAD plus only the two owned visual-acceptance sentences; unrelated dirty sections were excluded. No credentials, environment file, kubeconfigs, private journals or other working-tree dirt are included. This immutable v2 archive includes the final purpose-based experiment/span naming correction. The original `prepared-public-source-20261009.tar.gz` archive remains untouched and superseded; use v2 to resume. Neither archive contains this later handoff document.

On recovery, inspect the manifest and verify the archive hash first. Compare each archived file with the current worktree. Recover only files that are absent or demonstrably lost, into a reviewable staging directory first. Never extract the archive over the worktree wholesale. The archive is public-source recovery, not a backup of runtime PVCs or private operator dependencies.

## 2. What Is Configured

### Control Plane, Project And Identity

The OpenShell gateway/control plane remains in `openshell`. The **AI Agents** OpenShift project `ai-agents` is the separate hosting boundary, mapped one-to-one to native workspace `ai-agents`. The selected Agent Sandbox controller accepts the reviewed namespaces; generic cross-namespace creation is not the deployment method. Existing `openshell-admin` and `openshell-developer` workspaces retain their independent memberships.

`rhods-admins` administers the OpenShift AI Agents project. The genuine `ai-admin` identity is its sole native workspace administrator. It has native `openshell-user`, not platform-wide `openshell-platform-admin`. Native OIDC uses the Keycloak `openshell` realm, the verified OpenShift identity broker and immutable subject binding. The gateway relay uses native authenticated TLS/OIDC forwarding. `ai-developer` receives no shared native workspace membership, hosting-project access, listener credentials or owner session.

This access choice is deliberate. At the selected OpenShell pin, native `user` provides workspace-wide sandbox create/use/delete. Relay and SSH-session creation require `sandbox:write` and `user`; there is no supported consume-only relay role. The first client slice therefore uses the genuine owner. Developer shared membership or a custom proxy would change the authority boundary and requires a separate design. This slice adds neither.

Admitted workloads use `openshell-sandbox`, no automatically mounted service-account token and `restricted-v2` admission. Qualification checks the exact actual Pod image, service account/SCC, native readiness, owned Kubernetes Sandbox UID, Bound PVC UID and mounted claim. A Running/Ready Pod alone is insufficient: the native Sandbox phase must also be Ready before native execution.

### Exact Version And Image Provenance

| Component | Selected pin and purpose |
|---|---|
| OpenShell source | `12cec59bf4c36c305032143eb90870bd16d8820b`, upstream PR 4150 merge; runtime reports `0.1.3-dev.99+g12cec59bf` |
| Helm chart | `oci://ghcr.io/nvidia/openshell/helm-chart`, version `0.0.0-dev.12cec59bf4c36c305032143eb90870bd16d8820b`; OCI digest `sha256:c96f4a2444a46679ca70b398308e97120834a70e71154a6c8a9ac208897ab8b8` |
| Pinned CLI | Artifact `11390640802`; executable SHA-256 `6323f7749fd6291bb3c96d13a54274c01a84f3f9f509dba5800fa5d2e1424c42`; ZIP SHA-256 `8ba077cd95dd708a3e45a2049460c812ded4c72ff29dea0ddc4a0db18a94b154` |
| Gateway amd64 | `sha256:437777e61c20707f9f06dc2b4b8a89b6c95a0b521dec9b00b3829d259fef163d` |
| Supervisor amd64 | `sha256:0783c6e10a0ec6871af1698d861cc1542f6ac5c4dd2ed2e550bb66250d82cc02` |
| OpenShell sandbox base amd64 | `sha256:ecac6542c16de6849c0a279020edcae2390025c90344afb813f0793fc6932167` |
| Agent Sandbox operator | Package `agent-sandbox-operator`, channel `preview-0.9`; qualified starting CSV `agent-sandbox-operator.v0.9.0` |
| OpenCode | 1.18.16, source `a3647eb025c7615159d417dcc49fc39fdaeba65b`; hosted image `image-registry.openshift-image-registry.svc:5000/ai-agents/opencode-runtime@sha256:86922260052003a80883880b40fa4245ae7645b25a4ee5f988ec7f1daca93d09` |
| Hermes base | Upstream `fcbd1076a93841fa88855acce810e342a5b78101` / v2026.8.19 / 0.20.5; Stage 130 patched tree `9e5b79b9583d7aef515e8866eba993eb96679f4b` |
| Hermes published base image | `quay.io/rhoai3-coding-demo/rhoai3-ws-080@sha256:5aab5558481fcbb69483122543b7bcb96b9c34daf44466eea6d375fd37c92029` |
| Hermes Stage 060 derivative | `image-registry.openshift-image-registry.svc:5000/ai-agents/hermes-runtime-api@sha256:b20974ad1bd66f081a48455458f1a7e9f882efa882bbbfb173f94d395a32116c` |

Complete chart/archive/attestation inputs live in [source-pins.json](../../gitops/stages/060-agent-runtime-and-agentops/runtime-candidate/source-pins.json). Native Automatic operator approval follows selected rolling channels; historical CSVs are qualified baselines, not immutable future operator-installation pins. Recheck compatibility before a fresh deployment. RHOAI 3.5 OpenShell and Agent Catalog integration are **Developer Preview**. The chosen upstream development build is not a tagged production-supported RHOAI runtime.

OpenCode uses the pinned baseline Linux x64 asset, bundled Bun 1.3.14 and the reviewed UBI image. The older OpenShell read-only socket writeback behavior prevented the Bun server from starting; PR 4150 corrected the runtime behavior. The solution retained enforcement rather than relaxing the filesystem policy. See the image source inputs, not a floating upstream image or latest starter kit.

Hermes retains the Stage 130 release's 0001–0021 patch set. Its historical image/stamp names contain `080`; they are provenance identifiers, not a relocation of Stage 130. The base had native API/CLI imports and YAML but lacked `aiohttp`. The derivative adds pinned `aiohttp==3.14.3` and its hashed, offline dependency closure: `aiohappyeyeballs 2.7.1`, `aiosignal 1.4.0`, `attrs 26.1.0`, `frozenlist 1.8.0`, `multidict 6.9.1`, `propcache 0.5.4`, `yarl 1.25.1`; existing `idna 3.20` and `typing_extensions 4.16.0` remain unchanged. Source and patch stamps are verified before and after packaging.

The derivative replaces only `/opt/hermes-venv/bin/python3.11`'s symlink with a byte-identical physical ELF. Interpreter SHA-256 is `8b10834091fce423fa1a256c115fd705c1bd327083c61069b0000249383aee9e`. Actual `/proc/self/exe` readback proved this private path; `/usr/bin/python3.11` has no model-network authority. This avoids granting shared system Python the MaaS allow rule. Native API source was unchanged. Provenance is checked at `/opt/rhoai3/080.pins` and `/opt/rhoai3/hermes-api/packaging-evidence.json`. The Dockerfile, wheel hashes and interpreter contract are in `stages/060-agent-runtime-and-agentops/images/hermes-api/`.

### Agent Configuration And API Differences

Both agents are named, persistent native Sandboxes with separate owned storage, 1 CPU/1 GiB template limits and work under `/sandbox/workspace`. They use the exact model `publishers/internal-models/models/qwen3-8-27b-int4`, named runtime provider `qwen38`, and 1024 per-call output tokens. They are not migration workers or shared Dev Spaces checkouts. Coding-tool proof covers local file and terminal tools. The approved Sandbox network policy admits only the scoped MaaS chat request; it does not permit Git/Gitea cloning, MCP calls, or MLflow export from inside either agent. Git checkout provisioning/exchange and external tool egress/auth require separately qualified integrations. Selected MLflow export runs in the external owner client.

| Contract | OpenCode | Hermes |
|---|---|---|
| Native model provider | `opencode-maas-qwen38` | `hermes-maas-qwen38` |
| Dedicated MaaS subscription | `opencode-private-qwen38` | `hermes-private-qwen38` |
| Listener | Loopback `127.0.0.1:4096`; Basic user `opencode`, private password | Loopback `127.0.0.1:8642`; private Bearer API key |
| Readiness/auth | Authenticated `/global/health`; absent/wrong Basic yields 401 | `/health` is public; protected `/health/detailed` is the auth gate; absent/wrong key yields 401 |
| Bounded agent work | Build steps 4, sharing/update/model fetching/web fetch disabled | Max turns 4, file/terminal API toolsets, local terminal cwd workspace, title/background review disabled |
| Approval semantics | Bash permission asks; approve only the exact reviewed fixed test command once | Native manual approvals apply to commands Hermes flags as dangerous; do not claim every command asks |
| Native cancellation | `POST /session/{id}/abort`, then observed application idle/abort evidence | `POST /v1/runs/{id}/stop` returns `stopping`; actual terminal `cancelled` and `run.cancelled` event required |
| Durable state | Saved HOME/XDG state under `/sandbox/state` | `HOME=/sandbox/state`, `HERMES_HOME=/sandbox/state/hermes`; sessions in `state.db` |

Hermes starts through the existing native console script using the private ELF and `gateway run --external-supervisor`. `security.allow_lazy_installs: false` prevents runtime dependency installs; `security.tirith_enabled: false` matches the selected release. Its native sessions/runs/SSE/stop APIs are used directly; no custom agent adapter was added. Its active HTTP run tasks, statuses and event queues are in-memory. A restart preserves session history, not an active run's continuation. A retained session ID does not prove the native run API automatically reloads prior conversation; verify the explicit history-loading/request contract before continuing a migration conversation. OpenCode session history likewise must be read back explicitly.

### Complete Gateway-Global Policy

The active policy is the complete global authority in [global-policy.yaml](../../stages/060-agent-runtime-and-agentops/runtime/global-policy.yaml). It is not a floor underneath freely editable per-Sandbox policies. An active global policy blocks per-Sandbox policy updates. The owner approved the change subject to alignment with official recommendations; the final complete scope and private-interpreter choice were independently reviewed. This is a tested project recipe, not a certified Red Hat Hermes deployment recipe.

- `include_workdir: false`; Landlock compatibility `hard_requirement`.
- Read-only: `/usr`, `/bin`, `/lib`, `/lib64`, `/etc`, `/proc`, `/dev/urandom`, `/dev/random`, `/opt/hermes-agent`, `/opt/hermes-venv`, `/opt/rhoai3/080.pins`, `/opt/rhoai3/hermes-api/packaging-evidence.json`.
- Writable: `/sandbox`, `/tmp`, `/dev/null`.
- Network rule keys `opencode_maas` and `hermes_maas` allow only the exact current common MaaS host on port 443, inspected REST with enforcement `enforce`, **POST `/v1/chat/completions`**.
- Authorized executable paths are only `/usr/local/bin/opencode` and `/opt/hermes-venv/bin/python3.11` respectively. Other paths/methods, metadata and general internet egress are denied.

The resolved host is private environment data; it is intentionally omitted here. Rules apply to all existing and future workspaces whose workloads execute these paths. Protected native provider attachment still supplies the model credential. Binary identity binds an executable, not arbitrary Python source: scripts executing that private ELF share its network authority. Do not claim all Python is denied or that the allow rule identifies only Hermes application code. A broader system-Python proposal was rejected before execution and replaced by this narrower path.

Policy compare/write is not an atomic native CAS. The helpers reduce races using sole-writer control, immediate full identity/fleet/hash checks and exact readback with journal transition guards; retain this limitation in any concurrency design. **Do not run the old `qualify-inference.py` live against this retained fleet:** its exclusive empty-fleet temporary-policy path restores a no-network global policy.

## 3. Credentials, Ownership And Retention

MaaS model credentials and agent HTTP listener credentials have different roles. Each non-ephemeral, named 30-day MaaS key is owned by `ai-admin`, limited to its dedicated subscription and Qwen3.8 model, and held by the native protected provider. The actual in-agent `MAAS_API_KEY` is a native resolve placeholder, not the real value. Qualification checks placeholder grammar and that its hash differs from the retained real-key hash, without printing either. The private journal stores key ID, expiry, scope and real-key SHA-256, not the real key.

| Runtime | Native Sandbox ID | Kubernetes Sandbox UID | Owned PVC UID | Key expiry, last operator metadata |
|---|---|---|---|---|
| OpenCode | `61554152-e667-44d4-a1f3-2cdd5e4dd2c5` | `a237679d-fea3-4b4f-9945-502f82b787c5` | `62cd436d-e51e-4295-b25f-b51e569f3f4d` | `2026-11-08T09:04:47Z` |
| Hermes | `a131de56-ee8a-4002-9095-2d5aefe539f1` | `2c3a94a1-1041-49f8-bcfa-769fe999348b` | `739a51ef-4732-4fbd-b6c2-21d1577d8127` (`workspace-hermes`) | `2026-11-08T12:19:47Z` |

These identifiers are checkpoint evidence, not authority to adopt a different resource. Helpers must match current journal bindings, workspace, provider ID/hash, namespace/gateway UIDs, source inputs, workload identity and private persona. Native attached-provider output contains only `name`, `type`, `config_keys`, `credential_keys`, not an ID; full scoped provider inventory supplies the exact-ID proof. The qualifier preserves both checks instead of inventing a missing field.

Private operator dependencies, **paths only**:

| Path | Purpose |
|---|---|
| `/private/tmp/060-ai-agents-scoped-kubeconfig` | Guarded bootstrap context, kept separate from the genuine owner persona |
| `/private/tmp/060-ai-agents-ai-admin-kubeconfig` | Genuine `ai-admin` OpenShift identity for native checks and MLflow auth plugin |
| `/private/tmp/060-opencode-ai-admin-native` | Verified native owner CLI login/home used by both agent clients |
| `/private/tmp/060-opencode-state/state.json` | Exact OpenCode recovery ownership/binding journal |
| `/private/tmp/060-hermes-state/state.json` | Exact Hermes recovery ownership/binding journal |
| `/private/tmp/060-opencode-state/upload/state/auth/server-password` | Owner-only OpenCode listener password; inside `/sandbox/state/auth/server-password` |
| `/private/tmp/060-hermes-state/upload/state/auth/server-key` | Owner-only Hermes listener key; inside `/sandbox/state/auth/server-key` |
| `/private/tmp/060-owner-client-venv/bin/python3` | External selected-client SDK environment; not in either Sandbox |

Credential and journal files are regular nonsymlink owner files, mode 600, in private directories. The SDK interpreter is an executable with its normal executable permissions. Native setgid directory ownership was corrected with a narrowly reviewed upload/start recovery; that did not require reading/changing password bytes, Pod edits or weakened enforcement. Listener keys are readable by the agent's own UID; they are not protected model-provider credentials. Do not claim otherwise. `/private/tmp` is an operator dependency, not durable public storage: securely retain journals/persona inputs as appropriate, without committing them or copying them into the public-source archive.

Plan rotation before the dates above. Use the exact existing provider/subscription/owner and native expiry metadata; verify the replacement before revoking the exact previous owned key. The pinned provider update supports `--credential MAAS_API_KEY`, `--credential-expires-at MAAS_API_KEY=<expiry milliseconds>` and `--wait`; keep real bytes in the existing private credential mechanism, never command output or Git. A pending/unknown key-creation outcome must be resolved by exact ID before another mint. Listener rotation is separate and requires synchronized native startup/local client state. This report does not authorize deletion or rotation.

Native stop/start preserves Sandbox/PVC identity and history; native deletion is destructive and is not a restart technique. Qualification finishes Running and never deletes the retained Sandbox or revokes its retained key. Retain uniquely named qualification fixtures and sessions as evidence. The disposable, no-provider Hermes packaging/API probes were separately retired only after exact-ID/UID checks; `/private/tmp/060-hermes-probes-retired.json` records that. `/private/tmp/060-hermes-disposable-probe-archive` contains metadata/input receipts, **not** a byte-for-byte PVC backup.

The earlier pre-PR-4150 recovery set in `openshell` was last reported as snapshot/claim `openshell-data-pre-pr4150` and four `*-pre-pr4150` secret copies. Their current presence was not rechecked. Do not infer they were deleted or are safe to delete. Existing compatibility build/template inputs are also retained until consumer retirement is reviewed.

## 4. Evidence And Claim Boundaries

| Evidence | What passed | What it does not establish |
|---|---|---|
| `/private/tmp/060-opencode-final.json` | All 16 finite gates: owned runtime; authenticated/missing/wrong-password HTTP; placeholder; real coding tool; exact one-time test approval; canonical model; SSE assistant deltas; independent fixture test; actual application abort; filesystem/egress/foreign-workspace denials; same-identity stop/start persistence; Running at end | Every future task, full migration, broad evaluation/load campaign, agent-internal tracing or full Stage 060 acceptance |
| `/private/tmp/060-hermes-final.json` | All 13 protocol gates: owned runtime/installed inputs; protected auth; real coding tool/text stream/fixed test; canonical configured model with positive usage; independent fixture test; actual cancelled run and terminal SSE; retained history/fixture across restart; Running at end | Active-run resume after restart, blanket shell approvals, or a native final runtime attribution field (the pinned API has none) |
| Hermes confinement supplement | Ten gates including pre/post identity/inputs/auth, filesystem, internet, metadata, shared interpreter, wrong method/path and Running at end | A full red-team campaign, unrestricted binary/source attribution or generic transport failure as policy proof |
| Human console check | Both deployed agents visibly Ready/Sandboxed in AI Agents | Catalog entries hosting agents, saved Playground profiles equalling deployments, or UI verification of future MLflow trace content |
| Committed client/tracing source | Independent review PASS; operator reports six owner-wrapper tests and nine trace privacy/evidence tests PASS | Published code, live owner permissions, experiment creation, new client tasks or persisted trace privacy proof |

All model tasks used tiny public/synthetic fixtures in uniquely owned `qualification-*` directories. The independent oracle accepts only a fixed harmless AST/function and runs the exact fixed test outside the agent's writable verifier boundary. No customer code, full migration or external fallback was used.

OpenCode's first abort gate found a predicate mismatch after the coding evidence had already passed. A targeted continuation retained the exact prior session/receipt, independently rechecked the fixture, established its hash at continuation time, performed one additional bounded cancellation and checked persistence. Do not retroactively claim an undocumented earlier fixture hash. Correct cancellation evidence was active busy/text, native abort acknowledgement, worker `MessageAbortedError`, fresh idle SSE, settled status and no late text. An absent status-map entry alone was insufficient. Foreign-workspace GET of a nonexistent Sandbox was inconclusive; the accepted LIST denial explicitly contained both the native permission phrase and `not a member of workspace openshell-developer`.

Hermes cancellation required busy/text before stopping, actual `cancelled` status with the matching fresh `run.cancelled` event, no late text/tool activity and a settled stream. A `stopping` response alone was insufficient. Its no-model REST denials required native HTTP 403, `X-OpenShell-Policy: hermes_maas`, `policy_denied` and exact inspected method/path/binary metadata; 401, timeouts or generic connection errors were not accepted. Filesystem, direct Internet/metadata sockets and shared-system-interpreter connection denials returned permission errors. Runtime inputs were checked before and after work/restart: installed config/start hashes, listener secret hash/ownership, placeholder and physical interpreter.

### Catalog, Deployments And Playground Are Separate

The Agent Catalog discovery ConfigMap retained UID `368db9b0-f631-4f84-991d-f86dd4283bf4`, entries `opencode`/`hermes`, titles OpenCode/Hermes and coding category. The stale Hermes qualification-pending label was removed; other discovery fields were preserved. Catalog metadata does not create a persistent Sandbox.

Deployments are the two actual native Sandboxes and their owned storage. Saved Gen AI Playground Agent profiles are separate user objects. Two historical qualifier profiles were backed up and removed through their native API with GET-404 verification; the owner later intentionally recreated Playground state. Do not restore those old objects automatically or attribute the human recreation to the runtime deployment. See `/private/tmp/060-step1-final.json` and `/private/tmp/060-step1-profile-backups` for the checkpoint. No blanket claim about concurrent Playground/PVC preservation is made.

## 5. Prepared Owner Client And Selected MLflow Tracing

The narrow next milestone uses the current native listeners through the authenticated owner relay. It changes neither runtime image nor global egress policy. Matching external dependencies are pinned in `client-requirements.txt`: `mlflow-skinny[kubernetes]==3.14.0`, `kubernetes==35.0.0` (held below the kubernetes-client 36 `BearerToken` rename that MLflow 3.14's `kubernetes-namespaced` provider does not read; corrected 2026-10-09 after the first live `--trace` attempt), `PyYAML==6.0.3`. They are installed in the external private SDK environment listed above.

The actual MLflow CR reports version 3.14.0, one ready instance, native TLS service port 8443 and a public HTTPS status URL with `/mlflow` prefix. Its native app is `kubernetes-auth`, workspaces enabled with `kubernetes://`, authorization mode `self_subject_access_review`. The reviewed client derives its only destination from that guarded Available CR and uses the genuine owner's kubeconfig with `kubernetes-namespaced`, `MLFLOW_WORKSPACE=ai-agents`, verified TLS and synchronous trace export. No manual shared bearer, alternate auth or insecure TLS is introduced.

The actual workspace API is `/api/3.0/mlflow/workspaces`; workspace `ai-agents` GET returned 200. Earlier guessed `/api/2.0` GET-404 was not evidence of a missing namespace. The SDK uses native workspace lookup. The global-MLflow-workspace namespace label is not a prerequisite in this installed configuration; adding it would opt into broader auth-group bindings and is intentionally avoided.

At the last authorization inventory, genuine `ai-admin` has **no** get/list/create/update permission for `experiments.mlflow.kubeflow.org` in `ai-agents`. HTTP experiment search 200 with an empty result does not prove write access. Two reviewed GitOps operands, committed in `9851b7aa…` but not deployed, specify only these verbs:

- Role `ai-agents/agent-trace-experiments` on `mlflow.kubeflow.org/experiments`.
- RoleBinding `ai-agents/ai-admin-agent-trace-experiments`, subject **User `ai-admin` only**.

This is project-wide experiment scope, not single-experiment isolation. The native experiment pseudoresource covers runs/traces/artifacts. No delete, registered-model/dataset permissions, shared groups, service-account grants or developer grants are included. Proposed experiment name is `agent-runtime-traces`; it has not been created by this slice.

`selected_task_trace.py` records a manual **CLIENT** span named `agent.client.task` for each explicitly selected real task. Purpose-based experiment/span names omit workshop stage codes; private file and source paths retain their existing Stage 060 routing. It projects only allowlisted client-observed facts: exact source/image/runtime/Sandbox/provider/session/run/model/subscription bindings, native tool status and identifiers, permitted usage counts and independently verified fixture SHA/outcome. It does not store prompts, code, arguments, commands, streamed text, tool output, headers, keys or raw exceptions. Failure handling remains inside the MLflow span context so SDK automatic exception recording cannot capture raw private failures.

A successful trace requires observed successful tool completion, not merely tool activity or assistant text. Hermes `tool.completed` with `error=True` cannot count as success. Fresh-process readback retrieves the exact trace and checks persisted CLIENT type, experiment/bindings, verified fixture outcome and all projected event schemas/IDs. It scans the full serialized stored payload, including server-added metadata and forbidden private values. The owner token and listener secret are private scan inputs; they never become authored trace fields.

This is truthful client observation, not automatic universal tracing or reconstructed agent-internal planning/LLM spans. Existing Hermes OTLP source covers gateway diagnostics; it does not establish coding-task internals. OpenCode has experimental upstream telemetry, but adopting its process-wide content/export behavior would require another privacy, dependency and egress design. Neither is enabled by this slice. MaaS subscription/model/time-window aggregate counters can accompany the trace; there is no demonstrated per-request trace-ID join to MaaS.

Final source review accepted both wrapper fixes: `sdk()` restores the original SDK environment and `KUBECONFIG` in `finally`; failure cleanup cancels only the newly owned OpenCode session or exact sole Hermes run and polls terminal acknowledgement before closing the relay. Unknown run creation fails closed without adopting another task. These were historical fixed findings, not remaining source blockers. After the purpose-name correction, frozen trace module SHA-256 is `6ccca08e2c98aea41b3ef13addb603e88ef2ec34ec407a7eb49d7c298bf8b079`; trace test SHA-256 is `718b8934d8eea39b5f18ebd75626ce75f802860d0ffd51e8ab70e91fa0fecfc4`; wrapper SHA-256 is `e5ab36e5bb0b01bfa0d66aa817ed22e6820ca5d27eb5ceddb5e560bda1b5c9d2`. The nine trace tests were also independently rerun after this literal-only change and passed. The archive manifest binds the historical precommit files. The reviewed implementation is now committed as `9851b7aa…`; confirm its remote SHA before live execution. No isolated live candidate, RBAC grant, experiment, trace or model task has run.

## 6. Ordered Remaining Work And Acceptance

1. **Re-establish the checkpoint without inference.** Inspect branch/HEAD/diff, archive hash/manifest and private input existence/modes. Preserve concurrent changes. Confirm no other writer is running. Re-read this report, the Stage 060 plan and actual helper source. Keep bootstrap and persona contexts separate; current guards bind the exact cluster, issuer, native subject/workspace, source revision, retained IDs and policy hash.
2. **Validate committed source and prepare isolated publication.** Render the runtime tree: intended resource count moves 61 → 63 only by adding the two RBAC operands. Perform schema validation, guarded server dry-run and exact target ownership checks. The twelve reviewed task files are already committed as `9851b7aaafe927e8ecf791feadd9e49534816176`; do not recreate that commit or reset the shared branch. Confirm remote publication of it and the report-only follow-up, then create an isolated immutable live tree based on actual runtime `3a65ec3c131124216597602a3437061140d0b332`. Preserve native identity/config delegation and Application automation. Parent/root publishes the reviewed source/report commits; the isolated live candidate still has no SHA yet. Acceptance: full reviewed diff, immutable published source, exact two-resource delta and no unrelated drift.
3. **Sync only the reviewed RBAC resources.** Use the existing guarded selective no-hook/no-prune procedure, retaining automation. Do not sync a floating main/whole branch, install all Stage 060 again or grant native developer membership. Acceptance: exact Role/RoleBinding ownership/spec; genuine `ai-admin` get/list/create/update = four yes and genuine `ai-developer` = four no. Use genuine persona or SAR with actual groups; bare `--as` without groups is not equivalent evidence. No access grants beyond the reviewed two operands.
4. **Run owner client checks.** `--check` validates both native owner relays, auth denials and retained identities/inputs. It performs no inference or MLflow lookup, and does not check or create an experiment. Experiment verification/creation belongs to `--trace`; retain the separately verified MLflow authorization gates from the preceding step.
5. **Run the selected tracing milestone once.** After published source/live revision and rights match, `--trace` creates or verifies the exact experiment and performs one new bounded synthetic coding task per agent, observes real successful tool events, independently verifies the fixture, reconnects retained session/history without another model request and performs fresh-process stored trace/privacy verification. One task can make several model calls within its configured four-step/turn limit; do not describe this as exactly two inference requests. Acceptance: each task/trace passes with exact IDs, native auth/reconnect/identity retained, private payload scan passed, and two directly usable trace links/IDs for the owner.
6. **Reconcile evidence and documentation.** Save owner-only receipts, record published source and actual live Application revisions, experiment/trace IDs, independent outcomes and developer negatives. Update the existing README/plan/Operations/Backlog in the owning writer's diff. Human browser verification stays user-owned. Do not mark full Stage 060 complete while its validator or other required gates remain pending.

The exact current client interface, **for future authorized execution only**, is:

```bash
# Run from the active source worktree. Load the existing guard privately.
export RHOAI_ENV_ROOT=/Users/adrina/Sandbox/rhoai3-coding-demo
export REPO_ROOT="$RHOAI_ENV_ROOT"
export KUBECONFIG=/private/tmp/060-ai-agents-scoped-kubeconfig
source scripts/shared/lib.sh
load_env
check_oc_logged_in
# Local .env must contain the unique RHOAI_EXPECTED_API_SERVER target.

/private/tmp/060-owner-client-venv/bin/python3 \
  stages/060-agent-runtime-and-agentops/owner-client.py \
  --trace \
  --revision '<published isolated Stage060 full SHA containing reviewed source>' \
  --persona-home /private/tmp/060-opencode-ai-admin-native \
  --persona-kubeconfig /private/tmp/060-ai-agents-ai-admin-kubeconfig \
  --state-root /private/tmp \
  --receipt '<new owner-only final receipt path>'
```

Substitute `--check` for the no-inference mode. `--readback <private trace receipt>` is the fresh-process verification mode; `--receipt`, `--revision` and both persona arguments remain required. `--trace` already invokes bounded fresh readback; do not add another coding run for readback. Source guards require relevant local bytes to equal the published revision and the current runtime Application revision to match. A mismatched helper-only commit is a pending publication gate, not a reason to bypass checks.

Narrow offline commands, from the active worktree with the matching installed SDK environment:

```bash
PYTHONDONTWRITEBYTECODE=1 /private/tmp/060-owner-client-venv/bin/python3 \
  -m unittest discover -s stages/060-agent-runtime-and-agentops/qualification \
  -p test_owner_client.py -v
PYTHONDONTWRITEBYTECODE=1 /private/tmp/060-owner-client-venv/bin/python3 \
  -m unittest discover -s stages/060-agent-runtime-and-agentops/qualification \
  -p test_selected_task_trace.py -v
```

No further research framework or repeated model campaign is needed before this finite slice. Other Stage 060 work (including MCP Gateway aggregation/governance and complete reproducible stage acceptance) stays separately tracked. Existing direct MCP catalog/Studio services are adjacent deployments, not evidence that an AI agent used those tools in the qualified coding task.

## 7. Recovery, Fresh Deployment And Rollback

For current retained agents, use existing setup helpers **without `--apply`** for native configuration/ownership, provenance and key-scope checks: `setup-opencode.py --revision <live SHA>` and `setup-hermes.py --revision <live SHA>`, with the verified persona arguments/environment. These setup checks do not establish Sandbox Ready or protected HTTP health; `owner-client.py --check` supplies those native readiness and health gates. `setup-ai-agents.py --revision <live SHA> --check` checks the foundation. `RHOAI_STAGE060_OPENSHELL_CLI`, `RHOAI_STAGE060_ADMIN_CLI_HOME`, `RHOAI_STAGE060_ADMIN_KUBECONFIG` and `RHOAI_STAGE060_EXPECTED_REVISION` must refer to the pinned/current inputs. `RHOAI_STAGE060_PYTHON` selects the external dependency-capable interpreter where documented.

`--apply` performs actual native setup and possible global policy/provider/key/Sandbox changes; it is not a harmless retry. Initial deployment uses the reviewed `--expected-policy-hash` baseline. An existing fleet or pending journal changes the permitted operation; helpers refuse foreign adoption, unknown creates and credential remint. Preserve failed state and report the exact pending gate. Do not remove a journal to force a fresh create.

`deploy.sh`, `deploy-runtime.sh` and their `--finish` recovery path contain the actual guarded immutable Application procedure. Read them before use. The current installation was qualified on the existing target cluster, identities and storage. A full clean-room end-to-end rebuild is not yet a demonstrated product artifact. Automatic operator channels, external image artifacts, private cluster prerequisites, provider key expiry and initial policy state all need review for a fresh environment.

`qualify-opencode.py --static` and `qualify-hermes.py --static` are offline entrypoints. Their `--run` modes perform real model work and native lifecycle operations and should only run for an authorized changed-runtime qualification, not to refresh this report. Hermes `--confinement-only` is the reusable no-model supplement. OpenCode's special `--remaining-from`, `--coding-session`, `--fixture-hash` mode is for an exact reviewed failed-abort receipt, not a general recovery framework. Source exposes all arguments; do not infer a new CLI from latest docs.

Separate application cancellation from Sandbox lifecycle. `sandbox stop`/`sandbox start` on the exact owned native ID/name follow bounded native phase and Kubernetes termination/readiness waits; post-start proof requires the same native Sandbox and PVC UIDs plus retained marker, fixture and session history. Never delete the retained Sandbox/PVC/key to restart it. Native CLI `forward service` binds a local loopback port through the authenticated gateway; no public agent ingress or generic browser endpoint is provisioned.

A rollback that downgrades OpenShell below the selected PR 4150 fix can reintroduce the OpenCode startup failure. Restoring an older no-network global policy can disable both agents. Runtime GitOps rollback alone does not reconstruct native providers, encrypted credentials, expired MaaS keys or lost PVC contents. New tracing RBAC removal affects future experiment access; it does not erase retained traces. Any rollback needs exact current identity, policy, storage and native state review. Destructive retirement, backup deletion and credential revocation require their own explicit authorization.

Stage 070 will provide Dev Spaces/RHDH/SCM integration, including planned Gitea. `/projects` in a developer IDE and `/sandbox/workspace` in an agent are separate filesystems/checkouts; there is no automatic sync. Use reviewed commits or patch exchange and clear ownership. OpenCode supports a pinned remote attach/session interface; Hermes here uses native HTTP APIs, not an invented equivalent remote CLI. Full Stage 130 Kanban/MTA managed-scope migration is not moved into the standalone Hermes profile by exposing HTTP. See the [Stage 070 plan](070-developer-platform-and-scm-plan.md) and Stage 130 release/contracts before expanding scope.

## 8. Reference Index And Authority

This index records the sources used or considered during the work. It is not a claim that every external link was fetched again for this handoff. Official current product documentation establishes support boundaries; pinned source establishes the selected native behavior; local manifests/helpers and guarded receipts establish deployed behavior. Latest upstream docs and older skill captures cannot override exact installed contracts.

### Official Product And Architecture Sources

| Reference | Role and decision |
|---|---|
| [Red Hat kernel-level agent security article](https://www.redhat.com/en/blog/beyond-container-boundaries-kernel-level-agent-security-red-hat-openshift-ai-35) | Architecture motivation: runtime/kernel controls complement prompt/model guardrails; not proof of this deployment |
| [RHOAI 3.5 Developer Preview features](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/release_notes/developer-preview-features_relnotes) | Adopted support boundary for OpenShell/Agent Catalog/running Sandbox views |
| [RHOAI supported configurations 3.x](https://access.redhat.com/articles/rhoai-supported-configs-3.x) | Baseline/compatibility authority; reconcile OCP4.22/RHOAI3.5.1/installed components before a rebuild |
| [RHOAI 3.5 MLflow installation](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/working_with_mlflow/installing-mlflow_mlflow) | Adopted SSAR/namespace experiment pseudoresource authorization and Role/RoleBinding pattern; broader global opt-in not adopted |
| [RHOAI 3.5 SDK installation/authentication](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/working_with_mlflow/installing-and-authenticating-mlflow-sdk_mlflow) | Adopted Kubernetes SDK authentication; actual server/client 3.14.0 wins over guide examples citing a different SDK/server minor |
| [RHOAI 3.5 trace archival overview](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/working_with_mlflow/mlflow-trace-archival-overview_mlflow) | Retention planning; no new archival configuration claimed here |
| [RHOAI 3.5 observability](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/managing_openshift_ai/managing-observability_managing-rhoai) | Existing platform/MaaS observability distinction; not evidence of agent-internal traces |

### Selected OpenShell And Controller Contracts

| Reference | Role and decision |
|---|---|
| [OpenShell PR 4150](https://github.com/NVIDIA/OpenShell/pull/4150) | Adopted startup compatibility fix; selected merge commit `12cec59b…` |
| [Pinned Kubernetes setup](https://github.com/NVIDIA/OpenShell/blob/12cec59bf4c36c305032143eb90870bd16d8820b/docs/kubernetes/setup.mdx) and [driver README](https://github.com/NVIDIA/OpenShell/blob/12cec59bf4c36c305032143eb90870bd16d8820b/crates/openshell-driver-kubernetes/README.md#L131) | Native gateway/controller installation, workload namespace and storage integration |
| [Pinned workspaces](https://github.com/NVIDIA/OpenShell/blob/12cec59bf4c36c305032143eb90870bd16d8820b/docs/how-it-works/workspaces.mdx) | Lines 25–58 establish role model; adopted owner-only first client because no consume-only user role |
| [Pinned protocol](https://github.com/NVIDIA/OpenShell/blob/12cec59bf4c36c305032143eb90870bd16d8820b/proto/openshell.proto#L199) | Relay/SSH permission checks, including lines 199–203 and 261–267; no invented read-only relay |
| [Pinned global policy overview](https://github.com/NVIDIA/OpenShell/blob/12cec59bf4c36c305032143eb90870bd16d8820b/docs/how-it-works/policies/overview.mdx#global-policy) and [server policy implementation](https://github.com/NVIDIA/OpenShell/blob/12cec59bf4c36c305032143eb90870bd16d8820b/crates/openshell-server/src/grpc/policy.rs) | Complete global authority, local update behavior, honest non-atomic policy transition |
| [Pinned binary identity guidance](https://github.com/NVIDIA/OpenShell/blob/12cec59bf4c36c305032143eb90870bd16d8820b/docs/security/best-practices.mdx#binary-identity-binding) | Adopted private ELF/path boundary and explicit interpreter limitation |
| [Pinned provider CLI serialization](https://github.com/NVIDIA/OpenShell/blob/12cec59bf4c36c305032143eb90870bd16d8820b/crates/openshell-cli/src/commands/provider.rs#L282) | Attachment rows have name/type/key lists, not provider ID; exact workspace inventory supplies ID proof |
| [Agent Sandbox upstream](https://github.com/kubernetes-sigs/agent-sandbox) | Controller API/lifecycle context; local source pins and observed installed preview0.9/owned PVCs establish this deployment |
| [Current NVIDIA OpenShift guide](https://docs.nvidia.com/openshell/dev/kubernetes/openshift) | Supporting route to upstream guidance; exact selected pin remains authoritative |

### Selected Agent And Tracing Contracts

| Reference | Role and decision |
|---|---|
| [OpenCode server docs](https://opencode.ai/docs/server/) | Conceptual native HTTP/server entrypoint; validate against 1.18.16, not latest alone |
| [Pinned OpenCode attach](https://github.com/anomalyco/opencode/blob/a3647eb025c7615159d417dcc49fc39fdaeba65b/packages/opencode/src/cli/cmd/attach.ts) | Actual remote/session/dir client semantics; server auth source in the same pin establishes Basic password |
| [Pinned OpenCode build-step config](https://github.com/anomalyco/opencode/blob/v1.18.16/packages/core/src/v1/config/agent.ts#L32) | Finite `steps: 4` supported contract |
| [OpenCode native LLM telemetry](https://github.com/anomalyco/opencode/blob/v1.18.16/packages/opencode/src/session/llm.ts#L208) and [OTLP setup](https://github.com/anomalyco/opencode/blob/v1.18.16/packages/core/src/observability/otlp.ts#L55) | Investigated; process-wide internal export/content not adopted in this milestone |
| [Hermes current API docs](https://hermes-agent.nousresearch.com/docs/user-guide/features/api-server) | Discovery only where newer than selected fork |
| [Pinned Hermes native API source](https://github.com/NousResearch/hermes-agent/blob/fcbd1076a93841fa88855acce810e342a5b78101/gateway/platforms/api_server.py#L2061) | Adopted route/field/terminal semantics: auth around1790; public/protected health2998–3013; sessions2220+; runs6681+/6947–7009; approval7164–7248; stop7312–7342; loopback/key guard7396–7465 |
| [Pinned Hermes OTLP exporter](https://github.com/NousResearch/hermes-agent/blob/fcbd1076a93841fa88855acce810e342a5b78101/agent/monitoring/otlp_exporter.py#L19) | Diagnostic/health exporter considered; does not establish coding task spans |
| [MLflow 3.14 manual tracing implementation](https://github.com/mlflow/mlflow/blob/v3.14.0/mlflow/tracing/fluent.py#L513), [Span](https://github.com/mlflow/mlflow/blob/v3.14.0/mlflow/entities/span.py#L964), [SpanEvent](https://github.com/mlflow/mlflow/blob/v3.14.0/mlflow/entities/span_event.py) | Adopted start/end/manual CLIENT span and exact projected event API |
| [MLflow 3.14 workspace REST store](https://github.com/mlflow/mlflow/blob/v3.14.0/mlflow/store/workspace/rest_store.py#L22) and [TraceInfo](https://github.com/mlflow/mlflow/blob/v3.14.0/mlflow/entities/trace_info.py#L174) | Exact workspace 3.0/retrieval/experiment binding; avoids guessed route/field |
| [MLflow manual tracing guide](https://mlflow.org/docs/latest/genai/tracing/app-instrumentation/manual-tracing/) | Conceptual selected-call approach; pinned SDK source decides implementation |
| [MLflow OTLP ingestion](https://mlflow.org/docs/latest/genai/tracing/opentelemetry/ingest/) | Future native-export alternative considered; no new Collector/Tempo or Sandbox MLflow egress deployed |
| [Kubeflow MLflow workspace provider](https://github.com/kubeflow/mlflow-integration/blob/main/docs/workspace-provider.md) | Namespace-backed workspace/filter context; installed plugin and actual `/api/3.0` readback are authority |

### Discovery, Alternatives And Historical Diagnostics

| Reference | Role and disposition |
|---|---|
| [Pinned agent-ops OpenShift guide](https://github.com/opendatahub-io/agent-ops/blob/7230605c8c0a4cec41c3e39e52e521db5c941355/guides/getting-started-openshell-openshift.md) | Considered implementation guide; its older/current demo tuples, privileged/anonymous assumptions are not the selected restricted/OIDC recipe |
| [OpenCode starter kit](https://github.com/red-hat-data-services/agentic-starter-kits/blob/b6b69cc0fc7b36c8415f7756f0d6ecb3a19cbd1d/agents/opencode/README.md) | Discovery source, not hosting proof or drop-in deployment; starter 1.17.1 differs from selected1.18.16 |
| [Secure Agent Workspace alternative](https://github.com/validatedpatterns-sandbox/secure-agent-workspace/tree/3f02cba94cf7681ec232d105f9e4c5c9e5553717) | Considered VM/Fedora44 bootc/rootless Podman recipe with different OpenShell/custom patch and compatibility assumptions; rejected as an overlay on this existing cluster. No VM alternative deployed |
| [OpenShell v0.1.2 release](https://github.com/NVIDIA/OpenShell/releases/tag/v0.1.2) and [older sandbox architecture](https://github.com/NVIDIA/OpenShell/blob/6648bd0c290efbc41ba131ee9831ee45cd431f94/architecture/sandbox.md#L252) | Historical compatibility investigation; not current selected pins |
| [Bun1.3.14 socket source](https://github.com/oven-sh/bun/blob/bun-v1.3.14/packages/bun-usockets/src/bsd.c#L729) | Historical OpenCode startup diagnosis; resolved by selected OpenShell fix |
| [Keycloak issue45966](https://github.com/keycloak/keycloak/issues/45966) | Historical realm recovery context; no claim of a particular Red Hat backport |
| [Pinned AI gateway payload processor](https://github.com/red-hat-data-services/ai-gateway-payload-processing/tree/a98a2650e74f8b832ff75206f795cbb62b9cd688), [Red Hat image metadata](https://catalog.redhat.com/api/containers/v1/images/id/6ab154c878e6fe9f08e47a14), [llm-d processor](https://github.com/llm-d/llm-d-inference-payload-processor/tree/a8bbe6a6a75a) | Historical empty/nonstreaming MaaS-response investigation; no custom response translation adopted. Current task qualification uses successful native streaming evidence |
| [Pinned dashboard Agent profiles](https://github.com/opendatahub-io/odh-dashboard/blob/f4a81e89bf8a1fb0bbe3dfdc7b10eaa39b3d7439/packages/gen-ai/bff/internal/integrations/kubernetes/agent_profiles.go) | Native saved-profile lifecycle distinct from catalog and deployed Sandboxes |

### Local Continuation Map And Secondary Skills

Read these repository sources before changing behavior: [Stage 060 plan](060-agent-runtime-and-agentops-plan.md), [Stage 060 README](../../stages/060-agent-runtime-and-agentops/README.md), [Operations](../OPERATIONS.md), [Troubleshooting](../TROUBLESHOOTING.md), [Backlog](../../BACKLOG.md), [platform baseline](../PLATFORM_BASELINE.md), [Stage 050 plan](050-model-evaluation-plan.md), [Stage 070 plan](070-developer-platform-and-scm-plan.md), Stage 130 `hermes-runtime/RELEASE.md` and its patch/build inputs. Stage 060 setup/native API/qualification/client source and focused tests are executable contracts; GitOps source pins, rendered templates, subscriptions and policy define desired state. Historical plan entries and older Operations commands are dated evidence, not confirmation that Stage 070 is deployed.

The consulted guidance routes include `AGENTS.md`, `.agents/rules/{project,env,docs,gitops,rhoai,ocp}.md`, the OpenShift safety skill, `project-documentation-authoring`, `demo-operations-docs`, `rhoai-mlflow`, `rhoai-observability`, `ocp-opentelemetry`, and relevant Hermes configuration/session/tool/profile/managed-scope guidance. Their captured product baselines include RHOAI3.4/OCP4.20/older telemetry documentation; use them for routing and safeguards, with official3.5/actual4.22 and exact selected runtime source taking precedence. They do not certify the custom patched Hermes image. Full Stage 130 contracts remain in that stage rather than being imported wholesale into this standalone profile.

## 9. Last-Verified Versus Prepared Records

The final operator checkpoint reports no running sessions and no current-slice live calls. The twelve reviewed public implementation files are committed as `9851b7aaafe927e8ecf791feadd9e49534816176`, preserving concurrent MCP parent `aa6a578bc6456ad0ea7af51d0a7b997f5daa43f8`. The report follows in its own documentation commit; confirm both remote SHAs before live execution. No isolated live candidate has been created. The existing two agent qualification/visual checks are accepted historical live evidence. The owner-client wrapper, trace module and two RBAC operands are independently source-reviewed PASS with reported 6+9 offline tests. Private readiness records are `/private/tmp/060-mlflow-owner-readiness.json`; metadata-only inventories are `/private/tmp/060-client-tracing-inventory-private.json` and `/private/tmp/060-mlflow-actual-roles-private.json`. Keep those private; this document exposes only sanitized paths and conclusions.

The next meaningful action is finite publication/validation of the two RBAC operands followed by owner-client tracing. There is no remaining source architecture blocker, but there is no live trace proof yet. Any later agent must update this checkpoint with new source/live revisions, rights and receipts before changing its completion claims.

## 10. Continuation checkpoint, 2026-10-09 (owner-client tracing milestone complete)

Continuation by the next agent on the same branch, with AI assistance disclosed; a human still reviews and owns the result. Steps 1–5 of section 6 are done; step 6 is this record. Stage 060 as a whole remains incomplete: `validate.sh` still reports `[PENDING]` by design, and Stage 070 integration, MCP Gateway governance and key rotation stay open.

| Item | Verified state |
|---|---|
| Reviewed source | `9851b7aaafe927e8ecf791feadd9e49534816176` on `origin/codex/stage-010-foundation-35`; pin correction `738f54ed` (`kubernetes==35.0.0`) |
| Isolated live trees (tags on origin) | `ff92a7550e8bdfb96629abc7eab1797d61ec4c47` = `stage060-client-traces-20261009` (retained runtime `3a65ec3c…` + the twelve reviewed files; runtime renders 61 → 63) and `07a29a299fd6ed6c8da3aa5ce35a82a1a15dc74f` = `stage060-client-traces-k8s-pin-20261009` (+ the pin correction only; 63 → 63) |
| Live `openshell-runtime` | `07a29a299fd6ed6c8da3aa5ce35a82a1a15dc74f`, Synced/Healthy; revision-only Application patch, then `argocd --core app sync … --strategy apply --resource` for exactly `Role/ai-agents/agent-trace-experiments` and `RoleBinding/ai-agents/ai-admin-agent-trace-experiments` (no hooks, no prune) |
| Authorization | SelfSubjectAccessReview as the genuine personas: `ai-admin` get/list (existing `admin` aggregation) and create/update (new Role) all allowed; `ai-developer` all four denied. `oc auth can-i` shorthand reports "no" for the unserved pseudo-resource and is not evidence |
| Owner client `--check` | PASS for OpenCode and Hermes (authenticated ready, missing/wrong auth denied, owner relay reconnected, retained identity); receipt `/private/tmp/060-client-receipts/check-20261009T151319Z.json` |
| Owner client `--trace` | PASS: experiment `agent-runtime-traces` (id `3`, workspace `ai-agents`); OpenCode trace `tr-e5eeda85743482fc08803fda34993ae3` (session `ses_edec04486ffew6x26eJ12m69ix`, 11 observed events); Hermes trace `tr-e148bf1f3808f46626974af74d954aff` (run `run_b815906683234efeb41beea39a45cb95`, 7 events); fixture `2921fc2c…` independently verified for both; stored payload scans clean; receipt `/private/tmp/060-client-receipts/trace-20261009T151908Z.json` |
| Retained identities | Unchanged: OpenCode `61554152-…` / UID `a237679d-…` / PVC `62cd436d-…`; Hermes `a131de56-…` / UID `2c3a94a1-…` / PVC `739a51ef-…` |

Two defects surfaced during execution and were corrected without touching keys, PVCs or policy:

- **Credential revision drift.** The first `--check` failed `placeholderNotRealKey` for OpenCode only. OpenShell issues revisioned resolve placeholders (`openshell:resolve:env:v<revision>_MAAS_API_KEY`); the OpenCode process started at 09:44Z still held revision `v1433…` while every fresh exec received `v1559…`, so the provider credential had been re-revisioned later that morning (Hermes, restarted at 12:25Z, matched). Remedy: the sanctioned native `sandbox stop`/`sandbox start` of the retained OpenCode Sandbox with identity compared before and after (same native id, Kubernetes UID and PVC UID; 6 s to Stopped, 23 s to Ready). After the restart the process and exec revisions match and the gate passes.
- **SDK auth plugin mismatch.** The first `--trace` stopped at MLflow's `kubernetes-namespaced` provider with "Could not determine Kubernetes credentials": kubernetes-client 36+ stores the kubeconfig bearer under `api_key["BearerToken"]`, MLflow 3.14.0 reads only `"authorization"` (fixed upstream in 3.15). The server is 3.14.0, so the client pin moved to `kubernetes==35.0.0` (`738f54ed`), the private SDK environment was reinstalled accordingly, and a read-only workspace lookup proved the fix before the second run.

Private operator inputs used, unchanged: the scoped bootstrap kubeconfig, the genuine `ai-admin` kubeconfig and native CLI home, the pinned CLI at `/private/tmp/openshell-pr4150/client/openshell` (SHA-256 `6323f774…`), the recovery journals and listener secrets. A thin loader wrapper was used to read the client's failing gate name without modifying the guarded script. Browser verification is done: on 2026-10-09 the owner, signed in as `ai-admin`, opened **Experiments → agent-runtime-traces → Traces** and confirmed both traces render with state OK (`tr-e148bf1f…` 19.186 s at 17:21:16, `tr-e5eeda85…` 20.338 s at 17:19:48 local time).
