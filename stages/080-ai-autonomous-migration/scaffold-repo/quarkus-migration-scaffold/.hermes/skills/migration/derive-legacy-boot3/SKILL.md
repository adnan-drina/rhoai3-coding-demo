---
name: derive-legacy-boot3
description: Before M1 on a Boot 2.x legacy mount — freezes a derived legacy@3.x tree and stamps the harvest_referent manifest
license: Apache-2.0
compatibility: Linux seat; Java 21 and Maven; writable derived tree
metadata:
  author: rhoai3-harness-team
  version: "1.2.1"
  hermes:
    tags:
    - migration
    - quarkus
    category: migration
    kind: guidance
---
# Boot 2→3 derivation (before M1)

## When to Use

- Before M1 ANALYZE, when `evidence/derived/legacy-at-3.json` is missing or
  `check-manifest.sh` fails (empty required field, schema ≠ `legacy-at-3/v2`,
  `harvest_referent` not a directory).
- After a wipe of `/projects/.derived/legacy-at-3` — the manifest then names a
  tree that no longer exists; re-derive, never repoint at the 2.x mount.
- When the legacy mount is swapped for a different specimen or revision: the
  recorded `sha256` no longer describes what M1 would harvest against.

Do **not** load this on ordinary coding turns — it is a one-time precondition.
Harvest and MTA **read** the manifest; they never re-derive.

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
  `/projects/.derived/legacy-at-3`; write `evidence/derived/legacy-at-3.json`.
- Manifest schema `legacy-at-3/v2` records **JDK and Spring Boot versions
  before and after** (W2 §3.1) beside `sha256` / `harvest_referent`, so a later
  failure can attribute the bundled upgrades without splitting the frozen stage.
- **Upgrade command (default wired):** `derive-legacy-boot3.sh` runs the
  **free-primitives-boot3** composite (`scripts/free-primitives-boot3/`) when
  `DERIVE_UPGRADE_CMD` is unset. Operator declined Moderne-licensed recipes
  (`E-20260807T184100Z`); there is no fall-through to `UpgradeSpringBoot_3_0`.
  Override with `DERIVE_UPGRADE_CMD` only for explicit experiments. Admit table
  + cites: `scripts/free-primitives-boot3/RULES.md`. Apply log:
  `evidence/derived/free-primitives-apply-log.json` (W2 §12.3).

## Pitfalls

- Never edit `/projects/legacy` or a frozen derived tree to "fix" Boot-3.
- Never tell harvest or MTA to use the 2.x mount when the manifest points at a
  derived referent.
- Do not invoke Moderne `rewrite-spring` / `UpgradeSpringBoot_3_0` as the
  default — operator-declined even where the Agreement reading is permissive.
- Do not leave this procedure in `AGENTS.md` — it is phase-scoped; conventions
  stay always-on.
- Do not treat "not the golden tip" as "therefore a derived tree". Apply-log
  defaults write beside `COMPOSITE_ROOT` only when `APPLY_LOG_PATH` is set or
  the tree is positively derived (`.rhoai3-derived-tree` or a `.derived` path
  segment). A tree with no `pom.xml` and no `*.java` is `no_candidate_sources`
  (typed exit 2, no receipt) — not a completed derivation.


## Verification

- `derive-legacy-boot3.sh` exits 0 with human `OK: …` on stderr and one JSON
  object on stdout (`script`,`ok`,`mode`,`harvest_referent`,… — UPLIFT-2).
  Progress and DRY-RUN lines are on stderr only.
- `check-manifest.sh` exits 0 printing `OK: legacy-at-3 mode=<identity|derived>
  harvest_referent=<path> jdk A→B boot X→Y`. It fails closed when any of the
  eight required fields is empty, the schema is not `legacy-at-3/v2`, or
  `harvest_referent` is not a directory.
- `run-composite.sh` (free-primitives) emits `free-primitives-boot3: OK` on
  stderr and `{script:run-composite,ok,composite_root,rule_count,…}` on stdout.
- `mode=derived`: `/projects/.derived/legacy-at-3` exists, its `pom.xml`
  resolves to Boot ≥ 3, and the tree is write-protected (`chmod a-w`, dirs keep
  `+x`). A writable derived tree means the freeze never ran or something edited
  it afterwards — re-derive; do not `chmod` it back.
- **Silent-failure catch:** `harvest_referent=/projects/legacy` while
  `spring_boot_version_source` is < 3. That combination means harvest is being
  compared to the 2.x mount, which reads every Boot-3 API change as infidelity.
- Default composite path leaves `evidence/derived/free-primitives-apply-log.json`
  (`schema free-primitives-apply-log/v1`) with one entry per rule — `rule_id`,
  `cite`, `pre_digest`/`post_digest`, `skipped`. Missing log with `mode=derived`
  and `DERIVE_UPGRADE_CMD` unset ⇒ the upgrade did not run. A tree with no
  `pom.xml` and no `*.java` is `no_candidate_sources` (exit 2, no receipt).
- Apply-log default is beside `COMPOSITE_ROOT` only when `APPLY_LOG_PATH` is set
  or the tree is positively derived (`.rhoai3-derived-tree` or a `.derived`
  path segment). Any other cwd writes `$TMPDIR` (FP-1).
- `/projects/legacy` is byte-identical afterwards — the derivation copies out
  (rsync, or tar when rsync is absent) and never writes to the RO mount.
