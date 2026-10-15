---
name: ocp-lightspeed-release-notes
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: ocp_lightspeed
  docs-version: "1.0"
  skill-group: "OpenShift Platform"
description: >
  Use when checking which OpenShift Lightspeed release the cluster runs, what
  changed between 1.1.x z-streams, their known issues, or whether the doc
  map's documentation set still fits the installed operator. Do NOT use for
  product concepts (use ocp-lightspeed-about) or failures on the cluster (use
  ocp-lightspeed-troubleshoot).
---

# OpenShift Lightspeed release notes

Thin skill: repo facts here, release content in the linked release notes.

## When to use

- The provisioner's Automatic `stable` subscription moved the operator to a
  new z-stream and someone asks what changed.
- Reviewing whether `products.ocp_lightspeed.docs_version` in the doc map is
  still the right documentation set.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| No Git pin: the subscription belongs to the provisioner; observed versions are recorded with dates (1.1.4 on 2026-10-05, 1.1.5 on 2026-10-15) | `docs/OPERATIONS.md`, `.agents/references/red-hat-doc-map.yaml` | [Release notes][relnotes] |
| The documentation set labelled "1.0" is used for the 1.1.x operator: it is the only published set and its notes include 1.1 to 1.1.4 | `.agents/references/red-hat-doc-map.yaml` | [Version 1.1][v11] |

## Procedure

1. Read the installed CSV version (read-only, after the OpenShift safety guard
   in `AGENTS.md`), then the matching release-notes section below.
2. If Red Hat publishes another documentation set (for example `/1.1/`),
   follow `route_update_rules.when_upgrading_product` in the doc map and
   `project-red-hat-doc-skill-authoring`.

## Pitfalls

- 1.1.5 had no release-notes section on 2026-10-15; do not cite one.
- Each z-stream has its own known-issues list; read the one for the installed
  version, not only the newest.

## Official documentation (OpenShift Lightspeed, "1.0" set)

| Topic | Section |
|---|---|
| All releases | [Release notes][relnotes] |
| 1.1.4 | [Version 1.1.4][v114], [its known issues][v114-known] |
| 1.1.3 | [Version 1.1.3][v113] |
| 1.1.2 | [Version 1.1.2][v112] |
| 1.1.1 | [Version 1.1.1][v111] |
| 1.1 | [Version 1.1][v11] |
| 1.0 | [Version 1.0][v10] |

## Related skills

`ocp-lightspeed-about`, `ocp-lightspeed-install`,
`project-red-hat-doc-skill-authoring`.

[relnotes]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html-single/release_notes/index#ols-release-notes
[v114]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html-single/release_notes/index#ols-1-1-4-release-notes_ols-release-notes
[v114-known]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html-single/release_notes/index#ols-1-1-4-known-issues_ols-release-notes
[v113]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html-single/release_notes/index#ols-1-1-3-release-notes_ols-release-notes
[v112]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html-single/release_notes/index#ols-1-1-2-release-notes_ols-release-notes
[v111]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html-single/release_notes/index#ols-1-1-1-release-notes_ols-release-notes
[v11]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html-single/release_notes/index#ols-1-1-release-notes_ols-release-notes
[v10]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html-single/release_notes/index#ols-1-0-release-notes_ols-release-notes
