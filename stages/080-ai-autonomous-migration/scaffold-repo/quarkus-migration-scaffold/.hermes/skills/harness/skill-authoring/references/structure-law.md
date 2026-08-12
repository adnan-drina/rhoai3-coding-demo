# Structure law (R-SK.1 + R-SK.7)

**Official:** https://hermes-agent.nousresearch.com/docs/user-guide/features/skills
§Skill Directory Structure

Canonical tree: `SKILL.md` plus only `references/`, `templates/`, `scripts/`,
`examples/`, `assets/`. Unreferenced repository files are not copied on
install (R-SK.6).

## R-SK.7 categories (Architect amend E-20260812T104205Z)

| Directory | Owns |
|-----------|------|
| `analysis/` | M1 / derive / inventory |
| `sdd/` | M2 Spec Kit readiness |
| `gates/` | Domain + release gates |
| `harness/` | Orchestration, conduct, config, authoring |
| `spring-to-quarkus/` | Pair/product pattern surface (replaces abstract `patterns/`) |

Leaf skill names stay stable for `skills=[...]` / `--skill` attach. Directory
moves only at **v13 mint** boundary — mid-chain path anchors in card bodies
must not break.
