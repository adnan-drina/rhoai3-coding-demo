# Thin Product Skill Template

Copy, then replace every `<...>`. Keep it under ~150 lines. Converted examples:
`.agents/skills/odf-storagecluster/SKILL.md`, `.agents/skills/rhcl-configure/SKILL.md`.

```markdown
---
name: <prefix>-<capability>
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: <map product key, e.g. odf>
  docs-version: "<map docs_version, e.g. 4.22>"
  skill-group: "<group from platform-skill-taxonomy.md>"
description: >
  Use when <repo-specific situations, named resources and paths>. Do NOT use
  for <neighbour task> (use <other skill>).
---

# <Title>

Thin skill: repo decisions and pitfalls here, product behavior in the linked
<Product> <docs-version> sections. Detailed record: `<component README path>`.

## When to use

- <situation tied to a path or symptom>

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| <what this repo chose> | `<gitops/... path>` | [<section title>][<ref>] |

## Procedure

1. <repo step: file to change, script to run>
2. Validate after the OpenShift safety guard in `AGENTS.md`:

   ```bash
   <read-only oc commands or stage validate.sh>
   ```

## Pitfalls

- <product quirk or repo trap>, linked to [<section>][<ref>] or
  `docs/TROUBLESHOOTING.md#<anchor>`.

## Official documentation (<Product> <docs-version>)

| Topic | Section |
|---|---|
| <topic> | [<section title>][<ref>] |

## Related skills

`<skill>`, `<skill>`.

[<ref>]: https://docs.redhat.com/en/documentation/<docs_slug>/<docs_version>/html-single/<book>/index#<anchor>
```

Then add or update the route in `.agents/references/red-hat-doc-map.yaml`:

```yaml
          - book: <book_slug>
            status: active
            skill: <prefix>-<capability>
            sections:
              - <anchor-id>
            reviewed: { version: "<docs_version>", date: <YYYY-MM-DD> }
```
