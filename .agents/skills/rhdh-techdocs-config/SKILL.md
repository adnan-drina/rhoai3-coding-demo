---
name: rhdh-techdocs-config
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhdh
  docs-version: "1.10"
  skill-group: "Developer Hub"
description: >
  Use when changing or reviewing how this demo's Developer Hub builds and
  stores TechDocs: the local builder, generator and publisher in
  app-config-rhdh, the techdocs-ref annotations rendered into the runtime
  catalog, and the decision not to use object storage or a CI docs pipeline.
  Also use before proposing S3/ODF storage or TechDocs add-ons. Do NOT use
  for reading or editing documentation content (use rhdh-techdocs-manage),
  general app-config (use rhdh-configure), or ObjectBucketClaims (use
  odf-object-bucket-claims).
---

# RHDH TechDocs configuration

Thin skill: repo decisions and pitfalls here, product procedure in the linked
Developer Hub 1.10 sections. Detailed record:
`gitops/stages/070-advanced-app-platform/070-rhdh/README.md` (Alignment row
"TechDocs").

## When to use

- A change touches the `techdocs:` block of
  `070-rhdh/rhdh-instance/app-config-configmap.yaml`.
- A docs page fails to build or render in the portal.
- Someone proposes CI-built docs, object storage, or TechDocs add-ons.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| `techdocs.builder: local`, `generator.runIn: local`, `publisher.type: local`: the portal builds docs itself (Deviation, justified: one platform docs source, no docs pipeline) | `gitops/stages/070-advanced-app-platform/070-rhdh/rhdh-instance/app-config-configmap.yaml` | [Configure TechDocs][configure] |
| Docs source is the pinned platform revision in the private GitLab mirror: `backstage.io/techdocs-ref: url:__RHOAI3_PLATFORM_TREE_URL__`, rendered by the catalog generator to `<platform repo>/-/tree/<revision>` | `070-rhdh/catalog/all.yaml`, `070-rhdh/jobs/catalog/render_catalog.py` | [Configure TechDocs][configure] |
| Docs are read from GitLab through the GitLab integration and `backend.reading.allow` for `${GITLAB_HOST}` | `app-config-configmap.yaml` | see `rhdh-git-integration` |
| No object storage, no CI/CD publishing, no add-ons beyond product defaults | — | [Storage][storage], [CI/CD][cicd], [Add-ons][addons] |

## Procedure

1. Change TechDocs settings only in `app-config-configmap.yaml`; a change to the
   docs source changes `catalog/all.yaml` and goes through the catalog
   generator (bundle hash, GitLab byte check).
2. Static checks: `./stages/070-advanced-app-platform/validate.sh --static`
   (`render_catalog.test.py`).
3. After the OpenShift safety guard in `AGENTS.md`, deploy with
   `./stages/070-advanced-app-platform/deploy.sh`; then check read-only:

   ```bash
   oc get configmap catalog-runtime-rhdh -n rhdh -o jsonpath='{.data.all\.yaml}' | grep techdocs-ref
   oc logs deployment/backstage-developer-hub -n rhdh -c backstage-backend --tail=300 | grep -i techdocs
   ```

## Pitfalls

- The 1.10 guide states the default local builder setup is not intended for
  production ([Configure TechDocs][configure]); keep the deviation recorded
  if this demo is reused as a production pattern.
- A docs link that still contains `__RHOAI3_` means the runtime catalog was
  not rendered: `docs/TROUBLESHOOTING.md#rhdh-catalog-generator-refuses-factory_bundle_mismatch`.
- The 1.10 docs-adding procedures expect an `mkdocs.yml` and a `docs/`
  directory with `index.md` at the referenced root, and show only the
  `dir:.` form of `techdocs-ref` ([Add documentation][add-docs]). The platform
  repository has no `mkdocs.yml`, and the repo uses `url:<tree>`; whether the
  platform docs page renders is unverified here (check live before demoing).
- Moving to S3 or ODF storage needs a bucket (an OBC, `odf-object-bucket-claims`),
  credentials outside Git, and a CI step that builds and publishes the site;
  that is a new design, not a config toggle.

## Official documentation (Developer Hub 1.10)

| Topic | Section |
|---|---|
| Overview | [About TechDocs][about] |
| Builder and publisher | [Configure TechDocs][configure] |
| Storage (not used) | [Storage for TechDocs files][storage], [Amazon S3][s3], [OpenShift Data Foundation][odf], [Operator object storage][odf-operator] |
| CI/CD publishing (not used) | [Generate and publish TechDocs sites][cicd] |
| Add-ons (not used) | [TechDocs add-ons][addons], [Operator install of an add-on][addon-operator], [Create an add-on][addon-create] |

## Related skills

`rhdh-techdocs-manage`, `rhdh-configure`, `rhdh-git-integration`,
`odf-object-bucket-claims`.

[about]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/techdocs_for_red_hat_developer_hub/index#about-techdocs_techdocs-for-rhdh
[configure]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/techdocs_for_red_hat_developer_hub/index#configure-techdocs_techdocs-for-rhdh
[storage]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/techdocs_for_red_hat_developer_hub/index#configuring-storage-for-techdocs-files_configure-techdocs
[s3]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/techdocs_for_red_hat_developer_hub/index#configure-amazon-s3-for-file-storage_configure-techdocs
[odf]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/techdocs_for_red_hat_developer_hub/index#configure-for-file-storage_configure-techdocs
[odf-operator]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/techdocs_for_red_hat_developer_hub/index#make-object-storage-accessible-to-containers-by-using-the-operator_configure-techdocs
[cicd]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/techdocs_for_red_hat_developer_hub/index#configuring-ci-cd-to-generate-and-publish-techdocs-sites_configure-techdocs
[addons]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/techdocs_for_red_hat_developer_hub/index#techdocs-add-ons_techdocs-for-rhdh
[addon-operator]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/techdocs_for_red_hat_developer_hub/index#install-and-configure-an-external-techdocs-add-on-using-the-operator_install-and-configure-a-techdocs-add-on
[add-docs]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/manage_and_consume_technical_documentation_within_red_hat_developer_hub/index#add-documentation-to-techdocs-for-your-project_manage-and-consume-technical-documentation-within-rhdh
[addon-create]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/techdocs_for_red_hat_developer_hub/index#create-a-techdocs-add-on_techdocs-for-rhdh
