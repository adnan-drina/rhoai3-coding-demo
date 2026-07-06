# Source Capture

Use this reference before writing a generated Red Hat product skill.

## Baseline Gate

Read `docs/PLATFORM_BASELINE.md` and verify:

- product family is pinned in the baseline, or the user has asked to pin it
- documentation URL uses the matching product and version path
- chapter or page belongs to official Red Hat documentation, Customer Portal,
  or another official Red Hat source
- source category is recorded, or an exception is documented

Reject or flag:

- unversioned latest documentation paths when a versioned path exists
- older or newer product versions without an explicit upgrade task
- ODF sources before an ODF baseline is pinned
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
| Product family | <RHOAI/OCP/ODF> |
| Product version | <version from baseline> |
| Chapter or page title | <official title> |
| Source URL | <versioned docs.redhat.com or official Red Hat URL> |
| Documentation category | <Install/Administer/Networking/Storage/etc.> |
| Doc-map route | `.agents/references/red-hat-doc-map.yaml` -> `<product>.<category>.<book/topic>` |
| Mapped skill | `<rhoai-*|ocp-*|odf-*>` |
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
- Preserve official names exactly for APIs, CRDs, fields, statuses, product
  features, operators, channels, and images.
- Record unresolved or ambiguous items instead of filling gaps from memory.
- If a code example is needed, trace every field back to official docs or label
  it as a demo-specific example requiring schema verification.
