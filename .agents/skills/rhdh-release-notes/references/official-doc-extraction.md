# Official Doc Extraction

Use this extraction to keep RHDH 1.10 release note content grounded in official
Red Hat sources.

## Release Identity

- Product: Red Hat Developer Hub 1.10 (GA)
- Upstream: Backstage 1.49.4
- Runtime: Node.js 24
- Supported platforms: OCP 4.21, Kubernetes 1.34

## New Features and Enhancements (Chapter 1)

### Developer Lightspeed for RHDH

- Available as default plugin on Operator and Helm chart deployments.
- Installed but unavailable until LLM is configured by platform engineer.
- Opt out via `lightspeed` flavour exclusion (Operator) or `enabled` toggle
  (Helm).
- MCP servers manageable from chat interface: administrators define servers in
  `app-config.yaml`; users toggle servers and manage tokens via settings panel.
- Tokens encrypted at rest with AES-256-GCM when `backend.auth.keys` is
  configured; supports key rotation and automatic legacy token migration.
- Permissions: `lightspeed.mcp.read` (view), `lightspeed.mcp.manage` (toggle
  and manage tokens).
- Uses 1.9 RAG embeddings; 1.10 embeddings in a future update.

### Scaffolder MCP Tools

Additional Scaffolder capabilities exposed as MCP tools through
`scaffolder` and `scaffolder-mcp-extras` plugins. Enables discovery, validation,
execution, and task monitoring via MCP.

### Personalized Homepages

Create persona-specific homepages for different user groups. Attach homepages to
Backstage or RBAC groups; configure layouts with dynamic plugins. Visibility
rules control access.

### Default RBAC Role

Administrators configure default RBAC role and baseline permissions for all
authenticated users via `permission.rbac.defaultPermissions` in
`app-config.yaml`. Removes need for manual `all-employee` groups.

### PingFederate Authentication

PingFederate available as sign-in provider. User resolved to organization data
in software catalog. Enabled by user and group provisioning with LDAP catalog
provider plugin.

### Flavor-Based Operator Configuration

v1alpha5 API introduces `spec.flavours[]` array in Backstage CR. Supports
multiple ConfigMaps in single YAML for default configuration. New
`rhdh.redhat.com/sub-path` annotation controls volume mount behavior.

### New Frontend System (NFS)

NFS support added to Red Hat GA frontend plugins: Adoption Insights, Bulk
Import, Extensions, Scorecard, RBAC, Orchestrator, Global Header, and others.

Enable with:
- `APP_CONFIG_app_packageName=app-next`
- `ENABLE_STANDARD_MODULE_FEDERATION=true`

Core UI features (Homepage, Analytics Provider, Theme, Translation) migrated
to load as dynamic plugins. Global Header and Drawer migrated to Blueprints.

### Scorecard Enhancements

- File-level compliance checks for repository files (LICENSE, CODEOWNERS,
  Dockerfile, .gitignore). Fully configurable paths and names.
- Customized aggregated metric cards with `average` aggregation type
  (normalized 0-100 percentage score).
- Aggregated KPI cards show last-updated timestamps; navigate to contributing
  entities; sort and paginate per-entity values.

### Bulk Import

- Repository list scoped to signed-in user via SCM OAuth.
- Hides already-imported repositories.
- Preserves selected approval tool (GitHub/GitLab) across page refreshes.
- Requires GitHub and GitLab OAuth for repository listing.

### Orchestrator

- Loki backend module GA for centralized workflow log aggregation (`AUTH_TOKEN`
  required).
- Retry configuration for widgets: retry count, initial delay, backoff
  multiplier, status code triggers.
- Custom review page via `getReviewComponent()` on `OrchestratorFormApi`.
- `ReviewComponentProps` and shared helpers in `orchestrator-form-react`.

### Single Database Deployments

`pluginDivisionMode: schema` enables schema-based plugin isolation within a
single PostgreSQL database. Schemas auto-created when `ensureExists` defaults to
`true`. DB user needs `CREATE SCHEMA` privileges.

### Dynamic Plugin Factory

- Multi-workspace builds supported.
- `plugins-list.yaml` auto-generation for common scenarios.
- `--clean` argument for reusing mounted workspaces.
- Git repository references via CLI for single repository cases.

### Localization

Spanish and German language available across portal and core plugins.

### Other Enhancements

- Browser tab displays Scaffolder template title.
- Human-readable entity titles in Adoption Insights "Top 3" widgets.
- Improved entity types documentation (mandatory fields, tabs, conditional UI).
- Helm Chart and Operator deployment comparison table.
- Cloud events to Kafka for workflow triggers.
- Updated session expiration documentation.

## Technology Preview Features (Chapter 2)

- **Scorecard Dependabot and OpenSSF integrations**: security compliance
  reporting with visual summary.
- **RHDH must-gather**: promoted from Developer Preview to Technology Preview.
  Collects diagnostic data for support case troubleshooting.

## Developer Preview Features (Chapter 3)

- **Personal AI Notebooks**: isolated RAG-based workspaces for project-specific
  documentation (PDF, Markdown, .docx). Known issues with large PDF upload
  speed, duplicate entries, and incomplete document search.
- **Backstage MCP tools**: available by default with `rhdh-mcp-extras` overlay
  plugins for advanced catalog filters and Scaffolder actions.
- **Customizable Scorecard severity levels**: custom severity states, color
  mappings (hex, theme variables, RGB), and icon assignments.
- **Developer Lightspeed evaluation framework**: QA datasets and evaluation
  result reports for model selection.

## Deprecated Features (Chapter 4)

- **Global Floating Action Button**: disabled by default; use Global Header.
- **Community auth providers**: Atlassian, Auth0, Azure-easyauth, Bitbucket,
  Bitbucket Server, Cloudflare Access, Google, Google IAP, OAuth 2 Custom
  Proxy, OneLogin, Okta will move to dynamic plugins in a future release.
- **backstage-community-plugin-acr**: moved to Community support; use `oci://`
  reference.

## Removed Features (Chapter 5)

- **OCM plugin**: removed entirely.
- **Operator resource deletion**: no longer auto-deletes user-created resources
  when features disabled in CR.
- **Plugins downgraded to Community support** (removed as embedded wrappers):
  - `backstage-community-plugin-quay`
  - `backstage-community-plugin-scaffolder-backend-module-quay-dynamic`
  - `backstage-community-plugin-tekton`
  - `roadiehq-scaffolder-backend-argocd-dynamic`
  - `roadie-backstage-plugins/plugins/scaffolder-actions/scaffolder-backend-argocd`
  Use `oci://` path references to continue using these plugins.

## Known Issues (Chapter 6)

1. **Orchestrator in-place upgrade failure**: `Job.batch` immutable
   `spec.template` error. Workaround: delete completed Job, re-run upgrade.
2. **OCI images from registry.access.redhat.com**: fail plugin path
   auto-detection. Workaround: use digest or append `!path` suffix.
3. **Custom thresholds unavailable** for Filecheck, Openssf, Dependabot
   Scorecard modules.
4. **Label casing mismatch** in HAS_LABEL RBAC policies causes search
   mismatch. Workaround: standardize label casing.
5. **Bulk Import**: repos with open PRs incorrectly marked as already imported.

## Fixed Issues (Chapter 7)

### Fixed in 1.10.1

- Outdated RAG content image causing installation failure (corrected image
  reference).

### Fixed in 1.10.0 (Selected Highlights)

- Grid layout broken with quick-access panel.
- Keycloak nested subgroups missing on Keycloak 26.4.0+.
- Topology toolbar missing translations.
- Deprecated `janus-idp` template references replaced with `rhdh`.
- Notifications page title not translated.
- `default-config/dynamic-plugins.yaml` includes now disableable with empty
  `includes: []`.
- External PostgreSQL connection documentation.
- `registries.conf` for transparent plugin mirroring.
- Deprecated `backend.auth.keys` removed, replaced by static token.
- Developer Lightspeed overlay layout and scroll fixes.
- `additionalImages` indentation fix for `oc-mirror`.
- Event timestamps stored in UTC.
- `ui:hidden` fields no longer leave empty space.
- Multi-step workflow validation limited to active step.
- Lightspeed Tool Call and Thinking sections display correctly.
- Backstage CR `Deployed` status condition reports correct value.
- Heap dump collection no longer stuck in `must-gather`.
- JSON Schema defaults applied to initial form state.
- Operator `spec.deployment.patch` ordering with
  `rhdh.redhat.com/deployment-patch-list-merge-mode: prepend`.
- Operator reconciliation loop no longer causes unnecessary pod restarts
  (sorted map keys).
- `ENABLE_CACHE_LABEL_FILTER` environment variable support.
- `ActiveMultiSelect` `clearOnRetrigger` replaces values correctly.
- Template expression support for `fetch:response` fields.
- Developer Lightspeed RAG Sources section displayed.
- Air-gapped plugin installation docs for Operator.
- Quick Access card customization docs.
- Sidebar color no longer impacts plugin UI backgrounds.
- Numbered pointer messages no longer split in Lightspeed.
- Duplicate workflows with shared IDs fixed.

## Security Fixes (Chapter 8)

- RHDH 1.10.0: RHSA-2026:24841
