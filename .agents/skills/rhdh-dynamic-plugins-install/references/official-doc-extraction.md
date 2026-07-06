# Official Documentation Extraction

Source: Red Hat Developer Hub 1.10 — Installing and viewing plugins
Captured: 2026-07-06

---

## 1. Operator-Based Plugin Installation

### ConfigMap for Dynamic Plugins

```yaml
kind: ConfigMap
apiVersion: v1
metadata:
  name: dynamic-plugins-rhdh
data:
  dynamic-plugins.yaml: |
    includes:
      - dynamic-plugins.default.yaml
    plugins:
      - package: './dynamic-plugins/dist/backstage-plugin-catalog-backend-module-github-dynamic'
        disabled: false
        pluginConfig:
          catalog:
            providers:
              github:
                organization: "${GITHUB_ORG}"
                schedule:
                  frequency: { minutes: 1 }
                  timeout: { minutes: 1 }
                  initialDelay: { seconds: 100 }
```

### Backstage CR Reference

```yaml
apiVersion: rhdh.redhat.com/v1alpha5
kind: Backstage
metadata:
  name: my-rhdh
spec:
  application:
    dynamicPluginsConfigMapName: dynamic-plugins-rhdh
```

### Verification

```bash
curl <RHDH_URL>/api/dynamic-plugins-info/loaded-plugins
```

## 2. Helm-Based Plugin Installation

```yaml
global:
  dynamic:
    includes:
      - dynamic-plugins.default.yaml
    plugins:
      - package: <package-spec>
        disabled: false
        pluginConfig: ...
```

### Enable/Disable Patterns

```yaml
# Disable a plugin from included file
plugins:
  - package: <plugin-from-default-yaml>
    disabled: true

# Enable a disabled plugin
plugins:
  - package: <disabled-plugin-from-default-yaml>
    disabled: false
```

## 3. Plugin Dependencies

### Cluster-Level Configuration

Place Kubernetes manifests in `/config/profile/{PROFILE}/plugin-deps/`:

```yaml
# kustomization.yaml
configMapGenerator:
  - files:
      - plugin-deps/example-dep1.yaml
      - plugin-deps/example-dep2.yaml
    name: plugin-deps
```

Reference in plugin config:

```yaml
plugins:
  - disabled: false
    package: "path-or-url-to-example-plugin"
    dependencies:
      - ref: example-dep
```

Placeholders `{{backstage-name}}` and `{{backstage-ns}}` are replaced by the
Operator with the Backstage CR name and namespace.

## 4. Air-Gapped Installation

### NPM Registry Secret (Operator)

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: dynamic-plugins-npmrc
type: Opaque
stringData:
  .npmrc: |
    registry=https://<your_internal_registry>
    //<your_internal_registry>:_authToken=<your_auth_token>
```

Mount in Backstage CR:

```yaml
apiVersion: rhdh.redhat.com/v1alpha5
kind: Backstage
metadata:
  name: my-rhdh
spec:
  application:
    extraFiles:
      secrets:
        - name: dynamic-plugins-npmrc
          mountPath: /opt/app-root/src/.npmrc.dynamic-plugins
          containers:
            - install-dynamic-plugins
```

Verify:

```bash
oc logs -c install-dynamic-plugins deploy/backstage-my-rhdh
```

### NPM Registry Secret (Helm)

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: <release_name>-dynamic-plugins-npmrc
type: Opaque
stringData:
  .npmrc: |
    registry=<registry_link>
    //<registry_link>:_authToken=<auth_token>
```

## 5. OCI Plugin Mirroring (Disconnected)

Script: `mirror-plugins.sh` from
`https://raw.githubusercontent.com/redhat-developer/rhdh-operator/refs/heads/release-1.10/.rhdh/scripts/mirror-plugins.sh`

Prerequisites: Skopeo >= 1.20, tar >= 1.35, jq >= 1.7, Podman >= 5.6.

### Partial Disconnect

```bash
bash mirror-plugins.sh \
  --plugin-index oci://registry.access.redhat.com/rhdh/plugin-catalog-index:1.10 \
  --to-registry <target_registry>
```

### Full Disconnect (Two-Phase)

```bash
# Phase 1: Export
bash mirror-plugins.sh \
  --plugin-index oci://registry.access.redhat.com/rhdh/plugin-catalog-index:1.10 \
  --to-dir <my_plugin_mirror_dir>

# Phase 2: Import
bash mirror-plugins.sh \
  --from-dir <my_plugin_mirror_dir> \
  --to-registry <target_registry>
```

### Specific Plugins

```bash
bash mirror-plugins.sh \
  --plugins oci://quay.io/rhdh-plugin-catalog/backstage-community-plugin-quay:<tag> \
  --to-registry <target_registry>
```

### From File

```bash
bash mirror-plugins.sh \
  --plugin-list plugins.txt \
  --to-registry <target_registry>
```

Output: `rhdh-plugin-mirroring-summary.txt` with mappings.

## 6. Custom Certificates for OCI Registries

### Per-Registry TLS (Operator)

```yaml
spec:
  application:
    extraFiles:
      configMaps:
        - name: registry-ca-crt
          mountPath: '/etc/containers/certs.d/reg.example.com:5000'
          containers:
            - install-dynamic-plugins
```

### CA Bundle (Operator)

```yaml
spec:
  application:
    extraFiles:
      configMaps:
        - name: registry-ca-bundle
          mountPath: /etc/pki/tls/certs/
          containers:
            - install-dynamic-plugins
```

### OpenShift Cluster-Wide Trusted CA

Create empty ConfigMap with label:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: trusted-ca
  labels:
    config.openshift.io/inject-trusted-cabundle: "true"
```

Mount at `/etc/pki/ca-trust/extracted/pem` in init container.

## 7. Custom Plugin Export and Packaging

### Export (rhdh-cli)

```bash
npx @red-hat-developer-hub/cli@latest plugin export
```

Backend: `--shared-package` and `--embed-package` flags control dependency
bundling.

Frontend: auto-generates Scalprum configuration.

### OCI Packaging

```bash
npx @red-hat-developer-hub/cli@latest plugin package \
  --tag quay.io/example/image:v0.0.1
podman push quay.io/example/image:v0.0.1
```

### TGZ Packaging

```bash
npm pack
# Reference with integrity hash in dynamic-plugins.yaml
```

### JavaScript Package

```bash
npm publish --registry <npm_registry_url>
# Private registry only
```

## 8. Loading Plugins

### OCI Image

```yaml
plugins:
  - disabled: false
    package: oci://quay.io/example/image:v1.0.0
```

For private registries, create pull secret:
- Operator: `dynamic-plugins-registry-auth`
- Helm: `<release_name>-dynamic-plugins-registry-auth`

### Version Inheritance

```yaml
includes:
  - dynamic-plugins.default.yaml
plugins:
  - disabled: false
    package: oci://quay.io/example/image:{{inherit}}
```

### TGZ

```yaml
plugins:
  - disabled: false
    package: https://example.com/plugin-1.0.0.tgz
    integrity: sha512-<hash>
```

### JavaScript Package

```yaml
plugins:
  - disabled: false
    package: @example/plugin@1.0.0
    integrity: sha512-<hash>
```

## 9. Enabling Pre-Installed Plugins

Since RHDH 1.10, `dynamic-plugins.default.yaml` is in the plugin catalog index
image (`registry.access.redhat.com/rhdh/plugin-catalog-index:1.10`).

```yaml
plugins:
  - package: oci://registry.access.redhat.com/rhdh/backstage-community-plugin-analytics-provider-segment:{{inherit}}
    disabled: false
```

## 10. Extensions UI (Technology Preview)

- View: Administration > Extensions
- Catalog tab: available plugins
- Installed tab: currently loaded plugins
- Search/filter by name, category, author, support type

### Disable Extensions

```yaml
plugins:
  - package: ./dynamic-plugins/dist/red-hat-developer-hub-backstage-plugin-extensions
    disabled: true
  - package: ./dynamic-plugins/dist/red-hat-developer-hub-backstage-plugin-catalog-backend-module-extensions-dynamic
    disabled: true
  - package: ./dynamic-plugins/dist/red-hat-developer-hub-backstage-plugin-extensions-backend-dynamic
    disabled: true
```

## 11. Developer Preview: Install via Extensions UI

Development environment only (`NODE_ENV=development`). Requires PVC named
`dynamic-plugins-root` for persistence.

Operator CR setup:

```yaml
apiVersion: rhdh.redhat.com/v1alpha5
kind: Backstage
spec:
  application:
    dynamicPluginsConfigMapName: dynamic-plugins-rhdh
    extraEnvs:
      envs:
        - name: NODE_ENV
          value: "development"
```

RBAC permissions for Extensions: `extensions.install.create`,
`extensions.install.read`.

## 12. Front-End Plugin Wiring

### Dynamic Routes

```yaml
dynamicRoutes:
  - path: /my-new-page
    importName: MyPluginPage
    menuItem:
      icon: favorite
      text: My Custom Page
```

### Mount Points

```yaml
mountPoints:
  - mountPoint: entity.page.overview/cards
    importName: ExampleCard
    config:
      layout:
        gridColumnEnd: 'span 4'
      if:
        allOf:
          - isKind: component
```

### Entity Tabs

```yaml
entityTabs:
  - mountPoint: entity.page.feedback
    path: /feedback
    title: Feedback
```

### Wiring Scenarios

| Scenario | Config key |
|----------|-----------|
| New pages/routes | `dynamicRoutes` |
| Extend entity pages | `mountPoints` |
| Sidebar navigation | `dynamicRoutes.menuItem`, `menuItems` |
| Custom icons/themes | `appIcons`, `themes` |
| Entity tabs | `entityTabs` |
| Route bindings | `routeBindings` |
| Custom APIs | `apiFactories` |
| Scaffolder fields | `scaffolderFieldExtensions` |
| TechDocs add-ons | `techdocsAddons` |
| Translations | `translationResources` |

## 13. Troubleshooting Pod Startup

Error pattern:

```
Plugin '<NAME>' startup failed; caused by Error: Missing required config
value at '<variable>' in 'app-config.local.yaml'
```

Fix: create Secret with missing env vars and mount via `extraEnvs.secrets`
(Operator) or `extraEnvVarsSecrets` (Helm).

```yaml
# Operator
spec:
  application:
    extraEnvs:
      secrets:
        - name: rhdh-secrets

# Helm
upstream:
  backstage:
    extraEnvVarsSecrets:
      - rhdh-secrets
```
