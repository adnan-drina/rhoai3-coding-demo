---
name: rhdh-dynamic-plugins-develop
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "rhdh"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Developer Hub"
description: >
  Use when developing and deploying custom dynamic plugins for Red Hat Developer
  Hub 1.10, from development environment setup through plugin creation,
  conversion, packaging, deployment, and local verification with RHDH Local.
  Do NOT use for installing pre-built or shipped plugins (use
  rhdh-dynamic-plugins-install) or for using already-installed plugins (use
  rhdh-dynamic-plugins-usage).
---

# RHDH Dynamic Plugins: Develop and Deploy

Use this skill to develop, convert, package, and deploy custom dynamic plugins
for Red Hat Developer Hub 1.10.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority. This skill covers the full plugin
development lifecycle: environment setup, plugin creation, implementation,
local testing, front-end wiring, conversion to dynamic format, OCI/TGZ/NPM
packaging, and RHDH Local verification.

## Key Concepts

1. **Dynamic plugin system** — RHDH loads plugins at runtime from NPM, tarballs,
   or OCI container images via `dynamic-plugins.yaml`. No application rebuild
   needed; only a restart.
2. **RHDH compatibility matrix** — RHDH 1.10 maps to Backstage 1.49.1 and
   `create-app` version 0.8.1. Plugins must use compatible Backstage versions.
3. **Development toolchain** — Node.js v22 (via NVM), Yarn 4, Docker/Podman,
   and `@red-hat-developer-hub/cli` (`rhdh-cli`).
4. **Plugin types** — frontend-plugin, backend-plugin, backend-plugin-module,
   plugin-web-library, plugin-node-library, plugin-common-library.
5. **Dynamic export** — `npx @red-hat-developer-hub/cli@latest plugin export`
   converts standard Backstage plugins into the dynamic plugin format,
   producing `dist-dynamic/` with `dist-scalprum/` (frontend) or bundled
   backend code.
6. **Packaging formats** — OCI image (recommended), TGZ file, or JavaScript
   package (private NPM registry only).
7. **RHDH Local** — Local testing environment that reads
   `dynamic-plugins.override.yaml` and mounts `local-plugins/` directory.

## Development Workflow

1. **Create workspace** — `npx @backstage/create-app@0.8.1 --path .`
2. **Create plugin** — `yarn new` (select frontend-plugin or backend-plugin)
3. **Implement components** — React components, entity cards, pages in
   `src/components/`; register in `src/plugin.ts` and export from `src/index.ts`
4. **Test locally** — `yarn start` in plugin directory, or use RHDH Local with
   `dist-dynamic/` copied to `local-plugins/`
5. **Configure front-end wiring** — `dynamic-plugins.yaml` with
   `dynamicRoutes`, `mountPoints`, `appIcons`, `menuItem` entries
6. **Convert to dynamic** — `npx @red-hat-developer-hub/cli@latest plugin export`
7. **Package as OCI** —
   `npx @red-hat-developer-hub/cli@latest plugin package --tag <registry>/<image>:<tag>`
8. **Push to registry** — `podman push <registry>/<image>:<tag>`
9. **Deploy to RHDH** — Add `oci://<registry>/<image>:<tag>` to
   `dynamic-plugins.yaml` and restart

## Front-End Wiring

Frontend plugins require `pluginConfig.dynamicPlugins.frontend` in
`dynamic-plugins.yaml`:

- `dynamicRoutes` — register pages with sidebar menu items
- `mountPoints` — inject components into entity pages (e.g.,
  `entity.page.overview/cards`)
- `appIcons` — register custom icons
- `menuItem` — sidebar navigation entries

The `importName` must match the export name in `src/index.ts`.

## Backend Plugin Export

Backend plugins must be compatible with the new Backstage backend system
(`createBackendPlugin()` / `createBackendModule()`). Key flags:

- `--shared-package` — mark dependencies provided by RHDH (default:
  `@backstage` scoped); use `!` prefix for exceptions
- `--embed-package` — bundle specific workspace packages (default: `-node`
  and `-common` suffix packages)

## Plugin Packaging

| Format | Command | Notes |
|--------|---------|-------|
| OCI image | `rhdh-cli plugin package --tag` | Recommended; push with podman/docker |
| TGZ | `npm pack` from `dist-dynamic/` | Host on HTTP server; include `integrity` hash |
| NPM | `npm publish --registry` | Private registry only |

## RHDH Local Verification

1. Export plugin: `npx @red-hat-developer-hub/cli@latest plugin export`
2. Copy `dist-dynamic/` to `<RHDH_LOCAL>/local-plugins/<plugin-name>/`
3. Configure in `dynamic-plugins.override.yaml`
4. Restart RHDH Local

## Dynamic Plugin Factory

The RHDH Dynamic Plugin Factory automates conversion and packaging of standard
Backstage plugins. Red Hat maintains it as open source but does not support it
under any SLA.

## Validation

```bash
# Check loaded plugins
curl <RHDH_URL>/api/dynamic-plugins-info/loaded-plugins | jq .

# Verify plugin appears in Extensions UI
# Administration > Extensions > Installed tab
```

## Related Skills

- `rhdh-dynamic-plugins-install` — installing and viewing plugins
- `rhdh-dynamic-plugins-usage` — using installed plugins

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
