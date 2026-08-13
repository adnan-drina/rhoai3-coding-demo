# AD-011 skill extension law (R-AD011.1–5)

**Status:** binding proving-min
**Basis:** `20260810-harness-steering-skill-extensibility.md`

## Primacy

Hermes harness is a **primary product surface** of the migration workflow.
Users steer behavior via skills + contracts — **not** SOUL.

## Extension law

| ID | Rule |
|----|------|
| **R-AD011.1** | Demo-user overrides via (1) overlay `skills.external_dirs`, and/or (2) `HERMES_HOME` name-shadow, and/or (3) `references/` patches — **never SOUL**, never inject skill bodies into prompts (AD-002D). |
| **R-AD011.2** | Tip additive overlay: author under `extensions/<skill>/references/*`. Create/init **must** sync into `.hermes/skills/<skill>/references/` (R-M3.32) so in-skill `skill_view references/<file>` resolves — Hermes has no merge/`extends`. |
| **R-AD011.3** | Keep AD-002G attach matrix. Harness refuse/preflight stays in `governance/contracts` + scripts. **OBJECT** 1:1 new `SKILL.md` per workflow component. |
| **R-AD011.4** | Workshop starter lives under `workshop-extensions/` (see README). |
| **R-AD011.5** | Migration workers: prefer deny `skill_manage` + FS RO on golden `.hermes/skills/**` when the FS allows. **Headless Kanban:** `skills.write_approval: true` is **forbidden** (no approver → timeout-deny) — use `write_approval: false` and protect acks via AR-1.1. |
| **R-AD011.6** | Bundles DEFER (P2.4). |
| **R-AD011.7** | P1.3 HOLD stands except steward-named influence lifts. |

**Reject:** MiniMax · skill-pile dump · SOUL-as-extension · invent `extends:` frontmatter · mid-run tip rewrite on live tasks.

## Taxonomy

| Layer | Home | User extend? |
|-------|------|--------------|
| A attach | Phase matrix `SKILL.md` | Shadow whole skill (rare) |
| B L2 refs | `references/*` + `extensions/<skill>/references/*` | **Preferred** |
| C contracts | `governance/contracts` + scripts | Platform tip only |
| D human | human review packs | Out of worker attach |

## Overlay layout (tip)

```
extensions/<skill-name>/references/<topic>.md
workshop-extensions/README.md # how to wire external_dirs / shadow
```
