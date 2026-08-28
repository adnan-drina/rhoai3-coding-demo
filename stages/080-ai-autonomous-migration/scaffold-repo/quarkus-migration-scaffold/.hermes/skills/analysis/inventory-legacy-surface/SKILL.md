---
name: inventory-legacy-surface
description: Use when M1 must inventory legacy@3.x entry points and the types reachable from those files. Writes evidence/entry-point-inventory.json then evidence/type-inventory.json from harvest_referent in evidence/derived/legacy-at-3.json (do not hardcode /projects/legacy). Use before scan-with-mta (mta-analyze-legacy.sh emits the M1→M2 handoff internally and AR-4.1-refuses without the inventory), when partition coverage must cover dest twins as well as HTTP rows, when a collaborator layer is missing from the plan, or when smoke sampling needs the inventory — even if the user does not name type inventory. Do not use as a substitute for scan-with-mta.
license: Apache-2.0
compatibility: Linux seat; Python 3.11+; reads the legacy@3.x tree
metadata:
  author: rhoai3-harness-team
    version: "1.4.3"
  hermes:
    tags:
    - analysis
    - m1
    category: analysis
    kind: guidance
---
# Legacy surface inventory (HTTP entry points + type graph)

## When to Use

- M1 ANALYZE, **before** `scan-with-mta`: `mta-analyze-legacy.sh` calls
  `emit-findings-handoff.py` internally, which refuses (exit 2, AR-4.1)
  unless `evidence/entry-point-inventory.json` already exists. Inventory
  after the handoff invalidates its digest. Do not split emit into a
  separate paved-road step.
- Before M2 plan / Kanban populate: the inventory is a declared M1 output
  and an accept-scope path
  (`check-release-readiness/scripts/check-accept-scope.py`). Do not pin
  this leaf on the card. Pin `--skill paved-road-m1`; this inventory
  loads via `skill_view` from `steps.json`.
- Before writing `migration/story-endpoint-partition.json`: the partition's
  endpoint union must equal this inventory exactly (conservation gate in
  `check-findings-handoff.py`).
- After slices land, or after any re-derivation of the referent — re-scan to
  detect entry-point drift, then re-emit the handoff (the digest changes).
- Not a substitute for `scan-with-mta`: this is a regex scan of `*.java` that
  answers "what can call into this app", not a rules engine. Rule violations
  come from the analyzer, never from here.

## Procedure

1. Resolve the referent — `harvest_referent` in
   `evidence/derived/legacy-at-3.json` names the Boot-3 harvest. Pass
   `--from-manifest` so inventory and MTA share that path. Do **not**
   hardcode `/projects/legacy` when the mode is derived. Do **not** pass
   `/projects/.derived/legacy-at-3` as a literal (K2 fence; Architect
   `082958ZA`). Never scan a read-only 2.x mount as if it were the harvest.
   `mode=identity` harvest is `/projects/legacy` (in `K2_ALLOW_ROOT`); that
   does **not** close W4 (Boot-2 petclinic only).
2. Scan `harvest_referent`. `-o` defaults to
   `evidence/entry-point-inventory.json` (relative to cwd).

```bash
python3 "${HERMES_SKILL_DIR}/scripts/inventory-entry-points.py" \
  --from-manifest evidence/derived/legacy-at-3.json \
  -o evidence/entry-point-inventory.json
```

3. Read the printed counts and confirm the run was not vacuous (below).
4. Walk types reachable from each inventory row `file` (no Kanban body):

```bash
python3 "${HERMES_SKILL_DIR}/scripts/inventory-type-graph.py" \
  --dest-root /projects/modernized \
  --inventory evidence/entry-point-inventory.json \
  --from-manifest evidence/derived/legacy-at-3.json \
  -o evidence/type-inventory.json
```

5. Fail closed if the inventory `root` is not `harvest_referent`:

```bash
python3 "${HERMES_SKILL_DIR}/scripts/assert-harvest-referent-pair.py" \
  /projects/modernized
```

The walk parser is `scripts/type_graph.py` in this skill (not `.hermes/lib/`).
Layer is the last package segment of the dest path, not a name pattern.
Each row may set `generated: true` (path under `target/generated-sources`,
`@Generated`, or a declared generator plugin — no Dto/name pattern). M2
Creates source `dest_file`s; generated types carry the spec and configure
the dest generator — do not Create their `.java`.

Kinds: `http` (subtype `spring-mvc-or-jaxrs`) and `non-http`
(`lifecycle`, `scheduled`, `messaging`, `cli`, `event`). Type-level
`@RequestMapping`/`@Path` prefixes and bare `@RestController`/`@Controller`
are deliberately **not** counted — only independently callable handlers are.
Those prefixes **are** joined onto method mappings as structured
`http_method` and `http_path` (Architect `E-20260816T193813Z`). Mint A-8
coverage joins on dest-file equality (same-stack shortcut), inventory
`symbol` named in the story body, or transcribed `http_path`+`http_method`
— never a RestController→Resource filename map, and never by guessing a
route from a Java filename. `target/`, `build/`, `node_modules/`,
`fixtures/`, `.git/`, `.derived/` are skipped relative to the scan root
only, so a referent living under `/projects/.derived/…` still scans.

## Pitfalls

- Inventorying the RO legacy mount without the Boot-3 derived harvest
  referent when Boot source is still 2.x (`assert-harvest-referent-pair`
  REFUSE).
- Closing W4 on `mode=identity` (gs-rest) — `--require-boot2-derivation`
  is INCONCLUSIVE until a Boot-2 petclinic run.
- Treating HTTP-only inventory as complete when non-HTTP entry points exist.
- Treating HTTP inventory as complete for collaborator layers — those
  dest twins live in `evidence/type-inventory.json`, not on a route.
- Planning a Create for a `generated: true` dest twin — those are build
  output; the story owns the spec and the generator config.
- Writing inventory into `/projects/legacy` (read-only provenance).

## Verification

- `evidence/entry-point-inventory.json` exists with
  `schema: rhoai3.entry-point-inventory/v1` and a fresh `scanned_at`.
- `evidence/type-inventory.json` exists with
  `schema: rhoai3.type-inventory/v1` after the type-graph walk.
- `execution_evidence.ran == true` and `execution_evidence.vacuous == false`.
  `vacuous: "zero_java_files"` means the root was wrong or empty — the result
  is INCONCLUSIVE, not "no entry points"; fix the root before handing off.
- `execution_evidence.java_files_seen > 0` and `inputs_digest_sha256` non-empty;
  `counts.total` equals `len(entry_points)` and `counts.by_subtype` sums to it.
- HTTP rows carry `http_method` (GET/POST/…) and `http_path` (class prefix
  joined to the method mapping). Empty fields mean the scanner could not
  parse a route; coverage then joins on dest-file shortcut or `symbol`.
- `assert-harvest-referent-pair.py <dest>` exits 0: inventory `root` equals
  `harvest_referent`. `--require-boot2-derivation` exits 2 on `mode=identity`
  (W4 stays open; not gs-rest).
- Script prints `OK: <n> entry points (<h> http, <n> non-http) → <path>` and
  exits 0. Exit 2 = scan root is not a directory (nothing was written).
- Digest coupling: `check-findings-handoff.py` re-hashes this file and compares
  it to `handoff.inventory.sha256` plus `endpoint_count`. Re-running the scanner
  after `evidence/findings-handoff.json` was emitted invalidates the handoff —
  re-emit it (skill `scan-with-mta`).
