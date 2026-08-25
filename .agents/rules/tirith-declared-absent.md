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

Operator: `E-20260825T083840ZO`. Architect BIND on that Need.

## Non-negotiable

1. Dest `config.yaml` (dest-init and golden) MUST set
   `security.tirith_enabled: false` until a named GO ships the binary
   **and** turns the scanner on as a set.
2. Do **not** set `security.tirith_fail_open: false` while the binary is
   absent — official docs: that **blocks commands** when tirith is
   unavailable. Honesty is disable, not fail-closed on a missing tool.
3. Do **not** install tirith in the 080 overlay this sitting (new binary,
   pin, rebuild). Later GO only.
4. Do **not** edit dest-4 live profile YAML under a running worker.
5. Do not cite tirith as a dest control. `claimed_control` stays false.
   Official cite: `.agents/skills/hermes-managed-scope/` Security keys.
