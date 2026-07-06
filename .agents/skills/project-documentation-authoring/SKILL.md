---
name: project-documentation-authoring
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Documentation"
description: >
  Author and improve rhoai3-coding-demo documentation: root README, stage
  READMEs, docs/OPERATIONS.md, docs/TROUBLESHOOTING.md, BACKLOG.md, and
  supporting docs. Use when creating or updating demo prose, adding architecture
  sections, introducing platform concepts (Private AI, GPU-as-a-Service,
  Models-as-a-Service, MCP, governed access), improving narrative alignment,
  preparing concise Why/What README content for later slide generation, adding
  demo visual evidence (screenshots and animated GIFs), or routing captured
  project knowledge to the correct documentation home. Pair with
  project-demo-stage-authoring when creating a new stage end to end. Do NOT use
  for GitOps manifest authoring (use review-gitops-change), live cluster
  troubleshooting (use rhoai-troubleshoot), or operational runbooks from scratch
  (use demo-operations-docs).
---

# Documentation Authoring

Use this skill to keep repo documentation clear, demonstrable, and aligned with
official Red Hat messaging and the implemented demo story.

## Workflow

1. Identify the documentation home before writing:
   root README for demo overview, stage README for concise Why/What story,
   `docs/OPERATIONS.md` for runbooks, `docs/TROUBLESHOOTING.md` for recovery,
   `BACKLOG.md` for deferred capabilities and future work.
   For a new stage, start with `project-demo-stage-authoring`.
2. Read the relevant existing document before changing it.
3. Confirm whether a companion manifest, script, README, or operations document
   change is required.
4. For README concept introductions, consult official Red Hat documentation and
   product pages for the relevant product versions to define the concept and
   enterprise value.
5. For stage README structure and presentation style, read
   `references/readme-standard.md`.
6. For implementation detail boundaries in READMEs, read
   `references/implementation-detail-boundary.md`.
7. For demo visual evidence (screenshots, GIFs, `## Demo` section), read
   the "Demo Visual Evidence" section in `references/readme-standard.md`.
8. For continuous documentation and troubleshooting knowledge capture, read
   `references/knowledge-governance.md`.
9. After substantive README edits, verify alignment using the
   `update-demo-docs` skill's consistency checks.

## Documentation Principles

- Stage READMEs are concise Why/What documents, not deployment runbooks.
- Stage READMEs should introduce the concept first, explain why a
  regulated enterprise should care, and cite Red Hat documentation.
- Stage READMEs should support a three-part presentation extraction contract:
  concept/value (Why), technology enablers (What), and architecture delta +
  demo visual evidence (How).
- Each stage README should include a `## Demo` section with annotated
  screenshots (at least one per key component, at least one customer-facing
  result) when visual evidence is available. Visual evidence lives in
  `docs/assets/demos/stage-NNN/`.
- Implementation details that affect understanding, troubleshooting, or
  cross-stage dependencies belong in the README. Operational procedures and
  step-by-step commands do not. See `references/implementation-detail-boundary.md`.
- Operational runbook detail belongs in `docs/OPERATIONS.md`.
- Failure recovery detail belongs in `docs/TROUBLESHOOTING.md`.
- Future or deferred capabilities must be labeled explicitly and tracked in
  `BACKLOG.md` when they are actionable project work.
- References sections should point to official Red Hat docs for the active
  product baseline.

## References

- `references/readme-standard.md`
- `references/implementation-detail-boundary.md`
- `references/knowledge-governance.md`
