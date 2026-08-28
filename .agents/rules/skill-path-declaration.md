---
name: skill-path-declaration
skill-group: Demo Environment
applies-to:
  - stages/080-ai-autonomous-migration/scaffold-repo/**/SKILL.md
  - gitops/stages/050-advanced-app-platform/base/devspaces/**
---

# Skills declare paths they touch; dest-init fail-closes, not mid-run

Workers should not discover allow-root by being refused. dest-init
reconciles each skill’s declared paths against `K2_ALLOW_ROOT` and
**fails closed at init** when a declared path is outside every grant
(Operator `E-20260825T083840ZO` GAP 4). Same move as `assert-zip-exec-bits`:
check the invariant where it can still be fixed.

Follows GAP 2 (env-assignment) and GAP 3 (derived root). **Not** a dest-4
M2 blocker. Do not invent devfile schema. Do not copy this into dest
AD-020.

## Non-negotiable

1. Golden analysis/migration skills declare the path **classes** they
   read or write (legacy harvest, dest tree, derived output, tool
   prefixes they *invoke* vs trees they *mutate*).
2. dest-init fail-closed on a declared path outside `K2_ALLOW_ROOT`.
   Mid-run surprise is the defect, not the design.
3. **Derived output** defaults **inside** a grant — dest tree
   (`/projects/modernized/.derived/…`), not `/projects/.derived`.
   OBJECT adding `/projects/.derived` or `/opt/kantra` to allow-root
   (`214325ZA`, `082958ZA`).
4. Do not widen allow-root to make an undeclared path pass.
5. Consult `agentskills-authoring` before editing dest `SKILL.md`.
