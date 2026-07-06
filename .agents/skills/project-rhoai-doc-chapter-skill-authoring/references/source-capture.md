# Source Capture

Use this reference before writing a generated `rhoai-*` skill.

## Baseline Gate

Read `docs/PLATFORM_BASELINE.md` and verify:

- product is Red Hat OpenShift AI Self-Managed
- documentation URL uses the active baseline path
- chapter category exists in the baseline index, or the exception is recorded

Reject or flag:

- `/latest/` links
- older or newer RHOAI versions without an explicit upgrade task
- upstream-only docs used as product authority
- copied examples with no official Red Hat source

## Source Ledger Template

Create `references/source-capture.md` inside the generated component skill:

```markdown
# Source Capture

## Official Product Source

| Field | Value |
|-------|-------|
| Product baseline | `docs/PLATFORM_BASELINE.md` |
| Chapter title | <official title> |
| Chapter URL | <versioned docs.redhat.com URL> |
| Documentation category | <Install/Administer/Develop/etc.> |
| Retrieved date | <YYYY-MM-DD> |
| Sections used | <section names or anchors> |

## Supporting Red Hat Sources

| Source | Role |
|--------|------|
| <Red Hat article/blog/product page> | Narrative, example, or implementation pattern |

## Source Boundaries

- Product configuration truth: official docs above.
- Narrative and examples: Red Hat articles/blogs and rh-brain.
- Verification: cluster schema commands listed in the generated skill.
- Not authoritative: upstream community docs unless explicitly labeled as
  supplemental background.
```

## Capture Rules

- Paraphrase official docs into project-specific guidance.
- Use short direct quotes only when exact Red Hat wording is required.
- Preserve official names exactly for APIs, CRDs, fields, statuses, and product
  features.
- Record unresolved or ambiguous items instead of filling gaps from memory.
- If a code example is needed, trace every field back to official docs or label
  it as a demo-specific example requiring schema verification.
