---
name: rhdh-preview-features
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhdh
  docs-version: "1.10"
  skill-group: "Developer Hub"
description: >
  Use when someone asks about the Red Hat Developer Hub 1.10 book of emerging
  and supplemental preview capabilities (in 1.10 it covers Argo CD notifications
  in Developer Hub). Not used in this repo. Do NOT use for the Argo CD plugin
  the repo does use (use rhdh-dynamic-plugins-configure) or release posture (use
  rhdh-release-notes).
---

# Developer Hub preview capabilities

Thin skill, link-only stub: the feature is not used in this repo. Product
behavior lives in the linked Developer Hub 1.10 sections.

## When to use

- Someone proposes Argo CD notifications in Developer Hub or another item from the preview book.

## Not used in this repo

The repo shows Argo CD state through the Argo CD plugins in
`gitops/stages/070-advanced-app-platform/rhdh/rhdh-instance/dynamic-plugins-configmap.yaml`;
it does not configure Argo CD notifications into Developer Hub.

Adopting it is a Stage 070 change: record the decision in
`gitops/stages/070-advanced-app-platform/rhdh/README.md` and convert this stub
to a full thin skill.

## Official documentation (Developer Hub 1.10)

| Topic | Section |
|---|---|
| Integrate Argo CD notifications | [Integrate Argo CD notifications][l1] |
| Troubleshooting | [Troubleshooting][l2] |
| Security considerations | [Security considerations][l3] |

## Related skills

`rhdh-dynamic-plugins-configure`, `rhdh-release-notes`.

[l1]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/explore_preview_of_emerging_and_supplemental_capabilities/index#integrate-argo-cd-notifications-with-red-hat-developer-hub
[l2]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/explore_preview_of_emerging_and_supplemental_capabilities/index#troubleshooting
[l3]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/explore_preview_of_emerging_and_supplemental_capabilities/index#security-considerations
