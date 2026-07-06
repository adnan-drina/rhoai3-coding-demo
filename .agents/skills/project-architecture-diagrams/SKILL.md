---
name: project-architecture-diagrams
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Documentation"
description: >
  Maintain and update the root and stage README architecture capability diagrams.
  Use when the user asks to update docs/assets/architecture/*.svg, change
  scripts/generate-architecture-diagrams.mjs, revise architecture diagram layout,
  apply Red Hat product-layer coloring, add or remove capabilities from the
  diagram, or distinguish new, previously introduced, and not-yet-introduced
  capabilities across stages. Also use when adding a new stage that needs to
  appear in the capability map. Do NOT use for live cluster troubleshooting (use
  rhoai-troubleshoot), deploying stages (use validate-demo-step), or creating
  presentations (use red-hat-quick-deck).
---

# Architecture Diagrams

Use this workflow to update the root and stage README architecture diagrams
without losing the project-specific visual story.

## Source Of Truth

- Generator: `scripts/generate-architecture-diagrams.mjs`
- Output directory: `docs/assets/architecture/`
- Root diagram: `docs/assets/architecture/rhoai-capability-map.svg`
- Stage diagrams: `docs/assets/architecture/stage-NNN-capability-map.svg`

Do not hand-edit generated SVG files. Update the generator, regenerate all SVGs,
and visually inspect representative root, early, middle, and final stage maps.

## Design Standard

The generator uses the Red Hat Layout B layered table pattern:

- Left product rail with product-colored backgrounds.
- Logical layer label column.
- Capability boxes to the right.
- Transparent outer SVG canvas (no background color).
- Dark neutral panels, gray borders, white text.
- Red Hat product-layer colors:
  - Red Hat Advanced Developer Suite layers: purple `#3d2785`.
  - Red Hat OpenShift AI layers: teal `#147878`.
  - Red Hat OpenShift / container platform layers: Red Hat red `#ee0000`.

### State Treatment

- **Root map**: all canonical capabilities are active, using dark fill plus a
  product-colored left stripe.
- **New in the current stage**: dark fill, heavy product-colored border, bold
  white text, drop shadow filter.
- **Previously introduced**: dark fill, gray border, white text, product-colored
  left stripe.
- **Not yet introduced / not demonstrated**: dimmed dark fill with opacity,
  muted text, gray border.

Do not use pale product fills for previously introduced capabilities; they look
too white in this dark design and compete with the current-stage highlight.

Stage maps should highlight capabilities introduced in the current demo stage
while keeping previously introduced components visible for architectural
context.

## Generator Architecture

The generator (`scripts/generate-architecture-diagrams.mjs`) is structured as:

1. **Stage definitions**: array of `[stageId, name, description]` tuples.
2. **Color palette**: Red Hat-aligned dark color tokens.
3. **Product definitions**: product labels and their primary colors.
4. **Row definitions**: logical layers with capabilities, each capability
   mapped to the stage where it is introduced.
5. **Layout constants**: canvas size, column positions, gaps.
6. **Rendering functions**: SVG element generators for capabilities, rows,
   product rail, legend, and full diagram.

The generator produces one root SVG (all capabilities active) and one SVG per
stage (highlighting that stage's new capabilities).

## Update Process

1. Read `README.md` and all active `stages/NNN-*/README.md` files.
2. Read `scripts/generate-architecture-diagrams.mjs`.
3. Identify the canonical root capability list from the demo story, stage
   READMEs, and generator data.
4. Map each capability to the stage where it is first introduced, preserving
   the current stage inventory.
5. Update `scripts/generate-architecture-diagrams.mjs`:
   - Add/modify/remove capability entries in row definitions.
   - Update stage list if stages are added or renamed.
   - Preserve the existing layout, color scheme, and rendering logic unless
     explicitly asked to change them.
6. Regenerate with `node scripts/generate-architecture-diagrams.mjs`.
7. Visually inspect representative SVGs.
8. Verify root README and stage READMEs reference the correct SVG paths.

## Validation

```bash
node scripts/generate-architecture-diagrams.mjs
git diff --stat docs/assets/architecture/
```

If any stage README references an SVG that no longer exists, update the
reference or regenerate the missing diagram.

## Expected Output

The final change should include:

- Updated generator (when capability list or layout changes).
- Regenerated root and stage SVGs.
- Any needed README updates (e.g., new stage needs SVG reference).
- A short validation summary noting what was visually inspected.

## When to Invoke This Skill

- A new stage is added to the demo.
- A capability is added, removed, or moved between stages.
- The product-layer structure changes.
- The user asks to "update the diagrams" or "regenerate architecture SVGs".
- A stage README references an outdated or missing diagram.
