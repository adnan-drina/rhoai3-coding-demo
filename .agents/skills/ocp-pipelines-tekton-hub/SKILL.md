---
name: ocp-pipelines-tekton-hub
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: ocp_pipelines
  docs-version: "1.24"
  skill-group: "OpenShift Platform"
description: >
  Use when someone asks about Tekton Hub, the hub resolver, tkn hub, or
  migrating catalog task references to Artifact Hub on OpenShift Pipelines
  1.24. No Tekton Hub or hub resolver is used in this repo; this stub records
  that and links the official sections. Do NOT use to deploy a Tekton Hub, or
  for the repo's own Tasks (use ocp-pipelines-cicd).
---

# Tekton Hub and Artifact Hub (not used in this repo)

Link-only stub. Product guidance lives in the linked OpenShift Pipelines 1.24
sections.

## When to use

- A pipeline proposal references a hub or catalog task, or an old Tekton Hub
  resource needs retiring.

## Not used in this repo

No `TektonHub` resource, hub resolver or Artifact Hub reference exists in
Git. Every Task the platform runs is a namespaced Task in
`gitops/stages/070-advanced-app-platform/pipelines/project-pipeline/`,
reviewed and pinned with the platform revision. In 1.24, Pipelines as Code
removed its Tekton Hub integration and `tkn hub` targets Artifact Hub.

## Official documentation (OpenShift Pipelines 1.24)

| Topic | Section |
|---|---|
| Removal and deprecation | [Removed features][removed], [Deprecated features][deprecated] |
| Migration | [Migrating to Artifact Hub][migrate], [Assess impact][assess], [Private Artifact Hub][private] |
| Hub resolver | [Hub resolver][hub-resolver] |
| CLI | [tkn hub commands][tkn-hub] |

## Related skills

`ocp-pipelines-cicd`, `ocp-pipelines-as-code`, `ocp-pipelines-release-notes`.

[removed]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/release_notes/index#removed-features-1-24-0_op-release-notes-1-24
[deprecated]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/release_notes/index#deprecated-features-1-24-0_op-release-notes-1-24
[migrate]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/installing_and_configuring/index#op-migrating-to-artifact-hub_customizing-configurations-in-the-tektonconfig-cr
[assess]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/installing_and_configuring/index#op-assess-migration-impact_customizing-configurations-in-the-tektonconfig-cr
[private]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/installing_and_configuring/index#op-configuring-private-artifact-hub_customizing-configurations-in-the-tektonconfig-cr
[hub-resolver]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/creating_cicd_pipelines/index#resolver-hub_remote-pipelines-tasks-resolvers
[tkn-hub]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/pipelines_cli_tkn_reference/index#op-tkn-hub-interaction_op-tkn-reference
