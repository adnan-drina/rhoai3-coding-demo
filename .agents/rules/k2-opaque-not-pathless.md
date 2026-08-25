---
name: k2-opaque-not-pathless
skill-group: Demo Environment
applies-to:
  - stages/080-ai-autonomous-migration/scaffold-repo/**/pre_tool_call.sh
  - stages/080-ai-autonomous-migration/validate.sh
  - gitops/stages/050-advanced-app-platform/base/devspaces/**
---

# K2 denies opaque construction, not every pathless command

Architect `214743ZA` OBJECT’d cwd-ALLOW of **unproven** commands because
the dest-3 worker encoded paths and the hook saw no path token. The
landed reading treated **empty path set** as unproven and denied `mvn`,
`java`, and `git` — the toolchain M2/M3 exist to run (Operator
`E-20260825T085036ZO`, measured on live dest-4). A fence that blocks
permitted work manufactures the evasion it was landed to stop.

**AMEND `214743ZA`:** the discriminator is **opacity**, not path-presence.

Operator: `E-20260825T085036ZO`. Architect BIND: this sitting. Guardrail,
not claimed control (AD-020).

## Non-negotiable

1. **Opaque** construction **deny on every command**, including when an
   in-root path already proved the span set (Operator `090438ZO`).
   `_OPAQUE` must run **before** the `proven` gate. Prefixing
   `ls <in-root> &&` must not carry `base64 -d`. That is the dest-3
   vector made cheaper. Do not restore pre-`214743ZA` any-pathless cwd
   ALLOW.
2. **Transparent pathless** commands that act on cwd (`mvn -q verify`,
   `java -version`, `git status`) **allow** only if hook cwd realpath is
   inside `K2_ALLOW_ROOT`. Missing/unresolved cwd stays deny.
3. Do **not** close GAP 2 on `strip_env_assignments` alone. Assignment
   skip is necessary and **insufficient**.
4. Do **not** add an argv[0] allowlist. A decoder not on the list still
   passes — AD-020; do not dress this as containment.
5. Selftest must include proven-prefix encoded BLOCK
   (`ls <in-root> && ls $(echo … | base64 -d)`) plus dest-3-class 15/15
   and toolchain ALLOW. `validate.sh` must require `if cmd.strip():`
   before `for _rx in _OPAQUE`.
6. dest-4 live MATCH is **not** working-tree green. Operator `090943ZO`:
   commit+push `harness-v2`, `bootstrap-migration-scaffold-v2.sh`, Argo
   050 hard-refresh, dest-4 dest-init uptake, then seat `mvn -q verify`
   ALLOW **and** encoded proven-prefix BLOCK. Do not dest-apply. Do not
   auto-start M2. Do not widen `K2_ALLOW_ROOT`.
