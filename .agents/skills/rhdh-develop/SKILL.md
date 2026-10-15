---
name: rhdh-develop
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhdh
  docs-version: "1.10"
  skill-group: "Developer Hub"
description: >
  Use when working with this demo's Developer Hub software catalog and
  Software Templates: the generated runtime catalog, the two golden-path
  templates (agentic-quarkus-scaffold "New Quarkus app", app-migration
  "Application migration"), GitLab discovery of catalog-info.yaml, why
  developers cannot register components, and why Bulk Import is not used. Do
  NOT use for TechDocs (use rhdh-techdocs-manage), plugin tabs (use
  rhdh-dynamic-plugins-usage), GitLab integration settings (use
  rhdh-git-integration), or the Stage 130 migration run itself.
---

# RHDH software development and management

Thin skill: how this portal's catalog and templates are produced and governed;
generic catalog and template usage is in the linked Developer Hub 1.10
sections. Detailed record: `gitops/stages/070-advanced-app-platform/rhdh/README.md`
("Catalog generation", "Catalog sources") and
`rhdh/templates/app-migration/delivery-path.md`.

## When to use

- Changing `rhdh/catalog/all.yaml` (Users, Group, Domain, System, Component
  `coolstore-inventory-service`, API, one model Resource, two template
  Locations) or a template under `rhdh/templates/`.
- A template or entity is missing, duplicated, or flaps between 200 and 404.
- Explaining what a developer can and cannot do in the catalog.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| The runtime catalog is generated: bundle ConfigMap (content-hashed) → `render_catalog.py verify` against the GitLab mirror at the synced revision → `catalog-runtime-rhdh`, stamped with `rhoai3.redhat.com/catalog-revision` | `gitops/stages/070-advanced-app-platform/rhdh/jobs/catalog/`, `rhdh/jobs/generate-rhdh-catalog.yaml`, `rhdh/catalog/all.yaml` | [Centralize components in the catalog][catalog] |
| Only the file location may introduce `Template` entities; template Locations point at the same pinned revision and older ones are pruned | `rhdh/rhdh-instance/app-config-configmap.yaml` (`catalog.locations`, `catalog.rules`), `render_catalog.py` | [Import an existing Software Template][import-tpl] |
| GitLab discovery reads `catalog-info.yaml` on `main` in group `rhoai-workloads` every minute and may not ingest templates; `orphanStrategy: delete` | `app-config-configmap.yaml` (`catalog.providers.gitlab.workloads`) | [Update existing components][update] |
| Templates publish private GitLab repositories (`publish:gitlab`) and open an enrollment issue (`gitlab:issues:create`); they never call `catalog:register` | `rhdh/templates/agentic-quarkus-scaffold/template.yaml`, `rhdh/templates/app-migration/template.yaml` | [Create a component from a template][create-tpl] |
| `ai-developer` may read the catalog and run templates; `catalog.location.create`, `catalog.entity.create`, `catalog.entity.delete` are denied | `rhdh/rhdh-instance/rbac-policy.yaml` | [Register components manually][register] |
| No Bulk Import: projects enter only through templates and the enrollment coordinator | — | [Import your team's codebase][bulk] |

## Procedure

1. Edit the catalog or a template in Git; keep placeholders in the
   `__RHOAI3_*__` form the renderer resolves.
2. Static checks: `./stages/070-advanced-app-platform/validate.sh --static`
   (`render_catalog.test.py`, `app-migration-template.test.py`,
   `security-boundaries.test.py`, `product-schemas.test.py`).
3. After the OpenShift safety guard in `AGENTS.md`, deploy with
   `./stages/070-advanced-app-platform/deploy.sh` and run `validate.sh`
   ("Portal catalog bundle stamped", "Portal catalog has no unresolved
   placeholders", "Portal templates use private GitLab mirror").
4. Read-only checks:

   ```bash
   oc get configmap catalog-runtime-rhdh -n rhdh -o jsonpath='{.metadata.annotations}{"\n"}'
   oc get cronjob refresh-rhdh-catalog -n rhdh
   ```

## Pitfalls

- Generator refusals (`FACTORY_BUNDLE_MISMATCH`, `CATALOG_RENDER`):
  `docs/TROUBLESHOOTING.md#rhdh-catalog-generator-refuses-factory_bundle_mismatch`.
- A template flapping 200/404 means more than one Location for it:
  `docs/TROUBLESHOOTING.md#rhdh-template-entity-returns-200-then-404-after-a-catalog-re-stamp`;
  re-run the generator, do not restart RHDH as the fix.
- `app-migration` refuses without the MaaS route annotations on the platform
  entity: `docs/TROUBLESHOOTING.md#migration-workspace-creation-fails-with-factory_maas_route_missing`.
- Template GitLab inputs must match the installed scaffolder action schemas
  (`product-schemas.test.py`); the GitLab scaffolder module is Technology
  Preview in 1.10 (`rhdh-dynamic-plugins-reference`).
- Do not "fix" a missing entity by registering it in the UI: developers are
  denied and admin registrations bypass the pinned bundle.

## Official documentation (Developer Hub 1.10)

| Topic | Section |
|---|---|
| Catalog | [Centralize components][catalog], [Add new components][add], [Update][update], [Find by kind][find], [Review YAML][yaml] |
| Software Templates | [Create a component from a template][create-tpl], [Search templates][search-tpl], [Import a template][import-tpl] |
| Bulk Import (not used) | [Import your team's codebase][bulk] |

## Related skills

`rhdh-techdocs-manage`, `rhdh-dynamic-plugins-usage`, `rhdh-git-integration`,
`rhdh-authorization`, `rhdh-getting-started-navigate`, `ocp-pipelines-cicd`.

[catalog]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/streamline_software_development_and_management_in_red_hat_developer_hub/index#centralize-your-software-components-in-the-rhdh-catalog_streamline-software-development-and-management-in-rhdh
[add]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/streamline_software_development_and_management_in_red_hat_developer_hub/index#add-new-components-to-your-rhdh-instance_centralize-your-software-components-in-the-rhdh-catalog
[register]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/streamline_software_development_and_management_in_red_hat_developer_hub/index#register-components-manually-in-your-rhdh-instance_centralize-your-software-components-in-the-rhdh-catalog
[update]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/streamline_software_development_and_management_in_red_hat_developer_hub/index#update-existing-components-in-your-rhdh-catalog_centralize-your-software-components-in-the-rhdh-catalog
[find]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/streamline_software_development_and_management_in_red_hat_developer_hub/index#find-components-by-kind-in-the-rhdh-catalog_centralize-your-software-components-in-the-rhdh-catalog
[yaml]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/streamline_software_development_and_management_in_red_hat_developer_hub/index#review-the-yaml-configuration-of-your-rhdh-software-catalog_centralize-your-software-components-in-the-rhdh-catalog
[create-tpl]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/streamline_software_development_and_management_in_red_hat_developer_hub/index#create-a-software-component-using-software-templates_import-and-use-an-existing-software-template-for-faster-development
[search-tpl]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/streamline_software_development_and_management_in_red_hat_developer_hub/index#search-and-filter-software-templates-in-your-rhdh-instance_import-and-use-an-existing-software-template-for-faster-development
[import-tpl]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/streamline_software_development_and_management_in_red_hat_developer_hub/index#import-an-existing-software-template_import-and-use-an-existing-software-template-for-faster-development
[bulk]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/streamline_software_development_and_management_in_red_hat_developer_hub/index#import-your-team-s-codebase-from-git_streamline-software-development-and-management-in-rhdh
