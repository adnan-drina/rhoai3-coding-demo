---
name: rhdh-git-integration
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhdh
  docs-version: "1.10"
  skill-group: "Developer Hub"
description: >
  Use when changing or debugging how this demo's Red Hat Developer Hub talks
  to the private GitLab: integrations.gitlab with the rhdh-publisher token
  from Secret rhdh-gitlab, the GitLab catalog discovery provider for group
  rhoai-workloads (catalog-info.yaml on main, no templates), the scaffolder
  GitLab module used by the templates (publish:gitlab, gitlab:issues:create),
  the read-only gitlab-catalog-reader used by the catalog generator, and token
  rotation. Do NOT use for GitLab itself (see the gitlab component README),
  sign-in (use rhdh-authentication), template content (use rhdh-customize),
  or GitHub and Bulk Import (not used in this repo).
---

# Developer Hub Git provider integration

Thin skill: repo decisions and pitfalls here, product behavior in the linked
Developer Hub 1.10 sections. Detailed record:
`gitops/stages/070-advanced-app-platform/rhdh/README.md` (How: Catalog
sources) and `gitops/stages/070-advanced-app-platform/gitlab/README.md`
(How 5: integration hub).

## When to use

- A change touches the `integrations` or `catalog.providers` blocks of
  `app-config-rhdh`, or the GitLab modules in `dynamic-plugins-rhdh`.
- A template cannot publish, or a project's `catalog-info.yaml` does not
  appear in the catalog.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| GitLab is the only Git provider; GitHub integration, GitHub App and Bulk Import are not used | `rhdh/rhdh-instance/app-config-configmap.yaml` | [Integrate with GitLab][gitlab] |
| `integrations.gitlab` host, base and API URL from `${GITLAB_HOST}`/`${GITLAB_BASE_URL}`, token `${GITLAB_PUBLISHER_TOKEN}` (service user `rhdh-publisher`) from Secret `rhdh-gitlab` written by `070-gitlab` | same file; `gitlab/README.md` | [Share secrets with GitLab][share] |
| Dynamic plugins `backstage-plugin-catalog-backend-module-gitlab-dynamic` and `backstage-plugin-scaffolder-backend-module-gitlab-dynamic` enabled | `rhdh/rhdh-instance/dynamic-plugins-configmap.yaml` | see `rhdh-dynamic-plugins-reference` |
| Discovery provider `gitlab.workloads`: group `rhoai-workloads`, branch `main`, `catalog-info.yaml`, every minute; catalog rules forbid `Template` from discovery | `rhdh/rhdh-instance/app-config-configmap.yaml` | [Integrate with GitLab][gitlab] (keys `branch`, `entityFilename` not in the 1.10 guide) |
| Templates publish private repositories and open an enrollment issue; they never call `catalog:register` | `rhdh/templates/*/template.yaml` | see `rhdh-customize` |
| The catalog generator verifies every bundled file against the mirror with the read-only `gitlab-catalog-reader` token | `rhdh/jobs/catalog/render_catalog.py` | — (repo control) |
| `backend.reading.allow` lists `${GITLAB_HOST}` (plus GitHub raw hosts) | `rhdh/rhdh-instance/app-config-configmap.yaml` | — |

Paths are under `gitops/stages/070-advanced-app-platform/`.

## Procedure

1. Token values never enter Git; `070-gitlab` mints 90-day tokens and reuses
   them while valid. Rotate before expiry (a token expiring within seven days
   refuses the GitLab sync) with
   `stages/070-advanced-app-platform/rotate-credentials.py --component publisher`
   (dry run unless `--execute`; it also needs `--revision`, `--repo-url`,
   `--report`; procedure in `docs/OPERATIONS.md#gitlab-ownership-and-lifecycle`).

2. Validate after the safety guard in `AGENTS.md`:

   ```bash
   ./stages/070-advanced-app-platform/validate.sh --static   # template input vs GitLab action schemas
   ./stages/070-advanced-app-platform/validate.sh            # gitlab-publisher, gitlab-catalog-reader, private mirror checks
   oc get secret rhdh-gitlab gitlab-publisher gitlab-catalog-reader -n rhdh -o name
   ```

## Pitfalls

- Template inputs must match the installed GitLab action schemas
  (`stages/070-advanced-app-platform/tests/product-schemas.test.py`).
- Do not let discovery ingest templates; a second Location for a template
  causes 200/404 flapping:
  `docs/TROUBLESHOOTING.md#rhdh-template-entity-returns-200-then-404-after-a-catalog-re-stamp`.
- A mirror that is behind the synced revision makes the generator refuse:
  `docs/TROUBLESHOOTING.md#rhdh-catalog-generator-refuses-factory_bundle_mismatch`.
- No apply annotation may hold GitLab credentials (`security-status.py`).
- GitLab API rate limits on the catalog provider: [Catalog provider errors][ratelimit].
- Token lifecycle: `docs/OPERATIONS.md#gitlab-ownership-and-lifecycle`.

## Official documentation (Developer Hub 1.10)

| Topic | Section |
|---|---|
| GitLab | [Integrate with GitLab][gitlab], [Share secrets with GitLab][share], [Import users from GitLab][gl-users] (not used) |
| Bulk Import (not used) | [Bulk importing from GitLab][bulk] |
| GitHub (not used) | [Integrate with GitHub][github] |
| Troubleshooting | [Catalog provider errors][ratelimit] |

## Related skills

`rhdh-configure`, `rhdh-customize`, `rhdh-authentication`,
`rhdh-dynamic-plugins-reference`.

[gitlab]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/integrating_red_hat_developer_hub_with_your_git_provider/index#integrate-with-gitlab_integrate-with-github
[bulk]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/integrating_red_hat_developer_hub_with_your_git_provider/index#bulk-importing-from-gitlab_integrate-with-gitlab
[github]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/integrating_red_hat_developer_hub_with_your_git_provider/index#integrate-with-github_integrating-rhdh-with-your-git-provider
[share]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/authentication_in_red_hat_developer_hub/index#share-secrets-with-gitlab_share-a-secret-with-your-identity-provider
[gl-users]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/authentication_in_red_hat_developer_hub/index#import-users-and-groups-from-gitlab_import-users-and-groups-from-your-identity-provider
[ratelimit]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/authentication_in_red_hat_developer_hub/index#troubleshoot-catalog-provider-errors_troubleshoot-authentication-issues
