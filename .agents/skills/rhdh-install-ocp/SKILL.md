---
name: rhdh-install-ocp
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "rhdh"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Developer Hub"
description: >
  Use when installing Red Hat Developer Hub 1.10 on OpenShift Container Platform
  using the Operator or Helm chart, including prerequisites, namespace setup,
  custom configuration provisioning, Backstage CR authoring, and verification.
  Do NOT use for air-gapped/disconnected installations (use rhdh-install-airgapped),
  configuration beyond initial deployment, or plugin development.
---

# RHDH Install on OpenShift Container Platform

Use this skill to install Red Hat Developer Hub 1.10 on a connected OpenShift
Container Platform cluster using either the Operator or the Helm chart.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority. This skill covers Operator installation
via OperatorHub, Helm chart deployment via console or CLI, custom configuration
provisioning (config maps, secrets, dynamic plugins), Backstage CR authoring,
and deployment verification.

## Installation Methods

RHDH 1.10 supports two installation methods on OpenShift:

1. **Red Hat Developer Hub Operator** — OLM-managed, automatic subscription
   updates, installed via OperatorHub.
2. **Red Hat Developer Hub Helm chart** — manual install via web console or
   Helm CLI from `charts.openshift.io`.

## Prerequisites (Operator)

- OpenShift Container Platform 4.18 to 4.21
- Administrator access to the web console
- Appropriate roles and permissions to create applications
- System meets minimum sizing requirements

## Prerequisites (Helm chart)

- OpenShift Container Platform with admin role configured
- Project created in OpenShift
- Helm CLI installed (for CLI method)
- System meets minimum sizing requirements

## Operator Installation

- **Update channels:** `fast` or `fast-1.10` (z-stream only)
- **Installation mode:** All namespaces on the cluster (required)
- **Installed namespace:** `rhdh-operator` (recommended for security)
- **Verification:** Ecosystem > Installed Operators shows `Succeeded`

## Custom Configuration Provisioning

Before creating the Backstage CR, provision:

1. **Secrets** — `oc create secret generic my-rhdh-secrets --from-file=secrets.txt`
2. **App config** — `oc create configmap my-rhdh-app-config --from-file=app-config.yaml`
3. **Dynamic plugins** — `oc create configmap dynamic-plugins-rhdh --from-file=dynamic-plugins.yaml`

Critical: Set `baseUrl` in `app-config.yaml` to match the external URL of the
instance in both `app.baseUrl` and `backend.baseUrl`.

## Backstage CR

- **apiVersion:** `rhdh.redhat.com/v1alpha5`
- **kind:** `Backstage`
- **Key spec fields:** `spec.application.appConfig.configMaps`,
  `spec.application.dynamicPluginsConfigMapName`,
  `spec.application.extraEnvs.secrets`, `spec.application.route.enabled`,
  `spec.database.enableLocalDb`

Apply with:
```bash
oc apply -f my-rhdh-custom-resource.yaml -n my-rhdh-project
```

## Helm Chart Installation (CLI)

```bash
NAMESPACE=rhdh
oc new-project ${NAMESPACE} || oc project ${NAMESPACE}

helm upgrade redhat-developer-hub -i \
  https://github.com/openshift-helm-charts/charts/releases/download/redhat-redhat-developer-hub-1.10.1/redhat-developer-hub-1.10.1.tgz

PASSWORD=$(oc get secret redhat-developer-hub-postgresql -o jsonpath="{.data.password}" | base64 -d)
CLUSTER_ROUTER_BASE=$(oc get route console -n openshift-console -o=jsonpath='{.spec.host}' | sed 's/^[^.]*\.//')

helm upgrade redhat-developer-hub -i \
  "https://github.com/openshift-helm-charts/charts/releases/download/redhat-redhat-developer-hub-1.10.1/redhat-developer-hub-1.10.1.tgz" \
  --set global.clusterRouterBase="$CLUSTER_ROUTER_BASE" \
  --set global.postgresql.auth.password="$PASSWORD"
```

## Verification

```bash
oc get backstage -n my-rhdh-project
oc get pods -n my-rhdh-project
oc get route -n my-rhdh-project
echo "https://redhat-developer-hub-${NAMESPACE}.${CLUSTER_ROUTER_BASE}"
```

## Troubleshooting

Pod in `CrashLoopBackOff` with error `Missing required config value at
'backend.database.client'` indicates the configuration files are not accessible.
Verify config maps are correctly mounted.

## Workflow

1. Read `references/official-doc-extraction.md` for exact YAML patterns.
2. Choose installation method (Operator vs Helm).
3. Verify prerequisites and sizing.
4. For Operator: install via OperatorHub, provision config, create Backstage CR.
5. For Helm: create project, run `helm upgrade -i`, configure router base.
6. Validate with verification commands.

## Related Skills

- `rhdh-install-airgapped` — Air-gapped/disconnected installation
- `ocp-gitops-operator` — GitOps-managed deployment patterns

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
