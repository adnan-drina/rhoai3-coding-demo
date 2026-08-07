# Source Capture

## Official Sources

| Field | Value |
|-------|-------|
| Product | Migration Toolkit for Applications |
| Product version | 8.2 |
| Baseline source | `docs/PLATFORM_BASELINE.md` |
| Chapter or page title | Using the migration toolkit for applications command-line interface |
| Source URL | https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.2/html-single/using_the_migration_toolkit_for_applications_command-line_interface/index |
| Documentation category | Using the Tools |
| Capture date | 2026-08-07 |
| Recapture note | Chapter numbers refreshed from live 8.2 CLI guide (analyzing Java apps is Ch. 4, was Ch. 3 in 8.1). Cross-checked with nested `harness-refactoring/source-analysis/mta-kantra/mta-8.2-recapture.md`. |

## Captured Sections

From "Using the migration toolkit for applications command-line interface" (MTA 8.2 TOC):

- Chapter 1: Introduction to the MTA command-line interface
- Chapter 2: Supported migration paths
- Chapter 3: *(renumbered in 8.2 — see Ch. 4 for Java analysis)*
- Chapter 4: Analyzing Java applications with MTA CLI
  - 4.1 Analyzing a single application
  - 4.2 Analyzing multiple applications (Developer Preview)
  - 4.3 Analyzing an application in containerless mode
  - 4.4 The analyze command options
- Subsequent chapters (non-Java analysis, Hub profiles, reports, transform,
  platform assets, known issues, appendices) — content largely unchanged from
  the prior 8.1 grounding; re-verify chapter numbers against the live 8.2 TOC
  before citing a chapter number in prose.

## Source Boundaries

This skill captures:

- CLI introduction and supported migration paths
- Java application analysis (single, bulk, containerless)
- Non-Java application analysis (Go, .NET, Node.js, Python)
- All `mta-cli analyze` command options
- Analysis profile sync from MTA Hub (`mta-cli config`)
- Analysis report structure (Dashboard, Issues, Dependencies, Technologies, Insights)
- Issue severity categories and story point guidelines
- Source code transformation with OpenRewrite recipes
- Cloud Foundry discovery and Helm-based deployment manifest generation
- Known issues (Podman on Windows, container runtime)
- Supported technology tags list

This skill does not capture:

- Web UI analysis workflows (separate guide)
- VS Code extension workflows (separate guide)
- IntelliJ plugin workflows (separate guide)
- AI-assisted code resolution (use mta-lightspeed)
- MTA Operator installation (separate guide)
- Custom rule authoring (separate guide)
- MTA Hub administration (separate guide)

## API Versions and CRDs

No CRDs are directly used by the CLI. The CLI interacts with:

| Component | Notes |
|-----------|-------|
| MTA Hub | REST API for profile sync (`mta-cli config login/sync`) |
| Tackle CR | Indirectly; profiles are configured in Hub which requires Tackle |

## Related Official Sources To Add Later

- Migration Toolkit for Applications 8.2 Installation Guide
- Migration Toolkit for Applications 8.2 Configuring and Using Red Hat Developer Lightspeed for MTA
- Migration Toolkit for Applications 8.2 Using the Web Console
- Migration Toolkit for Applications 8.2 VS Code Extension Guide
- Migration Toolkit for Applications 8.2 Configuring and Using Rules
