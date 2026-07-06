---
name: mta-cli
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
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
platform asset generation with Migration Toolkit for Applications (MTA) 8.1.

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

Default for Java applications. Runs analysis directly on the local machine
without Podman or Docker. Requires `mvn` on `PATH` and `JVM_MAX_MEM` set.
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
6. Optionally run transformations (`transform openrewrite`).
7. Optionally generate deployment manifests (`discover` / `generate helm`).

### Single Application Analysis

```shell
mta-cli analyze --input <path_to_input> \
  --output <path_to_output> \
  --source <source_name> \
  --target <target_name>
```

### List Available Targets

```shell
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
mta-cli config sync --url https://github.com/<repo> \
  --application-path <path> --insecure
mta-cli analyze -i <path> -o <report_path> --overwrite --mode source-only
```

### Source Code Transformation

```shell
mta-cli transform openrewrite --list-targets
mta-cli transform openrewrite --input=<source_path> --target=<recipe>
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
| `--source` / `--target` | Source and target technologies |
| `--rules` | Custom rule files or directory |
| `--label-selector` | Filter rules by label expression |
| `--provider` | Language provider for non-Java analysis |
| `--run-local` | Enable/disable containerless mode (default: true) |
| `--bulk` | Analyse multiple apps with shared output (Dev Preview) |
| `--mode` | `full` (default) or `source-only` |
| `--overwrite` | Overwrite existing output directory |
| `--skip-static-report` | Skip HTML report generation |
| `--json-output` | Produce JSON output |
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
mta-cli analyze --list-targets
mta-cli analyze --list-providers
mta-cli analyze --list-sources
```

## Known Issues

- Podman on Windows: RHEL 9 / UBI 9 images require x86-64-v2 CPU support.
  Workaround: use Docker by setting `CONTAINER_TOOL=/usr/local/bin/docker`.
- `--provider` must be specified for non-Java analysis or the analysis may fail
  if unsupported providers are discovered.
- Bulk analysis (`--bulk`) is Developer Preview; not production-ready.

## Related Skills

- `mta-lightspeed` — AI-assisted code migration with LLM integration.
- `mta-ui` — web UI analysis and assessment workflows.
- `mta-install` — MTA Operator installation and Tackle CR management.
- `mta-vscode` — VS Code extension (non-AI features).
- `mta-intellij` — IntelliJ IDEA plugin workflows.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
