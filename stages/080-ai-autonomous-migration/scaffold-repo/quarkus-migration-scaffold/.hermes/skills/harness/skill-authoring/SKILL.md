---
name: skill-authoring
description: Author and verify skills per R-SK law and official layout
version: 1.0.1
author: rhoai3-harness-team
license: Apache-2.0
platforms: [linux]
metadata:
  hermes:
    tags: [skills, authoring, conformance, governance]
    category: harness
---

# Skill Authoring

## When to Use
Creating a new skill, editing any SKILL.md or skill subdirectory, moving
skills between categories, authoring a bundle manifest, or reviewing a staged
skill write (`/skills pending`). Consult BEFORE writing; run the lint BEFORE
landing.

## Procedure
1. Read `references/structure-law.md` (R-SK.1 layout + R-SK.7 categories) and
   place the skill: `analysis/` | `sdd/` | `gates/` | `harness/` |
   `migration/` (fixed set; Architect FINAL E-104706Z). Path-qualify
   `.hermes/skills/migration/` vs workspace `migration/` run-state.
2. Author frontmatter per `references/frontmatter-law.md` (R-SK.2): name =
   leaf directory, description ≤60 chars imperative, semver `version` (bump on
   EVERY content change), `author`, `license`, `metadata.hermes.tags` +
   `category` (must equal the parent directory).
3. Body per `references/body-template.md` (R-SK.3): `## When to Use` →
   `## Procedure` → `## Verification` required, `## Pitfalls` / `## Example`
   optional. Keep SKILL.md lean; depth goes to `references/*` (R-SK.4).
4. Helper logic ships as `scripts/*` — never inline-expected code (official
   authoring standard #6).
5. Validate: `python3 scripts/check-skill-conformance.py <skill-dir>` (or
   `--all --flat-ok` from the skills root until v13 mint). rc=0 required to
   land **new/edited** skills.
6. Bundles: validate manifests with `scripts/check-bundle-manifest.py`
   (skills must exist — official "missing skills are skipped, not fatal" is
   fail-open; our assert closes it).

## Verification
- `check-skill-conformance.py` on THIS skill → rc=0 (self-pass).
- New/edited skills pass the same lint before tip land.
- `--all --flat-ok` advisory until CS-6 #2 / v13 category move.
- Category directory == `metadata.hermes.category` for categorized skills.

## Pitfalls
- Description >60 chars breaks the selection house style (R9/R10 audit class).
- Editing a skill without bumping `version` defeats origin-hash drift
  detection (`.bundled_manifest` pattern).
- Path-anchored references in card bodies break on category moves — move
  skills only at mint boundaries (R-SK.7 rider).

## Example
`references/worked-example.md` mirrors the official published skill
(one-three-one-rule v1.0.0) with our frontmatter overlay applied.
