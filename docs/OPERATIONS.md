# Operations Guide

> **Foundation migration (2026-07-06):** stages 010-040 now import the
> validated rhoai3-demo foundation (former 050/060 folded into 040). Sections
> below that describe the pre-migration 010-060 implementation are historical
> until rewritten after the first migrated deployment.

This document explains how to deploy, validate, and operate the workshop environment. The README files teach the architecture and product story; this guide is the operational companion for people running the demo.

The executable source of truth remains the scripts:

- `stages/NNN-*/deploy.sh`
- `stages/NNN-*/validate.sh`
- `scripts/demo/bootstrap-scaffold-repos.sh` (read-only report of Stage 120/130 GitLab goldens)

Use this guide to understand when to run those scripts, what they do, and how to interpret the results.

## Fresh environment baseline (2026-10-05)

This section records the environment used for the staged OCP 4.22 / RHOAI 3.5 migration. An environment inventory establishes prerequisites; it does not prove a deployed demo stage. Stage 010 source now selects RHOAI 3.5 and ODF 4.22; later stages and historical records retain their legacy selections until individually upgraded and validated. The inventory below describes the environment before project installation.

### Stage 010 deployment evidence (2026-10-05)

The isolated implementation branch `codex/stage-010-foundation-35` is published without a pull request or main-branch merge, as authorized by the owner. The guarded deployment uses immutable source revisions; the revised deployed source is `f38d84c072ee18c38fb21072a6442a1b07d468eb`. GitOps 1.21.4, RHOAI 3.5.1, ODF 4.22.5, COO 1.5.3, OpenTelemetry operator 0.158.0-2 and Tempo operator 0.22.0-2 installed. Bundle metadata maps the tracing products to 3.11; an exact publicly documented tested RHOAI/operator tuple remains unverified.

On 2026-10-08, a separately approved native plan installed GitOps 1.21.5, Service Mesh 3.4.3 and MCP Gateway 0.7.1. The provider's Istio image, model routing and authentication specs were preserved; these metadata checks did not run model inference. The earlier foundation receipt above remains historical.

NooBaa initially waited for cloud credentials, then created its native default local PV pool (one 50Gi `gp3-csi` volume). The provider cloud-credential failure persists; it did not recover AWS credentials. Both buckets retain native placement. No project storage hook, custom pool or global bucket-class change was applied. The local pool is finite demo storage, without HA.

Native registry API/database readiness, metrics and Perses backend queries passed. Trace ingestion originally failed Tempo authorization; the source now includes narrow tenant writer/reader grants, with exact exact synthetic trace retrieval subsequently passed. MLflow became available and its operator-owned deployment was current. A strict-TLS synthetic experiment passed artifact proxy upload/download, independent S3 readback and PostgreSQL persistence; this is synthetic service evidence, not a real user login. The idempotent runtime setup reused database credentials and configured its native service connections. Confirmed OpenID names were assigned to demo groups and the sandbox S3 connection was created; OAuth/provider accounts were not changed. Real persona login and dashboard discovery remain separate foundation evidence gates; completed evaluation belongs to the later evaluation stage. The revised DSC is Ready at generation 2 with TrustyAI Removed; KServe remains deferred to Stage 030. The application at the revised source is Synced/Healthy with its operation Succeeded. The unused evaluation namespace and 10Gi claim were removed after exact identity/empty-data rechecks; its Delete-policy backing volume was reclaimed. MLflow, NooBaa, the sandbox and provider identity were preserved.

### Provisioning contract

| Input | Requested default | Evidence required on every fresh cluster |
|---|---|---|
| Provider / topology | AWS / multinode | Infrastructure platform and actual node roles |
| OCP minor | 4.22 | ClusterVersion desired/history, Kubernetes version, update channel and conditions |
| CPU workers | Four `m5a.8xlarge` workers | Node instance labels, capacity/allocatable CPU/memory, readiness, taints and MachineSets |
| Control plane | Reproduce the observed three `m6a.4xlarge` nodes; screenshot did not specify sizing | Confirm three control-plane nodes and at least the project 16 CPU / 60 GiB capacity rule independently; observed provider default is dual-role/schedulable, with later placement decisions reviewed per stage |
| OpenShift Lightspeed | Enabled | Owning Subscription/CSV, OLSConfig and operand health; selection alone is not installation evidence |
| Create users / OPEN Environment | Both unchecked | Inventory actual authentication configuration; do not infer that these settings remove ordinary provider add-ons |

The project guard in [require-node-sizing.sh](../scripts/platform/require-node-sizing.sh) requires at least 16 vCPU and 60 GiB **capacity** for every non-GPU control-plane and CPU worker node. It exempts accelerator nodes. This is a project rule for the complete demo, not a Red Hat minimum or a measured workload guarantee. Allocatable resources must also be recorded.

The [RHOAI 3.5 installation requirements](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/installing_and_uninstalling_openshift_ai_self-managed/installing-and-deploying-openshift-ai_install) separately require at least two workers with 8 CPUs / 32 GiB each, default dynamically provisioned storage and an identity provider. RHOAI installation and administrative setup require an appropriately privileged non-`kubeadmin` account; ordinary user access is governed separately by project/group permissions. Discovery using a provisioning administrator does not establish that application access is ready.

The [supported-configurations matrix](https://access.redhat.com/articles/rhoai-supported-configs-3.x), updated 2026-10-02, lists RHOAI 3.5 on x86_64 with OCP 4.19.9+, 4.20, 4.21 and 4.22. The 3.5 installation page still lists 4.19–4.20 in its platform requirements; use the newer matrix for the compatibility claim and validate exact dependency versions separately.

### Observed inventory and evidence

Guarded API reads completed on **2026-10-05 at 06:50–06:55 UTC**, from clean `main` at `59169d28ce661209eca52680e5621b8150043230` (19 commits behind cached `origin/main` at the start of discovery). No refs were changed. Login used an isolated private kubeconfig; the global context was untouched. The user confirmed the new API/console pair, and only the gitignored local `RHOAI_EXPECTED_API_SERVER` was aligned to that confirmed target. Private inventory is retained locally; addresses, credentials, account IDs and node identities are omitted here.

| Area | Observed state | Consequence |
|---|---|---|
| OCP / Kubernetes | OCP **4.22.14**, `stable-4.22`; kubelets **v1.35.6**; AWS, HighlyAvailable control-plane/infrastructure topology | Requested provider/minor/topology match; this is a fresh deployment baseline, not an in-place OCP upgrade |
| Core health | ClusterVersion Available=True, Failing=False, Progressing=False; all ClusterOperators Available and not Degraded; master/worker MachineConfigPools Updated and not Degraded | Core platform is available; this does not establish add-on health |
| Upgrade constraint | ClusterVersion Upgradeable=False, reason `MissingRootCredential`; cloud-credential reports missing parent `kube-system/aws-creds` | Provisioner must resolve before a future minor/major OCP upgrade; credential contents were not inspected or restored |
| Dedicated CPU workers | Four `m5a.8xlarge`, each 32 CPU / 123.666 GiB capacity, 31.5 CPU / 115.568 GiB allocatable | Requested worker count/type match; all Ready, no pressure conditions |
| Control plane | Three `m6a.4xlarge`, each 16 CPU / 61.461 GiB capacity, 15.5 CPU / 60.363 GiB allocatable | Control-plane size independently observed; all Ready and pass project capacity rule |
| Scheduling / GPUs | All seven nodes untainted; control planes also worker-labeled; `mastersSchedulable: true`; no GPU instance/role/advertised NVIDIA GPU capacity | Three dual-role control planes plus four dedicated workers; do not count seven dedicated workers or infer GPU readiness |
| Machines / scaling | Seven Machines; six worker MachineSets: three active `m5a.8xlarge` sets with replicas 2/1/1, three `m5a.4xlarge` sets at zero; no ClusterAutoscaler or MachineAutoscaler objects | Zero-replica sets are provisioner inventory, not demonstrated project debris |
| Node local storage | Each node advertises about 99.44 GiB ephemeral capacity / 88.49 GiB allocatable | Node-local capacity is not dynamically provisioned PVC capacity or an AWS EBS quota |
| Block / object storage | `gp3-csi` default and `gp2-csi`, both AWS EBS CSI, WaitForFirstConsumer, expansion enabled; one Bound 50Gi `gp3-csi` PVC/PV in `keycloak` | Dynamic storage configuration is present; provisioning/expansion not actively tested. No ODF/NooBaa or project object-store installation observed |
| Network / ingress / registry | OVNKubernetes; default ingress LoadBalancerService with two available replicas; internal registry Managed with S3 storage and Available=True | Provider/platform infrastructure; registry S3 is not a project S3 model-artifact service |
| Gateway API | Standard bundle **v1.4.1** CRDs present; zero GatewayClass, Gateway or HTTPRoute objects | API presence does not establish a MaaS gateway or gateway controller installation |
| Proxy / trust | No HTTP/HTTPS proxy configured; trustedCA reference configured; ingress/config certificates report Ready | Trust reference/certificate readiness observed; trust contents and external connectivity were not tested |
| Authentication | One OpenID identity provider; preinstalled Keycloak CR Ready, one instance; PostgreSQL deployment Ready and its 50Gi PVC Bound | Provider identity is present despite unchecked user-creation option; actual persona login and non-kubeadmin RHOAI admin access remain untested |
| Cleanliness | No demo stage namespaces or project Applications/workloads/PVCs observed; Application API unavailable. Five Failed platform revision pods created 2026-09-28 remain in kube-controller-manager/scheduler namespaces | Provisioner add-ons and platform revision history are not demo leftovers; do not delete them as cleanup |

All queried core inventory APIs responded; Argo CD Application API was unavailable. RHOAI, ODF/NooBaa, GPU/NFD, COO, Tempo, Dev Spaces, Pipelines and RHDH installations were not observed in Subscriptions/CSV/CRD/namespace inventory. Built-in OCP monitoring is present; Lightspeed's own OTel collector does not establish a separately installed Red Hat OpenTelemetry Operator. Three catalog sources reported READY; catalog availability is not installation or compatibility evidence.

| Preinstalled operator | Channel / approval / installed version | Primary CR / health / scope | Owner and consequence |
|---|---|---|---|
| cert-manager | `stable-v1` / Automatic / **1.20.1** | Operator and three cert-manager deployments Ready; OperatorGroup targets `cert-manager-operator` | Existing environment add-on; preserve its ownership when reviewing prerequisite overlap |
| Red Hat build of Keycloak | `stable-v26.4` / Automatic / **26.4.16-opr.1** | CSV Succeeded; Keycloak Ready; OperatorGroup watches only `keycloak` | Preinstalled; Stage 070 independently declares `rhbk` / `stable-v26`. Namespace/watch scope are distinct; reuse vs separate installation needs an explicit integration decision |
| OpenShift Lightspeed | `stable` / Automatic / **1.1.4** | CSV Succeeded; OLSConfig **NotReady**, ApiReady=False; two API containers running but unready, deployment has zero Ready replicas. Console/cache/collector/MCP/RHOKP Ready; optional agentic plugin/alerts adapter disabled | Selected provisioning add-on exists but is not fully healthy. Bounded API logs show `azure.core.exceptions.ClientAuthenticationError` and readiness requests returning 500; credential/provider configuration and user-facing service were not validated; provisioner follow-up required |

The 2026-10-05 11:16 UTC follow-up isolated the active Lightspeed failure to Azure Entra `AADSTS700016`; readiness is HTTP 503, both API containers remain unready, and all required credential keys are present. Provider registration/tenant correction is required from its owner; no credential or provider changes were made. Five old failed installer pods are retained history, with current control-plane revisions healthy. See [pod failure diagnosis and recovery](TROUBLESHOOTING.md#lightspeed-api-unready-azure-application-identity-not-found). The foundation remains pinned to `f38d84c0`, Synced/Healthy, with MLflow and registry availability preserved.

The CloudCredential CR has an empty `spec.credentialsMode` and no populated status; effective mode was not established without credential metadata. [OCP 4.22 cloud credential guidance](https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html/postinstallation_configuration/changing-cloud-credentials-configuration) permits root-credential removal in supported configurations. The observed upgrade condition is not, by itself, evidence of an improperly provisioned or unhealthy running cluster. Provider action is needed when an upgrade or new/changed CredentialsRequests require parent credentials.

These add-ons predate project deployment in this environment. Their provisioning source/automation was not inspected, so ownership is classified as **pre-existing environment state**, not a verified external GitOps repository. Operators own their generated workloads. CSV Succeeded alone is insufficient for an add-on readiness verdict.

### Stage 010 readiness and deferred cleanup

The initial pre-install inventory established cluster prerequisites. Stage 010 has since been published and deployed as recorded above; full qualification still requires native component/functionality and real persona acceptance. Existing provider identity is preserved: `setup-access.sh` assigns the confirmed OpenID names to groups and creates the S3 connection without adding an identity provider.

Cleanup remains scoped to replacement evidence. The former 3.4/4.20 channels and AutoRAG enablement are superseded by reviewed Stage 010 source. Native metrics and Perses transport evidence permit retirement of their old transport workarounds; persona-dependent dashboard RBAC remains pending. Stage 020 Kueue and Stages 030–050 require their own version/ownership review. Historical validation logs remain historical.

### Ownership and stage boundaries

| Component | Expected owner / source | Stage consequence |
|---|---|---|
| OCP control plane, workers, machine lifecycle, platform network/ingress, CSI/default storage, registry, catalog sources | Environment provisioner and OCP operators; actual add-on ownership must be inspected | Fresh-cluster prerequisites; project stages must not adopt or remove them without evidence |
| Lightspeed selected at provisioning | Provisioner / its installed operator, if observed | Record actual version/configuration/health; do not duplicate its installation in a project stage |
| GitOps operator and demo Argo CD configuration | Project [bootstrap overlays](../gitops/bootstrap/overlays/); GitOps operator generates operands | Stage 010 uses `gitops-1.21` Automatic, annotation tracking, `rhoai-demo` AppProject and demo controller RBAC; reconcile preinstalled ownership before applying |
| ODF / NooBaa standalone MCG | Project [Stage 010 `odf` component](../gitops/stages/010-openshift-ai-platform-foundation/odf/kustomization.yaml); operators generate operands | Selected `stable-4.22` channel and verified `gp3-csi`; native local MCG supplies object storage, not Ceph block/file |
| RHOAI / DSCI / DSC / model registry | Project Stage 010 [`rhoai-operator`](../gitops/stages/010-openshift-ai-platform-foundation/rhoai-operator/kustomization.yaml) and [`rhoai-platform`](../gitops/stages/010-openshift-ai-platform-foundation/rhoai-platform/kustomization.yaml) components; RHOAI owns generated components | Selected `stable-3.5`; Dashboard and Workbenches are foundation-owned; MLflow is deferred in fresh source and preserved on live f38; revised source delegates the modelregistry component and both catalogs to Stage 030, while the live f38 registry remains preserved; KServe remains Stage 030-owned, while TrustyAI/evaluation belongs to a later stage |
| COO / OpenTelemetry / Tempo | Project [Stage 010 `observability-operators` component](../gitops/stages/010-openshift-ai-platform-foundation/observability-operators/kustomization.yaml) | Automatic approval within the selected channels; native operators own operands, with narrow project tenant access grants |
| Keycloak `keycloak/keycloak` (`sso` realm, OAuth provider `rhbk`) | Provided by the demo environment (created at provisioning); not owned by GitOps | Prerequisite: Stage 010 `validate.sh` checks it is Ready and that OpenShift login uses the `rhbk` OpenID provider. Stages 060 and 070 own only their realm imports |
| Demo identity | Project [setup-access.sh](../stages/010-openshift-ai-platform-foundation/setup-access.sh) plus GitOps groups/RBAC; S3 connections from `010-sandbox-storage` | Separate mutating step after deployment; `deploy.sh` does not call it. Private authenticated persona kubeconfigs remain outside Git |
| GPUs / NFD / Kueue | Stage 020 desired state unless provisioner installation is observed | Stage 020 source selects NFD `stable`, NVIDIA `v26.7` and Kueue `stable-v1.4` with Automatic approval (installed 2026-10-14: NVIDIA v26.7.2, Kueue 1.4.3); no GPU capacity is implied by CPU worker settings |
| Model serving / MaaS / developer services | Stages 030 / 040 / 050 | Inventory any existing installations without promoting catalog entries into installed/compatible evidence |

MLflow, EvalHub and TrustyAI belong together in Stage 050 source; MLflow is now Stage 050-owned after its protected seven-resource handoff; registry and both catalogs remain Stage 030-owned after their completed protected handoff; OpenShell with standalone Hermes per project remains later-stage design. AutoRAG and AutoML are excluded from the intended scope. Their API availability, ownership, release posture and runtime acceptance remain stage-specific work. No feature is considered installed merely because it appears in a catalog, screenshot or planned target.

### Object storage purposes and preservation

The user removed the pre-creation naming review checkpoint on 2026-10-05. An OBC name is not necessarily the S3 name: `generateBucketName` is a prefix, while `bucketName` requests an exact name; verify the resolved name after provisioning. Before changing existing storage, assess its data, retention, dependent connections, artifact URIs and ownership; preserve existing consumers and data.

The confirmed logical purposes are a **models bucket** for model artifacts and a **workbench bucket** for shared S3 file exchange between workbenches. No AI Pipelines bucket is planned because this demo does not use pipelines. The workbench bucket provides shared data exchange; persistent workspace PVCs remain the workspace/POSIX filesystem. Models and Workbench connections use native bucket-generated credentials; this observability change creates no storage.

The existing `rhoai-mlflow-artifacts` bucket is separate MLflow component artifact storage associated with the Stage 050 ownership handoff. The user has accepted `rhoai-mlflow-artifacts` unchanged: preserve its existing bucket, name and data; this plan does not authorize creating a third bucket or deleting storage. The generic `demo-sandbox-bucket` claim was reviewed and retired on 2026-10-14 (its only content was a discarded SWE-bench pilot run).

### Local inputs and read-only preflight

Keep API/console addresses, login credentials and kubeconfigs only in local private inputs. `OPENSHIFT_API_URL`, `OPENSHIFT_CONSOLE_URL`, `OPENSHIFT_USER`, `OPENSHIFT_PASSWORD` and `RHOAI_EXPECTED_API_SERVER` must describe the same environment. The expected-server substring must be unique. Do not reuse an inherited endpoint silently: `load_env` preserves values already exported by a caller. Load access inputs in a fresh shell, use a private kubeconfig and call `load_env` plus `check_oc_logged_in` before discovery. The guard's normal output contains the private endpoint; keep its output private when producing evidence for publication.

Before a later deployment, verify `GIT_REPO_URL`/`GIT_REPO_BRANCH` and only the local secret inputs required by that stage. Do not dump `.env`, kubeconfig or Secrets. Inspect scripts before running them. Baseline discovery uses only API reads: do not run deployment/access setup, create test workloads/PVCs, or repair platform state as part of inventory.

Collect ClusterVersion/ClusterOperators, nodes/Machines/MachineSets/autoscalers, storage/CSI/PVs/PVCs, network/ingress/registry/proxy/authentication, Subscriptions/installed CSVs and owning CR health, plus namespace/workload/project leftovers. Discover optional APIs before querying their objects. Classify each result as observed healthy/unhealthy, absent object, unavailable API, forbidden, request failure or uninspected. Preserve names/versions of public products, but sanitize endpoints, account IDs, node IPs, infrastructure IDs and identity names. A Pending PVC with WaitForFirstConsumer is not sufficient evidence of failure.

## Script groups

| Directory | Purpose | Entry points |
|---|---|---|
| `scripts/platform/` | Platform sizing, GPU lifecycle and workshop layout validation | `require-node-sizing.sh`, `resume-gpu-demo.sh`, `validate-stage-flow.sh` |
| `scripts/demo/` | Stages 110–130 golden publishing, demo reset/cleanup and consumer checks | `bootstrap-scaffold-repos.sh`, `reset-coolstore-demo.sh`, `delete-scaffolded-project.sh`, `check-kilo-provider.py`, `check-workspace-creation.py` |
| `scripts/shared/` | Helpers used by both platform and developer workflow stages | `lib.sh`, `validate-lib.sh` |

Tests remain beside their helpers. Run scripts from the repository root using their full grouped paths; source common helpers from `scripts/shared/`. Publishing, reset, cleanup and GPU lifecycle actions retain their existing effects and guards. Stage-local deploy/validate scripts remain in their stage directories.

The obsolete manual workspace MaaS route repair helper `patch-workspace-maas-route.sh` and its companion test were removed: the current catalog/template validates and stamps routing at creation, and preflight/planner checks refuse missing or incorrect routes. The supported recovery path is to preserve work/evidence, refresh routing inputs and create a new workspace through the current template. Factory route injection and its acceptance tests remain active; historical workspaces are not patched by this cleanup.

## Operating Model

The repository follows a GitOps-first pattern:

1. Stage 010 `deploy.sh` installs OpenShift GitOps and the demo Argo CD project.
2. Each stage `deploy.sh` applies its Argo CD `Application`s: one per component for Stages 010–060 (`NNN-<component>`), one for Stage 070.
3. Argo CD reconciles manifests from `gitops/stages/NNN-*/<component>/` (Stage 070: `gitops/stages/070-advanced-app-platform/`).
4. Sync waves and in-cluster Jobs perform cluster-specific setup.
5. Each `validate.sh` confirms that the stage reached the expected operational state.

The deploy scripts do not imperatively install every component themselves. They hand ownership to Argo CD.

## Stage 130 golden

Stage 080 authoring lives in
`stages/130-ai-autonomous-migration/scaffold-repo/quarkus-migration-scaffold/`
on `main`. The Stage 070 `app-migration` template fetches the golden from the
in-cluster GitLab (`rhoai-platform/quarkus-migration-scaffold-v2`). The
`070-gitlab` integration hub publishes both goldens as one ordinary commit from
the Application's reviewed platform revision on every sync; the GitHub copies
only seed the first import and need no push. To publish a golden change, merge
it to `main` and deploy Stage 070. `scripts/demo/bootstrap-scaffold-repos.sh`
prints the published golden URLs (`SCAFFOLD_REPOS=migration` or `agentic` for
one). Do not GitHub-rename historical `quarkus-migration-scaffold`. Do not dest-complete
Operator ack gates or run `kanban daemon --force`. Factory isolation: Stage 080
[SOLUTION-ARCHITECTURE.md](../stages/130-ai-autonomous-migration/SOLUTION-ARCHITECTURE.md)
§8.

### Continuing M1 and recovering a pending unit

If a card is ACCEPTED but post-verdict admission refuses, keep that accepted
step and inspect the next work-list blocker before minting. Do not rerun the
accepted card or reset its attempts. ADR-024 permits up to 16 sealed method
symbols for a complete repository-fragment repair (other units: eight), with
the existing 20-file/160-site limits. Install its tested harness at an idle
boundary with digests/backups. A decision amendment is a product change:
with no live issued card and only the intended amendment dirty, record it from
the destination root, substituting the actual operator and reason:

```bash
python3 .hermes/skills/migration/fix-until-green/scripts/operator-step.py \
  --root . --operator WHO --adr ADR-024 --reason 'WHY' --no-mint
```

Require its recorded commit, known remeasurement, ADMITTED result and clean
product tree before K4 mints the successor. An installation manifest alone
does not establish an accepted baseline for changed `decisions.yaml`.
Package/startup and parity remain separate required evidence; `[0,0,0]` is
not completion.

When an exhausted worker is superseded by an Operator product repair, preserve
its budget. Record the repair using `operator-step.py --no-mint`, then use
`--disposition-only --takeover-deferred <cluster>` with the same Operator.
This requires the recorded repair at HEAD, a clean, freshly verified tree,
an empty measured work list, passing package/startup, and admission blocked
only by the named deferral. It appends a takeover, keeps all attempts and
clearances unchanged, and mints nothing. This releases the hold so the whole
artifact can be compared; it does not establish parity. Run the sealed
`run-parity.py` comparison and `refresh-accepted-parity.py --no-mint` before
K4 continuation. A failed comparison remains an obligation; the takeover
grants no new worker attempts.

`AUTO_START_MIGRATION=false` suppresses workspace startup. Once M1 has been
started, its final step uses `autostart-migration.sh --root /projects/modernized
--after-m1 "$HERMES_KANBAN_TASK"` to continue that native task. The script verifies
its phase and workspace; planner authorization still gates M2. Review checks
M2's actual parent and workspace, so a skipped launcher cannot pass as a handoff.
An explicitly inactive planner still permits analysis-only M1.

`build-worklist.sh` reports verification and baseline as separate phases, retaining
the failing exit code. Use one foreground invocation with timeout 600; diagnose
its recorded failure before retrying. Do not run a second Maven build to find
which wrapper phase failed.

For a `VERIFICATION_PENDING` unit, preserve its candidate and issued seal. A
harness repair belongs at the blocked task boundary with backups, exact file
hashes and regression results. For symbol retirement in a diagnostic-family or package-leaf unit, the
compiler's complete syntax inventory can prove the retired name absent despite
unrelated attribution errors (V16-1: an adapter-owned annotation such as
@CrossOrigin is retired this way; its behaviour stays owed to the adapter). Package retirement requires a complete qualified-name scan with no
references under the retired namespace. For inherited type names the compiler
must resolve the complete ancestor chain independently; unknown ancestry or
static imports still refuse. This does not prove general inheritance or call
relationships. Restore the retained
candidate with `restore-pending.py`, unblock the same native card, and re-run real
verification and `advance.py`. This spends no new attempt and does not approve the
candidate. Keep the original run deadline and append the intervention record.

Pending recovery takes precedence when the issued cluster disappears from the
work list. Read the retained diagnostic first: if it identifies an in-scope
repair, apply it to the restored candidate before fresh acceptance verification.
An explicit stale-evidence refusal is not an interrupted transaction to retry;
resolve its precondition. Retry an interrupted `advance.py` once only when its
verdict is unknown, or inspect the recorded verdict. A nonzero exit alone does
not justify another acceptance call.

When a retained package candidate exposes an unrelated failure outside its
scope, a changed first error is not a package PASS. The Operator may repair
the measured prerequisite on the accepted tree using `operator-step.py
--no-mint` beside the pending card. First require that the candidate is stored
away and no worker is active; commit only the prerequisite paths. Then restore
the candidate and unblock the same card for verification. Neither its scope
seal nor attempt history changes.

After `block_loop_detected`, check the native status: `unblock` does not
resume `triage`. Resolve the new diagnosis first. For an already specified,
sealed card, the shipped native `specify_triage_task` API supports a status-only
transition with title/body/assignee omitted; it retains recurrence counters
and runs normal parent gating. Record the diagnosis in a native comment and
verify those fields and the issued seal remain unchanged. Do not rerun an LLM
specifier or decomposer over the sealed card, or edit its database directly.

### Stage 130 run declaration and launch preflight

Every run created by the `app-migration` template after 2026-09-24 carries
`run-budget.json` (schema `rhoai3.run-budget/v2`), written by the factory into
the destination's initial commit, binding the golden's `run-defaults.json`.
Nothing is stamped by hand and the golden is not edited per run.

Check a destination's declaration from inside its workspace (read-only):

```bash
PYTHONPATH=/projects/modernized/.hermes/lib \
  python3 -m planner.run_declaration --root /projects/modernized --json
```

It prints the effective budget (limits, run, initial commit, declaration time)
or `REFUSE: RUN_DECLARATION_<CODE> …`; autostart records the same refusal in
`.hermes/AUTOSTART-STATUS` and mints nothing. The launch preflight is
run-agnostic; the expected model and wall budget come from the golden checkout:

```bash
WORKSPACE=<project-name> POD=<workspace-pod> GOLDEN_CHECKOUT=<clean golden clone> \
GOLDEN_SHA=<full sha> PLATFORM_SHA=<full sha> \
  bash stages/130-ai-autonomous-migration/run-preflight.sh
```

The version-specific v10/v11 preflight scripts are retired; their original
implementations remain in Git history. A `rhoai3.run-budget/v1` file is refused
as stale. New runs use the current preflight above.

`validate.sh` checks stage readiness and the remaining scaffold/platform checks.
The retired Stage 130 helper suites are no longer part of validation;
the launch preflight has syntax and image/identity regression checks in this entrypoint.

### Stage 130 run isolation

Repeated isolation campaigns are retired by the operator's decision. New runs
use the current read-only preflight against the selected platform and golden.
It still checks the live worker identity, ephemeral kubeconfig, source protection,
secret targeting, pinned database/provisioner images, model, quota, declaration,
and installed harness. Image identities come from the published golden's
`run-defaults.json`; no previous run's receipt is promoted to a new qualification.
Historical PASS and FAIL receipts retain their original meaning.

The factory selects the per-run `<run>-worker` identity through pod overrides.
A worker in `devworkspace-default-rolebinding` still refuses preflight. Restricting
new workers does not revoke existing legacy workspace accounts. Future changes to
that security boundary need a targeted review; they do not silently restart the
retired campaign.

Stage 070 reserves three concurrent workspace slots per user. The next migration
uses one fresh workspace and its bounded startup preflight.
The existing group grant still permits GET of the two named MaaS Secrets;
other-run parity Secrets must remain forbidden. The MaaS route helper loads the
cluster guard and refuses to change a started workspace. Stop through Dev Spaces
before applying that merge, then start again; do not interrupt postStart with a
pod-template change.

The migration template's pre-start initializer clones source onto a separate
volume and writes `.git/rhoai3-source.json`. The worker mounts it read-only;
the destination stays writable. Restarts verify that source commit and refuse
a changed or unrecorded volume. The launch preflight also checks every runtime
container for writable aliases. Do not repair this by chmod, widening Git's
safe-directory setting, or deleting the receipt. Preserve a failed initializer's
logs and volume, then diagnose or create a fresh disposable run.

Provisioning and retirement serialize on a per-run, atomically created ConfigMap
lock. Retirement records `retiring` before deletion and retains the tombstone.
Locks do not expire while an old writer could still operate. If a killed task
leaves a lock, establish its holder TaskRun and pod are stopped before platform
recovery removes it; never unlock a running writer. API errors refuse instead
of being interpreted as missing state. PostgreSQL and CLI images are digest pinned.

Missing resources refuse even after stamping. Legacy compatibility is disabled
by default; an existing workspace needs a platform-owned entry in
`/etc/hermes/migration-legacy-assignments.json`, keyed by DEVWORKSPACE_NAME with
`instance`, `engine`, `port` and `database`. Never place this file in a destination
repository or enable it for a fresh run. No such exception is installed by these
changes. The normal receipt checks engine, host, namespace, port, database,
workspace and scaffolding commit, with the original resource declaration still
present in that ancestor commit. These checks detect inconsistent bindings;
they are not a sandbox against a worker that can alter its environment or invoke
a database client outside the harness.

### Stage 130: after creating a migration workspace

The current app-migration factory stamps the MaaS hostAlias at creation using the Gateway hostname and internal Service IP validated by the catalog generator. Confirm the workspace resolves the MaaS hostname to that internal address; `run-preflight.sh` refuses the public load-balancer path. If routing inputs are stale, refresh the catalog, preserve existing work and run evidence, and create a new workspace through the current template. Do not manually repair the old workspace route.

### Stage 130: authorizing a run (the pilot seal)

Parity resets resolve the JDBC driver from
`verification/build/.work/classpath.txt`, with the OS-account Maven cache as
fallback. Hermes workers have a profile `HOME`; changing it is not the repair
for a missing driver. A missing jar produces an explicit refusal and supports
`--driver <jar>`. Diagnose with that refusal or `--print-plan`, without dumping
environment values or enabling shell tracing. The reset suppresses inherited
tracing and passes credential environment-variable names to Java, which resolves
them internally. The database ownership check still runs before any connection.

The golden ships `pins.planner.activation: not-activated` on purpose, and a
destination that inherits it mints **M1 only** — admission never ADMITs and K4
emits nothing. A run is authorized by sealing the destination's own
`.hermes/pins.json` *after* M1 has produced its evidence bundle, because the
seal names the exact bundle it covers:

```json
"planner": { "activation": "pilot",
             "pilot": { "run_id": "v8",
                        "authorized_by": "<operator>",
                        "evidence_bundle_sha256": "<sha256 of evidence/planning/evidence-bundle.json>" } }
```

Admission then admits that bundle and no other, and K4 re-derives the check
from this file rather than from receipt text or step order. Never overwrite a
destination's `pins.json` with the golden's when syncing a harness repair: the
seal lives there and nowhere else. A worker never edits this block.

First M2 verification runs before admission exists. Its before/after admission
snapshots therefore allow absence, while creation, deletion or changed bytes
during verification remain recorded changes. An unreadable receipt is a typed
failure, not absence. For a blocked-run verifier repair, install the tested
files between tasks with old/new digests and a backup, preserve `pins.json`,
board history and evidence, then unblock the original task. Record this as an
assisted continuation without restarting its time budget. See the
[fresh-M2 recovery](TROUBLESHOOTING.md#fresh-m2-verification-exits-silently-before-producing-its-work-list).

### Stage 130 loop: Operator actions (no human sign-off)

The M3 loop is autonomous by design: every card ends on a mechanical
verdict (`advance.py` ACCEPTED / REVERTED / VERIFICATION_PENDING / DEFERRED).
The implementer completes the card only on ACCEPTED or REVERTED (K2 checks
the loop record). `VERIFICATION_PENDING` and `DEFERRED` are
`kanban_block kind=needs_input`. There is
no approval gate and no reviewer seat on loop cards. What the Operator
does is repair mechanisms, never edit product code or evidence by hand:

| Situation | Operator action |
|---|---|
| A cluster is `VERIFICATION_PENDING` (verification could not conclude) | Do not remint. The cause is typed in `verification/loop/steps.json` `pending[]`: `exposed-outside-scope` (the issued compile failure is gone and the compiler now names something no sealed scope of the card covers), `unassessable-exceptions` (whether the candidate introduces an unhandled checked exception could not be decided), `continuation-budget` (a repair family used one continuation per member), `unproven-repair` (a failing package/boot gate stopped naming the issued obligation), or a harness/environment cause. Fix the prerequisite, then `restore-pending.py --root . --cluster <id>`, `run-verify.sh --mode acceptance`, and `advance.py` on the **same** card. (A family whose compiler moved to another of its own members is not pending: `advance.py` answers `CONTINUE` and the worker keeps going.) |
| A cluster is `DEFERRED` (attempt budget spent) | Find the cause in `verification/loop/steps.json` `rejected[].reason`. A catalog gap or measurement defect is a harness fix (golden + dest install); a design decision is an ADR in `decisions.yaml`. Then record the clearance: `operator-step.py --root . --operator WHO --reason WHY --clear-deferred <cluster>` with the product change that removes the cause, or `--clear-deferred <cluster> --disposition-only` when the cause was a harness defect (no commit, no step; the tree must be clean and verified). Either way the disposition names the cluster, its retry key and what was spent, the budget rises by that, and no attempt or card is deleted. `rewind.py` is for abandoning later steps, not for clearing a deferral. (Dest v8 was recovered this way on 2026-09-11: Operator steps `fbe01cf` and `c4a0270`.) |
| An accepted step turns out to be a false green | Same rewind, to the step before it. Nothing is deleted; the rewound steps and rejections stay on the record as `rewound`. |
| A gate fails with a message that names no file of the tree (the work list says `unlocatable`) | `fix-until-green/scripts/diagnose.py --root . --list` names the failure and what has been spent on it; `--open` starts one of two ten-minute attempts, `--close --conclusion LOCATED\|ENVIRONMENT\|DECISION_REQUIRED\|INCONCLUSIVE --investigated … --finding … --proposed-action …` records it under `evidence/diagnosis/`. The tool grants no write authority — a product change while it runs refuses the close — and closing **discharges nothing**: the blocker stays blocking, and what changes is that the run now carries a conclusion someone can act on. A third attempt refuses: that is the finding that the failure needs a decision, not more looking. |
| A card ended `blocked` although the loop record names its verdict | `hermes kanban complete <id> --summary "…"` from the workspace CLI (the daemon promotes the child only when every parent is done). |
| A card sits in `triage` | Dashboard "→ ready" (the CLI has no triage verb). |
| The worker stalls for minutes then reconnects | Check `providers.custom.stale_timeout_seconds` and `HERMES_STREAM_STALE_TIMEOUT` (900) in the managed config; exact-180 s `DC` lines in the gateway access log mean the default is back. `DC` lines at 400–500 s with the pod socket still established mean the workspace is on the public path: `getent hosts maas.apps.<domain>` must print the internal ClusterIP 172.30.250.250. Since 2026-09-24 the app-migration factory stamps that hostAlias at creation (from the platform entity's validated `rhoai3.redhat.com/maas-host`/`maas-internal-ip`) and `run-preflight.sh` refuses a workspace without it; for a stale workspace, refresh the routing inputs, preserve its work and evidence, and create a new workspace through the current template. |
| The loop refuses `RUN_CONTROL_MISSING`, `HARNESS_RELEASE_MISMATCH` or `MODEL_PROFILE_MISMATCH` (exit 2 from `run-verify.sh`, `advance.py` or `k4_mint.py`) | A v13+ run is governed by the platform's `<run>-run-control` ConfigMap (the migration-run provisioner writes it once from the scaffolding push, mounted read-only at `/etc/rhoai3/run-control`): the contract, the pinned model profile, and the harness release = the scaffolding commit. MISSING: the ConfigMap or its mount is absent; re-run provisioning for the run and restart the workspace. A mid-run harness change is an assisted continuation: commit it, then record `release-rebase.json` (`{"commit": "<sha>", "reason": "..."}`) in the ConfigMap with `oc` (platform authority, not the workspace); it applies at the next workspace start (mount-on-start). A profile change is a new run. |
| `LOOP_ADMISSION` / `LOOP_NO_SUCCESSOR` after an ACCEPTED step (the card is blocked, not done) | `verification/loop/continuation.json` names the stage (`admission-refused`, `mint-failed`, `no-successor`) and the reason. Restore the named prerequisite, then unblock the card; its worker re-runs `advance.py` with the same arguments, which finishes admission and the mint without a second step. K2 refuses `kanban_complete` until the continuation is `minted`. |
| Admission names `RUN_ACTIVATION_FOREIGN`, or the M1 binding is missing | The activation is the platform record plus the write-once M1 binding (`/projects/.platform/run-control-state/binding.json`, never `.hermes/pins.json`). FOREIGN: the record names another run or scaffolding commit; create the run again. A lost binding: re-run the M1 continuation (`autostart-migration.sh --after-m1`), which writes it once. |
| A worker is stopped with `STOP WORKER_TOOL_LOOP` (5 identical successful tool calls) | Nothing to do on the first halt: the runtime records a failed run, the card is respawned once (`max_retries` 2), and the new run's brief carries `candidate_on_tree` (its unaccepted edits and the next action). A second halt blocks the card (`gave_up`, with the guard's metadata). That is a finding for the harness, not something to reclaim again. Requires the ws-080 image with `stages/130-ai-autonomous-migration/hermes-runtime` patches (`/opt/rhoai3/080.pins` `hermes.patched_tree`). |
| A Qwen 3.8 worker is halted with `loop_escalation_restart_halt` | The same stall signature started a thinking-mode escalation twice and came back a third time (Hermes runtime patch 0018; the signature is tool plus argument hash, tool plus result hash, or for `repeat-read` one per stretch without an edit or `typed-repair.py` run). Nothing to do on the first halt: the run is recorded as failed and the card is respawned once; the launch shim sets `HERMES_START_ESCALATED_TURNS` so the retry starts on the thinking profile for `loop_escalation.retry_start_turns` turns. A second halt blocks the card. `grep '\[loop-escalation\]' <profile>/logs/agent.log` shows each start with its `trigger=`. |
| A worker run ends `STOP WORKER_CONTEXT_CEILING` (`context_ceiling_unreachable`) | Hermes runtime patch 0021 projected the next request (last provider prompt figure plus the estimated additions) plus `max_tokens` over the profile's `context_length`, and forced compaction could not bring it under. The request was never sent. The run is recorded as failed and respawned once. A repeat on the same card means one card's working set does not fit the window: check the card's write set against the planner's split limit (`SPLIT_MAX_BYTES` in `compatibility_objectives.py`) and the size of the protected tail. Before 0021 the same condition showed as a request waiting out the 900 s stream stale timeout. |
| A card is titled `… (part i of n: …)` | The planner split an objective whose write set passed 40 KiB on the M2 tree (bytes only, no file-count limit) into ordered parts of at most 40 KiB (`split-large-objectives/v1`). Earlier parts check only their own files; the last part keeps the objective id and verifies the whole objective. Everything that waited on the objective waits on every part, and progress counts the objective once. |
| Auto-start refuses `HERMES_RUNTIME_UNPATCHED` | The workspace image's Hermes is not the tree the harness was qualified on: `/opt/rhoai3/080.pins` `hermes.patched_tree` must equal golden `pins.json` `hermes_agent.patched_tree`. An unpatched image runs without the loop halt, the truncation and quota stops, and the request pacer, while still reporting `hermes 0.20.5`. Repin the devfile to the baked ws-080 digest and create the run again. |
| A worker run ends `STOP MODEL_REQUEST_BUDGET`, `STOP MODEL_QUOTA` or `STOP MODEL_OUTPUT_INCOMPLETE` | These are infrastructure stops, not repair verdicts. The run is recorded as failed, and the card is respawned once. REQUEST_BUDGET: the run spent its allowance (the profile's `quota`, 190 requests/h for Qwen 3.8, counted in `/projects/.platform/run-control-state/requests.log` across main, retry and auxiliary calls). The next free slot was more than 900 s away, so nothing was sent. Let the window roll, then unblock. MODEL_QUOTA: MaaS kept answering 429; check other consumers of the bucket before unblocking. OUTPUT_INCOMPLETE: a response hit the 32768 output cap; the card is too large for one response. |
| A worker's `git checkout`/`restore`/`reset`/`stash`/`clean`/`add`/`commit` is refused by K2 | By design: the loop tools own the index and the tree (`advance.py` commits or reverts, `restore-pending.py` restores). Workers may read with `diff`/`status`/`log`/`show`. |
| Auto-start refuses `STARTUP_MAAS_ROUTE` (no card is minted) | The workspace is not on the in-cluster MaaS route: the refusal names the expected gateway host and Service address and what the pod resolved. A factory-created v13 workspace carries `RHOAI3_MAAS_HOST`/`RHOAI3_MAAS_INTERNAL_IP` and the hostAlias. Refresh the catalog (stage 050 generator) and create the run again. Preserve existing work and evidence before recreating a workspace through the current template. |
| A workspace start fails with `FailedPostStartHook` | Press **Restart** promptly; do not wait for DWO. dest-init's log is on the volume at `/projects/.platform/poststart.log` (appended across attempts); the wrapper's `/tmp/poststart-std{out,err}.txt` die with the pod. A fully successful dest-init can still be killed when an earlier attempt's hook failure stops the workspace (kubelet restarts the container and runs dest-init again on the dying pod; the cards it minted survive). Applying `devspace-ai-tools-init` does not change a running workspace: dest-init regenerates the worker's Hermes config only at workspace start. On 2026-09-24 the applied ConfigMap left the running v12 workspace untouched until it was restarted by hand. From v13 on, a restarted run whose regenerated model profile differs from the one pinned at creation refuses `MODEL_PROFILE_MISMATCH` (see below), so apply such changes between runs. |

## Workspace overlay images

Stages 120 and 130 destfiles pull digest-pinned images from
`quay.io/rhoai3-coding-demo/rhoai3-ws-070` and
`quay.io/rhoai3-coding-demo/rhoai3-ws-080`. Image bake and push are not
part of this repository. Demo users do not build those images.

## Prerequisites

Before deploying the workshop, confirm:

- You are logged into the target OpenShift cluster with sufficient privileges.
- Stage 020 requires AWS capacity for at least one `g7e.2xlarge` RTX PRO 6000 worker (the default pool, one MachineSet per zone); the L40S (`g6e.2xlarge`) pool is optional. Generate and review the pool MachineSets before publishing them; all start at 0 replicas. The stage never scales CPU pools; the observed four CPU workers are distributed 2/1/1 across three pools. Confirm AMI architecture, region/AZ, instance quota and scoped Machine API credentials separately from API dry-run admission.
- `oc`, `git`, `bash`, `curl`, and `jq` are available locally.
- You are using the intended branch and remote for the GitOps source.
- `env.example` has been copied to `.env` and configured with required credentials.
- `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` and `NVIDIA_API_KEY` are set in `.env` for the external models that will be exercised (GPT-6 Luna, Claude Sonnet 5.5, Nemotron 3 Ultra).

Recommended checks:

```bash
oc whoami
oc whoami --show-server
git remote -v
git status --short
```

MCP servers are native Stage 060 components (MCP Lifecycle Operator, project `mcp-servers`): the read-only `openshift-mcp-server` is token-less and in-cluster (bounded ServiceAccount scope; caller tokens honored), the read-write `openshift-mcp-server-rw` requires the caller's OpenShift token. Stage 040 publishes both playground discovery entries with `publish-catalog-mcp.py`; no MCP credentials live in `.env`. Stage 040 also provisions the saved playground agent **OpenShift Ops Assistant** in `demo-sandbox`: the `agent-prompt-provisioner` Sync-hook Job registers the reviewed system prompt `openshift-ops-assistant` in the project's MLflow prompt registry (datascience runtime image, `kubernetes-namespaced` auth, new version only on template change) and the agent ConfigMap references it by name, so a prompt edit in Git becomes a new version on the next sync; check the Job (`oc get job agent-prompt-provisioner -n demo-sandbox`) and **Gen AI studio → Prompts** if the agent warns that its prompt is missing.

## Bootstrap

Run bootstrap once per cluster:

> **Cluster-local step (not in GitOps):** on AWS clusters, raise the default
> ingress ELB idle timeout or long-lived websockets (Dev Spaces IDE
> terminals) and LLM streams die at the AWS Classic ELB default of 60s:
>
> ```
> oc patch ingresscontroller default -n openshift-ingress-operator --type merge \
>   -p '{"spec":{"endpointPublishingStrategy":{"type":"LoadBalancerService","loadBalancer":{"scope":"External","providerParameters":{"type":"AWS","aws":{"type":"Classic","classicLoadBalancer":{"connectionIdleTimeout":"1h"}}}}}}}'
> ```
>
> The MaaS gateway's own ELB is covered in GitOps (`040 gateway.yaml`
> `infrastructure.annotations`); this patch covers the `*.apps` router.

```bash
cp env.example .env
oc login --token=<token> --server=<api>
./stages/010-openshift-ai-platform-foundation/deploy.sh
```

Stage 010 `deploy.sh` performs these actions:

- Applies `gitops/bootstrap/overlays/operator` (OpenShift GitOps operator Subscription).
- Waits for the GitOps CSV and the default Argo CD instance.
- Applies `gitops/bootstrap/overlays/demo` (annotation resource tracking, AppProject `rhoai-demo`, demo cluster-admin binding for the Argo CD application controller, custom health checks for PVCs and related resources).
- Applies the Stage 010 Argo CD Application from `gitops/argocd/app-of-apps/`, substituting `GIT_REPO_URL` and `GIT_REPO_BRANCH` from `.env`.

This broad GitOps control is intentional for disposable demo clusters because the stages create cluster-scoped operators, CRDs, RBAC, Gateway API resources, and OpenShift platform configuration. Do not treat the bootstrap RBAC and wildcard AppProject as a production recommendation. For a shared or long-lived environment, scope Argo CD permissions, destinations, source repositories, and cluster resource allow-lists to the smallest workable set.

Operator Subscriptions use `installPlanApproval: Automatic` so a disposable demo cluster can reconcile without manual OLM approval steps. This is a repeatability choice for the workshop, not a blanket recommendation for production change control.

Monitor GitOps:

```bash
oc get pods -n openshift-gitops
oc get route openshift-gitops-server -n openshift-gitops
```

## Deployment Order

Deploy stages in order:

```bash
./stages/010-openshift-ai-platform-foundation/deploy.sh
./stages/020-gpu-infrastructure-private-ai/deploy.sh
./stages/030-private-model-serving/deploy.sh
./stages/040-governed-models-as-a-service/deploy.sh
./stages/050-model-evaluation/deploy.sh
./stages/060-agent-runtime-and-agentops/deploy.sh
./stages/070-advanced-app-platform/deploy.sh
```

Stage 060 `deploy.sh` covers `060-openshell-identity` and `060-openshell-runtime`; its other three components use `deploy-mcp-platform.sh`, `deploy-native-mcp.sh` and `deploy-console.sh` (see the Stage 060 README).

Stages 110–130 are workflow-only (no deploy scripts, no Argo CD Applications of their own): stage 070 owns their infrastructure as components (identity, devspaces, pipelines, sonarqube, rhdh, mta). Validate their demo prerequisites with each stage's read-only `validate.sh`. Stage 070's deploy script creates no secrets from `.env`; it checks read-only preconditions (node sizing, a Managed and Available internal registry) and Sync hooks create the scoped GitLab, SonarQube and integration identities.

Each script applies its stage's Applications from `gitops/argocd/app-of-apps/`. GitOps stages are the `stages/*/` directories that have `deploy.sh`; each of its Applications is one file in `gitops/argocd/app-of-apps/<directory-name>/<component>.yaml` and renders `gitops/stages/<directory-name>/<component>/`. Workflow-only stages omit `deploy.sh` and have no Application.

| Stage | Argo CD app | Purpose |
|------|-------------|---------|
| 010 | `010-rhoai-operator`, `010-odf`, `010-observability-operators`, `010-rhoai-platform`, `010-access`; separately `010-console-observability`, `010-sandbox-storage` | RHOAI operator, ODF, observability operators and trace roles, DSCI/DSC/Auth/dashboard configuration, demo sandbox access; console plugin list and monitoring UI, sandbox S3 connections |
| 020 | `020-node-feature-discovery`, `020-nvidia-gpu-operator`, `020-kueue`, `020-gpu-machinesets`, `020-gpu-quotas` | NFD, GPU Operator with metrics access and console dashboard, Red Hat build of Kueue, GPU MachineSets, queue quota and hardware profiles |
| 030 | `030-private-model-serving` | Local private model serving |
| 040 | `040-maas-operators`, `040-maas-database`, `040-gateway-governance`, `040-maas-platform`, `040-local-models`, `040-external-models`, `040-model-access`, `040-genai-studio` | MaaS operators, PostgreSQL (data), Gateway with Kuadrant/Authorino, MaaS enablement and monitoring, private models, external models, subscriptions and auth policies, Gen AI studio playground and MCP list |
| 050 | `050-mlflow`, `050-model-qualification`, `050-evalhub`, `050-evaluation-content`, `050-oci-export` | MLflow tracking (data) and curated prompts, Evaluated Models project and qualification pipeline, EvalHub (data), evaluation collections and SWE-bench, OCI export |
| 060 | `060-openshell-identity`, `060-openshell-runtime`, `060-mcp-platform`, `060-agent-tools`, `060-agent-console` | OpenShell identity realm, OpenShell runtime and agent workspaces, native MCP lifecycle enablement, agent MCP tool servers, AgentOps console discovery (each deployed by its own script) |
| 070 | `070-namespaces`, `070-identity`, `070-devspaces`, `070-pipelines`, `070-sonarqube`, `070-mta`, `070-gitlab`, `070-rhdh` | All Stage 070 namespaces, platform Keycloak clients, Dev Spaces, Pipelines + Trusted Artifact Signer + project enrollment, SonarQube, MTA, GitLab and its integration hub, Developer Hub (deployed one at a time in this order) |
| 110 | *(workflow-only)* | AI-assisted development on stage 070 workspaces |
| 120 | *(workflow-only)* | AI-agentic development (OpenCode + skills) |
| 130 | *(workflow-only)* | AI-autonomous migration on the stage 070 MTA stack |

## Validation Strategy

Run static stage-layout validation before cluster work:

```bash
./scripts/platform/validate-stage-flow.sh
```

After stages are deployed, run every stage `validate.sh` in directory order:

```bash
./scripts/platform/validate-stage-flow.sh --live
```

Run the matching validation script after each stage:

```bash
./stages/040-governed-models-as-a-service/validate.sh
```

Validation scripts use these exit codes:

| Exit code | Meaning |
|-----------|---------|
| `0` | All checks passed |
| `1` | One or more critical failures |
| `2` | Warnings only |

Warnings are acceptable only when the script clearly explains that the condition is temporary or expected. For a polished demo, aim for zero warnings.

Check all Argo CD apps:

```bash
oc get applications -n openshift-gitops \
  -o custom-columns='APP:.metadata.name,SYNC:.status.sync.status,HEALTH:.status.health.status'
```

## Argo CD Operations

Argo CD SSO administration uses the dedicated `rhoai-gitops-admins` OpenShift Group with the confirmed `admin` member and an additive operator-managed Argo RBAC mapping. Direct OpenShift User cluster-admin bindings do not supply this Dex group claim. Keep the default Argo role empty; refresh the SSO session after group membership changes. See [the SSO visibility troubleshooting procedure](TROUBLESHOOTING.md#argo-cd-applications-missing-after-openshift-sso-login). The targeted access repair preserves Application revisions and all other Argo settings; it does not require a foundation sync.

Inspect an application, or every component Application of a stage:

```bash
oc get application 040-local-models -n openshift-gitops -o yaml
oc get applications -n openshift-gitops -l demo.rhoai.io/stage=040
python3 scripts/shared/stage_apps.py status 040
```

List resources managed by an application:

```bash
oc get application 040-local-models -n openshift-gitops -o json \
  | jq -r '.status.resources[]? | [.kind,.namespace,.name,.status,.health.status] | @tsv'
```

Find which component Application owns an object:

```bash
python3 scripts/shared/stage_apps.py owner 040 ConfigMap gen-ai-aa-mcp-servers redhat-ods-applications
```

Force a sync from the CLI if needed:

```bash
argocd app sync 040-local-models
```

If the `argocd` CLI is unavailable, use the OpenShift GitOps UI or wait for automated sync. Most applications have automated sync enabled.

### Stage component Applications

Stages 010 to 060 are deployed as component Applications instead of one large one each, so a model switch, a policy change or a failing hook touches only its own component, and data lives in components that never prune it. Each component renders its own folder `gitops/stages/<stage>/<component>/` and is named `<NNN>-<component>`; the stage folder's `kustomization.yaml` renders their union for validation. Components marked `demo.rhoai.io/deploy-order` are applied by the stage `deploy.sh` at one reviewed revision, and validation requires each of them Synced and Healthy at that revision; components marked `demo.rhoai.io/deploy-script` (all of Stage 060, `010-sandbox-storage`, `010-console-observability`, `030-private-model-serving`) are deployed by that script. A component that is expected to report another health state by design names it in its `demo.rhoai.io/accepted-health` annotation (`050-model-qualification` is Suspended while its candidate model is stopped). The layout rules are in `.agents/rules/gitops.md`.

### Moving objects between Applications

Splitting, renaming or re-pointing (new `source.path`) an Application must never delete and recreate its objects. The Applications have no `resources-finalizer`, so deleting one leaves its objects in place, and an Application takes an object over by rewriting its `argocd.argoproj.io/tracking-id`. `scripts/platform/move-applications.py` does this in a safe order:

```bash
python3 scripts/platform/move-applications.py --stage NNN --revision <pushed sha> [--app NAME ...] [--from OLD ...] --dry-run
python3 scripts/platform/move-applications.py --stage NNN --revision <pushed sha> [--app NAME ...] [--from OLD ...]
```

It records the objects and their UIDs, stops automated sync on the `--from` Applications, applies the new Applications at the revision, starts one sync (with the Application's own `syncOptions`) for Applications without automated sync, runs any sync gate (`060-openshell-runtime` needs `setup-runtime.py` after its sync applied `openshell-runtime-ready`), waits for each Application Synced and Healthy, checks every object's tracking id and UID, and then deletes the old Applications without cascade. Without `--from` it only re-points existing Applications. It is safe to re-run after a failure. Run the stage `validate.sh` afterwards. The procedure, its reasons and rollback are in the `gitops-move-applications` skill.

To roll back, re-create the previous Application at its last revision with automated sync off, sync it so it takes the objects back, delete the new Applications (no cascade), then turn automated sync on again.

## Developer Workflow Branch Validation

When validating developer-workflow changes on a sandbox cluster, patch only the existing platform applications that own the affected live resources.

For Stage 110 assisted-development changes, patch Stage 070 (it owns Dev Spaces and the developer portal) to the feature branch being validated:

```bash
# Patch the component that owns the change (070-devspaces for workspaces, 070-rhdh for the portal and templates).
oc patch application 070-devspaces -n openshift-gitops --type=merge -p '{"spec":{"source":{"targetRevision":"<feature-branch>"}}}'
oc annotate application 070-devspaces -n openshift-gitops argocd.argoproj.io/refresh=hard --overwrite
```

Rollback to the stable platform branch:

```bash
# Re-pin every Stage 070 component to the reviewed commit (stage_apps.py deploy 070 pins and orders them).
./stages/070-advanced-app-platform/deploy.sh
```

Do not merge a feature branch to `main` only to validate developer workflow catalog or workspace changes. Do not create Stage `100-170` directories or Argo CD applications until a workflow owns executable artifacts or dedicated cluster resources.

## Stage-Specific Operational Notes

### Stage 010

Stage 010 installs OpenShift AI and platform dependencies. Operator reconciliation can take several minutes.

The new source uses GitOps `gitops-1.21`, RHOAI `stable-3.5`, ODF `stable-4.22` and observability operator subscriptions, all with Automatic approval within their channels. Deployment requires an explicit published revision matching local Stage 010 manifests and scripts; `deploy.sh --revision <reviewed-published-sha>` pins the component Applications to that immutable commit. Do not point Argo at older `main` content. Exact InstallPlan owner and sole-CSV checks precede approval.

Use the existing OpenID accounts `ai-admin` and `ai-developer`; authenticate each through the provider for final acceptance. `scripts/platform/refresh-persona-logins.sh` signs each persona in through the browser into its own kubeconfig (`RHOAI_ADMIN_KUBECONFIG`, `RHOAI_DEVELOPER_KUBECONFIG`), never the default one; Stage 010 `validate.sh` reports a missing or expired persona session as a warning (exit 2) and a wrong user or cluster as a failure. Group membership can be configured before first login; missing User objects remain unverified identities. Set `RHOAI_ADMIN_USER` and `RHOAI_DEVELOPER_USER`, then run `setup-access.sh` after platform/OBC readiness. It assigns groups and the S3 connection without changing OAuth, passwords or provider Keycloak. Group membership remains external to GitOps self-heal. Supply separate private `RHOAI_ADMIN_KUBECONFIG` and `RHOAI_DEVELOPER_KUBECONFIG` files for actual persona checks; impersonated groups are not acceptance evidence.

MLflow uses a dedicated single-instance PostgreSQL 16 workload with a retained gp3 PVC and namespace NetworkPolicy. Database connections are plaintext within its namespace (`sslmode=disable`); this is a durable demo setup without HA or a production database claim. Provider Keycloak storage is not reused. The historical runtime helpers create missing credentials, reuse existing secrets without rotation and use NooBaa-generated S3 inputs with service CA trust.

Fresh Stage 010 owns native Auth; MLflow joins EvalHub/TrustyAI in Stage 050 source. The retained MLflow service and data are now adopted by Stage 050 without recreation. Fresh Stage 010 leaves KServe Removed for Stage 030 enablement; the current cluster has native KServe Managed and Ready under Stage 030. TrustyAI is now Managed for the ready Stage 050 EvalHub service; actual evaluation execution remains pending. Native metrics/tracing acceptance replaces legacy workaround-presence checks; persona-dependent dashboard permissions remain pending actual access evidence. Design and remaining gates are in [the migration plan](migration/010-foundation-plan.md).


Useful checks:

```bash
oc get datasciencecluster default-dsc -o yaml
oc get pods -n redhat-ods-applications
oc get odhdashboardconfig odh-dashboard-config -n redhat-ods-applications -o yaml
```

## Stage operating notes

Point-in-time validation logs from 2026-05 and 2026-07 remain in Git history. The notes below are the current stage operating checks.

### Stage 010 console observability component

The permanent `010-console-observability` Application manages `UIPlugin/monitoring` and the console plugin list (`Console/cluster` `spec.plugins`, from `console-plugins.yaml`); COO manages the generated monitoring plugin and console Perses server. Stage 010 `deploy.sh` deploys it after the foundation components; redeploy it alone with `./stages/010-openshift-ai-platform-foundation/deploy-console-observability.sh --revision <published ref>` and validate with `validate-console-observability.sh`. These commands do not touch the foundation components or deploy held Lightspeed/storage drafts.

The native Perses operator synchronizes the existing RHOAI dashboards/datasources into the console instance. No privileged global datasource or new metrics permission is configured. Native readiness passed. The console Perses accelerator datasource is restricted to platform administrators: installation-administrator proxy queries returned nonempty HTTP 200; genuine `ai-admin` and `ai-developer` returned HTTP 403. The RHOAI `ai-admin` Infrastructure metrics access remains enabled. No additional RBAC is granted; browser checks are user-owned. In the console, reload, open **Observe → Dashboards (Perses)** and select `redhat-ods-monitoring`; then open **Observe → Dashboards → NVIDIA DCGM Exporter Dashboard** for GPU metrics. Model-serving dashboards require later models/traffic. The existing trace dashboard backend error remains a separate issue.

### Stage 020

Stage 020 source installs native NFD, NVIDIA GPU Operator and Red Hat build of Kueue, plus the CPU queue and one GPU queue and hardware profile per GPU type. The three Subscriptions use Automatic approval within their channels, `stable` (NFD), `v26.7` (NVIDIA) and `stable-v1.4` (Kueue), with no `startingCSV`. Installed on 2026-10-14: `nfd.4.22.0-202609291750`, `gpu-operator-certified.v26.7.2` and `kueue-operator.v1.4.3`. No fixed Red Hat-tested RHOAI/operator tuple is claimed. The RHOAI 3.5 "Enabling NVIDIA GPUs" step that deletes the `migration-gpu-status` ConfigMap and restarts the dashboard is not automated. On this cluster the ConfigMap does not exist (checked 2026-10-14), so there is nothing to delete; check for it after an upgrade from an earlier release.

Generate the GPU pool files from one explicitly selected active AWS CPU worker MachineSet with `generate-gpu-machineset.sh --source <machineset> --write`. It writes both pools (RTX PRO 6000 `g7e.2xlarge` per zone as the default, and L40S `g6e.2xlarge`) at 0 replicas with 200 GB encrypted gp3 disks. Review the provider references, then publish the files. The deploy preflight checks published source, existing ownership, provider cert-manager and the healthy Stage 010 Kueue delegation before applying only the Stage 020 component Applications. It never repoints Stage 010 or changes CPU capacity. NFD, driver, validator and DCGM operands remain operator-owned.

Stage 020 patches only `default-dsc.spec.components.kueue` to `Unmanaged` with `autoCreateQueues: false`. The native integration creates the Kueue singleton; GitOps owns ClusterQueues, LocalQueues and profiles. The CPU queue and the two GPU queues (`cq-gpu-rtxpro6000` and the L40S `cq-gpu-reserved-demo`, two units each) are the supported topology; unused zero-quota shared/priority resources and the unconsumed priority class are removed. Global profiles require matching LocalQueues in every consuming project; this stage provisions them only in `demo-sandbox`.

`validate.sh --readiness` checks native readiness and labels that scope explicitly. `--functional` additionally inspects native per-node CUDA validator results and DCGM metrics through bounded local port-forwards. Neither command implicitly creates workloads or proves dashboard access. Full acceptance also requires a bounded queue-admission test and the intended administrator’s GPU Infrastructure dashboard showing current Kueue/DCGM data.

For a one-time reserved queue test, use the native **Pod** integration: the RHOAI-created Kueue configuration does not enable BatchJob. Derive the image and `vectorAdd` command from the successful native CUDA probe, request one GPU, and use the project-allocated nonroot UID with `restricted-v2`, `hostUsers: true`, dropped capabilities, disabled privilege escalation and RuntimeDefault seccomp. Do not add SCC grants or `NVIDIA_VISIBLE_DEVICES=all` to an ordinary allocated-GPU consumer. NVIDIA 26.7 documents that `hostUsers: false` is unsupported with CDI and can cause a sync-socket container-creation failure. [NVIDIA CDI known issues](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/26.7/cdi.html#known-issues).

```bash
source scripts/shared/lib.sh
REPO_ROOT="$PWD"
load_env
check_oc_logged_in
probe=$(mktemp)
project_uid=$(oc --request-timeout=10s get namespace demo-sandbox -o jsonpath='{.metadata.annotations.openshift\.io/sa\.scc\.uid-range}')
project_uid=${project_uid%%/*}
policy_uid=$(oc --request-timeout=10s get clusterpolicy gpu-cluster-policy -o jsonpath='{.metadata.uid}')
oc --request-timeout=10s get pods -n nvidia-gpu-operator \
  -l app=nvidia-cuda-validator -o json > "$probe"
python3 - "$probe" "$policy_uid" "$project_uid" > /private/tmp/gpu-reserved-admission-pod.json <<'PY'
import json,sys
pods=json.load(open(sys.argv[1]))['items']
assert sys.argv[2], 'Native ClusterPolicy UID is required'
ready=[p for p in pods if p['status']['phase']=='Succeeded'
       and any(o.get('uid')==sys.argv[2] for o in p['metadata'].get('ownerReferences',[]))
       and any(i['name']=='cuda-validation' and
               i.get('state',{}).get('terminated',{}).get('exitCode')==0
               for i in p['status'].get('initContainerStatuses',[]))]
assert ready, 'Run native CUDA functional validation first'
p=max(ready,key=lambda p:p['metadata']['creationTimestamp'])
i=next(i for i in p['spec']['initContainers'] if i['name']=='cuda-validation')
command=i.get('command',[]); args=i.get('args',[])
assert isinstance(command,list) and command and all(isinstance(v,str) and v for v in command), 'Meaningful native command required'
assert isinstance(args,list) and all(isinstance(v,str) for v in args), 'Invalid native arguments'
container={'name':'cuda-check','image':i['image'],'command':command,
           'args':['vectorAdd && sleep 20'],
           'securityContext':{'allowPrivilegeEscalation':False,'capabilities':{'drop':['ALL']}},
           'resources':{'requests':{'cpu':'1','memory':'1Gi','nvidia.com/gpu':'1'},
                        'limits':{'cpu':'1','memory':'1Gi','nvidia.com/gpu':'1'}}}
assert command==['sh','-c'] and args==['vectorAdd'], 'Review a changed native command before proceeding'
uid=int(sys.argv[3]); assert uid>=1000000000
pod={'apiVersion':'v1','kind':'Pod',
     'metadata':{'name':'gpu-reserved-admission-pod','namespace':'demo-sandbox',
                 'labels':{'kueue.x-k8s.io/queue-name':'lq-gpu-reserved-demo',
                           'kueue.x-k8s.io/managed':'true'}},
     'spec':{'restartPolicy':'Never','activeDeadlineSeconds':180,'hostUsers':True,
             'securityContext':{'runAsNonRoot':True,'runAsUser':uid,
                                'seccompProfile':{'type':'RuntimeDefault'}},
             'containers':[container],
             'tolerations':[{'key':'nvidia-gpu-only','operator':'Exists','effect':'NoSchedule'}]}}
print(json.dumps(pod,indent=2))
PY
rm "$probe"
```

The explicit opt-in test must use a new Pod name, `kueue.x-k8s.io/queue-name: lq-gpu-reserved-demo`, `kueue.x-k8s.io/managed: "true"`, the existing GPU taint toleration and an active deadline of 180 seconds. A short `vectorAdd && sleep 20` command allows observation of native quota/admission transitions. Default validation and resume never create this workload. Before creation, review the rendered Pod and refuse an existing name; never replace another workload. Run `oc create -f /private/tmp/gpu-reserved-admission-pod.json`; observe `oc get workloads.kueue.x-k8s.io -n demo-sandbox --watch -o yaml` while the Pod executes, and record `oc logs -n demo-sandbox gpu-reserved-admission-pod` plus the completed Pod JSON.

Record the Pod UID and its UID-owned Workload while running: `QuotaReserved=True`, `Admitted=True`, assignment of `nvidia.com/gpu` to `gpu-l40s`, scheduling to a Ready GPU node, successful CUDA output and Pod exit zero. Admission conditions may change after completion releases quota; retain the observed transitions rather than requiring them to stay true forever. Delete only the recorded test Pod with a UID precondition and confirm its Workload is removed. If both cards are occupied, report pending without evicting models, changing quota or adding capacity.

The native MachineSet has `Prune=false,Delete=false`; removing source or the Application is not an uninstall. Day-two cost control scales this exact Stage 020-owned pool to zero. Before deliberate removal, review active GPU workloads, node drain implications, Machine/PVC/data dependencies and AWS resource disposition; explicitly remove only the reviewed MachineSet after those gates. Never change native operator resources or CPU pools as part of this cleanup.

See [the Stage 020 implementation plan](migration/020-gpu-foundation-plan.md) for artifact disposition, installed-schema/native Driver Toolkit evidence and completed GPU/queue qualification. The scoped metrics repair at `797a270b` is Synced/Healthy: genuine `ai-admin` CA-verified native GPU queries return HTTP 200 with capacity 2, while `ai-developer` remains denied. Actual dashboard/profile browser reload remains pending.

### Stage 030

Stage 030 owns the native KServe control plane, `demo-registry` with its operator-managed PostgreSQL database, Model Catalog and Developer Preview Agent Catalog. Stage 040 owns model selection, registry records, runtime/model deployment and MaaS; Stage 030 creates no model or runtime clone.

Fresh deployments use the delegated foundation fields (declared on `010-rhoai-platform`) and the normal Stage 030 deploy entrypoint. The registry handoff from the former single Stage 010 Application is complete, and its one-time protect/omit helpers and bridge overlays are retired; see [the registry handoff](migration/030-serving-foundation-plan.md) for the history. Deployment refuses a registry namespace that Stage 030 does not own.

Native monitoring configuration enables user-workload monitoring and requests gp3-csi storage: 40Gi platform Prometheus and 20Gi user-workload Prometheus, with 7-day retention and size limits. The current provider configuration was absent and platform metrics used ephemeral 15-day storage; this rollout changes those defaults and may reset historical ephemeral metrics. Deployment rechecks named ConfigMap ownership before its Application write and refuses unreviewed provider configuration. The provider Alertmanager Secret remains untouched; the unused fake webhook is removed from source.

Canonical validation passed exact Application reconciliation, current native DSC/KServe and owned workloads, four Bound native monitoring PVCs, registry/database readiness and CA-verified registry/catalog APIs. Native KServe recovered from its initial apply failure without intervention; optional RHCL/LWS advanced capabilities remain Stage 040 work. Independent preservation and genuine-persona API audit passed: registry/database/credential UIDs and empty API digests are unchanged, retained MLflow identity/availability and both bucket identities are preserved, and both personas returned verified-TLS Model Catalog/Agent Catalog responses (10 entries each). This does not repeat the historical MLflow artifact test. Actual dashboard UI acceptance remains separate. See [runtime evidence](migration/030-serving-foundation-plan.md#final-independent-runtime-evidence).

### Stage 040

Stage 040 source targets native OpenShift AI 3.5 AIGateway/MaaS and GenAI Studio. It builds on the Stage 010 foundation and the Stage 030 registry/serving foundation. It is deployed as eight component Applications (see [Stage component Applications](#stage-component-applications)); the cluster's Gateway hostnames are a source patch on `040-gateway-governance`, model replica delegation lives on `040-local-models` and the playground MCP field delegation on `040-genai-studio`. The ordinary deployment's first write is its own immutable component Applications. The DSC component and dashboard fields Stage 040 enables are delegated in Git on `010-rhoai-platform`; the preflight refuses to deploy until they are.

The OLM Subscriptions use Automatic approval within their channels. Installed on 2026-10-14: RHCL 1.4.3, Authorino 1.4.3, DNS operator 1.4.2, Limitador 1.4.2, Service Mesh 3.4.3 and LWS 1.0.1. The native OpenShift Gateway controller supplies the existing accepted GatewayClass; installing the Mesh operator is not proof of an initialized Istio instance. Native operators own generated workloads. Do not patch their CSVs, Deployments or monitoring operands.

The one Gateway has two HTTPS listeners: `api` (shared API hostname, also used by external models) and `qwen3-8` (Qwen 3.8 compatibility hostname). Namespace restrictions and LLMI listener references separate routing. The AdminNetworkPolicy `maas-gateway-boundary` limits the gateway pods' ingress and egress; a new upstream needs an allow rule there first ([gateway-governance README](../gitops/stages/040-governed-models-as-a-service/gateway-governance/README.md)). The layout is a project qualification candidate for scheduler issue INFERENG-6962; actual EPP provenance remains a required independent proof. The gateway resources ConfigMap retains a 1Gi proxy memory reservation and 2Gi limit; change that native source rather than the generated proxy.

The durable PostgreSQL database remains in `models-as-a-service-db`. Runtime credentials are reused, never rotated by deployment. A metadata-only wave-7 credential barrier blocks database/storage wave 8 until the private setup helper supplies them. Native AIGateway creates `redhat-ai-gateway-infra`, where the runtime helper creates or reuses `maas-db-config`. Missing credentials with retained storage/configuration stop deployment. PostgreSQL plaintext transport is constrained by a namespace-scoped NetworkPolicy.

The project-owned `external-models` namespace contains the native ExternalProvider, ExternalModel and MaaSModelRef. `setup-provider-secret.sh` reuses the approved OpenAI credential or supplies approved local input through stdin. Git contains no provider key; the native Secret uses `inference.llm-d.ai/ipp-managed=true`. GPT-6 Luna uses `openai-chat`; function calls require `reasoning_effort=none`, and Responses built-in tools are outside this protocol. Red Hat-hosted MiniMax M2 and its `redhat-models` provider were removed from the governed catalog on 2026-10-09; Claude Sonnet 5.5 uses `openai-chat` against Anthropic's OpenAI-compatible endpoint.

```bash
./stages/040-governed-models-as-a-service/deploy.sh
./stages/040-governed-models-as-a-service/validate.sh --readiness
RHOAI_STAGE040_PERSONA_KUBECONFIG=/private/path/persona-kubeconfig \
./stages/040-governed-models-as-a-service/validate.sh --functional
./stages/040-governed-models-as-a-service/register-model-cards.sh
```

Functional validation creates and revokes only its own expiring synthetic key, with bounded chat/stream/tool-call/authorization/traffic checks. Quota enforcement, per-request EPP proof and user Studio interaction are recorded separately; an API response does not establish all stage acceptance. No GuideLLM benchmark runs implicitly.

GenAI Studio enablement is native OGX. The user creates a project playground through the dashboard and selects an available governed endpoint. The Stage 040 `genai-studio` component pre-provisions one playground asset in `demo-sandbox`: the custom endpoint "GPT-6 Luna (Playground)", whose MaaS key is minted by the `provision-playground-endpoint` Sync-hook Job for the `playground-sandbox` subscription (90-day maximum; a Stage 040 sync renews a key the MaaS API no longer reports active). Its generated pgvector resources remain native service-owned; do not pre-author them or patch generated workloads. Basic remote inference needs no new GPU or bucket; RAG, AutoRAG and AutoML are excluded.

The upstream-image OpenShift MCP server in `rhoai-mcp` and the inactive Slack/BrightData components were retired on 2026-10-09; the read-only consumer endpoint is the native catalog server at `openshift-mcp-server.mcp-servers.svc.cluster.local:8080/mcp` (token-less, bounded ServiceAccount) and the read-write server on its HTTPS Route (caller token). See the [Stage 040 technical plan](migration/040-governed-serving-plan.md) for dispositions, sources and live qualification boundaries.

### Stage 070 — Dev Spaces (devspaces component)

The stage 070 `devspaces` component installs Red Hat OpenShift Dev Spaces and persona namespaces (consumed by the workflow-only stages 110/120/130).

`validate.sh` checks that the component Application is Synced and Healthy and that the standing `agentic-coolstore` workspace in `wksp-ai-developer` and `wksp-ai-admin` clones from the private GitLab `rhoai-workloads/coolstore-inventory-service` project. Stages 120 and 130 create additional workspaces from RHDH factory templates at demo time. The CheCluster uses the `per-workspace` PVC strategy, so each workspace gets its own claim and factory workspaces run beside `agentic-coolstore`. Standing `getting-started-ai-coding`, `coolstore-inventory-service`, and `mca-coolstore` DevWorkspaces were retired. Component detail: [devspaces README](../gitops/stages/070-advanced-app-platform/devspaces/README.md).

Useful checks:

```bash
oc get checluster devspaces -n openshift-devspaces
oc get devworkspace -A
oc get pods -n openshift-devspaces
```

Factory links specify `?revision=main&existing=<project>` so reopening matches
the branch in the workspace. Migration workspace creation also requires its
Kubernetes name to equal the devfile's `MIGRATION_RUN_NAME`. Kubernetes rejects
a second object with that name; the admission policy rejects a suffixed copy.
This applies only to new migration workspaces, not existing workspace updates
or non-migration projects. It does not make Dashboard's separate workspace and
editor creation requests atomic. An interrupted creation must be recovered
under the original name; see the duplicate-workspace entry in troubleshooting.

Run `python3 scripts/demo/check-workspace-creation.py --live` after GitOps sync. It
checks generated links and uses server dry runs to exercise canonical,
suffixed, generated-name, missing/empty/conflicting-run and non-migration
requests without creating any workspace. Existing catalog entries retain
their originally published links; use their exact workspace dashboard link
until their catalog link is deliberately updated.

### Stage 070 — Identity (identity component)

The Stage 070 `identity` component reuses the base platform’s existing `Keycloak/keycloak` service in namespace `keycloak`. Its retained `platform` realm delegates application sign-in directly to the base `sso` realm through `base-sso`; the identity hook preserves existing user subjects and roles and verifies the OpenShift issuer before linking them. GitLab, Developer Hub, MTA and TAS use this application realm; SonarQube uses signed SAML with the base realm. OpenShift, OpenShift AI, Dev Spaces and Argo CD keep their native OpenShift login. See [shared base-platform SSO](#shared-base-platform-sso) for the credential boundaries and qualified flows.

Useful checks:

```bash
oc get keycloak keycloak -n keycloak -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}'
oc get keycloakrealmimport platform-realm -n keycloak -o jsonpath='{.status.conditions[?(@.type=="Done")].status}'
oc get route keycloak -n keycloak -o jsonpath='{.spec.host}'
oc get oauth cluster -o jsonpath='{.spec.identityProviders[*].openID.issuer}'
```

### Stage 070 — MTA (mta component)

The stage 070 `mta` component selects Migration Toolkit for Applications operator/operands 8.3.1 (consumed by workflow-only Stage 130). The exact `stable-v8.3` Manual InstallPlan is approved only for `mta-operator.v8.3.1`; the workspace CLI/RPC stays at its separately qualified 8.3.0. Native Hub Agents use `Gateway/maas-qwen` and the existing owner-bound MaaS subscription. They do not depend on Solution Server. The Lightspeed proxy remains enabled with the same MaaS base URL; optional Solution Server is disabled pending its vendor dependency correction. Keeping `kai_llm_proxy_enabled: true` retains the operator's shared `kai-db` deployment, credentials and PVC. Existing Hub OIDC and platform-realm SSO remain enabled. The `configure-mta-platform-sso` hook maintains that integration, and `mta-hub-workspace-config` publishes the launcher configuration. Stage 130 analysis workspaces come from the `app-migration` factory destfile; Stage 130's validator covers that contract.

Useful checks:

```bash
oc get tackle mta -n openshift-mta -o yaml
oc get deployment -n openshift-mta
```

### Stage 070 — Pipelines (pipelines component)

The Stage 070 `pipelines` component installs OpenShift Pipelines and Trusted Artifact Signer, tunes the cluster `TektonConfig`, and runs the GitLab project enrollment coordinator in `app-platform-build`. Each enrolled project gets its own `<project>-dev` namespace, Tekton pipeline and Argo CD runtime Application; Stage 130 migration runs are provisioned from the same namespace. Contents, ordering and checks: [pipelines README](../gitops/stages/070-advanced-app-platform/pipelines/README.md).

### Stage 070 — SonarQube (sonarqube component)

The Stage 070 `sonarqube` component runs SonarQube Community Build with its own PostgreSQL database in `sonarqube`, defines the `AI Platform Gate` quality gate and gives `app-platform-build` the control token the pipelines use to mint project-scoped scanner tokens. Sign-in uses SAML with the base `sso` realm. Contents, ordering and checks: [sonarqube README](../gitops/stages/070-advanced-app-platform/sonarqube/README.md).

### Stage 070 — GitLab (gitlab component)

The Stage 070 `gitlab` component runs GitLab Community Edition in `gitlab-system` with its PostgreSQL, Valkey, Gitaly storage and NooBaa buckets. Its integration hub creates the GitLab groups, service users, tokens and repository imports, and writes the credentials and configuration that Dev Spaces, Developer Hub, the enrollment pipeline and Argo CD consume. Contents, ordering and checks: [gitlab README](../gitops/stages/070-advanced-app-platform/gitlab/README.md).

### Stage 070 — Coolstore dev environment

Stage 070 declares only the `coolstore-dev` namespace for Coolstore (`namespaces/namespaces.yaml`, labelled `rhoai3.redhat.com/pipeline-project: "true"`). The workload reaches it in four steps:

1. **Namespace.** `070-namespaces` creates `coolstore-dev` with the enrollment label.
2. **GitLab enrollment.** The GitLab setup hook (`gitlab/bootstrap-scm.py`) imports `coolstore-inventory-service` into the `rhoai-workloads` group, commits the platform-reviewed runtime (`gitlab/coolstore-runtime.json`) as `k8s-run/platform-app.yaml`, and records the seed in the immutable ConfigMap `gitlab-import-seeds` in `app-platform-build`. The enrollment reconciler and the project's enrollment Job (both `pipelines/gitlab/reconcile.py`) then create the `project-coolstore-inventory-service` Application (pipeline, webhook listener), the delivery repository and the `runtime-coolstore-inventory-service` Application.
3. **Internal registry digest.** The project pipeline builds into the internal registry (`image-registry.openshift-image-registry.svc:5000/coolstore-dev/coolstore-inventory-service`). Until the first green run the declared runtime references the `:bootstrap` tag.
4. **Delivery Git.** The promotion step (`pipelines/project-pipeline/promote.py`) writes the runtime with the image pinned by `@sha256` digest to `rhoai-delivery/coolstore-inventory-service-deployment`; `runtime-coolstore-inventory-service` syncs the Deployment, Service and Route from that repository.

`deploy.sh` does not seed a pipeline run or create pull secrets. An empty `coolstore-dev` or an image pull failure on a fresh cluster means enrollment or the first pipeline run has not completed; check the steps above in order. Component detail: [gitlab README](../gitops/stages/070-advanced-app-platform/gitlab/README.md), [pipelines README](../gitops/stages/070-advanced-app-platform/pipelines/README.md), [namespaces README](../gitops/stages/070-advanced-app-platform/namespaces/README.md).

Useful checks:

```bash
oc get configmap gitlab-import-seeds -n app-platform-build
oc get application project-coolstore-inventory-service runtime-coolstore-inventory-service -n openshift-gitops
oc get pipelinerun -n coolstore-dev
oc get deployment coolstore-inventory-service -n coolstore-dev -o jsonpath='{.spec.template.spec.containers[0].image}{"\n"}'
oc get deployment,route -n coolstore-dev
curl -s https://$(oc get route coolstore-inventory-service -n coolstore-dev -o jsonpath='{.spec.host}')/q/health/ready
```

### Stage 070 — Developer Hub (rhdh component)

The stage 070 `rhdh` component installs Red Hat Developer Hub and configures OIDC through the existing Keycloak `platform` realm; MTA 8.3's built-in Hub OIDC provider federates to that same realm (`platform-sso` IdentityProvider). The application realm delegates sign-in directly to the base `sso` realm as described below. Existing application subjects, catalog references and role assignments remain stable.

The RHDH catalog location is runtime-derived from the Stage 070 Argo CD Application source. This avoids loading catalog entities from `main` when the demo is deployed from a validation branch or fork. Golden-path template Locations now use the same immutable platform commit through the private GitLab mirror. The catalog bundle replaces stale Locations as one unit; do not keep old registrations alongside the new bundle.

After a cluster suspend/resume, restart RHDH before demoing: the long-running backend can hold stale connections from before the suspend and fail OIDC sign-in with 504 errors even though Keycloak is healthy (`oc rollout restart deployment/backstage-developer-hub -n rhdh`; see TROUBLESHOOTING "Red Hat Developer Hub OIDC Sign-In Fails With 504 Gateway Timeout").

Useful checks:

```bash
oc get backstage developer-hub -n rhdh -o yaml
oc get pods -n rhdh
oc get route -n rhdh
oc get consolelink rhdh -o yaml
oc get secret rhdh-secrets -n rhdh -o jsonpath='{.data.RHDH_CATALOG_URL}' | base64 -d
```

## Updating The Demo

For GitOps-managed behavior:

1. Edit manifests under `gitops/`.
2. Commit and push changes to the branch referenced by the Argo CD Applications.
3. Let Argo CD reconcile or manually sync.
4. Run the matching `validate.sh`.

For documentation changes:

1. Edit `README.md`, `stages/*/README.md`, or files under `docs/`.
2. Run `git diff --check`.
3. Check that links and references still match the repo.

## Resuming GPU-Backed Stages After Shutdown

Stage 020 supplies the GPU-capacity resume workflow consumed by Stage 040 models. Use this after the GPU MachineSet was scaled to zero for cost saving, or after the demo environment has been stopped and started again.

```bash
./scripts/platform/resume-gpu-demo.sh status
./scripts/platform/resume-gpu-demo.sh resume
```

The `resume` command requests a sync of the existing Stage 020 revision, scales the selected pool's verified MachineSet up (default: one RTX PRO 6000 `g7e.2xlarge` in `us-east-2a`; `GPU_POOL=l40s` selects the L40S pool, `GPU_ZONE` another zone, and an explicit replica count up to two), waits for native GPU/operator readiness and runs readiness validation. It does not delete Machines, patch node labels, sync model stages or repair generated ReplicaSets. Model and functional acceptance remain separate; scale-to-zero is intentional cost control, not a passing GPU-capacity check.

To scale GPU capacity down for shutdown (every reviewed GPU pool goes to zero, so no forgotten pool keeps billing):

```bash
./scripts/platform/resume-gpu-demo.sh down
```

Kueue queue resources survive normal cluster restarts because they are Kubernetes API objects. Kueue does not create cloud GPU nodes by itself; GPU node lifecycle remains a platform capacity action through the MachineSet.

After any cluster suspend/resume, also restart the Stage 070 Developer Hub deployment — its long-running backend holds stale connections across the suspend and OIDC sign-in fails with 504 errors until it is bounced (see the Stage 070 Developer Hub notes and TROUBLESHOOTING).

## Coolstore Demo Reset

For the registered GitLab project, set `GITLAB_OPERATOR_TOKEN_FILE` to your uncommitted scoped operator token file and run `./scripts/demo/reset-coolstore-demo.sh --yes`. It restores the immutable registered baseline with a normal commit, stops only matching workspaces and retains their PVCs and local changes. No force push or workspace recreation is performed. The commit triggers the project’s main-branch pipeline and immutable image promotion.

Legacy GitHub projects have no GitLab registration. Do not use the GitLab lifecycle helper for them or fabricate a registration. Their cleanup remains a separately reviewed operation: inventory exact repository, webhook, Argo app, DevWorkspace, PipelineRun, Secret and PVC identities; archive local/evidence data; stop the matching workspace and disable the obsolete writer/webhook; remove only confirmed retired runtime resources. Keep repositories, PVCs and evidence until their owners explicitly authorize deletion. No broad namespace or historical cleanup is part of this release.

## Qwen 3.8 INT4 alongside Qwen 3.6

> Superseded on 2026-10-13 by [Model serving study and default model](#model-serving-study-and-default-model-2026-10-13): the served model is now `qwen3-8-27b` (NVFP4 on RTX PRO 6000) and Qwen 3.6 is retired. The INT4 history below is kept for the record; the Stage 050 evaluation candidate still serves the INT4 build.

`qwen3-8-27b-int4` is a second governed local model. It is not a Red Hat validated model. The validated-model matrix reviewed on 2026-09-22 has no `RedHatAI/Qwen3.8-27B-INT4` entry and no modelcar. The service runs on the installed RHOAI 3.4 operator vLLM through `hf://RedHatAI/Qwen3.8-27B-INT4:7fb3aaca2d21c0db4716572945208db40cef9966`. Recorded runtime image: `registry.redhat.io/rhaii/vllm-cuda-rhel9@sha256:dd65c7ed88a9369b962f1299ed19c6c8819ff0a64595c10e32f1e82ab0750e27` (running image ID `sha256:d2ed07d307845135c089bc7644b64734b9349d517abf746c9aa0aa23ed263da5`, vLLM `0.18.0+rhaiv.14`). The retained context is `--max-model-len=262144`. A 246077-token needle recall passed with a 512-token output reserve. A 128-token cap failed that shape at 222077 tokens. Stage 040's README has the comparison with Qwen 3.6.

Qwen 3.8's declared server defaults use its [recommended non-thinking profile](https://huggingface.co/Qwen/Qwen3.8-27B#best-practices): temperature 0.7, top_p 0.8, top_k 20, min_p 0.0, presence_penalty 1.5, repetition_penalty 1.0, and `--default-chat-template-kwargs={"enable_thinking":false}`. The Stage 070 Hermes profile explicitly supplies the same values, so each new run keeps its own sampling when server defaults change. Existing run-control profiles are not rewritten. Thinking-mode clients must explicitly set `enable_thinking: true` and the recommended thinking sampling (temperature 1.0, top_p 0.95, top_k 20, min_p 0.0, presence_penalty 0.0, repetition_penalty 1.0); changing the mode alone does not select another sampling profile.

Apply these serving arguments through the Stage 040 GitOps sync. They trigger a workload rollout: at one replica, the rolling strategy requests a second GPU before retiring the old pod. Schedule the rollout with available capacity or a planned serving interruption. Read back the Ready workload's arguments and the Stage 070 profile ConfigMap after sync; a local manifest check does not establish live adoption. Roll back sampling by reverting the serving/profile change together, preserving existing run-control records.

The Stage 020 provisioner creates a GPU MachineSet at 2 replicas only when none exists. This cluster's MachineSet `cluster-grnl8-ng7jk-gpu-us-east-2b` already existed at 1 replica, so it was scaled to 2 with `oc scale`. Instance type, disk, labels, and taints were left as they were.

Rollback:

1. Delete `LLMInferenceService/qwen3-8-27b-int4` and `MaaSModelRef/qwen3-8-27b-int4` in `models-as-a-service`.
2. Remove only the `qwen3-8-27b-int4` entries from the developer `MaaSSubscription` and `MaaSAuthPolicy` objects. Do not change `qwen3-6-27b` quotas. Stages 050-080 client defaults point at `qwen3-8-27b-int4`; revert those defaults in the same rollback.
3. Before scaling the GPU MachineSet down, list Machines and match `status.nodeRef` to nodes:

```bash
oc get machine -n openshift-machine-api -l machine.openshift.io/cluster-api-machineset=cluster-grnl8-ng7jk-gpu-us-east-2b \
  -o custom-columns=NAME:.metadata.name,PHASE:.status.phase,NODE:.status.nodeRef.name,TYPE:.spec.providerSpec.value.instanceType
oc get pod -n models-as-a-service -l app.kubernetes.io/name=qwen3-6-27b,kserve.io/component=workload \
  -o custom-columns=NAME:.metadata.name,NODE:.spec.nodeName
```

Scale to 1 only after the Machine that is not hosting `qwen3-6-27b` is identified. Machine API deletes one Machine to meet the lower replica count; name that Machine in the change record before scaling.

An update of either single-replica model uses RollingUpdate `maxSurge: 25%`, which schedules a second pod first. With both GPUs occupied that pod stays pending. Delete the previous workload pod for the model being updated so its GPU is released. Do not add a third GPU node for a rollout.

## Cleanup Guidance

The Argo CD Applications intentionally do not include finalizers. Deleting an Application by itself orphans the resources that it created.

For a full cleanup, prefer an explicit Argo CD cascade delete from the OpenShift GitOps UI or CLI:

```bash
for app in $(python3 scripts/shared/stage_apps.py names 070); do argocd app delete "$app" --cascade; done
for app in 060-agent-console 060-agent-tools 060-mcp-platform 060-openshell-runtime 060-openshell-identity; do argocd app delete "$app" --cascade; done
for app in $(python3 scripts/shared/stage_apps.py names 050); do argocd app delete "$app" --cascade; done
for app in $(python3 scripts/shared/stage_apps.py names 040); do argocd app delete "$app" --cascade; done
argocd app delete 030-private-model-serving --cascade
for app in $(python3 scripts/shared/stage_apps.py names 020); do argocd app delete "$app" --cascade; done
argocd app delete 010-sandbox-storage --cascade
argocd app delete 010-console-observability --cascade  # Console list is Prune/Delete=false
for app in $(python3 scripts/shared/stage_apps.py names 010); do argocd app delete "$app" --cascade; done
```

Delete in reverse deployment order. Review GPU MachineSets and persistent volumes separately before removing them because cloud infrastructure and storage cleanup can be environment-specific.

If the `argocd` CLI is unavailable, use the OpenShift GitOps UI and choose cascade deletion. Avoid broad namespace deletion unless you have confirmed no shared cluster resources are still needed.

## When To Use Which Document

| Need | Use |
|------|-----|
| Understand the architecture and value | `README.md` and stage READMEs |
| Deploy and validate the environment | This file |
| Diagnose failures | `docs/TROUBLESHOOTING.md` |
| See exact executable behavior | `deploy.sh` and `validate.sh` scripts |

## References

- [OpenShift GitOps documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_gitops/)
- [Red Hat OpenShift AI documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/)
- [OpenShift CLI documentation](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/cli_tools/openshift-cli-oc)
- [Argo CD documentation](https://argo-cd.readthedocs.io/)

## Model serving study and default model (2026-10-13)

**Decision.** The default private coding model is `qwen3-8-27b`: `RedHatAI/Qwen3.8-27B-NVFP4` (pinned `2889ddee`) on one NVIDIA RTX PRO 6000 Blackwell Server Edition (`g7e.2xlarge`, Stage 020 profile `gpu-rtxpro6000`, queue `lq-gpu-rtxpro6000`). The model id is format-neutral. `Qwen/Qwen3.8-27B-FP8` (pinned `017b9c7a`) is prepared as a one-line alternative; the final choice follows the next Hermes migration run, because the open question there is agent looping behaviour, which benchmarks do not measure. Qwen 3.6 is removed (its LLMInferenceService, MaaSModelRef, subscriptions and gateway listener); its registry entry remains as history.

**Identifying the deployed quantization.** The display name (`Qwen3.8 27B NVFP4`), the `openshift.io/description` (`Model id: qwen3-8-27b, quantization: NVFP4, context 262,144-token`, fixed configuration only) and the label `demo.rhoai.io/quantization` on the LLMInferenceService and MaaSModelRef; the FP8 component switches all three. `register-model-cards.sh` registers the deployed checkpoint with deployment linkage and every prepared format component's checkpoint without it, so the registry shows `Qwen3.8-27B-NVFP4` and `Qwen3.8-27B-FP8`, each description stating its quantization.

**Method.** Same qualification pipeline (v11) for every arm: latency (8K-token prompt, 8 concurrent agents), throughput (64 requests), LiveCodeBench v6 and the python-tasks collection (MBPP, HumanEval). Serving args identical to production (MTP speculative decoding with 3 tokens, batched tokens 16384, async scheduling, FP8 KV cache, 262,144-token window). A long-context check hid a fact in a 26K/130K/248K-token prompt and asked for it. Cost per million output tokens is the On-Demand price divided by measured throughput. Single runs; LiveCodeBench varies about plus or minus 0.03 run to run.

| Qwen 3.8 | TTFT 8K x8 | tok/s | ITL | $/M output | LCB / MBPP / HumanEval | Full 262K requests in KV |
|---|---|---|---|---|---|---|
| NVFP4, RTX PRO 6000 | 776 ms | 302.6 | 11.2 ms | 3.09 | 0.21 / 0.91 / 0.85 | 6.37 |
| FP8, RTX PRO 6000 | 966 ms | 249.8 | 12.3 ms | 3.74 | 0.20 / 0.87 / 0.90 | 5.77 |
| BF16, RTX PRO 6000 (reference) | 1,448 ms | 155.6 | 18.4 ms | 6.00 | 0.24 / 0.89 / 0.90 | 3.29 |
| INT4 W4A16, L40S (former) | 2,565 ms | 92.6 | ~16 ms | 6.73 | 0.24-0.22 / 0.88 / 0.87 | about 1 |
| INT4 W4A16, one A100 40 GB | 2,806 ms | 86.5 | 14.1 ms | 8.80 (all 8 GPUs busy) | not run | not run |

All three RTX PRO 6000 formats recalled the hidden fact at 248K prompt tokens (first token after 53-62 s). NVFP4 runs on vLLM's native FlashInfer CUTLASS NVFP4 kernel. INT4 W4A16 and MXFP4 were not carried onto Blackwell: INT4 runs weight-only with BF16 compute (NVFP4 has the same footprint with FP4 compute) and MXFP4 uses coarser scaling.

**Instance and capacity findings (us-east-2, On-Demand, 2026-10-13).** Prices from the AWS pricing feed: `g6e.2xlarge` 2.242, `g7e.2xlarge` 3.363, `p4d.24xlarge` 21.96 (8 GPUs), `p5.4xlarge` 6.88 $/h. `g7e.2xlarge` launched within seconds in `us-east-2a`. `p5.4xlarge` (H100) returned `InsufficientInstanceCapacity` in all three zones for 25 minutes; the "try another zone" text in that error is generic and every zone named the other two. `p4d.24xlarge` (A100) launched in 2a and 2b but one A100 was slower than one L40S for this model and AWS sells it only as an 8-GPU node; the A100 MachineSets were removed. Spot is not available in this account: every Spot request was refused by an organization service control policy. `g6e.4xlarge` would not help: on `g6e.2xlarge` vLLM peaked at 1.1 CPU cores and 22.5 GB memory with no CPU throttling.

**Switching to FP8.** Enable the component in `gitops/stages/040-governed-models-as-a-service/local-models/kustomization.yaml`:

```yaml
components:
  - components/qwen38-fp8
```

It swaps the checkpoint and sets `VLLM_USE_DEEP_GEMM=0` (required on this GPU, see TROUBLESHOOTING). Publish, re-pin Stage 040, then run `register-model-cards.sh`; the registry entry takes the checkpoint name (`Qwen3.8-27B-FP8`). Clients keep the same `qwen3-8-27b` id.

**Capacity probe.** `scripts/platform/gpu-capacity-probe.sh --pool rtxpro6000 [--zones "a b c"] [--gpu]` scales one zone's zero-replica MachineSet to one, records AWS's answer under `tmp/`, and always returns to zero.

**Study records.** `tmp/model-study/STUDY.md` (gitignored) holds the per-run log, `results.jsonl`, the ISVC generator and the long-context test.

## Model selection record (current estate and history)

The demo's default posture serves ONE local model, `qwen3-8-27b`, on 1×
`g7e.2xlarge` (1× NVIDIA RTX PRO 6000, 96 GB) since 2026-10-13 (see the
serving study above), governed through the MaaS gateway. The one-model
posture was first a measured cost decision on L40S (2026-07-25): single-stream decode parity between the dense 27B
and the 35B MoE (18.8 vs 17.7 tok/s) plus better quality at both harness
roles made a dedicated coding GPU unnecessary for presenter-driven use.
The MoE's real advantage (3.4× aggregate throughput at 4-way concurrency,
7.5s vs 25.8s per request) matters only for multi-user hands-on sessions
— for those, enable the workshop overlay below.

| Seat | Model | Why selected | Serving notes |
|---|---|---|---|
| Hermes main / Kanban workers | `qwen3-8-27b` via named provider `qwen38` (`api_mode: chat_completions`) | AD-008 primary; default of `model-profiles.json` and the Stage 130 golden `run-defaults.json` since 2026-10-13. MaaS gateway; declared context 220,000 under the served 262,144 window; output cap 8,192. | NVFP4 on one RTX PRO 6000 (`g7e.2xlarge`); FP8 prepared as a component. Qwen 3.6 retired. |
| OpenCode coding worker | `qwen38/qwen3-8-27b` | Same default; the only enabled provider | Common MaaS `/v1`, canonical namespace-qualified model ID, same authorized API key |

**How to add another Hermes model:** named `providers.<name>` entry + managed `.env` secret + explicit `models:` map (`discover_models: false`). Change `model.default` only if it is the new main.

**Workshop capacity overlay (historical; its folder
`040/.../local-models/optional/qwen35b-workshop/` no longer exists):** `qwen3-6-35b-a3b` — the MoE
coding worker for multi-user sessions. Enable: scale the GPU machineset
to 2, add the overlay + policy refs, re-mint the key (steps in the
overlay README). Its registry card stays active, marked
`deployment_status: workshop-overlay`.

**Retired seats** (registry keeps the archived cards — never delete):

- `nemotron-3-nano-30b-a3b` — retired after the stage 130 harness A/B: empty
  tool calls and instruction drift in long orchestration sessions (a
  small-model failure mode; the same packet later succeeded first-pass on a
  stronger model).
- `gemma-4-26b-a4b` — never served: the RHOAI 3.4 vLLM runtime's Transformers
  predates the gemma4 architecture (modelcars can publish ahead of runtime
  support — always arch-check the serving image before a swap; the vLLM
  native model registry is the authoritative gate, not transformers imports).
  Revisit at RHOAI 3.5.
- `granite-4-0-h-small` — served correctly but retired on benchmarks
  (τ²-Bench 17%, AA Intelligence 11): capability, not compatibility.

**Parked serving experiments (BACKLOG):** 35B NVFP4 variant (official
modelcar exists; blocked on vLLM #34694 — NVFP4 Marlin emulation garbles
BF16 output on Ada/sm89), MTP speculative decoding (`qwen3_next_mtp`),
27B modelcar graduation.

## Migration worker identity

Stage 070 provisions `<run>-worker` with only the init ConfigMap GET and named `container-build` SCC use. The factory pod-overrides selects that ServiceAccount. The DevWorkspace Operator's leftover generated account keeps its default Role and must not be mounted by new workers. Existing workspace identities are not revoked. Effective permissions also include the existing group GET grants for `maas-devspace-api-keys` and `workspace-maas-credentials`; no other-run parity Secret access is allowed.

Qualify isolation on a fresh disposable workspace with migration auto-start disabled, using `run-preflight.sh` and a receipt for the golden and platform under test. A standalone Job or a passing fixture is not that qualification.

The factory sets the route at creation. For stale routing, preserve work and run evidence, refresh the catalog inputs, and create a new workspace through the current template.


The final canonical Stage 010 validator against deployed `f38d84c0` returned exit 1: **30 checks passed and 2 failed**. Both failures are missing real administrator/developer persona kubeconfigs. The 11 MLflow readiness checks and native registry/metrics/exact-trace functional probes passed. Configured group memberships and synthetic service authorization do not replace authenticated persona acceptance. No full-stage pass is claimed.


### Stage 040 current acceptance (2026-10-05)

Stage 040 is Synced/Healthy at `6ab5e6f9ee35c89d189c6f48973f8bf40be620f1`. Both private Qwen models and Red Hat MiniMax M2 passed governed completion/streaming; MiniMax is available through existing personal grants at unchanged limits, while workspace grants remain local-only. The isolated own-subscription quota test returned 200 then 429, revoked its key and UID-deleted its subscription; native policy restoration and retained resource identities were independently confirmed.

The GenAI Studio API-key-loading incident is repaired at the backend: current native Authorino TLS rollout and genuine subscriptions/key-search JSON requests pass. Refresh Studio and check key listing and the native project playground yourself. GPT-6 Luna is registered but upstream account credits are exhausted; no further GPT calls or quota increases are warranted until credits are restored. EPP execution remains unqualified because the targeted counter series did not appear, despite successful authenticated Pod-targeted inference. Full Stage 040 acceptance is therefore incomplete. See [the current technical record](migration/040-governed-serving-plan.md#final-bounded-runtime-evidence) for evidence and limits.

### Stage 050 service foundation (2026-10-06)

Stage 050 reconciles at `af39a8b7`; core protection/omission uses `eb75e665` and retains all non-MLflow resources. Seven existing MLflow resources were adopted with retention protection; database credentials and the artifact bucket were reused. The private bridge baseline and both readbacks contain equal workspace records and artifact metadata (one sandbox experiment/run/artifact listing). Native MLflow, TrustyAI and EvalHub are ready; EvalHub uses a separate Bound 10Gi PostgreSQL volume. The native DB projection/defaults validator correction is published at `542913f1` and requires no resource redeploy.

Independent acceptance passed unchanged seven-resource ownership/UID/specs, runtime credential identities and all original workspace records/artifact metadata. Both genuine personas passed CA-verified service discovery; foreign tenants and invalid tokens were denied. Evidence is `/private/tmp/stage050-independent-poststate.json`. No evaluation or inference was run, and both Qwen replicas and GPU pools remain zero. The ten-sample chat-compatible benchmark still needs selection and a separately approved model resume. Readiness/discovery is service evidence; completed benchmark results linked to a FINISHED MLflow run are a later acceptance gate. Evaluation dashboard browser checks remain user-owned and Technology Preview. See [the Stage 050 record](migration/050-model-evaluation-plan.md).

### Stage 040 cost dashboards (2026-10-09)

The Observability page's **Cost per token** and **Tokenomics · break-even (live)** tabs are Stage 040 PersesDashboards (`gitops/stages/040-governed-models-as-a-service/maas-platform/observability/`, generated by `gen-cost-dashboards.py`). Prices (`price_prompt`, `price_completion`, `price_blended`, `api_price_*`) and `gpu_hourly_cost`/`gpu_count` are dashboard variables: change them in the tab for a what-if, change the generator defaults for a durable value. Validate a dashboard change with `oc apply --dry-run=server -k …/observability` (schema `perses.dev/v1alpha2`) and by running its PromQL against the RHOAI datasource (`svc/thanos-querier-data-science-thanos-querier:10902`). The observability stack review of 2026-10-09 (all Monitoring conditions True, six product dashboards present, scrape labels per the guide) and its product-level gaps are in TROUBLESHOOTING and BACKLOG.

### Stage 050 governed evaluations (2026-10-09)

Since 2026-10-12 every evaluation runs in the Evaluated Models tenant (`evaluated-models`); AI Coding Sandbox is no longer an EvalHub tenant. Stage 040 carries the `model-qualification` MaaS subscription and auth policy for both private Qwen models (5,000,000 tokens per hour) and the external judge models, owner `evaluated-models/evalhub-maas-key-provisioner`. Stage 050's `provision-evalhub-model-auth` Sync hook mints the key and keeps it in the tenant Secret `evalhub-model-auth-maas` (`api-key`, plus `key_id`, `expires_at`, `subscription`); the hook re-uses the key while the MaaS API reports it active and re-mints it after expiry (first key expires 2027-01-07) or revocation on the next Stage 050 sync. The tenant evaluator Role now carries the documented MLflow experiment rule.

Run an evaluation with `stages/050-model-evaluation/submit-evaluation.sh --model-name <maas model id> [--num-examples N]` (the caller's token, tenant `evaluated-models`, experiment `model-evaluations`); follow with `--status <job id> --wait` or in **Develop & train → Evaluations**. Coding v1 (`lcb:codegeneration_v6`) is sized by three limits in 3.5.1: 16 samples per request from lighteval, a 30-second sidecar model-request timeout, and the adapter's one-hour benchmark limit; the helper's code-only system prompt and 512-token cap keep requests short, and the evaluated model must admit at least 16 concurrent sequences. The 2026-10-09 probe (one problem) proved key resolution, dataset download, scoring and the FINISHED MLflow run on the two-sequence Qwen 3.8 profile, but its model calls timed out at 30 seconds (see TROUBLESHOOTING), so the probe was hard-deleted and no score is claimed. Both Qwen profiles were then raised to 16 concurrent sequences (`d3a32e31`), the second GPU worker resumed with `resume-gpu-demo.sh up 2`, and Qwen 3.6 unparked with a replica patch; a 16-sample request now takes about 14 s (3.8) and 16 s (3.6). Record a completed job on its registry model version with `record-evaluation.sh`. SWE-bench pieces are staged under `gitops/stages/050-model-evaluation/evaluation-content/swebench/` and driven by `swebench-run.sh`; enabling them needs the EvalHub CR providers entry, the anyuid SCC binding and Docker Hub pull capacity (Stage 050 README). Provider qualification on Qwen 3.8 (2026-10-12): LightEval Coding v1 passes with the helper defaults; lm-evaluation-harness log-likelihood tasks pass with a `tokenizer` parameter naming the model's Hugging Face repository, while its generative tasks fail at the sidecar's 30 s limit; GuideLLM passes when bounded by `max_seconds` or `max_requests`. SWE-bench is enabled (CR provider entry, `anyuid` binding) and generates patches, but its EvalHub grading step cannot run on 3.5.1 because adapters get no Kubernetes credentials. Delete probe jobs with `DELETE /api/v1/evaluations/jobs/<id>?hard_delete=true` and their MLflow runs. Programmatic access (2026-10-12): ServiceAccount `evaluated-models/evalhub-automation` is the documented ServiceAccount principal for the CLI/SDK (verified `evalhub health` and `providers list` with eval-hub-sdk 1.0.5) and MCP clients; the MCP server is enabled in the EvalHub CR (Route `evalhub-mcp`), calls EvalHub as `evalhub/evalhub-mcp-client` and is pinned to tenant `evaluated-models` (verified `discover_providers` and `evalhub://jobs`). Tokens from `oc create token` expire; re-issue on 401. OCI export (2026-10-12, operator decision: internal registry): Stage 050 `oci-export/` exposes the registry default route (`configs.imageregistry` `defaultRoute: true`; the evaluation sidecar trusts only public roots, and the route serves the ingress certificate), creates pusher ServiceAccount `evaluated-models/evalhub-oci-pusher` with `system:image-builder`, and a Sync hook composes the `kubernetes.io/dockerconfigjson` Secret `evalhub-oci-registry` from its token; the pusher token is long-lived, so rotate by deleting `evalhub-oci-pusher-token` and re-syncing Stage 050. Verified with a one-problem job: results artifact `evalhub-<hash>` and `evaluation-card-<job id>` in ImageStream `evaluated-models/evaluation-results`. Jobs are routed through the tenant LocalQueue `lq-cpu-default` (ClusterQueue `cq-cpu-default`) per section 2.8 of the 3.5 guide (Technology Preview): EvalHub labels the Job and pod with `kueue.x-k8s.io/queue-name`, and Kueue's `Pod` integration creates and admits the Workload (verified 2026-10-12); `submit-evaluation.sh --queue ''` submits without a queue.

### Stage 050 model qualification pipeline (2026-10-12)

The agentic coding qualification runs as an AI pipeline in project `evaluated-models`, an EvalHub tenant (Stage 050 `model-qualification/`). Argo CD deploys it in sync-wave order:
- waves 12 to 13: storage, the ODF buckets `evaluation-models-models`, `-workbench` and `-pipelines`, their dashboard connections, and the `evaluated-models-storage` PVC. Hook `evaluated-models-s3-connections` fills the connections; the Pipelines connection gets the ODF S3 Route so artifact links open in a browser;
- wave 14: hook `configure-pipeline-server` creates `dashboard-dspa-secret` and DSPA `dspa` exactly as the dashboard's **Configure pipeline server** does (default database, Kubernetes pipeline store, caching on), then waits for Ready. If DSPA `dspa` exists with a different storage host or bucket, the hook fails and asks for the DSPA to be deleted. The hook then copies the generated server config to `ds-pipeline-server-config-custom` with the MLflow plugin's `insecureSkipVerify: true` and points `apiServer.customServerConfigMap` at it, so per-step MLflow runs work (operator decision 2026-10-12, TROUBLESHOOTING). To return to the default, delete that ConfigMap and the DSPA field;
- wave 15: RoleBinding `pipeline-runner-evalhub-access` lets the pipeline runner submit EvalHub jobs;
- waves 16 to 17: the compiled Pipeline and PipelineVersion objects.

Candidate models are InferenceServices in the project; their evaluation jobs authenticate with Secret `qualification-model-auth` (hook `provision-candidate-model-auth`). Production models go through MaaS with `evalhub-model-auth-maas`.

- **Start a run:** in the dashboard's **Create run** form, select the latest pipeline version (`agentic-coding-model-qualification v11`) and MLflow experiment `agentic-coding-qualification`, and set `model_name` plus any `skip_*` switches. A script must send the same body to `POST /apis/v2beta1/runs`, including `plugins_input.mlflow.experiment_name`. Without it, every step fails its MLflow update (TROUBLESHOOTING).
- **Change the pipeline:** edit `stages/050-model-evaluation/qualification/pipeline.py`, compile a new version with kfp 2.16.1 (`python compile.py v<N>`), commit, and re-pin Stage 050. Argo CD does not prune the previous PipelineVersion; delete it with `oc delete pipelineversion agentic-coding-model-qualification-v<N-1> -n evaluated-models` so the run form offers one version. New criteria go into a new `-v2` collection, never an edited one.
- **Reset the pipeline server:** this discards all run history. Stop any running run, `oc delete workflows.argoproj.io --all -n evaluated-models`, `oc delete dspa dspa -n evaluated-models`, then sync Stage 050; the hook recreates the server with an empty database. Run metadata (Executions, Artifacts) has no delete API, so a reset is the only way to remove it.
- **Clean up evaluations:** hard-delete EvalHub jobs per tenant (`DELETE /api/v1/evaluations/jobs/<id>?hard_delete=true` with `X-Tenant`); the leaderboard reads only the remaining jobs. Delete MLflow runs per workspace. Delete a whole experiment only if nothing writes to it again: MLflow keeps a deleted experiment's name reserved, so `evaluated-models/AIP-default` keeps its experiment and loses only its runs. Manual evaluations (`submit-evaluation.sh`, `swebench-run.sh`, the CI template) log to `model-evaluations`, pipeline evaluation jobs to `agentic-coding-evaluations`, pipeline runs to `agentic-coding-qualification`.
- **Moving the tenant (2026-10-12):** Stage 050's enable hook removes the EvalHub tenant label from `demo-sandbox`; Argo CD prunes the retired sandbox Roles, RoleBindings and ServiceAccounts, and the operator removes its tenant objects. The Secrets created by the old hooks (`evalhub-model-auth-maas`, `evalhub-oci-registry`, `evalhub-s3-test-data`) and the MLflow experiment `agentic-coding-qualification` were deleted once by hand; Stage 040 no longer carries `evaluation-sandbox`, and its MaaS key was revoked.
- **Collections and step times (pipeline v11, tuned serving, 2026-10-13):** latency-v1 (3 min), throughput-v2 (64 requests, 4 min), livecodebench-v2 (alone; about 20 min with MTP, 42 min without), python-tasks-v1 (MBPP + HumanEval on the bounded `inspect-coding` provider, 7 min), security-quick-v2 (`garak-coding`, about 13 min); security-full-v2 is skipped (`skip_security_full`) until the models are fully tuned. End to end without the full scan: Qwen 3.6 43 min, Qwen 3.8 32 min, about 100 and 75 min before tuning. Qwen 3.6 was retired on 2026-10-13.
- **Serving tuning (2026-10-13):** the production `qwen3-8-27b` uses the model card's MTP speculative decoding, `--max-num-batched-tokens=16384` and `--async-scheduling` (Stage 040 README). With one GPU worker running, restart it after a serving change through `replicas` 0 then 1 (TROUBLESHOOTING). The tuning log with every probe is in the overnight report (`tmp/overnight-eval-2026-10-12.md`, local).
- **Shutdown state:** the candidate `qwen3-8-27b-int4` has `serving.kserve.io/stop: "true"` in Git (sync wave 40 so a stopped candidate does not block later waves), and every GPU MachineSet is at 0. The production model runs on the RTX PRO 6000 pool (`scripts/platform/resume-gpu-demo.sh up`); the candidate uses the L40S queue `lq-gpu-reserved-demo`, so a candidate run also needs `GPU_POOL=l40s scripts/platform/resume-gpu-demo.sh up` and stop `"false"` for the candidate.
- **Results (2026-10-12, Qwen 3.6, since retired):** every production baseline attempt (`qwen3-6-27b`) missed both serving gates through MaaS: TTFT 2,068 to 2,131 ms against 2,000 ms, and 52.5 to 55.2 output tokens/s against 60. Read these with the MaaS path in mind; the criteria are unchanged.

### Stage 060 — Agent Runtime and AgentOps workspace foundation

The shared OpenShell control plane is in `openshell`; `ai-agents` (AI Agents) is its separate administrator-managed agent-hosting workspace/project. Native operator mode maps the workspace name to the same allowlisted Namespace. GitOps provisions the namespace-scoped gateway Role/RoleBinding, sandbox ServiceAccount with token automount disabled, SSH NetworkPolicy, and the existing `rhods-admins` project-admin binding. Existing owner workspaces and core resources remain in place.

`deploy-runtime.sh` invokes the guarded, idempotent `setup-ai-agents.py` after the selected runtime revision is Synced/Healthy. Set `RHOAI_STAGE060_OPENSHELL_CLI` to the pinned CLI identified by `gitops/stages/060-agent-runtime-and-agentops/openshell-runtime/chart/source-pins.json`. The helper uses the existing native bootstrap administrator, verifies the managed `ai-admin` broker identity and immutable OpenShift UID, creates the native workspace if absent, and adds only that subject as workspace admin if absent. It never rewrites existing memberships, changes identity credentials, or launches sandboxes. Run the same helper with `--revision <deployed-SHA> --check` for read-only configuration validation. Private CLI credentials and the owned local forward are removed on exit. Native workspace membership is separate from OpenShift project RBAC; adding developer membership to this shared workspace would also grant workspace-wide agent lifecycle access and is not configured.

All five Stage 060 Applications are deployed. Owner-client access and selected-call MLflow tracing passed on 2026-10-09 (Stage 060 README). Full-stage acceptance remains pending (`validate.sh` reports it by design); the remaining gates are in the [implementation plan](migration/060-agent-runtime-and-agentops-plan.md).

## Fresh operator deployment

Use the standard cluster-credential contract in `env.example`. Repository-owned platform operators reconcile with native Automatic approval on their selected release channels; normal deployment does not require a human InstallPlan approval. OLM selects the compatible channel head; historical CSVs are qualified baselines, not immutable locks. Deployment rejects missing/incompatible catalog releases and foreign Manual subscriptions that block shared-namespace resolution. Cloud workload-identity clusters require their separate documented lifecycle. See [the version/channel matrix and applicability limits](migration/035-operator-automatic-policy.md). Existing immutable Application revisions are not changed by this source-only update; a fresh end-to-end installation has not been tested.

### Optional MCP Gateway retirement

The unused MCP Gateway component is removed from current cluster ownership and future installation (2026-10-08). The cleanup removed its App, MCP-only Subscription/CSV/controller, three empty Gateway CRDs and unused probe namespace; original global operators and their OperatorGroup remain. The future operator policy covers 22 tracked Subscriptions. RHCL/MaaS and the model Gateway, native MCP lifecycle, hosting project, Registry, direct HTTPS Studio endpoint and legacy server are preserved. Gateway failure evidence remains in the [technical tracker](migration/035-feature-completion.md); direct Studio is not MCP Gateway or MaaS-key governance. MCP Catalog is Developer Preview and its lifecycle operator is Technology Preview. The alpha MCPServer schema and installed MLflow Registry REST integration are version-coupled. Track lifecycle informer memory issue RHOAIENG-82694 before large-cluster use; no workaround is applied.

### Anthropic provider credential

Supply `ANTHROPIC_API_KEY` privately in the local environment. Stage040 uses its existing credential helper to create only `external-models/anthropic-provider-api-key` through standard input, reusing an existing correctly owned native credential without rotation. Never put a provider key into a MaaS request: callers use their own MaaS key. Claude is added to the three personal subscriptions; DevSpaces remains local-only. Native Messages streaming is not subscription-token-metered, and provider quotas aggregate callers. Initial live deployment uses an isolated reviewed revision preserving current operator policies; future defaults remain Automatic.


## Current local model routing and Studio storage, 2026-10-08

Local hosting is internal-models (Internal Models); external-models is External Models. Both projects are dashboard-visible. Governance remains models-as-a-service. Qwen 3.8 is active; Qwen 3.6, then parked, was removed with its listener on 2026-10-13. Current clients use common `/v1` and canonical `publishers/internal-models/models/<name>` IDs. The native MaaS catalog endpoints also select the API hostname. Three bounded common-host model requests passed; the identical namespace-qualified legacy local path returned HTTP 503 on the API host but passed on its dedicated Qwen 3.8 host. The `qwen3-8` compatibility listener remains, and old models-as-a-service local paths are not aliases.

Studio uses the retained genai-playground-state PVC at `/opt/app-root/src/.llama/distributions/rh` via supported OGX customer fields. Existing-state moves require quiesce, consistent private SQLite backup, integrity/record checks and restore before restart; never overwrite a live SQLite DB. The current saved response and two profile UUIDs/settings were preserved. Old unreferenced cached model registrations remain because the installed native API has no unregister. The fresh install helper attaches the same mount using exact returned CR and PVC ownership; fresh end-to-end deployment remains untested.

### Persistent OpenCode in AI Agents (Stage060)

Use the pinned native CLI and a Python interpreter with the existing PyYAML dependency. Set `RHOAI_ENV_ROOT` to the authoritative environment root, private `RHOAI_STAGE060_ADMIN_KUBECONFIG` to ai-admin's OpenShift session, and `RHOAI_STAGE060_ADMIN_CLI_HOME` to its verified native login. Provision only after the reviewed immutable runtime revision is Synced/Healthy and the exact image/subscription operands are ready:

```bash
python3 stages/060-agent-runtime-and-agentops/setup-opencode.py --revision "$RHOAI_STAGE060_EXPECTED_REVISION" --apply --expected-policy-hash "$RHOAI_STAGE060_EXPECTED_POLICY_HASH"
python3 stages/060-agent-runtime-and-agentops/setup-opencode.py --revision "$RHOAI_STAGE060_EXPECTED_REVISION"
```

The default owner-only recovery directory is `/private/tmp/060-opencode-state`. Keep its journal and independent listener-password file privately; never commit or print them. The real MaaS key is retained only by the native encrypted provider. Configuration check does not qualify inference or tool execution. A temporary inference helper refuses any active retained fleet before restoring a global policy.

For an ambiguous key POST, do not clear `key_pending` or mint again. Review only the named owner's native API-key metadata, reconcile its exact ID/subscription/creation time, and revoke an unused owned key through native MaaS before explicit journal recovery. If a provider or sandbox creation outcome is unknown, match the creation receipt and journal IDs; preserve any unidentified object. A recorded waiting sandbox can resume authenticated file upload; do not recreate it by name.

Before the recorded 30-day expiry, rotate explicitly as ai-admin: mint a replacement bound to `opencode-private-qwen38`; update the same provider through native `provider update --credential MAAS_API_KEY --credential-expires-at MAAS_API_KEY=<native-expiry> --wait` with the key supplied only in private process environment. Native stop/start is required because the old process retains its credential placeholder revision. Verify authenticated readiness and the exact new key/provider metadata before revoking the old journal key ID, then record the new native hashes/expiry. Failed rotation remains blocked; never use another subscription or external model.

Rollback first stops the exact owned sandbox and preserves its PVC. Restore the original global policy only after fresh all-workspace fleet review and an exact applied-policy hash check; never overwrite a concurrent policy. Revoke only the exact owned key on agent retirement. Archive state before native sandbox deletion, which destroys the owned PVC. No rollback alters Stage040, existing workspace memberships or the core gateway.

The qualified owner is `ai-admin`; native user membership grants control of every agent in a workspace and must not be added solely for API consumption. OpenCode listens on loopback `4096`; use the verified TLS/OIDC native relay and the separate private listener password, never a public unauthenticated listener or catalog credential. Existing native connection syntax is `openshell --workspace ai-agents forward service opencode --target-port 4096 --target-host 127.0.0.1 --local 127.0.0.1:4096`, executed in the reviewed authenticated gateway context. Keep the listener password out of command arguments and logs. The same runtime UID can read its own listener-password file; the MaaS key remains protected by the native provider. Broader client access remains a separate reviewed design.

For user-owned visual acceptance, open **AI hub → Agents → Deployments**, select **AI Agents (`ai-agents`)**, and check the expected logical sandbox `opencode`. Catalog cards and saved Playground profiles are separate surfaces. No browser check was automated. The bounded live OpenCode receipt is `/private/tmp/060-opencode-final.json`; all 16 gates passed, including real coding-tool execution, streaming, application cancellation and retained-state restart. The initial setgid recovery and exact continuation evidence boundary are recorded in the [implementation plan](migration/060-agent-runtime-and-agentops-plan.md). Before the recorded expiry (`2026-11-08T09:04:47Z`), renew through the explicit scoped rotation procedure above. The owner confirmed both OpenCode and Hermes Ready/Sandboxed visually. Hermes qualification is described below; reviewed client consumption and required selected-call tracing remain pending.


### Persistent Hermes in AI Agents (Stage060)

Hermes is deployed as native `ai-agents/hermes` with separate retained storage, loopback port 8642 and a private Bearer listener key. Use the same guarded environment, pinned CLI, verified ai-admin login and immutable runtime revision as OpenCode:

```bash
python3 stages/060-agent-runtime-and-agentops/setup-hermes.py --revision "$RHOAI_STAGE060_EXPECTED_REVISION"
# Initial provisioning only after reviewed GitOps/image/subscription/policy acceptance:
python3 stages/060-agent-runtime-and-agentops/setup-hermes.py --revision "$RHOAI_STAGE060_EXPECTED_REVISION" --apply
```

Keep `/private/tmp/060-hermes-state` owner-only, including its journal and listener-key file. The real MaaS key stays in the native encrypted provider; the agent receives its opaque placeholder. The separate local API key is readable by the same runtime UID. For native owner access, forward `hermes` with target host `127.0.0.1` and port 8642 through the authenticated TLS/OIDC gateway; supply the separate Bearer key privately to the client, never in command arguments, source, catalog or logs. No developer workspace membership is granted solely for API consumption.

Rotate before `2026-11-08T12:19:47Z` using the OpenCode procedure with the exact Hermes journal key/provider IDs and `hermes-private-qwen38` subscription. Verify the replacement native metadata and protected readiness after native stop/start before revoking the old key. Unknown outcomes fail closed; do not remint or adopt objects by name. Archive state before deletion; native stop/start retains its PVC, while deletion removes owned storage. Stored session history survives restart; active runs/events are not resumed.

Both setup helpers use one complete gateway-global policy. The exact private ELF `/opt/hermes-venv/bin/python3.11` admits only the common MaaS host on port 443, enforced POST `/v1/chat/completions`; scripts/future Sandboxes using that same private path share this authority. The common system Python is not admitted. Preserve OpenCode's rule and never use a temporary no-network qualifier to reset the retained fleet. Global-policy changes require exact source/fleet/identity/hash review.

The native Hermes protocol receipt `/private/tmp/060-hermes-final.json` has 13 passing gates; this is a bounded standalone qualification, not migration or full Stage060 completion. The owner confirmed both `opencode` and `hermes` Sandboxed/Ready under **AI hub → Agents → Deployments → AI Agents**. Client consumption and required selected-call tracing remain separate unfinished milestones.


The separate no-model confinement supplement passed all 10 gates and preserves the existing agent/session. Repeat it only when validating a changed runtime boundary:

```bash
python3 stages/060-agent-runtime-and-agentops/qualify-hermes.py --confinement-only --revision "$RHOAI_STAGE060_EXPECTED_REVISION"
```

Set `RHOAI_STAGE060_OPENSHELL_CLI` to the reviewed pinned CLI path. The consolidated receipt separates the 13 protocol gates from these negative checks; timeout, missing files and generic HTTP errors are not accepted as policy-denial proof.

The owner-only client (`owner-client.py --check` / `--trace`) runs from the source worktree with the guarded bootstrap kubeconfig, the pinned CLI, the genuine `ai-admin` persona inputs and the private SDK environment pinned by `client-requirements.txt`; `--revision` must be the published isolated live tree the runtime Application is pinned to (`07a29a29…` on 2026-10-09). If `--check` fails `placeholderNotRealKey` for one agent while its exec placeholder is valid, the long-running agent process holds a superseded credential placeholder revision: natively stop and start that retained Sandbox (identity compared before and after) rather than deleting or re-minting anything. Traces land in MLflow experiment `agent-runtime-traces` in workspace `ai-agents`; receipts stay owner-only under `/private/tmp/060-client-receipts/`.

## Stage 070 GitLab release

### Shared base-platform SSO

OpenShift's existing `rhbk` provider identifies the base Keycloak `sso` realm. Stage 070 validates that issuer before configuring application authentication; it does not change `OAuth/cluster`, the base realm's browser flow, the OpenShift client, user passwords or group memberships. OpenShift AI, Dev Spaces and Argo CD continue to use OpenShift OAuth.

Developer Hub, GitLab, MTA and TAS keep their existing OIDC clients and subjects in `platform`. Its `base-sso` identity provider now connects directly to the base realm, replacing the indirect `platform → OpenShift → sso` login path. A single confidential authorization-code client, `stage070-platform-broker`, has an exact broker callback, no service account and no direct password grant. Before linking an existing application user, the identity hook checks the base subject against the existing OpenShift identity and the application's stored OpenShift user UID. A missing or conflicting link refuses; username or email equality alone never authorizes linking. The hook preserves existing profile, role and credential records. Old OpenShift links remain for rollback, with the old provider disabled.

SonarQube Community Build uses its supported SAML client `sonarqube` directly in `sso`. Keycloak signs responses and assertions using RSA-SHA256; SonarQube trusts the signing certificate from the issuer's TLS-protected metadata and checks the exact issuer/callback. Only the login, name and email attributes are mapped. Group synchronization is not enabled, so existing local groups and permissions are retained. The local recovery administrator and scanner tokens remain valid. SAML sign-out ends the SonarQube session, not every application's session; this is a documented product limitation.

The portal's bootstrap Secret uses non-secret base64 placeholders under `data`, covered by the Application's existing `/data` ignore rule and `RespectIgnoreDifferences=true`. Do not change it back to `stringData`: Kubernetes would write those placeholders over preserved live credentials before the hook runs, regenerating client/session secrets and interrupting sign-in. Validate a repeated sync by comparing hashes, never by printing credentials.

TAS keeps the same public OIDC client and PKCE S256. Its native callback is restricted to `http://localhost/auth/callback` and the explicit default-port spelling `http://localhost:80/auth/callback`; Keycloak handles dynamic loopback ports through normalization. A wildcard inside the port is invalid. Other hosts and callback paths must remain refused. Routing success alone does not prove artifact signing.

Deployment uses the normal Stage 070 Argo sync. First validate authoring with `./stages/070-advanced-app-platform/validate.sh --static`; set `PYTHON` to the test environment containing `tests/requirements.txt` dependencies when necessary. Then validate fresh browser logins, including the same GitLab user IDs/private-project membership, the same portal catalog identity, MTA role visibility, Dev Spaces private-source access and SonarQube's Platform SSO button. Record denied access as well as successful sign-in. A configuration or redirect check alone is not completed login validation. Keep models stopped throughout.

Live read-back on 2026-10-14 passed at SSO code `78a14254` plus correction `1c4afd87`. Fresh browser sign-in passed for SonarQube, Developer Hub, GitLab, MTA and Argo CD as `ai-developer`; native Dev Spaces and OpenShift AI access also passed. Argo CD received only the explicitly approved `user:info` consent and retained the developer's groups. Its application list remained empty; no role was granted. The corrected full sync kept all seven checked credential fingerprints unchanged. TAS routing accepts two native loopback ports and refuses an unrelated host/path. Stage resource validation: 72 PASS / 0 FAIL / 1 WARN. The warning separates resource readiness from login, inference, signing and restore. Evidence and the original credential-rotation incident are retained in `tmp/stage070-live-20261013/sso-alignment/LIVE-REPORT.md`; no model was called or resumed. The later non-model qualification below adds second-persona sign-in and validation-artifact signing; this original preservation snapshot is retained separately.

For rollback, revert the SSO change and sync Stage 070. The previous hook restores the OpenShift identity provider configuration; reset the application realm's browser redirector to `openshift` through the supported Keycloak Admin API because reverting a script does not undo its database effects. Disable SonarQube SAML through its settings API. Retain all linked users, application roles, local recovery credentials and scanner tokens; do not recreate accounts or change the base platform's login. Existing sessions may require a sign-out and fresh sign-in after either transition.

Sources: [RHBK identity brokering](https://docs.redhat.com/en/documentation/red_hat_build_of_keycloak/26.4/html/server_administration_guide/identity_broker), [SonarQube Keycloak SAML](https://docs.sonarsource.com/sonarqube-community-build/instance-administration/authentication/saml/how-to-set-up-keycloak), [SonarQube SAML limitations](https://docs.sonarsource.com/sonarqube-community-build/instance-administration/authentication/saml/overview), [Argo CD ignored-field sync behavior](https://argo-cd.readthedocs.io/en/stable/user-guide/sync-options/#respect-ignore-differences-configs), [Keycloak 26.4 loopback redirect validation](https://github.com/keycloak/keycloak/blob/26.4.0/services/src/main/java/org/keycloak/protocol/oidc/utils/RedirectUtils.java).

The fresh authenticated Developer Hub template → private GitLab project → initial Tekton pipeline → internal image registry → Git delivery/Argo → HTTP workflow passed on 2026-10-14 for `stage070-validation-20261014`. Its first pipeline passed all six Tasks without a retry. The portal's CI, Topology and Kubernetes views passed; the generated Dev Spaces link cloned private source, initialized tooling and reopened the same workspace UID without duplication. Earlier failed installation checks and the older Coolstore validation retry remain preserved. [Current qualification](../BACKLOG.md#stage-070-live-qualification) separates this completed workflow from the resolved MTA controller startup issue, the deferred Solution Server defect and unqualified inference.

Non-model validation continued on 2026-10-14 at platform `659a3cff` (Stage 070 manifests unchanged from the SSO correction). TechDocs rendered through authenticated GitLab source and its Operations navigation worked. The documentation index had stale stage text and links outside the published tree; this documentation correction fixes those links. The new-project component has no CD tab, so the embedded Argo integration remains unqualified. Fresh `ai-admin` login passed for GitLab, SonarQube, MTA, Dev Spaces, Developer Hub and GitOps. Sonar grants that SSO persona only `sonar-users`, Dev Spaces shows only its own stopped workspace, and GitOps preserves `rhods-admins` without granting additional application access. The portal login needed a manual click after automated popup attempts produced competing state values; that automation path is not qualified.

TAS validation used the official cosign 3.0.4 image at digest `0d38e30e…`, the installed TUF root and the retained public signing client through PKCE. Signature verification passes only for the independently read IdP identity and issuer; wrong identity/issuer and tampered content fail. A test attestation verifies with its signed subject digest and predicate URI checked explicitly. Its predicate states that it is not build provenance. The CLI's `--type` flag alone did not reject a mismatched custom URI, so future policy must enforce that claim explicitly. No insecure verification flags, root replacement or signed-promotion policy changes were used. [Official TAS signing guidance](https://docs.redhat.com/en/documentation/red_hat_trusted_artifact_signer/1/html-single/deployment_guide/index).

The 02:00 UTC GitLab archive was copied locally with explicit authorization and owner-only permissions. Its database restored into disposable PostgreSQL 17.6 with no network and ephemeral storage; all eight Git bundles restored with matching refs and passed integrity checks. The container was removed and live GitLab was untouched. This is component recovery, not a restored GitLab service: that archive predates the later validation project and declares object-store contents skipped. Matching object-store recovery, Rails encryption-secret escrow, whole-service recovery and Sonar/TAS restoration remain required. Never rehearse by restoring over the live services. [Supported GitLab restore procedure](https://docs.gitlab.com/charts/backup-restore/restore/).

The integrated release and reviewed security corrections are published on `main`. Enrollment and exact-SHA delivery have been exercised on the installed platform. Models remain stopped. The [version/acceptance plan](migration/070-upgrade-and-gitlab-plan-20261013.md#implementation-status) records the release scope and data-retention requirements; current qualification above records the remaining limits.

### Installation and acceptance

1. Check the target cluster guard, existing Keycloak, NooBaa/gp3, persistent internal registry, free worker capacity and operator catalog pins. No model needs to be started for this step.
2. Publish the reviewed platform revision through the ordinary repository workflow. The root Stage 070 Application still bootstraps from the public platform repository; changing all root Applications to GitLab is a separate cutover.
3. Run `stages/070-advanced-app-platform/deploy.sh --revision <reviewed-published-commit>`. The selector refuses unpublished, modified or untracked stage source. Its first mutation applies the existing Stage Application without changing its destination/tracking identity; it then starts or joins the exact native full sync and waits for completed Succeeded, Synced and Healthy at that commit. Moving `main`, an older success or a selected-revision hook failure cannot satisfy that wait. Argo owns secret generation, OBC wiring, GitLab migrations, identity integrations and project tooling. It does not require a GitHub PAT/App or distribute Quay credentials.
4. Run `stages/070-advanced-app-platform/validate.sh`. A ready resource is not proof of a user workflow. Independently test the two demo users' GitLab/RHDH/Dev Spaces sign-in, private checkout, catalog/template loading and same-workspace reopen.
5. Qualify one project end to end: publisher enrollment of the first commit, exactly one initial build, private clone, a passing scan, a deliberate quality-gate failure that prevents promotion, an internal-registry digest push/pull, a GitLab delivery commit and matching Argo/deployment read-back. Replay enrollment and webhook events; confirm no duplicate runs or foreign-project authority. Verify the build Pod's user-namespace annotations, applied SCC and UID mapping; ordinary build Tasks use `app-builder`, only image building uses `image-builder`.
6. Rehearse GitLab object-store/database/Gitaly recovery and the relevant SonarQube/TAS restore. Never claim recoverability from PVC existence alone. Signed delivery is not in the current ordinary promotion contract: separately prove a signature/attestation bound to its identity and exact image, then review a blocking signing policy.
7. Once platform readiness passes, the operator can restart the models and authorize Developer Lightspeed and native agentic workflow tests. Solution Server remains deferred until its vendor dependency fix is qualified. No model inference or migration worker is launched by the static checks.

The native Agent Sandbox controller remains Stage 060-owned. MTA 8.3 uses the existing controller; no duplicate controller is installed. On the current live cluster that controller is Ready. Its compatibility with MTA's full agentic workflow remains to be exercised.

### Source reproduction

```bash
python3 -m venv tmp/stage070-tests
./tmp/stage070-tests/bin/pip install -r stages/070-advanced-app-platform/tests/requirements.txt
PYTHON=./tmp/stage070-tests/bin/python ./stages/070-advanced-app-platform/validate.sh --static
./tmp/stage070-tests/bin/python scripts/platform/render-stage070-charts.py --check
./scripts/platform/validate-stage-flow.sh
```

GitLab and SonarQube are ordinary Kustomize resources under `base/<component>/generated/`. Their upstream archives, versions, authoring Helm version, images and licenses are locked in `scripts/platform/stage070-charts.lock.json`. To update them, edit values/lock, regenerate with `render-stage070-charts.py`, and review the full generated diff. Deployment does not run Helm, chart inflation or a GitLab chart operator.

A wave-0 hook configures the canonical Argo `rhdh` read account while preserving existing RBAC. The GitLab sequence is: version precondition (wave 4), persistent shared secrets (5), scoped OBC connection/configuration (6), database/cache (7), Gitaly (8), migrations (9), services (10), successful-version receipt (12), integrations (14), then catalog and portal. Identity federation precedes these. RHDH credentials use a Sync hook in the operand's wave. MTA's Sync hook runs at wave11 after Tackle/Gateway apply at10, so its runtime endpoint write follows the Gateway apply. These hooks run before PostSync. The project reconciler waits for pipeline/scanner readiness before seeding a build.

### Shared workspace image

The checked-in Dockerfile extends the immutable published Hermes parent and replaces only MTA tools/extensions. `stages/070-advanced-app-platform/workspace-image/artifacts.lock.json` binds the official Linux amd64 MTA archive/binary and all four VSIX packages. Downloads stay outside Git. The current candidate digest is `sha256:e4ac365b3818773ea1d8f67202200011a95089d05ee53ca2652efa353de968e0` in `quay.io/rhoai3-coding-demo/rhoai3-ws-080`.

Start the selected Podman machine, then use `scripts/platform/build-stage070-workspace-image.sh <Linux-amd64-MTA-ZIP> <reviewed-tag>`. This stages verified artifacts, builds for amd64 and checks hashes, Java 21, Node and the preserved Hermes stamp. Adding `--push` explicitly publishes the shared candidate to Quay. Read back its digest and review pin changes before deployment. The script selects the rootless connection and never prunes or repairs a store. Ordinary application builds always target the internal registry.

The candidate ran a bounded MTA 8.3.0/Java 21 custom-rule canary on OpenShift; the CLI and Java-field incidents passed. The first fixture used `VARIABLE_DECLARATION` for a field and failed; corrected `FIELD_DECLARATION` evidence is retained in `tmp/stage070-implementation/live/`. The temporary namespace was retired. This proves tool usability on a small source fixture, not full migration or AI behavior.

### GitLab ownership and lifecycle

GitLab integration bootstrap creates scoped publisher, enrollment, catalog and repository readers, Dev Spaces OAuth, subject-bound demo-user memberships and private platform/workload/delivery groups. Existing tokens are reused only while their recorded identity and expiry are valid; expired or unknown credentials refuse and require operator renewal. Generated passwords/tokens remain in Secrets, never in Git.

The platform mirror retains reviewed Git history. A missing current revision can be fast-forwarded from the declared public upstream using an ephemeral bootstrap credential; divergent history refuses. Owned goldens are published from the exact platform revision as one ordinary atomic commit, with complete-tree checks and no force push. Catalog, templates and TechDocs use that private mirror revision. Platform root cutover is not implicit.

`bootstrap-scaffold-repos.sh` reports the current GitLab golden URLs. `check-gitlab-golden.py` compares private goldens against authoring files without printing the reader token. There is no GitHub-reset or force-push fallback.

For lifecycle helpers, set `GITLAB_OPERATOR_TOKEN_FILE` to an uncommitted scoped token file. `reset-coolstore-demo.sh --yes` stops only matching workspaces, restores the registered repository baseline through a normal commit and retains PVC/local changes. `delete-scaffolded-project.sh <project> --yes` checks registration ID/URL/group before archiving the repository and retiring its project resources. Migration resource retirement uses the platform pipeline. Workspace PVCs and delivery history remain. The helper refuses Stage-owned imports such as Coolstore; those are managed through the stage's GitOps source.

Retain GitLab database/Gitaly/object-store data, encryption Secrets and the successful-version receipt during recovery. An existing database without a trustworthy prior version refuses migration. A database downgrade is a supported restore operation, not a reverted image pin. Do not delete earlier live GitHub/Quay resources solely because this source no longer consumes them; retire old writers during the separately reviewed cutover.

### Stage 070 security review follow-up

The 2026-10-14 correction package is **authored, not yet deployed**. Its focused live probes validate the Secret writer and Python 3.6 runtime, not the complete updated platform. Preserve the previous workflow qualification separately until the following read-back succeeds.

- Runtime Secret writes use a canonical named create/merge-patch helper, not client-side apply or forced field ownership. The vendor Rails generation logic is preserved, but its final write now creates or merge-patches; it no longer applies its encryption payload. The few declarative Secret placeholders use Argo’s explicit `argocd-controller` server-side manager with `data`, while `ClientSideApplyMigration=false` disables the client-apply bridge. These are resource-specific SSA settings, not blanket field takeover. It removes `kubectl.kubernetes.io/last-applied-configuration` while preserving unrelated keys and object identity. Removing a copy does not revoke a credential: the original seven credential classes have an explicit one-time rotation procedure. A wider metadata-only inventory found additional old copies, including project tokens and the GitLab Rails Secret. Remove these copies by exact object too; the Rails encryption value is deliberately preserved, not generically rotated. No unauthorized disclosure has been established.
- Only `job-configure-platform-identity` retains master bootstrap access. RHDH, MTA and signing jobs obtain client-credentials tokens from separate named Secrets in their own namespaces. Their service accounts cannot read the master Secret. Their tokens cannot administer `master` or `sso`. MTA retains the platform-realm role/user permissions needed by its existing configuration.
- GitLab integration write/exec bindings are native Sync hooks. `stage070-bootstrap-cleanup` runs on PostSync and SyncFail and can only delete the exact named bindings. They are recreated on the next full sync. A controller outage before terminal hooks is not guaranteed cleanup; inspect and run the reviewed cleanup Job before treating an interrupted deployment as idle/accepted.
- `ServerSideDiff=true` is an Application compare annotation. Only named PVCs' controller-assigned `/spec/volumeName` is ignored; storage class, access modes and requested capacity remain compared. Stage 010 alone owns the console plugin list.
- Enrollment distinguishes native pending from permanent validation/permission failure. HTTP 408/429/5xx or transport waits have one fixed hour measured from request creation, never renewed by retries. Refused requests stay open with a refusal label and the coordinator exits nonzero; correct the request, investigate its named reason, then remove the refusal label. Do not mint another project or waive its identity gate.

After approved publication, load the project environment and verify the target API, then deploy the exact source and run:

```bash
./stages/070-advanced-app-platform/validate.sh --revision <reviewed-published-commit>
python3 stages/070-advanced-app-platform/security-status.py --models-stopped --output <private-evidence-directory>/security.json
```

Rotation is operator-only, never part of a routine sync. The external Sonar maintenance command uses the existing HTTPS Route; it does not replace the pipeline Secret’s cluster-local `host` value. Run `rotate-credentials.py` once per component with the exact deployed `--revision`, configured `--repo-url`, `--execute` and a new `--report` path. Rotation components are `gitlab_oidc`, `scm_client`, `publisher`, `devspaces_oauth`, `sonar`, `argo` and `mta`. The separate `annotation_copy` action requires `--secret <namespace/name>` and only removes metadata while checking unchanged UID, data and type. Use that exact-object action for the additional inventory, including Rails; it neither replaces encryption keys nor claims provider revocation. The report contains results only, not credentials. Reusing a report path refuses. Keep old human identities, client IDs, permissions and project memberships. The script uses supported provider APIs and checks replacement credentials and predecessor invalidation; a partial result requires diagnosis before any rerun. Preserve the previous reports. Browser-only Keycloak client checks require a fresh browser login in addition to server secret read-back.

The GitLab webservice is reloaded by its rotation step. After both portal token copies are updated, restart only the discovered Developer Hub Deployment through its normal rollout and wait for readiness; its environment must consume the new publisher and Argo reader tokens. The Dev Spaces server caches the OAuth client: verify that its server pod actually changes when reloading the rotated Secret; the operator can cancel a plain Deployment restart annotation. Replace only the exact server pod through its normal owner if needed, and verify its mounted credential matches the Secret. This leaves workspace pods and PVCs intact. Renew the same user grant through native OAuth and check the actual Git helper. The running workspace’s separate Git carrier can retain an expired token after successful native reauthorization. The validated recovery is a normal dashboard Stop then Open of that exact workspace, after checking for active user/build work and taking identity/storage/source snapshots. This refreshes the carrier and preserves the CR/PVC/UID, images, complete specification and clean source; verify a temporary private clone and final running state afterward. Uninterrupted hot refresh is not qualified. Do not copy tokens into the workspace, extend expiry or replace them with a shared PAT. MTA key status checks make no inference request.

Ingress allows same-namespace pods, the documented OpenShift ingress namespace label and monitoring. Only Sonar has an additional TCP/9000 scanner rule for `app-platform-build`, the two persona workspace namespaces, Coolstore and platform-labelled project namespaces. New project setup carries its own ingress policy. Egress is not restricted. Qualify router access, a scanner request from an allowed build namespace, and a denied direct request from an unrelated namespace; policy object existence alone is insufficient.

Finally repeat a complete native sync at the same pin. Confirm no recreated credential annotations, unchanged credential fingerprints after the intentional rotations, deleted temporary bindings, exact generated Application pins/diff annotations, unchanged accepted app digest/workspace UIDs, and both models/GPU MachineSets still stopped. Check actual GitLab/private-source, portal, Sonar and webhook workflows; retain earlier negative gates as earlier evidence, not new measurements.

Rollback uses a reviewed source pin and full native sync. Never restore revoked token values or downgrade databases by image rollback. Reverting the source does not undo Keycloak state or rotations. Preserve provider recovery access, existing data and users, and issue new valid credentials through the supported provider API if required. Review ingress changes separately before reopening any denied traffic.

Sources: [Argo phases and hook cleanup](https://argo-cd.readthedocs.io/en/stable/user-guide/sync-waves/), [Argo diff strategy](https://argo-cd.readthedocs.io/en/stable/user-guide/diff-strategies/), [Keycloak service accounts](https://www.keycloak.org/docs/latest/server_admin/index.html#_service_accounts), [OpenShift network policy](https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html/network_security/network-policy), [Kubernetes Secrets](https://kubernetes.io/docs/concepts/configuration/secret/).

For a future security correction, hold automatic Stage 070 installation until its package and negative tests have been reviewed. Install the approved revision through a full native sync before restoring automation. An operator-only selective sync or approved InstallPlan is not full stage acceptance. Restoring Automatic approval does not change an already-created Manual InstallPlan: inspect its exact CSV set and approve only the selected Pipelines/TAS versions; do not approve unrelated plans or edit shared operator policies.

`runtime-projects` permits only validated namespaced runtime kinds in project namespaces and private delivery sources; it has no cluster resources. `platform-projects` permits only the pinned platform project setup. Admission checks protect the coordinator’s Application source/renderer and project-local credentials/provisioning. The coordinator has namespace create and constrained Application rights; it cannot write ServiceAccounts or RBAC. It reads only the named project scanner Secret and mirrors project-analysis credentials into the two approved persona namespaces, targeted to one workspace. The platform-pinned project bootstrap alone reads the Sonar control credential; source-controlled build and IDE containers receive only their own project-analysis token. Promotion never mounts the build workspace: fresh Git, neutral configuration and `git show <sha>:path` provide the source artifacts. Route host/subdomain claims and foreign credentials remain refused. Portal registration is administrator-only; GitLab discovery ingests workload `catalog-info.yaml` files without granting ordinary users location/template registration.

The project lifecycle writes an immutable retirement record in `app-platform-build` before archiving. Migration retirement joins a deterministic PipelineRun, preserves failed runs and leaves the namespace intact on failure. Retries after namespace deletion can recover the original identity from that record; a failed pipeline requires diagnosis and an explicitly reviewed native retry, not new blind runs.

GitLab’s scheduled backup uses NooBaa in this same cluster. It does **not** protect against loss of the cluster. Separately capture the exact GitLab Rails encryption Secret (`gitlab-rails-secret`) into encrypted off-cluster storage, together with database/Gitaly/object-store backups, release identity and restore instructions. Never commit its contents or print them in logs. Demonstrate restore on the same GitLab release before claiming recovery.

For existing Stage 070 installations, back up/export SonarQube and its PostgreSQL data and the old `rhbk` realm before any upgrade or pruning. This release is qualified only as a fresh install; it does not perform PostgreSQL 15→16 migration on an existing PVC. Preserve the old namespace with `Prune=false` until its separately authorized decommission. Server model window `262144` and client input budget `220000` represent different bounds, not necessarily a mismatch. After the operator explicitly resumes models, qualify the selected MTA model alias through MaaS with one bounded request; until then the AI configuration is resource-only evidence.

SonarQube initial password rotation persists a policy-compliant pending credential before changing the API, then authenticates it and marks it ready. Job retries reuse that same Secret after an interruption; unknown authentication/storage failures refuse instead of resetting credentials. MTA proxy and Gateway model IDs must match MaaS discovery; the selected ID is `publishers/internal-models/models/qwen3-8-27b`. Native `Gateway.spec.endpoint` takes the MaaS origin without `/v1`, because its controller adds `/v1/models`; Tackle `kai_llm_baseurl` separately takes the versioned `/v1` API base for Lightspeed. The bootstrap and validator check both against the same discovered listener. Proxy readiness without inference can be validated with models stopped.

GitLab reserves the `ai-` username prefix. The trusted integration binds `ai-developer` to GitLab `platform-developer`, and `ai-admin` to `platform-admin`, using the same verified OIDC subjects. OpenShift and portal identities stay unchanged. The coordinator verifies both account ID and account name from `GITLAB_REQUESTER_IDS` / `GITLAB_REQUESTER_NAMES`, along with active state and project membership.

References: [RHDH Git provider integration](https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/integrating_red_hat_developer_hub_with_your_git_provider/index), [Backstage GitLab discovery](https://backstage.io/docs/integrations/gitlab/discovery/), [Pipelines automatic RBAC configuration](https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/installing_and_configuring/index), [GitLab protected branch API](https://docs.gitlab.com/api/protected_branches/), [GitLab reserved AI username prefixes](https://gitlab.com/gitlab-org/gitlab/-/merge_requests/213710).

Stage 070 scanner credentials use SonarQube `PROJECT_ANALYSIS_TOKEN` with an exact project key. Enrollment creates the private Sonar project, persists its token once, and verifies both token metadata and authentication on retry. An existing server token with a lost Secret refuses reconciliation rather than rotating blindly. Workspace credentials carry an exact `mount-to-devworkspace-include` target; they are mounted on normal startup and never bounce running workspaces. The platform administrator token stays in trusted bootstrap control, without a global workspace automount. See [SonarQube token guidance](https://docs.sonarsource.com/sonarqube-community-build/user-guide/managing-tokens).

On OpenShift 4.22, only the image-builder service account receives `use` of the built-in `nested-container` SCC. Its TaskRun explicitly requires that SCC and `hostUsers: false`. Buildah runs as UID1000, with SETUID/SETGID helpers, unconfined seccomp and unmasked proc confined to the mandatory pod user namespace. The built-in constraint requires `container_engine_t` and disallows privileged containers and host namespaces. It is not granted to the runner, runtime or migration workers. The read-only subordinate-ID files map `build:1001:64535`, entirely inside the outer 65536-ID pod range; the image's default100000-based range cannot be used there. The Task refuses an absent or host-level mapping before registry authentication. Verify the admitted SCC, hostUsers, UID mapping, rootless multi-user base build and internal-registry push. See [OpenShift nested-container guidance](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/authentication_and_authorization/managing-pod-security-policies) and [Linux user namespaces](https://docs.redhat.com/en/documentation/openshift_container_platform/4.21/pdf/nodes/OpenShift_Container_Platform-4.21-Nodes-en-US.pdf).

RHDH1.10 Argo frontend/backend plugins are installed as the documented Community OCI artifacts, pinned from Backstage1.49.4-compatible tags; the previous embedded paths no longer exist. Existing Argo read-only credentials and API configuration remain the same.

The earlier custom RuntimeDefault/no-escalation constraint passed admission but failed actual Buildah user-namespace creation, including with UID0. It is replaced by the documented built-in nested-container path above; both its disposable probe and the complete Tekton build/internal push passed live qualification. Do not modify the built-in SCC or grant privileged/host access.

### MTA native Agents and controller memory sizing

Native Agents are Developer Preview; the Lightspeed proxy and optional Solution Server are separate Technology Preview capabilities. Stage 070 validates these paths independently. A disabled Solution Server is reported as deferred, never as a working server. Its missing-greenlet vendor defect stays open.

The MTA 8.3 operator hardcodes a 64Mi request / 128Mi limit for `agentic-controller`. `mta/controller-sizing/` installs Red Hat's OpenShift 4.22 Vertical Pod Autoscaler from `redhat-operators` and one namespaced policy targeting only `Deployment/agentic-controller`, container `manager`. The policy controls memory requests and limits, with requests bounded to 256–512Mi; the existing 2:1 ratio gives limits of 512Mi–1Gi. CPU, vendor images and the generated Deployment are unchanged. Other containers are opted out; no model has a VPA policy. The single-replica exception is local to this policy; the cluster default remains two.

`Recreate` re-admits the controller with the selected resources, recovering a crashing pod without an operator/Argo write conflict. Brief controller downtime is acceptable; its leader election handles restarts. In live qualification the old pod kept OOM-killing after in-place resource increases, while fresh admission started successfully with a measured peak near147Mi. The policy therefore recreates rather than resizing in place; no kernel-level cause is claimed. Wait for the official VPA CSV, admission service and recommendation, then verify the actual pod's resources, controller readiness and restart stability. Recommendation availability alone is not startup success. Do not claim workload sizing from this idle startup check; inference and migration need separate authorization.

References: [OpenShift 4.22 VPA](https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html/nodes/working-with-pods#nodes-pods-vertical-autoscaler), [selected policy schema](https://github.com/openshift/vertical-pod-autoscaler-operator/blob/53c0b654069d3b463860dc6dd2c2d37ee434b21d/config/vpa/vpa-crd.yaml).

Remove this sizing policy only when a qualified vendor default or supported MTA setting replaces it. Rollback removes the targeted VPA first; it does not change a running pod back to the old size. A later pod recreation without the policy again inherits the known-bad 128Mi limit. Retain the database PVC and existing MaaS/SSO configuration. Do not re-enable Solution Server merely to reproduce its known crash.
