---
name: rhdh-configure
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhdh
  docs-version: "1.10"
  skill-group: "Developer Hub"
description: >
  Use when changing or debugging this demo's Red Hat Developer Hub
  configuration: the Backstage CR developer-hub (appConfig,
  dynamicPluginsConfigMapName, extraFiles, extraEnvs, deployment patch
  maxSurge 0), ConfigMap app-config-rhdh, the runtime Secret rhdh-secrets
  written by the configure hook, NODE_EXTRA_CA_CERTS cluster CA trust, the
  catalog file location and providers, local database, and OutOfSync on
  Operator-owned fields. Do NOT use for appearance and global header (use
  rhdh-customize), sign-in (use rhdh-authentication), RBAC (use
  rhdh-authorization), plugins (use rhdh-dynamic-plugins-configure), TechDocs
  (use rhdh-techdocs-config), or upgrades (use rhdh-upgrade).
---

# Developer Hub configuration

Thin skill: repo decisions and pitfalls here, product behavior in the linked
Developer Hub 1.10 sections. Detailed record:
`gitops/stages/070-advanced-app-platform/070-rhdh/README.md`.

## When to use

- A change touches `gitops/stages/070-advanced-app-platform/070-rhdh/rhdh-instance/`
  or `070-rhdh/jobs/configure-rhdh.yaml`.
- The portal does not start, shows 503, or a plugin cannot reach the cluster.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| All configuration through the `Backstage` CR (`rhdh.redhat.com/v1alpha5`): `appConfig` ConfigMap `app-config-rhdh`, `dynamicPluginsConfigMapName: dynamic-plugins-rhdh`, `extraFiles`, `extraEnvs` | `rhdh-instance/backstage.yaml`, `rhdh-instance/app-config-configmap.yaml` | [Backstage CR][cr], [Extra files and env][extra] |
| `extraFiles` mounts the RBAC CSV, the runtime catalog `catalog-runtime-rhdh` and `kube-root-ca.crt` into `backstage-backend` only | `rhdh-instance/backstage.yaml` | [Mount to specific containers][mount] |
| Cluster CA trusted through `NODE_EXTRA_CA_CERTS`, never by disabling TLS | `rhdh-instance/backstage.yaml` | [NODE_EXTRA_CA_CERTS][ca] |
| `spec.deployment.patch` sets `maxSurge: 0`, `maxUnavailable: 1` so only one backend runs migrations | `rhdh-instance/backstage.yaml` | [Deployment with the Operator][deploy] |
| Cluster-specific values are `${VAR}` references; the wave-18 hook `job-configure-rhdh` merge-patches `rhdh-secrets` (base URL, OIDC and session secrets, Kubernetes and Argo CD tokens, catalog URL); Git holds placeholders only | `rhdh-instance/rhdh-secrets.yaml`, `jobs/configure-rhdh.yaml` | [RHDH secrets][secrets] |
| Catalog: one file location (runtime catalog, only source allowed to add `Template`), GitLab discovery that may not ingest templates, `orphanStrategy: delete` | `rhdh-instance/app-config-configmap.yaml`, `jobs/catalog/` | [Define locations][locations] |
| Operator-managed local PostgreSQL (Deviation; external database not used) | Backstage CR (no database override) | [External PostgreSQL][pg] |
| `backend.reading.allow` lists only the GitLab host and GitHub raw hosts | `rhdh-instance/app-config-configmap.yaml` | [Application configuration][appconfig] |

Paths are under `gitops/stages/070-advanced-app-platform/070-rhdh/`.

## Procedure

1. Edit the ConfigMap or CR in Git; secrets only through the configure hook
   or `070-gitlab`, never `stringData` in Git.
2. Validate statically, then sync and validate after the safety guard in `AGENTS.md`:

   ```bash
   ./stages/070-advanced-app-platform/validate.sh --static
   ./stages/070-advanced-app-platform/deploy.sh
   ./stages/070-advanced-app-platform/validate.sh
   ```

3. Read-only checks:

   ```bash
   oc get backstage developer-hub -n rhdh -o yaml
   oc get secret rhdh-secrets -n rhdh -o jsonpath='{.data}' | jq 'keys'
   oc logs deployment/backstage-developer-hub -n rhdh -c backstage-backend --tail=100
   ```

## Pitfalls

- Two backends on a fresh database crash with `relation ... already exists`
  and the portal stays 0/1; keep `maxSurge: 0` (`strategy.type: Recreate`
  produces an invalid Deployment with the Operator's base rollingUpdate).
- The Operator disables service-account token automount, so the cluster CA
  must come from `kube-root-ca.crt` via `extraFiles`:
  `docs/TROUBLESHOOTING.md#developer-hub-topologycikubernetes-tabs-show-problem-retrieving-kubernetes-objects`.
- Argo CD ignores `rhdh-secrets` `/data` so syncs keep the runtime values;
  never add `stringData` to the Git placeholder (it would overwrite them).
- Catalog load and generator failures:
  `docs/TROUBLESHOOTING.md#red-hat-developer-hub-catalog-does-not-load-coolstore`,
  `docs/TROUBLESHOOTING.md#rhdh-catalog-generator-refuses-factory_bundle_mismatch`.
- OutOfSync while healthy: narrow `ignoreDifferences` only, never the whole
  spec (`docs/TROUBLESHOOTING.md#red-hat-developer-hub-is-healthy-but-stage-070-is-outofsync`).
- Day-2 notes: `docs/OPERATIONS.md#stage-070--developer-hub-rhdh-component`.

## Official documentation (Developer Hub 1.10)

| Topic | Section |
|---|---|
| Configuration files | [Overview][files], [Application configuration][appconfig], [RHDH secrets][secrets], [Backstage CR][cr], [Precedence][precedence] |
| Running a custom configuration | [With the Operator][run-op], [Default configuration][defaults] |
| Container injection | [Extra files and env][extra], [Mount to specific containers][mount], [Deployment with the Operator][deploy] |
| Trust and TLS | [NODE_EXTRA_CA_CERTS][ca], [Route with external TLS][route-tls] |
| Database and HA (not used) | [External PostgreSQL][pg], [High availability][ha] |
| Catalog descriptors | [Catalog entity descriptor][descriptor], [Define locations][locations] |
| Troubleshooting | [Configuration issues][ts] |

## Related skills

`rhdh-install-ocp`, `rhdh-customize`, `rhdh-authentication`,
`rhdh-authorization`, `rhdh-git-integration`, `rhdh-dynamic-plugins-configure`,
`rhdh-techdocs-config`.

[files]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/configuring_red_hat_developer_hub/index#rhdh-configuration-files-overview_understanding-rhdh-configuration-files
[appconfig]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/configuring_red_hat_developer_hub/index#application-configuration-file_understanding-rhdh-configuration-files
[secrets]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/configuring_red_hat_developer_hub/index#rhdh-secrets_understanding-rhdh-configuration-files
[cr]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/configuring_red_hat_developer_hub/index#custom-resource_understanding-rhdh-configuration-files
[precedence]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/configuring_red_hat_developer_hub/index#configuration-precedence_understanding-rhdh-configuration-files
[run-op]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/configuring_red_hat_developer_hub/index#use-the-rhdh-operator-to-run-rhdh-with-your-custom-configuration_provision-and-use-your-custom-rhdh-configuration
[defaults]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/configuring_red_hat_developer_hub/index#rhdh-default-configuration_configuring-rhdh
[extra]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/configuring_red_hat_developer_hub/index#inject-extra-files-and-environment-variables-into-containers_configuring-rhdh
[mount]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/configuring_red_hat_developer_hub/index#mount-secrets-and-pvcs-to-specific-containers_configuring-rhdh
[deploy]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/configuring_red_hat_developer_hub/index#configure-rhdh-deployment-when-using-the-operator_configuring-rhdh
[ca]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/configuring_red_hat_developer_hub/index#configure-trust-for-corporate-certificate-authority-with-node-extra-ca-certs_configuring-rhdh
[route-tls]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/configuring_red_hat_developer_hub/index#configure-a-route-with-an-external-tls-certificate-by-using-the-operator_configuring-rhdh
[pg]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/configuring_red_hat_developer_hub/index#configure-external-postgresql-databases_configuring-rhdh
[ha]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/configuring_red_hat_developer_hub/index#configure-high-availability-in-rhdh_configuring-rhdh
[descriptor]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/configuring_red_hat_developer_hub/index#catalog-entity-descriptor-reference_rhdh-default-configuration
[locations]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/configuring_red_hat_developer_hub/index#define-locations-in-the-catalog_rhdh-default-configuration
[ts]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/configuring_red_hat_developer_hub/index#troubleshoot-rhdh-configuration-issues_configuring-rhdh
