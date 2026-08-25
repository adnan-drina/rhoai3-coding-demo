---
name: external-dirs-home-contract
skill-group: Demo Environment
applies-to:
  - gitops/stages/050-advanced-app-platform/base/devspaces/**
  - stages/080-ai-autonomous-migration/scaffold-repo/**/check-external-dirs.py
  - stages/080-ai-autonomous-migration/scaffold-repo/**/init-spec-workspace/**
---

# dest-init lists dest-user skills; the checker must not reinvent home

`check-external-dirs.py` required `Path.home()/.hermes/skills`. dest-init
writes hardcoded `/home/user/.hermes/skills`. Inside `hermes -p <assignee>`
those are different paths, so the M2 KEEP gate exited 1 on every profile
worker (Operator `104946ZO`). The worker then completed anyway.

**Canonical skills home slot = dest-init’s dest-user path**
`/home/user/.hermes/skills` (postStart `HOME`, `HERMES_GLOBAL_SKILLS_DIR`,
spec-kit `Path.home()` at dest-user `specify init` — spec-kit#3334 still
ignores `$HERMES_HOME`).

That is **not** the profile process home
(`$HERMES_HOME/profiles/<name>/home/.hermes/skills`). AMEND any reading
that treated worker `Path.home()` as the second required root.

Do not retarget this skills literal at the profile home to “fix” a
binary PATH. Tirith is retired (`122315ZO`); this gate is still about
the dest-user skills path dest-init listed.

Operator retracted the blast radius (`105355ZO`): the gate fires where
`init-spec-workspace` is pinned (M2), not on M3. The contract mismatch
still stands.

## Non-negotiable

1. Relocated assert requires **project**
   `/projects/modernized/.hermes/skills` **and** dest-user
   `/home/user/.hermes/skills` as dest-init lists them. Checker compares
   against those listed paths (or the dest-user literal), **not**
   `Path.home()` of the current process.
2. Do **not** retarget dest-init to each profile home to satisfy the
   checker. Spec-kit installs under dest-user home; implementer discovery
   of `/speckit-*` is the **project copy** (`125450Z`), not a second
   worker-writable tree.
3. Listing dest-user `~/.hermes/skills` on a profile is a **read** root
   for that install dump. It is not a grant to mutate
   `/home/user/.hermes/skills` from implementer. Do not widen
   `K2_ALLOW_ROOT` to `/home/user`.
4. Exit 1 from this KEEP gate is `kanban_block`, not `kanban_complete`.
   A gate a worker can walk past is not a gate (`104946ZO`).
5. Do not dest-cp dest-4 to land this. Lead lands golden dest-init +
   checker, then publish. Do not dest-wipe dest-4.

Official cite: `.agents/skills/hermes-skills/` External Skill Directories
(`~` / `${VAR}` expansion; missing dirs are skipped by Hermes itself —
our KEEP gate exists because skip is silent).
