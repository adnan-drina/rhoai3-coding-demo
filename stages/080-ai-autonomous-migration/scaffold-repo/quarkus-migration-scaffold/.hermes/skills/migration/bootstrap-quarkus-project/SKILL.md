---
name: bootstrap-quarkus-project
description: Before the first destination app sources exist — author a Red Hat Quarkus pom.xml from the T-1 structure reference and tooling-pins, lint with check-pom-platform-pins, then add evidence-driven extensions via manage-quarkus-extensions; use when provisioning /projects/modernized app code (create-app path retired)
license: Apache-2.0
compatibility: Linux seat; Red Hat Quarkus platform; quarkus CLI optional (extensions only)
metadata:
  author: rhoai3-harness-team
  version: "2.0.0"
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
tree (`.hermes/`, `governance/`, `AGENTS.md`, `SOUL.md`). Platform GAV values
live only in `governance/contracts/tooling-pins.md`.

**DD1 (Operator E-20260814T065925Z):** `quarkus create app` /
`quarkus-maven-plugin:create` into the destination is **retired**. Foundation
stories author `pom.xml` from the T-1 reference. Official RHBQ documents
hand-authoring as a dedicated path (Research E-20260814T074356Z).

## When to Use

- The golden scaffold has no hand-maintained destination `pom.xml` /
  `src/` (see root `BOOTSTRAP.md`) and M3 needs a real Quarkus app tree.
- Fresh seat / factory provision after harness-only tip checkout.
- **Not** for mid-story extension add/rm — use `manage-quarkus-extensions`.
- **Not** for Spring→Quarkus form mapping (`spring-to-quarkus-patterns`).
- **Not** to invoke `scripts/bootstrap.sh` for create — that script refuses
  (retired create path).

## Procedure

1. Read `governance/contracts/tooling-pins.md` (Red Hat Quarkus platform row)
   and `../manage-quarkus-extensions/references/rh-bom-and-mandatory-deps.md`.
2. **Author** `pom.xml` at the destination root using the T-1 structure
   (ledger: `harness-refactoring/monitoring/20260814-t1-canonical-rh-quarkus-pom-grounding.md`):
   - properties: `quarkus.platform.group-id` /
     `quarkus.platform.artifact-id` / `quarkus.platform.version` from pins
   - `dependencyManagement` imports `quarkus-bom` from that stream
   - `<build>` declares `com.redhat.quarkus.platform:quarkus-maven-plugin`
     with the three-goal execution (`build` / `generate-code` /
     `generate-code-tests`)
   - **dependency block empty at mint** — extensions are story-owned (DD3)
   - Java release **21**; Jacoco/`argLine` + surefire pins when the foundation
     story's write-set includes the POM (A-3 / H3)
3. Run
   `../manage-quarkus-extensions/scripts/check-pom-platform-pins.py <root>`.
4. **Extensions (evidence-driven, DD3):** invoke `manage-quarkus-extensions`
   (`quarkus ext ls/search/add` when CLI present — W1; else Maven). The
   **needing story owns** the extension and its config/artifacts — do not
   paste a fixed menu on foundation for later stories.
5. Refuse `quarkus-spring-*` compatibility extensions (native Quarkus only).

## Verification

- Destination `pom.xml` exists and
  `check-pom-platform-pins.py <root>` prints
  `OK: pom platform pins match tooling-pins.md`.
- `quarkus.platform.group-id` is `com.redhat.quarkus.platform`.
- Harness tree still present: `.hermes/enforcement/validate-contracts/`,
  `governance/contracts/`, `AGENTS.md`.
- `scripts/bootstrap.sh` exits non-zero with `CREATE_PATH_RETIRED` if invoked
  for create (DD1 fail-closed).
