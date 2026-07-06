# Source Capture

## Official Sources

| Field | Value |
|-------|-------|
| Product | Migration Toolkit for Applications |
| Product version | 8.1 |
| Baseline source | `docs/PLATFORM_BASELINE.md` |
| Chapter or page title | Using the migration toolkit for applications command-line interface |
| Source URL | https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.1/html-single/using_the_migration_toolkit_for_applications_command-line_interface/index |
| Documentation category | Using the Tools |
| Capture date | 2026-07-06 |

## Captured Sections

From "Using the migration toolkit for applications command-line interface":

- Chapter 1: Introduction to the MTA command-line interface
- Chapter 2: Supported migration paths
- Chapter 3: Analyzing Java applications with MTA CLI
  - 3.1 Analyzing a single application
  - 3.2 Analyzing multiple applications (Developer Preview)
  - 3.3 Analyzing an application in containerless mode
  - 3.4 The analyze command options
- Chapter 4: Analyzing applications written in languages other than Java
  - 4.1 Analyzing for a supported language provider
  - 4.2 Analyzing for an unsupported language provider
- Chapter 5: Analyzing applications by using profiles from the MTA Hub
  - 5.1 Analyzing by using a profile (Technology Preview)
  - 5.2 The config command options
  - 5.3 A sample profile configuration
- Chapter 6: Reviewing an analysis report
  - 6.1 Accessing an analysis report
  - 6.2 Analysis report sections
  - 6.3 Reviewing issues and incidents
- Chapter 7: Performing a transformation with the MTA CLI
  - 7.1 Transforming applications source code
  - 7.2 Available OpenRewrite recipes
  - 7.3 The openrewrite command options
- Chapter 8: Generating platform assets for application deployment
  - 8.1–8.8 Discovery and generation workflows (Developer Preview)
- Chapter 9: Known issues
- Appendix A: Supported technology tags
- Appendix B: Rule story points

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

- Migration Toolkit for Applications 8.1 Installation Guide
- Migration Toolkit for Applications 8.1 Configuring and Using Red Hat Developer Lightspeed for MTA
- Migration Toolkit for Applications 8.1 Using the Web Console
- Migration Toolkit for Applications 8.1 VS Code Extension Guide
- Migration Toolkit for Applications 8.1 Configuring and Using Rules
