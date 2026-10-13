# Current Verified Guidance — Developer Hub 1.10

Reviewed 2026-10-13 in the public Red Hat documentation browser. Sources:

- https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/upgrading_red_hat_developer_hub/index
- https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/red_hat_developer_hub_release_notes/index
- https://access.redhat.com/support/policy/updates/developerhub

## Current decisions
- Current 1.10 release notes include 1.10.5 and identify Backstage 1.49.4 / Node.js 24. Plugin compatibility and packaging must match the actual RHDH patch and image.
- Tekton, Quay and scaffolder Quay wrappers are removed from the embedded packages and are Community-supported. The Roadie Argo CD scaffolder wrapper is also removed. Use the officially listed OCI reference and verified digest instead of a guessed ./dynamic-plugins/dist path.
- The GitLab catalog/org/scaffolder modules listed as bundled are distinct from the Community GitLab UI/backend plugins. Do not infer package availability from a frontend name.
- Bulk Import repository listing requires the signed-in user's SCM OAuth token; service integration credentials do not substitute. Keep portal OIDC login, GitLab OAuth, catalog discovery and scaffolder credentials separate.
- The older upgrade guide lists OCP 4.18–4.21, but the current official lifecycle matrix explicitly includes OCP 4.22 for RHDH 1.10. Use the current matrix for support claims. Live upgrade/readiness qualification is still separate.
- 1.10.5 fixes dynamic-plugin override cleanup, startup SQLite crashes and stale Orchestrator/Lightspeed catalog links. Verify loaded packages and rendered configuration after upgrade, not only the CSV phase.

## Project workflow

Keep platform configuration in native Kustomize/Argo CD resources. Helm may be
used to render a pinned chart during authoring; do not install or upgrade a live
Helm release for this project. Keep credentials outside Git. Before any live
cluster access, use `load_env` and `check_oc_logged_in` from
`scripts/shared/lib.sh`; match the selected cluster and product schema.

## Earlier detailed reference — not a fresh product qualification

The material below retains the earlier extraction's provenance and useful
detail. Where a command, support level, version, default or field conflicts
with the current decisions above, the current decisions take precedence.
Verify any remaining version-sensitive detail against the current linked guide
and installed CLI/CRD before use. Historical runtime observations are not new
1.10 validation.

---

# Official Documentation Extraction

Source: Red Hat Developer Hub 1.10 — Upgrading Red Hat Developer Hub
Captured: 2026-07-06

---

## 1. Operator Upgrade

### Prerequisites

- Logged in as administrator on the OpenShift Container Platform web console
- Red Hat Developer Hub Operator installed
- Appropriate roles and permissions configured for the project
- OCP supported from version 4.18 to 4.21

### Procedure

1. In Administrator perspective: Operators > Installed Operators
2. Click Red Hat Developer Hub Operator
3. Click Subscription tab
4. In Upgrade status field, click "Upgrade available"
5. On InstallPlan details page, click Preview InstallPlan > Approve

### Post-upgrade note (Orchestrator plugin 1.7)

If on Orchestrator plugin 1.7, manually update the plugin configuration after
approval to avoid a failed deployment.

### Verification

- Upgrade status field value is "Up to date"

---

## 2. Helm Chart Upgrade (Web Console)

### Warning

If Developer Hub was installed manually using Helm CLI, the web console upgrade
will fail. Use Helm CLI instead. If you still want to use the console, select
the Helm Chart version from the drop-down, select the RHDH version, and save
your `values.yaml` configuration file in a different location first.

### Version skip policy

You can upgrade directly from any earlier version to the latest release without
installing intermediate versions. Before upgrading, review the release notes for
every skipped version to identify breaking changes, deprecations, or required
migration steps.

---

## 3. Helm Chart Upgrade (CLI)

```bash
oc login -u <user> -p <password> https://api.<HOSTNAME>:6443
oc project my-rhdh-project

helm upgrade -i rhdh -f new-values.yml \
  openshift-helm-charts/redhat-developer-hub --version 1.10.1
```

Extra values can be provided via a `new-values.yml` file that overrides
attributes in the installed chart or adds new attributes.

---

## 4. Migration: 1.8 to 1.10 (Helm Chart)

### Trigger

Custom `values.yaml` files that override any of the following:

- `upstream.backstage.extraVolumeMounts`
- `upstream.backstage.extraVolumes`
- `upstream.backstage.initContainers`

### Required merge

Add these mandatory new defaults into the custom `values.yaml`:

```yaml
upstream:
  backstage:
    extraVolumeMounts:
      - name: extensions-catalog
        mountPath: /extensions

    extraVolumes:
      - name: extensions-catalog
        emptyDir: {}

    initContainers:
      - name: install-dynamic-plugins
        env:
          - name: CATALOG_INDEX_IMAGE
            value: '{{ .Values.global.catalogIndex.image.registry }}/{{ .Values.global.catalogIndex.image.repository }}:{{ .Values.global.catalogIndex.image.tag }}'
          - name: CATALOG_ENTITIES_EXTRACT_DIR
            value: '/extensions'
        volumeMounts:
          - name: extensions-catalog
            mountPath: /extensions
```

### View full defaults

```bash
helm show values redhat-developer-hub --repo https://charts.openshift.io --version 1.10.1
```

### Verification

- Red Hat Developer Hub application successfully initializes after upgrade.
