# Official Documentation Extraction

Source: Red Hat Developer Hub 1.10 — Develop and deploy dynamic plugins
Captured: 2026-07-06

---

## 1. Dynamic Plugin System

RHDH implements a dynamic plugin system that loads plugins at runtime from NPM,
tarballs, or OCI container images. Plugins are specified in
`dynamic-plugins.yaml`:

```yaml
plugins:
  - package: oci://quay.io/account-name/image-name:tag
    disabled: false
    pluginConfig: {}
```

## 2. RHDH Compatibility Matrix

| RHDH version | Backstage version | create-app version |
|---|---|---|
| 1.10 | 1.49.1 | 0.8.1 |
| 1.9 | 1.45.3 | 0.7.6 |
| 1.8 | 1.42.5 | 0.7.3 |
| 1.7 | 1.39.1 | 0.6.2 |

## 3. Development Toolchain

- **Node.js v22** via NVM
- **Yarn 4** for workspace and dependency management
- **Docker or Podman** for OCI image packaging
- **rhdh-cli** (`@red-hat-developer-hub/cli`) for `export-dynamic-plugin`
  and `plugin package` commands
- **RHDH Plugin Factory** (open source, not supported under SLA)

## 4. Create a Backstage Application

```bash
mkdir rhdh-plugin-dev && cd rhdh-plugin-dev
npx @backstage/create-app@0.8.1 --path .
```

Expected workspace structure: `packages/app/`, `packages/backend/`,
`plugins/`, `package.json`.

## 5. Create a New Plugin

```bash
cd rhdh-plugin-dev
yarn new
# Select: frontend-plugin, backend-plugin, backend-plugin-module, etc.
# Enter plugin ID, e.g., "simple-example"
```

Optional RHDH theme preview:

```bash
cd plugins/simple-example
yarn add --dev @red-hat-developer-hub/backstage-plugin-theme
```

Update `dev/index.tsx`:

```typescript
import { getAllThemes } from '@red-hat-developer-hub/backstage-plugin-theme';
createDevApp()
  .addThemes(getAllThemes())
  .render();
```

## 6. Implement a Plugin Component

Entity card example (`src/components/ExampleCard/ExampleCard.tsx`):

```typescript
import React from 'react';
import { InfoCard } from '@backstage/core-components';
import { useEntity } from '@backstage/plugin-catalog-react';

export const ExampleCard = () => {
  const { entity } = useEntity();
  return (
    <InfoCard title="Simple Example Info">
      <p>Entity: {entity.metadata.name}</p>
    </InfoCard>
  );
};
```

Register in `src/plugin.ts`:

```typescript
import { createComponentExtension } from '@backstage/core-plugin-api';

export const ExampleCard = simpleExamplePlugin.provide(
  createComponentExtension({
    name: 'ExampleCard',
    component: {
      lazy: () =>
        import('./components/ExampleCard').then(m => m.ExampleCard),
    },
  }),
);
```

Export from `src/index.ts`:

```typescript
export { simpleExamplePlugin, SimpleExamplePage, ExampleCard } from './plugin';
```

## 7. Test Locally

Run the dev harness:

```bash
cd plugins/simple-example
yarn start
```

Navigate to `http://localhost:3000/simple-example/entity`.

## 8. Front-End Plugin Wiring

```yaml
plugins:
  - package: oci://quay.io/<namespace>/simple-example:v0.1.0
    disabled: false
    pluginConfig:
      dynamicPlugins:
        frontend:
          internal.backstage-plugin-simple-example:
            dynamicRoutes:
              - path: /simple-example
                importName: SimpleExamplePage
                menuItem:
                  icon: extension
                  text: Simple Example
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

For RHDH Local development, use `dynamic-plugins.override.yaml` instead.

## 9. Convert to Dynamic Plugin

```bash
cd plugins/simple-example
npx @red-hat-developer-hub/cli@latest plugin export
```

Frontend: produces `dist-dynamic/dist-scalprum/` with Webpack federated modules.
Backend: produces `dist-dynamic/` with bundled backend code.

### Export Flags

- `--shared-package` — dependencies provided by RHDH platform (default:
  `@backstage` scoped); use `!` prefix to treat `@backstage` package as private
- `--embed-package` — packages to bundle (default: `-node` / `-common` suffix)

Example:

```bash
npx @red-hat-developer-hub/cli@latest plugin export \
  --shared-package '!/@backstage/plugin-notifications/' \
  --embed-package @backstage/plugin-notifications-backend
```

## 10. Package as OCI Image

```bash
export QUAY_USER=<username>
export PLUGIN_NAME=simple-example
export VERSION=$(cat package.json | jq .version -r)

npx @red-hat-developer-hub/cli@latest plugin package \
  --tag quay.io/$QUAY_USER/$PLUGIN_NAME:$VERSION

podman push quay.io/$QUAY_USER/$PLUGIN_NAME:$VERSION
```

## 11. Package as TGZ

```bash
cd dist-dynamic
npm pack
npm pack --json | head -n 10  # get integrity hash
```

Reference in `dynamic-plugins.yaml`:

```yaml
plugins:
  - package: https://example.com/backstage-plugin-myplugin-1.0.0.tgz
    integrity: sha512-<hash>
```

## 12. RHDH Local Verification

1. Export: `npx @red-hat-developer-hub/cli@latest plugin export`
2. Copy: `cp -r dist-dynamic/ <RHDH_LOCAL>/local-plugins/simple-example`
3. Configure in `configs/dynamic-plugins/dynamic-plugins.override.yaml`
4. `local-plugins/simple-example/` should contain `dist-scalprum/` and
   `package.json`

Paths:
- Default config: `configs/dynamic-plugins/dynamic-plugins.yaml`
- Override config: `configs/dynamic-plugins/dynamic-plugins.override.yaml`
- Local plugins mount: `/opt/app-root/src/local-plugins`

## 13. Dynamic Plugin Factory

Open source tool (not Red Hat supported) that automates:
- Source code cloning and patching
- Yarn install and TypeScript compilation
- rhdh-cli build, export, and package
- Optional push to Quay or OpenShift registry

## 14. Scalprum Configuration

Default (auto-generated during export):

```json
{
  "name": "<package_name>",
  "exposedModules": {
    "PluginRoot": "./src/index.ts"
  }
}
```

Custom configuration can be added to `package.json` under the `scalprum` key.

## 15. Verification

```bash
# Check loaded plugins endpoint
curl <RHDH_URL>/api/dynamic-plugins-info/loaded-plugins | jq .

# Extensions UI: Administration > Extensions > Installed tab
```
