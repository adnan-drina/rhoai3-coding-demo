---
name: tirith-declared-absent
skill-group: Demo Environment
applies-to:
  - gitops/stages/050-advanced-app-platform/base/devspaces/**
  - stages/080-ai-autonomous-migration/scaffold-repo/**/.hermes/**
---

# A declared security control must be present, or declared off

Hermes defaults `security.tirith_enabled: true` and
`security.tirith_fail_open: true` (official managed-scope Security keys).
Stage 080 overlay does **not** install the `tirith` binary. Dest worker
logs then open with “tirith security scanner enabled but not available —
command scanning will use pattern matching only.” That is AD-020’s
pathology **inside the runtime**: a control designs may cite that does
not exist, and it fails open.

Operator: `E-20260825T083840ZO`, AMEND `E-20260825T111519ZO`,
`E-20260825T113535ZO` (`Operator:GO-enable-tirith` GRANTED).

## Non-negotiable

1. **Enable on published golden dest-init for dest-5**, not dest-4.
   dest-init PATH prepend (Lead `113418ZL`) plus
   `security.tirith_enabled: true` as a set. dest-4 M4 receipts are
   contaminated (`113417ZR`); do not dest-edit dest-4 YAML to flip
   tirith.
2. The GO’s **proof** is Review dest-cite that a **profile worker**
   resolves tirith (`which tirith` = base `$HERMES_HOME/bin/tirith`),
   not merely that dest-init exports PATH. Until that MATCH, do not cite
   tirith as a dest control. `claimed_control` stays false.
3. Do **not** set `security.tirith_fail_open: false` until that worker
   MATCH. Official docs: fail-closed **blocks commands** when tirith is
   unavailable.
4. Do **not** install tirith in the 080 overlay this sitting (rebuild).
   Path honesty + enable-as-set is the land.
5. **KEEP** `assert-no-fence-evasion` in M4 fail-closed (AMEND
   `114617ZA` / Operator `115007ZO`). Tirith **ALLOW**s dest-3
   encode-then-exec (`base64 -d | xargs`); it blocks `curl | sh` and
   homographs. Disjoint classes — neither subsumes the other. K2 opacity
   stays. Do **not** publish `2dd339ac` (retire; native `pre_tool_call`
   **block** at `kanban_create`).
6. Official cite: `.agents/skills/hermes-managed-scope/` Security keys;
   `.agents/rules/profile-home-contract.md`.
