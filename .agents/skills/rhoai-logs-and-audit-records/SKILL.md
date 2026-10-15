---
name: rhoai-logs-and-audit-records
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhoai
  docs-version: "3.5"
  skill-group: "RHOAI Platform"
description: >
  Use when reading OpenShift AI Operator logs (rhods-operator pods in
  redhat-ods-operator), raising the operator log level through
  DSCInitialization default-dsci spec.devFlags.logLevel for a troubleshooting
  session, or reviewing kube-apiserver audit records for who changed the
  DataScienceCluster default-dsc or the DSCI (including Argo CD and the stage
  enablement Jobs that patch delegated DSC fields). Do NOT use for model server,
  workbench or pipeline run logs (use the component skill or
  rhoai-troubleshoot), the RHOAI observability stack (use rhoai-observability),
  OpenShift logging or audit policy design (use ocp-observability), or install
  failures (use rhoai-installation-troubleshooting).
---

# RHOAI Logs And Audit Records

Thin skill: repo decisions and pitfalls here, product behavior in the linked
OpenShift AI 3.5 "View logs and audit records" sections.

## When to use

- The DSC or DSCI is not Ready and the operator log is the next evidence.
- Someone needs more operator detail (`debug`) for a short session.
- A DSC component flipped unexpectedly and you need to know who patched it.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| `default-dsci` sets no `devFlags`, so the operator runs at its default level | `gitops/stages/010-openshift-ai-platform-foundation/010-rhoai-platform/dsc-init.yaml` | [Configure the operator logger][logger] |
| A raised log level is temporary: change it in Git on a branch, deploy, collect, then revert the commit; the DSCI is owned by `010-rhoai-platform` (automated sync, self-heal) | `gitops/stages/010-openshift-ai-platform-foundation/010-rhoai-platform/README.md` | [Configure the operator logger][logger] |
| DSC changes come from three writers: Argo CD (`010-rhoai-platform`), the stage enablement Sync-hook Jobs on delegated fields, and the operator itself; audit review separates them by user | `gitops/stages/010-openshift-ai-platform-foundation/010-rhoai-platform/README.md` (Delegation model) | [View audit records][audit] |
| The cluster is self-managed OCP on AWS, so kube-apiserver audit logging is on by default; this repo does not change the audit policy | `docs/OPERATIONS.md` (Fresh environment baseline) | [View audit records][audit] |
| Logs and audit excerpts stay outside Git unless sanitized; never commit raw logs | `AGENTS.md` (Security and privacy) | — |

## Procedure

1. Read operator logs, after the OpenShift safety guard in `AGENTS.md`:

   ```bash
   oc get pods -n redhat-ods-operator -l name=rhods-operator
   oc logs -n redhat-ods-operator -l name=rhods-operator --tail=200
   oc get dsc default-dsc -o jsonpath='{range .status.conditions[*]}{.type}={.status} {.reason}{"\n"}{end}'
   ```

2. To raise the level, set `spec.devFlags.logLevel` in `dsc-init.yaml` (check
   the allowed values with `oc explain dscinitialization.spec.devFlags`),
   publish and deploy Stage 010 as usual (`docs/OPERATIONS.md`, Stage 010;
   `deploy.sh --revision <published-sha>`), collect, then revert the same way.
3. Audit review (cluster-admin): collect and filter the kube-apiserver audit
   records for DSC and DSCI changes with the procedure in [View audit
   records][audit]. Map each user to Argo CD or a stage Job ServiceAccount
   (`python3 scripts/shared/stage_apps.py delegated 010 DataScienceCluster default-dsc --group datasciencecluster.opendatahub.io`
   lists the delegated fields).
4. Keep extracts in a private scratch location.

## Pitfalls

- 3.5 documents `spec.devFlags.logLevel`; older notes in this repo used
  `logmode`. Do not copy the old field.
- The log level applies to `rhods-operator` only, not to the components it
  deploys.
- A live `oc patch` of the DSCI is not the procedure here; a field absent from
  Git may persist silently and be forgotten. Use the Git change.
- The documented audit filter excludes the operator's own service account and
  read verbs; changes by Argo CD and stage Jobs still appear.
- Request bodies are only in audit records with `WriteRequestBodies` or a
  broader profile; this cluster's profile is not changed by the repo.

## Official documentation (OpenShift AI 3.5)

| Topic | Section |
|---|---|
| Chapter | [View logs and audit records][chapter] (Managing OpenShift AI); same content in the install guide: [View logs and audit records][chapter-install] |
| Operator logger | [Configure the OpenShift AI Operator logger][logger] ([install guide copy][logger-install]) |
| Audit records | [View audit records][audit] ([install guide copy][audit-install]) |

## Related skills

`rhoai-installation-troubleshooting`, `rhoai-troubleshoot`,
`rhoai-dsci-dsc-configuration`, `rhoai-observability`, `ocp-observability`.

[chapter]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_openshift_ai/index#viewing-logs-and-audit-records_managing-rhoai
[logger]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_openshift_ai/index#configuring-the-operator-logger_managing-rhoai
[audit]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_openshift_ai/index#viewing-audit-records_managing-rhoai
[chapter-install]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/installing_and_uninstalling_openshift_ai_self-managed/index#viewing-logs-and-audit-records_install
[logger-install]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/installing_and_uninstalling_openshift_ai_self-managed/index#configuring-the-operator-logger_install
[audit-install]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/installing_and_uninstalling_openshift_ai_self-managed/index#viewing-audit-records_install
