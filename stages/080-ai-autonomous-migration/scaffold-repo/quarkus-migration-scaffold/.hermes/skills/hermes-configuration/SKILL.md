---
name: hermes-configuration
description: Cite Hermes docs before any config.yaml change.
version: 1.0.0
author: rhoai3-coding-demo
license: MIT
metadata:
  hermes:
    tags: config,kanban,skills,hooks,managed-scope
    category: platform
---

# Hermes configuration

AD-013 enablement package (CS-8). Packages official Hermes configuration
digests + URLs so config/Managed Scope/kanban/skills/hooks work cites
source without board archaeology. Sunset tag: **KEEP** (user-space
evidence) pending chain-end drift audit.

## When to Use

- Any change to `config.yaml`, Managed Scope (`HERMES_MANAGED_DIR`),
  `kanban.*`, `skills.*`, hooks, bundles, taps, or profiles.
- Class A tip work that touches Hermes runtime knobs (stream/stale,
  dispatch, write-approval, external_dirs).
- AD-013 citation duty when evaluating official vs homegrown mechanism.

Do **not** use for product Quarkus migration code (use phase skills).
Do **not** treat this skill as permission to lift serial HOLD or remint
M3 cards.

## Procedure

1. Identify the domain: `configuration` | `kanban` | `skills-governance` |
   `hooks`.
2. Load the matching digest via `skill_view(hermes-configuration, path)`:
   - `references/configuration.md`
   - `references/kanban.md`
   - `references/skills-governance.md`
   - `references/hooks.md`
3. Cite the **official URL + section** (AD-013 / R-OF.1) in the ledger or
   contract before changing behavior.
4. Respect Managed Scope precedence: pinned keys under
   `$HERMES_MANAGED_DIR` win; do not copy secrets into writable
   `$HERMES_HOME`.
5. Compare against VALIDATED examples under `examples/` (factory 5-liner,
   Managed Scope pin, AD-002E preload).
6. Validate on the live seat (`hermes config check` / `hermes doctor` /
   targeted probe) before claiming done.

Pointers to the CS-5 pack and W1 research doc:
`references/pointers.md`.

## Verification

- [ ] Entry or contract carries an official Hermes/OpenCode/spec-kit URL
      cite for the touched domain (AD-013).
- [ ] Change was checked against the matching `references/<domain>.md`.
- [ ] Managed Scope precedence respected (`HERMES_MANAGED_DIR` pin;
      no secret dual-home under `$HERMES_HOME`).
- [ ] Live-seat validation ran (`hermes config check` and/or domain probe).
- [ ] This skill passes
      `python3 .hermes/skills/harness-validate/scripts/check-skill-conformance.py . --skill hermes-configuration --strict`.

## Pitfalls

- Pointing at scattered board archaeology instead of this package (R9/R10).
- Setting `skills.write_approval: true` on headless Kanban seats (no
  approver → timeout-deny).
- Treating `external_dirs` as a write boundary — it is discovery only.
- Using `--accept-hooks` casually outside dispatcher profile workers.
- Wrapper Class A without R-OF.1 cite while BANK-CONV-LIVE is
  CHAIN-CRITICAL.
