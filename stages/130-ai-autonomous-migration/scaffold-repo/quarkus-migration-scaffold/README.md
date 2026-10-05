# Quarkus Migration Scaffold

Corporate Quarkus destination scaffold for AI-autonomous application
migration. Provisioned per migration by the `app-migration` golden-path
template in the platform's Developer Hub.

The workspace this repository defines contains two projects:

| Folder | Role |
|--------|------|
| `/projects/legacy` | The application being migrated — workspace-only clone of the source repository. Read-only; never cataloged, never pushed. |
| `/projects/modernized` | This repository — the Quarkus destination. Catalog-registered, CI/CD-wired (own namespace, pipeline, SonarQube gate). |

The migrated application does not exist yet — that is the point. MTA analysis
of the legacy project produces the migration's ground truth, and the
modernized service is built here against it.

Every push to `main` runs this project's own delivery pipeline with the
SonarQube quality gate.
