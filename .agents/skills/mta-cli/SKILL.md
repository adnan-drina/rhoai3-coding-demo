---
name: mta-cli
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: mta
  docs-version: "8.3"
  skill-group: "Application Modernization"
description: >
  Use when running or reviewing MTA command-line analysis in this demo: the
  digest-locked mta-cli 8.3.0 in the Stage 070 workspace image, the Stage 130
  scan-with-mta analyze invocation (targets, custom rules with the canary, no
  --source, containerless Java 21), the kantra fallback and its provenance
  receipt, Hub profiles from a workspace, and analysis report review. Do NOT
  use for writing rules (use mta-rules), Hub UI or native Agents (use mta-ui),
  the operator install (use mta-install), or the IDE extension (use
  mta-vscode).
---

# MTA CLI

Thin skill: repo decisions and pitfalls here, command reference in the linked
MTA 8.3 CLI guide. Repo sources: `stages/070-advanced-app-platform/workspace-image/`
and the Stage 130 scaffold skill
`stages/130-ai-autonomous-migration/scaffold-repo/quarkus-migration-scaffold/.hermes/skills/analysis/scan-with-mta/`.

## When to use

- A workspace analysis fails, falls back to kantra, or its receipt is not
  admissible.
- The workspace image's MTA CLI or Java runtime changes.
- Someone adds an `analyze` option, a target, or a Hub profile to a workflow.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| `mta-cli` 8.3.0 at `/opt/mta-cli` (symlinked to `/usr/local/bin`), archive and binary SHA-256 locked; `MTA_CLI_HOME=/opt/mta-cli` | `stages/070-advanced-app-platform/workspace-image/Dockerfile`, `artifacts.lock.json` | [Install the CLI from a .zip][zip] |
| Image check proves hashes, the Java external provider, the analyzer bundle, `mta-cli version` and Java 21 | `stages/070-advanced-app-platform/workspace-image/Dockerfile` (the former checker `verify-image.py` is in git history at `82092e01`) | — |
| Containerless Java analysis on Java 21 (the analyzer bundle wedges on 17) | `.../scan-with-mta/scripts/mta-analyze-legacy.sh` | [Containerless mode][containerless] |
| Migration workspaces set `JVM_MAX_MEM=8G` (below the 12Gi container limit), `HUB_URL` from the template, `HUB_INSECURE=false` | `gitops/stages/070-advanced-app-platform/070-rhdh/templates/app-migration/skeleton/devfile.yaml` | [Containerless mode][containerless] |
| Invocation: `analyze --input <frozen copy> --output … --target <each> --rules <custom ruleset> --json-output --overwrite`; never `--source` | `.../scan-with-mta/scripts/mta-analyze-legacy.sh` | [analyze options][flags] |
| Targets come from `migration.yaml` `analysis.targets`; the custom ruleset carries a canary rule that must fire | `.../.hermes/planning/mta-rules/rhoai3-canary.yaml` | see `mta-rules` |
| Community kantra is a provisional fallback only: receipt `provenance: kantra-fallback` is non-admissible | `.../scan-with-mta/scripts/emit-mta-receipt.py`, `.agents/rules/ensure-cli-capability.md` | — |
| Workspaces get the Hub URL from ConfigMap `mta-hub-config` (`MTA_HUB_URL`); TLS verification stays on | `gitops/stages/070-advanced-app-platform/070-mta/jobs/mta-hub-workspace-config.yaml` | [Connect the CLI to the Hub][hub] |

## Procedure

1. Change the CLI only through the workspace image lock and verifier; the
   operator (8.3.1) and the workspace CLI (8.3.0) are qualified separately
   (`docs/OPERATIONS.md#stage-070--mta-mta-component`).
2. In a workspace, prove usability, not presence:

   ```bash
   mta-cli version
   readlink -f "$(command -v mta-cli)"   # expect /opt/mta-cli/mta-cli
   ```

   The former image checker `verify-image.py` that proved the full contract
   at build time was retired; its last version is in git history at `82092e01`.

3. Stage 130 analysis runs through the scaffold scripts, never by hand-built
   argv; check the receipt in `evidence/producers/mta.json`
   (`provenance`, `admissible`, `binary_realpath`).
4. Static checks: `./stages/130-ai-autonomous-migration/validate.sh` and
   the scaffold tests under `scan-with-mta/scripts/*.test.py`.

## Pitfalls

- An executable file or version string is not analyzer qualification; a
  shipped non-executable ruleset fixture once pushed `ensure_cli` to kantra:
  `docs/TROUBLESHOOTING.md#stage-130-mta-receipt-is-kantra-fallback-though-overlay-mta-cli-is-821`.
- `--source` narrows rule selection and excluded the custom rules; the
  canary then reports `CANARY_MISSING`.
- `--overwrite` empties the output directory when the analyzer starts; keep
  receipts outside it.
- Deprecated commands still exist but have replacements; check
  [Deprecated commands][deprecated] before scripting one.
- Image, CLI and VSIX versions drift independently; see
  `docs/TROUBLESHOOTING.md#stage-070-workspace-tools-or-mta-ai-are-unavailable`.

## Official documentation (MTA 8.3)

| Topic | Section |
|---|---|
| Install | [.zip install][zip], [Disconnected][disc] |
| Commands | [Command structure][structure], [Deprecated commands][deprecated] |
| Java analysis | [Single application][single], [Containerless mode][containerless], [analyze options][flags] |
| Other languages | [Provider and rules options][provider] |
| Hub profiles | [Connect to the Hub][hub], [Analyze with a profile][profile] |
| Reports and known issues | [Report sections][report], [Issues and incidents][incidents], [Known issues][known] |
| Transformation (not used) | [OpenRewrite transformation][transform] |

## Related skills

`mta-rules`, `mta-ui`, `mta-vscode`, `mta-release-notes`, `manage-devspaces`.

[zip]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/installing_the_migration_toolkit_for_applications/index#installing-cli-zip_installing-mta-cli
[disc]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/installing_the_migration_toolkit_for_applications/index#installing-mta-disconnected-environment_installing-mta-cli
[structure]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/using_the_migration_toolkit_for_applications_command-line_interface/index#cli-command-structure_about-the-command-line-tool
[deprecated]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/using_the_migration_toolkit_for_applications_command-line_interface/index#deprecated-commands-and-options_about-the-command-line-tool
[single]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/using_the_migration_toolkit_for_applications_command-line_interface/index#analyzing-single-app-wth-mta-cli_analyzing-applications-mta-cli
[containerless]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/using_the_migration_toolkit_for_applications_command-line_interface/index#running-the-containerless-mta-cli_analyzing-applications-mta-cli
[flags]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/using_the_migration_toolkit_for_applications_command-line_interface/index#mta-cli-analyze-flags_analyzing-applications-mta-cli
[provider]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/using_the_migration_toolkit_for_applications_command-line_interface/index#provider-and-rules-command-options_analyzing-nonjava-applications
[hub]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/using_the_migration_toolkit_for_applications_command-line_interface/index#connect-cli-hub_analyzing-apps-profiles
[profile]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/using_the_migration_toolkit_for_applications_command-line_interface/index#analyzing-app-with-profile_analyzing-apps-profiles
[report]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/using_the_migration_toolkit_for_applications_command-line_interface/index#analysis-report-sections_reviewing-analysis-reports
[incidents]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/using_the_migration_toolkit_for_applications_command-line_interface/index#reviewing-analysis-issues-and-incidents_reviewing-analysis-reports
[known]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/using_the_migration_toolkit_for_applications_command-line_interface/index#cli-known-issues_cli-guide
[transform]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/using_the_migration_toolkit_for_applications_command-line_interface/index#transforming-application-source-code_performing-transformation
