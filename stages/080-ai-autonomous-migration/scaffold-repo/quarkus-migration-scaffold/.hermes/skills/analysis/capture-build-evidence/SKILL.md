---
name: capture-build-evidence
description: >
  Use at M1 ANALYZE after freeze-migration-input to record the legacy
  build facts: dependency warm-up (online) separately from an offline
  compile, the resolved classpath, source and generated-source roots,
  toolchain pins, and the compile outcome. A failed build still yields
  planning-only evidence; it never yields execution admission. Do not use
  to repair the legacy build.
license: Apache-2.0
compatibility: Linux seat; Maven 3.9+; Java 21; Python 3.11+
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
      reads: ["/projects/modernized/.derived/frozen-input", "/home/user/.m2"]
      writes: ["/projects/modernized/evidence/build", "/projects/modernized/evidence/producers"]
---
# Capture build evidence (M1 producer)

Owns `evidence/producers/build.json`. Runs Maven against the **frozen
analysis copy** recorded by `freeze-migration-input` — never against
`/projects/legacy` (read-only) and never against a derived Boot 3 tree.

## When to Use

- Second step of `paved-road-m1`, after the freeze and before the JDK-model
  extractor (which uses the classpath when one exists).
- **Not** to make a red build green. A failed offline compile is a fact
  the receipt records (`outcome: failure`); the ledger turns it into
  `BUILD_FAILED` (planning-only). Repairing the build is a separate
  restricted bootstrap run followed by a refreeze (SAD §7).

## Procedure

```bash
bash "${HERMES_SKILL_DIR}/scripts/capture-build-evidence.sh" --root /projects/modernized
```

The wrapper, in order:

1. Reads `evidence/producers/freeze.json` for `analysis_copy` and
   `source_digest`; refuses without them.
2. **Warm-up** (network allowed): `mvn -q -B dependency:go-offline`.
   Recorded separately as `warmup.outcome`; it is not the build.
3. **Offline build**: `mvn -q -B -o compile`. Exit code and the last
   lines of output go to `evidence/build/compile.log`.
4. **Classpath**: `mvn -q -B -o dependency:build-classpath
   -Dmdep.outputFile=evidence/build/classpath.txt`.
5. **Roots and pins**: `java -version`, `mvn -v`, the pom's
   `maven.compiler.release`/`source`, `<sourceDirectory>`, and any
   `target/generated-sources/*` directories after compile.
6. `emit-build-receipt.py` turns those raw files into the receipt.

## Verification

- `evidence/producers/build.json` has `outcome` in
  `success|failure`, `classpath_available` true only when
  `evidence/build/classpath.txt` is non-empty, `warmup.outcome`
  recorded separately, and `toolchain.java` / `toolchain.maven` set.
- A `failure` outcome exits 0 from the wrapper (the fact was recorded)
  but exits 1 from the paved-road audit's admission later — do not
  "fix" it here.

## Scripts

- `scripts/capture-build-evidence.sh` — Maven wrapper (records, never repairs)
- `scripts/emit-build-receipt.py` — raw outputs → receipt
- `scripts/emit-build-receipt.test.py` — selftest with fixture outputs
