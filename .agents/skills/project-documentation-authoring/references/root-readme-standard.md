# Root README Standard

The root README is the home page of the project. It serves three audiences at
once: a presenter who needs to deliver the demo, an architect who needs to
evaluate the platform pattern, and a platform engineer who needs to deploy it.
The README must give each audience a clear entry point without forcing any of
them to read content meant for another.

## Design Principles

These principles are drawn from Red Hat's showroom content standard (the
`adv-app-platform-demo-showroom` index and overview pattern) adapted for a
single-page GitHub README:

1. **Story-first, not technology-first.** Open with the business problem the
   demo solves, not with a product list. Technology is the answer, not the
   question.

2. **Progressive sections.** Group stages into thematic sections that build on
   each other, each with a one-sentence positioning statement. The audience
   should see a clear maturity or capability progression.

3. **Concise stage descriptions.** Each stage gets one line in the stage table.
   The stage README carries the detail; the root README carries the navigation.

4. **Problem and value before solution.** Dedicate space to the business
   challenges and pain points the demo addresses. Quantify where possible.

5. **Audience-specific guidance.** Tell the reader how to use the demo for
   different customer conversations. Different personas (platform engineer,
   developer, security, executive) need different entry points.

6. **Common questions.** Anticipate the objections and questions a customer or
   internal stakeholder will raise. Answer them in the README so the presenter
   does not have to improvise.

7. **Separation of concerns.** The root README is an overview and navigation
   document. Deployment commands go in a short "Running The Workshop" section
   that points to ops docs. Product tables and open-source inventories go after
   the narrative sections, not before them.

## Required Shape

```markdown
# <Project Title>

## Why This Workshop Exists

## Architecture

## What We Are Building

## What The Demo Shows

## Why This Is Worth Knowing

## How Red Hat And Open Source Make It Work

## Trust Boundaries

## Running The Workshop

## Repository Map

## Demo Personas

## Red Hat Products Demonstrated

## Open Source Projects You Will Meet

## References
```

Not every section needs to be long. Some are a single paragraph or a compact
table. The ordering is intentional: Why/What/How narrative first, then
operational sections (Running, Repository Map, Personas), then reference tables
(Products, OSS, References) last.

### Why This Workshop Exists

The opening section. Lead with the business problem, not the technology. Name
the two or three enterprise concerns the demo addresses (e.g., control,
maturity, governance, cost, compliance). Use the demo's own language for the
core thesis.

Structure:

1. **The headline problem** — one or two sentences that name the challenge.
2. **The control dimension** — how the demo addresses governance, privacy,
   credential management, or regulatory concerns. Use bullets.
3. **The maturity dimension** — how the demo structures the developer journey as
   a progression (if applicable). Include the maturity ladder table if the demo
   has one. Each rung should name the stage number, the developer experience,
   and the tooling.
4. **The honest scope statement** — what the demo does NOT claim (e.g.,
   regulatory compliance, production readiness).

Keep this section to approximately 15–25 lines. The details live in stage
READMEs.

### What The Demo Shows

This section replaces a flat stage list with grouped, progressive sections.

Structure:

1. **Section grouping.** Group stages into 2–4 thematic sections (e.g.,
   "Platform Foundation", "Developer Maturity Ladder", "Governance and Trust").
   Each section gets:
   - a one-sentence positioning statement in italics
   - a bullet list of stages, each as one line: stage link + dash + short
     description

2. **Stage table.** After the grouped view, include a compact reference table
   with stage number, capability name (linked), and a single "Why it matters"
   sentence. This table is for scanning, not reading.

3. **Presenter guidance.** One paragraph explaining how to use the sections:
   which to present together, where to start for different audiences, which
   stage transitions have deliberate "aha" moments.

### Architecture

One architecture diagram (preferably the layered capability map SVG) plus a
brief paragraph. The diagram should show all stages at once and make the
progressive capability layers visible.

### Red Hat Products Demonstrated

A compact table: product name (linked) and role in the workshop. This is
reference material — it belongs late in the document.

### Open Source Projects You Will Meet

A compact table: project name (linked), where it appears, and what it
contributes. This is reference material.

### Running The Workshop

Keep this minimal:

1. Clone + env setup (3–5 lines of shell).
2. A note about prerequisites (OpenShift cluster, credentials).
3. The ordered deploy script list.
4. Links to `docs/OPERATIONS.md` and `docs/TROUBLESHOOTING.md` for details.

No inline explanations, no validation output, no recovery procedures. The ops
docs own that.

### Repository Map

A `tree`-style code block showing the top-level directory structure with
one-line comments. 10–15 lines maximum.

### Demo Personas

A compact table of demo users, their purpose, and which stages they appear in.

### References

A short list of official product documentation links. No inline articles or
blog posts — those belong in stage READMEs.

## Anti-Patterns

Avoid these in the root README:

| Anti-pattern | Why it fails | Fix |
|-------------|-------------|-----|
| Leading with product names | Reads like a datasheet, not a story | Lead with the business problem |
| Flat stage list with long descriptions | Reader skims and misses the progression | Group into sections, keep descriptions to one line |
| Deployment commands in the overview | Mixes concerns; breaks when commands change | Move to "Running The Workshop" section |
| Product/OSS tables before the narrative | Reader hits reference before understanding context | Put reference tables after the narrative |
| Claiming what the demo doesn't show | Reader finds gaps during the live demo | Add an honest scope statement |

## Relationship to Stage READMEs

The root README navigates to stage READMEs. It does not duplicate their
content. Each stage README carries the full Why/What/Architecture/Demo story
for that stage (see `readme-standard.md`). The root README carries only:

- the one-line stage description
- the section grouping and positioning
- the cross-cutting narrative (maturity ladder, trust boundaries, etc.)

## Relationship to Showroom Content

If the project also has an Antora showroom deployment, the root README and the
showroom index page serve different audiences:

- **Root README** — developers and agents reading the repository on GitHub.
  Must be self-contained as a single markdown file.
- **Showroom index** — presenters running the live demo from a deployed
  showroom. Can link to separate overview, details, and module pages.

The narrative, scenario, and section grouping should be consistent between the
two. The showroom may expand each section into a separate page; the README
keeps everything in one document.
