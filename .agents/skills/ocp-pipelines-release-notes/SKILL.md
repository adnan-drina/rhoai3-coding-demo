---
name: ocp-pipelines-release-notes
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: ocp_pipelines
  docs-version: "1.24"
  skill-group: "OpenShift Platform"
description: >
  Use when checking OpenShift Pipelines 1.24 version posture for this demo:
  which z-stream runs, supported OpenShift versions, component versions,
  breaking changes, deprecated and removed features, and what to read before
  moving the pipelines-1.24 channel. Do NOT use for installing or configuring
  the operator (use ocp-pipelines-install-config), pipeline authoring (use
  ocp-pipelines-cicd), or security (use ocp-pipelines-security).
---

# OpenShift Pipelines 1.24 release posture

Thin skill: the repo's version facts here, release content in the linked
OpenShift Pipelines 1.24 release notes.

## When to use

- Before changing the channel in
  `gitops/stages/070-advanced-app-platform/070-pipelines/operators/pipelines-subscription.yaml`.
- A z-stream lands (Automatic approval) and behavior changes.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| Channel `pipelines-1.24`, Automatic; patch updates arrive without review (1.24.1 live on 2026-10-15, 1.24.2 on 2026-10-26) | `gitops/stages/070-advanced-app-platform/070-pipelines/operators/pipelines-subscription.yaml` | [Compatibility and support matrix][matrix] |
| The validator accepts any `openshift-pipelines-operator-rh.v1.24.*` | `stages/070-advanced-app-platform/validate.sh` | — |
| Docs version and Git pin are tied in the doc map | `.agents/references/red-hat-doc-map.yaml` (`ocp_pipelines`) | — |

## Procedure

1. Read the [matrix][matrix]: OpenShift 4.22 is listed for 1.24.
2. For each z-stream, read its breaking changes and fixed issues; for a new
   minor, read [deprecated][deprecated] and [removed][removed] features and
   search the repo for each removed item (`git grep -n -i <feature>`).
3. Then follow `ocp-pipelines-install-config` (procedure step 4).

## Pitfalls

- 1.24.1's only breaking change is in Manual Approval Gate (explicit
  RoleBindings needed); the repo does not use Manual Approval Gate.
- Pipelines as Code dropped Tekton Hub integration in 1.24; the repo uses
  neither (see `ocp-pipelines-tekton-hub`).
- A z-stream can drop an operand: see
  `docs/TROUBLESHOOTING.md#pipelines-1226-template-publishes-but-provisioning-never-starts`.

## Official documentation (OpenShift Pipelines 1.24)

| Topic | Section |
|---|---|
| Versions and OpenShift support | [Compatibility and support matrix][matrix] |
| 1.24.1 | [Release notes 1.24.1][r1241], [Breaking changes][r1241-break] |
| 1.24.0 | [Release notes 1.24.0][r1240], [New features][new], [Deprecated][deprecated], [Removed][removed] |

## Related skills

`ocp-pipelines-install-config`, `ocp-pipelines-tekton-hub`, `ocp-pipelines-as-code`.

[matrix]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/release_notes/index#compatibility-support-matrix_op-release-notes-1-24
[r1241]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/release_notes/index#op-release-notes-1-24-1_op-release-notes-1-24
[r1241-break]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/release_notes/index#breaking-changes-1-24-1_op-release-notes-1-24
[r1240]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/release_notes/index#op-release-notes-1-24-0_op-release-notes-1-24
[new]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/release_notes/index#new-features-and-enhancements-1-24-0_op-release-notes-1-24
[deprecated]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/release_notes/index#deprecated-features-1-24-0_op-release-notes-1-24
[removed]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/release_notes/index#removed-features-1-24-0_op-release-notes-1-24
