# Operations Guide

> **Foundation migration (2026-07-06):** stages 010-040 now import the
> validated rhoai3-demo foundation (former 050/060 folded into 040). Sections
> below that describe the pre-migration 010-060 implementation are historical
> until rewritten after the first migrated deployment.

This document explains how to deploy, validate, and operate the workshop environment. The README files teach the architecture and product story; this guide is the operational companion for people running the demo.

The executable source of truth remains the scripts:

- `stages/NNN-*/deploy.sh`
- `stages/NNN-*/validate.sh`
- `scripts/demo/bootstrap-scaffold-repos.sh` (golden GitHub reset for stages 070/080)

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
| ODF / NooBaa standalone MCG | Project [Stage 010 ODF aggregate](../gitops/stages/010-openshift-ai-platform-foundation/base/odf/aggregate/overlays/demo/kustomization.yaml); operators generate operands | Selected `stable-4.22` overlay and verified `gp3-csi`; native local MCG supplies object storage, not Ceph block/file |
| RHOAI / DSCI / DSC / model registry | Project [Stage 010 RHOAI aggregate](../gitops/stages/010-openshift-ai-platform-foundation/base/rhoai/aggregate/overlays/demo/kustomization.yaml); RHOAI owns generated components | Selected `stable-3.5`; Dashboard and Workbenches are foundation-owned; MLflow is deferred in fresh source and preserved on live f38; revised source delegates the modelregistry component and both catalogs to Stage 030, while the live f38 registry remains preserved; KServe remains Stage 030-owned, while TrustyAI/evaluation belongs to a later stage |
| COO / OpenTelemetry / Tempo | Project [Stage 010 observability aggregate](../gitops/stages/010-openshift-ai-platform-foundation/base/observability/aggregate/overlays/demo/kustomization.yaml) | Reviewed Manual InstallPlans select exact catalog CSVs; native operators own operands, with narrow project tenant access grants |
| Demo identity and S3 connection | Project [setup-access.sh](../stages/010-openshift-ai-platform-foundation/setup-access.sh) plus GitOps groups/RBAC/OBC | Separate mutating step after deployment; `deploy.sh` does not call it. Private authenticated persona kubeconfigs remain outside Git |
| GPUs / NFD / Kueue | Stage 020 desired state unless provisioner installation is observed | Reviewed Stage 020 source selects NFD 4.22, NVIDIA 26.7.1 and Kueue 1.4.2; live qualification remains pending; no GPU capacity is implied by CPU worker settings |
| Model serving / MaaS / developer services | Stages 030 / 040 / 050 | Inventory any existing installations without promoting catalog entries into installed/compatible evidence |

MLflow, EvalHub and TrustyAI belong together in Stage 050 source; MLflow is now Stage 050-owned after its protected seven-resource handoff; registry and both catalogs remain Stage 030-owned after their completed protected handoff; OpenShell with standalone Hermes per project remains later-stage design. AutoRAG and AutoML are excluded from the intended scope. Their API availability, ownership, release posture and runtime acceptance remain stage-specific work. No feature is considered installed merely because it appears in a catalog, screenshot or planned target.

### Object storage purposes and preservation

The user removed the pre-creation naming review checkpoint on 2026-10-05. An OBC name is not necessarily the S3 name: `generateBucketName` is a prefix, while `bucketName` requests an exact name; verify the resolved name after provisioning. Before changing existing storage, assess its data, retention, dependent connections, artifact URIs and ownership; preserve existing consumers and data.

The confirmed logical purposes are a **models bucket** for model artifacts and a **workbench bucket** for shared S3 file exchange between workbenches. No AI Pipelines bucket is planned because this demo does not use pipelines. The workbench bucket provides shared data exchange; persistent workspace PVCs remain the workspace/POSIX filesystem. Models and Workbench connections use native bucket-generated credentials; this observability change creates no storage.

The existing `rhoai-mlflow-artifacts` bucket is separate MLflow component artifact storage associated with the Stage 050 ownership handoff. The user has accepted `rhoai-mlflow-artifacts` unchanged: preserve its existing bucket, name and data; this plan does not authorize creating a third bucket or deleting storage. Review the existing generic `demo-sandbox-bucket` claim's consumers and data before deciding whether to retain, reassign or remove it.

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
2. Each stage `deploy.sh` applies one Argo CD `Application`.
3. Argo CD reconciles manifests from `gitops/stages/NNN-*/base`.
4. Sync waves and in-cluster Jobs perform cluster-specific setup.
5. Each `validate.sh` confirms that the stage reached the expected operational state.

The deploy scripts do not imperatively install every component themselves. They hand ownership to Argo CD.

## Stage 130 golden

Stage 080 authoring lives in
`stages/130-ai-autonomous-migration/scaffold-repo/quarkus-migration-scaffold/`
on `main`. The Stage 050 `app-migration` template fetches GitHub
`quarkus-migration-scaffold-v2`. Publish both workshop goldens with
`scripts/demo/bootstrap-scaffold-repos.sh` (force-push reset). A Stage 080 release
publishes only its own golden: `SCAFFOLD_REPOS=migration` (or `agentic` for
Stage 070 only; the default `all` is the demo reset). Do not
GitHub-rename historical `quarkus-migration-scaffold`. Do not dest-complete
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
- Stage 020 requires AWS capacity for two `g6e.2xlarge` L40S workers in the explicitly selected active CPU worker pool’s availability zone. Generate and review the native environment MachineSet before publishing it. The stage never scales CPU pools; the observed four CPU workers are distributed 2/1/1 across three pools. Confirm AMI architecture, region/AZ, instance quota and scoped Machine API credentials separately from API dry-run admission.
- `oc`, `git`, `bash`, `curl`, and `jq` are available locally.
- You are using the intended branch and remote for the GitOps source.
- `env.example` has been copied to `.env` and configured with required credentials.
- `OPENAI_API_KEY` is set in `.env` if external model inference (gpt-4o, gpt-4o-mini) will be exercised.
- Optional: `SLACK_BOT_TOKEN` and/or `BRIGHTDATA_API_TOKEN` in `.env` if those MCP servers are needed.

Recommended checks:

```bash
oc whoami
oc whoami --show-server
git remote -v
git status --short
```

MCP integrations have their own prerequisites. Stage 040 includes the read-only OpenShift MCP server (uses ServiceAccount RBAC, no token needed). Slack and BrightData are credential-gated integrations. Set `SLACK_BOT_TOKEN` and `BRIGHTDATA_API_TOKEN` in `.env` when those integrations are approved; missing credentials produce validation warnings, not failures.

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
./stages/070-advanced-app-platform/deploy.sh
```

Stages 060–080 are workflow-only (no deploy scripts, no Argo CD Applications of their own): stage 070 owns their infrastructure as components (identity, devspaces, pipelines, sonarqube, rhdh, mta). Validate their demo prerequisites with each stage's read-only `validate.sh`. Stage 070's deploy script provisions `app-platform-build` secrets from `.env` (`GITHUB_WEBHOOK_SECRET`, `GITHUB_TOKEN`) before applying the Application.

Each script applies one file from `gitops/argocd/app-of-apps/`. GitOps stages are the `stages/*/` directories that have `deploy.sh`; the matching Application is `gitops/argocd/app-of-apps/<directory-name>.yaml`. Workflow-only stages omit `deploy.sh` and have no Application.

| Stage | Argo CD app | Purpose |
|------|-------------|---------|
| 010 | `010-openshift-ai-platform-foundation` | OpenShift AI platform foundation |
| 020 | `020-gpu-infrastructure-private-ai` | NFD, GPU Operator, GPU MachineSets, Red Hat build of Kueue, queue quota, KEDA readiness |
| 030 | `030-private-model-serving` | Local private model serving |
| 040 | `040-governed-models-as-a-service` | MaaS control plane, gateway, governance, external models, MCP context |
| 050 | `070-advanced-app-platform` | Platform RHBK identity, Dev Spaces, webhook dispatcher + per-project pipelines + SonarQube gate, Developer Hub, Trusted Artifact Signer, MTA, coolstore dev environment |
| 060 | *(workflow-only)* | AI-assisted development on stage 070 workspaces |
| 070 | *(workflow-only)* | AI-agentic development (OpenCode + skills) |
| 080 | *(workflow-only)* | AI-autonomous migration on the stage 070 MTA stack |

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

Inspect an application:

```bash
oc get application 040-governed-models-as-a-service -n openshift-gitops -o yaml
```

List resources managed by an application:

```bash
oc get application 040-governed-models-as-a-service -n openshift-gitops -o json \
  | jq -r '.status.resources[]? | [.kind,.namespace,.name,.status,.health.status] | @tsv'
```

Force a sync from the CLI if needed:

```bash
argocd app sync 040-governed-models-as-a-service
```

If the `argocd` CLI is unavailable, use the OpenShift GitOps UI or wait for automated sync. Most applications have automated sync enabled.

## Developer Workflow Branch Validation

When validating developer-workflow changes on a sandbox cluster, patch only the existing platform applications that own the affected live resources.

For Stage 110 assisted-development changes, patch Stage 070 (it owns Dev Spaces and the developer portal) to the feature branch being validated:

```bash
oc patch application 070-advanced-app-platform -n openshift-gitops --type=merge -p '{"spec":{"source":{"targetRevision":"<feature-branch>"}}}'
oc annotate application 070-advanced-app-platform -n openshift-gitops argocd.argoproj.io/refresh=hard --overwrite
```

Rollback to the stable platform branch:

```bash
oc patch application 070-advanced-app-platform -n openshift-gitops --type=merge -p '{"spec":{"source":{"targetRevision":"main"}}}'
oc annotate application 070-advanced-app-platform -n openshift-gitops argocd.argoproj.io/refresh=hard --overwrite
```

Do not merge a feature branch to `main` only to validate developer workflow catalog or workspace changes. Do not create Stage `100-170` directories or Argo CD applications until a workflow owns executable artifacts or dedicated cluster resources.

## Stage-Specific Operational Notes

### Stage 010

Stage 010 installs OpenShift AI and platform dependencies. Operator reconciliation can take several minutes.

The new source uses GitOps `gitops-1.21`, RHOAI `stable-3.5`, ODF `stable-4.22` and reviewed Manual observability subscriptions. Deployment requires an explicit published revision matching local Stage 010 manifests and scripts; `deploy.sh --revision <reviewed-published-sha>` pins the Application to that immutable commit. Do not point Argo at older `main` content. Exact InstallPlan owner and sole-CSV checks precede approval.

Use the existing OpenID accounts `ai-admin` and `ai-developer`; authenticate each through the provider for final acceptance. Group membership can be configured before first login; missing User objects remain unverified identities. Set `RHOAI_ADMIN_USER` and `RHOAI_DEVELOPER_USER`, then run `setup-access.sh` after platform/OBC readiness. It assigns groups and the S3 connection without changing OAuth, passwords or provider Keycloak. Group membership remains external to GitOps self-heal. Supply separate private `RHOAI_ADMIN_KUBECONFIG` and `RHOAI_DEVELOPER_KUBECONFIG` files for actual persona checks; impersonated groups are not acceptance evidence.

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

The permanent `010-console-observability` Application manages only `UIPlugin/monitoring`; COO manages the generated monitoring plugin and console Perses server. Fresh foundation deployment includes it; the current retained core bridge can add it independently with `./stages/010-openshift-ai-platform-foundation/deploy-console-observability.sh --revision <published ref>`. Validate with `validate-console-observability.sh`. These commands do not repoint the core or deploy held Lightspeed/storage drafts.

The native Perses operator synchronizes the existing RHOAI dashboards/datasources into the console instance. No privileged global datasource or new metrics permission is configured. Native readiness passed. The console Perses accelerator datasource is restricted to platform administrators: installation-administrator proxy queries returned nonempty HTTP 200; genuine `ai-admin` and `ai-developer` returned HTTP 403. The RHOAI `ai-admin` Infrastructure metrics access remains enabled. No additional RBAC is granted; browser checks are user-owned. In the console, reload, open **Observe → Dashboards (Perses)** and select `redhat-ods-monitoring`; then open **Observe → Dashboards → NVIDIA DCGM Exporter Dashboard** for GPU metrics. Model-serving dashboards require later models/traffic. The existing trace dashboard backend error remains a separate issue.

### Stage 020

Stage 020 source installs native NFD, NVIDIA GPU Operator and Red Hat build of Kueue, plus CPU and reserved GPU queue/profile identities. Reviewed Manual lifecycle selections are `nfd.4.22.0-202609212027` (`stable`), `gpu-operator-certified.v26.7.1` (`v26.7`) and `kueue-operator.v1.4.2` (`stable-v1.4`). `startingCSV` selects the initial version; subsequent InstallPlans need explicit review. No fixed Red Hat-tested RHOAI/operator tuple is claimed.

Generate the environment overlay from one explicitly selected active AWS CPU worker MachineSet. Review its native provider references and two exclusive L40S workers with 200Gi encrypted gp3 disks, then publish it. The deploy preflight checks published source, existing ownership, provider cert-manager and the healthy Stage 010 Kueue delegation before applying only the Stage 020 Application. It never repoints Stage 010 or changes CPU capacity. NFD, driver, validator and DCGM operands remain operator-owned.

Stage 020 patches only `default-dsc.spec.components.kueue` to `Unmanaged` with `autoCreateQueues: false`. The native integration creates the Kueue singleton; GitOps owns ClusterQueues, LocalQueues and profiles. The CPU queue and two-unit reserved GPU queue are the supported topology; unused zero-quota shared/priority resources and the unconsumed priority class are removed. Global profiles require matching LocalQueues in every consuming project; this stage provisions them only in `demo-sandbox`.

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

Fresh deployments use the delegated foundation fields and the normal Stage 030 deploy entrypoint. The current cluster completed the separately reviewed [registry handoff](migration/030-serving-foundation-plan.md) through the f38-based omission bridge at `882f327f`; Stage 030 reconciled at `147b6208`: never repoint the core at the newer fresh Stage 010 base while its MLflow data remains retained. The explicit one-time helper uses immutable f38-based protect/omit overlays, checks both existing Bound OBCs and registry/database/credential identities, and preserves the rest of the core. No bucket is created or renamed. For a future reviewed handoff, run each phase and inspect its private evidence before continuing:

```bash
./scripts/platform/handoff-model-registry.sh protect "$GIT_REPO_BRANCH" /private/tmp/registry-handoff
./scripts/platform/handoff-model-registry.sh omit "$GIT_REPO_BRANCH" /private/tmp/registry-handoff
./stages/030-private-model-serving/deploy.sh "$GIT_REPO_BRANCH" /private/tmp/registry-handoff
./stages/030-private-model-serving/validate.sh
```

Protection adds `Prune=false,Delete=false` to the exact registry namespace, CR and two group bindings. Omission retains them until Stage 030 adopts the unchanged identities; the native registry CR retains its PostgreSQL PVC and credentials. Deliberate deletion requires a separate data/lifecycle review. The f38 bridge retains MLflow and existing operator approval policies; stop for unexpected CSV or InstallPlan advancement. The additive ODF console-plugin hook may replay, preserving the existing plugin list.

Native monitoring configuration enables user-workload monitoring and requests gp3-csi storage: 40Gi platform Prometheus and 20Gi user-workload Prometheus, with 7-day retention and size limits. The current provider configuration was absent and platform metrics used ephemeral 15-day storage; this rollout changes those defaults and may reset historical ephemeral metrics. Deployment rechecks named ConfigMap ownership before its Application write and refuses unreviewed provider configuration. The provider Alertmanager Secret remains untouched; the unused fake webhook is removed from source.

Canonical validation passed exact Application reconciliation, current native DSC/KServe and owned workloads, four Bound native monitoring PVCs, registry/database readiness and CA-verified registry/catalog APIs. Native KServe recovered from its initial apply failure without intervention; optional RHCL/LWS advanced capabilities remain Stage 040 work. Independent preservation and genuine-persona API audit passed: registry/database/credential UIDs and empty API digests are unchanged, retained MLflow identity/availability and both bucket identities are preserved, and both personas returned verified-TLS Model Catalog/Agent Catalog responses (10 entries each). This does not repeat the historical MLflow artifact test. Actual dashboard UI acceptance remains separate. See [runtime evidence](migration/030-serving-foundation-plan.md#final-independent-runtime-evidence).

### Stage 040

Stage 040 source targets native OpenShift AI 3.5 AIGateway/MaaS and GenAI Studio. It preserves the retained Stage 010 bridge and Stage 030 registry/serving foundation. The ordinary deployment's first write is its own immutable Application; run the reviewed `scripts/platform/delegate-maas-fields.sh` separately before the first existing-cluster deployment. This merges only exact component/dashboard delegation paths and does not repoint the core Application.

Persistent Manual OLM subscriptions select RHCL 1.4.3, Authorino 1.4.3, DNS 0.6.0, Limitador 1.4.2, Service Mesh 3.4.3 and LWS 1.0.1. The native OpenShift Gateway controller supplies the existing accepted GatewayClass; installing the Mesh operator is not proof of an initialized Istio instance. Native operators own generated workloads. Do not patch their CSVs, Deployments or monitoring operands.

The one Gateway uses distinct API/external, Qwen 3.6 and Qwen 3.8 HTTPS hosts. Namespace restrictions and LLMI listener references separate routing. The layout is a project qualification candidate for scheduler issue INFERENG-6962; actual EPP provenance remains a required independent proof. The gateway resources ConfigMap retains a 1Gi proxy memory reservation and 2Gi limit; change that native source rather than the generated proxy.

The durable PostgreSQL database remains in `models-as-a-service-db`. Runtime credentials are reused, never rotated by deployment. A metadata-only wave-7 credential barrier blocks database/storage wave 8 until the private setup helper supplies them. Native AIGateway creates `redhat-ai-gateway-infra`, where the runtime helper creates or reuses `maas-db-config`. Missing credentials with retained storage/configuration stop deployment. PostgreSQL plaintext transport is constrained by a namespace-scoped NetworkPolicy.

The project-owned `external-models` namespace contains the native ExternalProvider, ExternalModel and MaaSModelRef. `setup-provider-secret.sh` reuses the approved OpenAI credential or supplies approved local input through stdin. Git contains no provider key; the native Secret uses `inference.llm-d.ai/ipp-managed=true`. GPT-6 Luna uses `openai-chat`; function calls require `reasoning_effort=none`, and Responses built-in tools are outside this protocol. Red Hat-hosted MiniMax remains conditional on actual governed incremental streaming and final usage proof.

```bash
./stages/040-governed-models-as-a-service/deploy.sh
./stages/040-governed-models-as-a-service/validate.sh --readiness
RHOAI_STAGE040_PERSONA_KUBECONFIG=/private/path/persona-kubeconfig \
./stages/040-governed-models-as-a-service/validate.sh --functional
./stages/040-governed-models-as-a-service/register-model-cards.sh
```

Functional validation creates and revokes only its own expiring synthetic key, with bounded chat/stream/tool-call/authorization/traffic checks. Quota enforcement, per-request EPP proof and user Studio interaction are recorded separately; an API response does not establish all stage acceptance. No GuideLLM benchmark runs implicitly.

GenAI Studio enablement is native OGX. The user creates a project playground through the dashboard and selects an available governed endpoint. Its generated pgvector resources remain native service-owned; do not pre-author them or patch generated workloads. Basic remote inference needs no new GPU or bucket; RAG, AutoRAG and AutoML are excluded.

Required read-only OpenShift MCP remains at `openshift-mcp.rhoai-mcp.svc:8080/mcp`, with pinned upstream v0.0.67 and existing Kubernetes RBAC. Slack/BrightData are inactive optional integrations. Upstream image origin does not establish Red Hat product support. See the [Stage 040 technical plan](migration/040-governed-serving-plan.md) for dispositions, sources and live qualification boundaries.

### Stage 070 — Dev Spaces (devspaces component)

The stage 070 `devspaces` component installs Red Hat OpenShift Dev Spaces and persona namespaces (consumed by the workflow-only stages 110/120/130).

Validation now checks both service readiness and persona namespace readiness. The stage is not considered fully validated unless `wksp-kubeadmin`, `wksp-ai-admin`, and `wksp-ai-developer` exist, the `ai-admin` / `ai-developer` workspace edit RoleBindings point at the expected OpenShift users, and the Stage 110 catalog seat `agentic-coolstore` exists in `wksp-ai-developer` and `wksp-ai-admin`. Stages 120 and 130 create additional workspaces from RHDH factory templates at demo time. Those factory destfiles set `controller.devfile.io/storage-type: per-workspace` so they can run beside `agentic-coolstore` without multi-attaching the CheCluster per-user RWO claim. Standing `getting-started-ai-coding`, `coolstore-inventory-service`, and `mca-coolstore` DevWorkspaces were retired.

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

The stage 070 `identity` component deploys the standalone platform RHBK (Red Hat build of Keycloak, namespace `rhbk`): RHBK Operator (`stable-v26`), a PostgreSQL backing store, the `platform-rhbk` Keycloak CR (HTTP-enabled behind an edge-terminated Route, `proxy.headers: xforwarded`), a `KeycloakRealmImport` for the `platform` realm shell, and the `configure-platform-identity` PostSync job that patches the `platform-keycloak` OAuthClient, creates the `openshift-v4` identity provider, and pre-creates the demo users with IdP links. RHDH signs in against this realm; the MTA-operator-managed Keycloak is MTA-only.

Useful checks:

```bash
oc get keycloak platform-rhbk -n rhbk -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}'
oc get keycloakrealmimport platform-realm -n rhbk -o jsonpath='{.status.conditions[?(@.type=="Done")].status}'
oc get route platform-rhbk -n rhbk -o jsonpath='{.spec.host}'
oc get oauthclient platform-keycloak -o jsonpath='{.redirectURIs[0]}'
```

### Stage 070 — MTA (mta component)

The stage 070 `mta` component installs Migration Toolkit for Applications 8.2 (consumed by the workflow-only stage 130). Developer Lightspeed/Kai is disabled until the demo needs it (`kai_llm_proxy_enabled`/`kai_solution_server_enabled: false`; no MaaS wiring — see BACKLOG "Developer Lightspeed re-enable"). Hub auth uses the 8.2 built-in OIDC provider federated to the platform realm: the `configure-mta-platform-sso` PostSync job maintains the realm roles (`role.admin`/`role.architect`/`role.migrator`), the `mta-hub` client (realm roles delivered as `+role.<name>` entries in the access token's `scope` claim), the `mta-idp-client-secret` Secret, and the `platform-sso` IdentityProvider CR, restarting the hub on changes. It also owns the `mta-hub-workspace-config` PostSync job (`mta-hub-config` ConfigMaps in the persona namespaces). Stage 130 analysis workspaces come from the `app-migration` factory destfile; stage 130's `validate.sh` covers that contract.

Useful checks:

```bash
oc get tackle mta -n openshift-mta -o yaml
oc get deployment -n openshift-mta
```

### Stage 070 — Coolstore dev environment (coolstore component)

The `coolstore` component keeps a running `coolstore-inventory-service` in `coolstore-dev` so the demo starts from a deployed brownfield system. The Deployment pins `quay.io/…/coolstore-inventory-service:latest`; the shared pipeline's `tag-latest` task republishes that tag on every green run. `deploy.sh` seeds the first run (topic, PipelineRun, rollout) and provisions `quay-pull-secret` from `.env`. If the deployment shows ImagePullBackOff on a fresh cluster, the seed run has not completed yet — re-run `stages/070-advanced-app-platform/deploy.sh`.

Useful checks:

```bash
oc get pipelinerun -n coolstore-dev -l backstage.io/kubernetes-id=coolstore-inventory-service
oc get deployment,route -n coolstore-dev
curl -s https://$(oc get route coolstore-inventory-service -n coolstore-dev -o jsonpath='{.spec.host}')/q/health/ready
```

### Stage 070 — Developer Hub (rhdh component)

The stage 070 `rhdh` component installs Red Hat Developer Hub and configures OIDC through the platform RHBK (realm `platform`) from the `identity` component of the same stage; MTA 8.2's built-in Hub OIDC provider federates to the same realm (`platform-sso` IdentityProvider).

The RHDH catalog location is runtime-derived from the Stage 070 Argo CD Application source. This avoids loading catalog entities from `main` when the demo is deployed from a validation branch or fork. Golden-path template Locations use that same `targetRevision` (stable branch). They must not be SHA-pinned blob URLs — those accumulate and flap `template:default/app-migration` 200/404.

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

The `resume` command requests a sync of the existing Stage 020 revision, scales only its verified GPU MachineSet back to two replicas, waits for native GPU/operator readiness and runs readiness validation. It does not delete Machines, patch node labels, sync model stages or repair generated ReplicaSets. Model and functional acceptance remain separate; scale-to-zero is intentional cost control, not a passing GPU-capacity check.

To scale GPU capacity down for shutdown:

```bash
./scripts/platform/resume-gpu-demo.sh down
```

Kueue queue resources survive normal cluster restarts because they are Kubernetes API objects. Kueue does not create cloud GPU nodes by itself; GPU node lifecycle remains a platform capacity action through the MachineSet.

After any cluster suspend/resume, also restart the Stage 070 Developer Hub deployment — its long-running backend holds stale connections across the suspend and OIDC sign-in fails with 504 errors until it is bounced (see the Stage 070 Developer Hub notes and TROUBLESHOOTING).

## Coolstore Demo Reset

The stage 070 coding exercise pushes real commits to `coolstore-inventory-service` `main` (required — pipeline triggers listen only on `refs/heads/main`). To make demo runs repeatable, a `golden` branch in that repo pins the pristine baseline.

```bash
./scripts/demo/reset-coolstore-demo.sh
```

| Flag | Effect |
|------|--------|
| `--yes` | Skip the confirmation prompt |
| `--keep-sonar` | Skip the SonarQube project deletion (deletion is the default: a post-demo rewind re-introduces fixed lines as new violations and the validation run goes red without it) |
| `--skip-workspace` | Leave the DevWorkspace as-is |
| `--wait-pipeline` | Poll the reset PipelineRun until Succeeded/Failed (max 15 min) |

The script rewinds `main` to `golden` via the GitHub API, recreates the `agentic-coolstore` DevWorkspace (Argo CD self-heals it to `Stopped`), and optionally clears SonarQube history. The force-push fires one expected `app-push` PipelineRun in `coolstore-dev` that re-validates the chain and re-tags `:latest`.

**Advancing the baseline:** when the demo app legitimately evolves, push the new baseline commit to `main`, verify the pipeline is green, then update the golden branch:

```bash
gh api -X PATCH "repos/adnan-drina/coolstore-inventory-service/git/refs/heads/golden" \
  -f sha="$(gh api repos/adnan-drina/coolstore-inventory-service/git/refs/heads/main --jq .object.sha)" \
  -F force=true
```

Or: `git push origin main:golden --force`.

## Qwen 3.8 INT4 alongside Qwen 3.6

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
argocd app delete 070-advanced-app-platform --cascade
argocd app delete 040-governed-models-as-a-service --cascade
argocd app delete 030-private-model-serving --cascade
argocd app delete 020-gpu-infrastructure-private-ai --cascade
argocd app delete 010-openshift-ai-platform-foundation --cascade
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

## Model selection record (current estate and history)

The demo's default posture serves ONE local model on 1× g6e.2xlarge (1×
NVIDIA L40S, 48GB), governed through the MaaS gateway — a measured cost
decision (2026-07-25): single-stream decode parity between the dense 27B
and the 35B MoE (18.8 vs 17.7 tok/s) plus better quality at both harness
roles made a dedicated coding GPU unnecessary for presenter-driven use.
The MoE's real advantage (3.4× aggregate throughput at 4-way concurrency,
7.5s vs 25.8s per request) matters only for multi-user hands-on sessions
— for those, enable the workshop overlay below.

| Seat | Model | Why selected | Serving notes |
|---|---|---|---|
| Hermes main / Kanban workers | `qwen3-8-27b-int4` via named provider `qwen38` (`api_mode: chat_completions`) | AD-008 primary. MaaS gateway; declared context 220,000 under the served 262,144 window; output cap 8,192. Alias `qwen27b` switches to `qwen3-6-27b` and then needs `model.context_length` 110000 | Gateway path `/models-as-a-service/qwen3-8-27b-int4/v1` in `MAAS_API_BASE_URL`. `MAAS_API_BASE_URL_QWEN36` keeps `/models-as-a-service/qwen3-6-27b/v1`. Managed Scope `providers.qwen38` with `discover_models: false` |
| OpenCode coding worker | `qwen38/qwen3-8-27b-int4` | Same default; `qwen27b/qwen3-6-27b` stays in the picker | Separate MaaS base URL per model, same API key |
| MiniMax M2 (exception) | Hermes `providers.minimax` / OpenCode `redhat/minimax-m2` | AD-008 exception only — typed escalation file required; **not** the default; **not** in `fallback_providers` | Direct Red Hat LiteMaaS until RHOAI 3.5 restores external-model streaming through the gateway. 196K window |

**How to add another Hermes model:** named `providers.<name>` entry + managed `.env` secret + explicit `models:` map (`discover_models: false`). Change `model.default` only if it is the new main. Exception models follow the MiniMax gate. Full recipe: `stages/130-ai-autonomous-migration/README.md` (Applied Hermes model configuration) and AD-008 §11 in `harness-refactoring/architecture/SOLUTION-ARCHITECTURE.md`. Official schema: [Configuring Models](https://hermes-agent.nousresearch.com/docs/user-guide/configuring-models).

**Workshop capacity overlay:** `qwen3-6-35b-a3b`
(gitops `040/.../local-models/optional/qwen35b-workshop/`) — the MoE
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

**External-model routing option:** MiniMax M2 (`providers.minimax` /
`minimax-m2`, 196K) on the Red Hat MaaS portal's direct endpoint is an
**AD-008 exception**, not a factory default. Hermes registers it only when
`.rhoai3-model-escalation.json` is valid. It is direct-endpoint only because
the RHOAI 3.4 gateway buffers streaming for external models (see
TROUBLESHOOTING "External Model Streaming Resets"); expected fixed in
RHOAI 3.5, after which it can route through the gateway with platform
telemetry like the local models. Do not add it to `fallback_providers`.

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

### Planned Stage 060 — Agent Runtime and AgentOps

Stage 060 has no deployment script or Application; its validator reports pending (exit 2). Stage 070 is the renamed developer platform. Before a future Stage 070 deployment, verify that neither a legacy `060-advanced-app-platform` owner nor a conflicting `070-advanced-app-platform` Application exists; do not create dual owners or cascade-delete data to renumber. This repository change does not reconcile live resources. Runtime implementation gates are in the [Stage 060 proposal](migration/060-agent-runtime-and-agentops-plan.md); developer/SCM gates are in the [Stage 070 proposal](migration/070-developer-platform-and-scm-plan.md).

## Fresh operator deployment

Use the standard cluster-credential contract in `env.example`. Repository-owned platform operators reconcile with native Automatic approval on their selected release channels; normal deployment does not require a human InstallPlan approval. OLM selects the compatible channel head; historical CSVs are qualified baselines, not immutable locks. Deployment rejects missing/incompatible catalog releases and foreign Manual subscriptions that block shared-namespace resolution. Cloud workload-identity clusters require their separate documented lifecycle. See [the version/channel matrix and applicability limits](migration/035-operator-automatic-policy.md). Existing immutable Application revisions are not changed by this source-only update; a fresh end-to-end installation has not been tested.

### Optional MCP Gateway retirement

The unused MCP Gateway component is removed from current cluster ownership and future installation (2026-10-08). The cleanup removed its App, MCP-only Subscription/CSV/controller, three empty Gateway CRDs and unused probe namespace; original global operators and their OperatorGroup remain. The future operator policy covers 22 tracked Subscriptions. RHCL/MaaS and the model Gateway, native MCP lifecycle, hosting project, Registry, direct HTTPS Studio endpoint and legacy server are preserved. Gateway failure evidence remains in the [technical tracker](migration/035-feature-completion.md); direct Studio is not MCP Gateway or MaaS-key governance. MCP Catalog is Developer Preview and its lifecycle operator is Technology Preview. The alpha MCPServer schema and installed MLflow Registry REST integration are version-coupled. Track lifecycle informer memory issue RHOAIENG-82694 before large-cluster use; no workaround is applied.

### Anthropic provider credential

Supply `ANTHROPIC_API_KEY` privately in the local environment. Stage040 uses its existing credential helper to create only `external-models/anthropic-provider-api-key` through standard input, reusing an existing correctly owned native credential without rotation. Never put a provider key into a MaaS request: callers use their own MaaS key. Claude is added to the three personal subscriptions; DevSpaces remains local-only. Native Messages streaming is not subscription-token-metered, and provider quotas aggregate callers. Initial live deployment uses an isolated reviewed revision preserving current operator policies; future defaults remain Automatic.
