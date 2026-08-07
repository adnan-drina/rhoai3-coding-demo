---
name: mta-rules
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "mta"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Application Modernization"
description: >
  Use when creating custom rules for MTA 8.2 analysis, including YAML rule
  syntax, rule metadata (labels, categories, effort), provider conditions
  (java, builtin, go, csharp, python, nodejs), logical conditions, condition
  chaining, custom variables, rule actions, and rulesets. Do NOT use for CLI
  workflows (use mta-cli), web UI workflows (use mta-ui), or AI-assisted
  resolution (use mta-lightspeed).
---

# MTA Rules Development

Use this skill to ground Migration Toolkit for Applications (MTA) 8.2 custom
rule authoring in the official Configuring and Using Rules guide. MTA rules
instruct the analyzer to detect problematic patterns in application source
code before migration to target technologies.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official
Red Hat documentation is product authority.

## YAML Rule Structure

Rules consist of metadata, conditions, and actions:

```yaml
ruleID: <unique_id>
category: mandatory|optional|potential
effort: <integer>
description: <summary>
labels:
  - konveyor.io/source=<source_tech>
  - konveyor.io/target=<target_tech>
links:
  - url: <hyperlink>
    title: <title>
when:
  <condition(s)>
message: "<message>"
tag:
  - <tag_1>, <tag_2>
```

## Rule Metadata

- **ruleID**: unique within the ruleset
- **category**: `mandatory` (must fix), `optional` (should fix), `potential`
  (needs examination)
- **effort**: integer estimating story points to resolve
- **labels**: `key=val` pairs; reserved prefixes `konveyor.io/source`,
  `konveyor.io/target`, `konveyor.io/include` (values: `always` or `never`)

### Label Selectors

Use `--label-selector` to filter rules by labels with logical AND (`&&`),
OR (`||`), NOT (`!`), and grouping `()`. Use `--dep-label-selector` to filter
dependency-generated incidents.

## Providers and Capabilities

| Provider | Capabilities | Support Level |
|----------|-------------|---------------|
| `java` | `referenced`, `dependency` | Fully supported |
| `builtin` | `xml`, `json`, `filecontent`, `file`, `hasTags` | Fully supported |
| `go` | `referenced`, `dependency` | Fully supported |
| `csharp` | `referenced` | Developer Preview |
| `python` | `referenced` | Developer Preview |
| `nodejs` | `referenced` | Developer Preview |

### Java Provider

**`java.referenced`**: search by `pattern` (regex), `location` (IMPORT,
PACKAGE, TYPE, ANNOTATION, IMPLEMENTS_TYPE, RETURN_TYPE, VARIABLE_DECLARATION,
FIELD, METHOD, METHOD_CALL, CLASS, CONSTRUCTOR_CALL, INHERITANCE), and
`annotated` (annotation inspection with elements).

**`java.dependency`**: check dependencies by `name` (required), `nameregex`,
`upperbound`, `lowerbound`.

### Builtin Provider

- **`builtin.xml`**: XPath queries with optional `filepaths` and `namespaces`
- **`builtin.json`**: XPath queries on JSON files with optional `filepaths`
- **`builtin.filecontent`**: regex `pattern` with optional `filePattern`
- **`builtin.file`**: find files matching a name `pattern`
- **`builtin.hasTags`**: check application tags (logical AND for multiple)

### Go, C#, Python, Node.js Providers

Go supports `referenced` (pattern) and `dependency` (name, bounds). C# supports
`referenced` with `pattern` and `location` (CLASS, METHOD, FIELD, ALL). Python
and Node.js support `referenced` with `pattern` only.

## Logical Conditions

- **`and`**: all child conditions must match
- **`or`**: any child condition must match
- **Nesting**: combine `and`/`or` at multiple levels

## Condition Chaining

Use `as` to save a condition's output, `from` to reference it, and Mustache
templates (`{{name.filepaths}}`) for variable interpolation. Set `ignore: true`
on conditions used only for chaining. In Java rules, capitalize the variable
(e.g., `{{annotation.Filepaths}}`).

## Custom Variables

Capture data from matched source lines using `customVariables`:

```yaml
customVariables:
  - pattern: '([A-z]+)\.get\(\)'
    name: VariableName
message: "Found generic call - {{ VariableName }}"
```

## Rule Actions

- **Message**: informative text in the report with optional `links`
- **Tag**: categorize code with `key=val` pairs; tag-only rules do not
  generate issues

## Rulesets

Group rules in a directory with a `ruleset.yaml` file:

```yaml
name: "Ruleset name"
description: "Ruleset description"
labels:
  - key=val
```

Rules inherit ruleset labels. Pass the directory with `--rules=<dir>`.

## Workflow

1. Identify the migration path and target technology.
2. Choose the appropriate provider and capability for the condition.
3. Read `references/official-doc-extraction.md` for field details and examples.
4. Write the rule with metadata, condition, and action.
5. Test with `mta-cli analyze --input <app> --output <dir> --rules <rule.yaml>`.
6. Review the static report at `<output>/static-report/index.html`.

## Related Skills

- Use `mta-intellij` for IntelliJ IDEA plugin analysis workflows.
- Use `mta-cli` for command-line analysis workflows.
- Use `mta-ui` for web console analysis workflows.
- Use `mta-lightspeed` for AI-assisted code resolution.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
