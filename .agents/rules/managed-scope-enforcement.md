---
name: managed-scope-enforcement
skill-group: Demo Environment
applies-to:
  - gitops/stages/050-advanced-app-platform/base/devspaces/**
  - stages/080-ai-autonomous-migration/scaffold-repo/**
---

# PVC Managed Scope is precedence, not enforcement

Official (`hermes-managed-scope`): enforcement is **filesystem
permissions**; default `/etc/hermes` is root-owned. Relocate with
`HERMES_MANAGED_DIR` baked into the **image or unit** — a user who can
set it can repoint managed scope.

Operator `120434ZO` / Review `121000ZR` dest-4: managed dir
`/projects/.platform/hermes` is `user:user`; `config.yaml` and K2
`pre_tool_call.sh` are **writable by the workspace uid**. `hermes doctor`
“41 keys pinned” is precedence, not a boundary. AD-020’s fence is weaker
still: the agent can rewrite the hook, not only encode around it.
`claimed_control` stays false.

## Non-negotiable

1. Do **not** cite PVC Managed Scope, `doctor` pinned-count, or a
   writable K2 script as containment. Guardrail against accident (AD-020)
   still holds; it is not an intent boundary.
2. **Native location is `/etc/hermes` in the overlay image** (already
   root-owned, agent cannot write). Bake immutable pins **and** the hook
   **script** there. dest-init as the workspace user cannot `chown` to
   root — do not ask it to. Pin `hooks:` at the image path so the PVC
   copy is not the live script.
3. **Split keys (Lead after dest-5, not before the cut):**
   - **Immutable (image):** `security.*` (including retired
     `tirith_enabled: false`), hook declaration + script, model pin, no
     `fallback_providers`, orchestrator `disabled_toolsets`,
     `K2_ALLOW_ROOT` policy.
   - **Per-dest remainder (dest-init / dest config):** legacy URL,
     cluster MAAS base URL / service-CA wiring, dest identity. Secrets
     stay Managed Scope rules (no high-sensitivity in world-readable
     `.env`).
4. **Tirith is retired** (Operator `122315ZO`). dest-init pins
   `security.tirith_enabled: false`. Do not enable it, do not
   `tirith_fail_open: false`, do not restore the base-PATH prepend.
5. **dest-5 cuts before this split.** Overlay bake is a later named GO
   (image rebuild). dest-5 uses the published golden after tirith
   retirement. Review dest-5 `stat` of managed files will likely still
   show writable — that MATCH documents the known gap, it does not
   block Gate K. Architect does **not** grant `GO-cut-dest-5`
   (Operator’s). Lead does **not** start the split this sitting.

Official cite: `.agents/skills/hermes-managed-scope/` enforcement
ceiling and `HERMES_MANAGED_DIR`.
