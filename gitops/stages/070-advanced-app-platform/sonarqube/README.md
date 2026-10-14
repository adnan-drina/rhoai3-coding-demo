# SonarQube quality gate (`070-sonarqube`)

This Application runs SonarQube Community Build with its own PostgreSQL database in the `sonarqube` namespace. It defines the `AI Platform Gate` quality gate, which fails on any new issue, and gives the build namespace a control token. The Stage 070 pipelines use that token to mint project-scoped scanner tokens. Each project's Tekton `sonar-scan` task waits on the gate, so code from AI-assisted or agentic changes must pass the same static-analysis bar before an image is promoted. Developers sign in through the platform base SSO realm (SAML).

| | |
|---|---|
| Argo CD Application | `070-sonarqube` ([manifest](../../../argocd/app-of-apps/070-advanced-app-platform/sonarqube.yaml)) |
| Deployed by | `stages/070-advanced-app-platform/deploy.sh` → `application.py deploy` (deploy-order 5) |
| Validated by | `stages/070-advanced-app-platform/validate.sh` (live checks "SonarQube ready" and "SonarQube reachable", plus `security-status.py`); `validate.sh --static` (`sonarqube-bootstrap.test.py`, `sso-alignment.test.py`, `chart-gitops.test.py`, `correction-package.test.py`) |
| Sync | Automated, `prune: true`, `selfHeal: true`; `CreateNamespace`, `SkipDryRunOnMissingResource`, `RespectIgnoreDifferences`, `ClientSideApplyMigration=false`; compare-option `ServerSideDiff=true`; `ignoreDifferences` on `/spec/volumeName` of PVCs `sonardb-data` and `sonarqube` |
| Depends on | `070-namespaces` (the `sonarqube` and `app-platform-build` namespaces); `070-identity` (SAML client `sonarqube` in the base `sso` realm); Stage 010 (the existing Keycloak `rhbk` OpenID provider in the cluster OAuth config) |
| Used by | `070-pipelines` (the GitLab reconciler mints per-project analysis tokens from `app-platform-build/sonarqube-credentials`; the `sonar-scan` task); `070-devspaces` (workspace Sonar credential mirror); `stages/070-advanced-app-platform/rotate-credentials.py` |

## Why

The delivery contract needs a quality gate that a pipeline can enforce and an operator can audit. SonarQube's Community Build is the analysis engine. It is an upstream component, not a Red Hat product, as the [stage README](../../../../stages/070-advanced-app-platform/README.md#trust-boundaries) states. SonarSource ships it as a Helm chart that needs an external database [1].

The chart is rendered at authoring time into plain manifests under `generated/`, so Argo CD applies ordinary Kustomize output and no Helm runtime runs in the cluster. `scripts/platform/render-stage070-charts.py` renders it from the chart and the image digest pinned in `scripts/platform/stage070-charts.lock.json`. SonarQube, its database, its bootstrap and its ingress boundary are one Application because they share one namespace and one lifecycle. Pipelines and workspaces consume only the token Secret and the in-cluster Service.

## What

### Access and boundary

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| RoleBinding | `rhoai-developers-view` | `sonarqube` | `view` for group `rhoai-developers` (wave 5) |
| RoleBinding | `ai-admin-admin` | `sonarqube` | `admin` for user `ai-admin` (wave 5) |
| NetworkPolicy | `platform-ingress` | `sonarqube` | Ingress only: same namespace, OpenShift router, monitoring. TCP 9000 also from `app-platform-build`, `wksp-ai-developer`, `wksp-ai-admin`, `coolstore-dev` and namespaces labelled `rhoai3.redhat.com/pipeline-project: "true"`. Egress is not restricted |

The `sonarqube` namespace comes from `070-namespaces`.

### Database

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| ServiceAccount, Role, RoleBinding | `job-ensure-sonardb-secret` | `sonarqube` | Secrets `get`/`create` for the hook below (wave 3, standing) |
| Job (Sync hook) | `job-ensure-sonardb-secret` | `sonarqube` | Wave 4, `BeforeHookCreation,HookSucceeded`. Creates Secrets `sonarqube-monitoring` (`passcode`) and `sonardb` (user, password, database name) only when absent |
| PersistentVolumeClaim | `sonardb-data` | `sonarqube` | 5Gi RWO `gp3-csi` (wave 5) |
| Deployment, Service | `sonardb` | `sonarqube` | `registry.redhat.io/rhel9/postgresql-16`, pinned by digest, `Recreate` strategy, port 5432 (wave 6) |

### SonarQube (`generated/`, chart `sonarqube-2026.5.1002`)

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| ConfigMap | `sonarqube-config`, `sonarqube-install-plugins`, `sonarqube-jdbc-config` | `sonarqube` | Chart configuration; the JDBC URL points at `sonardb.sonarqube.svc:5432/sonar` (wave 6) |
| Secret | `sonarqube-http-proxies` | `sonarqube` | Empty proxy keys rendered by the chart; `ServerSideApply=true` (wave 6) |
| PersistentVolumeClaim | `sonarqube` | `sonarqube` | 10Gi RWO `gp3-csi`, `Prune=false` (wave 6) |
| Service, Route | `sonarqube` | `sonarqube` | ClusterIP 9000; edge-terminated Route that redirects HTTP (wave 6) |
| StatefulSet | `sonarqube` | `sonarqube` | 1 replica, image `docker.io/library/sonarqube:26.9.0.129388-community` pinned by digest, no service-account token mount, restricted container security context, requests 500m/2Gi, limits 800m/4Gi (wave 10) |

### Bootstrap (Sync hooks, wave 11, `BeforeHookCreation,HookSucceeded`)

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| ConfigMap | `sonarqube-admin-bootstrap-<hash>` | `sonarqube` | `bootstrap-admin.py`, `configure-sso.py`, `secret_writer.py` (wave 10, generated) |
| ServiceAccount | `job-configure-sonarqube` | `sonarqube` | Job identity |
| Role, RoleBinding | `job-configure-sonarqube` | `sonarqube`, `app-platform-build` | Secret `get`/`create`/`patch`/`update`; `get` on Route `sonarqube` |
| ClusterRole, ClusterRoleBinding | `job-configure-sonarqube-sso` | (cluster) | `get` on `oauths.config.openshift.io/cluster` only |
| Job | `job-configure-sonarqube` | `sonarqube` | Rotates the admin password, provisions the control token, creates the gate, configures SAML |

Not in Git: Secrets `sonardb`, `sonarqube-monitoring` and `sonarqube-admin` (created by the hooks), `app-platform-build/sonarqube-credentials` (written by the Job), and the per-project analysis tokens minted by the `070-pipelines` reconciler.

## How

- **Order.** The database Secret Job (wave 4) runs before PostgreSQL (waves 5–6). The SonarQube StatefulSet (wave 10) must be ready before the configuration Job (wave 11) runs. Inside one Application the waves give this order. Across Applications, `application.py` deploys `070-sonarqube` fifth, after `070-namespaces` has created `sonarqube` and `app-platform-build`.
- **Admin credential.** `bootstrap-admin.py` stores a random password in `sonarqube-admin` with the annotation `rhoai3.redhat.com/password-bootstrap: pending` before it changes the default `admin` password. It marks the Secret `ready` only after it verifies the new password. A rerun therefore resumes an interrupted rotation and never resets an unknown credential.
- **Control token.** The Job reuses the existing token in `app-platform-build/sonarqube-credentials` while it still authenticates. Otherwise it mints a new `platform-pipeline` token. `secret_writer.py` writes the Secret with keys `host` and `token`, and writes no `last-applied-configuration` annotation. The host is the in-cluster Service address that scanners use. `rotate-credentials.py` rotates this token through the HTTPS Route.
- **Quality gate.** The Job creates `AI Platform Gate` with the condition `new_violations > 0` and makes it the default gate.
- **SSO.** `configure-sso.py` reads the issuer of the `rhbk` OpenID provider from the cluster OAuth config. It requires that issuer to be the base `sso` realm. It fetches the realm's SAML descriptor and checks the entity ID, the signing certificate and the login endpoint. It then sets `sonar.core.serverBaseURL` and the SAML application ID, provider ID, login URL, certificate and the `login`/`name`/`email` attributes [2]. SAML is enabled last. Local users, tokens, groups and permissions are kept. The matching SAML client is created by `070-identity`.
- **Storage.** Both PVCs name `gp3-csi`, as the deploy contract requires. Argo CD ignores the controller-written `/spec/volumeName`. The SonarQube data PVC carries `Prune=false`.
- **Secrets as placeholders.** The kustomization adds `argocd.argoproj.io/sync-options: ServerSideApply=true` to the one rendered Secret, so Argo CD's server-side apply manager owns only the declared fields.

Failure handling, password recovery and the coverage-gate diagnosis are in [Troubleshooting](../../../../docs/TROUBLESHOOTING.md#stage-070-shared-sso-refuses-a-user-or-sonarqube-login) and [SonarQube gate fails on new_coverage](../../../../docs/TROUBLESHOOTING.md#sonarqube-gate-fails-on-new_coverage-0-despite-passing-tests).

## Validation

- `validate.sh` (live): "SonarQube ready" (StatefulSet `readyReplicas` = 1) and "SonarQube reachable" (`/api/system/status` returns 200 through the Route). `security-status.py` checks `ingress_policy_installed:sonarqube`, `no_retained_secret_annotation:sonarqube`, `no_credential_annotation:app-platform-build/sonarqube-credentials` and `only_named_controller_pvc_fields_ignored`.
- `validate.sh --static`:
  - `sonarqube-bootstrap.test.py`: password persisted before rotation, resume after interruption, no reset of an unknown credential.
  - `sso-alignment.test.py`: `test_correct_issuer_and_certificate_and_no_group_reset`, `test_wrong_issuer_missing_or_malformed_certificate_refused`, `test_foreign_login_endpoint_refused`, `test_sonar_does_not_receive_keycloak_administrator_credentials`.
  - `chart-gitops.test.py`: `test_sonarqube_version_label_is_not_the_image_digest`.
  - `correction-package.test.py`: `test_operator_sonar_uses_route_and_preserves_pipeline_host`, `test_ingress_contract_preserves_only_declared_cross_namespace_path`.
  - `sonarqube-scope.test.py`: the project-token logic in `070-pipelines` that consumes this component.
- `deploy.sh` refuses to deploy over a PostgreSQL 15 SonarQube database.

By hand (read-only):

```bash
oc get statefulset,deployment,pvc,networkpolicy -n sonarqube
oc get job -n sonarqube   # completed hooks are deleted; a remaining Job means a failed run
```

## Alignment with official guidance

| Topic | Official guidance | This repository | Status |
|---|---|---|---|
| Installation method | Helm chart with `community.enabled` and `community.buildNumber`; OpenShift via `OpenShift.enabled` [1] | Chart 2026.5.1002 rendered offline with those values; image pinned by digest | Deviation (justified: GitOps without a Helm runtime; same chart output) |
| Database | External database required by the chart, given through `jdbcOverwrite` [1]; PostgreSQL 15–18 with UTF-8 [4] | Dedicated PostgreSQL 16 through `jdbcOverwrite` | Aligned on version; UTF-8 encoding not verified on the live database |
| Monitoring passcode | Provide a monitoring passcode at install time; needed for upgrades [1] | Random `sonarqube-monitoring` Secret, referenced by the chart probes | Aligned |
| Sizing | Small installation: 4 GB RAM, 2 cores [3] | Requests 500m/2Gi, limits 800m/4Gi | Deviation (justified: demo-scale, one project per persona) |
| Keycloak SAML | SAML client with redirect `<base>/oauth2/callback/saml`; `login`, `name`, optional `email` attributes; provider ID, login URL and certificate from IdP metadata; server base URL set first [2] | All set by `configure-sso.py` from the live metadata; the base URL is set before SAML is enabled | Aligned |
| Group sync | Optional `groups` attribute [2] | Not configured; local groups and permissions kept | Aligned (optional feature not used) |
| Network isolation | The `policy-group.network.openshift.io/ingress` label selects router traffic on OVN-Kubernetes [5] | Ingress policy with router, monitoring and named scanner namespaces | Aligned; egress not restricted |
| Hook cleanup | `HookFailed` deletes failed hooks; otherwise a failed hook stays until the next run [6] | `BeforeHookCreation,HookSucceeded` | Aligned (failed hooks stay for diagnosis) |

## References

1. Installing SonarQube from the Helm chart, SonarQube Community Build (upstream). https://docs.sonarsource.com/sonarqube-community-build/server-installation/on-kubernetes-or-openshift/installing-helm-chart
2. Setting up SAML authentication with Keycloak, SonarQube Community Build (upstream). https://docs.sonarsource.com/sonarqube-community-build/instance-administration/authentication/saml/how-to-set-up-keycloak
3. Server host requirements, SonarQube Community Build (upstream). https://docs.sonarsource.com/sonarqube-community-build/server-installation/server-host-requirements
4. Installing the database, SonarQube Community Build (upstream). https://docs.sonarsource.com/sonarqube-community-build/server-installation/installing-the-database
5. Network policy, 3.1.1.1 "Policy additivity", OpenShift Container Platform 4.22. https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html/network_security/network-policy
6. Sync phases and waves, hook deletion policies, Argo CD (upstream). https://argo-cd.readthedocs.io/en/stable/user-guide/sync-waves/
7. Repository: [Stage 070 README](../../../../stages/070-advanced-app-platform/README.md), [Operations: Stage 070 GitLab release](../../../../docs/OPERATIONS.md#stage-070-gitlab-release), [chart lock](../../../../scripts/platform/stage070-charts.lock.json).
