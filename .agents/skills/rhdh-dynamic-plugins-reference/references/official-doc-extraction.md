# Current Verified Guidance — Developer Hub 1.10

Reviewed 2026-10-13 in the public Red Hat documentation browser. Sources:

- https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/dynamic_plugins_reference/index
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

This extraction is derived from the official RHDH 1.10 guide captured in
`source-capture.md`.

## Dynamic Plugin Architecture

Dynamic plugin support is based on the backend plugin manager package, which
scans a configured root directory (`dynamicPlugins.rootDirectory` in app
config) for dynamic plugin packages and loads them dynamically.

Plugins can be consumed from:
- preinstalled packages inside the RHDH container image
- external OCI artifacts from `ghcr.io` or `registry.access.redhat.com`
- NPM packages from a public registry

## Preinstalled Dynamic Plugins

15 preinstalled dynamic plugins are enabled by default in RHDH 1.10:

- `@backstage-community/plugin-analytics-provider-segment`
- `@backstage-community/plugin-scaffolder-backend-module-regex`
- `@backstage/plugin-techdocs-backend`
- `@backstage/plugin-techdocs-module-addons-contrib`
- `@backstage/plugin-techdocs`
- `@red-hat-developer-hub/backstage-plugin-adoption-insights-backend`
- `@red-hat-developer-hub/backstage-plugin-adoption-insights`
- `@red-hat-developer-hub/backstage-plugin-analytics-module-adoption-insights`
- `@red-hat-developer-hub/backstage-plugin-catalog-backend-module-extensions`
- `@red-hat-developer-hub/backstage-plugin-dynamic-home-page`
- `@red-hat-developer-hub/backstage-plugin-extensions-backend`
- `@red-hat-developer-hub/backstage-plugin-extensions`
- `@red-hat-developer-hub/backstage-plugin-global-floating-action-button`
- `@red-hat-developer-hub/backstage-plugin-global-header`
- `@red-hat-developer-hub/backstage-plugin-quickstart`

Plugins requiring custom configuration are disabled by default. To enable a
disabled preinstalled plugin:

```yaml
global:
  dynamic:
    includes:
      - dynamic-plugins.default.yaml
    plugins:
      - package: ./dynamic-plugins/dist/<plugin-dist-name>
        disabled: false
```

Default configuration comes from `dynamic-plugins.default.yaml`; use
`pluginConfig` to override defaults.

## Red Hat GA Plugins

35 GA plugins with full Red Hat support. Key examples:

| Name | Version | Path pattern |
|------|---------|-------------|
| Adoption Insights | 0.8.2 | `./dynamic-plugins/dist/red-hat-developer-hub-backstage-plugin-adoption-insights` |
| GitHub (catalog) | 0.13.0 | `./dynamic-plugins/dist/backstage-plugin-catalog-backend-module-github-dynamic` |
| GitHub (scaffolder) | 0.9.7 | `./dynamic-plugins/dist/backstage-plugin-scaffolder-backend-module-github-dynamic` |
| GitLab (catalog) | 0.8.1 | `./dynamic-plugins/dist/backstage-plugin-catalog-backend-module-gitlab-dynamic` |
| Keycloak | 3.19.2 | `./dynamic-plugins/dist/backstage-community-plugin-catalog-backend-module-keycloak-dynamic` |
| Kubernetes (backend) | 0.21.2 | `./dynamic-plugins/dist/backstage-plugin-kubernetes-backend-dynamic` |
| Lightspeed | 2.8.5 | `oci://registry.access.redhat.com/rhdh/red-hat-developer-hub-backstage-plugin-lightspeed@sha256:...` |
| Orchestrator | 5.7.12 / 8.9.4 | `oci://registry.access.redhat.com/rhdh/...` |
| RBAC | 1.52.4 | `./dynamic-plugins/dist/backstage-community-plugin-rbac` |
| TechDocs | 1.17.2 / 2.1.6 | `./dynamic-plugins/dist/backstage-plugin-techdocs` / `backstage-plugin-techdocs-backend-dynamic` |
| Topology | 2.12.3 | `./dynamic-plugins/dist/backstage-community-plugin-topology` |

## Red Hat Technology Preview Plugins

16 Technology Preview plugins. TP features are not supported with Red Hat
production SLAs. Key examples:

| Name | Version | Path pattern |
|------|---------|-------------|
| Bulk Import (frontend + backend) | 7.3.5 | `./dynamic-plugins/dist/red-hat-developer-hub-backstage-plugin-bulk-import*` |
| Events Backend Module GitHub | 0.4.10 | `oci://registry.access.redhat.com/rhdh/backstage-plugin-events-backend-module-github@sha256:...` |
| Extensions (frontend + backend + catalog) | 0.17.1 | `./dynamic-plugins/dist/red-hat-developer-hub-backstage-plugin-extensions*` |
| Kubernetes (frontend) | 0.12.17 | `./dynamic-plugins/dist/backstage-plugin-kubernetes` |
| Notifications (frontend + backend + email) | varies | `./dynamic-plugins/dist/backstage-plugin-notifications*` |

## Community-Supported Plugins

44 community-supported plugins served from `ghcr.io`. These use the OCI path
pattern:

```text
oci://ghcr.io/redhat-developer/rhdh-plugin-export-overlays/<plugin-name>:<tag>
```

Key examples include ArgoCD, Azure DevOps, Datadog, GitHub Actions/Issues/PRs,
GitLab, Jenkins, Jira, JFrog Artifactory, Nexus Repository Manager,
PagerDuty, Quay, ServiceNow, SonarQube, and Tekton.

## Plugin Versioning

The `<tag>` format for community plugins is:

```text
bs_<backstage-version>__<plugin-version>
```

Double underscore delimiter between Backstage version and plugin version. Find
the Backstage version in the RHDH release notes preface.

### SHA256 Digest Determination

For environment stability, use a SHA256 digest instead of a version tag:

```bash
skopeo inspect docker://<plugin-path>:<tag> | jq '.Digest'
```

Or look up digests in the RHDH Plugin Export Overlays GitHub repository.

## Other Installable Plugins

3 Technology Preview plugins not preinstalled, requiring external installation:

| Name | Plugin | Version |
|------|--------|---------|
| Ansible Automation Platform Frontend | `@ansible/plugin-backstage-rhaap` | 1.0.0 |
| Ansible Automation Platform Backend | `@ansible/plugin-backstage-rhaap-backend` | 1.0.0 |
| Ansible Automation Platform Scaffolder | `@ansible/plugin-scaffolder-backend-module-backstage-rhaap` | 1.0.0 |

## Deprecated Plugins

Earlier extraction claim superseded: several embedded wrappers are removed in
1.10. See the verified current packaging decisions above.

## Troubleshooting

Plugin not loading checks:
1. Verify the `ghcr.io` path is correct and the image tag or digest exists.
2. Confirm the cluster has network access to `ghcr.io`.
3. Review Developer Hub logs for OCI pull errors.
