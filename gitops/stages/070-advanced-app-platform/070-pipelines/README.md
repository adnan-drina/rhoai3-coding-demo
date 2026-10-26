# Pipelines, signing and project enrollment (`070-pipelines`)

This Application installs Red Hat OpenShift Pipelines 1.24 and Red Hat Trusted Artifact Signer (TAS) 1.5, tunes the cluster `TektonConfig`, and fills the `app-platform-build` coordinator namespace. That namespace runs the GitLab project enrollment reconciler. The reconciler gives each approved GitLab project its own `<project>-dev` namespace, a per-project Tekton pipeline (clone, Maven build, SonarQube gate, internal-registry image, digest promotion) and an Argo CD runtime Application. Developer Hub templates, the Coolstore reference project and Stage 130 migration runs consume it.

| | |
|---|---|
| Argo CD Application | `070-pipelines` ([manifest](../../../applications/070-pipelines.yaml)) |
| Deployed by | `stages/070-advanced-app-platform/deploy.sh` → `stage-apps.sh deploy 070` (deploy-order 4) |
| Validated by | `stages/070-advanced-app-platform/validate.sh` (operator, TektonConfig, enrollment, Coolstore delivery, TAS checks), `stages/070-advanced-app-platform/validate.sh`, `validate.sh --static` tests |
| Sync | Automated, `prune: true`, `selfHeal: true`; `CreateNamespace`, `SkipDryRunOnMissingResource`, `RespectIgnoreDifferences`, `ClientSideApplyMigration=false`; compare-option `ServerSideDiff=true`; `ignoreDifferences` on Subscription `startingCSV`, and Securesign `platform` `/spec/fulcio/config/oidcIssuers` |
| Depends on | `070-namespaces` (`app-platform-build`, `trusted-artifact-signer`); existing Keycloak `keycloak/keycloak` and its Route; `070-identity` (Secret `stage070-signing-provisioner` and the `platform` realm); internal image registry; `gp3-csi` storage class |
| Used by | `070-gitlab` (integration hub writes `gitlab-enroller`, `gitlab-platform-config`, `gitlab-import-seeds` and `stage070-project-release` for this coordinator); `070-sonarqube` (writes the control credential `sonarqube-credentials`); `070-devspaces` (migration-run provisioner identity and workspace Secret writer bindings); `070-rhdh` (templates file enrollment issues) |

## Why

The workshop needs one route from a developer's private GitLab project to a running, quality-gated application without granting the project RBAC or cluster authority. OpenShift Pipelines provides the Tekton build engine and Triggers. Operator Lifecycle Manager installs it from the versioned `pipelines-1.24` channel into `openshift-operators`, as documented [1]. TAS provides the signing services (Fulcio, Rekor, Trillian, TUF, TSA) through one `Securesign` resource [4].

Enrollment is a coordinator, not a webhook. A webhook can only request a build of its own project's `main` branch. A trusted publisher files the enrollment request as a GitLab issue. The reconciler validates it against GitLab and the immutable first commit, then creates a pinned Argo CD Application from this repository. Project resources therefore come from reviewed platform code, and admission policies hold that boundary even if the coordinator is misused.

One Application holds these parts because they change together: the per-project templates in `project-pipeline/` and `project-enrollment/` are rendered by the coordinator from the same pinned revision.

## What

### Root and `operators/`: operators and cluster tuning

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| Subscription | `openshift-pipelines-operator-rh` | `openshift-operators` | Channel `pipelines-1.24`, Automatic, `startingCSV` v1.24.2, the channel head, so a fresh install does not upgrade mid-install (wave 2) |
| Subscription | `rhtas-operator` | `openshift-operators` | Channel `stable-v1.5`, Automatic, `startingCSV` v1.5.0 (wave 2) |
| ClusterRole | `pipeline-userns-builder` | cluster | `use` on the default `nested-container` SCC (wave 3) |
| SA, ClusterRole, ClusterRoleBinding, Job (Sync hook) | `configure-tekton-pruner` | `app-platform-build` | Patches `TektonConfig` pruner: PipelineRuns, keep 10, hourly (Job wave 12) |
| NetworkPolicy | `platform-ingress` | `app-platform-build`, `trusted-artifact-signer` | Ingress from same namespace, the router and monitoring (and, for `trusted-artifact-signer`, the RHTAS operator in `openshift-operators`); egress unchanged |

### `build/`: coordinator settings

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| RoleBinding | `rhoai-developers-view`, `ai-admin-admin` | `app-platform-build` | Persona `view` and `admin` (wave 5) |
| SA, ClusterRole, ClusterRoleBinding, Job (Sync hooks) | `job-configure-tektonconfig` | `app-platform-build` | Sets `spec.pipeline.coschedule: pipelineruns` and `createRbacResource=false` on `TektonConfig` (wave 11) |
| Task, Pipeline | `provision-migration-run` | `app-platform-build` | Creates or retires one Stage 130 migration run's database, Secrets and worker identity (wave 12) |

### `signing/`: Trusted Artifact Signer

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| SA, Role, RoleBinding | `configure-signing` | `trusted-artifact-signer`, `keycloak` | Patch only Securesign `platform`, read only `stage070-signing-provisioner` and Route `keycloak` (wave 3) |
| ConfigMap | `signing-bootstrap-<hash>` | `trusted-artifact-signer` | `configure-signing.py` (wave 3) |
| Securesign | `platform` | `trusted-artifact-signer` | Fulcio, Rekor (attestations), Trillian, TUF, TSA; RWO `gp3-csi` claims with `retain: true`; `Prune=false` (wave 10) |
| Job (Sync hook) | `configure-signing` | `trusted-artifact-signer` | Creates or updates the public PKCE client `trusted-artifact-signer` in the `platform` realm and sets the Fulcio OIDC issuer from the Keycloak Route (wave 10) |

### `070-gitlab/`: enrollment coordinator and boundaries

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| CronJob | `project-provisioner` | `app-platform-build` | Every 2 minutes runs `reconcile.py`: imported seeds, then open `platform-enrollment` issues; a refused request whose project is archived (retired) is closed rather than failing the run (wave 13) |
| SA, Roles, bindings | `project-provisioner`, `project-provisioner-applications`, `project-enrollment-inputs` | `app-platform-build`, `openshift-gitops` | Create namespaces; read named inputs; create PipelineRuns; create/patch Applications |
| ConfigMap | `gitlab-project-reconciler-<hash>` | `app-platform-build` | `reconcile.py` and `secret_writer.py` |
| AppProject | `platform-projects` | `openshift-gitops` | Pinned project setup into `*-dev` (wave 12) |
| AppProject | `runtime-projects` | `openshift-gitops` | Delivery repos into `*-dev`; Deployment, Service, Route, PVC, ConfigMap only; no cluster kinds (wave 12) |
| ValidatingAdmissionPolicy | `stage070-project-applications` | cluster | Coordinator and per-project bootstrap may create only their own pinned or delivery Applications; parameters from `stage070-project-release` (deny if absent) (wave 12). Its Binding lives in `070-gitlab`, after that component's wave-0 hook creates the denying parameter, so a fresh install never has a binding without its parameter |
| ValidatingAdmissionPolicy + Binding | `stage070-bootstrap-secrets` | cluster | Per-project bootstrap may write only its own named Secrets (wave 12) |
| ValidatingAdmissionPolicy + Binding | `stage070-project-provisioning` | cluster | Per-project bootstrap may never create PipelineRuns in `app-platform-build` (wave 12) |

The `app-platform-build` and `trusted-artifact-signer` namespaces come from `070-namespaces`.

### `project-pipeline/` and `project-enrollment/`: per-project templates (not rendered by this Application)

The coordinator creates `project-<name>` Applications that render `project-enrollment/` (which includes `project-pipeline/`) with the project name and namespace as annotations. Each project gets: ServiceAccounts `app-builder`, `image-builder`, `app-runtime` (no token); Tasks `gitlab-clone`, `maven-build`, `sonar-scan`, `build-internal-image`, `promote-gitlab-runtime`, `resolve-image-registry`; Pipeline `app-push` (wave 20); ImageStream, `maven-cache` PVC, registry CA and policy ConfigMaps; NetworkPolicy `project-ingress`; the `project-enrollment` bootstrap Job (Sync hook, wave 22) and its scoped Roles in the project namespace, `app-platform-build` and `openshift-gitops`.

### Not in Git

| Object | Owner |
|---|---|
| `TektonConfig` `config`, TAS operands and certificates | Operators |
| `gitlab-enroller`, `gitlab-platform-config`, `gitlab-import-seeds` (`app-platform-build`); `stage070-project-release` (`openshift-gitops`) | `070-gitlab` integration hub |
| `sonarqube-credentials` (`app-platform-build`) | `070-sonarqube` |
| `stage070-signing-provisioner` (`trusted-artifact-signer`) | `070-identity` |
| `<project>-dev` namespaces, `project-*` and `runtime-*` Applications, delivery repositories, webhooks | Enrollment coordinator |
| Per-project `gitlab-read-source`, `gitlab-webhook`, `gitlab-delivery-writer`, `sonarqube-credentials`; `gitlab-delivery-reader-<name>` (`openshift-gitops`); `<name>-sonar-credentials` (workspace namespaces) | Bootstrap Job and coordinator |

## How

- **Order.** `stage-apps.sh deploy 070` syncs this Application fourth, after `070-namespaces`, `070-identity` and `070-devspaces`. Inside it: Subscriptions (wave 2), signing RBAC (3), Securesign and signing hook (10), TektonConfig and Triggers settings (11), admission policies, AppProjects, provisioning Pipeline and pruner hook (12), coordinator (13).
- **Operator installation.** Pipelines and TAS share `openshift-operators`, so they keep Automatic approval on versioned channels; `startingCSV` is an installation floor (1.24.1 is installed live). Dev Spaces moved to `openshift-operators` on 2026-10-15 and uses Automatic approval like them; RHDH and MTA use Manual approval, and each of those components approves its own reviewed InstallPlan.
- **TektonConfig.** The operator owns the singleton, so Sync hooks patch single fields instead of declaring the CR. `coschedule: pipelineruns` replaces the removed `disable-affinity-assistant` flag [3] and lets the source and Maven cache PVCs bind to one run. `createRbacResource=false` disables the operator's per-namespace pipeline ServiceAccount grants and `pipelines-scc-rolebinding` [1]. Only the `image-builder` ServiceAccount receives `nested-container` through `pipeline-userns-builder`.
- **Image builds.** `build-internal-image` runs Buildah as UID 1000 in a pod user namespace (`hostUsers: false`, SCC `nested-container` [6]), refuses a non-mapped namespace, pushes only to its own project's internal registry path with a full commit tag, and returns the digest. Registry login uses the TaskRun's projected token.
- **Promotion.** `promote-gitlab-runtime` writes the image digest into the platform-owned `rhoai-delivery/<name>-deployment` repository with the project's `gitlab-delivery-writer` token. Argo CD (`runtime-projects`) deploys it. The delivery repository carries a push webhook to Argo CD's `/api/webhook` endpoint (added by the enrollment coordinator), so `runtime-<name>` refreshes on each promotion instead of waiting for the next Git poll; the endpoint has no webhook secret, which only means anyone who can reach it can request a refresh.
- **Triggers interceptor map.** Pipelines 1.24 ships `config-triggers-core-interceptors` itself (owned by its `TektonInstallerSet`), so the Git copy added for the 1.22.6 gap was removed on 2026-10-15 after a signed webhook check; see [Troubleshooting](../../../../docs/TROUBLESHOOTING.md#pipelines-1226-template-publishes-but-provisioning-never-starts).
- **Signing.** `configure-signing.py` authenticates with the `stage070-signing-provisioner` platform-realm service account, never the master administrator. It sets the issuer only; it never replaces keys or roots. Argo CD ignores `oidcIssuers` because the hook owns the cluster-specific URL.
- **Credentials.** No credential is in Git. Secrets are written through `secret_writer.py`, which never stores a payload in `last-applied-configuration`. Per-project deploy tokens are read-only; the delivery writer is a 90-day project access token.

Day-2 procedures: [Operations: Stage 070 GitLab release](../../../../docs/OPERATIONS.md#stage-070-gitlab-release). Enrollment refusals: [Troubleshooting](../../../../docs/TROUBLESHOOTING.md#stage-070-gitlab-project-enrollment-is-pending) and [internal-registry build refuses](../../../../docs/TROUBLESHOOTING.md#stage-070-internal-registry-build-refuses).

## Validation

`validate.sh` (live, read-only):

- `openshift-pipelines-operator-rh stays on selected minor` and `rhtas-operator stays on selected minor`, plus `<csv> succeeded`.
- `TektonConfig ready`, `Internal registry available`, `GitLab enrollment reconciler installed`, `Scoped integration Secret app-platform-build/gitlab-enroller exists`.
- Coolstore delivery: `Coolstore pipeline installed`, `Coolstore initial-build receipt bound`, `Coolstore uses digest from internal registry`, `Runtime is reconciled from delivery Git`, `Webhook listener ready`, `Pipeline may push its own images`, `Pipeline cannot push another project image`.
- `TAS service Ready`, `TAS uses existing platform realm`.
- `stages/070-advanced-app-platform/validate.sh`: `ingress_policy_installed:app-platform-build` and `:trusted-artifact-signer`, `no_master_secret:trusted-artifact-signer/configure-signing`, scoped-client checks for `stage070-signing-provisioner`, no credential annotations in project namespaces, `ServerSideDiff=true` on generated Applications.

`validate.sh --static` checks renders, disjoint components and script syntax; the former offline tests (`security-boundaries.test.py`, `internal-registry.test.py`, `delivery-integration.test.py`, `stage070-upgrade.test.py`, `product-schemas.test.py`) are in git history at `82092e01`.

By hand:

```bash
oc get tektonconfig config -o jsonpath='{.spec.pruner}{"\n"}{.spec.pipeline.coschedule}{"\n"}{.spec.params}{"\n"}'
oc get cronjob project-provisioner -n app-platform-build -o jsonpath='{.status.lastSuccessfulTime}{"\n"}'
oc get securesign platform -n trusted-artifact-signer -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}{"\n"}'
```

## Alignment with official guidance

| Topic | Official guidance | This repository | Status |
|---|---|---|---|
| Pipelines installation | Subscription `openshift-pipelines-operator-rh` in `openshift-operators` on `latest` or a `pipelines-<version>` channel [1] | `pipelines-1.24`, Automatic | Aligned |
| Pruner | Job-based pruner, default keep 100 daily at 08:00 [1] | Keep 10 hourly, PipelineRuns only | Deviation (justified: demo-scale cluster; TaskRuns cascade with their PipelineRun) |
| RBAC resource creation | `createRbacResource=false` disables cluster-wide RBAC creation; `pipelines-scc-rolebinding` is a potential security concern [1] | Disabled; one named SA gets one SCC | Aligned |
| Affinity assistant | `disable-affinity-assistant` removed; use `coschedule` [3] | `coschedule: pipelineruns` | Aligned |
| Non-root Buildah | User-namespace or custom SA/SCC methods [2] | User namespace with the OCP default `nested-container` SCC [6], bound to `image-builder` only | Aligned (OCP SCC instead of the guide's annotation method) |
| SCC grant | Role-based access to SCCs (`use` verb) [6] | ClusterRole with `resourceNames: [nested-container]` | Aligned |
| Triggers interceptor ConfigMap | Operator-owned operand | Owned by the operator's `TektonInstallerSet`; the Git copy was removed on 2026-10-15 | Aligned |
| TAS installation | Operator in `openshift-operators` via OLM [4] | `stable-v1.5`, Automatic | Aligned |
| TAS OIDC issuer | `fulcio.config` OIDC issuers with issuer, client ID, issuer URL, type `email`; Red Hat build of Keycloak example [4] | Platform realm issuer, client `trusted-artifact-signer`, type `email` | Aligned |
| TAS storage | TUF must use RWX for HA; one TUF replica not recommended for production [5] | Single replica, RWO `gp3-csi`, retained claims | Deviation (justified: demo scale; signing roots retained) |
| Image signing in the pipeline | Tekton Chains or cosign signing of images [2] | Not wired into `app-push` | Gap (known, see stage README) |
| Network isolation | Router ingress label `policy-group.network.openshift.io/ingress` [7] | Ingress policies in both namespaces; egress open | Aligned; not tenant isolation |
| Ordering and hooks | Waves order resources within one sync; `BeforeHookCreation`, `HookSucceeded` cleanup [8] | Waves 0–13; all hooks use both policies | Aligned |
| Project boundaries | AppProjects restrict sources, destinations and kinds [9]; admission policies with `failurePolicy: Fail` [10] | Two AppProjects and three VAPs | Aligned |

## References

1. Installing and configuring, sections 1.1, 3.13, 3.15 and 3.21.1, Red Hat OpenShift Pipelines 1.24. https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/installing_and_configuring/index
2. Securing OpenShift Pipelines, chapters 1–5 (Tekton Chains) and 10 "Building of container images using Buildah as a non-root user", Red Hat OpenShift Pipelines 1.24. https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/securing_openshift_pipelines/index
3. Release notes, Red Hat OpenShift Pipelines 1.24. https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/release_notes/index
4. Install Trusted Artifact Signer using the Operator Lifecycle Manager, Red Hat Trusted Artifact Signer 1.5. https://docs.redhat.com/en/documentation/red_hat_trusted_artifact_signer/1.5/install-installing_trusted_artifact_signer_by_using_the_operator_lifecycle_manager
5. Storage requirements for high availability, Red Hat Trusted Artifact Signer 1.5. https://docs.redhat.com/en/documentation/red_hat_trusted_artifact_signer/1.5/plan-storage_requirements_for_high_availability
6. Managing security context constraints, 17.1.1 "Default security context constraints" (`nested-container`) and 17.6 "Role-based access to security context constraints", OpenShift Container Platform 4.22. https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html/authentication_and_authorization/managing-pod-security-policies
7. Network policy, 3.1.1.1 "Policy additivity" (`allow-from-router`), OpenShift Container Platform 4.22. https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html/network_security/network-policy
8. Sync phases and waves, Argo CD (upstream). https://argo-cd.readthedocs.io/en/stable/user-guide/sync-waves/
9. Projects, Argo CD (upstream). https://argo-cd.readthedocs.io/en/stable/user-guide/projects/
10. Validating Admission Policy, Kubernetes (upstream). https://kubernetes.io/docs/reference/access-authn-authz/validating-admission-policy/
11. [Stage 070 README](../../../../stages/070-advanced-app-platform/README.md) and [Application manifest](../../../applications/070-pipelines.yaml).
