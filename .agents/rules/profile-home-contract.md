---
name: profile-home-contract
skill-group: Demo Environment
applies-to:
  - gitops/stages/050-advanced-app-platform/base/devspaces/**
  - stages/080-ai-autonomous-migration/scaffold-repo/**
---

# Profile workers have three homes; dest-init must name each

Operator `111519ZO` / `122315ZO`: dest is a container. Official
`terminal.home_mode: auto` uses `{HERMES_HOME}/home` as `HOME`. Tirith is
**retired** (`122315ZO`); it is not why dest-init lists dest-user skills.

Official (`hermes-configuration` profiles): **`HERMES_HOME` is the
profile boundary**; **`HOME` is the OS/CLI home**. They are not
interchangeable.

## The three paths (dest-4 measured)

| Layer | Dest path | Who sees it |
|---|---|---|
| Base `HERMES_HOME` | `/projects/modernized/.hermes/home` | dest-init, dest-user CLI |
| Profile `HERMES_HOME` | `…/home/profiles/<name>` | `hermes -p <name>` / kanban spawn |
| OS `HOME` | dest-user `/home/user` at postStart; `{HERMES_HOME}/home` in a profile worker | `Path.home()`, spec-kit, host CLIs |

Spec-kit still dumps under dest-user `/home/user/.hermes/skills`
(spec-kit#3334 ignores `$HERMES_HOME`).

## Three questions (Operator `112106ZO`, AMEND `122315ZO`)

1. **Tirith:** **retired.** Managed pin `security.tirith_enabled: false`
   (Hermes default is `true`). Do **not** prepend base
   `$HERMES_HOME/bin` to PATH (`112249ZA` / `113418ZL` superseded). Do
   **not** set `tirith_fail_open: false`. Residual: Hermes may still
   auto-download the binary to `$HERMES_HOME/bin` (`cli.py
   ensure_installed` before the flag). That is not a dest control.
2. **`skills.external_dirs`:** dest-init dest-user
   `/home/user/.hermes/skills` plus project `.hermes/skills`
   (`external-dirs-home-contract.md`). Not a required per-profile skills
   dir. Checker uses that literal / `human_home()`, not `Path.home()`.
   **Specify at run:** worker `Path.home()` is the profile home (0 speckit
   skills). dest-init installs a `specify` PATH shim that sets `HOME` to
   the project **for that child only** so `specify workflow run speckit`
   resolves `speckit-specify` without collapsing the three homes
   (Operator `091320ZO`). Do not tell workers to prefix `HOME=` — dest-6
   and dest-7 showed they will not.
3. **Python `human_home()`:** **yes.** Same contract as
   `mta-analyze-legacy.sh` (`getent passwd` OS account, not `$HOME`).
   Land in dest `.hermes/lib/` beside `path_maps.py`. KEEP gates that
   mean dest-user home **must** call it (or take the path as an explicit
   argument). `Path.home()` in a Python KEEP gate is the defect
   signature unless the contract is literally “this process’s CLI HOME”
   **and** `terminal.home_mode` is cited. `assert-extension-tooling.py`
   is in that set.

## Non-negotiable

1. **Do not collapse the three paths.** dest-init dest-user
   `/home/user/.hermes/skills` remains the listed skills **read** root
   (`external-dirs-home-contract.md`). Checker still must not use worker
   `Path.home()`.
2. **Do not dest-edit dest-4 live profile YAML** under leftover cards.
   Land golden dest-init; dest-5 / next dest absorbs it.
3. **KEEP** `assert-no-fence-evasion` in M4 fail-closed (Operator
   `115007ZO` / `122315ZO`). K2 opacity `pre_tool_call.sh` stays
   (`k2-opaque-not-pathless.md`). AMEND `114617ZA` demote.
4. **Retire** `assert-m3-card-contract` / `2dd339ac` — do not publish,
   do not keep as an M4 board audit (same post-hoc walkable shape).
   Dest `pre_tool_call` **block**s illegal `kanban_create` (exit 2 /
   `{"action":"block"}`, `fail_closed: true`). Official `hermes-hooks`
   names `block` / `approve` only — OBJECT `modify` as Gate K contract.
   `k4_mint.py` emits legal argv so rewrite is not the control. Kanban
   lifecycle hooks fire **after** the DB write and cannot veto create.
5. **`k4_convert.py` stays.** Native `kanban decompose` is LLM-driven.
   K4 is deterministic over a typed partition. That is the stated reason
   (Operator `111519ZO`).
6. **M4 must not mint floor receipts.** Writing
   `evidence/verdicts/` refusal JSON during M4 so
   `assert-pinned-gates-ran` turns green is the walked-KEEP shape
   (Review `112040ZR`). If a pinned gate never ran, M4 `kanban_block`.
   Do not dest-complete leftover dest-4 cards around that.
7. **SOUL.md is per profile home.** dest-init places dest-user identity
   at base `HERMES_HOME/SOUL.md` and each worker's authored
   `{name}.SOUL.md` at `profiles/<name>/SOUL.md`. OBJECT `--clone` as
   the copy (EX-4). Workers must not share dest-user identity.

Official cite: `.agents/skills/hermes-configuration/` HERMES_HOME vs HOME
and `terminal.home_mode`; `.agents/skills/hermes-hooks/` `pre_tool_call`.
