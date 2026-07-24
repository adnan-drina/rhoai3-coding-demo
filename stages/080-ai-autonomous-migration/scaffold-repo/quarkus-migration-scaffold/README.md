# Quarkus Migration Scaffold

Corporate Quarkus destination scaffold for AI-autonomous application
migration. Provisioned per migration by the `app-migration` golden-path
template in the platform's Developer Hub.

The workspace this repository defines contains two projects:

| Folder | Role |
|--------|------|
| `/projects/legacy` | The application being migrated — workspace-only clone of the source repository. Read-only; never cataloged, never pushed. |
| `/projects/modernized` | This repository — the Quarkus destination. Catalog-registered, CI/CD-wired (own namespace, pipeline, SonarQube gate). |

The migrated application does not exist yet — that is the point. MTA
analysis of the legacy project produces the migration's ground truth; specs
capture the observed behavior; and a coding agent (OpenCode) builds the
Quarkus-native replacement here, steered by the corporate standards in this
repository:

- `AGENTS.md` — the agent's entry point: workspace rules, workflow, commands.
- `.opencode/skills/` — migration workflow, REST conventions, test
  standards, and the MaaS-only LLM integration pattern.
- `migration.yaml` — provenance: which repository this migration started from.

## Getting started

1. Open this repository's workspace in Dev Spaces (both projects clone
   automatically; the MTA extension pack is preinstalled).
2. Run an MTA analysis of `/projects/legacy` and keep the report open.
3. Start OpenCode in `/projects/modernized` and follow the spec-driven
   migration workflow (`/speckit.specify` from the analysis + observed
   behavior, then plan, tasks, implement).

Every push to `main` runs this project's own delivery pipeline with the
SonarQube quality gate.
