---
name: rhcl-update
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhcl
  docs-version: "1.4"
  skill-group: "Connectivity Link"
description: >
  Use when updating Red Hat Connectivity Link in this demo: z-stream updates on
  the stable-1.4 channel, raising the qualified minimum in the operator policy,
  moving to a new minor, checking supported OpenShift / Service Mesh /
  cert-manager versions, and the Gateway API CRD constraint. Also use when old
  guidance says to pin 1.3.z or block 1.4 — that posture is retired. Do NOT use
  for first install (use rhcl-install) or policy changes (use rhcl-configure).
---

# Connectivity Link update

Thin skill: repo decisions and pitfalls here, product procedure in the linked
Connectivity Link 1.4 sections.

## When to use

- A new Connectivity Link z-stream or minor is available.
- A wasm-shim or gateway fix you need ships in a newer release.
- Someone cites the old "stay on 1.3.4" rule.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| Channel `stable-1.4`, Automatic approval, no `startingCSV`: 1.4 z-streams arrive without a Git change | `gitops/stages/040-governed-models-as-a-service/040-maas-operators/rhcl/rhcl-operator-subscription.yaml` | [Update with the web console][update-console] |
| The qualified minor line and minimum (rhcl 1.4.4) live in the operator policy, which refuses other channels and older or other-minor releases | `check_operator_policy` in `scripts/lib.sh` (`minimum`, `channels`) | [Release notes][relnotes] |
| The doc map's `products.rhcl.docs_version` must equal that minor; the checker enforces it | `.agents/references/red-hat-doc-map.yaml` | — |
| The 1.3.4 pin with Manual approval (2026-07) is retired; its rollback is historical only | `docs/TROUBLESHOOTING.md#maas-gateway-times-out-on-every-path-rhcl-14x-drift` | [Release notes][relnotes] (1.4.0 deprecated; install or upgrade to 1.4.1+) |

## Procedure (new minor)

1. Read the target [release notes][relnotes] and [supported
   configurations][configs]; confirm OpenShift, Service Mesh (3.3/3.4 for 1.4)
   and cert-manager versions match the cluster.
2. In one change: update `minimum`/`channels` in `check_operator_policy`
   for rhcl, authorino, limitador and dns; set `docs_version` in the doc map;
   run `python3 .agents/tools/check-doc-links.py` and fix every `rhcl`
   finding (skills, READMEs, book slugs and anchors — they changed between
   1.3 and 1.4).
3. Re-test the MaaS paths that depend on wasm-shim behavior (metering,
   streaming, error bodies) with `./stages/040-governed-models-as-a-service/validate.sh`
   and the `docs/TROUBLESHOOTING.md` diagnostics.
4. On a running cluster, a channel change in Git alone stops Stage 040
   `deploy.sh`: `check_operator_policy` refuses a live Subscription whose
   channel differs from Git (`Existing selected operator has incompatible
   source/channel scope`), and patching the live Subscription does not help:
   Argo CD self-heal restores the pinned revision's channel. After the change
   is on `main`, merge-patch `spec.source.targetRevision` of
   `040-maas-operators` to that commit, wait for the CSVs, move the other
   Stage 040 Applications to the same commit (`stage-apps.sh status 040`
   needs one revision and a sync operation at it; start syncs with
   `operation.sync` carrying each app's own syncOptions), then run
   `deploy.sh` and `validate.sh` (done for `stable` → `stable-1.4` on
   2026-11-10).
5. Check live after the OpenShift safety guard in `AGENTS.md`:

   ```bash
   oc get csv -n openshift-operators | grep -E 'rhcl|authorino|limitador|dns-operator'
   oc get subscription rhcl-operator -n openshift-operators -o jsonpath='{.status.installedCSV}{"\n"}'
   ```

## Pitfalls

- On OpenShift 4.19+, pre-existing Gateway API CRDs must exactly match the
  version OpenShift supports before updating ([Update to 1.4][update-proc]).
- Connectivity Link 1.4.0 is deprecated; never qualify it.
- Channel naming differs inside the 1.4 docs: the update procedure says
  `stable`, while the install guide and the 1.4.4 release notes say
  `stable-1.4`. The live catalog (2026-11-10) has `stable` at 1.4.3,
  `stable-1.4` at 1.4.4 and `stable-1.5` at 1.5.0, so the repo pins
  `stable-1.4`; a new minor is a channel change. 1.4.4 brings about 5 s of
  Authorino downtime on upgrade.
- `openshift-operators` is shared: one InstallPlan can move the whole Kuadrant
  family at once.

## Official documentation (Connectivity Link 1.4)

| Topic | Section |
|---|---|
| Supported configurations for the update | [Supported configurations][configs] |
| Update procedure | [Update with the web console][update-console], [Update to 1.4][update-proc] |
| What changed in each z-stream | [Release notes][relnotes] |

## Related skills

`rhcl-release-notes`, `rhcl-install`, `rhcl-troubleshoot`.

[configs]: https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/update_red_hat_connectivity_link/index#rhcl-supported-configs_updating-rhcl
[update-console]: https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/update_red_hat_connectivity_link/index#con-update-rhcl-with-web-console_updating-rhcl
[update-proc]: https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/update_red_hat_connectivity_link/index#proc-update-rhcl-with-web-console_updating-rhcl
[relnotes]: https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/release_notes/index#rhcl-relnotes-about_rhcl-release-notes
