---
name: hermes-configuration
description: Official Hermes config sources, keys, and vetted examples
version: 1.0.0
author: rhoai3-harness-team
license: Apache-2.0
platforms: [linux]
metadata:
  hermes:
    tags: [configuration, harness, official-docs, governance]
    category: harness
---

# Hermes Configuration

## When to Use
Any change touching Hermes agent configuration in this project: `config.yaml`
(any seat), Managed Scope pins, `kanban.*` dispatcher keys, `skills.*`
governance (external_dirs, write_approval, bundles, taps), shell hooks,
profiles, or provider/model wiring. Consult BEFORE designing; AD-013 requires
citing the official section you relied on.

## Procedure
1. Identify the config domain; open the matching reference:
   - locations, precedence, Managed Scope → `references/configuration.md`
   - dispatcher/kanban keys → `references/kanban-config.md`
   - skills governance, bundles, taps → `references/skills-governance.md`
   - shell hooks, pre_verify, accept-hooks → `references/hooks.md`
2. Read the official recommendation there (each file quotes the doc and links
   the exact page/section).
3. Prefer the official mechanism; if it is insufficient, record why in your
   entry (AD-013 citation duty).
4. Copy the nearest vetted snippet from `examples/` and adapt; never hand-copy
   digests or secrets.
5. Validate on a live seat before landing (see Verification).

## Verification
- The proposing entry cites the official doc section (AD-013).
- Change validated against a live seat (`hermes config get` / seat restart /
  `hermes hooks doctor` as applicable).
- Managed Scope precedence respected: user-seat files never override pins.
- No secrets outside `.env`/Secret objects (official secrets rule).

## Example
Pin the worker model fleet-wide (Managed Scope, AD-008): see
`examples/managed-scope-pin.yaml` — admin-tier pin per the official line
"an administrator can pin specific config and secret values that a standard
user cannot override." Cite: user-guide/configuration §Managed Scope.
