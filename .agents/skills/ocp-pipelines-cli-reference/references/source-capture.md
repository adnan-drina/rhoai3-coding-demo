# Source Capture

## Official Sources

| Field | Value |
|-------|-------|
| Product family | Red Hat OpenShift Pipelines |
| Baseline source | `docs/PLATFORM_BASELINE.md` |
| Documentation category | Reference |
| Official guide | Pipelines CLI (tkn) reference |
| Source URL | https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.22/html-single/pipelines_cli_tkn_reference/index |
| Multi-page URL | https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.22/html/pipelines_cli_tkn_reference/index |
| Capture date | 2026-07-06 |

## Captured Sections

From Pipelines CLI (tkn) reference:

- Chapter 1: Installing tkn
  - Linux (tar.gz archive: x86_64, s390x, ppc64le, aarch64)
  - Linux via RPM (RHEL 8, subscription-manager workflow)
  - Windows (zip archive)
  - macOS (tar.gz archive: x86_64, ARM)
  - Bundled executables: tkn, tkn-pac, opc
- Chapter 2: Configuring the OpenShift Pipelines tkn CLI
  - Enabling tab completion (bash, zsh)
- Chapter 3: OpenShift Pipelines tkn reference
  - Basic syntax: `tkn [command or options] [arguments]`
  - Global options: `--help, -h`
  - Utility commands: tkn, completion, version
  - Pipeline management: pipeline (delete, describe, list, logs, start)
  - Pipeline run commands: pipelinerun (cancel, delete, describe, list, logs)
  - Task management: task (delete, describe, list, start)
  - Task run commands: taskrun (cancel, delete, describe, list, logs)
  - Pipeline Resource management: resource (create, delete, describe, list)
  - Trigger management: eventlistener, triggerbinding, triggertemplate, clustertriggerbinding
  - Hub interaction: hub (downgrade, get, info, install, reinstall, search, upgrade)

## Source Boundaries

This skill covers the "Pipelines CLI (tkn) reference" guide only. It provides
CLI command syntax, flags, and usage examples for the tkn tool. It does not
cover:

- Pipeline concepts and Tekton CRD specifications (separate guide)
- Installation and configuration of the operator (separate guide)
- Creating CI/CD solutions with pipelines (separate guide)
- Pipelines as Code workflows (separate guide)
- Security topics (separate guide)
- Observability topics (separate guide)

## CLI Tool Versions Documented

| Tool | Status |
|------|--------|
| `tkn` | GA — primary CLI for OpenShift Pipelines |
| `tkn-pac` | GA — Pipelines as Code CLI |
| `opc` | Technology Preview — not for production |

## Related Official Sources To Add Later

- Pipelines as Code CLI reference (tkn-pac subcommands)
- opc CLI detailed reference when it reaches GA
