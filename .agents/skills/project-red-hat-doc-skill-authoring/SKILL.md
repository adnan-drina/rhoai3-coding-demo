---
name: project-red-hat-doc-skill-authoring
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  skill-group: "Project Structure"
description: >
  Create, update, or convert a Red Hat product skill (rhoai-*, ocp-*,
  ocp-devspaces-*, ocp-lightspeed-*, ocp-pipelines-*, odf-*, rhcl-*, rhdh-*,
  mta-*) under the thin-skill contract: repo decisions with
  manifest paths, repo procedure, pitfalls, and links to versioned official
  sections, with versions and provenance in .agents/references/red-hat-doc-map.yaml.
  Use when adding a product skill, converting a family away from copied
  documentation, upgrading a product's documentation version, adding a doc-map
  route, or deciding which family a Red Hat source belongs to. Do NOT use for
  live cluster deployment or troubleshooting (use the stage validate scripts
  and rhoai-troubleshoot), or as product authority by itself.
---

# Red Hat Doc Skill Authoring

Product skills in this repo are thin. They hold what an agent cannot get from
Red Hat documentation — this repo's decisions, procedures and pitfalls — and
link to the official sections for everything else. The single version and
routing registry is `.agents/references/red-hat-doc-map.yaml`; the checker is
`.agents/tools/check-doc-links.py`.

## Contract (binding for new or updated product skills)

- `SKILL.md` only, under ~150 lines. `references/` only for repo-owned
  material (working configuration, repo patterns); never copied product text.
- No `official-doc-extraction.md`, no `source-capture.md`. Provenance goes into
  the map route: `sections` (anchor ids) and `reviewed: {version, date}`.
- Frontmatter `metadata.product` (map key) and `metadata.docs-version` (the
  version the skill was reviewed against; must equal the map's docs_version).
- Body sections, in this order: When to use; Repo decisions (table: decision,
  path under `gitops/` or `scripts/`, official section link); Procedure (repo
  commands and validation); Pitfalls; Official documentation (table of
  versioned links with anchors); Related skills.
- Links use `docs_url_template` with the map's `docs_version`; never `/latest/`
  or another version. Link sections (`#anchor`), not whole books, when a
  section exists.
- Short quotations are allowed only for names a decision depends on (field,
  API version, channel, command). Do not paraphrase procedures, tables, or
  examples from the docs.

Why linking, not copying: Red Hat documentation is licensed CC BY-SA 3.0
(attribution and share-alike apply to copies and adaptations; see
docs.redhat.com/legal-notice). Copies also go stale silently on every product
release. Links plus repo decisions keep the repo's own license choice open and
make a version bump a checkable worklist. Not legal advice.

## Workflow

1. Find the product and route in the map. Use the routed skill when one
   exists; add a route (with `sections`) when a new book or skill is needed.
2. Check the pin: the map's `docs_version` must equal the Git pin it names
   (Subscription channel, `startingCSV`, or operator policy). If the Git pin
   moved, update the map first.
3. Collect the repo facts: manifests, component README ("Why/What/How",
   "Alignment with official guidance"), `docs/TROUBLESHOOTING.md`, and the
   stage validate scripts. Repo facts are the skill's content.
4. Read the official sections of `docs_version` that each decision depends on
   (WebFetch or a browser). docs.redhat.com may answer 403/429/503 to
   automated clients: then say in the skill or the map route note what could
   not be verified. Never invent a field, channel, version, or anchor.
5. Write `SKILL.md` from `examples/component-skill-outline.md`. Each kept
   product claim must be verified against `docs_version` and linked.
6. When converting, classify each old extraction item (see
   `references/extraction-rules.md`): delete generic behavior and link it;
   keep facts the repo depends on as one-line decisions or pitfalls; replace
   YAML/CLI examples with a pointer to the repo manifest. Delete the
   extraction and source-capture files; record the last commit that held them
   in the commit message.
7. Validate:

   ```bash
   python3 .agents/skills/agentskills-authoring/scripts/validate-skills.py --all
   python3 .agents/tools/check-doc-links.py --family <family>
   python3 .agents/tools/check-doc-links.py --live --family <family>   # optional, rate limited
   ```

8. Add each converted skill to `converted_skills` in the map so the checker
   fails on its regressions while the rest of the family is pending. When a
   family has no findings left, add it to `converted_families` and drop its
   `converted_skills` entries.

## Upgrading a product version

Follow `route_update_rules.when_upgrading_product` in the map: Git pin first,
then `docs_version`, then the checker's worklist (each skill and README link
behind), then re-read release notes and cited sections and bump each skill's
`docs-version`.

## Inventory

- Map route for every product skill (the checker reports `UNROUTED`).
- `AGENTS.md` Shared Skills table only if the family row lists names.
- Family rule (`.agents/rules/<family>.md`) only for cross-family handoffs and
  always-on posture; routing lives in the map.

## Hard Rules

- Do not invent CR fields, API versions, annotations, operator channels, image
  names, storage classes, support posture, or anchors.
- Upstream community docs and rh-brain are not Red Hat product authority.
- Do not create nested skill folders to mirror documentation categories.
- If an official source cannot be read, write only what the repo itself
  proves and mark the gap.

## References

- `references/extraction-rules.md` — what to keep, link, or delete
- `references/platform-skill-taxonomy.md` — families, prefixes, skill groups
- `references/validation-checklist.md` — review before finishing
- `examples/component-skill-outline.md` — the thin template
- `.agents/references/red-hat-doc-map.yaml` — versions, pins, routes, provenance
