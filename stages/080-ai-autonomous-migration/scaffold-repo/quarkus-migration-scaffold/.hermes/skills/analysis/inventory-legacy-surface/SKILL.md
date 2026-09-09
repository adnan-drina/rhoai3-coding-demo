---
name: inventory-legacy-surface
description: >
  Use at M1 ANALYZE after capture-build-evidence to extract the admitted
  structural truth of the frozen legacy source with the JDK's own compiler
  API (javax.lang.model + com.sun.source through JavacTask): types,
  annotations, supertypes, fields, injection sites, methods, calls, and
  type references, each with full or partial resolution. No third-party
  library; the pinned toolchain JDK is the extractor. Writes
  evidence/structure/structure.json plus the v1-compatible entry-point and
  type inventories. Works without a classpath when the build is damaged.
  Refuses when pins.structure_extractor is missing or the running JDK is
  not the pinned release. Never a regex scan; not a substitute for
  scan-with-mta.
license: Apache-2.0
compatibility: Linux seat; JDK 21 (javac required); Python 3.11+
metadata:
  author: rhoai3-harness-team
  version: "3.0.0"
  hermes:
    tags:
    - analysis
    - m1
    category: analysis
    kind: guidance
    paths:
      reads: ["/projects/modernized/.derived/frozen-input", "/projects/modernized/evidence/build"]
      writes: ["/projects/modernized/evidence/structure", "/projects/modernized/evidence/producers", "/projects/modernized/evidence/entry-point-inventory.json", "/projects/modernized/evidence/type-inventory.json"]
---
# Legacy surface inventory (JDK model, M1 producer)

Owns `evidence/structure/structure.json` (`rhoai3.structure/v1`) and
`evidence/producers/jdk-model.json`, and derives the v1-compatible
`evidence/entry-point-inventory.json` / `evidence/type-inventory.json`
from that structure and the entry-point catalog. Every structural claim
carries provenance (`jdk-model`, the exact runtime string) and resolution
(`full` / `partial`).

## Why the JDK compiler API

The extractor is `scripts/jdk-model/JdkModelExtract.java`, compiled at run
time by the toolchain `javac` and driven through `JavacTask`. It adds no
dependency to the stack: the pinned JDK (`pins.structure_extractor`,
`jdk-21`) is the tool, so there is no third-party version or license to
decide. Without a classpath javac still attributes the tree and marks
every unresolved reference as an error type; the extractor records the
name as written and the claim as `partial`. It decides nothing.

## When to Use

- Third step of `paved-road-m1`, after `capture-build-evidence` and before
  `scan-with-mta` (the MTA handoff refuses without the inventory).
- After any refreeze (the manifest digest changed).
- Never as a regex scan. There is no regex path in this skill.

## Procedure

```bash
bash "${HERMES_SKILL_DIR}/scripts/run-jdk-model-extract.sh" --root /projects/modernized
python3 "${HERMES_SKILL_DIR}/scripts/assert-frozen-root-pair.py" /projects/modernized
```

1. Reads `pins.structure_extractor` from `.hermes/pins.json`. **Missing
   pin, or a running JDK whose feature release differs from it → producer
   receipt `status: unpinned`, exit 1.** The pin is the toolchain JDK; a
   worker never changes it.
2. Compiles `JdkModelExtract.java` with the toolchain `javac` and runs it
   over the frozen analysis copy. With a classpath from
   `capture-build-evidence` the mode is `full`; without one the mode is
   `partial` and claims touching unresolved references are marked partial.
3. `normalize-structure.py` resolves names left as written through the
   compilation-unit imports (explicit import → unique catalog-known
   wildcard → single wildcard), sorts, stamps the frozen source digest,
   validates against `.hermes/planning/schemas/structure.schema.json`,
   and writes the three evidence files plus the receipt (extractor source
   sha256 in `tool.artifact_sha256`, runtime string in `tool.runtime`).
4. `assert-frozen-root-pair.py` refuses if the inventory root or digest
   is not the frozen analysis copy.

## Verification

- `evidence/producers/jdk-model.json` `status: ok`, `mode` recorded,
  `tool.version` equals `pins.structure_extractor.version`.
- `evidence/structure/structure.json` `source_digest` equals the freeze
  receipt `source_digest`; `types` non-empty; every type has `resolution`.
- `evidence/entry-point-inventory.json` `execution_evidence.provenance`
  starts with `jdk-model:`; `counts.total` equals `len(entry_points)`.
- Zero entry points is **not** a clean result: the planner records
  `ZERO_ENTRY_POINTS` and admission stays INCONCLUSIVE.
- `scripts/inventory-legacy-surface.test.py` compiles and runs the real
  extractor on a Spring fixture without a classpath and proves the
  catalog-derived entry points (HTTP and scheduled), partial-mode
  evidence, the unpinned refusal, and the JDK-mismatch refusal.

## Scripts

- `scripts/run-jdk-model-extract.sh` — launcher (fail-closed on pin / JDK mismatch)
- `scripts/jdk-model/JdkModelExtract.java` — extractor source (JDK compiler API only)
- `scripts/normalize-structure.py` — raw → canonical structure + compat inventories + receipt
- `scripts/assert-frozen-root-pair.py` — inventory root equals frozen copy
- `scripts/inventory-legacy-surface.test.py` — selftest

## Pitfalls

- Pointing the extractor at `/projects/legacy` or a derived Boot 3 tree.
  Input is the freeze receipt's `analysis_copy`, byte-identical to the
  frozen mount.
- Treating a `partial` mode as an error. It is recorded evidence; the
  ledger decides what it blocks.
- Editing `entry-point-inventory.json` by hand. It is a derived view.
