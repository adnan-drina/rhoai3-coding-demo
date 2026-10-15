---
name: rhdh-customize
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhdh
  docs-version: "1.10"
  skill-group: "Developer Hub"
description: >
  Use when changing what developers see in this demo's Red Hat Developer Hub:
  the portal title, the global header (application launcher tiles for
  SonarQube and Dev Spaces), and the two software templates
  agentic-quarkus-scaffold and app-migration (steps publish:gitlab and
  gitlab:issues:create, skeletons, catalog registration through the pinned
  runtime catalog). Do NOT use for app-config plumbing, secrets and the
  Backstage CR (use rhdh-configure), plugin enablement (use
  rhdh-dynamic-plugins-configure), TechDocs (use rhdh-techdocs-config), or
  sign-in (use rhdh-authentication).
---

# Developer Hub customization

Thin skill: repo decisions and pitfalls here, product behavior in the linked
Developer Hub 1.10 sections. Detailed record:
`gitops/stages/070-advanced-app-platform/070-rhdh/README.md`.

## When to use

- Changing the header, launcher tiles or title in `app-config-rhdh`.
- Adding or changing a software template under
  `gitops/stages/070-advanced-app-platform/070-rhdh/templates/`.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| Title `RHOAI Coding Demo Portal`; base URL from `${RHDH_BASE_URL}` written by the configure hook | `070-rhdh/rhdh-instance/app-config-configmap.yaml` | [Title][title], [Base URL][baseurl] |
| Global header `mountPoints` restate the full default composition and append the demo launcher tiles (`${SONARQUBE_URL}`, `${DEVSPACES_URL}`) | same file (`dynamicPlugins.frontend`) | [Customize the global header][header], [Mount points][mounts] |
| Floating action button, home page, learning paths, Tech Radar, theme and branding are not customized | — | [Floating action button][fab], [Theme and branding][theme] |
| Two templates, `agentic-quarkus-scaffold` and `app-migration`; they publish private GitLab repositories (`publish:gitlab`) and open an enrollment issue (`gitlab:issues:create`), never `catalog:register` | `070-rhdh/templates/*/template.yaml` | [Software templates][templates], [Create a template][create] |
| Templates enter the catalog only from the generated runtime catalog pinned to one platform commit; GitLab discovery may not ingest `Template` | `070-rhdh/catalog/all.yaml`, `070-rhdh/jobs/catalog/render_catalog.py` | [Share templates][share] |
| Template versioning and automated template sync are not used; the pinned bundle is the version | `070-rhdh/jobs/catalog/generate.sh` | [Version a template][version], [Automated template updates][autoupdate] |

Paths are under `gitops/stages/070-advanced-app-platform/`.

## Procedure

1. Header: copy the whole current `mountPoints` list and append; never send
   a partial list.
2. Templates: edit `template.yaml` and its `skeleton/`; the bundle hash
   changes, Argo CD applies the new ConfigMap and the catalog generator
   publishes it only when every bundled file matches the GitLab mirror.
3. Validate statically, then after the safety guard in `AGENTS.md`:

   ```bash
   ./stages/070-advanced-app-platform/validate.sh --static   # render_catalog and app-migration template tests
   ./stages/070-advanced-app-platform/validate.sh
   oc get configmap catalog-runtime-rhdh -n rhdh -o jsonpath='{.metadata.annotations.rhoai3\.redhat\.com/catalog-revision}{"\n"}'
   ```

## Pitfalls

- A custom header `mountPoints` list replaces the default composition in
  practice (observed live 2026-07-14, comment in the ConfigMap); dropping the
  `GlobalHeader` entry removes the whole top header. The 1.10 guide says only
  to copy the default configuration and modify it.
- Template input names must match the installed GitLab action schemas
  (check them against the action list in Developer Hub; the offline schema
  test was retired and is in git history at `82092e01`).
- Template flaps 200/404 after a re-stamp:
  `docs/TROUBLESHOOTING.md#rhdh-template-entity-returns-200-then-404-after-a-catalog-re-stamp`.
- `FACTORY_MAAS_ROUTE_MISSING` from `app-migration`:
  `docs/TROUBLESHOOTING.md#migration-workspace-creation-fails-with-factory_maas_route_missing`.

## Official documentation (Developer Hub 1.10)

| Topic | Section |
|---|---|
| Title, URL | [Title][title], [Base URL][baseurl] |
| Global header | [Configure the global header][header-ch], [Customize][header], [Mount points][mounts] |
| Templates | [About templates][about-templates], [Software templates][templates], [Create a template][create], [Share templates][share], [Version a template][version], [Automated template updates][autoupdate] |
| Not used | [Floating action button][fab], [Theme and branding][theme], [Navigation][nav], [Localization][l10n] |

## Related skills

`rhdh-configure`, `rhdh-dynamic-plugins-configure`, `rhdh-git-integration`,
`rhdh-techdocs-config`, `rhdh-getting-started-navigate`.

[title]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/customizing_red_hat_developer_hub/index#customize-your-rhdh-title_customizing-rhdh
[baseurl]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/customizing_red_hat_developer_hub/index#customize-your-rhdh-base-url_customizing-rhdh
[about-templates]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/customizing_red_hat_developer_hub/index#about-software-templates_customizing-rhdh
[version]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/customizing_red_hat_developer_hub/index#version-a-software-template-in-rhdh_about-software-templates
[autoupdate]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/customizing_red_hat_developer_hub/index#enable-automated-template-updates_automated-software-template-lifecycle-management
[templates]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/customizing_red_hat_developer_hub/index#software-templates-in-rhdh_standardize-project-development-with-software-templates
[create]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/customizing_red_hat_developer_hub/index#create-a-basic-software-template_standardize-project-development-with-software-templates
[share]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/customizing_red_hat_developer_hub/index#share-software-templates-with-your-organization_standardize-project-development-with-software-templates
[header-ch]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/customizing_red_hat_developer_hub/index#configure-the-global-header-in-rhdh_customizing-rhdh
[header]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/customizing_red_hat_developer_hub/index#customize-your-rhdh-global-header_configure-the-global-header-in-rhdh
[mounts]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/customizing_red_hat_developer_hub/index#mount-points-for-dynamic-plugin-integration_configure-the-global-header-in-rhdh
[fab]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/customizing_red_hat_developer_hub/index#configure-a-floating-action-button-in-rhdh_customizing-rhdh
[theme]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/customizing_red_hat_developer_hub/index#customize-rhdh-theme-and-branding_customizing-rhdh
[nav]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/customizing_red_hat_developer_hub/index#customize-rhdh-navigation_customizing-rhdh
[l10n]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/customizing_red_hat_developer_hub/index#localization-in-rhdh_customizing-rhdh
