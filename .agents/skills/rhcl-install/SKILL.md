---
name: rhcl-install
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhcl
  docs-version: "1.4"
  skill-group: "Connectivity Link"
description: >
  Use when reviewing or changing how this demo installs Red Hat Connectivity
  Link for MaaS: the rhcl-operator, authorino-operator, limitador-operator and
  dns-operator Subscriptions, the servicemeshoperator3 Subscription, the
  Kuadrant and Authorino instances, operator resource overrides, and install
  verification. Do NOT use for upgrades between versions (use rhcl-update),
  policies (use rhcl-configure), or the MCP gateway (use rhcl-install-mcp).
---

# Connectivity Link install

Thin skill: repo decisions and pitfalls here, product procedure in the linked
Connectivity Link 1.4 sections. Detailed record:
`gitops/stages/040-governed-models-as-a-service/040-maas-operators/README.md`.

## When to use

- A change touches `gitops/stages/040-governed-models-as-a-service/040-maas-operators/rhcl/`
  or `.../gateway-governance/governance/`.
- Stage 040 install fails before the MaaS Gateway is ready.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| `rhcl-operator` from `redhat-operators`, channel `stable`, Automatic, no `startingCSV`, in `openshift-operators` (global OperatorGroup) | `040-maas-operators/rhcl/rhcl-operator-subscription.yaml` | [Install from the CLI][install-cli] |
| Authorino, Limitador and DNS operators declared as explicit Subscriptions on `stable` so their channel is reviewed | `040-maas-operators/rhcl/*-subscription.yaml` | [Install from the CLI][install-cli] (verification lists all four operators) |
| Qualified minima: rhcl 1.4.3, authorino 1.4.3, limitador 1.4.2, dns 1.4.2; other channels refused | `scripts/platform/check-operator-policy.py` | [Release notes][relnotes] (1.4.0 deprecated; use 1.4.1+) |
| `servicemeshoperator3` on `stable-3.4`, kept for the Istio CRDs (ServiceEntry, DestinationRule, WasmPlugin, EnvoyFilter, Telemetry); no `Istio` CR | `040-maas-operators/rhcl/servicemeshoperator3-subscription.yaml` | [Required platforms and components][install-req] |
| Kuadrant operator override: `AUTH_SERVICE_TIMEOUT=2s`, requests 500m/512Mi, limits 2 CPU/1Gi via Subscription `config` | `040-maas-operators/rhcl/rhcl-operator-subscription.yaml` | not documented in the install guide (recorded as a Gap in the README) |
| `Kuadrant` in `kuadrant-system` with `spec.observability.enable: true`; Authorino with a TLS listener using a service serving certificate | `040-gateway-governance/governance/kuadrant.yaml`, `authorino.yaml` | [Install from the CLI][install-cli]; see `rhoai-maas-governance` for the Authorino TLS requirement |

## Procedure

1. Change Subscriptions in Git only; keep the channel and minimum in
   `check-operator-policy.py` consistent with the doc map
   (`python3 scripts/shared/check-doc-links.py`).
2. Deploy and validate through the stage scripts:
   `./stages/040-governed-models-as-a-service/deploy.sh`, then
   `./stages/040-governed-models-as-a-service/validate.sh`.
3. By hand, after the OpenShift safety guard in `AGENTS.md`:

   ```bash
   oc get subscription rhcl-operator authorino-operator limitador-operator dns-operator servicemeshoperator3 \
     -n openshift-operators -o custom-columns=NAME:.metadata.name,CHANNEL:.spec.channel,CSV:.status.installedCSV
   oc wait kuadrant/kuadrant --for=condition=Ready=true -n kuadrant-system --timeout=300s
   ```

## Pitfalls

- `openshift-operators` is shared: an InstallPlan there can carry the whole
  Kuadrant family. Never approve a foreign InstallPlan by hand; the repo uses
  Automatic approval gated by the operator policy.
- Kuadrant controller probe timeouts under CPU throttling: see
  `docs/TROUBLESHOOTING.md#kuadrant-operator-controller-restarts-until-probes-time-out`.
- The guide's web-console path creates its own OperatorGroup; the repo relies
  on the existing global one in `openshift-operators`.

## Official documentation (Connectivity Link 1.4)

| Topic | Section |
|---|---|
| Platforms, prerequisites | [Required platforms and components][install-req], [Prerequisites for other components][install-opt] |
| CLI install and verification | [Install from the CLI][install-cli] |
| Istio as gateway controller (not used) | [Install with Istio][install-istio] |
| Disconnected install (not used) | [Install in a disconnected environment][install-disc] |
| Version status | [Release notes][relnotes] |

## Related skills

`rhcl-update`, `rhcl-configure`, `rhoai-maas-governance`, `ocp-ingress-gateway-routes`.

[install-req]: https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/install_connectivity_link/index#rhcl-required-platforms-components_install-on-ocp
[install-opt]: https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/install_connectivity_link/index#rhcl-optional-components_install-on-ocp
[install-cli]: https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/install_connectivity_link/index#proc-install-on-ocp-cmd-cio_install-on-ocp
[install-istio]: https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/install_connectivity_link/index#proc-install-on-ocp-cmd-istio_install-on-ocp
[install-disc]: https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/install_connectivity_link/index#rhcl-install-disconnected
[relnotes]: https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/release_notes/index#rhcl-relnotes-about_rhcl-release-notes
