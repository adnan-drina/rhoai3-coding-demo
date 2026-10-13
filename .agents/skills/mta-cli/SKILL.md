---
name: mta-cli
metadata:
  author: rhoai3-coding-demo
  version: 1.1.0
  platform-family: "mta"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Application Modernization"
description: >
  Use when using the MTA CLI for application analysis, migration assessment,
  and modernization. Do NOT use for UI workflows (use mta-ui), VS Code (use
  mta-vscode), IntelliJ (use mta-intellij), or AI features (use
  mta-lightspeed).
---

# MTA CLI

Use this skill for command-line application analysis, transformation, and
platform asset generation with Migration Toolkit for Applications (MTA) 8.3.

## Current Product Guidance (2026-10-13)

Documentation target: **MTA 8.3**. Read the current-update section
in `references/official-doc-extraction.md` and its source ledger before using
configuration details. It supersedes the retained earlier reference material.
`docs/PLATFORM_BASELINE.md` distinguishes documentation, selected deployment
pins and live qualification. This refresh does not upgrade an existing run.

## Source Grounding

Read `references/source-capture.md` before using product configuration details.
Official Red Hat docs are product authority. This skill covers the `mta-cli`
binary for analysing Java and non-Java applications, transforming source code,
generating deployment manifests, and reviewing analysis reports.

## Supported Languages

| Language | Support level |
|----------|---------------|
| Java | GA — containerless and container modes |
| Go | GA |
| .NET | Developer Preview |
| Node.js | Technology Preview |
| Python | Technology Preview |

## Key Concepts

### Containerless Mode

Default for Java applications. Requires JDK 17+, Maven 3.9.9+, JAVA_HOME,
`mvn` on PATH and an explicitly sized JVM_MAX_MEM.
Disable with `--run-local=false` to use container runtime.

### Container Mode

Required for non-Java languages. Uses Podman (or Docker as unsupported
alternative). Automatically used when non-Java providers are detected.

### Analysis Profiles

Technology Preview feature. Download standardised analysis configurations from
the MTA Hub (`mta-cli config sync`). Profiles include target/source
technologies, custom rules, and label selectors.

## Workflow

1. Read `references/source-capture.md` and confirm the product baseline.
2. Read `references/official-doc-extraction.md` for detailed procedures.
3. Install the `mta-cli` binary.
4. Select analysis mode:
   - Single application analysis
   - Bulk analysis (Developer Preview)
   - Non-Java language analysis
   - Profile-based analysis from MTA Hub
5. Run analysis and review reports.
6. Optionally run transformations (`openrewrite`).
7. Optionally generate deployment manifests (`discover` / `generate helm`).

### Single Application Analysis

Select the intended target and confirm that all required rules match the
source/target label filters. Unlabeled-rule behavior measured on 8.2 does
not qualify 8.3; verify inclusion on the upgraded provider:

```shell
mta-cli analyze --input <path_to_input> \
  --output <path_to_output> \
  --target <target_name>
```

When adding `--source`, verify matching source labels and the actual rules selected.

### List Available Targets

8.3 uses the rules subcommand; the analyze flag is a deprecated
compatibility form, not the default for new scripts:

```shell
mta-cli rules list-targets
mta-cli analyze --list-targets
```

### Non-Java Analysis

```shell
mta-cli analyze --input <path_to_input> \
  --output <path_to_output> \
  --provider <language_provider> \
  --rules <path_to_custom_rules>
```

### Profile-Based Analysis

```shell
mta-cli config login
mta-cli config sync --url https://<git-host>/<group>/<repo> \
  --application-path <path>
mta-cli analyze -i <path> -o <report_path> --overwrite --mode source-only
```

### Source Code Transformation

```shell
mta-cli openrewrite --list-targets
mta-cli openrewrite --input=<source_path> --target=<recipe>
```

Requires container runtime. Available recipes: `javax`-to-`jakarta` imports,
bootstrapping files, `persistence.xml`, and Spring Boot-to-Quarkus properties.

### Platform Asset Generation (Developer Preview)

```shell
mta-cli discover cloud-foundry --input <manifest> --output-dir <dir>
mta-cli generate helm --chart-dir <chart> --input <discovery.yaml> \
  --output-dir <dir>
```

## Key CLI Options

| Option | Description |
|--------|-------------|
| `--input` | Path to application source or binary |
| `--output` | Output directory for reports |
| `--source` / `--target` | Source and target technologies (label filters; unlabeled rules excluded) |
| `--rules` | Custom rule files or directory |
| `--label-selector` | Filter rules by label expression |
| `--provider` | Language provider for non-Java analysis |
| `--run-local` | Enable/disable containerless mode (default: true) |
| `--bulk` | Analyse multiple apps with shared output (Dev Preview) |
| `--mode` | `full` (default) or `source-only` |
| `--overwrite` | Overwrite existing output directory |
| `--skip-static-report` | Skip HTML report generation |
| `--json-output` | Boolean: also write `output.json` (and `dependencies.json`) into `--output`; takes no path. MTA CLI 8.2.1 exits 1 after a completed analysis when `dependencies.yaml` has nested `baseDep.extras` ("json: unsupported type: map[interface {}]interface {}"); `output.json` is already written |
| `--enable-default-rulesets` | Include default rules (default: true) |

## Analysis Report Sections

| Section | Purpose |
|---------|---------|
| Dashboard | Overview of incidents and story points by category |
| Issues | Summary of migration issues requiring attention |
| Dependencies | Java-packaged dependencies found in the application |
| Technologies | Embedded libraries grouped by functionality |
| Insights | Zero-effort rule violations and technology tags (Tech Preview) |

## Story Points

| Level | Points | Meaning |
|-------|--------|---------|
| Information | 0 | Low-priority informational warning |
| Trivial | 1 | Simple library swap, minimal API changes |
| Complex | 3 | Documented but complex changes |
| Redesign | 5 | Complete library change, significant API changes |
| Rearchitecture | 7 | Complete component rearchitecture |
| Unknown | 13 | Solution not known, possible rewrite |

## Validation

```shell
mta-cli rules list-targets
mta-cli analyze --list-targets
mta-cli provider list
mta-cli rules list-sources
```

## Known Issues

- Podman on Windows: RHEL 9 / UBI 9 images require x86-64-v2 CPU support.
  Workaround: use Docker by setting `CONTAINER_TOOL=/usr/local/bin/docker`.
- `--provider` must be specified for non-Java analysis or the analysis may fail
  if unsupported providers are discovered.
- Bulk analysis (`--bulk`) is Developer Preview; not production-ready.
- `--source` / `--target` exclude rules without matching labels (documented in
  MTA 7.1; omitted from 8.1/8.2 Rule metadata docs; confirmed on 8.2 runs).

## Related Skills

- `mta-lightspeed` — AI-assisted code migration with LLM integration.
- `mta-ui` — web UI analysis and assessment workflows.
- `mta-install` — MTA Operator installation and Tackle CR management.
- `mta-vscode` — VS Code extension (non-AI features).
- `mta-intellij` — IntelliJ IDEA plugin workflows.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
