---
name: rhdh-dynamic-plugins-reference
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhdh
  docs-version: "1.10"
  skill-group: "Developer Hub"
description: >
  Use when checking which Developer Hub 1.10 plugins this demo enables and
  their support tier (preinstalled, GA, Technology Preview, community,
  deprecated), whether a plugin is embedded or must be pulled as an OCI
  package, and how its digest is pinned before it goes into
  dynamic-plugins-rhdh. Do NOT use for per-plugin settings (use
  rhdh-dynamic-plugins-configure), the install mechanics (use
  rhdh-dynamic-plugins-install), or Helm values (use rhdh-helm-reference).
---

# RHDH dynamic plugins reference

Thin skill: the repo's plugin inventory and tiers here, the authoritative
plugin tables in the linked Developer Hub 1.10 reference. Detailed record:
`gitops/stages/070-advanced-app-platform/rhdh/README.md` ("Plugins",
"Alignment with official guidance").

## When to use

- Before adding or replacing a plugin in
  `rhdh/rhdh-instance/dynamic-plugins-configmap.yaml`.
- Writing or reviewing a support statement about the portal's plugins.
- A plugin moves between tiers or becomes deprecated in a release note.

## Repo decisions

| Plugin in this repo (1.10 tier) | Package form in Git | Official section |
|---|---|---|
| GitLab catalog backend module, RBAC, Kubernetes backend, Topology (GA) | embedded `./dynamic-plugins/dist/...` | [GA plugins][ga] |
| GitLab scaffolder backend module, Kubernetes frontend (Technology Preview) | embedded `./dynamic-plugins/dist/...` | [Technology Preview plugins][tp] |
| Tekton (community) | `oci://ghcr.io/redhat-developer/rhdh-plugin-export-overlays/backstage-community-plugin-tekton@sha256:...` | [Community plugins][community] |
| Argo CD frontend (Community) and Roadie Argo CD backend (community) | OCI from the same registry, digest-pinned | [Community plugins][community] |

All entries live in
`gitops/stages/070-advanced-app-platform/rhdh/rhdh-instance/dynamic-plugins-configmap.yaml`;
the digest rule is tested by
`stages/070-advanced-app-platform/tests/stage070-upgrade.test.py`
(`test_argo_plugins_follow_110_oci_packaging`).

## Procedure

1. Look the plugin up in the 1.10 tables below and record its tier in the
   change description; community plugins carry community support only.
2. For an OCI package, take the documented tag form, resolve its digest with a
   registry client of your choice, and pin `@sha256:<digest>` (the product
   guide recommends digests for stability).
3. Continue with `rhdh-dynamic-plugins-install`; then run
   `./stages/070-advanced-app-platform/validate.sh --static`.

## Pitfalls

- Tekton and both Argo CD packages are community supported in 1.10, and the
  GitLab scaffolder module and Kubernetes frontend are Technology Preview; do
  not describe templates' GitLab publishing, the Kubernetes tab, CI or Argo CD
  tabs as fully supported.
- Embedded is not the same as preinstalled: none of the repo's embedded
  plugins is in the 1.10 "Preinstalled" chapter; keep each enabled explicitly
  with `disabled: false`.
- The Roadie Argo CD backend paired with the Community frontend mixes two
  plugin families, which the configuration guide does not recommend; it is a
  recorded Gap in the component README.
- Embedded package paths change between RHDH releases; re-check
  [Preinstalled plugins][pre] and [Deprecated plugins][deprecated] on every
  RHDH minor upgrade (`rhdh-upgrade`).
- Do not invent package names or OCI paths: copy them from the reference.

## Official documentation (Developer Hub 1.10)

| Topic | Section |
|---|---|
| Preinstalled (embedded) plugins | [Preinstalled dynamic plugins][pre] |
| Red Hat GA and Technology Preview | [GA plugins][ga], [Technology Preview plugins][tp] |
| Community supported (Tekton, Argo CD) | [Community plugins][community] |
| Deprecated and other installable plugins | [Deprecated][deprecated], [Other installable][other] |

## Related skills

`rhdh-dynamic-plugins-install`, `rhdh-dynamic-plugins-configure`,
`rhdh-release-notes`, `rhdh-upgrade`.

[pre]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/dynamic_plugins_reference/index#preinstalled-dynamic-plugins_dynamic-plugins-reference
[ga]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/dynamic_plugins_reference/index#ga-plugins_dynamic-plugins-reference
[tp]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/dynamic_plugins_reference/index#technology-preview-plugins_dynamic-plugins-reference
[community]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/dynamic_plugins_reference/index#community-supported-plugins_dynamic-plugins-reference
[deprecated]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/dynamic_plugins_reference/index#deprecated-plugins_dynamic-plugins-reference
[other]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/dynamic_plugins_reference/index#other-installable-plugins_dynamic-plugins-reference
