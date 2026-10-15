---
name: ocp-lightspeed-install
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: ocp_lightspeed
  docs-version: "1.0"
  skill-group: "OpenShift Platform"
description: >
  Use when asked to install, reinstall, or take ownership of the OpenShift
  Lightspeed Operator on the demo cluster, or to decide whether Lightspeed
  should move into Git. Do NOT use for OLSConfig and provider settings (use
  ocp-lightspeed-configure) or for an operator that is installed but unhealthy
  (use ocp-lightspeed-troubleshoot).
---

# OpenShift Lightspeed installation

Thin skill: repo decisions here, installation steps in the linked sections.

## When to use

- A fresh cluster lacks Lightspeed, or someone proposes managing it in Git.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| The repo does not install Lightspeed; the environment provisioner does (channel `stable`, Automatic approval) | `docs/OPERATIONS.md` (Fresh environment baseline) | [How Operators are installed][operators] |
| The console plugin is enabled through the Git-owned Console plugin list, so a reinstall needs no console patch | `gitops/stages/010-openshift-ai-platform-foundation/console-observability/console-plugins.yaml` | [Install from the software catalog][catalog] |
| Moving Lightspeed into Git is not planned; it would need a stage owner, a Subscription and a doc-map `pin` replacing `pin.none` | — | [Supported product subscriptions][subs] |

## Procedure

1. Do not install or remove the operator from this repo; route a missing or
   broken add-on to the provisioner (`docs/TROUBLESHOOTING.md`, "A fresh
   cluster is available but the baseline has exceptions").
2. If that decision changes, author a GitOps component per
   `.agents/rules/gitops.md`, follow the linked install section, then pin the
   version in the doc map.

## Pitfalls

- Never patch the cluster Console `spec.plugins` by hand; Stage 010 owns that
  list by server-side apply.
- The operator is listed only on supported architectures; see
  `ocp-lightspeed-troubleshoot`.

## Official documentation (OpenShift Lightspeed, "1.0" set)

| Topic | Section |
|---|---|
| LLM choice before install | [Large language model overview][llm] |
| Subscriptions | [Supported product subscriptions][subs] |
| Operator install | [From OperatorHub][hub], [from the software catalog][catalog] |

## Related skills

`ocp-lightspeed-about`, `ocp-lightspeed-configure`, `ocp-gitops-operator`,
`ocp-web-console`.

[llm]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html-single/install/index#ols-large-language-model-overview_ols-installing-openshift-lightspeed
[subs]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html-single/install/index#about-subscription-requirements_ols-installing-openshift-lightspeed
[operators]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html-single/install/index#ols-about-adding-operators-to-a-cluster_ols-installing-openshift-lightspeed
[hub]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html-single/install/index#ols-installing-operator-from-operatorhub_ols-installing-openshift-lightspeed
[catalog]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html-single/install/index#ols-installing-operator-from-software-catalog_ols-installing-openshift-lightspeed
