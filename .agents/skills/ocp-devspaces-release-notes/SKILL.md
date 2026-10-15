---
name: ocp-devspaces-release-notes
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: ocp_devspaces
  docs-version: "3.30"
  skill-group: "OpenShift Platform"
description: >
  Use when checking OpenShift Dev Spaces 3.30 release posture for this demo:
  the pinned 3.30.2 operator with Dev Workspace Operator 0.43.0, patch
  releases, known issues, deprecated, removed and changed features, Technology
  Preview scope, and reviewing a Dev Spaces z-stream or minor update. Do NOT
  use for concepts (use ocp-devspaces-about), installing or upgrading (use
  ocp-devspaces-install), administration (use ocp-devspaces-admin), or
  workspace usage (use ocp-devspaces-user-guide).
---

# Dev Spaces release notes

Thin skill: the repo's version posture here, release content in the linked
Dev Spaces 3.30 topics.

## When to use

- Reviewing a Dev Spaces or Dev Workspace Operator update.
- Checking whether a known issue or removed feature explains a workspace
  symptom.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| Operator on `stable` with Automatic approval; the operator policy holds the 3.30 line from 3.30.2 (DWO 0.43.0 observed with it) | `gitops/stages/070-advanced-app-platform/devspaces/subscription.yaml`, `scripts/platform/check-operator-policy.py` | [3.30.2 patch release][p2], [Release notes][rn] |
| Doc map pin: `startingCSV` minor equals `docs_version` | `.agents/references/red-hat-doc-map.yaml` | — |
| Workspace UDI image stays `udi-rhel9:3.29.1` (one minor behind; recorded Gap) | `gitops/stages/070-advanced-app-platform/devspaces/agentic-workspace.yaml` | — (README Alignment table) |
| Managed Open VSX registry (Technology Preview) not used; `open-vsx.org` URL instead | `devspaces/checluster.yaml` | [Technology Preview][tp] |

## Procedure

1. Read the target patch release page, known issues and changed/removed
   features.
2. Update `startingCSV`, the approver allowlist (including the DWO CSV the
   release ships) and the validator expectation together (`ocp-devspaces-install`).
3. A minor bump also updates the map `docs_version` and the 3.30 links in
   the Dev Spaces skills and `devspaces/README.md`
   (`python3 scripts/shared/check-doc-links.py --family ocp_devspaces`).

## Pitfalls

- Patch-release pages do not name the DWO version; read the InstallPlan
  before approving.
- Release notes give OpenShift support for 3.30 as 4.16–4.22; re-check on a
  cluster upgrade.
- The only listed OAuth refresh-token issue (CRW-6859) concerns GitHub and
  Azure DevOps, not GitLab; GitLab token expiry in running workspaces is a
  repo issue
  (`docs/TROUBLESHOOTING.md#stage-070-running-workspace-retains-an-expired-gitlab-credential`).

## Official documentation (Dev Spaces 3.30)

| Topic | Section |
|---|---|
| Release | [Release notes][rn], [New features][new], [Patch releases][patches], [3.30.1][p1], [3.30.2][p2] |
| Changes | [Deprecated][deprecated], [Removed][removed], [Changed][changed], [Technology Preview][tp] |
| Issues | [Known issues][known], [Bug fixes][bugs], [CVEs][cves] |
| Background | [Dev Spaces vs Eclipse Che][che], [FAQ][faq] |

## Related skills

`ocp-devspaces-install`, `ocp-devspaces-admin`, `ocp-devspaces-about`, `manage-devspaces`.

[rn]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/whats_new-ref_release_notes
[new]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/whats_new-ref_new_features
[patches]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/whats_new-ref_patch_releases
[p1]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/whats_new-dev_spaces_3_30_patch_release_september_18__2026__3_30_1_
[p2]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/whats_new-dev_spaces_3_30_patch_release_september_30__2026
[deprecated]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/whats_new-ref_deprecated_functionalities
[removed]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/whats_new-ref_removed_functionalities
[changed]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/whats_new-ref_changed_features
[tp]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/whats_new-ref_technology_preview
[known]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/whats_new-ref_known_issues
[bugs]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/whats_new-ref_bug_fixes
[cves]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/whats_new-ref_cve_fixes
[che]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/whats_new-ref_differences_between_devspaces_and_che
[faq]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/whats_new-ref_frequently_asked_questions
