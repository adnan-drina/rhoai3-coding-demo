---
name: ocp-lightspeed-release-notes
metadata:
  author: rhoai3-coding-demo
  version: 3.0.0
  product: ocp_lightspeed
  docs-version: "2.0"
  skill-group: "OpenShift Platform"
description: >
  Use when checking which OpenShift Lightspeed release the cluster runs, what
  changed between 2.0.x and 1.1.x z-streams, their known issues, or whether the doc
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
| No Git pin: the subscription belongs to the provisioner; observed versions are recorded with dates (1.1.4 on 2026-10-05, 1.1.5 on 2026-10-15, 2.0.0 on 2026-10-27 and 2026-11-10, 2.0.1 on 2026-11-12) | `docs/OPERATIONS.md`, `.agents/references/red-hat-doc-map.yaml` | [Release notes][relnotes] |
| The "2.0" documentation set is used for the 2.0.x operator; Red Hat published it on 2026-11-12, and its notes run from 1.0 through 2.0.1. Before that the only set was labelled "1.0" | `.agents/references/red-hat-doc-map.yaml` | [Version 2.0][v20] |
| Autonomous agents (2.0, Technology Preview, OpenShift 5.0 only) are not deployed: the cluster runs OpenShift 4.22 | `040-openshift-lightspeed/olsconfig.yaml` | [Version 2.0][v20] |

## Procedure

1. Read the installed CSV version (read-only, after the OpenShift safety guard
   in `AGENTS.md`), then the matching release-notes section below.
2. If Red Hat publishes another documentation set (for example `/2.1/`),
   follow `route_update_rules.when_upgrading_product` in the doc map and
   `project-red-hat-doc-skill-authoring`.

## Pitfalls

- 2.0's [known issue][v20-known]: the tool classifier can fail a large tool
  result as malicious (workaround: turn off tool inspection in the
  OLSConfig). 2.0.1 resolves tool-result inspection regressions and says why a
  result is rejected; 1.1.5 had [its own inspection issue][v115-known].
- 2.0.1 exposes the OpenShift MCP server's mutating and write tools when
  introspection is enabled, controlled by the `disable_destructive` flag;
  execution stays subject to the asking user's Kubernetes permissions. The
  demo's OLSConfig enables introspection, so these tools are reachable; the
  2.0 [security defaults][security-defaults] require human approval for
  non-read tool operations (`spec.ols.toolsApprovalConfig`).
- 2.0.1's Offline Knowledge Portal image has no OpenShift 5 documentation yet.
- Each z-stream has its own known-issues list; read the one for the installed
  version, not only the newest.

## Official documentation (OpenShift Lightspeed, "2.0" set)

| Topic | Section |
|---|---|
| All releases (1.0 to 2.0.1) | [Release notes][relnotes] |
| 2.0.1 | [Version 2.0.1][v201] |
| 2.0 | [Version 2.0][v20], [its known issues][v20-known] |
| 1.1.5 | [Version 1.1.5][v115], [its known issues][v115-known] |
| 1.1.4 | [Version 1.1.4][v114], [its known issues][v114-known] |
| 1.1.3 | [Version 1.1.3][v113] |
| 1.1.2 | [Version 1.1.2][v112] |
| 1.1.1 | [Version 1.1.1][v111] |
| 1.1 | [Version 1.1][v11] |
| 1.0 | [Version 1.0][v10] |

## Related skills

`ocp-lightspeed-about`, `ocp-lightspeed-install`,
`project-red-hat-doc-skill-authoring`.

[relnotes]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/2.0/html-single/release_notes/index#ols-release-notes
[v201]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/2.0/html-single/release_notes/index#ols-2-0-1-release-notes_ols-release-notes
[v20]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/2.0/html-single/release_notes/index#ols-2-0-release-notes_ols-release-notes
[v20-known]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/2.0/html-single/release_notes/index#ols-2-0-known-issues_ols-release-notes
[v115]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/2.0/html-single/release_notes/index#ols-1-1-5-release-notes_ols-release-notes
[v115-known]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/2.0/html-single/release_notes/index#ols-1-1-5-known-issues_ols-release-notes
[v114]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/2.0/html-single/release_notes/index#ols-1-1-4-release-notes_ols-release-notes
[v114-known]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/2.0/html-single/release_notes/index#ols-1-1-4-known-issues_ols-release-notes
[v113]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/2.0/html-single/release_notes/index#ols-1-1-3-release-notes_ols-release-notes
[v112]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/2.0/html-single/release_notes/index#ols-1-1-2-release-notes_ols-release-notes
[v111]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/2.0/html-single/release_notes/index#ols-1-1-1-release-notes_ols-release-notes
[v11]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/2.0/html-single/release_notes/index#ols-1-1-release-notes_ols-release-notes
[v10]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/2.0/html-single/release_notes/index#ols-1-0-release-notes_ols-release-notes
[security-defaults]: https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/2.0/html-single/configure/index#ols-security-defaults-by-deployment-mode_ols-configuring-openshift-lightspeed
