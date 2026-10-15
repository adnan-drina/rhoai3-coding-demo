---
name: project-rhoai-doc-chapter-skill-authoring
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  skill-group: "Project Structure"
description: >
  Create, update, or convert one rhoai-* skill from one official Red Hat
  OpenShift AI documentation chapter under the thin-skill contract: repo
  decisions with manifest paths, repo procedure, pitfalls, and links to the
  chapter's sections at the doc map's RHOAI version. Use when the user gives a
  docs.redhat.com RHOAI chapter URL or title, asks to turn a chapter into a
  skill, or asks to move an rhoai-* skill off copied documentation (for
  example from 3.4 captures to 3.5). For other product families use
  project-red-hat-doc-skill-authoring. Do NOT use for live cluster work or as
  product authority by itself.
---

# RHOAI Doc Chapter Skill Authoring

RHOAI-specific entry point for `project-red-hat-doc-skill-authoring`. That
skill's contract, citation rules, checklist and template apply unchanged:

- `.agents/skills/project-red-hat-doc-skill-authoring/SKILL.md` (contract, workflow)
- `.agents/skills/project-red-hat-doc-skill-authoring/references/extraction-rules.md`
- `.agents/skills/project-red-hat-doc-skill-authoring/references/validation-checklist.md`
- `.agents/skills/project-red-hat-doc-skill-authoring/examples/component-skill-outline.md`

## Input

One of: a docs.redhat.com RHOAI chapter URL, a chapter title, or a saved
export of the chapter. Optional: target skill name, component scope, consuming
stage. Split broad requests ("all install skills") into one skill per chapter
or tightly related component.

## RHOAI specifics

1. Version: the map's `products.rhoai.docs_version` (pinned to the
   `stable-<x.y>` channel in
   `gitops/stages/010-openshift-ai-platform-foundation/010-rhoai-operator/subscription.yaml`).
   A chapter URL of another version is re-pointed to that version before use;
   never `/latest/`.
2. Route: find the book and `topics` under `products.rhoai.categories` in
   `.agents/references/red-hat-doc-map.yaml`; add `sections` anchors and
   `reviewed` to the route you used.
3. Repo facts: the stage README and component READMEs under
   `gitops/stages/<stage>/` (their "Alignment with official guidance" tables
   already pair decisions with sections), `docs/TROUBLESHOOTING.md`, and
   `stages/<stage>/validate.sh`. An existing skill's "Repo decisions" table
   is the starting point; re-verify each row against the current repo.
4. Existing `references/working-configuration.md` or pattern files in an
   rhoai skill are repo-owned: keep them, but correct stale facts (GPU type,
   models, versions) in the same change.
5. Validate with `python3 .agents/tools/check-doc-links.py --family rhoai`
   plus the shared checklist.

## Hard rules

- Do not invent CR fields, API versions, annotations, operator channels,
  image names, model artifacts, support status, or anchors.
- Upstream Open Data Hub or community docs are not RHOAI product authority.
- If the chapter cannot be read, keep only what the repo proves and record
  the gap in the map route `note`.
