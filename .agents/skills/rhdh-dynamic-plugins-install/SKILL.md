---
name: rhdh-dynamic-plugins-install
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "rhdh"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Developer Hub"
description: >
  Use when installing and viewing plugins in Red Hat Developer Hub 1.10,
  including Operator-based and Helm-based dynamic plugin installation, OCI
  registry configuration, custom certificates, air-gapped mirroring,
  dependency management, custom plugin export/packaging/loading, front-end
  wiring, Extensions UI management, and troubleshooting pod startup failures.
  Do NOT use for developing new plugins from scratch (use
  rhdh-dynamic-plugins-develop) or for using already-installed plugins (use
  rhdh-dynamic-plugins-usage).
---

# RHDH Dynamic Plugins: Install and View

Use this skill to install, configure, and view dynamic plugins in Red Hat
Developer Hub 1.10.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority. This skill covers Operator and Helm
plugin installation, OCI/TGZ/NPM plugin loading, custom certificates,
air-gapped mirroring, dependency management, custom plugin export and
packaging, front-end wiring, Extensions UI, and troubleshooting.

## Installation Methods

### Operator-Based

Store plugin config in a ConfigMap (`dynamic-plugins.yaml` key) and reference
it from the Backstage CR via `spec.application.dynamicPluginsConfigMapName`.
The CR `apiVersion` is `rhdh.redhat.com/v1alpha5`, kind `Backstage`.

### Helm-Based

Use `global.dynamic.plugins` in Helm values. Plugin merging: main values
override `includes` file entries for matching packages.

See `references/official-doc-extraction.md` for full YAML examples of both
methods.

## Plugin Loading Formats

| Format | `package` value | Integrity required |
|--------|----------------|-------------------|
| OCI image | `oci://quay.io/example/image:v1.0.0` | No (digest optional) |
| OCI digest | `oci://quay.io/example/image@sha256:...` | Implicit |
| TGZ | `https://example.com/plugin-1.0.0.tgz` | Yes (`integrity:`) |
| NPM | `@example/plugin@1.0.0` | Yes (`integrity:`) |
| Local dir | `./dynamic-plugins/dist/plugin-name` | No |

Version inheritance from base config: use `{{inherit}}` placeholder.

## Plugin Dependencies

Dependencies are Kubernetes resources created alongside the Backstage CR:

- Cluster-level: manifests in `/config/profile/{PROFILE}/plugin-deps/`
- Infrastructure: `/config/profile/{PROFILE}/plugin-infra/` (use
  `make plugin-infra` with caution)
- Referenced via `dependencies[].ref` in plugin configuration

## Air-Gapped / Disconnected Environments

- **NPM registry** — create `.npmrc` Secret, mount into
  `install-dynamic-plugins` init container via `extraFiles.secrets`
- **OCI mirroring** — use `mirror-plugins.sh` script with `--plugin-index`,
  `--to-registry`, `--to-dir`/`--from-dir` for two-phase disconnect

See `references/official-doc-extraction.md` for full YAML and commands.

## Custom Certificates for OCI Registries

Three approaches:
1. **Per-registry TLS** — mount CA cert ConfigMap at
   `/etc/containers/certs.d/<registry>:<port>`
2. **CA bundle** — mount at `/etc/pki/tls/certs/`
3. **OpenShift cluster-wide** — use `config.openshift.io/inject-trusted-cabundle`
   label on empty ConfigMap, mount at `/etc/pki/ca-trust/extracted/pem`

## Extensions UI (Tech Preview)

- View available plugins: Administration > Extensions > Catalog
- View installed plugins: Administration > Extensions > Installed
- Search by name, filter by category/author/support
- Install plugins (Developer Preview, development environments only)
- RBAC permissions: `extensions.install.create`, `extensions.install.read`

## Front-End Plugin Wiring

Key configuration sections under `pluginConfig.dynamicPlugins.frontend`:

- `dynamicRoutes` — pages and sidebar menu items
- `mountPoints` — inject components into entity pages
- `entityTabs` — add/customize entity view tabs
- `appIcons` — register custom icons
- `menuItems` — sidebar navigation
- `routeBindings` — link routes between plugins
- `apiFactories` — custom utility API implementations
- `scaffolderFieldExtensions` — Scaffolder custom fields
- `techdocsAddons` — TechDocs add-ons
- `translationResources` — localization overrides

## Enabling Pre-Installed Plugins

Since RHDH 1.10, `dynamic-plugins.default.yaml` exists in the plugin catalog
index image. Retrieve with:

```bash
unpack registry.access.redhat.com/rhdh/plugin-catalog-index:1.10 \
  dynamic-plugins.default.yaml
```

Or use `{{inherit}}` tag for automatic version resolution:

```yaml
plugins:
  - package: oci://registry.access.redhat.com/rhdh/backstage-community-plugin-analytics-provider-segment:{{inherit}}
    disabled: false
```

## Troubleshooting Pod Startup

If RHDH pod fails after enabling a plugin, check logs for missing env vars:

```bash
oc logs -c install-dynamic-plugins deploy/backstage-my-rhdh
```

Set missing variables via a Secret mounted with `extraEnvs.secrets` (Operator)
or `extraEnvVarsSecrets` (Helm).

## Verification

```bash
# Loaded plugins API
curl <RHDH_URL>/api/dynamic-plugins-info/loaded-plugins | jq .

# Init container logs
oc logs -c install-dynamic-plugins deploy/backstage-<name>
```

## Related Skills

- `rhdh-dynamic-plugins-develop` — developing custom dynamic plugins
- `rhdh-dynamic-plugins-usage` — using installed plugins

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
