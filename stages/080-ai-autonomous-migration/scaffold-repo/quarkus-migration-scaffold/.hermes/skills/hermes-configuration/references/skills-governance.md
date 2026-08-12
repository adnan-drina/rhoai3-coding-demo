# Skills governance

**Official page:** https://hermes-agent.nousresearch.com/docs/user-guide/features/skills

**CS-5 cross-pointer:**
`harness-refactoring/source-analysis/hermes/20260812-official-kanban-alignment.md`

## Config knobs

| Knob | Official meaning |
|------|------------------|
| `skills.external_dirs` | Extra skill roots scanned in place — **not a write-protection boundary** |
| `skills.write_approval` | Stage writes to `~/.hermes/pending/skills/`; review via `/skills approve\|reject` |
| Bundles | YAML manifest + `instruction:` + `skills:`; `.bundled_manifest` origin hashes |
| Taps | Remote / workshop skill sources |
| Per-task attach | `kanban_create(skills=[...])` / `--skill` — prefer over editing assignee profile |

## Bundle caution (official vs our doctrine)

Official: **"missing skills are skipped, not fatal."**

Our doctrine (CS-7): that skip is **FORBIDDEN** on dispatch — fail-closed
exists-assert every bundle-listed skill resolves on the seat before
`kanban dispatch`.

## Headless Kanban note

`skills.write_approval: true` with no interactive approver → timeout-deny
(R-AD011.5). Demo Managed Scope uses `write_approval: false` and protects
golden skills via FS / policy elsewhere.
