# Official Doc Extraction

Use this extraction to keep MTA rule authoring content grounded in official
Red Hat sources. When creating custom rules, verify provider capabilities and
field names against the installed MTA version.

## Rule Structure

MTA YAML rules consist of metadata, conditions, and actions. A rule file
contains one or more rules. A ruleset groups rules in a directory with a
`ruleset.yaml` manifest.

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
  - Category=<tag_3>
```

## Rule Metadata

### Rule ID

Must be unique within the ruleset.

### Category

| Value | Meaning |
|-------|---------|
| `mandatory` | Must resolve for successful migration |
| `optional` | Should resolve; schedule soon after migration if deferred |
| `potential` | Needs examination; insufficient detail to determine if mandatory |

### Effort

Integer value representing story points to resolve the issue.

### Labels

Format: `key=val` pairs as a list of strings. Keys can be subdomain-prefixed
(e.g., `konveyor.io/key=val`). Values can be empty or omitted.

### Reserved Labels

| Label | Purpose |
|-------|---------|
| `konveyor.io/source` | Source technology for the rule or ruleset |
| `konveyor.io/target` | Target technology for the rule or ruleset |
| `konveyor.io/include` | Override filter behavior: `always` (always include) or `never` (always exclude) |

### Label Selector Syntax

The `--label-selector` CLI option supports:

| Operator | Example | Meaning |
|----------|---------|---------|
| `=` | `konveyor.io/source=eap6` | Match label with specific value |
| (key only) | `konveyor.io/source` | Match label with any value |
| `&&` | `key1=val1 && key2` | Logical AND |
| `\|\|` | `key1=val1 \|\| key2` | Logical OR |
| `!` | `!key1=val1` | Logical NOT |
| `()` | `(key1=val1 \|\| key2) && !val3` | Grouping for precedence |

### Dependency Labels

The analyzer automatically adds labels to dependencies:

- `konveyor.io/dep-source=internal` — indicates internal dependency
- `konveyor.io/language=java` — programming language

Use `--dep-label-selector` to filter dependency incidents, e.g.,
`!konveyor.io/dep-source=open-source` to exclude open-source dependencies.

## Providers

### Builtin Provider

Internal provider for file analysis and metadata inspection.

**`builtin.xml`**:

```yaml
when:
  builtin.xml:
    xpath: "<xpath_expression>"
    filepaths:
      - "/src/file1.xml"
    namespaces:
      var: http://xmlns.example.com/schema
```

- `xpath` (required): valid XPath expression
- `filepaths` (optional): scope to specific files
- `namespaces` (optional): map namespace variables for XPath

**`builtin.json`**:

```yaml
when:
  builtin.json:
    xpath: "<xpath_expression>"
    filepaths: "{{chain.filepaths}}"
```

- `xpath` (required): valid XPath expression
- `filepaths` (optional): scope to specific files

**`builtin.filecontent`**:

```yaml
when:
  builtin.filecontent:
    pattern: "<regex>"
    filePattern: "<filename_regex>"
```

- `pattern` (required): regex to match content
- `filePattern` (optional): regex to scope to matching filenames

**`builtin.file`**:

```yaml
when:
  builtin.file:
    pattern: "<filename_pattern>"
```

- `pattern` (required): filename pattern to match

**`builtin.hasTags`**:

```yaml
when:
  builtin.hasTags:
    - "tag1"
    - "tag2"
```

Multiple tags imply logical AND.

### Java Provider

Uses Eclipse JDTLS for source code analysis.

**`java.referenced`**:

```yaml
when:
  java.referenced:
    pattern: "<regex>"
    location: <LOCATION>
    annotated:
      pattern: <annotation_fqn>
      elements:
        - name: <element_name>
          value: "<element_value_regex>"
```

- `pattern` (required): regex matching Java types, methods, or packages
- `location` (optional): one of the supported locations below
- `annotated` (optional): annotation inspection query

**Java Locations**:

| Location | Matches |
|----------|---------|
| `IMPORT` | Class imports (FQN or wildcard) |
| `PACKAGE` | Package usage in imports or FQN code references |
| `TYPE` | All types: classes, interfaces, enums, annotation types |
| `ANNOTATION` | Annotations |
| `IMPLEMENTS_TYPE` | Types implementing the given type |
| `RETURN_TYPE` | Method return types |
| `VARIABLE_DECLARATION` | Variable declarations |
| `FIELD` or `FIELD_DECLARATION` | Field declarations |
| `METHOD` | Method declarations |
| `METHOD_CALL` | Method calls |
| `CLASS` | Class declarations |
| `CONSTRUCTOR_CALL` | Constructor calls |
| `INHERITANCE` | Classes inheriting from the given type |

**Annotation Inspection**:

```yaml
annotated:
  pattern: org.framework.Bean
  elements:
    - name: url
      value: "http://www.example.com"
```

Both `pattern` and `elements` are optional. Can be used with `location:
ANNOTATION` or combined with other locations.

**`java.dependency`**:

```yaml
when:
  java.dependency:
    name: junit.junit
    upperbound: 4.12.2
    lowerbound: 4.4.0
```

- `name` (required): dependency name (groupId.artifactId)
- `nameregex` (optional): regex to match name
- `upperbound` (optional): max version (inclusive)
- `lowerbound` (optional): min version (inclusive)

Analysis precision is lower for projects that cannot be built (Maven falls
back to pom.xml parsing).

### Go Provider

**`go.referenced`**:

```yaml
when:
  go.referenced:
    pattern: "v1beta1.CustomResourceDefinition"
```

**`go.dependency`**:

```yaml
when:
  go.dependency:
    name: sigs.k8s.io/structured-merge-diff/v4
    upperbound: v4.2.2
    lowerbound: v4.2.0
```

### C# Provider (Developer Preview)

Uses tree-sitter and stack graphs for semantic analysis in source-only mode.

```yaml
when:
  csharp.referenced:
    pattern: "WebMatrix.WebData.WebSecurity"
    location: ALL
```

Supported locations: `CLASS`, `METHOD`, `FIELD`, `ALL`.

### Python Provider (Developer Preview)

```yaml
when:
  python.referenced:
    pattern: "bad_method"
```

### Node.js Provider (Developer Preview)

```yaml
when:
  nodejs.referenced:
    pattern: "React"
```

## Logical Conditions

### AND Condition

```yaml
when:
  and:
    - java.dependency:
        name: junit.junit
        upperbound: 4.12.2
        lowerbound: 4.4.0
    - java.referenced:
        location: IMPORT
        pattern: junit.junit
```

### OR Condition

```yaml
when:
  or:
    - java.dependency:
        name: junit.junit
    - java.referenced:
        location: IMPORT
        pattern: junit.junit
```

### Nested Conditions

Combine `and` and `or` at multiple levels for complex conditions.

## Condition Chaining

Save a condition's output with `as` and reference it with `from`:

```yaml
when:
  or:
    - builtin.xml:
        xpath: "//dependencies/dependency"
        filepaths: "{{poms.filepaths}}"
      from: poms
    - builtin.file:
        pattern: pom.xml
      as: poms
      ignore: true
```

- `as: <name>` — save output to a named variable
- `from: <name>` — use a previously saved variable
- `ignore: true` — exclude this condition from violation detection
- Use Mustache templates: `{{name.filepaths}}`
- In Java rules, capitalize the variable: `{{annotation.Filepaths}}`

## Custom Variables

```yaml
customVariables:
  - pattern: '([A-z]+)\.get\(\)'
    name: VariableName
message: "Found generic call - {{ VariableName }}"
```

- `pattern`: regex with capture group to extract from source line
- `name`: variable name for use in message templates

## Rule Actions

### Message Action

```yaml
message: "Issue description text."
links:
  - url: "https://example.com/docs"
    title: "Migration documentation"
```

### Tag Action

```yaml
tag:
  - "Language=Golang"
  - "Env=production"
  - "Source Code"
```

Tags with `key=val` format assign a category. Tag-only rules do not create
issues.

## Rulesets

```yaml
name: "Unique ruleset name"
description: "Ruleset description"
labels:
  - konveyor.io/source=eap6
  - konveyor.io/target=eap8
```

Place rule files in the same directory as `ruleset.yaml`. Rules inherit
ruleset labels. Pass with:

```bash
mta-cli analyze --input=<app> --output=<dir> --rules=<ruleset_dir> \
  --enable-default-rulesets=false
```

Use `--target` or `--source` options with reserved labels to filter rules.

**Caveat (MTA 7.1 documented; silent in 8.1/8.2 Rule metadata docs; confirmed
on 8.2 runs):** when `--source` or `--target` is set, the engine selects only
rules that match that label — rules **without** source/target labels are
excluded. Label custom rules accordingly, or omit `--source` (and carefully
choose `--target`) when unlabeled rules must participate. See `mta-cli`
extraction and nested `mta-8.2-recapture.md`.

## Testing Custom Rules

```bash
mta-cli analyze --input <path_to_app> --output <path_to_report> \
  --rules <path_to_rule.yaml>
```

Add `--overwrite` to reuse the same output directory. Add `--run-local=false`
for Go, Python, Node.js, and C# providers. Review results at
`<output>/static-report/index.html`.
