# Partition schema (M2 producer reference)

**Authoritative refuse codes and remedies live in**
`.hermes/kernel/k4_schema.py` (`REMEDY`). This page names the fields a
worker must write. `scripts/assert-partition-schema-sync.py` fails if a
code or field below disappears from either side.

Do **not** copy remedy prose here. Do **not** read `k4_convert.py` to
learn the shape — use this page plus a failing convert run's `K4_*` code.

## File

Write `evidence/partition.json` (coverage also accepts
`evidence/briefs/partition.json`). One object.

## Top-level keys

| Key | Rule |
|-----|------|
| `type_inventory_sha256` | 64 lowercase hex of `evidence/type-inventory.json` |
| `stories` | non-empty array of story objects |

## Each `stories[]` object

| Key | Rule |
|-----|------|
| `story_id` | stable id (`setup`, `us1_greeting`, …). `id` is accepted as alias |
| `files_writable` | non-empty dest-relative paths; K4 copies this as the write-set |
| `parents` | list of other `story_id`s (import graph). `[]` on roots |
| `kind` | `setup` / `us` / `polish` / `database` when `skills[]` omitted |
| `skills` | pinned leaves from **Valid producers** below; else `kind` → that table |
| `endpoints` | HTTP stories: `["GET /greeting", …]` (METHOD + path). Coverage 1:1 |
| `legacy_source` | HTTP stories: inventory `file` from `entry-point-inventory.json` (legacy package/path). Copied onto the M3 body as `identity.legacy_source`. Dest `files_writable` is the dest package. |
| `dest_file` | HTTP stories: the **type-inventory dest twin of an inventoried legacy type** (path or list). It is **not** the new file this story creates. Naming a created file that is not that twin is invented dest_file and REFUSEs at convert (`K4_DEST_FILE`). |
| `title` | human title; not the write-set |
| `acceptance_criteria` | strings; paths named here must sit in `files_writable` |
| `supersedes` | optional named 1:N successor set for a dest_file |

## Valid producers

Authoritative names live in `.hermes/kernel/k4_producers.py`
(`PRODUCERS`, `KIND_DEFAULTS`). Mint refuses a card whose pinned skills
contain no producer for its **primary artifact** (`K4_NO_PRODUCER`).
Checkers (`check-*`, `assert-*`) are not producers. Do not guess names.

| Skill | Primary artifact |
|-------|------------------|
| `derive-legacy-boot3` | m1-analyze |
| `scan-with-mta` | m1-analyze |
| `inventory-legacy-surface` | m1-analyze |
| `plan-migration-partition` | m2-partition |
| `author-destination-pom` | dest-pom |
| `reference-rh-quarkus-pom` | dest-pom |
| `manage-quarkus-extensions` | dest-pom |
| `configure-quarkus-profiles` | dest-pom |
| `spring-to-quarkus-patterns` | dest-java |
| `form-entity-persistence` | dest-k8s |
| `commit-destination-tree` | dest-commit |
| `compose-m4-verdict` | m4-verdict |

`kind` → default `skills[]` when omitted (`KIND_DEFAULTS`):

| kind | default skills |
|------|----------------|
| `setup` | `author-destination-pom`, `reference-rh-quarkus-pom`, `manage-quarkus-extensions`, `configure-quarkus-profiles` |
| `us` | `spring-to-quarkus-patterns` |
| `polish` | `spring-to-quarkus-patterns`, `manage-quarkus-extensions` |
| `database` | `form-entity-persistence` |

Pin `skills[]` when the default would not own the story's primary artifact
(example: polish that only amends `pom.xml` still has `manage-quarkus-extensions`;
polish that authors Java needs `spring-to-quarkus-patterns`).

## Codes this authoring must not trip

`K4_SCHEMA` `K4_SCOPE` `K4_SKILLS` `K4_PARENT` `K4_T0_3_SERVICE`
`K4_PATH_TOKEN` `K4_PLANNING_DEFECT` `K4_LEGACY_SOURCE` `K4_DEST_FILE`

`K4_T0_3_SERVICE`: the same `*Service.java` must not be writable on two
stories. One story MAY own a shared facade. Split-one-class-per-aggregate
is architecture (petclinic ADR), not this mint refuse.

`K4_PATH_TOKEN`: `tasks.md` must not ask to scrape write-sets.
`K4_PLANNING_DEFECT`: a path named in `tasks.md` must already be in some
story `files_writable`. Do not grow the write-set from prose.

## After authoring

```bash
python3 .hermes/kernel/k4_convert.py \
  --partition evidence/partition.json \
  --tasks specs/*/tasks.md \
  --out evidence/partition-payloads.json
```

Cards come from that convert, minted by `k4_mint.py`. Speckit remains the
plan (`tasks.md`), not the card factory.
