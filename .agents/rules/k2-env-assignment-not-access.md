---
name: k2-env-assignment-not-access
skill-group: Demo Environment
applies-to:
  - stages/080-ai-autonomous-migration/scaffold-repo/**/pre_tool_call.sh
  - gitops/stages/050-advanced-app-platform/base/devspaces/**
---

# K2 must not treat environment-assignment values as access targets

The K2 `pre_tool_call` hook extracts POSIX-looking path spans from the
terminal command string. `export JAVA_HOME=/usr/lib/jvm/…` and
`export PATH=/bin:$PATH` then block as “resolves outside allow root”
(Operator `E-20260825T083840ZO`, reproduced against the hook). Those
spans are **values**, not cwd or argv access. M2/M3 compile Java and need
`JAVA_HOME`. A fence that blocks legitimate work manufactures the
evasion pressure it exists to prevent (dest-3).

Architect BIND: this sitting. Lead lands the hook. Do not dest-apply
onto dest-4 without a named GO. Not claimed control.

## Non-negotiable

1. `export NAME=value` and `NAME=value command` **assignments** are not
   filesystem access of `value`. Skip those spans. Command argv paths
   and cwd (`cd`, `cat`, redirects) still check.
2. Do **not** “fix” this by adding `/bin`, `/usr`, `/usr/lib/jvm`, or
   `/` to `K2_ALLOW_ROOT`. Dual-root stays dest tree + `/projects/legacy`
   (`214325ZA`).
3. Do **not** dest-complete leftover cards or auto-start M2. GAP 2 is a
   **precondition of M2**, not an M2 GO. Do **not** close GAP 2 on
   `strip_env_assignments` alone (`085036ZO`).
4. Opaque construction still denies (`214743ZA` as **amended**: opacity,
   not empty path set). Transparent pathless + cwd inside a grant allows.
   Rule: `.agents/rules/k2-opaque-not-pathless.md`.
