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
  the stable channel, raising the qualified minimum in the operator policy,
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
| Channel `stable`, Automatic approval, no `startingCSV`: z-streams arrive without a Git change | `gitops/stages/040-governed-models-as-a-service/maas-operators/rhcl/rhcl-operator-subscription.yaml` | [Update with the web console][update-console] |
| The qualified minor line and minimum (rhcl 1.4.3) live in the operator policy, which refuses other channels and older or other-minor releases | `scripts/platform/check-operator-policy.py` (`minimum`, `channels`) | [Release notes][relnotes] |
| The doc map's `products.rhcl.docs_version` must equal that minor; the checker enforces it | `.agents/references/red-hat-doc-map.yaml` | — |
| The 1.3.4 pin with Manual approval (2026-07) is retired; its rollback is historical only | `docs/TROUBLESHOOTING.md#maas-gateway-times-out-on-every-path-rhcl-14x-drift` | [Release notes][relnotes] (1.4.0 deprecated; install or upgrade to 1.4.1+) |

## Procedure (new minor)

1. Read the target [release notes][relnotes] and [supported
   configurations][configs]; confirm OpenShift, Service Mesh (3.3/3.4 for 1.4)
   and cert-manager versions match the cluster.
2. In one change: update `minimum`/`channels` in `check-operator-policy.py`
   for rhcl, authorino, limitador and dns; set `docs_version` in the doc map;
   run `python3 scripts/shared/check-doc-links.py` and fix every `rhcl`
   finding (skills, READMEs, book slugs and anchors — they changed between
   1.3 and 1.4).
3. Re-test the MaaS paths that depend on wasm-shim behavior (metering,
   streaming, error bodies) with `./stages/040-governed-models-as-a-service/validate.sh`
   and the `docs/TROUBLESHOOTING.md` diagnostics.
4. Check live after the OpenShift safety guard in `AGENTS.md`:

   ```bash
   oc get csv -n openshift-operators | grep -E 'rhcl|authorino|limitador|dns-operator'
   oc get subscription rhcl-operator -n openshift-operators -o jsonpath='{.status.installedCSV}{"\n"}'
   ```

## Pitfalls

- On OpenShift 4.19+, pre-existing Gateway API CRDs must exactly match the
  version OpenShift supports before updating ([Update to 1.4][update-proc]).
- Connectivity Link 1.4.0 is deprecated; never qualify it.
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
