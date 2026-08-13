---
name: bootstrap-quarkus-project
description: Before the first destination app sources exist — create a Red Hat Quarkus project via CLI (RH registry-first) or Maven :create, add evidence-driven extensions, then apply the linted harness pom patch; use when retiring the hand-maintained skeleton or provisioning /projects/modernized app code
license: Apache-2.0
compatibility: Linux seat; Red Hat Quarkus platform; quarkus CLI optional (Maven fallback)
metadata:
  author: rhoai3-harness-team
  version: "1.0.0"
  hermes:
    tags:
    - migration
    - quarkus
    - bootstrap
    category: migration
    kind: guidance
---
# Bootstrap Quarkus project (destination)

Guidance only (R-SK.14). Creates the **destination application** under the
scaffold root (or `/projects/modernized`). Does **not** replace the harness
tree (`.hermes/`, `governance/contracts/`, `AGENTS.md`, `SOUL.md`). Platform
GAV values live only in `governance/contracts/tooling-pins.md`.

Plan basis: `harness-refactoring/monitoring/20260813-v14-quarkus-bootstrap-plan.md`
(CLI ADOPTABLE with RH registry-first + GA Maven; Maven `:create` first-class
fallback).

## When to Use

- The golden scaffold has no hand-maintained destination `pom.xml` /
  `src/` (see root `BOOTSTRAP.md`) and M3 needs a real Quarkus app tree.
- Fresh seat / factory provision after harness-only tip checkout.
- **Not** for mid-story extension add/rm — use `manage-quarkus-extensions`.
- **Not** for Spring→Quarkus form mapping (`spring-to-quarkus-patterns`).

## Procedure

1. Read `governance/contracts/tooling-pins.md` (Red Hat Quarkus platform row)
   and `../manage-quarkus-extensions/references/rh-bom-and-mandatory-deps.md`.
2. **Prereqs (CLI path):** `~/.quarkus/config.yaml` lists
   `registry.quarkus.redhat.com` **first**; Maven reaches
   `maven.repository.redhat.com/ga/`. If either fails → Maven fallback.
3. **Create** into a staging dir, then sync into the scaffold root (never
   overwrite `.hermes/`, `migration/`, `AGENTS.md`, `SOUL.md`, `BOOTSTRAP.md`):
   - Prefer: `scripts/bootstrap.sh` (wraps `quarkus create app` with
     `-P <groupId>:<artifactId>:<version>` from tooling-pins).
   - Fallback: same script with `BOOTSTRAP_MODE=maven` →
     `mvn io.quarkus.platform:quarkus-maven-plugin:…:create` using the
     **Red Hat** plugin GAV stream from the pins (not community-only).
4. **Extensions (evidence-driven):** invoke `manage-quarkus-extensions`
   (`quarkus ext ls/search/add` or Maven fallback). Do not paste a fixed
   extension menu; derive from inventory / story evidence.
5. **Harness pom patch (lint-verified):** apply the declared post-generate
   patch (Java 21 release, Jacoco/`argLine`, dual Sonar jacoco paths,
   surefire pin) then run
   `../manage-quarkus-extensions/scripts/check-pom-platform-pins.py <root>`.
6. Refuse `quarkus-spring-*` compatibility extensions (native Quarkus only).

## Verification

- Destination `pom.xml` exists and
  `check-pom-platform-pins.py <root>` prints
  `OK: pom platform pins match tooling-pins.md`.
- `quarkus.platform.group-id` is `com.redhat.quarkus.platform` (no community
  rewrite).
- Harness tree still present: `.hermes/enforcement/validate-contracts/`,
  `governance/contracts/`, `AGENTS.md`.
- Silent failure catch: missing pins → pins script exit 1; CLI without RH
  registry-first → refuse CLI path and use Maven fallback (or typed block).
