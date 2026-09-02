---
name: agentskills-authoring
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "agentskills"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Agent Skills Standard"
description: >
  Use whenever creating a new Agent Skill or modifying an existing one in
  this project — writing or editing any SKILL.md, choosing what belongs in
  the body vs references/, structuring scripts and assets, or deciding
  whether a capability should be a skill at all. Encodes the official
  agentskills.io creation guidance and format specification. Do NOT use
  for this repo's own taxonomy conventions (use maintain-rules-and-skills)
  or for writing the description field (use agentskills-descriptions).
---

# Authoring Agent Skills (official standard)

Consult this BEFORE writing or editing any `SKILL.md` in this repository.
It encodes agentskills.io — the open standard our `.agents/skills/` path
is the default discovery location for, and the standard Hermes skills
declare compatibility with.

## Source Grounding

Official pages (captured 2026-08-13, see `references/source-capture.md`):
Quickstart, Best practices, Specification. Format constraints live in
`references/specification.md`.

## How a skill is consumed (why structure matters)

Three stages: **discovery** (at startup the agent reads only `name` and
`description` — ~100 tokens per skill), **activation** (on a match it
loads the entire `SKILL.md` body), **execution** (it follows the body,
loading `references/`, `scripts/`, `assets/` only when told to). That is
progressive disclosure, and every structural rule below follows from it.

## Format essentials

A skill is a directory containing `SKILL.md`, optionally `scripts/`,
`references/`, `assets/`. Required frontmatter: `name` (≤64 chars,
lowercase alphanumerics + single hyphens, no leading/trailing/consecutive
hyphens, **must match the parent directory**) and `description` (≤1024
chars, non-empty). Optional: `license`, `compatibility` (≤500 chars, only
if there are real environment requirements), `metadata` (string→string
map), `allowed-tools` (experimental). Full table and examples:
`references/specification.md`.

**Size targets**: keep `SKILL.md` under **500 lines and ~5,000 tokens**.
Reference files stay one level deep from the skill root, referenced by
relative path.

## Start from real expertise (the highest-leverage rule)

"A common pitfall in skill creation is asking an LLM to generate a skill
without providing domain-specific context… The result is vague, generic
procedures ('handle errors appropriately') rather than the specific API
patterns, edge cases, and project conventions that make a skill
valuable." Two documented sourcing methods:

- **Extract from a hands-on task** — do the real work with an agent, then
  harvest: steps that worked, corrections you made, input/output formats,
  and project context the agent lacked.
- **Synthesize from project artifacts** — runbooks, API specs, code
  review comments, git history (especially fixes), real failure cases.
  "The key is project-specific material, not generic references."

Then **refine with real execution**: run the skill on real tasks and feed
back all results, not just failures. "Even a single pass of
execute-then-revise noticeably improves quality." Read execution traces,
not just outputs — wasted steps signal vague instructions, inapplicable
instructions, or too many options without a default.

## Spend context wisely

- **Add what the agent lacks, omit what it knows.** Ask of every line:
  "Would the agent get this wrong without this instruction?" If no, cut
  it. If the agent already does the whole task well, the skill may not be
  adding value at all.
- **Design coherent units** — "like deciding what a function should do".
  Too narrow forces multiple skills per task; too broad can't activate
  precisely.
- **Aim for moderate detail.** "Concise, stepwise guidance with a working
  example tends to outperform exhaustive documentation."
- **Push depth into `references/` with a load trigger.** "Read
  `references/api-errors.md` if the API returns a non-200 status code" is
  more useful than "see references/ for details."

## Calibrate control to fragility

- **Freedom** where multiple approaches are valid — and explain *why*, so
  the agent can make context-dependent decisions.
- **Prescription** where operations are fragile or order matters ("Run
  exactly this sequence… Do not modify the command").
- **Defaults, not menus** — pick one tool, mention alternatives briefly.
- **Procedures over declarations** — teach how to approach a class of
  problems, not the answer to one instance.

## Patterns worth reaching for

| Pattern | Use it for |
|---|---|
| **Gotchas section** | Environment facts that defy reasonable assumptions ("the `users` table uses soft deletes"). Keep in `SKILL.md` — the agent may not recognize the trigger to load a reference. |
| **Output templates** | Concrete structures beat prose descriptions; long ones go in `assets/`. |
| **Checklists** | Multi-step workflows with dependencies or gates. |
| **Validation loops** | Do work → run validator → fix → repeat until it passes. |
| **Plan-validate-execute** | Batch/destructive ops: emit a plan, validate it against a source of truth, only then execute. |
| **Bundled scripts** | When traces show the agent reinventing the same logic every run, write it once into `scripts/`. |

When an agent makes a mistake you correct, add the correction to Gotchas —
"one of the most direct ways to improve a skill iteratively".

## Workflow

1. Confirm the capability deserves a skill (coherent unit; agent doesn't
   already handle it well).
2. Source content from real expertise — never generic LLM generation.
3. Draft `SKILL.md`: frontmatter per `references/specification.md`, body
   with the minimum the agent lacks, depth to `references/` with load
   triggers.
4. Calibrate each section's prescriptiveness independently.
5. Optimize the description (see `agentskills-descriptions`).
6. Prove it with evals (see `agentskills-evaluation`).
7. Apply this repo's own conventions on top (see
   `maintain-rules-and-skills`) — they are stricter, never looser.

## Validation

```shell
# Bundled spec checker (name pattern/length, description ≤1024,
# <500-line target, reference depth) — run before landing any skill:
python3 .agents/skills/agentskills-authoring/scripts/validate-skills.py \
        .agents/skills/<name>
python3 .agents/skills/agentskills-authoring/scripts/validate-skills.py --all

# Official reference validator, if installed:
skills-ref validate ./path/to/skill
```

Known repo state (2026-08-13): 14 `rhoai-*` skills exceed the 1024-char
description limit — generated before this standard was adopted. Do not
add new violations; see `references/source-capture.md`.

## Pitfalls

- Generating a skill from an LLM's general knowledge — the documented
  #1 pitfall; produces generic filler.
- Explaining what the agent already knows (what a PDF is, how HTTP
  works) — pure context tax.
- A `references/` file with no stated load trigger — it either loads
  never or always.
- Presenting a menu of equivalent options — pick a default.
- Encoding one specific answer instead of a reusable method.
- Letting `SKILL.md` sprawl past ~500 lines instead of splitting.
- Name/directory mismatch, uppercase, or consecutive hyphens — hard spec
  violations.

## Related Skills

- `agentskills-descriptions` — the description field and its triggering
  evals.
- `agentskills-evaluation` — proving the skill improves outputs.
- `maintain-rules-and-skills` — this repo's taxonomy layered on top.

## References

- `references/source-capture.md`
- `references/specification.md`
