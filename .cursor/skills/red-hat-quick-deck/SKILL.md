---
name: red-hat-quick-deck
metadata:
  author: shared-rhoai-demo
  version: 1.1.0
  rhoai-version: "3.4"
  ocp-version: "4.20"
description: >
 Create beautiful, shareable HTML-based slide presentations styled to Red Hat brand standards.
 Generates single-file, self-contained HTML decks with click/keyboard navigation, story-arc-driven
 narrative structure, and cinematic dark-mode aesthetics. Supports embedded videos (YouTube, Vimeo,
 direct URLs) and linked media (memes, GIFs, images) with brand-consistent styling. Use this skill
 whenever the user wants to create a slide deck, presentation, quick deck, quick slides, pitch deck,
 talk, or briefing that should follow Red Hat branding. Also trigger when the user mentions "quick deck",
 "quick slides", "HTML slides", "shareable deck", "presentation for [audience]", "talk about [topic]",
 or asks to present technical content in Red Hat style. This skill is specifically for HTML output; if
 the user explicitly asks for .pptx, use the pptx skill instead, but suggest this skill as an alternative
 for easy sharing. Do NOT use for live cluster operations, GitOps changes, resource management, or
 troubleshooting; use the project operations and troubleshooting skills instead.
---

# Red Hat Quick Deck

Generate self-contained HTML presentations that follow Red Hat brand standards and use a deliberate narrative arc.

## Before You Begin

1. Read `references/redhat-brand.md` for the Red Hat palette, typography, logo, and brand rules.
2. Read `references/story-arcs.md` for narrative structures and slide design principles.
3. Read `references/deck-design-system.md` when applying CSS, RHDS tokens, logo/icon treatment, media, or tag styling.
4. Read `references/deck-html-template.md` before writing the HTML skeleton or required slide types.
5. Read `references/deck-build-and-delivery.md` for narrative workflow, JavaScript navigation, animations, QA, media placement, and delivery rules.
6. Ask the user which visual mode they prefer:
   - Dark mode: cinematic, dark backgrounds, best for screens and presenting.
   - Light mode: clean, white backgrounds, best for print and email sharing.
   - Default to dark mode when the user does not specify.

## What This Skill Produces

A single `.html` file that:

- is self-contained with inline CSS and JavaScript
- can be opened in any browser, emailed, or hosted on any web server
- supports keyboard and click navigation
- includes a slide counter or progress indicator
- follows a persuasive story arc
- includes optional contextual notes toggled with the `N` key
- supports embedded video and linked media
- is responsive for mobile and async viewing

## Workflow

1. Identify the audience, goal, topic, output path, visual mode, and any source material.
2. Select a story arc from `references/story-arcs.md`.
3. Build the deck outline before writing slide HTML.
4. Use the HTML skeleton and slide patterns from `references/deck-html-template.md`.
5. Apply the design system from `references/deck-design-system.md`.
6. Add navigation, notes, media behavior, and quality checks from `references/deck-build-and-delivery.md`.
7. Validate that the deck opens locally, navigation works, text fits, media renders, and the file is self-contained.
8. Report the generated file path and any intentionally omitted or placeholder media.

## Reference Map

| Reference | Load when |
|-----------|-----------|
| `references/redhat-brand.md` | Any Red Hat branded deck work |
| `references/story-arcs.md` | Choosing narrative structure or slide sequence |
| `references/rhds-icons.md` | Selecting Red Hat Design System icons |
| `references/deck-design-system.md` | CSS, palette, typography, logo, icons, media, tags |
| `references/deck-html-template.md` | HTML skeleton and required slide types |
| `references/deck-build-and-delivery.md` | Build process, navigation JavaScript, animations, QA, delivery, media placement |

## Guardrails

- Keep output as HTML unless the user explicitly requests `.pptx`.
- Do not use this skill for cluster operations, GitOps changes, troubleshooting, or resource management.
- Do not embed private credentials, tokens, kubeconfigs, or private environment details in decks.
- Prefer references over expanding this `SKILL.md`; keep the entry point concise.
