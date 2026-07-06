# Validation Checklist

Run this checklist before finishing a generated Red Hat product skill.

## Skill Structure

- Folder is under `.agents/skills/`.
- Folder name and frontmatter `name` match.
- Prefix is one of:
  - `rhoai-` for RHOAI component knowledge
  - `ocp-` for OpenShift Container Platform knowledge
  - `odf-` for OpenShift Data Foundation knowledge
- Metadata includes:
  - `author: rhoai3-demo`
  - `platform-family: "rhoai"`, `"ocp"`, or `"odf"`
  - `platform-baseline: "repo"`
  - `ocp-baseline: "repo"`
  - matching `skill-group`
- `SKILL.md` is concise and points to references instead of duplicating them.
- Reference files are one level below the skill folder.

## Source Grounding

- Generated skill points to `docs/PLATFORM_BASELINE.md`.
- `references/source-capture.md` records product family, product version,
  official URL, title, category, retrieved date, and sections used.
- Official docs use the active baseline version when a versioned path exists.
- ODF skills are not generated until ODF version and source are pinned.
- Red Hat articles and rh-brain sources are labeled as narrative or examples,
  not product configuration truth.
- Unsupported, preview, deprecated, or ambiguous items are labeled.

## Product Accuracy

- No CR field, API version, annotation, operator channel, image, storage
  class, or recommended setting is invented.
- Every example manifest or command has an official source or verification
  command.
- Required namespaces, operators, subscriptions, and dependencies are explicit.
- Validation commands use readonly checks where possible.
- Live cluster commands are guarded by `AGENTS.md` safety rules.

## Repo Integration

When adding a new component skill, update:

- `AGENTS.md`
- `.agents/rules/<family>.md` if the family rule exists or this is the first
  skill in that family
- `.agents/skills/project-structure/SKILL.md`
- `.agents/skills/project-agent-guidance/SKILL.md`
- the relevant roadmap under `.agents/skills/project-structure/references/`

## Static Checks

Run:

```bash
git diff --check
find .agents/skills -mindepth 1 -maxdepth 1 -type d | wc -l
```

Also scan the generated skill for unversioned documentation paths,
placeholder markers, unverified assumptions, and invented product fields.

If a check is intentionally skipped, record why in the final response.
