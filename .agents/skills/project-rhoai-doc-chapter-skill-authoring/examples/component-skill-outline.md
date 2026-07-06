# Component Skill Outline

Use this as a starting point for a generated `rhoai-*` skill.

```markdown
---
name: rhoai-<capability>
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "RHOAI Platform"
description: >
  <Strong trigger description tied to the official docs chapter. Include
  specific scenarios and negative triggers.>
---

# <Capability Name>

Use this skill for <component/workflow> on the active product baseline in
`docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product configuration details.
Official Red Hat docs are product authority. Red Hat articles and rh-brain are
supporting narrative and examples only.

## Workflow

1. Confirm prerequisites.
2. Follow the official-doc-backed install/configure/use sequence.
3. Verify with readonly commands.
4. Update README, GitOps, scripts, and validation together when implementing
   demo content.

## Validation

- <readonly command or schema check>
- <expected healthy signal>
- <failure signal and next diagnostic>

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
```

Suggested generated reference files:

```text
references/source-capture.md
references/official-doc-extraction.md
references/validation-checklist.md
examples/<minimal-example>.md
```
