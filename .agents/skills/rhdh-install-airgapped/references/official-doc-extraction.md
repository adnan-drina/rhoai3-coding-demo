# Official Documentation Extraction

Source: Red Hat Developer Hub 1.10 — Installing in an Air-Gapped Environment
Captured: 2026-07-06

---

## 1. Environment Types

- **Fully disconnected:** No internet access; mirror to disk, transfer
  physically, push to internal registry.
- **Partially disconnected:** Cluster cannot reach external registries but has
  access to an internal mirror registry.

## 2. Operator — Fully Disconnected

### Prerequisites

Tools required on workstation: GNU `sed`, GNU `tar` 1.35+, `jq` 1.7+,
`oc-mirror` (recommended on OCP), `opm` CLI, Podman 5.3+, Skopeo 1.20+,
`umoci` CLI, `yq` 4.44+.

Active registry session to `registry.redhat.io`.

### Download mirroring script

```bash
curl -sSLO https://raw.githubusercontent.com/redhat-developer/rhdh-operator/refs/heads/release-1.10/.rhdh/scripts/prepare-restricted-environment.sh
```

### Mirror to disk

```bash
bash prepare-restricted-environment.sh \
  --filter-versions "1.10" \
  --to-dir <my_pulled_image_location> \
  [--use-oc-mirror true]
```

### Install from disk (on disconnected host)

```bash
bash <my_pulled_image_location>/install.sh \
  --from-dir <my_pulled_image_location> \
  [--to-registry <my.registry.example.com>] \
  [--use-oc-mirror true]
```

If `oc-mirror` was used to mirror to disk, it must also be used to mirror from
disk.

### Update cluster pull secret (OCP)

```bash
oc get secret pull-secret -n openshift-config -o json | \
  jq -r '.data.".dockerconfigjson"' | base64 -d | \
  jq --arg registry "<mirror_registry>" \
     --arg auth "$(echo -n '<username>:<password>' | base64)" \
     '.auths[$registry] = {"auth": $auth}' | \
  oc set data secret/pull-secret -n openshift-config --from-file=.dockerconfigjson=/dev/stdin
```

Wait for all machine config pools to finish updating before proceeding.

### Create pull secret (Kubernetes)

```bash
kubectl create secret docker-registry rhdh-pull-secret \
  --docker-server=<mirror_registry> \
  --docker-username=<username> \
  --docker-password=<password> \
  --namespace=<target_namespace>

kubectl patch serviceaccount default \
  --namespace=<target_namespace> \
  --type='json' \
  --patch='[{"op":"add","path":"/imagePullSecrets/-","value":{"name":"rhdh-pull-secret"}}]'
```

### Plugin mirroring — export to disk

```bash
curl -sSLO https://raw.githubusercontent.com/redhat-developer/rhdh-operator/refs/heads/release-1.10/.rhdh/scripts/mirror-plugins.sh

bash mirror-plugins.sh \
  --plugin-index oci://registry.access.redhat.com/rhdh/plugin-catalog-index:1.10 \
  --to-dir <my_plugin_mirror_dir>
```

### Plugin mirroring — import from disk

```bash
bash mirror-plugins.sh \
  --from-dir <my_plugin_mirror_dir> \
  --to-registry <target_registry>
```

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

### Optional signature verification

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: rhdh-mirror-policy
data:
  policy.json: |
    {
      "transports": {
        "docker": {
          "<target_registry>/<namespace>": [
            {
              "type": "signedBy",
              "keyType": "GPGKeys",
              "keyPath": "<path_to_gpg_key>"
            }
          ]
        }
      }
    }
```

Mount in Backstage CR:
```yaml
        - name: rhdh-mirror-policy
          key: policy.json
          mountPath: /etc/containers
          containers:
            - install-dynamic-plugins
```

## 3. Operator — Partially Disconnected

Same script, but mirrors directly to registry:

```bash
bash prepare-restricted-environment.sh \
  --filter-versions "1.10" \
  [--to-registry <my.registry.example.com>] \
  [--use-oc-mirror true]
```

Plugin mirroring goes directly to registry:

```bash
bash mirror-plugins.sh \
  --plugin-index oci://registry.access.redhat.com/rhdh/plugin-catalog-index:1.10 \
  --to-registry <target_registry>
```

Same registries.conf and Backstage CR mount as fully disconnected.

## 4. Helm Chart — Fully Disconnected (OCP)

### ImageSetConfiguration

```yaml
apiVersion: mirror.openshift.io/v2alpha1
kind: ImageSetConfiguration
mirror:
  helm:
    repositories:
      - name: openshift-charts
        url: https://charts.openshift.io
        charts:
          - name: redhat-developer-hub
            version: "1.10"
```

### Mirror to disk

```bash
oc mirror --v2 -c <config_dir>/ImageSetConfiguration.yaml file://<archive_dir>/
```

Note: `--v2` flag required for OCP 4.21+.

### Mirror from disk to registry

```bash
oc mirror --v2 -c <config> --from file://<archive_dir> docker://<target_registry>
```

### Apply IDMS/ITMS manifests

```bash
oc apply -f <workspace>/working-dir/cluster-resources
```

### Deploy Helm chart

```bash
CLUSTER_ROUTER_BASE=$(oc get route console -n openshift-console -o=jsonpath='{.spec.host}' | sed 's/[.]*\.//')

helm install <instance> <workspace>/working-dir/helm/charts/<archive>.tgz \
  --namespace <namespace> --create-namespace \
  --set global.clusterRouterBase="$CLUSTER_ROUTER_BASE"
```

### Mount registries.conf in Helm values

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

**Important:** Because of Helm merge limitations, include all existing default
volumes, volume mounts, and init container fields from the chart alongside
additions. Omitting defaults overwrites them and can break deployment.

## 5. Helm Chart — Partially Disconnected (OCP)

Same ImageSetConfiguration; mirror directly to registry:

```bash
oc mirror --v2 --config=<config_dir>/ImageSetConfiguration.yaml docker://<target_registry>
```

Apply IDMS/ITMS, update pull secret, deploy Helm chart, mirror plugins same as
fully disconnected but without the disk transfer step.

## 6. Kubernetes Platforms (AKS, EKS, GKE) — Fully Disconnected

### Fetch Helm chart

```bash
helm repo add <repo_name> https://charts.openshift.io/
helm repo update
helm show values <repo_name>/redhat-developer-hub --version <version> > values.default.yaml
helm pull <repo_name>/redhat-developer-hub --version <version>
```

### Extract image digests

```bash
RHDH_IMAGE=$(yq '.upstream.backstage.image | .registry + "/" + .repository' values.default.yaml)
RHDH_DIGEST=$(yq '.upstream.backstage.image.tag' values.default.yaml)
PG_IMAGE=$(yq '.upstream.postgresql.image | .registry + "/" + .repository' values.default.yaml)
PG_DIGEST=$(yq '.upstream.postgresql.image.tag' values.default.yaml)
```

### Mirror images with skopeo

```bash
skopeo copy --all docker://${RHDH_IMAGE}:${RHDH_DIGEST} dir:./rhdh-hub
skopeo copy --all docker://${PG_IMAGE}:${PG_DIGEST} dir:./postgresql
```

### Load to air-gapped registry

```bash
skopeo copy --all dir:./rhdh-hub docker://<mirror_registry>/<rhdh_repo>:${RHDH_DIGEST}
skopeo copy --all dir:./postgresql docker://<mirror_registry>/<pg_repo>:${PG_DIGEST}
```

### values.yaml image overrides

```yaml
upstream:
  backstage:
    image:
      registry: "<mirror_registry>"
      repository: <rhdh_repo>
      tag: "${RHDH_DIGEST}"
  postgresql:
    image:
      registry: "<mirror_registry>"
      repository: <pg_repo>
      tag: "${PG_DIGEST}"
```

### Install

```bash
helm install rhdh ./<chart_archive>.tgz -f values.yaml
```

## 7. Critical Notes

- `ImageDigestMirrorSet` and `ImageContentSourcePolicy` do NOT apply to the
  `install-dynamic-plugins` init container because it uses `skopeo` directly.
- The `--v2` flag for `oc mirror` is required for OCP 4.21+.
- If `oc-mirror` was used to mirror to disk, it must also be used to mirror
  from disk (folder layout dependency).
- Plugin catalog index OCI reference: `oci://registry.access.redhat.com/rhdh/plugin-catalog-index:1.10`
- Wait for machine config pools to finish before proceeding after pull secret
  update.

## 8. Key Specifications

| Item | Value |
|------|-------|
| Backstage CR apiVersion | `rhdh.redhat.com/v1alpha5` |
| ImageSetConfiguration apiVersion | `mirror.openshift.io/v2alpha1` |
| Mirroring script branch | `release-1.10` |
| Plugin catalog index | `oci://registry.access.redhat.com/rhdh/plugin-catalog-index:1.10` |
| Minimum OCP for --v2 flag | 4.21 |
| Supported OCP versions | 4.18+ |
| registries.conf mount path | `/etc/containers/registries.conf.d` |
| policy.json mount path | `/etc/containers` |
