# GitLab CE and integration hub (`070-gitlab`)

This Application runs the private source-control service of the developer platform: GitLab Community Edition 19.4.2, its dedicated PostgreSQL and Valkey services, Gitaly storage and six NooBaa object buckets. It also carries the integration hub. That Sync-hook Job runs after GitLab is ready. It creates GitLab groups, service users, tokens and repository imports, and it writes the credentials and configuration that Dev Spaces, Developer Hub, the enrollment pipeline and Argo CD consume. Developers, workspaces, Tekton pipelines, Developer Hub templates and Argo CD delivery all reach GitLab through its HTTPS Route.

| | |
|---|---|
| Argo CD Application | `070-gitlab` ([manifest](../../../applications/070-gitlab.yaml)) |
| Deployed by | `stages/070-advanced-app-platform/deploy.sh` → `stage-apps.sh deploy 070` (deploy-order 7) |
| Validated by | `stages/070-advanced-app-platform/validate.sh` (GitLab release, readiness, bucket, Route, integration-Secret and security-boundary checks); `validate.sh --static` (renders, disjoint components, scripts parse; the former offline tests `tests/*.test.py` are in git history at `82092e01`) |
| Sync | Automated, `prune: true`, `selfHeal: true`; `CreateNamespace`, `SkipDryRunOnMissingResource`, `RespectIgnoreDifferences`, `ClientSideApplyMigration=false`; compare-option `ServerSideDiff=true`; `ignoreDifferences` on `/spec/volumeName` of PVCs `gitlab-postgresql-data` and `gitlab-valkey-data` |
| Depends on | `070-namespaces` (`gitlab-system`, `app-platform-build`, `rhdh` and the other target namespaces); `070-identity` (Secret `stage070-scm-provisioner` in `gitlab-system`, platform realm and persona links); `070-devspaces` (CheCluster `devspaces`, standing DevWorkspaces `agentic-coolstore`); `070-mta` (Route `mta`); existing Keycloak, NooBaa (`openshift-storage.noobaa.io`, Route `s3`), `gp3-csi` and OpenShift GitOps |
| Used by | `070-rhdh` (catalog and TechDocs from the platform mirror, `rhdh-gitlab`, `gitlab-publisher`, `gitlab-catalog-reader`, `gitlab-platform-config`, `rhdh-local-user` (operator-managed)); `070-pipelines` enrollment (`gitlab-enroller`, `gitlab-platform-config`, `gitlab-import-seeds`); Dev Spaces (GitLab OAuth); Argo CD (`gitlab-platform-reader` repository Secret, `stage070-project-release`); Stages 110–130 |

## Why

The workshop keeps application source inside the cluster boundary. GitLab CE provides private groups, project-bound webhooks, OAuth for Dev Spaces and an HTTPS Git endpoint that Argo CD and Tekton can read. GitLab is an upstream community component, not a Red Hat product.

GitLab's Helm chart needs external PostgreSQL, Redis or Valkey, and object storage [1]. The chart was rendered offline during authoring from a pinned archive and image digests; the generated manifests in `generated/` are now the source and are edited directly (the former renderer `render-stage070-charts.py` and `stage070-charts.lock.json` are in git history at `82092e01`). Argo CD then applies plain Kustomize resources: there is no Helm release, chart inflation at sync time or GitLab Operator. Every object and image digest is reviewable in Git, and Argo CD remains the single owner. The generated manifests carry sync waves so that the chart's own order still holds: secrets, then database, then migrations, then application pods.

The integration hub lives in this Application because it is the only step that can see all its inputs at once: GitLab ready, Dev Spaces and MTA Routes present, the platform realm configured. Argo CD orders hooks only inside one Application [9], so `stage-apps.sh deploy 070` deploys GitLab after Dev Spaces, Pipelines, SonarQube and MTA, and before Developer Hub, whose catalog hook reads the GitLab mirror.

## What

### Chart render (`generated/`, `values.yaml`)

`generated/` holds 30 rendered objects. Edit `values.yaml` or the renderer and regenerate; never edit `generated/` by hand. `values.yaml` and `LICENSE.gitlab-chart` (upstream MIT licence) are inputs and records only; `kustomization.yaml` does not include them.

| Kind | Name | Purpose |
|---|---|---|
| ServiceAccount, Role, RoleBinding | `gitlab-shared-secrets` | Chart secrets generator: `get/list/create/patch` on Secrets in `gitlab-system` (wave 3) |
| ConfigMap (×10) | `gitlab-gitaly`, `-gitlab-exporter`, `-migrations`, `-sidekiq`, `-toolbox`, `-webservice`, `-workhorse-default`, `-shared-secrets`, `-gitlab-upgrade-check`, `-runtime-templates` | Chart configuration (wave 3). `gitlab-runtime-templates` holds the templates with `example.invalid` and `pending-<bucket>` markers plus `release.json` (`10.4.2` / `19.4.2`) |
| Service | `gitlab-webservice-default`, `gitlab-gitaly`, `gitlab-gitlab-exporter` | In-cluster endpoints (wave 3) |
| Job (Sync hook) | `gitlab-gitlab-upgrade-check` | Wave 4. Runs `bootstrap.py check-upgrade`: refuses downgrades, foreign incomplete installs and databases without a release receipt; runs the chart's `runcheck` on upgrades |
| Job (Sync hook) | `gitlab-shared-secrets` | Wave 5. Generates the Rails, Gitaly, Workhorse and shell secrets |
| StatefulSet, PDB | `gitlab-gitaly` | Git repository storage, 20 Gi `gp3-csi`, `Prune=false` (wave 8) |
| Job (Sync hook) | `gitlab-migrations` | Wave 9. Database migrations |
| Deployment, HPA, PDB | `gitlab-webservice-default`, `gitlab-sidekiq-all-in-1-v2` | Web/API and background jobs; HPA min = max = 1 (wave 10) |
| Deployment | `gitlab-toolbox`, `gitlab-gitlab-exporter` | Rails console/backup tooling and metrics exporter (wave 10) |
| CronJob | `gitlab-toolbox-backup` | Daily backup at 02:00 UTC to the `gitlab-backups` bucket (wave 10) |

Chart pods use ServiceAccount `gitlab-app-nonroot` and UID 1000. Every image is pinned by digest. All hook Jobs use `BeforeHookCreation,HookSucceeded`.

### Platform services (`database-cache.yaml`, `buckets.yaml`, `route.yaml`, `network-policy.yaml`)

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| ObjectBucketClaim (×6) | `gitlab-lfs`, `-artifacts`, `-uploads`, `-packages`, `-backups`, `-backup-tmp` | `gitlab-system` | One NooBaa bucket each (`noobaa-default-bucket-class`), wave 5, `Prune=false` |
| PersistentVolumeClaim | `gitlab-postgresql-data`, `gitlab-valkey-data` | `gitlab-system` | 10 Gi `gp3-csi` each, wave 6, `Prune=false` |
| Deployment, Service | `gitlab-postgresql` | `gitlab-system` | PostgreSQL (upstream image by digest), `Recreate`, credentials from Secret `gitlab-database` (wave 7) |
| Deployment, Service | `gitlab-valkey` | `gitlab-system` | Valkey with append-only persistence and a password from Secret `gitlab-cache` (wave 7) |
| Route | `gitlab` | `gitlab-system` | Edge TLS, HTTP redirect, 600 s router timeout, to `http-workhorse` (wave 3) |
| NetworkPolicy | `platform-ingress` | `gitlab-system` | Ingress only from the same namespace, the OpenShift router and monitoring; egress unchanged |
| ServiceAccount, Role, RoleBinding | `gitlab-app-nonroot`, `gitlab-use-nonroot` | `gitlab-system` | `use` on SCC `nonroot-v2` only, for `gitlab-app-nonroot`, `gitlab-shared-secrets` and `gitlab-bootstrap` (wave 3). The SA has no token mount |

PostgreSQL and Valkey run under the default ServiceAccount and the `restricted-v2` SCC. The `gitlab-system` namespace comes from `070-namespaces`.

### Bootstrap and integration hooks (`bootstrap.yaml`, `integrations-bootstrap.yaml`, `bootstrap-cleanup.yaml`, `argocd-reader.yaml`)

| Hook (wave) | ServiceAccount | Writes |
|---|---|---|
| `stage070-argocd-reader-setup` (Sync, 0), namespace `openshift-gitops` | `stage070-argocd-reader-setup` | Creates the denying `stage070-project-release` ConfigMap if absent; then checks (read-only) that the `rhdh` local user and `role:rhdh-reader` rules Stage 010 declares on the ArgoCD CR are present. The `stage070-project-applications` binding (wave 12) follows this hook |
| `gitlab-bootstrap` (Sync, 6) | `gitlab-bootstrap` | Configures the GitLab OIDC client in the `platform` realm and writes `gitlab-oidc`. Generates `gitlab-database`, `gitlab-cache` and `gitlab-initial-root` once. Builds `gitlab-storage-*` from the OBC credentials. Grants the backup account access to the temporary bucket with a bucket policy. Writes the `*-runtime` ConfigMaps from the Route host and bucket names |
| `gitlab-record-release` (Sync, 12) | `gitlab-bootstrap` | Writes `gitlab-gitlab-chart-info` only after webservice, sidekiq and toolbox are available |
| `gitlab-integrations-bootstrap` (Sync, 14) | `gitlab-integrations-bootstrap` | See How |
| `stage070-bootstrap-cleanup` (PostSync + SyncFail, 99) | `stage070-bootstrap-cleanup` | Deletes the ten wave-12 hook RoleBindings |

`gitlab-bootstrap` holds standing, mostly name-scoped Secret/ConfigMap rights in `gitlab-system`, plus `get` on Route `s3` (`openshift-storage`), Route `keycloak` (`keycloak`), `ingresses.config/cluster` and one ObjectBucket. The integration hub's rights come from ClusterRole `gitlab-integrations-bootstrap` (`get/create/patch/update` on Secrets and ConfigMaps). Wave-12 hook RoleBindings bind that ClusterRole in `gitlab-system`, `rhdh`, `app-platform-build` and `openshift-devspaces`. Further wave-12 Roles grant `pods/exec` in `gitlab-system`, named objects in `openshift-gitops`, `openshift-mta`, `keycloak` and the two `wksp-ai-*` namespaces. The cleanup hook removes all those bindings, so between syncs the hub ServiceAccount holds only `get` on `ingresses.config/cluster`.

Not in Git: every generated Secret, the `*-runtime` ConfigMaps, `gitlab-initial-release`, `gitlab-gitlab-chart-info`, `gitlab-import-seeds` and the GitLab-side users, groups, tokens and projects. The bootstrap Jobs own them.

## How

1. **Ordering.** Waves 0–10 reproduce the chart's order. Upgrade check (4) precedes secrets (5), credentials and runtime ConfigMaps (6), database (7), Gitaly (8), migrations (9) and the application (10). The release receipt (12) records a version only after the pods are available. The upgrade check therefore compares against the last version that actually ran, never against the newly applied manifest. Troubleshooting: [migration precondition](../../../../docs/TROUBLESHOOTING.md#stage-070-gitlab-refuses-its-migration-precondition).
2. **Cluster values without deploy-time patches.** The render uses `gitlab.example.invalid`, `apps.example.invalid` and `pending-<bucket>` markers. `bootstrap.py prepare` replaces them from the Route host, the ingress domain and the bound OBC bucket names. It refuses to write a ConfigMap that still contains a marker.
3. **Object storage.** Each OBC yields a ConfigMap and Secret with its bucket name and keys [5]. LFS, artifacts, uploads and packages each get a separate bucket and connection Secret (`proxy_download: true`, path-style S3 against the NooBaa Route). Backups use an s3cmd config for `gitlab-backups`, as the chart expects [3]. `gitlab-backup-tmp` is opened only to the backup account. No NooBaa administrator credential is used.
4. **Sign-in.** GitLab's only SSO provider is `openid_connect` against the `platform` realm (`discovery: true`, `uid_field: sub`); `blockAutoCreatedUsers: true` [6]. Sign-up is disabled, importers are limited to `git`, and Auto DevOps is off.
5. **Integration hub (wave 14).** It mints a one-day root `api` token through `gitlab-rails runner` in the toolbox pod and revokes it in a `finally` block. With it, the hub:
   - creates the private groups `rhoai-platform`, `rhoai-workloads` and `rhoai-delivery`;
   - links the personas to their platform-realm subjects, as `platform-developer` and `platform-admin`;
   - creates the service users `rhdh-publisher`, `platform-enroller` and `platform-catalog-reader`, with 90-day tokens that carry an `rhoai3.io/expires-at` annotation;
   - imports the platform, golden and sample repositories from GitHub;
   - fast-forwards the platform mirror to the Application's exact `targetRevision` (never a force push);
   - publishes the two goldens as one ordinary commit;
   - creates the Dev Spaces GitLab OAuth application and the `gitlab-oauth-config` Secret, and patches CheCluster `gitServices` and `allowedSources`;
   - repoints the stopped `agentic-coolstore` workspaces;
   - writes `gitlab-platform-config` (in `rhdh` and `app-platform-build`), `stage070-project-release` and the Argo CD repository Secret `gitlab-platform-reader` (deploy token).

   Existing tokens are reused while valid. One that expires within seven days refuses the sync, and the operator renews it through GitLab's token API ([rotation](../../../../docs/OPERATIONS.md#stage-070-security-review-follow-up); the former helper `rotate-credentials.py` is in git history at `82092e01`).
6. **Secrets.** Every credential is generated in the cluster and written through `secret_writer.py`, which never stores the payload in `kubectl.kubernetes.io/last-applied-configuration`. Recovery requires the Rails secret to be escrowed separately; see [Operations](../../../../docs/OPERATIONS.md#stage-070-gitlab-release).
7. **`ignoreDifferences`.** Only the dynamically bound `volumeName` of the two hand-authored PVCs is ignored.

## Validation

`validate.sh` (live, read-only) checks that `gitlab-gitlab-chart-info` records `19.4.2`; that webservice, Gitaly and sidekiq are ready; that the six OBCs are `Bound` and `/-/readiness` returns 200 through the Route. It checks that the scoped integration Secrets exist (`rhdh/gitlab-publisher`, `rhdh/gitlab-catalog-reader`, `app-platform-build/gitlab-enroller`, `openshift-devspaces/gitlab-oauth-config`, `gitlab-system/gitlab-oidc`). It also checks that both standing workspaces clone from GitLab and that the enrollment CronJob exists. `stages/070-advanced-app-platform/validate.sh` adds four checks. No credential Secret carries a last-applied annotation. Only named PVC `volumeName` fields are ignored. The idle hub ServiceAccount can neither `exec` nor create Secrets (`idle_bootstrap_cannot_exec`, `idle_bootstrap_cannot_write_credentials`). `platform-ingress` is installed in `gitlab-system`.

Static checks: `validate.sh --static`. The former offline tests (`chart-gitops.test.py`, `stage070-upgrade.test.py`, `security-boundaries.test.py`) are in git history at `82092e01`.

```bash
oc get deploy,sts,obc,pvc,cronjob -n gitlab-system
oc get configmap gitlab-gitlab-chart-info -n gitlab-system -o jsonpath='{.data}'
```

## Alignment with official guidance

| Topic | Official guidance | This repository | Status |
|---|---|---|---|
| Installation method on OpenShift | Use the GitLab Operator on OpenShift, "otherwise you must update the security context constraints yourself" [1][2] | Offline chart render with namespace-scoped SCC bindings | Deviation (justified: one Argo CD owner and reviewable manifests, no Helm or Operator at runtime; decided 2026-10-13) |
| SCC | Operator binds `nonroot-v2` to `gitlab-app-nonroot`, a ServiceAccount with no other privileges [7]; `nonroot-v2` drops all capabilities and defaults seccomp to `runtime/default` [8] | `use` on `nonroot-v2` only, by name, in one namespace; no `anyuid` or `privileged` | Aligned |
| Chart and application version | Chart 10.4.2 maps to GitLab 19.4.2 [4] | Lock and receipt both record 10.4.2 / 19.4.2 | Aligned |
| External PostgreSQL | `global.psql.*` with a password Secret [10]; GitLab 19.x needs PostgreSQL 17.x–18.x [11] | `global.psql` to `gitlab-postgresql`; PostgreSQL 17.6 per the restore record in Operations | Aligned (version pinned by digest only) |
| External Redis/Valkey | `global.redis.host` and auth Secret [12]; Valkey minimum and recommended 7.2 [11] | `global.redis` to `gitlab-valkey` with `auth.secret: gitlab-cache` | Aligned (Valkey version not recorded in the repository) |
| Object storage | Separate bucket per object type; backups through an s3cmd-format `toolbox.backups.objectStorage.config` [3] | Four per-type buckets plus backup and temporary backup buckets, s3cmd config | Aligned |
| OBC consumption | OBC ConfigMap and Secret carry bucket name and keys [5] | Read by `bootstrap.py` | Aligned |
| Backups | Scheduled through `toolbox.backups.cron`; Rails secrets are not in the backup and must be saved separately [13] | Daily CronJob; separate encrypted escrow is documented as an operator duty | Aligned |
| OIDC | `discovery: true`; issuer equals the discovery base; `uid_field` defaults to `sub` [6] | Platform-realm issuer, discovery, `sub` | Aligned |
| Dev Spaces GitLab OAuth | Callback `https://<devspaces>/api/oauth/callback`; scopes `api write_repository openid`; Confidential [14]; Secret `gitlab-oauth-config` with the documented labels and annotations [15] | Same, created by the hub | Aligned. The guide also asks to tick "Expire access tokens"; the API call does not set it explicitly (not verified) |
| Argo CD account for Developer Hub | Declare local users in the Argo CD CR (`spec.localUsers`); the operator issues, stores and renews their API tokens; use `admin` only for initial setup [16], [17] | Stage 010 `argocd-instance.yaml` declares local user `rhdh` (2160h token, auto-renew) and its read-only `rhdh-reader` rules; the operator writes `openshift-gitops/rhdh-local-user`. The hub has no access to the admin password; `configure-argocd-reader.py` only checks the account and rules | Aligned |
| Network isolation | Router traffic is admitted through the `policy-group.network.openshift.io/ingress` namespace label [17] | `platform-ingress` allows same namespace, router and monitoring | Aligned (ingress only; egress unchanged by design) |

## References

1. GitLab Helm chart, "Install GitLab on Kubernetes" (upstream). https://docs.gitlab.com/charts/
2. GitLab Operator (upstream). https://docs.gitlab.com/operator/
3. Configure the GitLab chart with an external object storage (upstream). https://docs.gitlab.com/charts/advanced/external-object-storage/
4. GitLab chart version mappings (upstream). https://docs.gitlab.com/charts/installation/version_mappings/
5. Managing hybrid and multicloud resources, "Object Bucket Claim", Red Hat OpenShift Data Foundation 4.22. https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.22/html/managing_hybrid_and_multicloud_resources/object-bucket-claim
6. Use OpenID Connect as an authentication provider (upstream). https://docs.gitlab.com/administration/auth/oidc/
7. GitLab Operator, Security context constraints (upstream). https://docs.gitlab.com/operator/security_context_constraints/
8. Authentication and authorization, "Managing security context constraints", OpenShift Container Platform 4.22. https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html/authentication_and_authorization/managing-pod-security-policies
9. Sync phases and waves, Argo CD (upstream). https://argo-cd.readthedocs.io/en/stable/user-guide/sync-waves/
10. Configure the GitLab chart with an external database (upstream). https://docs.gitlab.com/charts/advanced/external-db/
11. GitLab installation requirements, PostgreSQL and Redis/Valkey (upstream). https://docs.gitlab.com/install/requirements/
12. Configure the GitLab chart with an external Redis (upstream). https://docs.gitlab.com/charts/advanced/external-redis/
13. Backing up a GitLab installation (chart, upstream). https://docs.gitlab.com/charts/backup-restore/backup/
14. Setting up the GitLab authorized application, Red Hat OpenShift Dev Spaces 3.30. https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/integrate-proc_setting_up_the_gitlab_authorized_application
15. Applying the GitLab-authorized application Secret, Red Hat OpenShift Dev Spaces 3.30. https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/integrate-proc_applying_the_gitlab_authorized_application_secret
16. User management, local users and admin account, Argo CD (upstream). https://argo-cd.readthedocs.io/en/stable/operator-manual/user-management/
17. Access control and user management, chapter 4 "Managing local users in Argo CD", Red Hat OpenShift GitOps 1.20. https://docs.redhat.com/en/documentation/red_hat_openshift_gitops/1.20/html-single/access_control_and_user_management
17. Network security, "Network policy", OpenShift Container Platform 4.22. https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html/network_security/network-policy

Repository: [Stage 070 README](../../../../stages/070-advanced-app-platform/README.md) · [Operations: GitLab release](../../../../docs/OPERATIONS.md#stage-070-gitlab-release) · [Troubleshooting: enrollment pending](../../../../docs/TROUBLESHOOTING.md#stage-070-gitlab-project-enrollment-is-pending)
