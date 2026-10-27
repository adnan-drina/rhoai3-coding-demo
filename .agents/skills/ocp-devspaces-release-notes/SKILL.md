---
name: ocp-devspaces-release-notes
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: ocp_devspaces
  docs-version: "3.31"
  skill-group: "OpenShift Platform"
description: >
  Use when checking OpenShift Dev Spaces 3.31 release posture for this demo:
  the 3.31 operator line with Dev Workspace Operator 1.0.0, known issues,
  deprecated, removed and changed features, and reviewing a Dev Spaces
  z-stream or minor update. Do NOT
  use for concepts (use ocp-devspaces-about), installing or upgrading (use
  ocp-devspaces-install), administration (use ocp-devspaces-admin), or
  workspace usage (use ocp-devspaces-user-guide).
---

# Dev Spaces release notes

Thin skill: the repo's version posture here, release content in the linked
Dev Spaces 3.31 topics.

## When to use

- Reviewing a Dev Spaces or Dev Workspace Operator update.
- Checking whether a known issue or removed feature explains a workspace
  symptom.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| Operator on `stable` with Automatic approval; the operator policy holds the 3.31 line from 3.31.0 (the release notes name DWO 1.0.0) | `gitops/stages/070-advanced-app-platform/070-devspaces/subscription.yaml`, `check_operator_policy` in `scripts/lib.sh` | [Release notes][rn] |
| Doc map pin: the `OPERATOR_POLICY["devspaces"]` minor equals `docs_version` | `.agents/references/red-hat-doc-map.yaml` | — |
| Workspace UDI image stays `udi-rhel9:3.29.1` (two minors behind; recorded Gap) | `gitops/stages/070-advanced-app-platform/070-devspaces/agentic-workspace.yaml` | — (README Alignment table) |
| Internal Open VSX registry (`spec.components.openVSXRegistry`, the default for new installations from 3.32) not used; `open-vsx.org` URL instead | `070-devspaces/checluster.yaml` | [Deprecated][deprecated] |

## Procedure

1. Read the target patch release page, known issues and changed/removed
   features.
2. `stable` moves to a new minor on its own (3.30 to 3.31 on 2026-10-27), and the
   Stage 070 deploy then refuses it. Update `OPERATOR_POLICY["devspaces"]` in
   `scripts/lib.sh` and the validator expectation (`devspacesoperator.v3.NN.`)
   together (`ocp-devspaces-install`).
3. A minor bump also updates the map `docs_version` and the 3.31 links in
   the Dev Spaces skills and `070-devspaces/README.md`
   (`python3 .agents/tools/check-doc-links.py --family ocp_devspaces`).

## Pitfalls

- Patch-release pages do not name the DWO version; read the InstallPlan
  before approving.
- Release notes give OpenShift support for 3.31 as 4.16–4.22; re-check on a
  cluster upgrade.
- The only listed OAuth refresh-token issue (CRW-6859) concerns GitHub and
  Azure DevOps, not GitLab. 3.31 renews an expired GitLab OAuth token when
  the user opens the dashboard Git Services tab (CRW-13559, [New
  features][new]); GitLab token expiry in running workspaces is a repo issue
  (`docs/TROUBLESHOOTING.md#stage-070-running-workspace-retains-an-expired-gitlab-credential`).

## Official documentation (Dev Spaces 3.31)

| Topic | Section |
|---|---|
| Release | [Release notes][rn], [New features][new] |
| Changes | [Deprecated][deprecated], [Removed][removed], [Changed][changed] |
| Issues | [Known issues][known], [Bug fixes][bugs], [CVEs][cves] |
| Background | [Dev Spaces vs Eclipse Che][che], [FAQ][faq] |

## Related skills

`ocp-devspaces-install`, `ocp-devspaces-admin`, `ocp-devspaces-about`, `manage-devspaces`.

[rn]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.31/whats_new-ref_release_notes
[new]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.31/whats_new-ref_new_features
[deprecated]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.31/whats_new-ref_deprecated_functionalities
[removed]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.31/whats_new-ref_removed_functionalities
[changed]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.31/whats_new-ref_changed_features
[known]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.31/whats_new-ref_known_issues
[bugs]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.31/whats_new-ref_bug_fixes
[cves]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.31/whats_new-ref_cve_fixes
[che]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.31/whats_new-ref_differences_between_devspaces_and_che
[faq]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.31/whats_new-ref_frequently_asked_questions
