---
name: rhoai-update-channels
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhoai
  docs-version: "3.5"
  skill-group: "RHOAI Platform"
description: >
  Use when reviewing or changing the Red Hat OpenShift AI Operator update
  channel or approval mode: spec.channel stable-3.5 and installPlanApproval
  Automatic on the rhods-operator Subscription in
  gitops/stages/010-openshift-ai-platform-foundation/010-rhoai-operator/, the
  channel and minimum version enforced by
  scripts/platform/check-operator-policy.py, the doc map RHOAI version, and
  planning a minor upgrade (for example 3.5 to 3.6). Do NOT use for the
  install objects themselves (use rhoai-self-managed-installation), DSC
  component changes (use rhoai-dsci-dsc-configuration), or support posture of
  features (use rhoai-release-and-support-posture).
---

# RHOAI update channels

Thin skill: repo decisions and pitfalls here, product behaviour in the linked
OpenShift AI 3.5 sections. Detailed record:
`gitops/stages/010-openshift-ai-platform-foundation/010-rhoai-operator/README.md`.

## When to use

- A change touches `spec.channel` or `installPlanApproval` in
  `gitops/stages/010-openshift-ai-platform-foundation/010-rhoai-operator/subscription.yaml`.
- A change touches the `rhods-operator` entries in `scripts/platform/check-operator-policy.py`.
- The next RHOAI minor is planned, or `deploy.sh` refuses the catalog.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| Version-pinned `stable-3.5` channel (not rolling `stable` or `fast`), so a minor upgrade is a reviewed Git change | `010-rhoai-operator/subscription.yaml` | [Update channels][channels] |
| `installPlanApproval: Automatic`: z-streams within 3.5 install without review; the CLI example sets no approval mode (recorded as a justified deviation) | `010-rhoai-operator/subscription.yaml` | [Install the Operator by using the CLI][op-cli] |
| Fail-closed policy: channel must be `stable-3.5`, installed version at least `3.5.1` and inside the 3.5 minor; no `startingCSV` | `scripts/platform/check-operator-policy.py` (`channels`, `minimum`) | [Update channels][channels] |
| Product docs version for every `rhoai-*` skill follows the channel's minor | `.agents/references/red-hat-doc-map.yaml` (`products.rhoai.docs_version`) | n/a (repo convention) |

## Procedure

1. Read the [Update channels][channels] table for the target channel's support
   window and cadence; check the target minor's release notes.
2. Change the channel in `subscription.yaml`, the `rhods-operator` channel and
   minimum in `check-operator-policy.py`, and the doc map `docs_version` in
   one change; then re-point the `rhoai-*` skills
   (`project-rhoai-doc-chapter-skill-authoring`).
3. Deploy and validate:
   `./stages/010-openshift-ai-platform-foundation/deploy.sh`, then
   `./stages/010-openshift-ai-platform-foundation/validate.sh` and each later
   stage's `validate.sh`.
4. By hand, after the OpenShift safety guard in `AGENTS.md`:

   ```bash
   oc get packagemanifest rhods-operator -n openshift-marketplace \
     -o jsonpath='{range .status.channels[*]}{.name}{" "}{.currentCSV}{"\n"}{end}'
   python3 scripts/platform/check-operator-policy.py gitops/stages/010-openshift-ai-platform-foundation --verify
   ```

## Pitfalls

- Do not select the legacy `embedded` or `beta` channels; `alpha` is early
  access only ([Update channels][channels]).
- A channel only changes what OLM offers; DSC component patches that need a new
  schema must wait until the new CSV has succeeded.
- After an Automatic update, hooks that wait on a fixed CSV name hang:
  `docs/TROUBLESHOOTING.md#stage-020-sync-hangs-on-job-enable-dsc-kueue-after-an-operator-update`.
- Vanished CSV after a catalog change:
  `docs/TROUBLESHOOTING.md#operator-subscription-claims-a-csv-that-no-longer-exists`.

## Official documentation (RHOAI 3.5)

| Topic | Section |
|---|---|
| Channel types, support windows, legacy channels | [Update channels][channels] |
| Subscription fields in the CLI install | [Install the Operator by using the CLI][op-cli] |
| Web console install (channel and approval choice) | [Install the Operator by using the web console][op-web] |

Support lifecycle: <https://access.redhat.com/support/policy/updates/rhoai-sm/lifecycle>.

## Related skills

`rhoai-self-managed-installation`, `rhoai-release-and-support-posture`,
`rhoai-dsci-dsc-configuration`, `rhoai-uninstallation`, `ocp-gitops-operator`.

[channels]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/installing_and_uninstalling_openshift_ai_self-managed/index#understanding-update-channels_install
[op-cli]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/installing_and_uninstalling_openshift_ai_self-managed/index#installing-openshift-ai-operator-using-cli_operator-install
[op-web]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/installing_and_uninstalling_openshift_ai_self-managed/index#installing-openshift-ai-operator-using-web-console_operator-install
