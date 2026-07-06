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
