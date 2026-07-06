# Validation Checklist

Run this checklist before finishing a generated `rhoai-*` skill.

## Skill Structure

- Folder is under `.agents/skills/`.
- Folder name and frontmatter `name` match.
- Prefix is `rhoai-` for component/platform knowledge.
- Metadata includes:
  - `author: rhoai3-demo`
  - `platform-family: "rhoai"`
  - `platform-baseline: "repo"`
  - `ocp-baseline: "repo"`
  - `skill-group: "RHOAI Platform"`
- `SKILL.md` is concise and points to references instead of duplicating them.
- Reference files are one level below the skill folder.

## Source Grounding

- Generated skill points to `docs/PLATFORM_BASELINE.md`.
- `references/source-capture.md` records the official chapter URL, title,
  category, retrieved date, and sections used.
- Official RHOAI docs use the active baseline URL, not `/latest/`.
- Red Hat articles and rh-brain sources are labeled as narrative or examples,
  not product configuration truth.
- Unsupported, preview, or ambiguous items are labeled.

## Product Accuracy

- No CR field, API version, annotation, operator channel, image, or model
  artifact is invented.
- Every example manifest or command has an official source or verification
  command.
- Required namespaces, operators, and dependencies are explicit.
- Validation commands use readonly checks where possible.
- Live cluster commands are guarded by `AGENTS.md` safety rules.

## Repo Integration

When adding a new skill, update:

- `AGENTS.md`
- `.agents/rules/rhoai.md` for `rhoai-*` component skills
- `.agents/rules/project.md` for project meta-skills
- `.agents/skills/project-structure/SKILL.md`
- `.agents/skills/project-agent-guidance/SKILL.md`
- `.agents/skills/project-structure/references/rhoai-component-skill-roadmap.md`

## Static Checks

Run:

```bash
git diff --check
find .agents/skills -mindepth 1 -maxdepth 1 -type d | wc -l
rg -n "/latest/|TODO|FIXME|unsupported guess|invent" .agents/skills/<skill-name>
```

If a check is intentionally skipped, record why in the final response.
