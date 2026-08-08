---
name: derive-legacy-boot3
description: >
  Produce the frozen legacy@3.x derivation (Boot 2→3) and write
  migration/derived/legacy-at-3.json before M1 ANALYZE. Use once when the
  workspace starts or when the derivation manifest is missing. Harvest and MTA
  must compare against harvest_referent, never the 2.x mount alone.
---

# Boot 2→3 derivation (before M1)

## When to use

- Before M1 ANALYZE, when `migration/derived/legacy-at-3.json` is missing
- After a wipe of `/projects/.derived/legacy-at-3` that requires re-freeze

Do **not** load this on ordinary coding turns — it is a one-time precondition.

## Why this exists

The Quarkus migration analyzes and harvests against **legacy@3.x**, not the
read-only 2.x mount. Boot 2→3 is a **pure derivation**: never mutate
`/projects/legacy`.

**Harvest faithfulness compares the destination to `harvest_referent` from the
manifest (legacy@3.x). Comparing to 2.x alone is wrong — Boot-3 API changes
would look like infidelity.** That sentence is the whole point of the
derivation design; do not "simplify" harvest checks back to the RO mount.

## Procedure

```bash
bash "${HERMES_SKILL_DIR}/scripts/derive-legacy-boot3.sh"
bash "${HERMES_SKILL_DIR}/scripts/check-manifest.sh"
```

- If `spring-boot.version >= 3` already: `mode=identity` — `harvest_referent`
  is `/projects/legacy`.
- Otherwise: copy → Boot 2→3 upgrade → freeze under
  `/projects/.derived/legacy-at-3`; write `migration/derived/legacy-at-3.json`.
- Manifest schema `legacy-at-3/v2` records **JDK and Spring Boot versions
  before and after** (W2 §3.1) beside `sha256` / `harvest_referent`, so a later
  failure can attribute the bundled upgrades without splitting the frozen stage.
- **Upgrade command (default wired):** `derive-legacy-boot3.sh` runs the
  **free-primitives-boot3** composite (`scripts/free-primitives-boot3/`) when
  `DERIVE_UPGRADE_CMD` is unset. Operator declined Moderne-licensed recipes
  (`E-20260807T184100Z`); there is no fall-through to `UpgradeSpringBoot_3_0`.
  Override with `DERIVE_UPGRADE_CMD` only for explicit experiments. Admit table
  + cites: `scripts/free-primitives-boot3/RULES.md`. Apply log:
  `migration/derived/free-primitives-apply-log.json` (W2 §12.3).

## Pitfalls

- Never edit `/projects/legacy` or a frozen derived tree to "fix" Boot-3.
- Never tell harvest or MTA to use the 2.x mount when the manifest points at a
  derived referent.
- Do not invoke Moderne `rewrite-spring` / `UpgradeSpringBoot_3_0` as the
  default — operator-declined even where the Agreement reading is permissive.
- Do not leave this procedure in `AGENTS.md` — it is phase-scoped; conventions
  stay always-on.
