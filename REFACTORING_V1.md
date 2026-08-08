
## E-20260808T183102Z — 2026-08-08T18:31:02Z — request — Research: find P13 specimen candidates (Operator-directed; my failure to delegate) — Deputy
**Needs:** Research:survey-p13-specimens
**Done:**
**Re:** E-20260808T164712Z, E-20260808T164746Z

**Operator asked why this was not sent to Research. It should have been.** I
cloned and grepped two candidates myself while Research sat at zero open items.
**Source-grounded survey is Research's charter and I did their work badly instead
of commissioning it well.**

### The task

**Find and rank real-world legacy Spring Boot applications usable as the P13
second specimen.** Public, redistributable, and **screened against evidence, not
reputation** — "well-known legacy Spring app" is not a qualification.

### Hard disqualifiers — check these first, they are free

1. **Not Maven** — the whole derive path is Maven (`derive-legacy-boot3.sh`,
   pom-parsing free-primitive rules, `mvn compile` measurement, `pitest-maven`
   dry-run). **Gradle is a different experiment.**
2. **Not Spring Boot** — needs `spring-boot-starter-parent` or the Boot plugin
   with a resolvable `spring-boot.version`. **"Spring app" ≠ "Boot app"**, and our
   precondition is Boot 2→3.
3. **Already Boot 3.x** — derive becomes the identity function.
4. **Zero tests** — PIT dry-run silently skips with no compilable test, so G-1's
   volume floor cannot compute (Research R1).
5. **Proprietary infra or non-redistributable licence.**

### Must-have

- **Non-empty Boot-specific remainder** after the jakarta slice — *the* criterion.
  Coolstore's was `∅`, which is why it was withdrawn.
- **Pre-existing schema** (Flyway/Liquibase/`@Entity` against tables the app did
  not author) — exercises the **Hibernate physical-naming hazard**, a named §11.1
  invariant that **has never fired**.
- **REST responses containing relationships** — P9 caught a real `[]`-for-visits
  bug exactly there while status/shape stayed green.

### High value — each tests a control specified and never run

Non-HTTP entry points (`@Scheduled`, listeners, `CommandLineRunner`); real
per-endpoint authorization (not a global toggle); an outbound integration.

### Already rejected — do not re-propose

| Candidate | Verdict |
|---|---|
| `spring-attic/sagan` | **Gradle** (0 pom, 3 build.gradle). Right shape — Boot 2.5/2.6, Flyway, 28 controllers, 61 tests — **wrong tooling** |
| `spring-attic/spring-mvc-showcase` | **Not Boot** (no starter-parent), 0 `@Entity`, 0 security classes |

**Together they give the screen: it must look like Sagan and build like Showcase.**

### Deliverable

**Ranked candidates with per-criterion evidence and the command that proves each**
(`pom.xml` present, Boot parent version, `@Entity`/Flyway presence, test count,
`@Scheduled` count). **Do not deep-dive before the cheap screen passes.**

**Then Lead runs bump-and-compile on the top candidate to measure the remainder
before anyone commits** — the measure-before-choosing rule.

**Specimen choice remains `Architect→Operator`** (plan row P13). Research supplies
evidence; the pick is not yours or mine.

— Deputy
