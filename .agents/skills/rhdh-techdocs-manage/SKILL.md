---
name: rhdh-techdocs-manage
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhdh
  docs-version: "1.10"
  skill-group: "Developer Hub"
description: >
  Use when adding, finding, reading or editing documentation in this demo's
  Developer Hub TechDocs: which entities carry backstage.io/techdocs-ref,
  where their content comes from (the pinned platform revision in the private
  GitLab mirror), and how a docs change reaches the portal. Do NOT use for
  builder, storage or add-on configuration (use rhdh-techdocs-config), catalog
  and template workflows (use rhdh-develop), or GitHub Actions doc builds
  (not used here).
---

# RHDH TechDocs: manage and consume

Thin skill: how documentation reaches this portal; the product's authoring
and reading procedures are in the linked Developer Hub 1.10 sections.
Detailed record: `gitops/stages/070-advanced-app-platform/070-rhdh/README.md`
("Catalog generation", "Catalog sources").

## When to use

- A presenter or developer looks for platform documentation in the portal.
- A new catalog entity or template should show a Docs tab.
- A docs change does not appear in the portal.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| Docs are attached to platform-owned entities only (System `coolstore`, Component `coolstore-inventory-service`) through `backstage.io/techdocs-ref: url:__RHOAI3_PLATFORM_TREE_URL__` | `gitops/stages/070-advanced-app-platform/070-rhdh/catalog/all.yaml` | [Add documentation][add] |
| The URL is rendered to the platform GitLab mirror at the synced revision, so docs follow the reviewed commit, not `main` | `070-rhdh/jobs/catalog/render_catalog.py`, `070-rhdh/jobs/catalog/generate.sh` | [Import documentation from a remote repository][import] |
| Template skeletons set no `techdocs-ref`; template-created projects have no Docs tab | `070-rhdh/templates/*/skeleton/catalog-info.yaml` | [Enable documentation for an existing entity][existing] |
| Doc changes go through Git review and a platform commit; the portal shows them only after `070-rhdh` syncs that commit | `070-rhdh/catalog/all.yaml` | [Make changes to documentation][edit] |
| No GitHub Actions doc builds; the portal builds locally (`rhdh-techdocs-config`) | `070-rhdh/rhdh-instance/app-config-configmap.yaml` | [GitHub Actions builds][gha] |

## Procedure

1. Change documentation in the platform repository and merge it; the
   documentation shown is the revision `070-rhdh` synced.
2. To attach docs to another platform entity, add the same `techdocs-ref` form
   in `catalog/all.yaml`; run `./stages/070-advanced-app-platform/validate.sh --static`.
3. After the OpenShift safety guard in `AGENTS.md`, sync `070-rhdh` and confirm
   the stamped revision (read-only):

   ```bash
   oc get configmap catalog-runtime-rhdh -n rhdh \
     -o jsonpath='{.metadata.annotations.rhoai3\.redhat\.com/catalog-revision}{"\n"}'
   ```

4. In the portal: Docs, then search ([Search][search], [Access and navigate][navigate]).

## Pitfalls

- Docs lag a push until Argo CD has synced the commit and the generator has
  verified the GitLab mirror; a hand-edited bundle is refused:
  `docs/TROUBLESHOOTING.md#rhdh-catalog-generator-refuses-factory_bundle_mismatch`.
- The product procedures assume `mkdocs.yml` plus `docs/index.md` at the
  referenced root and show `dir:.`; the repo's `url:` form against a tree
  without `mkdocs.yml` is unverified (see `rhdh-techdocs-config`).
- The GitLab discovery provider may not ingest Templates and the catalog
  file is the only Template source; new docs-bearing templates go into
  `catalog/all.yaml`.

## Official documentation (Developer Hub 1.10)

| Topic | Section |
|---|---|
| Add docs | [Add documentation][add], [Import from a remote repository][import], [Standalone documentation][standalone], [Existing entity][existing] |
| Read docs | [Search][search], [Access and navigate][navigate] |
| Change docs | [Make changes][edit], [Video content][video] |
| CI builds (not used) | [GitHub Actions][gha] |

## Related skills

`rhdh-techdocs-config`, `rhdh-develop`, `rhdh-getting-started-navigate`,
`rhdh-git-integration`.

[add]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/manage_and_consume_technical_documentation_within_red_hat_developer_hub/index#add-documentation-to-techdocs-for-your-project_manage-and-consume-technical-documentation-within-rhdh
[import]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/manage_and_consume_technical_documentation_within_red_hat_developer_hub/index#import-documentation-into-techdocs-from-a-remote-repository_add-documentation-to-techdocs-for-your-project
[standalone]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/manage_and_consume_technical_documentation_within_red_hat_developer_hub/index#create-standalone-documentation-in-techdocs_add-documentation-to-techdocs-for-your-project
[existing]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/manage_and_consume_technical_documentation_within_red_hat_developer_hub/index#enable-documentation-for-an-existing-entity_add-documentation-to-techdocs-for-your-project
[search]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/manage_and_consume_technical_documentation_within_red_hat_developer_hub/index#search-for-relevant-content_manage-and-consume-technical-documentation-within-rhdh
[navigate]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/manage_and_consume_technical_documentation_within_red_hat_developer_hub/index#access-and-navigate-documentation_manage-and-consume-technical-documentation-within-rhdh
[edit]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/manage_and_consume_technical_documentation_within_red_hat_developer_hub/index#make-changes-to-project-documentation-in-techdocs_manage-and-consume-technical-documentation-within-rhdh
[video]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/manage_and_consume_technical_documentation_within_red_hat_developer_hub/index#add-video-content-to-enhance-techdocs_manage-and-consume-technical-documentation-within-rhdh
[gha]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/manage_and_consume_technical_documentation_within_red_hat_developer_hub/index#streamline-documentation-builds-using-github-actions_manage-and-consume-technical-documentation-within-rhdh
