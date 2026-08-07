# Official Doc Extraction

Use this extraction to keep MTA CLI content grounded in official Red Hat
sources. When implementation needs exact command syntax, verify against
`mta-cli --help` and `mta-cli analyze --help` on the installed version
(product baseline: MTA 8.2).

Live 8.2 CLI guide: analyzing Java applications is **Chapter 4** (was
Chapter 3 in 8.1). Nested grounding for this bump:
`harness-refactoring/source-analysis/mta-kantra/mta-8.2-recapture.md`
(Research, 2026-08-07).

## `--source` / `--target` and unlabeled rules (important)

Passing `--source` or `--target` restricts the engine to rules that carry a
matching source/target label. Rules **without** those labels are excluded.

- **Documented (MTA 7.1 Rules Development Guide)** — verbatim note that if you
  use `--target` or `--source`, the engine only selects rules matching that
  label; add source/target labels on custom rules accordingly.
- **Silent in MTA 8.1 and 8.2** docs (Rule metadata chapter) — the caveat was
  dropped between 7.1 and 8.1; surrounding reserved-label / `--label-selector`
  material is otherwise unchanged.
- **Confirmed on MTA 8.2 runs** (Track B, 2026-07-27): `--source` excluded
  source-labelless rules (including custom contract rules) and narrowed the set.

**Demo / harness practice:** prefer `--target` only (from
`migration.yaml` `analysis.targets`) and **never** pass `--source` when the
ruleset includes unlabeled custom rules. See AD-003 amendment A.

## Supported Migration Paths (Java)

| Source | JBoss EAP 7/8 | OpenShift | OpenJDK 11/17/21 | Jakarta EE 9 | Camel 3/4 | Spring Boot | Quarkus | Open Liberty |
|--------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| Oracle WebLogic | Yes | Yes | Yes | - | - | - | - | - |
| IBM WebSphere | Yes | Yes | Yes | - | - | - | - | Yes |
| JBoss EAP 5 | Yes | Yes | Yes | - | - | - | - | - |
| JBoss EAP 6 | Yes | Yes | Yes | - | - | - | - | - |
| JBoss EAP 7 | Yes | Yes | Yes | - | - | - | Yes | - |
| Spring Boot | - | Yes | Yes | Yes | - | Yes | Yes | - |
| Camel 2 | - | Yes | Yes | - | Yes | - | - | - |
| Any Java app | - | Yes | Yes | - | - | - | - | - |

## Analyzing a Single Application

Preferred when custom or unlabeled rules must apply (see caveat above):

```shell
mta-cli analyze \
  --input <path_to_input> \
  --output <path_to_output> \
  --target <target_name>
```

Official docs also show `--source` with `--target`. Only add `--source` when
every needed rule carries a matching `konveyor.io/source=…` label:

```shell
mta-cli analyze \
  --input <path_to_input> \
  --output <path_to_output> \
  --source <source_name> \
  --target <target_name>
```

Output files: `analysis.log`, `dependencies.yaml`, `output.yaml`, `shim.log`,
`static-report/`, `static-report.log`.

Access report: `file:///<output_dir>/static-report/index.html`.

## Analyzing Multiple Applications (Developer Preview)

```shell
mta-cli analyze --bulk --input <path_A> --output <shared_output> \
  --target <tgt_A>
mta-cli analyze --bulk --input <path_B> --output <shared_output> \
  --target <tgt_B>
```

One `--input` per command; same `--output` directory for all inputs.
Add `--source` only when label coverage is complete (see caveat).

## Containerless Mode

Default for Java. Requirements:

- `mvn` binary on `PATH`.
- `JVM_MAX_MEM` system variable set (analysis may hang without it).
- For Gradle: OpenJDK 8, `$JAVA8_HOME` set, project has Gradle Wrapper.

Disable with `--run-local=false` to use container runtime.

```shell
mta-cli analyze --overwrite \
  --input <path_to_input> \
  --output <path_to_output> \
  --target <target>
```

## analyze Command Options

Table grounded in the 8.2 CLI guide Ch. 4.4 plus flags confirmed by surrounding
8.2 prose / prior verified help (`--provider`, `--bulk` may be truncated in
some rendered doc tables — do not treat absence in a partial fetch as removal).
Confirm listing flags against `mta-cli analyze --help` on a real 8.2 binary.

| Option | Type | Description |
|--------|------|-------------|
| `--input` | string | Path to source code or binary |
| `--output` | string | Output directory for reports |
| `--source` | string | Source technology (repeatable); excludes unlabeled rules — see caveat |
| `--target` | string | Target technology (repeatable); same label-filter behavior |
| `--rules` | stringArray | Rule files or directory |
| `--label-selector` | string | Filter rules by label expression |
| `--mode` | string | `full` (default) or `source-only` |
| `--provider` | string | Language provider for non-Java analysis |
| `--run-local` | bool | Containerless mode (default: true for Java) |
| `--bulk` | bool | Bulk analysis mode (Dev Preview) |
| `--overwrite` | bool | Overwrite output directory |
| `--skip-static-report` | bool | Skip HTML report |
| `--json-output` | string | JSON output |
| `--enable-default-rulesets` | bool | Include defaults (default: true) |
| `--analyze-known-libraries` | bool | Include open-source libraries |
| `--context-lines` | int | Source lines per incident (default: 100) |
| `--dependency-folders` | stringArray | Dependency directories |
| `--incident-selector` | string | Filter incidents by custom variables |
| `--maven-settings` | string | Custom Maven settings file |
| `--list-targets` | - | List available targets (analyze flag; see also `rules list-targets`) |
| `--list-sources` | - | List available sources (analyze flag; see also `rules list-sources`) |
| `--list-providers` | - | List available language providers |
| `--list-languages` | - | List languages in source (not binary) |
| `--disable-maven-search` | bool | Skip Maven index lookups |
| `--log-level` | uint32 | Log verbosity (default: 4) |
| `--http-proxy` / `--https-proxy` / `--no-proxy` | string | Proxy configuration |
| `--jaeger-endpoint` | string | Jaeger tracing endpoint |
| `--no-cleanup` | bool | Do not clean up temporary resources |

### Listing sources and targets (8.2)

8.2 worked examples prefer the subcommand form:

```shell
mta-cli rules list-targets
mta-cli rules list-sources
```

The analyze flags (`mta-cli analyze --list-targets` / `--list-sources`) remain
documented in upstream kantra help and prior 8.1 examples. Treat both as
likely current until confirmed on a provisioned 8.2 `mta-cli` binary; do not
silently drop the flag form.

## Non-Java Analysis

```shell
mta-cli analyze --list-providers

mta-cli analyze \
  --input <path_to_input> \
  --output <path_to_output> \
  --provider <provider_name> \
  --rules <path_to_rules>
```

`--provider` must be specified or analysis may fail on unsupported providers.

### Unsupported Provider Override

Create a provider configuration JSON file, then:

```shell
mta-cli analyze \
  --provider-override <path_to_config> \
  --output <path_to_output> \
  --rules <path_to_rules>
```

## Profile-Based Analysis (Technology Preview)

### Login

```shell
mta-cli config login
# Prompts: Host, Username, Password
# Host: https://mta-namespace.apps.cluster.example.com/hub
```

### Sync Profiles

```shell
mta-cli config sync \
  --url https://github.com/<app_repo> \
  --application-path <local_path> \
  --insecure
```

Downloads profiles to `.konveyor/profiles/` and rules to
`.konveyor/profiles/<name>/rules/`.

### List Downloaded Profiles

```shell
mta-cli config list --profile-dir <app_path>
```

### Run Analysis With Profile

```shell
mta-cli analyze -i <app_path> -o <report_path> --overwrite --mode source-only
```

Override profile values:

```shell
mta-cli analyze -i <app_path> -o <report_path> --overwrite \
  --target quarkus --mode source-only
```

### config Command Options

| Option | Description |
|--------|-------------|
| `config login` | Enter Hub host, username, password |
| `config sync --url <repo> --application-path <path>` | Download profiles |
| `config list --profile-dir <path>` | List local profiles |
| `-k`, `--insecure` | Skip TLS verification |

## Analysis Report Sections

| Section | Description |
|---------|-------------|
| Dashboard | Overview of incidents and story points by category |
| Issues | Migration issues requiring attention |
| Dependencies | Java-packaged dependencies |
| Technologies | Embedded libraries by functionality |
| Insights (Tech Preview) | Zero-effort violations and technology tags |

## Story Points and Categories

| Level | Points | Description |
|-------|--------|-------------|
| Information | 0 | Informational, low priority |
| Trivial | 1 | Simple library swap |
| Complex | 3 | Complex but documented |
| Redesign | 5 | Complete library change |
| Rearchitecture | 7 | Complete component rearchitecture |
| Unknown | 13 | Solution not known |

Categories: Mandatory, Optional, Potential, Information.

## Source Code Transformation

Requires container runtime configured.

### List Recipes

```shell
mta-cli transform openrewrite --list-targets
```

### Transform

```shell
mta-cli transform openrewrite \
  --input=<source_path> \
  --target=<recipe_target>
```

### Available Recipes

| Path | Recipe | Purpose |
|------|--------|---------|
| javax → Jakarta EE | `org.jboss.windup.JavaxToJakarta` | Replace javax imports/artifacts |
| javax → Jakarta EE | `org.jboss.windup.jakarta.javax.BootstrappingFiles` | Rename bootstrapping files |
| javax → Jakarta EE | `org.jboss.windup.javax-jakarta.PersistenceXML` | Transform persistence.xml |
| Spring Boot → Quarkus | `org.jboss.windup.sb-quarkus.Properties` | Replace spring.jpa properties |

### openrewrite Options

| Option | Description |
|--------|-------------|
| `--input` | Source code directory |
| `--target` | Target OpenRewrite recipe |
| `--goal` | Target goal (default: `dryRun`) |
| `--list-targets` | List available recipes |
| `--maven-settings` | Custom Maven settings |

## Platform Asset Generation (Developer Preview)

### Discovery

```shell
mta-cli discover --list-platforms
mta-cli discover cloud-foundry \
  --input <cf_manifest> \
  --output-dir <output>
```

### Live Discovery

```shell
mta-cli discover cloud-foundry \
  --use-live-connection \
  --orgs=<org> --spaces=<space> \
  --output-dir <output> \
  --cf-config=<cf_config_path>
```

### Conceal Sensitive Data

```shell
mta-cli discover cloud-foundry \
  --conceal-sensitive-data=true \
  --input <manifest> \
  --output-dir <output>
```

### Generate Deployment Manifests

```shell
mta-cli generate helm \
  --chart-dir <helm_chart> \
  --input <discovery.yaml> \
  --output-dir <output>
```

Override values: `--set name="new-name" --set instances=2`.

Value priority: `--set` flag > discovery manifest > `values.yaml`.

## Known Issues

- **Podman on Windows**: RHEL 9 / UBI 9 images require x86-64-v2 CPU.
  Error: `Fatal glibc error: CPU does not support x86-64-v2`.
  Workaround: set `CONTAINER_TOOL=/usr/local/bin/docker`.
- Different container runtime configurations are not supported.

## Boundaries

- This extraction covers CLI usage only.
- Web UI workflows belong in `mta-ui`.
- VS Code extension belongs in `mta-vscode`.
- AI-assisted code resolution belongs in `mta-lightspeed`.
- MTA Operator installation and Tackle CR management belong in `mta-install`.
- Custom rule authoring belongs in a separate skill.
