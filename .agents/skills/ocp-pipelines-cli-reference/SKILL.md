---
name: ocp-pipelines-cli-reference
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: ocp_pipelines
  docs-version: "1.24"
  skill-group: "OpenShift Platform"
description: >
  Use when someone needs the tkn CLI (install, pipeline, pipelinerun, task,
  taskrun, trigger and hub commands) for OpenShift Pipelines 1.24. The repo's
  scripts and runbooks use oc, not tkn; this stub records that and links the
  official sections. Do NOT use for pipeline authoring (use
  ocp-pipelines-cicd) or operator settings (use ocp-pipelines-install-config).
---

# tkn CLI reference (not used by repo scripts)

Link-only stub. Product guidance lives in the linked OpenShift Pipelines 1.24
sections.

## When to use

- A person prefers `tkn` for interactive inspection of runs, or a new script
  considers depending on it.

## Not used in this repo

No stage script, validator or runbook calls `tkn`; they use `oc get
pipelinerun,taskrun` (for example `stages/070-advanced-app-platform/validate.sh`
and `docs/OPERATIONS.md#stage-070--coolstore-dev-environment`). Keep new
automation on `oc` so it needs no extra binary; `tkn` is fine for manual,
read-only inspection (`tkn pipelinerun logs`, `tkn taskrun describe`).

## Official documentation (OpenShift Pipelines 1.24)

| Topic | Section |
|---|---|
| Install | [Installing tkn][install], [Linux][linux], [macOS][macos] |
| Configure | [Configuring tkn][configure] |
| Commands | [Reference][ref], [Pipeline runs][pr], [Task runs][tr], [Triggers][triggers], [Hub][hub] |

## Related skills

`ocp-pipelines-cicd`, `ocp-pipelines-observability`, `ocp-pipelines-tekton-hub`.

[install]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/pipelines_cli_tkn_reference/index#installing-tkn
[linux]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/pipelines_cli_tkn_reference/index#installing-tkn-on-linux
[macos]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/pipelines_cli_tkn_reference/index#installing-tkn-on-macos
[configure]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/pipelines_cli_tkn_reference/index#op-configuring-tkn
[ref]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/pipelines_cli_tkn_reference/index#op-tkn-reference
[pr]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/pipelines_cli_tkn_reference/index#op-tkn-pipeline-run_op-tkn-reference
[tr]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/pipelines_cli_tkn_reference/index#op-tkn-task-run_op-tkn-reference
[triggers]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/pipelines_cli_tkn_reference/index#op-tkn-trigger-management_op-tkn-reference
[hub]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/pipelines_cli_tkn_reference/index#op-tkn-hub-interaction_op-tkn-reference
