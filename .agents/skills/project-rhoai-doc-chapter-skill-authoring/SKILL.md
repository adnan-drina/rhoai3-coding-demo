---
name: project-rhoai-doc-chapter-skill-authoring
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Project Structure"
description: >
  Create or update a compliant rhoai-* component skill from one official Red
  Hat OpenShift AI documentation chapter. Use when the user provides a
  docs.redhat.com RHOAI chapter URL, asks to turn an official RHOAI chapter
  into a reusable skill, wants source capture, extraction rules, validation
  criteria, examples, or asks to build the missing RHOAI component skills from
  docs/PLATFORM_BASELINE.md. For OCP or ODF product skills, use
  project-red-hat-doc-skill-authoring instead. Do NOT use for live cluster
  deployment or troubleshooting; use env-* skills. Do NOT use as product
  authority by itself; the generated skill must cite official Red Hat docs and
  verification commands.
---

# RHOAI Doc Chapter Skill Authoring

Use this meta-skill to convert one official Red Hat OpenShift AI documentation
chapter into a durable repo skill. The output is usually a new or updated
`rhoai-*` component skill under `.agents/skills/`.

For new `ocp-*` or `odf-*` skills, use
`project-red-hat-doc-skill-authoring`.

## Input Contract

Accept one of:

- an official `docs.redhat.com` RHOAI chapter URL
- a chapter title from `docs/PLATFORM_BASELINE.md`
- a locally saved export of an official RHOAI chapter

Optional input:

- target skill name, such as `rhoai-model-serving-platform`
- component scope, such as "KServe model serving" or "Llama Stack RAG"
- demo stage or future stage that will consume the skill

If the user gives broad input such as "create all install skills", split it
into one skill per documentation chapter or tightly related component area.

## Required References

Read only the files needed for the current task:

- `references/source-capture.md` for the source ledger template and rules
- `references/extraction-rules.md` for what to extract from the official docs
- `references/validation-checklist.md` before finishing the generated skill
- `examples/component-skill-outline.md` when creating a new `rhoai-*` skill

## Workflow

1. Read `docs/PLATFORM_BASELINE.md`.
2. Confirm the input chapter matches the active RHOAI documentation baseline.
   Do not use `/latest/` or another RHOAI version unless it is recorded as an
   explicit exception.
3. Capture official sources before writing the skill:
   - chapter URL and title
   - documentation category from the baseline index
   - retrieved date
   - sections used
   - related Red Hat docs, articles, and rh-brain examples
4. Extract only supported product behavior:
   - component purpose and supported posture
   - prerequisites
   - install/configure/use workflow
   - CRDs, API groups, fields, annotations, images, and artifacts
   - verification commands and failure signals
   - boundaries between Red Hat product behavior and demo glue
5. Design the target skill:
   - folder name uses `rhoai-<capability>` unless the output is project
     governance, docs, or environment workflow
   - frontmatter `name` matches the folder name
   - metadata uses `platform-baseline: "repo"` and `ocp-baseline: "repo"`
   - description lists strong positive triggers and negative triggers
   - `SKILL.md` stays concise; move detail into one-level reference files
6. Add examples only when they are traceable to official docs or are clearly
   marked as demo-specific examples. Do not copy long Red Hat docs passages.
7. Validate the generated skill with `references/validation-checklist.md`.
8. Update shared inventory when adding or renaming a skill:
   - `AGENTS.md`
   - `.agents/rules/project.md` or `.agents/rules/rhoai.md`
   - `.agents/skills/project-structure/SKILL.md`
   - `.agents/skills/project-agent-guidance/SKILL.md`
   - `.agents/skills/project-structure/references/rhoai-component-skill-roadmap.md`

## Output Contract

A completed generated component skill should normally contain:

```text
.agents/skills/rhoai-<capability>/
  SKILL.md
  references/
    source-capture.md
    official-doc-extraction.md
    validation-checklist.md
  examples/
    <minimal-example>.md or focused manifest/prompt/runbook snippets
```

Keep generated examples minimal. Prefer snippets that demonstrate exact field
placement, verification commands, or recommended workflow shape.

## Hard Rules

- Do not invent CR fields, API versions, annotations, operator channels, image
  names, model artifacts, support status, or recommended settings.
- Do not treat upstream community documentation as Red Hat product authority.
- Do not treat rh-brain as product configuration truth; use it for narrative,
  Red Hat articles, blogs, and code examples after official docs are captured.
- If official docs are ambiguous, mark the item unresolved and include an
  `oc explain`, CRD, CSV, catalog, registry, or image lookup command.
- If the official chapter cannot be accessed and no local export is provided,
  create only a draft scaffold or stop and ask for the source content.
