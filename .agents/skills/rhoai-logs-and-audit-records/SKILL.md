---
name: rhoai-logs-and-audit-records
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "RHOAI Platform"
description: >
  Use when configuring, documenting, reviewing, or troubleshooting Red Hat
  OpenShift AI Operator logging and audit-record workflows: DSCI
  spec.devFlags.logmode, development versus production log output, viewing
  rhods-operator pod logs in redhat-ods-operator, collecting OpenShift
  kube-apiserver audit logs, filtering audit records for DataScienceCluster
  and DSCInitialization changes, audit policy prerequisites, and GitOps review
  of logger settings. Do NOT use for general application logs, model-serving
  logs, pipeline run logs, OpenShift cluster logging architecture, or live
  environment troubleshooting; use env-troubleshoot or the relevant rhoai-*
  component skill.
---

# RHOAI Logs And Audit Records

Use this skill to configure and review OpenShift AI Operator logging and audit
record access for the active baseline in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product configuration details.
Official Red Hat documentation is product authority. This skill adapts the
official Administer logs and audit-record guidance to this repo's GitOps
operating model and live-cluster safety guard.

## Scope

This skill covers:

- OpenShift AI Operator logger configuration through
  `DSCInitialization.spec.devFlags.logmode`
- viewing OpenShift AI Operator logs from `rhods-operator` pods
- collecting kube-apiserver audit logs from control plane nodes
- filtering audit records for `DataScienceCluster` and `DSCInitialization`
  changes

This skill does not cover model server logs, pipeline run logs, notebook logs,
cluster logging stack deployment, log forwarding architecture, or SIEM
integration.

## Logger Policy

For this repo:

- Keep production/default logging unless a troubleshooting task explicitly needs
  development output.
- Treat `development`/`devel` logging as temporary because it is more verbose.
- Record any GitOps change to DSCI logger settings in docs or operations notes.
- Prefer reverting temporary logger changes to production/default after
  troubleshooting.
- Do not patch live DSCI objects unless the user explicitly asks for live
  troubleshooting and the OpenShift safety guard has passed.

## Audit Policy

Audit records are useful for reviewing who changed OpenShift AI Operator
configuration. The official chapter focuses on DSC and DSCI custom resources.

For this repo:

- Use audit records for governance and change review, not as the primary
  deployment validation mechanism.
- Do not change OpenShift audit policy casually. If full changed-resource
  content is needed, document why `WriteRequestBodies` or a broader profile is
  required.
- Check cluster type before relying on audit availability. Standard OpenShift
  configurations enable audit logging by default; Red Hat OpenShift Service on
  AWS has different default behavior called out by Red Hat docs.
- Store collected audit excerpts outside the repo unless they are sanitized and
  intentionally committed as documentation evidence.

## Workflow

1. Confirm the active baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/official-doc-extraction.md`.
3. Decide whether the task is:
   - persistent GitOps logger configuration
   - temporary live troubleshooting
   - readonly log viewing
   - audit-record review
4. For logger configuration, verify the active DSCI schema with
   `oc explain dscinitialization.spec.devFlags`.
5. For audit review, confirm cluster-admin access and audit log availability.
6. Use `examples/operator-log-and-audit-commands.md` for command patterns.
7. Validate with `references/validation-checklist.md`.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
- `examples/operator-log-and-audit-commands.md`
