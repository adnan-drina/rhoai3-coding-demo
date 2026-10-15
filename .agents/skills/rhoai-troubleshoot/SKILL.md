---
name: rhoai-troubleshoot
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhoai
  docs-version: "3.5"
  skill-group: "Demo Environment"
description: >
  Diagnose and fix problems in this RHOAI 3.5 demo. Use when a stage
  deploy.sh or validate.sh fails, pods are CrashLoopBackOff, Pending, Error or
  ImagePullBackOff, an Argo CD Application is OutOfSync, Degraded or stuck on
  a hook, an operator CSV is not Succeeded, GPU nodes do not join, a model is
  not Ready, or the user asks "why isn't X working?" for a demo component.
  Do NOT use for scaling or parking resources (use manage-resources), GPU
  resume (use resume-gpu-demo), or RHOAI operator install failures in depth
  (use rhoai-installation-troubleshooting).
---

# RHOAI Troubleshooting

Repo-specific workflow for the demo on OpenShift AI 3.5 and OpenShift 4.22.
The knowledge base is `docs/TROUBLESHOOTING.md`; this skill is the procedure
around it. Command list: `references/diagnostic-commands.md`; symptom index:
`references/diagnostic-patterns.md`.

## When to use

- A stage script fails or reports warnings.
- Argo CD shows OutOfSync, Degraded, ComparisonError or a stuck operation.
- Pods, operators, GPU nodes, models, MaaS or the playground misbehave.

## Rules

- **Never guess.** Every diagnosis rests on observed cluster state, a repo
  file, or an official section of the versions in
  `.agents/references/red-hat-doc-map.yaml`.
- Before any `oc` command: `load_env` and `check_oc_logged_in` from
  `scripts/shared/lib.sh` (OpenShift safety guard in `AGENTS.md`). Diagnosis
  is read-only.
- Fix in Git and redeploy with the stage `deploy.sh`; do not patch live
  objects that Argo CD owns, and never edit a delegated field (DSC,
  `odh-dashboard-config`) by hand.
- Keep demo security simple (`.agents/rules/env.md`); record a security
  finding instead of adding hardening during a fix.

## Procedure

1. Run the failing stage's validation; note the first failing check:

   ```bash
   ./stages/<NNN-name>/validate.sh
   ./scripts/platform/validate-stage-flow.sh --live
   ```

2. Find the owning component: `python3 scripts/shared/stage_apps.py names <NNN>`,
   then read its README under `gitops/stages/<stage>/<application name>/README.md`
   (Validation, Alignment with official guidance).
3. Gather state with `references/diagnostic-commands.md` for that component.
4. Match the symptom in `references/diagnostic-patterns.md` and
   `docs/TROUBLESHOOTING.md`; for product behavior use the product skill of
   the area (stage skill map in `AGENTS.md`).
5. Apply the smallest fix in Git, publish, redeploy the stage, re-run
   `validate.sh`.
6. A new issue gets a `docs/TROUBLESHOOTING.md` entry (symptom, cause,
   diagnostic commands, recovery). Stage READMEs keep selection rationale,
   not failure stories. A product workaround also goes to `BACKLOG.md`.

## Pitfalls

- Argo CD can report `Synced` at a new SHA with a stale render; compare the
  rendered manifests before trusting it
  (`docs/TROUBLESHOOTING.md#argo-cd-reports-synced-but-new-manifests-are-missing`).
- A manual sync can skip Sync hooks; enablement Jobs then never run
  (`docs/TROUBLESHOOTING.md#manually-triggered-sync-finishes-in-seconds-and-skips-hooks`).
- Removing a pointer from `010-rhoai-platform` `ignoreDifferences` restores
  the Git value `Removed` and uninstalls that component.
- With GPU MachineSets at 0, model, evaluation and serving alerts fail by
  design; check `resume-gpu-demo` before debugging serving.
- Stage 130 dest Hermes issues follow the Stage 130 rules listed in
  `AGENTS.md`, not this skill alone.

## Escalation

If one diagnostic cycle does not resolve it: report what was tried, the exact
errors and `oc` output, what could not be validated, and the next manual
checks. Say "Not validated against a live cluster" when no cluster was used.

## Official documentation (OpenShift AI 3.5)

| Area | Book |
|---|---|
| Known issues | [Release notes][relnotes] |
| Install, components | [Installing and uninstalling][install] |
| Serving | [Deploying models][deploying] |
| MaaS | [Govern LLM access with MaaS][maas] |
| Pipelines | [Working with AI pipelines][pipelines] |

## Related skills

`rhoai-installation-troubleshooting`, `inspect-cluster`, `validate-demo-step`,
`manage-resources`, `resume-gpu-demo`, `review-gitops-change`,
`workaround-review`.

[relnotes]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/release_notes/index
[install]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/installing_and_uninstalling_openshift_ai_self-managed/index
[deploying]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/deploying_models/index
[maas]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/govern_llm_access_with_models-as-a-service/index
[pipelines]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_ai_pipelines/index
