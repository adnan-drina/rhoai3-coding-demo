---
name: rhdh-release-notes
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhdh
  docs-version: "1.10"
  skill-group: "Developer Hub"
description: >
  Use when checking what Red Hat Developer Hub 1.10 release notes say about a
  feature this demo depends on: fixed issues per z-stream (1.10.0 to 1.10.5),
  Technology and Developer Preview status, deprecated and removed features
  (embedded Tekton and Argo CD wrappers, floating action button), and known
  issues before reporting a bug. Do NOT use for product concepts (use
  rhdh-about), installing (use rhdh-install-ocp), upgrading (use rhdh-upgrade),
  or preview feature details (use rhdh-preview-features).
---

# Developer Hub release notes

Thin skill: which release-note facts the repo depends on; the notes
themselves are linked, not copied. Deployed version: `rhdh-operator.v1.10.5`
(`gitops/stages/070-advanced-app-platform/070-rhdh/rhdh-operator/subscription.yaml`).

## When to use

- Before a z-stream or minor upgrade (with `rhdh-upgrade`).
- A plugin, header or sign-in behaves unexpectedly and may be a known issue.
- Deciding whether a feature is GA, Technology Preview or Developer Preview.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| Tekton and Argo CD plugins are loaded as digest-pinned `oci://` packages, because their embedded wrappers were removed and support moved to Community | `gitops/stages/070-advanced-app-platform/070-rhdh/rhdh-instance/dynamic-plugins-configmap.yaml` | [Removed features][removed] |
| The global header (not the deprecated floating action button) carries the demo tiles | `gitops/stages/070-advanced-app-platform/070-rhdh/rhdh-instance/app-config-configmap.yaml` | [Deprecated features][deprecated] |
| OIDC against Red Hat build of Keycloak is a supported provider (not on the deprecated community provider list) | same app-config | [Deprecated features][deprecated] |
| Developer Lightspeed is installed by default and needs a configured LLM; the repo neither configures nor disables it (Gap in the component README) | `gitops/stages/070-advanced-app-platform/070-rhdh/README.md` | see `rhdh-developer-lightspeed` |

## Procedure

1. Read [Fixed issues][fixed] for each z-stream between the installed and the
   target version, then [Known issues][known] and [Removed features][removed].
2. Check each Technology or Developer Preview item the repo would rely on
   ([TP][tp], [DP][dp]) and record the posture in the component README
   "Alignment with official guidance" table.
3. Confirm the installed version read-only after the safety guard in `AGENTS.md`:

   ```bash
   oc get csv -n rhdh-operator -o custom-columns=NAME:.metadata.name,PHASE:.status.phase
   ```

## Pitfalls

- Support status of a plugin can change between z-streams; quote the release
  note section, not a skill, when recording a support claim.
- Bulk Import and Orchestrator known issues do not affect this repo (neither
  is enabled).
- Fixed security issues are listed by advisory; check them before deferring
  a z-stream.

## Official documentation (Developer Hub 1.10)

| Topic | Section |
|---|---|
| New features | [New features and enhancements][new] |
| Preview posture | [Technology Preview][tp], [Developer Preview][dp] |
| Deprecated, removed | [Deprecated features][deprecated], [Removed features][removed] |
| Issues | [Known issues][known], [Fixed issues][fixed] ([1.10.5][fix-1105]), [Security fixes][sec] |

## Related skills

`rhdh-upgrade`, `rhdh-about`, `rhdh-preview-features`,
`rhdh-dynamic-plugins-install`, `rhdh-developer-lightspeed`.

[new]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/red_hat_developer_hub_release_notes/index#new-features-and-enhancements
[tp]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/red_hat_developer_hub_release_notes/index#technology-preview-features
[dp]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/red_hat_developer_hub_release_notes/index#developer-preview-features
[deprecated]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/red_hat_developer_hub_release_notes/index#deprecated-features
[removed]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/red_hat_developer_hub_release_notes/index#removed-features
[known]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/red_hat_developer_hub_release_notes/index#known-issues
[fixed]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/red_hat_developer_hub_release_notes/index#fixed-issues
[fix-1105]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/red_hat_developer_hub_release_notes/index#fixed-issues-in-1-10-5
[sec]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/red_hat_developer_hub_release_notes/index#fixed-security-issues
