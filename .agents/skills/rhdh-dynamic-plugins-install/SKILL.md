---
name: rhdh-dynamic-plugins-install
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhdh
  docs-version: "1.10"
  skill-group: "Developer Hub"
description: >
  Use when adding, removing, pinning or debugging a Developer Hub dynamic
  plugin in this demo: the dynamic-plugins-rhdh ConfigMap referenced by the
  Backstage CR, embedded ./dynamic-plugins/dist packages versus digest-pinned
  OCI packages from rhdh-plugin-export-overlays, the includes of
  dynamic-plugins.default.yaml, the install-dynamic-plugins init container,
  and a portal pod that fails to start after a plugin change. Do NOT use for
  per-plugin settings and annotations (use rhdh-dynamic-plugins-configure),
  support tiers (use rhdh-dynamic-plugins-reference), or writing new plugins
  (use rhdh-dynamic-plugins-develop).
---

# RHDH dynamic plugin installation

Thin skill: repo decisions and pitfalls here, product procedure in the linked
Developer Hub 1.10 sections. Detailed record:
`gitops/stages/070-advanced-app-platform/070-rhdh/README.md` ("Plugins").

## When to use

- A plugin is added to, removed from, or re-pinned in
  `070-rhdh/rhdh-instance/dynamic-plugins-configmap.yaml`.
- The `backstage-developer-hub` pod stays in `Init` or crash-loops after a
  plugin change.
- Reviewing whether a plugin is embedded in the RHDH image or pulled from OCI.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| Operator path only: ConfigMap `dynamic-plugins-rhdh` (key `dynamic-plugins.yaml`) referenced by `spec.application.dynamicPluginsConfigMapName` on `Backstage` `developer-hub` (`rhdh.redhat.com/v1alpha5`) | `gitops/stages/070-advanced-app-platform/070-rhdh/rhdh-instance/dynamic-plugins-configmap.yaml`, `070-rhdh/rhdh-instance/backstage.yaml` | [Install with the Operator][operator] |
| The file `includes` `dynamic-plugins.default.yaml` and enables embedded packages by path: GitLab catalog and scaffolder modules, RBAC, Kubernetes backend and frontend, Topology | `dynamic-plugins-configmap.yaml` | [Enable plugins added in the RHDH image][embedded] |
| Tekton, Argo CD (Community frontend) and Roadie Argo CD backend are OCI packages from `ghcr.io/redhat-developer/rhdh-plugin-export-overlays`, pinned by `@sha256` digest, never by tag | `dynamic-plugins-configmap.yaml` (the former offline test `stage070-upgrade.test.py` that enforced it is in git history at `82092e01`) | [Install with the Operator][operator], [Community plugins][community] |
| No custom plugins, no air-gapped mirroring, no registry CA for OCI pulls (ghcr.io is public) | — | [Custom plugins][custom], [Mirror plugins][mirror], [Custom certificates][oci-certs] |
| Extensions UI stays at product default; plugins are installed only through Git | `dynamic-plugins-configmap.yaml` | [Extensions][extensions] |

## Procedure

1. Check the plugin's support tier and package form in
   `rhdh-dynamic-plugins-reference`; for an OCI package, resolve the digest of
   the tag you reviewed and write `oci://...@sha256:<digest>`.
2. Edit only `dynamic-plugins-configmap.yaml` (and the app-config block the
   plugin needs, see `rhdh-dynamic-plugins-configure`). Keep `disabled: false`
   explicit.
3. Static checks: `./stages/070-advanced-app-platform/validate.sh --static`.
4. After the OpenShift safety guard in `AGENTS.md`, deploy with
   `./stages/070-advanced-app-platform/deploy.sh` and run `validate.sh`.
5. Read-only diagnosis of a failed start:

   ```bash
   oc get pods -n rhdh
   oc logs deployment/backstage-developer-hub -n rhdh -c install-dynamic-plugins --tail=100
   oc logs deployment/backstage-developer-hub -n rhdh -c backstage-backend --tail=200
   ```

## Pitfalls

- A plugin that needs environment variables fails the pod start until they
  exist; the repo injects them from `rhdh-secrets` and `rhdh-gitlab` through
  `extraEnvs.secrets` ([Troubleshoot a pod startup failure][startup]).
- `rhdh-secrets` `/data` is ignored by Argo CD and written by the configure
  hook; adding a variable means changing `070-rhdh/jobs/configure-rhdh.yaml`, not
  the placeholder Secret.
- One backend must run migrations on a fresh database: keep `maxSurge: 0` in
  `backstage.yaml` when a plugin change restarts the portal.
- Tekton is a Community plugin delivered as OCI in 1.10, not an embedded
  wrapper; do not switch it to a `./dynamic-plugins/dist` path.

## Official documentation (Developer Hub 1.10)

| Topic | Section |
|---|---|
| Operator install, dependencies | [Install with the Operator][operator], [Dependency management][deps] |
| Embedded plugins | [Enable plugins added in the RHDH image][embedded] |
| Custom plugins (not used) | [Custom plugins][custom] |
| Disconnected and private registries (not used) | [Mirror plugins][mirror], [Custom certificates][oci-certs] |
| Extensions UI | [Extensions][extensions] |
| Front-end wiring (mount points) | [Front-end plugin wiring][wiring], [Using mount points][mounts] |
| Pod startup failure | [Troubleshoot][startup] |

## Related skills

`rhdh-dynamic-plugins-configure`, `rhdh-dynamic-plugins-reference`,
`rhdh-dynamic-plugins-develop`, `rhdh-install-airgapped`, `rhdh-configure`.

[operator]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/installing_and_viewing_plugins_in_red_hat_developer_hub/index#install-dynamic-plugins-with-the-rhdh-operator_install-dynamic-plugins-in-rhdh
[deps]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/installing_and_viewing_plugins_in_red_hat_developer_hub/index#dynamic-plugins-dependency-management_install-dynamic-plugins-in-rhdh
[embedded]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/installing_and_viewing_plugins_in_red_hat_developer_hub/index#enable-plugins-added-in-the-rhdh-container-image_plugins-in-rhdh
[custom]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/installing_and_viewing_plugins_in_red_hat_developer_hub/index#plugins-in-rhdh_mirror-rhdh-dynamic-plugins-in-disconnected-environments
[mirror]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/installing_and_viewing_plugins_in_red_hat_developer_hub/index#mirror-rhdh-dynamic-plugins-in-disconnected-environments_install-dynamic-plugins-in-rhdh
[oci-certs]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/installing_and_viewing_plugins_in_red_hat_developer_hub/index#install-plugins-from-oci-registries-by-using-custom-certificates_mirror-rhdh-dynamic-plugins-in-disconnected-environments
[extensions]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/installing_and_viewing_plugins_in_red_hat_developer_hub/index#extensions-in-rhdh_plugins-in-rhdh
[wiring]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/installing_and_viewing_plugins_in_red_hat_developer_hub/index#front-end-plugin-wiring_plugins-in-rhdh
[mounts]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/installing_and_viewing_plugins_in_red_hat_developer_hub/index#using-mount-points_front-end-plugin-wiring
[startup]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/installing_and_viewing_plugins_in_red_hat_developer_hub/index#troubleshoot-a-pod-startup-failure-after-enabling-a-plugin_plugins-in-rhdh
[community]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/dynamic_plugins_reference/index#community-supported-plugins_dynamic-plugins-reference
