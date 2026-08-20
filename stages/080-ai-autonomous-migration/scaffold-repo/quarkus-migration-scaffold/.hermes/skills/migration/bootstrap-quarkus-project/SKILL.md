---
name: bootstrap-quarkus-project
description: Before the first destination app sources exist — author a Red Hat Quarkus pom.xml from skill reference-rh-quarkus-pom and tooling-pins, lint with check-pom-platform-pins, then add evidence-driven extensions via manage-quarkus-extensions; use when provisioning /projects/modernized app code (create-app path retired)
license: Apache-2.0
compatibility: Linux seat; Red Hat Quarkus platform; quarkus CLI optional (extensions only)
metadata:
  author: rhoai3-harness-team
  version: "2.1.0"
  hermes:
    tags:
    - migration
    - quarkus
    - bootstrap
    category: migration
    kind: guidance
---
# Bootstrap Quarkus project (destination) — author the POM

Guidance only (R-SK.14). Authors the **destination application POM** under the
scaffold root (or `/projects/modernized`). Does **not** replace the harness
tree (`.hermes/`, `AGENTS.md`, `.hermes/SOUL.md`, `devfile.yaml` — write-fenced).
Platform GAV values live only in `.hermes/pins.json`.

**DD1 (Operator E-20260814T065925Z):** `quarkus create app` /
`quarkus-maven-plugin:create` into the destination is **retired**. Foundation
stories author `pom.xml` from skill `reference-rh-quarkus-pom`. Official RHBQ
documents hand-authoring as a dedicated path.

## When to Use

- The golden scaffold has no hand-maintained destination `pom.xml` /
  `src/` and M3 needs a real Quarkus app tree.
- Fresh seat / factory provision after harness-only tip checkout.
- **Not** for mid-story extension add/rm — use `manage-quarkus-extensions`.
- **Not** for Spring→Quarkus form mapping (`spring-to-quarkus-patterns`).
- **Not** to invoke `scripts/bootstrap.sh` for create — that script refuses
  (retired create path).

## Procedure

1. Read `.hermes/pins.json` (Red Hat Quarkus platform row)
   and `../manage-quarkus-extensions/references/rh-bom-and-mandatory-deps.md`.
2. Open skill `reference-rh-quarkus-pom` (`../reference-rh-quarkus-pom/`) —
   assemble structure from `references/pom-structure.md` +
   `references/maven-repos.md`.
3. **Author** `pom.xml` at the destination root:
   - properties / BOM import / plugin executions per that reference
   - `<build>` uses `com.redhat.quarkus.platform:quarkus-maven-plugin`
     — **never** `io.quarkus` / `io.quarkus.platform` plugin GAV (H-1)
   - Story extensions: the sole `pom.xml` writer applies
     `identity.extensions_apply` (sorted unique union of every story's
     `identity.extensions_declared`, including M1
     `evidence/required-extensions.json` on the pom writer, Architect
     E-20260814T205052Z DD3 / V35-EXTENSIONS).
     Later stories do **not** write `pom.xml`. **Exception:** carry
     foundation Jacoco/Sonar wiring from
     `references/foundation-jacoco-wiring.md` (A-3 / H-3 — build
     infrastructure, not story-owned) **and** the S-010 test toolchain
     (`io.rest-assured:rest-assured` + `org.assertj:assertj-core@version`,
     `../manage-quarkus-extensions/references/test-toolchain.md`). These
     are harness-owned Maven test deps, not Quarkus extensions.
   - Java release and surefire from pins
4. Run
   `../manage-quarkus-extensions/scripts/check-pom-platform-pins.py <root>`
   and
   `../manage-quarkus-extensions/scripts/check-pom-jacoco-wiring.py <root>`.
5. **Tooling preflight (W3):** run
   `../manage-quarkus-extensions/scripts/assert-extension-tooling.py`
   before the first `ext` / Maven extension mutation. CLI absent → typed
   `MAVEN_FALLBACK` (not improvisation).
6. **Extensions (evidence-driven, DD3 declare/apply/own):** invoke
   `manage-quarkus-extensions` (`quarkus ext ls/search/add` when CLI
   present — W1; else Maven). The **pom.xml writer** applies
   `identity.extensions_apply` (union). Other stories declare
   `identity.extensions_declared` only — they do not write `pom.xml`
   and must not paste a fixed menu. T-3 path heuristic stamps declared
   at mint; do not invent artifactIds/GAVs.
7. Refuse `quarkus-spring-*` compatibility extensions (native Quarkus only).

## Pitfalls

- Invoking `scripts/bootstrap.sh` for create — it refuses (`CREATE_PATH_RETIRED`).
- Leaving Jacoco dual Sonar paths / surefire `argLine` off the foundation POM
  (A-3 gate fails once `pom.xml` exists).
- Using community `io.quarkus.platform` plugin GAV instead of
  `com.redhat.quarkus.platform` from `.hermes/pins.json`.
- Citing out-of-scaffold ledger paths for structure — use
  `reference-rh-quarkus-pom` in-tree (R-SK.13).

## Verification

- Destination `pom.xml` exists and
  `check-pom-platform-pins.py <root>` prints
  `OK: pom platform pins match `.hermes/pins.json``.
- `check-pom-jacoco-wiring.py <root>` prints
  `OK: pom Jacoco/Sonar dual-path + argLine wiring present`.
- `quarkus.platform.group-id` is `com.redhat.quarkus.platform`.
- Harness tree still present: `.hermes/skills/harness/validate-contracts/`,
  `AGENTS.md`, `devfile.yaml`.
- `scripts/bootstrap.sh` exits non-zero with `CREATE_PATH_RETIRED` if invoked
  for create (DD1 fail-closed). Do **not** depend on `rsync` (W2 — seat has
  `tar`; create sync path is retired).
