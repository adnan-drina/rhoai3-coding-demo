---
name: rhdh-install-airgapped
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "rhdh"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Developer Hub"
description: >
  Use when installing Red Hat Developer Hub 1.10 in disconnected, air-gapped,
  or network-restricted environments using either the Operator or Helm chart.
  Covers fully disconnected (mirror-to-disk) and partially disconnected
  (mirror-to-registry) workflows, image mirroring, plugin mirroring, pull
  secret updates, and registries.conf configuration. Do NOT use for connected
  installations (use rhdh-install-ocp), post-install configuration, or plugin
  development.
---

# RHDH Install in Air-Gapped Environment

Use this skill to install Red Hat Developer Hub 1.10 in a disconnected or
network-restricted environment on OpenShift Container Platform or supported
Kubernetes platforms.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority. This skill covers fully disconnected and
partially disconnected workflows for both the Operator and Helm chart methods,
including image mirroring, plugin artifact mirroring, pull secret configuration,
and init container registry redirection.

## Environment Types

- **Fully disconnected** — No internet access; mirror images to disk, transfer
  physically, then push to internal registry.
- **Partially disconnected** — Cluster cannot reach external registries but can
  access an internal mirror registry directly.

## Operator Installation (Air-Gapped)

### Fully Disconnected Workflow

1. Download mirroring script from `rhdh-operator` repo (release-1.10 branch)
2. Run `prepare-restricted-environment.sh --filter-versions "1.10" --to-dir <path>`
3. Transfer disk archive to disconnected environment
4. Run `install.sh --from-dir <path> [--to-registry <registry>]`
5. Update cluster pull secret for mirror registry
6. Mirror plugins with `mirror-plugins.sh`
7. Create `rhdh-plugin-mirror-conf` ConfigMap for registries.conf
8. Mount ConfigMap in `install-dynamic-plugins` init container via Backstage CR

### Partially Disconnected Workflow

1. Download mirroring script
2. Run `prepare-restricted-environment.sh --filter-versions "1.10" --to-registry <registry>`
3. Update cluster pull secret
4. Mirror plugins with `mirror-plugins.sh --to-registry <registry>`
5. Create and mount registries.conf ConfigMap

## Helm Chart Installation (Air-Gapped, OpenShift)

### Fully Disconnected Workflow

1. Create `ImageSetConfiguration` specifying `redhat-developer-hub` version 1.10
2. Run `oc mirror --v2` to archive images to disk
3. Transfer archive to disconnected environment
4. Run `oc mirror --v2 --from file://<archive> docker://<registry>`
5. Apply generated IDMS/ITMS manifests
6. Update cluster pull secret
7. Deploy Helm chart from workspace archive with `helm install`
8. Mirror plugins and configure registries.conf in Helm values

### Partially Disconnected Workflow

1. Create `ImageSetConfiguration` for version 1.10
2. Run `oc mirror --v2 --config=<config> docker://<registry>`
3. Apply IDMS/ITMS manifests
4. Update cluster pull secret
5. Deploy Helm chart from workspace with `helm install`
6. Mirror plugins and configure registries.conf

## Critical Configuration: Plugin Mirroring

Cluster-level `ImageDigestMirrorSet` and `ImageContentSourcePolicy` do NOT
apply to the `install-dynamic-plugins` init container (uses `skopeo` directly).
You must configure `registries.conf` explicitly.

### registries.conf ConfigMap

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: rhdh-plugin-mirror-conf
data:
  rhdh-registries.conf: |
    [[registry]]
    prefix = "registry.access.redhat.com/rhdh"
    location = "<target_registry>/rhdh"

    [[registry]]
    prefix = "quay.io/rhdh"
    location = "<target_registry>/rhdh"
```

### Mount in Backstage CR (Operator)

```yaml
spec:
  application:
    extraFiles:
      configMaps:
        - name: rhdh-plugin-mirror-conf
          key: rhdh-registries.conf
          mountPath: /etc/containers/registries.conf.d
          containers:
            - install-dynamic-plugins
```

### Mount in Helm values

```yaml
upstream:
  backstage:
    extraVolumes:
      - name: rhdh-plugin-mirror-conf
        configMap:
          name: rhdh-plugin-mirror-conf
    initContainers:
      - name: install-dynamic-plugins
        volumeMounts:
          - name: rhdh-plugin-mirror-conf
            mountPath: /etc/containers/registries.conf.d/rhdh-registries.conf
            subPath: rhdh-registries.conf
            readOnly: true
```

## Tools Required

- `oc-mirror` (recommended on OCP), `opm`, Podman 5.3+, Skopeo 1.20+, `umoci`,
  `yq` 4.44+, `jq` 1.7+, GNU `tar` 1.35+, GNU `sed`
- `oc mirror --v2` flag required for OCP 4.21+

## Verification

```bash
oc get pods -n rhdh-operator
kubectl -n rhdh-operator get pods
oc get backstage -n <namespace>
```

## Workflow

1. Read `references/official-doc-extraction.md` for exact commands and YAML.
2. Determine environment type (fully vs partially disconnected).
3. Choose installation method (Operator vs Helm).
4. Execute the appropriate mirroring workflow.
5. Update pull secrets and apply mirror configuration.
6. Mirror plugins separately (required for both methods).
7. Configure registries.conf for the init container.
8. Validate pod readiness.

## Related Skills

- `rhdh-install-ocp` — Connected OpenShift installation
- `ocp-image-registry-and-mirroring` — OCP image mirroring concepts

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
