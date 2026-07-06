---
name: rhdh-upgrade
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "rhdh"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Developer Hub"
description: >
  Use when upgrading Red Hat Developer Hub to a later version using Operator or
  Helm chart. Covers Operator subscription upgrades, Helm chart version bumps,
  and the 1.8-to-1.10 migration for custom values.yaml overrides. Do NOT use
  for initial installation, configuration, or customization of RHDH.
---

# RHDH Upgrade

Use this skill to upgrade Red Hat Developer Hub 1.10 grounded in official
product documentation.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority. This skill covers Operator-based
upgrades, Helm chart upgrades, and the specific 1.8-to-1.10 migration path.

## Key Upgrade Paths

1. **Operator upgrade** — Use the OpenShift web console Subscription page to
   approve an available InstallPlan upgrade for the RHDH Operator.
2. **Helm chart upgrade (web console)** — Select the newer Helm chart version
   from the OpenShift console; save `values.yaml` first if initially deployed
   via Helm CLI.
3. **Helm chart upgrade (CLI)** — Run `helm upgrade` with the target chart
   version and a `values.yaml` override file.
4. **1.8-to-1.10 migration** — Manually merge new mandatory defaults into
   custom `values.yaml` files that override `extraVolumeMounts`,
   `extraVolumes`, or `initContainers`.

## Operator Upgrade Procedure

Prerequisites:
- Logged in as administrator on OpenShift web console
- RHDH Operator already installed
- Appropriate roles and permissions configured

Steps:
1. Navigate to Operators > Installed Operators > Red Hat Developer Hub Operator
2. Click Subscription tab
3. In Upgrade status field, click "Upgrade available"
4. On InstallPlan details page, click Preview InstallPlan > Approve

Verification:
- Upgrade status field shows "Up to date"

## Helm Chart Upgrade (CLI)

```bash
oc login -u <user> -p <password> https://api.<HOSTNAME>:6443
oc project my-rhdh-project
helm upgrade -i rhdh -f new-values.yml \
  openshift-helm-charts/redhat-developer-hub --version 1.10.1
```

## 1.8-to-1.10 Migration (Helm)

When custom `values.yaml` overrides `upstream.backstage.extraVolumeMounts`,
`upstream.backstage.extraVolumes`, or `upstream.backstage.initContainers`,
merge these mandatory new defaults before upgrading:

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

View full defaults:
```bash
helm show values redhat-developer-hub --repo https://charts.openshift.io --version 1.10.1
```

## Important Notes

- OCP supported from version 4.18 to 4.21
- Helm upgrades can skip intermediate versions; review release notes for all
  skipped versions to identify breaking changes
- Orchestrator plugin 1.7 users must manually update plugin config after
  Operator approval to avoid failed deployment
- Helm CLI-deployed releases cannot be upgraded via the OCP web console due to
  platform limitations; use `helm upgrade` instead

## Workflow

1. Read `references/official-doc-extraction.md` for exact procedures.
2. Identify upgrade method (Operator or Helm).
3. If Helm with custom `values.yaml`, check for affected override fields.
4. Apply the upgrade following documented steps.
5. Verify the RHDH application initializes successfully.

## Related Skills

- `rhdh-configure` — Configuration with config maps, secrets, and plugins
- `rhdh-customize` — Appearance and feature customization
- `rhdh-techdocs-config` — TechDocs plugin configuration

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
