# Stage README Standard

Each stage README is a concise Why/What document for a technical audience. It
should educate a new reader, explain the RHOAI value introduced by the stage,
and stay short enough to become a three-slide presentation segment.

GitOps manifests, deploy scripts, validation scripts, and the live demo show
How. Stage READMEs explain Why the stage matters and What Red Hat technologies
make it possible.

## Reader Promise

Each stage README should let an enterprise architect, platform engineer, or
developer experience team quickly answer:

- What concept is introduced in this stage?
- Why should a regulated enterprise care?
- What business or platform value does it provide?
- Which RHOAI, OpenShift, or Red Hat AI technologies enable it?
- Which components are new in this stage, and which were introduced earlier?

## Required README Shape

Use this shape for stage READMEs:

```markdown
# Stage NNN: Capability Name

## Why This Matters

## Architecture

## What This Stage Adds

## What To Notice And Why It Matters

## How Red Hat And Open Source Make It Work

## Trust Boundaries

## Red Hat Products Used

## Deploy And Validate

## Next Stage
```

The `## Demo` section is optional but recommended for all implemented stages
with a live environment. When present, place it after `## Architecture`. It
provides visual evidence of the stage working on a real cluster.

## Why This Matters

This section is the source for slide 1: concept and value.

Keep it short. Define the concept introduced by the stage and explain why a
regulated enterprise should care. Focus on the value to the audience, not
implementation mechanics.

Include:

- a plain definition of the concept in Red Hat terminology
- the enterprise concern it addresses, such as governance, control, cost,
  compliance, traceability, productivity, portability, safety, or scale
- the specific value this stage adds to the demo story
- at least one reference to official Red Hat documentation or product page

Do not use generic market claims when a Red Hat source exists.

## Architecture

This section is the source for slide 3: architecture delta.

The stage diagram must make the current stage components visually distinct from
previously introduced components. Preferred format is an ASCII or Mermaid
diagram inline in the README.

After the diagram, add a short architecture delta list:

```markdown
- New in this stage: <components introduced now>
- Already available: <relevant components from earlier stages>
- Value of the integration: <why the combined architecture matters>
```

The architecture diagram must accurately reflect all deployed components. If the
implementation changes, update the diagram in the same commit.

## What This Stage Adds

This section should be concise and capability-oriented:

- One short capability sentence plus four to six bullets.
- Prefer product/platform language.
- Mention CRs or resource names only when they are important teaching concepts.
- Avoid per-bullet manifest links; the stage manifest directory belongs in
  `Deploy And Validate`.
- Avoid YAML field paths, probe timings, patch jobs, sync hooks, and generated
  resource names unless they are central to the architecture story.

## References

References should be short and source-focused:

- official Red Hat docs for product configuration
- Red Hat product pages for concept/value
- links to `BACKLOG.md` only for actionable deferred capabilities
- links to `docs/OPERATIONS.md` or `docs/TROUBLESHOOTING.md` only when the
  reader needs the operational path or recovery procedure

## Demo Visual Evidence

Each stage README can include a `## Demo` section that provides annotated
screenshots and an animated GIF demonstrating the stage's customer-facing
outcome. This visual evidence serves the "How" slide in the three-part
presentation contract and proves the implementation works on a live cluster.

### Coverage Requirements

Screenshots should cover:

1. **At least one screenshot per key component introduced in the stage.**
   A "key component" is any technology listed in `## What This Stage Adds` that
   has its own visible surface in the RHOAI dashboard, OpenShift console, Argo CD,
   Grafana, or a custom application UI.

2. **At least one screenshot showing the final customer-facing demo result.**
   This is the moment a user (data scientist, AI engineer, platform admin)
   would see and interact with.

### Section Format

```markdown
## Demo

> Animated walkthrough of the main user-facing feature.

![Stage NNN demo](images/stage-NNN-demo.gif)

### Key Screens

| Screen | Component | What it shows |
|--------|-----------|---------------|
| ![alt](images/01-name.png) | Component Name | One-sentence description |
| ![alt](images/02-name.png) | Component Name | One-sentence description |
```

### Naming Convention

Screenshots live in `images/` within the stage directory with zero-padded sequence
numbers: `01-descriptive-name.png`, `02-descriptive-name.png`, etc. The
animated GIF is named `stage-NNN-demo.gif`.

### Screenshot Guidance

- Capture from the RHOAI dashboard or relevant application UI.
- Show the full browser viewport (1024x576 or similar 16:9) for context.
- Avoid capturing transient loading states unless they demonstrate a
  meaningful platform behavior.
- Annotate only when the screenshot alone is ambiguous.
- When a component is only visible from the OpenShift admin console (e.g.
  Kueue ClusterQueues, MachineSet status), capture the admin view.

### Animated GIF

The GIF stitches the key screenshots into a ~15-second walkthrough at 2-3
seconds per frame. It provides the "at a glance" demo experience for
stakeholders who will not run the live environment.

## Presentation Extraction Contract

Write READMEs so a future deck-generation skill can create three slides per
stage without guessing:

| Slide | README source | Purpose |
|-------|---------------|---------|
| 1 | `## Why This Matters` | Define the concept and explain why the audience should care |
| 2 | `## What This Stage Adds` | Explain the RHOAI and Red Hat technologies used |
| 3 | `## Architecture` + `## Demo` | Show new components in context; prove with visual evidence |

Keep each section concise enough that the deck generator can lift the main
message directly instead of summarizing long runbook content.

## Content Boundaries

- Stage READMEs should not be deployment runbooks.
- Do not include scripted walkthroughs, long command blocks, or repeated
  validation output.
- Put deployment order, environment preparation, shutdown/recovery, and day-2
  operations in `docs/OPERATIONS.md`.
- Put repeated symptoms, root causes, and repair procedures in
  `docs/TROUBLESHOOTING.md`.
- Put deferred capabilities and future enhancements in `BACKLOG.md`.

## Formatting

- Keep heading levels sequential.
- Use `-` for unordered lists.
- Add language identifiers to fenced code blocks.
- Use backticks for filenames, commands, config keys, and resource names.
- Use relative links within the repository.
- Prefer short paragraphs and compact tables.
