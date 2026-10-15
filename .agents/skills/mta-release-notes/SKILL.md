---
name: mta-release-notes
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: mta
  docs-version: "8.3"
  skill-group: "Application Modernization"
description: >
  Use when checking MTA 8.3 release posture for this demo: which z-stream is
  pinned (operator 8.3.1, workspace CLI 8.3.0, VSIX 8.3.1), Developer Preview
  vs Technology Preview status of native Agents, Lightspeed and Solution
  Server, known issues that affect the repo, and reviewing an MTA update. Do
  NOT use for installing (use mta-install), AI configuration (use
  mta-lightspeed or mta-ui), or CLI usage (use mta-cli).
---

# MTA release notes

Thin skill: the repo's version posture here, release content in the linked
MTA 8.3 release notes.

## When to use

- Reviewing an MTA operator, CLI or extension update.
- Deciding whether a feature the repo relies on is Developer Preview,
  Technology Preview or GA.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| Operator pinned to `mta-operator.v8.3.1` (Subscription `startingCSV`, approver allowlist, validator) | `gitops/stages/070-advanced-app-platform/mta/mta-operator/` | [MTA 8.3][rn83] |
| Workspace CLI 8.3.0 and VSIX 8.3.1 qualified separately from the operator | `stages/070-advanced-app-platform/workspace-image/artifacts.lock.json` | [MTA 8.3.0][rn830] |
| Native Agents treated as Developer Preview; unqualified while models are stopped | `gitops/stages/070-advanced-app-platform/mta/README.md` | [MTA agents][agents] |
| Lightspeed proxy and Solution Server treated as Technology Preview; Solution Server disabled | `mta/mta-instance/tackle.yaml` | see `mta-lightspeed` |
| `mta-ops` (PVC transfer) and BuildConfig conversion (Technology Preview) are not used | — | [mta-ops][mtaops], [Technology Preview][tp] |

## Procedure

1. Read the release notes for the target z-stream and its known issues.
2. Update the pin as one change: Subscription, approver allowlist, validator
   (see `mta-install`), then `.agents/references/red-hat-doc-map.yaml` if the
   minor changes.
3. Re-qualify the workspace CLI and VSIX separately (`mta-cli`, `mta-vscode`).

## Pitfalls

- The 8.3 release notes describe 8.3.0 only (checked 2026-10-15); the repo
  runs 8.3.1, so its fixes are not in this book. Check the Red Hat errata for
  the CSV before relying on a fix.
- The book also carries 8.0–8.2 chapters; attribute a feature to its actual
  release.
- MTA-6530 (wildcard imports miss annotation matches) affects rules that
  gate on annotations (`mta-rules`).

## Official documentation (MTA 8.3)

| Topic | Section |
|---|---|
| 8.3 | [MTA 8.3][rn83], [8.3.0][rn830], [New features][new], [Technology Preview][tp], [Known issues][known], [Fixed issues][fixed] |
| Previous minor | [MTA 8.2.1][rn821] |

## Related skills

`mta-install`, `mta-lightspeed`, `mta-ui`, `mta-cli`, `mta-rules`.

[rn83]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/release_notes/index#mta-8-3_release-notes
[rn830]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/release_notes/index#mta-8-3-0_mta-8-3
[new]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/release_notes/index#new-features-and-enhancements-8-3-0_mta-8-3-0
[agents]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/release_notes/index#mta_agents
[mtaops]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/release_notes/index#mta_ops_command_line_interface
[tp]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/release_notes/index#tech-previews-8-3-0_mta-8-3-0
[known]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/release_notes/index#known-issues-8-3-0_mta-8-3-0
[fixed]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/release_notes/index#fixed-issues-8-3-0_mta-8-3-0
[rn821]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/release_notes/index#mta-8-2-1_mta-8-2
