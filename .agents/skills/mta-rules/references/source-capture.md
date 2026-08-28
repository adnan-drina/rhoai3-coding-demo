# Source Capture

## Official Sources

| Field | Value |
|-------|-------|
| Product | Migration Toolkit for Applications |
| Version | 8.2 |
| Documentation category | Rules Development |
| Official guide | Configuring and Using Rules for an MTA Analysis |
| Source URL | https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.2/html-single/configuring_and_using_rules_for_an_mta_analysis/index |
| Multi-page URL | https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.2/html/configuring_and_using_rules_for_an_mta_analysis/index |
| Capture date | 2026-07-06 |

## Captured Sections

From Configuring and Using Rules for an MTA Analysis:

- Chapter 1: Introduction to rules (rule and ruleset concepts, how MTA
  performs an analysis, YAML rule structure and syntax)
- Chapter 2: Rule metadata (ruleID, labels, effort, category, reserved labels
  konveyor.io/source|target|include, label selectors with AND/OR/NOT,
  dependency labels konveyor.io/dep-source and konveyor.io/language,
  dep-label-selector)
- Chapter 3: Providers and rule conditions (builtin, java, go, csharp,
  python, nodejs providers; provider capabilities; condition fields per
  provider; support status including Developer Preview for csharp, python,
  nodejs)
- Chapter 4: Java condition and capabilities (Java locations: IMPORT, PACKAGE,
  TYPE, ANNOTATION, IMPLEMENTS_TYPE, RETURN_TYPE, VARIABLE_DECLARATION, FIELD,
  METHOD, METHOD_CALL, CLASS, CONSTRUCTOR_CALL, INHERITANCE; annotation
  inspection with elements; condition patterns using JDK SearchPattern)
- Chapter 5: Logical conditions, condition chaining, and custom variables
  (AND, OR, nesting, as/from/ignore/Mustache templates, Java chaining with
  capitalized Filepaths, customVariables with pattern and name)
- Chapter 6: Rule actions (message action with links, tag action with
  categories, hyperlinks)
- Chapter 7: Creating custom rules (YAML rule example, Go rule example,
  Node.js rule example, Python rule example, C# rule example)
- Chapter 8: Rulesets (ruleset.yaml, passing rulesets with --rules, label
  inheritance)

## Source Boundaries

This skill covers the Configuring and Using Rules guide only. It provides
rule authoring guidance for all supported providers. It does not cover:

- MTA CLI usage beyond rule testing (separate CLI Guide)
- MTA web UI workflows (separate User Interface Guide)
- IntelliJ IDEA or VS Code plugin usage (separate plugin guides)
- AI-assisted code resolution via Developer Lightspeed
- Server-side MTA deployment or operator configuration
- XML-based legacy rule format (guide focuses on YAML rules)
