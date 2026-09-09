---
name: freeze-migration-input
description: >
  Use as the first M1 ANALYZE step to freeze the original legacy source
  (/projects/legacy) into a content-addressed manifest and, when a tool
  needs a writable input, a byte-identical analysis copy whose digest is
  verified. Every later producer records this source digest. Do not use
  on a derived or upgraded tree; do not modify /projects/legacy.
license: Apache-2.0
compatibility: Linux seat; Python 3.11+; reads the read-only legacy mount
metadata:
  author: rhoai3-harness-team
  version: "1.0.0"
  hermes:
    tags:
    - analysis
    - m1
    category: analysis
    kind: guidance
    paths:
      reads: ["/projects/legacy"]
      writes: ["/projects/modernized/evidence/frozen", "/projects/modernized/evidence/producers", "/projects/modernized/.derived/frozen-input"]
---
# Freeze the migration input (M1 producer)

The authoritative source root is the **original frozen legacy
application**, not a model-produced or mechanically upgraded tree
(SAD §5.1). This skill owns `evidence/frozen/source-manifest.json` and
`evidence/producers/freeze.json`.

## When to Use

- First step of `paved-road-m1` (`steps.json`), before build, the JDK-model inventory, probe,
  and MTA. Load via `skill_view`; do not pin this leaf on the card.
- When `evidence/frozen/source-manifest.json` is missing or its `digest`
  no longer matches the mount (the legacy checkout changed).
- **Not** for Boot 2→3 derivation (`derive-legacy-boot3` is an
  execution-side transformation, never the baseline).

## Procedure

```bash
python3 "${HERMES_SKILL_DIR}/scripts/freeze-migration-input.py" \
  --source /projects/legacy \
  --root /projects/modernized \
  --copy-to /projects/modernized/.derived/frozen-input
```

1. Walks `--source` (skipping `.git`, `target/`, `build/`, `node_modules/`,
   `.idea/`, `.vscode/`), hashes every file, sorts by path, and writes the
   manifest. The manifest `digest` is the SHA-256 of the canonical
   `{files:[{path,sha256}]}` list — hostnames and timestamps are excluded.
2. With `--copy-to`, makes a byte-identical copy for tools that need a
   writable input (MTA's JDT/m2e writes `.project`), re-hashes the copy,
   and refuses if any byte differs. The copy is created **before** any
   transformation; nothing may edit it before baseline analysis.
3. Writes the producer receipt with `status: ok`, the source digest, the
   copy path, and output digests.

## Verification

- `evidence/frozen/source-manifest.json` has `schema
  rhoai3.source-manifest/v1`, non-empty `files`, and a 64-hex `digest`.
- `evidence/producers/freeze.json` passes
  `.hermes/planning/schemas/producer-receipt.schema.json` and names
  `analysis_copy` when `--copy-to` was given.
- Re-running on an unchanged mount yields byte-identical files.
- Exit 1 with `FREEZE_COPY_MISMATCH` means the copy differs from the
  source — do not proceed; the copy is not evidence.

## Scripts

- `scripts/freeze-migration-input.py` — the producer
- `scripts/freeze-migration-input.test.py` — land-time selftest
