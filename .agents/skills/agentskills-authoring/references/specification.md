# Agent Skills format specification (extract)

Source: https://agentskills.io/specification (captured 2026-08-13,
verbatim constraints).

## Directory structure

```
skill-name/
├── SKILL.md          # Required: metadata + instructions
├── scripts/          # Optional: executable code
├── references/       # Optional: documentation
├── assets/           # Optional: templates, resources
└── ...               # Any additional files or directories
```

## Frontmatter fields

| Field | Required | Constraints |
|---|---|---|
| `name` | Yes | Max 64 chars. Lowercase letters, numbers, hyphens only. Must not start/end with a hyphen. Must not contain consecutive hyphens. **Must match the parent directory name.** |
| `description` | Yes | Max 1024 characters. Non-empty. "Describes what the skill does and when to use it." |
| `license` | No | License name or reference to a bundled license file; keep it short. |
| `compatibility` | No | Max 500 chars. Only if the skill has real environment requirements (product, packages, network). "Most skills do not need the `compatibility` field." |
| `metadata` | No | Map from string keys to string values. "We recommend making your key names reasonably unique to avoid accidental conflicts." |
| `allowed-tools` | No | Space-separated pre-approved tools, e.g. `Bash(git:*) Bash(jq:*) Read`. **Experimental** — support varies. |

Valid names: `pdf-processing`, `data-analysis`, `code-review`.
Invalid: `PDF-Processing` (uppercase), `-pdf` (leading hyphen),
`pdf--processing` (consecutive hyphens).

Minimal example:

```markdown
---
name: skill-name
description: A description of what this skill does and when to use it.
---
```

## Body content

"There are no format restrictions." Recommended sections: step-by-step
instructions, examples of inputs and outputs, common edge cases. The
whole file loads on activation — split longer content into referenced
files.

## Progressive disclosure (the load ladder)

1. **Metadata** (~100 tokens) — `name` + `description`, loaded at startup
   for every available skill.
2. **Instructions** (<5,000 tokens recommended) — the full `SKILL.md`
   body, loaded on activation.
3. **Resources** (as needed) — `scripts/`, `references/`, `assets/`
   loaded only when required.

"Keep your main `SKILL.md` under 500 lines."

## File references

Use relative paths from the skill root ("See
[the reference guide](references/REFERENCE.md)"). "Keep file references
one level deep from `SKILL.md`. Avoid deeply nested reference chains."

## Optional directory conventions

- `scripts/` — self-contained or documented dependencies, helpful error
  messages, graceful edge-case handling.
- `references/` — focused files loaded on demand ("smaller files mean
  less use of context").
- `assets/` — templates, images, data files.

## Validation

```bash
skills-ref validate ./my-skill
```

Reference library: https://github.com/agentskills/agentskills/tree/main/skills-ref
