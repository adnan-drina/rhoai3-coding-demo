---
name: project-red-hat-doc-skill-authoring
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "red-hat"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Project Structure"
description: >
  Create or update a compliant product skill from official Red Hat
  documentation for this demo's platform stack. Use when the user provides
  Red Hat OpenShift AI, OpenShift Container Platform, or OpenShift Data
  Foundation documentation sources and asks to create rhoai-*, ocp-*, or odf-*
  skills; when defining a new Red Hat product skill family; when capturing
  source evidence, extraction rules, validation criteria, examples, or a
  component roadmap; or when deciding whether a source belongs in RHOAI, OCP,
  ODF, project, or environment guidance. Do NOT use for live cluster deployment
  or troubleshooting; use env-* skills. Do NOT use as product authority by
  itself; generated skills must cite official Red Hat docs and verification
  commands.
---

# Red Hat Doc Skill Authoring

Use this meta-skill to convert official Red Hat product documentation into
durable repo skills. The output is usually a new or updated component skill
under `.agents/skills/` with one of these prefixes:

- `rhoai-*` for Red Hat OpenShift AI component knowledge
- `ocp-*` for Red Hat OpenShift Container Platform component knowledge
- `odf-*` for Red Hat OpenShift Data Foundation component knowledge

## Required References

Read only the files needed for the current task:

- `.agents/references/red-hat-doc-map.yaml` for routing Red Hat product
  documentation sources and repo routing categories to flat repo skills
- `references/platform-skill-taxonomy.md` for product-family routing,
  frontmatter metadata, and rule/roadmap expectations
- `references/source-capture.md` for the source ledger template and baseline
  gate
- `references/extraction-rules.md` for what to extract from official docs
- `references/validation-checklist.md` before finishing the generated skill
- `examples/component-skill-outline.md` when creating a new component skill

## Workflow

1. Read `docs/PLATFORM_BASELINE.md`.
2. Read `.agents/references/red-hat-doc-map.yaml` and identify whether the
   official source already maps to an existing, planned, or blocked skill.
3. Identify the product family and prefix:
   - Red Hat OpenShift AI Self-Managed -> `rhoai-*`
   - Red Hat OpenShift Container Platform -> `ocp-*`
   - Red Hat OpenShift Data Foundation -> `odf-*`
4. Confirm the input source matches the active baseline for that product.
   If the product version is not pinned in `docs/PLATFORM_BASELINE.md`, stop
   after drafting the source-capture note and ask to pin the baseline before
   creating a reusable component skill.
5. If the doc-map route is `active`, update the mapped skill unless the source
   clearly belongs to a different capability. If the route is `planned`, create
   the planned flat skill. If the route is missing, choose a stable flat skill
   name and add a route for it. If the route is `blocked-baseline`, do not
   create the reusable skill until the baseline is pinned.
6. Capture official sources before writing the skill:
   - product and version
   - chapter or page URL
   - source type, such as versioned docs.redhat.com documentation, Customer
     Portal article, external Red Hat product docs, or repo-specific guidance
   - documentation category
   - retrieved date
   - sections used
   - related Red Hat docs, articles, and rh-brain examples
7. Extract only supported product behavior:
   - purpose and supported posture
   - prerequisites
   - install/configure/use/upgrade/remove workflows
   - operators, namespaces, subscriptions, CRDs, API groups, fields, labels,
     annotations, images, and artifacts
   - validation commands and failure signals
   - boundaries between Red Hat product behavior and demo glue
8. Design the target skill:
   - folder name uses the selected prefix and a stable capability name
   - frontmatter `name` matches the folder name
   - metadata uses `platform-baseline: "repo"` and `ocp-baseline: "repo"`
   - `metadata.platform-family` is `rhoai`, `ocp`, or `odf`
   - `metadata.skill-group` matches the taxonomy
   - description lists strong positive triggers and negative triggers
   - `SKILL.md` stays concise; move detail into one-level reference files
9. Add examples only when they are traceable to official docs or are clearly
   marked as demo-specific examples requiring schema verification.
10. Validate the generated skill with `references/validation-checklist.md`.
    For repository-level consistency, also run
    `scripts/validate-agent-guidance.rb` after updating the doc map, rules, or
    shared skill inventory.
11. Update shared inventory when adding or renaming a skill:
   - `.agents/references/red-hat-doc-map.yaml`
   - `AGENTS.md`
   - `.agents/rules/<family>.md` when that family has at least one real skill
   - `.agents/skills/project-structure/SKILL.md`
   - `.agents/skills/project-agent-guidance/SKILL.md`
   - the relevant roadmap under `.agents/skills/project-structure/references/`

## Output Contract

A completed generated component skill should normally contain:

```text
.agents/skills/<prefix>-<capability>/
  SKILL.md
  references/
    source-capture.md
    official-doc-extraction.md
    validation-checklist.md
  examples/
    <minimal-example>.md or focused manifest/runbook snippets
```

Keep generated examples minimal. Prefer snippets that demonstrate exact field
placement, verification commands, or recommended workflow shape.

## Hard Rules

- Do not invent CR fields, API versions, annotations, operator channels, image
  names, storage classes, installation modes, support posture, or recommended
  settings.
- Do not treat upstream community documentation as Red Hat product authority.
- Do not treat rh-brain as product configuration truth; use it for narrative,
  Red Hat articles, blogs, and code examples after official docs are captured.
- Do not create nested skill folders to mirror Red Hat documentation
  categories; represent product/category/book/chapter routing and source type
  in `.agents/references/red-hat-doc-map.yaml`.
- Do not generate new `odf-*` skills unless the ODF product version and
  official documentation source are pinned in `docs/PLATFORM_BASELINE.md`.
- If official docs are ambiguous, mark the item unresolved and include an
  `oc explain`, CRD, CSV, catalog, registry, or image lookup command.
- If the official source cannot be accessed and no local export is provided,
  create only a draft scaffold or stop and ask for source content.

## References

- `references/platform-skill-taxonomy.md`
- `references/source-capture.md`
- `references/extraction-rules.md`
- `references/validation-checklist.md`
- `examples/component-skill-outline.md`
- `.agents/references/red-hat-doc-map.yaml`
